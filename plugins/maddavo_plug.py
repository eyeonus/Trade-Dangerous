import cache
import pathlib
import plugins
import re
import tradeenv
import transfers

from plugins import PluginException


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads data from maddavo's site.
    """

    stampFile = "maddavo.stamp"
    dateRe = re.compile(r"(\d\d\d\d-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)")

    options = {
        'syscsv':   "Also download System.csv from the site.",
        'stncsv':   "Also download Station.csv from the site.",
        'skipdl':   "Skip doing any downloads.",
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
        if not self.getOption("skipdl"):
            if self.getOption("syscsv"):
                transfers.download(
                    self.tdenv,
                    "http://www.davek.com.au/td/System.csv",
                    "data/System.csv",
                    backup=True,
                )
            if self.getOption("stncsv"):
                transfers.download(
                    self.tdenv,
                    "http://www.davek.com.au/td/Station.csv",
                    "data/Station.csv",
                    backup=True,
                )
            # Download 
            transfers.download(
                    self.tdenv,
                    "http://www.davek.com.au/td/prices.asp",
                    self.filename,
            )

        if self.tdenv.download:
            return False

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
            if not self.tdenv.quiet:
                print("No new data - nothing to do - doing nothing.")
            return False

        if self.tdenv.detail:
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
        if not self.tdenv.quiet and numStationsUpdated:
            if len(updatedStations) > 12 and self.tdenv.detail < 2:
                updatedStations = list(updatedStations)[:10] + ["..."]
            print("{} {} updated:\n{}".format(
                numStationsUpdated,
                "stations" if numStationsUpdated > 1 else "station",
                ', '.join(updatedStations)
            ))

        # Temporarily disable "ignoreUnkown"
        mytdenv = tradeenv.TradeEnv(properties=self.tdenv)
        mytdenv.ignoreUnknown = True
        cache.importDataFromFile(
                self.tdb,
                mytdenv,
                pathlib.Path(self.filename),
        )

        self.save_timestamp(newestDate)

        # We did all the work
        return False
