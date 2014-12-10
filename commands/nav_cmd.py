from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
import math
from tradedb import System, Station
from tradeexcept import TradeException

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
    ParseArgument('--ship',
            help='Use the maximum jump distance of the specified ship.',
            metavar='shiptype',
            type=str,
        ),
    ParseArgument('--full',
            help='(With --ship) '
                    'Limits the jump distance to that of a full ship.',
            action='store_true',
            default=False,
        ),
    ParseArgument('--ly-per',
            help='Maximum light years per jump.',
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
        ),
    ParseArgument('--aggressive',
            help='Try more aggressively.',
            action='count',
            dest='aggressiveness',
            default=0,
        ),
    ParseArgument('--avoid',
            help='Exclude a system from the route. If you specify a station, '
                 'the system that station is in will be avoided instead.',
            action='append',
        ),
    ParseArgument('--stations',
            help='Show system\'s stations',
            dest='showstations',
 	    action='store_true',
            default=False
        ),
]

######################################################################
# Helpers


class NoRouteError(TradeException):
    pass


def getRoute(cmdenv, tdb, srcSystem, dstSystem, maxLyPer):
    openList = dict()
    distances = { srcSystem: [ 0.0, None ] }

    # Check for a direct route and seed the open list with the systems
    # in direct-range of the origin.
    for dstSys, dist in tdb.genSystemsInRange(srcSystem, maxLyPer):
        distances[dstSys] = [ dist, srcSystem ]
        if dstSys == dstSystem:
            return [ dstSystem, srcSystem ], distances
        openList[dstSys] = dist
    # Is there only one system in the list?
    if not openList:
        raise NoRouteError(
                "There are no systems within {}ly of {}.".format(
                    maxLyPer, srcSystem.name()
                ))

    # Check whether the destination system has a connecting link
    inRange = False
    for dstSys, dist in tdb.genSystemsInRange(dstSystem, maxLyPer):
        inRange = True
        break
    if not inRange:
        raise NoRouteError(
                "There are no systems within {}ly of {}.".format(
                    maxLyPer, dstSystem.name()
                ))
        return None, None

    avoiding = frozenset([
            place.system if isinstance(place, Station) else place
            for place in cmdenv.avoidPlaces
    ])
    if avoiding:
        cmdenv.DEBUG0("Avoiding: {}", list(avoiding))

    # As long as the open list is not empty, keep iterating.
    overshoot = (cmdenv.aggressiveness * 4) + 1
    while openList:
        if dstSystem in distances:
            overshoot -= 1
            if overshoot == 0:
                break

        # Expand the search domain by one jump; grab the list of
        # nodes that are this many hops out and then clear the list.
        openNodes, openList = openList, {}

        gsir = tdb.genSystemsInRange
        for node, startDist in openNodes.items():
            for (destSys, destDist) in gsir(node, maxLyPer):
                if destSys in avoiding:
                    continue
                dist = startDist + destDist
                # If we aready have a shorter path, do nothing
                try:
                    distNode = distances[destSys]
                    if distNode[0] <= dist:
                        continue
                    distNode[0], distNode[1] = dist, node
                except KeyError:
                    distances[destSys] = [ dist, node ]
                openList[destSys] = dist

    # Unravel the route by tracing back the vias.
    route = [ dstSystem ]
    while route[-1] != srcSystem:
        jumpEnd = route[-1]
        try:
            jumpStart = distances[jumpEnd][1]
        except KeyError:
            raise NoRouteError(
                    "No route found between {} and {} "
                        "with {}ly jump limit.".format(
                            srcSystem.name(), dstSystem.name(), maxLyPer
                    ))
            return None, None
        route.append(jumpStart)

    return route, distances


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    srcSystem, dstSystem = cmdenv.origPlace, cmdenv.destPlace
    if isinstance(srcSystem, Station):
        srcSystem = srcSystem.system
    if isinstance(dstSystem, Station):
        dstSystem = dstSystem.system

    maxLyPer = cmdenv.maxLyPer or tdb.maxSystemLinkLy

    cmdenv.DEBUG0("Route from {} to {} with max {}ly per jump.",
                    srcSystem.name(), dstSystem.name(), maxLyPer)

    route, distances = getRoute(cmdenv, tdb, srcSystem, dstSystem, maxLyPer)

    results.summary = ResultRow(
                fromSys=srcSystem,
                toSys=dstSystem,
                maxLy=maxLyPer,
            )

    lastHop, totalLy, dirLy = None, 0.00, 0.00
    route.reverse()
    for hop in route:
        jumpLy = (distances[hop][0] - distances[lastHop][0]) if lastHop else 0.00
        totalLy += jumpLy
        if cmdenv.detail:
            dirLy = math.sqrt(dstSystem.distToSq(hop))
        row = ResultRow(
                action='Via',
                system=hop,
                jumpLy=jumpLy,
                totalLy=totalLy,
                dirLy=dirLy,
                )
        results.rows.append(row)
        lastHop = hop
    results.rows[0].action='Depart'
    results.rows[-1].action='Arrive'

    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

    if cmdenv.quiet > 1:
        print(','.join(row.system.name() for row in results.rows))
        return

    longestNamed = max(results.rows,
                    key=lambda row: len(row.system.name()))
    longestNameLen = len(longestNamed.system.name())

    rowFmt = RowFormat()
    if cmdenv.detail:
        rowFmt.addColumn("Action", '<', 6, key=lambda row: row.action)
    rowFmt.addColumn("System", '<', longestNameLen,
            key=lambda row: row.system.name())
    rowFmt.addColumn("JumpLy", '>', '7', '.2f',
            key=lambda row: row.jumpLy)
    if cmdenv.showstations:
        rowFmt.addColumn("Stations", '>', 2, 
            key=lambda row: len(row.system.stations))
    if cmdenv.detail:
        rowFmt.addColumn("DistLy", '>', '7', '.2f',
            key=lambda row: row.totalLy)
    if cmdenv.detail > 1:
        rowFmt.addColumn("DirLy", '>', 7, '.2f',
            key=lambda row: row.dirLy)

    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(rowFmt.format(row))

    return results

