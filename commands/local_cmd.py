from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
import math
from tradeexcept import TradeException
import itertools

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
    ParseArgument('--ages',
            help='Show stations and the age of their price data.',
            default=False,
            action='store_true',
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

    distances = { srcSystem: 0.0 }

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

    showStations = cmdenv.detail or cmdenv.ages
    ages = {}
    if cmdenv.ages:
        stationIDs = ",".join([
                ",".join(str(stn.ID) for stn in sys.stations)
                for sys in distances.keys()
                if sys.stations
        ])
        stmt = """
                SELECT  si.station_id,
                        JULIANDAY('NOW') - JULIANDAY(MAX(si.modified))
                  FROM  StationItem AS si
                 WHERE  si.station_id IN ({})
                 GROUP  BY 1
                """.format(stationIDs)
        cmdenv.DEBUG0("Fetching ages: {}", stmt)
        for ID, age in tdb.query(stmt):
            ages[ID] = age

    for (system, dist) in sorted(distances.items(), key=lambda x: x[1]):
        row = ResultRow()
        row.system = system
        row.dist = dist
        row.stations = []
        if showStations:
            for (station) in system.stations:
                try:
                    age = "{:7.2f}".format(ages[station.ID])
                except:
                    age = "-"
                rr = ResultRow(
                        station=station,
                        dist=station.lsFromStar,
                        age=age
                )
                row.stations.append(rr)
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
                ColumnFormat("Dist", '>', '7', '.2f',
                        key=lambda row: row.dist)
            )

    showStations = cmdenv.detail or cmdenv.ages
    if showStations:
        stnRowFmt = RowFormat(prefix='  +  ').append(
                ColumnFormat("Station", '<', 32,
                        key=lambda row: row.station.str())
            )
        if cmdenv.detail:
            stnRowFmt.append(
                ColumnFormat("Dist", '>', '10',
                        key=lambda row: '{}ls'.format(row.dist) if row.dist else '')
            )
        if cmdenv.ages:
            stnRowFmt.append(
                ColumnFormat("Age/days", '>', 7,
                        key=lambda row: row.age)
            )

    cmdenv.DEBUG0(
            "Systems within {ly:<5.2f}ly of {sys}.\n",
                    sys=results.summary.near.name(),
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

