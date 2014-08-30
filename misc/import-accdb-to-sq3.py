#! /usr/bin/env python
######################################################################
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
######################################################################
# CAUTION: NOT INTENDED FOR GENERAL END-USER OPERATION.
# If you don't know what this script is for, you can safely ignore it.
######################################################################
# TradeDangerous :: Misc :: Legacy data import.
#
# Bootstrap a new SQLite3 database from python files and an existing
# Microsoft Access .ACCDB database.
#
# Note: This is NOT intended to be user friendly. If you don't know what this
# script is for, then you can safely ignore it.

# Main imports.
import sys, os, re

# We'll need a list of star systems.
import dataseed.stars
import dataseed.ships
from tradedb import *

# Filenames/URIs
dbDef   = "dataseed/dbdef.sql"
inDB	= "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=.\\TradeDangerous.accdb"
outDB	= TradeDB.defaultDB

systems, systemByID = {}, {}
stations, stationByOldID = {}, {}
categories, categoryByOldID = {}, {}
items, itemByOldID = {}, {}
debug = 1

# We also track the maximum distance any ship can jump,
# then we use this value to constrain links between stations.
maxJumpDistanceLy = 0.0

######################################################################
# Helpers

class check_item(object):
    """
        Wrapper class that allows us to beautify the output as a sort
        of checklist.

        Usage:
          with check_item("Step description"):
            things_in_step()
    """
    margin = 60
    def __init__(self, title):
        self.title, self.noop = title, False
    def __enter__(self):
        print('- {:.<{width}}:  '.format(self.title, width=self.margin - 3), end='')
        return self
    def __exit__(self, type, value, traceback):
        if value:           # Exception occurred
            print("\a\rX {:.<{width}}: ERROR".format(self.title.upper(), width=self.margin - 3))
            print()
        else:
            print('[+]') if not self.noop else print("\bNO-OP")

def debug_log(level, message):
    if debug >= level:
        print("  | {:^54} |".format(message))

######################################################################
# Main

def main():
    # Destroy the SQLite database if it already exists.
    try: os.remove(outDB)
    except: pass

    with check_item("Connect to MS Access DB"):
        import pypyodbc
        inConn = pypyodbc.connect(inDB)
        inCur  = inConn.cursor()

    with check_item("Connect to SQLite3 DB"):
        import sqlite3
        outConn = sqlite3.connect(outDB)
        outCur  = outConn.cursor()
        # Add a function for calculating distance between stars
        outConn.create_function("calc_distance_sq", 6, TradeDB.distanceSq)

    with check_item("Apply DDL commands from '%s'" % dbDef):
        # Sure, I could have written: outCur.executescript(open(dbDef).read()).commit()
        # but my perl days are behind me...
        ddlScript = open(dbDef).read()
        outCur.executescript(ddlScript)

    with check_item("Populate `System` table"):
        # Star data is stored in 'stars.py'
        stmt = "INSERT INTO System (name, pos_x, pos_y, pos_z) VALUES (?, ?, ?, ?)"
        for star in data.stars.stars:
            outCur.execute(stmt, [ star.name, star.x, star.y, star.z ])
            systemID = int(outCur.lastrowid)
            system = System(systemID, star.name, star.x, star.y, star.z)
            systems[TradeDB.normalizedStr(star.name)] = system
            systemByID[systemID] = system
    debug_log(1, "{} star systems loaded".format(len(systems)))

    with check_item("Populate `Station` table"):
        # We're going to remap the station IDs to new IDs, and we're the accessdb
        # hails back to ED:Beta 1 so it doesn't distinguish between systems and
        # stations, so we'll need to make the associations between stations
        # and the systems they are in.

        # Systems without a station were represented by a station called 'STARNAME*',
        # and we're going to want to filter those out.
        fakeNameRe = re.compile(r'\*$')

        inCur.execute("SELECT ID, station, system FROM Stations ORDER BY ID")
        stmt = "INSERT INTO Station (name, system_id, ls_from_star) VALUES (?, ?, 0)"
        for (ID, stationName, systemName) in inCur:
            if fakeNameRe.search(stationName):
                continue

            system = systems[TradeDB.normalizedStr(systemName)]

            outCur.execute(stmt, [ stationName, system.ID ])
            newStationID = int(outCur.lastrowid)
            oldStationID = int(ID)

            station = Station(newStationID, system, stationName)
            stations[stationName] = station
            stationByOldID[oldStationID] = newStationID
    debug_log(1, "{} stations loaded".format(len(stations)))

    with check_item("Populate `Ship` table"):
        global maxJumpDistanceLy
        # I'm not entirely sure whether I really want this data in the database,
        # it seems perfectly fine to maintain it as a python script.
        stmt = """
                INSERT INTO Ship
                    ( name, capacity, mass, drive_rating, max_ly_empty, max_ly_full, max_speed, boost_speed  )
                VALUES
                    ( ?, ?, ?, ?, ?, ?, ?, ? )
                """
        rows = []
        for ship in data.ships.ships:
            assert ship.maxJump > 0 and ship.maxJumpFull > 0
            assert ship.maxJumpFull <= ship.maxJump
            rows += [ [
                    ship.name
                    , ship.capacity, ship.mass, ship.driveRating
                    , ship.maxJump, ship.maxJumpFull
                    , ship.maxSpeed, ship.boostSpeed
                    ] ]
            maxJumpDistanceLy = max(maxJumpDistanceLy, ship.maxJump, ship.maxJumpFull)
        outCur.executemany(stmt, rows)
    debug_log(1, "{} ships loaded".format(len(data.ships.ships)))
    debug_log(1, "Maximum distance any ship jumps: {:.2f}ly".format(maxJumpDistanceLy))

    shipLocations = 0
    with check_item("Populate `ShipVendor` table"):
        stmt = """
                INSERT INTO ShipVendor
                    ( ship_id, station_id, cost )
                VALUES
                    ( (SELECT ship_id FROM Ship WHERE Ship.name = ?), ?, ? )
                """
        rows = []
        for ship in data.ships.ships:
            for stationName in ship.stations:
                station = stations[TradeDB.listSearch("Station", stationName, stations)]
                rows += [ [
                        ship.name, station.ID, 0    # We don't have prices yet.
                        ] ]
        outCur.executemany(stmt, rows)
        shipLocations = len(rows)
    debug_log(1, "{} ship locations loaded".format(shipLocations))

    with check_item("Populate `Upgrade` table") as check:
        # TODO: Populate Upgrade
        check.noop = True

    with check_item("Populate `UpgradeVendor' table") as check:
        # TODO: UpgradeVendor
        check.noop = True

    with check_item("Populate `Category` table") as check:
        # Copy from accdb and track the newly assigned ID.
        inCur.execute("SELECT ID, category FROM Categories ORDER BY ID")
        categoryID = 0
        stmt = "INSERT INTO Category (category_id, name) VALUES (?, ?)"
        rows = []
        for (ID, categoryName) in inCur:
            categoryID += 1
            rows += [ [ categoryID, categoryName ] ]
            categories[TradeDB.normalizedStr(categoryName)] = categoryID
            categoryByOldID[ID] = categoryID
        outCur.executemany(stmt, rows)
    debug_log(1, "{} item categories loaded".format(len(categories)))

    with check_item("Populate `Item` table") as check:
        inCur.execute("SELECT ID, category_id, item FROM Items")
        stmt = "INSERT INTO Item (item_id, category_id, name) VALUES (?, ?, ?)"
        rows = []
        itemID = 0
        for (ID, category_id, itemName) in inCur:
            itemID += 1
            rows += [ [ itemID, categoryByOldID[category_id], itemName ] ]
            items[TradeDB.normalizedStr(itemName)] = itemID
            itemByOldID[ID] = itemID
        outCur.executemany(stmt, rows)
    debug_log(1, "{} items loaded".format(len(items)))

    pricesCount = 0
    with check_item("Populate `Price` table") as check:
        inCur.execute("SELECT station_id, item_id, sell_cr, buy_cr, ui_order FROM Prices ORDER BY item_id, station_id")
        stmt = """
                INSERT INTO Price
                    (item_id, station_id, ui_order, sell_to, buy_from)
                VALUES
                    (?, ?, ?, ?, ?)
                """
        rows = []
        for (oldStationID, oldItemID, stnPayingCr, stnAskingCr, uiOrder) in inCur:
            itemID, stationID = itemByOldID[oldItemID], stationByOldID[oldStationID]
            rows += [ [ itemID, stationID, uiOrder or 0, stnPayingCr, stnAskingCr or 0 ] ]
        outCur.executemany(stmt, rows)
        pricesCount = len(rows)
    debug_log(1, "{} prices loaded".format(pricesCount))

    outConn.commit()

    numLinks = 0
    with check_item("Checking system links/performance") as check:
        import math
        outCur.execute("""
                SELECT from_system_id, to_system_id, distance_sq
                  FROM vLink
                 WHERE from_system_id < to_system_id
                   AND distance_sq <= ?
                """, [ maxJumpDistanceLy ** 2])
        links = {}
        for (lhsID, rhsID, distSq) in outCur:
            # Round the distance up to the next 100th of a lightyear.
            distLy = math.ceil(math.sqrt(distSq) * 100.0) / 100.0
            # Generate a 64-bit identifier that describes a link
            # between two systems that can be consistent regardless
            # of which way round you use them (that is, you always
            # have to do the min/max the same for each 32 bits)
            linkID = (min(lhsID, rhsID) << 32) | (max(lhsID, rhsID))
            links[linkID] = distLy
            numLinks += 1
    debug_log(1, "Number of links calculated: {}".format(numLinks))

if __name__ == "__main__":
    main()
