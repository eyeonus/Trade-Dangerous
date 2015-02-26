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
    ParseArgument(
        'name',
        help='Items or Ships to look for.',
        type=str
    ),
]
switches = [
    ParseArgument(
        '--quantity',
        help='Require at least this quantity.',
        default=0,
        type=int,
    ),
    ParseArgument(
        '--near',
        help='Find sellers within jump range of this system.',
        type=str
    ),
    ParseArgument(
        '--ly',
        help='[Requires --near] Systems within this range of --near.',
        default=None,
        dest='maxLyPer',
        metavar='N.NN',
        type=float,
    ),
    ParseArgument(
        '--limit',
        help='Maximum number of results to list.',
        default=None,
        type=int,
    ),
    ParseArgument(
        '--pad-size', '-p',
        help='Limit the padsize to this ship size (S,M,L or ? for unkown).',
        metavar='PADSIZES',
        dest='padSize',
    ),
    MutuallyExclusiveGroup(
        ParseArgument(
            '--price-sort', '-P',
            help='(When using --near) Sort by price not distance',
            action='store_true',
            default=False,
            dest='sortByPrice',
        ),
        ParseArgument(
            '--stock-sort', '-S',
            help='Sort by stock followed by price',
            action='store_true',
            default=False,
            dest='sortByStock',
        ),
    ),
    ParseArgument(
        '--gt',
        help='Limit to prices above Ncr',
        metavar='N',
        dest='gt',
        type=int,
    ),
    ParseArgument(
        '--lt',
        help='Limit to prices below Ncr',
        metavar='N',
        dest='lt',
        type=int,
    ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    if cmdenv.lt and cmdenv.gt:
        if cmdenv.lt <= cmdenv.gt:
            raise CommandLineError("--gt must be lower than --lt")

    try:
        item = tdb.lookupItem(cmdenv.name)
        cmdenv.DEBUG0("Looking up item {} (#{})", item.name(), item.ID)
    except LookupError:
        item = tdb.lookupShip(cmdenv.name)
        cmdenv.DEBUG0("Looking up ship {} (#{})", item.name(), item.ID)
        cmdenv.ship = True

    results.summary = ResultRow()
    results.summary.item = item

    if cmdenv.detail:
        if cmdenv.ship:
            results.summary.avg = item.cost
        else:
            avgPrice = tdb.query("""
                    SELECT CAST(AVG(ss.price) AS INT)
                      FROM StationSelling AS ss
                     WHERE ss.item_id = ?
            """, [item.ID]).fetchone()[0]
            results.summary.avg = avgPrice

    # Constraints
    if cmdenv.ship:
        tables = "ShipVendor AS ss"
        constraints = [ "(ship_id = {})".format(item.ID) ]
        columns = [
            'ss.station_id',
            '0',
            '1',
            "0",
            ]
        bindValues = [ ]
    else:
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

    padSize = cmdenv.padSize

    stationByID = tdb.stationByID
    for (stationID, priceCr, stock, age) in cur:
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
    if not cmdenv.ship:
        stnRowFmt.addColumn('Cost', '>', 10, 'n',
                key=lambda row: row.price)
        stnRowFmt.addColumn('Stock', '>', 10,
                key=lambda row: '{:n}'.format(row.stock) if row.stock >= 0 else '?')

    if cmdenv.nearSystem:
        stnRowFmt.addColumn('DistLy', '>', 6, '.2f',
                key=lambda row: row.dist)

    if not cmdenv.ship:
        stnRowFmt.addColumn('Age/days', '>', 7, '.2f',
                key=lambda row: row.age)
    stnRowFmt.addColumn("StnLs", '>', 10,
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
                "-- Average" if not cmdenv.ship else "-- Ship Cost",
                results.summary.avg,
                lnl=longestNameLen,
        ))
