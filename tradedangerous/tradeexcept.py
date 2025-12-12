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
    
    def __str__(self) -> str:
        anyMatch, key = self.anyMatch, self.key

        # ------------------------------------------------------------------
        # Special-case: system name collisions where we passed in
        # (index, System) pairs from TradeDB.lookupSystem.
        # ------------------------------------------------------------------
        if (
            self.lookupType == "System"
            and anyMatch
            and isinstance(anyMatch[0], tuple)
            and len(anyMatch[0]) >= 2
        ):
            lines = [
                f'System name "{self.searchKey}" refers to more than one distinct system.',
                "",
                'Select the one you intended using "@N":',
                "",
            ]
            for index, system in anyMatch:
                # Be tolerant in case the contents are not exactly (int, System)
                try:
                    name = system.dbname
                    x, y, z = system.posX, system.posY, system.posZ
                    lines.append(
                        f"    {name}@{index} 45 ({x:.1f}, {y:.1f}, {z:.1f})"
                    )
                except Exception:
                    # Fallback to the provided key() formatter
                    lines.append(f"    {key((index, system))}")
            lines.append("")
            lines.append("(Index numbers are ordered by Galactic X coordinate.)")
            return "\n".join(lines)

        # ------------------------------------------------------------------
        # Generic ambiguity formatting used everywhere else
        # ------------------------------------------------------------------
        if not anyMatch:
            # Not matching anything is not "ambiguous".
            raise RuntimeError('called AmbiguityError with no matches')

        # Truncate the list of candidates so we don't show more than 10
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
