from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
import math
from tradeexcept import TradeException

######################################################################
# Parser config

name='local'
help='Calculate local systems.'
epilog=None
wantsTradeDB=True
arguments = [
    ParseArgument('near', help='System to measure from', type=str),
]
switches = [
    ParseArgument('--ship',
            help='Use maximum jump distance of the specified ship.',
            metavar='shiptype',
            type=str,
        ),
    ParseArgument('--full',
            help='(With --ship) Limits the jump distance to that of a full ship.',
            action='store_true',
            default=False,
        ),
    ParseArgument('--ly',
            help='Maximum light years to measure.',
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
        ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    cmdenv = results.cmdenv
    tdb = cmdenv.tdb
    srcSystem = cmdenv.nearSystem

    ly = cmdenv.maxLyPer or tdb.maxSystemLinkLy

    results.summary = ResultRow()
    results.summary.near = srcSystem
    results.summary.ly = ly

    distances = { }

    # Calculate the bounding dimensions
    srcX, srcY, srcZ = srcSystem.posX, srcSystem.posY, srcSystem.posZ
    lySq = ly * ly

    for destSys in tdb.systems():
        distSq = (
                    (destSys.posX - srcX) ** 2 +
                    (destSys.posY - srcY) ** 2 +
                    (destSys.posZ - srcZ) ** 2
                )
        if distSq <= lySq and destSys is not srcSystem:
            distances[destSys] = math.sqrt(distSq)

    detail = cmdenv.detail
    for (system, dist) in sorted(distances.items(), key=lambda x: x[1]):
        row = ResultRow()
        row.system = system
        row.dist = dist
        row.stations = []
        if detail:
            for (station) in system.stations:
                row.stations.append(ResultRow(station=station, dist=station.lsFromStar))
        results.rows.append(row)

    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

    if not results or not results.rows:
        raise TradeException("No systems found within {}ly of {}.".format(
                    results.summary.ly,
                    results.summary.near.name(),
                ))

    # Compare system names so we can tell 
    longestNamed = max(results.rows,
                    key=lambda row: len(row.system.name()))
    longestNameLen = len(longestNamed.system.name())

    sysRowFmt = RowFormat().append(
                ColumnFormat("System", '<', longestNameLen,
                        key=lambda row: row.system.name())
            ).append(
                ColumnFormat("Dist", '>', '6', '.2f',
                        key=lambda row: row.dist)
            )

    if cmdenv.detail:
        stnRowFmt = RowFormat(prefix='  +  ').append(
                ColumnFormat("Station", '<', 32,
                        key=lambda row: row.station.str())
            ).append(
                ColumnFormat("Dist", '>', '9',
                        key=lambda row: '{}ls'.format(row.dist) if row.dist else '')
            )

    cmdenv.DEBUG0(
            "Systems within {ly:<5.2f}ly of {sys}.\n",
                    sys=results.summary.near.name(),
                    ly=results.summary.ly,
        )

    if not cmdenv.quiet:
        heading, underline = sysRowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(sysRowFmt.format(row))
        for stnRow in row.stations:
            print(stnRowFmt.format(stnRow))

