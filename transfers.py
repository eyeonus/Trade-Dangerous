from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

from pathlib import Path
from tradeexcept import TradeException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import time
import urllib.error


######################################################################
# Helpers


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
    

def rateVal(bytes, started):
    """
    Determine the rate at which data has been transferred.

    bytes:
        The number of bytes transferred.

    started:
        The time.time() when the transfer started.
    """

    now = time.time()
    if bytes == 0 or now <= started:
        return "..."
    units = (makeUnit(bytes / (now - started))+"/s") or "FAST!"
    return units


def download(
            cmdenv, url, localFile,
            headers=None,
            backup=False,
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
    """

    if headers:
        req = Request(url, headers=headers)
    else:
        req = Request(url)

    if not cmdenv.quiet:
        print("Connecting to server: {}".format(url))
    try:
        f = urlopen(req)
    except urllib.error.URLError as e:
        raise TradeException(
                "Unable to connect ("+url+")\n"+str(e)
        )
    cmdenv.DEBUG0(str(f.info()))

    # Figure out how much data we have
    bytes = int(f.getheader('Content-Length'))
    maxBytesLen = len("{:>n}".format(bytes))
    fetched = 0
    started = time.time()

    # Fetch four memory pages at a time
    chunkSize = 4096 * 4

    tmpPath = Path(localFile + ".dl")
    actPath = Path(localFile)

    with tmpPath.open("wb") as fh:
        # Use the 'while True' approach so that we always print the
        # download status including, especially, the 100% report.
        while True:
            if not cmdenv.quiet:
                print("{}: "
                        "{:>{len}n}/{:>{len}n} bytes "
                        "| {:>10s} "
                        "| {:>5.2f}% "
                        .format(
                                localFile,
                                fetched, bytes,
                                rateVal(fetched, started),
                                (fetched * 100 / bytes),
                                len=maxBytesLen
                ), end='\r')

            if fetched >= bytes:
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

