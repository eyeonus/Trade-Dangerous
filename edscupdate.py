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
import misc.clipboard
import misc.edsc
import os
import re
import sys


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


if 'DEBUG' in os.environ or 'TEST' in os.environ:
    testMode = True
else:
    testMode = False

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
    test=testMode,
    confidence=2,
    date=date,
    )
data = edsq.fetch()

ignore = [
]

if edsq.status['statusnum'] != 0:
    raise Exception("Query failed: {} ({})".format(
                edsq.status['msg'],
                edsq.status['statusnum'],
            ))

date = data['date']
systems = data['systems']
clip = misc.clipboard.SystemNameClip()


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
    print(
        "To correct a typo'd name that has the correct distance, "
        "use =correct name"
    )
    print()

with open("tmp/new.systems.csv", "a") as output:
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
                clip.copy_text(name.lower())
                prompt = "'{}'".format(name)
                prompt += " ({:.2f}ly)".format(distance)

                ok = input(prompt+"? ".format(name))
                if ok.lower() == 'q':
                    break
                if ok.startswith('='):
                    name = ok[1:].strip().upper()
                    ok = 'y'
                    with open("data/extra-stars.txt", "a") as fh:
                        print(name, file=fh)
                        print("Added to data/extra-stars.txt")
                if ok.lower() == 'y':
                    print("'{}',{},{},{},'Release 1.00-EDStar','{}'".format(
                        name, x, y, z, created,
                    ), file=output)
                    sub = misc.edsc.StarSubmission(
                        star=name.upper(),
                        commander=cmdr,
                        distances={startSys.name(): distance},
                        test=testMode,
                    )
                    r = sub.submit()
                    result = misc.edsc.StarSubmissionResult(
                        star=name.upper(),
                        response=r,
                    )

                    print(str(result))

    except KeyboardInterrupt:
        print("^C")

