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
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Mapping, Optional, Tuple

# Framework modules
from .. import plugins, cache, csvexport  # provided by project

# DB helpers (dialect specifics live here)
from ..db import utils as db_utils

# SQLAlchemy
from sqlalchemy import MetaData, Table, select, insert, update, func, and_
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
        self._ensure_dir(self.data_dir)
        self._ensure_dir(self.tmp_dir)

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

        # Acquire source path/stream
        try:
            source_path = self._acquire_source()
        except CleanExit as ce:
            self._warn(str(ce))
            return False
        except Exception as e:
            self._error(f"Acquisition failed: {e!r}")
            return False

        # Ensure DB is initialised (bootstrap hook)
        if not self._ensure_bootstrap():
            return False

        # --- RareItem dance around buildCache ---
        ri_path = Path(self.tdb.dataPath, "RareItem.csv")
        rib_path = ri_path.with_suffix(".tmp")
        try:
            if ri_path.exists():
                if rib_path.exists():
                    rib_path.unlink()
                ri_path.rename(rib_path)

            # Build cache (seeds Added, Category, Item, etc. via lifecycle)
            cache.buildCache(self.tdb, self.tdenv)
        except Exception as e:
            self._error(f"buildCache failed: {e!r}")
            return False
        finally:
            # Always restore RareItem.csv if it was renamed
            if rib_path.exists():
                if ri_path.exists():
                    ri_path.unlink()
                rib_path.rename(ri_path)

        # Open session and decide batching for *spansh*
        try:
            self.session = self._open_session()
            self.batch_size = self._resolve_batch_size()
        except Exception as e:
            self._error(f"Failed to open DB session: {e!r}")
            return False

        # Reflect required tables
        try:
            tables = self._reflect_tables(self.session.get_bind())
        except Exception as e:
            self._error(f"Failed to reflect tables: {e!r}")
            return False

        # Categories (case-insensitive map)
        try:
            categories = self._load_categories(self.session, tables)
        except Exception as e:
            self._error(f"Failed to load categories: {e!r}")
            return False

        # Import Spansh (streaming)
        try:
            if self._debug_level < 1:
                self._print("This will take at least several minutes...")
                self._print("You can increase verbosity (-v) to get a sense of progress")
            self._print("Importing spansh data")
            stats = self._import_stream(source_path, categories, tables)
        except CleanExit as ce:
            self._warn(str(ce))
            self._safe_close_session()
            return False
        except Exception as e:
            self._error(f"Import failed: {e!r}")
            self._safe_close_session()
            return False

        # Enforce Item.ui_order (idempotent)
        try:
            self._enforce_ui_order(self.session, tables)
        except Exception as e:
            self._error(f"ui_order enforcement failed: {e!r}")
            self._safe_close_session()
            return False

        # Final commit
        try:
            self.session.commit()
        except Exception as e:
            self._warn(f"Commit failed at end of import; rolling back. Cause: {e!r}")
            self.session.rollback()
            self._safe_close_session()
            return False

        self._safe_close_session()

        # Import RareItem.csv from templates (now that System/Station exist)
        try:
            self._import_rareitems()
        except CleanExit as ce:
            self._warn(str(ce))
            return False
        except Exception as e:
            self._error(f"RareItem import failed: {e!r}")
            return False

        # Export CSVs + prices
        try:
            self._export_cache()
        except Exception as e:
            self._error(f"Export failed: {e!r}")
            return False

        # Summary
        elapsed = self._format_hms(time.time() - started)
        self._print(
            f"{elapsed}  Done  "
            f"{stats['stations']} st "
            f"{stats['commodities']} co  "
            f"{stats['ships']} sh   "
            f"{stats['modules']} mo"
        )
        return False  # IMPORTANT: stop default flow (prevents reloadCache)



    def finish(self) -> bool:
        """
        No-op: our run() handled everything and returned False,
        so finish() will not be invoked by the command.
        """
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
        Show a single-line 'Parsing' progress with bytes and rate.
        Always enabled (even at low verbosity) so users see it’s alive.
        """
        now = time.time()
        if now - self._last_progress_time < min_interval:
            return
        self._last_progress_time = now

        rate = consumed_bytes / max(now - start_ts, 1e-9)  # B/s
        # format rate and bytes with the same helper used by download
        msg = f"Parsing Spansh: {self._fmt_bytes(consumed_bytes)} read  {self._fmt_bytes(rate)}/s"
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
        if hasattr(self.tdb, "Session") and callable(self.tdb.Session):
            return self.tdb.Session()
        if hasattr(db_utils, "get_session"):
            return db_utils.get_session(self.tdb.engine)
        raise RuntimeError("No Session factory available")

    def _reflect_tables(self, engine: Engine) -> Dict[str, Table]:
        meta = MetaData()
        names = [
            "System",
            "Station",
            "Item",
            "Category",
            "StationItem",
            "Ship",
            "ShipVendor",
            "Upgrade",
            "UpgradeVendor",
        ]
        return {n: Table(n, meta, autoload_with=engine) for n in names}

    def _ensure_bootstrap(self) -> bool:
        """Ensure DB is initialised and ready for import (delegate to project bootstrap if present)."""
        try:
            if hasattr(self.tdb, "bootstrap") and callable(self.tdb.bootstrap):
                self.tdb.bootstrap()
            return True
        except Exception as e:
            self._error(f"Bootstrap failed: {e!r}")
            return False

    # ------------------------------
    # Import (streaming JSON → upserts)
    # ------------------------------
    def _import_stream(self, source_path: Path, categories: Dict[str, int], tables: Dict[str, Table]) -> Dict[str, int]:
        batch_ops = 0
        stats = {"systems": 0, "stations": 0, "commodities": 0, "ships": 0, "modules": 0}

        maxage_days = float(self.getOption("maxage")) if self.getOption("maxage") else None
        maxage_td = timedelta(days=maxage_days) if maxage_days is not None else None
        now_utc = datetime.utcnow()

        def service_recent(ts: Optional[datetime]) -> bool:
            if ts is None:
                return False
            if maxage_td is None:
                return True
            return (now_utc - ts) <= maxage_td

        with open(source_path, "rb") as fh:
            try:
                if self._debug_level >= 2:
                    sz = os.path.getsize(source_path)
                    self._print(f"Opened JSON file ({self._fmt_bytes(sz)})")
            except Exception:
                pass

            for sys_idx, system_obj in enumerate(self._iter_top_level_json_array(fh), 1):
                # --- System ---
                sys_id64 = system_obj.get("id64")
                sys_name = system_obj.get("name")
                coords = system_obj.get("coords") or {}
                sys_modified = self._parse_ts(system_obj.get("date"))

                if sys_id64 is None or sys_name is None or not isinstance(coords, dict):
                    if self._debug_level >= 3:
                        self._warn(f"Skipping malformed system object at index {sys_idx}")
                    continue

                x, y, z = coords.get("x"), coords.get("y"), coords.get("z")
                self._upsert_system(tables["System"], sys_id64, sys_name, x, y, z, sys_modified)
                stats["systems"] += 1
                batch_ops += 1

                # --- Stations: top-level + body-embedded ---
                stations_iter: List[Dict[str, Any]] = []
                if isinstance(system_obj.get("stations"), list):
                    stations_iter.extend(system_obj["stations"])
                bodies = system_obj.get("bodies") or []
                if isinstance(bodies, list):
                    for b in bodies:
                        st = b.get("stations")
                        if isinstance(st, list):
                            stations_iter.extend(st)

                for st in stations_iter:
                    station_id = st.get("id")
                    st_name = st.get("name")
                    if station_id is None or st_name is None:
                        continue

                    # --- Service detection (case-insensitive) ---
                    raw_services = st.get("services") or []
                    if not isinstance(raw_services, list):
                        raw_services = []
                    services = {s.strip().lower(): s for s in raw_services if isinstance(s, str)}

                    has_market = "market" in services
                    has_outfit = "outfitting" in services
                    has_ship = "shipyard" in services

                    if not (has_market or has_outfit or has_ship):
                        continue

                    dist = st.get("distanceToArrival")
                    if isinstance(dist, (int, float)):
                        ls_from_star = int(round(dist))
                    else:
                        ls_from_star = 999999
                    type_name = st.get("type")
                    landing = st.get("landingPads") or {}
                    st_modified = self._parse_ts(st.get("updateTime"))

                    type_id, planetary = self._map_station_type(type_name)
                    max_pad = self._derive_pad_size(landing)

                    # liberalised mappings
                    has_rearm = "restock" in services or "rearm" in services
                    has_blackmkt = "black market" in services or "blackmarket" in services
                    has_refuel = "refuel" in services
                    has_repair = "repair" in services

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

                    self._upsert_station(
                        tables["Station"],
                        station_id, sys_id64, st_name, ls_from_star,
                        max_pad, type_id, planetary, sflags, st_modified
                    )
                    stats["stations"] += 1
                    batch_ops += 1

                    # --- Shipyard ---
                    if has_ship:
                        shipyard = st.get("shipyard") or {}
                        ship_ts = self._parse_ts(shipyard.get("updateTime"))
                        if service_recent(ship_ts):
                            ships = shipyard.get("ships") or []
                            if isinstance(ships, list) and ships:
                                wrote = self._upsert_shipyard(tables, station_id, ships, ship_ts)
                                stats["ships"] += wrote
                                batch_ops += wrote

                    # --- Outfitting ---
                    if has_outfit:
                        outfit = st.get("outfitting") or {}
                        outf_ts = self._parse_ts(outfit.get("updateTime"))
                        if service_recent(outf_ts):
                            modules = outfit.get("modules") or []
                            if isinstance(modules, list) and modules:
                                wrote = self._upsert_outfitting(tables, station_id, modules, outf_ts)
                                stats["modules"] += wrote
                                batch_ops += wrote

                    # --- Market ---
                    if has_market:
                        market = st.get("market") or {}
                        mkt_ts = self._parse_ts(market.get("updateTime"))
                        if service_recent(mkt_ts):
                            commodities = market.get("commodities") or []
                            if isinstance(commodities, list) and commodities:
                                wrote_i, wrote_si = self._upsert_market(
                                    tables, categories, station_id, commodities, mkt_ts
                                )
                                stats["commodities"] += wrote_i
                                batch_ops += (wrote_i + wrote_si)

                    # --- Progress & batching ---
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

        return stats


    # ------------------------------
    # Upsert helpers
    # ------------------------------
    def _upsert_system(
        self, t_system: Table, system_id: int, name: str,
        x: Optional[float], y: Optional[float], z: Optional[float],
        modified: Optional[datetime],
    ) -> None:
        if modified is None:
            row = self.session.execute(
                select(t_system.c.system_id).where(t_system.c.system_id == system_id)
            ).first()
            if row is None:
                self.session.execute(
                    insert(t_system).values(
                        system_id=system_id, name=name, pos_x=x, pos_y=y, pos_z=z, modified=None
                    )
                )
            return

        row = self.session.execute(
            select(t_system.c.modified).where(t_system.c.system_id == system_id)
        ).first()

        if row is None:
            self.session.execute(
                insert(t_system).values(
                    system_id=system_id, name=name, pos_x=x, pos_y=y, pos_z=z, modified=modified
                )
            )
        else:
            db_modified = row[0]
            if db_modified is None or modified > db_modified:
                self.session.execute(
                    update(t_system)
                    .where(t_system.c.system_id == system_id)
                    .values(name=name, pos_x=x, pos_y=y, pos_z=z, modified=modified)
                )

    def _upsert_station(
        self, t_station: Table, station_id: int, system_id: int, name: str,
        ls_from_star: Optional[float], max_pad: str, type_id: int, planetary: bool,
        sflags: Dict[str, str], modified: Optional[datetime],
    ) -> None:
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
            return

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
            values["modified"] = modified or db_modified

        if modified is not None and (db_modified is None or modified > db_modified):
            values["modified"] = modified

        self.session.execute(
            update(t_station).where(t_station.c.station_id == station_id).values(**values)
        )

    def _upsert_shipyard(self, tables: Dict[str, Table], station_id: int, ships: List[Dict[str, Any]], ts: datetime) -> int:
        t_ship, t_vendor = tables["Ship"], tables["ShipVendor"]
        row = self.session.execute(
            select(func.max(t_vendor.c.modified)).where(t_vendor.c.station_id == station_id)
        ).first()
        if row and row[0] and row[0] >= ts:
            return 0

        wrote = 0
        for sh in ships:
            ship_id = sh.get("shipId")
            name = sh.get("name")
            if ship_id is None or name is None:
                continue

            exists = self.session.execute(
                select(t_ship.c.ship_id, t_ship.c.name).where(t_ship.c.ship_id == ship_id)
            ).first()
            if exists is None:
                self.session.execute(insert(t_ship).values(ship_id=ship_id, name=name))
            else:
                _, db_name = exists
                if db_name != name:
                    self.session.execute(
                        update(t_ship).where(t_ship.c.ship_id == ship_id).values(name=name)
                    )

            ven = self.session.execute(
                select(t_vendor.c.modified).where(and_(t_vendor.c.ship_id == ship_id, t_vendor.c.station_id == station_id))
            ).first()
            if ven is None:
                self.session.execute(insert(t_vendor).values(ship_id=ship_id, station_id=station_id, modified=ts))
                wrote += 1
            else:
                dbm = ven[0]
                if dbm is None or ts > dbm:
                    self.session.execute(
                        update(t_vendor)
                        .where(and_(t_vendor.c.ship_id == ship_id, t_vendor.c.station_id == station_id))
                        .values(modified=ts)
                    )
                    wrote += 1
        return wrote

    def _upsert_outfitting(
        self,
        tables: Dict[str, Table],
        station_id: int,
        modules: List[Dict[str, Any]],
        ts: datetime,
    ) -> int:
        t_up, t_vendor = tables["Upgrade"], tables["UpgradeVendor"]
        row = self.session.execute(
            select(func.max(t_vendor.c.modified)).where(t_vendor.c.station_id == station_id)
        ).first()
        if row and row[0] and row[0] >= ts:
            return 0

        wrote = 0
        for mo in modules:
            up_id = mo.get("moduleId")
            name = mo.get("name")
            cls = mo.get("class")
            rating = mo.get("rating")
            ship = mo.get("ship")
            if up_id is None or name is None:
                continue

            # --- Upgrade table upsert (no "modified" column here) ---
            exists = self.session.execute(
                select(
                    t_up.c.upgrade_id,
                    t_up.c.name,
                    t_up.c["class"],
                    t_up.c.rating,
                    t_up.c.ship,
                ).where(t_up.c.upgrade_id == up_id)
            ).first()

            if exists is None:
                self.session.execute(
                    insert(t_up).values(
                        upgrade_id=up_id,
                        name=name,
                        **{"class": cls},
                        rating=rating,
                        ship=ship,
                    )
                )
            else:
                _, db_name, db_class, db_rating, db_ship = exists
                if (db_name != name) or (db_class != cls) or (db_rating != rating) or (db_ship != ship):
                    self.session.execute(
                        update(t_up)
                        .where(t_up.c.upgrade_id == up_id)
                        .values(
                            name=name,
                            **{"class": cls},
                            rating=rating,
                            ship=ship,
                        )
                    )

            # --- UpgradeVendor upsert (timestamp lives here) ---
            ven = self.session.execute(
                select(t_vendor.c.modified).where(
                    and_(t_vendor.c.upgrade_id == up_id, t_vendor.c.station_id == station_id)
                )
            ).first()
            if ven is None:
                self.session.execute(
                    insert(t_vendor).values(upgrade_id=up_id, station_id=station_id, modified=ts)
                )
                wrote += 1
            else:
                dbm = ven[0]
                if dbm is None or ts > dbm:
                    self.session.execute(
                        update(t_vendor)
                        .where(and_(t_vendor.c.upgrade_id == up_id, t_vendor.c.station_id == station_id))
                        .values(modified=ts)
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
        """
        Upsert market commodities for a station.

        - Creates new Item rows if missing, keyed by fdev_id (commodityId).
        - Never touches avg_price (Listener maintains that).
        - Ensures Item.name/category_id stay correct.
        - Updates/creates StationItem rows with current supply/demand/prices.
        """
        t_item, t_si = tables["Item"], tables["StationItem"]
        wrote_items = 0
        wrote_links = 0

        row = self.session.execute(
            select(func.max(t_si.c.modified)).where(t_si.c.station_id == station_id)
        ).first()
        if row and row[0] and row[0] >= ts:
            return (0, 0)

        for co in commodities:
            fdev_id = co.get("commodityId")
            name = co.get("name")
            cat_name = co.get("category")
            if fdev_id is None or name is None or cat_name is None:
                continue

            cat_id = categories.get(str(cat_name).lower())
            if cat_id is None:
                raise CleanExit(f'Unknown commodity category "{cat_name}"')

            # --- Item upsert (ignores avg_price) ---
            item_row = self.session.execute(
                select(t_item.c.item_id, t_item.c.name, t_item.c.category_id).where(t_item.c.fdev_id == fdev_id)
            ).first()

            if item_row is None:
                # Insert new item with minimal fields
                self.session.execute(
                    insert(t_item).values(
                        item_id=fdev_id,
                        name=name,
                        category_id=cat_id,
                        fdev_id=fdev_id,
                        ui_order=0,
                    )
                )
                wrote_items += 1
                item_id = fdev_id
            else:
                item_id, db_name, db_cat = item_row
                # Update only if name or category differs; do not touch avg_price
                if (db_name != name) or (db_cat != cat_id):
                    self.session.execute(
                        update(t_item)
                        .where(t_item.c.item_id == item_id)
                        .values(name=name, category_id=cat_id)
                    )

            # --- StationItem upsert ---
            demand = co.get("demand")
            supply = co.get("supply")
            buy = co.get("buyPrice")
            sell = co.get("sellPrice")

            si = self.session.execute(
                select(t_si.c.modified).where(and_(t_si.c.station_id == station_id, t_si.c.item_id == item_id))
            ).first()

            values = dict(
                station_id=station_id,
                item_id=item_id,
                demand_price=sell,
                demand_units=demand,
                demand_level=-1,
                supply_price=buy,
                supply_units=supply,
                supply_level=-1,
                from_live=0,
                modified=ts,
            )

            if si is None:
                self.session.execute(insert(t_si).values(**values))
                wrote_links += 1
            else:
                dbm = si[0]
                if dbm is None or ts > dbm:
                    self.session.execute(
                        update(t_si)
                        .where(and_(t_si.c.station_id == station_id, t_si.c.item_id == item_id))
                        .values(**values)
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
        """Import RareItem.csv from templates via cache.processImportFile()."""
        rare_src = None
        if hasattr(self.tdenv, "templateDir") and self.tdenv.templateDir:
            candidate = Path(self.tdenv.templateDir) / "RareItem.csv"
            if candidate.exists():
                rare_src = candidate
        if rare_src is None:
            rare_src = (Path(__file__).resolve().parents[1] / "templates" / "RareItem.csv")

        if not rare_src.exists():
            raise CleanExit(f"RareItem.csv not found at {rare_src}")

        sess = None
        try:
            sess = self._open_session()
            cache.processImportFile(self.tdenv, sess, rare_src, "RareItem")
            sess.commit()
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

    # ------------------------------
    # Export / cache refresh
    # ------------------------------
    def _export_cache(self) -> None:
        sess = None
        try:
            sess = self._open_session()
            self._print("Exporting to cache...")
            for table in (
                "Item", "Station", "System", "StationItem",
                "Ship", "ShipVendor", "Upgrade", "UpgradeVendor",
                "RareItem",
            ):
                self._print(f"Exporting {table}.csv            ", end="\r")
                csvexport.exportTableToFile(sess, self.tdenv, table)
            self._print("Exporting TradeDangerous.prices", end="\r")
            cache.regeneratePricesFile(sess, self.tdenv)
        finally:
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
        self._print("Cache export completed")

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
    def _iter_top_level_json_array(self, fh: io.BufferedReader) -> Generator[Dict[str, Any], None, None]:
        """
        Robust streaming JSON reader:
          - Handles a top-level array of objects (primary format).
          - Falls back to concatenated objects (NDJSON-like) if no '[' found.
          - Uses an incremental UTF-8 decoder to avoid partial-codepoint issues.
          - Emits a single-line heartbeat (like download) as it reads.
        """
        import codecs
        decoder = json.JSONDecoder()
        inc = codecs.getincrementaldecoder("utf-8")()
        buf = ""
        bbuf = b""
        chunk_size = 2 * 1024 * 1024  # 2 MiB bytes
        consumed_bytes = 0
        start_ts = time.time()

        def fill() -> bool:
            nonlocal bbuf, buf, consumed_bytes
            data = fh.read(chunk_size)
            if not data:
                return False
            consumed_bytes += len(data)
            # single-line parse progress (always on, throttled)
            self._parse_progress(consumed_bytes, start_ts)
            bbuf += data
            # decode available bytes; incremental decoder buffers partials internally
            buf += inc.decode(bbuf)
            bbuf = b""
            return True

        # Prime buffer
        if not fill():
            raise CleanExit("Empty JSON input")

        # Probe first non-space char to decide mode
        i = 0
        while i < len(buf) and buf[i].isspace():
            i += 1
        if i >= len(buf):
            while fill():
                while i < len(buf) and buf[i].isspace():
                    i += 1
                if i < len(buf):
                    break
            if i >= len(buf):
                raise CleanExit("Unexpected EOF before JSON content")

        mode_array = buf[i] == "["

        # If not an array, attempt concatenated-object mode
        if not mode_array and buf[i] != "{":
            raise CleanExit("Invalid JSON: expected '[' (array) or '{' (object stream) at start")

        pos = i + (1 if mode_array else 0)  # skip '[' in array mode
        first = True

        while True:
            # Skip whitespace and commas (array mode)
            while True:
                while pos < len(buf) and buf[pos].isspace():
                    pos += 1
                if mode_array and not first and pos < len(buf) and buf[pos] == ",":
                    pos += 1
                    while pos < len(buf) and buf[pos].isspace():
                        pos += 1
                break
            first = False

            # End of array?
            if mode_array:
                while pos >= len(buf):
                    if not fill():
                        break
                if pos < len(buf) and buf[pos] == "]":
                    # clear the live line once finished (TTY only)
                    if self._is_tty:
                        self._live_status("")  # clears line
                    return

            # Decode one object
            while True:
                try:
                    obj, end = decoder.raw_decode(buf, pos)
                    pos = end
                    yield obj
                    # Trim buffer periodically to control growth
                    if pos > (8 * 1024 * 1024):
                        buf = buf[pos:]
                        pos = 0
                    break
                except json.JSONDecodeError:
                    if not fill():
                        # Final attempt on EOF
                        try:
                            obj, end = decoder.raw_decode(buf, pos)
                            pos = end
                            yield obj
                        except Exception:
                            raise CleanExit("Truncated or malformed JSON at EOF")
                        if self._is_tty:
                            self._live_status("")  # clear line
                        return



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
        Prefer utils.get_import_batch_size(session, profile="spansh"); else env; else fallback.
        """
        if self.session is not None and hasattr(db_utils, "get_import_batch_size"):
            try:
                return db_utils.get_import_batch_size(self.session, profile="spansh")  # may be None
            except Exception:
                pass

        raw = os.environ.get("TD_LISTINGS_BATCH")
        if raw is not None:
            try:
                val = int(raw)
                return val if val > 0 else None
            except ValueError:
                return None

        return 5000  # conservative default

    # ---- ts/format/logging helpers ----
    def _parse_ts(self, value: Any) -> Optional[datetime]:
        try:
            return db_utils.parse_ts(value)  # UTC-naive, μs=0
        except Exception:
            return None

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

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
        now = time.time()
        if now - self._last_progress_time < (0.5 if self._debug_level < 1 else 0.2):
            return
        self._last_progress_time = now
        msg = (
            f"Importing…  systems: {stats['systems']:,}  "
            f"stations: {stats['stations']:,}  "
            f"kept: mkt≈{stats['commodities']:,} outf≈{stats['modules']:,} shp≈{stats['ships']:,}"
        )
        self._live_status(msg)


    def _live_line(self, msg: str) -> None:
        """
        DEPRECATED: kept for compatibility. Use _live_status().
        """
        self._live_status(msg)
            
    def _live_status(self, msg: str) -> None:
        """
        Single-line live status (clears previous line to avoid tail artifacts).
        Uses stderr when TTY; falls back to normal print on non-TTY.
        """
        s = f"\x1b[2K\r{msg}"
        try:
            if self._is_tty:
                sys.stderr.write(s)
                sys.stderr.flush()
            else:
                self._print(msg)
        except Exception:
            self._print(msg)


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
