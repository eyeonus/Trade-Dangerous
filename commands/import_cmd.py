from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import *
import math
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import urllib.error

import cache
from pathlib import Path

######################################################################
# Parser config

help=(
    "Imports price data from a '.prices' format file. "
    "Previous data for the stations included in the file "
    "is removed, but other stations are not affected."
)
name='import'
epilog=None
wantsTradeDB=True
arguments = [
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument('filename',
            help='Name of the file to read.',
            type=str,
            default=None,
        ),
        MutuallyExclusiveGroup(
            ParseArgument('--maddavo',
                help='Import prices from Maddavo\'s site.',
                dest='url',
                action='store_const',
                const="http://www.davek.com.au/td/prices.asp",
            ),
        ),
    ),
    ParseArgument(
        '--ignore-unknown', '-i',
        default=False, action='store_true',
        dest='ignoreUnknown',
        help=(
            "Data for systems, stations and items that are not "
            "recognized is reported as warning but skipped."
        ),
    ),
]

######################################################################
# Helpers

def makeUnit(value):
    units = [ '', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y' ]
    unitSize = int(value)
    for unit in units:
        if unitSize <= 640:
            return "{:5.2f}{}B".format(unitSize, unit)
        unitSize /= 1024
    return None
    

def rateVal(fetched, started):
    now = time.time()
    if fetched == 0 or now <= started:
        return "..."
    units = (makeUnit(fetched / (now - started))+"/s") or "FAST!"
    return units


def download(cmdenv, url):
    """
        Download a prices file from the web.
    """

    req = Request(url)

    if not cmdenv.quiet:
        print("Connecting to server")
    try:
        f = urlopen(req)
    except urllib.error.URLError as e:
        raise TradeException(
                "Unable to connect ("+url+")\n" +
                str(e)
        )
    cmdenv.DEBUG0(str(f.info()))

    # Figure out how much data we have
    bytes = int(f.getheader('Content-Length'))
    maxBytesLen = len("{:>n}".format(bytes))
    fetched = 0
    started = time.time()

    # Fetch four memory pages at a time
    chunkSize = 4096 * 4

    dstFile = "import.prices"
    with open(dstFile, "w") as fh:
        # Use the 'while True' approach so that we always print the
        # download status including, especially, the 100% report.
        while True:
            if not cmdenv.quiet:
                print("Download: "
                        "{:>{len}n}/{:>{len}n} bytes "
                        "| {:>10s} "
                        "| {:>5.2f}% "
                        .format(
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
            print(chunk.decode(), file=fh, end="")

    return dstFile


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    # If the filename specified was "-" or None, then go ahead
    # and present the user with an open file dialog.

    if cmdenv.url:
        cmdenv.filename = download(cmdenv, cmdenv.url)
        assert cmdenv.filename

    if not cmdenv.filename:
        import tkinter
        from tkinter.filedialog import askopenfilename
        tk = tkinter.Tk()
        tk.withdraw()
        filetypes = (
                ("TradeDangerous '.prices' Files", "*.prices"),
                ("All Files", "*.*"),
                )
        filename = askopenfilename(
                    title="Select the file to import",
                    initialfile="TradeDangerous.prices",
                    filetypes=filetypes,
                    initialdir='.',
                )
        if not filename:
            raise SystemExit("Aborted")
        cmdenv.filename = filename

    if re.match("^https?://", cmdenv.filename, re.IGNORECASE):
        cmdenv.filename = download(cmdenv.filename)

    # check the file exists.
    filePath = Path(cmdenv.filename)
    if not filePath.is_file():
        raise CommandLineError("File not found: {}".format(
                    str(filePath)
                ))

    cache.importDataFromFile(tdb, cmdenv, filePath)
    return None

