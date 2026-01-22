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
    search as db_search,
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
        if (fast_candidate := db_search.fast_find_sub(self.session, "Station", name, orm.Station, orm.System)):
            if isinstance(fast_candidate, orm.Station):
                return fast_candidate
            if isinstance(fast_candidate, orm.System) and fast_candidate.name.lower() == name.lower():
                raise TradeException(
                    f"expected a station, '{name}' is a system."
                    f" you can use '/{name}' to ignore the system match."
                )

        fuzzy_candidate = db_search.fuzzy_like(self.session, "Station", name, table=orm.Station, group_table=orm.System)
        if isinstance(fuzzy_candidate, orm.Station):
            return fuzzy_candidate

        return None
    
    def lookup_system(self, name: str) -> orm.System | None:
        """ Use the database to lookup a system, which accepts a name that
            is either a unique system name (or partial of one), or in the
            'system name/station name' component. If the system does not
            match a unique system, raises an AmbiguityError
        """
        if (system := db_search.fast_find(self.session, "System", name, table=orm.System)):
            return system
        return db_search.fuzzy_like(self.session, "System", name, table=orm.System, group_table=None)
    
    def lookup_place(self, name: str) -> orm.Station | orm.System | None:
        """ Using a "[<system>]/[<station>]" style name, look up either a Station or a System."""
        if (candidate := db_search.fast_find_sub(self.session, "Place", name, orm.Station, orm.System)):
            return candidate

        return db_search.fuzzy_like(self.session, "Place", name, orm.Station, orm.System)
