#! /usr/bin/env python
# Convert accdb to sqlite3 db

import sys
import os
import re

# We'll need a list of star systems.
import stars
from tradedb import *

inDB	= "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=.\\TradeDangerous.accdb"
outDB	= "tradedb.sq3"

# Delete the old file. This is an import tool not a maintenance tool.
try: os.remove(outDB)
except: pass

systems = {}
stations, stationByOldID, stationByNewID = {}, {}, {}

class check_item(object):
    """
        'with' wrapper for putting 
    """
    def __init__(self, title):
        self.title = title
    def __enter__(self):
        print('- {:.<72}:  '.format(self.title), end='')
        return None
    def __exit__(self, type, value, traceback):
        if value:           # Exception occurred
            print("\a\rX {:.<72}: ERROR".format(self.title.upper()))
            print()
        else:
            print('[+]')

# This is not intended to be user friendly.
with check_item("Connect to MS Access DB"):
    import pypyodbc
    inConn = pypyodbc.connect(inDB)
    inCur  = inConn.cursor()

with check_item("Connect to SQLite3 DB"):
    import sqlite3
    outConn = sqlite3.connect(outDB)
    outCur  = outConn.cursor()

with check_item("Initialize SQlite3 DB Structure"):
    outCur.executescript(open("dbdef.sql").read())
    outConn.commit()

with check_item("Populate `Systems` table"):
    stmt = "INSERT INTO Systems (name, pos_x, pos_y, pos_z) VALUES (?, ?, ?, ?)"
    values = []
    for star in stars.stars:
        outCur.execute(stmt, [ star.name, star.x, star.y, star.z ])
        systemID = int(outCur.lastrowid)
        system = System(systemID, star.name, star.x, star.y, star.z)
        systems[TradeDB.normalized_str(star.name)] = system
    outConn.commit()

with check_item("Populate `Stations` table"):
    inCur.execute("SELECT ID, station, system FROM Stations ORDER BY ID")
    stmt = "INSERT INTO Stations (name, system_id, ls_from_star) VALUES (?, ?, 0)"
    fakeNameRe = re.compile(r'\*$')
    values = []
    for (ID, stationName, systemName) in inCur:
        if fakeNameRe.search(stationName):
            pass
        system = systems[TradeDB.normalized_str(systemName)]

        outCur.execute(stmt, [ stationName, system.ID ])
        newStationID = int(outCur.lastrowid)
        oldStationID = int(ID)

        station = Station(newStationID, system, stationName)
        stationByOldID[oldStationID] = station
        stationByNewID[newStationID] = station
    outConn.commit()
