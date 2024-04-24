import os
import json
import pathlib
from datetime import datetime, timezone

from .. import csvexport
from . import PluginException, ImportPluginBase


def snapToGrid32(val):
    try:
        val = float(val)
        corr = -0.5 if val < 0 else 0.5
        pos = int(val*32+corr)/32
    except:
        pos = None
        pass
    return pos

def getYNfromService(obj, key):
    return "Y" if key in obj else "N"

class JournalStation:
    __slots__ = (
        'lsFromStar', 'blackMarket', 'maxPadSize',
        'market', 'shipyard', 'outfitting',
        'rearm', 'refuel', 'repair',
        'planetary', 'modified'
    )
    
    def __init__(
        self, lsFromStar=0, blackMarket='?', maxPadSize='?',
        market='?', shipyard='?', outfitting='?',
        rearm='?', refuel='?', repair='?',
        planetary='?', modified='now'
    ):
        self.lsFromStar = lsFromStar
        self.blackMarket = blackMarket
        self.maxPadSize = maxPadSize
        self.market = market
        self.shipyard = shipyard
        self.outfitting = outfitting
        self.rearm = rearm
        self.refuel = refuel
        self.repair = repair
        self.planetary = planetary
        self.modified = modified
    
    def __str__(self):
        return "{}ls Pad:{} Mkt:{} Blk:{} Shp:{} Out:{} Arm:{} Ref:{} Rep:{} Plt:{}".format(
            self.lsFromStar, self.maxPadSize, self.market,
            self.blackMarket, self.shipyard, self.outfitting,
            self.rearm, self.refuel, self.repair, self.planetary
        )

class ImportPlugin(ImportPluginBase):
    """
    Plugin that parses the Journal file and add or update systems and stations.
    """
    
    logGlob = "Journal.*.log"
    ADDED_NAME = 'Journal'
    LOGDIR_NAME = "FDEVJRNDIR"
    DATE_FORMATS = {
         2: ("%y",       "YY",         "%y"),
         4: ("%Y",       "YYYY",       "%y"),
         5: ("%y-%m",    "YY-MM",      "%y%m"),
         7: ("%Y-%m",    "YYYY-MM",    "%y%m"),
         8: ("%y-%m-%d", "YY-MM-DD",   "%y%m%d"),
        10: ("%Y-%m-%d", "YYYY-MM-DD", "%y%m%d"),
    }
    ignoreSysNames = [
        'TRAINING',
        'DESTINATION',
    ]
    pluginOptions = {
        'show': "Only show the system or station. Don't update the DB.",
        'last': "Only parse the last (newest) Journal file.",
        'date': "Only parse Journal files from date, format=[YY]YY[-MM[-DD]].",
    }
    filePathList = []
    sysList = {}
    stnList = {}
    blkList = []
    
    planetTypeList = (
        "SURFACESTATION",
        "CRATERPORT",
        "CRATEROUTPOST",
    )
    
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
    
    def getJournalDirList(self):
        """
        get all Journal files
        """
        tdenv = self.tdenv
        optDate = self.getOption("date")
        logLast = self.getOption("last")
        
        logDate = None
        if isinstance(optDate, str):
            fmtLen = len(optDate)
            fmtDate = self.DATE_FORMATS.get(fmtLen, None)
            if fmtDate:
                tdenv.DEBUG0("date format: {}", fmtDate[0])
                try:
                    logDate = datetime.strptime(optDate, fmtDate[0])
                except ValueError:
                    logDate = None
                    pass
            if logDate:
                globDat = logDate.strftime(fmtDate[2])
                self.logGlob = "Journal." + globDat + "*.log"
                tdenv.NOTE("using date: {}", logDate.strftime(fmtDate[0]))
            else:
                raise PluginException(
                    "Wrong date '{}' format. Must be in the form of '{}'"
                    .format(
                        optDate,
                        "','".join([d[1] for d in self.DATE_FORMATS.values()])
                    )
                )
        tdenv.NOTE("using pattern: {}", self.logGlob)
        
        for filePath in sorted(self.logPath.glob(self.logGlob)):
            tdenv.DEBUG0("logfile: {}", str(filePath))
            self.filePathList.append(filePath)
        
        listLen = len(self.filePathList)
        if listLen == 0:
            raise PluginException("No journal file found.")
        elif listLen == 1:
            tdenv.NOTE("Found one journal file.")
        else:
            tdenv.NOTE("Found {} journal files.", listLen)
        
        if logLast and listLen > 1:
            del self.filePathList[:-1]
    
    def parseJournalDirList(self):
        """
        parse Journal files
        see: https://forums.frontier.co.uk/showthread.php/275151-Commanders-log-manual-and-data-sample
        """
        tdenv = self.tdenv
        
        logSysList = {}
        stnSysList = {}
        blkStnList = []
        for filePath in self.filePathList:
            tdenv.NOTE("parsing '{}'", filePath.name)
            aktStation = False
            inMultiCrew = False
            sysCount = stnCount = blkCount = 0
            with filePath.open() as logFile:
                lineCount = 0
                statHeader = True
                for line in logFile:
                    lineCount += 1
                    try:
                        # parse the json-event-line of the journal
                        event = json.loads(line)
                        if inMultiCrew:
                            # ignore all events in multicrew except
                            if event["event"] == "QuitACrew":
                                inMultiCrew = False
                            else:
                                tdenv.DEBUG1("event '{}' ignored (multicrew)", event["event"])
                            continue
                        logDate = datetime.strptime(
                            event["timestamp"], "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(tzinfo=timezone.utc)
                        if statHeader:
                            # check the first line
                            statHeader = False
                            if event["event"] == "Fileheader":
                                if "beta" in event["gameversion"].lower():
                                    # don't parse data from beta versions
                                    tdenv.NOTE("Ignoring Beta-Version.")
                                    break
                                # ignore the header-event
                                continue
                            else:
                                # don't stop parsing if it's not the header-line
                                tdenv.WARN("Doesn't seem do be a FDEV Journal file")
                        if event["event"] == "Location":
                            # convert event before the if-elif starts
                            if event.get("Docked", False):
                                event["event"] = "Docked"
                                tdenv.DEBUG0("   EVENT: Changed Location to Docked")
                        # if-elif starts here
                        if event["event"] == "FSDJump":
                            sysCount += 1
                            sysDate = logDate
                            sysName = event["StarSystem"]
                            sysPosA = event["StarPos"]
                            sysPosX, sysPosY, sysPosZ = sysPosA[0], sysPosA[1], sysPosA[2]
                            sysPosX = snapToGrid32(sysPosX)
                            sysPosY = snapToGrid32(sysPosY)
                            sysPosZ = snapToGrid32(sysPosZ)
                            tdenv.DEBUG0(
                                "  SYSTEM: {} {} {} {} {}",
                                sysDate, sysName, sysPosX, sysPosY, sysPosZ
                            )
                            logSysList[sysName] = (sysPosX, sysPosY, sysPosZ, sysDate)
                        elif event["event"] == "Docked":
                            stnCount += 1
                            sysName = event["StarSystem"]
                            stnList = stnSysList.get(sysName, None)
                            if not stnList:
                                stnList = stnSysList[sysName] = {}
                            stnDate = logDate
                            stnName = event["StationName"]
                            jrnStation = JournalStation(modified=stnDate)
                            jrnStation.lsFromStar = int(event.get("DistFromStarLS", 0) + 0.5)
                            stnType = event.get("StationType", None)
                            if stnType:
                                # conclusions from the stationtype
                                jrnStation.planetary = "Y" if stnType.upper() in self.planetTypeList else "N"
                                jrnStation.maxPadSize = "M" if stnType.startswith("Outpost") else "L"
                            stnServices = event.get("StationServices", None)
                            if stnServices:
                                # station services since ED update 2.4
                                jrnStation.blackMarket = getYNfromService(stnServices, 'BlackMarket')
                                jrnStation.market = getYNfromService(stnServices, 'Commodities')
                                jrnStation.shipyard = getYNfromService(stnServices, 'Shipyard')
                                jrnStation.outfitting = getYNfromService(stnServices, 'Outfitting')
                                jrnStation.rearm = getYNfromService(stnServices, 'Rearm')
                                jrnStation.refuel = getYNfromService(stnServices, 'Refuel')
                                jrnStation.repair = getYNfromService(stnServices, 'Repair')
                            tdenv.DEBUG0(
                                " STATION: {} {}/{} {}",
                                stnDate, sysName, stnName, str(jrnStation)
                            )
                            stnList[stnName] = jrnStation
                            aktStation = True
                            sysPosA = event.get("StarPos", None)
                            if sysPosA:
                                # we got system data inside a docking event
                                # use it (changed Location or maybe EDDN capture)
                                sysCount += 1
                                sysDate = logDate
                                sysPosX, sysPosY, sysPosZ = sysPosA[0], sysPosA[1], sysPosA[2]
                                sysPosX = snapToGrid32(sysPosX)
                                sysPosY = snapToGrid32(sysPosY)
                                sysPosZ = snapToGrid32(sysPosZ)
                                tdenv.DEBUG0("  SYSTEM: {} {} {} {} {}", sysDate, sysName, sysPosX, sysPosY, sysPosZ)
                                logSysList[sysName] = (sysPosX, sysPosY, sysPosZ, sysDate)
                        elif event["event"] == "MarketSell" and aktStation:
                            # check for BlackMarket
                            if event.get("BlackMarket", False):
                                stnBlackMarket = (sysName, stnName)
                                if stnBlackMarket not in blkStnList:
                                    tdenv.DEBUG0("B/MARKET: {}/{}", sysName, stnName)
                                    blkCount += 1
                                    blkStnList.append(stnBlackMarket)
                        elif event["event"] == "Undocked":
                            aktStation = False
                        elif event["event"] == "JoinACrew":
                            inMultiCrew = True
                        else:
                            tdenv.DEBUG1("event '{}' ignored", event["event"])
                    except:
                        tdenv.WARN("Something wrong with line {} (skipped it).", lineCount)
            
            tdenv.NOTE(
                "Found {} System{}, {} Station{} and {} BlackMarket{}.",
                sysCount, "" if sysCount == 1 else "s",
                stnCount, "" if stnCount == 1 else "s",
                blkCount, "" if blkCount == 1 else "s",
            )
        self.sysList = logSysList
        self.stnList = stnSysList
        self.blkList = blkStnList
    
    def updateJournalSysList(self):
        """
        check the found systems and add them to the DB if new.
        """
        tdb, tdenv = self.tdb, self.tdenv
        optShow = self.getOption("show")
        
        if not optShow:
            try:
                idJournal = tdb.lookupAdded(self.ADDED_NAME)
                tdenv.DEBUG1("idjournal = {}", idJournal)
            except KeyError:
                tdenv.WARN("Entry '{}' not found in 'Added' table.", self.ADDED_NAME)
                tdenv.WARN("Trying to add it myself.")
                db = tdb.getDB()
                cur = db.cursor()
                cur.execute(
                    "INSERT INTO Added(name) VALUES(?)",
                    [self.ADDED_NAME]
                )
                db.commit()
                tdenv.NOTE("Export Table 'Added'")
                _, path = csvexport.exportTableToFile(tdb, tdenv, "Added")
                pass
        
        addCount = oldCount = newCount = 0
        for sysName in sorted(self.sysList):
            sysPosX, sysPosY, sysPosZ, sysDate = self.sysList[sysName]
            utcDate = sysDate.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            tdenv.DEBUG0(
                "log system '{}' ({}, {}, {}, '{}')",
                sysName, sysPosX, sysPosY, sysPosZ, utcDate
            )
            if sysName.upper() in self.ignoreSysNames:
                tdenv.NOTE("Ignoring system: '{}'", sysName)
                continue
            systemTD = tdb.systemByName.get(sysName.upper(), None)
            if systemTD:
                # we allready know the system, check coords
                tdenv.DEBUG0(
                    "Old system '{}' ({}, {}, {})",
                    systemTD.dbname, systemTD.posX, systemTD.posY, systemTD.posZ
                )
                oldCount += 1
                if not (systemTD.posX == sysPosX and
                        systemTD.posY == sysPosY and
                        systemTD.posZ == sysPosZ):
                    tdenv.WARN("System '{}' has different coordinates:", sysName)
                    tdenv.WARN("   database: {}, {}, {}", systemTD.posX, systemTD.posY, systemTD.posZ)
                    tdenv.WARN("    Journal: {}, {}, {}", sysPosX, sysPosY, sysPosZ)
            else:
                # it's a new system
                newCount += 1
                if optShow:
                    # display only
                    tdenv.NOTE(
                        "New system '{}' ({}, {}, {}, '{}')",
                        sysName, sysPosX, sysPosY, sysPosZ, utcDate
                    )
                else:
                    # add it to the database
                    # the function will output something
                    tdb.addLocalSystem(
                        sysName.upper(),
                        sysPosX, sysPosY, sysPosZ,
                        added=self.ADDED_NAME,
                        modified=utcDate,
                        commit=False
                    )
                    addCount += 1
        
        # output statistics
        allCount = oldCount + newCount
        tdenv.NOTE(
            "Found {:>3} System{} altogether.",
            allCount, "" if allCount == 1 else "s",
        )
        for iCount, iText in [
            (oldCount, "old"), (newCount, "new"), (addCount, "added"),
        ]:
            tdenv.NOTE("      {:>3} {}", iCount, iText)
        if addCount:
            tdb.getDB().commit()
            tdenv.NOTE("Export Table 'System'")
            _, path = csvexport.exportTableToFile(tdb, tdenv, "System")
    
    def updateJournalStnList(self):
        """
        check the found stations and
        add them to the DB if new or
        update them in the DB if changed.
        """
        tdb, tdenv = self.tdb, self.tdenv
        optShow = self.getOption("show")
        
        addCount = oldCount = newCount = updCount = 0
        for sysName in sorted(self.stnList):
            if sysName.upper() in self.ignoreSysNames:
                tdenv.NOTE("Ignoring system: '{}'", sysName)
                continue
            system = tdb.systemByName.get(sysName.upper(), None)
            if not (system or optShow):
                # only warn if we are not in show mode
                # otherwise we could have addded the system before
                tdenv.WARN("System '{}' unknown.", sysName)
                continue
            for stnName in sorted(self.stnList[sysName]):
                jrnStation = self.stnList[sysName][stnName]
                utcDate = jrnStation.modified.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                station = None
                if system:
                    # system could be None in show mode and the lookup
                    # function would try very hard to find the station
                    try:
                        station = tdb.lookupStation(stnName, system)
                    except LookupError:
                        pass
                
                if (sysName, stnName) in self.blkList:
                    # BlackMarket found
                    jrnStation.blackMarket = "Y"
                elif station:
                    if jrnStation.blackMarket == "?":
                        # don't change current value if new one is unknown
                        jrnStation.blackMarket = station.blackMarket
                
                tdenv.DEBUG0(
                    "log station '{}/{}' ({}, '{}')",
                    sysName, stnName, str(jrnStation), utcDate
                )
                
                if not station:
                    # must be a new station
                    newCount += 1
                    if optShow:
                        # display only
                        tdenv.NOTE(
                            "New station '{}/{}' ({}, '{}')",
                            sysName, stnName, str(jrnStation), utcDate
                        )
                    else:
                        # add it to the database
                        # the function will output something
                        station = tdb.addLocalStation(
                            system=system,
                            name=stnName,
                            lsFromStar=jrnStation.lsFromStar,
                            blackMarket=jrnStation.blackMarket,
                            maxPadSize=jrnStation.maxPadSize,
                            market=jrnStation.market,
                            shipyard=jrnStation.shipyard,
                            outfitting=jrnStation.outfitting,
                            rearm=jrnStation.rearm,
                            refuel=jrnStation.refuel,
                            repair=jrnStation.repair,
                            planetary=jrnStation.planetary,
                            modified=utcDate,
                            commit=False,
                        )
                        addCount += 1
                else:
                    oldCount += 1
                    tdenv.DEBUG0(
                        "Old station '{}' ({}ls Pad:{} Mkt:{} Blk:{} Shp:{} Out:{} Arm:{} Ref:{} Rep:{} Plt:{})",
                        station.name(), station.lsFromStar, station.maxPadSize, station.market,
                        station.blackMarket, station.shipyard, station.outfitting,
                        station.rearm, station.refuel, station.repair, station.planetary
                    )
                    if not optShow:
                        if (station.lsFromStar != jrnStation.lsFromStar and
                            station.blackMarket == jrnStation.blackMarket and
                            station.maxPadSize == jrnStation.maxPadSize and
                            station.market == jrnStation.market and
                            station.shipyard == jrnStation.shipyard and
                            station.outfitting == jrnStation.outfitting and
                            station.rearm == jrnStation.rearm and
                            station.refuel == jrnStation.refuel and
                            station.repair == jrnStation.repair and
                            station.planetary == jrnStation.planetary
                        ):
                            # ignore 15% deviation if it's the only change
                            lsMin = int(station.lsFromStar * 0.85)
                            lsMax = int(station.lsFromStar*1.15 + 1)
                            if lsMin <= jrnStation.lsFromStar <= lsMax:
                                tdenv.DEBUG0(
                                    "ignore 15% deviation ({}ls ~ {}ls)",
                                    jrnStation.lsFromStar, station.lsFromStar
                                )
                                jrnStation.lsFromStar = station.lsFromStar
                        # the function will do it's own check and output
                        # something if the station is updated
                        if tdb.updateLocalStation(
                            station=station,
                            lsFromStar=jrnStation.lsFromStar,
                            blackMarket=jrnStation.blackMarket,
                            maxPadSize=jrnStation.maxPadSize,
                            market=jrnStation.market,
                            shipyard=jrnStation.shipyard,
                            outfitting=jrnStation.outfitting,
                            rearm=jrnStation.rearm,
                            refuel=jrnStation.refuel,
                            repair=jrnStation.repair,
                            planetary=jrnStation.planetary,
                            modified=utcDate,
                            commit=False,
                        ):
                            updCount += 1
        
        # output statistics
        allCount = oldCount + newCount
        tdenv.NOTE(
            "Found {:>3} Station{} altogether.",
            allCount, "" if allCount == 1 else "s",
        )
        for iCount, iText in [
            (oldCount, "old"), (updCount, "updated"),
            (newCount, "new"), (addCount, "added"),
        ]:
            tdenv.NOTE("      {:>3} {}", iCount, iText)
        if (updCount+addCount) > 0:
            tdb.getDB().commit()
            tdenv.NOTE("Export Table 'Station'")
            _, path = csvexport.exportTableToFile(tdb, tdenv, "Station")
    
    def run(self):
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.DEBUG0("show: {}", self.getOption("show"))
        tdenv.DEBUG0("last: {}", self.getOption("last"))
        tdenv.DEBUG0("date: {}", self.getOption("date"))
        
        # Ensure the cache is built and reloaded.
        tdb.reloadCache()
        tdb.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)
        
        self.getJournalDirList()
        self.parseJournalDirList()
        self.updateJournalSysList()
        self.updateJournalStnList()
        
        # We did all the work
        return False
