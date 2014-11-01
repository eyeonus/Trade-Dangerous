from commands import MutuallyExclusiveGroup, ParseArgument
from formatting import RowFormat, ColumnFormat
import math

name='local'
help='Calculate local systems.'
epilog=None
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
	MutuallyExclusiveGroup(
		ParseArgument('--pill',
				help='Show distance along the pill in ly.',
				action='store_true',
				default=False,
			),
		ParseArgument('--percent',
				help='Show distance along pill as percentage.',
				action='store_true',
				default=False,
			),
	),
]

class PillCalculator(object):
	def __init__(self, startStar, endStar, percent):
		lhs, rhs = tdb.lookupSystem(startStar), tdb.lookupSystem(endStar)
		self.normal = [
			rhs.posX - lhs.posX,
			rhs.posY - lhs.posY,
			rhs.posZ - lhs.posZ
		]
		length2 = (normal[0]**2) + (normal[1]**2) + (normal[2]**2)
		self.pillLength = math.sqrt(length2)
		self.lhs = lhs
		self.percent = percent

	def distance(self, star):
		lhs, normal = self.lhs, self.normal
		dotProduct = ((normal[0] * (lhs.posX - star.posX)) +
					  (normal[1] * (lhs.posY - star.posY)) +
					  (normal[2] * (lhs.posZ - star.posZ)))
		if self.percent:
			return (100. * dotProduct / self.pillLength) / self.pillLength
		else:
			return dotProduct / self.pillLength


@staticmethod
def check(tdb, tdenv):
	pass

@staticmethod
def run(tdb, tdenv, results):
	srcSystem = tdenv.nearSystem

	ly = tdenv.maxLyPer or tdb.maxSystemLinkLy

	tdb.buildLinks()

	results.summary = {
		'heading': {
			'near': srcSystem,
			'ly'  : ly
		}
	}

	distances = { }

	for (destSys, destDist) in srcSystem.links.items():
		if destDist <= ly:
			distances[destSys] = destDist

	detail = tdenv.detai
	if tdenv.pill or tdenv.percent:
		pillCalc = PillCalculator(tdb, pill.percent)
	else:
		pillCalc = None

	for (system, dist) in sorted(distances.items(), key=lambda x: x[1]):
		row = {
			'system': system,
			'dist'  : dist,
		}
		if pillCalc:
			row['pill'] = pillCalc.distance(system)
		if detail:
			row['stations'] = []
			for (station) in system.stations:
				row.stations.append({'station': station, 'dist': station.lsFromStar})
				stationDistance = " {} ls".format(station.lsFromStar) if station.lsFromStar > 0 else ""
				print("\t<{}>{}".format(station.str(), stationDistance))
		results.data.append(row)

	return results


@staticmethod
def render(tdb, tdenv, results):
	longestName = max(results.data, key=lambda row: row.system.name()).system.name()
	sysRowFmt = RowFormat().append(
				ColumnFormat("System", '<', longestName,
						key=lambda row: row.system.name())
			).append(
				ColumnFormat("Dist", '>', '6', '.2f',
						key=lambda row: row.system.name())
			)

	if tdenv.percent:
		sysRowFmt.append(after='System',
			col=ColumnFormat("Pill", '>', '4', '.0f', pre='[', post='%]',
						key=lambda row: row.system.pill))
	elif tdenv.pill:
		sysRowFmt.append(after='System',
			col=ColumnFormat("PillLy", '>', '6', '.2f', pre='[', post=']'))

	if tdenv.detail:
		stnRowFmt = RowFormat(prefix='  +  ').append(
				ColumnFormat("Station", '.<', 32,
						key=lambda row: row.station.str())
			).append(
				ColumnFormat("Dist", '>', '9',
						key=lambda row: '{}ls'.format(row.dist) if row.dist else '')
			)

	heading = sysRowFmt.str()
	subHeading = '-' * len(heading)
	print("Systems within {sys}ly of {ly:<5.2f}.\n"
			"{heading}\n"
			"{subHeading}".format(
				sys=results.heading.near.name(),
				ly=results.heading.ly,
				headig=heading,
				subHeading=subHeading
		))

	for row in results.data:
		print(sysRowFmt.format(row))
		for stnRow in row.stations:
			print(stnRowFmt.format(stnRow))
