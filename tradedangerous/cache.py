# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
# Copyright (C) Stefan 'Tromador' Morrell 2025
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# ---------------
# -----------------------------------------------------
# TradeDangerous :: Modules :: Cache loader (SQLAlchemy adapter)
#
# This module replaces the sqlite3/raw-SQL implementation with SQLAlchemy 2.x.
# Behavioural goal: same results/side-effects as legacy cache.py; only the
# persistence layer changes. CSV shapes must be accepted as-is.
#
from __future__ import annotations

from pathlib import Path
import csv
from typing import Dict, Iterable, Sequence

from sqlalchemy import select, func
from sqlalchemy.orm import Session

# ---- ORM imports (prefer package path, fall back to local) ----
try:
    # canonical project layout
    from tradedangerous.db.orm_models import (
        Base,
        Added as SA_Added,
        System as SA_System,
        Station as SA_Station,
        Item as SA_Item,
        Category as SA_Category,
        StationItem as SA_StationItem,
        RareItem as SA_RareItem,
        Ship as SA_Ship,
        Upgrade as SA_Upgrade,
        ShipVendor as SA_ShipVendor,
        UpgradeVendor as SA_UpgradeVendor,
    )
except Exception:  # pragma: no cover
    from orm_models import (  # type: ignore
        Base,
        Added as SA_Added,
        System as SA_System,
        Station as SA_Station,
        Item as SA_Item,
        Category as SA_Category,
        StationItem as SA_StationItem,
        RareItem as SA_RareItem,
        Ship as SA_Ship,
        Upgrade as SA_Upgrade,
        ShipVendor as SA_ShipVendor,
        UpgradeVendor as SA_UpgradeVendor,
    )

# ---------------- Index helpers (unchanged semantics) ----------------

def getSystemByNameIndex(session: Session) -> Dict[str, int]:
    rows = session.execute(select(SA_System.system_id, SA_System.name))
    return {str(name).upper(): int(sid) for sid, name in rows}

def getStationByNameIndex(session: Session) -> Dict[str, int]:
    q = (
        select(SA_Station.station_id, SA_System.name, SA_Station.name)
        .join(SA_System, SA_System.system_id == SA_Station.system_id)
    )
    rows = session.execute(q).all()
    return {f"{sys}/{stn}".upper(): int(station_id) for station_id, sys, stn in rows}

def getItemByNameIndex(session: Session) -> Dict[str, int]:
    rows = session.execute(select(SA_Item.item_id, SA_Item.name))
    return {str(name).upper(): int(item_id) for item_id, name in rows}

# ---------------- CSV import helpers ----------------

def _read_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # normalize headers to lower-case keys where needed?
            yield {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}

# Compatibility shapes: legacy CSVs have specific filenames → tables
# Added.csv, System.csv, Station.csv, Category.csv, Item.csv, RareItem.csv, Ship.csv, Upgrade.csv
# For prices: <station_id>.prices with headers:
# station_id,item_id,demand_price,demand_units,demand_level,supply_price,supply_units,supply_level

def processImportFile(session: Session, path: Path, table_hint: str | None = None) -> int:
    """
    Import a *single* CSV file into the mapped tables using ORM objects.
    Returns count of rows staged/added (best-effort).
    """
    tbl = (table_hint or path.stem or "").strip().lower()
    count = 0

    if tbl == "added":
        for r in _read_csv(path):
            obj = SA_Added(name=r["name"])
            # unique on name: idempotent insert-ignore via merge-like semantics
            existing = session.execute(select(SA_Added).where(SA_Added.name == obj.name)).scalar_one_or_none()
            if not existing:
                session.add(obj); count += 1
    elif tbl == "system":
        for r in _read_csv(path):
            sid = int(r["system_id"]) if r.get("system_id") else int(r["id"]) if r.get("id") else None
            if sid is None:
                continue
            obj = session.get(SA_System, sid) or SA_System(system_id=sid)
            obj.name = r["name"]
            obj.pos_x = float(r.get("pos_x", 0) or 0)
            obj.pos_y = float(r.get("pos_y", 0) or 0)
            obj.pos_z = float(r.get("pos_z", 0) or 0)
            session.add(obj); count += 1
    elif tbl == "station":
        for r in _read_csv(path):
            stid = int(r["station_id"]) if r.get("station_id") else int(r["id"]) if r.get("id") else None
            if stid is None:
                continue
            obj = session.get(SA_Station, stid) or SA_Station(station_id=stid)
            obj.name = r["name"]
            obj.system_id = int(r.get("system_id") or r.get("system") or 0)
            obj.ls_from_star = int(r.get("ls_from_star") or 0)
            # Flags: tolerate missing columns (bootstrap CSVs sometimes omit)
            for col in ("blackmarket","market","shipyard","outfitting","rearm","refuel","repair","planetary"):
                if col in r and getattr(obj, col, None) is not None:
                    setattr(obj, col, (r[col] or "?")[:1])
            if "max_pad_size" in r and getattr(obj, "max_pad_size", None) is not None:
                obj.max_pad_size = (r["max_pad_size"] or "?")[:1]
            if "type_id" in r and r["type_id"]:
                try: obj.type_id = int(r["type_id"])
                except ValueError: pass
            session.add(obj); count += 1
    elif tbl == "category":
        for r in _read_csv(path):
            cid = int(r.get("category_id") or r.get("id") or 0)
            if cid == 0: continue
            obj = session.get(SA_Category, cid) or SA_Category(category_id=cid)
            obj.name = r["name"]
            session.add(obj); count += 1
    elif tbl == "item":
        for r in _read_csv(path):
            iid = int(r.get("item_id") or r.get("id") or 0)
            if iid == 0: continue
            obj = session.get(SA_Item, iid) or SA_Item(item_id=iid)
            obj.name = r["name"]
            obj.category_id = int(r.get("category_id") or 0)
            if "ui_order" in r and r["ui_order"]:
                try: obj.ui_order = int(r["ui_order"])
                except ValueError: pass
            if "avg_price" in r and r["avg_price"]:
                try: obj.avg_price = int(r["avg_price"])
                except ValueError: pass
            if "fdev_id" in r and r["fdev_id"]:
                try: obj.fdev_id = int(r["fdev_id"])
                except ValueError: pass
            session.add(obj); count += 1
    elif tbl == "rareitem" and SA_RareItem is not None:
        for r in _read_csv(path):
            rid = int(r.get("rare_id") or r.get("id") or 0)
            if rid == 0: continue
            obj = session.get(SA_RareItem, rid) or SA_RareItem(rare_id=rid)
            obj.station_id = int(r.get("station_id") or 0)
            obj.category_id = int(r.get("category_id") or 0)
            obj.name = r["name"]
            if "cost" in r and r["cost"]:
                try: obj.cost = int(r["cost"])
                except ValueError: pass
            if "max_allocation" in r and r["max_allocation"]:
                try: obj.max_allocation = int(r["max_allocation"])
                except ValueError: pass
            for col in ("illegal","suppressed"):
                if col in r and r[col]:
                    setattr(obj, col, r[col][:1])
            session.add(obj); count += 1
    elif tbl == "ship" and SA_Ship is not None:
        for r in _read_csv(path):
            shid = int(r.get("ship_id") or r.get("id") or 0)
            if shid == 0: continue
            obj = session.get(SA_Ship, shid) or SA_Ship(ship_id=shid)
            obj.name = r["name"]
            if "cost" in r and r["cost"]:
                try: obj.cost = int(r["cost"])
                except ValueError: pass
            session.add(obj); count += 1
    elif tbl == "upgrade" and SA_Upgrade is not None:
        for r in _read_csv(path):
            upid = int(r.get("upgrade_id") or r.get("id") or 0)
            if upid == 0: continue
            obj = session.get(SA_Upgrade, upid) or SA_Upgrade(upgrade_id=upid)
            obj.name = r["name"]
            if hasattr(obj, "class_") and "class" in r:
                try: obj.class_ = int(r["class"])
                except ValueError: pass
            if "rating" in r: obj.rating = (r["rating"] or "")[0:1]
            if "ship" in r: obj.ship = r["ship"]
            session.add(obj); count += 1
    else:
        # Accept unknown tables silently (legacy seeds include extras sometimes)
        count = 0

    return count

def processPricesRows(session: Session, station_id: int, rows: Sequence[dict[str, str]]) -> int:
    """
    Import <station_id>.prices content already parsed into dict rows.
    """
    count = 0
    for r in rows:
        item_id = int(r["item_id"])
        obj = session.get(SA_StationItem, {"station_id": station_id, "item_id": item_id})
        if not obj:
            obj = SA_StationItem(station_id=station_id, item_id=item_id,
                                 demand_price=0, demand_units=0, demand_level=0,
                                 supply_price=0, supply_units=0, supply_level=0)
        # tolerate blanks; coerce to 0
        def _iv(key: str) -> int:
            v = r.get(key, "") or 0
            try: return int(v)
            except ValueError: return 0
        obj.demand_price = _iv("demand_price")
        obj.demand_units = _iv("demand_units")
        obj.demand_level = _iv("demand_level")
        obj.supply_price = _iv("supply_price")
        obj.supply_units = _iv("supply_units")
        obj.supply_level = _iv("supply_level")
        # mark as 'has market' if any price present later
        session.add(obj)
        count += 1
    # set Station.market='Y' if any StationItem now exists
    has_rows = session.execute(
        select(func.count()).select_from(SA_StationItem).where(SA_StationItem.station_id == station_id)
    ).scalar_one()
    if has_rows:
        st = session.get(SA_Station, station_id)
        if st and hasattr(st, "market"):
            st.market = "Y"
    return count

def processPricesFile(session: Session, path: Path) -> int:
    """
    Read a .prices file and apply rows to StationItem for that station.
    """
    rows = list(_read_csv(path))
    if not rows:
        return 0
    stid = int(rows[0].get("station_id") or 0)
    return processPricesRows(session, stid, rows)

# ---------------- High-level entry points (called by tradedb) ----------------

def buildCache(tdb, tdenv) -> None:
    """
    Seed a brand-new database from template CSVs under tradedangerous/templates.
    Mirrors the legacy buildCache() behaviour but uses the ORM.
    """
    template_dir = Path(tdenv.templatePath)
    order = [
        ("Added.csv", "Added"),
        ("System.csv", "System"),
        ("Station.csv", "Station"),
        ("Category.csv", "Category"),
        ("Item.csv", "Item"),
        ("RareItem.csv", "RareItem"),
        ("Ship.csv", "Ship"),
        ("Upgrade.csv", "Upgrade"),
    ]

    with tdb._Session() as s:  # type: ignore[attr-defined]
        with s.begin():
            for filename, table in order:
                p = template_dir / filename
                if p.exists():
                    processImportFile(s, p, table)

def importDataFromFile(tdb, path: Path) -> int:
    """Compatibility shim used by callers to import a single CSV/prices file.
    Returns number of rows affected (best-effort).
    """
    suffix = path.suffix.lower()
    table = path.stem
    with tdb._Session() as s:  # type: ignore[attr-defined]
        with s.begin():
            if suffix == ".prices":
                # very small, explicit format: station_id,item_i...demand_units,demand_level,supply_price,supply_units,supply_level
                rows = list(_read_csv(path))
                if not rows:
                    return 0
                stid = int(rows[0].get("station_id") or 0)
                return processPricesRows(s, stid, rows)
            else:
                return processImportFile(s, path, table)
