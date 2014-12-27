import cache
import pathlib
import plugins
import re
import tradedb
import tradeenv
import transfers

from plugins import PluginException


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
                        "there is no new data."
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

        prevImportDate = "0000-00-00 00:00:00"
        try:
            fh = self.stampPath.open('rU')
            line = fh.readline().split('\n')
            if line and line[0]:
                if ImportPlugin.dateRe.match(line[0]):
                    return line[0]
        except FileNotFoundError:
            pass

        return "0000-00-00 00:00:00"


    def save_timestamp(self, newestDate):
        """
        Save a date to the timestamp file.
        """

        with self.stampPath.open('w') as fh:
            print(newestDate, file=fh)


    def run(self):
        tdb, tdenv = self.tdb, self.tdenv

        cacheNeedsRebuild = self.getOption("buildcache")
        if not self.getOption("skipdl"):
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
            transfers.download(
                    tdenv,
                    "http://www.davek.com.au/td/prices.asp",
                    self.filename,
            )

        if tdenv.download:
            if cacheNeedsRebuild:
                print("NOTE: Did not rebuild cache")
            return False

        tdenv.ignoreUnknown = True

        if cacheNeedsRebuild:
            tdb = tdb
            # Make sure we disconnect from the db
            if tdb.conn:
                tdb.conn.close()
            tdb.conn = tdb.cur = None
            tdb.reloadCache()
            tdb.load(
                    maxSystemLinkLy=tdenv.maxSystemLinkLy,
                    )

        prevImportDate = self.load_timestamp()

        # Scan the file for the latest data.
        firstDate = None
        newestDate = prevImportDate
        numNewLines = 0
        minLen = len(prevImportDate) + 10
        dateRe = ImportPlugin.dateRe
        lastStn = None
        updatedStations = set()
        with open("import.prices", "rU", encoding="utf-8") as fh:
            firstLine = fh.readline()
            m = re.match(
                    r'^#!\s*trade.py\s*import\s*.*\s*--timestamp\s*"([^"]+)"',
                    firstLine
            )
            if not m:
                raise PluginException("File does not look like a maddavo import.")
            importDate = m.group(1)

            for line in fh:
                if line.startswith('@'):
                    lastStn = line[2:-1]
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
            if not tdenv.quiet:
                print("Cache is up-to date / no new price entries.")
            if not self.getOption("force"):
                return False

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
            print("{} {} updated:\n{}".format(
                numStationsUpdated,
                "stations" if numStationsUpdated > 1 else "station",
                ', '.join(updatedStations)
            ))

        cache.importDataFromFile(
                tdb,
                tdenv,
                pathlib.Path(self.filename),
        )

        self.save_timestamp(newestDate)

        # We did all the work
        return False
