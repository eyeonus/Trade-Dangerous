from .commandenv import ResultRow
from .exceptions import CommandLineError
from .parsing import (
    ParseArgument, MutuallyExclusiveGroup,
)
from ..formatting import RowFormat


######################################################################
# Parser config

help='Lists items bought/sold at a given station.'
name='market'
epilog=None
wantsTradeDB=True
arguments = [
    ParseArgument(
        'origin',
        help='Station being queried.',
        metavar='STATIONNAME',
        type=str,
    ),
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument(
            '--buying', '-B',
            help='Show items station is buying',
            action='store_true',
        ),
        ParseArgument(
            '--selling', '-S',
            help='Show items station is selling',
            action='store_true',
        ),
    ),
]

######################################################################
# Perform query and populate result set


def render_units(units, level):
    if level == 0:
        return '-'
    if units < 0:
        return '?'
    levelNames = { -1: '?', 1: 'L', 2: 'M', 3: 'H' }
    return "{:n}{}".format(units, levelNames[level])


def run(results, cmdenv, tdb):
    origin = cmdenv.startStation
    if not origin.itemCount:
        raise CommandLineError(
            "No trade data available for {}".format(origin.name())
        )
    
    buying, selling = cmdenv.buying, cmdenv.selling
    
    results.summary = ResultRow()
    results.summary.origin = origin
    results.summary.buying = cmdenv.buying
    results.summary.selling = cmdenv.selling
    
    tdb.getAverageSelling()
    tdb.getAverageBuying()
    cur = tdb.query("""
        SELECT  item_id,
                demand_price, demand_units, demand_level,
                supply_price, supply_units, supply_level,
                JULIANDAY('now') - JULIANDAY(modified)
          FROM  StationItem
         WHERE  station_id = ?
    """, [origin.ID])
    
    for row in cur:
        it = iter(row)
        item = tdb.itemByID[next(it)]
        row = ResultRow()
        row.item = item
        row.buyCr = int(next(it) or 0)
        row.avgBuy = tdb.avgBuying.get(item.ID, 0)
        units, level = int(next(it) or 0), int(next(it) or 0)
        row.buyUnits = units
        row.buyLevel = level
        row.demand = render_units(units, level)
        if not selling:
            hasBuy = (row.buyCr or units or level)
        else:
            hasBuy = False
        row.sellCr = int(next(it) or 0)
        row.avgSell = tdb.avgSelling.get(item.ID, 0)
        units, level = int(next(it) or 0), int(next(it) or 0)
        row.sellUnits = units
        row.sellLevel = level
        row.supply = render_units(units, level)
        if not buying:
            hasSell = (row.sellCr or units or level)
        else:
            hasSell = False
        row.age = float(next(it) or 0)
        
        if hasBuy or hasSell:
            results.rows.append(row)
    
    if not results.rows:
        raise CommandLineError("No items found")
    
    results.rows.sort(key=lambda row: row.item.dbname)
    results.rows.sort(key=lambda row: row.item.category.dbname)
    
    return results

#######################################################################
## Transform result set into output


def render(results, cmdenv, tdb):
    longest = max(results.rows, key=lambda row: len(row.item.name()))
    longestLen = len(longest.item.name())
    longestDmd = max(results.rows, key=lambda row: len(row.demand)).demand
    longestSup = max(results.rows, key=lambda row: len(row.supply)).supply
    dmdLen = max(len(longestDmd), len("Demand"))
    supLen = max(len(longestSup), len("Supply"))
    
    showCategories = (cmdenv.detail > 0)
    
    rowFmt = RowFormat()
    if showCategories:
        rowFmt.prefix = '    '
    
    sellPred = lambda row: row.sellCr != 0 and row.supply != '-'    # noqa: E731
    buyPred = lambda row: row.buyCr != 0 and row.demand != '-'      # noqa: E731
    
    rowFmt.addColumn('Item', '<', longestLen,
            key=lambda row: row.item.name())
    if not cmdenv.selling:
        rowFmt.addColumn('Buying', '>', 7, 'n',
            key=lambda row: row.buyCr,
            pred=buyPred)
        if cmdenv.detail:
            rowFmt.addColumn('Avg', '>', 7, 'n',
            key=lambda row: row.avgBuy,
            pred=buyPred)
        if cmdenv.detail > 1:
            rowFmt.addColumn('Demand', '>', dmdLen,
                key=lambda row: row.demand,
                pred=buyPred)
    if not cmdenv.buying:
        rowFmt.addColumn('Selling', '>', 7, 'n',
            key=lambda row: row.sellCr,
            pred=sellPred)
        if cmdenv.detail:
            rowFmt.addColumn('Avg', '>', 7, 'n',
            key=lambda row: row.avgSell,
            pred=sellPred)
        rowFmt.addColumn('Supply', '>', supLen,
            key=lambda row: row.supply,
            pred=sellPred)
    if cmdenv.detail:
        rowFmt.addColumn('Age/Days', '>', 7, '.2f',
        key=lambda row: row.age)
    
    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')
    
    lastCat = None
    for row in results.rows:
        if showCategories and row.item.category is not lastCat:
            print("+{}".format(row.item.category.name()))
            lastCat = row.item.category
        print(rowFmt.format(row))
