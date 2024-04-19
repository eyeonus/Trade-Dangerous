import os
import sys
import time
from datetime import datetime, timedelta
from collections import namedtuple
from pathlib import Path

import requests
import simdjson
import sqlite3

from .. import plugins, cache, fs, transfers

SOURCE_URL = 'https://downloads.spansh.co.uk/galaxy_stations.json'

STATION_TYPE_MAP = {
    'Drake-Class Carrier': 24,  # fleet carriers
    'Settlement': 25,           # odyssey settlements
}

System = namedtuple('System', 'name,pos_x,pos_y,pos_z,modified')
Station = namedtuple('Station', 'name,distance,max_pad_size,market,black_market,shipyard,outfitting,rearm,refuel,repair,planetary,type,modified')
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
        self.maxage = float(self.getOption('maxage'))
        self.listener = self.getOption('listener')
        assert not (self.url and self.file), 'Provide either url or file, not both'
        if self.file and (self.file != '-'):
            self.file = (Path(self.tdenv.cwDir) / self.file).resolve()
        self.known_space = self.load_known_space()
        self.known_commodities = self.load_known_commodities()

    def print(self, *args, **kwargs):
        return self.tdenv.uprint(*args, **kwargs)

    def run(self):
        fs.ensurefolder(self.tdenv.tmpDir)
        filePath = self.tdenv.tmpDir / Path("spansh.prices")
        if self.tdenv.detail < 1:
            self.print('This will take at least several minutes...')
            self.print('You can increase verbosity (-v) to get a sense of progress')
        with open(filePath, 'w') as f, Timing() as timing:
            self.print(f'Writing prices to {filePath}')
            f.write('# Generated from spansh galaxy data\n')
            f.write(f'# Source: {self.file or self.url}\n')
            f.write('#\n')
            f.write((
                '#     {name:50s}  {sell:>7s}  {buy:>7s}  '
                '{demand:>11s}  {supply:>11s}  {ts}\n'
            ).format(
                name='Item Name',
                sell='SellCr',
                buy='BuyCr',
                demand='Demand',
                supply='Supply',
                ts='Timestamp',
            ))
            system_count = 0
            total_station_count = 0
            total_commodity_count = 0
            self.need_commit = False
            seen_stations = set()
            for system, stations in self.data_stream():
                self.ensure_system(system)
                station_count = 0
                commodity_count = 0
                for station, commodities in stations:
                    fq_station_name = f'@{system.name.upper()}/{station.name}'
                    if (datetime.now() - station.modified) > timedelta(days=self.maxage):
                        if self.tdenv.detail >= 1:
                            self.print(f'        |  @{fq_station_name:50s}  |  Skipping station due to age: {datetime.now() - station.modified}, ts: {station.modified}')
                        continue
                    if (system.name.upper(), station.name.upper()) in seen_stations:
                        if self.tdenv.detail >= 1:
                            self.print(f'        |  {fq_station_name:50s}  |  Skipping duplicate station record')
                        continue
                    seen_stations.add((system.name.upper(), station.name.upper()))
                    self.ensure_station(system, station)
                    f.write('\n')
                    f.write(f'@ {system.name.upper()}/{station.name}\n')
                    categories = self.categorise_commodities(commodities)
                    for category_name, category_commodities in categories.items():
                        f.write(f'   + {category_name}\n')
                        for commodity in category_commodities:
                            commodity = self.ensure_commodity(station, commodity)
                            f.write((
                                '      {name:50s}  {sell:7d}  {buy:7d}  '
                                '{demand:10d}?  {supply:10d}?  {modified}\n'
                            ).format(
                                name=commodity.name,
                                sell=commodity.sell,
                                buy=commodity.buy,
                                demand=commodity.demand,
                                supply=commodity.supply,
                                modified=commodity.modified,
                            ))
                            commodity_count += 1
                    station_count += 1
                system_count += 1
                total_station_count += station_count
                total_commodity_count += commodity_count
                if self.tdenv.detail >= 1:
                    self.print(
                        f'{system_count:6d}  |  {system.name.upper():50s}  |  '
                        f'{station_count:3d} st  {commodity_count:6d} co'
                    )
                if self.need_commit:
                    self.execute('COMMIT')
                    self.need_commit = False
            self.print(
                f'{timedelta(seconds=int(timing.elapsed))!s}  Done  '
                f'{total_station_count} st  {total_commodity_count} co'
            )
            
        if not self.listener:
            with Timing() as timing:
                self.print('Importing to cache...')
                self.tdenv.mergeImport = True
                cache.importDataFromFile(self.tdb, self.tdenv, filePath)
                self.print(f'Cache import completed in {timedelta(seconds=int(timing.elapsed))!s}')
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
        # attempts = 5
        cursor = self.tdb.getDB().cursor()
        while True:
            try:
                return cursor.execute(query, params or kwparams)
            except sqlite3.OperationalError as ex:
                # if not attempts:
                #     raise
                # attempts -= 1
                self.print(f'Retrying query: {ex!s}')
                time.sleep(1)

    def load_known_space(self):
        cache = {}
        result = self.execute(
            '''
            SELECT System.name, Station.name FROM System
            LEFT JOIN Station USING (system_id)
            '''
        ).fetchall()
        for system, station in result:
            cache.setdefault(system.upper(), set())
            if station is not None:
                cache[system.upper()].add(station.upper())
        return cache

    def load_known_commodities(self):
        return dict(self.execute('SELECT fdev_id, name FROM Item').fetchall())

    def ensure_system(self, system):
        if system.name.upper() in self.known_space:
            return
        self.execute(
            '''
            INSERT INTO System (name, pos_x, pos_y, pos_z, modified) VALUES (?, ?, ?, ?, ?)
            ''',
            system.name, system.pos_x, system.pos_y, system.pos_z, system.modified,
        )
        self.need_commit = True
        if self.tdenv.detail >= 2:
            self.print(f'        |  {system.name.upper():50s}  |  Added missing system')
        self.known_space[system.name.upper()] = set()

    def ensure_station(self, system, station):
        if station.name.upper() in self.known_space.get(system.name.upper(), set()):
            return
        self.execute(
            '''
            INSERT INTO Station (
                system_id,
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ''',
            system.name.upper(),
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
        self.need_commit = True
        if self.tdenv.detail >= 2:
            self.print(f'        |  {station.name:50s}  |  Added missing station')
        self.known_space[system.name.upper()].add(station.name.upper())

    def ensure_commodity(self, station, commodity):
        if commodity.id in self.known_commodities:
            if self.known_commodities[commodity.id] != commodity.name:
                if self.tdenv.detail >= 3:
                    self.print(f'        |    -  {station.name:45s}  |  Replace "{commodity.name}" with pre-existing "{self.known_commodities[commodity.id]}"')
                return Commodity(
                    id=commodity.id,
                    name=self.known_commodities[commodity.id],
                    category=commodity.category,
                    demand=commodity.demand,
                    supply=commodity.supply,
                    sell=commodity.sell,
                    buy=commodity.buy,
                    modified=commodity.modified,
                )
            return commodity
        self.execute(
            '''
            INSERT INTO Item (category_id, name, fdev_id)
            VALUES ((SELECT category_id FROM Category WHERE upper(name) = ?), ?, ?)
            ''',
            commodity.category.upper(),
            commodity.name,
            commodity.id,
        )
        self.need_commit = True
        if self.tdenv.detail >= 2:
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
                name=system_data.get('name', 'Unnamed'),
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
    is_planetary = False
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
                    name=station_data.get('name', 'Unnamed'),
                    distance=station_data.get('distanceToArrival', 999999),
                    max_pad_size=max_pad_size,
                    market=True,
                    black_market='Black Market' in services,
                    shipyard='Shipyard' in services,
                    outfitting='Outfitting' in services,
                    rearm='Restock' in services,
                    refuel='Refuel' in services,
                    repair='Repair' in services,
                    planetary=is_planetary,
                    type=STATION_TYPE_MAP.get(station_data.get('type'), 0),
                    modified=parse_ts(station_data.get('updateTime')),
                ),
                ingest_market(market),
            )
        # first target is system stations, everything else is planetary
        is_planetary = True


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
