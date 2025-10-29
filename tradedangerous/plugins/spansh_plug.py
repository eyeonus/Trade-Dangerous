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
import traceback
import time
import json # Used for debug tracing 
import ijson # Used for main stream
import shutil
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Mapping, Optional, Tuple, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed


# Framework modules
from .. import plugins, cache, csvexport  # provided by project

# DB helpers (dialect specifics live here)
from ..db import utils as db_utils
from ..db.lifecycle import ensure_fresh_db
from ..db.locks import station_advisory_lock

# SQLAlchemy
from sqlalchemy import MetaData, Table, select, insert, update, func, and_, or_, text, UniqueConstraint
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
        "version": "2.1",
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
        "skip_stationitems": "Skip exporting StationItem.csv (large). Env: TD_SKIP_STATIONITEM_EXPORT=1",
        "progress_compact": "Use shorter one-line import status (or set env TD_PROGRESS_COMPACT=1).",
        # --- EDCD sourcing (hardcoded URLs; can be disabled or overridden) ---
        "no_edcd": "Disable EDCD preloads (categories, FDev tables) and EDCD rares import.",
        "edcd_commodity": "Override URL or local path for EDCD commodity.csv.",
        "edcd_outfitting": "Override URL or local path for EDCD outfitting.csv.",
        "edcd_shipyard": "Override URL or local path for EDCD shipyard.csv.",
        "edcd_rares": "Override URL or local path for EDCD rare_commodity.csv.",
        # --- Extra Debug Options
        "only_system": "Process only the system with this name or id64; still stream the real file.",
        "debug_trace": "Emit compact JSONL decision logs to tmp/spansh_trace.jsonl (1 line per decision).",
    }
    
    # Hardcoded EDCD sources (raw GitHub)
    EDCD_URLS = {
        "commodity": "https://raw.githubusercontent.com/EDCD/FDevIDs/master/commodity.csv",
        "outfitting": "https://raw.githubusercontent.com/EDCD/FDevIDs/master/outfitting.csv",
        "shipyard": "https://raw.githubusercontent.com/EDCD/FDevIDs/master/shipyard.csv",
        "rares": "https://raw.githubusercontent.com/EDCD/FDevIDs/master/rare_commodity.csv",
    }
    
    # ------------------------------
    # Construction & plumbing
    # ------------------------------
    # ------------------------------
    # Construction & plumbing (REPLACEMENT)
    # ------------------------------
    def __init__(self, tdb, cmdenv):
        super().__init__(tdb, cmdenv)
        self.tdb = tdb
        self.tdenv = cmdenv
        self.session: Optional[Session] = None
        
        # Paths (data/tmp) from env/config; fall back defensively
        self.data_dir = Path(getattr(self.tdenv, "dataDir", getattr(self.tdb, "dataDir", "data"))).resolve()
        self.tmp_dir = Path(getattr(self.tdenv, "tmpDir", getattr(self.tdb, "tmpDir", "tmp"))).resolve()
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
        
        # Station type mapping (existing helper in this module)
        self._station_type_map = self._build_station_type_map()
        
        # Debug trace option
        self.debug_trace = str(self.getOption("debug_trace") or "0").strip().lower() not in ("0", "", "false", "no")
        self._trace_fp = None
    
    # --------------------------------------
    # Small tracing helper 
    # --------------------------------------
    def _trace(self, **evt) -> None:
        """
        Lightweight debug tracer. Writes one compact JSON line per call
        into tmp/spansh_trace.jsonl when -O debug_trace=1 is set.
        Has no side-effects on existing logic if disabled.
        """
        if not getattr(self, "debug_trace", False):
            return
        try:
            import json
            # lazily open file handle if not yet opened
            if not hasattr(self, "_trace_fp") or self._trace_fp is None:
                tmp = getattr(self, "tmp_dir", Path("tmp"))
                tmp.mkdir(parents=True, exist_ok=True)
                self._trace_fp = (tmp / "spansh_trace.jsonl").open("a", encoding="utf-8")
            
            # sanitize datetimes
            for k, v in list(evt.items()):
                if hasattr(v, "isoformat"):
                    evt[k] = v.isoformat()
            
            self._trace_fp.write(json.dumps(evt, ensure_ascii=False) + "\n")
            self._trace_fp.flush()
        except Exception:
            pass  # never break main flow
    
    # --- TD shim: seed 'Added' from templates (idempotent) ---
    def _seed_added_from_templates(self, session) -> None:
        """
        Seed the legacy 'Added' table from the packaged CSV:
            tradedangerous/templates/Added.csv
        
        DB-agnostic; uses cache.processImportFile. No reliance on any templatesDir.
        """
        from importlib.resources import files, as_file
        from tradedangerous.cache import processImportFile
        
        # Obtain a Traversable for the packaged resource and materialize to a real path
        res = files("tradedangerous").joinpath("templates", "Added.csv")
        with as_file(res) as csv_path:
            if not csv_path.exists():
                # Graceful failure so schedulers can retry
                raise CleanExit(f"Packaged Added.csv not found: {csv_path}")
            try:
                processImportFile(
                    tdenv=self.tdenv,
                    session=session,
                    importPath=csv_path,
                    tableName="Added",
                )
            except Exception as e:
                # Keep diagnostics, but avoid hard process exit
                self._warn("Seeding 'Added' from templates failed; continuing without it.")
                self._warn(f"{type(e).__name__}: {e}")
                traceback.print_exc()
                raise CleanExit("Failed to seed 'Added' table from templates.")


    # --------------------------------------
    # EDCD Import Functions
    # --------------------------------------
    
    # ---------- Download from EDCD ----------       
    def _acquire_edcd_files(self) -> Dict[str, Optional[Path]]:
        """
        Download (or resolve) EDCD CSVs to tmp/ with conditional caching.
        Honors -O no_edcd=1 and per-file overrides:
          - edcd_commodity, edcd_outfitting, edcd_shipyard, edcd_rares
        Each override may be a local path or an http(s) URL.
        Returns dict: {commodity,outfitting,shipyard,rares} -> Path or None.
        """
        def _resolve_one(opt_key: str, default_url: str, basename: str) -> Optional[Path]:
            override = self.getOption(opt_key)
            target = self.tmp_dir / f"edcd_{basename}.csv"
            label = f"EDCD {basename}.csv"
            
            # Explicit disable via empty override
            if override is not None and str(override).strip() == "":
                return None
            
            # Local path override
            if override and ("://" not in override):
                p = Path(override)
                if not p.exists():
                    cwd = getattr(self.tdenv, "cwDir", None)
                    if cwd:
                        p = Path(cwd, override)
                if p.exists() and p.is_file():
                    return p.resolve()
                override = None  # fall back to URL
            
            # URL (override or default)
            url = override or default_url
            try:
                return self._download_with_cache(url, target, label=label)
            except CleanExit:
                return target if target.exists() else None
            except Exception:
                return target if target.exists() else None
        
        if self.getOption("no_edcd"):
            return {"commodity": None, "outfitting": None, "shipyard": None, "rares": None}
        
        return {
            "commodity": _resolve_one("edcd_commodity", self.EDCD_URLS["commodity"], "commodity"),
            "outfitting": _resolve_one("edcd_outfitting", self.EDCD_URLS["outfitting"], "outfitting"),
            "shipyard":  _resolve_one("edcd_shipyard",  self.EDCD_URLS["shipyard"],  "shipyard"),
            "rares":     _resolve_one("edcd_rares",     self.EDCD_URLS["rares"],     "rare_commodity"),
        }


    # ---------- EDCD: Categories (add-only) ----------
    def _edcd_import_categories_add_only(
            self,
            session: Session,
            tables: Dict[str, Table],
            commodity_csv: Path,
        ) -> int:
        """
        Read EDCD commodity.csv, extract distinct category names, and add any
        missing Category rows. No updates, no deletes. Cross-dialect safe.
        
        Returns: number of rows inserted.
        """
        t_cat = tables["Category"]
        
        # Load existing category names (case-insensitive) to avoid duplicates.
        existing_lc = {
            (str(n) or "").strip().lower()
            for (n,) in session.execute(select(t_cat.c.name)).all()
            if n is not None
        }
        
        # Parse the CSV and collect unique category names.
        with open(commodity_csv, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            
            # Find the 'category' column (case-insensitive).
            cat_col = None
            for h in (reader.fieldnames or []):
                if h and str(h).strip().lower() == "category":
                    cat_col = h
                    break
            if cat_col is None:
                raise CleanExit(f"EDCD commodity.csv missing 'category' column: {commodity_csv}")
            
            seen_lc: set[str] = set()
            to_add: list[dict] = []
            
            for row in reader:
                raw = row.get(cat_col)
                if not raw:
                    continue
                name = str(raw).strip()
                if not name:
                    continue
                
                lk = name.lower()
                if lk in existing_lc or lk in seen_lc:
                    continue
                
                seen_lc.add(lk)
                to_add.append({"name": name})
        
        if not to_add:
            return 0
        
        # Cross-dialect safe "add-only": bulk insert the missing names.
        session.execute(insert(t_cat), to_add)
        return len(to_add)




    # ---------- EDCD: FDev tables (direct load) ----------
    def _edcd_import_table_direct(self, session: Session, table: Table, csv_path: Path) -> int:
        """
        Upsert CSV rows into a table whose columns match CSV headers.
        Prefers the table's primary key; if absent, falls back to a single-column
        UNIQUE key (e.g. 'id' in FDev tables). Returns approx rows written.
        """
        # --- choose key columns for upsert ---
        pk_cols = tuple(c.name for c in table.primary_key.columns)
        key_cols: tuple[str, ...] = pk_cols
        
        if not key_cols:
            # Common case for EDCD FDev tables: UNIQUE(id) but no PK
            if "id" in table.c:
                key_cols = ("id",)
            else:
                # Try to discover a single-column UNIQUE constraint via reflection
                try:
                    uniq_single = []
                    for cons in getattr(table, "constraints", set()):
                        if isinstance(cons, UniqueConstraint):
                            cols = tuple(col.name for col in cons.columns)
                            if len(cols) == 1:
                                uniq_single.append(cols[0])
                    if uniq_single:
                        key_cols = (uniq_single[0],)
                except Exception:
                    pass
        
        if not key_cols:
            raise CleanExit(f"Table {table.name} has neither a primary key nor a single-column UNIQUE key; cannot upsert from EDCD")
        
        # --- read CSV ---
        with open(csv_path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            cols = [c for c in (reader.fieldnames or []) if c in table.c]
            if not cols:
                return 0
            rows = [{k: row.get(k) for k in cols} for row in reader]
        
        if not rows:
            return 0
        
        # --- table-specific sanitation (fixes ck_fdo_mount / ck_fdo_guidance) ---
        if table.name == "FDevOutfitting":
            allowed_mount = {"Fixed", "Gimballed", "Turreted"}
            allowed_guid  = {"Dumbfire", "Seeker", "Swarm"}
            
            def _norm(val, allowed):
                if val is None:
                    return None
                s = str(val).strip()
                if not s or s not in allowed:
                    return None
                return s
            
            for r in rows:
                if "mount" in r:
                    r["mount"] = _norm(r["mount"], allowed_mount)
                if "guidance" in r:
                    r["guidance"] = _norm(r["guidance"], allowed_guid)
        
        # --- perform upsert using chosen key columns ---
        upd_cols = tuple(c for c in cols if c not in key_cols)
        
        if db_utils.is_sqlite(session):
            db_utils.sqlite_upsert_simple(session, table, rows=rows, key_cols=key_cols, update_cols=upd_cols)
            return len(rows)
        
        if db_utils.is_mysql(session):
            db_utils.mysql_upsert_simple(session, table, rows=rows, key_cols=key_cols, update_cols=upd_cols)
            return len(rows)
        
        # Generic backend (read-then-insert/update)
        for r in rows:
            cond = and_(*[getattr(table.c, k) == r[k] for k in key_cols])
            ext = session.execute(select(*[getattr(table.c, k) for k in key_cols]).where(cond)).first()
            if ext is None:
                session.execute(insert(table).values(**r))
            elif upd_cols:
                session.execute(update(table).where(cond).values(**{k: r[k] for k in upd_cols}))
        return len(rows)
    
    def _edcd_import_fdev_catalogs(self, session: Session, tables: Dict[str, Table], *, outfitting_csv: Path, shipyard_csv: Path) -> Tuple[int, int]:
        u = self._edcd_import_table_direct(session, tables["FDevOutfitting"], outfitting_csv)
        s = self._edcd_import_table_direct(session, tables["FDevShipyard"],   shipyard_csv)
        return (u, s)
    
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
            ts_sp: Optional[datetime],
            kind: str,  # "ship" or "module"
        ) -> Tuple[int, int]:
        """
        Fast, set-based vendor sync for a single station and one service (shipyard/outfitting).
        
        Returns: (number_of_inserts_or_updates_on_vendor_links, deletions_count).
        """
        # Ensure we never write NULL into NOT NULL 'modified' columns.
        ts_eff = (ts_sp or datetime.utcnow().replace(microsecond=0))
        
        if kind == "ship":
            t_master = tables["Ship"]
            t_vendor = tables["ShipVendor"]
            id_key = "shipId"
            id_col = "ship_id"
            master_rows = []
            keep_ids: set[int] = set()
            for e in entries:
                if not isinstance(e, dict):
                    continue
                ship_id = e.get(id_key)
                name = e.get("name")
                if ship_id is None or name is None:
                    continue
                keep_ids.add(int(ship_id))
                master_rows.append({"ship_id": ship_id, "name": name})
        
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
        
        # 1) Ensure master rows exist (simple upsert, no timestamp guards).
        if master_rows:
            key_name = list(master_rows[0].keys())[0]
            update_cols = tuple(k for k in master_rows[0].keys() if k != key_name)
            if db_utils.is_sqlite(self.session):
                db_utils.sqlite_upsert_simple(
                    self.session, t_master, rows=master_rows,
                    key_cols=(key_name,),
                    update_cols=update_cols,
                )
            elif db_utils.is_mysql(self.session):
                db_utils.mysql_upsert_simple(
                    self.session, t_master, rows=master_rows,
                    key_cols=(key_name,),
                    update_cols=update_cols,
                )
            else:
                for r in master_rows:
                    cond = (getattr(t_master.c, key_name) == r[key_name])
                    exists = self.session.execute(select(getattr(t_master.c, key_name)).where(cond)).first()
                    if exists is None:
                        self.session.execute(insert(t_master).values(**r))
                    else:
                        upd = {k: v for k, v in r.items() if k != key_name}
                        if upd:
                            self.session.execute(update(t_master).where(cond).values(**upd))
        
        # 2) Link rows with timestamp guard for vendor tables.
        wrote = 0
        delc = 0
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
                if (mod is None) or (ts_eff > mod)
            }
            wrote = len(to_insert) + len(to_update)
            
            vendor_rows = [{id_col: vid, "station_id": station_id, "modified": ts_eff} for vid in keep_ids]
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
                        mod = cur[0]
                        if (mod is None) or (ts_eff > mod):
                            self.session.execute(update(t_vendor).where(cond).values(modified=ts_eff))
        
        return wrote, delc
    
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
        Full orchestrator: acquisition → bootstrap → EDCD preload → import → rares → export.
        Returns False to keep default flow suppressed.
        """
        started = time.time()
        
        if self.getOption("pricesonly"):
            try:
                self._print("Regenerating TradeDangerous.prices …")
                cache.regeneratePricesFile(self.tdb, self.tdenv)
                self._print("Prices file generated.")
            except Exception as e:
                self._error(f"Prices regeneration failed: {e!r}")
                return False
            return False
        
        # Acquire Spansh JSON
        try:
            source_path = self._acquire_source()
        except CleanExit as ce:
            self._warn(str(ce)); return False
        except Exception as e:
            self._error(f"Acquisition failed: {e!r}"); return False
        
        # -------- Bootstrap DB (no cache rebuild here) --------
        try:
            backend  = self.tdb.engine.dialect.name.lower()
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
                rebuild=False,   # do not run buildCache here
            )
            self._print(
                f"DB bootstrap: action={summary.get('action','kept')} "
                f"reason={summary.get('reason','ok')} backend={summary.get('backend')}"
            )
            
            # No valid DB? Create full schema now (SQLite from canonical SQL; MariaDB via ORM)
            if summary.get("action") == "needs_rebuild":
                from tradedangerous.db.lifecycle import reset_db
                db_path = Path(self.tdb.engine.url.database or (data_dir / "TradeDangerous.db"))  # SQLite only
                self._print("No valid DB detected — creating full schema…")
                reset_db(self.tdb.engine, db_path=db_path)
                
                # Seed 'Added' once on a fresh schema
                self.session = self._open_session()
                self._seed_added_from_templates(self.session)
                self.session.commit()
                self._safe_close_session()
        
        except Exception as e:
            self._error(f"Database bootstrap failed: {e!r}")
            return False
        
        # -------- Session + batch + reflection --------
        try:
            self.session = self._open_session()
            self.batch_size = self._resolve_batch_size()
            tables = self._reflect_tables(self.session.get_bind())
        except Exception as e:
            self._error(f"Failed to open/reflect DB session: {e!r}")
            return False
        
        # -------- EDCD preloads (hardcoded URLs; can be disabled) --------
        edcd = self._acquire_edcd_files()
        
        # Categories (add-only) — COMMIT immediately so they persist even if later phases fail.
        try:
            if edcd.get("commodity"):
                added = self._edcd_import_categories_add_only(self.session, tables, edcd["commodity"])
                if added:
                    self._print(f"EDCD categories: added {added} new categories")
                self.session.commit()
        except CleanExit as ce:
            self._warn(str(ce)); return False
        except Exception as e:
            self._warn(f"EDCD categories skipped due to error: {e!r}")
        
        # FDev catalogs (outfitting, shipyard) — COMMIT immediately as well.
        try:
            if edcd.get("outfitting") and edcd.get("shipyard"):
                u, s = self._edcd_import_fdev_catalogs(
                    self.session, tables,
                    outfitting_csv=edcd["outfitting"],
                    shipyard_csv=edcd["shipyard"],
                )
                if (u + s) > 0:
                    self._print(f"EDCD FDev: Outfitting upserts={u:,}  Shipyard upserts={s:,}")
                self.session.commit()
        except Exception as e:
            self._warn(f"EDCD FDev catalogs skipped due to error: {e!r}")
        
        # Load categories (may have grown) before Spansh import
        try:
            categories = self._load_categories(self.session, tables)
        except Exception as e:
            self._error(f"Failed to load categories: {e!r}")
            return False
        
        # -------- Import Spansh JSON --------
        try:
            if self._debug_level < 1:
                self._print("This will take at least several minutes.")
                self._print("You can increase verbosity (-v) to get a sense of progress")
            self._print("Importing spansh data")
            stats = self._import_stream(source_path, categories, tables)
            self._end_live_status()
            
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
            self._warn(str(ce)); self._safe_close_session(); return False
        except Exception as e:
            self._error(f"Import failed: {e!r}"); self._safe_close_session(); return False
        
        # Enforce Item.ui_order
        try:
            t0 = time.time()
            self._enforce_ui_order(self.session, tables)
            self._print(f"ui_order enforced in {time.time()-t0:.2f}s")
        except Exception as e:
            self._error(f"ui_order enforcement failed: {e!r}")
            self._safe_close_session(); return False
        
        # Final commit for import phase
        try:
            self.session.commit()
        except Exception as e:
            self._warn(f"Commit failed at end of import; rolling back. Cause: {e!r}")
            self.session.rollback(); self._safe_close_session(); return False
        
        self._safe_close_session()
        
        # -------- Rares (prefer EDCD; fallback to template) --------
        try:
            t0 = time.time()
            if edcd.get("rares"):
                self._import_rareitems_edcd(edcd["rares"])
            else:
                self._import_rareitems()
            self._print(f"Rares imported in {time.time()-t0:.2f}s")
        except CleanExit as ce:
            self._warn(str(ce)); return False
        except Exception as e:
            self._error(f"RareItem import failed: {e!r}"); return False
        
        # -------- Export (uses your parallel exporter already present) --------
        try:
            self._export_and_mirror()  # timing + final print handled inside
        except Exception as e:
            self._error(f"Export failed: {e!r}"); return False
        
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
        
        # Pass a friendly label so progress says “Spansh dump”
        return self._download_with_cache(url, cache_path, label="Spansh dump")
    
    def _download_with_cache(self, url: str, cache_path: Path, *, label: str = "download") -> Path:
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
                self._print(f"Remote not newer; using cached {label}")
                return cache_path
        
        self._print(f"Downloading {label} from {url} …")
        part = cache_path.with_suffix(cache_path.suffix + ".part")
        if part.exists():
            try:
                part.unlink()
            except Exception:
                pass
        
        req = urllib.request.Request(url, method="GET")
        connect_timeout = 30
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
                    self._download_progress(downloaded, total, start, label=label)
            
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
            raise CleanExit(f"Download failed or timed out for {label}; skipping run ({e!r})")
        
        self._print(f'Download complete: {label} → "{cache_path}"')
        return cache_path
    
    def _download_progress(self, downloaded: int, total: Optional[int], start_ts: float, *, label: str = "download") -> None:
        now = time.time()
        if now - self._last_progress_time < 0.5 and self._debug_level < 1:
            return
        self._last_progress_time = now
        
        rate = downloaded / max(now - start_ts, 1e-9)
        if total:
            pct = (downloaded / total) * 100.0
            msg = f"{label}: {self._fmt_bytes(downloaded)} / {self._fmt_bytes(total)} ({pct:5.1f}%)  {self._fmt_bytes(rate)}/s"
        else:
            msg = f"{label}: {self._fmt_bytes(downloaded)} read  {self._fmt_bytes(rate)}/s"
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
            "FDevOutfitting", "FDevShipyard", "RareItem",
        ]
        return {n: Table(n, meta, autoload_with=engine) for n in names}
    
    # ------------------------------
    # Import (streaming JSON → upserts)
    # ------------------------------
    def _import_stream(self, source_path: Path, categories: Dict[str, int], tables: Dict[str, Table]) -> Dict[str, int]:
        """
        Streaming importer with service-level maxage gating (FK-safe), using per-row rules.
        
        FIXES:
        - Batch commits now honor utils.get_import_batch_size() across *all* parent/child ops.
        - System/Station increments are counted in stats and batch_ops.
        - Commit checks occur before each station is processed (outside advisory lock scope),
          reducing long transactions and making Ctrl-C loss less likely.
        """
        batch_ops = 0
        stats = {
            "systems": 0, "stations": 0,
            "market_stations": 0, "outfit_stations": 0, "ship_stations": 0,
            "market_writes": 0, "outfit_writes": 0, "ship_writes": 0,
            "commodities": 0,
        }
        
        # NEW: initialize parse metrics for _progress_line(); iterator keeps these updated
        self._parse_bytes = 0
        self._parse_rate = 0.0
        
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
                
                self._trace(phase="system", decision="consider", name=sys_name, id64=sys_id64)
                
                # Collect stations (top-level + body-embedded)
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
                
                # --- System upsert ---
                t_system = tables["System"]
                x = coords.get("x"); y = coords.get("y"); z = coords.get("z")
                sys_modified = self._parse_ts(system_obj.get("updateTime"))
                self._upsert_system(t_system, int(sys_id64), str(sys_name), x, y, z, sys_modified)
                
                # Count system progress and participate in batching
                stats["systems"] += 1
                batch_ops += 1
                
                imported_station_modifieds: list[datetime] = []
                
                for st in stations:
                    # Periodic commit BEFORE processing the next station (outside any advisory locks)
                    if (self.batch_size is not None) and (batch_ops >= self.batch_size):
                        try:
                            self.session.commit()
                            batch_ops = 0
                        except Exception as e:
                            self._warn(f"Batch commit failed; rolling back. Cause: {e!r}")
                            self.session.rollback()
                    
                    name = st.get("name")
                    sid = st.get("id")
                    if not isinstance(name, str) or sid is None:
                        continue
                    station_id = int(sid)
                    seen_station_ids.add(station_id)
                    stats["stations"] += 1
                    # Count at least one op per station so batching still progresses even if no vendor writes occur
                    batch_ops += 1
                    
                    # NEW: drive live progress from here (throttled inside _progress_line)
                    self._progress_line(stats)
                    
                    # Flags/timestamps
                    has_market = bool(st.get("hasMarket") or ("market" in st))
                    has_outfit = bool(st.get("hasOutfitting") or ("outfitting" in st))
                    has_ship   = bool(st.get("hasShipyard") or ("shipyard" in st))
                    mkt_ts  = svc_ts(st, "market")
                    outf_ts = svc_ts(st, "outfitting")
                    ship_ts = svc_ts(st, "shipyard")
                    mkt_fresh  = recent(mkt_ts)
                    outf_fresh = recent(outf_ts)
                    ship_fresh = recent(ship_ts)
                    
                    # Station upsert (idempotent)
                    t_station = tables["Station"]
                    type_id, planetary = self._map_station_type(st.get("type"))
                    pads = st.get("landingPads") or {}
                    max_pad = self._derive_pad_size(pads)
                    sflags = {
                        "market": "Y" if has_market else "N",
                        "blackmarket": "?" if st.get("hasBlackmarket") is None else ("Y" if st.get("hasBlackmarket") else "N"),
                        "shipyard": "Y" if has_ship else "N",
                        "outfitting": "Y" if has_outfit else "N",
                        "rearm": "?" if st.get("hasRearm") is None else ("Y" if st.get("hasRearm") else "N"),
                        "refuel": "?" if st.get("hasRefuel") is None else ("Y" if st.get("hasRefuel") else "N"),
                        "repair": "?" if st.get("hasRepair") is None else ("Y" if st.get("hasRepair") else "N"),
                    }
                    st_modified = self._parse_ts(st.get("updateTime"))
                    if st_modified:
                        imported_station_modifieds.append(st_modified)
                    
                    ls_from_star_val = st.get("distanceToArrival", 0)
                    try:
                        if ls_from_star_val is None:
                            ls_from_star_val = 0
                        else:
                            ls_from_star_val = int(float(ls_from_star_val))
                            if ls_from_star_val < 0:
                                ls_from_star_val = 0
                    except Exception:
                        ls_from_star_val = 0
                    
                    self._upsert_station(
                        t_station, station_id=int(station_id), system_id=int(sys_id64), name=name,
                        ls_from_star=ls_from_star_val, max_pad=max_pad,
                        type_id=int(type_id), planetary=planetary, sflags=sflags, modified=st_modified
                    )
                    
                    # ----------------------------
                    # Ship vendor
                    # ----------------------------
                    if has_ship and ship_fresh:
                        ships = (st.get("shipyard") or {}).get("ships") or []
                        if isinstance(ships, list) and ships:
                            if force_baseline:
                                wrote, _, delc = self._apply_vendor_block_per_rules(
                                    tables["ShipVendor"], station_id, (s.get("shipId") for s in ships if isinstance(s, dict)),
                                    ship_ts, id_col="ship_id",
                                )
                                if wrote or delc:
                                    stats["ship_writes"] += 1
                                    batch_ops += (wrote + delc)
                                stats["ship_stations"] += 1
                            else:
                                wrote, delc = self._sync_vendor_block_fast(
                                    tables, station_id=station_id, entries=ships, ts_sp=ship_ts, kind="ship"
                                )
                                if wrote or delc:
                                    stats["ship_writes"] += 1
                                    batch_ops += (wrote + delc)
                                stats["ship_stations"] += 1
                        else:
                            stats["ship_stations"] += 1
                    
                    # ----------------------------
                    # Outfitting vendor
                    # ----------------------------
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
                                stats["outfit_stations"] += 1
                            else:
                                wrote, delc = self._sync_vendor_block_fast(
                                    tables, station_id=station_id, entries=modules, ts_sp=outf_ts, kind="module"
                                )
                                if wrote or delc:
                                    stats["outfit_writes"] += 1
                                    batch_ops += (wrote + delc)
                                stats["outfit_stations"] += 1
                        else:
                            stats["outfit_stations"] += 1
                    
                    # ----------------------------
                    # Market (commit check already happened before this station)
                    # ----------------------------
                    if has_market and mkt_fresh:
                        commodities = (st.get("market") or {}).get("commodities") or []
                        if isinstance(commodities, list) and commodities:
                            from ..db.locks import station_advisory_lock
                            # The advisory lock context pins lock + DML to the same connection/txn.
                            with station_advisory_lock(self.session, station_id, timeout_seconds=0.2, max_retries=4) as got:
                                if not got:
                                    # Could not acquire; try this station on a later pass
                                    continue
                                
                                self._trace(phase="market", decision="process",
                                            station_id=station_id, commodities=len(commodities))
                                
                                if force_baseline:
                                    wrote_i, wrote_si = self._upsert_market(
                                        tables, categories, station_id, commodities, mkt_ts
                                    )
                                    # Remove any extras unconditionally (baseline reset)
                                    t_si = tables["StationItem"]
                                    keep_ids = {
                                        int(co.get("commodityId"))
                                        for co in commodities
                                        if isinstance(co, dict) and co.get("commodityId") is not None
                                    }
                                    if keep_ids:
                                        self.session.execute(
                                            t_si.delete().where(
                                                and_(t_si.c.station_id == station_id, ~t_si.c.item_id.in_(keep_ids))
                                            )
                                        )
                                    stats["commodities"] += wrote_si
                                    if wrote_si or wrote_i:
                                        stats["market_writes"] += 1
                                        batch_ops += (wrote_i + wrote_si)
                                    stats["market_stations"] += 1
                                else:
                                    wrote_links, delc = self._sync_market_block_fast(
                                        tables, categories,
                                        station_id=station_id,
                                        commodities=commodities,
                                        ts_sp=mkt_ts,
                                    )
                                    if wrote_links or delc:
                                        stats["market_writes"] += 1
                                        batch_ops += (wrote_links + delc)
                                    stats["market_stations"] += 1
                        else:
                            stats["market_stations"] += 1
        
        # Baseline absent-station cleanup (global, after full stream)
        # We only remove baseline content (from_live=0 for markets; vendor links)
        # and only where modified <= json_ts, so anything newer (e.g. live/ZMQ) is preserved.
        try:
            if force_baseline and seen_station_ids:
                m_del, u_del, s_del = self._cleanup_absent_stations(
                    tables,
                    present_station_ids=seen_station_ids,
                    json_ts=json_ts,
                )
                if (m_del + u_del + s_del) > 0 and self._debug_level >= 1:
                    self._print(
                        f"Baseline cleanup: markets={m_del:,}  upgrades={u_del:,}  ships={s_del:,}"
                    )
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
    def _import_rareitems_edcd(self, rares_csv: Path, commodity_csv: Optional[Path] = None) -> None:
        """
        EDCD rares → TD.RareItem
        
        Supports CSV shapes:
          A) name, system, station
          B) id, symbol, market_id, category, name  (FDevIDs canonical)
        
        Shape B maps: station_id = int(market_id), category by name.
        Clears RareItem then upserts by UNIQUE(name). Writes a CSV of skipped rows to tmp/.
        """
        
        def _norm(s: Optional[str]) -> str:
            if s is None: return ""
            s = s.strip().strip("'").strip('"')
            s = s.replace("’", "'").replace("‘", "'")
            s = s.replace("–", "-").replace("—", "-")
            s = " ".join(s.split())
            return s.casefold()
        
        def _kwant(fieldnames, *aliases) -> Optional[str]:
            if not fieldnames: return None
            canon = {}
            for h in fieldnames or []:
                if not h: continue
                k = h.strip().lower().replace("_", "").replace(" ", "")
                canon[k] = h
            for a in aliases:
                k = a.strip().lower().replace("_", "").replace(" ", "")
                if k in canon: return canon[k]
            return None
        
        sess = None
        try:
            sess = self._open_session()
            tables = self._reflect_tables(sess.get_bind())
            t_sys, t_stn, t_cat, t_rare = tables["System"], tables["Station"], tables["Category"], tables["RareItem"]
            
            # Build lookups for Shape A
            stn_by_names: Dict[tuple[str, str], int] = {}
            for sid, sys_name, stn_name in sess.execute(
                select(t_stn.c.station_id, t_sys.c.name, t_stn.c.name).where(t_stn.c.system_id == t_sys.c.system_id)
            ).all():
                if sys_name and stn_name:
                    stn_by_names[(_norm(sys_name), _norm(stn_name))] = int(sid)
            
            # Category name -> id (from DB)
            cat_id_by_name = {
                _norm(n): int(cid)
                for cid, n in sess.execute(select(t_cat.c.category_id, t_cat.c.name)).all()
                if n is not None
            }
            
            kept = skipped = 0
            skipped_no_station = 0
            skipped_no_category = 0
            out_rows: list[dict] = []
            skipped_rows: list[dict] = []   # <-- record details
            
            with open(rares_csv, "r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                hdr = [h for h in (reader.fieldnames or []) if h]
                hdr_canon = [h.lower().replace("_", "").replace(" ", "") for h in hdr]
                
                has_market_shape = all(x in hdr_canon for x in ["id", "symbol", "marketid", "category", "name"])
                has_name_shape   = all(x in hdr_canon for x in ["name", "system", "station"])
                
                if not (has_market_shape or has_name_shape):
                    raise CleanExit(
                        "rare_commodity.csv headers not recognized. "
                        f"Seen headers: {', '.join(reader.fieldnames or [])}. File: {rares_csv}"
                    )
                
                if has_market_shape:
                    # FDevIDs: station_id = int(market_id)
                    k_name   = _kwant(reader.fieldnames, "name")
                    k_market = _kwant(reader.fieldnames, "market_id", "marketid")
                    k_cat    = _kwant(reader.fieldnames, "category", "categoryname")
                    
                    for row in reader:
                        rn_raw = row.get(k_name)
                        mk_raw = row.get(k_market)
                        cat_raw= row.get(k_cat)
                        
                        try:
                            station_id = int(mk_raw) if mk_raw is not None else None
                        except (TypeError, ValueError):
                            station_id = None
                        
                        # validate station exists
                        if station_id is None or sess.execute(
                            select(t_stn.c.station_id).where(t_stn.c.station_id == station_id)
                        ).first() is None:
                            skipped += 1; skipped_no_station += 1
                            skipped_rows.append({"reason":"no_station","name":rn_raw,"market_id":mk_raw,"category":cat_raw})
                            continue
                        
                        cid = cat_id_by_name.get(_norm(cat_raw))
                        if cid is None:
                            skipped += 1; skipped_no_category += 1
                            skipped_rows.append({"reason":"no_category","name":rn_raw,"market_id":mk_raw,"category":cat_raw})
                            continue
                        
                        out_rows.append({
                            "name": rn_raw,
                            "station_id": station_id,
                            "category_id": cid,
                            "cost": None,
                            "max_allocation": None,
                        })
                        kept += 1
                
                else:
                    # Legacy/community: need commodity.csv to map product -> category
                    name_to_catid: Dict[str, int] = {}
                    if commodity_csv is None:
                        files = self._acquire_edcd_files()
                        commodity_csv = files.get("commodity")
                    if commodity_csv and Path(commodity_csv).exists():
                        with open(commodity_csv, "r", encoding="utf-8", newline="") as fh2:
                            rd2 = csv.DictReader(fh2)
                            k2_name = _kwant(rd2.fieldnames, "name","commodity","commodityname","product")
                            k2_cat  = _kwant(rd2.fieldnames, "category","categoryname")
                            if k2_name and k2_cat:
                                for r2 in rd2:
                                    n = _norm(r2.get(k2_name)); c = _norm(r2.get(k2_cat))
                                    if n and c:
                                        cid = cat_id_by_name.get(c)
                                        if cid is not None:
                                            name_to_catid[n] = cid
                    
                    k_name    = _kwant(reader.fieldnames, "name","commodity","commodityname","product")
                    k_system  = _kwant(reader.fieldnames, "system","systemname")
                    k_station = _kwant(reader.fieldnames, "station","stationname")
                    
                    for row in reader:
                        rn_raw  = row.get(k_name)
                        sys_raw = row.get(k_system)
                        stn_raw = row.get(k_station)
                        rn = _norm(rn_raw); sysn = _norm(sys_raw); stnn = _norm(stn_raw)
                        
                        if not rn or not sysn or not stnn:
                            skipped += 1
                            skipped_rows.append({"reason":"missing_fields","name":rn_raw,"system":sys_raw,"station":stn_raw})
                            continue
                        
                        station_id = stn_by_names.get((sysn, stnn))
                        if station_id is None:
                            skipped += 1; skipped_no_station += 1
                            skipped_rows.append({"reason":"no_station","name":rn_raw,"system":sys_raw,"station":stn_raw})
                            continue
                        
                        cid = name_to_catid.get(rn)
                        if cid is None:
                            skipped += 1; skipped_no_category += 1
                            skipped_rows.append({"reason":"no_category","name":rn_raw,"system":sys_raw,"station":stn_raw})
                            continue
                        
                        out_rows.append({
                            "name": rn_raw,
                            "station_id": station_id,
                            "category_id": cid,
                            "cost": None,
                            "max_allocation": None,
                        })
                        kept += 1
            
            # Clear → upsert
            try:
                sess.execute(text('DELETE FROM "RareItem"'))
            except Exception:
                sess.execute(text("DELETE FROM RareItem"))
            
            if out_rows:
                if db_utils.is_sqlite(sess):
                    db_utils.sqlite_upsert_simple(
                        sess, t_rare, rows=out_rows, key_cols=("name",),
                        update_cols=tuple(k for k in out_rows[0].keys() if k != "name")
                    )
                elif db_utils.is_mysql(sess):
                    db_utils.mysql_upsert_simple(
                        sess, t_rare, rows=out_rows, key_cols=("name",),
                        update_cols=tuple(k for k in out_rows[0].keys() if k != "name")
                    )
                else:
                    for r in out_rows:
                        ex = sess.execute(select(t_rare.c.name).where(t_rare.c.name == r["name"])).first()
                        if ex is None:
                            sess.execute(insert(t_rare).values(**r))
                        else:
                            sess.execute(
                                update(t_rare).where(t_rare.c.name == r["name"])
                                .values({k: r[k] for k in r.keys() if k != "name"})
                            )
            sess.commit()
            
            # Write a CSV with skipped details
            if skipped_rows:
                outp = self.tmp_dir / "edcd_rares_skipped.csv"
                keys = sorted({k for r in skipped_rows for k in r.keys()})
                with open(outp, "w", encoding="utf-8", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=keys)
                    w.writeheader(); w.writerows(skipped_rows)
                self._print(f"EDCD Rares: imported={kept:,}  skipped={skipped:,}  "
                            f"(no_station={skipped_no_station:,}, no_category={skipped_no_category:,})  "
                            f"→ details: {outp}")
            else:
                self._print(f"EDCD Rares: imported={kept:,}  skipped={skipped:,}  "
                            f"(no_station={skipped_no_station:,}, no_category={skipped_no_category:,})")
        
        except Exception as e:
            if sess is not None:
                try: sess.rollback()
                except Exception: pass
            raise CleanExit(f"RareItem import failed: {e!r}")
        finally:
            if sess is not None:
                try: sess.close()
                except Exception: pass


    # ------------------------------
    # Export / cache refresh
    # ------------------------------
    def _export_cache(self) -> None:
        """Export CSVs and regenerate TradeDangerous.prices — concurrently, with optional StationItem gating."""
        
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
            "FDevOutfitting",
            "FDevShipyard",
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
    
    def _mirror_csv_exports(self) -> None:
        """
        If TD_CSV is set, mirror all CSVs emitted into tdenv.dataDir to TD_CSV.
        Avoids running csvexport twice (Spansh already produced the CSVs).
        """
        src_dir = Path(self.tdenv.dataDir).resolve()
        dst_env = os.environ.get("TD_CSV")
        if not dst_env:
            return
        dst_dir = Path(dst_env).expanduser().resolve()
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._warn(f"TD_CSV mirror: unable to create destination {dst_dir}: {e!r}")
            return
        
        copied = 0
        for src in src_dir.glob("*.csv"):
            try:
                shutil.copy2(src, dst_dir / src.name)
                copied += 1
            except Exception as e:
                self._warn(f"TD_CSV mirror: failed to copy {src.name}: {e!r}")
        
        self._print(f"TD_CSV mirror: copied {copied} csv file(s) → {dst_dir}")
    
    def _export_and_mirror(self) -> None:
        """
        Run the normal cache/CSV export, then mirror CSVs to TD_CSV if set.
        Use this in place of a direct _export_cache() call.
        """
        import time
        t0 = time.time()
        self._export_cache()  # existing exporter (unchanged)
        self._print(f"Cache export completed in {time.time()-t0:.2f}s")
        self._mirror_csv_exports()
    
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
        NOTE: As of 2025-10, we removed _parse_progress(). This iterator now
        maintains byte/rate metrics only; rendering is handled by _progress_line().
        """
        start_ts = time.time()
        last_tick_systems = 0
        TICK_EVERY = 256
        
        it = self._ijson_items(fh, 'item')
        for idx, obj in enumerate(it, 1):
            if (idx - last_tick_systems) >= TICK_EVERY:
                last_tick_systems = idx
                # Update parse metrics (no printing here)
                try:
                    pos = fh.tell()
                    elapsed = max(time.time() - start_ts, 1e-9)
                    self._parse_bytes = pos
                    self._parse_rate = pos / elapsed
                except Exception:
                    pass
            yield obj
        
        # Final metric update at EOF
        try:
            pos = fh.tell()
            elapsed = max(time.time() - start_ts, 1e-9)
            self._parse_bytes = pos
            self._parse_rate = pos / elapsed
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
        
        Modes:
          - default (verbose-ish): rich long line
          - compact: shorter, log-friendly line (enable with -O progress_compact=1 or TD_PROGRESS_COMPACT=1)
        """
        now = time.time()
        if now - self._last_progress_time < (0.5 if self._debug_level < 1 else 0.2):
            return
        self._last_progress_time = now
        self._started_importing = True
        
        # Determine compact mode (CLI overrides env; default is rich/False)
        # Truthy whitelist: 1, true, yes, on, y (case-insensitive)
        _opt = self.getOption("progress_compact")
        if _opt is not None:
            _val = str(_opt).strip().lower()
        else:
            _env = os.getenv("TD_PROGRESS_COMPACT")
            _val = "" if _env is None else str(_env).strip().lower()
        compact = _val in {"1", "true", "yes", "on", "y"}
        
        parse_bytes = getattr(self, "_parse_bytes", 0)
        parse_rate  = getattr(self, "_parse_rate", 0.0)
        systems     = stats.get("systems", 0)
        stations    = stats.get("stations", 0)
        
        wm = stats.get("market_writes", 0)
        wo = stats.get("outfit_writes", 0)
        ws = stats.get("ship_writes", 0)
        
        km = stats.get("market_stations", 0)
        ko = stats.get("outfit_stations", 0)
        ks = stats.get("ship_stations", 0)
        
        if compact:
            # Compact, log-friendly (newline prints)
            msg = (
                f"Importing…  {parse_bytes/1048576:.1f} MiB read  {parse_rate/1048576:.1f} MiB/s  "
                f"systems:{systems:,}  stations:{stations:,}  "
                f"checked m/o/s:{km:,}/{ko:,}/{ks:,}  written m/o/s:{wm:,}/{wo:,}/{ws:,}"
            )
            self._print(msg)
            return
        
        # Rich/long line (TTY-optimized; truncated only on TTY)
        msg = (
            f"Importing…  {parse_bytes/1048576:.1f} MiB read  {parse_rate/1048576:.1f} MiB/s  "
            f"[Parsed - Systems: {systems:,} Stations: {stations:,}]  "
            f"Checked(stations): mkt={km:,} outf={ko:,} shp={ks:,}  "
            f"Written(stations): mkt={wm:,} outf={wo:,} shp={ws:,}"
        
        )
        self._live_status(msg)
    
    def _live_line(self, msg: str) -> None:
        self._live_status(msg)
    
    def _live_status(self, msg: str) -> None:
        """
        Live status line for TTY; plain prints for non-TTY.
        IMPORTANT: only truncate when TTY so logs are not cut off.
        """
        try:
            if self._is_tty:
                import shutil
                width = shutil.get_terminal_size(fallback=(120, 20)).columns
                if width and width > 4:
                    msg = msg[: width - 2]
                s = f"\x1b[2K\r{msg}"
                sys.stderr.write(s)
                sys.stderr.flush()
            else:
                # Non-TTY: emit full line, no truncation, no control codes.
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
