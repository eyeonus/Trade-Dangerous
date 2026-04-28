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


class TradeORM:
    DEFAULT_PATH = "data"
    DEFAULT_DB = "TradeDangerous.db"
    DB_CONFIG_VAR = "TD_DB_CONFIG"
    DB_CONFIG_FILE = "db_config.ini"
    
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
    
    def lookup_station(
        self,
        name: str | orm.Station | orm.System,
        system: str | orm.System | None = None,
    ) -> orm.Station:
        """ Exact station lookup.

        Accepts a Station (pass-through), a System (returns its single station
        or raises SystemNotStationError), or a str name.  When *system* is
        supplied the search is scoped to that system; without it a dual-scan
        is performed (exact station first, then exact system) and the results
        are reconciled per the resolver contract.
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

        if system is not None:
            sys_obj = self.lookup_system(system)
            results = (
                self.session.query(orm.Station)
                .filter(orm.Station.system_id == sys_obj.system_id)
                .filter(orm.Station.name == name)
                .all()
            )
            if not results:
                raise LookupError(f"station {name!r} not found in {sys_obj.name!r}")
            if len(results) == 1:
                return results[0]
            raise AmbiguityError("Station", name, results, key=lambda s: s.dbname())

        # Dual scan: exact station + exact system queries
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
                key=lambda x: x.dbname(),
            )

        if station:
            return station

        # Only system matched
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
        """ Look up a system by name, with optional '@N' disambiguation index. """
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
            raise LookupError(f"unknown system: {base_name!r}")

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
        """ Resolve a place name to a System or Station.

        Accepts System/Station instances (pass-through) or a str in any of:
          bare name, @system, /station, system/station, @system/station.
        Backslash is treated as forward slash.

        Fast path (no slash after stripping @ annotation):
          Calls lookup_system() — inherits full @N semantics.
          Falls through to global exact station search on LookupError.
          AmbiguityError / TradeException propagate immediately.
          If a leading @ is present and the system is not found: LookupError
          (@ signals "this is a system", no station fallback).

        Slow path (slash present):
          System part resolved via a raw exact case-insensitive query
          (NOT via lookup_system — @N must not work in compound syntax).
          If system matches exist, station candidates are scoped to those
          systems; if not, station search is global (unknown-system fallback).
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
                # @ marks an explicit system intent — no station fallback.
                raise LookupError(f"Unrecognized place: {name!r}")
            stn_results = (
                self.session.query(orm.Station)
                .filter(orm.Station.name == norm)
                .all()
            )
            if not stn_results:
                raise LookupError(f"Unrecognized place: {name!r}")
            if len(stn_results) == 1:
                return stn_results[0]
            raise AmbiguityError("Place", norm, stn_results, key=lambda s: s.dbname())

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
        stn_query = self.session.query(orm.Station)
        if sys_results:
            system_ids = [s.system_id for s in sys_results]
            stn_query = stn_query.filter(orm.Station.system_id.in_(system_ids))

        results = stn_query.filter(orm.Station.name == stn_part).all()
        if not results:
            raise LookupError(f"Unrecognized place: {name!r}")
        if len(results) == 1:
            return results[0]
        raise AmbiguityError("Place", stn_part, results, key=lambda s: s.dbname())
    
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

