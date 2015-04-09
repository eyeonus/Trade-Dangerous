from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.exceptions import *
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from tradedb import TradeDB

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
    ParseArgument('--pad-size', '-p',
            help='Limit the padsize to this ship size (S,M,L or ? for unkown).',
            metavar='PADSIZES',
            dest='padSize',
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
    ParseArgument('--gt',
            help='Limit to prices above Ncr',
            metavar='N',
            dest='gt',
            type="credits",
    ),
    ParseArgument('--lt',
            help='Limit to prices below Ncr',
            metavar='N',
            dest='lt',
            type="credits",
    ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    if cmdenv.lt and cmdenv.gt:
        if cmdenv.lt <= cmdenv.gt:
            raise CommandLineError("--gt must be lower than --lt")

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
    columns = [
            'sb.station_id',
            'sb.price',
            'sb.units',
            "JULIANDAY('NOW') - JULIANDAY(sb.modified)",
    ]
    bindValues = [ ]

    if cmdenv.quantity:
        constraints.append("(units = -1 or units >= ?)")
        bindValues.append(cmdenv.quantity)

    if cmdenv.lt:
        constraints.append("(price < ?)")
        bindValues.append(cmdenv.lt)
    if cmdenv.gt:
        constraints.append("(price > ?)")
        bindValues.append(cmdenv.gt)

    nearSystem = cmdenv.nearSystem
    if nearSystem:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy
        distanceFn = nearSystem.distanceTo
    else:
        distanceFn = None

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
    padSize = cmdenv.padSize
    for (stationID, priceCr, demand, age) in cur:
        station = stationByID[stationID]
        if padSize and not station.checkPadSize(padSize):
            continue
        row = ResultRow()
        row.station = station
        if distanceFn:
            distance = distanceFn(row.station.system)
            if distance > maxLy:
                continue
            row.dist = distance
        row.price = priceCr
        row.demand = demand
        row.age = age
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
                key=lambda row: '{:n}'.format(row.demand) if row.demand >= 0 else '?')
    if cmdenv.nearSystem:
        stnRowFmt.addColumn('DistLy', '>', 6, '.2f',
                key=lambda row: row.dist)

    stnRowFmt.addColumn('Age/days', '>', 7, '.2f',
            key=lambda row: row.age)
    stnRowFmt.addColumn('StnLs', '>', 10,
                key=lambda row: row.station.distFromStar())
    stnRowFmt.addColumn('B/mkt', '>', 4,
            key=lambda row: TradeDB.marketStates[row.station.blackMarket])
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
