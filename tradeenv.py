# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Argument Parsing/Objects

import argparse             # For parsing command line args.
import sys
import pathlib
import os

from tradeexcept import TradeException

######################################################################
# Exceptions

class CommandLineError(TradeException):
	"""
		Raised when you provide invalid input on the command line.
		Attributes:
			errorstr       What to tell the user.
	"""
	def __init__(self, errorStr):
		self.errorStr = errorStr
	def __str__(self):
		return 'Error in command line: {}'.format(self.errorStr)


class NoDataError(TradeException):
	"""
		Raised when a request is made for which no data can be found.
		Attributes:
			errorStr        Describe the problem to the user.
	"""
	def __init__(self, errorStr):
		self.errorStr = errorStr
	def __str__(self):
		return "Error: {}\n".format(self.errorStr) + (
				"This can happen when there are no profitable trades"
				" matching your criteria, or if you have not yet entered"
				" any price data for the station(s) involved.\n"
				"\n"
				"See '{} update -h' for help entering/updating prices, or"
				" obtain a '.prices' file from the web, such as maddavo's:"
				" http://www.davek.com.au/td/\n"
				"\n"
				"See https://bitbucket.org/kfsone/tradedangerous/wiki/"
					"Price%20Data"
				" for more help."
			).format(sys.argv[0])


######################################################################
# Helpers

class HelpAction(argparse.Action):
	"""
		argparse action helper for printing the argument usage,
		because Python 3.4's argparse is ever-so subtly very broken.
	"""
	def __call__(self, parser, namespace, values, option_string=None):
		parser.print_help()
		sys.exit(0)


class EditAction(argparse.Action):
	"""
		argparse action that stores a value and also flags args._editing
	"""
	def __call__(self, parser, namespace, values, option_string=None):
		setattr(namespace, "_editing", True)
		setattr(namespace, self.dest, values or self.default)


class EditActionStoreTrue(argparse.Action):
	"""
		argparse action that stores True but also flags args._editing
	"""
	def __init__(self, option_strings, dest, nargs=None, **kwargs):
		if nargs is not None:
			raise ValueError("nargs not allowed")
		super(EditActionStoreTrue, self).__init__(option_strings, dest, nargs=0, **kwargs)
	def __call__(self, parser, namespace, values, option_string=None):
		setattr(namespace, "_editing", True)
		setattr(namespace, self.dest, True)


class ParseArgument(object):
	"""
		Provides argument forwarding so that 'makeSubParser' can take function-like arguments.
	"""
	def __init__(self, *args, **kwargs):
		self.args, self.kwargs = args, kwargs


class MutuallyExclusiveGroup(object):
	def __init__(self, *args):
		self.arguments = list(args)


def _addArguments(group, options, required, topGroup=None):
	"""
		Registers a list of options to the specified group. Nodes
		are either an instance of ParseArgument or a list of
		ParseArguments. The list form is considered to be a
		mutually exclusive group of arguments.
	"""
	for option in options:
		if isinstance(option, MutuallyExclusiveGroup):
			exGrp = (topGroup or group).add_mutually_exclusive_group()
			_addArguments(exGrp, option.arguments, required, topGroup=group)
		else:
			assert not required in option.kwargs
			if option.args[0][0] == '-':
				group.add_argument(*(option.args), required=required, **(option.kwargs))
			else:
				group.add_argument(*(option.args), **(option.kwargs))


class SubCommandParser(object):
	"""
		Provide a normalized sub-parser for a specific command. This helps to
		make it easier to keep the command lines consistent and makes the calls
		to build them easier to write/read.
	"""
	def __init__(self, name, cmdFunc, help, arguments=None, switches=None, epilog=None):
		self.name, self.cmdFunc, self.help = name, cmdFunc, help
		self.arguments = arguments
		self.switches = switches
		self.epilog = epilog


	def apply(self, subparsers):
		subParser = subparsers.add_parser(self.name,
									help=self.help,
									add_help=False,
									epilog=self.epilog,
									)

		arguments = self.arguments
		if arguments:
			argParser = subParser.add_argument_group('Required Arguments')
			_addArguments(argParser, arguments, True)

		switchParser = subParser.add_argument_group('Optional Switches')
		switchParser.add_argument('-h', '--help',
				help='Show this help message and exit.',
				action=HelpAction, nargs=0
				)
		_addArguments(switchParser, self.switches, False)

		subParser.set_defaults(subCommand=self.name)
		subParser.set_defaults(cmdFunc=self.cmdFunc)

		return subParser

######################################################################
# TradeEnv class

class TradeEnv(object):
	"""
		Container for command line arguments/settings
		for TradeDangerous.
	"""

	def __init__(self, description=None, subCommandParsers=None, extraArgs=None):
		self.tdb = None
		self._formats = {
		}
		self.subCommand = None
		self.mfd = None

		parser = argparse.ArgumentParser(
					description=description or "TradeDangerous",
					add_help=False,
					epilog='For help on a specific command, use the command followed by -h.'
				)
		parser.set_defaults(_editing=False)

		# Arguments common to all subparsers.
		stdArgs = parser.add_argument_group('Common Switches')
		stdArgs.add_argument('-h', '--help',
					help='Show this help message and exit.',
					action=HelpAction, nargs=0,
				)
		stdArgs.add_argument('--debug', '-w',
					help='Enable diagnostic output.',
					default=0, required=False, action='count',
				)
		stdArgs.add_argument('--detail', '-v',
					help='Increase level  of detail in output.',
					default=0,required=False, action='count',
				)
		stdArgs.add_argument('--quiet', '-q',
					help='Reduce level of detail in output.',
					default=0, required=False, action='count',
				)
		stdArgs.add_argument('--db',
					help='Specify location of the SQLite database.',
					default=None, dest='dbFilename', type=str,
				)
		stdArgs.add_argument('--cwd', '-C',
					help='Change the working directory file accesses are made from.',
					type=str, required=False,
				)
		stdArgs.add_argument('--link-ly', '-L',
					help='Maximum lightyears between systems to be considered linked.',
					default=None, dest='linkLy',
				)

		if extraArgs:
			for arg in extraArgs:
				parser.add_argument(*(arg.args), **(arg.kwargs))

		if subCommandParsers:
			self.subparsers = parser.add_subparsers(dest='subparser', title='Sub-Commands')

			for subParser in subCommandParsers:
				subParser.apply(self.subparsers)

		self._clargs = parser.parse_args()
		if subCommandParsers and 'subCommand' not in self._clargs:
			helpText = "No sub-command specified.\n" + parser.format_help()
			raise CommandLineError(helpText)

		if self.detail and self.quiet:
			raise CommandLineError("'--detail' (-v) and '--quiet' (-q) are mutually exclusive.")

		# If a directory was specified or the program is being run
		# from a different directory than the path of the executable,m
		# change directory.
		if not self.cwd and sys.argv[0]:
			cwdPath = pathlib.Path('.').resolve()
			exePath = pathlib.Path(sys.argv[0]).parent.resolve()
			if cwdPath != exePath:
				self.cwd = str(exePath)
				self.DEBUG(1, "cwd at launch was: {}, changing to {} to match trade.py",
								cwdPath, self.cwd)
		if self.cwd:
			os.chdir(self.cwd)


	def __getattr__(self, key, default=None):
		try:
			return getattr(self._clargs, key, default)
		except AttributeError:
			return default


	def format(self, formatName, defaultFormat,
				*args,
				debugLevel=None, detailLevel=None, isInfo=False,
				**kwargs
				):
		if debugLevel and self.debug < debugLevel:
			return ""
		if detailLevel and self.detail < detailLevel:
			return ""
		if isInfo and not (self.debug or self.detail):
			return ""

		try:
			formatMask = self._formats[formatName]
		except KeyError:
			formatMask = defaultFormat
		return formatMask.format(*args, **kwargs)

	def printHeading(self, text):
		""" Print a line of text followed by a matching line of '-'s. """
		print(text)
		print('-' * len(text))



	def DEBUG(self, debugLevel, outText, *args, **kwargs):
		if self.debug > debugLevel:
			print('#', outText.format(*args, **kwargs))


	def parse(self, tdb):
		self.tdb = tdb

		self.parseMFD()
		self.parseFromToNear()
		self.parseAvoids()
		self.parseVias()
		self.parseShip()

		cmdFunc = self._clargs.cmdFunc
		return cmdFunc(tdb, self)

	def parseMFD(self):
		self.mfd = None
		try:
			if not self.x52pro:
				return
		except AttributeError:
			return

		from mfd import X52ProMFD
		self.mfd = X52ProMFD()


	def parseFromToNear(self):
		origin = getattr(self, 'origin', None)
		if origin:
			self.startStation = self.tdb.lookupStation(origin)
		else:
			self.startStation = None
		origin = getattr(self, 'startSys', None)
		if origin:
			self.startSystem = self.tdb.lookupSystemRelaxed(origin)
		else:
			self.startSystem = None
		dest = getattr(self, 'dest', None)
		if dest:
			self.stopStation = self.tdb.lookupStation(dest)
		else:
			self.stopStation = None
		dest = getattr(self, 'endSys', None)
		if dest:
			self.stopSystem = self.tdb.lookupSystemRelaxed(dest)
		else:
			self.stopSystem = None
		near = getattr(self, 'near', None)
		if near:
			self.nearSystem = self.tdb.lookupSystemRelaxed(near)
		else:
			self.nearSystem = None


	def parseAvoids(self):
		"""
			Process a list of avoidances.
		"""

		avoidItems = self.avoidItems = []
		avoidSystems = self.avoidSystems = []
		avoidStations = self.avoidStations = []

		try:
			avoidances = self.avoid
			if not avoidances:
				return
		except AttributeError:
			return

		tdb = self.tdb

		# You can use --avoid to specify an item, system or station.
		# and you can group them together with commas or list them
		# individually.
		for avoid in ','.join(avoidances).split(','):
			# Is it an item?
			item, system, station = None, None, None
			try:
				item = tdb.lookupItem(avoid)
				avoidItems.append(item)
				if tdb.normalizedStr(item.name()) == tdb.normalizedStr(avoid):
					continue
			except LookupError:
				pass
			# Is it a system perhaps?
			try:
				system = tdb.lookupSystem(avoid)
				avoidSystems.append(system)
				if tdb.normalizedStr(system.str()) == tdb.normalizedStr(avoid):
					continue
			except LookupError:
				pass
			# Or perhaps it is a station
			try:
				station = tdb.lookupStationExplicitly(avoid)
				if (not system) or (station.system is not system):
					avoidSystems.append(station.system)
					avoidStations.append(station)
				if tdb.normalizedStr(station.str()) == tdb.normalizedStr(avoid):
					continue
			except LookupError as e:
				pass

			# If it was none of the above, whine about it
			if not (item or system or station):
				raise CommandLineError("Unknown item/system/station: {}".format(avoid))

			# But if it matched more than once, whine about ambiguity
			if item and system:
				raise AmbiguityError('Avoidance', avoid, [ item, system.str() ])
			if item and station:
				raise AmbiguityError('Avoidance', avoid, [ item, station.str() ])
			if system and station and station.system != system:
				raise AmbiguityError('Avoidance', avoid, [ system.str(), station.str() ])

		self.DEBUG(0, "Avoiding items %s, systems %s, stations %s" % (
					[ item.name() for item in avoidItems ],
					[ system.name() for system in avoidSystems ],
					[ station.name() for station in avoidStations ]
		))


	def parseVias(self):
		""" Process a list of station names and build them into a list of waypoints. """
		viaStationNames = getattr(self._clargs, 'via', None)
		viaStations = self.viaStations = []
		# accept [ "a", "b,c", "d" ] by joining everything and then splitting it.
		if viaStationNames:
			for via in ",".join(viaStationNames).split(","):
				viaStations.add(self.tdb.lookupStation(via))


	def parseShip(self):
		""" Parse user-specified ship and populate capacity and maxLyPer from it. """
		ship = getattr(self._clargs, 'ship', None)
		if ship:
			ship = self.ship = self.tdb.lookupShip(ship)
			self.capacity = self.capacity or ship.capacity
			self.maxLyPer = self.maxLyPer or ship.maxLyFull
