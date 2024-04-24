from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import sys
import time
import typing
from collections import namedtuple
if sys.version_info.major == 3 and sys.version_info.minor >= 10:
    from dataclasses import dataclass
else:
    dataclass = False  # pylint: disable=invalid-name

from rich.progress import Progress
import ijson
import sqlite3

from .. import plugins, cache, transfers, csvexport, corrections

if typing.TYPE_CHECKING:
    from typing import Any, Iterable, Optional
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
    'Settlement': [25, True],           # odyssey settlements
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
        """ If the timing has finish, calculates the elapsed time. """
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


def get_timings(started: float, system_count: int, total_station_count: int, *, min_count: int = 100) -> str:
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
        'url':  f'URL to download galaxy data from (defaults to {SOURCE_URL})',
        'file': 'Local filename to import galaxy data from; use "-" to load from stdin',
        'maxage': 'Skip all entries older than specified age in days, ex.: maxage=1.5',
        'listener': 'For use by TD-listener, prevents updating cache from generated prices file',
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = self.getOption('url')
        self.file = self.getOption('file')
        self.maxage = float(self.getOption('maxage')) if self.getOption('maxage') else None
        self.listener = self.getOption('listener')
        assert not (self.url and self.file), 'Provide either url or file, not both'
        if self.file and (self.file != '-'):
            self.file = (Path(self.tdenv.cwDir, self.file)).resolve()
        if not Path(self.tdb.dataPath, "TradeDangerous.prices").exists():
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
        self.known_commodities = self.load_known_commodities()
    
    def print(self, *args, **kwargs) -> None:
        """ Shortcut to the TradeEnv uprint method. """
        self.tdenv.uprint(*args, **kwargs)
    
    def commit(self, *, force: bool = False) -> None:
        """ Perform a commit if required, but try not to do a crazy amount of committing. """
        if not force and not self.need_commit:
            return self.cursor
        
        if not force and self.commit_limit > 0:
            self.commit_limit -= 1
            return self.cursor
        
        db = self.tdb.getDB()
        db.commit()
        self.cursor = db.cursor()
        
        self.commit_limit = self.commit_rate
        self.need_commit = False
    
    def run(self) -> bool:
        if not self.tdenv.detail:
            self.print('This will take at least several minutes...')
            self.print('You can increase verbosity (-v) to get a sense of progress')
        
        theme = self.tdenv.theme
        BOLD, CLOSE, DIM, ITALIC = theme.bold, theme.CLOSE, theme.dim, theme.italic  # pylint: disable=invalid-name
        
        sys_desc = f"Importing {ITALIC}spansh{CLOSE} data"
        with Timing() as timing, Progresser(self.tdenv, sys_desc, total=len(self.known_systems)) as progress:
            system_count = 0
            total_station_count = 0
            total_commodity_count = 0
            
            age_cutoff = timedelta(days=self.maxage) if self.maxage else None
            now = datetime.now()
            started = time.time()
            
            for system, station_iter in self.data_stream():
                upper_sys = system.name.upper()
                
                elapsed, averages = get_timings(started, system_count, total_station_count)
                label = f"{ITALIC}#{system_count:<5d}{CLOSE} {BOLD}{upper_sys:30s}{CLOSE} {DIM}({elapsed:.2f}s, avgs: {averages}){CLOSE}"
                stations = list(station_iter)
                with progress.task(label, total=len(stations)) as sys_task:
                    if system.id not in self.known_systems:
                        self.ensure_system(system, upper_sys)
                    
                    station_count = 0
                    commodity_count = 0
                    
                    for station, commodities in stations:
                        fq_station_name = f'@{upper_sys}/{station.name}'
                        if age_cutoff and (now - station.modified) > age_cutoff:
                            if self.tdenv.detail:
                                self.print(f'        |  {fq_station_name:50s}  |  Skipping station due to age: {now - station.modified}, ts: {station.modified}')
                            progress.bump(sys_task)
                            continue
                        
                        station_info = self.known_stations.get(station.id)
                        if not station_info:
                            self.ensure_station(station)
                        elif station_info[1] != station.system_id:
                            self.print(f'        |  {station.name:50s}  |  Megaship station moved, updating system')
                            self.execute("UPDATE Station SET system_id = ? WHERE station_id = ?", station.system_id, station.id, commitable=True)
                            self.known_stations[station.id] = (station.name, station.system_id)
                        
                        items = []
                        db_times = dict(self.execute("SELECT item_id, modified FROM StationItem WHERE station_id = ?", station.id))
                        
                        for commodity in commodities:
                            if commodity.id not in self.known_commodities:
                                commodity = self.ensure_commodity(commodity)
                            
                            db_modified = db_times.get(commodity.id)
                            modified = parse_ts(db_modified) if db_modified else None
                            if modified and commodity.modified <= modified:
                                # All commodities in a station will have the same modified time,
                                # so no need to check the rest if the fist is older.
                                if self.tdenv.detail:
                                    self.print(f'        |  {fq_station_name:50s}  |  Skipping older commodity data')
                                break
                            items.append((station.id, commodity.id, commodity.modified,
                                commodity.sell, commodity.demand, -1,
                                commodity.buy, commodity.supply, -1, 0))
                        if items:
                            self.executemany("""INSERT OR REPLACE INTO StationItem (
                                station_id, item_id, modified,
                                demand_price, demand_units, demand_level,
                                supply_price, supply_units, supply_level, from_live
                            ) VALUES (
                                ?, ?, IFNULL(?, CURRENT_TIMESTAMP),
                                ?, ?, ?,
                                ?, ?, ?, ?
                            )""", items, commitable=True)
                            commodity_count += len(items)
                            # Good time to save data and try to keep the transaction small
                            self.commit()
                        
                        if commodity_count:
                            station_count += 1
                        progress.bump(sys_task)
                    
                    if station_count:
                        system_count += 1
                        total_station_count += station_count
                        total_commodity_count += commodity_count
                        if self.tdenv.detail:
                            self.print(
                                f'{system_count:6d}  |  {upper_sys:50s}  |  '
                                f'{station_count:3d} st  {commodity_count:6d} co'
                            )
                    self.commit()
                    
                    if system_count % 25 == 1:
                        avg_stations = total_station_count / (system_count or 1)
                        progress.update(f"{sys_desc}{DIM} ({total_station_count}:station:, {avg_stations:.1f}per:glowing_star:){CLOSE}")
            
            self.commit()
            
            # Need to make sure cached tables are updated, if changes were made
            # if self.update_cache:
            #     for table in [ "Item", "Station", "System" ]:
            #         _, path = csvexport.exportTableToFile( self.tdb, self.tdenv, table )
            
            self.tdb.close()
            
            # Need to make sure cached tables are updated
            for table in ("Item", "Station", "System", "StationItem"):
                # _, path =
                csvexport.exportTableToFile(self.tdb, self.tdenv, table)
            
            self.print(
                f'{timedelta(seconds=int(timing.elapsed))!s}  Done  '
                f'{total_station_count} st  {total_commodity_count} co'
            )
        
        with Timing() as timing:
            self.print('Exporting to cache...')
            cache.regeneratePricesFile(self.tdb, self.tdenv)
            self.print(f'Cache export completed in {timedelta(seconds=int(timing.elapsed))!s}')
        
        return False
    
    def data_stream(self):
        if not self.file:
            url = self.url or SOURCE_URL
            self.print(f'Downloading prices from remote URL: {url}')
            self.file = Path(self.tdenv.tmpDir, "galaxy_stations.json")
            transfers.download(self.tdenv, url, self.file)
            self.print(f'Download complete, saved to local file: "{self.file}"')
        
        if self.file == '-':
            self.print('Reading prices from stdin')
            stream = sys.stdin
        elif self.file:
            self.print(f'Reading prices from local file: "{self.file}"')
            stream = open(self.file, 'r', encoding='utf8')
        return ingest_stream(stream)
    
    def categorise_commodities(self, commodities):
        categories = {}
        for commodity in commodities:
            categories.setdefault(commodity.category, []).append(commodity)
        return categories
    
    def execute(self, query: str, *params, commitable: bool = False) -> Optional[sqlite3.Cursor]:
        """ helper method that performs retriable queries and marks the transaction as needing to commit
            if the query is commitable."""
        if commitable:
            self.need_commit = True
        attempts = 5
        while True:
            try:
                return self.cursor.execute(query, params)
            except sqlite3.OperationalError as ex:
                if "no transaction is active" in str(ex):
                    self.print(f"no transaction for {query}")
                    return
                if not attempts:
                    raise
                attempts -= 1
                self.print(f'Retrying query \'{query}\': {ex!s}')
                time.sleep(1)
    
    def executemany(self, query: str, data: Iterable[Any], *, commitable: bool = False) -> Optional[sqlite3.Cursor]:
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
                    return
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
    
    def load_known_stations(self) -> dict[int, tuple[str, int]]:
        """ Returns a dictionary of {station_id -> (station_name, system_id)} for all current stations in the database. """
        try:
            return {cols[0]: (cols[1], cols[2]) for cols in self.cursor.execute('SELECT station_id, name, system_id FROM Station')}
        except Exception as e:  # pylint: disable=broad-except
            self.print("[purple]:thinking_face:Assuming no station data yet")
            self.tdenv.DEBUG0(f"load_known_stations query raised {e}")
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
            INSERT INTO Station (
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
        if self.tdenv.detail > 1:
            self.print(f'        |  {station.name:50s}  |  Added missing station')
        self.known_stations[station.id] = (station.name, station.system_id)
    
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


def ingest_stream(stream):
    """Ingest a spansh-style galaxy dump, yielding system-level data."""
    for system_data in ijson.items(stream, 'item', use_float=True):
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
            if 'Market' not in services:
                continue
            market = station_data.get('market', {})
            if not market.get('commodities'):
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
                    market=True,
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
                ingest_market(market),
            )


def ingest_market(market):
    """Ingest station-level market data, yielding commodities."""
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
