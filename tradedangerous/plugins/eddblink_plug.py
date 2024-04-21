# ----------------------------------------------------------------
# Import plugin that uses data files from EDDB.io and (optionally)
# a EDDBlink_listener server to update the Database.
# ----------------------------------------------------------------
import certifi
import codecs
import csv
import datetime
import json
import os
import platform
import sqlite3
import ssl
import time

from urllib import request
from calendar import timegm
from pathlib import Path
from importlib import reload

from .. import plugins, cache, csvexport, tradedb, tradeenv, transfers
from ..misc import progress as pbar
from ..plugins import PluginException
from shutil import copyfile

# Constants
BASE_URL = os.environ.get('TD_SERVER') or "https://elite.tromador.com/files/"
CONTEXT=ssl.create_default_context(cafile=certifi.where())


def request_url(url, headers=None):
    data = None
    if headers:
        data = bytes(json.dumps(headers), encoding="utf-8")
        
    return request.urlopen(request.Request(url, data=data), context=CONTEXT)


class DecodingError(PluginException):
    pass


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
        'solo':         "Don't download crowd-sourced market data. (Implies '-O skipvend', supercedes '-O all', '-O clean', '-O listings'.)"
    }
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
        
        self.dataPath = Path(os.environ.get('TD_EDDB')) if os.environ.get('TD_EDDB') else self.tdb.dataPath / Path("eddb")
        self.categoriesPath = Path("Category.csv")
        self.commoditiesPath = Path("Item.csv")
        self.rareItemPath = Path("RareItem.csv")
        self.shipPath = Path("Ship.csv")
        self.FDevShipyardPath = Path("FDevShipyard.csv")
        self.shipVendorPath = Path("ShipVendor.csv")
        self.stationsPath = Path("Station.csv")
        self.sysPath = Path("System.csv")
        self.upgradesPath = Path("Upgrade.csv")
        self.FDevOutfittingPath = Path("FDevOutfitting.csv")
        self.upgradeVendorPath = Path("UpgradeVendor.csv")
        self.listingsPath = Path("listings.csv")
        self.liveListingsPath = Path("listings-live.csv")
        self.pricesPath = Path("listings.prices")
    
    def now(self):
        return datetime.datetime.now()
    
    def execute(self, sql_cmd, args = None):
        cur = self.tdb.getDB().cursor()
        
        success = False
        result = None
        while not success:
            try:
                if args:
                    result = cur.execute(sql_cmd, args)
                else:
                    result = cur.execute(sql_cmd)
                success = True
            except sqlite3.OperationalError as e:
                if "locked" not in str(e):
                    success = True
                    raise sqlite3.OperationalError(e)
                else:
                    print("(execute) Database is locked, waiting for access.", end = "\r")
                    time.sleep(1)
        return result
    
    def executemany(self, sql_cmd, args):
        cur = self.tdb.getDB().cursor()
        
        success = False
        result = None
        while not success:
            try:
                result = cur.executemany(sql_cmd, args)
                success = True
            except sqlite3.OperationalError as e:
                if "locked" not in str(e):
                    success = True
                    raise sqlite3.OperationalError(e)
                else:
                    print("(execute) Database is locked, waiting for access.", end = "\r")
                    time.sleep(1)
        return result
    
    @staticmethod
    def fetchIter(cursor, arraysize = 1000):
        """
        An iterator that uses fetchmany to keep memory usage down
        and speed up the time to retrieve the results dramatically.
        """
        while True:
            results = cursor.fetchmany(arraysize)
            if not results:
                break
            for result in results:
                yield result
    
    @staticmethod
    def blocks(f, size = 65536):
        while True:
            b = f.read(size)
            if not b:
                break
            yield b
    
    def downloadFile(self, path):
        """
        Fetch the latest dumpfile from the website if newer than local copy.
        """
        
        def openURL(url):
            return request_url(url, headers = {'User-Agent': 'Trade-Dangerous'})
        
        if path != self.liveListingsPath and path != self.listingsPath:
            localPath = self.tdb.dataPath / path
        else:
            localPath = self.dataPath / path
        
        url  = BASE_URL + str(path)
        
        self.tdenv.NOTE("Checking for update to '{}'.", path)
        try:
            response = openURL(url)
        except Exception as e:
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
        return True
    
    def purgeSystems(self):
        """
        Purges systems from the System table that do not have any stations claiming to be in them.
        Keeps table from becoming too large because of fleet carriers moving to unpopulated systems.
        """
    
        self.tdenv.NOTE("Purging Systems with no stations: Start time = {}", self.now())
    
        self.execute("PRAGMA foreign_keys = OFF")
    
        print("Saving systems with stations.... " + str(self.now()) + "\t\t\t\t", end="\r")
        self.execute("DROP TABLE IF EXISTS System_copy")
        self.execute("""CREATE TABLE System_copy AS SELECT * FROM System
                            WHERE system_id IN (SELECT system_id FROM Station)
                    """)
    
        print("Erasing table and reinserting kept systems.... " + str(self.now()) + "\t\t\t\t", end="\r")
        self.execute("DELETE FROM System")
        self.execute("INSERT INTO System SELECT * FROM System_copy")
    
        print("Removing copy.... " + str(self.now()) + "\t\t\t\t", end="\r")
        self.execute("PRAGMA foreign_keys = ON")
        self.execute("DROP TABLE IF EXISTS System_copy")
    
        self.tdenv.NOTE("Finished purging Systems. End time = {}", self.now())
    
    def commit(self):
        success = False
        while not success:
            try:
                self.tdb.getDB().commit()
                success = True
            except sqlite3.OperationalError:
                print("(commit) Database is locked, waiting for access.", end = "\r")
                time.sleep(1)
    
    def importListings(self, listings_file):
        """
        Updates the market data (AKA the StationItem table) using listings.csv
        Writes directly to database.
        """
        
        self.tdenv.NOTE("Processing market data from {}: Start time = {}", listings_file, self.now())
        if not (self.dataPath / listings_file).exists():
            self.tdenv.NOTE("File not found, aborting: {}", (self.dataPath / listings_file))
            return
        
        total = 1
        
        from_live = 0 if listings_file == self.listingsPath else 1
        
        # Used to check if the listings file is using the fdev_id as a temporary
        # item_id, but the item is in the DB with a permanent item_id.
        fdev2item = dict()
        result = self.execute("SELECT fdev_id,item_id FROM Item ORDER BY fdev_id").fetchall()
        for item in result:
            fdev2item[item[0]] = item[1]
        
        with open(str(self.dataPath / listings_file), "r", encoding = "utf-8", errors = 'ignore') as f:
            total += (sum(bl.count("\n") for bl in self.blocks(f)))
        
        liveList = []
        liveStmt = """UPDATE StationItem
                    SET from_live = 0
                    WHERE station_id = ?"""
        
        delList = []
        delStmt = "DELETE from StationItem WHERE station_id = ?"
        
        listingList = []
        listingStmt = """INSERT OR IGNORE INTO StationItem
                        (station_id, item_id, modified,
                         demand_price, demand_units, demand_level,
                         supply_price, supply_units, supply_level, from_live)
                        VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ? )"""
        
        items = []
        it_result = self.execute("SELECT item_id FROM Item ORDER BY item_id").fetchall()
        for item in it_result:
            items.append(item[0])
        
        stationList = {
            stationID
            for (stationID,) in self.execute("SELECT station_id FROM Station")
        }
        
        with open(str(self.dataPath / listings_file), "r") as fh:
            prog = pbar.Progress(total, 50)
            listings = csv.DictReader(fh)
            
            cur_station = -1
            
            for listing in listings:
                prog.increment(1, postfix = lambda value, goal: " " + str(round(value / total * 100)) + "%")
                
                station_id = int(listing['station_id'])
                if station_id not in stationList:
                    continue
                
                if station_id != cur_station:
                    cur_station = station_id
                    skipStation = False
                    
                    # Check if listing already exists in DB and needs updated.
                    # Only need to check the date for the first item at a specific station.
                    result = self.execute("SELECT modified FROM StationItem WHERE station_id = ?", (station_id,)).fetchone()
                    if result:
                        updated = timegm(datetime.datetime.strptime(result[0].split('.')[0], '%Y-%m-%d %H:%M:%S').timetuple())
                        # When the listings.csv data matches the database, update to make from_live == 0.
                        if int(listing['collected_at']) == updated and not from_live:
                            liveList.append((cur_station,))
                        # Unless the import file data is newer, nothing else needs to be done for this station,
                        # so the rest of the listings for this station can be skipped.
                        if int(listing['collected_at']) <= updated:
                            skipStation = True
                            continue
                        
                        # The data from the import file is newer, so we need to delete the old data for this station.
                        delList.append((cur_station,))
                
                if skipStation:
                    continue
                
                # Since this station is not being skipped, get the data and prepare for insertion into the DB.
                item_id = int(listing['commodity_id'])
                # listings.csv includes rare items, which we are ignoring.
                if item_id not in items:
                    continue
                modified = datetime.datetime.utcfromtimestamp(int(listing['collected_at'])).strftime('%Y-%m-%d %H:%M:%S')
                demand_price = int(listing['sell_price'])
                demand_units = int(listing['demand'])
                demand_level = int(listing['demand_bracket']) if listing['demand_bracket'] != '' else -1
                supply_price = int(listing['buy_price'])
                supply_units = int(listing['supply'])
                supply_level = int(listing['supply_bracket']) if listing['supply_bracket'] != '' else -1
                
                listingList.append((station_id, item_id, modified,
                                    demand_price, demand_units, demand_level,
                                    supply_price, supply_units, supply_level, from_live))
            
            while prog.value < prog.maxValue:
                prog.increment(1, postfix = lambda value, goal: " " + str(round(value / total * 100)) + "%")
            prog.clear()
            
            self.tdenv.NOTE("Import file processing complete, updating database. {}", self.now())
            if liveList:
                self.tdenv.NOTE("Marking data now in the EDDB listings.csv as no longer 'live'. {}", self.now())
                self.executemany(liveStmt, liveList)
            if delList:
                self.tdenv.NOTE("Deleting old listing data. {}", self.now())
                self.executemany(delStmt, delList)
            if listingList:
                self.tdenv.NOTE("Inserting new listing data. {}", self.now())
                self.executemany(listingStmt, listingList)
        
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
            # if not option in ('force', 'fallback', 'skipvend', 'progbar'):
            if not option in ('force', 'skipvend'):
                default = False
        if default:
            self.options["listings"] = True
        
        # We can probably safely assume that the plugin has never been run if
        # the prices file doesn't exist, since the plugin always generates it.
        if not (self.tdb.dataPath / Path("TradeDangerous.prices")).exists():
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
        
        self.tdenv.ignoreUnknown = True
        
        success = False
        while not success:
            try:
                self.tdenv.DEBUG0("Loading Database. {}", self.now())
                self.tdb.load(maxSystemLinkLy = self.tdenv.maxSystemLinkLy)
                success = True
            except sqlite3.OperationalError:
                print("Database is locked, waiting for access.", end = "\r")
                time.sleep(1)
        self.tdenv.DEBUG0("Database loaded.")
        
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
        if self.getOption("purge"):
            self.purgeSystems()
            self.commit()
        
        if self.getOption("upgrade"):
            if self.downloadFile(self.upgradesPath) or self.getOption("force"):
                self.downloadFile(self.FDevOutfittingPath)
                buildCache = True
        
        if self.getOption("ship"):
            if self.downloadFile(self.shipPath) or self.getOption("force"):
                self.downloadFile(self.FDevShipyardPath)
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
            cache.buildCache(self.tdb, self.tdenv)
        
        if self.getOption("listings"):
            if self.downloadFile(self.listingsPath) or self.getOption("force"):
                self.importListings(self.listingsPath)
            if self.downloadFile(self.liveListingsPath) or self.getOption("force"):
                self.importListings(self.liveListingsPath)
        
        self.commit()
        
        self.tdb.close()
        
        if self.getOption("listings"):
            self.tdenv.NOTE("Regenerating .prices file.")
            cache.regeneratePricesFile(self.tdb, self.tdenv)
        
        self.tdenv.NOTE("Import completed.")
        
        # TD doesn't need to do anything, tell it to just quit.
        return False
