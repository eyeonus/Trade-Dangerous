import cache
import pathlib
import plugins
import tradeenv
import transfers


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads data from maddavo's site.
    """


    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)

        self.filename = self.defaultImportFile


    def run(self):
        # Download 
        transfers.download(
                self.tdenv,
                "http://www.davek.com.au/td/prices.asp",
                self.filename,
        )

        # Temporarily disable "ignoreUnkown"
        mytdenv = tradeenv.TradeEnv(properties=self.tdenv)
        mytdenv.ignoreUnknown = True
        cache.importDataFromFile(
                self.tdb,
                mytdenv,
                pathlib.Path(self.filename),
        )

        # We did all the work
        return False
