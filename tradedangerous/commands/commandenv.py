from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

from .exceptions import CommandLineError, PadSizeError, PlanetaryError
from ..tradedb import AmbiguityError, System, Station
from ..tradeenv import TradeEnv

import os
import pathlib
import sys


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

        if self.detail and self.quiet:
            raise CommandLineError("'--detail' (-v) and '--quiet' (-q) are mutually exclusive.")

        self._cmd   = cmdModule or __main__
        self.wantsTradeDB = getattr(cmdModule, 'wantsTradeDB', True)
        self.usesTradeData = getattr(cmdModule, 'usesTradeData', False)

        # We need to relocate to the working directory so that
        # we can load a TradeDB after this without things going
        # pear-shaped
        if not self.cwd and argv[0]:
            cwdPath = pathlib.Path('.').resolve()
            exePath = pathlib.Path(argv[0]).parent.resolve()
            if cwdPath != exePath:
                self.cwd = str(exePath)
                self.DEBUG1("cwd at launch was: {}, changing to {} to match trade.py",
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
        self.checkPadSize()
        self.checkPlanetary()

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

        from ..mfd import X52ProMFD
        self.mfd = X52ProMFD()


    def checkFromToNear(self):
        def check(label, fieldName, wantStation):
            key = getattr(self, fieldName, None)
            if not key:
                return None

            try:
                place = self.tdb.lookupPlace(key)
            except LookupError:
                raise CommandLineError(
                        "Unrecognized {}: {}"
                            .format(label, key))
            if not wantStation:
                if isinstance(place, Station):
                    return place.system
                return place


            if isinstance(place, Station):
                return place

            # it's a system, we want a station
            if not place.stations:
                raise CommandLineError(
                        "Station name required for {}: "
                        "{} is a SYSTEM but has no stations.".format(
                            label, key
                        ))
            if len(place.stations) > 1:
                raise AmbiguityError(
                        label, key, place.stations,
                        key=lambda key: key.name()
                )

            return place.stations[0]

        def lookupPlace(label, fieldName):
            key = getattr(self, fieldName, None)
            if key:
                return self.tdb.lookupPlace(key)
            return None


        self.startStation = check('origin station', 'origin', True)
        self.stopStation  = check('destination station', 'dest', True)
        self.origPlace    = lookupPlace('origin', 'starting')
        self.destPlace    = lookupPlace('destination', 'ending')
        self.nearSystem   = check('system', 'near', False)


    def checkAvoids(self):
        """
            Process a list of avoidances.
        """

        avoidItems = self.avoidItems = []
        avoidPlaces = self.avoidPlaces = []
        avoidances = self.avoid
        if not self.avoid:
            return
        avoidances = self.avoid

        tdb = self.tdb

        # You can use --avoid to specify an item, system or station.
        # and you can group them together with commas or list them
        # individually.
        for avoid in ','.join(avoidances).split(','):
            # Is it an item?
            item, place = None, None
            try:
                item = tdb.lookupItem(avoid)
                avoidItems.append(item)
                if tdb.normalizedStr(item.name()) == tdb.normalizedStr(avoid):
                    continue
            except LookupError:
                pass
            # Or is it a place?
            try:
                place = tdb.lookupPlace(avoid)
                avoidPlaces.append(place)
                if tdb.normalizedStr(place.name()) == tdb.normalizedStr(avoid):
                    continue
                continue
            except LookupError:
                pass

            # If it was none of the above, whine about it
            if not (item or place):
                raise CommandLineError("Unknown item/system/station: {}".format(avoid))

            # But if it matched more than once, whine about ambiguity
            if item and place:
                raise AmbiguityError('Avoidance', avoid, [ item, place.str() ])

        self.DEBUG0("Avoiding items {}, places {}",
                    [ item.name() for item in avoidItems ],
                    [ place.name() for place in avoidPlaces ],
        )


    def checkVias(self):
        """ Process a list of station names and build them into a list of waypoints. """
        viaPlaceNames = getattr(self, 'via', None)
        viaPlaces = self.viaPlaces = []
        # accept [ "a", "b,c", "d" ] by joining everything and then splitting it.
        if viaPlaceNames:
            for via in ",".join(viaPlaceNames).split(","):
                viaPlaces.append(self.tdb.lookupPlace(via))

    def checkPadSize(self):
        padSize = getattr(self, 'padSize', None)
        if not padSize:
            return
        padSize = ''.join(sorted(list(set(padSize)))).upper()
        if padSize == '?LMS':
            self.padSize = None
            return
        self.padSize = padSize = padSize.upper()
        for value in padSize:
            if not value in 'SML?':
                raise PadSizeError(padSize)
        self.padSize = padSize

    def checkPlanetary(self):
        planetary = getattr(self, 'planetary', None)
        if not planetary:
            return
        planetary = ''.join(sorted(list(set(planetary)))).upper()
        if planetary == '?NY':
            self.planetary = None
            return
        self.planetary = planetary = planetary.upper()
        for value in planetary:
            if not value in 'YN?':
                raise PlanetaryError(planetary)
        self.planetary = planetary
