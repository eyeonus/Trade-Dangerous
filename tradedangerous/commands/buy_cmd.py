from __future__ import annotations
from collections import defaultdict
from .commandenv import ResultRow
from .exceptions import CommandLineError, NoDataError
from ..formatting import RowFormat, max_len
from ..tradedb import Station, System, TradeDB
from .parsing import (
    AvoidPlacesArgument, BlackMarketSwitch, FleetCarrierArgument, MutuallyExclusiveGroup,
    NoPlanetSwitch, OdysseyArgument, PadSizeArgument, ParseArgument, PlanetaryArgument,
)
from sqlalchemy import text

# TODO: Add UPGRADE_MODE
ITEM_MODE = "Item"
SHIP_MODE = "Ship"

######################################################################
# Parser config

help = 'Find places to buy a given item within range of a given station.'
name = 'buy'
epilog = None
wantsTradeDB = True
arguments = (
    ParseArgument(
        'name',
        help = 'Items or Ships to look for.',
        type = str,
        nargs = '+',
    ),
)
switches = (
    ParseArgument(
        '--supply', '--quantity',
        help = 'Limit to stations known to have at least this much supply.',
        default = 0,
        type = int,
    ),
    ParseArgument(
        '--near',
        help = 'Find sellers within jump range of this system.',
        type = str
    ),
    ParseArgument(
        '--ly',
        help = '[Requires --near] Systems within this range of --near.',
        default = None,
        dest = 'maxLyPer',
        metavar = 'N.NN',
        type = float,
    ),
    ParseArgument(
        '--limit',
        help = 'Maximum number of results to list.',
        default = None,
        type = int,
    ),
    AvoidPlacesArgument(),
    ParseArgument('--age', '--max-days-old', '-MD',
        help = 'Maximum age (in days) of trade data to use.',
        metavar = 'DAYS',
        type = float,
        dest = 'maxAge',
    ),
    PadSizeArgument(),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    OdysseyArgument(),
    BlackMarketSwitch(),
    MutuallyExclusiveGroup(
        ParseArgument(
            '--one-stop', '-1',
            help = 'Only list stations that carry all items listed.',
            action = 'store_true',
            dest = 'oneStop',
        ),
        ParseArgument(
            '--price-sort', '-P',
            help = '(When using --near) Sort by price not distance',
            action = 'store_true',
            default = False,
            dest = 'sortByPrice',
        ),
        ParseArgument(
            '--units-sort', '-S',
            help = 'Sort by available units followed by price',
            action = 'store_true',
            default = False,
            dest = 'sortByUnits',
        ),
    ),
    ParseArgument(
        '--gt',
        help = 'Limit to prices above Ncr',
        metavar = 'N',
        dest = 'gt',
        type = "credits",
    ),
    ParseArgument(
        '--lt',
        help = 'Limit to prices below Ncr',
        metavar = 'N',
        dest = 'lt',
        type = "credits",
    ),
    ParseArgument('--ls-max',
        help='Only consider stations up to this many ls from their star.',
        metavar='LS',
        dest='maxLs',
        type=int,
        default=0,
    ),
)


def get_lookup_list(cmdenv, tdb):
    # Credit: http://stackoverflow.com/a/952952/257645
    # Turns [['a'],['b','c']] => ['a', 'b', 'c']
    names = [
        name for names in cmdenv.name for name in names.split(',')
    ]
    # We only support searching for one type of purchase a time: ship or item.
    # Our first match is open-ended, but once we have matched one type of
    # thing, the remaining arguments are all sourced from the same pool.
    # Thus: [food, cobra, metals] is illegal but [metals, hydrogen] is legal.
    mode = None
    
    queries = {}
    for name in names:
        if mode is not SHIP_MODE:
            # Either no mode selected yet or we are in ITEM_MODE.
            # Consider categories first.
            try:
                category = tdb.lookupCategory(name)
                for item in category.items:
                    names.append(item.name())
                    queries[item.ID] = item
                mode = ITEM_MODE
                continue
            except LookupError:
                pass
            
            # Item names secondary.
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
        
        # Either no mode selected yet or we are in SHIP_MODE.
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
    """
    Backend-portable query builder.
    - Uses named binds (':param') instead of SQLite '?'.
    - Materializes rows eagerly to avoid closed-cursor issues.
    - Preserves return shapes:
        * Ship:   (ship_id, station_id, cost, 1)
        * Item:   (item_id, station_id, supply_price, supply_units)
    """
    ids = list(queries.keys())
    
    # Build a stable, named-parameter IN(...) list
    params = {}
    placeholders = []
    for i, val in enumerate(ids):
        key = f"id{i}"
        placeholders.append(f":{key}")
        params[key] = val
    id_list_sql = ",".join(placeholders)
    
    if mode is SHIP_MODE:
        columns = "s.ship_id, s.station_id, sh.cost, 1"
        tables = "ShipVendor AS s JOIN Ship AS sh ON sh.ship_id = s.ship_id"
        constraints = [f"(s.ship_id IN ({id_list_sql}))"]
    else:
        columns = "s.item_id, s.station_id, s.supply_price, s.supply_units"
        tables = "StationItem AS s"
        constraints = [
            f"(s.item_id IN ({id_list_sql}))",
            "(s.supply_price > 0)",  # preserves index intent across backends
        ]
        if cmdenv.supply:
            constraints.append("(s.supply_units >= :supply)")
            params["supply"] = cmdenv.supply
        if cmdenv.lt:
            constraints.append("(s.supply_price < :lt)")
            params["lt"] = cmdenv.lt
        if cmdenv.gt:
            constraints.append("(s.supply_price > :gt)")
            params["gt"] = cmdenv.gt
    
    where_clause = " AND ".join(constraints)
    stmt = f"SELECT DISTINCT {columns} FROM {tables} WHERE {where_clause}"
    cmdenv.DEBUG0('SQL: {} ; params={}', stmt, params)
    
    # Eagerly fetch to avoid closed cursor when iterating later.
    with tdb.engine.connect() as conn:
        result = conn.execute(text(stmt), params)
        rows = result.fetchall()
    return rows



######################################################################
# Perform query and populate result set


def run(results, cmdenv, tdb):
    if cmdenv.lt and cmdenv.gt:
        if cmdenv.lt <= cmdenv.gt:
            raise CommandLineError("--gt must be lower than --lt")
    
    # Find out what we're looking for.
    queries, mode = get_lookup_list(cmdenv, tdb)
    cmdenv.DEBUG0("{} query: {}", mode, queries.values())
    
    avoidSystems = {s for s in cmdenv.avoidPlaces if isinstance(s, System)}
    avoidStations = {s for s in cmdenv.avoidPlaces if isinstance(s, Station)}
    
    # Summarize
    results.summary = ResultRow()
    results.summary.mode = mode
    results.summary.queries = queries
    results.summary.oneStop = cmdenv.oneStop
    results.summary.avoidSystems = avoidSystems
    results.summary.avoidStations = avoidStations
    
    # In single mode with detail enabled, add average reports.
    # Thus if you're looking up "algae" or the "asp", it'll
    # tell you the average/ship cost.
    singleMode = len(queries) == 1
    if singleMode and cmdenv.detail:
        first = list(queries.values())[0]
        if mode is SHIP_MODE:
            results.summary.avg = first.cost
        else:
            # Portable AVG with named bind; eager scalar fetch
            with tdb.engine.connect() as conn:
                avg_val = conn.execute(
                    text("""
                        SELECT AVG(si.supply_price) AS avg_price
                          FROM StationItem AS si
                         WHERE si.item_id = :item_id AND si.supply_price > 0
                    """),
                    {"item_id": first.ID},
                ).scalar()
            results.summary.avg = int(avg_val or 0)
    
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
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    odyssey = cmdenv.odyssey
    wantNoPlanet = cmdenv.noPlanet
    wantBlackMarket = cmdenv.blackMarket
    mls = cmdenv.maxLs
    
    stations = defaultdict(list)
    stationByID = tdb.stationByID
    
    cur = sql_query(cmdenv, tdb, queries, mode)
    for (ID, stationID, price, units) in cur:
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
        if mls:
            distanceFromStar = station.lsFromStar
            if distanceFromStar > mls:
                continue
        if distanceFn:
            distance = distanceFn(row.station.system)
            if distance > maxLy:
                continue
            row.dist = distance
        row.item = queries[ID]
        row.price = price
        row.units = units
        row.age = station.itemDataAgeStr
        if oneStopMode:
            stationRows = stations[stationID]
            stationRows.append(row)
            if len(stationRows) >= len(queries):
                results.rows.extend(stationRows)
        else:
            results.rows.append(row)
    
    if not results.rows:
        if oneStopMode and len(stations):
            raise NoDataError("No one-stop stations found")
        raise NoDataError("No available items found")
    
    if oneStopMode and not singleMode:
        results.rows.sort(key = lambda result: result.item.name())
    results.rows.sort(key = lambda result: result.station.name())
    if cmdenv.sortByUnits:
        results.summary.sort = "units"
        results.rows.sort(key = lambda result: result.price)
        results.rows.sort(key = lambda result: result.units, reverse = True)
    else:
        if not oneStopMode:
            results.summary.sort = "Price"
            results.rows.sort(key = lambda result: result.units, reverse = True)
            results.rows.sort(key = lambda result: result.price)
        if nearSystem and not cmdenv.sortByPrice:
            results.summary.sort = "Ly"
            results.rows.sort(key = lambda result: result.dist)
    
    limit = cmdenv.limit or 0
    if limit > 0:
        results.rows = results.rows[:limit]
    
    return results



#######################################################################
# # Transform result set into output


def render(results, cmdenv, tdb):
    mode = results.summary.mode
    singleMode = len(results.summary.queries) == 1
    maxStnLen = max_len(results.rows, key = lambda row: row.station.name())
    
    stnRowFmt = RowFormat()
    stnRowFmt.addColumn('Station', '<', maxStnLen,
            key = lambda row: row.station.name())
    if not singleMode:
        maxItmLen = max_len(results.rows, key = lambda row: row.item.name(cmdenv.detail))
        stnRowFmt.addColumn(results.summary.mode, '<', maxItmLen,
                key = lambda row: row.item.name(cmdenv.detail)
        )
    if mode is not SHIP_MODE or not singleMode:
        stnRowFmt.addColumn('Cost', '>', 10, 'n',
                key = lambda row: row.price)
    if mode is not SHIP_MODE:
        stnRowFmt.addColumn('Units', '>', 10,
                key = lambda row: '{:n}'.format(row.units) if row.units >= 0 else '?')
    
    if cmdenv.nearSystem:
        stnRowFmt.addColumn('DistLy', '>', 6, '.2f',
                key = lambda row: row.dist)
    
    if mode is not SHIP_MODE:
        stnRowFmt.addColumn('Age/days', '>', 7,
                key = lambda row: row.age)
    stnRowFmt.addColumn("StnLs", '>', 10,
            key = lambda row: row.station.distFromStar())
    stnRowFmt.addColumn('B/mkt', '>', 4,
            key = lambda row: TradeDB.marketStates[row.station.blackMarket])
    stnRowFmt.addColumn("Pad", '>', '3',
            key = lambda row: TradeDB.padSizes[row.station.maxPadSize])
    stnRowFmt.addColumn("Plt", '>', '3',
            key = lambda row: TradeDB.planetStates[row.station.planetary])
    stnRowFmt.addColumn("Flc", '>', '3',
            key = lambda row: TradeDB.fleetStates[row.station.fleet])
    stnRowFmt.addColumn("Ody", '>', '3',
            key = lambda row: TradeDB.odysseyStates[row.station.odyssey])
    
    if not cmdenv.quiet:
        heading, underline = stnRowFmt.heading()
        print(heading, underline, sep = '\n')
    
    for row in results.rows:
        print(stnRowFmt.format(row))
    
    if singleMode and cmdenv.detail:
        msg = "-- Ship Cost" if mode is SHIP_MODE else "-- Average"
        print(f"{msg:{maxStnLen}} {results.summary.avg:>10n}")
