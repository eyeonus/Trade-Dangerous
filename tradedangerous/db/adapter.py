# tradedangerous/db/adapter.py
from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Generator, Iterable, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# Local engine + ORM (authoritative)
from .engine import make_engine_from_config, get_session_factory  # uses env/CWD-resolved db_config.ini by default
from .orm_models import System, Station, Item, StationItem  # canonical models
from .paths import resolve_db_config_path

# ---- Public factory ---------------------------------------------------------

def get_adapter_if_enabled(cfg_path: Optional[str] = None) -> "TradeDBReadAdapter | None":
    """
    Return an adapter when [database] backend != 'sqlite', else None.
    - No engine/session created at import: construction is lazy.
    - This is called by tradedb.py (thin gate).
    """
    import configparser, os
    if cfg_path is None:
        cfg_path = str(resolve_db_config_path())
    cfg = configparser.ConfigParser()
    if not os.path.exists(cfg_path):
        return None
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg.read_file(fh)
    backend = (cfg.get("database", "backend", fallback="sqlite") or "sqlite").strip().lower()
    if backend == "sqlite":
        return None
    
    # Engine is created lazily via the property below to honour "no side-effects at import".
    return TradeDBReadAdapter(cfg_path)

# ---- Adapter (read-only) ----------------------------------------------------

class TradeDBReadAdapter:
    """
    Very small, read-only façade over SQLAlchemy for legacy TradeDB reads:
      - systems() list
      - lookup system by name (case-insensitive)
      - station by (system_id, station_name) (case-insensitive)
      - average selling/buying prices (used by trade_cmd at detail>1)
    """
    def __init__(self, cfg_path: str):
        self._cfg_path = cfg_path
        self._engine: Optional[Engine] = None
        self._Session = None  # sessionmaker
    
    # Lazy engine/session factory (no import-time work)
    @property
    def Session(self):
        if self._Session is None:
            engine = make_engine_from_config(self._cfg_path)
            self._engine = engine
            self._Session = get_session_factory(engine)
        return self._Session
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        Session = self.Session
        with Session() as s:
            yield s
    
    # ---- Reads mapped to ORM ------------------------------------------------
    
    def list_system_rows(self) -> Iterable[Tuple[int, str, float, float, float, Optional[int]]]:
        """
        Shape matches legacy _loadSystems SELECT:
        (system_id, name, pos_x, pos_y, pos_z, added_id)
        """
        with self.session() as s:
            rows = s.execute(
                select(
                    System.system_id,
                    System.name,
                    System.pos_x,
                    System.pos_y,
                    System.pos_z,
                    System.added_id,
                )
            )
            for r in rows:
                yield (r.system_id, r.name, r.pos_x, r.pos_y, r.pos_z, r.added_id)
    
    def system_by_name(self, name_ci: str) -> Optional[Tuple[int, str, float, float, float, Optional[int]]]:
        """
        Case-insensitive name match for System.
        """
        with self.session() as s:
            row = s.execute(
                select(
                    System.system_id, System.name, System.pos_x, System.pos_y, System.pos_z, System.added_id
                ).where(func.upper(System.name) == func.upper(func.trim(func.cast(name_ci, System.name.type))))
            ).first()
            if not row:
                return None
            return (row.system_id, row.name, row.pos_x, row.pos_y, row.pos_z, row.added_id)
    
    def station_by_system_and_name(
        self, system_id: int, station_name_ci: str
    ) -> Optional[Tuple[int, int, str, int, str, str, str, str, str, str, str, str, str, int]]:
        """
        Return the single Station row by system + name (CI).
        Shape matches legacy _loadStations row consumed by Station(...):
          (station_id, system_id, name,
           ls_from_star, market, blackmarket, shipyard,
           max_pad_size, outfitting, rearm, refuel, repair, planetary, type_id)
        """
        with self.session() as s:
            r = s.execute(
                select(
                    Station.station_id,
                    Station.system_id,
                    Station.name,
                    Station.ls_from_star,
                    Station.market,
                    Station.blackmarket,
                    Station.shipyard,
                    Station.max_pad_size,
                    Station.outfitting,
                    Station.rearm,
                    Station.refuel,
                    Station.repair,
                    Station.planetary,
                    Station.type_id,
                ).where(
                    Station.system_id == system_id,
                    func.upper(Station.name) == func.upper(func.trim(func.cast(station_name_ci, Station.name.type))),
                )
            ).first()
            if not r:
                return None
            return (
                r.station_id,
                r.system_id,
                r.name,
                r.ls_from_star,
                r.market,
                r.blackmarket,
                r.shipyard,
                r.max_pad_size,
                r.outfitting,
                r.rearm,
                r.refuel,
                r.repair,
                r.planetary,
                r.type_id,
            )
    
    def average_selling(self) -> Dict[int, int]:
        """
        {item_id: avg_supply_price>0}
        Mirrors the legacy SQL used in TradeDB.getAverageSelling.
        """
        with self.session() as s:
            rows = s.execute(
                select(
                    Item.item_id,
                    func.IFNULL(func.avg(StationItem.supply_price), 0),
                )
                .select_from(Item.__table__.outerjoin(
                    StationItem, (Item.item_id == StationItem.item_id) & (StationItem.supply_price > 0)
                ))
                .where(StationItem.supply_price > 0)
                .group_by(Item.item_id)
            )
            return {int(item_id): int(avg_cr) for (item_id, avg_cr) in rows}
    
    def average_buying(self) -> Dict[int, int]:
        """
        {item_id: avg_demand_price>0}
        Mirrors the legacy SQL used in TradeDB.getAverageBuying.
        """
        with self.session() as s:
            rows = s.execute(
                select(
                    Item.item_id,
                    func.IFNULL(func.avg(StationItem.demand_price), 0),
                )
                .select_from(Item.__table__.outerjoin(
                    StationItem, (Item.item_id == StationItem.item_id) & (StationItem.demand_price > 0)
                ))
                .where(StationItem.demand_price > 0)
                .group_by(Item.item_id)
            )
            return {int(item_id): int(avg_cr) for (item_id, avg_cr) in rows}
