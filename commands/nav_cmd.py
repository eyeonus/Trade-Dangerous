from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
import math

######################################################################
# Parser config

help='Calculate a route between two systems.'
name='nav'
epilog=None
wantsTradeDB=True
arguments = [
    ParseArgument('startSys', help='System to start from', type=str),
    ParseArgument('endSys', help='System to end at', type=str),
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
            default=1,
        ),
]

######################################################################
# Helpers

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    srcSystem = cmdenv.startSystem
    dstSystem = cmdenv.stopSystem
    maxLyPer = cmdenv.maxLyPer or tdb.maxSystemLinkLy

    cmdenv.DEBUG0("Route from {} to {} with max {} ly per jump.",
                    srcSystem.name(), dstSystem.name(), maxLyPer)

    openList = { srcSystem: 0.0 }
    distances = { srcSystem: [ 0.0, None ] }

    # As long as the open list is not empty, keep iterating.
    overshoot = cmdenv.aggressiveness * 4
    while openList:
        if dstSystem in distances:
            overshoot -= 1
            if overshoot == 0:
                break

        # Expand the search domain by one jump; grab the list of
        # nodes that are this many hops out and then clear the list.
        openNodes, openList = openList, {}

        gsir = tdb.genSystemsInRange
        for (node, startDist) in openNodes.items():
            for (destSys, destDistSq) in gsir(node, maxLyPer):
                destDist = math.sqrt(destDistSq)
                dist = startDist + destDist
                # If we aready have a shorter path, do nothing
                try:
                    distNode = distances[destSys]
                    if distNode[0] <= dist:
                        continue
                    distNode[0], distNode[1] = dist, node
                except KeyError:
                    distances[destSys] = [ dist, node ]
                assert not destSys in openList or openList[destSys] > dist
                openList[destSys] = dist

    # Unravel the route by tracing back the vias.
    route = [ dstSystem ]
    try:
        while route[-1] != srcSystem:
            jumpEnd = route[-1]
            jumpStart = distances[jumpEnd][1]
            route.append(jumpStart)
    except KeyError:
        print("No route found between {} and {} with {}ly jump limit.".format(srcSystem.name(), dstSystem.name(), maxLyPer))
        return

    results.summary = ResultRow(
                fromSys=srcSystem,
                toSys=dstSystem,
                maxLy=maxLyPer,
            )
    
    lastHop, totalLy = None, 0.00
    route.reverse()
    for hop in route:
        jumpLy = (distances[hop][0] - distances[lastHop][0]) if lastHop else 0.00
        totalLy += jumpLy
        row = ResultRow(
                action='Via',
                system=hop,
                jumpLy=jumpLy,
                totalLy=totalLy
                )
        results.rows.append(row)
        lastHop = hop
    results.rows[0].action='Depart'
    results.rows[1].action='Arrive'

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
        rowFmt.addColumn("DistLy", '>', '7', '.2f',
            key=lambda row: row.totalLy)

    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')
    
    for row in results.rows:
        print(rowFmt.format(row))

    return results

