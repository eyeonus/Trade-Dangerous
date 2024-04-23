from commands.commandenv import ResultRow
from commands.parsing import *
from formatting import RowFormat, ColumnFormat

######################################################################
# Parser config

help = 'Describe your command briefly here for the top-level --help.'
name = 'TEMPLATE'       # name of your .py file excluding the _cmd
epilog = None           # text to print at the bottom of --help
wantsTradeDB = True     # Should we try to load the cache at startup?
usesTradeData = True    # Will we be needing trading data?
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
    """
    Implement code that validates arguments, collects and prepares
    any data you will need to generate your results for the user.
    
    If your command has finished and has no output to generate,
    return None, otherwise return "results" to be forwarded to
    the 'render' function.
    
    DO NOT print() during 'run', this allows run() functions to
    be re-used between modules and allows them to be used beyond
    the trade.py command line - e.g. someone writing a TD GUI
    will call run() and then render the results themselves.
    """
    
    ### TODO: Implement
    
    return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
    """
    If run() returns a non-None value, the trade.py code will then
    call the corresponding render() function.
    
    This is where you should generate any output from your command.
    """
    
    ### TODO: Implement
