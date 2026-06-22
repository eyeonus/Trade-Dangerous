from __future__ import annotations
import math
from collections import defaultdict

from sqlalchemy import literal, text
from sqlalchemy.orm import joinedload

from tradedangerous.db import orm_models as orm
from tradedangerous.db.station_types import (
    fleet_carrier_state, settlement_state,
)
from tradedangerous.db.utils import age_in_days
from tradedangerous.formatting import RowFormat, max_len
from tradedangerous import formatting

from .commandenv import Needs, ResultRow
from .exceptions import CommandLineError, NoDataError
from .parsing import (
    AvoidPlacesArgument, BlackMarketSwitch, FleetCarrierArgument, MutuallyExclusiveGroup,
    NoPlanetSwitch, SettlementArgument, PadSizeArgument, ParseArgument, PlanetaryArgument,
)


# TODO: Add UPGRADE_MODE
ITEM_MODE = "Item"
SHIP_MODE = "Ship"

def _fleet_state(station: orm.Station) -> str:
    return fleet_carrier_state(station.type_id)


def _settlement_state(station: orm.Station) -> str:
    return settlement_state(station.type_id)


def _dist_from_star(station: orm.Station) -> str:
    ls = station.ls_from_star
    if not ls:
        return '?'
    if ls < 1000:
        return f'{ls:n}'
    if ls < 10000:
        return f'{ls / 1000:.2f}K'
    if ls < 1000000:
        return f'{int(ls / 1000):n}K'
    return f'{ls / (365*24*60*60):.2f}ly'


######################################################################
# Parser config

help = 'Find places to buy a given item within range of a given station.'
name = 'buy'
epilog = None
needs = Needs.RESOLVER
arguments = (
    ParseArgument(
        'name',
        help = 'Items or Ships to look for. Omit when using --rare.',
        type = str,
        nargs = '*',
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
        '--rare',
        help = 'Limit to rare commodities only.',
        action = 'store_true',
        default = False,
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
        dest = 'ly',
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
    SettlementArgument(),
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
        name for names in cmdenv.name for name in names.split(',') if name
    ]
    if not names:
        if cmdenv.rare:
            return {}, ITEM_MODE
        raise CommandLineError("No item or ship specified")
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
                category = tdb.lookup_category(name)
                for item in category.items:
                    names.append(item.name)
                    queries[item.item_id] = item
                mode = ITEM_MODE
                continue
            except LookupError:
                pass

            # Item names secondary.
            try:
                item = tdb.lookup_item(name)
                cmdenv.DEBUG0("Looking up item {} (#{})", item.name, item.item_id)
                queries[item.item_id] = item
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
            ship = tdb.lookup_ship(name)
            cmdenv.DEBUG0("Looking up ship {} (#{})", ship.name, ship.ship_id)
            queries[ship.ship_id] = ship
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

    if cmdenv.rare and mode is SHIP_MODE:
        raise CommandLineError("--rare cannot be used with ships")

    return queries, mode

def _near_station_ids(cmdenv, tdb) -> list[int] | None:
    """
    Return station IDs inside the --near bounding box.

    This deliberately forces the first major cut to be spatial. The later
    Python sphere check remains authoritative; this only narrows the database
    probe to stations plausibly within range before StationItem/ShipVendor is
    queried.
    """
    near_system = cmdenv.nearSystem
    if not near_system:
        return None

    max_ly = cmdenv.ly if cmdenv.ly is not None else cmdenv.maxSystemLinkLy
    rows = (
        tdb.session.query(orm.Station.station_id)
        .join(orm.System, orm.System.system_id == orm.Station.system_id)
        .filter(orm.System.pos_x.between(
            near_system.pos_x - max_ly,
            near_system.pos_x + max_ly,
        ))
        .filter(orm.System.pos_y.between(
            near_system.pos_y - max_ly,
            near_system.pos_y + max_ly,
        ))
        .filter(orm.System.pos_z.between(
            near_system.pos_z - max_ly,
            near_system.pos_z + max_ly,
        ))
        .all()
    )
    return [r.station_id for r in rows]

def sql_query(cmdenv, tdb, queries, mode):
    """
    Backend-portable query builder.
    - Composes through SQLAlchemy rather than handwritten SQL.
    - Materializes rows eagerly to avoid closed-cursor issues.
    - Preserves return shapes:
        * Ship:   (ship_id, station_id, cost, 1)
        * Item:   (item_id, station_id, supply_price, supply_units, age)
    """
    ids = list(queries.keys())
    near_station_ids = _near_station_ids(cmdenv, tdb)
    if near_station_ids == []:
        return []

    def build_query(station_id_chunk: list[int] | None = None):
        if mode is SHIP_MODE:
            query = (
                tdb.session.query(
                    orm.ShipVendor.ship_id,
                    orm.ShipVendor.station_id,
                    orm.Ship.cost,
                    literal(1),
                )
                .join(orm.Ship, orm.Ship.ship_id == orm.ShipVendor.ship_id)
                .filter(orm.ShipVendor.ship_id.in_(ids))
            )
            if station_id_chunk is not None:
                query = query.filter(
                    orm.ShipVendor.station_id.in_(station_id_chunk)
                )
            return query.distinct()

        age_expr = age_in_days(tdb.session, orm.StationItem.modified)
        query = tdb.session.query(
            orm.StationItem.item_id,
            orm.StationItem.station_id,
            orm.StationItem.supply_price,
            orm.StationItem.supply_units,
            age_expr.label("data_age"),
        )
        if cmdenv.rare:
            query = query.join(
                orm.Item,
                orm.Item.item_id == orm.StationItem.item_id,
            )
        if station_id_chunk is not None:
            query = query.filter(
                orm.StationItem.station_id.in_(station_id_chunk)
            )
        query = query.filter(orm.StationItem.supply_price > 0)
        if ids:
            query = query.filter(orm.StationItem.item_id.in_(ids))
        if cmdenv.rare:
            query = query.filter(orm.Item.rare_station_id.isnot(None))
            query = query.filter(orm.StationItem.supply_units > 0)
        if cmdenv.maxAge:
            query = query.filter(age_expr <= cmdenv.maxAge)
        if cmdenv.supply:
            query = query.filter(orm.StationItem.supply_units >= cmdenv.supply)
        if cmdenv.lt:
            query = query.filter(orm.StationItem.supply_price < cmdenv.lt)
        if cmdenv.gt:
            query = query.filter(orm.StationItem.supply_price > cmdenv.gt)
        return query.distinct()

    if near_station_ids is None:
        query = build_query()
        cmdenv.DEBUG0("SQL: {}", query)
        return query.all()

    rows = []
    for offset in range(0, len(near_station_ids), 900):
        station_id_chunk = near_station_ids[offset:offset + 900]
        query = build_query(station_id_chunk)
        cmdenv.DEBUG0("SQL: {}", query)
        rows.extend(query.all())

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

    if cmdenv.rare and cmdenv.oneStop and not queries:
        raise CommandLineError("--one-stop requires one or more named items when using --rare")

    avoidSystems = {s for s in cmdenv.avoidPlaces if isinstance(s, orm.System)}
    avoidStations = {s for s in cmdenv.avoidPlaces if isinstance(s, orm.Station)}

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
            avg_val = tdb.session.execute(
                text("""
                    SELECT AVG(si.supply_price) AS avg_price
                      FROM StationItem AS si
                     WHERE si.item_id = :item_id AND si.supply_price > 0
                """),
                {"item_id": first.item_id},
            ).scalar()
            results.summary.avg = int(avg_val or 0)

    # System-based search
    nearSystem = cmdenv.nearSystem
    if nearSystem:
        maxLy = cmdenv.ly if cmdenv.ly is not None else cmdenv.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy
        nx, ny, nz = nearSystem.pos_x, nearSystem.pos_y, nearSystem.pos_z
        distanceFn = lambda sys: math.sqrt(  # noqa: E731
            (nx - sys.pos_x) ** 2 + (ny - sys.pos_y) ** 2 + (nz - sys.pos_z) ** 2
        )
    else:
        distanceFn = None

    oneStopMode = cmdenv.oneStop
    padSize = cmdenv.padSize
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    settlement = cmdenv.settlement
    wantNoPlanet = cmdenv.noPlanet
    wantBlackMarket = cmdenv.blackMarket
    mls = cmdenv.maxLs

    # Fetch raw SQL results then bulk-load the matching stations.
    raw_rows = sql_query(cmdenv, tdb, queries, mode)

    station_ids = list({r[1] for r in raw_rows})
    station_by_id = {}
    for offset in range(0, len(station_ids), 900):
        station_id_chunk = station_ids[offset:offset + 900]
        _stations = (
            tdb.session.query(orm.Station)
            .options(joinedload(orm.Station.system))
            .filter(orm.Station.station_id.in_(station_id_chunk))
            .all()
        )
        station_by_id.update({s.station_id: s for s in _stations})

    stations = defaultdict(list)

    for row_data in raw_rows:
        if mode is SHIP_MODE:
            ID, stationID, price, units = row_data
            data_age = None
        else:
            ID, stationID, price, units, data_age = row_data
        station = station_by_id.get(stationID)
        if station is None:
            continue
        if padSize and station.max_pad_size not in padSize:
            continue
        if planetary and station.planetary not in planetary:
            continue
        if fleet and _fleet_state(station) not in fleet:
            continue
        if settlement and _settlement_state(station) not in settlement:
            continue
        if wantNoPlanet and station.planetary != 'N':
            continue
        if wantBlackMarket and station.blackmarket != 'Y':
            continue
        if station in avoidStations:
            continue
        if station.system in avoidSystems:
            continue

        item = queries.get(ID)
        if item is None:
            try:
                item = tdb.item_by_id(ID)
            except LookupError:
                continue

        row = ResultRow()
        row.station = station
        if mls:
            if station.ls_from_star > mls:
                continue
        if distanceFn:
            distance = distanceFn(row.station.system)
            if distance > maxLy:
                continue
            row.dist = distance
        row.item = item
        row.price = price
        row.units = units
        row.age = f"{data_age:7.2f}" if data_age is not None else "-"
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
        results.rows.sort(key = lambda result: result.item.name)
    results.rows.sort(key = lambda result: result.station.dbname())
    if cmdenv.sortByUnits:
        results.summary.sort = "units"
        results.rows.sort(key = lambda result: result.price)
        results.rows.sort(key = lambda result: result.units, reverse = True)
    else:
        if not oneStopMode:
            results.summary.sort = "Price"
            results.rows.sort(key = lambda result: result.units, reverse = True)
            results.rows.sort(
                key=lambda result: (
                    result.price if result.price is not None else float("inf")
                )
            )
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
    maxStnLen = max_len(results.rows, key = lambda row: row.station.dbname())

    stnRowFmt = RowFormat()
    stnRowFmt.addColumn('Station', '<', maxStnLen,
            key = lambda row: row.station.dbname())
    if not singleMode:
        maxItmLen = max_len(results.rows, key = lambda row: row.item.dbname(cmdenv.detail))
        stnRowFmt.addColumn(results.summary.mode, '<', maxItmLen,
                key = lambda row: row.item.dbname(cmdenv.detail)
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
            key = lambda row: _dist_from_star(row.station))
    stnRowFmt.addColumn('B/mkt', '>', 4,
            key = lambda row: formatting.marketStates[row.station.blackmarket])
    stnRowFmt.addColumn("Pad", '>', '3',
            key = lambda row: formatting.padSizes[row.station.max_pad_size])
    stnRowFmt.addColumn("Plt", '>', '3',
            key = lambda row: formatting.planetStates[row.station.planetary])
    stnRowFmt.addColumn("Flc", '>', '3',
            key = lambda row: formatting.fleetStates[_fleet_state(row.station)])
    stnRowFmt.addColumn("Stl", '>', '3',
            key = lambda row: formatting.settlementStates[_settlement_state(row.station)])

    if not cmdenv.quiet:
        heading, underline = stnRowFmt.heading()
        print(heading, underline, sep = '\n')

    for row in results.rows:
        print(stnRowFmt.format(row))

    if singleMode and cmdenv.detail:
        msg = "-- Ship Cost" if mode is SHIP_MODE else "-- Average"
        print(f"{msg:{maxStnLen}} {results.summary.avg:>10n}")
