from commands.exceptions import CommandLineError
import pathlib

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
    pass


class CommandEnv(object):
    """
        Base class for a TradeDangerous sub-command which has auxilliary
        "environment" data in the form of command line options.
    """

    def __init__(self, argv, cmdModule, properties):
        self.tdb = None
        self.mfd = None

        if properties.detail and properties.quiet:
            raise CommandLineError("'--detail' (-v) and '--quiet' (-q) are mutually exclusive.")

        self._argv  = argv
        self._cmd   = cmdModule
        self._props = properties
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


    def __getattr__(self, key, default=None):
        """ Fall back to _props when accessing attributes. """
        try:
            return getattr(self._props, key, default)
        except AttributeError:
            return default


    def DEBUG(self, debugLevel, outText, *args, **kwargs):
        """
            Output text to stderr on the condition that
            the current debug setting is higher than debugLevel
        """
        if self.debug > debugLevel:
            print('#', outText.format(*args, **kwargs))


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
        origin = getattr(self._props, 'origin', None)
        if origin:
            self.startStation = self.tdb.lookupStation(origin)
        else:
            self.startStation = None
        origin = getattr(self._props, 'startSys', None)
        if origin:
            self.startSystem = self.tdb.lookupSystemRelaxed(origin)
        else:
            self.startSystem = None
        dest = getattr(self._props, 'dest', None)
        if dest:
            self.stopStation = self.tdb.lookupStation(dest)
        else:
            self.stopStation = None
        dest = getattr(self._props, 'endSys', None)
        if dest:
            self.stopSystem = self.tdb.lookupSystemRelaxed(dest)
        else:
            self.stopSystem = None
        near = getattr(self._props, 'near', None)
        if near:
            self.nearSystem = self.tdb.lookupSystemRelaxed(near)
        else:
            self.nearSystem = None


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

