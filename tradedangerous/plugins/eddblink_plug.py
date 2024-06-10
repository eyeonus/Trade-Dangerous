"""
Import plugin that uses data files from 
https://elite.tromador.com/ to update the Database.
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from pathlib import Path
from .. fs import file_line_count
from .. import plugins, cache, transfers
from ..misc import progress as pbar
from ..plugins import PluginException

import csv
import datetime
import os
import requests
import sqlite3
import typing


if typing.TYPE_CHECKING:
    from typing import Optional
    from .. tradeenv import TradeEnv

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


def _make_item_id_lookup(tdenv: TradeEnv, db: sqlite3.Cursor) -> frozenset[int]:
    """ helper: retrieve the list of commodities in database. """
    tdenv.DEBUG0("Getting list of commodities...")
    return frozenset(cols[0] for cols in db.execute("SELECT item_id FROM Item"))


def _make_station_id_lookup(tdenv: TradeEnv, db: sqlite3.Cursor) -> frozenset[int]:
    """ helper: retrieve the list of station IDs in database. """
    tdenv.DEBUG0("Getting list of stations...")
    return frozenset(cols[0] for cols in db.execute("SELECT station_id FROM Station"))


def _collect_station_modified_times(tdenv: TradeEnv, db: sqlite3.Cursor) -> dict[int, int]:
    """ helper: build a list of the last modified time for all stations by id. """
    tdenv.DEBUG0("Getting last-update times for stations...")
    return dict(db.execute("SELECT station_id, strftime('%s', MIN(modified)) FROM StationItem GROUP BY station_id"))


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads data from eddb.
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
        return datetime.datetime.now()
    
    def downloadFile(self, path):
        """
        Fetch the latest dumpfile from the website if newer than local copy.
        """
        if path not in (self.liveListingsPath, self.listingsPath):
            localPath = Path(self.tdb.dataPath, path)
        else:
            localPath = Path(self.dataPath, path)
        
        url  = BASE_URL + str(path)
        
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
        db = self.tdb.getDB()
        self.tdenv.NOTE("Purging Systems with no stations: Start time = {}", self.now())
        
        db.execute("""
            DELETE FROM System
             WHERE NOT EXISTS(SELECT 1 FROM Station WHERE Station.system_id = System.system_id)
        """)
        db.commit()
        
        self.tdenv.NOTE("Finished purging Systems. End time = {}", self.now())
    
    def importListings(self, listings_file):
        """
        Updates the market data (AKA the StationItem table) using listings_file
        Writes directly to database.
        """
        listings_path = Path(self.dataPath, listings_file).absolute()
        from_live = listings_path != Path(self.dataPath, self.listingsPath).absolute()
        
        self.tdenv.NOTE("Checking listings")
        total = _count_listing_entries(self.tdenv, listings_path)
        if not total:
            self.tdenv.NOTE("No listings")
            return
        
        self.tdenv.NOTE("Processing market data from {}: Start time = {}. Live = {}", listings_file, self.now(), from_live)
        
        db = self.tdb.getDB()
        stmt_unliven_station = """UPDATE StationItem SET from_live = 0 WHERE station_id = ?"""
        stmt_flush_station   = """DELETE from StationItem WHERE station_id = ?"""
        stmt_add_listing     = """
            INSERT OR IGNORE INTO StationItem (
                station_id, item_id, modified, from_live,
                demand_price, demand_units, demand_level,
                supply_price, supply_units, supply_level
            )
            VALUES (
                ?, ?, datetime(?, 'unixepoch'), ?,
                ?, ?, ?,
                ?, ?, ?
            )
        """
        
        # Fetch all the items IDS
        item_lookup = _make_item_id_lookup(self.tdenv, db.cursor())
        station_lookup = _make_station_id_lookup(self.tdenv, db.cursor())
        last_station_update_times = _collect_station_modified_times(self.tdenv, db.cursor())
        
        cur_station = None
        is_debug = self.tdenv.debug > 0
        self.tdenv.DEBUG0("Processing entries...")
        
        # Try to find a balance between doing too many commits where we fail
        # to get any benefits from constructing transactions, and blowing up
        # the WAL and memory usage by making massive transactions.
        max_transaction_items, transaction_items = 32 * 1024, 0
        with pbar.Progress(total, 40, prefix="Processing", style=pbar.LongRunningCountBar) as prog,\
              listings_path.open("r", encoding="utf-8", errors="ignore") as fh:
            cursor = db.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            for listing in csv.DictReader(fh):
                prog.increment(1)
                
                station_id = int(listing['station_id'])
                if station_id not in station_lookup:
                    continue
                
                listing_time = int(listing['collected_at'])
                
                if station_id != cur_station:
                    # commit anything from the previous station, get a new cursor
                    if transaction_items >= max_transaction_items:
                        cursor.execute("COMMIT")
                        transaction_items = 0
                        cursor.execute("BEGIN TRANSACTION")
                    cur_station, skip_station = station_id, False
                    
                    # Check if listing already exists in DB and needs updated.
                    last_modified: int = int(last_station_update_times.get(station_id, 0))
                    if last_modified:
                        # When the listings.csv data matches the database, update to make from_live == 0.
                        if listing_time == last_modified and not from_live:
                            if is_debug:
                                self.tdenv.DEBUG1(f"Marking {cur_station} as no longer 'live' (old={last_modified}, listing={listing_time}).")
                            cursor.execute(stmt_unliven_station, (cur_station,))
                            transaction_items += 1
                            skip_station = True
                            continue
                        
                        # Unless the import file data is newer, nothing else needs to be done for this station,
                        # so the rest of the listings for this station can be skipped.
                        if listing_time <= last_modified:
                            skip_station = True
                            continue
                        
                        # The data from the import file is newer, so we need to delete the old data for this station.
                        if is_debug:
                            self.tdenv.DEBUG1(f"Deleting old listing data for {cur_station} (old={last_modified}, listing={listing_time}).")
                        cursor.execute(stmt_flush_station, (cur_station,))
                        transaction_items += 1
                        last_station_update_times[station_id] = listing_time
                
                # station skip lasts until we change station id.
                if skip_station:
                    continue
                
                # Since this station is not being skipped, get the data and prepare for insertion into the DB.
                item_id = int(listing['commodity_id'])
                # listings.csv includes rare items, which we are ignoring.
                if item_id not in item_lookup:
                    continue
                
                demand_price = int(listing['sell_price'])
                demand_units = int(listing['demand'])
                demand_level = int(listing.get('demand_bracket') or '-1')
                supply_price = int(listing['buy_price'])
                supply_units = int(listing['supply'])
                supply_level = int(listing.get('supply_bracket') or '-1')
                
                if is_debug:
                    self.tdenv.DEBUG1(f"Inserting new listing data for {station_id}.")
                cursor.execute(stmt_add_listing, (
                        station_id, item_id, listing_time, from_live,
                        demand_price, demand_units, demand_level,
                        supply_price, supply_units, supply_level,
                ))
                transaction_items += 1
        
        # These will take a little while, which has four steps, so we'll make it a counter.
        with pbar.Progress(1, 40, prefix="Saving"):
            # Do a final commit to be sure
            cursor.execute("COMMIT")
        
        if self.getOption("optimize"):
            with pbar.Progress(1, 40, prefix="Optimizing"):
                db.execute("VACUUM")
        
        self.tdb.close()
        
        self.tdenv.NOTE("Finished processing market data. End time = {}", self.now())
    
    def run(self):
        self.tdenv.ignoreUnknown = True
        
        # Create the /eddb folder for downloading the source files if it doesn't exist.
        try:
            Path(str(self.dataPath)).mkdir()
        except FileExistsError:
            pass
        
        # Run 'listings' by default:
        # If no options, or if only 'force', and/or 'skipvend',
        # have been passed, enable 'listings'.
        default = True
        for option in self.options:
            if option not in ('force', 'skipvend', 'purge'):
                default = False
        if default:
            self.options["listings"] = True
        
        # We can probably safely assume that the plugin
        # has never been run if the db file doesn't exist.
        if not self.tdb.dbPath.exists():
            self.options["clean"] = True
        
        if self.getOption("clean"):
            # Rebuild the tables from scratch. Must be done on first run of plugin.
            # Can be done at anytime with the "clean" option.
            for name in [
                "Category",
                "Item",
                "RareItem",
                "Ship",
                "ShipVendor",
                "Station",
                "System",
                "Upgrade",
                "UpgradeVendor",
                "FDevShipyard",
                "FDevOutfitting",
            ]:
                file = self.tdb.dataPath / Path(name + ".csv")
                try:
                    os.remove(str(file))
                except FileNotFoundError:
                    pass
            
            try:
                os.remove(str(self.tdb.dataPath) + "/TradeDangerous.db")
            except FileNotFoundError:
                pass
            try:
                os.remove(str(self.tdb.dataPath) + "/TradeDangerous.prices")
            except FileNotFoundError:
                pass
            
            # Because this is a clean run, we need to temporarily rename the RareItem.csv,
            # otherwise TD will crash trying to insert the rare items to the database,
            # because there's nothing in the Station table it tries to pull from.
            ri_path = self.tdb.dataPath / Path("RareItem.csv")
            rib_path = ri_path.with_suffix(".tmp")
            if ri_path.exists():
                if rib_path.exists():
                    rib_path.unlink()
                ri_path.rename(rib_path)
            
            self.tdb.close()
            
            self.tdb.reloadCache()
            self.tdb.close()
            
            # Now it's safe to move RareItems back.
            if ri_path.exists():
                ri_path.unlink()
            if rib_path.exists():
                rib_path.rename(ri_path)
            
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
            self.tdb.close()
        
        if self.getOption("listings"):
            if self.downloadFile(self.listingsPath) or self.getOption("force"):
                self.importListings(self.listingsPath)
            if self.downloadFile(self.liveListingsPath) or self.getOption("force"):
                self.importListings(self.liveListingsPath)
        
        if self.getOption("listings"):
            self.tdenv.NOTE("Regenerating .prices file.")
            cache.regeneratePricesFile(self.tdb, self.tdenv)
        
        self.tdenv.NOTE("Import completed.")
        
        # TD doesn't need to do anything, tell it to just quit.
        return False
