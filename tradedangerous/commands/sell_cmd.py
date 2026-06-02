from __future__ import annotations
import math

from sqlalchemy import text
from sqlalchemy.orm import joinedload

from tradedangerous.db import orm_models as orm
from tradedangerous.db.station_types import (
    fleet_carrier_state, settlement_state,
)
from tradedangerous.db.utils import age_in_days
from tradedangerous.formatting import RowFormat, max_len
from . import display_labels

from .commandenv import Needs, ResultRow
from .exceptions import CommandLineError, NoDataError
from .parsing import (
    AvoidPlacesArgument, BlackMarketSwitch, FleetCarrierArgument,
    MutuallyExclusiveGroup, NoPlanetSwitch, SettlementArgument,
    PadSizeArgument, ParseArgument, PlanetaryArgument,
)


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

help = 'Find places to sell a given item within range of a given station.'
name = 'sell'
epilog = None
needs = Needs.RESOLVER
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
        help='Maximum age (in days) of trade data to use.',
        metavar='DAYS',
        type=float,
        dest='maxAge',
    ),
    AvoidPlacesArgument(),
    PadSizeArgument(),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    SettlementArgument(),
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


def _near_station_ids(cmdenv, tdb) -> list[int] | None:
    """
    Return station IDs inside the --near bounding box.

    Forces the first major cut to be spatial before probing StationItem.
    The Python sphere check in run() remains authoritative.
    """
    near_system = cmdenv.nearSystem
    if not near_system:
        return None

    max_ly = cmdenv.maxLyPer or cmdenv.maxSystemLinkLy
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


def sql_query(cmdenv, tdb, item_id):
    near_station_ids = _near_station_ids(cmdenv, tdb)
    if near_station_ids == []:
        return []

    age_expr = age_in_days(tdb.session, orm.StationItem.modified)

    def build_query(station_id_chunk=None):
        query = tdb.session.query(
            orm.StationItem.station_id,
            orm.StationItem.demand_price,
            orm.StationItem.demand_units,
            age_expr.label("data_age"),
        ).filter(
            orm.StationItem.item_id == item_id,
            orm.StationItem.demand_price > 0,
        )
        if station_id_chunk is not None:
            query = query.filter(
                orm.StationItem.station_id.in_(station_id_chunk)
            )
        if cmdenv.demand:
            query = query.filter(orm.StationItem.demand_units >= cmdenv.demand)
        if cmdenv.maxAge:
            query = query.filter(age_expr <= cmdenv.maxAge)
        if cmdenv.lt:
            query = query.filter(orm.StationItem.demand_price < cmdenv.lt)
        if cmdenv.gt:
            query = query.filter(orm.StationItem.demand_price > cmdenv.gt)
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

    item = tdb.lookup_item(cmdenv.item)
    cmdenv.DEBUG0("Looking up item {} (#{})", item.name, item.item_id)

    avoidSystems = {s for s in cmdenv.avoidPlaces if isinstance(s, orm.System)}
    avoidStations = {s for s in cmdenv.avoidPlaces if isinstance(s, orm.Station)}

    results.summary = ResultRow()
    results.summary.item = item
    results.summary.avoidSystems = avoidSystems
    results.summary.avoidStations = avoidStations

    if cmdenv.detail:
        avg_val = tdb.session.execute(
            text("""
                SELECT AVG(si.demand_price)
                  FROM StationItem AS si
                 WHERE si.item_id = :item_id AND si.demand_price > 0
            """),
            {"item_id": item.item_id},
        ).scalar()
        results.summary.avg = int(avg_val or 0)

    nearSystem = cmdenv.nearSystem
    if nearSystem:
        maxLy = cmdenv.maxLyPer or cmdenv.maxSystemLinkLy
        results.summary.near = nearSystem
        results.summary.ly = maxLy
        nx, ny, nz = nearSystem.pos_x, nearSystem.pos_y, nearSystem.pos_z
        distanceFn = lambda sys: math.sqrt(  # noqa: E731
            (nx - sys.pos_x) ** 2 + (ny - sys.pos_y) ** 2 + (nz - sys.pos_z) ** 2
        )
    else:
        distanceFn = None

    padSize = cmdenv.padSize
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    settlement = cmdenv.settlement
    wantNoPlanet = cmdenv.noPlanet
    wantBlackMarket = cmdenv.blackMarket

    raw_rows = sql_query(cmdenv, tdb, item.item_id)

    station_ids = list({r[0] for r in raw_rows})
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

    for (stationID, priceCr, demand, data_age) in raw_rows:
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

        row = ResultRow()
        row.station = station
        if distanceFn:
            distance = distanceFn(row.station.system)
            if distance > maxLy:
                continue
            row.dist = distance
        row.price = priceCr
        row.demand = demand
        row.age = f"{data_age:7.2f}" if data_age is not None else "-"
        results.rows.append(row)

    if not results.rows:
        if nearSystem:
            raise NoDataError(
                "No buyers for {} found within {:.0f}ly of {}".format(
                    item.name, maxLy, nearSystem.name
                )
            )
        raise NoDataError("No buyers for {} found".format(item.name))

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
# Transform result set into output

def render(results, cmdenv, tdb):
    maxStnLen = max_len(results.rows, key=lambda row: row.station.dbname())

    stnRowFmt = RowFormat()
    stnRowFmt.addColumn('Station', '<', maxStnLen,
            key=lambda row: row.station.dbname())
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
            key=lambda row: _dist_from_star(row.station))
    stnRowFmt.addColumn('B/mkt', '>', 4,
            key=lambda row: display_labels.marketStates[row.station.blackmarket])
    stnRowFmt.addColumn("Pad", '>', '3',
            key=lambda row: display_labels.padSizes[row.station.max_pad_size])
    stnRowFmt.addColumn("Plt", '>', '3',
            key=lambda row: display_labels.planetStates[row.station.planetary])
    stnRowFmt.addColumn("Flc", '>', '3',
            key=lambda row: display_labels.fleetStates[_fleet_state(row.station)])
    stnRowFmt.addColumn("Stl", '>', '3',
            key=lambda row: display_labels.settlementStates[_settlement_state(row.station)])

    if not cmdenv.quiet:
        heading, underline = stnRowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(stnRowFmt.format(row))

    if cmdenv.detail:
        print("{:{lnl}} {:>10n}".format(
            "-- Average",
            results.summary.avg,
            lnl=maxStnLen,
        ))
