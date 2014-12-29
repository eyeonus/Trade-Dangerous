from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.exceptions import *
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from tradedb import TradeDB

import math

######################################################################
# Parser config

help='Find places to buy a given item within range of a given station.'
name='buy'
epilog=None
wantsTradeDB=True
arguments = [
    ParseArgument('item', help='Name of item to query.', type=str),
]
switches = [
    ParseArgument('--quantity',
            help='Require at least this quantity.',
            default=0,
            type=int,
    ),
    ParseArgument('--near',
            help='Find sellers within jump range of this system.',
            type=str
    ),
    ParseArgument('--ly',
            help='[Requires --near] Systems within this range of --near.',
            default=None,
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
    ),
    ParseArgument('--limit',
            help='Maximum number of results to list.',
            default=None,
            type=int,
    ),
    MutuallyExclusiveGroup(
        ParseArgument('--price-sort', '-P',
                help='(When using --near) Sort by price not distance',
                action='store_true',
                default=False,
                dest='sortByPrice',
        ),
        ParseArgument('--stock-sort', '-S',
            help='Sort by stock followed by price',
            action='store_true',
            default=False,
            dest='sortByStock',
        ),
    ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    item = tdb.lookupItem(cmdenv.item)
    cmdenv.DEBUG0("Looking up item {} (#{})", item.name(), item.ID)

    results.summary = ResultRow()
    results.summary.item = item

    if cmdenv.detail:
        avgPrice = tdb.query("""
                SELECT CAST(AVG(ss.price) AS INT)
                  FROM StationSelling AS ss
                 WHERE ss.item_id = ?
        """, [item.ID]).fetchone()[0]
        results.summary.avg = avgPrice

    # Constraints
    tables = "StationSelling AS ss"
    constraints = [ "(item_id = {})".format(item.ID) ]
    columns = [
            'ss.station_id',
            'ss.price',
            'ss.units',
            "JULIANDAY('NOW') - JULIANDAY(ss.modified)",
    ]
    bindValues = [ ]

    if cmdenv.quantity:
        constraints.append("(units = -1 or units >= ?)")
        bindValues.append(cmdenv.quantity)

    nearSystem = cmdenv.nearSystem
    if nearSystem:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy

        cmdenv.DEBUG0("Searching within {}ly of {}", maxLy, nearSystem.name())
        systemRanges = {
            system: dist
            for system, dist in tdb.genSystemsInRange(
                    nearSystem,
                    maxLy,
                    includeSelf=True,
            )
        }
        tables += (
                " INNER JOIN Station AS stn"
                " ON (stn.station_id = ss.station_id)"
        )
        constraints.append("(stn.system_id IN ({}))".format(
            ",".join(['?'] * len(systemRanges))
        ))
        bindValues += list(system.ID for system in systemRanges.keys())

    whereClause = ' AND '.join(constraints)
    stmt = """
               SELECT DISTINCT {columns}
                 FROM {tables}
                WHERE {where}
           """.format(
                    columns=','.join(columns),
                    tables=tables,
                    where=whereClause
                    )
    cmdenv.DEBUG0('SQL: {}', stmt)
    cur = tdb.query(stmt, bindValues)

    stationByID = tdb.stationByID
    for (stationID, priceCr, stock, age) in cur:
        row = ResultRow()
        row.station = stationByID[stationID]
        cmdenv.DEBUG2("{} {}cr {} units", row.station.name(), priceCr, stock)
        if nearSystem:
           row.dist = systemRanges[row.station.system]
        row.price = priceCr
        row.stock = stock
        row.age = age
        results.rows.append(row)

    if not results.rows:
        raise NoDataError("No available items found")

    if cmdenv.sortByStock:
        results.summary.sort = "Stock"
        results.rows.sort(key=lambda result: result.price)
        results.rows.sort(key=lambda result: result.stock, reverse=True)
    else:
        results.summary.sort = "Price"
        results.rows.sort(key=lambda result: result.stock, reverse=True)
        results.rows.sort(key=lambda result: result.price)
        if nearSystem and not cmdenv.sortByPrice:
            results.summary.sort = "Ly"
            results.rows.sort(key=lambda result: result.dist)

    limit = cmdenv.limit or 0
    if limit > 0:
        results.rows = results.rows[:limit]

    return results

#######################################################################
## Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

    longestNamed = max(results.rows, key=lambda result: len(result.station.name()))
    longestNameLen = len(longestNamed.station.name())

    stnRowFmt = RowFormat()
    stnRowFmt.addColumn('Station', '<', longestNameLen,
            key=lambda row: row.station.name())
    stnRowFmt.addColumn('Cost', '>', 10, 'n',
            key=lambda row: row.price)
    stnRowFmt.addColumn('Stock', '>', 10,
            key=lambda row: '{:n}'.format(row.stock) if row.stock >= 0 else '?')

    if cmdenv.nearSystem:
        stnRowFmt.addColumn('DistLy', '>', 6, '.2f',
                key=lambda row: row.dist)

    stnRowFmt.addColumn('Age/days', '>', 7, '.2f',
            key=lambda row: row.age)
    stnRowFmt.addColumn("StnLs", '>', 10,
            key=lambda row: row.station.distFromStar())
    stnRowFmt.addColumn("Pad", '>', '3',
            key=lambda row: TradeDB.padSizes[row.station.maxPadSize])

    if not cmdenv.quiet:
        heading, underline = stnRowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(stnRowFmt.format(row))

    if cmdenv.detail:
        print("{:{lnl}} {:>10n}".format(
                "-- Average",
                results.summary.avg,
                lnl=longestNameLen,
        ))
