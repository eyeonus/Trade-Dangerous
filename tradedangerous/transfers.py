import csv
import json
import time

from collections import deque
from pathlib import Path
from .tradeexcept import TradeException
from .misc import progress as pbar
from . import fs

import requests


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

def download(
            tdenv, url, localFile,
            headers=None,
            backup=False,
            shebang=None,
            chunkSize=4096,
            timeout=90,
        ):
    """
    Fetch data from a URL and save the output
    to a local file. Returns the response headers.
    
    tdenv:
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
    
    tdenv.NOTE("Requesting {}".format(url))
    req = requests.get(url, headers=headers or None, stream=True, timeout=timeout)
    req.raise_for_status()
    
    encoding = req.headers.get('content-encoding', 'uncompress')
    length = req.headers.get('content-length', None)
    transfer = req.headers.get('transfer-encoding', None)
    if transfer != 'chunked':
        # chunked transfer-encoding doesn't need a content-length
        if length is None:
            print(req.headers)
            raise Exception("Remote server replied with invalid content-length.")
        length = int(length)
        if length <= 0:
            raise TradeException(
                "Remote server gave an empty response. Please try again later."
            )

    # if the file is being compressed by the server, the headers tell us the
    # length of the compressed data, but in our loop below we will be receiving
    # the uncompressed data, which should be larger, which will cause our
    # download indicators to sit at 100% for a really long time if the file is
    # heavily compressed and large (e.g spansh 1.5gb compressed vs 9GB uncompressed)
    if encoding == "gzip" and length:
        length *= 4
    
    if tdenv.detail > 1:
        if length:
            tdenv.NOTE("Downloading {} {}ed data", makeUnit(length), encoding)
        else:
            tdenv.NOTE("Downloading {} {}ed data", transfer, encoding)
    tdenv.DEBUG0(str(req.headers).replace("{", "{{").replace("}", "}}"))
    
    # Figure out how much data we have
    if length and not tdenv.quiet:
        progBar = pbar.Progress(length, 20)
    else:
        progBar = None
    
    actPath = Path(localFile)
    fs.ensurefolder(tdenv.tmpDir)
    tmpPath = Path(tdenv.tmpDir, "{}.dl".format(actPath.name))
    
    histogram = deque()
    
    fetched = 0
    lastTime = started = time.time()
    spinner, spinners = 0, [
        '.    ', '..   ', '...  ', ' ... ', '  ...', '   ..', '    .'
    ]
    with tmpPath.open("wb") as fh:
        for data in req.iter_content(chunk_size=chunkSize):
            fh.write(data)
            fetched += len(data)
            if shebang:
                bangLine = data.decode().partition("\n")[0]
                tdenv.DEBUG0("Checking shebang of {}", bangLine)
                shebang(bangLine)
                shebang = None
            if progBar:
                now = time.time()
                deltaT = max(now - lastTime, 0.001)
                lastTime = now
                if len(histogram) >= 15:
                    histogram.popleft()
                histogram.append(len(data) / deltaT)
                progBar.increment(
                    len(data),
                    postfix=lambda value, goal: \
                            " {:>7s} [{:>7s}/s] {:>3.0f}% {:1s}".format(
                            makeUnit(value),
                            makeUnit(sum(histogram) / len(histogram)),
                            (fetched * 100. / length),
                            spinners[spinner]
                        )
                )
                if deltaT > 0.200:
                    spinner = (spinner + 1) % len(spinners)
        tdenv.DEBUG0("End of data")
    if not tdenv.quiet:
        if progBar:
            progBar.clear()
        elapsed = (time.time() - started) or 1
        tdenv.NOTE(
            "Downloaded {} of {}ed data {}/s",
            makeUnit(fetched), encoding,
            makeUnit(fetched / elapsed)
        )
    
    fs.ensurefolder(actPath.parent)
    
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
    
    req.close()
    return req.headers

def get_json_data(url, *, timeout: int = 90):
    """
    Fetch JSON data from a URL and return the resulting dictionary.
    
    Displays a progress bar as it downloads.
    """
    
    req = requests.get(url, stream=True, timeout=timeout)
    
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

class CSVStream:
    """
    Provides an iterator that fetches CSV data from a given URL
    and presents it as an iterable of (columns, values).
    
    Example:
        stream = transfers.CSVStream("http://blah.com/foo.csv")
        for cols, vals in stream:
            print("{} = {}".format(cols[0], vals[0]))
    """
    
    def __init__(self, url, tdenv=None, *, timeout: int = 90):
        self.url = url
        self.tdenv = tdenv
        if not url.startswith("file:///"):
            self.req = requests.get(self.url, stream=True, timeout=timeout)
            self.lines = self.req.iter_lines()
        else:
            self.lines = open(url[8:], "rUb")
        self.columns = self.next_line().split(',')
    
    def next_line(self):
        """ Fetch the next line as a text string """
        while True:
            line = next(self.lines)
            try:
                return line.decode(encoding="utf-8")
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
