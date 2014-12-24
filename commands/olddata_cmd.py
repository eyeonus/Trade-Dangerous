from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from tradedb import TradeDB
from tradeexcept import TradeException

import itertools
import math

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
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    cmdenv = results.cmdenv
    tdb = cmdenv.tdb
    srcSystem = cmdenv.nearSystem

    results.summary = ResultRow()
    results.limit = cmdenv.limit

    if cmdenv.limit:
        limitClause = "LIMIT {}".format(cmdenv.limit)
    else:
        limitClause = ""

    fields = [
        "si.station_id",
        "JULIANDAY('NOW') - JULIANDAY(MAX(si.modified))",
        "stn.ls_from_star",
    ]

    joins = []
    wheres = []
    havings = []

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
             {limit}
    """.format(
            fields=fieldStr,
            joins=joinStr,
            wheres=whereStr,
            having=haveStr,
            limit=limitClause,
    )

    cmdenv.DEBUG1(stmt)

    for (stnID, age, ls, dist2) in tdb.query(stmt):
        cmdenv.DEBUG2("{}:{}:{}", stnID, age, ls)
        row = ResultRow()
        row.station = tdb.stationByID[stnID]
        row.age = age
        if ls:
            row.ls = "{:n}".format(ls)
        else:
            row.ls = "?"
        row.dist2 = dist2
        results.rows.append(row)

    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

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

    if cmdenv.nearSystem:
        rowFmt.addColumn('Dist', '>', 6, '.2f',
                key=lambda row: math.sqrt(row.dist2))
    
    rowFmt.append(
            ColumnFormat("Age/days", '>', '8', '.2f',
                    key=lambda row: row.age)
    ).append(
            ColumnFormat("Ls/Star", '>', '10',
                    key=lambda row: row.ls)
    ).append(
            ColumnFormat("Pad", '>', '3',
                    key=lambda row: \
                        TradeDB.padSizes[row.station.maxPadSize])
    )

    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(rowFmt.format(row))

