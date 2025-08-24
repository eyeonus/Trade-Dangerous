# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018-2025
# Copyright (C) Stefan 'Tromador' Morrell 2025
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------

"""
Trade:Dangerous — TradeDB (SQLAlchemy ORM)

Provides the TradeDB API and core types:
System, Station, Ship, Item, RareItem, Category.

Quick usage:
    from tradedangerous.tradedb import TradeDB

    tdb = TradeDB()
    sol = tdb.lookupSystem("SOL")
    abe = tdb.lookupStation("Abraham Lincoln")            # case-insensitive, unique substring
    abe_in_sol = tdb.lookupStation("Abraham Lincoln", sol)

    avg_sell = tdb.getAverageSelling()
    avg_buy  = tdb.getAverageBuying()

Notes:
- All database access uses SQLAlchemy ORM sessions (no raw SQL).
- SQLite schema is created elsewhere from templates/TradeDangerous.sql; this module does no DDL.
- MariaDB schema is managed via Alembic/ORM; runtime behaviour is backend-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Iterable, Tuple
from contextlib import contextmanager
from math import sqrt as _sqrt

from .tradeenv import TradeEnv          # type: ignore
from .tradeexcept import TradeException # type: ignore
from . import fs                        # type: ignore

from tradedangerous.db import resolve_db_config_path, make_engine_from_config, get_session_factory
from tradedangerous.db.orm_models import (
    Base,
    Added as SA_Added,
    System as SA_System,
    Station as SA_Station,
    Category as SA_Category,
    Item as SA_Item,
    StationItem as SA_StationItem,
    Ship as SA_Ship,
    RareItem as SA_RareItem,
)
from sqlalchemy import select, func
from sqlalchemy.orm import Session as SASession

@dataclass
class System:
    ID: int
    dbname: str
    posX: float
    posY: float
    posZ: float
    addedID: int = 0
    @property
    def system(self) -> "System":
        return self
    def distanceTo(self, other: "System") -> float:
        dx = self.posX - other.posX
        dy = self.posY - other.posY
        dz = self.posZ - other.posZ
        return _sqrt(dx*dx + dy*dy + dz*dz)

@dataclass
class Station:
    ID: int
    system: System
    dbname: str
    lsFromStar: int
    market: str
    blackMarket: str
    shipyard: str
    maxPadSize: str
    outfitting: str
    rearm: str
    refuel: str
    repair: str
    planetary: str
    fleet: str
    odyssey: str
    itemCount: int = 0
    dataAge: Optional[float] = None
    def fullName(self) -> str:
        return f"{self.system.dbname}/{self.dbname}"

@dataclass
class Ship:
    ID: int
    dbname: str
    cost: Optional[int] = None
    stations: Optional[List[Station]] = None
    def name(self, detail: int = 0) -> str:
        return self.dbname

@dataclass
class Category:
    ID: int
    dbname: str
    items: List["Item"]

@dataclass
class Item:
    ID: int
    dbname: str
    category: Category
    fullname: str
    avgprice: Optional[int] = None
    fdev_id: Optional[int] = None

@dataclass
class RareItem:
    ID: int
    station: Station
    dbname: str
    cost: Optional[int]
    maxAllocation: Optional[int]
    illegal: str
    suppressed: str
    category: Category
    fullname: str

class TradeDB:
    defaultDB = 'TradeDangerous.db'
    defaultSQL = 'TradeDangerous.sql'
    defaultPrices = 'TradeDangerous.prices'
    def __init__(self, tdenv: Optional[TradeEnv] = None, load: bool = True, debug: Optional[int] = None):
        self.tdenv = tdenv or TradeEnv(debug=debug)
        self.templatePath = self.tdenv.templateDir
        self.dataPath = fs.ensurefolder(self.tdenv.dataDir)
        self.csvPath = fs.ensurefolder(self.tdenv.csvDir)
        cfg_path = resolve_db_config_path()
        # Resolve DB config and build SQLAlchemy Engine/Session.
        self._engine = make_engine_from_config(cfg_path)
        self._Session = get_session_factory(self._engine)
        # Session factory; sessions are short‑lived per method call.
        self.addedByID: Dict[int, str] = {}
        self.systemByID: Dict[int, System] = {}
        self.systemByName: Dict[str, System] = {}
        self.stationByID: Dict[int, Station] = {}
        self.shipByID: Dict[int, Ship] = {}
        self.categoryByID: Dict[int, Category] = {}
        self.itemByID: Dict[int, Item] = {}
        self.itemByName: Dict[str, Item] = {}
        self.itemByFDevID: Dict[int, Item] = {}
        self.rareItemByID: Dict[int, RareItem] = {}
        self.rareItemByName: Dict[str, RareItem] = {}
        self.avgSelling: Optional[Dict[int, int]] = None
        self.avgBuying: Optional[Dict[int, int]] = None
        self.tradingStationCount: int = 0
        self.stellarGrid = None
        if load:
            self.reloadCache()
    # Context-managed Session scope (no global connections).
    @contextmanager
    def _session(self) -> Iterable[SASession]:
        s = self._Session()
        try:
            yield s
        finally:
            s.close()
    def close(self) -> None:
        return None
    # Reload in-memory caches from the database.
    # CAUTION: Will orphan previously loaded objects. Order matters.
    def reloadCache(self) -> None:
        self._loadAdded()
        self._loadSystems()
        self._loadStations()
        self._loadCategories()
        self._loadItems()
        self._loadShips()
        self._loadRareItems()
    def _loadAdded(self) -> None:
        m: Dict[int, str] = {}
        with self._session() as s:
            for aid, name in s.execute(select(SA_Added.added_id, SA_Added.name)):
            # ORM select of Added -> in‑memory id→name map.
                m[int(aid)] = name
        self.addedByID = m
    # Initial load of systems.
    # CAUTION: Will orphan previously loaded objects.
    def _loadSystems(self) -> None:
        by_id: Dict[int, System] = {}
        by_name: Dict[str, System] = {}
        with self._session() as s:
            rows = s.execute(select(
            # ORM select of System rows; build id and uppercase‑name maps.
                SA_System.system_id, SA_System.name,
                SA_System.pos_x, SA_System.pos_y, SA_System.pos_z,
                SA_System.added_id
            ))
            for sid, name, x, y, z, added_id in rows:
                sys = System(int(sid), str(name).upper(), float(x), float(y), float(z), int(added_id or 0))
                by_id[sys.ID] = sys
                by_name[sys.dbname] = sys
        self.systemByID, self.systemByName = by_id, by_name
    # Populate the Station list.
    # CAUTION: Will orphan previously loaded objects.
        # Fleet Carriers are station type 24.
        # Odyssey settlements are station type 25.
        # Assume type 0 (Unknown) are also Fleet Carriers.
    def _loadStations(self) -> None:
        self.stationByID = {}
        self.tradingStationCount = 0
        types = {'fleet-carrier': [24, 0], 'odyssey': [25]}
        with self._session() as s:
            rows = s.execute(select(
            # ORM select of Station rows; derive flags and create Station objects.
                SA_Station.station_id, SA_Station.system_id, SA_Station.name,
                SA_Station.ls_from_star, SA_Station.market, SA_Station.blackmarket,
                SA_Station.shipyard, SA_Station.max_pad_size, SA_Station.outfitting,
                SA_Station.rearm, SA_Station.refuel, SA_Station.repair,
                SA_Station.planetary, SA_Station.type_id
            ))
            for (stn_id, sys_id, name, ls, mkt, bm, shipyard, pad, outf, rearm, refuel, repair, planetary, type_id) in rows:
                sys = self.systemByID[int(sys_id)]
                isFleet = 'Y' if int(type_id) in types['fleet-carrier'] else 'N'
                isOdyssey = 'Y' if int(type_id) in types['odyssey'] else 'N'
                st = Station(
                    ID=int(stn_id), system=sys, dbname=str(name),
                    lsFromStar=int(ls or 0), market=str(mkt), blackMarket=str(bm),
                    shipyard=str(shipyard), maxPadSize=str(pad), outfitting=str(outf),
                    rearm=str(rearm), refuel=str(refuel), repair=str(repair),
                    planetary=str(planetary), fleet=isFleet, odyssey=isOdyssey,
                    itemCount=0, dataAge=None,
                )
                self.stationByID[st.ID] = st
            for stn_id, count in s.execute(
                select(SA_StationItem.station_id, func.count())
                .group_by(SA_StationItem.station_id)
                # Aggregate StationItem counts per station (trading stations).
                .having(func.count() > 0)
            ):
                st = self.stationByID.get(int(stn_id))
                if st:
                    st.itemCount = int(count)
                    self.tradingStationCount += 1
    # Populate the list of item categories.
    # CAUTION: Will orphan previously loaded objects.
    def _loadCategories(self) -> None:
        with self._session() as s:
            self.categoryByID = {
                int(cid): Category(int(cid), str(name), [])
                for cid, name in s.execute(select(SA_Category.category_id, SA_Category.name))
                # Load categories; items attached in _loadItems.
            }
    # Populate the Item list.
    # CAUTION: Will orphan previously loaded objects.
    def _loadItems(self) -> None:
        by_id: Dict[int, Item] = {}
        by_name: Dict[str, Item] = {}
        by_fdev: Dict[int, Item] = {}
        with self._session() as s:
            rows = s.execute(select(
            # Load items and wire to categories; build name/fdev maps.
                SA_Item.item_id, SA_Item.name, SA_Item.category_id, SA_Item.avg_price, SA_Item.fdev_id
            ))
            for iid, name, cat_id, avg_p, fdev in rows:
                cat = self.categoryByID[int(cat_id)]
                it = Item(int(iid), str(name), cat, f"{cat.dbname}/{name}", int(avg_p) if avg_p is not None else None, int(fdev) if fdev is not None else None)
                by_id[it.ID] = it
                by_name[it.dbname] = it
                if it.fdev_id is not None:
                    by_fdev[it.fdev_id] = it
                cat.items.append(it)
        self.itemByID, self.itemByName, self.itemByFDevID = by_id, by_name, by_fdev
    # Populate the Ship list.
    # CAUTION: Will orphan previously loaded objects.
    def _loadShips(self) -> None:
        with self._session() as s:
            self.shipByID = {
                int(sid): Ship(int(sid), str(name), int(cost) if cost is not None else None, stations=[])
                for sid, name, cost in s.execute(select(SA_Ship.ship_id, SA_Ship.name, SA_Ship.cost))
                # Load ships (stations list filled elsewhere if needed).
            }
    # Populate the RareItem list.
    def _loadRareItems(self) -> None:
        by_id: Dict[int, RareItem] = {}
        by_name: Dict[str, RareItem] = {}
        with self._session() as s:
            rows = s.execute(select(
            # Load rare items and map by id/name.
                SA_RareItem.rare_id, SA_RareItem.station_id, SA_RareItem.category_id, SA_RareItem.name,
                SA_RareItem.cost, SA_RareItem.max_allocation, SA_RareItem.illegal, SA_RareItem.suppressed
            ))
            for rid, stn_id, cat_id, name, cost, max_alloc, illegal, suppressed in rows:
                st = self.stationByID[int(stn_id)]
                cat = self.categoryByID[int(cat_id)]
                r = RareItem(int(rid), st, str(name), int(cost) if cost is not None else None,
                             int(max_alloc) if max_alloc is not None else None, str(illegal), str(suppressed),
                             cat, f"{cat.dbname}/{name}")
                by_id[r.ID] = r
                by_name[r.dbname] = r
        self.rareItemByID, self.rareItemByName = by_id, by_name
    def systems(self) -> Iterable[System]:
        return self.systemByID.values()
    def items(self) -> Iterable[Item]:
        return self.itemByID.values()
    # Exact match by uppercased name; otherwise unique substring match.
    # System lookup: exact match on uppercased name; else unique substring.
    def lookupSystem(self, name: str) -> System:
        key = self.normalizedStr(name)
        if key in self.systemByName:
            return self.systemByName[key]
        hits = [s for s in self.systemByID.values() if key in s.dbname]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise TradeException(f"System not found: {name}")
        raise TradeException(f"Ambiguous system: {name} -> {', '.join(h.dbname for h in hits[:5])}")
    # Restrict to a system when provided; otherwise unique substring across all stations.
    # Station lookup: restrict to given system when provided; else unique substring.
    def lookupStation(self, name: str, system: Optional[System] = None) -> Station:
        key = self.normalizedStr(name)
        if system:
            hits = [st for st in self.stationByID.values() if st.system.ID == system.ID and key in self.normalizedStr(st.dbname)]
        else:
            hits = [st for st in self.stationByID.values() if key in self.normalizedStr(st.dbname)]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise TradeException(f"Station not found: {name}")
        raise TradeException(f"Ambiguous station: {name} -> {', '.join(h.fullName() for h in hits[:5])}")
    def lookupCategory(self, name: str) -> Category:
        key = self.normalizedStr(name)
        for cat in self.categoryByID.values():
            if key == self.normalizedStr(cat.dbname):
                return cat
        raise TradeException(f"Category not found: {name}")
    def lookupItem(self, name: str) -> Item:
        key = self.normalizedStr(name)
        it = self.itemByName.get(name) or self.itemByName.get(key)
        if it:
            return it
        for cand in self.itemByID.values():
            if key == self.normalizedStr(cand.dbname):
                return cand
        raise TradeException(f"Item not found: {name}")
    # Query the database for average selling prices of all items.
    # Lazily compute and cache average supply prices per item (ORM aggregate).
    def getAverageSelling(self) -> Dict[int, int]:
        if self.avgSelling is None:
            self.avgSelling = {itemID: 0 for itemID in self.itemByID}
            with self._session() as s:
                for iid, avgv in s.execute(
                    select(SA_StationItem.item_id, func.avg(SA_StationItem.supply_price))
                    .where(SA_StationItem.supply_price > 0)
                    .group_by(SA_StationItem.item_id)
                ):
                    self.avgSelling[int(iid)] = int(avgv or 0)
        return self.avgSelling
    # Query the database for average buying prices of all items.
    # Lazily compute and cache average demand prices per item (ORM aggregate).
    def getAverageBuying(self) -> Dict[int, int]:
        if self.avgBuying is None:
            self.avgBuying = {itemID: 0 for itemID in self.itemByID}
            with self._session() as s:
                for iid, avgv in s.execute(
                    select(SA_StationItem.item_id, func.avg(SA_StationItem.demand_price))
                    .where(SA_StationItem.demand_price > 0)
                    .group_by(SA_StationItem.item_id)
                ):
                    self.avgBuying[int(iid)] = int(avgv or 0)
        return self.avgBuying
    # Create System via ORM; ensure Added row exists; update in‑memory caches.
    def addLocalSystem(self, name: str, x: float, y: float, z: float, added: str = "Local", modified: str = 'now', commit: bool = True) -> System:
        with self._session() as s:
            added_id = s.scalar(select(SA_Added.added_id).where(SA_Added.name == added))
            # Ensure 'Added' source exists (create if missing).
            if not added_id:
                row_a = SA_Added(name=added)
                s.add(row_a)
                s.flush()
                added_id = row_a.added_id
            row = SA_System(name=name, pos_x=x, pos_y=y, pos_z=z, added_id=added_id)
            s.add(row)
            # Insert System and commit if requested; capture new PK.
            if commit:
                s.commit()
            ID = int(row.system_id)
        system = System(ID, name.upper(), x, y, z, int(added_id or 0))
        self.systemByID[ID] = system
        # Keep cache maps in sync with DB.
        self.systemByName[system.dbname] = system
        self.stellarGrid = None
        # Invalidate stellar grid (legacy side‑effect).
        return system
    # Update System via ORM and refresh cache entries.
    def updateLocalSystem(self, system: System, name: str, x: float, y: float, z: float, added: str = "Local", modified: str = 'now', force: bool = False, commit: bool = True) -> System:
        with self._session() as s:
            row = s.get(SA_System, system.ID)
            # Load current row; raise if missing to surface stale references.
            if not row:
                raise KeyError(system.ID)
            row.name, row.pos_x, row.pos_y, row.pos_z = name, x, y, z
            # Apply attribute updates.
            if added:
                aid = s.scalar(select(SA_Added.added_id).where(SA_Added.name == added))
                if aid:
                    row.added_id = aid
            if commit:
                s.commit()
                # Commit transaction if requested.
        if system.dbname in self.systemByName:
            del self.systemByName[system.dbname]
            # Refresh in‑memory name map to reflect rename.
        system.dbname, system.posX, system.posY, system.posZ = name.upper(), x, y, z
        self.systemByName[system.dbname] = system
        self.stellarGrid = None
        return system
    # Delete System via ORM and purge from caches.
    def removeLocalSystem(self, system: System, commit: bool = True) -> None:
        with self._session() as s:
            row = s.get(SA_System, system.ID)
            if row:
                s.delete(row)
                # Delete row if present and commit.
                if commit:
                    s.commit()
        self.systemByID.pop(system.ID, None)
        # Remove from in‑memory caches.
        self.systemByName.pop(system.dbname, None)
        self.stellarGrid = None
    # Create Station via ORM; map Fleet/Odyssey flags to type_id; cache result.
    def addLocalStation(self, system: System, name: str, lsFromStar: int, market: str, blackMarket: str, shipyard: str, maxPadSize: str, outfitting: str, rearm: str, refuel: str, repair: str, planetary: str, fleet: str, odyssey: str, modified: str = 'now', commit: bool = True) -> Station:
        type_id = 24 if fleet == 'Y' else (25 if odyssey == 'Y' else 0)
        # Translate Fleet/Odyssey flags to numeric type_id.
        with self._session() as s:
            row = SA_Station(
                name=name, system_id=system.ID, ls_from_star=lsFromStar,
                market=market, blackmarket=blackMarket, shipyard=shipyard,
                max_pad_size=maxPadSize, outfitting=outfitting, rearm=rearm,
                refuel=refuel, repair=repair, planetary=planetary, type_id=type_id
            )
            s.add(row)
            # Insert Station and commit if requested; capture new PK.
            if commit:
                s.commit()
            ID = int(row.station_id)
        st = Station(ID, system, name, lsFromStar, market, blackMarket, shipyard, maxPadSize, outfitting, rearm, refuel, repair, planetary, fleet, odyssey, 0, None)
        self.stationByID[ID] = st
        # Cache new station by id.
        return st
    # Update Station via ORM and update in‑memory object fields.
    def updateLocalStation(self, station: Station, system: System, name: str, lsFromStar: int, market: str, blackMarket: str, shipyard: str, maxPadSize: str, outfitting: str, rearm: str, refuel: str, repair: str, planetary: str, fleet: str, odyssey: str, modified: str = 'now', commit: bool = True) -> Station:
        type_id = 24 if fleet == 'Y' else (25 if odyssey == 'Y' else 0)
        with self._session() as s:
            row = s.get(SA_Station, station.ID)
            # Load current row; raise if missing to surface stale references.
            if not row:
                raise KeyError(station.ID)
            row.name = name
            # Apply attribute updates (no raw SQL).
            row.system_id = system.ID
            row.ls_from_star = lsFromStar
            row.market = market
            row.blackmarket = blackMarket
            row.shipyard = shipyard
            row.max_pad_size = maxPadSize
            row.outfitting = outfitting
            row.rearm = rearm
            row.refuel = refuel
            row.repair = repair
            row.planetary = planetary
            row.type_id = type_id
            if commit:
                s.commit()
        station.system = system
        # Keep in‑memory station object consistent with DB.
        station.dbname = name
        station.lsFromStar = lsFromStar
        station.market = market
        station.blackMarket = blackMarket
        station.shipyard = shipyard
        station.maxPadSize = maxPadSize
        station.outfitting = outfitting
        station.rearm = rearm
        station.refuel = refuel
        station.repair = repair
        station.planetary = planetary
        station.fleet = 'Y' if type_id in (24, 0) else 'N' if type_id not in (24, 0) else station.fleet
        # Recompute Fleet/Odyssey flags on in‑memory object.
        station.odyssey = 'Y' if type_id == 25 else 'N' if type_id != 25 else station.odyssey
        return station
    # Delete Station via ORM and purge from cache.
    def removeLocalStation(self, station: Station, commit: bool = True) -> None:
        with self._session() as s:
            row = s.get(SA_Station, station.ID)
            if row:
                s.delete(row)
                # Delete row if present and commit.
                if commit:
                    s.commit()
        self.stationByID.pop(station.ID, None)
        # Remove from in‑memory cache.
    @staticmethod
    # Distance helper kept for compatibility with previous UDF usage.
    # Distance helper kept for compatibility with historical UDF.
    def calculateDistance2(x1, y1, z1, x2, y2, z2) -> float:
        dx = x1 - x2
        dy = y1 - y2
        dz = z1 - z2
        return dx*dx + dy*dy + dz*dz
    @staticmethod
    # Euclidean distance wrapper.
    def calculateDistance(x1, y1, z1, x2, y2, z2) -> float:
        return _sqrt(TradeDB.calculateDistance2(x1, y1, z1, x2, y2, z2))
    @staticmethod
    # Legacy normalisation used across lookups.
    # Normalise names for matching (uppercase + trim).
    def normalizedStr(s: str) -> str:
        return (s or "").upper().strip()
    # Legacy raw‑SQL helper disabled (ORM only).
    def getDB(self, *a, **k):
        raise RuntimeError("TradeDB.getDB is removed; use ORM sessions.")
    # Legacy raw‑SQL helper disabled (ORM only).
    def query(self, *a, **k):
        raise RuntimeError("TradeDB.query is removed; use ORM sessions.")
    # Legacy raw‑SQL helper disabled (ORM only).
    def queryColumn(self, *a, **k):
        raise RuntimeError("TradeDB.queryColumn is removed; use ORM sessions.")