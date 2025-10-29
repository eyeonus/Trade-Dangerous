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
from .db import orm_models as SA
from .tradeexcept import TradeException


class Element:      # TODO: enum?
    basic     = 1 << 0
    supply    = 1 << 1
    timestamp = 1 << 2
    full      = basic | supply | timestamp
    blanks    = 1 << 31


######################################################################
# Main

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
        ID: [name, systems.get(sysID)]
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
    
    defaultDemandVal = 0 if defaultZero else -1
    
    # Build the main query
    q = (
        session.query(
            SA.StationItem.station_id,
            SA.Item.item_id,
            SA.StationItem.demand_price,
            SA.StationItem.supply_price,
            SA.StationItem.demand_units,
            SA.StationItem.demand_level,
            SA.StationItem.supply_units,
            SA.StationItem.supply_level,
            SA.StationItem.modified,
            SA.Item.name,
            SA.Item.category_id,
            SA.Category.name.label("category_name"),
            SA.Station.name.label("station_name"),
            SA.System.name.label("system_name"),
        )
        .join(SA.Item, SA.Item.item_id == SA.StationItem.item_id)
        .join(SA.Category, SA.Category.category_id == SA.Item.category_id)
        .join(SA.Station, SA.Station.station_id == SA.StationItem.station_id)
        .join(SA.System, SA.System.system_id == SA.Station.system_id)
        .order_by(SA.Station.station_id, SA.Category.name, SA.Item.ui_order)
    )
    
    if stationID:
        q = q.filter(SA.StationItem.station_id == stationID)
    
    # Set up output
    if not file:
        file = sys.stdout
    
    if stationID:
        stationSet = str(stations[stationID])
    else:
        stationSet = "ALL Systems/Stations"
    
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
        "\n".format(stationSet)
    )
    
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
    header = outFmt.format(
        "Item Name",
        "SellCr", "BuyCr",
        "Demand", "Supply",
        "Timestamp",
    )
    file.write('#' + header[1:])
    
    naIQL = "-"
    unkIQL = "?"
    defIQL = "?" if not defaultZero else "-"
    
    # Main loop — stream results instead of preloading
    output = ""
    lastStn, lastCat = None, None
    for row in q.yield_per(1000).execution_options(stream_results=True):
        stnID = row.station_id
        itemID = row.item_id
        station = row.station_name
        system = row.system_name
        item = row.name
        catID = row.category_id
        category = row.category_name
        
        # Guard against bad system names
        if not system:
            raise TradeException(
                f"Station {station} (ID {stnID}) is linked to a system with no name."
            )
        
        if stnID != lastStn:
            file.write(output)
            output = f"\n\n@ {system.upper()}/{station}\n"
            lastStn = stnID
            lastCat = None
        
        if catID != lastCat:
            output += f"   + {category}\n"
            lastCat = catID
        
        demandCr = row.demand_price or 0
        supplyCr = row.supply_price or 0
        demandUnits = row.demand_units or defaultDemandVal
        demandLevel = row.demand_level or defaultDemandVal
        supplyUnits = row.supply_units or defaultDemandVal
        supplyLevel = row.supply_level or defaultDemandVal
        
        # Demand/supply formatting
        if supplyCr > 0:
            demandStr = defIQL if demandCr <= 0 else unkIQL
            supplyStr = (
                naIQL if supplyLevel == 0
                else (f"{supplyUnits if supplyUnits >= 0 else '?'}{levelDesc[supplyLevel+1]}")
            )
        else:
            demandStr = (
                naIQL if demandCr == 0 or demandLevel == 0
                else (f"{demandUnits if demandUnits >= 0 else '?'}{levelDesc[demandLevel+1]}")
            )
            supplyStr = naIQL
        
        modified = row.modified or ""
        output += outFmt.format(item, demandCr, supplyCr, demandStr, supplyStr, modified)
    
    file.write(output)
