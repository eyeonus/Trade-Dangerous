# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Database Module
#
#  Containers for describing the current TradeDangerous database
#  and loading it from the SQLite database cache.

######################################################################
# Imports

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

import re                   # Because irregular expressions are dull
import sys
from collections import namedtuple, defaultdict
import itertools
import math
from pathlib import Path

from tradeexcept import TradeException
from tradeenv import TradeEnv
import cache

import locale
locale.setlocale(locale.LC_ALL, '')

######################################################################
# Classes

class AmbiguityError(TradeException):
    """
        Raised when a search key could match multiple entities.
        Attributes:
            lookupType - description of what was being queried,
            searchKey  - the key given to the search routine,
            anyMatch - list of anyMatch
            key        - retrieve the display string for a candidate
    """
    def __init__(self, lookupType, searchKey, anyMatch, key=lambda item:item):
        self.lookupType = lookupType
        self.searchKey = searchKey
        self.anyMatch = anyMatch
        self.key = key


    def __str__(self):
        anyMatch, key = self.anyMatch, self.key
        if len(anyMatch) > 10:
            opportunities = ", ".join([
                        key(c) for c in anyMatch[:10]
                    ] + ["..."])
        else:
            opportunities = ", ".join([
                        key(c) for c in anyMatch[0:-1]
                    ])
            opportunities += " or " + key(anyMatch[-1])
        return '{} lookup: "{}" could match {}'.format(
                        self.lookupType, str(self.searchKey),
                        opportunities
                    )


class SystemNotStationError(TradeException):
    """
        Raised when a station lookup matched a System but
        could not be automatically reduced to a Station.
    """
    pass


######################################################################


class System(object):
    """
        Describes a star system, which may contain one or more Station objects,
        and lists which stars it has a direct connection to.
        Do not use _rangeCache directly, use TradeDB.genSystemsInRange.
    """
    __slots__ = ('ID', 'dbname', 'posX', 'posY', 'posZ', 'links', 'stations', '_rangeCache')

    class RangeCache(object):
        """
            Lazily populated cache of neighboring systems.
        """
        def __init__(self):
            self.systems = dict()
            self.probedLy = 0.

    def __init__(self, ID, dbname, posX, posY, posZ):
        self.ID, self.dbname, self.posX, self.posY, self.posZ = ID, dbname, posX, posY, posZ
        self.links = {}
        self.stations = []
        self._rangeCache = None


    def distToSq(self, other):
        """
            Calculate the square of the distance (in ly)
            to a given other star.
        """
        dx2 = (self.posX - other.posX) ** 2
        dy2 = (self.posY - other.posY) ** 2
        dz2 = (self.posZ - other.posZ) ** 2
        return (dx2 + dy2 + dz2)


    def name(self):
        return self.dbname.upper()


    def str(self):
        return self.dbname


    def __repr__(self):
        return "System(ID={}, dbname='{}', posX={}, posY={}, posZ={})".format(self.ID, re.escape(self.dbname), self.posX, self.posY, self.posZ)


######################################################################


class Destination(namedtuple('Destination', [
                    'system', 'station', 'via', 'distLy' ])):
    pass

class DestinationNode(namedtuple('DestinationNode', [
                    'system', 'via', 'distLy' ])):
    pass


class Station(object):
    """
        Describes a station within a given system along with what trade
        opportunities it presents.
    """
    __slots__ = ('ID', 'system', 'dbname', 'lsFromStar', 'tradingWith', 'itemCount')

    def __init__(self, ID, system, dbname, lsFromStar, itemCount):
        self.ID, self.system, self.dbname, self.lsFromStar, self.itemCount = ID, system, dbname, lsFromStar, itemCount
        self.tradingWith = None       # dict[tradingPartnerStation] -> [ available trades ]
        system.stations.append(self)


    def name(self):
        return '%s/%s' % (self.system.name(), self.dbname)


    def str(self):
        return self.dbname


    def __repr__(self):
        return "Station(ID={}, system='{}', dbname='{}', lsFromStar={})".format(self.ID, re.escape(self.system.dbname), re.escape(self.dbname), self.lsFromStar)


######################################################################


class Ship(namedtuple('Ship', [ 'ID', 'dbname', 'capacity', 'mass', 'driveRating', 'maxLyEmpty', 'maxLyFull', 'maxSpeed', 'boostSpeed', 'stations' ])):
    def name(self):
        return self.dbname


######################################################################


class Category(namedtuple('Category', [ 'ID', 'dbname', 'items' ])):
    """
        Items are organized into categories (Food, Drugs, Metals, etc).
        Category object describes a category's ID, name and list of items.
    """
    def name(self):
        return self.dbname.upper()


    def __str__(self):
        return self.dbname


######################################################################


class Item(object):
    """
        Describes a product that can be bought/sold in the game.

        Attributes:
            ID       -- Database ID.
            dbname   -- Name as it appears in-game and in the DB.
            category -- Reference to the category.
            fullname -- Combined category/dbname for lookups.
            altname  -- The internal name used by the game.
    """
    __slots__ = ('ID', 'dbname', 'category', 'fullname', 'altname')

    def __init__(self, ID, dbname, category, fullname, altname=None):
        self.ID, self.dbname, self.category, self.fullname, self.altname = ID, dbname, category, fullname, altname


    def name(self):
        return self.dbname


    def __str__(self):
        return '{}/{}'.format(self.category.name, self.dbname)


    def __repr__(self):
        return "Item(ID={}, dbname='{}', category={}, fullname='{}', altName={})".format(
                self.ID, re.escape(self.dbname), repr(self.category), re.escape(self.fullname),
                "'{}'".format(re.escape(self.altname) if self.altname else 'None')
            )


######################################################################


class Trade(namedtuple('Trade', [
            'item', 'itemID', 'costCr', 'gainCr', 'stock', 'stockLevel', 'demand', 'demandLevel', 'srcAge', 'dstAge'
        ])):
    """
        Describes what it would cost and how much you would gain
        when selling an item between two specific stations.
    """
    def name(self):
        return self.item.name()


    def str(self):
        return self.item.name()


    def __repr__(self):
        return "Trade(item={}, itemID={}, costCr={}, gainCr={})".format(self.item.name(), self.itemID, self.costCr, self.gainCr)


######################################################################


class TradeDB(object):
    """
        Encapsulation for the database layer.

        Attributes:
            dbPath              -   Path object describing the db location.
            dbFilename          -   str(dbPath)
            conn                -   The database connection.

        Methods:
            load                -   Reloads entire database. CAUTION: Destructive - Orphans existing records you reference.
            loadTrades          -   Reloads just the price data. CAUTION: Destructive - Orphans existing records.
            lookupSystem        -   Return a system matching "name" with ambiguity detection.
            lookupStation       -   Return a station matching "name" with ambiguity detection.
            lookupShip          -   Return a ship matching "name" with ambiguity detection.
            getTrades           -   Returns the list of Trade objects between two stations.

            query               -   Executes the specified SQL on the db and returns a cursor.
            fetch_all           -   Generator that yields all the rows retrieved by an sql cursor.

        Static methods:
            listSearch          -   Performs a partial-match search of a list for a value.
            normalizedStr       -   Normalizes a search index string.
    """

    # Translation map for normalizing strings
    normalizeTrans = str.maketrans(
            'abcdefghijklmnopqrstuvwxyz',
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
            '[]()*+-.,{}:'
            )
    # The DB cache
    defaultDB = 'TradeDangerous.db'
    # File containing SQL to build the DB cache from
    defaultSQL = 'TradeDangerous.sql'
    # File containing text description of prices
    defaultPrices = 'TradeDangerous.prices'
    # array containing standard tables, csvfilename and tablename
    # WARNING: order is important because of dependencies!
    defaultTables = [
                      [ 'Added.csv', 'Added' ],
                      [ 'System.csv', 'System' ],
                      [ 'Station.csv', 'Station' ],
                      [ 'Ship.csv', 'Ship' ],
                      [ 'ShipVendor.csv', 'ShipVendor' ],
                      [ 'Upgrade.csv', 'Upgrade' ],
                      [ 'UpgradeVendor.csv', 'UpgradeVendor' ],
                      [ 'Category.csv', 'Category' ],
                      [ 'Item.csv', 'Item' ],
                      [ 'AltItemNames.csv', 'AltItemNames' ]
                    ]


    def __init__(self,
                    tdenv=None,
                    load=True,
                    buildLinks=False,
                    includeTrades=False,
                    debug=None,
                ):
        self.conn = None
        self.cur = None
        self.numLinks = None
        self.tradingCount = None

        tdenv = tdenv or TradeEnv(debug=(debug or 0))
        self.tdenv = tdenv

        dataDir = Path(tdenv.dataDir).resolve()
        self.dbPath = Path(tdenv.dbFilename or dataDir / TradeDB.defaultDB)
        self.sqlPath = dataDir / Path(tdenv.sqlFilename or TradeDB.defaultSQL)
        self.pricesPath = dataDir / Path(tdenv.pricesFilename or TradeDB.defaultPrices)
        self.importTables = [(str(dataDir / Path(x[0])), x[1]) for x in TradeDB.defaultTables]

        self.dbFilename = str(self.dbPath)
        self.sqlFilename = str(self.sqlPath)
        self.pricesFilename = str(self.pricesPath)

        if load:
            self.reloadCache()
            self.load(maxSystemLinkLy=tdenv.maxSystemLinkLy,
                    buildLinks=buildLinks,
                    includeTrades=includeTrades,
                    )


    ############################################################
    # Access to the underlying database.

    def getDB(self):
        if self.conn: return self.conn
        try:
            self.tdenv.DEBUG1("Connecting to DB")
            import sqlite3
            conn = sqlite3.connect(self.dbFilename)
            conn.execute("PRAGMA foreign_keys=ON")
            return conn
        except ImportError as e:
            print("ERROR: You don't appear to have the Python sqlite3 module installed. Impressive. No, wait, the other one: crazy.")
            raise e


    def query(self, *args):
        """ Perform an SQL query on the DB and return the cursor. """
        conn = self.getDB()
        cur = conn.cursor()
        cur.execute(*args)
        return cur


    # following the convention of how fetch_all is written in python modules.
    def fetch_all(self, *args):
        """ Perform an SQL query on the DB and iterate across the rows. """
        for row in self.query(*args):
            yield row


    def reloadCache(self):
        """
            Checks if the .sql, .prices or *.csv files are newer than the cache.
        """

        if self.dbPath.exists():
            dbFileStamp = self.dbPath.stat().st_mtime

            paths = [ self.sqlPath ]
            paths += [ Path(f) for (f, _) in self.importTables ]

            changedPaths = [
                    [path, path.stat().st_mtime]
                        for path in paths
                        if path.exists() and
                            path.stat().st_mtime > dbFileStamp
                    ]

            if not changedPaths:
                # Do we need to reload the .prices file?
                if not self.pricesPath.exists():
                    self.tdenv.DEBUG1("No .prices file to load")
                    return

                pricesStamp = self.pricesPath.stat().st_mtime
                if pricesStamp <= dbFileStamp:
                    self.tdenv.DEBUG1("DB Cache is up to date.")
                    return

                self.tdenv.DEBUG0(".prices has changed: re-importing")
                cache.importDataFromFile(self, self.tdenv, self.pricesPath, reset=True)
                return

            self.tdenv.DEBUG0("Rebuilding DB Cache [{}]", str(changedPaths))
        else:
            self.tdenv.DEBUG0("Building DB Cache")

        cache.buildCache(self, self.tdenv)


    ############################################################
    # Star system data.


    def systems(self):
        """ Iterate through the list of systems. """
        yield from self.systemByID.values()


    def _loadSystems(self):
        """
            Initial load the (raw) list of systems.
            If you have previously loaded Systems, this will orphan the old System objects.
        """
        stmt = """
                SELECT system_id, name, pos_x, pos_y, pos_z
                  FROM System
            """
        self.cur.execute(stmt)
        systemByID, systemByName = {}, {}
        for (ID, name, posX, posY, posZ) in self.cur:
            sys = systemByID[ID] = systemByName[name] = System(ID, name, posX, posY, posZ)

        self.systemByID, self.systemByName = systemByID, systemByName
        self.tdenv.DEBUG1("Loaded {:n} Systems", len(systemByID))


    def buildLinks(self):
        """
            Populate the list of reachable systems for every star system.

            Not every system can reach every other, and we use the longest jump
            that can be made by a ship to limit how many connections we consider
            to be "links".
        """

        assert not self.numLinks

        self.tdenv.DEBUG1("Building trade links")

        stmt = """
                    SELECT DISTINCT lhs_system_id, rhs_system_id, dist
                      FROM StationLink
                     WHERE dist <= {} AND lhs_system_id != rhs_system_id
                     ORDER BY lhs_system_id
                 """.format(self.maxSystemLinkLy)
        self.cur.execute(stmt)
        systemByID = self.systemByID
        lastLhsID, lhsLinks = None, None
        self.numLinks = 0
        for lhsID, rhsID, dist in self.cur:
            if lhsID != lastLhsID:
                lhsLinks = systemByID[lhsID].links
                lastLhsID = lhsID
            lhsLinks[systemByID[rhsID]] = dist
            self.numLinks += 1

        self.numLinks /= 2

        self.tdenv.DEBUG1("Number of links between systems: {:n}", self.numLinks)

        if self.tdenv.debug:
            self._validate()


    def lookupSystem(self, key):
        """
            Look up a System object by it's name.
        """
        if isinstance(key, System):
            return key
        if isinstance(key, Station):
            return key.system

        return TradeDB.listSearch("System", key, self.systems(), key=lambda system: system.dbname)


    def lookupSystemRelaxed(self, key):
        """
            Lookup a System object by it's name or by the name of any of it's stations.
        """
        try:
            place = self.lookupPlace(key)
            if isinstance(place, Station):
                return place.system
            else:
                return place
        except AmbiguityError as e:
            # See if the ambiguity resolves down to a single system.
            systems = set()
            for candidate in e.anyMatch:
                if isinstance(candidate, Station):
                    systems.add(candidate.system)
                else:
                    systems.add(candidate)
            if len(systems) == 1:
                return systems[0]
            # Nope, genuine ambiguity
            raise


    def genSystemsInRange(self, system, ly, includeSelf=False):
        """
            Generator for systems within ly range of system using a
            lazily-populated, per-system cache.
        """

        if isinstance(system, Station):
            system = system.system
        elif not isinstance(system, System):
            place = self.lookupPlace(system)
            system = place.system if isinstance(system, Station) else place

        # Yield what we already have
        if includeSelf:
            yield system, 0.

        cache = system._rangeCache
        if not cache:
            cache = system._rangeCache = System.RangeCache()
        cachedSystems = cache.systems
        probedLy = cache.probedLy
        if probedLy > ly:
            # Cache may contain values outside our view
            for sys, dist in cachedSystems.items():
                if dist <= ly:
                    yield sys, dist
        else:
            # No need to be conditional inside the loop
            yield from cachedSystems.items()

        if probedLy >= ly:
            # If the cache already covered us, we can leave
            return

        # Consult the database for stars we haven't seen.
        sysX, sysY, sysZ = system.posX, system.posY, system.posZ
        self.cur.execute("""
                SELECT  sys.system_id
                  FROM  System AS sys
                 WHERE  sys.pos_x BETWEEN ? AND ?
                   AND  sys.pos_y BETWEEN ? AND ?
                   AND  sys.pos_z BETWEEN ? AND ?
                   AND  sys.system_id != ?
        """, [
                sysX - ly, sysX + ly,
                sysY - ly, sysY + ly,
                sysZ - ly, sysZ + ly,
                system.ID,
        ])
        knownIDs = frozenset(
            system.ID for system in cachedSystems.keys()
        )
        lySq = ly * ly
        for candID, in self.cur:
            if candID in knownIDs:
                continue
            candidate = self.systemByID[candID]
            distSq = (
                    (candidate.posX - sysX) ** 2 +
                    (candidate.posY - sysY) ** 2 +
                    (candidate.posZ - sysZ) ** 2
            )
            if distSq <= lySq:
                cachedSystems[candidate] = dist = math.sqrt(distSq)
                yield candidate, dist

        cache.probedLy = ly


    ############################################################
    # Station data.

    def stations(self):
        """ Iterate through the list of stations. """
        yield from self.stationByID.values()


    def _loadStations(self):
        """
            Populate the Station list.
            Station constructor automatically adds itself to the System object.
            If you have previously loaded Stations, this will orphan the old objects.
        """
        stmt = """
                SELECT  station_id, system_id, name, ls_from_star,
                        (SELECT COUNT(*)
                            FROM StationItem
                            WHERE station_id = Station.station_id) AS itemCount
                  FROM  Station
            """
        self.cur.execute(stmt)
        stationByID = {}
        systemByID = self.systemByID
        for (ID, systemID, name, lsFromStar, itemCount) in self.cur:
            station = Station(ID, systemByID[systemID], name, lsFromStar, itemCount)
            stationByID[ID] = station

        self.stationByID = stationByID
        self.tdenv.DEBUG1("Loaded {:n} Stations", len(stationByID))


    def lookupPlace(self, name):
        """
            Lookup the station/system specified by 'name' which can be the
            name of a System or Station or it can be "System/Station" when
            the user needs to disambiguate a station. In this case, both
            system and station can be partial matches.

            The system tries to allow partial matches as well as matches
            which omit whitespaces. In order to do this and still support
            the massive namespace of Stars and Systems, we rank the
            matches so that exact matches win, and only inferior close
            matches are looked at if no exacts are found.

            Legal annotations:
                system
                station
                @system    [explicitly a system name]
                /station   [explicitly a station name]
                system/station
                @system/station
        """
        if isinstance(name, System) or isinstance(name, Station):
            return name

        slashPos = name.find('/')
        nameOff = 1 if name.startswith('@') else 0
        if slashPos > nameOff:
            # Slash indicates it's, e.g., AULIN/ENTERPRISE
            sysName, stnName = name[nameOff:slashPos], name[slashPos+1:]
        elif slashPos == nameOff:
            sysName, stnName = None, name[nameOff+1:]
        elif nameOff:
            # It's explicitly a station
            sysName, stnName = name[nameOff:], None
        else:
            # It could be either, use the name for both.
            sysName = stnName = name[nameOff:]

        exactMatch = []
        closeMatch = []
        wordMatch = []
        anyMatch = []

        def lookup(name, candidates):
            """ Search candidates for the given name """

            normTrans = TradeDB.normalizeTrans
            trimTrans = str.maketrans('', '', ' \'')

            nameNorm = name.translate(normTrans)
            nameTrimmed = nameNorm.translate(trimTrans)

            nameLen = len(name)
            nameNormLen = len(nameNorm)
            nameTrimmedLen = len(nameTrimmed)

            for place in candidates:
                placeName = place.dbname
                placeNameNorm = placeName.translate(normTrans)
                placeNameNormLen = len(placeNameNorm)

                if nameTrimmedLen > placeNameNormLen:
                    # The needle is bigger than this haystack.
                    continue

                # If the lengths match, do a direct comparison.
                if len(placeName) == nameLen:
                    if placeNameNorm == nameNorm:
                        exactMatch.append(place)
                    continue
                if placeNameNormLen == nameNormLen:
                    if placeNameNorm == nameNorm:
                        closeMatch.append(place)
                    continue

                if nameNormLen < placeNameNormLen:
                    subPos = placeNameNorm.find(nameNorm)
                    if subPos == 0:
                        if placeNameNorm[nameNormLen] == ' ':
                            # first word
                            wordMatch.append(place)
                        else:
                            anyMatch.append(place)
                        continue
                    elif subPos > 0:
                        if placeNameNorm[subPos] == ' ' and \
                                placeNameNorm[subPos + nameNormLen] == ' ':
                            wordMatch.append(place)
                        else:
                            anyMatch.append(place)
                        continue

                # Lets drop whitespace and remaining punctuation...
                placeNameTrimmed = placeNameNorm.translate(trimTrans)
                placeNameTrimmedLen = len(placeNameTrimmed)
                if placeNameTrimmedLen == placeNameNormLen:
                    # No change
                    continue

                # A match here is not exact but still fairly interesting
                if len(placeNameTrimmed) == nameTrimmedLen:
                    if placeNameTrimmed == nameTrimmed:
                        closeMatch.append(place)
                    continue
                if placeNameTrimmed.find(nameTrimmed) >= 0:
                    anyMatch.append(place)

        if sysName:
            lookup(sysName, self.systemByID.values())
        if stnName:
            # Are we considering the name as a station?
            # (we don't if they type, e,g '@aulin')
            # compare against nameOff to allow '@/station'
            if slashPos > nameOff + 1:
                # "sys/station"; the user should have specified a system
                # name and we should be able to narrow down which
                # stations we compare against. Check first if there are
                # any matches.
                stationCandidates = []
                for sys in itertools.chain(
                        exactMatch, closeMatch, wordMatch, anyMatch
                        ):
                    stationCandidates += sys.stations
                # Clear out the candidate lists
                exactMatch = []
                closeMatch = []
                wordMatch = []
                anyMatch = []
            else:
                # Consider against all station names
                stationCandidates = self.stationByID.values()
            lookup(stnName, stationCandidates)

        # consult the match sets in ranking order for a single
        # match, which denotes a win at that tier. For example,
        # if there is one exact match, we don't care how many
        # close matches there were.
        for matchSet in exactMatch, closeMatch, wordMatch, anyMatch:
            if len(matchSet) == 1:
                return matchSet[0]

        # Nothing matched
        if not any([exactMatch, closeMatch, wordMatch, anyMatch]):
            raise TradeException("Unrecognized place: {}".format(name))

        # More than one match
        raise AmbiguityError(
                    'System/Station', name,
                    exactMatch + closeMatch + wordMatch + anyMatch,
                    key=lambda place: place.name())


    def lookupStation(self, name, system=None):
        """
            Look up a Station object by it's name or system.
        """
        if isinstance(name, Station):
            return name
        if isinstance(name, System):
            # If they provide a system and it only has one station, return that.
            if len(name.stations) != 1:
                raise SystemNotStationError("System '%s' has %d stations, please specify a station instead." % (name.str(), len(name.stations)))
            return name.stations[0]

        if system:
            system = self.lookupSystem(system)
            return TradeDB.listSearch("Station", name, system.stations, key=lambda system: system.dbname)

        stationID, station, systemID, system = None, None, None, None
        try:
            system = TradeDB.listSearch("System", name, self.systemByID.values(), key=lambda system: system.dbname)
        except LookupError:
            pass
        try:
            station = TradeDB.listSearch("Station", name, self.stationByID.values(), key=lambda station: station.dbname)
        except LookupError:
            pass
        # If neither matched, we have a lookup error.
        if not (station or system):
            raise LookupError("'%s' did not match any station or system." % (name))

        # If we matched both a station and a system, make sure they resovle to the
        # the same station otherwise we have an ambiguity. Some stations have the
        # same name as their star system (Aulin/Aulin Enterprise)
        if system and station and system != station.system:
            raise AmbiguityError('Station', name, [ system.name(), station.name() ])

        if station:
            return station

        # If we only matched a system name, ensure that it's a single station system
        # otherwise they need to specify a station name.
        if len(system.stations) != 1:
            raise SystemNotStationError("System '%s' has %d stations, please specify a station instead." % (system.name(), len(system.stations)))
        return system.stations[0]


    def getDestinations(self,
            origin,
            maxJumps=None,
            maxLyPer=None,
            avoidPlaces=None,
            trading=False):
        """
            Gets a list of the Station destinations that can be reached
            from this Station within the specified constraints.
            Limits to stations we are trading with if trading is True.
        """

        assert isinstance(origin, Station)

        if trading:
            if not origin.tradingWith:
                return []
            tradingWith = origin.tradingWith

        if maxJumps is None:
            maxJumps = sys.maxsize
        maxLyPer = maxLyPer or self.maxSystemLinkLy
        if avoidPlaces is None:
            avoidPlaces = []

        # The open list is the list of nodes we should consider next for
        # potential destinations.
        # The path list is a list of the destinations we've found and the
        # shortest path to them. It doubles as the "closed list".
        # The closed list is the list of nodes we've already been to (so
        # that we don't create loops A->B->C->A->B->C->...)

        origSys = origin.system
        openList = [ DestinationNode(origSys, [origSys], 0) ]
        # I don't want to have to consult both the pathList
        # AND the avoid list every time I'm considering a
        # station, so copy the avoid list into the pathList
        # with a negative distance so I can ignore them again
        # when I scrape the pathList.
        # Don't copy stations because those only affect our
        # termination points, and not the systems we can
        # pass through en-route.
        pathList = { system.ID: DestinationNode(system, None, -1.0)
                        for system in avoidPlaces
                        if isinstance(system, System) }

        # As long as the open list is not empty, keep iterating.
        jumps = 0
        while openList and jumps < maxJumps:
            # Expand the search domain by one jump; grab the list of
            # nodes that are this many hops out and then clear the list.
            ring, openList = openList, []
            # All of the destinations we are about to consider will
            # either be on the closed list or they will be +1 jump away.
            jumps += 1

            for node in ring:
                gsir = self.genSystemsInRange(node.system, maxLyPer, False)
                for (destSys, destDist) in gsir:
                    dist = node.distLy + destDist
                    # If we already have a shorter path, do nothing
                    try:
                        prevDist = pathList[destSys.ID].distLy
                    except KeyError:
                        pass
                    else:
                        if dist >= prevDist:
                            continue
                    # Add to the path list
                    destNode = DestinationNode(destSys, node.via + [destSys], dist)
                    pathList[destSys.ID] = destNode
                    # Add to the open list but also include node to the via
                    # list so that it serves as the via list for all next-hops.
                    openList.append(destNode)

        destStations = []
        # always include the local stations, unless the user has indicated they are
        # avoiding this system. E.g. if you're in Chango but you've specified you
        # want to avoid Chango...
        if origSys not in avoidPlaces:
            for station in origSys.stations:
                if (trading and station not in tradingWith):
                    continue
                if station not in avoidPlaces:
                    destStations.append(Destination(origSys, station, [], 0.0))

        # We have a system-to-system path list, now we
        # need stations to terminate at.
        for node in pathList.values():
            # negative values are avoidances
            if node.distLy < 0.0:
                continue
            for station in node.system.stations:
                if (trading and station not in tradingWith):
                    continue
                if station in avoidPlaces:
                    continue
                destStations.append(
                            Destination(node.system,
                                    station,
                                    node.via,
                                    node.distLy)
                        )

        return destStations


    ############################################################
    # Ship data.

    def ships(self):
        """ Iterate through the list of ships. """
        yield from self.shipByID.values()


    def _loadShips(self):
        """
            Populate the Ship list.
            If you have previously loaded Ships, this will orphan the old objects.
        """
        stmt = """
                SELECT ship_id, name, capacity, mass, drive_rating, max_ly_empty, max_ly_full, max_speed, boost_speed
                  FROM Ship
            """
        self.cur.execute(stmt)
        self.shipByID = { row[0]: Ship(*row, stations=[]) for row in self.cur }

        self.tdenv.DEBUG1("Loaded {} Ships", len(self.shipByID))


    def lookupShip(self, name):
        """
            Look up a ship by name
        """
        return TradeDB.listSearch("Ship", name, self.shipByID.values(), key=lambda ship: ship.dbname)


    ############################################################
    # Item data.

    def categories(self):
        """
            Iterate through the list of categories. key = category name, value = list of items.
        """
        yield from self.categoryByID.items()


    def _loadCategories(self):
        """
            Populate the list of item categories.
            If you have previously loaded Categories, this will orphan the old objects.
        """
        stmt = """
                SELECT category_id, name
                  FROM Category
            """
        self.categoryByID = { ID: Category(ID, name, []) for (ID, name) in self.cur.execute(stmt) }

        self.tdenv.DEBUG1("Loaded {} Categories", len(self.categoryByID))


    def lookupCategory(self, name):
        """
            Look up a category by name
        """
        return TradeDB.listSearch("Category", name, self.categoryByID.values(), key=lambda cat: cat.dbname)


    def items(self):
        """ Iterate through the list of items. """
        yield from self.itemByID.values()


    # TODO: Provide CATEGORIES so that you can do an item lookup.
    def _loadItems(self):
        """
            Populate the Item list.
            If you have previously loaded Items, this will orphan the old objects.
        """
        stmt = """
                SELECT item_id, name, category_id
                  FROM Item
            """
        itemByID, itemByName = {}, {}
        for (ID, name, categoryID) in self.cur.execute(stmt):
            category = self.categoryByID[categoryID]
            item = Item(ID, name, category, '{}/{}'.format(category.dbname, name), None)
            itemByID[ID] = item
            itemByName[name] = item
            category.items.append(item)

        # Some items have different actual names than display names.
        # Load the aliases.
        stmt = """
                SELECT alt_name, item_id
                  FROM AltItemNames
            """
        aliases = 0
        for (altName, itemID) in self.cur.execute(stmt):
            assert altName not in itemByName
            aliases += 1
            item = itemByID[itemID]
            item.altname = altName
            itemByName[altName] = item
            self.tdenv.DEBUG1("'{}' alias for #{} '{}'", altName, itemID, item.fullname)

        self.itemByID = itemByID
        self.itemByName = itemByName

        self.tdenv.DEBUG1("Loaded {:n} Items, {:n} AltItemNames",
                                len(self.itemByID), aliases)


    def lookupItem(self, name):
        """
            Look up an Item by name using "CATEGORY/Item"
        """
        return TradeDB.listSearch("Item", name, self.itemByName.items(), key=lambda kvTup: kvTup[0], val=lambda kvTup: kvTup[1])


    ############################################################
    # Price data.

    def loadTrades(self):
        """
            Populate the "Trades" table for stations.

            A trade is a connection between two stations where the SRC station

            NOTE: Trades MUST be loaded such that they are populated into the
            lists in descending order of profit (highest profit first)
        """

        if self.numLinks is None:
            self.buildLinks()

        self.tdenv.DEBUG1("Loading universal trade data")

        # NOTE: Overconsumption.
        # We currently fetch ALL possible trades with no regard for reachability;
        # as the database grows this will become problematic and we should switch
        # to some form of lazy load - that is, given a star, load all potential
        # trades it has within a given ly range (based on a multiple of max-ly and
        # max jumps).
        stmt = """
                SELECT  *
                  FROM  vProfits
                 ORDER  BY src_station_id, dst_station_id, gain DESC
                """
        self.cur.execute(stmt)
        stations, items = self.stationByID, self.itemByID
        self.tradingCount = 0

        prevSrcStnID, prevDstStnID = None, None
        srcStn, dstStn = None, None
        tradingWith = None

        for (itemID, srcStnID, dstStnID, srcPriceCr, profit, stock, stockLevel, demand, demandLevel, srcAge, dstAge) in self.cur:
            if srcStnID != prevSrcStnID:
                srcStn, prevSrcStnID, prevDstStnID = stations[srcStnID], srcStnID, None
                assert srcStn.tradingWith is None
                srcStn.tradingWith = {}
            if dstStnID != prevDstStnID:
                dstStn, prevDstStnID = stations[dstStnID], dstStnID
                tradingWith = srcStn.tradingWith[dstStn] = []
                self.tradingCount += 1
            tradingWith.append(Trade(items[itemID], itemID, srcPriceCr, profit, stock, stockLevel, demand, demandLevel, srcAge, dstAge))


    def loadStationTrades(self, fromStationIDs):
        """
            Loads all profitable trades that could be made
            from the specified list of stations. Does not
            take reachability into account.
        """

        if not fromStationIDs:
            return

        assert isinstance(fromStationIDs, list)
        assert isinstance(fromStationIDs[0], int)

        self.tdenv.DEBUG1("Loading trades for {}".format(str(fromStationIDs)))

        stmt = """
                SELECT  *
                  FROM  vProfits
                 WHERE  src_station_id IN ({})
                 ORDER  BY src_station_id, dst_station_id, gain DESC
                """.format(','.join(str(ID) for ID in fromStationIDs))
        self.cur.execute(stmt)
        stations, items = self.stationByID, self.itemByID

        prevSrcStnID, prevDstStnID = None, None
        srcStn, dstStn = None, None
        tradingWith = None
        if self.tradingCount is None:
            self.tradingCount = 0

        for (itemID, srcStnID, dstStnID, srcPriceCr, profit, stock, stockLevel, demand, demandLevel, srcAge, dstAge) in self.cur:
            if srcStnID != prevSrcStnID:
                srcStn, prevSrcStnID, prevDstStnID = stations[srcStnID], srcStnID, None
                assert srcStn.tradingWith is None
                srcStn.tradingWith = {}
            if dstStnID != prevDstStnID:
                dstStn, prevDstStnID = stations[dstStnID], dstStnID
                tradingWith = srcStn.tradingWith[dstStn] = []
                self.tradingCount += 1
            tradingWith.append(Trade(items[itemID], itemID, srcPriceCr, profit, stock, stockLevel, demand, demandLevel, srcAge, dstAge))


    def getTrades(self, src, dst):
        """ Returns a list of the Trade objects between src and dst. """

        # I could write this more compactly, but it makes errors less readable.
        srcStn = self.lookupStation(src)
        dstStn = self.lookupStation(dst)
        return srcStn.tradingWith[dstStn]


    def load(self, maxSystemLinkLy=None, buildLinks=True, includeTrades=True):
        """
            Populate/re-populate this instance of TradeDB with data.
            WARNING: This will orphan existing records you have
            taken references to:
                tdb.load()
                x = tdb.lookupStation("Aulin")
                tdb.load() # x now points to an orphan Aulin
        """

        self.tdenv.DEBUG1("Loading data")

        self.conn = conn = self.getDB()
        self.cur = conn.cursor()

        # Load raw tables. Stations will be linked to systems, but nothing else.
        # TODO: Make station -> system link a post-load action.
        self._loadSystems()
        self._loadStations()
        self._loadShips()
        self._loadCategories()
        self._loadItems()

        systems, stations, ships, items = self.systemByID, self.stationByID, self.shipByID, self.itemByID

        # Calculate the maximum distance anyone can jump so we can constrain
        # the maximum "link" between any two stars.
        if not maxSystemLinkLy:
            longestJumper = max(ships.values(), key=lambda ship: ship.maxLyEmpty)
            self.maxSystemLinkLy = longestJumper.maxLyEmpty
        else:
            self.maxSystemLinkLy = maxSystemLinkLy
        self.tdenv.DEBUG2("Max ship jump distance: {} @ {:.02f}",
                                longestJumper.name(), self.maxSystemLinkLy)

        if buildLinks:
            self.buildLinks()

        if includeTrades:
            self.loadTrades()


    def _validate(self):
        # Check that things correctly reference themselves.
        # Check that system links are bi-directional
        for (name, sys) in self.systemByName.items():
            if not sys.links:
                self.tdenv.DEBUG2("NOTE: System '%s' has no links" % name)
            if sys in sys.links:
                raise ValueError("System %s has a link to itself!" % name)
            if name in sys.links:
                raise ValueError("System %s's name occurs in sys.links" % name)
            for link in sys.links:
                if sys not in link.links:
                    raise ValueError("System %s does not have a reciprocal link in %s's links" % (name, link.str()))


    ############################################################
    # General purpose static methods.

    @staticmethod
    def listSearch(listType, lookup, values, key=lambda item: item, val=lambda item: item):
        """
            Searches [values] for 'lookup' for least-ambiguous matches,
            return the matching value as stored in [values].
            If [values] contains "bread", "water", "biscuits and "It",
            searching "ea" will return "bread", "WaT" will return "water"
            and "i" will return "biscuits". Searching for "a" will raise
            an AmbiguityError because "a" matches "bread" and "water", but
            searching for "it" will return "It" because it provides an
            exact match of a key.
        """

        class ListSearchMatch(namedtuple('Match', [ 'key', 'value' ])):
            pass

        normTrans = TradeDB.normalizeTrans
        needle = lookup.translate(normTrans)
        partialMatch, wordMatch = [], []
        # make a regex to match whole words
        wordRe = re.compile(r'\b{}\b'.format(lookup), re.IGNORECASE)
        # describe a match
        for entry in values:
            entryKey = key(entry)
            normVal = entryKey.translate(normTrans)
            if normVal.find(needle) > -1:
                # If this is an exact match, ignore ambiguities.
                if len(normVal) == len(needle):
                    return val(entry)
                match = ListSearchMatch(entryKey, val(entry))
                if wordRe.match(entryKey):
                    wordMatch.append(match)
                else:
                    partialMatch.append(match)
        # Whole word matches trump partial matches
        if wordMatch:
            if len(wordMatch) > 1:
                raise AmbiguityError(listType, lookup, wordMatch, key=lambda item: item.key)
            return wordMatch[0].value
        # Fuzzy matches
        if partialMatch:
            if len(partialMatch) > 1:
                raise AmbiguityError(listType, lookup, partialMatch, key=lambda item: item.key)
            return partialMatch[0].value
        # No matches
        raise LookupError("Error: '%s' doesn't match any %s" % (lookup, listType))


    @staticmethod
    def normalizedStr(text):
        """
            Returns a case folded, sanitized version of 'str' suitable for
            performing simple and partial matches against. Removes various
            punctuation characters that don't contribute to name uniqueness.
            NOTE: No-longer removes whitespaces or apostrophes.
        """
        return text.translate(TradeDB.normalizeTrans)

