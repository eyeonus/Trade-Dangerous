import os
import sys
import time
from datetime import datetime, timedelta
from collections import namedtuple
from pathlib import Path

import requests
import simdjson
import sqlite3

from .. import plugins, cache, fs, transfers, csvexport, corrections

SOURCE_URL = 'https://downloads.spansh.co.uk/galaxy_stations.json'

STATION_TYPE_MAP = {
    'None' : [0, False],
    'Outpost' : [1, False],
    'Coriolis Starport' : [2, False],
    'Ocellus Starport' : [3, False],
    'Orbis Starport' : [4, False],
    'Planetary Outpost' : [11, True],
    'Planetary Port' : [12, True],
    'Mega ship' : [13, False],
    'Asteroid base' : [14, False],
    'Drake-Class Carrier': [24, False],  # fleet carriers
    'Settlement': [25, True],           # odyssey settlements
}

System = namedtuple('System', 'id,name,pos_x,pos_y,pos_z,modified')
Station = namedtuple('Station', 'id,name,distance,max_pad_size,market,black_market,shipyard,outfitting,rearm,refuel,repair,planetary,type,modified')
Commodity = namedtuple('Commodity', 'id,name,category,demand,supply,sell,buy,modified')


class Timing:

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
    def elapsed(self):
        if self.start_ts is None:
            return None
        return (self.end_ts or time.perf_counter()) - self.start_ts

    @property
    def is_finished(self):
        return self.end_ts is not None


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
            self.file = (Path(self.tdenv.cwDir) / self.file).resolve()
        if not (self.tdb.dataPath / Path("TradeDangerous.prices")).exists():
            ri_path = self.tdb.dataPath / Path("RareItem.csv")
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
        
        # self.known_space = self.load_known_space()
        self.known_systems = self.load_known_systems()
        self.known_stations = self.load_known_stations()
        self.known_commodities = self.load_known_commodities()

    def print(self, *args, **kwargs):
        return self.tdenv.uprint(*args, **kwargs)

    def run(self):
        # fs.ensurefolder(self.tdenv.tmpDir)
        # filePath = self.tdenv.tmpDir / Path("spansh.prices")
        if not self.tdenv.detail:
            self.print('This will take at least several minutes...')
            self.print('You can increase verbosity (-v) to get a sense of progress')
        with Timing() as timing:
        # with open(filePath, 'w') as f, Timing() as timing:
        #     self.print(f'Writing prices to {filePath}')
        #     f.write('# Generated from spansh galaxy data\n')
        #     f.write(f'# Source: {self.file or self.url}\n')
        #     f.write('#\n')
        #     f.write((
        #         '#     {name:50s}  {sell:>7s}  {buy:>7s}  '
        #         '{demand:>11s}  {supply:>11s}  {ts}\n'
        #     ).format(
        #         name='Item Name',
        #         sell='SellCr',
        #         buy='BuyCr',
        #         demand='Demand',
        #         supply='Supply',
        #         ts='Timestamp',
        #     ))
            system_count = 0
            total_station_count = 0
            total_commodity_count = 0
            # self.need_commit = False
            # self.update_cache = False
            # seen_stations = set()
            for system, stations in self.data_stream():
                self.ensure_system(system)
                station_count = 0
                commodity_count = 0
                for station, commodities in stations:
                    fq_station_name = f'@{system.name.upper()}/{station.name}'
                    if self.maxage and (datetime.now() - station.modified) > timedelta(days=self.maxage):
                        if self.tdenv.detail:
                            self.print(f'        |  {fq_station_name:50s}  |  Skipping station due to age: {datetime.now() - station.modified}, ts: {station.modified}')
                        continue
                    # if (system.name.upper(), station.name.upper()) in seen_stations:
                    #     if self.tdenv.detail:
                    #         self.print(f'        |  {fq_station_name:50s}  |  Skipping duplicate station record')
                    #     continue
                    # seen_stations.add((system.name.upper(), station.name.upper()))
                    self.ensure_station(system, station)
                    # f.write('\n')
                    # f.write(f'@ {system.name.upper()}/{station.name}\n')
                    
                    items = []
                    for commodity in commodities:
                        commodity = self.ensure_commodity(commodity)
                        result = self.execute("""SELECT modified FROM StationItem
                                        WHERE station_id = ? AND item_id = ?""",
                                        station.id, commodity.id, ).fetchone()
                        modified = parse_ts(result[0]) if result else None
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
                        for item in items:
                            self.execute("""INSERT OR REPLACE INTO StationItem (
                                station_id, item_id, modified,
                                demand_price, demand_units, demand_level,
                                supply_price, supply_units, supply_level, from_live
                            ) VALUES (
                                ?, ?, IFNULL(?, CURRENT_TIMESTAMP),
                                ?, ?, ?,
                                ?, ?, ?, ?
                            )""", *item )
                            commodity_count += 1
                        self.execute('COMMIT')
                    
                    # categories = self.categorise_commodities(commodities)
                    # for category_name, category_commodities in categories.items():
                    #     f.write(f'   + {category_name}\n')
                    #     for commodity in category_commodities:
                    #         commodity = self.ensure_commodity(commodity)
                    #         f.write((
                    #             '      {name:50s}  {sell:7d}  {buy:7d}  '
                    #             '{demand:10d}?  {supply:10d}?  {modified}\n'
                    #         ).format(
                    #             name=commodity.name,
                    #             sell=commodity.sell,
                    #             buy=commodity.buy,
                    #             demand=commodity.demand,
                    #             supply=commodity.supply,
                    #             modified=commodity.modified,
                    #         ))
                    #         commodity_count += 1
                    if commodity_count:
                        station_count += 1
                if station_count:
                    system_count += 1
                    total_station_count += station_count
                    total_commodity_count += commodity_count
                    if self.tdenv.detail:
                        self.print(
                            f'{system_count:6d}  |  {system.name.upper():50s}  |  '
                            f'{station_count:3d} st  {commodity_count:6d} co'
                        )
                # self.execute('COMMIT')
                # if self.need_commit:
                #     self.execute('COMMIT')
                #     self.need_commit = False
                #     self.update_cache = True
                    
            # Need to make sure cached tables are updated, if changes were made
            # if self.update_cache:
            #     for table in [ "Item", "Station", "System" ]:
            #         _, path = csvexport.exportTableToFile( self.tdb, self.tdenv, table )
            
            self.execute('COMMIT')
            self.tdb.close()
            # Need to make sure cached tables are updated
            for table in [ "Item", "Station", "System", "StationItem" ]:
                _, path = csvexport.exportTableToFile( self.tdb, self.tdenv, table )
                        
            self.print(
                f'{timedelta(seconds=int(timing.elapsed))!s}  Done  '
                f'{total_station_count} st  {total_commodity_count} co'
            )
            
        with Timing() as timing:
            self.print('Exporting to cache...')
            cache.regeneratePricesFile(self.tdb, self.tdenv)
            self.print(f'Cache export completed in {timedelta(seconds=int(timing.elapsed))!s}')

        # if not self.listener:
        #     with Timing() as timing:
        #         self.print('Importing to database...')
        #         self.tdenv.mergeImport = True
        #         cache.importDataFromFile(self.tdb, self.tdenv, filePath)
        #         self.print(f'Database import completed in {timedelta(seconds=int(timing.elapsed))!s}')
        return False

    def data_stream(self):
        if not self.file:
            url = self.url or SOURCE_URL
            self.print(f'Downloading prices from remote URL: {url}')
            self.file = self.tdenv.tmpDir / Path("galaxy_stations.json")
            transfers.download(self.tdenv, url, self.file)
            self.print(f'Download complete, saved to local file: {self.file}')

        if self.file == '-':
            self.print('Reading prices from stdin')
            stream = sys.stdin
        elif self.file:
            self.print(f'Reading prices from local file: {self.file}')
            stream = open(self.file, 'r', encoding='utf8')
        # else:
        #     url = self.url or SOURCE_URL
        #     self.print(f'Reading prices from remote URL: {url}')
        #     req = requests.get(url, stream=True)
        #     stream = req.iter_lines(decode_unicode=True)
        return ingest_stream(stream)

    def categorise_commodities(self, commodities):
        categories = {}
        for commodity in commodities:
            categories.setdefault(commodity.category, []).append(commodity)
        return categories

    def execute(self, query, *params, **kwparams):
        attempts = 5
        cursor = self.tdb.getDB().cursor()
        while True:
            try:
                return cursor.execute(query, params or kwparams)
            except sqlite3.OperationalError as ex:
                if "no transaction is active" in str(ex):
                    return
                if not attempts:
                    raise
                attempts -= 1
                self.print(f'Retrying query \'{query}\': {ex!s}')
                time.sleep(1)

    # def load_known_space(self):
    #     cache = {}
    #     result = self.execute(
    #         '''
    #         SELECT System.name, Station.name FROM System
    #         LEFT JOIN Station USING (system_id)
    #         '''
    #     ).fetchall()
    #     for system, station in result:
    #         cache.setdefault(system.upper(), set())
    #         if station is not None:
    #             cache[system.upper()].add(station.upper())
    #     return cache
    
    def load_known_systems(self):
        try:
            return dict(self.execute('SELECT system_id, name FROM System').fetchall())
        except:
            return dict()
    
    def load_known_stations(self):
        try:
            return dict(self.execute('SELECT station_id, name FROM Station').fetchall())
        except:
            return dict()
    
    def load_known_commodities(self):
        try:
            return dict(self.execute('SELECT fdev_id, name FROM Item').fetchall())
        except:
            return dict()

    def ensure_system(self, system):
        if system.id in self.known_systems:
            return
        self.execute(
            '''
            INSERT INTO System (system_id, name, pos_x, pos_y, pos_z, modified) VALUES (?, ?, ?, ?, ?, ?)
            ''',
            system.id, system.name, system.pos_x, system.pos_y, system.pos_z, system.modified,
        )
        self.execute('COMMIT')
        if self.tdenv.detail > 1:
            self.print(f'        |  {system.name.upper():50s}  |  Added missing system')
        self.known_systems[system.id] = system.name

    def ensure_station(self, system, station):
        if station.id in self.known_stations:
            system_id = self.execute('SELECT system_id FROM Station WHERE station_id = ?', station.id, ).fetchone()[0]
            if system_id != system.id:
                self.print(f'        |  {station.name:50s}  |  Megaship station moved, updating system')
                self.execute("UPDATE Station SET system_id = ? WHERE station_id = ?", system.id, station.id, )
                self.execute('COMMIT')
            return
        self.execute(
            '''
            INSERT INTO Station (
                system_id,
                station_id,
                name,
                ls_from_star,
                max_pad_size,
                market,
                blackmarket,
                shipyard,
                outfitting,
                rearm,
                refuel,
                repair,
                planetary,
                modified,
                type_id
            )
            VALUES (
                (SELECT system_id FROM System WHERE upper(name) = ?),
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ''',
            system.name.upper(),
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
        )
        self.execute('COMMIT')
        if self.tdenv.detail > 1:
            self.print(f'        |  {station.name:50s}  |  Added missing station')
        self.known_stations[station.id]= station.name

    def ensure_commodity(self, commodity):
        if commodity.id in self.known_commodities:
            # if self.known_commodities[commodity.id] != commodity.name:
            #     if self.tdenv.detail >= 3:
            #         self.print(f'        |    -  {commodity.name:45s}  |  Replace with pre-existing "{self.known_commodities[commodity.id]}"')
            #     return Commodity(
            #         id=commodity.id,
            #         name=self.known_commodities[commodity.id],
            #         category=commodity.category,
            #         demand=commodity.demand,
            #         supply=commodity.supply,
            #         sell=commodity.sell,
            #         buy=commodity.buy,
            #         modified=commodity.modified,
            #     )
            return commodity
        self.execute(
            '''
            INSERT INTO Item (item_id, category_id, name, fdev_id)
            VALUES (?, (SELECT category_id FROM Category WHERE upper(name) = ?), ?, ?)
            ''',
            commodity.id,
            commodity.category.upper(),
            corrections.correctItem(commodity.name),
            commodity.id,
        )
        
        # Need to update ui_order
        temp = self.execute("""SELECT
                        name, category_id, fdev_id
                        FROM Item
                        ORDER BY category_id, name
                        """)
        cat_id = 0
        ui_order = 1
        self.tdenv.DEBUG0("Updating ui_order data for items.")
        for line in temp:
            if line[1] != cat_id:
                ui_order = 1
                cat_id = line[1]
            else:
                ui_order += 1
            self.execute("""UPDATE Item
                        set ui_order = ?
                        WHERE fdev_id = ?""",
                        ui_order, line[2],)                    
        
        self.execute('COMMIT')
        if self.tdenv.detail > 1:
            self.print(f'        |  {commodity.name:50s}  |  Added missing commodity')
        self.known_commodities[commodity.id] = commodity.name
        return commodity

    def bool_yn(self, value):
        return '?' if value is None else ('Y' if value else 'N')


def ingest_stream(stream):
    """Ingest a spansh-style galaxy dump, yielding system-level data."""
    line = next(stream)
    assert line.rstrip(' \n,') == '['
    for line in stream:
        line = line.rstrip().rstrip(',')
        if line == ']':
            break
        system_data = simdjson.Parser().parse(line)
        coords = system_data.get('coords', {})
        yield (
            System(
                id = system_data.get('id64'),
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
            yield (
                Station(
                    id = station_data.get('id'),
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
                    planetary=STATION_TYPE_MAP.get(station_data.get('type'))[1] or False,
                    type=STATION_TYPE_MAP.get(station_data.get('type'))[0] or 0,
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
