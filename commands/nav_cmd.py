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
    ParseArgument('--ly-per',
            help='Maximum light years per jump.',
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
        ),
    ParseArgument('--avoid',
            help='Exclude a system from the route. If you specify a station, '
                 'the system that station is in will be avoided instead.',
            action='append',
        ),
]

######################################################################
# Helpers


class NoRouteError(TradeException):
    pass


class Distance(object):
    def __init__(self, start, end, dist):
        self.start, self.end, self.dist = start, end, dist

    def __repr__(self):
        return "Distance({}, {}, {})".format(
                self.start, self.end, self.dist
        )


def getRoute(cmdenv, tdb, srcSystem, dstSystem, maxLyPer):
    openList = { srcSystem: 0 }
    distances = { srcSystem: Distance(srcSystem, srcSystem, 0.0) }

    avoiding = frozenset([
            place.system if isinstance(place, Station) else place
            for place in cmdenv.avoidPlaces
    ])
    if avoiding:
        cmdenv.DEBUG0("Avoiding: {}", list(avoiding))

    leastHops = False

    # Once we find a path, we can curb any remaining paths that
    # are longer. This allows us to search aggresively until we
    # find the shortest route.
    shortestDist = float("inf")
    while openList:

        # Expand the search domain by one jump; grab the list of
        # nodes that are this many hops out and then clear the list.
        openNodes, openList = openList, {}

        gsir = tdb.genSystemsInRange
        for node, startDist in openNodes.items():
            for (destSys, destDist) in gsir(node, maxLyPer):
                if destSys in avoiding:
                    continue
                dist = startDist + destDist
                if dist >= shortestDist:
                    continue
                # If we aready have a shorter path, do nothing
                try:
                    distNode = distances[destSys]
                    if distances[destSys].dist <= dist:
                        continue
                except KeyError:
                    pass
                distances[destSys] = Distance(node, destSys, dist)
                openList[destSys] = dist
                if destSys == dstSystem:
                    shortestDist = dist

    # Unravel the route by tracing back the vias.
    route = [ dstSystem ]
    jumpEnd = dstSystem
    while jumpEnd != srcSystem:
        try:
            distEnt = distances[jumpEnd]
        except KeyError:
            raise NoRouteError(
                    "No route found between {} and {} "
                        "with {}ly jump limit.".format(
                            srcSystem.name(), dstSystem.name(), maxLyPer
                    ))

        route.append(distEnt.start)
        jumpEnd = distEnt.start

    return route


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

    route = getRoute(cmdenv, tdb, srcSystem, dstSystem, maxLyPer)

    results.summary = ResultRow(
                fromSys=srcSystem,
                toSys=dstSystem,
                maxLy=maxLyPer,
            )

    lastSys, totalLy, dirLy = srcSystem, 0.00, 0.00
    route.reverse()
    for jumpSys in route:
        jumpLy = math.sqrt(lastSys.distToSq(jumpSys))
        totalLy += jumpLy
        if cmdenv.detail:
            dirLy = math.sqrt(jumpSys.distToSq(dstSystem))
        row = ResultRow(
                action='Via',
                system=jumpSys,
                jumpLy=jumpLy,
                totalLy=totalLy,
                dirLy=dirLy,
                )
        results.rows.append(row)
        lastSys = jumpSys
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
    if cmdenv.detail:
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

