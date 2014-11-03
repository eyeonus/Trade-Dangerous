from commands import MutuallyExclusiveGroup, ParseArgument
import math

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
    MutuallyExclusiveGroup(
        ParseArgument('--pill',
                help='Show distance along the pill in ly.',
                action='store_true',
                default=False,
            ),
        ParseArgument('--percent',
                help='Show distance along pill as percentage.',
                action='store_true',
                default=False,
            ),
    ),
]

######################################################################
# Helpers

class PillCalculator(object):
    """
        Helper that calculates the position of stars relative to
        a line of stars.
    """

    def __init__(self, tdb, startStar, endStar, percent):
        lhs, rhs = tdb.lookupSystem(startStar), tdb.lookupSystem(endStar)
        self.normal = [
            rhs.posX - lhs.posX,
            rhs.posY - lhs.posY,
            rhs.posZ - lhs.posZ
        ]
        length2 = (normal[0]**2) + (normal[1]**2) + (normal[2]**2)
        self.pillLength = math.sqrt(length2)
        self.lhs = lhs
        self.percent = percent

    def distance(self, star):
        lhs, normal = self.lhs, self.normal
        dotProduct = ((normal[0] * (lhs.posX - star.posX)) +
                      (normal[1] * (lhs.posY - star.posY)) +
                      (normal[2] * (lhs.posZ - star.posZ)))
        if self.percent:
            return (100. * dotProduct / self.pillLength) / self.pillLength
        else:
            return dotProduct / self.pillLength

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

    detail = cmdenv.detai
    if cmdenv.pill or cmdenv.percent:
        pillCalc = PillCalculator(tdb, "Eranin", "HIP 107457", pill.percent)
    else:
        pillCalc = None

    for (system, dist) in sorted(distances.items(), key=lambda x: x[1]):
        row = ResultRow()
        row.system = system
        row.dist = dist
        if pillCalc:
            row.pill = pillCalc.distance(system)
        else:
            row.pill = None
        row.stations = []
        if detail:
            for (station) in system.stations:
                row.stations.append({'station': station, 'dist': station.lsFromStar})
                stationDistance = " {} ls".format(station.lsFromStar) if station.lsFromStar > 0 else ""
                print("\t<{}>{}".format(station.str(), stationDistance))
        results.rows.append(row)

    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

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

    if cmdenv.percent:
        sysRowFmt.append(after='System',
            col=ColumnFormat("Pill", '>', '4', '.0f', pre='[', post='%]',
                        key=lambda row: row.pill))
    elif cmdenv.pill:
        sysRowFmt.append(after='System',
            col=ColumnFormat("PillLy", '>', '6', '.2f', pre='[', post=']',
                        key=lambda row: row.pill))

    if cmdenv.detail:
        stnRowFmt = RowFormat(prefix='  +  ').append(
                ColumnFormat("Station", '.<', 32,
                        key=lambda row: row.station.str())
            ).append(
                ColumnFormat("Dist", '>', '9',
                        key=lambda row: '{}ls'.format(row.dist) if row.dist else '')
            )

    cmdenv.DEBUG(0,
            "Systems within {ly:<5.2f}ly of {sys}.\n",
                    sys=results.summary.near.name(),
                    ly=results.summary.ly,
        )

    if cmdenv.detail:
        heading, underline = sysRowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(sysRowFmt.format(row))
        for stnRow in row.stations:
            print(stnRowFmt.format(stnRow))
