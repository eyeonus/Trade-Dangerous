
from tradeenv import *

def getEditorPaths(tdenv, editorName, envVar, windowsFolders, winExe, nixExe):
	tdenv.DEBUG(0, "Locating {} editor", editorName)
	try:
		return os.environ[envVar]
	except KeyError: pass

	paths = []

	import platform
	system = platform.system()
	if system == 'Windows':
		binary = winExe
		for folder in ["Program Files", "Program Files (x86)"]:
			for version in windowsFolders:
				paths.append("{}\\{}\\{}".format(os.environ['SystemDrive'], folder, version))
	else:
		binary = nixExe

	try:
		paths += os.environ['PATH'].split(os.pathsep)
	except KeyError: pass

	for path in paths:
		candidate = os.path.join(path, binary)
		try:
			if pathlib.Path(candidate).exists():
				return candidate
		except OSError:
			pass

	raise CommandLineError("ERROR: Unable to locate {} editor.\nEither specify the path to your editor with --editor or set the {} environment variable to point to it.".format(editorName, envVar))


def editUpdate(tdb, tdenv, stationID):
	"""
		Dump the price data for a specific station to a file and
		launch the user's text editor to let them make changes
		to the file.

		If the user makes changes, re-load the file, update the
		database and regenerate the master .prices file.
	"""

	tdenv.DEBUG(0, "'update' mode with editor. editor:{} station:{}",
					tdenv.editor, tdenv.origin)

	import buildcache
	import prices
	import subprocess
	import os

	editor, editorArgs = tdenv.editor, []
	if tdenv.sublime:
		tdenv.DEBUG(0, "Sublime mode")
		if not editor:
			editor = getEditorPaths(tdenv, "sublime", "SUBLIME_EDITOR", ["Sublime Text 3", "Sublime Text 2"], "sublime_text.exe", "subl")
		editorArgs += [ "--wait" ]
	elif tdenv.npp:
		tdenv.DEBUG(0, "Notepad++ mode")
		if not editor:
			editor = getEditorPaths(tdenv, "notepad++", "NOTEPADPP_EDITOR", ["Notepad++"], "notepad++.exe", "notepad++")
		if not tdenv.quiet:
			print("NOTE: You'll need to exit Notepad++ to return control back to trade.py")
	elif tdenv.vim:
		tdenv.DEBUG(0, "VI iMproved mode")
		if not editor:
			# Hack... Hackity hack, hack, hack.
			# This has a disadvantage in that: we don't check for just "vim" (no .exe) under Windows
			vimDirs = [ "Git\\share\\vim\\vim{}".format(vimVer) for vimVer in range(70,75) ]
			editor = getEditorPaths(tdenv, "vim", "EDITOR", vimDirs, "vim.exe", "vim")
	elif tdenv.notepad:
		tdenv.DEBUG(0, "Notepad mode")
		editor = "notepad.exe"  # herp

	try:
		envArgs = os.environ["EDITOR_ARGS"]
		if envArgs: editorArgs += envArgs.split(' ')
	except KeyError: pass

	# Create a temporary text file with a list of the price data.
	tmpPath = pathlib.Path("prices.tmp")
	if tmpPath.exists():
		print("ERROR: Temporary file ({}) already exists.".format(tmpPath))
		sys.exit(1)
	absoluteFilename = None
	dbFilename = tdenv.dbFilename or tdb.defaultDB
	try:
		elementMask = prices.Element.basic
		if tdenv.supply: elementMask |= prices.Element.supply
		if tdenv.timestamps: elementMask |= prices.Element.timestamp
		# Open the file and dump data to it.
		with tmpPath.open("w") as tmpFile:
			# Remember the filename so we know we need to delete it.
			absoluteFilename = str(tmpPath.resolve())
			prices.dumpPrices(dbFilename, elementMask,
								file=tmpFile,
								stationID=stationID,
								defaultZero=tdenv.forceNa,
								debug=tdenv.debug)

		# Stat the file so we can determine if the user writes to it.
		# Use the most recent create/modified timestamp.
		preStat = tmpPath.stat()
		preStamp = max(preStat.st_mtime, preStat.st_ctime)

		# Launch the editor
		editorCommandLine = [ editor ] + editorArgs + [ absoluteFilename ]
		tdenv.DEBUG(0, "Invoking [{}]", ' '.join(editorCommandLine))
		try:
			result = subprocess.call(editorCommandLine)
		except FileNotFoundError:
			raise CommandLineError("Unable to launch specified editor: {}".format(editorCommandLine))
		if result != 0:
			print("NOTE: Edit failed ({}), nothing to import.".format(result))
			sys.exit(1)

		# Did they update the file? Some editors destroy the file and rewrite it,
		# other files just write back to it, and some OSes do weird things with
		# these timestamps. That's why we have to use both mtime and ctime.
		postStat = tmpPath.stat()
		postStamp = max(postStat.st_mtime, postStat.st_ctime)

		if postStamp == preStamp:
			import random
			print("- No changes detected - doing nothing. {}".format(random.choice([
					"Brilliant!", "I'll get my coat.", "I ain't seen you.", "You ain't seen me", "... which was nice", "Bingo!", "Scorchio!", "Boutros, boutros, ghali!", "I'm Ed Winchester!", "Suit you, sir! Oh!"
				])))
			sys.exit(0)

		tdenv.DEBUG(0, "File changed - importing data.")

		buildcache.processPricesFile(tdenv,
						 db=tdb.getDB(),
						 pricesPath=tmpPath,
						 stationID=stationID,
						 defaultZero=tdenv.forceNa
					)

		# If everything worked, we need to re-build the prices file.
		tdenv.DEBUG(0, "Update complete, regenerating .prices file")

		with tdb.pricesPath.open("w") as pricesFile:
			prices.dumpPrices(dbFilename, prices.Element.full, file=pricesFile, debug=tdenv.debug)

		# Update the DB file so we don't regenerate it.
		pathlib.Path(dbFilename).touch()

	finally:
		# If we created the file, we delete the file.
		if absoluteFilename: tmpPath.unlink()


def updateCommand(tdb, tdenv):
	"""
		Allow the user to update the prices database.
	"""

	station = tdenv.startStation
	stationID = station.ID

	if tdenv.all or tdenv.zero:
		raise CommandLineError("--all and --zero have been removed. Use '--supply' (-S for short) if you want to edit demand and stock values during update. Use '--timestamps' (-T for short) if you want to include timestamps.")

	if tdenv._editing:
		# User specified one of the options to use an editor.
		return editUpdate(tdb, tdenv, stationID)

	tdenv.DEBUG(0, 'guided "update" mode station:{}', station)

	print("Guided mode not implemented yet. Try using --editor, --sublime or --notepad")


subCommand_UPDATE = SubCommandParser(
	name='update',
	cmdFunc=updateCommand,
	help='Update prices for a station.',
	epilog="Generates a human-readable version of the price list for a given station "
				"and opens it in the specified text editor.\n"
				"The format is intended to closely resemble the presentation of the "
				"market in-game. If you change the order items are listed in, "
				"the order will be kept for future edits, making it easier to quickly "
				"check for changes.",
	arguments = [
		ParseArgument('origin', help='Name of the station to update.', type=str)
	],
	switches = [
		ParseArgument('--editor',
				help='Generates a text file containing the prices for the station and '
						'loads it into the specified editor for you.',
				action=EditAction,
				default=None,
				type=str,
			),
		ParseArgument('--supply', '-S', 
				help='Includes demand and stock (supply) values in the update.',
				action='store_true',
				default=False,
			),
		ParseArgument('--timestamps', '-T', 
				help='Includes timestamps in the update.',
				action='store_true',
				default=False,
			),
		ParseArgument('--force-na', '-0', 
				help="Forces 'unk' supply to become 'n/a' by default",
				action='store_true',
				default=False,
				dest='forceNa',
			),
		MutuallyExclusiveGroup(
			ParseArgument('--sublime', 
					help='Like --editor but uses Sublime Text (2 or 3), which is nice.',
					action=EditActionStoreTrue,
				),
			ParseArgument('--notepad', 
					help='Like --editor but uses Notepad.',
					action=EditActionStoreTrue,
				),
			ParseArgument('--npp',     
					help='Like --editor but uses Notepad++.',
					action=EditActionStoreTrue,
				),
			ParseArgument('--vim',     
					help='Like --editor but uses vim.',
					action=EditActionStoreTrue,
				),
		)
	]
)
