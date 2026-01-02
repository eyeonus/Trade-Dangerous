from __future__ import annotations
from itertools import chain
import datetime
import typing

from tradedangerous import TradeORM
from tradedangerous.tradeorm import PADSIZE_LABELS, TRISTATE_LABELS
from tradedangerous.db.orm_models import Station, System
from tradedangerous.formatting import RowFormat, ColumnFormat, max_len

from .commandenv import ResultRow
from .exceptions import CommandLineError, NoDataError
from .parsing import (
    ParseArgument, PadSizeArgument, MutuallyExclusiveGroup, NoPlanetSwitch,
    PlanetaryArgument, FleetCarrierArgument, OdysseyArgument, BlackMarketSwitch,
    ShipyardSwitch, OutfittingSwitch, RearmSwitch, RefuelSwitch, RepairSwitch,
)

from sqlalchemy import select, and_, not_
from sqlalchemy.orm import aliased, selectinload, with_loader_criteria


if typing.TYPE_CHECKING:
    from typing import Any
    from .commandenv import CommandEnv, CommandResults


######################################################################
# Parser config

name='local'
help='Calculate local systems.'
epilog="See also the 'station' sub-command."
wantsTradeDB=False
wantsTradeORM=True
arguments = [
    ParseArgument(
            'near',
            help='Name of the system to query from.',
            type=str,
            metavar='SYSTEMNAME',
    ),
]
switches: list[Any] = [
    ParseArgument('--ly',
            help='Maximum light years from system.',
            dest='ly',
            metavar='N.NN',
            type=float,
            default=None,
    ),
    PadSizeArgument(),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    OdysseyArgument(),
    ParseArgument('--stations',
            help='Limit to systems which have stations.',
            action='store_true',
    ),
    ParseArgument('--trading',
            help='Limit stations to ones with price data or flagged as having '
                 'a market.',
            action='store_true',
    ),
    ParseArgument('--ls-max',
        help = 'Only consider stations upto this many ls from their star.',
        metavar = 'LS',
        dest = 'maxLs',
        type = int,
        default = 0,
    ),
    ParseArgument('--limit', '-n',
                  help='Limit output to the first N results. (0 = no limit)',
                  dest='limit',
                  type=int,
                  default=0,
    ),
    BlackMarketSwitch(),
    ShipyardSwitch(),
    OutfittingSwitch(),
    RearmSwitch(),
    RefuelSwitch(),
    RepairSwitch(),
]

######################################################################
# Perform query and populate result set
# Return the result set to render or False.

def run(results: CommandResults, cmdenv: CommandEnv, tdb: TradeORM | None) -> CommandResults | bool:
    cmdenv = results.cmdenv  # Needs clarification
    tdb = TradeORM(tdenv=cmdenv)
    # Show the stations if present
    show_stations: bool = bool(cmdenv.detail)
    # Only match systems with stations
    need_stations: bool = bool(getattr(cmdenv, "stations", False))

    try:
        origin = tdb.lookup_system(cmdenv.near)
    except LookupError as e:
        raise CommandLineError(str(e))
    
    if not origin:
        raise CommandLineError(f"Unknown system: {cmdenv.near}")

    # Allow the user to say '0' for system-only
    ly = cmdenv.ly if cmdenv.ly is not None else cmdenv.maxSystemLinkLy
    
    results.summary = ResultRow()
    results.summary.near = origin
    results.summary.ly = ly
    results.summary.stations = 0
    results.summary.limit = max(cmdenv.limit, 0)
    results.summary.show_stations = show_stations

    candidate = aliased(System, name="candidate")
    # distance clamp. if this is too slow, we might
    # want to do a simple range <= x-x <= range, first.
    dx = candidate.pos_x - origin.pos_x
    dy = candidate.pos_y - origin.pos_y
    dz = candidate.pos_z - origin.pos_z
    range_sq: float = float((ly or 0.0) ** 2)
    distance_sq = ((dx * dx) + (dy * dy) + (dz * dz)).label("distance_sq")

    query = (
        select(candidate, distance_sq)
        .where(distance_sq <= range_sq)
        .order_by(distance_sq)
    )

    station_filters: list[Any] = []

    if show_stations or need_stations:
        # apply filter rules
        if cmdenv.trading:
            station_filters.append(Station.market == 'Y')
        if cmdenv.blackMarket:
            station_filters.append(Station.blackmarket == 'Y')
        if cmdenv.maxLs:
            station_filters.append(and_(Station.ls_from_star > 0, Station.ls_from_star <= cmdenv.maxLs))
        if cmdenv.outfitting:
            station_filters.append(Station.outfitting == 'Y')

        if cmdenv.shipyard:
            station_filters.append(Station.shipyard == 'Y')

        if cmdenv.rearm:
            station_filters.append(Station.rearm == 'Y')
        if cmdenv.refuel:
            station_filters.append(Station.refuel == 'Y')
        if cmdenv.repair:
            station_filters.append(Station.repair == 'Y')

        if cmdenv.padSize:
            station_filters.append(Station.max_pad_size.in_(list(cmdenv.padSize)))
        if cmdenv.noPlanet:
            station_filters.append(not_(Station.is_planetary))
        elif cmdenv.planetary:
            station_filters.append(Station.planetary.in_(list(cmdenv.planetary)))
        elif cmdenv.odyssey:
            station_filters.append(Station.odyssey.in_(list(cmdenv.odyssey)))

        if cmdenv.fleet == 'Y':
            station_filters.append(Station.is_fleet_carrier)
        elif cmdenv.fleet == 'N':
            station_filters.append(not_(Station.is_fleet_carrier))

    if station_filters:
        combined_filter = and_(*station_filters)
        query = query.where(candidate.stations.any(combined_filter))
        # Now, make the systems only load their stations that match the filter.
        query = query.options(
            selectinload(candidate.stations),
            with_loader_criteria(Station, combined_filter, include_aliases=True),
        )
    elif need_stations:
        query = query.where(candidate.stations.any())

    if results.summary.limit:
        query = query.limit(results.summary.limit)

    if cmdenv.debug > 0:
        compiled = query.compile(dialect=tdb.session.bind.dialect, compile_kwargs={"literal_binds": True})
        cmdenv.DEBUG0("query: {}", compiled)

    rows = tdb.session.execute(query).all()
    for system, distance_sq in rows:
        row = ResultRow()
        row.system = system
        row.dist = distance_sq ** 0.5
        row.stations = []
        results.rows.append(row)

        results.summary.stations += len(row.stations)
    
    return results


def render(results, cmdenv, tdb):
    """ render transforms a result set into output for the CLI. """
    if not results or not results.rows:
        distance, origin = results.summary.ly, results.summary.near.name
        raise NoDataError(f"No suitable systems found within {distance}ly of {origin}.")
    
    # Compare name lengths for formatting
    maxSysLen = max_len(results.rows, key=lambda row: row.system.name)
    
    sysRowFmt = RowFormat().append(
        ColumnFormat("System", '<', maxSysLen,
                key=lambda row: row.system.name)
    ).append(
        ColumnFormat("Dist", '>', '7', '.2f',
                key=lambda row: row.dist)
    )
    
    if results.summary.show_stations:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        maxStnLen = max_len(
            chain.from_iterable(row.system.stations for row in results.rows),
            key=lambda stn: stn.name
        )
        maxLsLen = max_len(
            chain.from_iterable(row.system.stations for row in results.rows),
            key=lambda stn: f"{int(stn.ls_from_star or 0):n}"
        )
        maxLsLen = max(maxLsLen, 5)
        stnRowFmt = RowFormat(prefix='  /  ').append(
                ColumnFormat("Station", '<', maxStnLen + 2,
                    key=lambda stn: stn.name)
        ).append(
                ColumnFormat("StnLs", '>', maxLsLen, "n",
                    key=lambda stn: int(stn.ls_from_star or 0))
        ).append(
                ColumnFormat("Mkt", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.market])
        ).append(
                ColumnFormat("BMk", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.blackmarket])
        ).append(
                ColumnFormat("Shp", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.shipyard])
        ).append(
                ColumnFormat("Out", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.outfitting])
        ).append(
                ColumnFormat("Arm", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.rearm])
        ).append(
                ColumnFormat("Ref", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.refuel])
        ).append(
                ColumnFormat("Rep", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.repair])
        ).append(
                ColumnFormat("Pad", '>', '3',
                    key=lambda stn: PADSIZE_LABELS[stn.max_pad_size])
        ).append(
                ColumnFormat("Plt", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.planetary])
        ).append(
                ColumnFormat("Flc", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.fleet_carrier])
        ).append(
                ColumnFormat("Ody", '>', '3',
                    key=lambda stn: TRISTATE_LABELS[stn.odyssey])
        )
        if cmdenv.detail > 1:
            stnRowFmt = stnRowFmt.append(
                ColumnFormat("Age/days", '>', 7,
                            key=lambda stn: (round((now - stn.modified).total_seconds() / 86400, 2)) if stn.modified else "n/a")
            )
            stnRowFmt.append(
                ColumnFormat("Itms", ">", 4,
                    key=lambda stn: len(stn.items))
            )
    
    cmdenv.DEBUG0(
        "Systems within {ly:<5.2f}ly of {sys}.\n",
        sys=results.summary.near.name,
        ly=results.summary.ly,
    )
    
    if not cmdenv.quiet:
        heading, underline = sysRowFmt.heading()
        if results.summary.show_stations:
            cmdenv.uprint(heading)
            heading, underline = stnRowFmt.heading()
        cmdenv.uprint(heading, underline, sep='\n')
    
    for row in results.rows:
        cmdenv.uprint(sysRowFmt.format(row))
        if not results.summary.show_stations:
            continue
        stations = row.system.stations
        truncate = results.summary.limit > 0 and len(stations) > results.summary.limit
        if truncate:
            stations = stations[:results.summary.limit]
        for stnRow in stations:
            cmdenv.uprint(stnRowFmt.format(stnRow))
        if truncate:
            cmdenv.uprint(f"  /  ... {len(row.system.stations) - results.summary.limit} more ...")
