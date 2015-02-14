import cache
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


hasTkInter = False
if not 'NOTK' in os.environ and platform.system() != 'Darwin':  # focus bug
    try:
        import tkinter
        import tkinter.messagebox as mbox
        hasTkInter = True
    except ImportError:
        pass


class DecodingError(PluginException):
    pass


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads data from maddavo's site.
    """

    stampFile = "maddavo.stamp"
    dateRe = re.compile(r"(\d\d\d\d-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)")

    pluginOptions = {
        'buildcache':   "Forces a rebuild of the cache before processing "
                        "of the .prices file.",
        'syscsv':       "Also download System.csv from the site.",
        'stncsv':       "Also download Station.csv from the site.",
        'skipdl':       "Skip doing any downloads.",
        'force':        "Process prices even if timestamps suggest "
                        "there is no new data.",
        'use3h':        "Force download of the 3-hours .prices file",
        'use2d':        "Force download of the 2-days .prices file",
        'usefull':      "Force download of the full .prices file",
    }

    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)

        self.filename = self.defaultImportFile
        stampFilePath = pathlib.Path(ImportPlugin.stampFile)
        self.stampPath = tdb.dataPath / stampFilePath


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


    def checkShebang(self, line, checkAge):
        m = re.match(
                r'^#!\s*trade.py\s*import\s*.*\s*--timestamp\s*"([^"]+)"',
                line
        )
        if not m:
            raise PluginException("Data is not Maddavo's prices list: " + line)
        self.importDate = m.group(1)
        if checkAge and not self.getOption("force"):
            if self.importDate <= self.prevImportDate:
                raise SystemExit(
                        "Local data is already current [{}].".format(
                            self.importDate
                ))
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


    def checkForFirstTimeUse(self):
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
                    "  http://davek.com.au/td/\n"
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
                    "refresh your Station.csv file by adding the "
                    "'--opt=stncsv' flag periodically, or you can export the "
                    "placeholders to your .csv file with the command:\n"
                    "  trade.py export --table Station.csv\n"
                    "or for short:\n"
                    "  trade.py exp --tab Station.csv\n"
                    "\n"
                    "PLEASE BE AWARE: Using a 3rd party source for your .csv "
                    "files may cause conflicts when updating the "
                    "TradeDangerous code.\n"
                    "\n"
                    "See the group (http://kfs.org/td/group), thread "
                    "(http://kfs.org/td/thread) or wiki "
                    "(http://kfs.org/td/wiki) for more help."
                )



    def run(self):
        tdb, tdenv = self.tdb, self.tdenv

        # It takes a while to download these files, so we want
        # to record the start time before we download. What we
        # care about is when we downloaded relative to when the
        # files were previously generated.

        self.checkForFirstTimeUse()

        startTime = time.time()

        prevImportDate, lastRunDays = self.load_timestamp()
        self.prevImportDate = prevImportDate

        cacheNeedsRebuild = self.getOption("buildcache")
        skipDownload = self.getOption("skipdl")
        forceParse = self.getOption("force") or skipDownload

        use3h = 1 if self.getOption("use3h") else 0
        use2d = 1 if self.getOption("use2d") else 0
        usefull = 1 if self.getOption("usefull") else 0
        if use3h + use2d + usefull > 1:
            raise PluginError(
                "Only one of use3h/use2d/usefull can be used at once."
            )
        if (use3h or use2d or usefull) and skipDownload:
            raise PluginError(
                "use3h/use2d/usefull has no effect with --opt=skipdl"
            )
        if use3h:
            lastRunDays = 0.01
        elif use2d:
            lastRunDays = 1.0
        elif usefull:
            lastRunDays = 3.0

        if not skipDownload:
            if self.getOption("syscsv"):
                transfers.download(
                    tdenv,
                    "http://www.davek.com.au/td/System.csv",
                    "data/System.csv",
                    backup=True,
                )
                cacheNeedsRebuild = True
            if self.getOption("stncsv"):
                transfers.download(
                    tdenv,
                    "http://www.davek.com.au/td/station.asp",
                    "data/Station.csv",
                    backup=True,
                )
                cacheNeedsRebuild = True
            # Download 
            if lastRunDays < 3/24:
                priceFile = "prices-3h.asp"
            elif lastRunDays < 1.9:
                priceFile = "prices-2d.asp"
            else:
                priceFile = "prices.asp"
            transfers.download(
                    tdenv,
                    "http://www.davek.com.au/td/"+priceFile,
                    self.filename,
                    shebang=lambda line: self.checkShebang(line, True),
            )

        if tdenv.download:
            if cacheNeedsRebuild:
                tdenv.NOTE("Did not rebuild cache")
            return False

        tdenv.ignoreUnknown = True

        # Let the system decide if it needs to reload-cache
        tdenv.DEBUG0("Checking the cache")
        tdb.close()
        tdb.reloadCache()
        tdb.load(
                maxSystemLinkLy=tdenv.maxSystemLinkLy,
        )
        tdb.close()

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
            self.checkShebang(firstLine, False)
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
                        line = line.decode(encoding="latin1").encode("utf-8").decode()
                    except UnicodeDecodeError:
                        raise DecodingError(
                            "{} line {}: "
                            "Invalid (unrecognized, non-utf8) character sequence: {}\n{}".format(
                                self.filename, lineNo, str(e), line,
                        )) from None
                    raise DecodingError(
                        "{} line {}: "
                        "Invalid (latin1, non-utf8) character sequence:\n{}".format(
                            self.filename, lineNo, line,
                    ))
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
                                "(newer than the import?)".format(
                                    lastStn,
                                    date
                            ))

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
                tdenv.NOTE("{} {} updated:\n{}",
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
