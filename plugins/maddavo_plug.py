import cache
import corrections
import csvexport
import os
import pathlib
import platform
import plugins
import re
import time
import tradedb
import tradeenv
import transfers

from plugins import PluginException

# Constants

BASE_URL = "http://www.davek.com.au/td/"
CORRECTIONS_URL = BASE_URL + "correctionsfile.asp"
SYSTEMS_URL = BASE_URL + "System.csv"
STATIONS_URL = BASE_URL + "station.asp"
SHIPVENDOR_URL = BASE_URL + "shipvendor.asp"

class DecodingError(PluginException):
    pass


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads data from maddavo's site.
    """

    stampFile = "maddavo.stamp"
    dateRe = re.compile(r"(\d\d\d\d-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)")

    pluginOptions = {
        'csvs':         "Merge Corrections, System, Station and ShipVendor "
                        "data into the local db.",
        'corrections':  "Merge Corrections data into local db.",
        'systems':      "Merge System data into local db.",
        'stations':     "Merge Station data into local db.",
        'shipvendors':  "Merge ShipVendor data into local db.",
        'exportcsv':    "Regenerate System and Station .csv files after "
                        "merging System/Station data.",
        'csvonly':      "Stop after csv work, don't import prices",
        'skipdl':       "Skip doing any downloads.",
        'force':        "Process prices even if timestamps suggest "
                        "there is no new data.",
        'use3h':        "Force download of the 3-hours .prices file.",
        'use2d':        "Force download of the 2-days .prices file.",
        'usefull':      "Force download of the full .prices file.",
    }


    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)

        self.filename = self.defaultImportFile
        stampFilePath = pathlib.Path(ImportPlugin.stampFile)
        self.stampPath = tdb.dataPath / stampFilePath
        self.modSystems = 0
        self.modStations = 0


    def load_timestamp(self):
        """
        Read the date from the timestamp file.
        Returns a zero date if the file doesn't exist or
        doesn't contain a date.
        """

        prevImportDate = None
        lastRunDays = float("inf")
        if self.stampPath.is_file():
            try:
                fh = self.stampPath.open('rU')
                line = fh.readline().split('\n')
                if line and line[0]:
                    if ImportPlugin.dateRe.match(line[0]):
                        prevImportDate = line[0]
                line = fh.readline().split('\n')
                if line and line[0]:
                    lastRunAge = time.time() - float(line[0])
                    lastRunDays = lastRunAge / (24 * 60 * 60)
            except FileNotFoundError:
                pass

        if not prevImportDate:
            prevImportDate = "0000-00-00 00:00:00"
        return prevImportDate, lastRunDays


    def save_timestamp(self, newestDate, startTime):
        """
        Save a date to the timestamp file.
        """

        with self.stampPath.open('w') as fh:
            print(newestDate, file=fh)
            print(startTime, file=fh)


    def check_shebang(self, line, checkAge):
        m = re.match(
            r'^#!\s*trade.py\s*import\s*.*\s*--timestamp\s*"([^"]+)"',
            line
        )
        if not m:
            raise PluginException(
                "Data is not Maddavo's prices list format: " + line
            )
        self.importDate = m.group(1)
        if checkAge and not self.getOption("force"):
            if self.importDate <= self.prevImportDate:
                raise SystemExit(
                    "Local data is already current [{}]."
                    .format(self.importDate)
                )
            if self.tdenv.detail:
                print("New timestamp: {}, Old timestamp: {}".format(
                    self.importDate,
                    self.prevImportDate
                ))


    def csv_stream_rows(self, url, tableName):
        """
        Iterate rows from a CSV resource for a given table.
        """
        if self.getOption(tableName.lower()):
            self.tdenv.NOTE("Importing {}", tableName)
            for _, values in transfers.CSVStream(url, tdenv=self.tdenv):
                yield values


    def import_corrections(self):
        """
        Fetch and import deletions/renames from Corrections.csv
        """
    
        tdb, tdenv = self.tdb, self.tdenv
        sysLookup = tdb.systemByName.get
        db = tdb.getDB()
        deletes, updates = 0, 0

        # Build a name lookup table from a given ID index.
        def make_index(table):
            return { i.dbname: i for i in table.values() }

        # For each ID table that we accept corrections for, build
        # a name-based lookup index.
        basicTypes = {
            'Category': ('category_id', make_index(tdb.categoryByID)),
            'Item': ('item_id', make_index(tdb.itemByID)),
            'Rare': ('rare_id', make_index(tdb.rareItemByID)),
            'Ship': ('ship_id', make_index(tdb.shipByID)),
            'System': ('system_id', make_index(tdb.systemByID)),
            'Station': ('station_id', {
                stn.name().upper(): stn for stn in tdb.stationByID.values()
            }),
        }

        FIXING, DELETING, DISCARDING = 'FIXING', 'DELETING', 'DISCARDING'

        stream = self.csv_stream_rows(CORRECTIONS_URL, "Corrections")
        for src, oldName, newName in stream:
            action = FIXING if (newName != 'DELETED') else DELETING

            try:
                (idColumn, index) = basicTypes[src]
            except KeyError:
                tdenv.NOTE("Unsupported correction type {} ignored", src)
                continue

            item = index.get(oldName, None)
            if not item:
                tdenv.DEBUG1(
                    "Correction for {} not needed, skipping.", oldName
                )
                continue

            if src == 'Station':
                if action is FIXING:
                    newItemName = "/".join(
                        [item.system.dbname, newName]
                    ).upper()
            else:
                if action is FIXING:
                    newItemName = newName

            if action is FIXING:
                newItem = index.get(newItemName, None)
                if newItem and newItem is not item:
                    tdenv.DEBUG1(
                        "{} exists so {} can be deleted.",
                        newItemName, oldName,
                    )
                    action = DISCARDING

            if action is FIXING:
                tdenv.DEBUG0("{} {} {} -> {}", action, src, oldName, newName)
                stmt = "UPDATE {} SET name = ? WHERE {} = ?".format(
                    src, idColumn
                )
                binds = [newName, item.ID]
                updates += 1
            else:
                tdenv.DEBUG0("{} {} {}", action, src, oldName)
                stmt = "DELETE FROM {} WHERE {} = ?".format(src, idColumn)
                binds = [item.ID]
                deletes += 1

            if tdenv.debug:
                tdenv.DEBUG1("{} [{}]", stmt, binds)
            db.execute(stmt, binds)

        if updates == 0 and deletes == 0:
            tdenv.DEBUG0("No corrections applied.")
            return

        tdenv.NOTE("{} updates, {} deletions", updates, deletes)
        db.commit()
        db.execute("VACUUM")
        if not self.getOption("exportcsv"):
            tdenv.WARN(
                "Corrections imported without --opt=exportcsv. "
                "You may want to manually export data later on."
            )

        # We need to reload stuff.
        tdb.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)


    def csv_system_rows(self, url, tableName):
        """
        Iterate systems from a CSV resource.
        """
        tdb, tdenv = self.tdb, self.tdenv
        sysLookup = tdb.systemByName.get
        sysAdjust = corrections.systems.get
        DELETED = corrections.DELETED

        stream = self.csv_stream_rows(url, tableName)
        for values in stream:
            srcName = values[0].upper()
            sysName = sysAdjust(srcName, srcName)
            if sysName == DELETED:
                tdenv.DEBUG0("Ignoring deleted system {}", srcName)
                continue
            system = sysLookup(sysName, None)
            yield sysName, system, values


    def import_systems(self):
        """
        Fetch and import data from Systems.csv
        """

        tdb, tdenv = self.tdb, self.tdenv

        stream = self.csv_system_rows(SYSTEMS_URL, "Systems")
        for sysName, system, values in stream:
            added = values[4]
            modified = values[5]
            if added.startswith("DEL") or modified.startswith("DEL"):
                if system:
                    tdb.removeLocalSystem(
                        system
                    )
                self.modSystems += 1
                continue

            x, y, z = float(values[1]), float(values[2]), float(values[3])
            if not system:
                tdb.addLocalSystem(
                    sysName, x, y, z, added, modified,
                    commit=False,
                )
                self.modSystems += 1
            elif system.posX != x or system.posY != y or system.posZ != z:
                print("{} position change: {}v{}, {}v{}, {}v{}".format(
                    sysName, system.posX, x, system.posY, y, system.posZ, z
                ))
                tdb.updateLocalSystem(
                    system, sysName, x, y, z, added, modified,
                    commit=False,
                )
                self.modSystems += 1

        if self.modSystems:
            tdb.getDB().commit()


    def csv_station_rows(self, url, tableName):
        """
        Fetch rows from a CSV resource that start with a system and a station,
        applying corrections.
        """

        tdb, tdenv = self.tdb, self.tdenv
        sysAdjust = corrections.systems.get
        stnAdjust = corrections.stations.get
        DELETED = corrections.DELETED

        stream = self.csv_system_rows(url, tableName)
        for sysName, system, values in stream:
            if not system:
                tdenv.NOTE(
                    "Unrecognized system for station {}/{}",
                    sysName, stnName,
                )
                continue
            stnName = values[1]
            stnName = stnAdjust('/'.join([sysName, stnName.upper()]), stnName)
            if stnName == DELETED:
                tdenv.DEBUG0(
                    "Ignoring deleted station {}/{}",
                    values[0], values[1],
                )
                continue
            station = system.getStation(stnName)
            yield system, stnName, station, values


    def import_stations(self):
        """
        Fetch and import data from Stations.csv.
        """

        tdb, tdenv = self.tdb, self.tdenv

        stream = self.csv_station_rows(STATIONS_URL, "Stations")
        for system, stnName, station, values in stream:
            try:
                lsFromStar = float(values[2])
            except ValueError:
                tdenv.WARN(
                    "Invalid, non-numeric, lsFromStar value ('{}') for {}/{}",
                    values[2], system.name(), stnName
                )
                continue
            if int(lsFromStar) != lsFromStar:
                tdenv.NOTE(
                    "Discarding floating-point part of {} for {}/{}",
                    lsFromStar, system.name(), stnName
                )
                lsFromStar = int(lsFromStar)
            modified = values[7] if len(values) > 7 else 'now'
            if lsFromStar < 0 or modified.startswith("DEL"):
                if station:
                    tdb.removeLocalStation(station, commit=False)
                    self.modStations += 1
                continue
            blackMarket = values[3]
            maxPadSize = values[4]
            market = values[5] if len(values) > 5 else '?'
            shipyard = values[6] if len(values) > 6 else '?'
            outfitting = values[8] if len(values) > 8 else '?'
            rearm = values[9] if len(values) > 9 else '?'
            refuel = values[10] if len(values) > 10 else '?'
            repair = values[11] if len(values) > 11 else '?'
            if station:
                if tdb.updateLocalStation(
                        station,
                        name=stnName,
                        lsFromStar=lsFromStar,
                        market=market,
                        blackMarket=blackMarket,
                        shipyard=shipyard,
                        maxPadSize=maxPadSize,
                        outfitting=outfitting,
                        rearm=rearm,
                        refuel=refuel,
                        repair=repair,
                        modified=modified,
                        commit=False,
                        ):
                    self.modStations += 1
            else:
                tdb.addLocalStation(
                    system=system,
                    name=stnName,
                    lsFromStar=lsFromStar,
                    market=market,
                    blackMarket=blackMarket,
                    shipyard=shipyard,
                    maxPadSize=maxPadSize,
                    outfitting=outfitting,
                    rearm=rearm,
                    refuel=refuel,
                    repair=repair,
                    modified=modified,
                    commit=False,
                )
                self.modStations += 1

        if self.modStations:
            tdenv.DEBUG0("commit")
            tdb.getDB().commit()


    def import_shipvendors(self):
        """
        Fetch dave's ShipVendor.csv and import it.
        """

        tdb, tdenv = self.tdb, self.tdenv
        db = tdb.getDB()
        ships = { ship.dbname.upper(): ship for ship in tdb.shipByID.values() }
        lastFail = None

        # Index ship locations.
        stmt = """
            SELECT  ship_id, station_id
              FROM  ShipVendor
        """
        shipLocs = set(
            (shipID, stnID) for shipID, stnID in db.execute(stmt)
        )
        newShips = {}
        delShips = set()

        stream = self.csv_station_rows(SHIPVENDOR_URL, "ShipVendors")
        for system, stnName, station, values in stream:
            if not station:
                if not tdenv.quiet:
                    name = "{}/{}".format(system.name(), stnName)
                    if name != lastFail:
                        tdenv.NOTE(
                            "Ignoring unrecognized station: {}/{}",
                            system.name(), stnName,
                        )
                        lastFail = name
                continue
            shipName = values[2]
            modified = values[3] if len(values) > 3 else 'now'
            isDelete = modified.startswith("DEL")
            ship = ships.get(shipName.upper(), None)
            if not ship:
                if not isDelete:
                    tdenv.NOTE(
                        "Ignoring unrecognized ship {} at {}",
                        shipName, station.name()
                    )
                continue
            locKey = (ship.ID, station.ID)
            if locKey in shipLocs:
                if isDelete and not locKey in delShips:
                    try:
                        newShips.remove(locKey)
                    except KeyError:
                        pass
                    delShips.add(locKey)
                    tdenv.NOTE(
                        "Removing {} from {}",
                        ship.name(), station.name()
                    )
                continue
            if locKey in newShips:
                continue
            try:
                delShips.remove(locKey)
            except KeyError:
                pass
            tdenv.NOTE(
                "Adding {} at {}", ship.name(), station.name(),
            )
            newShips[locKey] = (ship.ID, station.ID, modified)
        if newShips:
            stmt = """
                REPLACE INTO ShipVendor
                (ship_id, station_id, modified)
                VALUES
                (?, ?, DATETIME(?))
            """
            db.executemany(stmt, newShips.values())
        if delShips:
            db.executemany("""
                DELETE FROM ShipVendor WHERE ship_id = ? and station_id = ?
            """, delShips)
        if newShips or delShips:
            db.commit()


    def refresh_csv(self):
        if not self.getOption("exportcsv"):
            return

        for table in [
            "Category", "Item",
            "System", "Station",
            "Ship", "ShipVendor",
            "RareItem"
        ]:
            _, path = csvexport.exportTableToFile(
                self.tdb, self.tdenv, table
            )
            self.tdenv.NOTE("{} re-exported.", path)

    def download_prices(self, lastRunDays):
        """ Figure out which file to download and fetch it. """

        # Argument checking
        use3h = 1 if self.getOption("use3h") else 0
        use2d = 1 if self.getOption("use2d") else 0
        usefull = 1 if self.getOption("usefull") else 0
        if use3h + use2d + usefull > 1:
            raise PluginException(
                "Only one of use3h/use2d/usefull can be used at once."
            )
        if self.getOption("skipdl"):
            if (use3h or use2d or usefull):
                raise PluginException(
                    "use3h/use2d/usefull has no effect with --opt=skipdl"
                )
            return

        # Overrides
        if use3h:
            lastRunDays = 0.01
        elif use2d:
            lastRunDays = 1.0
        elif usefull:
            lastRunDays = 3.0

        # Use age/options to determine which file
        if lastRunDays < 3 / 24:
            priceFile = "prices-3h.asp"
        elif lastRunDays < 1.9:
            priceFile = "prices-2d.asp"
        else:
            priceFile = "prices.asp"

        # Fetch!
        transfers.download(
            self.tdenv,
            BASE_URL + priceFile,
            self.filename,
            shebang=lambda line: self.check_shebang(line, True),
        )

    def import_prices(self):
        """ Download and import data price data """

        tdb, tdenv = self.tdb, self.tdenv

        # It takes a while to download these files, so we want
        # to record the start time before we download. What we
        # care about is when we downloaded relative to when the
        # files were previously generated.
        startTime = time.time()

        prevImportDate, lastRunDays = self.load_timestamp()
        self.prevImportDate = prevImportDate

        self.download_prices(lastRunDays)
        if tdenv.download:
            return

        # Scan the file for the latest data.
        firstDate = None
        newestDate = prevImportDate
        numNewLines = 0
        minLen = len(prevImportDate) + 10
        dateRe = ImportPlugin.dateRe
        lastStn = None
        updatedStations = set()
        tdenv.DEBUG0("Reading prices data")
        with open(self.filename, "rUb") as fh:
            # skip the shebang.
            firstLine = fh.readline().decode(encoding="utf-8")
            self.check_shebang(firstLine, False)
            importDate = self.importDate

            lineNo = 0
            while True:
                lineNo += 1
                try:
                    line = next(fh)
                except StopIteration:
                    break
                try:
                    line = line.decode(encoding="utf-8")
                except UnicodeDecodeError as e:
                    try:
                        line = line.decode(encoding="latin1")
                        line = line.encode("utf-8")
                        line = line.decode()
                    except UnicodeDecodeError:
                        raise DecodingError(
                            "{} line {}: "
                            "Invalid (unrecognized, non-utf8) character "
                            "sequence: {}\n{}".format(
                                self.filename, lineNo, str(e), line,
                            )
                        ) from None
                    raise DecodingError(
                        "{} line {}: "
                        "Invalid (latin1, non-utf8) character "
                        "sequence:\n{}".format(
                            self.filename, lineNo, line,
                        )
                    )
                if line.startswith('@'):
                    lastStn = line[2:line.find('#')].strip()
                    continue
                if not line.startswith(' ') or len(line) < minLen:
                    continue
                m = dateRe.search(line)
                if not m:
                    continue
                date = m.group(1) + ' ' + m.group(2)
                if not firstDate or date < firstDate:
                    firstDate = date
                if date > prevImportDate:
                    updatedStations.add(lastStn)
                    numNewLines += 1
                    if date > newestDate:
                        newestDate = date
                        if date > importDate:
                            raise PluginException(
                                "Station {} has suspicious date: {} "
                                "(newer than the import?)"
                                .format(lastStn, date)
                            )

        if numNewLines == 0:
            tdenv.NOTE("No new price entries found.")

        forceParse = self.getOption("force") or self.getOption("skipdl")
        if numNewLines > 0 or forceParse:
            if tdenv.detail:
                print(
                    "Date of last import   : {}\n"
                    "Timestamp of import   : {}\n"
                    "Oldest update in file : {}\n"
                    "Newest update in file : {}\n"
                    "Number of new entries : {}\n"
                    .format(
                        prevImportDate,
                        importDate,
                        firstDate,
                        newestDate,
                        numNewLines,
                    ))

            numStationsUpdated = len(updatedStations)
            if not tdenv.quiet and numStationsUpdated:
                if len(updatedStations) > 12 and tdenv.detail < 2:
                    updatedStations = list(updatedStations)[:10] + ["..."]
                tdenv.NOTE(
                    "{} {} updated:\n{}",
                    numStationsUpdated,
                    "stations" if numStationsUpdated > 1 else "station",
                    ', '.join(updatedStations)
                )

            cache.importDataFromFile(
                tdb,
                tdenv,
                pathlib.Path(self.filename),
            )

        self.save_timestamp(importDate, startTime)

    def run(self):
        tdb, tdenv = self.tdb, self.tdenv

        tdenv.ignoreUnknown = True

        if self.getOption("csvs"):
            self.options["corrections"] = True
            self.options["systems"] = True
            self.options["stations"] = True
            self.options["shipvendors"] = True
            self.options["exportcsv"] = True

        # Ensure the cache is built and reloaded.
        tdb.reloadCache()
        tdb.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)

        self.import_corrections()
        self.import_systems()
        self.import_stations()
        self.import_shipvendors()

        # Let the system decide if it needs to reload-cache
        tdb.close()

        self.refresh_csv()

        if not self.getOption("csvonly"):
            self.import_prices()

        tdenv.NOTE("Import completed.")

        # We did all the work
        return False
