from commands.commandenv import ResultRow
from commands import MutuallyExclusiveGroup, ParseArgument
from formatting import RowFormat, ColumnFormat

######################################################################
# Parser config

help=#'Terse description of command'
name=#'cmd'
epilog=#None
arguments = [
	#ParseArgument('near', help='System to start from', type=str),
]
switches = [
	#ParseArgument('--ly-per',
	#		help='Maximum light years per jump.',
	#		dest='maxLyPer',
	#		metavar='N.NN',
	#		type=float,
	#	),
]

######################################################################
# Helpers

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):

	### TODO: Implement

	return results

######################################################################
# Transform result set into output

def render(results, cmdenv, tdb):
	### TODO: Implement