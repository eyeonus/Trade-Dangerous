from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.exceptions import *
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from tradedb import TradeDB

import math

######################################################################
# Parser config

help='Find rares near your current local.'
name='rare'
epilog=None
wantsTradeDB=True
arguments = [
    ParseArgument('near', help='Your current system.', type=str),
]
switches = [
    ParseArgument('--ly',
            help='Maximum distance to search.',
            metavar='LY',
            type=float,
            default=42,
            dest='maxLyPer',
    ),
    ParseArgument('--limit',
            help='Maximum number of results to list.',
            default=None,
            type=int,
    ),
    ParseArgument('--price-sort', '-P',
            help='(When using --near) Sort by price not distance',
            action='store_true',
            default=False,
            dest='sortByPrice',
    ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    start = cmdenv.nearSystem

    results.summary = ResultRow()
    results.summary.near = start
    results.summary.ly = cmdenv.maxLyPer

    maxLySq = cmdenv.maxLyPer ** 2

    for rare in tdb.rareItemByID.values():
        dist = start.distToSq(rare.station.system)
        if maxLySq > 0 and dist > maxLySq:
            continue

        row = ResultRow()
        row.rare = rare
        row.dist = math.sqrt(dist)
        results.rows.append(row)

    if cmdenv.sortByPrice:
        results.rows.sort(key=lambda row: row.dist)
        results.rows.sort(key=lambda row: row.rare.costCr, reverse=True)
    else:
        # order by distance, cost
        results.rows.sort(key=lambda row: row.rare.costCr, reverse=True)
        results.rows.sort(key=lambda row: row.dist)

    limit = cmdenv.limit or 0
    if limit > 0:
        results.rows = results.rows[:limit]

    return results

#######################################################################
## Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

    longestStnName = max(results.rows, key=lambda result: len(result.rare.station.name())).rare.station
    longestStnNameLen = len(longestStnName.name())
    longestRareName = max(results.rows, key=lambda result: len(result.rare.dbname)).rare
    longestRareNameLen = len(longestRareName.dbname)

    rowFmt = RowFormat()
    rowFmt.addColumn('Station', '<', longestStnNameLen,
            key=lambda row: row.rare.station.name())
    rowFmt.addColumn('Rare', '<', longestRareNameLen,
            key=lambda row: row.rare.name())
    rowFmt.addColumn('Cost', '>', 10, 'n',
            key=lambda row: row.rare.costCr)
    rowFmt.addColumn('DistLy', '>', 6, '.2f',
            key=lambda row: row.dist)
    rowFmt.addColumn('Alloc', '>', 6, 'n',
            key=lambda row: row.rare.maxAlloc)

    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(rowFmt.format(row))

