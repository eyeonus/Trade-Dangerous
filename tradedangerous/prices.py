# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Stefan 'Tromador' Morrell 2025
# Copyright (C) Jonathan 'eyeonus' Jones 2018-2025
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Modules :: Generate TradeDangerous.prices

import sys
from sqlalchemy.orm import Session
from sqlalchemy import func
from tradedangerous.db import orm_models as SA


class Element:  # TODO: consider converting to enum.IntFlag
    basic     = 1 << 0
    supply    = 1 << 1
    timestamp = 1 << 2
    full      = basic | supply | timestamp
    blanks    = 1 << 31


def dumpPrices(
    session: Session,      # SQLAlchemy session
    elementMask,           # which columns to output
    stationID=None,        # limits to one station
    file=None,             # file handle to write to
    defaultZero=False,
    debug=0,
):
    """
    Generate a prices list using data from the DB.
    If stationID is not None, only the specified station is dumped.
    If file is not None, outputs to the given file handle.
    """

    withTimes = elementMask & Element.timestamp
    getBlanks = elementMask & Element.blanks

    # ORM queries to build lookup dicts
    systems = dict(
        session.query(SA.System.system_id, SA.System.name).all()
    )

    stations = {
        ID: [name, systems[sysID]]
        for ID, name, sysID in session.query(
            SA.Station.station_id, SA.Station.name, SA.Station.system_id
        ).all()
    }

    categories = dict(
        session.query(SA.Category.category_id, SA.Category.name).all()
    )

    items = {
        ID: [name, catID, categories[catID]]
        for ID, name, catID in session.query(
            SA.Item.item_id, SA.Item.name, SA.Item.category_id
        ).all()
    }

    # find longest item name (for formatting)
    longestName = max(items.values(), key=lambda ent: len(ent[0]))
    longestNameLen = len(longestName[0])

    if stationID:
        # Check if station has any prices
        count = (
            session.query(SA.StationItem)
            .filter(SA.StationItem.station_id == stationID)
            .count()
        )
        if count == 0:
            getBlanks = True

    defaultDemandVal = 0 if defaultZero else -1
    stationFilter = stationID
    itemJoinOuter = getBlanks

    # Current timestamp for defaulting modified
    now = session.query(func.now()).scalar()

    # Build base query
    q = session.query(
        SA.Station.station_id,
        SA.Item.item_id,
        func.ifnull(SA.StationItem.demand_price, 0),
        func.ifnull(SA.StationItem.supply_price, 0),
        func.ifnull(SA.StationItem.demand_units, defaultDemandVal),
        func.ifnull(SA.StationItem.demand_level, defaultDemandVal),
        func.ifnull(SA.StationItem.supply_units, defaultDemandVal),
        func.ifnull(SA.StationItem.supply_level, defaultDemandVal),
        SA.StationItem.modified,
    ).select_from(SA.Station)

    # Join Item and Category
    q = q.join(SA.Item, SA.Item.category_id == SA.Category.category_id).join(SA.Category)

    # Join or outerjoin StationItem
    if itemJoinOuter:
        q = q.outerjoin(
            SA.StationItem,
            (SA.StationItem.station_id == SA.Station.station_id)
            & (SA.StationItem.item_id == SA.Item.item_id),
        )
    else:
        q = q.join(
            SA.StationItem,
            (SA.StationItem.station_id == SA.Station.station_id)
            & (SA.StationItem.item_id == SA.Item.item_id),
        )

    # Optional station filter
    if stationFilter:
        q = q.filter(SA.Station.station_id == stationFilter)

    # Ordering
    q = q.order_by(SA.Station.station_id, SA.Category.name, SA.Item.ui_order)

    if debug:
        print(str(q))

    rows = q.all()

    lastStn, lastCat = None, None

    if not file:
        file = sys.stdout

    stationSet = (
        str(stations[stationID]) if stationID else "ALL Systems/Stations"
    )

    file.write(
        "# TradeDangerous prices for {}\n"
        "\n"
        "# REMOVE ITEMS THAT DON'T APPEAR IN THE UI\n"
        "# ORDER IS REMEMBERED: Move items around within categories "
            "to match the game UI\n"
        "\n"
        "# File syntax:\n"
        "# <item name> <sell> <buy> [<demand> <supply> [<timestamp>]]\n"
        "#   Use '?' for demand/supply when you don't know/care,\n"
        "#   Use '-' for demand/supply to indicate unavailable,\n"
        "#   Otherwise use a number followed by L, M or H, e.g.\n"
        "#     1L, 23M or 30000H\n"
        "# If you omit the timestamp, the current time will be used when "
            "the file is loaded.\n"
        "\n".format(
            stationSet
    ))

    levelDesc = "?0LMH"
    maxCrWidth = 7
    levelWidth = 9

    outFmt = (
        "      {{:<{width}}}"
        " {{:>{crwidth}}}"
        " {{:>{crwidth}}}"
        "  {{:>{lvlwidth}}}"
        " {{:>{lvlwidth}}}".format(
            width=longestNameLen,
            crwidth=maxCrWidth,
            lvlwidth=levelWidth,
        )
    )
    if withTimes:
        outFmt += "  {}"
    outFmt += "\n"
    output = outFmt.format(
        "Item Name",
        "SellCr", "BuyCr",
        "Demand", "Supply",
        "Timestamp",
    )
    file.write('#' + output[1:])

    naIQL = "-"
    unkIQL = "?"
    defIQL = "?" if not defaultZero else "-"

    output = ""

    for (
        stnID,
        itemID,
        fromStn,
        toStn,
        demand,
        demandLevel,
        supply,
        supplyLevel,
        modified,
    ) in rows:
        modified = modified or now
        station, system = stations[stnID]
        item, catID, category = items[itemID]

        if stnID != lastStn:
            file.write(output)
            output = f"\n\n@ {system.upper()}/{station}\n"
            lastStn = stnID
            lastCat = None

        if catID is not lastCat:
            output += f"   + {category}\n"
            lastCat = catID

        # Is this item on sale?
        if toStn > 0:
            demandStr = defIQL if fromStn <= 0 else unkIQL
            if supplyLevel == 0:
                supplyStr = naIQL
            elif supplyLevel < 0 and supply <= 0:
                supplyStr = defIQL
            else:
                units = "?" if supply < 0 else str(supply)
                level = levelDesc[supplyLevel + 1]
                supplyStr = units + level
        else:
            if fromStn == 0 or demandLevel == 0:
                demandStr = naIQL
            elif demandLevel < 0 and demand <= 0:
                demandStr = defIQL
            else:
                units = "?" if demand < 0 else str(demand)
                level = levelDesc[demandLevel + 1]
                demandStr = units + level
            supplyStr = naIQL

        output += outFmt.format(
            item,
            fromStn,
            toStn,
            demandStr,
            supplyStr,
            modified,
        )

    file.write(output)
