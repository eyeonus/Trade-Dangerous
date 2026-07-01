"""
Import plugin that uses data files from
https://elite.tromador.com/ to update the Database.
"""
from __future__ import annotations

from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from pathlib import Path
import csv
import datetime
import hashlib
import json
import os
import requests
import time
import typing

from sqlalchemy import delete, exists, func, insert, select, text

from tradedangerous import plugins, transfers, TradeException
from tradedangerous.db import import_csv as td_cache
from tradedangerous.db import orm_models as SA, lifecycle
from tradedangerous.db.utils import (
    begin_bulk_mode, end_bulk_mode,
    get_import_batch_size,
)
from tradedangerous.fs import file_line_count
from tradedangerous.misc import progress as pbar
from tradedangerous.plugins import PluginException

if typing.TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from tradedangerous.tradeenv import TradeEnv


# Constants
BASE_URL = os.environ.get('TD_SERVER') or "https://elite.tromador.com/files/"


class DecodingError(PluginException):
    pass


@contextmanager
def bench(label: str, tdenv: TradeEnv):
    started = time.time()
    with pbar.Progress(0, 40, label=label, style=pbar.ElapsedBar):
        yield
    tdenv.NOTE("{} done ({:.3f}s)", label, time.time() - started)


def _count_listing_entries(tdenv: TradeEnv, listings: Path) -> int:
    """ Calculates the number of entries in a listing file by counting the lines. """
    if not listings.exists():
        tdenv.NOTE("File not found, aborting: {}", listings)
        return 0
    
    tdenv.DEBUG0(f"Getting total number of entries in {listings}...")
    count = file_line_count(listings)
    if count <= 1:
        if count == 1:
            tdenv.DEBUG0("Listing count of 1 suggests nothing but a header")
        else:
            tdenv.DEBUG0("Listings file is empty, nothing to do.")
        return 0
    
    return count + 1  # kfsone: Doesn't the header already make this + 1?


def _make_item_id_lookup(tdenv: TradeEnv, session: Session) -> frozenset[int]:
    """Helper: retrieve the list of commodities in database."""
    tdenv.DEBUG0("Getting list of commodities...")
    rows = session.query(SA.Item.item_id).all()
    return frozenset(r[0] for r in rows)


def _make_station_id_lookup(tdenv: TradeEnv, session: Session) -> frozenset[int]:
    """Helper: retrieve the list of station IDs in database."""
    tdenv.DEBUG0("Getting list of stations...")
    rows = session.query(SA.Station.station_id).all()
    return frozenset(r[0] for r in rows)


class ImportPlugin(plugins.ImportPluginBase):
    """
    Import plugin that uses data files from
    https://elite.tromador.com/ to update the Database.
    """
    pluginOptions = {
        'item':         "Update Items using latest file from server. (Implies '-O system,station')",
        'ship':         "Update Ships using latest file from server.",
        'system':       "Update Systems using latest file from server.",
        'station':      "Update Stations using latest file from server. (Implies '-O system')",
        'shipvend':     "Update ShipVendors using latest file from server. (Implies '-O system,station,ship')",
        'listings':     "Update market data using latest listings.csv dump. (Implies '-O item,system,station')",
        'all':          "Update everything with latest dumpfiles. (Regenerates all tables)",
        'clean':        "Erase entire database and rebuild from empty. (Regenerates all tables.)",
        'skipvend':     "Don't regenerate ShipVendors. (Supercedes '-O all', '-O clean'.)",
        'force':        "Force regeneration of selected items even if source file not updated since previous run. "
                        "(Useful for updating Vendor tables if they were skipped during a '-O clean' run.)",
        'purge':        "Remove any empty systems that previously had fleet carriers.",
        'optimize':     "Optimize ('vacuum') database after processing.",
        'solo':         "Don't download crowd-sourced market data. "
                        "(Implies '-O skipvend', supercedes '-O all', '-O clean', '-O listings'.)",
        '7days':        "Ignore data more than 7 days old during import, and expire old records after import.",
        'units':        "Treat listing entries with 0 units as having the corresponding supply/demand price treated "
                        "as 0. This stops things like Tritium showing up where it's not available but someone was "
                        "able to sell it.",
    }
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
        
        self.dataPath = os.environ.get('TD_EDDB') or self.tdenv.tmpDir
        self.categoriesPath = Path("Category.csv")
        self.commoditiesPath = Path("Item.csv")
        self.shipPath = Path("Ship.csv")
        self.urlShipyard = "https://raw.githubusercontent.com/EDCD/FDevIDs/master/shipyard.csv"
        self.FDevShipyardPath = self.tdb.data_dir / Path("FDevShipyard.csv")
        self.shipVendorPath = Path("ShipVendor.csv")
        self.stationsPath = Path("Station.csv")
        self.sysPath = Path("System.csv")
        self.listingsPath = Path("listings.csv")
        self.liveListingsPath = Path("listings-live.csv")
        self.pricesPath = Path("listings.prices")
    
    def _import_monitor(self):
        return getattr(self.tdenv, 'import_monitor', None)

    def _set_import_status(self, text: str) -> None:
        monitor = self._import_monitor()
        if monitor is not None:
            monitor.set_status(text)

    def _set_import_parent_progress(
        self,
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> None:
        monitor = self._import_monitor()
        if monitor is not None:
            monitor.set_parent_progress(label, value, total)

    def _set_import_child_progress(
        self,
        label: str | None,
        value: int | None,
        total: int | None,
    ) -> None:
        monitor = self._import_monitor()
        if monitor is not None:
            monitor.set_child_progress(label, value, total)

    def _check_import_stop(self) -> None:
        monitor = self._import_monitor()
        if monitor is not None and monitor.stop_requested():
            raise TradeException("Import stopped by user.")

    def now(self):
        return datetime.datetime.now().strftime('%H:%M:%S')

    def _eddblink_state_path(self) -> Path:
        """
        Single sidecar state file stored in TD_DATA (tdb.data_dir).
        This is the authoritative record of "downloaded from server" identity.
        """
        return (self.tdb.data_dir / "eddblink_state.json").resolve()

    def _load_eddblink_state(self) -> dict:
        state_path = self._eddblink_state_path()
        if not state_path.exists():
            return {"version": 1, "files": {}}

        try:
            with state_path.open("r", encoding="utf-8") as fh:
                state = json.load(fh)
            if not isinstance(state, dict):
                return {"version": 1, "files": {}}
            state.setdefault("version", 1)
            files = state.setdefault("files", {})
            if not isinstance(files, dict):
                state["files"] = {}
            return state
        except Exception:
            # Corrupt/partial JSON shouldn't brick the importer; treat as "no state"
            return {"version": 1, "files": {}}

    def _save_eddblink_state(self, state: dict) -> None:
        state_path = self._eddblink_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = state_path.with_name(state_path.name + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
            fh.write("\n")
        tmp_path.replace(state_path)

    def _file_sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _sanity_check_category_root(self) -> None:
        """
        Category is foundational. If it's wrong, the DB is not trustworthy.
        Minimal check: Category.category_id == 1 must be 'Metals' (case-insensitive).
        """
        rebuild_cmd = "trade import -P eddblink -O clean,skipvend"

        try:
            with self.tdb.session_maker() as session:
                row = session.execute(
                    select(SA.Category.category_id, SA.Category.name)
                    .where(SA.Category.category_id == 1)
                ).first()
        except Exception as e:
            raise PluginException(
                "Category table check failed (missing schema or broken DB).\n"
                "This DB is not usable; rebuild your local database with:\n"
                f"    {rebuild_cmd}"
            ) from e

        if not row:
            raise PluginException(
                "Category table is missing/empty.\n"
                "This DB is not usable; rebuild your local database with:\n"
                f"    {rebuild_cmd}"
            )

        name = row[1]
        got = (str(name) if name is not None else "").strip()
        if got.lower() != "metals":
            raise PluginException(
                "Category table is corrupt: category_id=1 expected 'Metals'.\n"
                f"Got: {got!r}\n"
                "This DB is not trustworthy; rebuild your local database with:\n"
                f"    {rebuild_cmd}"
            )


    def downloadFile(self, path):
        """
        Fetch the latest dumpfile from the website based on server identity,
        not local mtime.

        Proof-of-sync is stored in TD_DATA/eddblink_state.json.
        If there's no state entry for a file, it is considered out-of-sync
        (e.g. template-copied files) and will be downloaded.
        """
        if path not in (self.liveListingsPath, self.listingsPath):
            localPath = Path(self.tdb.data_dir, path)
        else:
            localPath = Path(self.dataPath, path)

        url = BASE_URL + str(path)
        key = str(path)

        self.tdenv.NOTE("Checking for update to '{}'.", path)

        state = self._load_eddblink_state()
        files_state = state.setdefault("files", {})
        entry = files_state.get(key)

        # Local integrity check against recorded state (detect template clobber / manual edits).
        in_sync_locally = False
        if entry and localPath.exists():
            try:
                st = localPath.stat()
                if int(entry.get("size", -1)) == int(st.st_size):
                    want_sha = entry.get("sha256")
                    if want_sha:
                        got_sha = self._file_sha256(localPath)
                        if got_sha == want_sha:
                            in_sync_locally = True
                    else:
                        in_sync_locally = True
            except Exception:
                in_sync_locally = False

        # HEAD request for remote identity (ETag/Last-Modified)
        headers = {"User-Agent": "Trade-Dangerous", "Accept-Encoding": "identity"}
        try:
            response = requests.head(url, headers=headers, timeout=70)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.tdenv.WARN("Problem with download:\n    URL: {}\n    Error: {}", url, str(e))
            return False

        if not getattr(response, "ok", False):
            self.tdenv.WARN("Problem with download:\n    URL: {}\n    HTTP: {}", url, getattr(response, "status_code", "?"))
            return False

        remote_etag = response.headers.get("etag")
        remote_last_modified = response.headers.get("last-modified")
        remote_length = response.headers.get("content-length")

        dump_mod_time = None
        if remote_last_modified:
            try:
                dump_mod_time = parsedate_to_datetime(remote_last_modified).timestamp()
            except Exception:
                dump_mod_time = None

        # If we have a prior server-proven state AND local file matches that state,
        # we can skip downloading when remote identity matches.
        if entry and in_sync_locally:
            # Prefer ETag when available; else fall back to Last-Modified.
            if remote_etag and entry.get("etag") == remote_etag:
                self.tdenv.DEBUG0("'{}': Remote ETag matches state; no download.", path)
                return False
            if (not remote_etag) and remote_last_modified and entry.get("last_modified") == remote_last_modified:
                self.tdenv.DEBUG0("'{}': Remote Last-Modified matches state; no download.", path)
                return False

        # If state is missing, or local doesn't match recorded state, or remote identity differs -> download.
        self.tdenv.NOTE("Downloading file '{}'.", path)
        transfers.download(self.tdenv, url, localPath, chunkSize=16384, length=remote_length)

        # Change timestamps on the file to match the server (human convenience only)
        if dump_mod_time is not None:
            try:
                os.utime(localPath, (dump_mod_time, dump_mod_time))
            except Exception:
                pass

        # Update sync state (stored in TD_DATA regardless of localPath location)
        try:
            st = localPath.stat()
            new_entry = {
                "url": url,
                "local_path": str(localPath.resolve()),
                "etag": remote_etag,
                "last_modified": remote_last_modified,
                "content_length": remote_length,
                "downloaded_at": datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat(),
                "size": int(st.st_size),
            }

            # Hash only the small “truth-critical” files (cheap + detects template clobber cleanly).
            if key in ("Category.csv", "Item.csv"):
                new_entry["sha256"] = self._file_sha256(localPath)

            files_state[key] = new_entry
            self._save_eddblink_state(state)
        except Exception:
            # State failures must not make downloads fail.
            pass

        return True
    
    def purgeSystems(self):
        """
        Purges systems from the System table that do not have any stations claiming to be in them.
        Keeps table from becoming too large because of fleet carriers moving to unpopulated systems.
        """
        self.tdenv.NOTE("Purging Systems with no stations: Start time = {}", self.now())
        
        with self.tdb.session_maker.begin() as session:
            subq = select(SA.Station.system_id).where(SA.Station.system_id == SA.System.system_id)
            stmt = delete(SA.System).where(~exists(subq))
            session.execute(stmt)
        
        self.tdenv.NOTE("Finished purging Systems. End time = {}", self.now())
    
    def importListings(self, listings_file):
        """
        Updates the market data (StationItem) using `listings_file`.

        Station snapshot write rule (docs/station_snapshot_write_rule.md):
        a station's market arrives as a whole snapshot, never piecemeal,
        so per station:
          - If the database already holds a newer row for the station →
            skip the WHOLE station (write nothing, delete nothing).
          - Otherwise → delete every existing row for the station and
            insert the snapshot's rows, all at the snapshot timestamp.
        Per-row merging is forbidden: it leaves older catalogue extras
        underneath fresher data, which is exactly the mixed-timestamp
        fault this rule removes.
        """
        listings_path = Path(self.dataPath, listings_file).absolute()
        from_live = listings_path != Path(self.dataPath, self.listingsPath).absolute()
        
        self.tdenv.NOTE("Checking listings")
        total = _count_listing_entries(self.tdenv, listings_path)
        if not total:
            self.tdenv.NOTE("No listings")
            return
        
        self.tdenv.NOTE(
            "Processing market data from {}: Start time = {}, Live = {}",
            listings_file, self.now(), from_live
        )
        
        # Prefetch item/station IDs for early filtering
        with self.tdb.session_maker() as session:
            item_lookup = _make_item_id_lookup(self.tdenv, session)
            station_lookup = _make_station_id_lookup(self.tdenv, session)
        
        self.tdenv.DEBUG0("Processing entries...")
        
        with pbar.Progress(total, 40, label="Processing", style=pbar.LongRunningCountBar) as prog, \
               listings_path.open("r", encoding="utf-8", errors="ignore") as fh, \
               self.tdb.session_maker() as session:
            
            token = begin_bulk_mode(session, profile="eddblink", phase="incremental")
            try:
                commit_batch = get_import_batch_size(session, profile="eddblink")
                execute_batch = commit_batch or 10000  # cap statement size even if single final commit

                table = SA.StationItem.__table__

                # The skip test needs each station's newest existing row.
                # One GROUP BY scan up front beats ~100k per-station MAX()
                # probes and is dialect-neutral. Updated in place as
                # snapshots land so a station repeated later in the file
                # compares against what was just written.
                newest_existing = {
                    int(sid): newest
                    for sid, newest in session.execute(
                        select(table.c.station_id, func.max(table.c.modified))
                        .group_by(table.c.station_id)
                    )
                }

                since_commit = 0
                processed_rows = 0
                
                # GUI-only: publish the active listings phase and clear any
                # parent progress carried over from an earlier import phase.
                # These calls are dormant for CLI use unless a GUI monitor exists.
                self._set_import_status(
                    f"Processing market data from {listings_file}..."
                )
                self._set_import_parent_progress(None, None, None)
                self._set_import_child_progress(
                    f"Processing {listings_file}",
                    0,
                    total,
                )
                
                # optimize away millions of lookups
                increment = prog.increment
                
                def bump_progress():
                    nonlocal processed_rows
                    # GUI-only: honour cooperative stop requests during the long
                    # listings pass and mirror determinate row progress into the
                    # NiceGUI import status strip.
                    self._check_import_stop()
                    increment(1)
                    processed_rows += 1
                    self._set_import_child_progress(
                        f"Processing {listings_file}",
                        processed_rows,
                        total,
                    )
                
                from_timestamp = datetime.datetime.fromtimestamp
                utc = datetime.timezone.utc
                from_live_val = int(from_live)
                week_in_seconds = 7 * 24 * 60 * 60
                time_cutoff = 0 if not self.getOption("7days") else time.time() - week_in_seconds
                squelch_zero_units = self.getOption("units")
                
                # Columns:
                #
                #   id, station_id, commodity_id, supply, supply_bracket, buy_price, sell_price, demand, demand_bracket, collected_at
                #   0   1           2             3       4               5          6           7       8               9
                reader = iter(csv.reader(fh))
                headers = next(reader)
                expect_headers = [
                    "id", "station_id", "commodity_id",
                    "supply", "supply_bracket", "buy_price",
                    "sell_price", "demand", "demand_bracket",
                    "collected_at"
                ]
                if headers[:10] != expect_headers:
                    raise TradeException(
                        f"incompatible csv field organization in {listings_path}. "
                        f"expected {expect_headers}; got {headers}"
                    )
                
                # Snapshots are applied in batches: delete the batch's
                # stations in one IN-list statement, insert their rows in
                # one executemany. Group state accumulates the current
                # station's rows until the file moves to the next station.
                pending_station_ids = []
                pending_station_set = set()
                pending_rows = []

                group_station_id = None
                group_known = False
                group_rows = {}   # item_id -> row dict; last occurrence wins
                group_max_ts = 0

                def flush_pending():
                    nonlocal since_commit
                    if not pending_station_ids:
                        return
                    session.execute(
                        table.delete().where(
                            table.c.station_id.in_(pending_station_ids)
                        )
                    )
                    if pending_rows:
                        session.execute(insert(table), pending_rows)
                    since_commit += len(pending_rows)
                    pending_station_ids.clear()
                    pending_station_set.clear()
                    pending_rows.clear()
                    if commit_batch and since_commit >= commit_batch:
                        session.commit()
                        since_commit = 0

                def close_group():
                    nonlocal group_station_id, group_known, group_rows, group_max_ts
                    station_id, known = group_station_id, group_known
                    rows, max_ts = group_rows, group_max_ts
                    group_station_id = None
                    group_known = False
                    group_rows = {}
                    group_max_ts = 0
                    if station_id is None or not known:
                        return
                    if not rows:
                        # Every row in the snapshot was junk (zero-priced or
                        # unknown items) — skip rather than wipe, mirroring
                        # the spansh writer's caution about bad input.
                        return
                    if time_cutoff and max_ts < time_cutoff:
                        return
                    snapshot_ts = from_timestamp(max_ts, utc)
                    newest = newest_existing.get(station_id)
                    if newest is not None and newest > snapshot_ts:
                        # Database already holds fresher data — the whole
                        # station is skipped, per the write rule.
                        return
                    if station_id in pending_station_set:
                        # Same station twice in one batch: flush so the
                        # later snapshot's delete removes the earlier one's
                        # rows instead of colliding with them.
                        flush_pending()
                    pending_station_ids.append(station_id)
                    pending_station_set.add(station_id)
                    for item_id in sorted(rows):
                        row = rows[item_id]
                        row["modified"] = snapshot_ts
                        pending_rows.append(row)
                    newest_existing[station_id] = snapshot_ts
                    if len(pending_rows) >= execute_batch:
                        flush_pending()

                for listing in reader:
                    bump_progress()
                    try:
                        if squelch_zero_units:
                            if listing[3] == "0":
                                listing[3] = listing[4] = listing[5] = "0"
                            if listing[7] == "0":
                                listing[6] = listing[7] = listing[8] = "0"

                        station_id = int(listing[1])
                        if station_id != group_station_id:
                            close_group()
                            group_station_id = station_id
                            group_known = station_id in station_lookup
                        if not group_known:
                            continue

                        # A zero-priced row is an untradeable listing — drop
                        # it from the snapshot rather than store dead rows.
                        if listing[5] == "0" and listing[6] == "0":
                            continue

                        item_id = int(listing[2])
                        if item_id not in item_lookup:
                            continue  # skip unknown item IDs

                        listing_time = int(listing[9])
                        if listing_time > group_max_ts:
                            group_max_ts = listing_time

                        group_rows[item_id] = {
                            "station_id":   station_id,
                            "item_id":      item_id,
                            "modified":     None,   # stamped with the snapshot timestamp at close
                            "from_live":    from_live_val,
                            "supply_units": int(listing[3]),
                            "supply_level": int(listing[4]),
                            "supply_price": int(listing[5]),
                            "demand_price": int(listing[6]),
                            "demand_units": int(listing[7]),
                            "demand_level": int(listing[8]),
                        }

                    except Exception as e:  # pylint: disable=broad-exception-caught
                        self.tdenv.WARN("Bad listing row (skipped): {}  error: {}", listing, e)
                        continue

                close_group()
                flush_pending()
                session.commit()
            
            finally:
                end_bulk_mode(session, token)
                # GUI-only: clear determinate child progress at the end of this
                # listings pass so the next phase can publish its own state cleanly.
                self._set_import_child_progress(None, None, None)
        
        # with pbar.Progress(1, 40, prefix="Saving"):
        #     pass
        
        if self.getOption("7days"):
            # This is a gimmick for first-time pruning: instead of trying to delete
            # years of old data, do it a piece at a time. It gives the progress bar
            # some movement.
            expirations = [360, 330, 300, 270, 240, 210, 180, 150, 120, 90, 60, 30, 21, 14, 7]
            with pbar.Progress(len(expirations) + 1, 40, 1, label="Expiring", style=pbar.LongRunningCountBar) as prog, self.tdb.session_maker.begin() as session:
                for expiration in expirations:
                    session.execute(text(f"DELETE FROM StationItem WHERE modified < datetime('now', '-{expiration} days')"))
                    prog.increment(1)
        
        if self.getOption("optimize"):
            with pbar.Progress(0, 40, label="Optimizing", style=pbar.ElapsedBar) as prog, self.tdb.session_maker.begin() as session:
                if self.tdb.engine.dialect.name == "sqlite":
                    session.execute(text("VACUUM"))
        
        self.tdenv.NOTE("Finished processing market data. End time = {}", self.now())
    
    def _refresh_dump_tables(self, table_jobs: list[tuple[str, Path]]) -> None:
        """Upsert-refresh (table_name, csv_path) jobs into the live ORM database,
        with a proper row-count progress bar.
        """
        if not table_jobs:
            return

        with self.tdb.session_maker() as session:
            with pbar.Progress(
                max_value=len(table_jobs) + 1,
                prefix="Upserting",
                width=25,
                style=pbar.CountingBar,
            ) as prog:
                # GUI-only: publish the current import phase and initialise the
                # parent/child progress state for the bespoke NiceGUI import pane.
                # These helper calls are dormant for CLI use unless a GUI
                # import_monitor has been attached to tdenv.
                self._set_import_status("Upserting base data...")
                self._set_import_parent_progress(
                    "Upserting",
                    0,
                    len(table_jobs),
                )
                self._set_import_child_progress(None, None, None)
                for index, (table_name, import_path) in enumerate(table_jobs, start=1):
                    # GUI-only: allow a cooperative stop request from the GUI to
                    # abort between table jobs. CLI behaviour is unchanged because
                    # no monitor is present there.
                    self._check_import_stop()
                    import_lines = file_line_count(import_path, missing_ok=True)
                    processed_lines = 0

                    def _line_callback(task, advance, description=None):
                        nonlocal processed_lines
                        # GUI-only: honour stop requests during a long table import.
                        self._check_import_stop()
                        prog.update_task(
                            task,
                            advance,
                            description=description,
                        )
                        processed_lines += int(advance)
                        # GUI-only: mirror child progress into the NiceGUI status
                        # strip. This does not affect CLI output.
                        self._set_import_child_progress(
                            table_name,
                            processed_lines,
                            import_lines,
                        )

                    with prog.sub_task(
                        max_value=import_lines,
                        description=table_name,
                    ) as child:
                        # GUI-only: update the visible phase text and parent/child
                        # counters for the active table.
                        self._set_import_status(
                            f"Upserting {table_name}..."
                        )
                        self._set_import_parent_progress(
                            "Upserting",
                            index - 1,
                            len(table_jobs),
                        )
                        self._set_import_child_progress(
                            table_name,
                            0,
                            import_lines,
                        )
                        prog.increment(value=1)
                        call_args = {"task": child, "advance": 1}
                        try:
                            td_cache.processImportFile(
                                self.tdenv,
                                session,
                                import_path,
                                table_name,
                                line_callback=_line_callback,
                                call_args=call_args,
                            )
                            session.commit()
                            # GUI-only: mark the parent counter as having completed
                            # this table once the import commits successfully.
                            self._set_import_parent_progress(
                                "Upserting",
                                index,
                                len(table_jobs),
                            )
                        except FileNotFoundError:
                            self.tdenv.WARN("Missing import file for {}: {}", table_name, import_path)
                        except StopIteration:
                            self.tdenv.NOTE(
                                "{} exists but is empty. Remove it or add the column definition line.",
                                import_path,
                            )

                prog.increment(1)
                # GUI-only: clear the child progress once the upsert phase is done.
                self._set_import_child_progress(None, None, None)


    def run(self):
        """
        EDDN/EDDB link importer.

        Refactored DB flow:
          - No dialect-specific logic in the plugin.
          - Preflight uses lifecycle.verify_db() (report-only sanity via lifecycle.ensure_fresh_db).
          - For '--clean' → do a single full rebuild.
          - Otherwise, if static CSVs changed → upsert-refresh only those tables (no drop/recreate).
          - Listings import unchanged.
        """
        self.tdenv.ignoreUnknown = True
        self.tdb.data_dir.mkdir(parents=True, exist_ok=True)

        # Enable 'listings' by default unless other explicit options are present
        default = True
        for option in self.options:
            if option not in ('force', 'skipvend', 'purge', '7days', 'units'):
                default = False
        if default:
            self.options["listings"] = True

        # Check if database already exists and enable `clean` if not.
        if lifecycle.is_empty(self.tdb.engine):
            self.options["clean"] = True

        if self.getOption("clean"):
            # Remove CSVs so downloads become the new source of truth
            for name in [
                "Category", "Item",
                "Ship", "ShipVendor",
                "Station", "System",
                "FDevShipyard",
            ]:
                f = self.tdb.data_dir / f"{name}.csv"
                try:
                    os.remove(str(f))
                except FileNotFoundError:
                    pass

            # Remove eddblink sync-state (sidecar) so templates never "win"
            try:
                os.remove(str(self._eddblink_state_path()))
            except FileNotFoundError:
                pass

            # Remove .prices (DEPRECATED)
            try:
                os.remove(str(self.tdb.data_dir / "TradeDangerous.prices"))
            except FileNotFoundError:
                pass

            self.options["all"] = True
            self.options["force"] = True
        else:
            # Category is foundational; if it's wrong, this DB is not trustworthy.
            # Hard-fail and force rebuild rather than attempting to "refresh" it.
            self._sanity_check_category_root()

        # Select which options will be updated
        if self.getOption("listings"):
            self.options["item"] = True
            self.options["station"] = True

        if self.getOption("shipvend"):
            self.options["ship"] = True
            self.options["station"] = True

        if self.getOption("item"):
            self.options["station"] = True

        if self.getOption("station"):
            self.options["system"] = True

        if self.getOption("all"):
            self.options["item"] = True
            self.options["ship"] = True
            self.options["shipvend"] = True
            self.options["station"] = True
            self.options["system"] = True
            self.options["listings"] = True

        if self.getOption("solo"):
            self.options["listings"] = False
            self.options["skipvend"] = True

        if self.getOption("skipvend"):
            self.options["shipvend"] = False

        # Download required files and decide which tables need upsert-refresh.
        force = self.getOption("force")

        ship_changed = False
        shipvend_changed = False
        system_changed = False
        station_changed = False
        category_changed = False
        item_changed = False

        # FDev bridge CSVs are treated as "changed" when we re-download them.
        fdev_shipyard_changed = False

        if self.getOption("ship"):
            ship_changed = self.downloadFile(self.shipPath) or force
            if ship_changed:
                transfers.download(self.tdenv, self.urlShipyard, self.FDevShipyardPath)
                fdev_shipyard_changed = True

        if self.getOption("shipvend"):
            shipvend_changed = self.downloadFile(self.shipVendorPath) or force

        if self.getOption("system"):
            system_changed = self.downloadFile(self.sysPath) or force

        if self.getOption("station"):
            station_changed = self.downloadFile(self.stationsPath) or force

        if self.getOption("item"):
            item_changed = self.downloadFile(self.commoditiesPath) or force
            # Category can change independently; always check when item option is active.
            category_changed = self.downloadFile(self.categoriesPath) or force

        # If any of the non-listings tables changed, ensure DB is fresh and then upsert-refresh.
        build_cache = any([
            ship_changed,
            shipvend_changed,
            system_changed, station_changed,
            category_changed, item_changed,
            fdev_shipyard_changed,
        ])

        if build_cache:
            if self.getOption("clean"):
                # "clean" must mean clean for all backends:
                #   - sqlite  → rotate/recreate DB file
                #   - mariadb → drop+recreate tables (NOT the database)
                self.tdenv.NOTE("NOTE: --clean requested; resetting database schema.")
                self.tdb.close()
                lifecycle.reset_db(
                    self.tdb.engine,
                    db_path=self.tdb.db_path,
                    sql_path=self.tdb.sql_path,
                )
            else:
                # Verify the database is present and structurally sane (report
                # only; rebuilding is the buildcache command's job).
                self.tdb.close()
                lifecycle.verify_db(self.tdb.engine, Path(self.tdenv.dataDir), self.tdenv)

            if self.tdb.engine.dialect.name == "sqlite":
                # kfsone: see https://sqlite.org/pragma.html#pragma_optimize
                self.tdb.session_maker().execute(text("PRAGMA optimize=0x10002"))

            # Upsert-refresh tables in dependency order.
            jobs: list[tuple[str, Path]] = []

            if system_changed:
                jobs.append(("System", (self.tdb.data_dir / self.sysPath).resolve()))

            if station_changed:
                jobs.append(("Station", (self.tdb.data_dir / self.stationsPath).resolve()))

            if category_changed or item_changed:
                jobs.append(("Category", (self.tdb.data_dir / self.categoriesPath).resolve()))
                jobs.append(("Item", (self.tdb.data_dir / self.commoditiesPath).resolve()))

            if ship_changed:
                jobs.append(("Ship", (self.tdb.data_dir / self.shipPath).resolve()))
            if fdev_shipyard_changed:
                jobs.append(("FDevShipyard", self.FDevShipyardPath.resolve()))

            if shipvend_changed:
                jobs.append(("ShipVendor", (self.tdb.data_dir / self.shipVendorPath).resolve()))

            self._refresh_dump_tables(jobs)
            self.tdb.close()

        if self.getOption("purge"):
            self.purgeSystems()

        # Listings import (prices)
        if self.getOption("listings"):
            if self.downloadFile(self.listingsPath) or force:
                self.importListings(self.listingsPath)
            if self.downloadFile(self.liveListingsPath) or force:
                self.importListings(self.liveListingsPath)

        if self.tdb.engine.dialect.name == "sqlite":
            with self.tdb.session_maker.begin() as session:
                if self.getOption("optimize"):
                    with bench("Vacuum and optimize", self.tdenv):
                        session.execute(text("VACUUM"))
                        # This is a very aggressive analyze/optimize pass
                        session.execute(text("ANALYZE"))
                else:
                    with bench("DB Tuning", self.tdenv):
                        session.execute(text("PRAGMA optimize"))
                    self.tdenv.INFO("Use --opt=optimize periodically for better query performance")
                    
        self.tdenv.NOTE("Import completed.")
        
        return False


    def finish(self):
        """ override the base class 'finish' method """
        # We expect to return 'False' from run, so if this is called, something went horribly wrong;
        # if this gets reached, someone added a bad return to run().
        self.tdenv.WARN("Internal error: plugin's finish() method was reached")
        return False
