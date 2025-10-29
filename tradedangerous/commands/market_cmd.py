from .commandenv import ResultRow
from .exceptions import CommandLineError
from .parsing import (
    ParseArgument, MutuallyExclusiveGroup,
)
from ..formatting import RowFormat
from sqlalchemy import select, table, column
from sqlalchemy.orm import Session


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
    # Lazy import to avoid any import-time tangles elsewhere.
    from tradedangerous.db.utils import age_in_days
    
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
    
    # Precompute averages (unchanged)
    tdb.getAverageSelling()
    tdb.getAverageBuying()
    
    # --- Backend-neutral query using SQLAlchemy Core + age_in_days ---
    si = table(
        "StationItem",
        column("item_id"),
        column("station_id"),
        column("demand_price"),
        column("demand_units"),
        column("demand_level"),
        column("supply_price"),
        column("supply_units"),
        column("supply_level"),
        column("modified"),
    )
    
    # Build session bound to current engine (needed by age_in_days)
    session = Session(bind=tdb.engine)
    
    stmt = (
        select(
            si.c.item_id,
            si.c.demand_price, si.c.demand_units, si.c.demand_level,
            si.c.supply_price, si.c.supply_units, si.c.supply_level,
            age_in_days(session, si.c.modified).label("age_days"),
        )
        .where(si.c.station_id == origin.ID)
    )
    
    rows = session.execute(stmt).fetchall()
    session.close()
    
    for r in rows:
        it = iter(r)
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
        
        age_days = next(it)
        row.age = float(age_days or 0.0)
        
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
