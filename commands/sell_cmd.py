from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import *
import math

######################################################################
# Parser config

help='Find places to sell a given item within range of a given station.'
name='sell'
epilog=None
wantsTradeDB=True
arguments = [
    ParseArgument('item', help='Name of item you want to sell.', type=str),
]
switches = [
    ParseArgument('--near',
            help='Find buyers within jump range of this system.',
            type=str
        ),
    ParseArgument('--ly-per',
            help='Maximum light years per jump.',
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

    item = tdb.lookupItem(cmdenv.item)
    cmdenv.DEBUG0("Looking up item {} (#{})", item.name(), item.ID)

    results.summary = ResultRow()
    results.summary.item = item

    if cmdenv.detail:
        avgPrice = tdb.query("""
                SELECT CAST(AVG(sb.price) AS INT)
                  FROM StationSelling AS sb
                 WHERE sb.item_id = ?
        """, [item.ID]).fetchone()[0]
        results.summary.avg = avgPrice

    # Constraints
    tables = "StationBuying AS sb"
    constraints = [ "(item_id = {})".format(item.ID) ]
    columns = [ 'sb.station_id', 'sb.price', 'sb.units' ]
    bindValues = [ ]

    if cmdenv.quantity:
        constraints.append("(units = -1 or units >= ?)")
        bindValues.append(cmdenv.quantity)

    nearSystem = cmdenv.nearSystem
    distances = dict()
    if nearSystem:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy

        cmdenv.DEBUG0("Searching within {}ly of {}", maxLy, nearSystem.name())
        tables += (
                " INNER JOIN StationLink AS sl"
                " ON (sl.rhs_station_id = sb.station_id)"
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
    for (stationID, priceCr, demand, dist) in cur:
        row = ResultRow()
        row.station = stationByID[stationID]
        cmdenv.DEBUG2("{} {}cr {} units", row.station.name(), priceCr, demand)
        if nearSystem:
           row.dist = dist
        row.price = priceCr
        row.demand = demand
        results.rows.append(row)

    if not results.rows:
        raise NoDataError("No available items found")

    results.summary.sort = "Price"
    results.rows.sort(key=lambda result: result.demand, reverse=True)
    results.rows.sort(key=lambda result: result.price, reverse=True)
    if nearSystem and not cmdenv.sortByPrice:
        results.summary.sort = "Dist"
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
    if cmdenv.detail:
        stnRowFmt.addColumn('Demand', '>', 10,
                key=lambda row: '{:n}'.format(row.demand) if row.demand >= 0 else 'unknown')
    if cmdenv.nearSystem:
        stnRowFmt.addColumn('Dist', '>', 6, '.2f',
                key=lambda row: row.dist)

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
