from .parsing import (
    FleetCarrierArgument, MutuallyExclusiveGroup, NoPlanetSwitch,
    OdysseyArgument, ParseArgument, PadSizeArgument, PlanetaryArgument,
)
from ..tradedb import TradeDB
from ..tradeexcept import TradeException


######################################################################
# Parser config

name='olddata'
help='Show oldest data in database.'
epilog=None
wantsTradeDB=True
arguments = [
]
switches = [
    ParseArgument('--limit',
            help='Maximum number of results to show',
            default=20,
            type=int,
    ),
    ParseArgument('--near',
            help='Find sellers within jump range of this system.',
            type=str
    ),
    ParseArgument('--ly',
            help='[Requires --near] Systems within this range of --near.',
            default=None,
            dest='maxLyPer',
            metavar='N.NN',
            type=float,
    ),
    ParseArgument('--route',
            help='Sort to shortest path',
            action='store_true',
    ),
    ParseArgument('--min-age',
            help='List data older than this number of days.',
            type=float,
            dest='minAge',
    ),
    PadSizeArgument(),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    OdysseyArgument(),
    ParseArgument('--ls-max',
        help='Only consider stations upto this many ls from their star.',
        metavar='LS',
        dest='maxLs',
        type=int,
        default=0,
    ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from .commandenv import ResultRow
    
    cmdenv = results.cmdenv
    tdb = cmdenv.tdb
    
    results.summary = ResultRow()
    results.limit = cmdenv.limit
    
    fields = [
        "si.station_id",
        "JULIANDAY('NOW') - JULIANDAY(MAX(si.modified))",
        "stn.ls_from_star",
    ]
    
    joins = []
    wheres = []
    havings = []
    
    if cmdenv.minAge:
        wheres.append(
            "(JULIANDAY('NOW') - JULIANDAY(si.modified) >= {})"
            .format(cmdenv.minAge)
        )
    
    nearSys = cmdenv.nearSystem
    if nearSys:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        maxLy2 = maxLy ** 2
        fields.append(
                "dist2("
                    "sys.pos_x, sys.pos_y, sys.pos_z,"
                    "{}, {}, {}"
                ") AS d2".format(
                    nearSys.posX,
                    nearSys.posY,
                    nearSys.posZ,
        ))
        joins.append("INNER JOIN System sys USING (system_id)")
        wheres.append("""(
                sys.pos_x BETWEEN {} and {}
                AND sys.pos_y BETWEEN {} and {}
                AND sys.pos_z BETWEEN {} and {}
        )""".format(
                nearSys.posX - maxLy,
                nearSys.posX + maxLy,
                nearSys.posY - maxLy,
                nearSys.posY + maxLy,
                nearSys.posZ - maxLy,
                nearSys.posZ + maxLy,
        ))
        havings.append("d2 <= {}".format(maxLy2))
    else:
        fields.append("0")
    
    fieldStr = ','.join(fields)
    
    if joins:
        joinStr = ' '.join(joins)
    else:
        joinStr = ''
    
    if wheres:
        whereStr = 'WHERE ' + ' AND '.join(wheres)
    else:
        whereStr = ''
    
    if havings:
        haveStr = 'HAVING ' + ' AND '.join(havings)
    else:
        haveStr = ''
    
    stmt = """
            SELECT  {fields}
              FROM  StationItem as si
                    INNER JOIN Station stn USING (station_id)
                    {joins}
             {wheres}
             GROUP  BY 1
             {having}
             ORDER  BY 2 DESC
    """.format(
            fields=fieldStr,
            joins=joinStr,
            wheres=whereStr,
            having=haveStr,
    )
    
    cmdenv.DEBUG1(stmt)
    
    padSize = cmdenv.padSize
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    odyssey = cmdenv.odyssey
    noPlanet = cmdenv.noPlanet
    mls = cmdenv.maxLs
    
    for (stnID, age, ls, dist2) in tdb.query(stmt):
        cmdenv.DEBUG2("{}:{}:{}", stnID, age, ls)
        row = ResultRow()
        row.station = tdb.stationByID[stnID]
        row.age = age
        if ls:
            row.ls = "{:n}".format(ls)
        else:
            row.ls = "?"
        row.dist = dist2 ** 0.5
        if not padSize or row.station.checkPadSize(padSize):
            if not planetary or row.station.checkPlanetary(planetary):
                if not fleet or row.station.checkFleet(fleet):
                    if not odyssey or row.station.checkOdyssey(odyssey):
                        if not noPlanet or row.station.planetary == 'N':
                            if not mls or row.station.lsFromStar <= mls:
                                results.rows.append(row)
    
    if cmdenv.route and len(results.rows) > 1:
        def walk(startNode, dist):
            rows = results.rows
            startNode = rows[startNode]
            openList = set(rows)
            path = [startNode]
            openList.remove(startNode)
            while len(path) < len(rows):
                lastNode = path[-1]
                distFn = lastNode.station.system.distanceTo
                nearest = min(openList, key=lambda row: distFn(row.station.system))
                openList.remove(nearest)
                path.append(nearest)
                dist += distFn(nearest.station.system)
            return (path, dist)
        if cmdenv.near:
            bestPath = walk(0, results.rows[0].dist)
        else:
            bestPath = (results.rows, float("inf"))
            for i in range(len(results.rows)):
                path = walk(i, 0)
                if path[1] < bestPath[1]:
                    bestPath = path
        results.rows[:] = bestPath[0]
    
    if cmdenv.limit:
        results.rows[:] = results.rows[:cmdenv.limit]
    
    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    from ..formatting import RowFormat, ColumnFormat
    
    if not results or not results.rows:
        raise TradeException("No data found")
    
    # Compare system names so we can tell
    longestNamed = max(results.rows,
                    key=lambda row: len(row.station.name()))
    longestNameLen = len(longestNamed.station.name())
    
    rowFmt = RowFormat().append(
            ColumnFormat("Station", '<', longestNameLen,
                    key=lambda row: row.station.name())
    )
    
    if cmdenv.quiet < 2:
        if cmdenv.nearSystem:
            rowFmt.addColumn('DistLy', '>', 6, '.2f',
                    key=lambda row: row.dist
            )
        
        rowFmt.append(
                ColumnFormat("Age/days", '>', '8', '.2f',
                        key=lambda row: row.age)
        ).append(
                ColumnFormat("StnLs", '>', '10',
                        key=lambda row: row.station.distFromStar())
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
    
    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')
    
    for row in results.rows:
        print(rowFmt.format(row))
