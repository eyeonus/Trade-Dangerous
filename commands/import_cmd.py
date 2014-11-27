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
    ParseArgument('filename', help='Name of the file to read.', type=str),
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
    filePath = Path(cmdenv.filename)
    cache.importDataFromFile(tdb, cmdenv, filePath)
    return None

