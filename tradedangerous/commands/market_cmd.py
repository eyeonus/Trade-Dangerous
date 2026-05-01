from __future__ import annotations

from sqlalchemy import func, select, table, column

from .commandenv import Needs, ResultRow
from .exceptions import CommandLineError
from .parsing import (
    ParseArgument, MutuallyExclusiveGroup,
)

from tradedangerous.formatting import RowFormat
from tradedangerous.db.utils import age_in_days


######################################################################
# Parser config

help='Lists items bought/sold at a given station.'
name='market'
epilog=None
needs=Needs.RESOLVER
arguments = [
    ParseArgument(
        'origin',
        help='Station being queried.',
        metavar='STATIONNAME',
        type=str,
    ),
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument(
            '--buying', '-B',
            help='Show items station is buying',
            action='store_true',
        ),
        ParseArgument(
            '--selling', '-S',
            help='Show items station is selling',
            action='store_true',
        ),
    ),
]

######################################################################
# Perform query and populate result set


def render_units(units, level):
    if level == 0:
        return '-'
    if units < 0:
        return '?'
    levelNames = { -1: '?', 1: 'L', 2: 'M', 3: 'H' }
    return "{:n}{}".format(units, levelNames[level])


def run(results, cmdenv, tdb):
    try:
        origin = tdb.lookup_station(cmdenv.origin)
    except LookupError:
        raise CommandLineError(
            "Unrecognized origin station: {}".format(cmdenv.origin)
        )

    buying, selling = cmdenv.buying, cmdenv.selling

    results.summary = ResultRow()
    results.summary.origin = origin
    results.summary.buying = cmdenv.buying
    results.summary.selling = cmdenv.selling

    si = table(
        "StationItem",
        column("item_id"),
        column("station_id"),
        column("demand_price"),
        column("demand_units"),
        column("demand_level"),
        column("supply_price"),
        column("supply_units"),
        column("supply_level"),
        column("modified"),
    )

    stmt = (
        select(
            si.c.item_id,
            si.c.demand_price, si.c.demand_units, si.c.demand_level,
            si.c.supply_price, si.c.supply_units, si.c.supply_level,
            age_in_days(tdb.session, si.c.modified).label("age_days"),
        )
        .where(si.c.station_id == origin.station_id)
    )

    rows = tdb.session.execute(stmt).fetchall()
    if not rows:
        raise CommandLineError(
            "No items available for trade at {}".format(origin.name)
        )

    avg_buying = {}
    avg_selling = {}
    visible_buy_ids = set()
    visible_sell_ids = set()

    for r in rows:
        item_id = int(r.item_id)
        buy_cr = int(r.demand_price or 0)
        buy_units = int(r.demand_units or 0)
        buy_level = int(r.demand_level or 0)
        sell_cr = int(r.supply_price or 0)
        sell_units = int(r.supply_units or 0)
        sell_level = int(r.supply_level or 0)

        has_buy = False if selling else (buy_cr or buy_units or buy_level)
        has_sell = False if buying else (sell_cr or sell_units or sell_level)

        if has_buy:
            visible_buy_ids.add(item_id)
        if has_sell:
            visible_sell_ids.add(item_id)

    if cmdenv.detail:
        if visible_buy_ids:
            avg_buy_stmt = (
                select(
                    si.c.item_id,
                    func.avg(si.c.demand_price).label("avg_price"),
                )
                .where(
                    si.c.demand_price > 0,
                    si.c.item_id.in_(sorted(visible_buy_ids)),
                )
                .group_by(si.c.item_id)
            )
            avg_buying = {
                int(item_id): int(avg_price or 0)
                for item_id, avg_price in tdb.session.execute(avg_buy_stmt)
            }

        if visible_sell_ids:
            avg_sell_stmt = (
                select(
                    si.c.item_id,
                    func.avg(si.c.supply_price).label("avg_price"),
                )
                .where(
                    si.c.supply_price > 0,
                    si.c.item_id.in_(sorted(visible_sell_ids)),
                )
                .group_by(si.c.item_id)
            )
            avg_selling = {
                int(item_id): int(avg_price or 0)
                for item_id, avg_price in tdb.session.execute(avg_sell_stmt)
            }

    for r in rows:
        item = tdb.item_by_id(int(r.item_id))

        row = ResultRow()
        row.item = item

        row.buyCr = int(r.demand_price or 0)
        row.avgBuy = avg_buying.get(item.item_id, 0)
        units, level = int(r.demand_units or 0), int(r.demand_level or 0)
        row.buyUnits = units
        row.buyLevel = level
        row.demand = render_units(units, level)
        hasBuy = False if selling else (row.buyCr or units or level)

        row.sellCr = int(r.supply_price or 0)
        row.avgSell = avg_selling.get(item.item_id, 0)
        units, level = int(r.supply_units or 0), int(r.supply_level or 0)
        row.sellUnits = units
        row.sellLevel = level
        row.supply = render_units(units, level)
        hasSell = False if buying else (row.sellCr or units or level)

        row.age = float(r.age_days or 0.0)

        if hasBuy or hasSell:
            results.rows.append(row)

    if not results.rows:
        if buying:
            raise CommandLineError(
                "No items to buy at {}".format(origin.name)
            )
        elif selling:
            raise CommandLineError(
                "No items for sale at {}".format(origin.name)
            )
        else:
            raise CommandLineError(
                "No items available for trade at {}".format(origin.name)
            )

    results.rows.sort(key=lambda row: row.item.name)
    results.rows.sort(key=lambda row: row.item.category.name)

    return results

#######################################################################
## Transform result set into output


def render(results, cmdenv, tdb):
    longest = max(results.rows, key=lambda row: len(row.item.name))
    longestLen = len(longest.item.name)
    longestDmd = max(results.rows, key=lambda row: len(row.demand)).demand
    longestSup = max(results.rows, key=lambda row: len(row.supply)).supply
    dmdLen = max(len(longestDmd), len("Demand"))
    supLen = max(len(longestSup), len("Supply"))

    showCategories = (cmdenv.detail > 0)

    rowFmt = RowFormat()
    if showCategories:
        rowFmt.prefix = '    '

    sellPred = lambda row: row.sellCr != 0 and row.supply != '-'    # noqa: E731
    buyPred = lambda row: row.buyCr != 0 and row.demand != '-'      # noqa: E731

    rowFmt.addColumn('Item', '<', longestLen,
            key=lambda row: row.item.name)
    if not cmdenv.selling:
        rowFmt.addColumn('Buying', '>', 7, 'n',
            key=lambda row: row.buyCr,
            pred=buyPred)
        if cmdenv.detail:
            rowFmt.addColumn('Avg', '>', 7, 'n',
            key=lambda row: row.avgBuy,
            pred=buyPred)
        if cmdenv.detail > 1:
            rowFmt.addColumn('Demand', '>', dmdLen,
                key=lambda row: row.demand,
                pred=buyPred)
    if not cmdenv.buying:
        rowFmt.addColumn('Selling', '>', 7, 'n',
            key=lambda row: row.sellCr,
            pred=sellPred)
        if cmdenv.detail:
            rowFmt.addColumn('Avg', '>', 7, 'n',
            key=lambda row: row.avgSell,
            pred=sellPred)
        rowFmt.addColumn('Supply', '>', supLen,
            key=lambda row: row.supply,
            pred=sellPred)
    if cmdenv.detail:
        rowFmt.addColumn('Age/Days', '>', 7, '.2f',
        key=lambda row: row.age)

    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')

    lastCat = None
    for row in results.rows:
        if showCategories and row.item.category is not lastCat:
            print("+{}".format(row.item.category.name.upper()))
            lastCat = row.item.category
        print(rowFmt.format(row))
