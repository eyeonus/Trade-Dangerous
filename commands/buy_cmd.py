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
    cmdenv.DEBUG(0, "Looking up item {} (#{})", item.name(), item.ID)

    # Constraints
    constraints = [ "(item_id = {})".format(item.ID), "buy_from > 0", "stock != 0" ]
    bindValues = [ ]

    if cmdenv.quantity:
        constraints.append("(stock = -1 or stock >= ?)")
        bindValues.append(cmdenv.quantity)

    results.summary = ResultRow()
    results.summary.item = item

    nearSystem = cmdenv.nearSystem
    distances = dict()
    if nearSystem:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy

        cmdenv.DEBUG(0, "Searching within {}ly of {}", maxLy, nearSystem.name())

        def genStationIDs():
            nonlocal distances
            for (sys, dist) in tdb.genSystemsInRange(
                            nearSystem, maxLy, includeSelf=True):
                cmdenv.DEBUG(2, "Checking stations in {}", sys.name())
                hadStation = False
                for station in sys.stations:
                    if station.itemCount > 0:
                        yield str(station.ID)
                        hadStation = True
                if hadStation:
                    distances[sys.ID] = math.sqrt(dist)

        stationList = "station_id IN ({})".format(
                                ','.join(genStationIDs()))
        if not distances:
            raise NoDataError(
                        "There are NO sales entries at ANY stations "
                            "within {}ly of {}".format(item.name()))

        constraints.append(stationList)

    whereClause = ' AND '.join(constraints)
    stmt = """
               SELECT station_id, buy_from, stock
                 FROM Price
                WHERE {}
           """.format(whereClause)
    cmdenv.DEBUG(0, 'SQL: {}', stmt)
    cur = tdb.query(stmt, bindValues)

    stationByID = tdb.stationByID
    for (stationID, priceCr, stock) in cur:
        row = ResultRow()
        row.station = stationByID[stationID]
        cmdenv.DEBUG(2, "{} {}cr {} units", row.station.name(), priceCr, stock)
        if nearSystem:
           row.dist = distances[row.station.system.ID]
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

    print(results.rows)

    return None

#######################################################################
## Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

    ### TODO: Implement

#   maxStnNameLen = len(max(results, key=lambda result: len(result.station.dbname) + len(result.station.system.dbname) + 1).station.name())
#   cmdenv.printHeading("{station:<{maxStnLen}} {cost:>10} {stock:>10} {dist:{distFmt}}".format(
#                           station="Station", cost="Cost", stock="Stock",
#                           dist="Ly" if near else "",
#                           maxStnLen=maxStnNameLen,
#                           distFmt=">6" if near else ""
#       ))
#   for result in results:
#       print("{station:<{maxStnLen}} {cost:>10n} {stock:>10} {dist:{distFmt}}".format(
#               station=result.station.name(),
#               cost=result.cost,
#               stock="{:n}".format(result.stock) if result.stock > 0 else "",
#               dist=result.dist if near else "",
#               maxStnLen=maxStnNameLen,
#               distFmt=">6.2f" if near else ""
#           ))
