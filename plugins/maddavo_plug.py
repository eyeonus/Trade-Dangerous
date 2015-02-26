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

# Check for TKInter support
hasTkInter = False
if 'NOTK' not in os.environ and platform.system() != 'Darwin':  # focus bug
    try:
        import tkinter
        import tkinter.messagebox as mbox
        hasTkInter = True
    except ImportError:
        pass


# Constants

BASE_URL = "http://www.davek.com.au/td/"
SYSTEMS_URL = BASE_URL + "System.csv"
STATIONS_URL = BASE_URL + "station.asp"


class DecodingError(PluginException):
    pass


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads data from maddavo's site.
    """

    stampFile = "maddavo.stamp"
    dateRe = re.compile(r"(\d\d\d\d-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)")

    pluginOptions = {
        'systems':      "Merge maddavo's System data into local db,",
        'stations':     "Merge maddavo's Station data into local db,",
        'exportcsv':    "Regenerate System and Station .csv files after "
                        "merging System/Station data.",
        'skipdl':       "Skip doing any downloads.",
        'force':        "Process prices even if timestamps suggest "
                        "there is no new data.",
        'use3h':        "Force download of the 3-hours .prices file",
        'use2d':        "Force download of the 2-days .prices file",
        'usefull':      "Force download of the full .prices file",
        'syscsv':       "DEPRECATED - see --opt=systems",
        'stncsv':       "DEPRECATED - see --opt=stations",
    }


    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)

        self.filename = self.defaultImportFile
        stampFilePath = pathlib.Path(ImportPlugin.stampFile)
        self.stampPath = tdb.dataPath / stampFilePath
        self.newSystems = 0
        self.newStations = 0


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


    def splash(self, title, text):
        if hasTkInter:
            tk = tkinter.Tk()
            tk.withdraw()
            mbox.showinfo(title, text)
        else:
            print("=== {} ===\n".format(title))
            print(text)
            input("Press return to continue: ")


    def check_first_time_use(self):
        iniFilePath = self.tdb.dataPath / "maddavo.ini"
        if not iniFilePath.is_file():
            with iniFilePath.open("w") as fh:
                print(
                    "[default]\n"
                    "firstUse={}".format(time.time()),
                    file=fh
                )
            self.splash(
                "Maddavo Plugin",
                "This plugin fetches price data from Maddavo's site, "
                "a 3rd party crowd-source data project.\n"
                "\n"
                "  {}\n"
                "\n"
                "To use this provider you may need to download some "
                "additional files such as the Station.csv or System.csv "
                "files from this provider's site.\n"
                "\n"
                "When importing prices from this provider, TD will "
                "automatically add temporary, 'placeholder' entries for "
                "stations in the .prices file that are not in your local "
                "'Station.csv' file.\n"
                "\n"
                "You can silence these warnings with '-q', or you can "
                "import Station data from maddavo's by adding the "
                "'--opt=stations' flag periodically. If you get errors "
                "about missing Systems, you can also import Systems "
                "from his site using --opt=systems.\n"
                "\n"
                "See the group (http://kfs.org/td/group), thread "
                "(http://kfs.org/td/thread) or wiki "
                "(http://kfs.org/td/wiki) for more help."
                .format(BASE_URL)
            )

    def import_systems(self):
        """
        Fetch and import data from Systems.csv
        """
        if not self.getOption("systems"):
            return

        tdb, tdenv = self.tdb, self.tdenv
        NOTE = tdenv.NOTE
        systems = tdb.systemByName

        NOTE("Importing Systems")
        stream = transfers.CSVStream(SYSTEMS_URL)
        for _, values in stream:
            name = values[0].upper()
            x, y, z = float(values[1]), float(values[2]), float(values[3])
            added, modified = values[4], values[5]
            system = systems.get(name, None)
            if not system:
                tdb.addLocalSystem(name, x, y, z, added, modified)
                self.newSystems += 1
            elif system.posX != x or system.posY != y or system.posZ != z:
                print("{} position change: {}v{}, {}v{}, {}v{}".format(
                    name, system.posX, x, system.posY, y, system.posZ, z
                ))
                tdb.updateLocalSystem(system, name, x, y, z, added, modified)
                self.newSystems += 1


    def import_stations(self):
        """
        Fetch and import data from Stations.csv
        """
        if not self.getOption("stations"):
            return

        tdb, tdenv = self.tdb, self.tdenv
        NOTE = tdenv.NOTE
        systems = tdb.systemByName
        sysAdjust = corrections.systems.get
        stnAdjust = corrections.stations.get
        DELETED = corrections.DELETED

        NOTE("Importing Stations")
        stream = transfers.CSVStream(STATIONS_URL)
        for _, values in stream:
            sysName, stnName = values[0].upper(), values[1]
            sysName = sysAdjust(sysName, sysName)
            if sysName == DELETED:
                tdenv.DEBUG0("Ignoring deleted system {}", values[0])
                continue
            system = systems.get(sysName, None)
            if not system:
                NOTE(
                    "Unrecognized system for station {}/{}",
                    sysName, stnName
                )
                continue
            stnName = stnAdjust('/'.join([sysName, stnName.upper()]), stnName)
            if stnName == DELETED:
                tdenv.DEBUG0(
                    "Ignoring deleted station {}/{}",
                    values[0], values[1]
                )
                continue
            station = system.getStation(stnName)
            lsFromStar = int(values[2])
            blackMarket = values[3]
            maxPadSize = values[4]
            market = values[5] if len(values) > 4 else '?'
            shipyard = values[6] if len(values) > 5 else '?'
            modified = values[7] if len(values) > 6 else 'now'
            if station:
                if tdb.updateLocalStation(
                        station,
                        name=stnName,
                        lsFromStar=lsFromStar,
                        market=market,
                        blackMarket=blackMarket,
                        shipyard=shipyard,
                        maxPadSize=maxPadSize,
                        modified=modified,
                        ):
                    self.newStations += 1
            else:
                tdb.addLocalStation(
                    system=system,
                    name=stnName,
                    lsFromStar=lsFromStar,
                    market=market,
                    blackMarket=blackMarket,
                    shipyard=shipyard,
                    maxPadSize=maxPadSize,
                    modified=modified,
                )
                self.newStations += 1


    def refresh_csv(self):
        if not self.getOption("exportcsv"):
            return

        _, path = csvexport.exportTableToFile(
            self.tdb, self.tdenv, "System"
        )
        self.tdenv.NOTE("{} updated.", path)
        _, path = csvexport.exportTableToFile(
            self.tdb, self.tdenv, "Station"
        )
        self.tdenv.NOTE("{} updated.", path)


    def run(self):
        tdb, tdenv = self.tdb, self.tdenv

        if self.getOption("syscsv") or self.getOption("stncsv"):
            raise PluginException(
                "\a--opt=syscsv and --opt=stncsv have been REPLACED.\n"
                "\n"
                "The behavior of the Maddavo plugin has changed drastically "
                "in version 6.10.0.\n"
                "\n"
                "The old options, syscsv and stncsv, would download the "
                "corresponding file from Maddavo's and REPLACE your local "
                "file with his data.\n"
                "\n"
                "The new options, --opt=systems and --opt=stations, will "
                "read his files and MERGE his data into your local db.\n"
                "\n"
                "An additional option, --opt=exportcsv, was also added "
                "to export the resulting, merged data, to your .csv files."
            )

        # It takes a while to download these files, so we want
        # to record the start time before we download. What we
        # care about is when we downloaded relative to when the
        # files were previously generated.

        self.check_first_time_use()

        startTime = time.time()

        tdenv.ignoreUnknown = True

        prevImportDate, lastRunDays = self.load_timestamp()
        self.prevImportDate = prevImportDate

        skipDownload = self.getOption("skipdl")
        forceParse = self.getOption("force") or skipDownload

        # Ensure the cache is built and reloaded.
        tdb.reloadCache()
        tdb.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)

        self.import_systems()
        self.import_stations()

        # Let the system decide if it needs to reload-cache
        tdb.close()

        self.refresh_csv()

        use3h = 1 if self.getOption("use3h") else 0
        use2d = 1 if self.getOption("use2d") else 0
        usefull = 1 if self.getOption("usefull") else 0
        if use3h + use2d + usefull > 1:
            raise PluginException(
                "Only one of use3h/use2d/usefull can be used at once."
            )
        if (use3h or use2d or usefull) and skipDownload:
            raise PluginException(
                "use3h/use2d/usefull has no effect with --opt=skipdl"
            )
        if use3h:
            lastRunDays = 0.01
        elif use2d:
            lastRunDays = 1.0
        elif usefull:
            lastRunDays = 3.0

        if not skipDownload:
            # Download
            if lastRunDays < 3 / 24:
                priceFile = "prices-3h.asp"
            elif lastRunDays < 1.9:
                priceFile = "prices-2d.asp"
            else:
                priceFile = "prices.asp"
            transfers.download(
                tdenv,
                BASE_URL + priceFile,
                self.filename,
                shebang=lambda line: self.check_shebang(line, True),
            )

        if tdenv.download:
            return False

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

        # We did all the work
        return False
