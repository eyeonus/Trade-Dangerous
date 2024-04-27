"""
Import plugin that uses data files from 
https://elite.tromador.com/ to update the Database.
"""
from __future__ import annotations
import certifi
import csv
import datetime
import json
import os
import sqlite3
import ssl
import time
import typing

from urllib import request
from pathlib import Path

from .. import plugins, cache, transfers
from ..misc import progress as pbar
from ..plugins import PluginException


if typing.TYPE_CHECKING:
    from typing import Optional
    from .. tradeenv import TradeEnv


# Constants
BASE_URL = os.environ.get('TD_SERVER') or "https://elite.tromador.com/files/"
CONTEXT=ssl.create_default_context(cafile=certifi.where())


def _request_url(url, headers=None):
    data = None
    if headers:
        data = bytes(json.dumps(headers), encoding="utf-8")
    
    return request.urlopen(request.Request(url, data=data), context=CONTEXT, timeout=90)


class DecodingError(PluginException):
    pass


def _file_line_count(from_file: Path, bufsize: int = 128 * 1024) -> int:
    """ counts the number of newline characters in a given file. """
    # Pre-allocate a buffer so we aren't putting pressure on the garbage collector.
    buf = bytearray(bufsize)
    
    # Capture it's counting method, so we don't have to keep looking that up on
    # large files.
    counter = buf.count
    
    total = 0
    with from_file.open("rb") as fh:
        # Capture the 'readinto' method to avoid lookups.
        reader = fh.readinto

        # read into the buffer and capture the number of bytes fetched,
        # which will be 'size' until the last read from the file.
        read = reader(buf)
        while read == bufsize:  # nominal case for large files
            total += counter(b'\n')
            read = reader(buf)

        # when 0 <= read < bufsize we're on the last page of the
        # file, so we need to take a slice of the buffer, which creates
        # a new object and thus we also have to lookup count. it's trivial
        # but if you have to do it 10,000x it's definitely not a rounding error.
        return total + buf[:read].count(b'\n')


def _count_listing_entries(tdenv: TradeEnv, listings: Path) -> int:
    """ Calculates the number of entries in a listing file by counting the lines. """
    if not listings.exists():
        tdenv.NOTE("File not found, aborting: {}", listings)
        return 0
    
    tdenv.DEBUG0(f"Getting total number of entries in {listings}...")
    count = _file_line_count(listings)
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
        'solo':         "Don't download crowd-sourced market data. (Implies '-O skipvend', supercedes '-O all', '-O clean', '-O listings'.)",
    }
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
        
        self.dataPath = Path(os.environ.get('TD_EDDB')) if os.environ.get('TD_EDDB') else self.tdb.dataPath / Path("eddb")
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
        
        def openURL(url):
            return _request_url(url, headers = {'User-Agent': 'Trade-Dangerous'})
        
        if path not in (self.liveListingsPath, self.listingsPath):
            localPath = Path(self.tdb.dataPath, path)
        else:
            localPath = Path(self.dataPath, path)
        
        url  = BASE_URL + str(path)
        
        self.tdenv.NOTE("Checking for update to '{}'.", path)
        try:
            response = openURL(url)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.tdenv.WARN("Problem with download:\n    URL: {}\n    Error: {}", BASE_URL + str(path), str(e))
            return False
        
        url_time = response.getheader("Last-Modified")
        dumpModded = datetime.datetime.strptime(url_time, "%a, %d %b %Y %H:%M:%S %Z").timestamp()
        
        if Path.exists(localPath):
            localModded = localPath.stat().st_mtime
            if localModded >= dumpModded:
                self.tdenv.DEBUG0("'{}': Dump is not more recent than Local.", path)
                return False
        
        self.tdenv.NOTE("Downloading file '{}'.", path)
        transfers.download(self.tdenv, url, localPath)
        os.utime(localPath, (dumpModded, dumpModded))
        return True
    
    def purgeSystems(self):
        """
        Purges systems from the System table that do not have any stations claiming to be in them.
        Keeps table from becoming too large because of fleet carriers moving to unpopulated systems.
        """
        db = self.tdb.getDB()
        self.tdenv.NOTE("Purging Systems with no stations: Start time = {}", self.now())

        db.execute("PRAGMA foreign_keys = OFF")

        self.tdenv.DEBUG0("Saving systems with stations.... " + str(self.now()) + "\t\t\t\t", end="\r")
        db.execute("DROP TABLE IF EXISTS System_copy")
        db.execute("""CREATE TABLE System_copy AS SELECT * FROM System
                            WHERE system_id IN (SELECT system_id FROM Station)
                    """)

        self.tdenv.DEBUG0("Erasing table and reinserting kept systems.... " + str(self.now()) + "\t\t\t\t", end="\r")
        db.execute("DELETE FROM System")
        db.execute("INSERT INTO System SELECT * FROM System_copy")

        self.tdenv.DEBUG0("Removing copy.... " + str(self.now()) + "\t\t\t\t", end="\r")
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("DROP TABLE IF EXISTS System_copy")

        db.commit()

        self.tdenv.NOTE("Finished purging Systems. End time = {}", self.now())
    
    def importListings(self, listings_file):
        """
        Updates the market data (AKA the StationItem table) using listings_file
        Writes directly to database.
        """
        listings_path = Path(self.dataPath, listings_file).absolute()
        from_live = listings_path != Path(self.dataPath, self.listingsPath).absolute()
        self.tdenv.NOTE("Processing market data from {}: Start time = {}. Live = {}", listings_file, self.now(), from_live)
        
        total = _count_listing_entries(self.tdenv, listings_path)
        if not total:
            return

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
        db = self.tdb.getDB()
        item_lookup = _make_item_id_lookup(self.tdenv, db.cursor())
        station_lookup = _make_station_id_lookup(self.tdenv, db.cursor())
        last_station_update_times = _collect_station_modified_times(self.tdenv, db.cursor())
        
        cur_station = None
        self.tdenv.DEBUG0("Processing entries...")
        with listings_path.open("r", encoding="utf-8", errors="ignore") as fh:
            prog = pbar.Progress(total, 50)

            cursor: Optional[sqlite3.Cursor] = db.cursor()
            
            for listing in csv.DictReader(fh):
                prog.increment(1, postfix = lambda value, total: f" {(value / total * 100):.0f}% {value} / {total}")
                
                station_id = int(listing['station_id'])
                if station_id not in station_lookup:
                    continue
                
                listing_time = int(listing['collected_at'])
                
                if station_id != cur_station:
                    # commit anything from the previous station, get a new cursor
                    db.commit()
                    cur_station, skip_station, cursor = station_id, False, db.cursor()
                    
                    # Check if listing already exists in DB and needs updated.
                    last_modified: int = int(last_station_update_times.get(station_id, 0))
                    if last_modified:
                        # When the listings.csv data matches the database, update to make from_live == 0.
                        if listing_time == last_modified and not from_live:
                            self.tdenv.DEBUG1(f"Marking {cur_station} as no longer 'live' (old={last_modified}, listing={listing_time}).")
                            cursor.execute(stmt_unliven_station, (cur_station,))
                            skip_station = True
                            continue

                        # Unless the import file data is newer, nothing else needs to be done for this station,
                        # so the rest of the listings for this station can be skipped.
                        if listing_time <= last_modified:
                            skip_station = True
                            continue
                        
                        # The data from the import file is newer, so we need to delete the old data for this station.
                        self.tdenv.DEBUG1(f"Deleting old listing data for {cur_station} (old={last_modified}, listing={listing_time}).")
                        cursor.execute(stmt_flush_station, (cur_station,))
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
                
                self.tdenv.DEBUG1(f"Inserting new listing data for {station_id}.")
                cursor.execute(stmt_add_listing, (
                        station_id, item_id, listing_time, from_live,
                        demand_price, demand_units, demand_level,
                        supply_price, supply_units, supply_level,
                ))
            
        prog.clear()
        
        # Do a final commit to be sure
        db.commit()
        
        self.tdenv.NOTE("Optimizing database...")
        db.execute("VACUUM")
        self.tdb.close()
        
        self.tdenv.NOTE("Finished processing market data. End time = {}", self.now())
    
    def run(self):
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
        if not (self.tdb.dataPath / Path("TradeDangerous.db")).exists():
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
            
            self.tdb.reloadCache()
            
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
        
        self.tdenv.ignoreUnknown = True
        
        if self.getOption("purge"):
            self.purgeSystems()
        
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
