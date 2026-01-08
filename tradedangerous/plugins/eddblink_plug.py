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
import os
import requests
import time
import typing

from sqlalchemy.orm import Session
from sqlalchemy import func, delete, select, exists, text

from tradedangerous import plugins, transfers, TradeException
from tradedangerous.db import orm_models as SA, lifecycle
from tradedangerous.db.utils import (
    begin_bulk_mode, end_bulk_mode,
    get_import_batch_size, get_upsert_fn,
)
from tradedangerous.fs import file_line_count
from tradedangerous.misc import progress as pbar
from tradedangerous.plugins import PluginException

if typing.TYPE_CHECKING:
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


def _collect_station_modified_times(tdenv: TradeEnv, session: Session) -> dict[int, int]:
    """Helper: build a list of the last modified time for all stations by id (epoch seconds)."""
    tdenv.DEBUG0("Getting last-update times for stations...")
    rows = (
        session.query(
            SA.StationItem.station_id,
            func.min(SA.StationItem.modified),
        )
        .group_by(SA.StationItem.station_id)
        .all()
    )
    return {
        station_id: int(modified.timestamp()) if modified else 0
        for station_id, modified in rows
    }


class ImportPlugin(plugins.ImportPluginBase):
    """
    Import plugin that uses data files from
    https://elite.tromador.com/ to update the Database.
    """
    pluginOptions = {
        'item':         "Update Items using latest file from server. (Implies '-O system,station')",
        'rare':         "Update RareItems using latest file from server. (Implies '-O system,station')",
        'ship':         "Update Ships using latest file from server.",
        'upgrade':      "Update Upgrades using latest file from server.",
        'system':       "Update Systems using latest file from server.",
        'station':      "Update Stations using latest file from server. (Implies '-O system')",
        'shipvend':     "Update ShipVendors using latest file from server. (Implies '-O system,station,ship')",
        'upvend':       "Update UpgradeVendors using latest file from server. (Implies '-O system,station,upgrade')",
        'listings':     "Update market data using latest listings.csv dump. (Implies '-O item,system,station')",
        'all':          "Update everything with latest dumpfiles. (Regenerates all tables)",
        'clean':        "Erase entire database and rebuild from empty. (Regenerates all tables.)",
        'skipvend':     "Don't regenerate ShipVendors or UpgradeVendors. (Supercedes '-O all', '-O clean'.)",
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
        'bootstrap':    "Helper to 'do the right thing' and get you some data",
    }
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
        
        self.dataPath = os.environ.get('TD_EDDB') or self.tdenv.tmpDir
        self.categoriesPath = Path("Category.csv")
        self.commoditiesPath = Path("Item.csv")
        self.rareItemPath = Path("RareItem.csv")
        self.shipPath = Path("Ship.csv")
        self.urlShipyard = "https://raw.githubusercontent.com/EDCD/FDevIDs/master/shipyard.csv"
        self.FDevShipyardPath = self.tdb.dataPath / Path("FDevShipyard.csv")
        self.shipVendorPath = Path("ShipVendor.csv")
        self.stationsPath = Path("Station.csv")
        self.sysPath = Path("System.csv")
        self.upgradesPath = Path("Upgrade.csv")
        self.urlOutfitting = "https://raw.githubusercontent.com/EDCD/FDevIDs/master/outfitting.csv"
        self.FDevOutfittingPath = self.tdb.dataPath / Path("FDevOutfitting.csv")
        self.upgradeVendorPath = Path("UpgradeVendor.csv")
        self.listingsPath = Path("listings.csv")
        self.liveListingsPath = Path("listings-live.csv")
        self.pricesPath = Path("listings.prices")
    
    def now(self):
        return datetime.datetime.now().strftime('%H:%M:%S')

    def _eddblink_state_path(self) -> Path:
        """
        Single sidecar state file stored in TD_DATA (tdb.dataPath).
        This is the authoritative record of "downloaded from server" identity.
        """
        return (self.tdb.dataPath / "eddblink_state.json").resolve()

    def _load_eddblink_state(self) -> dict:
        import json

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
        import json

        state_path = self._eddblink_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = state_path.with_name(state_path.name + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
            fh.write("\n")
        tmp_path.replace(state_path)

    def _file_sha256(self, path: Path) -> str:
        import hashlib

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

        Session = self.tdb.Session
        try:
            with Session() as session:
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

        cid, name = row
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
            localPath = Path(self.tdb.dataPath, path)
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
            if key in ("Category.csv", "RareItem.csv", "Item.csv"):
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
        
        Session = self.tdb.Session
        with Session.begin() as session:
            subq = select(SA.Station.system_id).where(SA.Station.system_id == SA.System.system_id)
            stmt = delete(SA.System).where(~exists(subq))
            session.execute(stmt)
        
        self.tdenv.NOTE("Finished purging Systems. End time = {}", self.now())
    
    def importListings(self, listings_file):
        """
        Updates the market data (StationItem) using `listings_file`.
        
        Rules:
          - If a row doesn't exist in DB → insert (copy CSV exactly).
          - If it exists → update only when CSV.modified > DB.modified.
          - If CSV.modified <= DB.modified → do nothing (no field changes).
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
        
        Session = self.tdb.Session
        
        # Prefetch item/station IDs for early filtering
        with Session.begin() as session:
            item_lookup = _make_item_id_lookup(self.tdenv, session)
            station_lookup = _make_station_id_lookup(self.tdenv, session)
        
        self.tdenv.DEBUG0("Processing entries...")
        
        with pbar.Progress(total, 40, label="Processing", style=pbar.LongRunningCountBar) as prog, \
               listings_path.open("r", encoding="utf-8", errors="ignore") as fh, \
               Session() as session:
            
            token = begin_bulk_mode(session, profile="eddblink", phase="incremental")
            try:
                commit_batch = get_import_batch_size(session, profile="eddblink")
                execute_batch = commit_batch or 10000  # cap statement size even if single final commit
                
                # Upsert: keys + guarded fields (including from_live), guarded by 'modified'
                table = SA.StationItem.__table__
                key_cols = ("station_id", "item_id")
                update_cols = (
                    "demand_price", "demand_units", "demand_level",
                    "supply_price", "supply_units", "supply_level",
                    "from_live",
                )
                upsert = get_upsert_fn(
                    session,
                    table,
                    key_cols=key_cols,
                    update_cols=update_cols,
                    modified_col="modified",
                    always_update=(),   # IMPORTANT: no unconditional updates
                )
                
                batch_rows = []
                since_commit = 0
                
                # optimize away millions of lookups
                increment = prog.increment
                
                def bump_progress():
                    increment(1)
                
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
                
                for listing in reader:
                    bump_progress()
                    try:
                        if squelch_zero_units:
                            if listing[3] == "0":
                                listing[3] = listing[4] = listing[5] = "0"
                            if listing[7] == "0":
                                listing[6] = listing[7] = listing[8] = "0"
                        
                        # Do the cheapest skip-check first
                        if listing[5] == "0" and listing[6] == "0":
                            continue
                        
                        # Cheap numeric condition
                        listing_time = int(listing[9])
                        if listing_time < time_cutoff:
                            continue
                        
                        station_id = int(listing[1])
                        if station_id not in station_lookup:
                            continue
                        
                        item_id = int(listing[2])
                        if item_id not in item_lookup:
                            continue  # skip rare items (not in Item table)
                        
                        dt_listing_time = from_timestamp(listing_time, utc)
                        
                        row = {
                            "station_id":   station_id,
                            "item_id":      item_id,
                            "modified":     dt_listing_time,   # guard column
                            "from_live":    from_live_val,     # copied exactly when updating/inserting
                            "supply_units": int(listing[3]),
                            "supply_level": int(listing[4]),
                            "supply_price": int(listing[5]),
                            "demand_price": int(listing[6]),
                            "demand_units": int(listing[7]),
                            "demand_level": int(listing[8]),
                        }
                        batch_rows += [row]
                        since_commit += 1
                        
                        if len(batch_rows) >= execute_batch:
                            upsert(batch_rows)
                            batch_rows[:] = []  # in-place clear without lookup
                        
                        if commit_batch and since_commit >= commit_batch:
                            session.commit()
                            since_commit = 0
                    
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        self.tdenv.WARN("Bad listing row (skipped): {}  error: {}", listing, e)
                        continue
                
                if batch_rows:
                    upsert(batch_rows)
                    batch_rows[:] = []  # in-place clear
                
                session.commit()
            
            finally:
                end_bulk_mode(session, token)
        
        # with pbar.Progress(1, 40, prefix="Saving"):
        #     pass
        
        if self.getOption("7days"):
            # This is a gimmick for first-time pruning: instead of trying to delete
            # years of old data, do it a piece at a time. It gives the progress bar
            # some movement.
            expirations = [360, 330, 300, 270, 240, 210, 180, 150, 120, 90, 60, 30, 21, 14, 7]
            with pbar.Progress(len(expirations) + 1, 40, 1, label="Expiring", style=pbar.LongRunningCountBar) as prog, \
                    Session.begin() as session:
                for expiration in expirations:
                    session.execute(text(f"DELETE FROM StationItem WHERE modified < datetime('now', '-{expiration} days')"))
                    prog.increment(1)
        
        if self.getOption("optimize"):
            with pbar.Progress(0, 40, label="Optimizing", style=pbar.ElapsedBar) as prog:
                if self.tdb.engine.dialect.name == "sqlite":
                    with Session.begin() as session:
                        session.execute(text("VACUUM"))
        
        self.tdenv.NOTE("Finished processing market data. End time = {}", self.now())
    
    def _refresh_dump_tables(self, table_jobs: list[tuple[str, Path]]) -> None:
        """Upsert-refresh (table_name, csv_path) jobs into the live ORM database,
        with a proper row-count progress bar.

        Note: RareItem is rebuilt (wiped then re-imported) whenever it is refreshed.
        This avoids UNIQUE(name) collisions caused by historical PK drift / template-era imports.
        """
        if not table_jobs:
            return

        # Local import to avoid plugin import-order headaches.
        from tradedangerous import cache as td_cache

        Session = self.tdb.Session
        with Session() as session:
            with pbar.Progress(
                max_value=len(table_jobs) + 1,
                prefix="Upserting",
                width=25,
                style=pbar.CountingBar,
            ) as prog:
                for table_name, import_path in table_jobs:
                    import_lines = file_line_count(import_path, missing_ok=True)
                    with prog.sub_task(
                        max_value=import_lines,
                        description=table_name,
                    ) as child:
                        prog.increment(value=1)
                        call_args = {"task": child, "advance": 1}
                        try:
                            # RareItem: rebuild contents on refresh to avoid uq_rareitem_name collisions
                            # when existing DB has same names under different rare_id values.
                            if table_name == "RareItem":
                                session.execute(delete(SA.RareItem))

                            td_cache.processImportFile(
                                self.tdenv,
                                session,
                                import_path,
                                table_name,
                                line_callback=prog.update_task,
                                call_args=call_args,
                            )
                            session.commit()
                        except FileNotFoundError:
                            self.tdenv.WARN("Missing import file for {}: {}", table_name, import_path)
                        except StopIteration:
                            self.tdenv.NOTE(
                                "{} exists but is empty. Remove it or add the column definition line.",
                                import_path,
                            )

                prog.increment(1)


    def run(self):
        """
        EDDN/EDDB link importer.

        Refactored DB flow:
          - No dialect-specific logic in the plugin.
          - Preflight uses TradeDB.reloadCache() (which centralizes sanity via lifecycle.ensure_fresh_db).
          - For '--clean' → do a single full rebuild with the RareItem dance.
          - Otherwise, if static CSVs changed → upsert-refresh only those tables (no drop/recreate).
          - Listings import unchanged.
        """
        self.tdenv.ignoreUnknown = True
        self.tdb.dataPath.mkdir(parents=True, exist_ok=True)

        # Enable 'listings' by default unless other explicit options are present
        default = True
        for option in self.options:
            if option not in ('force', 'skipvend', 'purge', '7days', 'units'):
                default = False
        if default:
            self.options["listings"] = True

        if self.getOption("bootstrap"):
            self.tdenv.NOTE("[bold][blue]bootstrap: Greetings, Commander!")
            self.tdenv.NOTE(
                "[yellow]This first-time import might take several minutes or longer, "
                "it ensures your database is up to date with current EDDBLink System, Station, and Item tables "
                "as well as trade listings for the last 7 days.")
            self.tdenv.NOTE(
                "[yellow]You can run this same command later to import updates - which should be much faster, "
                "or `trade import -P eddblink -O 7days,skipvend`.")
            self.tdenv.NOTE(
                "[yellow]To contribute your own discoveries to market data, consider running the "
                "Elite Dangerous Market Connector while playing.")
            for child in ["system", "station", "item", "listings", "skipvend", "7days"]:
                self.options[child] = True

        # Check if database already exists and enable `clean` if not.
        if lifecycle.is_empty(self.tdb.engine):
            self.options["clean"] = True

        if self.getOption("clean"):
            # Remove CSVs so downloads become the new source of truth
            for name in [
                "Category", "Item", "RareItem",
                "Ship", "ShipVendor",
                "Station", "System",
                "Upgrade", "UpgradeVendor",
                "FDevShipyard", "FDevOutfitting",
            ]:
                f = self.tdb.dataPath / f"{name}.csv"
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
                os.remove(str(self.tdb.dataPath / "TradeDangerous.prices"))
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

        if self.getOption("upvend"):
            self.options["upgrade"] = True
            self.options["station"] = True

        if self.getOption("item"):
            self.options["station"] = True

        if self.getOption("rare"):
            self.options["station"] = True

        if self.getOption("station"):
            self.options["system"] = True

        if self.getOption("all"):
            self.options["item"] = True
            self.options["rare"] = True
            self.options["ship"] = True
            self.options["shipvend"] = True
            self.options["station"] = True
            self.options["system"] = True
            self.options["upgrade"] = True
            self.options["upvend"] = True
            self.options["listings"] = True

        if self.getOption("solo"):
            self.options["listings"] = False
            self.options["skipvend"] = True

        if self.getOption("skipvend"):
            self.options["shipvend"] = False
            self.options["upvend"] = False

        # Download required files and decide which tables need upsert-refresh.
        force = self.getOption("force")

        upgrade_changed = False
        ship_changed = False
        rare_changed = False
        shipvend_changed = False
        upvend_changed = False
        system_changed = False
        station_changed = False
        category_changed = False
        item_changed = False

        # FDev bridge CSVs are treated as "changed" when we re-download them.
        fdev_shipyard_changed = False
        fdev_outfitting_changed = False

        if self.getOption("upgrade"):
            upgrade_changed = self.downloadFile(self.upgradesPath) or force
            if upgrade_changed:
                transfers.download(self.tdenv, self.urlOutfitting, self.FDevOutfittingPath)
                fdev_outfitting_changed = True

        if self.getOption("ship"):
            ship_changed = self.downloadFile(self.shipPath) or force
            if ship_changed:
                transfers.download(self.tdenv, self.urlShipyard, self.FDevShipyardPath)
                fdev_shipyard_changed = True

        if self.getOption("rare"):
            rare_changed = self.downloadFile(self.rareItemPath) or force

        if self.getOption("shipvend"):
            shipvend_changed = self.downloadFile(self.shipVendorPath) or force

        if self.getOption("upvend"):
            upvend_changed = self.downloadFile(self.upgradeVendorPath) or force

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
            upgrade_changed, ship_changed, rare_changed,
            shipvend_changed, upvend_changed,
            system_changed, station_changed,
            category_changed, item_changed,
            fdev_shipyard_changed, fdev_outfitting_changed,
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
                    db_path=self.tdb.dbPath,
                    sql_path=self.tdb.sqlPath,
                )
            else:
                # Ensure schema exists and is sane (may rebuild on first run).
                self.tdb.close()
                self.tdb.reloadCache()

            if self.tdb.engine.dialect.name == "sqlite":
                # kfsone: see https://sqlite.org/pragma.html#pragma_optimize
                self.tdb.Session().execute(text("PRAGMA optimize=0x10002"))

            # Upsert-refresh tables in dependency order.
            jobs: list[tuple[str, Path]] = []

            if system_changed:
                jobs.append(("System", (self.tdb.dataPath / self.sysPath).resolve()))

            if station_changed:
                jobs.append(("Station", (self.tdb.dataPath / self.stationsPath).resolve()))

            if category_changed or item_changed:
                jobs.append(("Category", (self.tdb.dataPath / self.categoriesPath).resolve()))
                jobs.append(("Item", (self.tdb.dataPath / self.commoditiesPath).resolve()))

            if ship_changed:
                jobs.append(("Ship", (self.tdb.dataPath / self.shipPath).resolve()))
            if fdev_shipyard_changed:
                jobs.append(("FDevShipyard", self.FDevShipyardPath.resolve()))

            if upgrade_changed:
                jobs.append(("Upgrade", (self.tdb.dataPath / self.upgradesPath).resolve()))
            if fdev_outfitting_changed:
                jobs.append(("FDevOutfitting", self.FDevOutfittingPath.resolve()))

            if shipvend_changed:
                jobs.append(("ShipVendor", (self.tdb.dataPath / self.shipVendorPath).resolve()))

            if upvend_changed:
                jobs.append(("UpgradeVendor", (self.tdb.dataPath / self.upgradeVendorPath).resolve()))

            if rare_changed:
                jobs.append(("RareItem", (self.tdb.dataPath / self.rareItemPath).resolve()))

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
            with self.tdb.Session.begin() as session:
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
