from __future__ import annotations

from math import sqrt

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from .commandenv import Needs, ResultRow
from .exceptions import CommandLineError
from .parsing import (
    FleetCarrierArgument, MutuallyExclusiveGroup, NoPlanetSwitch,
    SettlementArgument, ParseArgument, PadSizeArgument, PlanetaryArgument,
)

from tradedangerous import TradeException
from tradedangerous import formatting
from tradedangerous.db import orm_models as orm
from tradedangerous.db.station_types import (
    fleet_carrier_state, settlement_state,
    FLEET_CARRIER_TYPE_IDS, SETTLEMENT_TYPE_IDS, UNKNOWN,
)
from tradedangerous.db.utils import age_in_days
from tradedangerous.formatting import RowFormat, ColumnFormat, max_len


######################################################################
# Parser config

name = 'olddata'
help = 'Show oldest data in database.'
epilog = None
needs = Needs.RESOLVER
arguments = [
]
switches = [
    ParseArgument('--limit',
            help='Maximum number of results to show',
            default=20,
            type=int,
    ),
    ParseArgument('--near',
            help='Find stations within range of this system.',
            type=str,
    ),
    ParseArgument('--ly',
            help='[Requires --near] Systems within this range of --near.',
            default=None,
            dest='ly',
            metavar='N.NN',
            type=float,
    ),
    ParseArgument('--route',
            help='[Requires --near] Sort to shortest path',
            action='store_true',
    ),
    ParseArgument('--min-age',
            help='List data older than this number of days.',
            type=float,
            dest='minAge',
    ),
    PadSizeArgument(),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    SettlementArgument(),
    ParseArgument('--ls-max',
        help='Only consider stations upto this many ls from their star.',
        metavar='LS',
        dest='maxLs',
        type=int,
        default=0,
    ),
]


######################################################################
# Helpers

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


def _distance(sys_a: orm.System, sys_b: orm.System) -> float:
    dx = sys_a.pos_x - sys_b.pos_x
    dy = sys_a.pos_y - sys_b.pos_y
    dz = sys_a.pos_z - sys_b.pos_z
    return sqrt(dx * dx + dy * dy + dz * dz)


def _apply_tristate_filter(query, want, type_ids):
    """Filter stations by a Y/N/? flag derived from type_id.

    `want` holds the requested states ('Y'/'N'/'?'); `type_ids` is the set of
    type_ids that count as 'Y' for this flag. type_id UNKNOWN is '?', and any
    other type_id not in `type_ids` is 'N'. Mirrors the local command's filter.
    """
    want_y = 'Y' in want
    want_n = 'N' in want
    want_q = '?' in want
    ids = list(type_ids)
    if want_y and not want_n and not want_q:
        return query.filter(orm.Station.type_id.in_(ids))
    if want_n and not want_y and not want_q:
        return query.filter(
            orm.Station.type_id.notin_(ids),
            orm.Station.type_id != UNKNOWN,
        )
    if want_q and not want_y and not want_n:
        return query.filter(orm.Station.type_id == UNKNOWN)
    if want_y and want_n and not want_q:
        return query.filter(orm.Station.type_id != UNKNOWN)
    if want_y and want_q and not want_n:
        return query.filter(orm.Station.type_id.in_(ids + [UNKNOWN]))
    if want_n and want_q and not want_y:
        return query.filter(orm.Station.type_id.notin_(ids))
    return query


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    """
    Find the stations whose freshest market data is the oldest.

    The work is done in SQL: aggregate MAX(StationItem.modified) per station,
    convert it to an age in days, push all station/age/range filters into the
    query, order oldest-first, and LIMIT in the database. Only the surviving
    rows are then hydrated as ORM objects for rendering -- no full preload.
    """
    cmdenv = results.cmdenv
    tdb = cmdenv.tdb
    session = tdb.session

    nearSys = cmdenv.nearSystem  # resolved ORM System, or None

    age_expr = age_in_days(session, func.max(orm.StationItem.modified)).label('age')
    columns = [orm.Station.station_id.label('station_id'), age_expr]

    # --near: bounding box + exact-sphere range filter, both in SQL. The squared
    # distance is constant per station (one system), so MIN() makes it a legal
    # aggregate to select alongside the GROUP BY on every backend.
    dist2_raw = None
    if nearSys:
        ly = cmdenv.ly if cmdenv.ly is not None else cmdenv.maxSystemLinkLy
        x, y, z = nearSys.pos_x, nearSys.pos_y, nearSys.pos_z
        dist2_raw = (
            (orm.System.pos_x - x) * (orm.System.pos_x - x)
            + (orm.System.pos_y - y) * (orm.System.pos_y - y)
            + (orm.System.pos_z - z) * (orm.System.pos_z - z)
        )
        columns.append(func.min(dist2_raw).label('dist2'))

    query = (
        session.query(*columns)
        .select_from(orm.Station)
        .join(orm.StationItem, orm.StationItem.station_id == orm.Station.station_id)
    )

    if nearSys:
        query = (
            query.join(orm.System, orm.System.system_id == orm.Station.system_id)
            .filter(
                orm.System.pos_x.between(x - ly, x + ly),
                orm.System.pos_y.between(y - ly, y + ly),
                orm.System.pos_z.between(z - ly, z + ly),
                dist2_raw <= ly * ly,
            )
        )

    # Station-attribute filters, all pushed into SQL.
    if cmdenv.padSize:
        query = query.filter(orm.Station.max_pad_size.in_(list(cmdenv.padSize)))
    if cmdenv.planetary:
        query = query.filter(orm.Station.planetary.in_(list(cmdenv.planetary)))
    if cmdenv.noPlanet:
        query = query.filter(orm.Station.planetary == 'N')
    if cmdenv.maxLs:
        query = query.filter(orm.Station.ls_from_star <= cmdenv.maxLs)
    if cmdenv.fleet:
        query = _apply_tristate_filter(query, cmdenv.fleet, FLEET_CARRIER_TYPE_IDS)
    if cmdenv.settlement:
        query = _apply_tristate_filter(query, cmdenv.settlement, SETTLEMENT_TYPE_IDS)

    query = query.group_by(orm.Station.station_id)

    if cmdenv.minAge:
        query = query.having(age_expr >= float(cmdenv.minAge))

    query = query.order_by(age_expr.desc())
    if cmdenv.limit:
        query = query.limit(cmdenv.limit)

    rows = query.all()

    # Hydrate only the survivors (<= --limit) for rendering and --route.
    stn_ids = [r.station_id for r in rows]
    station_by_id = {}
    if stn_ids:
        hydrated = (
            session.query(orm.Station)
            .options(joinedload(orm.Station.system))
            .filter(orm.Station.station_id.in_(stn_ids))
            .all()
        )
        station_by_id = {s.station_id: s for s in hydrated}

    for r in rows:
        station = station_by_id.get(r.station_id)
        if station is None:
            continue
        row = ResultRow()
        row.station = station
        row.age = float(r.age or 0.0)
        row.dist = sqrt(float(r.dist2)) if nearSys and r.dist2 is not None else 0.0
        results.rows.append(row)

    # --route: reorder the bounded result set into a short nearest-neighbour path.
    if cmdenv.route:
        if not cmdenv.near:
            raise CommandLineError("--route requires --near")
        if len(results.rows) > 1:
            remaining = set(results.rows)
            path = [results.rows[0]]
            remaining.remove(results.rows[0])
            while remaining:
                last = path[-1].station.system
                nearest = min(remaining, key=lambda rr: _distance(last, rr.station.system))
                remaining.remove(nearest)
                path.append(nearest)
            results.rows[:] = path

    return results


######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    if not results or not results.rows:
        raise TradeException("No data found")

    nameLen = max_len(results.rows, key=lambda row: row.station.dbname())

    rowFmt = RowFormat().append(
            ColumnFormat("Station", '<', nameLen,
                    key=lambda row: row.station.dbname())
    )

    if cmdenv.quiet < 2:
        if cmdenv.nearSystem:
            rowFmt.addColumn('DistLy', '>', 6, '.2f',
                    key=lambda row: row.dist)
        rowFmt.append(
                ColumnFormat("Age/days", '>', '8', '.2f',
                        key=lambda row: row.age)
        ).append(
                ColumnFormat("StnLs", '>', '10',
                        key=lambda row: _dist_from_star(row.station))
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

    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(rowFmt.format(row))
