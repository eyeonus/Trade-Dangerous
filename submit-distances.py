#! /usr/bin/env python

"""
Small tool to submit new star data to EDStarCoordinator.

Use:

    submit-distances.py "system name"
"""

#
# NOTE: This tool is very hacky. If someone wants to clean it up,
# and submit a diff, that'd be greatly appreciated!
#

from __future__ import print_function

import json
import math
import os
import pathlib
import platform
import random
import re
import sys
import tradedb

from tkinter import Tk

try:
    import requests
except ImportError as e:
    import pip
    print("ERROR: Unable to load the Python 'requests' package.")
    approval = input(
        "Do you want me to try and install it with the package manager (y/n)? "
    )
    if approval.lower() != 'y':
        raise e
    pip.main(["install", "--upgrade", "requests"])
    import requests

url = "http://edstarcoordinator.com/api.asmx/SubmitDistances"

defaultStars = [
    "SOL",
    "ASELLUS AUSTRALIS",
    "46 GAMMA HYDRAE",
    "TEJAT POSTERIOR",
    "RHO PUPPIS",
]

extraStars = [
    "1 AURIGAE",
    "103 AQUARII",
    "2MASS J21371591+5726591",
    "52 PI AQUILAE",
    "64 LEONIS",
    "8 LEONIS",
    "AUCOFS UZ-E C28-11",
    "AUCOFS WL-J D10-28",
    "BETLEGEUSE",
    "BLOO DRYE QA-C B33-5",
    "BLU EUQ TJ-Q C5-6",
    "CHRAICHOOE TU-M D8-0",
    "DROJO DX-F C14",
    "DRYEAE AEC HM-C D13-0",
    "ELEPHANT'S TRUNK SECTOR LS-T B3-0",
    "EZ ORIONIS",
    "GM CEPHEI",
    "HD 133948",
    "HIP 24766",
    "HIP 96375",
    "HR 1327",
    "HR 2028",
    "HYPIAE BRUE EM-L D8-0",
    "IC 1396 SECTOR YJ-Z D10",
    "IORASP SP-G D10-0",
    "KY CYGNI",
    "NGC 3199 SECTOR MC-V C2-5",
    "NORTH AMERICA SECTOR IR-W D1-81",
    "PHIPOEA DC-B C1-4278",
    "SADR",
    "SMOJAI HA-H B39-0",
    "SYNUEFAI XI-B D1",
    "VV CEPHEI",
    "VY CANIS MAJORIS",
]


############################################################################


class UsageError(Exception):
    pass


def get_system(tdb):
    args = sys.argv[1:]
    if not args or args[0].startswith('-'):
        raise UsageError(
            "Usage: {} \"system name\"\n"
            "Collects distances for a given system and submits them to "
            "the EDStarCoordinator project.\n"
            "To submit distances for a existing system, prefix the name "
            "with an @ sign, e.g. @SOL"
            .format(sys.argv[0])
        )

    systemName = ' '.join(sys.argv[1:]).upper()
    if systemName.startswith('@'):
        allowUpdate = True
        systemName = systemName[1:]
    else:
        allowUpdate = False

    systemName = systemName.strip()

    try:
        system = tdb.lookupSystem(systemName)
    except (KeyError, tradedb.AmbiguityError, LookupError):
        system = None
        pass
    else:
        if not allowUpdate:
            raise UsageError(
                "ERROR: System '{}' already exists.\n"
                "Prefix the name with an '@' sign if you want to force "
                "submitting distances for an existing system."
            )

    return systemName, system


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


def get_extra_stars():
    extras = set(extraStars)
    try:
        with open("data/extra-stars.txt", "rU") as input:
            for line in input:
                line = line.strip()
                if line:
                    extras.add(line.upper())
    except FileNotFoundError:
        pass
    return random.sample(list(extras), len(extras))


def add_extra_star(name):
    try:
        with open("data/extra-stars.txt", "a") as output:
            print(name, file=output)
    except FileNotFoundError:
        pass


def paste_for_ed(tkroot, text):
    tkroot.clipboard_clear()
    tkroot.clipboard_append(text.lower())


def get_distances(tkroot, distances, stars):
    for star in stars:
        paste_for_ed(tkroot, star)

        dist = input("Distance to {}: ".format(star))
        if dist == 'q':
            return distances, 'q'

        if dist:
            distances.append({
                'name': star.upper(),
                'dist': float(dist),
            })

    return distances, 'end'
 

def check_system(tdb, tdbSys, name):
    try:
        system = tdb.lookupSystem(name)
        if not tdbSys:
            print("KNOWN SYSTEM")
            return
    except (tradedb.AmbiguityError, LookupError, KeyError):
        return

    print("KNOWN SYSTEM: {:.2f}ly".format(
        math.sqrt(tdbSys.distToSq(system))
    ))


############################################################################

def main():
    tdb = tradedb.TradeDB()

    system, tdbSys = get_system(tdb)
    cmdr = get_cmdr(tdb)

    extraStars = get_extra_stars()

    print("Add EDSC Star Distances for \"{}\"".format(system))
    print()
    print("You will now be prompted for distances to various stars.")
    print()
    print(
        "At each prompt, the star name will be copied into your paste buffer. "
        "You should alt-tab into the game and paste the name into the Galaxy "
        "Map's search box. Then alt-tab back and enter the distance value."
    )
    print()
    print(
        "At each prompt enter a ly distance (e.g. 123.45), q to stop, "
        "or leave the line empty if you don't want to enter data for "
        "this star."
    )

    tkroot = Tk()
    tkroot.withdraw()

    print()
    print("~~~ Default Stars: (q to stop listing default stars)")
    distances, term = get_distances(tkroot, list(), defaultStars)

    print()
    print("~~~ Additional Stars: (q to stop listing additional stars)")
    distances, term = get_distances(tkroot, distances, extraStars)

    print()
    print("~~~ Choose Your Own: (leave blank to stop)")
    while True:
        star = input("Enter star name: ").upper()
        star = star.strip()
        if not star:
            break
        for ref in distances:
            if ref['name'] == star:
                print("Duplicate")
                continue
        check_system(tdb, tdbSys, star)
        extras, term = get_distances(tkroot, list(), [star])
        if term != 'q' and len(extras) > 0:
            distances.extend(extras)
            add_extra_star(extras[0]['name'])

    if not distances:
        print("No distances, no submission.")
        return

    print()
    print("P0:", system)
    for ref in distances:
        print("  {}: {}ly".format(
            ref['name'], ref['dist']
        ))
    print()

    ok = input("Does this look correct (y/n)? ")
    if ok != 'y':
        print("Abandoning")
        return

    print("Submitting")

    data = {
            'test': False,
            'ver': 2,
            'commander': cmdr,
            'p0': { 'name': system },
            'refs': distances,
    }
    headers = {
            'Content-Type': 'application/json; charset=utf-8'
    }

    req = requests.post(url, headers=headers, data=json.dumps({'data':data}))

    print("Result: " + req.text)


if __name__ == "__main__":
    try:
        main()
    except UsageError as e:
        print(str(e))
