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

from misc.edsc import StarSubmission, annotate_submission_response
from tkinter import Tk

try:
    import requests
except ImportError as e:
    print("""ERROR: Unable to load the Python 'requests' package.

This script uses a Python module/package called 'requests' to allow
it to talk to the EDSC web service. This package is not installed
by default, but it can be installed with Python's package manager (pip).

You can either install/update it yourself, e.g.:

  pip install --upgrade requests

or if you like, I can try and install it for you now
""")
    approval = input(
        "Do you want me to try and install it with the package manager (y/n)? "
    )
    if approval.lower() != 'y':
        print("You didn't type 'y' so I'm giving up.")
        raise e
    import pip
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
    "2MASS J21371591+5726591",
    "64 LEONIS",
    "AUCOFS UZ-E C28-11",
    "BETELGEUSE",
    "BLU EUQ TJ-Q C5-6",
    "DROJO DX-F C14",
    "ELEPHANT'S TRUNK SECTOR LS-T B3-0",
    "GM CEPHEI",
    "HIP 24766",
    "HR 1327",
    "HYPIAE BRUE EM-L D8-0",
    "IORASP SP-G D10-0",
    "NGC 3199 SECTOR MC-V C2-5",
    "PEPPER",
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
""".format(sys.argv[0])
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
                .format(systemName)
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


def paste_for_ed(tkroot, text):
    tkroot.clipboard_clear()
    tkroot.clipboard_append(text.lower())


def get_distances(tkroot, distances, stars):
    for star in stars:
        # Check it's not already in the list
        star = star.upper()
        for d in distances:
            if d['name'] == star:
                continue

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


def add_extra_stars(extraStars):
    try:
        with open("data/extra-stars.txt", "a") as output:
            print(
                "Adding stars to data/extra-stars.txt: {}".format(
                    ', '.join(extraStars)
            ))
            for star in extraStars:
                print(star, file=output)
    except FileNotFoundError:
        pass


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
  To avoid saving a particular star to this file,
  prefix the name with a '*' (e.g. *SOL).
===================================================
""")
    newOutliers = []
    while True:
        star = input("Enter star name: ")
        star = star.strip()
        if not star or star == 'q':
            break
        # Remove surrounding quotes
        skipSave = False
        while star.startswith('*'):
            skipSave = True
            star = star[1:].strip()
        star = re.sub(r'^("|\')+\s*(.*)\s*\1+', r'\2', star)
        if star.find('"') >= 0:
            print("Invalid star name")
            continue
        while star.startswith('*'):
            skipSave = True
            star = star[1:].strip()
        star = star.upper()
        for ref in distances:
            if ref['name'] == star:
                print("'{}' is already listed.")
                continue
        check_system(tdb, tdbSys, star)
        extras, term = get_distances(tkroot, list(), [star])
        if term != 'q' and len(extras) > 0:
            distances.extend(extras)
            if not skipSave and star not in outliers:
                newOutliers.append(star)

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

    print()
    print("Submitting")

    sub = StarSubmission(
        star=system,
        commander=cmdr,
        refs=distances,
    )
    resp = sub.submit()

    try:
        annotate_submission_response(resp)
    except:
        status = resp['status']['input'][0]['status']
        if status['statusnum'] == 0:
            print(status['msg'])
            print()
        else:
            print("ERROR: {} ({})".format(
                status['msg'], status['statusnum'],
            ))

    add_extra_stars(newOutliers)


if __name__ == "__main__":
    try:
        main()
    except UsageError as e:
        print(str(e))

