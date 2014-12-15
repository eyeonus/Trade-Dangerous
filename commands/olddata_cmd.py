from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
import math
from tradeexcept import TradeException
import itertools

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

    stmt = """
            SELECT  si.station_id,
                    JULIANDAY('NOW') - JULIANDAY(MAX(si.modified)),
                    stn.ls_from_star
              FROM  StationItem as si
                    INNER JOIN Station stn USING (station_id)
             GROUP  BY 1
             ORDER  BY 2 DESC
             {limit}
    """.format(
            limit=limitClause
    )

    cmdenv.DEBUG1(stmt)

    for (stnID, age, ls) in tdb.query(stmt):
        cmdenv.DEBUG2("{}:{}:{}", stnID, age, ls)
        row = ResultRow()
        row.station = tdb.stationByID[stnID]
        row.age = age
        if ls:
            row.ls = "{:n}".format(ls)
        else:
            row.ls = "?"
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
            ).append(
                ColumnFormat("Age/days", '>', '8', '.2f',
                        key=lambda row: row.age)
            ).append(
                ColumnFormat("Ls/Star", '>', '10',
                        key=lambda row: row.ls)
            )

    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(rowFmt.format(row))

