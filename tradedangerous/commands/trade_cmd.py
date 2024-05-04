from .exceptions import CommandLineError
from .parsing import ParseArgument
from ..tradecalc import TradeCalc
from ..formatting import RowFormat, max_len

######################################################################
# Parser config

help='Find potential trades between two given stations.'
name='trade'
epilog=None
wantsTradeDB=True
arguments = [
    ParseArgument(
        'origin',
        help='Station you are purchasing from.',
        type=str,
    ),
    ParseArgument(
        'dest',
        help='Station you are selling to.',
        type=str,
    ),
]
switches = [
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from .commandenv import ResultRow
    
    calc = TradeCalc(tdb, cmdenv)
    
    lhs = cmdenv.startStation
    rhs = cmdenv.stopStation
    
    if lhs == rhs:
        raise CommandLineError("Must specify two different stations.")
    
    results.summary = ResultRow()
    results.summary.fromStation = lhs
    results.summary.toStation = rhs
    
    trades = calc.getTrades(lhs, rhs)
    if not trades:
        raise CommandLineError("No profitable trades {} -> {}".format(
            lhs.name(), rhs.name()
        ))
    
    if cmdenv.detail > 1:
        tdb.getAverageSelling()
        tdb.getAverageBuying()
    
    for item in trades:
        results.rows.append(item)
    
    return results

#######################################################################
## Transform result set into output

def render(results, cmdenv, tdb):
    longestNameLen = max_len(results.rows, key=lambda row: row.item.name(cmdenv.detail))
    
    rowFmt = RowFormat()
    rowFmt.addColumn('Item', '<', longestNameLen,
            key=lambda row: row.item.name(cmdenv.detail))
    rowFmt.addColumn('Profit', '>', 10, 'n',
            key=lambda row: row.gainCr)
    rowFmt.addColumn('Cost', '>', 10, 'n',
            key=lambda row: row.costCr)
    if cmdenv.detail > 1:
        rowFmt.addColumn('AvgCost', '>', 10,
            key=lambda row: tdb.avgSelling.get(row.item.ID, 0)
        )
        rowFmt.addColumn('Buying', '>', 10,
            key=lambda row: row.costCr + row.gainCr
        )
        rowFmt.addColumn('AvgBuy', '>', 10,
            key=lambda row: tdb.avgBuying.get(row.item.ID, 0)
        )
    
    if cmdenv.detail:
        rowFmt.addColumn('Supply', '>', 10,
            key=lambda row: '{:n}'.format(row.supply) if row.supply >= 0 else '?')
        rowFmt.addColumn('Demand', '>', 10,
            key=lambda row: '{:n}'.format(row.demand) if row.demand >= 0 else '?')
        rowFmt.addColumn('SrcAge', '>', 8, '.2f',
            key=lambda row: (row.srcAge / 86400))
        rowFmt.addColumn('DstAge', '>', 8, '.2f',
            key=lambda row: (row.dstAge / 86400))
    
    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')
    
    for row in results.rows:
        print(rowFmt.format(row))
