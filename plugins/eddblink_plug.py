import cache
import csv
import csvexport
import datetime
import json
import os
import platform
import plugins
import sqlite3
import time
import tradedb
import tradeenv
import transfers
import misc.progress as pbar

from urllib import request
from calendar import timegm
from pathlib import Path
from plugins import PluginException
from importlib import reload

# Constants

BASE_URL = "http://elite.ripz.org/files/"
FALLBACK_URL = "https://eddb.io/archive/v5/"
SHIPS_URL = "https://raw.githubusercontent.com/EDCD/coriolis-data/master/dist/index.json"
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
        'progbar':      "Use '[=   ]' progress instead of '(125/500) 25%'",
        'solo':         "Don't download crowd-sourced market data. (Implies '-O skipvend', supercedes '-O all', '-O clean', '-O listings'.)"
    }

    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)

        self.dataPath = tdb.dataPath / Path("eddb")
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
    
    def downloadFile(self, urlTail, path):
        """
        Fetch the latest dumpfile from the website if newer than local copy.
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.DEBUG0("Checking for update to '{}'.", path)
        if urlTail == SHIPS_URL:
            url = SHIPS_URL
        else:
            if not self.getOption('fallback'):
                try:
                    url = BASE_URL + urlTail
                    response = request.urlopen(url)
                except:
                    # If Tromador's server fails for whatever reason,
                    # fallback to download direct from EDDB.io
                    self.options["fallback"] = True
            if self.getOption('fallback'):
                # EDDB.io doesn't have live listings.
                if urlTail == LIVE_LISTINGS:
                    return False

                url = FALLBACK_URL + urlTail
                response = request.urlopen(url)
        
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
            dumpDT = datetime.datetime(int(dDL[3]), Months[dDL[2]], int(dDL[1]),\
               hour=int(dTL[0]), minute=int(dTL[1]), second=int(dTL[2]),\
               tzinfo=datetime.timezone.utc)
            dumpModded = timegm(dumpDT.timetuple())

        if Path.exists(self.dataPath / path):
            localModded = (self.dataPath / path).stat().st_mtime
            if localModded >= dumpModded and url != SHIPS_URL:
                tdenv.DEBUG0("'{}': Dump is not more recent than Local.", path)
                return False
        
        tdenv.NOTE("Downloading file '{}'.", path)
        transfers.download( self.tdenv, url, self.dataPath / path, )
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
            name = upgrade['name'] if upgrade['name'] else upgrade['ed_symbol'].replace('_',' ')
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
            
            #Change the names to match how they appear in Stations.jsonl
            if name == "Eagle":
                name = "Eagle Mk. II"
            if name == "Sidewinder":
                name = "Sidewinder Mk. I"
            if name == "Viper":
                name = "Viper Mk. III"

            # Make sure all the 'Mark N' ship names abbreviate 'Mark' the same.
            # Fix capitalization.
            name = name.replace('MK', 'Mk').replace('mk','Mk').replace('mK','Mk')
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

        progress = 0
        total = 1
        def blocks(f, size = 65536):
            while True:
                b = f.read(size)
                if not b: break
                yield b

        with open(str(self.dataPath / self.systemsPath), "r",encoding = "utf-8",errors = 'ignore') as f:
            total += (sum(bl.count("\n") for bl in blocks(f)))

        with open(str(self.dataPath / self.systemsPath), "rU") as fh:
            if self.getOption("progbar"):
                prog = pbar.Progress(total, 50)
            for line in fh:
                if self.getOption("progbar"):
                    prog.increment(1, postfix=lambda value, goal: " " + str(round(value / total * 100)) + "%")
                else:
                    progress += 1
                    print("\rProgress: (" + str(progress) + "/" + str(total) + ") " + str(round(progress / total * 100, 2)) + "%\t\t", end = "\r")        
                system = json.loads(line)
                system_id = system['id']
                name = system['name']
                pos_x = system['x']
                pos_y = system['y']
                pos_z = system['z']
                modified = datetime.datetime.utcfromtimestamp(system['updated_at']).strftime('%Y-%m-%d %H:%M:%S')
                
                result = self.execute("SELECT modified FROM System WHERE system_id = ?", (system_id,)).fetchone()
                if result:
                    updated = timegm(datetime.datetime.strptime(result[0],'%Y-%m-%d %H:%M:%S').timetuple())
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
            if self.getOption("progbar"):
                while prog.value < prog.maxValue:
                    prog.increment(1, postfix=lambda value, goal: " " + str(round(value / total * 100)) + "%")
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


        progress = 0
        total = 1
        def blocks(f, size = 65536):
            while True:
                b = f.read(size)
                if not b: break
                yield b

        with open(str(self.dataPath / self.stationsPath), "r",encoding = "utf-8",errors = 'ignore') as f:
            total += (sum(bl.count("\n") for bl in blocks(f)))
        
        with open(str(self.dataPath / self.stationsPath), "rU") as fh:
            if self.getOption("progbar"):
                prog = pbar.Progress(total, 50)
            for line in fh:
                if self.getOption("progbar"):
                    prog.increment(1, postfix=lambda value, goal: " " + str(round(value / total * 100)) + "%")
                else:
                    progress += 1
                    print("\rProgress: (" + str(progress) + "/" + str(total) + ") " + str(round(progress / total * 100, 2)) + "%\t\t", end = "\r")        
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
                    updated = timegm(datetime.datetime.strptime(result[0],'%Y-%m-%d %H:%M:%S').timetuple())
                    if station['updated_at'] > updated:
                        tdenv.DEBUG0("{}/{} has been updated: {} vs {}", 
                                    system ,name, modified, result[0])
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
                    tdenv.DEBUG0("{}/{} has been added:", system ,name)
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
                                (station_id,name,system_id,ls_from_star,
                                 blackmarket,max_pad_size,market,shipyard,
                                 modified,outfitting,rearm,refuel,
                                 repair,planetary,type_id))
                    self.updated['Station'] = True
                
                #Import shipyards into ShipVendors if shipvend is set.
                if station['has_shipyard'] and self.getOption('shipvend'):
                    if not station['shipyard_updated_at']:
                        station['shipyard_updated_at'] = station['updated_at']
                    modified = datetime.datetime.utcfromtimestamp(station['shipyard_updated_at']).strftime('%Y-%m-%d %H:%M:%S')
                    result = self.execute("SELECT modified FROM ShipVendor WHERE station_id = ?", (station_id,)).fetchone()
                    if result:
                        updated = timegm(datetime.datetime.strptime(result[0],'%Y-%m-%d %H:%M:%S').timetuple())
                    else:
                        updated = 0
                    if station['shipyard_updated_at'] > updated:
                        self.execute("DELETE FROM ShipVendor WHERE station_id = ?", (station_id,))
                        tdenv.DEBUG1("{}/{} has shipyard, updating ships sold.", system, name)
                        for ship in station['selling_ships']:
                            # Make sure all the 'Mark N' ship names abbreviate 'Mark' as '<Name> Mk. <Number>'.
                            # Fix capitalization.
                            ship = ship.replace('MK', 'Mk').replace('mk','Mk').replace('mK','Mk')
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
                            self.execute("""INSERT INTO ShipVendor
                                        ( ship_id,station_id,modified ) VALUES
                                        ( (SELECT Ship.ship_id FROM Ship WHERE Ship.name = ?), ?, ? ) """,
                                        (ship,
                                         station_id,
                                         modified))
                        self.updated['ShipVendor'] = True
                        
                #Import Outfitters into UpgradeVendors if upvend is set.
                if station['has_outfitting'] and self.getOption('upvend'):
                    if not station['outfitting_updated_at']:
                        station['outfitting_updated_at'] = station['updated_at']
                    modified = datetime.datetime.utcfromtimestamp(station['outfitting_updated_at']).strftime('%Y-%m-%d %H:%M:%S')
                    result = self.execute("SELECT modified FROM UpgradeVendor WHERE station_id = ?", (station_id,)).fetchone()
                    if result:
                        updated = timegm(datetime.datetime.strptime(result[0],'%Y-%m-%d %H:%M:%S').timetuple())
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
                            self.execute("""INSERT INTO UpgradeVendor
                                        ( upgrade_id,station_id,cost,modified ) VALUES
                                        ( ?, ?, (SELECT Upgrade.cost FROM Upgrade WHERE Upgrade.upgrade_id = ?), ? ) """,
                                        (upgrade,
                                         station_id,
                                         upgrade,
                                         modified))
                        self.updated['UpgradeVendor'] = True
            if self.getOption("progbar"):
                while prog.value < prog.maxValue:
                    prog.increment(1, postfix=lambda value, goal: " " + str(round(value / total * 100)) + "%")
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
            # EDDB still hasn't added these Salvage Commodities, so we'll add them ourselves.
            if "Antique Jewellery" not in fh:
                commodities.append({"id":1001,"name":"Antique Jewellery","category_id":16,"average_price":142465,"is_rare":0,"max_buy_price":None,"max_sell_price":None,"min_buy_price":None,"min_sell_price":None,"buy_price_lower_average":0,"sell_price_upper_average":0,"is_non_marketable":0,"ed_id":128672159,"category":{"id":16,"name":"Salvage"}})
            if "Gene Bank" not in fh:
                commodities.append({"id":1002,"name":"Gene Bank","category_id":16,"average_price":11100,"is_rare":0,"max_buy_price":None,"max_sell_price":None,"min_buy_price":None,"min_sell_price":None,"buy_price_lower_average":0,"sell_price_upper_average":0,"is_non_marketable":0,"ed_id":128672162,"category":{"id":16,"name":"Salvage"}})
            if "Time Capsule" not in fh:
                commodities.append({"id":1003,"name":"Time Capsule","category_id":16,"average_price":4187,"is_rare":0,"max_buy_price":None,"max_sell_price":None,"min_buy_price":None,"min_sell_price":None,"buy_price_lower_average":0,"sell_price_upper_average":0,"is_non_marketable":0,"ed_id":128672163,"category":{"id":16,"name":"Salvage"}})

        for commodity in iter(commodities):
            # Get the categories from the json and place them into the Category table.
            category_id = commodity['category']['id']
            name = commodity['category']['name']
            
            tdenv.DEBUG1("Updating: {}, {}", category_id, name)
            try:
                self.execute("""INSERT INTO Category
                            ( category_id, name ) VALUES
                            ( ?, ? ) """,
                            (category_id, name))
            except sqlite3.IntegrityError:
                try:
                    self.execute("""UPDATE Category
                                SET name = ?
                                WHERE category_id = ?""", 
                                (name, category_id))

                except sqlite3.IntegrityError:
                    tdenv.DEBUG0("Unable to insert or update: {}, {}", category_id, name)
            
            # Only put regular items here, rare items can't be dealt with.
            if not commodity['is_rare']:
                item_id = commodity['id']
                name = commodity['name']
                category_id = commodity['category_id']
                avg_price = commodity['average_price']
                fdev_id = commodity['ed_id']
                # "ui_order" doesn't have an equivalent field in the json.
                
                tdenv.DEBUG1("Updating: {}, {}, {}, {}, {}", item_id,name,category_id,avg_price,fdev_id)
                try:
                    self.execute("""INSERT INTO Item
                                ( item_id,name,category_id,avg_price,fdev_id ) VALUES
                                ( ?, ?, ?, ?, ? )""",
                                (item_id,name,category_id,avg_price,fdev_id))
                except sqlite3.IntegrityError:
                    try:
                        self.execute("""UPDATE Item
                                    SET name = ?,category_id = ?,avg_price = ?,fdev_id = ?
                                    WHERE item_id = ?""", 
                                    (name,category_id,avg_price,fdev_id,
                                     item_id))
                    except sqlite3.IntegrityError:
                        tdenv.DEBUG0("Unable to insert or update: {}, {}, {}, {}, {}", item_id,name,category_id,avg_price,fdev_id)
                        
        # The items aren't in the same order in the json as they are in the game's UI.
        # This creates a temporary object that has all the items sorted first
        # by category and second by name, as in the UI, which will then be used to
        # update the entries in the database with the correct "ui_order" value.
        temp = self.execute("""SELECT
                        name, category_id, item_id
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
                ui_order+= 1
            self.execute("""UPDATE Item
                        set ui_order = ?
                        WHERE item_id = ?""",
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
        
        progress = 0
        total = 1
        def blocks(f, size = 65536):
            while True:
                b = f.read(size)
                if not b: break
                yield b

        with open(str(self.dataPath / listings_file), "r",encoding = "utf-8",errors = 'ignore') as f:
            total += (sum(bl.count("\n") for bl in blocks(f)))

        with open(str(self.dataPath / listings_file), "rU") as fh:
            if self.getOption("progbar"):
                prog = pbar.Progress(total, 50)
            listings = csv.DictReader(fh)
            for listing in listings:
                if self.getOption("progbar"):
                    prog.increment(1, postfix=lambda value, goal: " " + str(round(value / total * 100)) + "%")
                else:
                    progress += 1
                    print("\rProgress: (" + str(progress) + "/" + str(total) + ") " + str(round(progress / total * 100, 2)) + "%\t\t", end = "\r")        
                station_id = int(listing['station_id'])
                item_id = int(listing['commodity_id'])
                modified = datetime.datetime.utcfromtimestamp(int(listing['collected_at'])).strftime('%Y-%m-%d %H:%M:%S')
                demand_price = int(listing['sell_price'])
                demand_units = int(listing['demand'])
                demand_level = int(listing['demand_bracket']) if listing['demand_bracket'] != '' else -1
                supply_price = int(listing['buy_price'])
                supply_units = int(listing['supply'])
                supply_level = int(listing['supply_bracket']) if listing['supply_bracket'] != '' else -1
                #from_live = 0 if listings_file == LISTINGS else 1
                from_live = 0
                
                result = self.execute("SELECT modified FROM StationItem WHERE station_id = ? AND item_id = ?", (station_id, item_id)).fetchone()
                if result:
                    updated = timegm(datetime.datetime.strptime(result[0],'%Y-%m-%d %H:%M:%S').timetuple())
                    # When the dump file data matches the database, update to make from_live == 0.
                    if int(listing['collected_at']) == updated and listings_file == LISTINGS:
                        self.execute("""UPDATE StationItem
                                    SET from_live = 0
                                    WHERE station_id = ? AND item_id = ?""",
                                    (station_id, item_id))
                    if int(listing['collected_at']) > updated:
                        tdenv.DEBUG1("Updating:{}, {}, {}, {}, {}, {}, {}, {}, {}",
                             station_id, item_id, modified,
                             demand_price, demand_units, demand_level,
                             supply_price, supply_units, supply_level)
                        try:
                            self.execute("""UPDATE StationItem
                                    SET modified = ?,
                                     demand_price = ?, demand_units = ?, demand_level = ?,
                                     supply_price = ?, supply_units = ?, supply_level = ?,
                                     from_live = ?
                                    WHERE station_id = ? AND item_id = ?""",
                                    (modified, demand_price, demand_units, demand_level, supply_price, supply_units, supply_level, from_live,
                                     station_id, item_id))
                        except sqlite3.IntegrityError:
                            tdenv.DEBUG1("Error on update.")
                else:
                    tdenv.DEBUG1("Inserting:{}, {}, {}, {}, {}, {}, {}, {}, {}",
                             station_id, item_id, modified,
                             demand_price, demand_units, demand_level,
                             supply_price, supply_units, supply_level)
                    try:
                        self.execute("""INSERT INTO StationItem
                                (station_id, item_id, modified,
                                 demand_price, demand_units, demand_level,
                                 supply_price, supply_units, supply_level, from_live)
                                VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ? )""",
                                (station_id, item_id, modified,
                                 demand_price, demand_units, demand_level,
                                 supply_price, supply_units, supply_level, from_live))
                    except sqlite3.IntegrityError:
                        tdenv.DEBUG1("Error on insert.")
            if self.getOption("progbar"):
                while prog.value < prog.maxValue:
                    prog.increment(1, postfix=lambda value, goal: " " + str(round(value / total * 100)) + "%")
                prog.clear()
        
        self.updated['Listings'] = True
        tdenv.NOTE("Finished processing market data. End time = {}", datetime.datetime.now())

    def run(self):
        tdb, tdenv = self.tdb, self.tdenv

        #Create the /eddb folder for downloading the source files if it doesn't exist.
        try:
           Path(str(self.dataPath)).mkdir()
        except FileExistsError:
            pass
        
        # Run 'listings' by default:
        # If no options, or if only 'progbar', 'force', 'skipvend', and/or 'fallback', 
        # have been passed, enable 'listings'.
        default = True
        for option in self.options:
            if not ((option == 'force') or (option == 'fallback') or (option == 'skipvend') or (option == 'progbar')):
                default = False
        if default:
            self.options["listings"] = True
        
        # We can probably safely assume that the plugin has never been run if
        # the prices file doesn't exist, since the plugin always generates it.
        firstRun = not (tdb.dataPath / Path("TradeDangerous.prices")).exists()

        if firstRun:
            self.options["clean"] = True
        
        try:
            self.execute("ALTER TABLE Station ADD type_id INTEGER DEFAULT 0 NOT NULL")
        except sqlite3.OperationalError:
            pass
        
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
        
        #Select which options will be updated
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

        if self.getOption("ship"):
            if self.downloadFile(SHIPS_URL, self.shipsPath) or self.getOption("force"):
                self.importShips()

        if self.getOption("system"):
            if self.downloadFile(SYSTEMS, self.systemsPath) or self.getOption("force"):
                self.importSystems()

        if self.getOption("station"):
            if self.downloadFile(STATIONS, self.stationsPath) or self.getOption("force"):
                self.importStations()

        if self.getOption("item"):
            if self.downloadFile(COMMODITIES, self.commoditiesPath) or self.getOption("force"):
                self.importCommodities()
        
        success = False
        while not success:
            try:
                tdb.getDB().commit()
                success = True
            except sqlite3.OperationalError:
                print("(commit) Database is locked, waiting for access.", end = "\r")
                time.sleep(1)
        
        #Remake the .csv files with the updated info.
        self.regenerate()

        if self.getOption("listings"):
            if self.downloadFile(LISTINGS, self.listingsPath) or self.getOption("force"):
                self.importListings(self.listingsPath)
            if self.downloadFile(LIVE_LISTINGS, self.liveListingsPath) or self.getOption("force"):
                self.importListings(self.liveListingsPath)

        success = False
        while not success:
            try:
                tdb.getDB().commit()
                success = True
            except sqlite3.OperationalError:
                print("(commit) Database is locked, waiting for access.", end = "\r")
                time.sleep(1)
        
        tdb.close()
        
        if self.updated['Listings']:
            tdenv.NOTE("Regenerating .prices file.")
            cache.regeneratePricesFile(tdb, tdenv)

        tdenv.NOTE("Import completed.")

        # TD doesn't need to do anything, tell it to just quit.
        return False
