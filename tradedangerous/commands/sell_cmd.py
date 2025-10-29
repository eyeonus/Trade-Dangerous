from .commandenv import ResultRow
from .exceptions import CommandLineError, NoDataError
from .parsing import (
    AvoidPlacesArgument, BlackMarketSwitch, FleetCarrierArgument,
    MutuallyExclusiveGroup, NoPlanetSwitch, OdysseyArgument,
    PadSizeArgument, ParseArgument, PlanetaryArgument,
)
from ..tradedb import TradeDB, System, Station
from ..formatting import RowFormat
from sqlalchemy import text


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
    ParseArgument(
        '--demand', '--quantity',
        help='Limit to stations known to have at least this much demand.',
        default=0,
        type=int,
    ),
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
    ParseArgument('--age', '--max-days-old', '-MD',
        help = 'Maximum age (in days) of trade data to use.',
        metavar = 'DAYS',
        type = float,
        dest = 'maxAge',
    ),
    AvoidPlacesArgument(),
    PadSizeArgument(),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    OdysseyArgument(),
    BlackMarketSwitch(),
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

def run(results, cmdenv, tdb: TradeDB):
    """
    Backend-neutral implementation:
      - Use SQLAlchemy text() with NAMED binds (':param') instead of '?'.
      - Eagerly materialize rows via engine.connect().execute(...).fetchall()
        to avoid closed-cursor errors when iterating later.
      - Preserve all existing filters, sorting, and output fields.
    """
    
    if cmdenv.lt and cmdenv.gt:
        if cmdenv.lt <= cmdenv.gt:
            raise CommandLineError("--gt must be lower than --lt")
    
    item = tdb.lookupItem(cmdenv.item)
    cmdenv.DEBUG0("Looking up item {} (#{})", item.name(), item.ID)
    
    avoidSystems = {s for s in cmdenv.avoidPlaces if isinstance(s, System)}
    avoidStations = {s for s in cmdenv.avoidPlaces if isinstance(s, Station)}
    
    results.summary = ResultRow()
    results.summary.item = item
    results.summary.avoidSystems = avoidSystems
    results.summary.avoidStations = avoidStations
    
    # Detail: average demand price for this item (portable named bind)
    if cmdenv.detail:
        with tdb.engine.connect() as conn:
            avg_val = conn.execute(
                text("""
                    SELECT AVG(si.demand_price)
                      FROM StationItem AS si
                     WHERE si.item_id = :item_id AND si.demand_price > 0
                """),
                {"item_id": item.ID},
            ).scalar()
        results.summary.avg = int(avg_val or 0)
    
    # Build the main query with named binds
    columns = "si.station_id, si.demand_price, si.demand_units"
    where = ["si.item_id = :item_id", "si.demand_price > 0"]
    params = {"item_id": item.ID}
    
    if cmdenv.demand:
        where.append("si.demand_units >= :demand")
        params["demand"] = cmdenv.demand
    if cmdenv.lt:
        where.append("si.demand_price < :lt")
        params["lt"] = cmdenv.lt
    if cmdenv.gt:
        where.append("si.demand_price > :gt")
        params["gt"] = cmdenv.gt
    
    stmt = f"""
        SELECT DISTINCT {columns}
          FROM StationItem AS si
         WHERE {' AND '.join(where)}
    """
    cmdenv.DEBUG0('SQL: {} ; params={}', stmt, params)
    
    # Execute and eagerly fetch rows
    with tdb.engine.connect() as conn:
        cur_rows = conn.execute(text(stmt), params).fetchall()
    
    stationByID = tdb.stationByID
    padSize = cmdenv.padSize
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    odyssey = cmdenv.odyssey
    wantNoPlanet = cmdenv.noPlanet
    wantBlackMarket = cmdenv.blackMarket
    
    # System-based search
    nearSystem = cmdenv.nearSystem
    if nearSystem:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy
        distanceFn = nearSystem.distanceTo
    else:
        distanceFn = None
    
    for (stationID, priceCr, demand) in cur_rows:
        station = stationByID[stationID]
        if padSize and not station.checkPadSize(padSize):
            continue
        if planetary and not station.checkPlanetary(planetary):
            continue
        if fleet and not station.checkFleet(fleet):
            continue
        if odyssey and not station.checkOdyssey(odyssey):
            continue
        if wantNoPlanet and station.planetary != 'N':
            continue
        if wantBlackMarket and station.blackMarket != 'Y':
            continue
        if station in avoidStations:
            continue
        if station.system in avoidSystems:
            continue
        maxAge, stnAge = cmdenv.maxAge, station.dataAge or float("inf")
        if maxAge and stnAge > maxAge:
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
        row.age = station.itemDataAgeStr
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
    
    stnRowFmt.addColumn('Age/days', '>', 7,
            key=lambda row: row.age)
    stnRowFmt.addColumn('StnLs', '>', 10,
                key=lambda row: row.station.distFromStar())
    stnRowFmt.addColumn('B/mkt', '>', 4,
            key=lambda row: TradeDB.marketStates[row.station.blackMarket])
    stnRowFmt.addColumn("Pad", '>', '3',
            key=lambda row: TradeDB.padSizes[row.station.maxPadSize])
    stnRowFmt.addColumn("Plt", '>', '3',
            key=lambda row: TradeDB.planetStates[row.station.planetary])
    stnRowFmt.addColumn("Flc", '>', '3',
            key=lambda row: TradeDB.fleetStates[row.station.fleet])
    stnRowFmt.addColumn("Ody", '>', '3',
            key=lambda row: TradeDB.odysseyStates[row.station.odyssey])
    
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
