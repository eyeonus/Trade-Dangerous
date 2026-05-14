"""
tradeorm provides the TradeORM class which uses the application database
rather than trying to be its own database in its own right like TradeDB.

Suggested use:

    # TradeEnv is optional, it's for controlling environment settings
    # builder-pattern style.
    from tradedangerous import TradeEnv, TradeORM

    tde = TradeEnv()  # debug settings, color, etc...
    tdo = TradeORM(tde)  # if not supplied, it will make its own
"""
from __future__ import annotations
from pathlib import Path
import os
import re
import typing

from . import TradeEnv
from .tradeexcept import AmbiguityError, TradeException, MissingDB, SystemNotStationError
from .db import (
    orm_models as orm,          # type: ignore  # so we can access models easily
    make_engine_from_config,    # type: ignore
    get_session_factory,        # type: ignore
)

if typing.TYPE_CHECKING:
    from .db.engine import sessionmaker, Engine, Session  # type: ignore

# Normalization tables matching TradeDB.normalizeTrans and TradeDB.trimTrans.
# Stage 1: uppercase a-z, delete [ ] ( ) * + - . , { } :
_normalize_trans = str.maketrans(
    'abcdefghijklmnopqrstuvwxyz',
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    '[]()*+-.,{}:'
)
# Stage 2: delete space and apostrophe
_trim_trans = str.maketrans('', '', " '")


class TradeORM:
    DEFAULT_PATH = "data"
    DEFAULT_DB = "TradeDangerous.db"
    DB_CONFIG_VAR = "TD_DB_CONFIG"
    DB_CONFIG_FILE = "db_config.ini"

    # Expose normalization tables as class attributes for test/external access.
    _normalize_trans = _normalize_trans
    _trim_trans = _trim_trans

    data_dir: Path
    db_path:  Path

    engine: Engine
    session_maker: sessionmaker[Session]
    session: Session

    def __init__(self, *, tdenv: TradeEnv | None = None, debug: int | None = None):
        tdenv = tdenv or TradeEnv(debug=debug or 0)
        self.tdenv = tdenv

        # Determine the legacy/default SQLite path.
        self.data_dir = Path(tdenv.dataDir)
        db_path = tdenv.dbFilename or (self.data_dir / TradeORM.DEFAULT_DB)
        self.db_path = Path(db_path)

        default_config = self.data_dir / TradeORM.DB_CONFIG_FILE
        db_config = os.environ.get(TradeORM.DB_CONFIG_VAR, default_config)
        tdenv.DEBUG0("db_config = {}", db_config)

        # Make the database available.
        self.engine = make_engine_from_config(db_config)
        backend = self.engine.dialect.name
        tdenv.DEBUG0("db_backend = {}", backend)

        # Don't raise if we don't even need a db file.
        if backend == "sqlite":
            sqlite_path = self.engine.url.database
            if sqlite_path:
                self.db_path = Path(sqlite_path)
            tdenv.DEBUG0("db_path = {}", self.db_path)
            if not self.db_path.exists():
                raise MissingDB(self.db_path)
        else:
            tdenv.DEBUG0("db_path check skipped for backend {}", backend)

        # The user will expect objects (instances of models) that we return
        # to have the same lifetime as the TradeORM() instance, so we want
        # a main session for things to use and return from.
        #
        # However: we also want them to be able to create transactions, etc
        # so we also make the session-factory available.
        self.session = get_session_factory(self.engine)()

    def commit(self):
        """ Commit the current transaction state. """
        return self.session.commit()

    def close(self, final: bool = False) -> None:
        """ Close the ORM session. """
        self.session.close()
    
    @property
    def tradingStationCount(self) -> int:
        """Return the number of stations with any market data."""
        return (
            self.session.query(orm.StationItem.station_id)
            .distinct()
            .count()
        )

    # ------------------------------------------------------------------
    # Partial-matching helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_str(s: str) -> str:
        """Apply the two-stage normalisation used by _list_search.

        Equivalent to TradeDB.normalizedStr(): stage-1 uppercases and removes
        punctuation; stage-2 removes spaces and apostrophes.
        """
        return s.translate(_normalize_trans).translate(_trim_trans)

    @staticmethod
    def _prefix_of(name: str) -> str:
        """Stage-1 normalize *name* and return the first space-delimited word.

        Used to build 'name ILIKE prefix%' DB queries that narrow candidates
        to a manageable superset before Python-side partial matching runs.
        No leading wildcard is used, so prefix scans can exploit
        idx_system_by_name / idx_station_by_name.
        """
        normalized = name.translate(_normalize_trans)
        parts = normalized.split()
        return parts[0] if parts else name

    @staticmethod
    def _list_search(
        list_type: str,
        lookup: str,
        candidates,
        key,
    ) -> object:
        """Python partial matching, mirrors TradeDB.listSearch.

        *key* extracts the display/match string from each candidate.
        Returns the single matched candidate or raises LookupError /
        AmbiguityError.

        Contract notes (PRESERVE FOR PARITY):
        - An exact normalized-length match returns immediately, bypassing
          ambiguity checking.
        - The word-boundary regex uses the original *lookup* string
          unescaped (DOCUMENTED LEGACY BUG — preserved for parity).
        """
        needle = lookup.translate(_normalize_trans).translate(_trim_trans)
        word_re = re.compile(f"\\b{lookup}\\b", re.IGNORECASE)
        partial_match: list = []
        word_match: list = []

        for entry in candidates:
            entry_key = key(entry)
            norm_val = (
                entry_key.translate(_normalize_trans).translate(_trim_trans)
            )
            if norm_val.find(needle) == -1:
                continue
            # Exact normalized-length match — return immediately, no ambiguity.
            if len(norm_val) == len(needle):
                return entry
            if word_re.match(entry_key):
                word_match.append(entry)
            else:
                partial_match.append(entry)

        if word_match:
            if len(word_match) > 1:
                raise AmbiguityError(list_type, lookup, word_match, key=key)
            return word_match[0]
        if partial_match:
            if len(partial_match) > 1:
                raise AmbiguityError(list_type, lookup, partial_match, key=key)
            return partial_match[0]
        raise LookupError(f"'{lookup}' does not match any {list_type}")

    @staticmethod
    def _place_lookup(
        token: str,
        candidates,
    ) -> tuple[list, list, list, list]:
        """Four-tier match against candidates, mirrors TradeDB.lookupPlace._lookup.

        *candidates* must expose a .name attribute (System or Station ORM objects).
        Returns (exact_match, close_match, word_match, any_match).

        Contract note (PRESERVE FOR PARITY): word boundaries are space
        characters in the stage-1-normalized string, not regex \\b.  This
        differs from _list_search which uses regex \\b.
        """
        token_norm = token.translate(_normalize_trans)
        token_trim = token_norm.translate(_trim_trans)
        token_len = len(token)
        token_norm_len = len(token_norm)
        token_trim_len = len(token_trim)

        exact_match: list = []
        close_match: list = []
        word_match: list = []
        any_match: list = []

        for place in candidates:
            place_name = place.name
            place_norm = place_name.translate(_normalize_trans)
            place_norm_len = len(place_norm)

            # Guard: trimmed needle longer than normalized candidate — skip.
            if token_trim_len > place_norm_len:
                continue

            # Tier 1: exact — same raw length and stage-1 normalized content.
            if len(place_name) == token_len and place_norm == token_norm:
                exact_match.append(place)
                continue

            # Tier 2: close — same stage-1 normalized length and content.
            if place_norm_len == token_norm_len and place_norm == token_norm:
                close_match.append(place)
                continue

            # Tier 3/4: substring with space-based word-boundary checks.
            if token_norm_len < place_norm_len:
                pos = place_norm.find(token_norm)
                if pos == 0:
                    if place_norm[token_norm_len:token_norm_len + 1] == " ":
                        word_match.append(place)
                    else:
                        any_match.append(place)
                    continue
                if pos > 0:
                    before = place_norm[pos - 1:pos]
                    after = place_norm[pos + token_norm_len:pos + token_norm_len + 1]
                    if before == " " and after == " ":
                        word_match.append(place)
                    else:
                        any_match.append(place)
                    continue

            # Trim tier: compare after removing spaces/apostrophes.
            place_trim = place_norm.translate(_trim_trans)
            place_trim_len = len(place_trim)
            if place_trim_len == place_norm_len:
                # Stage 2 changed nothing; no new information.
                continue
            if place_trim_len == token_trim_len and place_trim == token_trim:
                close_match.append(place)
            elif token_trim and place_trim.find(token_trim) >= 0:
                any_match.append(place)

        return exact_match, close_match, word_match, any_match

    @staticmethod
    def _resolve_place_tiers(
        name: str,
        exact: list,
        close: list,
        word: list,
        any_: list,
    ) -> orm.System | orm.Station:
        """Resolve four match tiers per the lookupPlace contract.

        Any tier with exactly one entry wins.  All-empty → LookupError.
        Multiple candidates across any tier → AmbiguityError.
        """
        for tier in (exact, close, word, any_):
            if len(tier) == 1:
                return tier[0]
        all_candidates = exact + close + word + any_
        if not all_candidates:
            raise LookupError(f"Unrecognized place: {name!r}")
        raise AmbiguityError(
            "Place", name, all_candidates,
            key=lambda p: p.name,
        )

    # ------------------------------------------------------------------
    # Public lookup API
    # ------------------------------------------------------------------

    def lookup_station(
        self,
        name: str | orm.Station | orm.System,
        system: str | orm.System | None = None,
    ) -> orm.Station:
        """ Exact-then-partial station lookup.

        Accepts a Station (pass-through), a System (returns its single station
        or raises SystemNotStationError), or a str name.  When *system* is
        supplied the search is scoped to that system; without it a dual-scan
        is performed (exact station first, then exact system) and the results
        are reconciled per the resolver contract.

        Partial matching is attempted when the exact query returns nothing.
        For scoped lookups all stations in the system are searched (bounded).
        For unscoped lookups a prefix ILIKE query narrows candidates before
        Python-side _list_search runs.
        """
        if isinstance(name, orm.Station):
            return name
        if isinstance(name, orm.System):
            stns = name.stations
            if len(stns) == 1:
                return stns[0]
            raise SystemNotStationError(
                f"System {name.name!r} has {len(stns)} stations; specify a station name"
            )
        if not isinstance(name, str):
            raise TypeError(f"lookup_station requires a str, got {type(name).__name__!r}")
        if "%" in name:
            raise TradeException("wildcards ('%') are not supported in station names")

        if "/" in name or "\\" in name:
            place = self.lookup_place(name)
            if isinstance(place, orm.Station):
                return place
            raise SystemNotStationError(
                f"Place {name!r} resolved to a system, not a station; specify a station name"
            )

        if system is not None:
            sys_obj = self.lookup_system(system)
            results = (
                self.session.query(orm.Station)
                .filter(orm.Station.system_id == sys_obj.system_id)
                .filter(orm.Station.name == name)
                .all()
            )
            if not results:
                # Partial matching: pull all stations in this system (bounded).
                all_stns = (
                    self.session.query(orm.Station)
                    .filter(orm.Station.system_id == sys_obj.system_id)
                    .all()
                )
                return self._list_search(
                    "Station", name, all_stns, key=lambda s: s.name
                )
            if len(results) == 1:
                return results[0]
            raise AmbiguityError("Station", name, results, key=lambda s: s.dbname())

        # Dual scan: exact station + exact system queries.
        stn_results = (
            self.session.query(orm.Station)
            .filter(orm.Station.name == name)
            .all()
        )
        sys_results = (
            self.session.query(orm.System)
            .filter(orm.System.name == name)
            .all()
        )

        if not stn_results and not sys_results:
            # Neither exact scan found anything — try partial via prefix ILIKE,
            # then interior ILIKE if prefix returns nothing (two-step superset).
            prefix = self._prefix_of(name)
            stn_cands = (
                self.session.query(orm.Station)
                .filter(orm.Station.name.ilike(f"{prefix}%"))
                .all()
            )
            if not stn_cands:
                stn_cands = (
                    self.session.query(orm.Station)
                    .filter(orm.Station.name.ilike(f"%{name}%"))
                    .all()
                )
            sys_cands = (
                self.session.query(orm.System)
                .filter(orm.System.name.ilike(f"{prefix}%"))
                .all()
            )
            if not sys_cands:
                sys_cands = (
                    self.session.query(orm.System)
                    .filter(orm.System.name.ilike(f"%{name}%"))
                    .all()
                )
            if stn_cands:
                try:
                    stn_results = [
                        self._list_search(
                            "Station", name, stn_cands, key=lambda s: s.name
                        )
                    ]
                except LookupError:
                    pass
                # AmbiguityError from _list_search propagates to caller.
            if sys_cands:
                try:
                    sys_results = [
                        self._list_search(
                            "System", name, sys_cands, key=lambda s: s.name
                        )
                    ]
                except LookupError:
                    pass

        if not stn_results and not sys_results:
            raise LookupError(f"'{name}' did not match any station or system.")

        if len(stn_results) > 1:
            raise AmbiguityError("Station", name, stn_results, key=lambda s: s.dbname())
        if len(sys_results) > 1:
            raise AmbiguityError("System", name, sys_results, key=lambda s: s.name)

        station = stn_results[0] if stn_results else None
        sys_obj = sys_results[0] if sys_results else None

        if station and sys_obj:
            if station.system_id == sys_obj.system_id:
                return station  # same system — station wins (Aulin-pattern)
            raise AmbiguityError(
                "Place", name,
                [station, sys_obj],
                key=lambda x: x.name,
            )

        if station:
            return station

        # Only system matched.
        stn_list = (
            self.session.query(orm.Station)
            .filter(orm.Station.system_id == sys_obj.system_id)
            .all()
        )
        if len(stn_list) == 1:
            return stn_list[0]
        raise SystemNotStationError(
            f"System {sys_obj.name!r} has {len(stn_list)} stations; specify a station name"
        )

    def lookup_system(self, name: str | orm.System | orm.Station) -> orm.System:
        """ Exact-then-partial system lookup with optional '@N' disambiguation.

        Falls back to prefix ILIKE + _list_search when the exact query returns
        nothing, mirroring the listSearch fallback in TradeDB.lookupSystem.
        @N disambiguation is only available in the exact tier (PRESERVE FOR
        PARITY — the listSearch fallback receives the full name including @N
        as a literal search string, per the DOCUMENTED LEGACY BUG).
        """
        if isinstance(name, orm.System):
            return name
        if isinstance(name, orm.Station):
            return name.system
        if not isinstance(name, str):
            raise TypeError(f"lookup_system requires a str, got {type(name).__name__!r}")

        if "%" in name:
            raise TradeException("wildcards ('%') are not supported in system names")

        base_name, index = self._split_system_index(name)

        results = (
            self.session.query(orm.System)
            .filter(orm.System.name == base_name)
            .order_by(orm.System.pos_x, orm.System.pos_y, orm.System.pos_z, orm.System.system_id)
            .all()
        )

        if not results:
            # Partial matching fallback — mirrors listSearch on systemByName/systemByID.
            # Full name (including any @N) is passed to _list_search; @N is treated as
            # a literal search string in the partial path (DOCUMENTED LEGACY BUG parity).
            prefix = self._prefix_of(name)
            candidates = (
                self.session.query(orm.System)
                .filter(orm.System.name.ilike(f"{prefix}%"))
                .all()
            )
            if not candidates:
                # Interior fallback: prefix ILIKE is not a superset for interior-suffix names.
                candidates = (
                    self.session.query(orm.System)
                    .filter(orm.System.name.ilike(f"%{name}%"))
                    .all()
                )
            if not candidates:
                raise LookupError(f"unknown system: {base_name!r}")
            return self._list_search(
                "System", name, candidates, key=lambda s: s.name
            )

        if index is not None:
            if 1 <= index <= len(results):
                return results[index - 1]
            raise TradeException(
                f"System {base_name!r}@{index} does not exist "
                f"(valid range: 1-{len(results)})"
            )

        if len(results) == 1:
            return results[0]

        pairs = list(enumerate(results, start=1))
        raise AmbiguityError(
            "System", base_name, pairs,
            key=lambda pair: (
                f"{pair[1].name.upper()}/@{pair[0]} "
                f"({pair[1].pos_x:.1f}, {pair[1].pos_y:.1f}, {pair[1].pos_z:.1f})"
            ),
        )

    def lookup_place(
        self,
        name: str | orm.System | orm.Station,
    ) -> orm.System | orm.Station:
        """ Resolve a place name to a System or Station, with partial matching.

        Accepts System/Station instances (pass-through) or a str in any of:
          bare name, @system, /station, system/station, @system/station.
        Backslash is treated as forward slash.

        Fast path (no slash after stripping @ annotation):
          Calls lookup_system() — inherits full @N semantics and partial
          system matching.  Falls through to exact-then-partial global station
          search on LookupError.  AmbiguityError / TradeException propagate
          immediately.  If a leading @ is present and the system is not found:
          LookupError (@ signals "this is a system", no station fallback).

        Slow path (slash present):
          System part: exact query first; if nothing, prefix ILIKE + _place_lookup.
          Station part: if system candidates exist, all their stations are
          searched via _place_lookup (handles interior substrings such as
          "braham" → "Abraham Lincoln").  If no system context, prefix ILIKE +
          _place_lookup globally.
          @N is suppressed in compound syntax (PRESERVE FOR PARITY).
        """
        if isinstance(name, (orm.System, orm.Station)):
            return name
        if not isinstance(name, str):
            raise TypeError(f"lookup_place requires a str, got {type(name).__name__!r}")
        if "%" in name:
            raise TradeException("wildcards ('%') are not supported in names")

        # Normalise backslash to forward slash.
        norm = name.replace("\\", "/")
        at_prefix = norm.startswith("@")
        slash_pos = norm.find("/")

        if slash_pos == -1:
            # Fast path: bare name or @name, no slash.
            bare = norm[1:] if at_prefix else norm
            try:
                return self.lookup_system(bare)
            except LookupError:
                pass
            # AmbiguityError / TradeException propagate above.
            if at_prefix:
                # @ marks explicit system intent — no station fallback.
                raise LookupError(f"Unrecognized place: {name!r}")
            # Exact station query first.
            stn_results = (
                self.session.query(orm.Station)
                .filter(orm.Station.name == norm)
                .all()
            )
            if not stn_results:
                # Partial station fallback: prefix ILIKE then interior ILIKE.
                prefix = self._prefix_of(norm)
                stn_cands = (
                    self.session.query(orm.Station)
                    .filter(orm.Station.name.ilike(f"{prefix}%"))
                    .all()
                )
                if not stn_cands:
                    stn_cands = (
                        self.session.query(orm.Station)
                        .filter(orm.Station.name.ilike(f"%{norm}%"))
                        .all()
                    )
                if not stn_cands:
                    raise LookupError(f"Unrecognized place: {name!r}")
                return self._list_search(
                    "Station", norm, stn_cands, key=lambda s: s.name
                )
            if len(stn_results) == 1:
                return stn_results[0]
            raise AmbiguityError("Place", norm, stn_results, key=lambda s: s.name)

        # Slow path: compound form with slash.
        # Strip leading @ annotation (not @N — that is suppressed here).
        name_off = 1 if at_prefix else 0
        sys_part = norm[name_off:slash_pos]   # empty string for leading /
        stn_part = norm[slash_pos + 1:]

        # Raw exact system query — do NOT use lookup_system() here.
        # This keeps @N disambiguation out of compound syntax (parity).
        if sys_part:
            sys_results = (
                self.session.query(orm.System)
                .filter(orm.System.name == sys_part)
                .all()
            )
            if not sys_results:
                # Partial system matching — prefix ILIKE then interior ILIKE,
                # then _place_lookup to tier the candidates.
                prefix = self._prefix_of(sys_part)
                sys_cands = (
                    self.session.query(orm.System)
                    .filter(orm.System.name.ilike(f"{prefix}%"))
                    .all()
                )
                if not sys_cands:
                    sys_cands = (
                        self.session.query(orm.System)
                        .filter(orm.System.name.ilike(f"%{sys_part}%"))
                        .all()
                    )
                if sys_cands:
                    exact_m, close_m, word_m, any_m = self._place_lookup(
                        sys_part, sys_cands
                    )
                    sys_results = exact_m + close_m + word_m + any_m
                # If still empty, sys_results = [] → station search is global.
        else:
            sys_results = []

        if not stn_part:
            # "system/" with no station — return system if unambiguous.
            if not sys_results:
                raise LookupError(f"Unrecognized place: {name!r}")
            if len(sys_results) == 1:
                return sys_results[0]
            raise AmbiguityError(
                "System", sys_part, sys_results, key=lambda s: s.name
            )

        # Station candidates: scoped to matched systems, or global if none.
        if sys_results:
            system_ids = [s.system_id for s in sys_results]
            stn_base = (
                self.session.query(orm.Station)
                .filter(orm.Station.system_id.in_(system_ids))
            )
            # Try exact first.
            stn_exact = stn_base.filter(orm.Station.name == stn_part).all()
            if stn_exact:
                results = stn_exact
            else:
                # Pull all stations in matched systems for partial matching.
                # This bounded set handles interior substrings (e.g. "braham").
                all_stns = stn_base.all()
                exact_m, close_m, word_m, any_m = self._place_lookup(
                    stn_part, all_stns
                )
                return self._resolve_place_tiers(name, exact_m, close_m, word_m, any_m)
        else:
            # Global station search (no system context).
            results = (
                self.session.query(orm.Station)
                .filter(orm.Station.name == stn_part)
                .all()
            )
            if not results:
                # Partial global search: prefix ILIKE then interior ILIKE.
                prefix = self._prefix_of(stn_part)
                stn_cands = (
                    self.session.query(orm.Station)
                    .filter(orm.Station.name.ilike(f"{prefix}%"))
                    .all()
                )
                if not stn_cands:
                    stn_cands = (
                        self.session.query(orm.Station)
                        .filter(orm.Station.name.ilike(f"%{stn_part}%"))
                        .all()
                    )
                if not stn_cands:
                    raise LookupError(f"Unrecognized place: {name!r}")
                exact_m, close_m, word_m, any_m = self._place_lookup(
                    stn_part, stn_cands
                )
                return self._resolve_place_tiers(name, exact_m, close_m, word_m, any_m)

        if not results:
            raise LookupError(f"Unrecognized place: {name!r}")
        if len(results) == 1:
            return results[0]
        raise AmbiguityError("Place", stn_part, results, key=lambda s: s.name)

    def lookup_item(self, name: str | orm.Item) -> orm.Item:
        """Exact-then-normalised item lookup by name.

        Mirrors TradeDB.lookupItem / listSearch. Exact CI match is tried first
        (fast path). Partial/normalised fallback scans the full item catalogue
        in Python via _list_search, which applies the same two-stage
        normalisation as the legacy path. A full scan is used rather than ILIKE
        narrowing because raw SQL cannot replicate stage-1 punctuation deletion,
        so ILIKE is not a superset of normalised matches (e.g. "HESuits" must
        reach "H.E. Suits"). The item catalogue is small enough (~300 rows) that
        a full scan is acceptable.
        """
        if isinstance(name, orm.Item):
            return name
        if not isinstance(name, str):
            raise TypeError(f"lookup_item requires a str, got {type(name).__name__!r}")
        if "%" in name:
            raise TradeException("wildcards ('%') are not supported in item names")

        # Exact CI match — fast path.
        results = (
            self.session.query(orm.Item)
            .filter(orm.Item.name == name)
            .all()
        )
        if results:
            if len(results) == 1:
                return results[0]
            raise AmbiguityError("Item", name, results, key=lambda i: i.name)

        # Full catalogue scan with Python-side normalised matching.
        all_items = self.session.query(orm.Item).all()
        if not all_items:
            raise LookupError(f"unknown item: {name!r}")
        return self._list_search("Item", name, all_items, key=lambda i: i.name)

    def lookup_category(self, name: str | orm.Category) -> orm.Category:
        """Exact-then-normalised category lookup by name.

        Mirrors TradeDB.lookupCategory / listSearch. Exact CI match is tried
        first (fast path, uses idx_category_by_name). Normalised fallback
        scans all categories in Python via _list_search. The category
        catalogue is tiny (~16 rows) so a full scan is acceptable.
        """
        if isinstance(name, orm.Category):
            return name
        if not isinstance(name, str):
            raise TypeError(f"lookup_category requires a str, got {type(name).__name__!r}")

        # Exact CI match — fast path.
        results = (
            self.session.query(orm.Category)
            .filter(orm.Category.name == name)
            .all()
        )
        if results:
            if len(results) == 1:
                return results[0]
            raise AmbiguityError("Category", name, results, key=lambda c: c.name)

        # Full catalogue scan with Python-side normalised matching.
        all_cats = self.session.query(orm.Category).all()
        if not all_cats:
            raise LookupError(f"unknown category: {name!r}")
        return self._list_search("Category", name, all_cats, key=lambda c: c.name)

    def lookup_ship(self, name: str | orm.Ship) -> orm.Ship:
        """Exact-then-normalised ship lookup by name.

        Mirrors TradeDB.lookupShip. Exact CI match is tried first (fast path).
        Normalised fallback scans the full ship catalogue via _list_search.
        The ship catalogue is small (~40 rows) so a full scan is acceptable.
        """
        if isinstance(name, orm.Ship):
            return name
        if not isinstance(name, str):
            raise TypeError(f"lookup_ship requires a str, got {type(name).__name__!r}")

        # Exact CI match — fast path.
        results = (
            self.session.query(orm.Ship)
            .filter(orm.Ship.name == name)
            .all()
        )
        if results:
            if len(results) == 1:
                return results[0]
            raise AmbiguityError("Ship", name, results, key=lambda s: s.name)

        # Full catalogue scan with Python-side normalised matching.
        all_ships = self.session.query(orm.Ship).all()
        if not all_ships:
            raise LookupError(f"unknown ship: {name!r}")
        return self._list_search("Ship", name, all_ships, key=lambda s: s.name)

    def item_by_id(self, item_id: int) -> orm.Item:
        """Look up an Item by its primary key.

        Mirrors TradeDB.itemByID[ID]. Uses the SQLAlchemy identity map when
        the item is already loaded in the session; otherwise issues a PK
        query. Raises LookupError if the item_id does not exist.
        """
        item = self.session.get(orm.Item, item_id)
        if item is None:
            raise LookupError(f"unknown item id: {item_id!r}")
        return item

    @staticmethod
    def _split_system_index(name: str) -> tuple[str, int | None]:
        """ Split 'Name@N' into ('Name', N); returns (name, None) if no valid suffix. """
        at = name.rfind('@')
        if at <= 0:
            return name, None
        tail = name[at + 1:]
        if not tail.isdigit():
            return name, None
        return name[:at], int(tail)
