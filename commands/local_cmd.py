from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.commandenv import ResultRow
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from formatting import RowFormat, ColumnFormat, max_len
from itertools import chain
from tradedb import TradeDB
from tradeexcept import TradeException

import math

######################################################################
# Parser config

name='local'
help='Calculate local systems.'
epilog="See also the 'station' sub-command."
wantsTradeDB=True
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
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
            default=None,
    ),
    ParseArgument('--pad-size', '-p',
            help='Limit the padsize to this ship size (S,M,L or ? for unkown).',
            metavar='PADSIZES',
            dest='padSize',
    ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    cmdenv = results.cmdenv
    tdb = cmdenv.tdb
    srcSystem = cmdenv.nearSystem

    ly = cmdenv.maxLyPer
    if ly is None:
        ly = tdb.maxSystemLinkLy

    results.summary = ResultRow()
    results.summary.near = srcSystem
    results.summary.ly = ly

    distances = { srcSystem: 0.0 }

    # Calculate the bounding dimensions
    for destSys, dist in tdb.genSystemsInRange(srcSystem, ly):
        distances[destSys] = dist

    showStations = cmdenv.detail
    if showStations:
        stmt = """
                SELECT  si.station_id,
                        JULIANDAY('NOW') - JULIANDAY(MIN(si.modified))
                  FROM  StationItem AS si
                 GROUP  BY 1
                """
        cmdenv.DEBUG0("Fetching ages: {}", stmt)
        ages = {
            ID: age
            for ID, age in tdb.query(stmt)
        }

    padSize = cmdenv.padSize
    for (system, dist) in sorted(distances.items(), key=lambda x: x[1]):
        row = ResultRow()
        row.system = system
        row.dist = dist
        row.stations = []
        if showStations:
            for (station) in system.stations:
                if padSize and not station.checkPadSize(padSize):
                    continue
                try:
                    age = "{:7.2f}".format(ages[station.ID])
                except:
                    age = "-"
                rr = ResultRow(
                        station=station,
                        age=age,
                )
                row.stations.append(rr)
        results.rows.append(row)

    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    if not results or not results.rows:
        raise TradeException("No systems found within {}ly of {}.".format(
                    results.summary.ly,
                    results.summary.near.name(),
                ))

    # Compare system names so we can tell 
    maxSysLen = max_len(results.rows, key=lambda row: row.system.name())

    sysRowFmt = RowFormat().append(
                ColumnFormat("System", '<', maxSysLen,
                        key=lambda row: row.system.name())
            ).append(
                ColumnFormat("Dist", '>', '7', '.2f',
                        key=lambda row: row.dist)
            )

    showStations = cmdenv.detail
    if showStations:
        maxStnLen = max_len(
            chain.from_iterable(
                row.system.stations for row in results.rows
            ),
            key=lambda row: row.dbname
        )
        maxLsLen = max_len(
            chain.from_iterable(
                row.system.stations for row in results.rows
            ),
            key=lambda row: row.distFromStar()
        )
        maxLsLen = max(maxLsLen, 5)
        stnRowFmt = RowFormat(prefix='  /  ').append(
                ColumnFormat("Station", '<', maxStnLen + 1,
                    key=lambda row: row.station.str())
        ).append(
                ColumnFormat("StnLs", '>', maxLsLen,
                    key=lambda row: row.station.distFromStar())
        ).append(
                ColumnFormat("Age/days", '>', 7,
                        key=lambda row: row.age)
        ).append(
                ColumnFormat("Mkt", '>', '3',
                    key=lambda row: \
                        TradeDB.marketStates[row.station.market])
        ).append(
                ColumnFormat("BMk", '>', '3',
                    key=lambda row: \
                        TradeDB.marketStates[row.station.blackMarket])
        ).append(
                ColumnFormat("Shp", '>', '3',
                    key=lambda row: \
                        TradeDB.marketStates[row.station.shipyard])
        ).append(
                ColumnFormat("Pad", '>', '3',
                    key=lambda row: \
                        TradeDB.padSizes[row.station.maxPadSize])
        )
        if cmdenv.detail > 1:
            stnRowFmt.append(
                ColumnFormat("Itms", ">", 4,
                    key=lambda row: row.station.itemCount)
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

