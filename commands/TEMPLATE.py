from commands.parsing import MutuallyExclusiveGroup, ParseArgument

######################################################################
# Parser config

help=#'Terse description of command'
name=#'cmd'
epilog=#None
wantsTradeDB=True
arguments = [
    #ParseArgument('near', help='System to start from', type=str),
]
switches = [
    #ParseArgument('--ly-per',
    #       help='Maximum light years per jump.',
    #       dest='maxLyPer',
    #       metavar='N.NN',
    #       type=float,
    #   ),
]

######################################################################
# Helpers

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from commands.commandenv import ResultRow

    ### TODO: Implement

    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    from formatting import RowFormat, ColumnFormat

    ### TODO: Implement
