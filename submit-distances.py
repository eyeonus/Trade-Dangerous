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

from misc.edsc import StarSubmission
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

standardStars = [
    "SOL",
    "ASELLUS AUSTRALIS",
    "46 GAMMA HYDRAE",
    "TEJAT POSTERIOR",
    "RHO PUPPIS",
]

outlierStars = [
    "1 AURIGAE",
    "103 AQUARII",
    "2MASS J21371591+5726591",
    "52 PI AQUILAE",
    "64 LEONIS",
    "8 LEONIS",
    "AUCOFS UZ-E C28-11",
    "AUCOFS WL-J D10-28",
    "BETELGEUSE",
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
        raise UsageError("""Usage: {} \"new system\"

This tool prompts you with the names of several systems and asks you
to find the distance from "new system" to those systems.

When the tool prompts you with a system's name, it will also copy it
into your clipboard. Alt-Tab into the game, go to the GALAXY MAP and
the NAVIGATION tab, and paste (SHIFT+INS or CTRL-V) the name. Hit
enter and the map will pan to the system and tell you how far away
it is.

(Hint: Double-click the right end of the search box, then press
SHIFT+HOME to select the current text and backspace to delete it).

You will first be prompted for 'Standard Systems' which is a list of
5 fairly well known systems.

To skip a system: just hit enter.

After that you'll be prompted with a list of outlier stars. Again you
can just press enter to skip them or q to skip to the next section.

Finally you will be given a chance to choose stars not already listed.
Any stars you enter here will be saved in 'data/extra-stars.txt' and
added to the 'outlier stars' in future runs.

Finally you'll be asked to review the data you've entered and, if it
looks good, it will be submitted to EDSC.
"""
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
                "submitting distances for an existing system, e.g. @SOL."
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


def get_outliers():
    outliers = set(outlierStars)
    try:
        with open("data/extra-stars.txt", "rU") as input:
            for line in input:
                line = line.strip()
                if line:
                    outliers.add(line.upper())
    except FileNotFoundError:
        pass
    return random.sample(list(outliers), len(outliers))


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

    outliers = get_outliers()

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

    print("The more distances you submit per star, the better.")
    print()

    tkroot = Tk()
    tkroot.withdraw()

    print()
    print("""
===================================================
STANDARD STARS: (q to stop listing standard stars)

  These are stars with well-known positions.
===================================================
""")
    distances, term = get_distances(tkroot, list(), standardStars)

    print("""
===================================================
OUTLIERS: (q to stop listing outliers)

  Assorted outlier stars from around the galaxy
  mixed with any stars from data/extra-stars.txt.
===================================================
""")
    distances, term = get_distances(tkroot, distances, outliers)

    print("""
===================================================
CHOOSE YOUR OWN: (leave blank to stop)

  Specify additional stars, the names will be saved
  to data/extra-stars.txt so they appear in the
  outliers section in future.
===================================================
""")
    while True:
        star = input("Enter star name: ")
        star = star.strip()
        if not star or star == 'q':
            break
        star = star.upper()
        for ref in distances:
            if ref['name'] == star:
                print("Duplicate")
                continue
        check_system(tdb, tdbSys, star)
        extras, term = get_distances(tkroot, list(), [star])
        if term != 'q' and len(extras) > 0:
            distances.extend(extras)
            if not star in outliers:
                add_extra_star(star)

    if not distances:
        print("No distances, no submission.")
        return

    print()
    print("System:", system)
    print("Distances:")
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

    sub = StarSubmission(
        star=system,
        commander=cmdr,
        refs=distances,
    )
    resp = sub.submit()

    status = resp['status']['input'][0]['status']
    if status['statusnum'] == 0:
        print(status['msg'])
    else:
        print("ERROR: {} ({})".format(
            status['msg'], status['statusnum'],
        ))


if __name__ == "__main__":
    try:
        main()
    except UsageError as e:
        print(str(e))

