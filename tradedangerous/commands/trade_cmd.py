# tradedangerous/commands/trade_cmd.py
from __future__ import annotations
import datetime
import typing

from .commandenv import ResultRow
from .exceptions import CommandLineError, NoDataError, GameDataError
from .parsing import ParseArgument, MutuallyExclusiveGroup
from tradedangerous import TradeException, TradeORM
from tradedangerous.db import orm_models as models
from tradedangerous.tradegame import EliteGame, JsonFiles, require_game_data
from tradedangerous.formatting import RowFormat, max_len

from sqlalchemy import select
from sqlalchemy.orm import aliased


if typing.TYPE_CHECKING:
    from .commandenv import CommandEnv, CommandResults


######################################################################
# Parser config

help='Find potential trades between two given stations.'
name='trade'
epilog=None
wantsTradeDB=False
arguments = [
    ParseArgument(
        'origin',
        help='Station you are purchasing from.',
        type=str,
    ),
    ParseArgument(
        'dest',
        help='Station you are selling to.',
        type=str,
    ),
]
switches = [
    ParseArgument('--gain-per-ton', '--gpt',
        help = 'Specify the minimum gain per ton of cargo',
        dest = 'minGainPerTon',
        type = "credits",
        default = 1,
    ),
    ParseArgument('--limit', '-n',
        help = 'Limit output to the first N results',
        dest = 'limit',
        type = int,
        default = 0,
    ),
    MutuallyExclusiveGroup(
        ParseArgument('--fill', '-f',
            help = "Reports the maximum profit based on supply vs your current ship's cargo capacity.",
            action = 'store_true',
        ),
        ParseArgument('--load',
            help = "Lists only the trades needed to fill your current ship's current free cargo space (see --full-load).",
            action = 'store_true',
        ),
        ParseArgument('--full-load',
            help = "Lists only the trades needed to fill your current ship's cargo hold from scratch.",
            action = 'store_true',
        ),
    ),
    ParseArgument('--supply', '-S',
        help = 'Requires at least this many units available at the seller (default 1)',
        type = int,
        default = 1,
    ),
    ParseArgument('--reverse', '-r',
        help = "Show the reverse trade: swaps origin and dest. This is a convenience for command-line golfers.",
        action = 'store_true',
    ),
    ParseArgument('--demand', '-D',
        help = 'Requires at least this many units demand at the buyer (default 1)',
        type = int,
        default = 1,
    ),
]


def age(now: datetime, modified: datetime) -> float:
    """ Return age in hours between now and modified timestamp. """
    delta = (now - modified).total_seconds() / 60.0
    if delta < 90:
        return f"{delta:.1f}M"
    delta /= 60.0
    if delta < 25:
        return f"{delta:.1f}H"
    delta /= 7.0
    if delta < 7:
        return f"{delta:.1f}D"
    return f"{int(delta):n}D"


def apply_game_name_shortcut(cmdenv: CommandEnv, name: str) -> str:
    """ 
        @internal

        apply_game_lookup_term will process one of the shortcuts provided for
        substituting a "current" system/station name from the game journal.

        Currently, we're allowing '~' for "where I'm at", and '~@' for
        "my nav target".

        The nav target only exposes the system you targetted, and you might
        not be docked, or you might want to express a different station in
        the same system.

        So we also support ~/... and ~@/...
    """
    game = getattr(cmdenv, "game")
    if not game:
        raise TradeException("Internal error: missing EliteGame journal object")
    # Get the summary status information which has the fields we need.
    status = game.get_status()

    if name == "~":
        require_game_data(game, location=True, status_fields=["star_system", "station_name"])

        # Alias for "current station-or-system". It can only be station if they're docked.
        if not status.docked:
            raise CommandLineError("'~' only works while docked at a station.")
        return f"{status.star_system}/{status.station_name}"

    if name.startswith("~/"):
        # Shortcut for "current system/..."; we just swap in the system name and
        # let the regular parsing pick it up from there.
        require_game_data(game, location=True, status_fields=["star_system"])
        return f"{status.star_system}/{name[2:]}"

    if name == "~@":
        # Alias for "current nav-target system", but trade requires a station.
        raise CommandLineError("nav route doesn't include station, please qualify ('~@/soandso')")

    if name.startswith("~@/"):
        # Shortcut for "current navtarget system/..."
        require_game_data(game, navroute=True)
        nav_data = game.json_data[JsonFiles.NAVROUTE]
        cmdenv.DEBUG0("nav_data: {}", nav_data)
        nav_route = nav_data.get("Route", None)
        if not nav_route:
            raise CommandLineError("'~@/...' only works when you have a nav route programmed.")
        # The nav route is listed in jump order, so we want the last destination
        sys_name = nav_route[-1]["StarSystem"]
        return f"{sys_name}/{name[3:]}"

    # Not something we handle; fall thru
    return name


def get_stations(cmdenv: CommandEnv, tdb: TradeORM) -> tuple[models.Station, models.Station]:
    """ @internal get_stations will work out what the from/to stations are. """
    orig_name, dest_name = cmdenv.origin, cmdenv.dest

    # Do we need to consult the game?
    if orig_name.startswith("~") or dest_name.startswith("~"):
        orig_name = apply_game_name_shortcut(cmdenv, orig_name)
        dest_name = apply_game_name_shortcut(cmdenv, dest_name)
    
    lhs = tdb.lookup_station(orig_name)
    if not lhs:
        raise CommandLineError(f"Unknown origin station: {orig_name}")
    cmdenv.DEBUG0("from id: system={}, station={}", lhs.system_id, lhs.station_id)

    rhs = tdb.lookup_station(dest_name)
    if not rhs:
        raise CommandLineError(f"Unknown destination station: {dest_name}")
    cmdenv.DEBUG0("to id..: system={}, station={}", rhs.system_id, rhs.station_id)
    
    if lhs == rhs:
        raise CommandLineError("Must specify two different stations.")

    return lhs, rhs


######################################################################
# Perform query and populate result set

def run(results: CommandResults, cmdenv: CommandEnv, tdb: TradeORM | None) -> CommandResults:
    tdb = TradeORM(tdenv=cmdenv)

    # Did they specify --fill?
    full_load = getattr(cmdenv, "full_load", False)
    want_load = getattr(cmdenv, "load", False) or full_load
    want_fill = getattr(cmdenv, "fill", False)

    # Anything that references game data means (trying) to create an object
    if cmdenv.origin.startswith("~") or cmdenv.dest.startswith("~") or want_fill or want_load:
        # We need to load the navroute if we're going to resolve '~@'
        jsons = []
        if cmdenv.origin.startswith("~@") or cmdenv.dest.startswith("~@"):
            jsons += [JsonFiles.NAVROUTE]
        game = EliteGame(tdenv=cmdenv, extra_jsons=jsons)
    else:
        game = None
    setattr(cmdenv, "game", game)

    lhs, rhs = get_stations(cmdenv, tdb)
    if getattr(cmdenv, "reverse", False):
        cmdenv.DEBUG0("--reverse: Reversing origin and destination")
        lhs, rhs = rhs, lhs

    # We want numbers to use in an ">" operation such that we produce
    # `> 0` to mean "1 or more", matching the index.
    supply_cutoff = max(getattr(cmdenv, "supply", 1), 0) - 1
    demand_cutoff = max(getattr(cmdenv, "demand", 1), 0) - 1
    
    seller = aliased(models.StationItem, name="seller")
    buyer = aliased(models.StationItem, name="buyer")
    stmt = (
        select(
            models.Item,
            seller.supply_price, seller.supply_units, seller.supply_level,
            buyer.demand_price, buyer.demand_units, buyer.demand_level,
            seller.modified, buyer.modified,
        )
        .where(
            seller.station_id == lhs.station_id,
            buyer.station_id == rhs.station_id,
            seller.item_id == buyer.item_id,
            seller.item_id == models.Item.item_id,
            seller.supply_price > 0,
            seller.supply_units > supply_cutoff,
            buyer.demand_price > 0,                 # sqlite seems to need thi shint
            buyer.demand_units > demand_cutoff,
            buyer.demand_price >= seller.supply_price,
        )
        .order_by((buyer.demand_price - seller.supply_price).desc())
    )
    compiled = stmt.compile(
        dialect=tdb.session.bind.dialect,
        compile_kwargs={"literal_binds": True}
    )
    cmdenv.DEBUG1("query: {}", compiled)
    trades = tdb.session.execute(stmt).unique().all()
    cmdenv.DEBUG0("Raw result count: {}", len(trades))
    if not trades:
        raise NoDataError(f"No profitable trades {lhs.name} -> {rhs.name}")


    results.summary = ResultRow(color=cmdenv.color)
    results.summary.fromStation = lhs
    results.summary.toStation = rhs
    
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    
    if cmdenv.limit > 0:
        trades = trades[:cmdenv.limit]
    
    results.summary.cargo_space = 1
    if game and (want_fill or want_load):
        # Ensure cargo fields aren't None.
        need_current_cargo = not full_load  # not needed for the "to capacity" calculation
        require_game_data(game, cargo_space=True, cargo_load=need_current_cargo)

        status = game.get_status()

        cargo_space = max(status.cargo_space, 0)
        if not cargo_space:  # forgot to buy cargo modules?
            raise TradeException("Your current ship has zero cargo capacity, Commander.")
        
        # If they're doing --load but not --want_load, deduct the cargo occupancy
        if want_load and not full_load:
            cargo_space -= max(status.cargo_load, 0)
            if cargo_space < 0:
                raise GameDataError(
                    "Game data is inconsistent (cargo load exceeds cargo capacity)."
                )
            if cargo_space == 0:
                raise CommandLineError("Cargo hold is full: use --full-load if you want to ignore current cargo occupancy")
        results.summary.cargo_space = max(cargo_space, 1)  # clamp to >= 1

    units_seen = 0
    for item, sup_price, sup_units, sup_level, dem_price, dem_units, dem_level, sup_age, dem_age in trades:
        units = min(results.summary.cargo_space, sup_units, dem_units)
        if not units:
            continue
        gain = dem_price - sup_price
        if gain < cmdenv.minGainPerTon:
            # If they've asked for a load:
            # - if we haven't seen any units, break, indicating they can't meet that requirement,
            # - otherwise continue filling the load so they can see there's more to be made.
            if units_seen == 0 or not want_load:
                break

        if want_load:
            # How much space is left?
            spare_units = cargo_space - units_seen
            # That constrains how much you can buy really
            units = min(units, spare_units)
            units_seen += units

        results.rows.append({
            "item": item.dbname(cmdenv.detail),
            "sup_price": sup_price,
            "sup_units": sup_units,
            "sup_level": sup_level,
            "dem_price": dem_price,
            "dem_units": dem_units,
            "dem_level": dem_level,
            "sup_age": age(now, sup_age),
            "dem_age": age(now, dem_age),
            "gain": gain,
            "units": units,
        })
        if want_load and units_seen >= cargo_space:
            break

    return results

#######################################################################
## Transform result set into output

def render(results, cmdenv, tdb):
    want_load = getattr(cmdenv, "load", False) or getattr(cmdenv, "full_load", False)
    longestNameLen = max_len(results.rows, key=lambda row: row["item"])
    
    rowFmt = RowFormat()
    rowFmt.addColumn('Item', '<', longestNameLen,
            key=lambda row: row["item"])
    rowFmt.addColumn('Profit', '>', 10, 'n',
            key=lambda row: row["gain"])
    rowFmt.addColumn('Cost', '>', 10, 'n',
            key=lambda row: row["sup_price"])
    # if cmdenv.detail > 1:
    #     rowFmt.addColumn('AvgCost', '>', 10,
    #         key=lambda row: tdb.avgSelling.get(row.item.ID, 0)
    #     )
    rowFmt.addColumn('Buying', '>', 10, 'n',
            key=lambda row: row["dem_price"])
    # rowFmt.addColumn('AvgBuy', '>', 10,
    #     key=lambda row: tdb.avgBuying.get(row.item.ID, 0)
    # )
    
    if cmdenv.detail > 1:
        rowFmt.addColumn('Supply', '>', 10,
            key=lambda row: f'{row["sup_units"]:n}' if row["sup_units"] >= 0 else '?')
        rowFmt.addColumn('Demand', '>', 10,
            key=lambda row: f'{row["dem_units"]:n}' if row["dem_units"] >= 0 else '?')
    if cmdenv.detail:
        rowFmt.addColumn('SrcAge', '>', 9, 's',
            key=lambda row: row["sup_age"])
        rowFmt.addColumn('DstAge', '>', 9, 's',
            key=lambda row: row["dem_age"])

    if results.summary.cargo_space > 1:
        rowFmt.addColumn('|',      '>', 1,  key=lambda row: '|')
        rowFmt.addColumn('Units',  '>', 6, key=lambda row: f'{row["units"]:n}')
        rowFmt.addColumn('Profit', '>', 11, key=lambda row: f'{row["units"]*row["gain"]:n}')

    heading, underline = rowFmt.heading()
    if not cmdenv.quiet:
        print(f"{len(results.rows)} trades found between {results.summary.fromStation.dbname()} and {results.summary.toStation.dbname()}.")
        print(heading)
        print(underline)

    total_units, total_gain = 0, 0
    for row in results.rows:
        total_units += row["units"]
        total_gain += row["gain"] * row["units"]
        print(rowFmt.format(row))

    if total_units > 0 and not cmdenv.quiet and want_load:
        print(underline)
        cmdenv.uprint(f"Total Units: {total_units:n}. Total Profit: {total_gain:n}.")
