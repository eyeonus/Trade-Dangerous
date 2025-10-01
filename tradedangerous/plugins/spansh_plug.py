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
        "pricesonly": "Skip import/exports; regenerate TradeDangerous.prices only (for testing).",
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
        
        # Quick test path: regenerate prices only
        if self.getOption("pricesonly"):
            try:
                self._print("Regenerating TradeDangerous.prices …")
                cache.regeneratePricesFile(self.tdb, self.tdenv)
                self._print("Prices file generated.")
            except Exception as e:
                self._error(f"Prices regeneration failed: {e!r}")
                return False
            return False


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
            # Finalise the live status line and echo a clean summary snapshot
            self._end_live_status()
            self._print(
                f"Import complete — systems: {stats.get('systems', 0):,}  "
                f"stations: {stats.get('stations', 0):,}  "
                f"kept: markets≈{stats.get('market_stations', 0):,} "
                f"outfitters≈{stats.get('outfit_stations', 0):,} "
                f"shipyards≈{stats.get('ship_stations', 0):,}"
            )
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
        Update parse progress (bytes + rate). We still print the 'Parsing' heartbeat
        only *until* importing begins; after that, _progress_line will include these
        metrics to avoid line clobbering.
        """
        now = time.time()
        if now - self._last_progress_time < min_interval:
            # Still store latest metrics even if we don't print this tick.
            elapsed = max(now - start_ts, 1e-9)
            self._parse_bytes = consumed_bytes
            self._parse_rate = consumed_bytes / elapsed
            return
        self._last_progress_time = now

        # Lazily init state holders so we don't need to touch __init__
        if not hasattr(self, "_parse_bytes"):
            self._parse_bytes = 0
        if not hasattr(self, "_parse_rate"):
            self._parse_rate = 0.0
        if not hasattr(self, "_started_importing"):
            self._started_importing = False

        elapsed = max(now - start_ts, 1e-9)
        self._parse_bytes = consumed_bytes
        self._parse_rate = consumed_bytes / elapsed

        # Before importing starts, show the standalone parsing heartbeat.
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
        Create a DB session. If SQLite, enable bulk-write pragmas for this session/connection.
        """
        if hasattr(self.tdb, "Session") and callable(self.tdb.Session):
            sess = self.tdb.Session()
        elif hasattr(db_utils, "get_session"):
            sess = db_utils.get_session(self.tdb.engine)
        else:
            raise RuntimeError("No Session factory available")

        # If SQLite, tune for bulk import speed (per-connection pragmas).
        try:
            if db_utils.is_sqlite(sess):
                db_utils.sqlite_set_bulk_pragmas(sess)
        except Exception:
            # Don't fail the run just because pragmas couldn't be set
            pass

        return sess


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
        """
        Streaming importer with service-level maxage gating (FK-safe).

        Progress counters:
          - systems, stations → attempted upserts
          - commodities → StationItem rows written (kept listings)
          - modules → UpgradeVendor rows written
          - ships → ShipVendor rows written
          - market_stations / outfit_stations / ship_stations → number of stations where that fresh service was processed
        """
        batch_ops = 0
        stats = {
            "systems": 0,
            "stations": 0,
            "commodities": 0,
            "ships": 0,
            "modules": 0,
            "market_stations": 0,
            "outfit_stations": 0,
            "ship_stations": 0,
        }

        maxage_days = float(self.getOption("maxage")) if self.getOption("maxage") else None
        maxage_td = timedelta(days=maxage_days) if maxage_days is not None else None
        now_utc = datetime.utcnow()

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
            try:
                if self._debug_level >= 2:
                    sz = os.path.getsize(source_path)
                    self._print(f"Opened JSON file ({self._fmt_bytes(sz)})")
            except Exception:
                pass

            for sys_idx, system_obj in enumerate(self._iter_top_level_json_array(fh), 1):
                sys_id64 = system_obj.get("id64")
                sys_name = system_obj.get("name")
                coords = system_obj.get("coords") or {}
                if sys_id64 is None or sys_name is None or not isinstance(coords, dict):
                    if self._debug_level >= 3:
                        self._warn(f"Skipping malformed system object at index {sys_idx}")
                    continue

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

                # ---- SYSTEM GATE: any station with at least one fresh service?
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

                # ---- Upsert System FIRST (initial modified)
                x, y, z = coords.get("x"), coords.get("y"), coords.get("z")
                sys_date = self._parse_ts(system_obj.get("date"))
                self._upsert_system(tables["System"], sys_id64, sys_name, x, y, z, sys_date)
                stats["systems"] += 1
                batch_ops += 1

                imported_station_modifieds: List[datetime] = []

                # ---- STATIONS: only those with at least one fresh service
                for st in stations:
                    station_id = st.get("id")
                    st_name = st.get("name")
                    if station_id is None or st_name is None:
                        continue

                    raw_services = st.get("services") or []
                    if not isinstance(raw_services, list):
                        continue
                    services = {s.strip().lower(): s for s in raw_services if isinstance(s, str)}

                    has_market = "market" in services
                    has_outfit = "outfitting" in services
                    has_ship = "shipyard" in services
                    if not (has_market or has_outfit or has_ship):
                        continue

                    # Timestamps per service
                    ship_ts = svc_ts(st, "shipyard") if has_ship else None
                    outf_ts = svc_ts(st, "outfitting") if has_outfit else None
                    mkt_ts = svc_ts(st, "market") if has_market else None

                    ship_fresh = recent(ship_ts)
                    outf_fresh = recent(outf_ts)
                    mkt_fresh = recent(mkt_ts)

                    if not (ship_fresh or outf_fresh or mkt_fresh):
                        continue

                    # Derive Station row fields
                    dist = st.get("distanceToArrival")
                    ls_from_star = int(round(dist)) if isinstance(dist, (int, float)) else 999999
                    type_name = st.get("type")
                    landing = st.get("landingPads") or {}
                    type_id, planetary = self._map_station_type(type_name)
                    max_pad = self._derive_pad_size(landing)

                    # liberalised flags
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

                    # Station.modified = latest of the services we actually import for this station
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

                    # --- Per-service writes (increment kept-* once per station/service) ---
                    if has_ship and ship_fresh:
                        ships = (st.get("shipyard") or {}).get("ships") or []
                        if isinstance(ships, list) and ships:
                            wrote = self._upsert_shipyard(tables, station_id, ships, ship_ts)
                            stats["ships"] += wrote
                            stats["ship_stations"] += 1
                            batch_ops += wrote

                    if has_outfit and outf_fresh:
                        modules = (st.get("outfitting") or {}).get("modules") or []
                        if isinstance(modules, list) and modules:
                            wrote = self._upsert_outfitting(tables, station_id, modules, outf_ts)
                            stats["modules"] += wrote
                            stats["outfit_stations"] += 1
                            batch_ops += wrote

                    if has_market and mkt_fresh:
                        commodities = (st.get("market") or {}).get("commodities") or []
                        if isinstance(commodities, list) and commodities:
                            wrote_i, wrote_si = self._upsert_market(tables, categories, station_id, commodities, mkt_ts)
                            stats["commodities"] += wrote_si   # listings written
                            stats["market_stations"] += 1       # <-- kept market count
                            batch_ops += (wrote_i + wrote_si)

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

                # ---- Finalize System.modified
                sys_modified_final = max(imported_station_modifieds) if imported_station_modifieds else sys_date
                self._upsert_system(tables["System"], sys_id64, sys_name, x, y, z, sys_modified_final)

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

        # Compose the row to insert. Include 'added' for insert semantics only.
        row = {
            "system_id": system_id,
            "name": name,
            "pos_x": x, "pos_y": y, "pos_z": z,
            "modified": modified,
        }
        if has_added_col:
            row["added"] = 20  # EDSM on INSERT

        # --- Dialect fast paths ---
        if db_utils.is_sqlite(self.session):
            # On-conflict update does NOT touch 'added' (insert-only), then fix NULL → 20.
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

            # (no return fall-through)

        if db_utils.is_mysql(self.session):
            # On-dup-key update does NOT touch 'added' (insert-only), then fix NULL → 20.
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

        # --- Generic fallback ---
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
            # Never overwrite 'added' here; fix NULL after update if needed
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
        - Fast-path: delegates to db_utils.{sqlite,mysql}_upsert_modified
        - Fallback: SELECT then INSERT/UPDATE; only bump modified when newer
        """
        if modified is None:
            modified = datetime.utcfromtimestamp(0)

        # Dialect fast paths (keep this plugin DB-agnostic)
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
        """
        Batch upsert shipyard:
          - Ensure Ship rows exist/updated (name) via simple upsert (no timestamp)
          - Bulk upsert ShipVendor rows with timestamp guard (ship_id, station_id, modified)
          - No pre-read short-circuit; rely on ON CONFLICT/ON DUPLICATE guard
        """
        t_ship, t_vendor = tables["Ship"], tables["ShipVendor"]

        ship_rows = []
        vendor_rows = []

        for sh in ships:
            ship_id = sh.get("shipId")
            name = sh.get("name")
            if ship_id is None or name is None:
                continue

            ship_rows.append({"ship_id": ship_id, "name": name})
            vendor_rows.append({"ship_id": ship_id, "station_id": station_id, "modified": ts})

        # Upsert Ship
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

        # Upsert ShipVendor with timestamp guard
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
                        self.session.execute(insert(t_vendor).values(**r))
                        wrote += 1
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

    def _upsert_outfitting(
        self,
        tables: Dict[str, Table],
        station_id: int,
        modules: List[Dict[str, Any]],
        ts: datetime,
    ) -> int:
        """
        Batch upsert outfitting:
          - Ensure Upgrade rows exist/updated via simple upsert (no timestamp)
          - Bulk upsert UpgradeVendor rows with timestamp guard (upgrade_id, station_id, modified)
          - No pre-read short-circuit; rely on ON CONFLICT/ON DUPLICATE guard
        """
        t_up, t_vendor = tables["Upgrade"], tables["UpgradeVendor"]

        up_rows = []
        vendor_rows = []

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

        # Upsert Upgrade
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

        # Upsert UpgradeVendor with timestamp guard
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
                        self.session.execute(insert(t_vendor).values(**r))
                        wrote += 1
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
        """
        Batch upsert market:
          - Ensure Item rows exist/updated via simple upsert (no timestamp)
          - Bulk upsert StationItem rows with timestamp guard (station_id,item_id,modified)
          - No pre-read short-circuit; rely on ON CONFLICT/ON DUPLICATE guard
        """
        t_item, t_si = tables["Item"], tables["StationItem"]

        item_rows = []
        link_rows = []
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

        # Upsert Items (no timestamp guard)
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

        # Upsert StationItem with timestamp guard
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
                        self.session.execute(insert(t_si).values(**r))
                        wrote_links += 1
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
        - Decision is based on the current DB contents (independent of maxage used this run).
        - When writing the filtered file, rows are copied verbatim (no field normalisation).
        """
        import csv

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

            # Read as text lines to preserve exact formatting for kept rows
            with open(rare_src, "r", encoding="utf-8", newline="") as fin, \
                 open(tmp_csv, "w", encoding="utf-8", newline="") as fout:

                lines = fin.readlines()
                if not lines:
                    raise CleanExit(f"RareItem.csv is empty: {rare_src}")

                header_line = lines[0]
                fout.write(header_line)  # write header verbatim

                # Determine column indexes robustly
                # Expected names like: name@System.system_id , name@Station.station_id
                reader = csv.reader([header_line])
                headers = next(reader, [])
                h_norm = [ (h or "").strip().lower() for h in headers ]

                def find_col_idx(kind: str) -> int:
                    # 'kind' is 'system' or 'station'
                    # match if header contains both 'name@<kind>' and either '.system_id' or '.station_id'
                    for i, h in enumerate(h_norm):
                        if "name@" in h and kind in h:
                            return i
                    # fallback: any header that contains the token
                    for i, h in enumerate(h_norm):
                        if kind in h:
                            return i
                    return -1

                idx_sys = find_col_idx("system")
                idx_stn = find_col_idx("station")
                if idx_sys < 0 or idx_stn < 0:
                    # Unexpected header — pass through unchanged to avoid breaking imports.
                    # (Given your file shape, this branch should never be hit.)
                    for line in lines[1:]:
                        fout.write(line)
                        kept = -1  # unknown
                    skipped = 0
                else:
                    # Evaluate each data line: parse minimally to get the two names,
                    # but write the original line text back if we keep it.
                    for line in lines[1:]:
                        # Skip blank lines verbatim?
                        if not line.strip():
                            continue
                        try:
                            row = next(csv.reader([line]))
                        except Exception:
                            # If CSV parse fails, be conservative and skip this line
                            skipped += 1
                            continue

                        # Pull the two names, strip surrounding quotes/space, casefold
                        sys_name = (row[idx_sys] if idx_sys < len(row) else "").strip().strip("'\"").strip().lower()
                        stn_name = (row[idx_stn] if idx_stn < len(row) else "").strip().strip("'\"").strip().lower()

                        if sys_name and stn_name and (sys_name, stn_name) in pairs:
                            fout.write(line)  # write verbatim
                            kept += 1
                        else:
                            skipped += 1

            # Hand the filtered file (verbatim rows) to the existing importer
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
        """
        Export CSVs and regenerate TradeDangerous.prices.
        Uses normal prints (no carriage returns) so output scrolls cleanly.
        """
        sess = None
        try:
            sess = self._open_session()
            self._print("Exporting to cache...")
            for table in (
                "Item", "Station", "System", "StationItem",
                "Ship", "ShipVendor", "Upgrade", "UpgradeVendor",
                "RareItem",
            ):
                self._print(f"  - {table}.csv")
                csvexport.exportTableToFile(sess, self.tdenv, table)

            self._print("Regenerating TradeDangerous.prices …")
            # ✅ Use tdb (not Session) — regeneratePricesFile manages its own session lifecycle
            cache.regeneratePricesFile(self.tdb, self.tdenv)

            self._print("Cache export completed.")
        finally:
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass




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
        High-performance streaming reader for a huge top-level JSON array of systems.
        Requires `ijson` (declared in requirements), which provides a C-backed parser.

        Behaviour:
        - Iterates each top-level array item via ijson.items(fh, 'item').
        - Uses fh.tell() to report parse progress (bytes read + rate) via _parse_progress().
        - Keeps memory flat (no giant string buffers) and stable throughput even on 10–20 GiB dumps.

        Notes:
        - If the input is NOT a JSON array (e.g., NDJSON or concatenated objects), this will fail fast.
            Spansh galaxy dump is an array, so this is acceptable here for speed.
        """
        start_ts = time.time()
        last_tick_systems = 0
        TICK_EVERY = 256  # update progress roughly every 1k systems

        # ijson pulls incrementally from the file object. We tick progress using fh.tell().
        for idx, obj in enumerate(ijson.items(fh, 'item'), 1):
            # Periodic heartbeat (avoid spamming stderr)
            if (idx - last_tick_systems) >= TICK_EVERY:
                last_tick_systems = idx
                try:
                    self._parse_progress(fh.tell(), start_ts)
                except Exception:
                    # Some file-like objects may not support tell(); ignore and keep going.
                    pass

            yield obj

        # Final heartbeat to reflect 100%
        try:
            self._parse_progress(fh.tell(), start_ts)
        except Exception:
            pass

        # Clear the live status line if we were printing on a TTY
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

        Rules:
          - SQLite: single large transaction (None) for maximum throughput.
          - MySQL/MariaDB: large batches (50k) unless overridden.
          - Otherwise: 5000 default.
          - TD_LISTINGS_BATCH env can override (int>0 => that size; <=0 => None).
          - If db_utils.get_import_batch_size(session, profile="spansh") exists, use it first.
        """
        # Prefer project-provided policy
        if self.session is not None and hasattr(db_utils, "get_import_batch_size"):
            try:
                val = db_utils.get_import_batch_size(self.session, profile="spansh")
                if val is not None:
                    return val
            except Exception:
                pass

        # Env override
        raw = os.environ.get("TD_LISTINGS_BATCH")
        if raw is not None:
            try:
                envv = int(raw)
                return envv if envv > 0 else None
            except ValueError:
                pass

        # Backend-specific defaults
        try:
            if db_utils.is_sqlite(self.session):
                return None  # single transaction
            if db_utils.is_mysql(self.session):
                return 50_000
        except Exception:
            pass

        return 5_000 # Conservative default


    # ---- ts/format/logging helpers ----
    def _parse_ts(self, value: Any) -> Optional[datetime]:
        try:
            return db_utils.parse_ts(value)  # UTC-naive, μs=0
        except Exception:
            return None

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        """
        Ensure directory exists (mkdir -p). Raises CleanExit on failure so the
        import can stop cleanly with a readable message.
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise CleanExit(f"Failed to create directory {path}: {e!r}")

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
        - 'markets' = stations with fresh market processed
        - 'outfitters' = stations with fresh outfitting processed
        - 'shipyards' = stations with fresh shipyard processed
        """
        now = time.time()
        if now - self._last_progress_time < (0.5 if self._debug_level < 1 else 0.2):
            return
        self._last_progress_time = now

        self._started_importing = True

        parse_bytes = getattr(self, "_parse_bytes", 0)
        parse_rate = getattr(self, "_parse_rate", 0.0)

        msg = (
            f"Importing…  {self._fmt_bytes(parse_bytes)} read  {self._fmt_bytes(parse_rate)}/s  "
            f"systems: {stats['systems']:,}  "
            f"stations: {stats['stations']:,}  "
            f"kept: markets≈{stats['market_stations']:,} outfitters≈{stats['outfit_stations']:,} shipyards≈{stats['ship_stations']:,}"
        )
        self._live_status(msg)

        self._live_status(msg)


    def _live_line(self, msg: str) -> None:
        """
        DEPRECATED: kept for compatibility. Use _live_status().
        """
        self._live_status(msg)
            
    def _live_status(self, msg: str) -> None:
        """
        Single-line live status (bounded to terminal width to avoid wrapping).
        Uses stderr when TTY; falls back to normal print on non-TTY.
        """
        try:
            import shutil
            width = shutil.get_terminal_size(fallback=(120, 20)).columns
            # Leave a little space so some terminals don't re-wrap on the last column.
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
        """Finish any live status line cleanly and switch to normal scrolling output."""
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
