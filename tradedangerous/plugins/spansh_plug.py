""" Plugin for importing data from Spansh dumps (galaxy_stations.json).

Refactored for SQLAlchemy ORM; legacy sqlite3 usage removed.
"""
from __future__ import annotations

from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from rich.progress import Progress

from .. import plugins, cache, transfers, csvexport, corrections

import os
import requests
import sys
import time
import typing
import ijson

from dataclasses import dataclass  # project baseline Python ≥3.9

# SQLAlchemy / DB engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..db import get_session_factory
from ..db.orm_models import (
    System,
    Station,
    Ship,
    Upgrade,
    Item,
    StationItem,
    ShipVendor,
    UpgradeVendor,
    Category,
)

if typing.TYPE_CHECKING:
    from typing import Any, Optional
    from collections.abc import Iterable
    from ..tradeenv import TradeEnv

SOURCE_URL = 'https://downloads.spansh.co.uk/galaxy_stations.json'

# Mapping of station type names → [numeric code, planetary flag]
# ⚠ Must be preserved exactly for compatibility with existing data/logic.
STATION_TYPE_MAP = {
    'None': [0, False],
    'Outpost': [1, False],
    'Coriolis Starport': [2, False],
    'Ocellus Starport': [3, False],
    'Orbis Starport': [4, False],
    'Planetary Outpost': [11, True],
    'Planetary Port': [12, True],
    'Mega ship': [13, False],
    'Asteroid base': [14, False],
    'Drake-Class Carrier': [24, False],  # fleet carriers
    'Settlement': [25, True],            # Odyssey settlements
}


if dataclass:
    # Dataclass with slots is considerably cheaper and faster than namedtuple
    # but is only reliably introduced in 3.10+
    # DTO classes are used during JSON ingestion only.
    # They intentionally use *DTO suffixes to avoid colliding with ORM model names
    # (System, Station, Ship, Upgrade, Item, etc.) imported from db.orm_models.
    @dataclass(slots=True)
    class SystemDTO:
        id:       int
        name:     str
        pos_x:    float
        pos_y:    float
        pos_z:    float
        modified: float | None  # epoch seconds; converted to UTC datetime later

    @dataclass(slots=True)
    class StationDTO:  # pylint: disable=too-many-instance-attributes
        id:           int
        system_id:    int
        name:         str
        distance:     float
        max_pad_size: str
        # Service flags remain tri-state: 'Y'/'N'/'?'
        market:       str
        black_market: str
        shipyard:     str
        outfitting:   str
        rearm:        str
        refuel:       str
        repair:       str
        planetary:    str
        type:         int
        modified:     float  # epoch seconds

    @dataclass(slots=True)
    class ShipDTO:
        id:       int
        name:     str
        modified: float  # epoch seconds

    @dataclass(slots=True)
    class UpgradeDTO:
        id:       int
        name:     str
        cls:      int
        rating:   str
        ship:     str
        modified: float  # epoch seconds

    @dataclass(slots=True)
    class CommodityDTO:
        id:       int
        name:     str
        category: str
        demand:   int
        supply:   int
        sell:     int
        buy:      int
        modified: float  # epoch seconds

else:
    SystemDTO    = namedtuple('SystemDTO', 'id,name,pos_x,pos_y,pos_z,modified')
    StationDTO   = namedtuple('StationDTO',
                              'id,system_id,name,distance,max_pad_size,'
                              'market,black_market,shipyard,outfitting,'
                              'rearm,refuel,repair,planetary,type,modified')
    ShipDTO      = namedtuple('ShipDTO', 'id,name,modified')
    UpgradeDTO   = namedtuple('UpgradeDTO', 'id,name,cls,rating,ship,modified')
    CommodityDTO = namedtuple('CommodityDTO',
                              'id,name,category,demand,supply,sell,buy,modified')

def to_datetime(value):
    """Normalise timestamps to datetime (UTC). Accepts datetime, epoch float, or None."""
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    return datetime.utcfromtimestamp(value)


class Timing:
    """ Helper that provides a context manager for timing code execution. """
    
    def __init__(self):
        self.start_ts = None
        self.end_ts = None
    
    def __enter__(self):
        self.start_ts = time.perf_counter()
        self.end_ts = None
        return self
    
    def __exit__(self, *args):
        self.end_ts = time.perf_counter()
    
    @property
    def elapsed(self) -> Optional[float]:
        """ If the timing has finished, calculates the elapsed time. """
        if self.start_ts is None:
            return None
        return (self.end_ts or time.perf_counter()) - self.start_ts
    
    @property
    def is_finished(self) -> bool:
        """ True if the timing has finished. """
        return self.end_ts is not None


class Progresser:
    """ Encapsulates a potentially transient progress view for a given TradeEnv. """
    def __init__(self, tdenv: 'TradeEnv', title: str, fancy: bool = True, total: Optional[int] = None):
        self.started = time.time()
        self.tdenv = tdenv
        self.progress, self.main_task = None, None
        self.title = title
        self.fancy = fancy
        self.total = total
        self.main_task = None
        if fancy:
            self.progress = Progress(console=self.tdenv.console, transient=True, auto_refresh=True, refresh_per_second=2)
        else:
            self.progress = None
    
    def __enter__(self):
        if not self.fancy:
            self.tdenv.uprint(self.title)
        else:
            self.progress.start()
            self.main_task = self.progress.add_task(self.title, start=True, total=self.total)
        return self
    
    def __exit__(self, *args):
        if self.progress is not None:
            self.progress.stop()
    
    def update(self, title: str) -> None:
        if self.fancy:
            self.progress.update(self.main_task, description=title)
        else:
            self.tdenv.DEBUG1(title)
    
    @contextmanager
    def task(self, title: str, total: Optional[int] = None, parent: Optional[str] = None):
        parent = parent or self.main_task
        if self.fancy:
            task = self.progress.add_task(title, start=True, total=total, parent=parent)
        else:
            self.tdenv.DEBUG0(title)
            task = None
        try:
            yield task
        finally:
            if self.fancy:
                self.progress.remove_task(task)
        if task is not None and parent is not None:
            self.progress.update(parent, advance=1)
    
    def bump(self, task, advance: int = 1, description: Optional[str] = None):
        """ Advances the progress of a task by one mark. """
        if self.fancy and task is not None:
            self.progress.update(task, advance=advance, description=description)


def get_timings(started: float, system_count: int, total_station_count: int, *, min_count: int = 100) -> tuple[float, str]:
    """ describes how long it is taking to process each system and station """
    elapsed = time.time() - started
    timings = "sys="
    if system_count >= min_count:
        avg = elapsed / float(system_count) * 1000.0
        timings += f"{avg:5.2f}ms"
    else:
        timings += "..."
    timings += ", stn="
    if total_station_count >= min_count:
        avg = elapsed / float(total_station_count) * 1000.0
        timings += f"{avg:5.2f}ms"
    else:
        timings += "..."
    return elapsed, timings


class ImportPlugin(plugins.ImportPluginBase):
    """Plugin that downloads data from https://spansh.co.uk/dumps."""
    
    pluginOptions = {
        'url': f'URL to download galaxy data from (defaults to {SOURCE_URL})',
        'file': 'Local filename to import galaxy data from; use "-" to load from stdin',
        'maxage': 'Skip all entries older than specified age in days, ex.: maxage=1.5',
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = self.getOption('url')
        self.file = self.getOption('file')
        self.maxage = float(self.getOption('maxage')) if self.getOption('maxage') else None
        assert not (self.url and self.file), 'Provide either url or file, not both'
        if self.file and (self.file != '-'):
            self.file = (Path(self.tdenv.cwDir, self.file)).resolve()
        
        # Bootstrap if DB is missing (legacy behaviour)
        if not Path(self.tdb.dataPath, "TradeDangerous.db").exists():
            ri_path = Path(self.tdb.dataPath, "RareItem.csv")
            rib_path = ri_path.with_suffix(".tmp")
            if ri_path.exists():
                if rib_path.exists():
                    rib_path.unlink()
                ri_path.rename(rib_path)
            cache.buildCache(self.tdb, self.tdenv)
            if ri_path.exists():
                ri_path.unlink()
            if rib_path.exists():
                rib_path.rename(ri_path)
        
        # Transaction / batching controls
        self.need_commit = False
        env_batch = os.environ.get("TD_LISTINGS_BATCH")
        if env_batch:
            try:
                self.commit_rate = int(env_batch)
            except ValueError:
                self.tdenv.WARN(
                    "Invalid TD_LISTINGS_BATCH value %r, falling back to defaults.",
                    env_batch,
                )
                self.commit_rate = None
        else:
            self.commit_rate = None

        if self.commit_rate is None:
            if self.tdb.engine.dialect.name in ("mysql", "mariadb"):
                self.commit_rate = 50 * 1024   # ~50k rows per commit
            else:
                self.commit_rate = 250 * 1024  # ~250k rows per commit (SQLite is fine with big txns)

        self.commit_limit = self.commit_rate
        
        # SQLAlchemy session factory + active session
        self.Session = get_session_factory(self.tdb.engine)
        self.session = self.Session()
        
        # Preload known entities (to dedupe inserts)
        self.known_systems = self.load_known_systems()
        self.known_stations = self.load_known_stations()
        self.known_ships = self.load_known_ships()
        self.known_modules = self.load_known_modules()
        self.known_commodities = self.load_known_commodities()

    def print(self, *args, **kwargs) -> None:
        """ Shortcut to the TradeEnv uprint method. """
        self.tdenv.uprint(*args, **kwargs)
    
    def commit(self, *, force: bool = False) -> None:
        """Perform a commit if required, but try not to do a crazy amount of committing."""
        if not force and not self.need_commit:
            return

        if not force and self.commit_limit > 0:
            self.commit_limit -= 1
            return

        try:
            self.session.commit()
        except SQLAlchemyError as e:
            self.tdenv.WARN(f"Commit failed: {e}")
            self.session.rollback()
            raise

        self.commit_limit = self.commit_rate
        self.need_commit = False

    
    def run(self):
        if not self.tdenv.detail:
            self.print('This will take at least several minutes...')
            self.print('You can increase verbosity (-v) to get a sense of progress')
        
        theme = self.tdenv.theme
        BOLD, CLOSE, DIM, ITALIC = theme.bold, theme.CLOSE, theme.dim, theme.italic  # pylint: disable=invalid-name
        if not self.file:
            url = self.url or SOURCE_URL
            local_mod_time = 0
            self.file = Path(self.tdenv.tmpDir, "galaxy_stations.json")
            if self.file.exists():
                local_mod_time = self.file.stat().st_mtime
            
            headers = {"User-Agent": "Trade-Dangerous", "Accept-Encoding": "identity"}
            try:
                response = requests.head(url, headers=headers, timeout=70)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.tdenv.WARN("Problem with download:\n    URL: {}\n    Error: {}", url, str(e))
                return False
            last_modified = response.headers.get("last-modified")
            dump_mod_time = parsedate_to_datetime(last_modified).timestamp()
            if local_mod_time < dump_mod_time:
                if self.file.exists():
                    self.file.unlink()
                self.print(f'Downloading prices from remote URL: {url}')
                try:
                    transfers.download(self.tdenv, url, self.file)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.tdenv.WARN("Problem with download:\n    URL: {}\n    Error: {}", url, str(e))
                    return False
                self.print(f'Download complete, saved to local file: "{self.file}"')
                os.utime(self.file, (dump_mod_time, dump_mod_time))
        
        sys_desc = f"Importing {ITALIC}spansh{CLOSE} data"
        
        """
        # TODO: find a better way to get the total number of systems
        # A bad way to do it:
        total_systems = 0
        if self.tdenv.detail:
            print('Counting total number of systems...')
        with open(self.file, 'r', encoding='utf8') as stream:
            for system_data in ijson.items(stream, 'item', use_float=True):
                total_systems += 1
                if (not total_systems % 250) and self.tdenv.detail:
                    print(f'Total systems: {total_systems}', end='\r')
        
        if self.tdenv.detail:
            print(f'Total systems: {total_systems}')
        """
        
        # Estimate total number of systems from file size and average bytes per system.
        # Avoids a full pre-pass over the JSON (saves significant time).
        file_size = os.path.getsize(self.file)
        AVG_BYTES_PER_SYSTEM = 220_000  # derived from 17,007,808,433 ÷ 77,365 ≈ 219,803
        estimated_systems = max(1, int(file_size / AVG_BYTES_PER_SYSTEM))

        if self.tdenv.detail:
            self.print(
                f"Estimated {estimated_systems} systems "
                f"from {file_size:,} bytes using {AVG_BYTES_PER_SYSTEM} B/system average"
            )

        
        with Timing() as timing, Progresser(self.tdenv, sys_desc, total=estimated_systems) as progress:
        # with Timing() as timing, Progresser(self.tdenv, sys_desc, total=len(self.known_stations)) as progress:
            system_count = 0
            total_station_count = 0
            total_ship_count = 0
            total_module_count = 0
            total_commodity_count = 0
            
            age_cutoff = timedelta(days=self.maxage) if self.maxage else None
            now = datetime.now()
            started = time.time()
            
            for system, station_iter in self.data_stream():
                upper_sys = system.name.upper()
                
                elapsed, averages = get_timings(started, system_count, total_station_count)
                label = f"{ITALIC}#{system_count:<5d}{CLOSE} {BOLD}{upper_sys:30s}{CLOSE} {DIM}({elapsed:.2f}s, avgs: {averages}){CLOSE}"
                stations = list(station_iter)
                with progress.task(label, total=len(stations)) as sta_task:
                    if system.id not in self.known_systems:
                        self.ensure_system(system, upper_sys)
                    
                    station_count = 0
                    ship_count = 0
                    module_count = 0
                    commodity_count = 0
                    
                    for station, ships, modules, commodities in stations:
                        fq_station_name = f'@{upper_sys}/{station.name}'
                        
                        station_info = self.known_stations.get(station.id)
                        if not station_info or station.modified > station_info[2]:
                            self.ensure_station(station)
                        elif station_info[1] != station.system_id:
                            self.print(f'        |  {station.name:50s}  |  Megaship station moved, updating system')
                            db_station = self.session.query(Station).get(station.id)
                            if db_station:
                                db_station.system_id = station.system_id
                                db_station.modified = datetime.utcnow()
                                self.need_commit = True
                            self.known_stations[station.id] = (
                                station.name,
                                station.system_id,
                                station.modified,
                            )
                        
                        # Ships
                        db_ship_times = {
                            sid: modified
                            for sid, modified in (
                                self.session.query(ShipVendor.ship_id, ShipVendor.modified)
                                .filter(ShipVendor.station_id == station.id)
                                .all()
                            )
                        }

                        ship_entries = []
                        for ship in ships:
                            if ship.id not in self.known_ships:
                                ship = self.ensure_ship(ship)

                            # We're concerned with the ship age, not the station age,
                            # as they each have their own 'modified' times.
                            if age_cutoff and (now - ship.modified) > age_cutoff:
                                if self.tdenv.detail:
                                    self.print(
                                        f'        |  {fq_station_name:50s}  |  Skipping shipyard due to age: {now - ship.modified}, ts: {ship.modified}'
                                    )
                                break

                            db_modified = db_ship_times.get(ship.id)
                            modified_dt = parse_ts(db_modified) if db_modified else None
                            if modified_dt and ship.modified <= modified_dt:
                                # All ships in a station will have the same modified time,
                                # so no need to check the rest if the first is older.
                                if self.tdenv.detail > 2:
                                    self.print(
                                        f'        |  {fq_station_name:50s}  |  Skipping older shipyard data'
                                    )
                                break

                            ship_entries.append(
                                ShipVendor(
                                    ship_id=ship.id,
                                    station_id=station.id,
                                    modified=to_datetime(ship.modified),
                                )
                            )

                        if ship_entries:
                            for entry in ship_entries:
                                self.session.merge(entry)   # ORM upsert
                            self.need_commit = True
                            ship_count += len(ship_entries)
                        
                        # Upgrades
                        db_module_times = {
                            uid: modified
                            for uid, modified in (
                                self.session.query(UpgradeVendor.upgrade_id, UpgradeVendor.modified)
                                .filter(UpgradeVendor.station_id == station.id)
                                .all()
                            )
                        }

                        module_entries = []
                        for module in modules:
                            if module.id not in self.known_modules:
                                module = self.ensure_module(module)

                            # We're concerned with the outfitting age, not the station age,
                            # as they each have their own 'modified' times.
                            if age_cutoff and (now - module.modified) > age_cutoff:
                                if self.tdenv.detail:
                                    self.print(
                                        f'        |  {fq_station_name:50s}  |  Skipping outfitting due to age: {now - station.modified}, ts: {station.modified}'
                                    )
                                break

                            db_modified = db_module_times.get(module.id)
                            modified_dt = parse_ts(db_modified) if db_modified else None
                            if modified_dt and module.modified <= modified_dt:
                                # All modules in a station will have the same modified time,
                                # so no need to check the rest if the first is older.
                                if self.tdenv.detail > 2:
                                    self.print(
                                        f'        |  {fq_station_name:50s}  |  Skipping older outfitting data'
                                    )
                                break

                            module_entries.append(
                                UpgradeVendor(
                                    upgrade_id=module.id,
                                    station_id=station.id,
                                    modified=to_datetime(module.modified),
                                )
                            )

                        if module_entries:
                            for entry in module_entries:
                                self.session.merge(entry)   # ORM upsert
                            self.need_commit = True
                            module_count += len(module_entries)

                        
                        # Items
                        db_commodity_times = {
                            iid: modified
                            for iid, modified in (
                                self.session.query(StationItem.item_id, StationItem.modified)
                                .filter(StationItem.station_id == station.id)
                                .all()
                            )
                        }

                        commodity_entries = []
                        for commodity in commodities:
                            if commodity.id not in self.known_commodities:
                                commodity = self.ensure_commodity(commodity)

                            # We're concerned with the market age, not the station age,
                            # as they each have their own 'modified' times.
                            if age_cutoff and (now - commodity.modified) > age_cutoff:
                                if self.tdenv.detail:
                                    self.print(
                                        f'        |  {fq_station_name:50s}  |  Skipping market due to age: {now - station.modified}, ts: {station.modified}'
                                    )
                                break

                            db_modified = db_commodity_times.get(commodity.id)
                            modified_dt = parse_ts(db_modified) if db_modified else None
                            if modified_dt and commodity.modified <= modified_dt:
                                # All commodities in a station will have the same modified time,
                                # so no need to check the rest if the first is older.
                                if self.tdenv.detail > 2:
                                    self.print(
                                        f'        |  {fq_station_name:50s}  |  Skipping older market data'
                                    )
                                break

                            commodity_entries.append(
                                StationItem(
                                    station_id=station.id,
                                    item_id=commodity.id,
                                    modified=to_datetime(commodity.modified),
                                    demand_price=commodity.sell,
                                    demand_units=commodity.demand,
                                    demand_level=-1,
                                    supply_price=commodity.buy,
                                    supply_units=commodity.supply,
                                    supply_level=-1,
                                    from_live=0,
                                )
                            )

                        if commodity_entries:
                            for entry in commodity_entries:
                                self.session.merge(entry)   # ORM upsert
                            self.need_commit = True
                            commodity_count += len(commodity_entries)

                        # Good time to save data and try to keep the transaction small
                        self.commit()

                        if commodity_count or ship_count or module_count:
                            station_count += 1
                        progress.bump(sta_task)

                
                system_count += 1
                if station_count:
                    total_station_count += station_count
                    total_ship_count += ship_count
                    total_module_count += module_count
                    total_commodity_count += commodity_count
                    if self.tdenv.detail:
                        self.print(
                            f'{system_count:6d}  |  {upper_sys:50s}  |  '
                            f'{station_count:3d} st {commodity_count:5d} co '
                            f'{ship_count:4d} sh {module_count:4d} mo'
                        )
                self.commit()
                
                if not system_count % 25:
                    avg_stations = total_station_count / (system_count or 1)
                    progress.update(
                        f"{sys_desc}{DIM} ({total_station_count}:station:, "
                        f"{system_count}:glowing_star:, {avg_stations:.1f}:station:/:glowing_star:){CLOSE}"
                    )
            
            # Final flush
            self.commit()
            self.session.close()
            self.print(
                f'{timedelta(seconds=int(timing.elapsed))!s}  Done  '
                f'{total_station_count} st {total_commodity_count} co '
                f'{total_ship_count} sh {total_module_count} mo'
            )

        
        with Timing() as timing:
            # Need to make sure cached tables are updated
            self.print('Exporting to cache...')
            for table in (
                "Item", "Station", "System", "StationItem",
                "Ship", "ShipVendor", "Upgrade", "UpgradeVendor"
            ):
                self.print(f'Exporting {table}.csv            ', end='\r')
                csvexport.exportTableToFile(self.session, self.tdenv, table)
            self.print('Exporting TradeDangerous.prices', end='\r')
            cache.regeneratePricesFile(self.session, self.tdenv)
            self.print(f'Cache export completed in {timedelta(seconds=int(timing.elapsed))!s}')
        
        return False

    
    def data_stream(self):
        stream = None
        if self.file == '-':
            self.print('Reading data from stdin')
            stream = sys.stdin
        elif self.file:
            self.print(f'Reading data from local file: "{self.file}"')
            stream = open(self.file, 'r', encoding='utf8')
        return self.ingest_stream(stream)
    
    def load_known_systems(self) -> dict[int, str]:
        """Returns {system_id -> system_name} for all current systems in the database."""
        try:
            return {
                sid: name
                for sid, name in self.session.query(System.system_id, System.name).all()
            }
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no system data yet")
            self.tdenv.DEBUG0(f"load_known_systems query raised {e}")
            return {}

    def load_known_stations(self) -> dict[int, tuple[str, int, float]]:
        """Returns {station_id -> (station_name, system_id, modified)} for all current stations in the database."""
        try:
            return {
                sid: (name, sysid, modified)
                for sid, name, sysid, modified in self.session.query(
                    Station.station_id, Station.name, Station.system_id, Station.modified
                ).all()
            }
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no station data yet")
            self.tdenv.DEBUG0(f"load_known_stations query raised {e}")
            return {}

    def load_known_ships(self) -> dict[int, str]:
        """Returns {ship_id -> name} for all current ships in the database."""
        try:
            return {
                sid: name
                for sid, name in self.session.query(Ship.ship_id, Ship.name).all()
            }
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no ship data yet")
            self.tdenv.DEBUG0(f"load_known_ships query raised {e}")
            return {}

    def load_known_modules(self) -> dict[int, str]:
        """Returns {upgrade_id -> name} for all current modules in the database."""
        try:
            return {
                uid: name
                for uid, name in self.session.query(Upgrade.upgrade_id, Upgrade.name).all()
            }
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no module data yet")
            self.tdenv.DEBUG0(f"load_known_modules query raised {e}")
            return {}

    def load_known_commodities(self) -> dict[int, str]:
        """Returns {fdev_id -> name} for all current commodities in the database."""
        try:
            return {
                fdev_id: name
                for fdev_id, name in self.session.query(Item.fdev_id, Item.name).all()
            }
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no commodity data yet")
            self.tdenv.DEBUG0(f"load_known_commodities query raised {e}")
            return {}

    
    def ensure_system(self, system: SystemDTO, upper_name: str) -> None:
        """Adds a record for a system, and registers the system in the known_systems dict."""
        try:
            self.session.merge(
                System(
                    system_id=system.id,
                    name=system.name,
                    pos_x=system.pos_x,
                    pos_y=system.pos_y,
                    pos_z=system.pos_z,
                    modified=to_datetime(system.modified)
                    if system.modified
                    else datetime.utcnow(),
                )
            )
            self.need_commit = True

            if self.tdenv.detail > 1:
                self.print(
                    f'        |  {upper_name:50s}  |  Added missing system :glowing_star:'
                )

            self.known_systems[system.id] = system.name

        except Exception as e:  # pylint: disable=broad-except
            self.tdenv.WARN(f"Failed to ensure system {system.name} ({system.id}): {e}")
            raise

    
    def ensure_station(self, station: StationDTO) -> None:
        """Adds or updates a station, and registers it in the known_stations dict."""
        try:
            self.session.merge(
                Station(
                    station_id=station.id,
                    system_id=station.system_id,
                    name=station.name,
                    ls_from_star=station.distance,
                    max_pad_size=station.max_pad_size,
                    market=self.bool_yn(station.market),
                    blackmarket=self.bool_yn(station.black_market),
                    shipyard=self.bool_yn(station.shipyard),
                    outfitting=self.bool_yn(station.outfitting),
                    rearm=self.bool_yn(station.rearm),
                    refuel=self.bool_yn(station.refuel),
                    repair=self.bool_yn(station.repair),
                    planetary=self.bool_yn(station.planetary),
                    modified=to_datetime(station.modified),
                    type_id=station.type,
                )
            )
            self.need_commit = True

            note = "Updated" if self.known_stations.get(station.id) else "Added"
            if self.tdenv.detail > 1:
                system_name = self.known_systems[station.system_id]
                upper_sys = system_name.upper()
                fq_station_name = f'@{upper_sys}/{station.name}'
                self.print(
                    f'        |  {fq_station_name:50s}  |  {note} station'
                )

            self.known_stations[station.id] = (
                station.name,
                station.system_id,
                station.modified,
            )

        except Exception as e:  # pylint: disable=broad-except
            self.tdenv.WARN(
                f"Failed to ensure station {station.name} ({station.id}): {e}"
            )
            raise

    
    def ensure_ship(self, ship: ShipDTO):
        """Adds or updates a ship, and registers it in the known_ships dict."""
        try:
            self.session.merge(
                Ship(
                    ship_id=ship.id,
                    name=ship.name,
                )
            )
            self.need_commit = True
            self.known_ships[ship.id] = ship.name
            return ship
        except Exception as e:  # pylint: disable=broad-except
            self.tdenv.WARN(f"Failed to ensure ship {ship.name} ({ship.id}): {e}")
            raise

    def ensure_module(self, module: UpgradeDTO):
        """Adds or updates a module, and registers it in the known_modules dict."""
        try:
            self.session.merge(
                Upgrade(
                    upgrade_id=module.id,
                    name=module.name,
                    class_=module.cls,
                    rating=module.rating,
                    ship=module.ship,
                )
            )
            self.need_commit = True
            self.known_modules[module.id] = module.name
            return module
        except Exception as e:  # pylint: disable=broad-except
            self.tdenv.WARN(f"Failed to ensure module {module.name} ({module.id}): {e}")
            raise

    
    def ensure_commodity(self, commodity: CommodityDTO):
        """Adds or updates a commodity, and registers it in the known_commodities dict."""
        try:
            # Find category by case-insensitive name
            category = (
                self.session.query(Category)
                .filter(Category.name.ilike(commodity.category))
                .first()
            )
            if not category:
                raise RuntimeError(f"Unknown category for commodity {commodity.name}")

            # Insert or update the Item
            self.session.merge(
                Item(
                    item_id=commodity.id,
                    category_id=category.category_id,
                    name=corrections.correctItem(commodity.name),
                    fdev_id=commodity.id,
                )
            )
            self.need_commit = True

            # Update ui_order across all items (preserve existing algorithm)
            items = (
                self.session.query(Item.name, Item.category_id, Item.fdev_id, Item.ui_order)
                .order_by(Item.category_id, Item.name)
                .all()
            )
            cat_id = 0
            ui_order = 1
            self.tdenv.DEBUG0("Updating ui_order data for items.")
            changes = []
            for name, db_cat, fdev_id, db_order in items:
                if db_cat != cat_id:
                    ui_order = 1
                    cat_id = db_cat
                else:
                    ui_order += 1
                if ui_order != db_order:
                    self.tdenv.DEBUG0(f"UI order for {name} ({fdev_id}) needs correction.")
                    changes.append((ui_order, fdev_id))

            if changes:
                for new_order, fdev_id in changes:
                    (
                        self.session.query(Item)
                        .filter(Item.fdev_id == fdev_id)
                        .update({"ui_order": new_order})
                    )
                self.need_commit = True

            self.known_commodities[commodity.id] = commodity.name
            return commodity

        except Exception as e:  # pylint: disable=broad-except
            self.tdenv.WARN(
                f"Failed to ensure commodity {commodity.name} ({commodity.id}): {e}"
            )
            raise
            
    def bool_yn(self, value: Optional[bool]) -> str:
        """ translates a ternary (none, true, false) into the ?/Y/N representation """
        return '?' if value is None else ('Y' if value else 'N')
    
    def ingest_stream(self, stream):
        """Ingest a spansh-style galaxy dump, yielding system-level data."""
        for system_data in ijson.items(stream, 'item', use_float=True):
            if "Shinrarta Dezhra" in system_data.get('name') and self.tdenv.debug:
                with open(Path(self.tdenv.tmpDir, "shin_dez.json"), 'w') as file:
                    import json
                    json.dump(system_data, file, indent=4)
            
            coords = system_data.get('coords', {})
            yield (
                SystemDTO(
                    id=system_data.get('id64'),
                    name=system_data.get('name', 'Unnamed').strip(),
                    pos_x=coords.get('x', 999999),
                    pos_y=coords.get('y', 999999),
                    pos_z=coords.get('z', 999999),
                    modified=parse_ts(system_data.get('date')),
                ),
                ingest_stations(system_data),
            )



def ingest_stations(system_data):
    """Ingest system-level data, yielding station-level data."""
    sys_id = system_data.get('id64')
    targets = [system_data, *system_data.get('bodies', ())]
    for target in targets:
        for station_data in target.get('stations', ()):
            services = set(station_data.get('services', ()))
            shipyard = station_data.get('shipyard', {}) if 'Shipyard' in services else None
            outfitting = station_data.get('outfitting', {}) if 'Outfitting' in services else None
            market = station_data.get('market', {}) if 'Market' in services else None

            if not shipyard and not outfitting and not market:
                continue

            landing_pads = station_data.get('landingPads', {})
            max_pad_size = '?'
            if landing_pads.get('large'):
                max_pad_size = 'L'
            elif landing_pads.get('medium'):
                max_pad_size = 'M'
            elif landing_pads.get('small'):
                max_pad_size = 'S'

            station_type = STATION_TYPE_MAP.get(station_data.get('type'))
            yield (
                StationDTO(
                    id=station_data.get('id'),
                    system_id=sys_id,
                    name=station_data.get('name', 'Unnamed').strip(),
                    distance=station_data.get('distanceToArrival', 999999),
                    max_pad_size=max_pad_size,
                    market='Market' in services,
                    black_market='Black Market' in services,
                    shipyard='Shipyard' in services,
                    outfitting='Outfitting' in services,
                    rearm='Restock' in services,
                    refuel='Refuel' in services,
                    repair='Repair' in services,
                    planetary=station_type[1] if station_type else False,
                    type=station_type[0] if station_type else 0,
                    modified=parse_ts(station_data.get('updateTime')),
                ),
                ingest_shipyard(shipyard),
                ingest_outfitting(outfitting),
                ingest_market(market),
            )

def ingest_shipyard(shipyard):
    """Ingest station-level shipyard data, yielding ShipDTOs."""
    if not shipyard or not shipyard.get('ships'):
        return None
    for ship in shipyard['ships']:
        yield ShipDTO(
            id=ship.get('shipId'),
            name=ship.get('name'),
            modified=parse_ts(shipyard.get('updateTime')),
        )

def ingest_outfitting(outfitting):
    """Ingest station-level outfitting data, yielding UpgradeDTOs."""
    if not outfitting or not outfitting.get('modules'):
        return None
    for module in outfitting['modules']:
        yield UpgradeDTO(
            id=module.get('moduleId'),
            name=module.get('name'),
            cls=module.get('class'),
            rating=module.get('rating'),
            ship=module.get('ship'),
            modified=parse_ts(outfitting.get('updateTime')),
        )

def ingest_market(market):
    """Ingest station-level market data, yielding CommodityDTOs."""
    if not market or not market.get('commodities'):
        return None
    for commodity in market['commodities']:
        yield CommodityDTO(
            id=commodity.get('commodityId'),
            name=commodity.get('name', 'Unnamed'),
            category=commodity.get('category', 'Uncategorised'),
            demand=commodity.get('demand', 0),
            supply=commodity.get('supply', 0),
            sell=commodity.get('sellPrice', 0),
            buy=commodity.get('buyPrice', 0),
            modified=parse_ts(market.get('updateTime')),
        )

def parse_ts(ts):
    """Parses Spansh timestamps to datetime (UTC, microsecond=0)."""
    if ts is None:
        return None
    if ts.endswith('+00'):
        ts = ts[:-3]
    if '.' not in ts:
        ts += '.0'
    return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f').replace(microsecond=0)

