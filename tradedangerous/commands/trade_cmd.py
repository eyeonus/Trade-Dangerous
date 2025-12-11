# tradedangerous/commands/trade_cmd.py
import datetime

from .exceptions import CommandLineError
from .parsing import ParseArgument
from tradedangerous import TradeORM
from tradedangerous.db import orm_models as models
from tradedangerous.formatting import RowFormat, max_len

from sqlalchemy import select, text
from sqlalchemy.orm import aliased

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
        help = 'Limit output to the top N results',
        dest = 'limit',
        type = int,
        default = 0,
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


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from .commandenv import ResultRow

    # IMPORTANT: resolve stations BEFORE constructing TradeCalc
    tdb = TradeORM(tdenv=cmdenv)

    lhs = tdb.lookup_station(cmdenv.origin)
    if not lhs:
        raise CommandLineError(f"Unknown origin station: {cmdenv.origin}")
    cmdenv.DEBUG0("from id: system={}, station={}", lhs.system_id, lhs.station_id)
    rhs = tdb.lookup_station(cmdenv.dest)
    if not rhs:
        raise CommandLineError(f"Unknown destination station: {cmdenv.dest}")
    cmdenv.DEBUG0("to id..: system={}, station={}", rhs.system_id, rhs.station_id)

    if lhs == rhs:
        raise CommandLineError("Must specify two different stations.")
    
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
            seller.supply_price > 0,
            buyer.demand_price > 0,                 # (optional extra guard)
            buyer.demand_price >= seller.supply_price,
            seller.item_id == models.Item.item_id,
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
        raise CommandLineError(f"No profitable trades {lhs.name} -> {rhs.name}")

    results.summary = ResultRow(color=cmdenv.color)
    results.summary.fromStation = lhs
    results.summary.toStation = rhs

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    
    if cmdenv.limit > 0:
        trades = trades[:cmdenv.limit]

    for item, sup_price, sup_units, sup_level, dem_price, dem_units, dem_level, sup_age, dem_age in trades:
        gain = dem_price - sup_price
        if gain < cmdenv.minGainPerTon:
            continue
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
        })

    return results

#######################################################################
## Transform result set into output

def render(results, cmdenv, tdb):
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

    if not cmdenv.quiet:
        print(f"{len(results.rows)} trades found between {results.summary.fromStation.dbname()} and {results.summary.toStation.dbname()}.")
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')

    for row in results.rows:
        print(rowFmt.format(row))
