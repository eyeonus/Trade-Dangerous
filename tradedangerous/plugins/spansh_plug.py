# tradedangerous/plugins/spansh_plug.py
# -----------------------------------------------------------------------------
# Spansh Import Plugin (new, defragmented)
#
# Behavioural contract:
# - Optimised for modify/update (churn-safe via service timestamps)
# - Streaming reader for huge top-level JSON array
# - Options: -O url=… | -O file=… (mutually exclusive), -O maxage=<float days>
# - JSON/intermediate in tmp/, CSV & .prices in data/
# - Warnings gated by verbosity; low-verbosity uses single-line progress
# - After import: export CSVs (incl. RareItem) and regenerate TradeDangerous.prices
# - Returns True from finish() to stop default flow
#
# DB/dialect specifics live in tradedangerous.db.utils (parse_ts, batch sizing, etc.)
# -----------------------------------------------------------------------------

from __future__ import annotations

import io
import os
import sys
import time
import ijson
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Mapping, Optional, Tuple, Iterable

# Framework modules
from .. import plugins, cache, csvexport  # provided by project

# DB helpers (dialect specifics live here)
from ..db import utils as db_utils
from ..db.lifecycle import ensure_fresh_db

# SQLAlchemy
from sqlalchemy import MetaData, Table, select, insert, update, func, and_, or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

DEFAULT_URL = "https://downloads.spansh.co.uk/galaxy_stations.json"


class ImportPlugin(plugins.ImportPluginBase):
    """
    Spansh galaxy dump importer:
      - Consumes galaxy_stations.json (local file or remote URL)
      - Updates System, Station, Ship/ShipVendor, Upgrade/UpgradeVendor, Item/StationItem
      - Respects per-service freshness & optional maxage (days)
      - Imports RareItem.csv via cache.processImportFile() AFTER systems/stations exist
      - Exports CSVs (+RareItem) and rebuilds TradeDangerous.prices
    """

    pluginInfo = {
        "name": "spansh",
        "author": "TD Team",
        "version": "2.0",
        "minimum-tb-version": "1.76",
        "description": "Imports Spansh galaxy dump and refreshes cache artefacts.",
    }

    # Correct option contract: dict name -> help text
    pluginOptions = {
        "url": "Remote URL to galaxy_stations.json (default if neither url nor file is given)",
        "file": "Local path to galaxy_stations.json; use '-' to read from stdin",
        "maxage": "Skip service sections older than <days> (float), evaluated per service",
        "pricesonly": "Skip import/exports; regenerate TradeDangerous.prices only (for testing).",
        "force_baseline": "If set, overwrite service blocks to Spansh baseline (from_live=0) and delete any extras.",
    }

    # ------------------------------
    # Construction & plumbing
    # ------------------------------
    def __init__(self, tdb, cmdenv):
        super().__init__(tdb, cmdenv)
        self.tdb = tdb
        self.tdenv = cmdenv
        self.session: Optional[Session] = None

        # Paths (data/tmp) from env/config; fall back defensively
        self.data_dir = Path(getattr(self.tdenv, "dataDir", getattr(self.tdb, "dataDir", "data"))).resolve()
        self.tmp_dir = Path(getattr(self.tdenv, "tmpDir", getattr(self.tdb, "tmpDir", "tmp"))).resolve()
        # Ensure directories exist without relying on helper order
        for p in (self.data_dir, self.tmp_dir):
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise CleanExit(f"Failed to create directory {p}: {e!r}")

        # Batch size decided AFTER session is opened (see finish())
        self.batch_size: Optional[int] = None

        # Verbosity gates
        self._is_tty = sys.stderr.isatty() or sys.stdout.isatty()
        self._debug_level = int(getattr(self.tdenv, "debug", 0) or 0)  # -v levels
        self._warn_enabled = bool(getattr(self.tdenv, "warn", None)) or (self._debug_level >= 3)

        # Progress state
        self._last_progress_time = 0.0

        # Station type mapping
        self._station_type_map = self._build_station_type_map()

    # --------------------------------------
    # Comparison Helpers
    # --------------------------------------
    
    def _apply_vendor_block_per_rules(
        self,
        t_vendor: Table,
        station_id: int,
        ids: Iterable[int],
        ts_sp: datetime,
        *,
        id_col: str,
    ) -> Tuple[int, int, int]:
        """
        Per-row rule for ShipVendor / UpgradeVendor:
          - If db.modified > ts_sp: leave row.
          - If db.modified == ts_sp: no-op.
          - If db.modified <  ts_sp: set modified = ts_sp.
        Deletions:
          - Remove rows missing in JSON if (db.modified <= ts_sp).
        Returns (insert_count, update_count, delete_count).
        """
        keep_ids = {int(x) for x in ids if x is not None}
        inserts = updates = deletes = 0

        # --- INSERT missing (batch) ---
        if keep_ids:
            # Find which of keep_ids are missing
            existing_ids = {
                int(r[0]) for r in self.session.execute(
                    select(getattr(t_vendor.c, id_col)).where(
                        and_(t_vendor.c.station_id == station_id,
                             getattr(t_vendor.c, id_col).in_(keep_ids))
                    )
                ).all()
            }
            to_insert = keep_ids - existing_ids
            if to_insert:
                self.session.execute(
                    insert(t_vendor),
                    [{id_col: vid, "station_id": station_id, "modified": ts_sp} for vid in to_insert]
                )
                inserts = len(to_insert)

        # --- UPDATE only those with modified < ts_sp (batch) ---
        if keep_ids:
            res = self.session.execute(
                update(t_vendor)
                .where(
                    and_(
                        t_vendor.c.station_id == station_id,
                        getattr(t_vendor.c, id_col).in_(keep_ids),
                        or_(t_vendor.c.modified == None, t_vendor.c.modified < ts_sp),
                    )
                )
                .values(modified=ts_sp)
            )
            # rowcount includes both existing rows (not inserts) whose modified was < ts_sp
            updates = int(res.rowcount or 0)

        # --- DELETE rows NOT in keep_ids, but only if <= ts_sp (single statement) ---
        res = self.session.execute(
            t_vendor.delete().where(
                and_(
                    t_vendor.c.station_id == station_id,
                    ~getattr(t_vendor.c, id_col).in_(keep_ids) if keep_ids else True,
                    or_(t_vendor.c.modified == None, t_vendor.c.modified <= ts_sp),
                )
            )
        )
        deletes = int(res.rowcount or 0)

        return inserts, updates, deletes


    def _sync_vendor_block_fast(
        self,
        tables: Dict[str, Table],
        *,
        station_id: int,
        entries: List[Dict[str, Any]],
        ts_sp: datetime,
        kind: str,  # "ship" or "module"
    ) -> Tuple[int, int]:
        """
        Fast, set-based vendor sync for a single station and one service (shipyard/outfitting).

        Returns: (number_of_inserts_or_updates_on_vendor_links, deletions_count).
        """
        if kind == "ship":
            t_master = tables["Ship"]
            t_vendor = tables["ShipVendor"]
            id_key = "shipId"
            name_key = "name"
            id_col = "ship_id"
            master_rows = [
                {"ship_id": e.get(id_key), "name": e.get(name_key)}
                for e in entries
                if isinstance(e, dict) and e.get(id_key) is not None and e.get(name_key) is not None
            ]
            keep_ids = {int(e.get(id_key)) for e in entries if isinstance(e, dict) and e.get(id_key) is not None}
        elif kind == "module":
            t_master = tables["Upgrade"]
            t_vendor = tables["UpgradeVendor"]
            id_key = "moduleId"
            id_col = "upgrade_id"
            master_rows = []
            keep_ids = set()
            for e in entries:
                if not isinstance(e, dict):
                    continue
                up_id = e.get(id_key)
                name = e.get("name")
                if up_id is None or name is None:
                    continue
                keep_ids.add(int(up_id))
                master_rows.append({
                    "upgrade_id": up_id,
                    "name": name,
                    "class": e.get("class"),
                    "rating": e.get("rating"),
                    "ship": e.get("ship"),
                })
        else:
            raise CleanExit(f"_sync_vendor_block_fast: unknown kind={kind!r}")

        # 1) Ensure master rows exist (simple upsert, no timestamp guards)
        if master_rows:
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_simple(
                    self.session, t_master, rows=master_rows,
                    key_cols=(list(master_rows[0].keys())[0],),
                    update_cols=tuple([c for c in master_rows[0].keys() if c not in (id_col, "ship_id", "upgrade_id")]),
                )
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_simple(
                    self.session, t_master, rows=master_rows,
                    key_cols=(list(master_rows[0].keys())[0],),
                    update_cols=tuple([c for c in master_rows[0].keys() if c not in (id_col, "ship_id", "upgrade_id")]),
                )
            else:
                for r in master_rows:
                    pk = list(r.keys())[0]
                    exists = self.session.execute(
                        select(getattr(t_master.c, pk)).where(getattr(t_master.c, pk) == r[pk])
                    ).first()
                    if exists is None:
                        self.session.execute(insert(t_master).values(**r))
                    else:
                        upd = {k: v for k, v in r.items() if k != pk}
                        if upd:
                            self.session.execute(
                                update(t_master).where(getattr(t_master.c, pk) == r[pk]).values(**upd)
                            )

        # 2) Compute effective inserts/updates on vendor links (pre-check modified), then upsert
        wrote = 0
        if keep_ids:
            existing = {
                int(r[0]): (r[1] or None)
                for r in self.session.execute(
                    select(getattr(t_vendor.c, id_col), t_vendor.c.modified).where(
                        and_(t_vendor.c.station_id == station_id, getattr(t_vendor.c, id_col).in_(keep_ids))
                    )
                ).all()
            }
            to_insert = keep_ids - set(existing.keys())
            to_update = {
                vid for vid, mod in existing.items()
                if (mod is None) or (ts_sp is not None and ts_sp > mod)
            }
            wrote = len(to_insert) + len(to_update)

            vendor_rows = [{id_col: vid, "station_id": station_id, "modified": ts_sp} for vid in keep_ids]
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_modified(
                    self.session, t_vendor, rows=vendor_rows,
                    key_cols=(id_col, "station_id"),
                    modified_col="modified",
                    update_cols=(),
                )
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_modified(
                    self.session, t_vendor, rows=vendor_rows,
                    key_cols=(id_col, "station_id"),
                    modified_col="modified",
                    update_cols=(),
                )
            else:
                for r in vendor_rows:
                    cond = and_(getattr(t_vendor.c, id_col) == r[id_col], t_vendor.c.station_id == station_id)
                    cur = self.session.execute(select(t_vendor.c.modified).where(cond)).first()
                    if cur is None:
                        self.session.execute(insert(t_vendor).values(**r))
                    else:
                        dbm = cur[0]
                        if dbm is None or r["modified"] > dbm:
                            self.session.execute(update(t_vendor).where(cond).values(modified=r["modified"]))

        # 3) Delete extras missing in JSON (never delete newer-than-JSON)
        deleted = 0
        if keep_ids:
            del_stmt = t_vendor.delete().where(
                and_(
                    t_vendor.c.station_id == station_id,
                    ~getattr(t_vendor.c, id_col).in_(keep_ids),
                    (t_vendor.c.modified.is_(None)) | (t_vendor.c.modified <= ts_sp),
                )
            )
            res = self.session.execute(del_stmt)
            try:
                deleted = int(res.rowcount or 0)
            except Exception:
                deleted = 0

        return wrote, deleted
        
    def _cleanup_absent_stations(self, tables: Dict[str, Table], present_station_ids: set[int], json_ts: datetime) -> Tuple[int, int, int]:
        """
        After streaming, delete baseline rows for stations absent from the JSON
        if the JSON timestamp is >= row.modified. Never delete newer-than-JSON rows.
        Returns (market_del, outfit_del, ship_del) counts.
        """
        t_si, t_uv, t_sv, t_st = tables["StationItem"], tables["UpgradeVendor"], tables["ShipVendor"], tables["Station"]

        # All station ids in DB
        all_sids = [int(r[0]) for r in self.session.execute(select(t_st.c.station_id)).all()]
        absent = [sid for sid in all_sids if sid not in present_station_ids]
        if not absent:
            return (0, 0, 0)

        # Markets: delete baseline rows (from_live=0) with modified <= json_ts
        del_m = self.session.execute(
            t_si.delete().where(
                and_(
                    t_si.c.station_id.in_(absent),
                    t_si.c.from_live == 0,
                    or_(t_si.c.modified == None, t_si.c.modified <= json_ts),
                )
            )
        ).rowcount or 0

        # Vendors: delete rows with modified <= json_ts
        del_u = self.session.execute(
            tables["UpgradeVendor"].delete().where(
                and_(t_uv.c.station_id.in_(absent), or_(t_uv.c.modified == None, t_uv.c.modified <= json_ts))
            )
        ).rowcount or 0
        del_s = self.session.execute(
            tables["ShipVendor"].delete().where(
                and_(t_sv.c.station_id.in_(absent), or_(t_sv.c.modified == None, t_sv.c.modified <= json_ts))
            )
        ).rowcount or 0

        return (int(del_m), int(del_u), int(del_s))
        
    def _sync_market_block_fast(
        self,
        tables: Dict[str, Table],
        categories: Dict[str, int],
        *,
        station_id: int,
        commodities: List[Dict[str, Any]],
        ts_sp: datetime,
    ) -> Tuple[int, int]:
        """
        Fast, set-based market sync for one station.

        Returns: (number_of_inserts_or_updates_on_StationItem, deletions_count).
        """
        t_item, t_si = tables["Item"], tables["StationItem"]

        item_rows: List[Dict[str, Any]] = []
        link_rows: List[Dict[str, Any]] = []
        keep_ids: set[int] = set()

        for co in commodities:
            if not isinstance(co, dict):
                continue
            fdev_id = co.get("commodityId")
            name = co.get("name")
            cat_name = co.get("category")
            if fdev_id is None or name is None or cat_name is None:
                continue

            cat_id = categories.get(str(cat_name).lower())
            if cat_id is None:
                raise CleanExit(f'Unknown commodity category "{cat_name}"')

            keep_ids.add(int(fdev_id))
            item_rows.append({
                "item_id": fdev_id,
                "name": name,
                "category_id": cat_id,
                "fdev_id": fdev_id,
                "ui_order": 0,
            })

            demand = co.get("demand")
            supply = co.get("supply")
            buy = co.get("buyPrice")
            sell = co.get("sellPrice")

            link_rows.append({
                "station_id": station_id,
                "item_id": fdev_id,
                "demand_price": sell,
                "demand_units": demand,
                "demand_level": -1,
                "supply_price": buy,
                "supply_units": supply,
                "supply_level": -1,
                "from_live": 0,
                "modified": ts_sp,
            })

        # 1) Upsert Items (simple)
        if item_rows:
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_simple(
                    self.session, t_item, rows=item_rows,
                    key_cols=("item_id",),
                    update_cols=("name", "category_id", "fdev_id", "ui_order"),
                )
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_simple(
                    self.session, t_item, rows=item_rows,
                    key_cols=("item_id",),
                    update_cols=("name", "category_id", "fdev_id", "ui_order"),
                )
            else:
                for r in item_rows:
                    exists = self.session.execute(
                        select(t_item.c.item_id).where(t_item.c.item_id == r["item_id"])
                    ).first()
                    if exists is None:
                        self.session.execute(insert(t_item).values(**r))
                    else:
                        self.session.execute(
                            update(t_item).where(t_item.c.item_id == r["item_id"]).values(
                                name=r["name"], category_id=r["category_id"], fdev_id=r["fdev_id"], ui_order=r["ui_order"]
                            )
                        )

        # 2) Compute effective inserts/updates for StationItem (pre-check modified), then upsert
        wrote = 0
        if link_rows:
            existing = {
                (int(r[0]), int(r[1])): (r[2] or None)
                for r in self.session.execute(
                    select(t_si.c.station_id, t_si.c.item_id, t_si.c.modified).where(
                        and_(t_si.c.station_id == station_id, t_si.c.item_id.in_(keep_ids))
                    )
                ).all()
            }
            to_insert = {
                (station_id, rid) for rid in keep_ids
                if (station_id, rid) not in existing
            }
            to_update = {
                (station_id, rid) for rid, mod in ((rid, existing.get((station_id, rid))) for rid in keep_ids)
                if (mod is None) or (ts_sp is not None and ts_sp > mod)
            }
            wrote = len(to_insert) + len(to_update)

            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_modified(
                    self.session, t_si, rows=link_rows,
                    key_cols=("station_id", "item_id"),
                    modified_col="modified",
                    update_cols=("demand_price", "demand_units", "demand_level",
                                 "supply_price", "supply_units", "supply_level", "from_live"),
                )
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_modified(
                    self.session, t_si, rows=link_rows,
                    key_cols=("station_id", "item_id"),
                    modified_col="modified",
                    update_cols=("demand_price", "demand_units", "demand_level",
                                 "supply_price", "supply_units", "supply_level", "from_live"),
                )
            else:
                for r in link_rows:
                    row = self.session.execute(
                        select(t_si.c.modified).where(and_(
                            t_si.c.station_id == r["station_id"],
                            t_si.c.item_id == r["item_id"],
                        ))
                    ).first()
                    if row is None:
                        self.session.execute(insert(t_si).values(**r))
                    else:
                        dbm = row[0]
                        if dbm is None or r["modified"] > dbm:
                            self.session.execute(
                                update(t_si)
                                .where(and_(t_si.c.station_id == r["station_id"], t_si.c.item_id == r["item_id"]))
                                .values(**r)
                            )

        # 3) Delete baseline rows missing from JSON, not newer than ts_sp
        delc = 0
        base_where = and_(
            t_si.c.station_id == station_id,
            t_si.c.from_live == 0,
            or_(t_si.c.modified == None, t_si.c.modified <= ts_sp),
        )
        if keep_ids:
            delete_stmt = t_si.delete().where(and_(base_where, ~t_si.c.item_id.in_(keep_ids)))
        else:
            delete_stmt = t_si.delete().where(base_where)

        res = self.session.execute(delete_stmt)
        try:
            delc = int(res.rowcount or 0)
        except Exception:
            delc = 0

        return wrote, delc


    # ------------------------------
    # Lifecycle hooks
    # ------------------------------
    def run(self) -> bool:
        """
        Full orchestrator: acquisition → bootstrap → buildcache → import → rares → export.
        Returning False stops the import command's default flow (prevents
        tdb.reloadCache() and any early RareItem processing).
        """
        started = time.time()
        
        # prices-only fast path
        if self.getOption("pricesonly"):
            try:
                self._print("Regenerating TradeDangerous.prices …")
                cache.regeneratePricesFile(self.tdb, self.tdenv)
                self._print("Prices file generated.")
            except Exception as e:
                self._error(f"Prices regeneration failed: {e!r}")
                return False
            return False

        # Acquire source
        try:
            source_path = self._acquire_source()
        except CleanExit as ce:
            self._warn(str(ce))
            return False
        except Exception as e:
            self._error(f"Acquisition failed: {e!r}")
            return False

        # Bootstrap DB
        ri_path = Path(self.tdb.dataPath, "RareItem.csv")
        rib_path = ri_path.with_suffix(".tmp")
        try:
            if ri_path.exists():
                if rib_path.exists():
                    rib_path.unlink()
                ri_path.rename(rib_path)

            backend = getattr(self.tdb.engine.dialect, "name", None) or "unknown"
            data_dir = Path(getattr(self.tdenv, "dataDir", getattr(self.tdb, "dataDir", "data")))
            metadata = getattr(self.tdb, "metadata", None)

            summary = ensure_fresh_db(
                backend=backend,
                engine=self.tdb.engine,
                data_dir=data_dir,
                metadata=metadata,
                mode="auto",
                tdb=self.tdb,
                tdenv=self.tdenv,
            )
            self._print(f"DB bootstrap: action={summary.get('action')} reason={summary.get('reason', 'ok')} backend={summary.get('backend')}")
        except Exception as e:
            self._error(f"Database bootstrap failed: {e!r}")
            return False
        finally:
            if rib_path.exists():
                if ri_path.exists():
                    ri_path.unlink()
                rib_path.rename(ri_path)

        # Session + batch
        try:
            self.session = self._open_session()
            self.batch_size = self._resolve_batch_size()
        except Exception as e:
            self._error(f"Failed to open DB session: {e!r}")
            return False

        # Reflect + categories
        try:
            tables = self._reflect_tables(self.session.get_bind())
        except Exception as e:
            self._error(f"Failed to reflect tables: {e!r}")
            return False

        try:
            categories = self._load_categories(self.session, tables)
        except Exception as e:
            self._error(f"Failed to load categories: {e!r}")
            return False

        # Import Spansh
        try:
            if self._debug_level < 1:
                self._print("This will take at least several minutes...")
                self._print("You can increase verbosity (-v) to get a sense of progress")
            self._print("Importing spansh data")
            stats = self._import_stream(source_path, categories, tables)
            self._end_live_status()
            # Summarise by *stations* (evaluated = kept + writes)
            mk_e = stats.get("market_writes", 0) + stats.get("market_stations", 0)
            of_e = stats.get("outfit_writes", 0) + stats.get("outfit_stations", 0)
            sh_e = stats.get("ship_writes", 0) + stats.get("ship_stations", 0)
            self._print(
                f"Import complete — systems: {stats.get('systems',0):,}  "
                f"stations: {stats.get('stations',0):,}  "
                f"evaluated: markets≈{mk_e:,} outfitters≈{of_e:,} shipyards≈{sh_e:,}  "
                f"kept: markets≈{stats.get('market_stations',0):,} outfitters≈{stats.get('outfit_stations',0):,} shipyards≈{stats.get('ship_stations',0):,}"
            )
        except CleanExit as ce:
            self._warn(str(ce))
            self._safe_close_session()
            return False
        except Exception as e:
            self._error(f"Import failed: {e!r}")
            self._safe_close_session()
            return False

        # Enforce Item.ui_order
        try:
            t0 = time.time()
            self._enforce_ui_order(self.session, tables)
            self._print(f"ui_order enforced in {time.time()-t0:.2f}s")
        except Exception as e:
            self._error(f"ui_order enforcement failed: {e!r}")
            self._safe_close_session()
            return False

        # Final commit for import phase
        try:
            self.session.commit()
        except Exception as e:
            self._warn(f"Commit failed at end of import; rolling back. Cause: {e!r}")
            self.session.rollback()
            self._safe_close_session()
            return False

        self._safe_close_session()

        # RareItems
        try:
            t0 = time.time()
            self._import_rareitems()
            self._print(f"Rares imported in {time.time()-t0:.2f}s")
        except CleanExit as ce:
            self._warn(str(ce))
            return False
        except Exception as e:
            self._error(f"RareItem import failed: {e!r}")
            return False

        # Export + prices
        try:
            t0 = time.time()
            self._export_cache()
            self._print(f"Cache export completed in {time.time()-t0:.2f}s")
        except Exception as e:
            self._error(f"Export failed: {e!r}")
            return False

        # Final summary
        elapsed = self._format_hms(time.time() - started)
        self._print(f"{elapsed}  Done")
        return False


    def finish(self) -> bool:
        """No-op: handled in run(); finish() won’t be called."""
        return True
        
    # ------------------------------
    # Acquisition (url/file/stdin)
    # ------------------------------
    def _acquire_source(self) -> Path:
        """Return a readable filesystem path to the JSON source (tmp/)."""
        url = self.getOption("url")
        file_ = self.getOption("file")
        cache_path = self.tmp_dir / "galaxy_stations.json"

        if file_:
            if file_ == "-":
                self._print("Reading Spansh dump from stdin …")
                self._write_stream_to_file(sys.stdin.buffer, cache_path)
                return cache_path
            src = Path(file_)
            if not src.exists() or not src.is_file():
                raise CleanExit(f"Local file not found: {src}")
            return src.resolve()

        if not url:
            url = DEFAULT_URL

        return self._download_with_cache(url, cache_path)

    def _download_with_cache(self, url: str, cache_path: Path) -> Path:
        """Conditional download with HEAD Last-Modified and atomic .part."""
        import urllib.request
        from email.utils import parsedate_to_datetime

        remote_lm: Optional[datetime] = None
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                lm_header = resp.headers.get("Last-Modified")
                if lm_header:
                    try:
                        remote_lm = parsedate_to_datetime(lm_header).astimezone(timezone.utc).replace(tzinfo=None)
                    except Exception:
                        remote_lm = None
        except Exception:
            pass

        if cache_path.exists() and remote_lm:
            local_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc).replace(tzinfo=None)
            if local_mtime >= remote_lm:
                self._print("Remote not newer; using cached file")
                return cache_path

        self._print(f"Downloading Spansh dump from {url} …")
        part = cache_path.with_suffix(cache_path.suffix + ".part")
        if part.exists():
            try:
                part.unlink()
            except Exception:
                pass

        req = urllib.request.Request(url, method="GET")
        connect_timeout = 30
        read_timeout = 60
        chunk = 8 * 1024 * 1024  # 8 MiB

        try:
            with urllib.request.urlopen(req, timeout=connect_timeout) as resp, open(part, "wb") as fh:
                total_hdr = resp.headers.get("Content-Length")
                total = int(total_hdr) if total_hdr and total_hdr.isdigit() else None
                downloaded = 0
                start = time.time()

                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    fh.write(data)
                    downloaded += len(data)
                    self._download_progress(downloaded, total, start)

            part.replace(cache_path)

            # Set mtime to Last-Modified if present on GET
            lm_header = None
            try:
                with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=10) as head2:
                    lm_header = head2.headers.get("Last-Modified")
            except Exception:
                pass
            if lm_header:
                try:
                    from email.utils import parsedate_to_datetime
                    got_lm = parsedate_to_datetime(lm_header).astimezone(timezone.utc).replace(tzinfo=None)
                    ts = got_lm.replace(tzinfo=timezone.utc).timestamp()
                    os.utime(cache_path, (ts, ts))
                except Exception:
                    pass

        except Exception as e:
            try:
                if part.exists():
                    part.unlink()
            except Exception:
                pass
            raise CleanExit(f"Download failed or timed out; skipping run ({e!r})")

        self._print(f'Download complete, saved to "{cache_path}"')
        return cache_path

    def _download_progress(self, downloaded: int, total: Optional[int], start_ts: float) -> None:
        now = time.time()
        if now - self._last_progress_time < 0.5 and self._debug_level < 1:
            return
        self._last_progress_time = now

        rate = downloaded / max(now - start_ts, 1e-9)
        if total:
            pct = (downloaded / total) * 100.0
            msg = f"Downloading Spansh: {self._fmt_bytes(downloaded)} / {self._fmt_bytes(total)} ({pct:5.1f}%)  {self._fmt_bytes(rate)}/s"
        else:
            msg = f"Downloading Spansh: {self._fmt_bytes(downloaded)} read  {self._fmt_bytes(rate)}/s"
        self._live_status(msg)

    def _parse_progress(self, consumed_bytes: int, start_ts: float, *, min_interval: float = 0.5) -> None:
        """
        Update parse progress (bytes + rate). Standalone heartbeat until importing begins.
        """
        now = time.time()
        if now - self._last_progress_time < min_interval:
            elapsed = max(now - start_ts, 1e-9)
            self._parse_bytes = consumed_bytes
            self._parse_rate = consumed_bytes / elapsed
            return
        self._last_progress_time = now

        if not hasattr(self, "_parse_bytes"):
            self._parse_bytes = 0
        if not hasattr(self, "_parse_rate"):
            self._parse_rate = 0.0
        if not hasattr(self, "_started_importing"):
            self._started_importing = False

        elapsed = max(now - start_ts, 1e-9)
        self._parse_bytes = consumed_bytes
        self._parse_rate = consumed_bytes / elapsed

        if not self._started_importing:
            msg = f"Parsing Spansh: {self._fmt_bytes(self._parse_bytes)} read  {self._fmt_bytes(self._parse_rate)}/s"
            self._live_status(msg)

    def _write_stream_to_file(self, stream: io.BufferedReader, dest: Path) -> None:
        part = dest.with_suffix(dest.suffix + ".part")
        if part.exists():
            try:
                part.unlink()
            except Exception:
                pass
        written = 0
        start = time.time()
        try:
            with open(part, "wb") as fh:
                while True:
                    buf = stream.read(8 * 1024 * 1024)
                    if not buf:
                        break
                    fh.write(buf)
                    written += len(buf)
                    self._download_progress(written, None, start)
            part.replace(dest)
        except Exception as e:
            try:
                if part.exists():
                    part.unlink()
            except Exception:
                pass
            raise CleanExit(f"Failed to read stdin into tmp file: {e!r})")

    # ------------------------------
    # DB session / reflection
    # ------------------------------
    def _open_session(self) -> Session:
        """
        Create a DB session and apply per-connection bulk settings.
        """
        if hasattr(self.tdb, "Session") and callable(self.tdb.Session):
            sess = self.tdb.Session()
        elif hasattr(db_utils, "get_session"):
            sess = db_utils.get_session(self.tdb.engine)
        else:
            raise RuntimeError("No Session factory available")

        # SQLite pragmas (non-fatal)
        try:
            if db_utils.is_sqlite(sess):
                db_utils.sqlite_set_bulk_pragmas(sess)
        except Exception:
            pass

        # MySQL/MariaDB session tuning (non-fatal)
        try:
            if db_utils.is_mysql(sess):
                db_utils.mysql_set_bulk_session(sess)
        except Exception:
            pass

        return sess

    def _reflect_tables(self, engine: Engine) -> Dict[str, Table]:
        meta = MetaData()
        names = [
            "System", "Station", "Item", "Category", "StationItem",
            "Ship", "ShipVendor", "Upgrade", "UpgradeVendor",
        ]
        return {n: Table(n, meta, autoload_with=engine) for n in names}

    # ------------------------------
    # Import (streaming JSON → upserts)
    # ------------------------------
    def _import_stream(self, source_path: Path, categories: Dict[str, int], tables: Dict[str, Table]) -> Dict[str, int]:
        """
        Streaming importer with service-level maxage gating (FK-safe), using per-row rules.
        """
        batch_ops = 0
        stats = {
            "systems": 0, "stations": 0,
            "market_stations": 0, "outfit_stations": 0, "ship_stations": 0,
            "market_writes": 0, "outfit_writes": 0, "ship_writes": 0,
            "commodities": 0,
        }

        maxage_days = float(self.getOption("maxage")) if self.getOption("maxage") else None
        maxage_td = timedelta(days=maxage_days) if maxage_days is not None else None
        now_utc = datetime.utcnow()

        try:
            json_ts = datetime.fromtimestamp(os.path.getmtime(source_path), tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            json_ts = datetime.utcfromtimestamp(0)

        seen_station_ids: set[int] = set()
        force_baseline = bool(self.getOption("force_baseline"))

        def recent(ts: Optional[datetime]) -> bool:
            if ts is None:
                return False if maxage_td is not None else True
            if maxage_td is None:
                return True
            return (now_utc - ts) <= maxage_td

        def svc_ts(st: Dict[str, Any], key: str) -> Optional[datetime]:
            obj = st.get(key) or {}
            if not isinstance(obj, dict):
                return None
            return self._parse_ts(obj.get("updateTime"))

        with open(source_path, "rb") as fh:
            for sys_idx, system_obj in enumerate(self._iter_top_level_json_array(fh), 1):
                sys_id64 = system_obj.get("id64")
                sys_name = system_obj.get("name")
                coords = system_obj.get("coords") or {}
                if sys_id64 is None or sys_name is None or not isinstance(coords, dict):
                    if self._debug_level >= 3:
                        self._warn(f"Skipping malformed system object at index {sys_idx}")
                    continue

                stations: List[Dict[str, Any]] = []
                if isinstance(system_obj.get("stations"), list):
                    stations.extend(system_obj["stations"])
                bodies = system_obj.get("bodies") or []
                if isinstance(bodies, list):
                    for b in bodies:
                        if isinstance(b, dict):
                            stl = b.get("stations")
                            if isinstance(stl, list):
                                stations.extend(stl)

                def station_fresh_any(st: Dict[str, Any]) -> bool:
                    raw_services = st.get("services") or []
                    if not isinstance(raw_services, list):
                        return False
                    svcset = {s.strip().lower() for s in raw_services if isinstance(s, str)}
                    has_market = "market" in svcset
                    has_outfit = "outfitting" in svcset
                    has_ship = "shipyard" in svcset
                    if not (has_market or has_outfit or has_ship):
                        return False
                    mkt_ts = svc_ts(st, "market") if has_market else None
                    outf_ts = svc_ts(st, "outfitting") if has_outfit else None
                    ship_ts = svc_ts(st, "shipyard") if has_ship else None
                    return any(recent(t) for t in (mkt_ts, outf_ts, ship_ts))

                if maxage_td is not None and not any(station_fresh_any(st) for st in stations):
                    continue

                # Upsert System
                x, y, z = coords.get("x"), coords.get("y"), coords.get("z")
                sys_date = self._parse_ts(system_obj.get("date"))
                self._upsert_system(tables["System"], sys_id64, sys_name, x, y, z, sys_date)
                stats["systems"] += 1
                batch_ops += 1

                imported_station_modifieds: List[datetime] = []

                # Stations
                for st in stations:
                    station_id = st.get("id")
                    st_name = st.get("name")
                    if station_id is None or st_name is None:
                        continue
                    try:
                        seen_station_ids.add(int(station_id))
                    except Exception:
                        pass

                    raw_services = st.get("services") or []
                    if not isinstance(raw_services, list):
                        continue
                    services = {s.strip().lower(): s for s in raw_services if isinstance(s, str)}

                    has_market = "market" in services
                    has_outfit = "outfitting" in services
                    has_ship = "shipyard" in services
                    if not (has_market or has_outfit or has_ship):
                        continue

                    ship_ts = svc_ts(st, "shipyard") if has_ship else None
                    outf_ts = svc_ts(st, "outfitting") if has_outfit else None
                    mkt_ts = svc_ts(st, "market") if has_market else None

                    ship_fresh = recent(ship_ts)
                    outf_fresh = recent(outf_ts)
                    mkt_fresh = recent(mkt_ts)

                    if not (ship_fresh or outf_fresh or mkt_fresh):
                        continue

                    # Station fields
                    dist = st.get("distanceToArrival")
                    ls_from_star = int(round(dist)) if isinstance(dist, (int, float)) else 999999
                    type_name = st.get("type")
                    landing = st.get("landingPads") or {}
                    type_id, planetary = self._map_station_type(type_name)
                    max_pad = self._derive_pad_size(landing)

                    svcset = set(services.keys())
                    has_rearm = ("restock" in svcset) or ("rearm" in svcset)
                    has_blackmkt = ("black market" in svcset) or ("blackmarket" in svcset)
                    has_refuel = "refuel" in svcset
                    has_repair = "repair" in svcset

                    sflags = {
                        "market": "Y" if has_market else "N",
                        "blackmarket": "Y" if has_blackmkt else "N",
                        "shipyard": "Y" if has_ship else "N",
                        "outfitting": "Y" if has_outfit else "N",
                        "rearm": "Y" if has_rearm else "N",
                        "refuel": "Y" if has_refuel else "N",
                        "repair": "Y" if has_repair else "N",
                        "planetary": "Y" if planetary else "N",
                    }

                    st_effective_mod = max(
                        [t for t, ok in ((mkt_ts, mkt_fresh), (outf_ts, outf_fresh), (ship_ts, ship_fresh)) if ok and t is not None],
                        default=None
                    )

                    self._upsert_station(
                        tables["Station"],
                        station_id, sys_id64, st_name, ls_from_star,
                        max_pad, type_id, planetary, sflags, st_effective_mod
                    )
                    stats["stations"] += 1
                    batch_ops += 1
                    if st_effective_mod is not None:
                        imported_station_modifieds.append(st_effective_mod)

                    # Shipyard
                    if has_ship and ship_fresh:
                        ships = (st.get("shipyard") or {}).get("ships") or []
                        if isinstance(ships, list) and ships:
                            if force_baseline:
                                wrote = self._upsert_shipyard(tables, station_id, ships, ship_ts)
                                _, _, delc = self._apply_vendor_block_per_rules(
                                    tables["ShipVendor"], station_id,
                                    (s.get("shipId") for s in ships if isinstance(s, dict)),
                                    ship_ts, id_col="ship_id",
                                )
                                if wrote or delc:
                                    stats["ship_writes"] += 1
                                batch_ops += (wrote + delc)
                            else:
                                wrote, delc = self._sync_vendor_block_fast(
                                    tables, station_id=station_id, entries=ships, ts_sp=ship_ts, kind="ship"
                                )
                                if wrote or delc:
                                    stats["ship_writes"] += 1
                                stats["ship_stations"] += 1
                                batch_ops += (wrote + delc)
                        else:
                            stats["ship_stations"] += 1

                    # Outfitting
                    if has_outfit and outf_fresh:
                        modules = (st.get("outfitting") or {}).get("modules") or []
                        if isinstance(modules, list) and modules:
                            if force_baseline:
                                wrote = self._upsert_outfitting(tables, station_id, modules, outf_ts)
                                _, _, delc = self._apply_vendor_block_per_rules(
                                    tables["UpgradeVendor"], station_id,
                                    (m.get("moduleId") for m in modules if isinstance(m, dict)),
                                    outf_ts, id_col="upgrade_id",
                                )
                                if wrote or delc:
                                    stats["outfit_writes"] += 1
                                batch_ops += (wrote + delc)
                            else:
                                wrote, delc = self._sync_vendor_block_fast(
                                    tables, station_id=station_id, entries=modules, ts_sp=outf_ts, kind="module"
                                )
                                if wrote or delc:
                                    stats["outfit_writes"] += 1
                                stats["outfit_stations"] += 1
                                batch_ops += (wrote + delc)
                        else:
                            stats["outfit_stations"] += 1

                    # MARKET
                    if has_market and mkt_fresh:
                        commodities = (st.get("market") or {}).get("commodities") or []
                        if isinstance(commodities, list) and commodities:
                            if force_baseline:
                                # Overwrite all + delete extras (from_live=0 in helper)
                                wrote_i, wrote_si = self._upsert_market(tables, categories, station_id, commodities, mkt_ts)
                                # Remove any extras unconditionally (baseline reset)
                                t_si = tables["StationItem"]
                                keep_ids = {
                                    int(co.get("commodityId"))
                                    for co in commodities if isinstance(co, dict) and co.get("commodityId") is not None
                                }
                                if keep_ids:
                                    self.session.execute(
                                        t_si.delete().where(and_(t_si.c.station_id == station_id, ~t_si.c.item_id.in_(keep_ids)))
                                    )
                                stats["commodities"] += wrote_si
                                # Treat baseline overwrite as a write at the station
                                if wrote_si or wrote_i:
                                    stats["market_writes"] += 1
                                stats["market_stations"] += 1
                                batch_ops += (wrote_i + wrote_si)
                            else:
                                wrote_links, delc = self._sync_market_block_fast(
                                    tables, categories,
                                    station_id=station_id,
                                    commodities=commodities,
                                    ts_sp=mkt_ts,
                                )
                                if wrote_links or delc:
                                    stats["market_writes"] += 1
                                stats["market_stations"] += 1
                                batch_ops += (wrote_links + delc)
                        else:
                            # Market service present and fresh but no commodities array
                            stats["market_stations"] += 1

                    # Progress & batching
                    self._progress_line(stats)
                    if (self.batch_size is not None) and self.batch_size > 0 and (batch_ops >= self.batch_size):
                        t0 = time.time()
                        try:
                            self.session.commit()
                        except Exception as e:
                            self.session.rollback()
                            raise CleanExit(f"Commit failed; rolled back. Cause: {e!r}")
                        finally:
                            batch_ops = 0
                        if self._debug_level >= 3:
                            self._print(f"commit: {self.batch_size} ops in {time.time() - t0:.2f}s")

                # Finalize system.modified
                sys_modified_final = max(imported_station_modifieds) if imported_station_modifieds else sys_date
                self._upsert_system(tables["System"], sys_id64, sys_name, x, y, z, sys_modified_final)

        # Absent-station cleanup
        try:
            dm, du, ds = self._cleanup_absent_stations(tables, seen_station_ids, json_ts)
            if self._debug_level >= 2:
                self._print(f"Cleanup (absent stations): market_del={dm:,} outfit_del={du:,} ship_del={ds:,}")
        except Exception as e:
            self._warn(f"Absent-station cleanup skipped due to error: {e!r}")

        return stats



    # ------------------------------
    # Upsert helpers
    # ------------------------------
    def _upsert_system(
        self, t_system: Table, system_id: int, name: str,
        x: Optional[float], y: Optional[float], z: Optional[float],
        modified: Optional[datetime],
    ) -> None:
        """
        Upsert System with timestamp guard.
        'added' policy (when column exists):
          - INSERT: set added=20 (EDSM).
          - UPDATE: do not overwrite, unless existing added IS NULL → set to 20.
        """
        if modified is None:
            modified = datetime.utcfromtimestamp(0)

        has_added_col = hasattr(t_system.c, "added")

        row = {
            "system_id": system_id,
            "name": name,
            "pos_x": x, "pos_y": y, "pos_z": z,
            "modified": modified,
        }
        if has_added_col:
            row["added"] = 20  # EDSM on INSERT

        if db_utils.is_sqlite(self.session):
            db_utils.sqlite_upsert_modified(
                self.session, t_system,
                rows=[row],
                key_cols=("system_id",),
                modified_col="modified",
                update_cols=("name", "pos_x", "pos_y", "pos_z"),
            )
            if has_added_col:
                self.session.execute(
                    update(t_system)
                    .where((t_system.c.system_id == system_id) & (t_system.c.added.is_(None)))
                    .values(added=20)
                )
            return

        if db_utils.is_mysql(self.session):
            db_utils.mysql_upsert_modified(
                self.session, t_system,
                rows=[row],
                key_cols=("system_id",),
                modified_col="modified",
                update_cols=("name", "pos_x", "pos_y", "pos_z"),
            )
            if has_added_col:
                self.session.execute(
                    update(t_system)
                    .where((t_system.c.system_id == system_id) & (t_system.c.added.is_(None)))
                    .values(added=20)
                )
            return

        # Generic fallback
        sel_cols = [t_system.c.modified]
        if has_added_col:
            sel_cols.append(t_system.c.added)
        existing = self.session.execute(
            select(*sel_cols).where(t_system.c.system_id == system_id)
        ).first()

        if existing is None:
            self.session.execute(insert(t_system).values(**row))
        else:
            db_modified = existing[0]
            values = {"name": name, "pos_x": x, "pos_y": y, "pos_z": z}
            if db_modified is None or modified > db_modified:
                values["modified"] = modified
            self.session.execute(
                update(t_system)
                .where(t_system.c.system_id == system_id)
                .values(**values)
            )
            if has_added_col:
                db_added = existing[1] if len(existing) > 1 else None
                if db_added is None:
                    self.session.execute(
                        update(t_system)
                        .where((t_system.c.system_id == system_id) & (t_system.c.added.is_(None)))
                        .values(added=20)
                    )

    def _upsert_station(
        self, t_station: Table, station_id: int, system_id: int, name: str,
        ls_from_star: Optional[float], max_pad: str, type_id: int, planetary: str,
        sflags: Dict[str, str], modified: Optional[datetime],
    ) -> None:
        """
        Upsert Station with timestamp guard.
        """
        if modified is None:
            modified = datetime.utcfromtimestamp(0)

        if db_utils.is_sqlite(self.session):
            db_utils.sqlite_upsert_modified(
                self.session, t_station,
                rows=[{
                    "station_id": station_id,
                    "system_id": system_id,
                    "name": name,
                    "ls_from_star": ls_from_star,
                    "max_pad_size": max_pad,
                    "type_id": type_id,
                    "planetary": planetary,
                    "market": sflags["market"],
                    "blackmarket": sflags["blackmarket"],
                    "shipyard": sflags["shipyard"],
                    "outfitting": sflags["outfitting"],
                    "rearm": sflags["rearm"],
                    "refuel": sflags["refuel"],
                    "repair": sflags["repair"],
                    "modified": modified,
                }],
                key_cols=("station_id",),
                modified_col="modified",
                update_cols=(
                    "system_id", "name", "ls_from_star", "max_pad_size", "type_id", "planetary",
                    "market", "blackmarket", "shipyard", "outfitting", "rearm", "refuel", "repair",
                ),
            )
            return

        if db_utils.is_mysql(self.session):
            db_utils.mysql_upsert_modified(
                self.session, t_station,
                rows=[{
                    "station_id": station_id,
                    "system_id": system_id,
                    "name": name,
                    "ls_from_star": ls_from_star,
                    "max_pad_size": max_pad,
                    "type_id": type_id,
                    "planetary": planetary,
                    "market": sflags["market"],
                    "blackmarket": sflags["blackmarket"],
                    "shipyard": sflags["shipyard"],
                    "outfitting": sflags["outfitting"],
                    "rearm": sflags["rearm"],
                    "refuel": sflags["refuel"],
                    "repair": sflags["repair"],
                    "modified": modified,
                }],
                key_cols=("station_id",),
                modified_col="modified",
                update_cols=(
                    "system_id", "name", "ls_from_star", "max_pad_size", "type_id", "planetary",
                    "market", "blackmarket", "shipyard", "outfitting", "rearm", "refuel", "repair",
                ),
            )
            return

        # Generic fallback
        row = self.session.execute(
            select(t_station.c.system_id, t_station.c.modified)
            .where(t_station.c.station_id == station_id)
        ).first()

        if row is None:
            self.session.execute(
                insert(t_station).values(
                    station_id=station_id,
                    system_id=system_id,
                    name=name,
                    ls_from_star=ls_from_star,
                    max_pad_size=max_pad,
                    type_id=type_id,
                    planetary=planetary,
                    market=sflags["market"],
                    blackmarket=sflags["blackmarket"],
                    shipyard=sflags["shipyard"],
                    outfitting=sflags["outfitting"],
                    rearm=sflags["rearm"],
                    refuel=sflags["refuel"],
                    repair=sflags["repair"],
                    modified=modified,
                )
            )
        else:
            db_system_id, db_modified = row
            values = {
                "name": name,
                "ls_from_star": ls_from_star,
                "max_pad_size": max_pad,
                "type_id": type_id,
                "planetary": planetary,
                "market": sflags["market"],
                "blackmarket": sflags["blackmarket"],
                "shipyard": sflags["shipyard"],
                "outfitting": sflags["outfitting"],
                "rearm": sflags["rearm"],
                "refuel": sflags["refuel"],
                "repair": sflags["repair"],
            }
            if db_system_id != system_id:
                values["system_id"] = system_id
            if db_modified is None or modified > db_modified:
                values["modified"] = modified

            self.session.execute(
                update(t_station)
                .where(t_station.c.station_id == station_id)
                .values(**values)
            )

    def _upsert_shipyard(self, tables: Dict[str, Table], station_id: int, ships: List[Dict[str, Any]], ts: datetime) -> int:
        t_ship, t_vendor = tables["Ship"], tables["ShipVendor"]
        ship_rows, vendor_rows = [], []

        for sh in ships:
            ship_id = sh.get("shipId")
            name = sh.get("name")
            if ship_id is None or name is None:
                continue
            ship_rows.append({"ship_id": ship_id, "name": name})
            vendor_rows.append({"ship_id": ship_id, "station_id": station_id, "modified": ts})

        if ship_rows:
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_simple(self.session, t_ship, rows=ship_rows, key_cols=("ship_id",), update_cols=("name",))
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_simple(self.session, t_ship, rows=ship_rows, key_cols=("ship_id",), update_cols=("name",))
            else:
                for r in ship_rows:
                    exists = self.session.execute(select(t_ship.c.name).where(t_ship.c.ship_id == r["ship_id"])).first()
                    if exists is None:
                        self.session.execute(insert(t_ship).values(**r))
                    elif exists[0] != r["name"]:
                        self.session.execute(update(t_ship).where(t_ship.c.ship_id == r["ship_id"]).values(name=r["name"]))

        wrote = 0
        if vendor_rows:
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_modified(self.session, t_vendor, rows=vendor_rows,
                                                key_cols=("ship_id", "station_id"), modified_col="modified", update_cols=())
                wrote = len(vendor_rows)
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_modified(self.session, t_vendor, rows=vendor_rows,
                                               key_cols=("ship_id", "station_id"), modified_col="modified", update_cols=())
                wrote = len(vendor_rows)
            else:
                for r in vendor_rows:
                    ven = self.session.execute(
                        select(t_vendor.c.modified).where(and_(t_vendor.c.ship_id == r["ship_id"], t_vendor.c.station_id == r["station_id"]))
                    ).first()
                    if ven is None:
                        self.session.execute(insert(t_vendor).values(**r)); wrote += 1
                    else:
                        dbm = ven[0]
                        if dbm is None or r["modified"] > dbm:
                            self.session.execute(
                                update(t_vendor)
                                .where(and_(t_vendor.c.ship_id == r["ship_id"], t_vendor.c.station_id == r["station_id"]))
                                .values(modified=r["modified"])
                            )
                            wrote += 1
        return wrote

    def _upsert_outfitting(self, tables: Dict[str, Table], station_id: int, modules: List[Dict[str, Any]], ts: datetime) -> int:
        t_up, t_vendor = tables["Upgrade"], tables["UpgradeVendor"]
        up_rows, vendor_rows = [], []

        for mo in modules:
            up_id = mo.get("moduleId")
            name = mo.get("name")
            cls = mo.get("class")
            rating = mo.get("rating")
            ship = mo.get("ship")
            if up_id is None or name is None:
                continue

            up_rows.append({"upgrade_id": up_id, "name": name, "class": cls, "rating": rating, "ship": ship})
            vendor_rows.append({"upgrade_id": up_id, "station_id": station_id, "modified": ts})

        if up_rows:
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_simple(self.session, t_up, rows=up_rows, key_cols=("upgrade_id",),
                                              update_cols=("name", "class", "rating", "ship"))
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_simple(self.session, t_up, rows=up_rows, key_cols=("upgrade_id",),
                                             update_cols=("name", "class", "rating", "ship"))
            else:
                for r in up_rows:
                    exists = self.session.execute(select(t_up.c.upgrade_id).where(t_up.c.upgrade_id == r["upgrade_id"])).first()
                    if exists is None:
                        self.session.execute(insert(t_up).values(**r))
                    else:
                        self.session.execute(
                            update(t_up).where(t_up.c.upgrade_id == r["upgrade_id"]).values(
                                name=r["name"], **{"class": r["class"]}, rating=r["rating"], ship=r["ship"]
                            )
                        )

        wrote = 0
        if vendor_rows:
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_modified(self.session, t_vendor, rows=vendor_rows,
                                                key_cols=("upgrade_id", "station_id"), modified_col="modified", update_cols=())
                wrote = len(vendor_rows)
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_modified(self.session, t_vendor, rows=vendor_rows,
                                               key_cols=("upgrade_id", "station_id"), modified_col="modified", update_cols=())
                wrote = len(vendor_rows)
            else:
                for r in vendor_rows:
                    ven = self.session.execute(
                        select(t_vendor.c.modified).where(and_(t_vendor.c.upgrade_id == r["upgrade_id"], t_vendor.c.station_id == r["station_id"]))
                    ).first()
                    if ven is None:
                        self.session.execute(insert(t_vendor).values(**r)); wrote += 1
                    else:
                        dbm = ven[0]
                        if dbm is None or r["modified"] > dbm:
                            self.session.execute(
                                update(t_vendor)
                                .where(and_(t_vendor.c.upgrade_id == r["upgrade_id"], t_vendor.c.station_id == r["station_id"]))
                                .values(modified=r["modified"])
                            )
                            wrote += 1
        return wrote

    def _upsert_market(
        self,
        tables: Dict[str, Table],
        categories: Dict[str, int],
        station_id: int,
        commodities: List[Dict[str, Any]],
        ts: datetime,
    ) -> Tuple[int, int]:
        t_item, t_si = tables["Item"], tables["StationItem"]
        item_rows, link_rows = [], []
        wrote_items = 0

        for co in commodities:
            fdev_id = co.get("commodityId")
            name = co.get("name")
            cat_name = co.get("category")
            if fdev_id is None or name is None or cat_name is None:
                continue

            cat_id = categories.get(str(cat_name).lower())
            if cat_id is None:
                raise CleanExit(f'Unknown commodity category "{cat_name}"')

            item_rows.append({"item_id": fdev_id, "name": name, "category_id": cat_id, "fdev_id": fdev_id, "ui_order": 0})

            demand = co.get("demand")
            supply = co.get("supply")
            buy = co.get("buyPrice")
            sell = co.get("sellPrice")

            link_rows.append(dict(
                station_id=station_id,
                item_id=fdev_id,
                demand_price=sell,
                demand_units=demand,
                demand_level=-1,
                supply_price=buy,
                supply_units=supply,
                supply_level=-1,
                from_live=0,
                modified=ts,
            ))

        if item_rows:
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_simple(self.session, t_item, rows=item_rows, key_cols=("item_id",),
                                              update_cols=("name", "category_id", "fdev_id", "ui_order"))
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_simple(self.session, t_item, rows=item_rows, key_cols=("item_id",),
                                             update_cols=("name", "category_id", "fdev_id", "ui_order"))
            else:
                for r in item_rows:
                    exists = self.session.execute(
                        select(t_item.c.item_id, t_item.c.name, t_item.c.category_id).where(t_item.c.item_id == r["item_id"])
                    ).first()
                    if exists is None:
                        self.session.execute(insert(t_item).values(**r))
                        wrote_items += 1
                    else:
                        _, db_name, db_cat = exists
                        if (db_name != r["name"]) or (db_cat != r["category_id"]):
                            self.session.execute(
                                update(t_item).where(t_item.c.item_id == r["item_id"]).values(
                                    name=r["name"], category_id=r["category_id"]
                                )
                            )

        wrote_links = 0
        if link_rows:
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_modified(self.session, t_si, rows=link_rows,
                                                key_cols=("station_id", "item_id"), modified_col="modified",
                                                update_cols=("demand_price", "demand_units", "demand_level",
                                                             "supply_price", "supply_units", "supply_level", "from_live"))
                wrote_links = len(link_rows)
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_modified(self.session, t_si, rows=link_rows,
                                               key_cols=("station_id", "item_id"), modified_col="modified",
                                               update_cols=("demand_price", "demand_units", "demand_level",
                                                            "supply_price", "supply_units", "supply_level", "from_live"))
                wrote_links = len(link_rows)
            else:
                for r in link_rows:
                    si = self.session.execute(
                        select(t_si.c.modified).where(and_(t_si.c.station_id == r["station_id"], t_si.c.item_id == r["item_id"]))
                    ).first()
                    if si is None:
                        self.session.execute(insert(t_si).values(**r)); wrote_links += 1
                    else:
                        dbm = si[0]
                        if dbm is None or r["modified"] > dbm:
                            self.session.execute(
                                update(t_si)
                                .where(and_(t_si.c.station_id == r["station_id"], t_si.c.item_id == r["item_id"]))
                                .values(**r)
                            )
                            wrote_links += 1

        return (wrote_items, wrote_links)

    # ------------------------------
    # UI ordering
    # ------------------------------
    def _enforce_ui_order(self, session: Session, tables: Dict[str, Table]) -> None:
        t_item, t_cat = tables["Item"], tables["Category"]
        cats = session.execute(select(t_cat.c.category_id)).all()
        for (cat_id,) in cats:
            rows = session.execute(
                select(t_item.c.item_id, t_item.c.name, t_item.c.ui_order)
                .where(t_item.c.category_id == cat_id)
                .order_by(func.lower(t_item.c.name).asc(), t_item.c.name.asc(), t_item.c.item_id.asc())
            ).all()
            expected = 1
            for item_id, _name, ui_order in rows:
                if ui_order != expected:
                    session.execute(update(t_item).where(t_item.c.item_id == item_id).values(ui_order=expected))
                expected += 1

    # ------------------------------
    # Rares import (via cache.processImportFile)
    # ------------------------------
    def _import_rareitems(self) -> None:
        """
        Import RareItem.csv filtered by DB existence of (system, station).
        Implementation detail: table is cleared before import to avoid UNIQUE(name) conflicts.
        """
        import csv
        from sqlalchemy import text

        # Locate template
        rare_src = None
        if getattr(self.tdenv, "templateDir", None):
            candidate = Path(self.tdenv.templateDir) / "RareItem.csv"
            if candidate.exists():
                rare_src = candidate
        if rare_src is None:
            rare_src = (Path(__file__).resolve().parents[1] / "templates" / "RareItem.csv")
        if not rare_src.exists():
            raise CleanExit(f"RareItem.csv not found at {rare_src}")

        sess = None
        tmp_csv = None
        try:
            sess = self._open_session()
            tables = self._reflect_tables(sess.get_bind())
            t_station, t_system = tables["Station"], tables["System"]

            # Build existence set from DB (case/whitespace-insensitive)
            pairs = set()
            for sys_name, st_name in sess.execute(
                select(t_system.c.name, t_station.c.name).where(t_station.c.system_id == t_system.c.system_id)
            ):
                if sys_name and st_name:
                    pairs.add((str(sys_name).strip().lower(), str(st_name).strip().lower()))

            # Prepare output
            tmp_csv = self.tmp_dir / "RareItem.filtered.csv"
            kept = skipped = 0

            with open(rare_src, "r", encoding="utf-8", newline="") as fin, \
                 open(tmp_csv, "w", encoding="utf-8", newline="") as fout:

                lines = fin.readlines()
                if not lines:
                    raise CleanExit(f"RareItem.csv is empty: {rare_src}")

                header_line = lines[0]
                fout.write(header_line)

                # Determine column indexes robustly
                reader = csv.reader([header_line])
                headers = next(reader, [])
                h_norm = [(h or "").strip().lower() for h in headers]

                def find_col_idx(kind: str) -> int:
                    # 'kind' is 'system' or 'station'
                    for i, h in enumerate(h_norm):
                        if "name@" in h and kind in h:
                            return i
                    for i, h in enumerate(h_norm):
                        if kind in h:
                            return i
                    return -1

                idx_sys = find_col_idx("system")
                idx_stn = find_col_idx("station")

                if idx_sys < 0 or idx_stn < 0:
                    # Unexpected header — pass through unchanged
                    for line in lines[1:]:
                        fout.write(line)
                        kept = -1  # unknown
                    skipped = 0
                else:
                    for line in lines[1:]:
                        if not line.strip():
                            continue
                        try:
                            row = next(csv.reader([line]))
                        except Exception:
                            skipped += 1
                            continue

                        sys_name = (row[idx_sys] if idx_sys < len(row) else "").strip().strip("'\"").strip().lower()
                        stn_name = (row[idx_stn] if idx_stn < len(row) else "").strip().strip("'\"").strip().lower()

                        if sys_name and stn_name and (sys_name, stn_name) in pairs:
                            fout.write(line)
                            kept += 1
                        else:
                            skipped += 1

            # Clear RareItem before import to avoid UNIQUE(name) conflicts
            try:
                sess.execute(text('DELETE FROM "RareItem"'))
                sess.commit()
            except Exception:
                sess.rollback()
                # Try unquoted name for MySQL/MariaDB
                sess.execute(text("DELETE FROM RareItem"))
                sess.commit()

            # Hand the filtered file to the existing importer
            cache.processImportFile(self.tdenv, sess, tmp_csv, "RareItem")
            sess.commit()

            if kept >= 0 and skipped > 0:
                self._warn(f"RareItem: imported {kept} rows; skipped {skipped} (system/station not present in DB).")

        except Exception as e:
            if sess is not None:
                try:
                    sess.rollback()
                except Exception:
                    pass
            raise CleanExit(f"RareItem import failed: {e!r}")
        finally:
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
            try:
                if tmp_csv and tmp_csv.exists():
                    tmp_csv.unlink()
            except Exception:
                pass

    # ------------------------------
    # Export / cache refresh
    # ------------------------------
    def _export_cache(self) -> None:
        """Export CSVs and regenerate TradeDangerous.prices — concurrently, with optional StationItem gating."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Option/env gate for StationItem export (large file)
        def _opt_true(val: Optional[str]) -> bool:
            if val is None:
                return False
            if isinstance(val, str):
                return val.strip().lower() in ("1", "true", "yes", "on", "y")
            return bool(val)

        skip_stationitems = _opt_true(self.getOption("skip_stationitems")) or _opt_true(os.environ.get("TD_SKIP_STATIONITEM_EXPORT"))

        # Heaviest tables first to maximize overlap
        tables = [
            "StationItem",
            "ShipVendor",
            "UpgradeVendor",
            "Station",
            "System",
            "Item",
            "Ship",
            "Upgrade",
            "RareItem",
        ]
        if skip_stationitems:
            tables = [t for t in tables if t != "StationItem"]

        # Worker count (env override allowed); +1 slot reserved for prices task
        try:
            workers = int(os.environ.get("TD_EXPORT_WORKERS", "4"))
        except ValueError:
            workers = 4
        workers = max(1, workers) + 1  # extra slot for the prices job

        def _export_one(table_name: str) -> str:
            sess = None
            try:
                sess = self._open_session()  # fresh session per worker
                csvexport.exportTableToFile(sess, self.tdenv, table_name)
                return f"{table_name}.csv"
            finally:
                if sess is not None:
                    try:
                        sess.close()
                    except Exception:
                        pass

        def _regen_prices() -> str:
            cache.regeneratePricesFile(self.tdb, self.tdenv)
            return "TradeDangerous.prices"

        self._print("Exporting to cache...")
        for t in tables:
            self._print(f"  - {t}.csv")
        if skip_stationitems:
            self._warn("Skipping StationItem.csv export (requested).")
        self._print("Regenerating TradeDangerous.prices …")

        # Parallel export + prices regen, with conservative fallback
        try:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(_export_one, t): f"{t}.csv" for t in tables}
                futures[ex.submit(_regen_prices)] = "TradeDangerous.prices"
                for fut in as_completed(futures):
                    _ = fut.result()  # raise on any worker failure
        except Exception as e:
            self._warn(f"Parallel export encountered an error ({e!r}); falling back to serial.")
            for t in tables:
                _export_one(t)
            _regen_prices()

        self._print("Cache export completed.")
    # ------------------------------
    # Categories cache
    # ------------------------------
    def _load_categories(self, session: Session, tables: Dict[str, Table]) -> Dict[str, int]:
        t_cat = tables["Category"]
        rows = session.execute(select(t_cat.c.category_id, t_cat.c.name)).all()
        return {str(name).lower(): int(cid) for (cid, name) in rows}

    # ------------------------------
    # Streaming JSON reader
    # ------------------------------
    
    def _ijson_items(self, fh: io.BufferedReader, prefix: str):
        """
        Use the fastest available ijson backend with clean fallback.
        Order: yajl2_cffi → yajl2_c → yajl2 → python.
        """
        try:
            from ijson.backends import yajl2_cffi as ijson_fast
            return ijson_fast.items(fh, prefix)
        except Exception:
            pass
        try:
            from ijson.backends import yajl2_c as ijson_fast  # ctypes wrapper
            return ijson_fast.items(fh, prefix)
        except Exception:
            pass
        try:
            from ijson.backends import yajl2 as ijson_fast
            return ijson_fast.items(fh, prefix)
        except Exception:
            pass
        # Fallback to whatever was imported at module top
        return ijson.items(fh, prefix)

    def _iter_top_level_json_array(self, fh: io.BufferedReader) -> Generator[Dict[str, Any], None, None]:
        """
        High-performance streaming reader for a huge top-level JSON array of systems.
        """
        start_ts = time.time()
        last_tick_systems = 0
        TICK_EVERY = 256

        it = self._ijson_items(fh, 'item')
        for idx, obj in enumerate(it, 1):
            if (idx - last_tick_systems) >= TICK_EVERY:
                last_tick_systems = idx
                try:
                    self._parse_progress(fh.tell(), start_ts)
                except Exception:
                    pass
            yield obj

        try:
            self._parse_progress(fh.tell(), start_ts)
        except Exception:
            pass

        if self._is_tty:
            self._live_status("")

    # ------------------------------
    # Mapping / derivations / misc
    # ------------------------------
    @staticmethod
    def _build_station_type_map() -> Dict[Optional[str], Tuple[int, bool]]:
        return {
            None: (0, False),
            "None": (0, False),
            "Outpost": (1, False),
            "Coriolis Starport": (2, False),
            "Ocellus Starport": (3, False),
            "Orbis Starport": (4, False),
            "Planetary Outpost": (11, True),
            "Planetary Port": (12, True),
            "Mega ship": (13, False),
            "Asteroid base": (14, False),
            "Drake-Class Carrier": (24, False),
            "Settlement": (25, True),
        }

    def _map_station_type(self, type_name: Optional[str]) -> Tuple[int, str]:
        if isinstance(type_name, str):
            res = self._station_type_map.get(type_name)
            if res:
                type_id, is_planetary = res
                return type_id, "Y" if is_planetary else "N"
        return (0, "?")

    @staticmethod
    def _derive_pad_size(landing: Mapping[str, Any]) -> str:
        try:
            if landing.get("large"):
                return "L"
            if landing.get("medium"):
                return "M"
            if landing.get("small"):
                return "S"
        except Exception:
            pass
        return "?"

    def _resolve_batch_size(self) -> Optional[int]:
        """
        Decide commit batch size for *spansh* profile.
        """
        if self.session is not None and hasattr(db_utils, "get_import_batch_size"):
            try:
                val = db_utils.get_import_batch_size(self.session, profile="spansh")
                if val is not None:
                    return val
            except Exception:
                pass

        raw = os.environ.get("TD_LISTINGS_BATCH")
        if raw is not None:
            try:
                envv = int(raw)
                return envv if envv > 0 else None
            except ValueError:
                pass

        try:
            if db_utils.is_sqlite(self.session):
                return None
            if db_utils.is_mysql(self.session):
                return 50_000
        except Exception:
            pass

        return 5_000

    # ---- ts/format/logging helpers ----
    def _parse_ts(self, value: Any) -> Optional[datetime]:
        try:
            return db_utils.parse_ts(value)  # UTC-naive, μs=0
        except Exception:
            return None

    @staticmethod
    def _format_hms(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"

    def _fmt_bytes(self, n: float) -> str:
        units = ["B", "KiB", "MiB", "GiB", "TiB"]
        i = 0
        while n >= 1024 and i < len(units) - 1:
            n /= 1024.0
            i += 1
        return f"{int(n)} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"

    def _progress_line(self, stats: Dict[str, int]) -> None:
        """
        Single-line live status while importing.
        Shows bytes/rate, total systems/stations, and *per-station* service writes/kept.
        """
        now = time.time()
        # Slightly slower cadence at low verbosity to reduce stderr churn
        min_interval = 0.75 if self._debug_level < 1 else 0.25
        if now - self._last_progress_time < min_interval:
            return
        self._last_progress_time = now

        self._started_importing = True
        parse_bytes = getattr(self, "_parse_bytes", 0)
        parse_rate  = getattr(self, "_parse_rate", 0.0)
        systems  = stats.get("systems", 0)
        stations = stats.get("stations", 0)
        writes_m = stats.get("market_writes", 0)
        writes_o = stats.get("outfit_writes", 0)
        writes_s = stats.get("ship_writes", 0)
        kept_m = stats.get("market_stations", 0)
        kept_o = stats.get("outfit_stations", 0)
        kept_s = stats.get("ship_stations", 0)

        msg = (
            f"Importing…  {self._fmt_bytes(parse_bytes)} read  {self._fmt_bytes(parse_rate)}/s  "
            f"systems: {systems:,}  stations: {stations:,}  "
            f"writes(stations): mkt={writes_m:,} outf={writes_o:,} shp={writes_s:,}  "
            f"kept: mkt≈{kept_m:,} outf≈{kept_o:,} shp≈{kept_s:,}"
        )
        self._live_status(msg)


    def _live_line(self, msg: str) -> None:
        self._live_status(msg)

    def _live_status(self, msg: str) -> None:
        try:
            import shutil
            width = shutil.get_terminal_size(fallback=(120, 20)).columns
            if width and width > 4:
                msg = msg[: width - 2]
        except Exception:
            pass

        s = f"\x1b[2K\r{msg}"
        try:
            if self._is_tty:
                sys.stderr.write(s)
                sys.stderr.flush()
            else:
                self._print(msg)
        except Exception:
            self._print(msg)

    def _end_live_status(self) -> None:
        try:
            if self._is_tty:
                sys.stderr.write("\x1b[2K\r\n")
                sys.stderr.flush()
        except Exception:
            pass

    # ---- printing/warnings ----
    def _print(self, *args, **kwargs):
        printer = getattr(self.tdenv, "print", None)
        if callable(printer):
            printer(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def _warn(self, msg: str):
        if self._warn_enabled:
            self._print(f"WARNING: {msg}")

    def _error(self, msg: str):
        self._print(f"ERROR: {msg}")

    def _safe_close_session(self):
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
        self.session = None


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------
class CleanExit(Exception):
    """Controlled early exit: log and stop this run so schedulers can retry later."""
    pass
