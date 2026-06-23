from __future__ import annotations

from math import ceil, sqrt

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from .commandenv import Needs, ResultRow
from .exceptions import CommandLineError
from .parsing import (
    AvoidPlacesArgument, FleetCarrierArgument,
    SettlementArgument, PadSizeArgument, ParseArgument,
    PlanetaryArgument,
)

from tradedangerous import TradeException
from tradedangerous import formatting
from tradedangerous.db import orm_models as orm
from tradedangerous.db.station_types import fleet_carrier_state, settlement_state
from tradedangerous.db.utils import age_in_days
from tradedangerous.formatting import RowFormat, ColumnFormat
from tradedangerous.planner.failures import NoReachableRoute
from tradedangerous.planner.reachability import plan_jump_path, reachable_systems_from
from tradedangerous.planner.run_result import ResolvedSystem


######################################################################
# Parser config

help = 'Calculate a route between two systems.'
name = 'nav'
epilog = None
needs = Needs.RESOLVER
arguments = [
    ParseArgument('starting', help='System to start from', type=str),
    ParseArgument('ending', help='System to end at', type=str),
]
switches = [
    ParseArgument('--ly-per',
        help='Maximum light years per jump.',
        dest='maxLyPer',
        metavar='N.NN',
        type=float,
    ),
    AvoidPlacesArgument(),
    ParseArgument('--via',
        help='Require specified systems/stations to be en-route (in order).',
        action='append',
        metavar='PLACE[,PLACE,...]',
    ),
    ParseArgument('--stations', '-S',
        help='Include station details.',
        action='store_true',
    ),
    PadSizeArgument(),
    PlanetaryArgument(),
    FleetCarrierArgument(),
    SettlementArgument(),
]


######################################################################
# Helpers

class NoRouteError(TradeException):
    """ Exception denoting specifically a route could not be found. """


def validateRunArgumentsFast(cmdenv):
    # A jump range is mandatory and there is no sensible one-size default, so
    # demand it during preflight. Zero is not a valid range (you cannot move).
    if cmdenv.maxLyPer is None:
        raise CommandLineError("Missing '--ly-per'")
    if cmdenv.maxLyPer <= 0:
        raise CommandLineError("--ly-per must be greater than zero.")


def _as_system(place):
    """A nav waypoint is a system; a station waypoint routes through its system."""
    return place.system if isinstance(place, orm.Station) else place


def _to_resolved(system) -> ResolvedSystem:
    """Convert an ORM System into the planner's lightweight ResolvedSystem DTO."""
    return ResolvedSystem(
        system_id=system.system_id,
        name=system.name,
        dbname=system.name,
        x=system.pos_x,
        y=system.pos_y,
        z=system.pos_z,
    )


def _distance(a: ResolvedSystem, b: ResolvedSystem) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    dz = a.z - b.z
    return sqrt(dx * dx + dy * dy + dz * dz)


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


def _plan_leg(session, src, dst, *, max_ly, avoid_ids):
    """Find a jump path from src to dst at max_ly per jump.

    nav has no user-facing jump cap, but plan_jump_path needs one to size its
    search bubble. Start from the theoretical minimum (straight-line / range),
    then grow the bound geometrically until a path is found. Declare the
    destination unreachable once growing the bound stops reaching new systems --
    the source's connected component is exhausted. A fresh bubble cache is used
    per depth because the planner keys its cache on the source id alone, not the
    radius, so reuse across depths would consult an undersized bubble.
    """
    straight = _distance(src, dst)
    bound = max(1, ceil(straight / max_ly))
    prev_reached = -1
    while True:
        cache: dict = {}
        try:
            return plan_jump_path(
                src, dst,
                max_jumps_per_hop=bound,
                max_ly_per_jump=max_ly,
                session=session,
                bubble_cache=cache,
                avoid_system_ids=avoid_ids,
            )
        except NoReachableRoute:
            reached = reachable_systems_from(
                session, src,
                max_jumps_per_hop=bound,
                max_ly_per_jump=max_ly,
                bubble_cache=cache,
                avoid_system_ids=avoid_ids,
            )
            if len(reached) == prev_reached:
                raise NoRouteError(
                    "No route from {} to {} at {:g}ly per jump.".format(
                        src.name, dst.name, max_ly
                    )
                )
            prev_reached = len(reached)
            bound *= 2


def _load_route_stations(session, cmdenv, sys_ids):
    """Fetch the route systems' stations (command-owned, not via the planner).

    Returns a per-system total station count (unfiltered, for the detail
    'Stations' column) and -- only when --stations is set -- the filtered station
    rows with data age and item count for display. The candidate set is already
    narrowed to the route's systems, so the display filters run in Python.
    """
    station_count: dict = {}
    stations_by_system: dict = {}
    if not sys_ids:
        return stations_by_system, station_count
    
    all_stations = []
    for start in range(0, len(sys_ids), 900):
        chunk = sys_ids[start:start + 900]
        all_stations.extend(
            session.query(orm.Station)
            .options(joinedload(orm.Station.system))
            .filter(orm.Station.system_id.in_(chunk))
            .all()
        )
    
    for stn in all_stations:
        station_count[stn.system_id] = station_count.get(stn.system_id, 0) + 1
    
    if not cmdenv.stations:
        return stations_by_system, station_count
    
    age_by_stn: dict = {}
    stn_ids = [s.station_id for s in all_stations]
    for start in range(0, len(stn_ids), 900):
        chunk = stn_ids[start:start + 900]
        for row in (
            session.query(
                orm.StationItem.station_id,
                func.count().label('item_count'),
                func.avg(
                    age_in_days(session, orm.StationItem.modified)
                ).label('data_age'),
            )
            .filter(orm.StationItem.station_id.in_(chunk))
            .group_by(orm.StationItem.station_id)
            .all()
        ):
            age_by_stn[row.station_id] = (row.data_age, row.item_count)
    
    padSize = cmdenv.padSize
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    settlement = cmdenv.settlement
    for stn in all_stations:
        if padSize and stn.max_pad_size not in padSize:
            continue
        if planetary and stn.planetary not in planetary:
            continue
        if fleet and _fleet_state(stn) not in fleet:
            continue
        if settlement and _settlement_state(stn) not in settlement:
            continue
        data_age, item_count = age_by_stn.get(stn.station_id, (None, 0))
        age_str = f'{data_age:.2f}' if data_age is not None else '-'
        stations_by_system.setdefault(stn.system_id, []).append(
            ResultRow(station=stn, age=age_str, item_count=item_count)
        )
    
    return stations_by_system, station_count


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    cmdenv = results.cmdenv
    tdb = cmdenv.tdb
    session = tdb.session
    
    src = _to_resolved(_as_system(cmdenv.origPlace))
    dst = _to_resolved(_as_system(cmdenv.destPlace))
    max_ly = cmdenv.maxLyPer
    
    cmdenv.DEBUG0("Route from {} to {} with max {}ly per jump.",
                  src.name, dst.name, max_ly)
    
    # Waypoints: src -> via... -> dst. --avoid removes whole systems from the
    # jump graph (avoided stations do not constrain system-level routing).
    waypoints = [src]
    for via in (cmdenv.viaPlaces or []):
        waypoints.append(_to_resolved(_as_system(via)))
    waypoints.append(dst)
    
    avoid_ids = frozenset(
        place.system_id for place in cmdenv.avoidPlaces
        if isinstance(place, orm.System)
    )
    
    # A required waypoint must not also be avoided. The leg anchor is exempt --
    # you may leave the system you start in -- but routing to or through an
    # avoided system is contradictory, so reject it before planning rather than
    # letting it slip through for a one-jump leg (where plan_jump_path returns
    # before the avoid-filtered bubble loads) yet fail for a multi-jump one.
    clashes = [w for w in waypoints[1:] if w.system_id in avoid_ids]
    if clashes:
        raise CommandLineError(
            "Cannot route to or through an avoided system: {}".format(
                ', '.join(w.name for w in clashes)
            )
        )
    
    # Plan each consecutive leg and stitch, dropping the shared junction system.
    route_systems: list = []
    for hop_src, hop_dst in zip(waypoints, waypoints[1:]):
        leg = _plan_leg(
            session, hop_src, hop_dst, max_ly=max_ly, avoid_ids=avoid_ids
        ).systems
        if route_systems:
            leg = leg[1:]
        route_systems.extend(leg)
    
    results.summary = ResultRow(fromSys=src, toSys=dst, maxLy=max_ly)
    
    stations_by_system: dict = {}
    station_count: dict = {}
    if cmdenv.stations or cmdenv.detail:
        sys_ids = [s.system_id for s in route_systems]
        stations_by_system, station_count = _load_route_stations(
            session, cmdenv, sys_ids
        )
    
    lastSys, totalLy = src, 0.00
    for jumpSys in route_systems:
        jumpLy = _distance(lastSys, jumpSys)
        totalLy += jumpLy
        dirLy = _distance(jumpSys, dst) if cmdenv.detail else 0.00
        row = ResultRow(
            action='Via',
            system=jumpSys,
            jumpLy=jumpLy,
            totalLy=totalLy,
            dirLy=dirLy,
            station_count=station_count.get(jumpSys.system_id, 0),
        )
        row.stations = stations_by_system.get(jumpSys.system_id, []) if cmdenv.stations else []
        results.rows.append(row)
        lastSys = jumpSys
    
    results.rows[0].action = 'Depart'
    results.rows[-1].action = 'Arrive'
    
    return results


######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    if cmdenv.quiet > 1:
        print(','.join(row.system.name for row in results.rows))
        return False
    
    longestNamed = max(results.rows,
                    key=lambda row: len(row.system.name))
    longestNameLen = len(longestNamed.system.name)
    
    rowFmt = RowFormat()
    if cmdenv.detail:
        rowFmt.addColumn("Action", '<', 6, post=":", key=lambda row: row.action)
    rowFmt.addColumn("System", '<', longestNameLen,
            key=lambda row: row.system.name)
    rowFmt.addColumn("JumpLy", '>', '7', '.2f',
            key=lambda row: row.jumpLy)
    if cmdenv.detail:
        rowFmt.addColumn("Stations", '>', 2,
            key=lambda row: row.station_count)
    if cmdenv.detail:
        rowFmt.addColumn("DistLy", '>', '7', '.2f',
            key=lambda row: row.totalLy)
    if cmdenv.detail > 1:
        rowFmt.addColumn("DirLy", '>', 7, '.2f',
            key=lambda row: row.dirLy)
    
    showStations = cmdenv.stations
    if showStations:
        stnRowFmt = RowFormat(prefix='  /  ').append(
                ColumnFormat("Station", '<', 38,
                    key=lambda row: row.station.dbname())
        ).append(
                ColumnFormat("StnLs", '>', '10',
                    key=lambda row: _dist_from_star(row.station))
        ).append(
                ColumnFormat("Age/days", '>', 7,
                        key=lambda row: row.age)
        ).append(
                ColumnFormat('Mkt', '>', '3',
                    key=lambda row: formatting.marketStates[row.station.market])
        ).append(
                ColumnFormat("BMk", '>', '3',
                    key=lambda row: formatting.marketStates[row.station.blackmarket])
        ).append(
                ColumnFormat("Shp", '>', '3',
                    key=lambda row: formatting.marketStates[row.station.shipyard])
        ).append(
                ColumnFormat("Out", '>', '3',
                    key=lambda row: formatting.marketStates[row.station.outfitting])
        ).append(
                ColumnFormat("Arm", '>', '3',
                    key=lambda row: formatting.marketStates[row.station.rearm])
        ).append(
                ColumnFormat("Ref", '>', '3',
                    key=lambda row: formatting.marketStates[row.station.refuel])
        ).append(
                ColumnFormat("Rep", '>', '3',
                    key=lambda row: formatting.marketStates[row.station.repair])
        ).append(
                ColumnFormat("Pad", '>', '3',
                    key=lambda row: formatting.padSizes[row.station.max_pad_size])
        ).append(
                ColumnFormat("Plt", '>', '3',
                    key=lambda row: formatting.planetStates[row.station.planetary])
        ).append(
                ColumnFormat("Flc", '>', '3',
                    key=lambda row: formatting.fleetStates[_fleet_state(row.station)])
        ).append(
                ColumnFormat("Stl", '>', '3',
                    key=lambda row: formatting.settlementStates[_settlement_state(row.station)])
        )
        if cmdenv.detail > 1:
            stnRowFmt.append(
                ColumnFormat("Itms", ">", 4,
                    key=lambda row: row.item_count)
            )
    
    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        if showStations:
            print(heading)
            heading, underline = stnRowFmt.heading()
        print(heading, underline, sep='\n')
    
    for row in results.rows:
        print(rowFmt.format(row))
        for stnRow in row.stations:
            print(stnRowFmt.format(stnRow))
    
    return results
