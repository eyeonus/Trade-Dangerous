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

from misc.edsc import StarSubmission, StarSubmissionResult, SubmissionError
from misc.clipboard import SystemNameClip

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
    "RHO PUPPIS",
    "HIP 34707",
]

outlierStars = [
    "COL 285 SECTOR QE-M B22-6",
    "DITIBI",
    "GAMMA MUSCAE",
    "HIP 80454",
    "HYADES SECTOR NJ-O B7-4",
    "M CARINAE",
    "PUPPIS SECTOR ZZ-Y B4",
    "WREGOE YL-W B56-5",
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

    systemName = ' '.join(args[0].split()).upper()
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

    argv = args[1:]
    if argv:
        if len(argv) == 1 and argv[0].startswith("--pick"):
            _, _, num = argv[0].partition("=")
            try:
                num = int(num)
            except TypeError:
                raise UseageError("Expecting --pick=<number>")
            if num <= 0:
                raise UsageError("Expecting --pick to specify a number > 0")
            numSystems = len(tdb.systemByName)
            if numSystems < 1:
                raise UsageError(
                    "Your TD database doesn't contain any systems"
                )
            num = min(num, numSystems)
            destinations = random.sample([
                sysName for sysName in tdb.systemByName.keys()
            ], num)
        else:
            destinations = argv
    else:
        destinations = None

    return systemName, system, destinations


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
                if line and not line.startswith('#'):
                    outliers.add(line.upper())
    except FileNotFoundError:
        pass
    return random.sample(list(outliers), len(outliers))


def get_distances(clip, distances, stars):
    starNo = 0
    for star in stars:
        starNo += 1
        # Check it's not already in the list
        star = star.upper()
        for d in distances:
            if d['name'] == star:
                continue

        clip.copy_text(star)

        if len(stars) > 1:
            prefix = "{:>2}/{:2}: ".format(starNo, len(stars))
        else:
            prefix = ""
        dist = input(prefix + "Distance to {}: ".format(star))
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

    print("KNOWN SYSTEM: {:.2f} ly".format(
        tdbSys.distanceTo(system)
    ))


def add_extra_stars(extraStars):
    if not extraStars:
        return
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


def submit_distances(system, cmdr, distances):
    print()
    print("System:", system)
    print("Distances:")
    for ref in distances:
        print("  {}: {:.02f} ly".format(
            ref['name'], ref['dist']
        ))
    print()

    ok = input("Does this look correct (y/n)? ")
    if ok != 'y':
        print("Stopped")
        return

    if 'DEBUG' in os.environ or 'TEST' in os.environ:
        testMode = True
    else:
        testMode = False

    if os.environ.get("ASSERT"):
        print()
        for ref in distances:
            print("Submitting ({}->{} {})".format(
                ref['name'], system, ref['dist'],
            ))
            sub = StarSubmission(
                star=ref['name'],
                commander=cmdr,
                refs=[{'name': system, 'dist': ref['dist']}],
                test=testMode,
            )
            sub.submit()

    print()
    print("Submitting ({})".format("TEST" if testMode else "Live"))

    sub = StarSubmission(
        star=system,
        commander=cmdr,
        refs=distances,
        test=testMode,
    )
    resp = sub.submit()

    result = StarSubmissionResult(star=system, response=resp)
    print(str(result))
    if result.valid and result.recheck:
        return list(result.recheck.keys())
    return None


def do_rechecks(clip, system, rechecks):
    print("\aSome systems need their distances rechecked:")

    distances, term = get_distances(clip, list(), rechecks)
    return distances


def send_and_check_distances(clip, system, cmdr, distances):
    if not distances:
        print("No distances, no submission.")
        return False

    while distances:
        rechecks = submit_distances(system, cmdr, distances)
        if not rechecks:
            break

        distances = do_rechecks(clip, system, rechecks)

    return True


def get_standard_stars():
    testStars = set()
    if 'TEST' in os.environ:
        try:
            with open("data/test-stars.txt", "rU") as fh:
                for line in fh:
                    text = line.strip()
                    if text.startswith(';'):
                        continue
                    if text.startswith('#'):
                        continue
                testStars.add(text)
        except FileNotFoundError:
            pass
    if testStars:
        return list(testStars)
    return standardStars


############################################################################

def main():
    tdb = tradedb.TradeDB()

    system, tdbSys, destinations = get_system(tdb)
    cmdr = get_cmdr(tdb)

    if destinations:
        clip = SystemNameClip()
        distances, _ = get_distances(clip, list(), destinations)
        send_and_check_distances(clip, system, cmdr, distances)
        return

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

    clip = SystemNameClip()

    print()
    print("""
===================================================
STANDARD STARS: (q to skip to the next section)

  These are stars with well-known positions.
===================================================
""")
    standardStars = get_standard_stars()
    distances, term = get_distances(clip, list(), standardStars)

    print("""
===================================================
OUTLIERS: (q to skip to the next section)

  Assorted outlier stars from around the galaxy
  mixed with any stars from data/extra-stars.txt.
===================================================
""")
    distances, term = get_distances(clip, distances, outliers)

    print("""
===================================================
CHOOSE YOUR OWN: (q to stop)

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
        extras, term = get_distances(clip, list(), [star])
        if term != 'q' and len(extras) > 0:
            distances.extend(extras)
            if not skipSave and star not in outliers:
                newOutliers.append(star)

    if send_and_check_distances(clip, system, cmdr, distances):
        add_extra_stars(newOutliers)

if __name__ == "__main__":
    try:
        main()
    except SubmissionError as e:
        print(str(e))
    except UsageError as e:
        print(str(e))

