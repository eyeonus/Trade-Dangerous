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

        # Determine where the database should be
        data_dir = tdenv.dataDir or TradeORM.DEFAULT_PATH
        self.data_dir = Path(data_dir)
        tdenv.DEBUG0("data_dir = {}", self.data_dir)

        # Determine the path to the file itself
        db_path = tdenv.dbFilename or (self.data_dir / TradeORM.DEFAULT_DB)
        self.db_path  = Path(db_path)
        tdenv.DEBUG0("db_path = {}", self.db_path)

        # We need it to exist.
        if not self.db_path.exists():
            raise MissingDB(self.db_path)

        default_config = self.data_dir / TradeORM.DB_CONFIG_FILE
        db_config = os.environ.get(TradeORM.DB_CONFIG_VAR, default_config)
        tdenv.DEBUG0("db_config = {}", db_config)

        # Make the database available.
        self.engine = make_engine_from_config(db_config)

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

    def lookup_system(self, name: str) -> orm.System | None:
        """ Use the database to lookup a system, which accepts a name that
            is either a unique system name (or partial of one), or in the
            'system name/station name' component. If the system does not
            match a unique system, raises an AmbiguityError
        """
        if "%" in name:
            raise TradeException("wildcards ('%') are not supported in system names")
        system_name, _, _ = name.partition("/")
        if not system_name:
            raise TradeException(f"system name required for system lookup, got {name}")
        result: orm.Station | orm.System | None = self.lookup_place(system_name)
        if isinstance(result, orm.Station):
            return result.system
        return result

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
            if len(results) > 1:
                raise AmbiguityError("Station", stn_name, [s.name for s in results])
            return results[0]

        station = self._station_lookup(stn_name, exact=False)
        return station

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
