#! /usr/bin/env python
#
# Bootstrap a new .SQ3 database from dataseeds and an existing ACCDB database.
#
# Note: This is NOT intended to be user friendly. If you don't know what this
# script is for, then you can safely ignore it.

# Main imports.
import sys, os, re
import sqlite3

######################################################################
# Main

def main():
    conn = sqlite3.connect("TradeDangerous.sq3")
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
          FROM  Station, Item, Price
         WHERE  Station.station_id = Price.station_id
                AND Item.item_id = Price.item_id
         ORDER  BY Station.system_id, Station.station_id, Item.category_id, Price.ui_order, Price.item_id
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
