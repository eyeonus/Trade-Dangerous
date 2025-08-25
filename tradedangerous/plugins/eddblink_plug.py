"""
Import plugin that uses data files from 
https://elite.tromador.com/ to update the Database.
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from pathlib import Path
from .. fs import file_line_count
from .. import plugins, cache, transfers
from ..misc import progress as pbar
from ..plugins import PluginException

import csv
import datetime
import os
import requests
import sqlite3
import typing

from sqlalchemy import select, delete, update, func, exists
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.mysql import insert as mysql_insert
from ..db.engine import make_engine_from_config, get_session_factory
from ..db.orm_models import System, Station, Item, StationItem


if typing.TYPE_CHECKING:
    from typing import Optional
    from .. tradeenv import TradeEnv

# Constants
BASE_URL = os.environ.get('TD_SERVER') or "https://elite.tromador.com/files/"


class DecodingError(PluginException):
    pass


def _count_listing_entries(tdenv: TradeEnv, listings: Path) -> int:
    """ Calculates the number of entries in a listing file by counting the lines. """
    if not listings.exists():
        tdenv.NOTE("File not found, aborting: {}", listings)
        return 0
    
    tdenv.DEBUG0(f"Getting total number of entries in {listings}...")
    count = file_line_count(listings)
    if count <= 1:
        if count == 1:
            tdenv.DEBUG0("Listing count of 1 suggests nothing but a header")
        else:
            tdenv.DEBUG0("Listings file is empty, nothing to do.")
        return 0
    
    return count + 1  # kfsone: Doesn't the header already make this + 1?


def _make_item_id_lookup(tdenv: TradeEnv, db: sqlite3.Cursor) -> frozenset[int]:
    """ helper: retrieve the list of commodities in database. """
    tdenv.DEBUG0("Getting list of commodities...")
    return frozenset(cols[0] for cols in db.execute("SELECT item_id FROM Item"))


def _make_station_id_lookup(tdenv: TradeEnv, db: sqlite3.Cursor) -> frozenset[int]:
    """ helper: retrieve the list of station IDs in database. """
    tdenv.DEBUG0("Getting list of stations...")
    return frozenset(cols[0] for cols in db.execute("SELECT station_id FROM Station"))


def _collect_station_modified_times(tdenv: TradeEnv, db: sqlite3.Cursor) -> dict[int, int]:
    """ helper: build a list of the last modified time for all stations by id. """
    tdenv.DEBUG0("Getting last-update times for stations...")
    return dict(db.execute("SELECT station_id, strftime('%s', MIN(modified)) FROM StationItem GROUP BY station_id"))


class ImportPlugin(plugins.ImportPluginBase):
    """
    Import plugin that uses data files from
    https://elite.tromador.com/ to update the Database.
    """
    pluginOptions = {
        'item':         "Update Items using latest file from server. (Implies '-O system,station')",
        'rare':         "Update RareItems using latest file from server. (Implies '-O system,station')",
        'ship':         "Update Ships using latest file from server.",
        'upgrade':      "Update Upgrades using latest file from server.",
        'system':       "Update Systems using latest file from server.",
        'station':      "Update Stations using latest file from server. (Implies '-O system')",
        'shipvend':     "Update ShipVendors using latest file from server. (Implies '-O system,station,ship')",
        'upvend':       "Update UpgradeVendors using latest file from server. (Implies '-O system,station,upgrade')",
        'listings':     "Update market data using latest listings.csv dump. (Implies '-O item,system,station')",
        'all':          "Update everything with latest dumpfiles. (Regenerates all tables)",
        'clean':        "Erase entire database and rebuild from empty. (Regenerates all tables.)",
        'skipvend':     "Don't regenerate ShipVendors or UpgradeVendors. (Supercedes '-O all', '-O clean'.)",
        'force':        "Force regeneration of selected items even if source file not updated since previous run. "
                        "(Useful for updating Vendor tables if they were skipped during a '-O clean' run.)",
        'purge':        "Remove any empty systems that previously had fleet carriers.",
        'optimize':     "Optimize ('vacuum') database after processing.",
        'solo':         "Don't download crowd-sourced market data. (Implies '-O skipvend', supercedes '-O all', '-O clean', '-O listings'.)",
    }
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
        
        self.dataPath = os.environ.get('TD_EDDB') or self.tdenv.tmpDir
        self.categoriesPath = Path("Category.csv")
        self.commoditiesPath = Path("Item.csv")
        self.rareItemPath = Path("RareItem.csv")
        self.shipPath = Path("Ship.csv")
        self.urlShipyard = "https://raw.githubusercontent.com/EDCD/FDevIDs/master/shipyard.csv"
        self.FDevShipyardPath = self.tdb.dataPath / Path("FDevShipyard.csv")
        self.shipVendorPath = Path("ShipVendor.csv")
        self.stationsPath = Path("Station.csv")
        self.sysPath = Path("System.csv")
        self.upgradesPath = Path("Upgrade.csv")
        self.urlOutfitting = "https://raw.githubusercontent.com/EDCD/FDevIDs/master/outfitting.csv"
        self.FDevOutfittingPath = self.tdb.dataPath / Path("FDevOutfitting.csv")
        self.upgradeVendorPath = Path("UpgradeVendor.csv")
        self.listingsPath = Path("listings.csv")
        self.liveListingsPath = Path("listings-live.csv")
        self.pricesPath = Path("listings.prices")
        # SQLAlchemy engine/session
        cfg_path = os.environ.get("TD_DB_CONFIG") or (self.tdb.dbPath.parent / "db_config.ini")
        try:
            self.engine = make_engine_from_config(str(cfg_path))
        except Exception:
            # Fallback: try environment only; engine helper will resolve defaults
            self.engine = make_engine_from_config(os.environ.get("TD_DB_CONFIG", "db_config.ini"))
        self.Session = get_session_factory(self.engine)

    
    def now(self):
        return datetime.datetime.now()
    
    def downloadFile(self, path):
        """
        Fetch the latest dumpfile from the website if newer than local copy.
        """
        if path not in (self.liveListingsPath, self.listingsPath):
            localPath = Path(self.tdb.dataPath, path)
        else:
            localPath = Path(self.dataPath, path)
        
        url  = BASE_URL + str(path)
        
        self.tdenv.NOTE("Checking for update to '{}'.", path)
        # Use an HTTP Request header to obtain the Last-Modified and Content-Length headers.
        # Also, tell the server to give us the un-compressed length of the file by saying
        # that >this< request only wants text.
        headers = {"User-Agent": "Trade-Dangerous", "Accept-Encoding": "identity"}
        try:
            response = requests.head(url, headers=headers, timeout=70)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.tdenv.WARN("Problem with download:\n    URL: {}\n    Error: {}", url, str(e))
            return False
        
        last_modified = response.headers.get("last-modified")
        dump_mod_time = parsedate_to_datetime(last_modified).timestamp()
        
        if Path.exists(localPath):
            local_mod_time = localPath.stat().st_mtime
            if local_mod_time >= dump_mod_time:
                self.tdenv.DEBUG0("'{}': Dump is not more recent than Local.", path)
                return False
        
        # The server doesn't know the gzip'd length, and we won't see the gzip'd data,
        # so we want the actual text-only length. Capture it here so we can tell the
        # transfer mechanism how big the file is going to be.
        length = response.headers.get("content-length")
        
        self.tdenv.NOTE("Downloading file '{}'.", path)
        transfers.download(self.tdenv, url, localPath, chunkSize=16384, length=length)
        
        # Change the timestamps on the file so they match the website
        os.utime(localPath, (dump_mod_time, dump_mod_time))
        
        return True
    
    def purgeSystems(self):
        """
        Purges systems from the System table that do not have any stations claiming to be in them.
        Keeps table from becoming too large because of fleet carriers moving to unpopulated systems.
        """
        self.tdenv.NOTE("Purging Systems with no stations: Start time = {}", self.now())
        with self.Session.begin() as session:
            from sqlalchemy import exists
            session.execute(delete(System).where(~exists(select(1).where(Station.system_id == System.system_id))))
        self.tdenv.NOTE("Finished purging Systems. End time = {}", self.now())

    
    def importListings(self, listings_file):
        """
        Updates the market data (AKA the StationItem table) using listings_file
        Writes directly to database.
        """
        listings_path = Path(self.dataPath, listings_file).absolute()
        from_live = listings_path != Path(self.dataPath, self.listingsPath).absolute()

        self.tdenv.NOTE("Checking listings")
        total = _count_listing_entries(self.tdenv, listings_path)
        if not total:
            self.tdenv.NOTE("No listings")
            return

        self.tdenv.NOTE("Processing market data from {}: Start time = {}. Live = {}", listings_file, self.now(), from_live)

        # Session + lookups
        with self.Session() as session:
            item_lookup = {row[0] for row in session.execute(select(Item.item_id)).all()}
            station_lookup = {row[0] for row in session.execute(select(Station.station_id)).all()}
            last_station_update_times = {}
            for sid, dt in session.execute(select(StationItem.station_id, func.min(StationItem.modified)).group_by(StationItem.station_id)):
                if dt is not None:
                    last_station_update_times[int(sid)] = int(dt.timestamp())

        # Progress + batching
        max_transaction_items = 25000  # legacy intent: keep tx bounded
        transaction_items = 0
        cur_station = None
        skip_station = False

        with open(listings_path, "r", encoding="utf-8") as fh, \
             pbar.Progress(total, 40, prefix="Processing", style=pbar.LongRunningCountBar) as prog, \
             self.Session.begin() as session:

            # choose dialect upsert factory once
            dialect = self.engine.dialect.name
            def do_upsert(payloads):
                if not payloads:
                    return
                if dialect == "sqlite":
                    stmt = sqlite_insert(StationItem).values(payloads)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[StationItem.station_id, StationItem.item_id],
                        set_={
                            "demand_price": stmt.excluded.demand_price,
                            "demand_units": stmt.excluded.demand_units,
                            "demand_level": stmt.excluded.demand_level,
                            "supply_price": stmt.excluded.supply_price,
                            "supply_units": stmt.excluded.supply_units,
                            "supply_level": stmt.excluded.supply_level,
                            "modified": stmt.excluded.modified,
                            "from_live": stmt.excluded.from_live,
                        },
                    )
                else:
                    ins = mysql_insert(StationItem).values(payloads)
                    stmt = ins.on_duplicate_key_update(
                        demand_price=ins.inserted.demand_price,
                        demand_units=ins.inserted.demand_units,
                        demand_level=ins.inserted.demand_level,
                        supply_price=ins.inserted.supply_price,
                        supply_units=ins.inserted.supply_units,
                        supply_level=ins.inserted.supply_level,
                        modified=ins.inserted.modified,
                        from_live=ins.inserted.from_live,
                    )
                session.execute(stmt)

            buffer = []

            for listing in csv.DictReader(fh):
                prog.increment(1)

                station_id = int(listing['station_id'])
                if station_id not in station_lookup:
                    continue

                listing_time = int(listing['collected_at'])

                if station_id != cur_station:
                    # manage prior station boundaries / bounded transactions
                    if transaction_items >= max_transaction_items:
                        session.commit()
                        transaction_items = 0

                    cur_station, skip_station = station_id, False

                    # determine existing modified watermark
                    last_modified = int(last_station_update_times.get(station_id, 0)) or 0
                    if last_modified:
                        if listing_time == last_modified and not from_live:
                            # mark no-longer-live on full import, then skip the station
                            session.execute(update(StationItem).where(StationItem.station_id == cur_station).values(from_live=0))
                            transaction_items += 1
                            skip_station = True
                            continue
                        if listing_time < last_modified:
                            # incoming is older; skip station entirely
                            skip_station = True
                            continue
                        # newer: flush old data for station on full run
                        if not from_live:
                            session.execute(delete(StationItem).where(StationItem.station_id == cur_station))
                            transaction_items += 1
                            last_station_update_times[station_id] = listing_time

                if skip_station:
                    continue

                item_id = int(listing['commodity_id'])
                if item_id not in item_lookup:
                    continue

                payload = dict(
                    station_id=station_id,
                    item_id=item_id,
                    modified=datetime.datetime.utcfromtimestamp(listing_time),
                    from_live=1 if from_live else 0,
                    demand_price=int(listing['sell_price']),
                    demand_units=int(listing['demand']),
                    demand_level=int(listing.get('demand_bracket') or '-1'),
                    supply_price=int(listing['buy_price']),
                    supply_units=int(listing['supply']),
                    supply_level=int(listing.get('supply_bracket') or '-1'),
                )
                buffer.append(payload)
                transaction_items += 1

                if len(buffer) >= 1000:
                    do_upsert(buffer)
                    buffer.clear()

            if buffer:
                do_upsert(buffer)

    
    def run(self):
        self.tdenv.ignoreUnknown = True
        
        # Create the /eddb folder for downloading the source files if it doesn't exist.
        try:
            Path(str(self.dataPath)).mkdir()
        except FileExistsError:
            pass
        
        # Run 'listings' by default:
        # If no options, or if only 'force', and/or 'skipvend',
        # have been passed, enable 'listings'.
        default = True
        for option in self.options:
            if option not in ('force', 'skipvend', 'purge'):
                default = False
        if default:
            self.options["listings"] = True
        
        # We can probably safely assume that the plugin
        # has never been run if the db file doesn't exist.
        if not self.tdb.dbPath.exists():
            self.options["clean"] = True
        
        if self.getOption("clean"):
            # Rebuild the tables from scratch. Must be done on first run of plugin.
            # Can be done at anytime with the "clean" option.
            for name in [
                "Category",
                "Item",
                "RareItem",
                "Ship",
                "ShipVendor",
                "Station",
                "System",
                "Upgrade",
                "UpgradeVendor",
                "FDevShipyard",
                "FDevOutfitting",
            ]:
                file = self.tdb.dataPath / Path(name + ".csv")
                try:
                    os.remove(str(file))
                except FileNotFoundError:
                    pass
            
            try:
                os.remove(str(self.tdb.dataPath) + "/TradeDangerous.db")
            except FileNotFoundError:
                pass
            try:
                os.remove(str(self.tdb.dataPath) + "/TradeDangerous.prices")
            except FileNotFoundError:
                pass
            
            # Because this is a clean run, we need to temporarily rename the RareItem.csv,
            # otherwise TD will crash trying to insert the rare items to the database,
            # because there's nothing in the Station table it tries to pull from.
            ri_path = self.tdb.dataPath / Path("RareItem.csv")
            rib_path = ri_path.with_suffix(".tmp")
            if ri_path.exists():
                if rib_path.exists():
                    rib_path.unlink()
                ri_path.rename(rib_path)
            
            self.tdb.close()
            
            self.tdb.reloadCache()
            self.tdb.close()
            
            # Now it's safe to move RareItems back.
            if ri_path.exists():
                ri_path.unlink()
            if rib_path.exists():
                rib_path.rename(ri_path)
            
            self.options["all"] = True
            self.options["force"] = True
        
        # Select which options will be updated
        if self.getOption("listings"):
            self.options["item"] = True
            self.options["station"] = True
        
        if self.getOption("shipvend"):
            self.options["ship"] = True
            self.options["station"] = True
        
        if self.getOption("upvend"):
            self.options["upgrade"] = True
            self.options["station"] = True
        
        if self.getOption("item"):
            self.options["station"] = True
        
        if self.getOption("rare"):
            self.options["station"] = True
        
        if self.getOption("station"):
            self.options["system"] = True
        
        if self.getOption("all"):
            self.options["item"] = True
            self.options["rare"] = True
            self.options["ship"] = True
            self.options["shipvend"] = True
            self.options["station"] = True
            self.options["system"] = True
            self.options["upgrade"] = True
            self.options["upvend"] = True
            self.options["listings"] = True
        
        if self.getOption("solo"):
            self.options["listings"] = False
            self.options["skipvend"] = True
        
        if self.getOption("skipvend"):
            self.options["shipvend"] = False
            self.options["upvend"] = False
        
        # Download required files and update tables.
        buildCache = False
        if self.getOption("upgrade"):
            if self.downloadFile(self.upgradesPath) or self.getOption("force"):
                transfers.download(self.tdenv, self.urlOutfitting, self.FDevOutfittingPath)
                buildCache = True
        
        if self.getOption("ship"):
            if self.downloadFile(self.shipPath) or self.getOption("force"):
                transfers.download(self.tdenv, self.urlShipyard, self.FDevShipyardPath)
                buildCache = True
        
        if self.getOption("rare"):
            if self.downloadFile(self.rareItemPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("shipvend"):
            if self.downloadFile(self.shipVendorPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("upvend"):
            if self.downloadFile(self.upgradeVendorPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("system"):
            if self.downloadFile(self.sysPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("station"):
            if self.downloadFile(self.stationsPath) or self.getOption("force"):
                buildCache = True
        
        if self.getOption("item"):
            if self.downloadFile(self.commoditiesPath) or self.getOption("force"):
                self.downloadFile(self.categoriesPath)
                buildCache = True
                
                
        data_dir = Path(self.tdb.tdenv.dataPath or "./data")
        for name in [
            "System.csv","Station.csv","Category.csv","Item.csv",
            "RareItem.csv","Ship.csv","Upgrade.csv",
            "ShipVendor.csv","UpgradeVendor.csv"
        ]:
            p = data_dir / name
            if p.exists():
                cache.importDataFromFile(self.tdb, p)
        
        # Remake the .db files with the updated info.
        if buildCache:
            self.tdb.close()
            self.tdb.reloadCache()
            self.tdb.close()
        
        if self.getOption("purge"):
            self.purgeSystems()
            self.tdb.close()
        
        if self.getOption("listings"):
            if self.downloadFile(self.listingsPath) or self.getOption("force"):
                self.importListings(self.listingsPath)
            if self.downloadFile(self.liveListingsPath) or self.getOption("force"):
                self.importListings(self.liveListingsPath)
        
        if self.getOption("listings"):
            self.tdenv.NOTE("Regenerating .prices file.")
            cache.regeneratePricesFile(self.tdb, self.tdenv)
        
        self.tdenv.NOTE("Import completed.")
        
        # TD doesn't need to do anything, tell it to just quit.
        return False