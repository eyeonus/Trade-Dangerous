class Plugin(object):
    """
    Base class for plugin implementation.

    The first call is to "isExpectingData()" to determine if there
    is any expectation of new data. For instance, you might check
    to check the timestamp on a file in a dropbox folder.

    Next, prepareData() is called to fetch or load the data, which
    should return True if there is data to be processed, otherwise
    it should return False.

    In the case of prepareData() return True, processData() is
    called to process the data.
    """

    defaultImportFile = "import.prices"


    def __init__(self, tdb, cmdenv):
        self.tdb = tdb
        self.cmdenv = cmdenv


    def isExpectingData(self):
        """
        Return False if there is definitely no new data,
        otherwise return True.
        """
        raise Exception("Not implemented")


    def prepareData(self):
        """
        Plugin Must Implement:
        Prepare data for use - e.g. download from the web to
        a local file.
        Return True if there is data to be processed.
        """
        raise Exception("Not implemented")


    def processData(self):
        """
        Plugin Must Implement:
        Handle the data that has been retrieved.
        """
        raise Exception("Not implemented")

