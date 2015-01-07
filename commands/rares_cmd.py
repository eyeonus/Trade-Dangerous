from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.exceptions import *
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from tradedb import TradeDB

import math

######################################################################
# Parser config

help='Find rares near your current local.'
name='rares'
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
            default=180,
            dest='maxLyPer',
    ),
    ParseArgument('--limit',
            help='Maximum number of results to list.',
            default=None,
            type=int,
    ),
    ParseArgument('--pad-size', '-p',
            help='Limit the padsize to this ship size (S,M,L or ? for unkown).',
            metavar='PADSIZES',
            dest='padSize',
    ),
    ParseArgument('--price-sort', '-P',
            help='(When using --near) Sort by price not distance',
            action='store_true',
            default=False,
            dest='sortByPrice',
    ),
    ParseArgument('--reverse', '-r',
            help='Reverse the list.',
            action='store_true',
            default=False,
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

    padSize = cmdenv.padSize
    for rare in tdb.rareItemByID.values():
        if padSize and not rare.station.checkPadSize(padSize):
            continue
        dist = start.distToSq(rare.station.system)
        if maxLySq > 0 and dist > maxLySq:
            continue

        row = ResultRow()
        row.rare = rare
        row.dist = math.sqrt(dist)
        results.rows.append(row)

    if not results:
        print("No matches found.")
        return None

    if cmdenv.sortByPrice:
        results.rows.sort(key=lambda row: row.dist)
        results.rows.sort(key=lambda row: row.rare.costCr, reverse=True)
    else:
        results.rows.sort(key=lambda row: row.rare.costCr, reverse=True)
        results.rows.sort(key=lambda row: row.dist)

    if cmdenv.reverse:
        results.rows.reverse()

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
    rowFmt.addColumn("StnLs", '>', 10,
            key=lambda row: row.rare.station.distFromStar())
    rowFmt.addColumn('B/mkt', '>', 4,
            key=lambda row: \
                    TradeDB.marketStates[row.rare.station.blackMarket]
    )
    rowFmt.addColumn("Pad", '>', '3',
            key=lambda row: \
                    TradeDB.padSizes[row.rare.station.maxPadSize]
    )

    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(rowFmt.format(row))

