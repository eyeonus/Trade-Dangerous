# ----------------------------------------------------------------
# Import plugin that uses data files from EDDB.io and (optionally)
# a EDDBlink_listener server to update the Database.
# ----------------------------------------------------------------

import codecs
import csv
import datetime
import json
import os
import platform
import sqlite3
import time

from urllib import request
from calendar import timegm
from pathlib import Path
from importlib import reload
from builtins import str

from .. import plugins, cache, csvexport, tradedb, tradeenv, transfers
from ..misc import progress as pbar
from ..plugins import PluginException
from shutil import copyfile

# Constants
BASE_URL = os.environ.get('TD_SERVER') or "http://elite.tromador.com/files/"
FALLBACK_URL = os.environ.get('TD_FALLBACK') or "https://eddb.io/archive/v6/"
SHIPS_URL = os.environ.get('TD_SHIPS') or "https://beta.coriolis.io/data/index.json"
COMMODITIES = "commodities.json"
SYSTEMS = "systems_populated.jsonl"
STATIONS = "stations.jsonl"
UPGRADES = "modules.json"
LISTINGS = "listings.csv"
LIVE_LISTINGS = "listings-live.csv"


class DecodingError(PluginException):
    pass


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads data from eddb.
    """
    
    pluginOptions = {
        'item':         "Regenerate Categories and Items using latest commodities.json dump.",
        'system':       "Regenerate Systems using latest system-populated.jsonl dump.",
        'station':      "Regenerate Stations using latest stations.jsonl dump. (Implies '-O system')",
        'ship':         "Regenerate Ships using latest coriolis.io json dump.",
        'shipvend':     "Regenerate ShipVendors using latest stations.jsonl dump. (Implies '-O system,station,ship')",
        'upgrade':      "Regenerate Upgrades using latest modules.json dump.",
        'upvend':       "Regenerate UpgradeVendors using latest stations.jsonl dump. (Implies '-O system,station,upgrade')",
        'listings':     "Update market data using latest listings.csv dump. (Implies '-O item,system,station')",
        'all':          "Update everything with latest dumpfiles. (Regenerates all tables)",
        'clean':        "Erase entire database and rebuild from empty. (Regenerates all tables.)",
        'skipvend':     "Don't regenerate ShipVendors or UpgradeVendors. (Supercedes '-O all', '-O clean'.)",
        'force':        "Force regeneration of selected items even if source file not updated since previous run. "
                        "(Useful for updating Vendor tables if they were skipped during a '-O clean' run.)",
        'fallback':     "Fallback to using EDDB.io if Tromador's mirror isn't working.",
        'progbar':      "Does nothing, only included for backwards compatibility.",
        'solo':         "Don't download crowd-sourced market data. (Implies '-O skipvend', supercedes '-O all', '-O clean', '-O listings'.)"
    }
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
        
        self.dataPath = Path(os.environ.get('TD_EDDB')) if os.environ.get('TD_EDDB') else tdb.dataPath / Path("eddb")
        self.commoditiesPath = Path(COMMODITIES)
        self.systemsPath = Path(SYSTEMS)
        self.stationsPath = Path(STATIONS)
        self.upgradesPath = Path(UPGRADES)
        self.listingsPath = Path(LISTINGS)
        self.liveListingsPath = Path(LIVE_LISTINGS)
        self.shipsPath = Path("index.json")
        self.pricesPath = Path("listings.prices")
        self.updated = {
                "Category": False,
                "Item": False,
                "RareItem": False,
                "Ship": False,
                "ShipVendor": False,
                "Station": False,
                "System": False,
                "Upgrade": False,
                "UpgradeVendor": False,
                "Listings": False
            }
    
    def execute(self, sql_cmd, args = None):
        tdb, tdenv = self.tdb, self.tdenv
        cur = tdb.getDB().cursor()
        
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
        tdb, tdenv = self.tdb, self.tdenv
        cur = tdb.getDB().cursor()
        
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
    
    def downloadFile(self, urlTail, path):
        """
        Fetch the latest dumpfile from the website if newer than local copy.
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        def openURL(url):
            return request.urlopen(request.Request(url, headers = {'User-Agent': 'Trade-Dangerous'}))
        
        tdenv.NOTE("Checking for update to '{}'.", path)
        if urlTail == SHIPS_URL:
            url = SHIPS_URL
        else:
            url = BASE_URL + urlTail
        if url == SHIPS_URL or not self.getOption('fallback'):
            try:
                response = openURL(url)
            except Exception as e:
                # If Tromador's server fails for whatever reason,
                # fallback to download direct from EDDB.io
                tdenv.WARN("Problem with download:\nURL: {}\nError: {}", url, str(e))
                if url == SHIPS_URL:
                    tdenv.NOTE("Using Default Ship Index.")
                    copyfile(self.tdenv.templateDir / Path("DefaultShipIndex.json"), self.dataPath / path)
                    return True

                if urlTail != LIVE_LISTINGS:
                    self.options["fallback"] = True
        
        if self.getOption('fallback') and url != SHIPS_URL:
            # EDDB.io doesn't have live listings or the ship index.
            if urlTail == LIVE_LISTINGS:
                return False

            url = FALLBACK_URL + urlTail
            try:
                response = openURL(url)
            except Exception as e:
                tdenv.WARN("Problem with download (fallback enabled):\nURL: {}\nError: {}", url, str(e))
                return False
        
        dumpModded = 0
        # The coriolis file is from github, so it doesn't have a "Last-Modified" metadata.
        if url != SHIPS_URL:
            # Stupid strptime() is locale-dependent, so we do it ourself.
            # 'Last-Modified' is in the form "DDD, dd MMM yyyy hh:mm:ss GMT"
            # dDL                               0   1   2    3        4   5
            # dTL                                               0  1  2
            
            # We'll need to turn the 'MMM' into a number.
            Months = {'Jan':1, 'Feb':2, 'Mar':3, 'Apr':4, 'May':5, 'Jun':6, 'Jul':7, 'Aug':8, 'Sep':9, 'Oct':10, 'Nov':11, 'Dec':12}
            
            # We need to split the string twice, because the time is separated by ':', not ' '.
            dDL = response.getheader("Last-Modified").split(' ')
            dTL = dDL[4].split(':')
            
            # Now we need to make a datetime object using the DateList and TimeList we just created,
            # and then we can finally convert that to a Unix-epoch number.
            dumpDT = datetime.datetime(int(dDL[3]), Months[dDL[2]], int(dDL[1]), \
               hour = int(dTL[0]), minute = int(dTL[1]), second = int(dTL[2]), \
               tzinfo = datetime.timezone.utc)
            dumpModded = timegm(dumpDT.timetuple())
        
        if Path.exists(self.dataPath / path):
            localModded = (self.dataPath / path).stat().st_mtime
            if localModded >= dumpModded and url != SHIPS_URL:
                tdenv.DEBUG0("'{}': Dump is not more recent than Local.", path)
                return False
        
        tdenv.NOTE("Downloading file '{}'.", path)
        transfers.download(self.tdenv, url, self.dataPath / path)
        return True
    
    def importUpgrades(self):
        """
        Populate the Upgrade table using modules.json
        Writes directly to database.
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.NOTE("Processing Upgrades: Start time = {}", datetime.datetime.now())
        with open(str(self.dataPath / self.upgradesPath), "rU") as fh:
            upgrades = json.load(fh)
        for upgrade in iter(upgrades):
            upgrade_id = upgrade['id']
            name = upgrade['name'] if upgrade['name'] else upgrade['ed_symbol'].replace('_', ' ')
            weight = upgrade['mass'] if 'mass' in upgrade else 0
            cost = upgrade['price'] if upgrade['price'] else 0
            
            tdenv.DEBUG1("Updating: {}, {}, {}, {}", upgrade_id, name, weight, cost)
            try:
                self.execute("""INSERT INTO Upgrade
                            ( upgrade_id,name,weight,cost ) VALUES
                            ( ?, ?, ?, ? ) """,
                            (upgrade_id, name, weight, cost))
            except sqlite3.IntegrityError:
                try:
                    self.execute("""UPDATE Upgrade
                                SET name = ?,weight = ?,cost = ?
                                WHERE upgrade_id = ?""",
                                (name, weight, cost,
                                 upgrade_id))
                except sqlite3.IntegrityError:
                    tdenv.DEBUG0("Unable to insert or update: {}, {}, {}, {}", upgrade_id, name, weight, cost)
        
        self.updated['Upgrade'] = True
        
        tdenv.NOTE("Finished processing Upgrades. End time = {}", datetime.datetime.now())
    
    def importShips(self):
        """
        Populate the Ship table using coriolis.io's index.json
        Writes directly to database.
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.NOTE("Processing Ships: Start time = {}", datetime.datetime.now())
        with open(str(self.dataPath / self.shipsPath), "rU") as fh:
            ships = json.load(fh)['Ships']
        for ship in iter(ships):
            ship_id = ships[ship]['eddbID']
            name = ships[ship]['properties']['name']
            cost = ships[ship]['retailCost']
            fdev_id = ships[ship]['edID']
            # Arg. Why you do this to me, EDCD?
            if "Phantom" in name and ship_id == 35:
                ship_id = 37
            # Change the names to match how they appear in Stations.jsonl
            if name == "Eagle":
                name = "Eagle Mk. II"
            if name == "Sidewinder":
                name = "Sidewinder Mk. I"
            if name == "Viper":
                name = "Viper Mk. III"
            
            # Make sure all the 'Mark N' ship names abbreviate 'Mark' the same.
            # Fix capitalization.
            name = name.replace('MK', 'Mk').replace('mk', 'Mk').replace('mK', 'Mk')
            # Fix no '.' in abbreviation.
            if "Mk" in name and "Mk." not in name:
                name = name.replace('Mk', 'Mk.')
            # Fix no trailing space.
            if "Mk." in name and "Mk. " not in name:
                name = name.replace("Mk.", "Mk. ")
            # Fix no leading space.
            if "Mk." in name and " Mk." not in name:
                name = name.replace("Mk.", " Mk.")
            
            tdenv.DEBUG1("Updating: {}, {}, {}, {}", ship_id, name, cost, fdev_id)
            try:
                self.execute("""INSERT INTO Ship
                                ( ship_id,name,cost,fdev_id ) VALUES
                                ( ?, ?, ?, ? ) """,
                                (ship_id, name, cost, fdev_id))
            except sqlite3.IntegrityError:
                try:
                    self.execute("""UPDATE Ship
                                    SET name = ?,cost = ?,fdev_id = ?
                                    WHERE ship_id = ?""",
                                    (name, cost, fdev_id,
                                     ship_id))
                except sqlite3.IntegrityError:
                    tdenv.DEBUG0("Unable to insert or update: {}, {}, {}, {}", ship_id, name, cost, fdev_id)
        
        self.updated['Ship'] = True
        
        tdenv.NOTE("Finished processing Ships. End time = {}", datetime.datetime.now())
    
    def importSystems(self):
        """
        Populate the System table using systems_populated.jsonl
        Writes directly to database.
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.NOTE("Processing Systems: Start time = {}", datetime.datetime.now())
        
        total = 1
        
        with open(str(self.dataPath / self.systemsPath), "r", encoding = "utf-8", errors = 'ignore') as f:
            total += (sum(bl.count("\n") for bl in self.blocks(f)))
        
        with open(str(self.dataPath / self.systemsPath), "rU") as fh:
            prog = pbar.Progress(total, 50)
            for line in fh:
                prog.increment(1, postfix = lambda value, goal: " " + str(round(value / total * 100)) + "%")
                system = json.loads(line)
                system_id = system['id']
                name = system['name']
                pos_x = system['x']
                pos_y = system['y']
                pos_z = system['z']
                modified = datetime.datetime.utcfromtimestamp(system['updated_at']).strftime('%Y-%m-%d %H:%M:%S')
                
                result = self.execute("SELECT modified FROM System WHERE system_id = ?", (system_id,)).fetchone()
                if result:
                    updated = timegm(datetime.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').timetuple())
                    if system['updated_at'] > updated:
                        tdenv.DEBUG0("System '{}' has been updated: '{}' vs '{}'", name, modified, result[0])
                        tdenv.DEBUG1("Updating: {}, {}, {}, {}, {}, {}", system_id, name, pos_x, pos_y, pos_z, modified)
                        self.execute("""UPDATE System
                                    SET name = ?,pos_x = ?,pos_y = ?,pos_z = ?,modified = ?
                                    WHERE system_id = ?""",
                                    (name, pos_x, pos_y, pos_z, modified,
                                     system_id))
                        self.updated['System'] = True
                else:
                    tdenv.DEBUG0("System '{}' has been added.", name)
                    tdenv.DEBUG1("Inserting: {}, {}, {}, {}, {}, {}", system_id, name, pos_x, pos_y, pos_z, modified)
                    self.execute("""INSERT INTO System
                                ( system_id,name,pos_x,pos_y,pos_z,modified ) VALUES
                                ( ?, ?, ?, ?, ?, ? ) """,
                                (system_id, name, pos_x, pos_y, pos_z, modified))
                    self.updated['System'] = True
            while prog.value < prog.maxValue:
                prog.increment(1, postfix = lambda value, goal: " " + str(round(value / total * 100)) + "%")
            prog.clear()
        
        tdenv.NOTE("Finished processing Systems. End time = {}", datetime.datetime.now())
    
    def importStations(self):
        """
        Populate the Station table using stations.jsonl
        Also populates the ShipVendor table if the option is set.
        Writes directly to database.
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.NOTE("Processing Stations, this may take a bit: Start time = {}", datetime.datetime.now())
        if self.getOption('shipvend'):
            tdenv.NOTE("Simultaneously processing ShipVendors.")
        
        if self.getOption('upvend'):
            tdenv.NOTE("Simultaneously processing UpgradeVendors, this will take quite a while.")
        
        total = 1
        
        with open(str(self.dataPath / self.stationsPath), "r", encoding = "utf-8", errors = 'ignore') as f:
            total += (sum(bl.count("\n") for bl in self.blocks(f)))
        
        with open(str(self.dataPath / self.stationsPath), "rU") as fh:
            prog = pbar.Progress(total, 50)
            for line in fh:
                prog.increment(1, postfix = lambda value, goal: " " + str(round(value / total * 100)) + "%")
                station = json.loads(line)
                
                # Import Stations
                station_id = station['id']
                name = station['name']
                system_id = station['system_id']
                ls_from_star = station['distance_to_star'] if station['distance_to_star'] else 0
                blackmarket = 'Y' if station['has_blackmarket'] else 'N'
                max_pad_size = station['max_landing_pad_size'] if station['max_landing_pad_size'] and station['max_landing_pad_size'] != 'None' else '?'
                market = 'Y' if station['has_market'] else 'N'
                shipyard = 'Y' if station['has_shipyard'] else 'N'
                modified = datetime.datetime.utcfromtimestamp(station['updated_at']).strftime('%Y-%m-%d %H:%M:%S')
                outfitting = 'Y' if station['has_outfitting'] else 'N'
                rearm = 'Y' if station['has_rearm'] else 'N'
                refuel = 'Y' if station['has_refuel'] else 'N'
                repair = 'Y' if station['has_repair'] else 'N'
                planetary = 'Y' if station['is_planetary'] else 'N'
                type_id = station['type_id'] if station['type_id'] else 0
                
                system = self.execute("SELECT System.name FROM System WHERE System.system_id = ?", (system_id,)).fetchone()[0].upper()
                
                result = self.execute("SELECT modified FROM Station WHERE station_id = ?", (station_id,)).fetchone()
                if result:
                    updated = timegm(datetime.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').timetuple())
                    if station['updated_at'] > updated:
                        tdenv.DEBUG0("{}/{} has been updated: {} vs {}",
                                    system , name, modified, result[0])
                        tdenv.DEBUG1("Updating: {}, {}, {}, {}, {}, {}, {},"
                                              " {}, {}, {}, {}, {}, {}, {}, {}",
                                    station_id, name, system_id, ls_from_star, blackmarket,
                                    max_pad_size, market, shipyard, modified, outfitting,
                                    rearm, refuel, repair, planetary, type_id)
                        self.execute("""UPDATE Station
                                    SET name = ?, system_id = ?, ls_from_star = ?, blackmarket = ?,
                                    max_pad_size = ?, market = ?, shipyard = ?, modified = ?,
                                    outfitting = ?, rearm = ?, refuel = ?, repair = ?, planetary = ?, type_id = ?
                                    WHERE station_id = ?""",
                                    (name, system_id, ls_from_star, blackmarket,
                                     max_pad_size, market, shipyard, modified,
                                     outfitting, rearm, refuel, repair, planetary, type_id,
                                     station_id))
                        self.updated['Station'] = True
                else:
                    tdenv.DEBUG0("{}/{} has been added:", system , name)
                    tdenv.DEBUG1("Inserting: {}, {}, {}, {}, {}, {}, {},"
                                              " {}, {}, {}, {}, {}, {}, {}, {}",
                        station_id, name, system_id, ls_from_star, blackmarket,
                        max_pad_size, market, shipyard, modified, outfitting,
                        rearm, refuel, repair, planetary, type_id)
                    self.execute("""INSERT INTO Station (
                                station_id,name,system_id,ls_from_star,
                                blackmarket,max_pad_size,market,shipyard,
                                modified,outfitting,rearm,refuel,
                                repair,planetary,type_id ) VALUES
                                ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? ) """,
                                (station_id, name, system_id, ls_from_star,
                                 blackmarket, max_pad_size, market, shipyard,
                                 modified, outfitting, rearm, refuel,
                                 repair, planetary, type_id))
                    self.updated['Station'] = True
                
                # Import shipyards into ShipVendors if shipvend is set.
                if station['has_shipyard'] and self.getOption('shipvend'):
                    if not station['shipyard_updated_at']:
                        station['shipyard_updated_at'] = station['updated_at']
                    modified = datetime.datetime.utcfromtimestamp(station['shipyard_updated_at']).strftime('%Y-%m-%d %H:%M:%S')
                    result = self.execute("SELECT modified FROM ShipVendor WHERE station_id = ?", (station_id,)).fetchone()
                    if result:
                        updated = timegm(datetime.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').timetuple())
                    else:
                        updated = 0
                    if station['shipyard_updated_at'] > updated:
                        self.execute("DELETE FROM ShipVendor WHERE station_id = ?", (station_id,))
                        tdenv.DEBUG1("{}/{} has shipyard, updating ships sold.", system, name)
                        for ship in station['selling_ships']:
                            # Make sure all the 'Mark N' ship names abbreviate 'Mark' as '<Name> Mk. <Number>'.
                            # Fix capitalization.
                            ship = ship.replace('MK', 'Mk').replace('mk', 'Mk').replace('mK', 'Mk')
                            # Fix no '.' in abbreviation.
                            if "Mk" in ship and "Mk." not in ship:
                                ship = ship.replace('Mk', 'Mk.')
                            # Fix no trailing space.
                            if "Mk." in ship and "Mk. " not in ship:
                                ship = ship.replace("Mk.", "Mk. ")
                            # Fix no leading space.
                            if "Mk." in ship and " Mk." not in ship:
                                ship = ship.replace("Mk.", " Mk.")
                            
                            tdenv.DEBUG2("ship_id:{},station_id:{},modified:{}",
                                 ship,
                                 station_id,
                                 modified)
                            try:
                                self.execute("""INSERT INTO ShipVendor
                                        ( ship_id,station_id,modified ) VALUES
                                        ( (SELECT Ship.ship_id FROM Ship WHERE Ship.name = ?), ?, ? ) """,
                                        (ship,
                                         station_id,
                                         modified))
                            except sqlite3.IntegrityError:
                                continue
                        self.updated['ShipVendor'] = True
                
                # Import Outfitters into UpgradeVendors if upvend is set.
                if station['has_outfitting'] and self.getOption('upvend'):
                    if not station['outfitting_updated_at']:
                        station['outfitting_updated_at'] = station['updated_at']
                    modified = datetime.datetime.utcfromtimestamp(station['outfitting_updated_at']).strftime('%Y-%m-%d %H:%M:%S')
                    result = self.execute("SELECT modified FROM UpgradeVendor WHERE station_id = ?", (station_id,)).fetchone()
                    if result:
                        updated = timegm(datetime.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').timetuple())
                    else:
                        updated = 0
                    if station['outfitting_updated_at'] > updated:
                        self.execute("DELETE FROM UpgradeVendor WHERE station_id = ?", (station_id,))
                        tdenv.DEBUG1("{}/{} has outfitting, updating modules sold.", system, name)
                        for upgrade in station['selling_modules']:
                            tdenv.DEBUG2("upgrade_id:{},station_id:{},modified:{}",
                                 upgrade,
                                 station['id'],
                                 modified)
                            try:
                                self.execute("""INSERT INTO UpgradeVendor
                                        ( upgrade_id,station_id,cost,modified ) VALUES
                                        ( ?, ?, (SELECT Upgrade.cost FROM Upgrade WHERE Upgrade.upgrade_id = ?), ? ) """,
                                        (upgrade,
                                         station_id,
                                         upgrade,
                                         modified))
                            except sqlite3.IntegrityError:
                                continue
                        self.updated['UpgradeVendor'] = True
            while prog.value < prog.maxValue:
                prog.increment(1, postfix = lambda value, goal: " " + str(round(value / total * 100)) + "%")
            prog.clear()
        
        tdenv.NOTE("Finished processing Stations. End time = {}", datetime.datetime.now())
    
    def importCommodities(self):
        """
        Populate the Category, and Item tables using commodities.json
        Writes directly to the database.
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.NOTE("Processing Categories and Items: Start time = {}", datetime.datetime.now())
        with open(str(self.dataPath / self.commoditiesPath), "rU") as fh:
            commodities = json.load(fh)
        
        # EDDB still hasn't added these Commodities to the API,
        # so we'll add them ourselves.
        tdenv.NOTE("Checking for missing items....")
        
        # Need to get the category_ids from the .csv file.
        cat_ids = dict()
        try:
            with open(str(tdb.dataPath / Path("Category.csv")), "r") as fh:
                cats = csv.DictReader(fh, quotechar = "'")
                for cat in cats:
                    cat_ids[cat['name']] = int(cat['unq:category_id'])
        # Use default if no file, such as on a 'clean' run.
        except FileNotFoundError:
            cat_ids = {'Chemicals':1, 'Consumer Items':2, 'Legal Drugs':3, 'Foods':4, 'Industrial Materials':5,
                       'Machinery':6, 'Medicines':7, 'Metals':8, 'Minerals':9, 'Slavery':10, 'Technology':11,
                       'Textiles':12, 'Waste':13, 'Weapons':14, 'Unknown':15, 'Salvage':16}
        
        # EDCD is really quick about getting new items updated, so we'll use its item list to check
        # for missing items in EDDB.io's list.
        edcd_source = 'https://raw.githubusercontent.com/EDCD/FDevIDs/master/commodity.csv'
        edcd_csv = request.urlopen(edcd_source)
        edcd_dict = csv.DictReader(codecs.iterdecode(edcd_csv, 'utf-8'))
        
        def blankItem(name, ed_id, category, category_id):
            return {"id":ed_id, "name":name, "category_id":category_id, "average_price":None, "is_rare":0,
                    "max_buy_price":None, "max_sell_price":None, "min_buy_price":None, "min_sell_price":None,
                    "buy_price_lower_average":0, "sell_price_upper_average":0, "is_non_marketable":0, "ed_id":ed_id,
                    "category":{"id":category_id, "name":category}}
        
        for line in iter(edcd_dict):
            if not any(c.get('ed_id', None) == int(line['id']) for c in commodities):
                tdenv.DEBUG0("'{}' with fdev_id {} not found, adding.", line['name'], line['id'])
                commodities.append(blankItem(line['name'], line['id'], line['category'], cat_ids[line['category']]))
        
        tdenv.NOTE("Missing item check complete.")
        
        # Prep-work for checking if an item's item_id has changed.
        cur_ids = dict()
        result = self.execute("SELECT fdev_id,item_id FROM Item ORDER BY fdev_id").fetchall()
        for item in result:
            cur_ids[item[0]] = item[1]
        
        tdenv.DEBUG0("Beginning loop.")
        for commodity in iter(commodities):
            # Make sure the broken item(s) in EDDB.io's API isn't imported.
            if not commodity['ed_id']:
                tdenv.DEBUG0("Skipping faulty item: {}:{}" , commodity['id'], commodity['name'])
                continue
            # Get the categories from the json and place them into the Category table.
            category_id = commodity['category']['id']
            category_name = commodity['category']['name']
            
            tdenv.DEBUG1("Updating: {}, {}", category_id, category_name)
            try:
                self.execute("""INSERT INTO Category
                            ( category_id, name ) VALUES
                            ( ?, ? ) """,
                            (category_id, category_name))
            except sqlite3.IntegrityError:
                try:
                    self.execute("""UPDATE Category
                                SET name = ?
                                WHERE category_id = ?""",
                                (category_name, category_id))
                
                except sqlite3.IntegrityError:
                    tdenv.DEBUG0("Unable to insert or update: {}, {}", category_id, category_name)
            
            item_id = commodity['id']
            name = commodity['name']
            if name.lower() == 'salvageable wreckage':
                name = 'Wreckage Components'
            if name.lower() == 'political prisoner':
                name = 'Political Prisoners'
            if name.lower() == 'hostage':
                name = 'Hostages'
            if name.lower() == 'methanol monohydrate':
                name = 'Methanol Monohydrate Crystals'
            if name.lower() == 'occupied cryopod':
                name = 'Occupied Escape Pod'
            category_id = commodity['category_id']
            avg_price = commodity['average_price']
            fdev_id = commodity['ed_id']
            # "ui_order" doesn't have an equivalent field in the json.
            
            tdenv.DEBUG1("Updating: {}, {}, {}, {}, {}", item_id, name, category_id, avg_price, fdev_id)
            
            # If the item_id has changed, we need to completely delete the old entry.
            if cur_ids.get(fdev_id) != item_id:
                tdenv.DEBUG1("Did not match item_id:{} with fdev_id:{} -- {}", item_id, fdev_id, cur_ids.get(fdev_id))
                if cur_ids.get(fdev_id):
                    tdenv.DEBUG0("item_id  for '{}' has changed, updating.", name)
                    self.execute("DELETE FROM Item where fdev_id = ?", (fdev_id,))
            
            try:
                self.execute("""INSERT INTO Item
                            (item_id,name,category_id,avg_price,fdev_id) VALUES
                            ( ?, ?, ?, ?, ? )""",
                            (item_id, name, category_id, avg_price, fdev_id))
            except sqlite3.IntegrityError:
                try:
                    self.execute("""UPDATE Item
                                SET name = ?,category_id = ?,avg_price = ?,fdev_id = ?
                                WHERE item_id = ?""",
                                (name, category_id, avg_price, fdev_id, item_id))
                except sqlite3.IntegrityError:
                    tdenv.DEBUG0("Unable to insert or update: {}, {}, {}, {}, {}", item_id, name, category_id, avg_price, fdev_id)
        
        # The items aren't in the same order in the json as they are in the game's UI.
        # This creates a temporary object that has all the items sorted first
        # by category and second by name, as in the UI, which will then be used to
        # update the entries in the database with the correct "ui_order" value.
        temp = self.execute("""SELECT
                        name, category_id, fdev_id
                        FROM Item
                        ORDER BY category_id, name
                       """)
        cat_id = 0
        ui_order = 1
        tdenv.DEBUG0("Adding ui_order data to items.")
        for line in temp:
            if line[1] != cat_id:
                ui_order = 1
                cat_id = line[1]
            else:
                ui_order += 1
            self.execute("""UPDATE Item
                        set ui_order = ?
                        WHERE fdev_id = ?""",
                       (ui_order, line[2]))
        
        self.updated['Category'] = True
        self.updated['Item'] = True
        
        tdenv.NOTE("Finished processing Categories and Items. End time = {}", datetime.datetime.now())
    
    def regenerate(self):
        for table in [
            "Category",
            "Item",
            "RareItem",
            "Ship",
            "ShipVendor",
            "Station",
            "System",
            "Upgrade",
            "UpgradeVendor",
        ]:
            if self.updated[table]:
                _, path = csvexport.exportTableToFile(
                    self.tdb, self.tdenv, table
                )
                self.tdenv.NOTE("{} exported.", path)
    
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
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.NOTE("Processing market data from {}: Start time = {}", listings_file, datetime.datetime.now())
        if not (self.dataPath / listings_file).exists():
            tdenv.NOTE("File not found, aborting: {}", (self.dataPath / listings_file))
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
        
        with open(str(self.dataPath / listings_file), "rU") as fh:
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
                        updated = timegm(datetime.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').timetuple())
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
            
            tdenv.NOTE("Import file processing complete, updating database. {}", datetime.datetime.now())
            if liveList:
                tdenv.NOTE("Marking data now in the EDDB listings.csv as no longer 'live'. {}", datetime.datetime.now())
                self.executemany(liveStmt, liveList)
            if delList:
                tdenv.NOTE("Deleting old listing data. {}", datetime.datetime.now())
                self.executemany(delStmt, delList)
            if listingList:
                tdenv.NOTE("Inserting new listing data. {}", datetime.datetime.now())
                self.executemany(listingStmt, listingList)
        
        self.updated['Listings'] = True
        tdenv.NOTE("Finished processing market data. End time = {}", datetime.datetime.now())
    
    def run(self):
        tdb, tdenv = self.tdb, self.tdenv
        
        if self.getOption("progbar"):
            tdenv.NOTE("The 'progbar' option has been deprecated and no longer has any function.")
        
        # Create the /eddb folder for downloading the source files if it doesn't exist.
        try:
            Path(str(self.dataPath)).mkdir()
        except FileExistsError:
            pass
        
        # Run 'listings' by default:
        # If no options, or if only 'progbar', 'force', 'skipvend', and/or 'fallback',
        # have been passed, enable 'listings'.
        default = True
        for option in self.options:
            if not option in ('force', 'fallback', 'skipvend', 'progbar'):
                default = False
        if default:
            self.options["listings"] = True
        
        # We can probably safely assume that the plugin has never been run if
        # the prices file doesn't exist, since the plugin always generates it.
        if not (tdb.dataPath / Path("TradeDangerous.prices")).exists():
            self.options["clean"] = True
        
        if self.getOption("clean"):
            # Rebuild the tables from scratch. Must be done on first run of plugin.
            # Can be done at anytime with the "clean" option.
            for name in [
                "Category",
                "Item",
                "Ship",
                "ShipVendor",
                "Station",
                "System",
                "Upgrade",
                "UpgradeVendor",
            ]:
                file = tdb.dataPath / Path(name + ".csv")
                try:
                    os.remove(str(file))
                except FileNotFoundError:
                    pass
            
            try:
                os.remove(str(tdb.dataPath) + "/TradeDangerous.db")
            except FileNotFoundError:
                pass
            try:
                os.remove(str(tdb.dataPath) + "/TradeDangerous.prices")
            except FileNotFoundError:
                pass
            
            # Because this is a clean run, we need to temporarily rename the RareItem.csv,
            # otherwise TD will crash trying to insert the rare items to the database,
            # because there's nothing in the Station table it tries to pull from.
            ri_path = tdb.dataPath / Path("RareItem.csv")
            rib_path = ri_path.with_suffix(".tmp")
            if rib_path.exists() and ri_path.exists():
                rib_path.unlink()
            if ri_path.exists():
                ri_path.rename(rib_path)
            
            tdb.reloadCache()
            
            # Now it's safe to move RareItems back.
            if ri_path.exists():
                ri_path.unlink()
            if rib_path.exists():
                rib_path.rename(ri_path)
            
            self.options["all"] = True
            self.options["force"] = True
        
        tdenv.ignoreUnknown = True
        
        success = False
        while not success:
            try:
                tdb.load(maxSystemLinkLy = tdenv.maxSystemLinkLy)
                success = True
            except sqlite3.OperationalError:
                print("Database is locked, waiting for access.", end = "\r")
                time.sleep(1)
        
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
        
        if self.getOption("station"):
            self.options["system"] = True
        
        if self.getOption("all"):
            self.options["item"] = True
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
        if self.getOption("upgrade"):
            if self.downloadFile(UPGRADES, self.upgradesPath) or self.getOption("force"):
                self.importUpgrades()
                self.commit()
        
        if self.getOption("ship"):
            if self.downloadFile(SHIPS_URL, self.shipsPath) or self.getOption("force"):
                self.importShips()
                self.commit()
        
        if self.getOption("system"):
            if self.downloadFile(SYSTEMS, self.systemsPath) or self.getOption("force"):
                self.importSystems()
                self.commit()
        
        if self.getOption("station"):
            if self.downloadFile(STATIONS, self.stationsPath) or self.getOption("force"):
                self.importStations()
                self.commit()
        
        if self.getOption("item"):
            if self.downloadFile(COMMODITIES, self.commoditiesPath) or self.getOption("force"):
                self.importCommodities()
                self.commit()
        
        # Remake the .csv files with the updated info.
        self.regenerate()
        
        # (Re)make the RareItem table.
        cache.processImportFile(tdenv, tdb.getDB(), tdb.dataPath / Path('RareItem.csv'), 'RareItem')
        
        if self.getOption("listings"):
            if self.downloadFile(LISTINGS, self.listingsPath) or self.getOption("force"):
                self.importListings(self.listingsPath)
            if not self.getOption("fallback") and (self.downloadFile(LIVE_LISTINGS, self.liveListingsPath) or self.getOption("force")):
                self.importListings(self.liveListingsPath)
        
        self.commit()
        
        tdb.close()
        
        if self.updated['Listings']:
            tdenv.NOTE("Regenerating .prices file.")
            cache.regeneratePricesFile(tdb, tdenv)
        
        tdenv.NOTE("Import completed.")
        
        # TD doesn't need to do anything, tell it to just quit.
        return False
