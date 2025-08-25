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

# --- cache.py patch: robust template directory resolution ---
def _default_template_dir():
    """Return the built-in templates directory (package-relative)."""
    try:
        return Path(__file__).resolve().parent / 'templates'
    except Exception:
        return Path('tradedangerous') / 'templates'


from pathlib import Path
import csv
from typing import Dict, Iterable, Sequence

from sqlalchemy import select, func
from sqlalchemy.orm import Session

# ---- ORM imports ----
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

# I feel pretty, oh so pretty!
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

def _count_csv_rows(path: Path) -> int | None:
    """Count CSV lines minus header (fast-ish)."""
    try:
        with path.open("rb") as fh:
            total = sum(buf.count(b"\n") for buf in iter(lambda: fh.read(1 << 20), b""))
        return max(0, total - 1)
    except Exception:
        return None

def _progress_iter(path: Path, it, label: str):
    """Wrap an iterator with a progress bar or fallback counter."""
    total = _count_csv_rows(path)
    if tqdm and total is not None:
        yield from tqdm(it, total=total, unit="row", desc=f"{label}: {path.name}")
    else:
        # fallback counter
        import sys
        N, count = 10000, 0
        for r in it:
            count += 1
            if count % N == 0:
                sys.stdout.write(f"\r{label}: {path.name} … {count:,} rows")
                sys.stdout.flush()
            yield r
        if count:
            sys.stdout.write(f"\r{label}: {path.name} … {count:,} rows\n")
            sys.stdout.flush()


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
        if reader.fieldnames is None:
            return

        mapping = []
        for orig in reader.fieldnames:
            lk = (orig or "").strip().lower()
            base = lk
            if base.startswith("unq:"):
                base = base[4:]
            if base.startswith("!"):
                base = base[1:]
            if "@" in base:
                base = base.split("@", 1)[0]
            mapping.append((orig, lk, base))

        for row in reader:
            out: dict[str, str] = {}
            for orig, lk, base in mapping:
                v = row.get(orig, "")
                if isinstance(v, str):
                    s = v.strip()
                    # unwrap single-quoted CSV fields
                    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
                        s = s[1:-1].replace("''", "'")
                    v = s
                # always set the original lowered key
                if lk not in out:
                    out[lk] = v
                # set base key only if not already present (avoid clobber)
                if base and base != lk and base not in out:
                    out[base] = v
            yield out

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
        first = True
        for r in _progress_iter(path, _read_csv(path), "Import"):
            if first:
                # one-shot visibility into what we're actually reading
                print(f"DEBUG Added.csv path={path} keys={sorted(r.keys())[:8]}")
                first = False
            # accept plain or directive-prefixed header
            nm = r.get("name") or r.get("unq:name") or r.get("!name")
            if nm is None:
                raise KeyError(f"{path}: required 'name' not found.headers={list(r.keys())!r} row={r!r}")
            obj = SA_Added(name=nm)
            # unique on name: idempotent insert-ignore via merge-like semantics
            existing = session.execute(select(SA_Added).where(SA_Added.name == obj.name)).scalar_one_or_none()
            if not existing:
                session.add(obj); count += 1
    elif tbl == "system":
        for r in _progress_iter(path, _read_csv(path), "Import"):
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
        for r in _progress_iter(path, _read_csv(path), "Import"):
            stid = int(r["station_id"]) if r.get("station_id") else int(r["id"]) if r.get("id") else None
            if stid is None:
                continue
            obj = session.get(SA_Station, stid) or SA_Station(station_id=stid)
            obj.name = r["name"]
            obj.system_id = int(r.get("system_id") or r.get("system") or 0)
            val = r.get("ls_from_star")
            if not val:
                obj.ls_from_star = 0
            else:
                try:
                    obj.ls_from_star = int(float(val))
                except ValueError:
                    raise ValueError(f"{path}: bad ls_from_star value {val!r}")
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
        for r in _progress_iter(path, _read_csv(path), "Import"):
            cid = int(r.get("category_id") or r.get("id") or 0)
            if cid == 0: continue
            obj = session.get(SA_Category, cid) or SA_Category(category_id=cid)
            obj.name = r["name"]
            session.add(obj); count += 1
    elif tbl == "item":
        for r in _progress_iter(path, _read_csv(path), "Import"):
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
        for r in _progress_iter(path, _read_csv(path), "Import"):
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
        for r in _progress_iter(path, _read_csv(path), "Import"):
            shid = int(r.get("ship_id") or r.get("id") or 0)
            if shid == 0: continue
            obj = session.get(SA_Ship, shid) or SA_Ship(ship_id=shid)
            obj.name = r["name"]
            if "cost" in r and r["cost"]:
                try: obj.cost = int(r["cost"])
                except ValueError: pass
            session.add(obj); count += 1
    elif tbl == "upgrade" and SA_Upgrade is not None:
        for r in _progress_iter(path, _read_csv(path), "Import"):
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
    raw_tpl = getattr(tdenv, 'templatePath', None)
    template_dir = (Path(raw_tpl) if raw_tpl else _default_template_dir())
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
def regeneratePricesFile(tdb, tdenv):
    """
    Write a complete '.prices' CSV snapshot from the current StationItem table.
    Expected by plugins (e.g. eddblink) after listings import.

    Output columns exactly match the loader in cache.importDataFromFile():
    station_id,item_id,demand_price,demand_units,demand_level,
    supply_price,supply_units,supply_level

    Returns: Path to the written file.
    """
    from pathlib import Path
    import csv
    from sqlalchemy import select

    # Resolve output path the same way TradeDB does (dataPath + defaultPrices).
    out_path = Path(getattr(tdb, "pricesPath", None) or
                    (Path(getattr(tdb, "dataPath")) / getattr(tdb, "defaultPrices", "TradeDangerous.prices")))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Pull rows via ORM.
    with tdb._Session() as s:  # type: ignore[attr-defined]
        from tradedangerous.db.orm_models import StationItem as SA_StationItem
        rows = s.execute(
            select(
                SA_StationItem.station_id,
                SA_StationItem.item_id,
                SA_StationItem.demand_price,
                SA_StationItem.demand_units,
                SA_StationItem.demand_level,
                SA_StationItem.supply_price,
                SA_StationItem.supply_units,
                SA_StationItem.supply_level,
            ).order_by(SA_StationItem.station_id, SA_StationItem.item_id)
        )

        with out_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow([
                "station_id","item_id",
                "demand_price","demand_units","demand_level",
                "supply_price","supply_units","supply_level",
            ])
            for (station_id, item_id, d_p, d_u, d_l, s_p, s_u, s_l) in rows:
                w.writerow([
                    int(station_id), int(item_id),
                    int(d_p or 0), int(d_u or 0), int(d_l or 0),
                    int(s_p or 0), int(s_u or 0), int(s_l or 0),
                ])
    return out_path
