from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import *
import math

import cache
from pathlib import Path

######################################################################
# Parser config

help=(
    "Imports price data from a '.prices' format file "
    "without affecting data for stations not included "
    "in the import file."
)
name='import'
epilog=None
wantsTradeDB=True
arguments = [
    ParseArgument('filename', help='Name of the file to read. If the filename is - an open file dialog will be presented.', type=str),
]
switches = [
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
# Perform query and populate result set

def run(results, cmdenv, tdb):
    # If the filename specified was "-" or None, then go ahead
    # and present the user with an open file dialog.
    if not cmdenv.filename or cmdenv.filename == "-":
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

    # check the file exists.
    filePath = Path(cmdenv.filename)
    if not filePath.is_file():
        raise CommandLineError("File not found: {}".format(
                    str(filePath)
                ))
    cache.importDataFromFile(tdb, cmdenv, filePath)
    return None

