from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

from pathlib import Path
from tradeexcept import TradeException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import csv
import json
import math
import misc.progress as pbar
import time
import urllib.error

def import_requests():
    try:
        import requests
    except ImportError as e:
        print("ERROR: Unable to load the Python 'requests' package.")
        approval = input(
            "Do you want me to try and install it with 'pip', the "
            "Python package manager (y/n)? "
        )
        if approval.lower() != 'y':
            raise e
    else:
        return requests

    try:
        import pip
    except ImportError as e:
        raise TradeException(
            "Python 3.4.2 includes a package manager called 'pip', "
            "except it doesn't appear to be installed on your system:\n" +
            str(e)
        ) from None

    pip.main(["install", "--upgrade", "requests"])

    try:
        import requests
    except ImportError as e:
        raise TradeException(
            "The requests module did not install correctly, or you have "
            "multiple, conflicting instances of Python installed and it "
            "got very confused just now.\n"
            "\n"
            "You may want to try:\n"
            "  python3 -m pip install --upgrade pip setuptools\n"
            "  python3 -m pip install --upgrade requests\n"
            + str(e)
        ) from None

    return requests


######################################################################
# Helpers

class HTTP404(TradeException):
    pass


def makeUnit(value):
    """
    Convert a value in bytes into a Kb, Mb, Gb etc.
    """

    units = [ 'B ', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB' ]
    unitSize = int(value)
    for unit in units:
        if unitSize <= 640:
            return "{:>5.01f}{}".format(unitSize, unit)
        unitSize /= 1024
    return None


def rateVal(bytes, duration):
    """
    Determine the rate at which data has been transferred.

    bytes:
        The number of bytes transferred.

    started:
        The time.time() when the transfer started.
    """

    if bytes == 0 or duration <= 0:
        return "..."
    units = (makeUnit(bytes / (duration))+"/s") or "FAST!"
    return units


def download(
            cmdenv, url, localFile,
            headers=None,
            backup=False,
            shebang=None,
        ):
    """
    Fetch data from a URL and save the output
    to a local file. Returns the response headers.

    cmdenv:
        TradeEnv we're working under

    url:
        URL we're fetching (http, https or ftp)

    localFile:
        Name of the local file to open.

    headers:
        dict() of additional HTTP headers to send

    shebang:
        function to call on the first line
    """

    if headers:
        req = Request(url, headers=headers)
    else:
        req = Request(url)

    if not cmdenv.quiet:
        print("Connecting to server: {}".format(url))
    try:
        f = urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise HTTP404("{}: {}".format(e, url))
        raise TradeException(
                "HTTP Error: "+url+": "+str(e)
        )
    except urllib.error.URLError as e:
        raise TradeException(
                "Unable to connect ("+url+")\n"+str(e)
        )
    cmdenv.DEBUG0(str(f.info()))

    # Figure out how much data we have
    contentLength = int(f.getheader('Content-Length'))
    maxBytesLen = len("{:>n}".format(contentLength))
    fetched = 0
    started = time.time()

    chunkSize = 4096 * 16

    tmpPath = Path(localFile + ".dl")
    actPath = Path(localFile)

    with tmpPath.open("wb") as fh:
        if shebang:
            line = f.readline().decode()
            shebang(line)
            shebang = None
            fh.write(line.encode())
            fetched += len(line)

        if cmdenv.quiet:
            fh.write(f.read())
        else:
            # Use the 'while True' approach so that we always print the
            # download status including, especially, the 100% report.
            while True:
                duration = time.time() - started
                if contentLength and duration >= 1:
                    # estimated contentLength per second
                    rate = math.ceil(contentLength / duration)
                    # but how much can we download in 1/10s
                    burstSize = rate / 10
                    chunkSize += math.ceil((burstSize - chunkSize) * 0.7)
                print("{}: "
                        "{:>{len}n}/{:>{len}n} bytes "
                        "| {:>10s} "
                        "| {:>5.2f}% "
                        .format(
                                localFile,
                                fetched, contentLength,
                                rateVal(fetched, duration),
                                (fetched * 100 / contentLength),
                                len=maxBytesLen
                ), end='\r')

                if fetched >= contentLength:
                    if not cmdenv.quiet:
                        print()
                    break

                chunk = f.read(chunkSize)
                fetched += len(chunk)
                fh.write(chunk)

    # Swap the file into place
    if backup:
        bakPath = Path(localFile + ".bak")
        if bakPath.exists():
            bakPath.unlink()
        if actPath.exists():
            actPath.rename(localFile + ".bak")
    if actPath.exists():
        actPath.unlink()
    tmpPath.rename(actPath)

    return f.getheaders()


def get_json_data(url):
    """
    Fetch JSON data from a URL and return the resulting dictionary.

    Displays a progress bar as it downloads.
    """

    requests = import_requests()
    req = requests.get(url, stream=True)

    # credit for the progress indicator:
    # http://stackoverflow.com/a/15645088/257645
    totalLength = req.headers.get('content-length')
    if totalLength is None:
        compression = req.headers.get('content-encoding')
        compression = (compression + "'ed") if compression else "uncompressed"
        print("Downloading {}: {}...".format(compression, url))
        jsData = req.content
    else:
        totalLength = int(totalLength)
        progBar = pbar.Progress(totalLength, 25)
        jsData = bytes()
        for data in req.iter_content():
            jsData += data
            progBar.increment(
                len(data),
                postfix=lambda value, goal: \
                " {}/{}".format(
                    makeUnit(value),
                    makeUnit(goal),
            ))
        progBar.clear()

    return json.loads(jsData.decode())


class CSVStream(object):
    """
    Provides an iterator that fetches CSV data from a given URL
    and presents it as an iterable of (columns, values).

    Example:
        stream = transfers.CSVStream("http://blah.com/foo.csv")
        for cols, vals in stream:
            print("{} = {}".format(cols[0], vals[0]))
    """

    def __init__(self, url, tdenv=None):
        self.url = url
        self.tdenv = tdenv
        if not url.startswith("file:///"):
            requests = import_requests()
            self.req = requests.get(self.url, stream=True)
            self.lines = self.req.iter_lines()
        else:
            self.lines = open(url[8:], "rUb")
        self.columns = self.next_line().split(',')

    def next_line(self):
        """ Fetch the next line as a text string """
        while True:
            line = next(self.lines)
            try:
                return line.decode()
            except UnicodeDecodeError as e:
                if not self.tdenv:
                    raise e
                self.tdenv.WARN(
                    "{}: line:{}: {}\n{}",
                    self.url, self.csvin.line_num, line, e
                )

    def __iter__(self):
        """
        Iterate across data received as csv values.
        Yields [column headings], [column values]
        """
        self.csvin = csvin = csv.reader(
            iter(self.next_line, 'END'),
            delimiter=',', quotechar="'", doublequote=True
        )
        columns = self.columns
        for values in csvin:
            if values and len(values) == len(columns):
                yield columns, values