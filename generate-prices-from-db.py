#! /usr/bin/env python
#
# Generate .prices data from the current db.
#
# Note: This is NOT intended to be user friendly. If you don't know what this
# script is for, then you can safely ignore it.

# Main imports.
import sys, os, re
import sqlite3
from tradedb import TradeDB

######################################################################
# Main

def main():
    print("""
# SOURCE List of item prices for TradeDangerous.
#
# This file is used by TradeDangerous to populate the
# SQLite databsae with prices, whenever this file is
# updated or you delete the TradeDangerous.db file.

# FORMAT:
#
# # ...
#   A comment
#
# @ SYSTEM NAME/Station Name
#   Sets the current station
#   e.g. @ CHANGO/Chango Dock
#
# + Product Category
#   Sets the current product category
#   e.g. + Consumer Tech
#
# Item Name   Value    Cost
#   Item value line.
#     Item Name is the name of the item, e.g. Fish
#     Value is what the STATION pays for the item,
#     Cost is how much the item costs FROM the station
#
# Example:
# @ CHANGO/Chango Dock
#  + Chemicals
#     Mineral Oil     150    0
#     Hydrogen Fuels  63     0
#     Explosives      150  160
#
# This gives prives for items under the "Chemicals"
# heading. Mineral oil was listed first and was selling
# at the station for 150cr.
# Hydrogen Fuels was listed 3rd and sells for 63 cr.
# Explosives was listed 2nd and sells for 150 cr AND
# can be bought here for 160cr.
#

""")

    conn = sqlite3.connect(TradeDB.defaultDB)
    cur  = conn.cursor()

    systems = { ID: name for (ID, name) in cur.execute("SELECT system_id, name FROM system") }
    stations = { ID: name for (ID, name) in cur.execute("SELECT station_id, name FROM station") }
    categories = { ID: name for (ID, name) in cur.execute("SELECT category_id, name FROM category") }
    items = { ID: name for (ID, name) in cur.execute("SELECT item_id, name FROM item") }

    # find longest item name
    longestName = max(items.values(), key=lambda name: len(name))
    longestNameLen = len(longestName)

    cur.execute("""
        SELECT  Station.system_id
                , Price.station_id
                , Item.category_id
                , Price.item_id
                , Price.sell_to
                , Price.buy_from
          FROM  Station, Item, Category, Price
         WHERE  Station.station_id = Price.station_id
                AND (Item.category_id = Category.category_id) AND Item.item_id = Price.item_id
         ORDER  BY Station.system_id, Station.station_id, Category.name, Price.ui_order, Price.item_id
    """)
    lastSys, lastStn, lastCat = None, None, None
    for (sysID, stnID, catID, itemID, fromStn, toStn) in cur:
        system = systems[sysID]
        if system is not lastSys:
            if lastStn: print("\n")
            lastStn, lastCat = None, None
            lastSys = system

        station = stations[stnID]
        if station is not lastStn:
            if lastStn: print("")
            lastCat = None
            print("@ {}/{}".format(system.upper(), station))
            lastStn = station

        category = categories[catID]
        if category is not lastCat:
            print("   + {}".format(category))
            lastCat = category

        print("      {:<{width}} {:7d} {:6d}".format(items[itemID], fromStn, toStn, width=longestNameLen))


if __name__ == "__main__":
    main()
