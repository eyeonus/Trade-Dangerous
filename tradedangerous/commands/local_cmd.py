from __future__ import annotations
from itertools import chain
from math import sqrt

from sqlalchemy import exists, func

from .commandenv import Needs, ResultRow
from .exceptions import NoDataError
from .parsing import (
    ParseArgument, PadSizeArgument, MutuallyExclusiveGroup, NoPlanetSwitch,
    PlanetaryArgument, FleetCarrierArgument, SettlementArgument, BlackMarketSwitch,
    ShipyardSwitch, OutfittingSwitch, RearmSwitch, RefuelSwitch, RepairSwitch,
)
from . import display_labels
from tradedangerous.db import orm_models as orm
from tradedangerous.db.station_types import (
    fleet_carrier_state, settlement_state,
    FLEET_CARRIER_TYPE_IDS, SETTLEMENT_TYPE_IDS, UNKNOWN,
)
from tradedangerous.db.utils import age_in_days
from tradedangerous.formatting import RowFormat, ColumnFormat, max_len


######################################################################
# Parser config

name='local'
help='Calculate local systems.'
epilog="See also the 'station' sub-command."
needs = Needs.RESOLVER
arguments = [
    ParseArgument(
            'near',
            help='Name of the system to query from.',
            type=str,
            metavar='SYSTEMNAME',
    ),
]
switches = [
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
    SettlementArgument(),
    ParseArgument('--stations',
            help='Limit to systems which have stations.',
            action='store_true',
    ),
    ParseArgument('--trading',
            help='Limit stations to ones with price data or flagged as having '
                 'a market.',
            action='store_true',
    ),
    ParseArgument('--age', '--max-days-old', '-MD',
            help='Maximum age (in days) of trade data to use.',
            metavar='DAYS',
            type=float,
            dest='maxAge',
    ),
    BlackMarketSwitch(),
    ShipyardSwitch(),
    OutfittingSwitch(),
    RearmSwitch(),
    RefuelSwitch(),
    RepairSwitch(),
]

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
# Perform query and populate result set

def run(results, cmdenv, tdb):
    cmdenv = results.cmdenv
    tdb = cmdenv.tdb
    srcSystem = cmdenv.nearSystem  # ORM System

    # Allow the user to say '0' for system-only
    ly = cmdenv.ly if cmdenv.ly is not None else cmdenv.maxSystemLinkLy

    results.summary = ResultRow()
    results.summary.near = srcSystem
    results.summary.ly = ly
    results.summary.stations = 0

    # Bounding-box pre-filter in SQL; precise sphere check in Python.
    # Avoids loading all systems into memory (legacy stellarGrid approach).
    x, y, z = srcSystem.pos_x, srcSystem.pos_y, srcSystem.pos_z
    lySq = ly * ly
    distances = {srcSystem: 0.0}
    nearby = (
        tdb.session.query(orm.System)
        .filter(
            orm.System.pos_x.between(x - ly, x + ly),
            orm.System.pos_y.between(y - ly, y + ly),
            orm.System.pos_z.between(z - ly, z + ly),
            orm.System.system_id != srcSystem.system_id,
        )
        .all()
    )
    for sys in nearby:
        dx = sys.pos_x - x
        dy = sys.pos_y - y
        dz = sys.pos_z - z
        dist_sq = dx*dx + dy*dy + dz*dz
        if dist_sq <= lySq:
            distances[sys] = sqrt(dist_sq)

    showStations = cmdenv.detail
    wantStations = cmdenv.stations

    # Station query: only issued when station data is needed.
    # All flag filters are pushed to SQL; age data fetched separately
    # when required for display or --age filtering.
    stn_by_system: dict[int, list[ResultRow]] = {}
    if showStations or wantStations:
        padSize = cmdenv.padSize
        planetary = cmdenv.planetary
        fleet = cmdenv.fleet
        settlement = cmdenv.settlement
        wantNoPlanet = cmdenv.noPlanet
        wantTrading = cmdenv.trading
        maxAge = cmdenv.maxAge
        wantShipYard = cmdenv.shipyard
        wantBlackMarket = cmdenv.blackMarket
        wantOutfitting = cmdenv.outfitting
        wantRearm = cmdenv.rearm
        wantRefuel = cmdenv.refuel
        wantRepair = cmdenv.repair

        system_ids = [s.system_id for s in distances]
        q = (
            tdb.session.query(orm.Station)
            .filter(orm.Station.system_id.in_(system_ids))
        )

        if wantNoPlanet:
            q = q.filter(orm.Station.planetary == 'N')
        if wantBlackMarket:
            q = q.filter(orm.Station.blackmarket == 'Y')
        if wantShipYard:
            q = q.filter(orm.Station.shipyard == 'Y')
        if wantOutfitting:
            q = q.filter(orm.Station.outfitting == 'Y')
        if wantRearm:
            q = q.filter(orm.Station.rearm == 'Y')
        if wantRefuel:
            q = q.filter(orm.Station.refuel == 'Y')
        if wantRepair:
            q = q.filter(orm.Station.repair == 'Y')
        if padSize:
            q = q.filter(orm.Station.max_pad_size.in_(list(padSize)))
        if planetary:
            q = q.filter(orm.Station.planetary.in_(list(planetary)))
        if fleet:
            want_y = 'Y' in fleet
            want_n = 'N' in fleet
            want_q = '?' in fleet
            if want_y and not want_n and not want_q:
                q = q.filter(orm.Station.type_id.in_(list(FLEET_CARRIER_TYPE_IDS)))
            elif want_n and not want_y and not want_q:
                q = q.filter(
                    orm.Station.type_id.notin_(list(FLEET_CARRIER_TYPE_IDS)),
                    orm.Station.type_id != UNKNOWN,
                )
            elif want_q and not want_y and not want_n:
                q = q.filter(orm.Station.type_id == UNKNOWN)
            elif want_y and want_n and not want_q:
                q = q.filter(orm.Station.type_id != UNKNOWN)
            elif want_y and want_q and not want_n:
                q = q.filter(orm.Station.type_id.in_(list(FLEET_CARRIER_TYPE_IDS | {UNKNOWN})))
            elif want_n and want_q and not want_y:
                q = q.filter(orm.Station.type_id.notin_(list(FLEET_CARRIER_TYPE_IDS)))
        if settlement:
            want_y = 'Y' in settlement
            want_n = 'N' in settlement
            want_q = '?' in settlement
            if want_y and not want_n and not want_q:
                q = q.filter(orm.Station.type_id.in_(list(SETTLEMENT_TYPE_IDS)))
            elif want_n and not want_y and not want_q:
                q = q.filter(
                    orm.Station.type_id.notin_(list(SETTLEMENT_TYPE_IDS)),
                    orm.Station.type_id != UNKNOWN,
                )
            elif want_q and not want_y and not want_n:
                q = q.filter(orm.Station.type_id == UNKNOWN)
            elif want_y and want_n and not want_q:
                q = q.filter(orm.Station.type_id != UNKNOWN)
            elif want_y and want_q and not want_n:
                q = q.filter(orm.Station.type_id.in_(list(SETTLEMENT_TYPE_IDS | {UNKNOWN})))
            elif want_n and want_q and not want_y:
                q = q.filter(orm.Station.type_id.notin_(list(SETTLEMENT_TYPE_IDS)))
        if wantTrading:
            q = q.filter(
                (orm.Station.market == 'Y') |
                exists().where(
                    orm.StationItem.station_id == orm.Station.station_id
                )
            )

        all_stns = q.all()

        # Fetch age/count per station when needed for display or --age filtering.
        need_age = bool(maxAge) or bool(showStations)
        age_by_stn: dict[int, tuple] = {}
        if need_age and all_stns:
            stn_ids = [s.station_id for s in all_stns]
            age_rows = (
                tdb.session.query(
                    orm.StationItem.station_id,
                    func.count().label('item_count'),
                    func.avg(
                        age_in_days(tdb.session, orm.StationItem.modified)
                    ).label('data_age'),
                )
                .filter(orm.StationItem.station_id.in_(stn_ids))
                .group_by(orm.StationItem.station_id)
                .all()
            )
            age_by_stn = {
                row.station_id: (row.data_age, row.item_count)
                for row in age_rows
            }

        for stn in all_stns:
            data_age, item_count = age_by_stn.get(stn.station_id, (None, 0))
            if maxAge and (data_age is None or data_age > maxAge):
                continue
            age_str = f'{data_age:7.2f}' if data_age is not None else '-'
            stn_by_system.setdefault(stn.system_id, []).append(
                ResultRow(station=stn, age=age_str, item_count=item_count)
            )

    for (system, dist) in sorted(distances.items(), key=lambda x: x[1]):
        if showStations or wantStations:
            stn_rows = stn_by_system.get(system.system_id, [])
            if not stn_rows:
                continue
        else:
            stn_rows = []

        row = ResultRow()
        row.system = system
        row.dist = dist
        row.stations = stn_rows if showStations else []
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

    showStations = cmdenv.detail
    if showStations:
        maxStnLen = max_len(
            chain.from_iterable(row.stations for row in results.rows),
            key=lambda row: row.station.name
        )
        maxLsLen = max_len(
            chain.from_iterable(row.stations for row in results.rows),
            key=lambda row: _dist_from_star(row.station)
        )
        maxLsLen = max(maxLsLen, 5)
        stnRowFmt = RowFormat(prefix='  /  ').append(
                ColumnFormat("Station", '.<', maxStnLen + 2,
                    key=lambda row: row.station.name)
        ).append(
                ColumnFormat("StnLs", '>', maxLsLen,
                    key=lambda row: _dist_from_star(row.station))
        ).append(
                ColumnFormat("Age/days", '>', 7,
                        key=lambda row: row.age)
        ).append(
                ColumnFormat("Mkt", '>', '3',
                    key=lambda row: display_labels.marketStates[row.station.market])
        ).append(
                ColumnFormat("BMk", '>', '3',
                    key=lambda row: display_labels.marketStates[row.station.blackmarket])
        ).append(
                ColumnFormat("Shp", '>', '3',
                    key=lambda row: display_labels.marketStates[row.station.shipyard])
        ).append(
                ColumnFormat("Out", '>', '3',
                    key=lambda row: display_labels.marketStates[row.station.outfitting])
        ).append(
                ColumnFormat("Arm", '>', '3',
                    key=lambda row: display_labels.marketStates[row.station.rearm])
        ).append(
                ColumnFormat("Ref", '>', '3',
                    key=lambda row: display_labels.marketStates[row.station.refuel])
        ).append(
                ColumnFormat("Rep", '>', '3',
                    key=lambda row: display_labels.marketStates[row.station.repair])
        ).append(
                ColumnFormat("Pad", '>', '3',
                    key=lambda row: display_labels.padSizes[row.station.max_pad_size])
        ).append(
                ColumnFormat("Plt", '>', '3',
                    key=lambda row: display_labels.planetStates[row.station.planetary])
        ).append(
                ColumnFormat("Flc", '>', '3',
                    key=lambda row: display_labels.fleetStates[_fleet_state(row.station)])
        ).append(
                ColumnFormat("Stl", '>', '3',
                    key=lambda row: display_labels.settlementStates[_settlement_state(row.station)])
        )
        if cmdenv.detail > 1:
            stnRowFmt.append(
                ColumnFormat("Itms", ">", 4,
                    key=lambda row: row.item_count)
            )

    cmdenv.DEBUG0(
        "Systems within {ly:<5.2f}ly of {sys}.\n",
        sys=results.summary.near.name,
        ly=results.summary.ly,
    )

    if not cmdenv.quiet:
        heading, underline = sysRowFmt.heading()
        if showStations:
            print(heading)
            heading, underline = stnRowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(sysRowFmt.format(row))
        for stnRow in row.stations:
            print(stnRowFmt.format(stnRow))
