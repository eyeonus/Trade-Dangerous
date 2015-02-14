from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

from pathlib import Path
from tradeexcept import TradeException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import json
import math
import misc.progress as pbar
import time
import urllib.error

try:
    import requests
except ImportError as e:
    import pip
    print("ERROR: Unable to load the Python 'requests' package.")
    approval = input(
        "Do you want me to try and install it with the package manager (y/n)? "
    )
    if approval.lower() != 'y':
        raise e
    pip.main(["install", "--upgrade", "requests"])
    import requests


######################################################################
# Helpers

class HTTP404(TradeException):
    pass


def makeUnit(value):
    """
    Convert a value in bytes into a Kb, Mb, Gb etc.
    """

    units = [ '', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y' ]
    unitSize = int(value)
    for unit in units:
        if unitSize <= 640:
            return "{:5.2f}{}B".format(unitSize, unit)
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


def retrieve_json_data(url):
    """
    Fetch JSON data from a URL and return the resulting dictionary.

    Displays a progress bar as it downloads.
    """

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
            progBar.increment(len(data), postfix=lambda: \
                " {}/{} ".format(
                    makeUnit(progBar.value),
                    makeUnit(totalLength),
            ))
        progBar.clear()

    return json.loads(jsData.decode())

