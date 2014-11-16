from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import *
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
    ParseArgument('--ly-per',
            help='Maximum light years per jump.',
            default=None,
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
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

    # Constraints
    tables = "StationSelling AS ss"
    constraints = [ "(item_id = {})".format(item.ID) ]
    columns = [ 'ss.station_id', 'ss.price', 'ss.units' ]
    bindValues = [ ]

    if cmdenv.quantity:
        constraints.append("(units = -1 or units >= ?)")
        bindValues.append(cmdenv.quantity)

    results.summary = ResultRow()
    results.summary.item = item

    nearSystem = cmdenv.nearSystem
    distances = dict()
    if nearSystem:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy

        cmdenv.DEBUG0("Searching within {}ly of {}", maxLy, nearSystem.name())
        tables += (
                " INNER JOIN StationLink AS sl"
                " ON (sl.rhs_station_id = ss.station_id)"
                )
        columns.append('sl.dist')
        constraints.append("(lhs_system_id = {})".format(
                nearSystem.ID
                ))
        constraints.append("(dist <= {})".format(
                maxLy
                ))
    else:
        columns += [ '0' ]

    whereClause = ' AND '.join(constraints)
    stmt = """
               SELECT {columns}
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
    for (stationID, priceCr, stock, dist) in cur:
        row = ResultRow()
        row.station = stationByID[stationID]
        cmdenv.DEBUG2("{} {}cr {} units", row.station.name(), priceCr, stock)
        if nearSystem:
           row.dist = dist
        row.price = priceCr
        row.stock = stock
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
            results.summary.sort = "Dist"
            results.rows.sort(key=lambda result: result.dist)

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
            key=lambda row: '{:n}'.format(row.stock) if row.stock >= 0 else 'unknown')
    if cmdenv.nearSystem:
        stnRowFmt.addColumn('Dist', '>', 6, '.2f',
                key=lambda row: row.dist)

    if not cmdenv.quiet:
        heading, underline = stnRowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(stnRowFmt.format(row))
