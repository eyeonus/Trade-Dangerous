import os
import re
import pathlib
import tradedb
import tradeenv
import csvexport
import time as _time
from datetime import datetime, time, timedelta, timezone

from plugins import PluginException, ImportPluginBase

def snapToGrid32(val):
	try:
		val = float(val)
		if val < 0: corr = -0.5
		else:       corr = +0.5
		pos = int(val*32+corr)/32
	except:
		pos = None
		pass
	return pos


class ImportPlugin(ImportPluginBase):
	"""
	Plugin that parses the netLog file and add or update the system.
	"""

	logGlob = "netLog.*.log"
	ADDED_NAME = 'netLog'
	LOGDIR_NAME = "FDEVLOGDIR"
	DATE_FORMATS = {
		 2: ("%y",       "YY",         "%y"),
		 4: ("%Y",       "YYYY",       "%y"),
		 5: ("%y-%m",    "YY-MM",      "%y%m"),
		 7: ("%Y-%m",    "YYYY-MM",    "%y%m"),
		 8: ("%y-%m-%d", "YY-MM-DD",   "%y%m%d"),
		10: ("%Y-%m-%d", "YYYY-MM-DD", "%y%m%d"),
	}
	ignoreSysNames  = [
		'TRAINING',
		'DESTINATION',
	]

	pluginOptions = {
		'show': "Only show the system name and position. Don't update the DB.",
		'last': "Only parse the last (newest) netLog file.",
		'date': "Only parse netLog files from date, format=[YY]YY[-MM[-DD]].",
	}

	def __init__(self, tdb, tdenv):
		super().__init__(tdb, tdenv)

		logDirName = os.getenv(self.LOGDIR_NAME, None)
		if not logDirName:
			raise PluginException(
				"Environment variable '{}' not set "
				"(see 'README.md' for help)."
				.format(self.LOGDIR_NAME)
			)
		tdenv.NOTE("{}={}", self.LOGDIR_NAME, logDirName)

		self.logPath = pathlib.Path(logDirName)
		if not self.logPath.is_dir():
			raise PluginException(
				"{}: is not a directory.".format(
					str(self.logPath)
				)
			)

	def parseLogDirList(self):
		"""
		parse netLog files
		"""
		# HEADER: 16-07-02-00:18 Mitteleuropäische Sommerzeit  (22:18 GMT) - part 1
		# SYSTEM: {00:20:24} System:"Caelinus" StarPos:(0.188,-18.625,52.063)ly  NormalFlight
		tdb, tdenv = self.tdb, self.tdenv
		optShow = self.getOption("show")

		sysRegEx  = re.compile('^\{\d\d:\d\d:\d\d\}\s+System:"(?P<sysName>[^"]+)".*StarPos:\((?P<sysPos>[^)]+)\)ly')
		dateRegEx = re.compile('^\{(?P<logTime>\d\d:\d\d:\d\d)\}')

		sysCount = 0
		logSysList = {}
		for filePath in self.filePathList:
			tdenv.NOTE("parsing '{}'", filePath.name)
			oldCount = sysCount
			with filePath.open() as logFile:
				lineCount = 0
				for line in logFile:
					lineCount += 1
					line = line.strip('\r\n')
					if lineCount == 1:
						# parse first line to get the first date and GMT offset
						tdenv.DEBUG0(" HEADER: {}", line.replace("{", "{{").replace("}", "}}"))
						try:
							headDate = line.split()[0]
							headDate = datetime.fromtimestamp(
								_time.mktime(
									_time.strptime(headDate, '%y-%m-%d-%H:%M')
								),
								timezone.utc
							).astimezone()
						except:
							headDate = None
							pass
						tdenv.DEBUG0("   DATE: {}", headDate)
						if not headDate:
							raise PluginException("Doesn't seem do be a FDEV netLog file")
						lastDate = logDate = headDate
					else:
						tdenv.DEBUG1("LOGLINE: {}", line.replace("{", "{{").replace("}", "}}"))
						# check every line for new time to enhance the lastDate
						logTimeMatch = dateRegEx.match(line)
						if logTimeMatch:
							h, m, s = logTimeMatch.group('logTime').split(":")
							logTime = time(int(h), int(m), int(s), tzinfo=lastDate.tzinfo)
							logDate = datetime.combine(lastDate, logTime)
							if logDate < lastDate:
								logDate += timedelta(days=1)
							tdenv.DEBUG1("LOGDATE: {}", logDate)

						sysMatch = sysRegEx.match(line)
						if sysMatch:
							# we found a system, yeah
							sysDate = logDate
							sysName = sysMatch.group('sysName')
							sysPos  = sysMatch.group('sysPos')
							sysPosX, sysPosY, sysPosZ = sysPos.split(',')
							sysPosX = snapToGrid32(sysPosX)
							sysPosY = snapToGrid32(sysPosY)
							sysPosZ = snapToGrid32(sysPosZ)
							tdenv.DEBUG0(" SYSTEM: {} {} {} {} {}", sysDate, sysName, sysPosX, sysPosY, sysPosZ)
							logSysList[sysName] = (sysPosX, sysPosY, sysPosZ, sysDate)

						lastDate = logDate
			sysCount = len(logSysList)
			tdenv.NOTE("Found {} System(s).", sysCount-oldCount)

		if not optShow:
			try:
				idNetLog = tdb.lookupAdded(self.ADDED_NAME)
			except KeyError:
				tdenv.WARN("Entry '{}' not found in 'Added' table.", self.ADDED_NAME)
				tdenv.WARN("Trying to add it myself.")
				db = tdb.getDB()
				cur = db.cursor()
				cur.execute(
					"""
					INSERT INTO Added(name) VALUES(?)
					""",
					[self.ADDED_NAME]
				)
				db.commit()
				tdenv.NOTE("Export Table 'Added'")
				_, path = csvexport.exportTableToFile(tdb, tdenv, "Added")
				pass

		addCount = 0
		oldCount = 0
		newCount = 0
		for sysName in logSysList:
			sysPosX, sysPosY, sysPosZ, sysDate = logSysList[sysName]
			utcDate = sysDate.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
			tdenv.DEBUG0("log system '{}' ({}, {}, {}, {})",
				sysName, sysPosX, sysPosY, sysPosZ, utcDate
			)
			if sysName.upper() in self.ignoreSysNames:
				tdenv.NOTE("Ignoring system: '{}'", sysName)
				continue
			systemTD = tdb.systemByName.get(sysName.upper(), None)
			if systemTD:
				# we allready know the system, check coords
				tdenv.DEBUG0("Old system '{}' ({}, {}, {}, '{}')",
					sysName, sysPosX, sysPosY, sysPosZ, utcDate
				)
				oldCount += 1
				if not (systemTD.posX == sysPosX and
				        systemTD.posY == sysPosY and
				        systemTD.posZ == sysPosZ):
					tdenv.WARN("System '{}' has different coordinates:", sysName)
					tdenv.WARN("   database: {}, {}, {}", systemTD.posX, systemTD.posY, systemTD.posZ)
					tdenv.WARN("     netlog: {}, {}, {}", sysPosX, sysPosY, sysPosZ)
			else:
				# new system
				tdenv.NOTE("New system '{}' ({}, {}, {}, '{}')",
					sysName, sysPosX, sysPosY, sysPosZ, utcDate
				)
				newCount += 1
				if not optShow:
					tdb.addLocalSystem(
						sysName.upper(),
						sysPosX, sysPosY, sysPosZ,
						added=self.ADDED_NAME,
						modified=utcDate,
						commit=False
					)
					addCount += 1

		tdenv.NOTE("Found {:>3} System(s) altogether.", sysCount)
		if oldCount:
			tdenv.NOTE("      {:>3} old", oldCount)
		if newCount:
			tdenv.NOTE("      {:>3} new", newCount)
		if addCount:
			tdenv.NOTE("      {:>3} added", addCount)
			tdb.getDB().commit()
			tdenv.NOTE("Export Table 'System'")
			_, path = csvexport.exportTableToFile(tdb, tdenv, "System")

	def getLogDirList(self):
		"""
		get all netLog files
		"""
		tdenv   = self.tdenv
		logDate = self.getOption("date")
		logLast = self.getOption("last")

		self.logDate = None
		if isinstance(logDate, str):
			self.fmtDate = len(logDate)
			fmt = self.DATE_FORMATS.get(self.fmtDate, (None, None, None))
			if fmt[0]:
				tdenv.DEBUG0("date format: {}", fmt[0])
				try:
					self.logDate = datetime.strptime(logDate, fmt[0])
				except ValueError:
					pass
			if self.logDate:
				globDat = self.logDate.strftime(fmt[2])
				self.logGlob = "netLog." + globDat + "*.log"
			else:
				raise PluginException(
					"Wrong date '{}' format. Must be in the form of '{}'".format(
					logDate,
					"','".join([d[1] for d in self.DATE_FORMATS.values()]))
				)
			tdenv.NOTE("using date: {}", self.logDate.strftime(fmt[0]))
		tdenv.NOTE("using pattern: {}", self.logGlob)

		self.filePathList = []
		for filePath in sorted(self.logPath.glob(self.logGlob)):
			tdenv.DEBUG0("logfile: {}", str(filePath))
			self.filePathList.append(filePath)

		if logLast and len(self.filePathList) > 1:
			del self.filePathList[:-1]

		listLen = len(self.filePathList)
		if listLen == 0:
			raise PluginException("No logfile found.")
		elif listLen == 1:
			tdenv.NOTE("Found one logfile.")
		else:
			tdenv.NOTE("Found {} logfiles.", listLen)

	def run(self):
		tdb, tdenv = self.tdb, self.tdenv

		tdenv.DEBUG0("show: {}", self.getOption("show"))
		tdenv.DEBUG0("last: {}", self.getOption("last"))
		tdenv.DEBUG0("date: {}", self.getOption("date"))

		# Ensure the cache is built and reloaded.
		tdb.reloadCache()
		tdb.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)

		self.getLogDirList()
		self.parseLogDirList()

		# We did all the work
		return False
