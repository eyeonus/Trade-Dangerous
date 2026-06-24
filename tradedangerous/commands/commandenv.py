from __future__ import annotations

from enum import Flag, auto
from pathlib import Path
import sys
import typing

import ijson

from .exceptions import (
    CommandLineError, FleetCarrierError, SettlementError,
    PadSizeError, PlanetaryError,
)

from tradedangerous import TradeEnv
from tradedangerous.db import orm_models as orm


if typing.TYPE_CHECKING:
    from argparse import Namespace
    from typing import Any, ModuleType
    
    from tradedangerous import TradeORM


def _canonical_place_name(place):
    """Display name a resolved place echoes as: 'Sol' for a system,
    'Sol/Abraham Lincoln' for a station."""
    if isinstance(place, orm.Station):
        return place.dbname()
    return place.name


def _resolution_is_exact(raw, place):
    """True when the user's token already names ``place`` exactly (ignoring
    case), so no resolved-as echo is warranted. Strips the namespace decoration
    the syntax uses — a leading @, a leading/trailing slash, and an @N index —
    before comparing, so 'Sol', 'Sol/' and '@Sol' are all exact for system Sol,
    and 'Sol/Abraham Lincoln' / '/Abraham Lincoln' are exact for that station."""
    token = (raw or "").strip().replace("\\", "/")
    if token.startswith("@"):
        token = token[1:]
    at = token.rfind("@")
    if at > 0 and token[at + 1:].isdigit():
        token = token[:at]
    token = token.strip("/").strip().casefold()
    if isinstance(place, orm.Station):
        return token in (place.dbname().casefold(), place.name.casefold())
    return token == place.name.casefold()


def echo_resolution(label, raw, place):
    """Print a 'resolved as' line when a fuzzy or abbreviated token expanded to
    a different canonical name. Exact input — including a pure case difference
    or an @N selection — stays quiet. This gives every resolver-tier command the
    same expansion feedback ``trade run`` already prints for its endpoints."""
    if place is None or _resolution_is_exact(raw, place):
        return
    print(
        "{} {} resolved as {}".format(label, raw, _canonical_place_name(place)),
        flush=True,
    )


class Needs(Flag):
    """Backend capability requirements for a command.

    Commands declare their backend needs via a module-level ``needs``
    attribute. Every command must declare one; a module with no declaration
    is treated as incomplete and fails during command setup.
    """
    NOTHING  = 0        # no backend required (e.g. deprecated no-ops)
    RESOLVER = auto()   # TradeORM resolver only


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
    
    def render(self, cmdenv: 'CommandEnv' = None, tdb: TradeORM | None = None) -> None:
        cmdenv = cmdenv or self.cmdenv
        tdb = tdb or cmdenv.tdb
        cmdenv._cmd.render(self, cmdenv, tdb)  # type: ignore


class CommandEnv(TradeEnv):
    """
        Base class for a TradeDangerous sub-command which has auxilliary
        "environment" data in the form of command line options.
    """
    def __init__(self, properties: dict[str, Any] | Namespace | None, argv: list[str] | None, cmdModule: ModuleType | None) -> None:
        super().__init__(properties = properties)
        
        self.tdb = None
        self.argv = argv or sys.argv
        self._preflight_done = False
        
        if self.detail and self.quiet:
            raise CommandLineError("'--detail' (-v) and '--quiet' (-q) are mutually exclusive.")
        
        self._cmd = cmdModule
        needs_selector = getattr(cmdModule, 'selectNeeds', None)
        if needs_selector and callable(needs_selector):
            self.commandNeeds = needs_selector(self)
        else:
            _module_needs = getattr(cmdModule, 'needs', None)
            if _module_needs is None:
                # Every command must declare its backend needs explicitly. A
                # module with no declaration is an incomplete command, not a
                # legacy one, so fail loudly rather than hand it a backend.
                cmd_name = getattr(cmdModule, 'name', cmdModule)
                raise CommandLineError(
                    f"Command '{cmd_name}' does not declare its backend "
                    "needs (set needs = Needs.RESOLVER or Needs.NOTHING)."
                )
            self.commandNeeds = _module_needs
        self.needs_resolver = bool(self.commandNeeds & Needs.RESOLVER)
        self.usesTradeData = getattr(cmdModule, 'usesTradeData', False)
    
    def preflight(self) -> None:
        """
        Phase A: quick validation that must be able to short-circuit before the
        TradeORM database handle is built.
        
        Commands may optionally implement validateRunArgumentsFast(cmdenv).
        """
        if self._preflight_done:
            return
        
        self._preflight_done = True
        
        fast_validator = getattr(self._cmd, "validateRunArgumentsFast", None)
        if fast_validator:
            fast_validator(self)
    
    def run(self, tdb: TradeORM) -> CommandResults | bool | None:
        """ Try and execute the business logic of the command. Query commands
            will return a result set for us to render, whereas operational
            commands will likely do their own rendering as they work. """
        # Ensure fast validation is executed for non-CLI call paths too.
        self.preflight()
        
        # Set the current database context for this env and check that
        # the properties we have are valid.
        self.tdb = tdb
        update_database_schema(self.tdb)

        skip_resolver_prechecks = getattr(
            self._cmd,
            'skipResolverPrechecks',
            False,
        )
        if self.needs_resolver and not skip_resolver_prechecks:
            self.checkFromToNearORM()
            self.checkAvoidsORM()
            self.checkViasORM()
        
        self.checkPlanetary()
        self.checkFleet()
        self.checkSettlement()
        self.checkPadSize()
        
        results = CommandResults(self)
        return self._cmd.run(results, self, tdb)

    def checkFromToNearORM(self) -> None:
        def _resolve_place(label, fieldName):
            key = getattr(self, fieldName, None)
            if not key:
                return None
            try:
                place = self.tdb.lookup_place(key)
            except LookupError:
                raise CommandLineError(
                    "Unrecognized {}: {}".format(label, key)
                )
            echo_resolution(label, key, place)
            return place

        def _resolve_system(label, fieldName):
            place = _resolve_place(label, fieldName)
            if place is None:
                return None
            if isinstance(place, orm.Station):
                return place.system
            return place

        self.origPlace  = _resolve_place('origin', 'starting')
        self.destPlace  = _resolve_place('destination', 'ending')
        self.nearSystem = _resolve_system('system', 'near')

    def checkAvoidsORM(self) -> None:
        """Resolver-tier equivalent of checkAvoids().

        Mirrors the legacy try-item-then-place logic: each token is first
        resolved as an item, then as a place.  An exact CI item match skips
        the place lookup; a partial item match falls through so both can be
        appended independently.  AmbiguityError from either lookup propagates.
        """
        avoidItems = self.avoidItems = []
        avoidPlaces = self.avoidPlaces = []
        avoidances = getattr(self, 'avoid', None)
        if not avoidances:
            return
        for avoid in ','.join(avoidances).split(','):
            avoid = avoid.strip()
            if not avoid:
                continue
            item = None
            try:
                item = self.tdb.lookup_item(avoid)
                avoidItems.append(item)
                if self.tdb.normalize_str(item.name) == self.tdb.normalize_str(avoid):
                    continue
            except LookupError:
                pass
            try:
                place = self.tdb.lookup_place(avoid)
                avoidPlaces.append(place)
                echo_resolution('avoid', avoid, place)
                continue
            except LookupError:
                pass
            if not item:
                raise CommandLineError(
                    "Unknown item/system/station: {}".format(avoid)
                )

    def checkViasORM(self) -> None:
        """Resolver-tier equivalent of checkVias()."""
        viaPlaces = self.viaPlaces = []
        viaPlaceNames = getattr(self, 'via', None)
        if not viaPlaceNames:
            return
        for via in ','.join(viaPlaceNames).split(','):
            via = via.strip()
            if not via:
                continue
            try:
                place = self.tdb.lookup_place(via)
                viaPlaces.append(place)
                echo_resolution('via', via, place)
            except LookupError:
                raise CommandLineError(
                    "Unknown system/station: {}".format(via)
                )

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
    
    def checkSettlement(self) -> None:
        settlement = getattr(self, 'settlement', None)
        if not settlement:
            return
        settlement = ''.join(sorted(set(settlement))).upper()
        for value in settlement:
            if value not in 'YN?':
                raise SettlementError(settlement)
        if settlement == '?NY':
            self.settlement = None
            return
        self.settlement = settlement.upper()
        if 'Y' in self.settlement:
            planetary = getattr(self, 'planetary', None)
            if planetary and 'Y' not in planetary:
                raise CommandLineError(
                    "--settlement Y requires planetary Y because all "
                    "settlements are planetary stations."
                )
    
def update_database_schema(tdb: TradeORM) -> None:
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
