from tradeenv import *

def buyCommand(tdb, tdenv):
	"""
		Locate places selling a given item.
	"""

	item = tdb.lookupItem(tdenv.item)

	# Constraints
	constraints = [ "(item_id = ?)", "buy_from > 0", "stock != 0" ]
	bindValues = [ item.ID ]

	if tdenv.quantity:
		constraints.append("(stock = -1 or stock >= ?)")
		bindValues.append(tdenv.quantity)

	near = tdenv.near
	if near:
		tdb.buildLinks()
		nearSystem = tdb.lookupSystem(near)
		maxLy = float("inf") if tdenv.maxLyPer is None else tdenv.maxLyPer
		# Uh - why haven't I made a function on System to get a
		# list of all the systems within N hops at L ly per hop?
		stations = []
		for station in nearSystem.stations:
			if station.itemCount > 0:
				stations.append(str(station.ID))
		for system, dist in nearSystem.links.items():
			if dist <= maxLy:
				for station in system.stations:
					if station.itemCount > 0:
						stations.append(str(station.ID))
		if not stations:
			raise NoDataError("No stations listed as selling items within range")
		constraints.append("station_id IN ({})".format(','.join(stations)))

	whereClause = ' AND '.join(constraints)
	stmt = """
				SELECT station_id, buy_from, stock
				  FROM Price
				 WHERE {}
			""".format(whereClause)
	if tdenv.debug:
		print("* SQL: {}".format(stmt))
	cur = tdb.query(stmt, bindValues)

	from collections import namedtuple
	Result = namedtuple('Result', [ 'station', 'cost', 'stock', 'dist' ])
	results = []
	stationByID = tdb.stationByID
	dist = 0.0
	for (stationID, costCr, stock) in cur:
		stn = stationByID[stationID]
		if near:
			dist = stn.system.links[nearSystem] if stn.system != nearSystem else 0.0
		results.append(Result(stationByID[stationID], costCr, stock, dist))

	if not results:
		raise NoDataError("No available items found")

	if tdenv.sortByStock:
		results.sort(key=lambda result: result.cost)
		results.sort(key=lambda result: result.stock, reverse=True)
	else:
		results.sort(key=lambda result: result.stock, reverse=True)
		results.sort(key=lambda result: result.cost)
		if near and not tdenv.sortByPrice:
			results.sort(key=lambda result: result.dist)

	maxStnNameLen = len(max(results, key=lambda result: len(result.station.dbname) + len(result.station.system.dbname) + 1).station.name())
	tdenv.printHeading("{station:<{maxStnLen}} {cost:>10} {stock:>10} {dist:{distFmt}}".format(
							station="Station", cost="Cost", stock="Stock",
							dist="Ly" if near else "",
							maxStnLen=maxStnNameLen,
							distFmt=">6" if near else ""
		))
	for result in results:
		print("{station:<{maxStnLen}} {cost:>10n} {stock:>10} {dist:{distFmt}}".format(
				station=result.station.name(),
				cost=result.cost,
				stock="{:n}".format(result.stock) if result.stock > 0 else "",
				dist=result.dist if near else "",
				maxStnLen=maxStnNameLen,
				distFmt=">6.2f" if near else ""
			))

subCommand_BUY = SubCommandParser(
	name='buy',
	cmdFunc=buyCommand,
	help='Find places to buy a given item within range of a given station.',
	arguments = [
		ParseArgument('item', help='Name of item to query.', type=str),
	],
	switches = [
		ParseArgument('--quantity',
				help='Require at least this quantity.',
				default=0,
				type=int,
			),
		ParseArgument('--near',
				help='Find sellers within jump range of this system.',
				type=str
			),
		ParseArgument('--ly-per',
				help='Maximum light years per jump.',
				default=None,
				dest='maxLyPer',
				metavar='N.NN',
				type=float,
			),
		MutuallyExclusiveGroup(
			ParseArgument('--price-sort', '-P',
					help='(When using --near) Sort by price not distance',
					action='store_true',
					default=False,
					dest='sortByPrice',
				),
			ParseArgument('--stock-sort', '-S',
					help='Sort by stock followed by price',
					action='store_true',
					default=False,
					dest='sortByStock',
				),
		),
	],
)
