from tradeenv import *
import math

def distanceAlongPill(tdb, sc, percent):
	"""
		Estimate a distance along the Pill using 2 reference systems
	"""
	sa = tdb.lookupSystem("Eranin")
	sb = tdb.lookupSystem("HIP 107457")
	dotProduct = (sb.posX-sa.posX) * (sc.posX-sa.posX) \
			   + (sb.posY-sa.posY) * (sc.posY-sa.posY) \
			   + (sb.posZ-sa.posZ) * (sc.posZ-sa.posZ)
	length = math.sqrt((sb.posX-sa.posX) * (sb.posX-sa.posX)
					 + (sb.posY-sa.posY) * (sb.posY-sa.posY)
					 + (sb.posZ-sa.posZ) * (sb.posZ-sa.posZ))
	if percent:
		return 100. * dotProduct / length / length

	return dotProduct / length


def localCommand(tdb, tdenv):
	"""
		Local systems
	"""

	srcSystem = tdenv.nearSystem

	ly = tdenv.maxLyPer or tdb.maxSystemLinkLy

	tdb.buildLinks()

	tdenv.printHeading("Local systems to {} within {} ly.".format(srcSystem.name(), ly))

	distances = { }

	for (destSys, destDist) in srcSystem.links.items():
		if destDist <= ly:
			distances[destSys] = destDist

	detail, pill, percent = tdenv.detail, tdenv.pill, tdenv.percent
	for (system, dist) in sorted(distances.items(), key=lambda x: x[1]):
		pillLength = ""
		if pill or percent:
			pillLengthFormat = " [{:4.0f}%]" if percent else " [{:5.1f}]"
			pillLength = pillLengthFormat.format(distanceAlongPill(tdb, system, percent))
		print("{:5.2f}{} {}".format(dist, pillLength, system.str()))
		if detail:
			for (station) in system.stations:
				stationDistance = " {} ls".format(station.lsFromStar) if station.lsFromStar > 0 else ""
				print("\t<{}>{}".format(station.str(), stationDistance))


subCommand_LOCAL = SubCommandParser(
	name='local',
	cmdFunc=localCommand,
	help='Calculate local systems.',
	arguments = [
		ParseArgument('near', help='System to measure from', type=str),
	],
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
)
