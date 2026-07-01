"""
tradeexcept defines standard exceptions used within TradeDangerous.
"""
from __future__ import annotations
import typing

if typing.TYPE_CHECKING:
    try:
        from collections.abc import Callable
    except ImportError:
        from typing import Callable
    from typing import Any
    from pathlib import Path


AMBIGUITY_LIMIT = 6


class SimpleAbort(Exception):
    """
        SimpleAbort is Exception but can be caught and presented without
        any kind of backtrace.
    """


class TradeException(Exception):
    """
        Distinguishes runtime logical errors (such as no data for what you
        queried) from programmatic errors (such as Oliver accessing a hash
        with the wrong type of key).
        
        TradeExcepts should be caught by the program and displayed in the
        most user friendly way possible.
    """
    pass


class MissingDB(TradeException):
    """
        Reports that the database is missing in a scenario where it is
        required and not default-created for the user.
        
        Ideally, this should describe to the user how to create the
        database, perhaps through a "bootstrap" subcommand.
    """
    def __init__(self, dbpath: str | Path):
        super().__init__(
            f"{dbpath}: Data file(s) are missing, you must initialize the database first. "
            "Consider using `trade import -P eddblink -O bootstrap` or if you are "
            "managing data by hand, use the buildcache subcommand."
        )


def format_system_candidates(systems) -> list[str]:
    """Render duplicate-system candidates as indented '@N' lines.

    Each line is ``    Name@N - (x, y, z)`` (em dash in the live output),
    1-based, in the order supplied — the lookup orders by ascending Galactic X,
    then Y, Z, id. Takes ORM System rows (name, pos_x/pos_y/pos_z). This is the
    single place that owns the format, shared by the bare duplicate-name error
    and the invalid-@N error so the two can never drift apart.
    """
    return [
        f"    {system.name}@{index} — "
        f"({system.pos_x:.1f}, {system.pos_y:.1f}, {system.pos_z:.1f})"
        for index, system in enumerate(systems, start=1)
    ]


class AmbiguityError(TradeException):
    """
        Raised when a search key could match multiple entities.
        Attributes:
            lookupType - description of what was being queried,
            searchKey  - the key given to the search routine,
            anyMatch   - list of items which were found to match, if any
            key        - retrieve the display string for a candidate
    """
    def __init__(
            self,
            lookupType: str,
            searchKey: str,
            anyMatch: list[Any],
            key: Callable[[Any], str] = lambda item: item
            ) -> None:
        self.lookupType = lookupType
        self.searchKey = searchKey
        self.anyMatch = anyMatch
        self.key = key
        # Render candidate labels now, while we are still inside the live DB
        # session that produced these ORM objects. Deferring key() to __str__
        # is unsafe: the CLI stringifies the error after the session has closed,
        # and a key such as Station.dbname() crosses the Station->System
        # relationship, which cannot lazy-load on a detached instance
        # (DetachedInstanceError). The (index, System) tuple form used for
        # duplicate-system collisions is rendered separately in __str__ from
        # columns only, so it is skipped here.
        self.rendered = None
        if anyMatch and not isinstance(anyMatch[0], tuple):
            self.rendered = [key(c) for c in anyMatch[:AMBIGUITY_LIMIT]]

    def __str__(self) -> str:
        anyMatch, key = self.anyMatch, self.key
        
        # ------------------------------------------------------------------
        # Special-case: system name collisions where we passed in
        # (index, System) pairs from the system lookup.
        # ------------------------------------------------------------------
        if (
            self.lookupType == "System"
            and anyMatch
            and isinstance(anyMatch[0], tuple)
            and len(anyMatch[0]) >= 2
        ):
            systems = [system for _index, system in anyMatch]
            lines = [
                f'System name "{self.searchKey}" refers to more than one distinct system.',
                "",
                'Select the one you intended using "@N":',
                "",
            ]
            lines.extend(format_system_candidates(systems))
            lines.append("")
            lines.append("(Index numbers are ordered by Galactic X coordinate.)")
            return "\n".join(lines)
        
        # ------------------------------------------------------------------
        # Generic ambiguity formatting used everywhere else
        # ------------------------------------------------------------------
        if not anyMatch:
            # Not matching anything is not "ambiguous".
            raise RuntimeError('called AmbiguityError with no matches')
        
        # Truncate the list of candidates so we don't show more than 10.
        # Prefer the labels rendered eagerly at construction time, while the DB
        # session was still live; fall back to applying key() now only if they
        # were not captured.
        if self.rendered is not None:
            candidates = list(self.rendered)
        else:
            candidates = [key(c) for c in anyMatch[:AMBIGUITY_LIMIT]]
        if len(anyMatch) < 3:
            opportunities = " or ".join(candidates)
        else:
            if len(anyMatch) > AMBIGUITY_LIMIT:
                candidates[-1] = "..."
            else:
                candidates[-1] = "or " + candidates[-1]  # oxford comma
            opportunities = ", ".join(candidates)
        
        return f'{self.lookupType} "{self.searchKey}" could match {opportunities}'


class SystemNotStationError(TradeException):
    """ Raised when a station lookup matched a System but
        could not be automatically reduced to a Station.  """

# ---------------------------------------------------------------------
# Data-file import / parse errors (moved here from the former cache.py).
# Used by both the CSV importer (db/import_csv.py) and the .prices
# importer (import_prices.py).
# ---------------------------------------------------------------------


class BuildCacheBaseException(TradeException):
    """
    Baseclass for BuildCache exceptions
    Attributes:
        fileName    Name of file being processedStations
        lineNo      Line the error occurred on
        error       Description of the error
    """
    
    def __init__(self, fromFile: Path, lineNo: int, error: str | None = None) -> None:
        self.fileName = fromFile.name
        self.lineNo = lineNo
        self.category = "ERROR"
        self.error = error or "UNKNOWN ERROR"
    
    def __str__(self) -> str:
        return f'{self.fileName}:{self.lineNo} {self.category} {self.error}'


class DuplicateKeyError(BuildCacheBaseException):
    """
        Raised when an item is being redefined.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, keyType: str, keyValue: str, prevLineNo: int) -> None:
        super().__init__(fromFile, lineNo,
                         f'Second occurrance of {keyType} "{keyValue}", previous entry at line {prevLineNo}.')


class DeletedKeyError(BuildCacheBaseException):
    """
    Raised when a key value in a .csv file is marked as DELETED in the
    corrections file.
    """
    
    def __init__(self, fromFile: Path, lineNo: int, keyType: str, keyValue: str) -> None:
        super().__init__(
            fromFile, lineNo,
            f'{keyType} "{keyValue}" is marked as DELETED and should not be used.'
        )


class MultipleStationEntriesError(DuplicateKeyError):
    """ Raised when a station appears multiple times in the same file. """
    
    def __init__(self, fromFile: Path, lineNo: int, facility: str, prevLineNo: int) -> None:
        super().__init__(fromFile, lineNo, 'station', facility, prevLineNo)


class InvalidLineError(BuildCacheBaseException):
    """
    Raised when an invalid line is read.
    Attributes:
        problem     The problem that occurred
        text        Offending text
    """
    
    def __init__(self, fromFile: Path, lineNo: int, problem: str, text: str) -> None:
        super().__init__(fromFile, lineNo, f'{problem},\ngot: "{text.strip()}".')


class SupplyError(BuildCacheBaseException):
    """
    Raised when a supply field is incorrectly formatted.
    """

    def __init__(self, fromFile: Path, lineNo: int, category: str, problem: str, value: Any) -> None:
        super().__init__(fromFile, lineNo, f'Invalid {category} supply value: {problem}. Got: {value}')


class UnknownSystemError(BuildCacheBaseException):
    """
    Raised when the file contains an unknown star name.
    """

    def __init__(self, fromFile: Path, lineNo: int, key: str) -> None:
        super().__init__(fromFile, lineNo, f'Unrecognized SYSTEM: "{key}"')


class UnknownStationError(BuildCacheBaseException):
    """
    Raised when the file contains an unknown star/station name.
    """

    def __init__(self, fromFile: Path, lineNo: int, key: str) -> None:
        super().__init__(fromFile, lineNo, f'Unrecognized STAR/Station: "{key}"')


class UnknownItemError(BuildCacheBaseException):
    """
    Raised in the case of an item name that we don't know.
    Attributes:
        itemName   Key we tried to look up.
    """

    def __init__(self, fromFile: Path, lineNo: int, itemName: str) -> None:
        super().__init__(fromFile, lineNo, f'Unrecognized item name: "{itemName}"')


class MultipleItemEntriesError(DuplicateKeyError):
    """ Raised when one item appears multiple times in the same station. """

    def __init__(self, fromFile: Path, lineNo: int, item: str, prevLineNo: int) -> None:
        super().__init__(fromFile, lineNo, 'item', item, prevLineNo)


