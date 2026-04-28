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
    
    def lookup_station(self, name: str) -> orm.Station | None:
        """ Use the database to lookup a station, which accepts a name that
            is either a unique station name (or partial of one), or in the
            'system name/station name' component. If the station does not
            match a unique station, raises an AmbiguityError
        """
        if "%" in name:
            raise TradeException("wildcards ('%') are not supported in station names")
        if "/" not in name:
            if (station := self._station_lookup(name, exact=True, partial=False)):
                return station
            if self._system_lookup(name, exact=True, partial=False):
                raise SystemNotStationError(f'"{name}" is a system name, use "/{name}" if you meant it as a station')
            name = "/" + name
        station: orm.Station | None = self.lookup_place(name)
        return station
    
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
    
    def lookup_place(self, name: str) -> orm.Station | orm.System | None:
        """ Using a "[<system>]/[<station>]" style name, look up either a Station or a System."""
        if "%" in name:
            raise TradeException("wildcards ('%') are not supported in names")
        sys_name, slashed, stn_name = name.partition("/")
        if not slashed:
            if stn_name:
                station: orm.Station | None = self._station_lookup(stn_name, exact=True, partial=False)
                if station:
                    return station
            if sys_name:
                system: orm.System | None = self._system_lookup(sys_name, exact=True, partial=False)
                if system:
                    return system
        
        if sys_name:
            system = self._system_lookup(sys_name)
            if not system:
                raise TradeException(f"unknown system: {sys_name}")
            if not stn_name:
                return system
            
            # Now we match the list of station names for this system.
            stmt = self.session.query(orm.Station).filter(orm.Station.system_id == system.system_id).filter(orm.Station.name == stn_name)
            results = stmt.all()
            if len(results) == 1:
                return results[0]

            stmt = self.session.query(orm.Station).filter(orm.Station.system_id == system.system_id).filter(orm.Station.name.like(f"%{stn_name}%"))
            results = stmt.all()
            if not results:
                raise TradeException(f"no station in {sys_name} matches '{stn_name}'")
            if len(results) > 1:
                raise AmbiguityError("Station", stn_name, [s.name for s in results])
            return results[0]
        
        station = self._station_lookup(stn_name, exact=False)
        return station
    
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

    def _system_lookup(self, name: str, *, exact: bool = True, partial: bool = True) -> orm.System | None:
        """ Look up a model by exact name match. """
        assert exact or partial, "at least one of exact or partial must be True"
        results: list[orm.System] | None = None
        if exact:
            results = self.session.query(orm.System).filter(orm.System.name == name).all()
            if len(results) == 1:
                partial = False
        if partial:
            like_pattern = f"%{name}%"
            results = self.session.query(orm.System).filter(orm.System.name.like(like_pattern)).all()
        
        if not results:
            return None
        if len(results) > 1:
            raise AmbiguityError("System", name, results, key=lambda s: s.dbname())
        return results[0]
    
    def _station_lookup(self, name: str, *, exact: bool = True, partial: bool = True) -> orm.Station | None:
        """ Look up a model by exact name match. """
        assert exact or partial, "at least one of exact or partial must be True"
        results: list[orm.Station] | None = None
        if exact:
            results = self.session.query(orm.Station).filter(orm.Station.name == name).all()
            if len(results) == 1:
                partial = False
        if partial:
            like_pattern = f"%{name}%"
            results = self.session.query(orm.Station).filter(orm.Station.name.like(like_pattern)).all()
        if not results:
            return None
        if len(results) > 1:
            raise AmbiguityError("Station", name, results, key=lambda s: s.dbname())
        return results[0]
