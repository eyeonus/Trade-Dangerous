from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from collections import defaultdict
from commands.commandenv import ResultRow
from commands.exceptions import *
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from formatting import RowFormat, ColumnFormat, max_len
from tradedb import TradeDB, AmbiguityError

import math

ITEM_MODE = "Item"
SHIP_MODE = "Ship"

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
        nargs='+',
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
            '--one-stop', '-1',
            help='Only list stations that carry all items listed.',
            action='store_true',
            dest='oneStop',
        ),
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

def get_lookup_list(cmdenv, tdb):
    # Credit: http://stackoverflow.com/a/952952/257645
    # Turns [['a'],['b','c']] => ['a', 'b', 'c']
    names = [
        name for names in cmdenv.name for name in names.split(',')
    ]
    queries, mode = {}, None
    for name in names:
        if mode is not SHIP_MODE:
            try:
                item = tdb.lookupItem(name)
                cmdenv.DEBUG0("Looking up item {} (#{})", item.name(), item.ID)
                queries[item.ID] = item
                mode = ITEM_MODE
                continue
            except LookupError:
                if mode is ITEM_MODE:
                    raise CommandLineError(
                        "Unrecognized item: {}".format(name)
                    )
                pass

        try:
            ship = tdb.lookupShip(name)
            cmdenv.DEBUG0("Looking up ship {} (#{})", ship.name(), ship.ID)
            queries[ship.ID] = ship
            mode = SHIP_MODE
            continue
        except LookupError:
            if not mode:
                raise CommandLineError(
                    "Unrecognized item/ship: {}".format(name)
                )
            raise CommandLineError(
                "Unrecognized ship: {}".format(name)
            )

    return queries, mode


def sql_query(cmdenv, tdb, queries, mode):
    # Constraints
    idList = ','.join(str(ID) for ID in queries.keys())
    if mode is SHIP_MODE:
        tables = "ShipVendor AS ss"
        constraints = ["(ship_id IN ({}))".format(idList)]
        columns = [
            'ss.ship_id',
            'ss.station_id',
            '0',
            '1',
            "0",
            ]
        bindValues = []
    else:
        tables = "StationSelling AS ss"
        constraints = ["(item_id IN ({}))".format(idList)]
        columns = [
            'ss.item_id',
            'ss.station_id',
            'ss.price',
            'ss.units',
            "JULIANDAY('NOW') - JULIANDAY(ss.modified)",
            ]
        bindValues = []

    # Additional constraints in ITEM_MODE
    if mode is ITEM_MODE:
        if cmdenv.quantity:
            constraints.append("(units = -1 or units >= ?)")
            bindValues.append(cmdenv.quantity)
        if cmdenv.lt:
            constraints.append("(price < ?)")
            bindValues.append(cmdenv.lt)
        if cmdenv.gt:
            constraints.append("(price > ?)")
            bindValues.append(cmdenv.gt)

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
    return tdb.query(stmt, bindValues)
    

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    if cmdenv.lt and cmdenv.gt:
        if cmdenv.lt <= cmdenv.gt:
            raise CommandLineError("--gt must be lower than --lt")

    # Find out what we're looking for.
    queries, mode = get_lookup_list(cmdenv, tdb)
    cmdenv.DEBUG0("{} query: {}", mode, queries.values())

    # Summarize
    results.summary = ResultRow()
    results.summary.mode = mode
    results.summary.queries = queries
    results.summary.oneStop = cmdenv.oneStop

    # In single mode with detail enabled, add average reports.
    # Thus if you're looking up "algae" or the "asp", it'll
    # tell you the average/ship cost.
    singleMode = len(queries) == 1
    if singleMode and cmdenv.detail:
        first = list(queries.values())[0]
        if mode is SHIP_MODE:
            results.summary.avg = first.cost
        else:
            avgPrice = tdb.query("""
                    SELECT CAST(AVG(ss.price) AS INT)
                      FROM StationSelling AS ss
                     WHERE ss.item_id = ?
            """, [first.ID]).fetchone()[0]
            results.summary.avg = avgPrice

    # System-based search
    nearSystem = cmdenv.nearSystem
    if nearSystem:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy
        distanceFn = nearSystem.distanceTo
    else:
        distanceFn = None

    oneStopMode = cmdenv.oneStop
    padSize = cmdenv.padSize

    stations = defaultdict(list)
    stationByID = tdb.stationByID

    cur = sql_query(cmdenv, tdb, queries, mode)
    for (ID, stationID, priceCr, stock, age) in cur:
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
        row.item = queries[ID]
        row.price = priceCr
        row.stock = stock
        row.age = age
        stationRows = stations[stationID]
        stationRows.append(row)
        if oneStopMode and len(stationRows) < len(queries):
            continue
        results.rows.extend(stationRows)

    if not results.rows:
        if oneStopMode and len(stations):
            raise NoDataError("No one-stop stations found")
        raise NoDataError("No available items found")

    if oneStopMode and singleMode:
        results.rows.sort(key=lambda result: result.item.name())
    results.rows.sort(key=lambda result: result.station.name())
    if cmdenv.sortByStock:
        results.summary.sort = "Stock"
        results.rows.sort(key=lambda result: result.price)
        results.rows.sort(key=lambda result: result.stock, reverse=True)
    else:
        if not oneStopMode:
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
    mode = results.summary.mode
    singleMode = len(results.summary.queries) == 1
    maxStnLen = max_len(results.rows, key=lambda row: row.station.name())

    stnRowFmt = RowFormat()
    stnRowFmt.addColumn('Station', '<', maxStnLen,
            key=lambda row: row.station.name())
    if not singleMode:
        maxItmLen = max_len(results.rows, key=lambda row: row.item.name())
        stnRowFmt.addColumn(results.summary.mode, '<', maxItmLen,
                key=lambda row: row.item.name()
        )
    if mode is not SHIP_MODE:
        stnRowFmt.addColumn('Cost', '>', 10, 'n',
                key=lambda row: row.price)
        stnRowFmt.addColumn('Stock', '>', 10,
                key=lambda row: '{:n}'.format(row.stock) if row.stock >= 0 else '?')

    if cmdenv.nearSystem:
        stnRowFmt.addColumn('DistLy', '>', 6, '.2f',
                key=lambda row: row.dist)

    if mode is not SHIP_MODE:
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

    if singleMode and cmdenv.detail:
        print("{:{lnl}} {:>10n}".format(
                "-- Ship Cost" if mode is SHIP_MODE else "-- Average",
                results.summary.avg,
                lnl=maxStnLen,
        ))
