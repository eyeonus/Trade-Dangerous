from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import *
import math
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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

def download(cmdenv, url):
    """
        Download a prices file from the web.
    """

    req = Request(url)

    cmdenv.DEBUG0("Fetching: {}", url)
    f = urlopen(req)
    cmdenv.DEBUG0(str(f.info()))
    data = f.read().decode()

    dstFile = "import.prices"
    with open(dstFile, "w") as fh:
        print(data, file=fh)

    return dstFile


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    # If the filename specified was "-" or None, then go ahead
    # and present the user with an open file dialog.

    if cmdenv.url:
        cmdenv.filename = download(cmdenv, cmdenv.url)

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

