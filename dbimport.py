#! /usr/bin/env python
#
# Bootstrap a new .SQ3 database from dataseeds and an existing ACCDB database.
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
outDB	= "tradedb.sq3"

systems = {}
stations, stationByOldID, stationByNewID = {}, {}, {}
categories, categoryByOldID, categoryByNewID = {}, {}, {}

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

    with check_item("Apply DDL commands from '%s'" % dbDef):
        # Sure, I could have written: outCur.executescript(open(dbDef).read()).commit()
        # but my perl days are behind me...
        ddlScript = open(dbDef).read()
        outCur.executescript(ddlScript)

    with check_item("Populate `System` table"):
        # Star data is stored in 'stars.py'
        stmt = "INSERT INTO System (name, pos_x, pos_y, pos_z) VALUES (?, ?, ?, ?)"
        for star in dataseed.stars.stars:
            outCur.execute(stmt, [ star.name, star.x, star.y, star.z ])
            systemID = int(outCur.lastrowid)
            system = System(systemID, star.name, star.x, star.y, star.z)
            systems[TradeDB.normalized_str(star.name)] = system

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
                pass
            system = systems[TradeDB.normalized_str(systemName)]

            outCur.execute(stmt, [ stationName, system.ID ])
            newStationID = int(outCur.lastrowid)
            oldStationID = int(ID)

            station = Station(newStationID, system, stationName)
            stations[stationName] = station
            stationByOldID[oldStationID] = station
            stationByNewID[newStationID] = station

    with check_item("Populate `Ship` table"):
        # I'm not entirely sure whether I really want this data in the database,
        # it seems perfectly fine to maintain it as a python script.
        stmt = """
                INSERT INTO Ship
                    (
                      name
                    , capacity, mass, drive_rating
                    , max_ly_empty, max_ly_full
                    , max_speed, boost_speed 
                    )
                VALUES
                    (
                      ?
                    , ?, ?, ?
                    , ?, ?
                    , ?, ?
                    )
                """
        rows = []
        for ship in dataseed.ships.ships:
            rows += [ [
                    ship.name
                    , ship.capacity, ship.mass, ship.driveRating
                    , ship.maxJump, ship.maxJumpFull
                    , ship.maxSpeed, ship.boostSpeed
                    ] ]
        outCur.executemany(stmt, rows)

    with check_item("Populate `ShipVendor` table"):
        stmt = """
                INSERT INTO ShipVendor
                    ( ship_id, station_id, cost )
                VALUES
                    ( (SELECT ship_id FROM Ship WHERE Ship.name = ?), ?, ? )
                """
        rows = []
        for ship in dataseed.ships.ships:
            for stationName in ship.stations:
                station = stations[TradeDB.list_search("Station", stationName, stations)]
                rows += [ [
                        ship.name, station.ID, 0    # We don't have prices yet.
                        ] ]
        outCur.executemany(stmt, rows)

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
            categories[TradeDB.normalized_str(categoryName)] = categoryID
            categoryByOldID[ID] = categoryID
            categoryByNewID[categoryID] = ID
        outCur.executemany(stmt, rows)

    outConn.commit()


if __name__ == "__main__":
    main()
