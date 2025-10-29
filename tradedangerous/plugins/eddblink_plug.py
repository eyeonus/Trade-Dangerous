"""
Import plugin that uses data files from 
https://elite.tromador.com/ to update the Database.
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from pathlib import Path
from ..fs import file_line_count
from .. import plugins, cache, transfers
from ..misc import progress as pbar
from ..plugins import PluginException

import csv
import datetime
import os
import requests
import typing

from sqlalchemy.orm import Session
from sqlalchemy import func, delete, select, exists, text
from ..db import orm_models as SA, lifecycle

if typing.TYPE_CHECKING:
    from typing import Optional
    from ..tradeenv import TradeEnv

# Constants
BASE_URL = os.environ.get('TD_SERVER') or "https://elite.tromador.com/files/"


class DecodingError(PluginException):
    pass


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
        'solo':         "Don't download crowd-sourced market data. (Implies '-O skipvend', supercedes '-O all', '-O clean', '-O listings'.)",
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
    
    def downloadFile(self, path):
        """
        Fetch the latest dumpfile from the website if newer than local copy.
        """
        if path not in (self.liveListingsPath, self.listingsPath):
            localPath = Path(self.tdb.dataPath, path)
        else:
            localPath = Path(self.dataPath, path)
        
        url = BASE_URL + str(path)
        
        self.tdenv.NOTE("Checking for update to '{}'.", path)
        # Use an HTTP Request header to obtain the Last-Modified and Content-Length headers.
        # Also, tell the server to give us the un-compressed length of the file by saying
        # that >this< request only wants text.
        headers = {"User-Agent": "Trade-Dangerous", "Accept-Encoding": "identity"}
        try:
            response = requests.head(url, headers=headers, timeout=70)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.tdenv.WARN("Problem with download:\n    URL: {}\n    Error: {}", url, str(e))
            return False
        
        last_modified = response.headers.get("last-modified")
        dump_mod_time = parsedate_to_datetime(last_modified).timestamp()
        
        if Path.exists(localPath):
            local_mod_time = localPath.stat().st_mtime
            if local_mod_time >= dump_mod_time:
                self.tdenv.DEBUG0("'{}': Dump is not more recent than Local.", path)
                return False
        
        # The server doesn't know the gzip'd length, and we won't see the gzip'd data,
        # so we want the actual text-only length. Capture it here so we can tell the
        # transfer mechanism how big the file is going to be.
        length = response.headers.get("content-length")
        
        self.tdenv.NOTE("Downloading file '{}'.", path)
        transfers.download(self.tdenv, url, localPath, chunkSize=16384, length=length)
        
        # Change the timestamps on the file so they match the website
        os.utime(localPath, (dump_mod_time, dump_mod_time))
        
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
        from tradedangerous.db.utils import (
            get_import_batch_size,
            begin_bulk_mode,
            end_bulk_mode,
            get_upsert_fn,
        )
        
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
        
        is_debug = self.tdenv.debug > 0
        self.tdenv.DEBUG0("Processing entries...")
        
        with pbar.Progress(total, 40, prefix="Processing", style=pbar.LongRunningCountBar) as prog, \
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
                
                for listing in csv.DictReader(fh):
                    prog.increment(1)
                    try:
                        station_id = int(listing["station_id"])
                        if station_id not in station_lookup:
                            continue
                        
                        item_id = int(listing["commodity_id"])
                        if item_id not in item_lookup:
                            continue  # skip rare items (not in Item table)
                        
                        listing_time = int(listing["collected_at"])
                        dt_listing_time = datetime.datetime.utcfromtimestamp(listing_time)
                        
                        row = {
                            "station_id":   station_id,
                            "item_id":      item_id,
                            "modified":     dt_listing_time,   # guard column
                            "from_live":    int(from_live),        # copied exactly when updating/inserting
                            "demand_price": int(listing["sell_price"]),
                            "demand_units": int(listing["demand"]),
                            "demand_level": int(listing.get("demand_bracket") or "-1"),
                            "supply_price": int(listing["buy_price"]),
                            "supply_units": int(listing["supply"]),
                            "supply_level": int(listing.get("supply_bracket") or "-1"),
                        }
                        batch_rows.append(row)
                        since_commit += 1
                        
                        if len(batch_rows) >= execute_batch:
                            upsert(batch_rows)
                            batch_rows.clear()
                        
                        if commit_batch and since_commit >= commit_batch:
                            session.commit()
                            since_commit = 0
                    
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        self.tdenv.WARN("Bad listing row (skipped): {}  error: {}", listing, e)
                        continue
                
                if batch_rows:
                    upsert(batch_rows)
                    batch_rows.clear()
                
                session.commit()
            
            finally:
                end_bulk_mode(session, token)
        
        # with pbar.Progress(1, 40, prefix="Saving"):
        #     pass
        
        if self.getOption("optimize"):
            with pbar.Progress(1, 40, prefix="Optimizing"):
                if self.tdb.engine.dialect.name == "sqlite":
                    with Session.begin() as session:
                        session.execute(text("VACUUM"))
        
        self.tdenv.NOTE("Finished processing market data. End time = {}", self.now())
    
    def run(self):
        """
        EDDN/EDDB link importer.
        
        Refactored DB flow:
          - No dialect-specific logic in the plugin.
          - Preflight uses TradeDB.reloadCache() (which centralizes sanity via lifecycle.ensure_fresh_db).
          - For '--clean' → do a single full rebuild with the RareItem dance.
          - Otherwise, if static CSVs changed → incrementally import only those tables (no drop/recreate).
          - Listings import and .prices regeneration unchanged.
        """
        import os
        import time
        from pathlib import Path
        from tradedangerous import cache
        # bulk-mode helpers for the incremental static import session
        from tradedangerous.db.utils import begin_bulk_mode, end_bulk_mode
        
        self.tdenv.ignoreUnknown = True
        self.tdb.dataPath.mkdir(parents=True, exist_ok=True)
        
        # Enable 'listings' by default unless other explicit options are present
        default = True
        for option in self.options:
            if option not in ('force', 'skipvend', 'purge'):
                default = False
        if default:
            self.options["listings"] = True
        
        # Check if database already exists and enable `clean` if not.
        from tradedangerous.db.lifecycle import is_empty
        if is_empty(self.tdb.engine):
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
            
            # Remove .prices (DEPRECATED)
            try:
                os.remove(str(self.tdb.dataPath / "TradeDangerous.prices"))
            except FileNotFoundError:
                pass
                        
            self.options["all"] = True
            self.options["force"] = True
        
        
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
        
        # Download required files and update tables.
        buildCache = False
        if self.getOption("upgrade"):
            if self.downloadFile(self.upgradesPath) or self.getOption("force"):
                transfers.download(self.tdenv, self.urlOutfitting, self.FDevOutfittingPath)
                buildCache = True
        
        if self.getOption("ship"):
            if self.downloadFile(self.shipPath) or self.getOption("force"):
                transfers.download(self.tdenv, self.urlShipyard, self.FDevShipyardPath)
                buildCache = True
        
        if self.getOption("rare"):
            if self.downloadFile(self.rareItemPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("shipvend"):
            if self.downloadFile(self.shipVendorPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("upvend"):
            if self.downloadFile(self.upgradeVendorPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("system"):
            if self.downloadFile(self.sysPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("station"):
            if self.downloadFile(self.stationsPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("item"):
            if self.downloadFile(self.commoditiesPath) or self.getOption("force"):
                self.downloadFile(self.categoriesPath)
                buildCache = True
        
        # Remake the .db files with the updated info.
        if buildCache:
            self.tdb.close()
            self.tdb.reloadCache()
            self.tdb.close()
        
        if self.getOption("purge"):
            self.purgeSystems()
        
        # Listings import (prices)
        if self.getOption("listings"):
            if self.downloadFile(self.listingsPath) or self.getOption("force"):
                self.importListings(self.listingsPath)
            if self.downloadFile(self.liveListingsPath) or self.getOption("force"):
                self.importListings(self.liveListingsPath)
        
        # if self.getOption("listings"):
        #     self.tdenv.NOTE("Regenerating .prices file.")
        #     cache.regeneratePricesFile(self.tdb, self.tdenv)
        
        self.tdenv.NOTE("Import completed.")
        return False
