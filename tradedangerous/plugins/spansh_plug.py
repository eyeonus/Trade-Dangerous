""" Plugin for importing data from spansh """
from __future__ import annotations

from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from rich.progress import Progress

from .. import plugins, cache, transfers, csvexport, corrections

import sqlite3
import sys
import time
import typing

import ijson

if sys.version_info.major == 3 and sys.version_info.minor >= 10:
    from dataclasses import dataclass
else:
    dataclass = False  # pylint: disable=invalid-name

if typing.TYPE_CHECKING:
    from typing import Any, Optional
    from collections.abc import Iterable
    from .. tradeenv import TradeEnv

SOURCE_URL = 'https://downloads.spansh.co.uk/galaxy_stations.json'

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
    'Settlement': [25, True],            # odyssey settlements
}

if dataclass:
    # Dataclass with slots is considerably cheaper and faster than namedtuple
    # but is only reliably introduced in 3.10+
    @dataclass(slots=True)
    class System:
        id:             int
        name:           str
        pos_x:          float
        pos_y:          float
        pos_z:          float
        modified:       float | None
    
    @dataclass(slots=True)
    class Station:      # pylint: disable=too-many-instance-attributes
        id:             int
        system_id:      int
        name:           str
        distance:       float
        max_pad_size:   str
        market:         str     # should be Optional[bool]
        black_market:   str     # should be Optional[bool]
        shipyard:       str     # should be Optional[bool]
        outfitting:     str     # should be Optional[bool]
        rearm:          str     # should be Optional[bool]
        refuel:         str     # should be Optional[bool]
        repair:         str     # should be Optional[bool]
        planetary:      str     # should be Optional[bool]
        type:           int     # station type
        modified:       float
    
    @dataclass(slots=True)
    class Ship:
        id:             int
        name:           str
        modified:       float
    
    @dataclass(slots=True)
    class Module:
        id:             int
        name:           str
        cls:            int
        rating:         str
        ship:           str
        modified:       float
    
    @dataclass(slots=True)
    class Commodity:
        id:             int
        name:           str
        category:       str
        demand:         int
        supply:         int
        sell:           int
        buy:            int
        modified:       float

else:
    System = namedtuple('System', 'id,name,pos_x,pos_y,pos_z,modified')
    Station = namedtuple('Station',
                         'id,system_id,name,distance,max_pad_size,'
                         'market,black_market,shipyard,outfitting,rearm,refuel,repair,planetary,type,modified')
    Ship = namedtuple('Ship', 'id,name,modified')
    Module = namedtuple('Module', 'id,name,cls,rating,ship,modified')
    Commodity = namedtuple('Commodity', 'id,name,category,demand,supply,sell,buy,modified')


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
    """Plugin that downloads data from https://spansh.co.uk/dumps.
    """
    
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
        
        self.need_commit = False
        self.cursor = self.tdb.getDB().cursor()
        self.commit_rate = 200
        self.commit_limit = self.commit_rate
        
        self.known_systems = self.load_known_systems()
        self.known_stations = self.load_known_stations()
        self.known_ships = self.load_known_ships()
        self.known_modules = self.load_known_modules()
        self.known_commodities = self.load_known_commodities()
    
    def print(self, *args, **kwargs) -> None:
        """ Shortcut to the TradeEnv uprint method. """
        self.tdenv.uprint(*args, **kwargs)
    
    def commit(self, *, force: bool = False) -> None:
        """ Perform a commit if required, but try not to do a crazy amount of committing. """
        if not force and not self.need_commit:
            return
        
        if not force and self.commit_limit > 0:
            self.commit_limit -= 1
            return
        
        db = self.tdb.getDB()
        db.commit()
        self.cursor = db.cursor()
        
        self.commit_limit = self.commit_rate
        self.need_commit = False
    
    def run(self):
        if not self.tdenv.detail:
            self.print('This will take at least several minutes...')
            self.print('You can increase verbosity (-v) to get a sense of progress')
        
        theme = self.tdenv.theme
        BOLD, CLOSE, DIM, ITALIC = theme.bold, theme.CLOSE, theme.dim, theme.italic  # pylint: disable=invalid-name
        # TODO: don't download file if local copy is not older
        # see eddblink_plug.download_file()
        if not self.file:
            url = self.url or SOURCE_URL
            self.print(f'Downloading prices from remote URL: {url}')
            self.file = Path(self.tdenv.tmpDir, "galaxy_stations.json")
            transfers.download(self.tdenv, url, self.file)
            self.print(f'Download complete, saved to local file: "{self.file}"')
        
        sys_desc = f"Importing {ITALIC}spansh{CLOSE} data"
        
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
        
        with Timing() as timing, Progresser(self.tdenv, sys_desc, total=total_systems) as progress:
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
                            self.execute("UPDATE Station SET system_id = ? WHERE station_id = ?", station.system_id, station.id, commitable=True)
                            self.known_stations[station.id] = (station.name, station.system_id, station.modified)
                        
                        # Ships
                        ship_entries = []
                        db_ship_times = dict(self.execute("SELECT ship_id, modified FROM ShipVendor WHERE station_id = ?", station.id))
                        
                        for ship in ships:
                            if ship.id not in self.known_ships:
                                ship = self.ensure_ship(ship)
                            
                            # We're concerned with the ship age, not the station age,
                            # as they each have their own 'modified' times.
                            if age_cutoff and (now - ship.modified) > age_cutoff:
                                if self.tdenv.detail:
                                    self.print(f'        |  {fq_station_name:50s}  |  Skipping shipyard due to age: {now - ship.modified}, ts: {ship.modified}')
                                break
                            db_modified = db_ship_times.get(ship.id)
                            modified = parse_ts(db_modified) if db_modified else None
                            if modified and ship.modified <= modified:
                                # All ships in a station will have the same modified time,
                                # so no need to check the rest if the first is older.
                                if self.tdenv.detail > 2:
                                    self.print(f'        |  {fq_station_name:50s}  |  Skipping older shipyard data')
                                break
                            
                            ship_entries.append((ship.id, station.id, ship.modified))
                        if ship_entries:
                            self.executemany("""INSERT OR REPLACE INTO ShipVendor (
                                ship_id, station_id, modified
                            ) VALUES (
                                ?, ?, IFNULL(?, CURRENT_TIMESTAMP)
                            )""", ship_entries, commitable=True)
                            ship_count += len(ship_entries)
                        
                        # Upgrades
                        module_entries = []
                        db_module_times = dict(self.execute("SELECT upgrade_id, modified FROM UpgradeVendor WHERE station_id = ?", station.id))
                        
                        for module in modules:
                            if module.id not in self.known_modules:
                                module = self.ensure_module(module)
                            
                            # We're concerned with the outfitting age, not the station age,
                            # as they each have their own 'modified' times.
                            if age_cutoff and (now - module.modified) > age_cutoff:
                                if self.tdenv.detail:
                                    self.print(f'        |  {fq_station_name:50s}  |  Skipping outfitting due to age: {now - station.modified}, ts: {station.modified}')
                                break
                            db_modified = db_module_times.get(module.id)
                            modified = parse_ts(db_modified) if db_modified else None
                            if modified and module.modified <= modified:
                                # All modules in a station will have the same modified time,
                                # so no need to check the rest if the fist is older.
                                if self.tdenv.detail > 2:
                                    self.print(f'        |  {fq_station_name:50s}  |  Skipping older outfitting data')
                                break
                            
                            module_entries.append((module.id, station.id, module.modified))
                        if module_entries:
                            self.executemany("""INSERT OR REPLACE INTO UpgradeVendor (
                                upgrade_id, station_id, modified
                            ) VALUES (
                                ?, ?, IFNULL(?, CURRENT_TIMESTAMP)
                            )""", module_entries, commitable=True)
                            module_count += len(module_entries)
                        
                        # Items
                        commodity_entries = []
                        db_commodity_times = dict(self.execute("SELECT item_id, modified FROM StationItem WHERE station_id = ?", station.id))
                        
                        for commodity in commodities:
                            if commodity.id not in self.known_commodities:
                                commodity = self.ensure_commodity(commodity)
                            
                            # We're concerned with the market age, not the station age,
                            # as they each have their own 'modified' times.
                            if age_cutoff and (now - commodity.modified) > age_cutoff:
                                if self.tdenv.detail:
                                    self.print(f'        |  {fq_station_name:50s}  |  Skipping market due to age: {now - station.modified}, ts: {station.modified}')
                                break
                            
                            db_modified = db_commodity_times.get(commodity.id)
                            modified = parse_ts(db_modified) if db_modified else None
                            if modified and commodity.modified <= modified:
                                # All commodities in a station will have the same modified time,
                                # so no need to check the rest if the fist is older.
                                if self.tdenv.detail > 2:
                                    self.print(f'        |  {fq_station_name:50s}  |  Skipping older market data')
                                break
                            commodity_entries.append((station.id, commodity.id, commodity.modified,
                                                      commodity.sell, commodity.demand, -1,
                                                      commodity.buy, commodity.supply, -1, 0))
                        if commodity_entries:
                            self.executemany("""INSERT OR REPLACE INTO StationItem (
                                station_id, item_id, modified,
                                demand_price, demand_units, demand_level,
                                supply_price, supply_units, supply_level, from_live
                            ) VALUES (
                                ?, ?, IFNULL(?, CURRENT_TIMESTAMP),
                                ?, ?, ?,
                                ?, ?, ?, ?
                            )""", commodity_entries, commitable=True)
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
                    progress.update(f"{sys_desc}{DIM} ({total_station_count}:station:, {system_count}:glowing_star:, {avg_stations:.1f}:station:/:glowing_star:){CLOSE}")
            
            self.commit()
            self.tdb.close()
            self.print(
                f'{timedelta(seconds=int(timing.elapsed))!s}  Done  '
                f'{total_station_count} st {total_commodity_count} co '
                f'{total_ship_count} sh {total_module_count} mo'
            )
        
        with Timing() as timing:
            # Need to make sure cached tables are updated
            self.print('Exporting to cache...')
            for table in ("Item", "Station", "System", "StationItem", "Ship", "ShipVendor", "Upgrade", "UpgradeVendor"):
                self.print(f'Exporting {table}.csv            ', end='\r')
                csvexport.exportTableToFile(self.tdb, self.tdenv, table)
            self.print('Exporting TradeDangerous.prices', end='\r')
            cache.regeneratePricesFile(self.tdb, self.tdenv)
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
    
    def execute(self, query: str, *params, commitable: bool = False) -> sqlite3.Cursor:
        """ helper method that performs retriable queries and marks the transaction 
            as needing to commit if the query is commitable."""
        if commitable:
            self.need_commit = True
        attempts = 5
        while True:
            try:
                return self.cursor.execute(query, params)
            except sqlite3.OperationalError as ex:
                if "no transaction is active" in str(ex):
                    self.print(f"no transaction for {query}")
                    raise
                if not attempts:
                    raise
                attempts -= 1
                self.print(f'Retrying query \'{query}\': {ex!s}')
                time.sleep(1)
    
    def executemany(self, query: str, data: Iterable[Any], *, commitable: bool = False) -> sqlite3.Cursor:
        """ helper method that performs retriable queries and marks the transaction as needing to commit
            if the query is commitable."""
        if commitable:
            self.need_commit = True
        attempts = 5
        while True:
            try:
                return self.cursor.executemany(query, data)
            except sqlite3.OperationalError as ex:
                if "no transaction is active" in str(ex):
                    self.print(f"no transaction for {query}")
                    raise
                if not attempts:
                    raise
                attempts -= 1
                self.print(f'Retrying query \'{query}\': {ex!s}')
                time.sleep(1)
    
    def load_known_systems(self) -> dict[int, str]:
        """ Returns a dictionary of {system_id -> system_name} for all current systems in the database. """
        try:
            return dict(self.cursor.execute('SELECT system_id, name FROM System'))
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no system data yet")
            self.tdenv.DEBUG0(f"load_known_systems query raised {e}")
            return {}
    
    def load_known_stations(self) -> dict[int, tuple[str, int, float]]:
        """ Returns a dictionary of {station_id -> (station_name, system_id, modified)} for all current stations in the database. """
        try:
            return {cols[0]: (cols[1], cols[2], parse_ts(cols[3])) for cols in self.cursor.execute('SELECT station_id, name, system_id, modified FROM Station')}
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no station data yet")
            self.tdenv.DEBUG0(f"load_known_stations query raised {e}")
            return {}
    
    def load_known_ships(self):
        """ Returns a dictionary of {ship_id -> name} for all current ships in the database. """
        try:
            return dict(self.cursor.execute('SELECT ship_id, name FROM Ship'))
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no ship data yet")
            self.tdenv.DEBUG0(f"load_known_ships query raised {e}")
            return {}
    
    def load_known_modules(self):
        """ Returns a dictionary of {upgrade_id -> name} for all current modules in the database. """
        try:
            return dict(self.cursor.execute('SELECT upgrade_id, name FROM Upgrade'))
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no module data yet")
            self.tdenv.DEBUG0(f"load_known_modules query raised {e}")
            return {}
    
    def load_known_commodities(self):
        """ Returns a dictionary of {fdev_id -> name} for all current commodities in the database. """
        try:
            return dict(self.cursor.execute('SELECT fdev_id, name FROM Item'))
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no commodity data yet")
            self.tdenv.DEBUG0(f"load_known_commodities query raised {e}")
            return {}
    
    def ensure_system(self, system: System, upper_name: str) -> None:
        """ Adds a record for a system, and registers the system in the known_systems dict. """
        self.execute(
            '''
            INSERT INTO System (system_id, name, pos_x, pos_y, pos_z, modified) VALUES (?, ?, ?, ?, ?, ?)
            ''',
            system.id, system.name, system.pos_x, system.pos_y, system.pos_z, system.modified,
            commitable=True,
        )
        if self.tdenv.detail > 1:
            self.print(f'        |  {upper_name:50s}  |  Added missing system :glowing_star:')
        self.known_systems[system.id] = system.name
    
    def ensure_station(self, station: Station) -> None:
        """ Adds a record for a station, and registers the station in the known_stations dict. """
        self.execute(
            '''
            INSERT OR REPLACE INTO Station (
                system_id, station_id, name,
                ls_from_star, max_pad_size,
                market, blackmarket, shipyard, outfitting,
                rearm, refuel, repair,
                planetary,
                modified,
                type_id
            )
            VALUES (
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?,
                ?,
                ?
            )
            ''',
            station.system_id,
            station.id,
            station.name,
            station.distance,
            station.max_pad_size,
            self.bool_yn(station.market),
            self.bool_yn(station.black_market),
            self.bool_yn(station.shipyard),
            self.bool_yn(station.outfitting),
            self.bool_yn(station.rearm),
            self.bool_yn(station.refuel),
            self.bool_yn(station.repair),
            self.bool_yn(station.planetary),
            station.modified,
            station.type,
            commitable=True,
        )
        note = "Updated" if self.known_stations.get(station.id) else "Added"
        if self.tdenv.detail > 1:
            system_name = self.known_systems[station.system_id]
            upper_sys = system_name.upper()
            fq_station_name = f'@{upper_sys}/{station.name}'
            self.print(f'        |  {fq_station_name:50s}  |  {note} station')
        self.known_stations[station.id] = (station.name, station.system_id, station.modified)
    
    def ensure_ship(self, ship: Ship):
        """ Adds a record for a ship, and registers the ship in the known_ships dict. """
        self.execute(
            '''
            INSERT INTO Ship (ship_id, name) VALUES (?, ?)
            ''',
            ship.id, ship.name,
            commitable=True,
        )
        self.known_ships[ship.id] = ship.name
        
        return ship
    
    def ensure_module(self, module: Module):
        """ Adds a record for a module, and registers the module in the known_modules dict. """
        self.execute(
            '''
            INSERT INTO Upgrade (upgrade_id, name, class, rating, ship) VALUES (?, ?, ?, ?, ?)
            ''',
            module.id, module.name, module.cls, module.rating, module.ship,
            commitable=True,
        )
        self.known_modules[module.id] = module.name
        
        return module
    
    def ensure_commodity(self, commodity: Commodity):
        """ Adds a record for a commodity and registers the commodity in the known_commodities dict. """
        self.execute(
            '''
            INSERT INTO Item (item_id, category_id, name, fdev_id)
            VALUES (?, (SELECT category_id FROM Category WHERE upper(name) = ?), ?, ?)
            ''',
            commodity.id,
            commodity.category.upper(),
            corrections.correctItem(commodity.name),
            commodity.id,
            commitable=True,
        )
        
        # Need to update ui_order
        temp = self.execute("""SELECT name, category_id, fdev_id, ui_order
                        FROM Item
                        ORDER BY category_id, name
                        """)
        cat_id = 0
        ui_order = 1
        self.tdenv.DEBUG0("Updating ui_order data for items.")
        changes = []
        for name, db_cat, fdev_id, db_order in temp:
            if db_cat != cat_id:
                ui_order = 1
                cat_id = db_cat
            else:
                ui_order += 1
            if ui_order != db_order:
                self.tdenv.DEBUG0(f"UI order for {name} ({fdev_id}) needs correction.")
                changes += [(ui_order, fdev_id)]
        
        if changes:
            self.executemany(
                "UPDATE Item SET ui_order = ? WHERE fdev_id = ?",
                changes,
                commitable=True
            )
        
        self.known_commodities[commodity.id] = commodity.name
        
        return commodity
    
    def bool_yn(self, value: Optional[bool]) -> str:
        """ translates a ternary (none, true, false) into the ?/Y/N representation """
        return '?' if value is None else ('Y' if value else 'N')
    
    def ingest_stream(self, stream):
        """Ingest a spansh-style galaxy dump, yielding system-level data."""
        for system_data in ijson.items(stream, 'item', use_float=True):
            if "Shinrarta Dezhra" in system_data.get('name') and self.tdenv.debug:
                with open(Path(self.tdenv.tmpDir, "shin_dez.json"), 'w') as file:
                    # file.write(system_data)
                    import json
                    json.dump(system_data, file, indent=4)
            
            coords = system_data.get('coords', {})
            yield (
                System(
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
            shipyard = None
            if 'Shipyard' in services:
                shipyard = station_data.get('shipyard', {})
            outfitting = None
            if 'Outfitting' in services:
                outfitting = station_data.get('outfitting', {})
            market = None
            if 'Market' in services:
                market = station_data.get('market', {})
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
                Station(
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
    """Ingest station-level market data, yielding commodities."""
    if not shipyard or not shipyard.get('ships'):
        return None
    for ship in shipyard['ships']:
        yield Ship(
            id=ship.get('shipId'),
            name=ship.get('name'),
            modified=parse_ts(shipyard.get('updateTime'))
        )

def ingest_outfitting(outfitting):
    """Ingest station-level market data, yielding commodities."""
    if not outfitting or not outfitting.get('modules'):
        return None
    for module in outfitting['modules']:
        yield Module(
            id=module.get('moduleId'),
            name=module.get('name'),
            cls=module.get('class'),
            rating=module.get('rating'),
            ship=module.get('ship'),
            modified=parse_ts(outfitting.get('updateTime'))
        )

def ingest_market(market):
    """Ingest station-level market data, yielding commodities."""
    if not market or not market.get('commodities'):
        return None
    for commodity in market['commodities']:
        yield Commodity(
            id=commodity.get('commodityId'),
            name=commodity.get('name', 'Unnamed'),
            category=commodity.get('category', 'Uncategorised'),
            demand=commodity.get('demand', 0),
            supply=commodity.get('supply', 0),
            sell=commodity.get('sellPrice', 0),
            buy=commodity.get('buyPrice', 0),
            modified=parse_ts(market.get('updateTime'))
        )

def parse_ts(ts):
    if ts is None:
        return None
    if ts.endswith('+00'):
        ts = ts[:-3]
    if '.' not in ts:
        ts += '.0'
    return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f').replace(microsecond=0)
