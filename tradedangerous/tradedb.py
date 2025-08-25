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
from collections import namedtuple



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

######################################################################
# Classes

class AmbiguityError(TradeException):
    """
    Raised when a search key could match multiple entities.
    Attributes:
        lookupType - description of what was being queried
        searchKey  - the key given to the search routine
        anyMatch   - list of candidates
        key        - function to get display string for a candidate
    """
    def __init__(self, lookupType, searchKey, anyMatch, key=lambda item: item):
        self.lookupType = lookupType
        self.searchKey = searchKey
        self.anyMatch = anyMatch
        self.key = key

    def __str__(self):
        anyMatch, key = self.anyMatch, self.key
        if len(anyMatch) > 10:
            opportunities = ", ".join([key(c) for c in anyMatch[:10]] + ["..."])
        else:
            opportunities = ", ".join(key(c) for c in anyMatch[0:-1])
            opportunities += " or " + key(anyMatch[-1])
        return f'{self.lookupType} "{self.searchKey}" could match {opportunities}'
        
class Destination(namedtuple('Destination', [
        'system', 'station', 'via', 'distLy'
        ])):
    pass

class DestinationNode(namedtuple('DestinationNode', [
        'system', 'via', 'distLy'
        ])):
    pass


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

    def getStation(self, name: str) -> 'Optional[Station]':
        """
        Quick case-insensitive lookup of a station name within the
        stations in this system.
        
        Returns:
            Station() object if a match is found,
            otherwise None.
        """
        name = name.upper()
        for station in self.stations:
            if station.name == name:
                return station
        return None
    def name(self, detail: int = 0) -> str:     # pylint: disable=unused-argument
        """ Returns the display name for this System."""
        return self.dbname
    def text(self) -> str:
        return self.dbname
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

    def name(self, detail: int = 0) -> str:  # pylint: disable=unused-argument
        return f"{self.system.dbname}/{self.dbname}"
    def checkPadSize(self, maxPadSize):
        """
        Tests if the Station's max pad size matches one of the
        values in 'maxPadSize'.
        
        Args:
            maxPadSize
                A string of one or more max pad size values that
                you want to match against.
        
        Returns:
            True
                If self.maxPadSize is None or empty, or matches a
                member of maxPadSize
            False
                If maxPadSize was not empty but self.maxPadSize
                did not match it.
        
        Examples:
            # Require a medium max pad size - not small or large
            station.checkPadSize("M")
            # Require medium or unknown
            station.checkPadSize("M?")
            # Require small, large or unknown
            station.checkPadSize("SL?")
        """
        return (not maxPadSize or self.maxPadSize in maxPadSize)
    def checkPlanetary(self, planetary):
        """
        Tests if the Station's planetary matches one of the
        values in 'planetary'.
        
        Args:
            planetary
                A string of one or more planetary values that
                you want to match against.
        
        Returns:
            True
                If self.planetary is None or empty, or matches a
                member of planetary
            False
                If planetary was not empty but self.planetary
                did not match it.
        
        Examples:
            # Require a planetary station
            station.checkPlanetary("Y")
            # Require planetary or unknown
            station.checkPlanetary("Y?")
            # Require no planetary station
            station.checkPlanetary("N")
        """
        return (not planetary or self.planetary in planetary)
    def checkFleet(self, fleet):
        """
        Same as checkPlanetary, but for fleet carriers.
        """
        return (not fleet or self.fleet in fleet)
    def checkOdyssey(self, odyssey):
        """
        Same as checkPlanetary, but for Odyssey.
        """
        return (not odyssey or self.odyssey in odyssey)
    def distFromStar(self, addSuffix: bool = False) -> str:
        """
        Returns a textual description of the distance from this
        Station to the parent star.
        
        Args:
            addSuffix[=False]:
                Always add a unit suffix (ls, Kls, ly)
        """
        ls = self.lsFromStar
        if not ls:
            return "Unk" if addSuffix else "?"
        
        suffix = "ls" if addSuffix else ""
        
        if ls < 1000:
            return f"{ls:n}{suffix}"
        if ls < 10000:
            return f"{ls / 1000:.2f}K{suffix}"
        if ls < 1000000:
            return f"{int(ls / 1000):n}K{suffix}"
        return f'{ls / (365*24*60*60):.2f}ly'
    def isTrading(self) -> bool:
        """
        True if the station is thought to be trading.
        
        A station is considered 'trading' if it has an item count > 0 or
        if it's "market" column is flagged 'Y'.
        """
        return (self.itemCount > 0 or self.market == 'Y')
    def itemDataAgeStr(self):
        """ Returns the age in days of item data if present, else "-". """
        if self.itemCount and self.dataAge:
            return f"{self.dataAge:7.2f}"
        return "-"
    def text(self) -> str:
        return f"{self.system.dbname}/{self.dbname}"
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

    def name(self, detail=0):   # pylint: disable=unused-argument
        return self.dbname.upper()
    ID: int
    dbname: str
    items: List["Item"]

@dataclass
class Item:
    ID: int
    dbname: str

        def name(self, detail=0):
            return self.fullname if detail > 0 else self.dbname
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

        def name(self, detail=0):
            return self.fullname if detail > 0 else self.dbname
    maxAllocation: Optional[int]
    illegal: str
    suppressed: str
    category: Category
    fullname: str
    
class Trade(namedtuple('Trade', (
        'item',
        'costCr', 'gainCr',
        'supply', 'supplyLevel',
        'demand', 'demandLevel',
        'srcAge', 'dstAge'
        ))):
    """
    Describes what it would cost and how much you would gain
    when selling an item between two specific stations.
    """
    def name(self, detail=0):
        return self.item.name(detail=detail)

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

        def lookupAdded(self, name):
            name = name.lower()
            for ID, added in self.addedByID.items():
                if added.lower() == name:
                    return ID
            raise KeyError(name)
        def genStellarGrid(self, system, ly):
            """
            Yields Systems within a given radius of a specified System.
        
            Args:
                system:
                    The System to center the search on,
                ly:
                    The radius of the search around system,
        
            Yields:
                (candidate, distLySq)
                    candidate:
                        System that was found,
                    distLySq:
                        The *SQUARE* of the distance in light-years
                        between system and candidate.
            """
            if self.stellarGrid is None:
                self.__buildStellarGrid()
        
            sysX, sysY, sysZ = system.posX, system.posY, system.posZ
            lwrBound = make_stellar_grid_key(sysX - ly, sysY - ly, sysZ - ly)
            uprBound = make_stellar_grid_key(sysX + ly, sysY + ly, sysZ + ly)
            lySq = ly * ly  # in 64-bit python, ** invokes a function call making it 4x expensive as *.
            stellarGrid = self.stellarGrid
            for x in range(lwrBound[0], uprBound[0]+1):
                for y in range(lwrBound[1], uprBound[1]+1):
                    for z in range(lwrBound[2], uprBound[2]+1):
                        try:
                            grid = stellarGrid[(x, y, z)]
                        except KeyError:
                            continue
                        for candidate in grid:
                            delta = candidate.posX - sysX
                            distSq = delta * delta
                            if distSq > lySq:
                                continue
                            delta = candidate.posY - sysY
                            distSq += delta * delta
                            if distSq > lySq:
                                continue
                            delta = candidate.posZ - sysZ
                            distSq += delta * delta
                            if distSq > lySq:
                                continue
                            if candidate is not system:
                                yield candidate, math_sqrt(distSq)
        def genSystemsInRange(self, system, ly, includeSelf=False):
            """
            Yields Systems within a given radius of a specified System.
            Results are sorted by distance and cached for subsequent
            queries in the same run.
        
            Args:
                system:
                    The System to center the search on,
                ly:
                    The radius of the search around system,
                includeSelf:
                    Whether to include 'system' in the results or not.
        
            Yields:
                (candidate, distLy)
                    candidate:
                        System that was found,
                    distLy:
                        The distance in lightyears between system and candidate.
            """
        
            cur_cache = system._rangeCache  # pylint: disable=protected-access
            if not cur_cache:
                cur_cache = system._rangeCache = System.RangeCache()
            cached_systems = cur_cache.systems
        
            if ly > cur_cache.probed_ly:
                # Consult the database for stars we haven't seen.
                cached_systems = cur_cache.systems = list(
                    self.genStellarGrid(system, ly)
                )
                cached_systems.sort(key=lambda ent: ent[1])
                cur_cache.probed_ly = ly
        
            if includeSelf:
                yield system, 0.
        
            if cur_cache.probed_ly > ly:
                # Cache may contain values outside our view
                for candidate, dist in cached_systems:
                    if dist <= ly:
                        yield candidate, dist
            else:
                # No need to be conditional inside the loop
                yield from cached_systems
        def getRoute(self, origin, dest, maxJumpLy, avoiding=None, stationInterval=0):
            """
            Find a shortest route between two systems with an additional
            constraint that each system be a maximum of maxJumpLy from
            the previous system.
        
            Args:
                origin:
                    System (or station) to start from,
                dest:
                    System (or station) to terminate at,
                maxJumpLy:
                    Maximum light years between systems,
                avoiding:
                    List of systems being avoided
                stationInterval:
                    If non-zero, require a station at least this many jumps,
                tdenv.padSize:
                    Controls the pad size of stations for refuelling
        
            Returns:
                None
                    No route was found
            
                [(origin, 0),...(dest, N)]
                    A list of (system, distanceSoFar) values describing
                    the route.
        
            Example:
                If there are systems A, B and C such
                that A->B is 7ly and B->C is 8ly then:
                
                    origin = lookupPlace("A")
                    dest = lookupPlace("C")
                    route = tdb.getRoute(origin, dest, 9)
            
                The route should be:
                
                    [(System(A), 0), (System(B), 7), System(C), 15)]
        
            """
        
            if avoiding is None:
                avoiding = []
        
            if isinstance(origin, Station):
                origin = origin.system
            if isinstance(dest, Station):
                dest = dest.system
        
            if origin == dest:
                return ((origin, 0), (dest, 0))
        
            # openSet is the list of nodes we want to visit, which will be
            # used as a priority queue (heapq).
            # Each element is a tuple of the 'priority' (the combination of
            # the total distance to the node and the distance left from the
            # node to the destination.
            openSet = [(0, 0, origin.ID, 0)]
            # Track predecessor nodes for everwhere we visit
            distances = {origin: (None, 0)}
        
            if avoiding:
                if dest in avoiding:
                    raise ValueError("Destination is in avoidance list")
                for avoid in avoiding:
                    if isinstance(avoid, System):
                        distances[avoid] = (None, -1)
        
            systemsInRange = self.genSystemsInRange
            heappop  = heapq.heappop
            heappush = heapq.heappush
            distTo = float("inf")
            defaultDist = (None, distTo)
            getDist  = distances.get
        
            destID = dest.ID
            sysByID = self.systemByID
        
            maxPadSize = self.tdenv.padSize
            if not maxPadSize:
                def checkStations(system: System) -> bool:  # pylint: disable=function-redefined, missing-docstring
                    return bool(system.stations())
            else:
                def checkStations(system: System) -> bool:  # pylint: disable=function-redefined, missing-docstring
                    return any(stn for stn in system.stations if stn.checkPadSize(maxPadSize))
        
            while openSet:
                weight, curDist, curSysID, stnDist = heappop(openSet)
                # If we reached 'goal' we've found the shortest path.
                if curSysID == destID:
                    break
                if curDist >= distTo:
                    continue
                curSys = sysByID[curSysID]
                # A node might wind up multiple times on the open list,
                # so check if we've already found a shorter distance to
                # the system and if so, ignore it this time.
                if curDist > distances[curSys][1]:
                    continue
            
                system_iter = iter(systemsInRange(curSys, maxJumpLy))
                if stationInterval:
                    if checkStations(curSys):
                        stnDist = 0
                    else:
                        stnDist += 1
                        if stnDist >= stationInterval:
                            system_iter = iter(
                                v for v in system_iter if checkStations(v[0])
                            )
            
                distFn = curSys.distanceTo
                for nSys, nDist in system_iter:
                    newDist = curDist + nDist
                    if getDist(nSys, defaultDist)[1] <= newDist:
                        continue
                    distances[nSys] = (curSys, newDist)
                    weight = distFn(nSys)
                    nID = nSys.ID
                    heappush(openSet, (newDist + weight, newDist, nID, stnDist))
                    if nID == destID:
                        distTo = newDist
        
            if dest not in distances:
                return None
        
            path = []
        
            while True:
                (prevSys, dist) = getDist(dest)
                path.append((dest, dist))
                if dest == origin:
                    break
                dest = prevSys
        
            path.reverse()
        
            return path
        def stations(self) -> 'Generator[Station, None, None]':
            """ Iterate through the list of stations. """
            yield from self.stationByID.values()
        def lookupPlace(self, name):
            """
            Lookup the station/system specified by 'name' which can be the
            name of a System or Station or it can be "System/Station" when
            the user needs to disambiguate a station. In this case, both
            system and station can be partial matches.
        
            The system tries to allow partial matches as well as matches
            which omit whitespaces. In order to do this and still support
            the massive namespace of Stars and Systems, we rank the
            matches so that exact matches win, and only inferior close
            matches are looked at if no exacts are found.
        
            Legal annotations:
                system
                station
                @system    [explicitly a system name]
                /station   [explicitly a station name]
                system/station
                @system/station
            """
        
            if isinstance(name, (System, Station)):
                return name
        
            slashPos = name.find('/')
            if slashPos < 0:
                slashPos = name.find('\\')
            nameOff = 1 if name.startswith('@') else 0
            if slashPos > nameOff:
                # Slash indicates it's, e.g., AULIN/ENTERPRISE
                sysName = name[nameOff:slashPos].upper()
                stnName = name[slashPos+1:]
            elif slashPos == nameOff:
                sysName, stnName = None, name[nameOff+1:]
            elif nameOff:
                # It's explicitly a station
                sysName, stnName = name[nameOff:].upper(), None
            else:
                # It could be either, use the name for both.
                stnName = name[nameOff:]
                sysName = stnName.upper()
        
            exactMatch = []
            closeMatch = []
            wordMatch = []
            anyMatch = []
        
            def lookup(name, candidates):
                """ Search candidates for the given name """
            
                normTrans = TradeDB.normalizeTrans
                trimTrans = TradeDB.trimTrans
            
                nameNorm = name.translate(normTrans)
                nameTrimmed = nameNorm.translate(trimTrans)
            
                nameLen = len(name)
                nameNormLen = len(nameNorm)
                nameTrimmedLen = len(nameTrimmed)
            
                for place in candidates:
                    placeName = place.dbname
                    placeNameNorm = placeName.translate(normTrans)
                    placeNameNormLen = len(placeNameNorm)
                
                    if nameTrimmedLen > placeNameNormLen:
                        # The needle is bigger than this haystack.
                        continue
                
                    # If the lengths match, do a direct comparison.
                    if len(placeName) == nameLen:
                        if placeNameNorm == nameNorm:
                            exactMatch.append(place)
                        continue
                    if placeNameNormLen == nameNormLen:
                        if placeNameNorm == nameNorm:
                            closeMatch.append(place)
                        continue
                
                    if nameNormLen < placeNameNormLen:
                        subPos = placeNameNorm.find(nameNorm)
                        if subPos == 0:
                            if placeNameNorm[nameNormLen] == ' ':
                                # first word
                                wordMatch.append(place)
                            else:
                                anyMatch.append(place)
                            continue
                    
                        if subPos > 0:
                            if placeNameNorm[subPos] == ' ' and \
                                    placeNameNorm[subPos + nameNormLen] == ' ':
                                wordMatch.append(place)
                            else:
                                anyMatch.append(place)
                            continue
                
                    # Lets drop whitespace and remaining punctuation...
                    placeNameTrimmed = placeNameNorm.translate(trimTrans)
                    placeNameTrimmedLen = len(placeNameTrimmed)
                    if placeNameTrimmedLen == placeNameNormLen:
                        # No change
                        continue
                
                    # A match here is not exact but still fairly interesting
                    if len(placeNameTrimmed) == nameTrimmedLen:
                        if placeNameTrimmed == nameTrimmed:
                            closeMatch.append(place)
                        continue
                    if placeNameTrimmed.find(nameTrimmed) >= 0:
                        anyMatch.append(place)
        
            if sysName:
                try:
                    system = self.systemByName[sysName]
                    exactMatch = [system]
                except KeyError:
                    lookup(sysName, self.systemByID.values())
        
            if stnName:
                # Are we considering the name as a station?
                # (we don't if they type, e,g '@aulin')
                # compare against nameOff to allow '@/station'
                if slashPos > nameOff + 1:
                    # "sys/station"; the user should have specified a system
                    # name and we should be able to narrow down which
                    # stations we compare against. Check first if there are
                    # any matches.
                    stationCandidates = []
                    for system in itertools.chain(
                            exactMatch, closeMatch, wordMatch, anyMatch
                            ):
                        stationCandidates += system.stations
                    # Clear out the candidate lists
                    exactMatch = []
                    closeMatch = []
                    wordMatch = []
                    anyMatch = []
                else:
                    # Consider against all station names
                    stationCandidates = self.stationByID.values()
                lookup(stnName, stationCandidates)
        
            # consult the match sets in ranking order for a single
            # match, which denotes a win at that tier. For example,
            # if there is one exact match, we don't care how many
            # close matches there were.
            for matchSet in exactMatch, closeMatch, wordMatch, anyMatch:
                if len(matchSet) == 1:
                    return matchSet[0]
        
            # Nothing matched
            if not any([exactMatch, closeMatch, wordMatch, anyMatch]):
                # Note: this was a TradeException and may need to be again,
                # but then we need to catch that error in commandenv
                # when we process avoids
                raise LookupError(f"Unrecognized place: {name}")
        
            # More than one match
            raise AmbiguityError(
                'System/Station', name,
                exactMatch + closeMatch + wordMatch + anyMatch,
                key=lambda place: place.name()
            )
        def getDestinations(
                self,
                origin,
                maxJumps=None,
                maxLyPer=None,
                avoidPlaces=None,
                maxPadSize=None,
                maxLsFromStar=0,
                noPlanet=False,
                planetary=None,
                fleet=None,
                odyssey=None,
                ):
            """
            Gets a list of the Station destinations that can be reached
            from this Station within the specified constraints.
            Limits to stations we are trading with if trading is True.
            """
        
            if maxJumps is None:
                maxJumps = sys.maxsize
            maxLyPer = maxLyPer or self.maxSystemLinkLy
            if avoidPlaces is None:
                avoidPlaces = ()
        
            # The open list is the list of nodes we should consider next for
            # potential destinations.
            # The path list is a list of the destinations we've found and the
            # shortest path to them. It doubles as the "closed list".
            # The closed list is the list of nodes we've already been to (so
            # that we don't create loops A->B->C->A->B->C->...)
        
            origSys = origin.system if isinstance(origin, Station) else origin
            openList = [DestinationNode(origSys, [origSys], 0)]
            # I don't want to have to consult both the pathList
            # AND the avoid list every time I'm considering a
            # station, so copy the avoid list into the pathList
            # with a negative distance so I can ignore them again
            # when I scrape the pathList.
            # Don't copy stations because those only affect our
            # termination points, and not the systems we can
            # pass through en-route.
            pathList = {
                system.ID: DestinationNode(system, None, -1.0)
                for system in avoidPlaces
                if isinstance(system, System)
            }
            if origSys.ID not in pathList:
                pathList[origSys.ID] = openList[0]
        
            # As long as the open list is not empty, keep iterating.
            jumps = 0
            while openList and jumps < maxJumps:
                # Expand the search domain by one jump; grab the list of
                # nodes that are this many hops out and then clear the list.
                ring, openList = openList, []
                # All of the destinations we are about to consider will
                # either be on the closed list or they will be +1 jump away.
                jumps += 1
            
                ring.sort(key=lambda dn: dn.distLy)
            
                for node in ring:
                    for (destSys, destDist) in self.genSystemsInRange(
                            node.system, maxLyPer, False
                            ):
                        dist = node.distLy + destDist
                        # If we already have a shorter path, do nothing
                        try:
                            prevDist = pathList[destSys.ID].distLy
                        except KeyError:
                            pass
                        else:
                            if dist >= prevDist:
                                continue
                        # Add to the path list
                        destNode = DestinationNode(
                            destSys, node.via + [destSys], dist
                        )
                        pathList[destSys.ID] = destNode
                        # Add to the open list but also include node to the via
                        # list so that it serves as the via list for all next-hops.
                        openList.append(destNode)
        
            # We have a system-to-system path list, now we
            # need stations to terminate at.
            def path_iter_fn():
                for node in pathList.values():
                    if node.distLy >= 0.0:
                        for station in node.system.stations:
                            yield node, station
        
            path_iter = iter(
              (node, station) for (node, station) in path_iter_fn()
              if (station.planetary == 'N' if noPlanet else True) and
                (station not in avoidPlaces if avoidPlaces else True) and
                (station.checkPadSize(maxPadSize) if maxPadSize else True) and
                (station.checkPlanetary(planetary) if planetary else True) and
                (station.checkFleet(fleet) if fleet else True) and
                (station.checkOdyssey(odyssey) if odyssey else True) and
                (station.lsFromStar > 0 and station.lsFromStar <= maxLsFromStar if maxLsFromStar else True)
            )
            for node, stn in path_iter:
                yield Destination(node.system, stn, node.via, node.distLy)
        def ships(self):
            """ Iterate through the list of ships. """
            yield from self.shipByID.values()
        def lookupShip(self, name):
            """
            Look up a ship by name
            """
            return TradeDB.listSearch(
                "Ship", name, self.shipByID.values(),
                key=lambda ship: ship.dbname
            )
        def categories(self):
            """
            Iterate through the list of categories.
            key = category name, value = list of items.
            """
            yield from self.categoryByID.items()
        def load(self, maxSystemLinkLy=None):
            """
                Populate/re-populate this instance of TradeDB with data.
                WARNING: This will orphan existing records you have
                taken references to:
                    tdb.load()
                    x = tdb.lookupPlace("Aulin")
                    tdb.load() # x now points to an orphan Aulin
            """
        
            self.tdenv.DEBUG1("Loading data")


        
            self._loadAdded()
            self._loadSystems()
            self._loadStations()
            self._loadShips()
            self._loadCategories()
            self._loadItems()
            self._loadRareItems()
        
            # Calculate the maximum distance anyone can jump so we can constrain
            # the maximum "link" between any two stars.
            msll = maxSystemLinkLy or self.tdenv.maxSystemLinkLy or 30
            self.maxSystemLinkLy = msll
        def listSearch(
                listType, lookup, values,
                key=lambda item: item,
                val=lambda item: item
                ):
            """
            Searches [values] for 'lookup' for least-ambiguous matches,
            return the matching value as stored in [values].
        
            GIVEN [values] contains "bread", "water", "biscuits and "It",
            searching "ea" will return "bread", "WaT" will return "water"
            and "i" will return "biscuits".
        
            Searching for "a" would raise an AmbiguityError because "a" matches
            "bread" and "water", but searching for "it" will return "It"
            because it provides an exact match of a key.
            """
        
            class ListSearchMatch(namedtuple('Match', ['key', 'value'])):
                pass
        
            normTrans = TradeDB.normalizeTrans
            trimTrans = TradeDB.trimTrans
            needle = lookup.translate(normTrans).translate(trimTrans)
            partialMatch, wordMatch = [], []
            # make a regex to match whole words
            wordRe = re.compile(f"\\b{lookup}\\b", re.IGNORECASE)
            # describe a match
            for entry in values:
                entryKey = key(entry)
                normVal = entryKey.translate(normTrans).translate(trimTrans)
                if normVal.find(needle) > -1:
                    # If this is an exact match, ignore ambiguities.
                    if len(normVal) == len(needle):
                        return val(entry)
                    match = ListSearchMatch(entryKey, val(entry))
                    if wordRe.match(entryKey):
                        wordMatch.append(match)
                    else:
                        partialMatch.append(match)
            # Whole word matches trump partial matches
            if wordMatch:
                if len(wordMatch) > 1:
                    raise AmbiguityError(
                        listType, lookup, wordMatch,
                        key=lambda item: item.key,
                    )
                return wordMatch[0].value
            # Fuzzy matches
            if partialMatch:
                if len(partialMatch) > 1:
                    raise AmbiguityError(
                        listType, lookup, partialMatch,
                        key=lambda item: item.key,
                    )
                return partialMatch[0].value
            # No matches
            raise LookupError(f"Error: '{lookup}' doesn't match any {listType}")
    # Legacy raw‑SQL helper disabled (ORM only).
    def query(self, *a, **k):
        raise RuntimeError("TradeDB.query is removed; use ORM sessions.")
    # Legacy raw‑SQL helper disabled (ORM only).
    def queryColumn(self, *a, **k):
        raise RuntimeError("TradeDB.queryColumn is removed; use ORM sessions.")
        
####################################################################
# Assorted helpers

def describeAge(ageInSeconds: Union[float, int]) -> str:
    """
    Turns an age (in seconds) into a text representation.
    """
    hours = int(ageInSeconds / 3600)
    if hours < 1:
        return "<1 hr"
    if hours == 1:
        return "1 hr"
    if hours < 48:
        return f"{hours} hrs"
    days = int(hours / 24)
    if days < 90:
        return f"{days} days"
    return f"{int(days / 31)} mths"

# ---- Restored API (from legacy) ----
class SystemNotStationError(TradeException):
    """
        Raised when a station lookup matched a System but
        could not be automatically reduced to a Station.
    """
    pass  # pylint: disable=unnecessary-pass  # (it's not)
def make_stellar_grid_key(x: float, y: float, z: float) -> int:
    """
    The Stellar Grid is a map of systems based on their Stellar
    co-ordinates rounded down to 32lys. This makes it much easier
    to find stars within rectangular volumes.
    """
    return (int(x) >> 5, int(y) >> 5, int(z) >> 5)
