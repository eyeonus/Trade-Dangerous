from .parsing import (
    FleetCarrierArgument, MutuallyExclusiveGroup, NoPlanetSwitch,
    OdysseyArgument, ParseArgument, PadSizeArgument, PlanetaryArgument,
)
from ..tradedb import TradeDB
from ..tradeexcept import TradeException
from sqlalchemy import select, table, column, func, literal
from sqlalchemy.orm import Session


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
    """
    Backend-neutral rework:
      - Use SQLAlchemy Core to compute age and (optionally) distance².
      - age: age_in_days(session, MAX(StationItem.modified)) AS age_days
      - dist2: (sys.pos_x - x0)^2 + (sys.pos_y - y0)^2 + (sys.pos_z - z0)^2 (when --near)
      - Materialize rows to avoid closed-cursor errors.
      - Preserve downstream filters/sorting/limit exactly as before.
    """
    from .commandenv import ResultRow
    from tradedangerous.db.utils import age_in_days
    
    cmdenv = results.cmdenv
    tdb = cmdenv.tdb
    
    results.summary = ResultRow()
    results.limit = cmdenv.limit
    
    # SQLAlchemy lightweight table defs
    si = table(
        "StationItem",
        column("station_id"),
        column("item_id"),
        column("modified"),
    )
    stn = table(
        "Station",
        column("station_id"),
        column("system_id"),
        column("ls_from_star"),
    )
    sys_tbl = table(
        "System",
        column("system_id"),
        column("pos_x"),
        column("pos_y"),
        column("pos_z"),
    )
    
    # Build session bound to current engine (age_in_days needs the session)
    session = Session(bind=tdb.engine)
    
    # Base SELECT: station_id, ls_from_star, age_days
    age_expr = age_in_days(session, func.max(si.c.modified)).label("age_days")
    
    # Optional near-system distance²
    nearSys = cmdenv.nearSystem
    join_sys = False
    if nearSys:
        dx = (sys_tbl.c.pos_x - literal(nearSys.posX))
        dy = (sys_tbl.c.pos_y - literal(nearSys.posY))
        dz = (sys_tbl.c.pos_z - literal(nearSys.posZ))
        dist2_expr = (dx * dx + dy * dy + dz * dz).label("d2")
    else:
        dist2_expr = literal(0.0).label("d2")
    
    stmt = (
        select(
            si.c.station_id,
            age_expr,
            stn.c.ls_from_star,
            dist2_expr,
        )
        .select_from(
            si.join(stn, stn.c.station_id == si.c.station_id)
            .join(sys_tbl, sys_tbl.c.system_id == stn.c.system_id) if nearSys
            else si.join(stn, stn.c.station_id == si.c.station_id)
        )
        .group_by(si.c.station_id, stn.c.ls_from_star, dist2_expr)
        .order_by(age_expr.desc())
    )
    
    # Bounding box for near (keeps scan small, mirrors original)
    if nearSys:
        maxLy = cmdenv.maxLyPer or tdb.maxSystemLinkLy
        # Bounding box predicate
        stmt = stmt.where(
            sys_tbl.c.pos_x.between(nearSys.posX - maxLy, nearSys.posX + maxLy),
            sys_tbl.c.pos_y.between(nearSys.posY - maxLy, nearSys.posY + maxLy),
            sys_tbl.c.pos_z.between(nearSys.posZ - maxLy, nearSys.posZ + maxLy),
        )
        # Radius filter: HAVING dist2 <= maxLy^2
        stmt = stmt.having(dist2_expr <= (maxLy * maxLy))
    
    # Min-age filter (apply to aggregated age of MAX(modified))
    if cmdenv.minAge:
        stmt = stmt.having(age_expr >= float(cmdenv.minAge))
    
    # Execute and materialize rows
    rows = session.execute(stmt).fetchall()
    session.close()
    
    # Downstream filters (unchanged)
    padSize = cmdenv.padSize
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    odyssey = cmdenv.odyssey
    noPlanet = cmdenv.noPlanet
    mls = cmdenv.maxLs
    
    for (stnID, age, ls, dist2) in rows:
        cmdenv.DEBUG2("{}:{}:{}", stnID, age, ls)
        row = ResultRow()
        row.station = tdb.stationByID[stnID]
        row.age = float(age or 0.0)
        row.ls = "{:n}".format(ls) if ls else "?"
        row.dist = (float(dist2) ** 0.5) if dist2 else 0.0
        
        if padSize and not row.station.checkPadSize(padSize):
            continue
        if planetary and not row.station.checkPlanetary(planetary):
            continue
        if fleet and not row.station.checkFleet(fleet):
            continue
        if odyssey and not row.station.checkOdyssey(odyssey):
            continue
        if noPlanet and row.station.planetary != 'N':
            continue
        if mls and row.station.lsFromStar > mls:
            continue
        
        results.rows.append(row)
    
    # Route optimization and limiting (unchanged)
    if cmdenv.route and len(results.rows) > 1:
        def walk(start_idx, dist):
            rows_ = results.rows
            startNode = rows_[start_idx]
            openList = set(rows_)
            path = [startNode]
            openList.remove(startNode)
            while len(path) < len(rows_):
                lastNode = path[-1]
                distFn = lastNode.station.system.distanceTo
                nearest = min(openList, key=lambda r: distFn(r.station.system))
                openList.remove(nearest)
                path.append(nearest)
                dist += distFn(nearest.station.system)
            return (path, dist)
        
        if cmdenv.near:
            bestPath = walk(0, results.rows[0].dist)
        else:
            bestPath = (results.rows, float("inf"))
            for i in range(len(results.rows)):
                candidate = walk(i, 0)
                if candidate[1] < bestPath[1]:
                    bestPath = candidate
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
