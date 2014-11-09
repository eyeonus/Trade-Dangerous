from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.exceptions import CommandLineError
from tradeenv import TradeEnv
import pathlib
import sys
import os


class CommandResults(object):
    """
        Encapsulates the results returned by running a command.
    """

    def __init__(self, cmdenv):
        self.cmdenv = cmdenv
        self.summary, self.rows = {}, []

    def render(self, cmdenv=None, tdb=None):
        cmdenv = cmdenv or self.cmdenv
        tdb = tdb or cmdenv.tdb
        cmdenv._cmd.render(self, cmdenv, tdb)


class ResultRow(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class CommandEnv(TradeEnv):
    """
        Base class for a TradeDangerous sub-command which has auxilliary
        "environment" data in the form of command line options.
    """

    def __init__(self, properties, argv, cmdModule):
        super().__init__(properties=properties)
        self.tdb = None
        self.mfd = None
        self.argv = argv or sys.argv

        if properties.detail and properties.quiet:
            raise CommandLineError("'--detail' (-v) and '--quiet' (-q) are mutually exclusive.")

        self._cmd   = cmdModule or __main__
        self.wantsTradeDB = getattr(cmdModule, 'wantsTradeDB', True)

        # We need to relocate to the working directory so that
        # we can load a TradeDB after this without things going
        # pear-shaped
        if not properties.cwd and argv[0]:
            cwdPath = pathlib.Path('.').resolve()
            exePath = pathlib.Path(argv[0]).parent.resolve()
            if cwdPath != exePath:
                self.cwd = str(exePath)
                self.DEBUG(1, "cwd at launch was: {}, changing to {} to match trade.py",
                                cwdPath, self.cwd)
        if self.cwd:
            os.chdir(self.cwd)


    def run(self, tdb):
        """
            Set the current database context for this env and check that
            the properties we have are valid.
        """
        self.tdb = tdb

        self.checkMFD()
        self.checkFromToNear()
        self.checkAvoids()
        self.checkVias()
        self.checkShip()

        results = CommandResults(self)
        return self._cmd.run(results, self, tdb)


    def render(self, results):
        self._cmd.render(self, results, self, self.tdb)


    def checkMFD(self):
        self.mfd = None
        try:
            if not self.x52pro:
                return
        except AttributeError:
            return

        from mfd import X52ProMFD
        self.mfd = X52ProMFD()


    def checkFromToNear(self):
        def check(label, fn, fieldName):
            key = getattr(self._props, fieldName, None)
            if key:
                try:
                    return fn(key)
                except LookupError:
                    raise CommandLineError(
                            "Unrecognized {}: {}"
                                .format(label, key))
            return None

        stnLookup = self.tdb.lookupStation
        sysLookup = self.tdb.lookupSystemRelaxed
        self.startStation = check('origin station', stnLookup, 'origin')
        self.startSystem  = check('origin system', sysLookup, 'startSys')
        self.stopStation  = check('destination station', stnLookup, 'dest')
        self.stopSystem   = check('destination system', sysLookup, 'endSys')
        self.nearSystem   = check('system', sysLookup, 'near')


    def checkAvoids(self):
        """
            Process a list of avoidances.
        """

        avoidItems = self.avoidItems = []
        avoidSystems = self.avoidSystems = []
        avoidStations = self.avoidStations = []

        try:
            avoidances = self._props.avoid
            if not avoidances:
                raise AttributeError("Fake")
        except AttributeError:
            self.avoidPlaces = []
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

        self.avoidPlaces = self.avoidSystems + self.avoidStations


    def checkVias(self):
        """ Process a list of station names and build them into a list of waypoints. """
        viaStationNames = getattr(self._props, 'via', None)
        viaStations = self.viaStations = []
        # accept [ "a", "b,c", "d" ] by joining everything and then splitting it.
        if viaStationNames:
            for via in ",".join(viaStationNames).split(","):
                viaStations.add(self.tdb.lookupStation(via))


    def checkShip(self):
        """ Parse user-specified ship and populate capacity and maxLyPer from it. """
        ship = getattr(self._props, 'ship', None)
        if ship is None:
            return

        ship = self.ship = self.tdb.lookupShip(ship)

        # Assume we want maxLyFull unless there's a --full that's explicitly False
        if getattr(self._props, 'full', True):
            shipMaxLy = ship.maxLyFull
        else:
            shipMaxLy = ship.maxLyEmpty

        self.capacity = self.capacity or ship.capacity
        self.maxLyPer = self.maxLyPer or shipMaxLy

