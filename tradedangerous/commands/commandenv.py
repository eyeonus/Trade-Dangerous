from __future__ import annotations

from pathlib import Path
import os
import sys
import typing

import ijson

from .exceptions import (
    CommandLineError, FleetCarrierError, OdysseyError,
    PadSizeError, PlanetaryError,
)

from tradedangerous import TradeEnv
from tradedangerous.tradedb import AmbiguityError, Station


if typing.TYPE_CHECKING:
    from argparse import Namespace
    from typing import Any, ModuleType
    
    from tradedangerous import TradeDB, TradeORM


# See: https://espterm.github.io/docs/VT100%20escape%20codes.html
# or : https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences
#
# ANSI-compliant "terminal" streams support changing the color (including boldness) of text
# with 'Color Sequence' codes, consisting of an initializer (CS), one or more semicolon-separated (;)
# parameters, and a command code.
#
# The CSI is ESC '[' where esc is 1b in hex or 033 in octal.
# For color-changes, the command is 'm'.
# To clear all color-code/effect changes, the sequence is : [escape, '[', '0', 'm'].
#
ANSI_CSI = "\033["
ANSI_COLOR_CMD = "m" 
ANSI_COLOR = {
    "CLEAR": "0",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "lightGray": "37",
    "darkGray": "90",
    "lightRed": "91",
    "lightGreen": "92",
    "lightYellow": "93",
    "lightBlue": "94",
    "lightMagenta": "95",
    "lightCyan": "96",
    "white": "97",
}
ANSI_CLEAR = f"{ANSI_CSI}{ANSI_COLOR['CLEAR']}{ANSI_COLOR_CMD}"


class ResultRow:
    """ ResultRow captures a data item returned by a command. It's really an abstract namespace. """
    def __init__(self, **kwargs: typing.Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class CommandResults:
    """ Encapsulates the results returned by running a command.  """
    cmdenv: 'CommandEnv'
    summary: ResultRow
    rows: list[ResultRow]
    
    def __init__(self, cmdenv: 'CommandEnv') -> None:
        self.cmdenv = cmdenv
        self.summary = ResultRow()
        self.rows = []
    
    def render(self, cmdenv: 'CommandEnv' = None, tdb: TradeDB | TradeORM | None = None) -> None:
        cmdenv = cmdenv or self.cmdenv
        tdb = tdb or cmdenv.tdb
        cmdenv._cmd.render(self, cmdenv, tdb)


class CommandEnv(TradeEnv):
    """
        Base class for a TradeDangerous sub-command which has auxilliary
        "environment" data in the form of command line options.
    """
    def __init__(self, properties: dict[str, Any] | Namespace | None, argv: list[str] | None, cmdModule: ModuleType | None) -> None:
        super().__init__(properties = properties)
        
        self.tdb = None
        self.mfd = None
        self.argv = argv or sys.argv
        self._preflight_done = False
        
        if self.detail and self.quiet:
            raise CommandLineError("'--detail' (-v) and '--quiet' (-q) are mutually exclusive.")
        
        self._cmd = cmdModule
        self.wantsTradeDB = getattr(cmdModule, 'wantsTradeDB', True)
        self.usesTradeData = getattr(cmdModule, 'usesTradeData', False)
        
        # We need to relocate to the working directory so that
        # we can load a TradeDB after this without things going
        # pear-shaped
        if not self.cwd and argv[0]:
            cwdPath = Path('.').resolve()
            exePath = Path(argv[0]).parent.resolve()
            if cwdPath != exePath:
                self.cwd = str(exePath)
                self.DEBUG1("cwd at launch was: {}, changing to {} to match trade.py", cwdPath, self.cwd)
        if self.cwd:
            os.chdir(self.cwd)
    
    def preflight(self) -> None:
        """
        Phase A: quick validation that must be able to short-circuit before any
        heavy TradeDB(load=True) path is invoked.
        
        Commands may optionally implement validateRunArgumentsFast(cmdenv).
        """
        if self._preflight_done:
            return
        
        self._preflight_done = True
        
        fast_validator = getattr(self._cmd, "validateRunArgumentsFast", None)
        if fast_validator:
            fast_validator(self)
    
    def run(self, tdb: TradeDB | TradeORM) -> CommandResults | bool | None:
        """ Try and execute the business logic of the command. Query commands
            will return a result set for us to render, whereas operational
            commands will likely do their own rendering as they work. """
        # Ensure fast validation is executed for non-CLI call paths too.
        self.preflight()
        
        # Set the current database context for this env and check that
        # the properties we have are valid.
        self.tdb = tdb
        update_database_schema(self.tdb)
        
        if self.wantsTradeDB:
            self.checkFromToNear()
            self.checkAvoids()
            self.checkVias()
        
        self.checkPlanetary()
        self.checkFleet()
        self.checkOdyssey()
        self.checkPadSize()
        self.checkMFD()
        
        results = CommandResults(self)
        return self._cmd.run(results, self, tdb)
    
    def render(self, results: CommandResults) -> None:
        self._cmd.render(self, results, self, self.tdb)
    
    def checkMFD(self) -> None:
        self.mfd = None
        try:
            if not self.x52pro:
                return
        except AttributeError:
            return
        
        # The x52 module throws some hard errors, so we really only want to
        # import it as a last resort when the user has asked. We can't do a
        # soft "try and import and tell the user later".
        from tradedangerous.mfd import X52ProMFD  # noqa
        self.mfd = X52ProMFD()
    
    def checkFromToNear(self) -> None:
        if not self.wantsTradeDB:
            return
        
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
                    label,
                    key,
                    place.stations,
                    key=lambda st: (
                        f"{st.text()} — "
                        f"({st.system.posX:.1f}, {st.system.posY:.1f}, {st.system.posZ:.1f})"
                    ),
                )
            
            return place.stations[0]
        
        def lookupPlace(label, fieldName):
            key = getattr(self, fieldName, None)
            if key:
                return self.tdb.lookupPlace(key)
            return None
        
        self.startStation = check('origin station', 'origin', True)
        self.stopStation = check('destination station', 'dest', True)
        self.origPlace = lookupPlace('origin', 'starting')
        self.destPlace = lookupPlace('destination', 'ending')
        self.nearSystem = check('system', 'near', False)
    
    def checkAvoids(self) -> None:
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
                raise AmbiguityError('Avoidance', avoid, [ item, place.text() ])
        
        self.DEBUG0("Avoiding items {}, places {}",
                    [ item.name() for item in avoidItems ],
                    [ place.name() for place in avoidPlaces ],
        )
    
    def checkVias(self) -> None:
        """ Process a list of station names and build them into a list of waypoints. """
        viaPlaceNames = getattr(self, 'via', None)
        viaPlaces = self.viaPlaces = []
        # accept [ "a", "b,c", "d" ] by joining everything and then splitting it.
        if viaPlaceNames:
            for via in ",".join(viaPlaceNames).split(","):
                viaPlaces.append(self.tdb.lookupPlace(via))
    
    def checkPadSize(self) -> None:
        padSize = getattr(self, 'padSize', None)
        if not padSize:
            return
        padSize = ''.join(sorted(set(padSize))).upper()
        if padSize == '?LMS':
            self.padSize = None
            return
        self.padSize = padSize = padSize.upper()
        for value in padSize:
            if value not in 'SML?':
                raise PadSizeError(padSize)
        self.padSize = padSize
    
    def checkPlanetary(self) -> None:
        planetary = getattr(self, 'planetary', None)
        if not planetary:
            return
        planetary = ''.join(sorted(set(planetary))).upper()
        if planetary == '?NY':
            self.planetary = None
            return
        self.planetary = planetary = planetary.upper()
        for value in planetary:
            if value not in 'YN?':
                raise PlanetaryError(planetary)
        self.planetary = planetary
    
    def checkFleet(self) -> None:
        fleet = getattr(self, 'fleet', None)
        if not fleet:
            return
        fleet = ''.join(sorted(set(fleet))).upper()
        for value in fleet:
            if value not in 'YN?':
                raise FleetCarrierError(fleet)
        if fleet == '?NY':
            self.fleet = None
            return
        self.fleet = fleet = fleet.upper()
    
    def checkOdyssey(self) -> None:
        odyssey = getattr(self, 'odyssey', None)
        if not odyssey:
            return
        odyssey = ''.join(sorted(set(odyssey))).upper()
        for value in odyssey:
            if value not in 'YN?':
                raise OdysseyError(odyssey)
        if odyssey == '?NY':
            self.odyssey = None
            return
        self.odyssey = odyssey.upper()
    
    def colorize(self, color: str, raw_text: str) -> str:
        """
        Set up some coloring for readability.
        TODO: Rich already does this, use it instead?
        """
        if (code := ANSI_COLOR.get(color)):
            # Only do anything if there's a code for that.
            return f"{ANSI_CSI}{code}{ANSI_COLOR_CMD}{raw_text}{ANSI_CLEAR}"
        # Otherwise, keep it raw.
        return raw_text


def update_database_schema(tdb: TradeDB | TradeORM) -> None:
    """ Check if there are database changes to be made, and if so, execute them. """
    # TODO: This should really be a function of the DB itself and not something
    # the caller has to ask the database to do for it.
    template_folder = getattr(tdb, "templatePath", None)
    if not template_folder:
        return
    
    db_change = Path(template_folder, "database_changes.json")
    if not db_change.exists():
        return
    
    try:
        with db_change.open("r", encoding="utf-8") as file:
            for change in ijson.items(file, 'item'):
                tdb.getDB().execute(change)
    finally:
        db_change.unlink()
