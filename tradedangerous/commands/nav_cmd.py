from .parsing import (
    AvoidPlacesArgument, FleetCarrierArgument, MutuallyExclusiveGroup,
    NoPlanetSwitch, OdysseyArgument, PadSizeArgument, ParseArgument,
    PlanetaryArgument,
)
from ..tradedb import System, Station, TradeDB
from ..tradeexcept import TradeException


######################################################################
# Parser config

help='Calculate a route between two systems.'
name='nav'
epilog=None
wantsTradeDB=True
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
    ParseArgument('--refuel-jumps',
        help='Require a station after this many jumps',
        type=int,
        dest='stationInterval',
    ),
    PadSizeArgument(),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    OdysseyArgument(),
]

######################################################################
# Helpers


class NoRouteError(TradeException):
    pass


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from .commandenv import ResultRow
    
    srcSystem, dstSystem = cmdenv.origPlace, cmdenv.destPlace
    if isinstance(srcSystem, Station):
        srcSystem = srcSystem.system
    if isinstance(dstSystem, Station):
        dstSystem = dstSystem.system
    
    maxLyPer = cmdenv.maxLyPer or tdb.maxSystemLinkLy
    
    cmdenv.DEBUG0("Route from {} to {} with max {}ly per jump.",
                    srcSystem.name(), dstSystem.name(), maxLyPer)
    
    # Build a list of src->dst pairs
    hops = [ [ srcSystem, None ] ]
    if cmdenv.viaPlaces:
        for hop in cmdenv.viaPlaces:
            hops[-1][1] = hop
            hops.append([hop, None])
    hops[-1][1] = dstSystem
    
    avoiding = [
        avoid for avoid in cmdenv.avoidPlaces
        if isinstance(avoid, System)
    ]
    
    route = [ ]
    stationInterval = cmdenv.stationInterval
    for hop in hops:
        try:
            hopRoute = list(tdb.getRoute(
                hop[0], hop[1],
                maxLyPer,
                avoiding,
                stationInterval=stationInterval,
                ))
        except TypeError:
            raise NoRouteError(
                    "No route found between {} and {} "
                    "with a max {}ly/jump limit.".format(
                        hop[0].name(), hop[1].name(),
                        maxLyPer,
            ))
        route = route[:-1] + hopRoute
    
    results.summary = ResultRow(
                fromSys=srcSystem,
                toSys=dstSystem,
                maxLy=maxLyPer,
            )
    
    lastSys, totalLy, dirLy = srcSystem, 0.00, 0.00
    maxPadSize = cmdenv.padSize
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    odyssey = cmdenv.odyssey
    noPlanet = cmdenv.noPlanet
    
    for (jumpSys, dist) in route:
        jumpLy = lastSys.distanceTo(jumpSys)
        totalLy += jumpLy
        if cmdenv.detail:
            dirLy = jumpSys.distanceTo(dstSystem)
        row = ResultRow(
            action='Via',
            system=jumpSys,
            jumpLy=jumpLy,
            totalLy=totalLy,
            dirLy=dirLy,
            )
        row.stations = []
        if cmdenv.stations:
            for (station) in jumpSys.stations:
                if maxPadSize and not station.checkPadSize(maxPadSize):
                    continue
                if planetary and not station.checkPlanetary(planetary):
                    continue
                if fleet and not station.checkFleet(fleet):
                    continue
                if odyssey and not station.checkOdyssey(odyssey):
                    continue
                if noPlanet and station.planetary != 'N':
                    continue
                rr = ResultRow(
                    station=station,
                    age=station.itemDataAgeStr,
                )
                row.stations.append(rr)
        results.rows.append(row)
        lastSys = jumpSys
    results.rows[0].action='Depart'
    results.rows[-1].action='Arrive'
    
    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    from ..formatting import RowFormat, ColumnFormat
    
    if cmdenv.quiet > 1:
        print(','.join(row.system.name() for row in results.rows))
        return
    
    longestNamed = max(results.rows,
                    key=lambda row: len(row.system.name()))
    longestNameLen = len(longestNamed.system.name())
    
    rowFmt = RowFormat()
    if cmdenv.detail:
        rowFmt.addColumn("Action", '<', 6, post=":", key=lambda row: row.action)
    rowFmt.addColumn("System", '<', longestNameLen,
            key=lambda row: row.system.name())
    rowFmt.addColumn("JumpLy", '>', '7', '.2f',
            key=lambda row: row.jumpLy)
    if cmdenv.detail:
        rowFmt.addColumn("Stations", '>', 2,
            key=lambda row: len(row.system.stations))
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
                    key=lambda row: row.station.dbname)
        ).append(
                ColumnFormat("StnLs", '>', '10',
                    key=lambda row: row.station.distFromStar())
        ).append(
                ColumnFormat("Age/days", '>', 7,
                        key=lambda row: row.age)
        ).append(
                ColumnFormat('Mkt', '>', '3',
                    key=lambda row: TradeDB.marketStates[row.station.market])
        ).append(
                ColumnFormat("BMk", '>', '3',
                    key=lambda row: TradeDB.marketStates[row.station.blackMarket])
        ).append(
                ColumnFormat("Shp", '>', '3',
                    key=lambda row: TradeDB.marketStates[row.station.shipyard])
        ).append(
                ColumnFormat("Out", '>', '3',
                    key=lambda row: TradeDB.marketStates[row.station.outfitting])
        ).append(
                ColumnFormat("Arm", '>', '3',
                    key=lambda row: TradeDB.marketStates[row.station.rearm])
        ).append(
                ColumnFormat("Ref", '>', '3',
                    key=lambda row: TradeDB.marketStates[row.station.refuel])
        ).append(
                ColumnFormat("Rep", '>', '3',
                    key=lambda row: TradeDB.marketStates[row.station.repair])
        ).append(
                ColumnFormat("Pad", '>', '3',
                    key=lambda row: TradeDB.padSizes[row.station.maxPadSize])
        ).append(
                ColumnFormat("Plt", '>', '3',
                    key=lambda row: TradeDB.planetStates[row.station.planetary])
        ).append(
                ColumnFormat("Flc", '>', '3',
                    key=lambda row: TradeDB.fleetStates[row.station.fleet])
        ).append(
                ColumnFormat("Ody", '>', '3',
                    key=lambda row: TradeDB.odysseyStates[row.station.odyssey])
        )
        if cmdenv.detail > 1:
            stnRowFmt.append(
                ColumnFormat("Itms", ">", 4,
                    key=lambda row: row.station.itemCount)
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
