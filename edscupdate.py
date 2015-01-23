#! /usr/bin/env python

"""
Usage:
    edscupdate.py "<current system name>" ["<date>"]

This tool looks for changes in the EDSC service since the most
recent "modified" date in the System table or the date supplied
on the command line.

It then tries to do some validation but also requires user
confirmation.

For each star that appears to be new, it copies the name into
the clipboard so you can paste it into the "SEARCH" box in the
game to verify that the name is correct.

Additionally it shows you the distance from "current system"
to the star as a way to verify the co-ordinates.

This helps to catch cases where people have typo'd system names,
but given the right coordinates; it also helps catch cases where
people have used the star name from in-system which sometimes
differs from the star name in the galaxy map.

For each star you can type "y" to accept the star, "n" to skip it
or "q" to stop recording.
"""


import tradedb
import math
import misc.edsc
import os
import re
import sys

from tkinter import Tk

class UsageError(Exception):
    pass


def get_cmdr(tdb):
    try:
        return os.environ['CMDR']
    except KeyError:
        pass

    if 'SHLVL' not in os.environ and platform.system() == 'Windows':
        how = 'set CMDR="yourname"'
    else:
        how = 'export CMDR="yourname"'

    raise UsageError(
        "No 'CMDR' variable set.\n"
        "You can set an environment variable by typing:\n"
        "  "+how+"\n"
        "at the command/shell prompt."
    )


r = Tk()
r.withdraw()

if len(sys.argv) < 2 or len(sys.argv) > 3:
    print("Usage: {} <origin system> [date]".format(sys.argv[0]))
    sys.exit(1)

tdb = tradedb.TradeDB()
date = tdb.query("SELECT MAX(modified) FROM System").fetchone()[0]

cmdr = get_cmdr(tdb)

startSys = tdb.lookupPlace(sys.argv[1])
ox, oy, oz = startSys.posX, startSys.posY, startSys.posZ

if len(sys.argv) > 2:
    date = sys.argv[2]
    if not date.startswith("201"):
        print("ERROR: Invalid date {}".format(date))
        sys.exit(2)

print("start date: {}".format(date), file=sys.stderr)

edsq = misc.edsc.StarQuery(
    test=False,
    confidence=2,
    date=date,
    )
data = edsq.fetch()

ignore = [
    'ADAM NAPAT',
    'AN SEXSTANS',
    'ALRAI SECTOR EL-Y C3-1',
    'ALRAI SECTOR OI-T B3-6 A', # No 'A' at the end
    'COL 285 SECTOR ZJ-Y B140-1',
    'CORE SYS SECTOR HH-V B2-7',
    'CRU7CIS SECTOR EQ-Y B2',
    'CRUCIS SECTO GB-X B1-0',
    'CRUCIS SECTOR FM-V B2-O',
    'CRUCIS SECTOR MD-S B4-6',
    'CRUCIS SECTOR YE-A D142',
    'DQ TUCANE',
    'ED TUCANAE',
    'HYADES SECTOR WF-M B8-3',
    'HYADES SECTOR ZA-K B9-0',
    'ICZ EW-V B2-E',
    'ICZ FW-V B2-6',
    'LP 452-10 A',
    'LT 9028',
    'PHE ZHUA',
    'PISCIUM SECTOR BM-L AB-1', # should be A8-1
    'ROSS 41 A',
    'SCORPII SECTOR KB-X A1-01', # should be SCORPII SECTOR KB-X A1-0
    'WISE 0410+ 1502', # should be WISE 0410+1502
    'WISE 2200-3628',
    'WOLF 851 A',
    'ZAGARAS',
]

if edsq.status['statusnum'] != 0:
    raise Exception("Query failed: {} ({})".format(
                edsq.status['msg'],
                edsq.status['statusnum'],
            ))

date = data['date']
systems = data['systems']

def paste(text):
    r.clipboard_clear()
    r.clipboard_append(text.lower())


def dist(x, y, z):
    return math.sqrt((ox-x)**2 + (oy-y)**2 + (oz-z)**2)

def ischange(sysinfo):
    name = sysinfo['name'] = sysinfo['name'].upper()
    if name.startswith("argetl"):
        return False
    if name in ignore:
        return False
    x, y, z = sysinfo['coord']
    try:
        place = tdb.systemByName[name]
        if place.posX == x and place.posY == y and place.posZ == z:
            return False
    except KeyError:
        place = None
    sysinfo['place'] = place
    return True

systems = [
    sysinfo for sysinfo in systems if ischange(sysinfo)
]
print("{} changes".format(len(systems)))

if len(systems) > 0:
    print("At the prompt enter y, n or q. Default is n")

with open("new.systems.csv", "w") as output:
    try:
        for sysinfo in systems:
            name = sysinfo['name']
            x, y, z = sysinfo['coord']
            place = sysinfo['place']
            if place:
                print("! @{} [{},{},{}] vs @{} [{},{},{}]".format(
                    name, x, y, z,
                    place.dbname, place.posX, place.posY, place.posZ
                ), file=sys.stderr)
            else:
                created = sysinfo['createdate']

                # is it in the database?
                cur = tdb.query("""
                    SELECT name, pos_x, pos_y, pos_z
                      FROM System
                     WHERE pos_x BETWEEN ? and ?
                       AND pos_y BETWEEN ? and ?
                       AND pos_z BETWEEN ? and ?
                """, [ 
                    x - 0.5, x + 0.5,
                    y - 0.5, y + 0.5,
                    z - 0.5, z + 0.5,
                ])
                for mname, mx, my, mz in cur:
                    print(
                            "! @{} [{},{},{}] matches coords for "
                            "@{} [{},{},{}]".format(
                                name, x, y, z,
                                mname, mx, my, mz
                    ), file=sys.stderr)
                distance = float("{:.2f}".format(dist(x, y, z)))
                paste(name.lower())
                prompt = "'{}'".format(name)
                prompt += " ({:.2f}ly)".format(distance)

                ok = input(prompt+"? ".format(name))
                if ok.lower() == 'q':
                    break
                if ok.lower() == 'y':
                    print("'{}',{},{},{},'Release 1.00-EDStar','{}'".format(
                        name, x, y, z, created,
                    ), file=output)
                    print("Submitting distance")
                    sub = misc.edsc.StarSubmission(
                        star=name.upper(),
                        commander=cmdr,
                        distances={startSys.name(): distance},
                    )
                    r = sub.submit()
                    misc.edsc.annotate_submission_response(r)
                    print()
    except KeyboardInterrupt:
        print("^C")

