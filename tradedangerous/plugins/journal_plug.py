from __future__ import annotations
import datetime
import typing

from sqlalchemy import delete, func, select

from tradedangerous import TradeORM
from tradedangerous.db.orm_models import Station, Item, StationItem
from tradedangerous.misc.timeage import datetime_to_age
from tradedangerous.tradegame import EliteGame, JournalLoad, JsonFiles

from . import PluginException, ImportPluginBase


class ImportPlugin(ImportPluginBase):
    """ Plugin that reads the live game journal market json and imports the values. """
    pluginOptions = {}
    
    def run(self) -> bool:
        """ Read the market journal, if it exists. """
        tdo = TradeORM(tdenv=self.tdenv)

        # Load as little as possible, all we care about is your last market update
        game: EliteGame = EliteGame(tdenv=self.tdenv, journal_load=JournalLoad.DO_NOT_LOAD, json_files=[JsonFiles.MARKET])

        market: dict[str, typing.Any] = game.json_data[JsonFiles.MARKET]
        if not market:
            self.tdenv.NOTE("No data in Market.json, cancelling.")
            return False
        timestamp = datetime.datetime.strptime(market["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)

        market_id = market["MarketID"]
        station_name = f"{market['StarSystem']}/{market['StationName']}"
        station = tdo.session.get(Station, market_id)
        if not station:
            raise PluginException(f"Unknown station in Market.json: #{market_id}: {station_name}")

        # Find when the station was last updated.
        stmt = select(func.max(StationItem.modified)).where(StationItem.station_id == market_id)
        last_mod = tdo.session.execute(stmt).scalar_one_or_none()

        json_items = market["Items"]

        self.tdenv.NOTE("[bold]{}[/] (#{}) [yellow]{}[/]: ({}) items", station_name, market_id, timestamp, len(json_items))
        if last_mod:
            if last_mod == timestamp:
                self.tdenv.NOTE("Data already imported.")
                return False
            age = datetime_to_age(last_mod)
            if last_mod > timestamp:
                self.tdenv.NOTE("Database entries are more recent ([yellow]{}[/]/{}), skipping import.", last_mod, age)
                return False
            self.tdenv.NOTE("[green]Updating:[/green] previous entry: [yellow]{}[/]/{}", last_mod, age)
        else:
            self.tdenv.NOTE("[green]New Data[/green] [dim](station had no recent data)[/dim]")

        # Remove any existing entries
        stmt = delete(StationItem).where(StationItem.station_id == market_id)
        tdo.session.execute(stmt)

        # Add new ones
        items: list[dict[str, typing.Any]] = market["Items"]
        for item_entry in items:
            item_id: int = item_entry["id"]
            self.tdenv.DEBUG0("item: {}", item_entry)

            # todo #1: check Item table to make sure we know about it;
            # warn but ignore if we don't.
            if not tdo.session.get(Item, item_id):
                self.tdenv.WARN("Unknown item #{} [{}]", item_id, item_entry["Name_Localised"])
                continue

            demand_price: int = item_entry["SellPrice"]
            demand_units: int = item_entry["Demand"]
            demand_level: int = item_entry["DemandBracket"]
            supply_price: int = item_entry["BuyPrice"]
            supply_units: int = item_entry["Stock"]
            supply_level: int = item_entry["StockBracket"]
            
            if supply_price <= 0 or supply_units <= 0 or supply_level <= 0:
                supply_price, supply_units, supply_level = 0, 0, 0
            
            if not supply_price and not demand_price:
                self.tdenv.DEBUG0("Skipping item #{} as no supply or demand", item_id)
                continue

            entry = StationItem(
                station_id=market_id,
                item_id=item_id,
                demand_price=demand_price,
                demand_units=demand_units,
                demand_level=demand_level,
                supply_price=supply_price,
                supply_units=supply_units,
                supply_level=supply_level,
                modified=timestamp,
                from_live=1,
            )

            tdo.session.add(entry)
            
        tdo.session.commit()
        self.tdenv.NOTE("Import complete.")

        return False

    def finish(self) -> bool:
        return False
