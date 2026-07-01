#!/usr/bin/env python3.6
# Deprecated
# Website no longer exists

"""
Small tool to submit new star data to EDStarCoordinator.

Use:
    submit-distances.py "system name"
"""

#
# NOTE: This tool is very hacky. If someone wants to clean it up,
# and submit a diff, that'd be greatly appreciated!
#

import argparse
import os
import random
import re
import requests
import sys
import tradedb
import tradeenv

from tradedangerous.misc.edsc import StarSubmission, StarSubmissionResult, SubmissionError
from tradedangerous.misc.clipboard import SystemNameClip


standardStars = [
    "SOL",
    "NEW YEMBO",
    "VESUVIT",
    "HIP 79884",
    "ASELLUS AUSTRALIS",
]


sys.stderr.write("*** WARNING: submit-distances.py is deprecated; if you rely on it, please post a github issue\n")


############################################################################


class UsageError(Exception):
    def __init__(self, argv, error):
        self.argv, self.error = argv, error
    
    def __str__(self):
        return error + "\n" + argv.format_usage()

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Submit star distances to the EDSC project.',
    )
    parser.add_argument(
        'origin',
        help='System to submit distances for.',
        type=str,
    )
    parser.add_argument(
        '--pick',
        help='Randomly select N existing systems from gamma or ealier',
        required=False,
        type=int,
    )
    parser.add_argument(
        '--cmdr',
        required=False,
        help='Specify your commander name.',
        type=str,
        default=os.environ.get('CMDR', None)
    )
    parser.add_argument(
        '--test',
        help='Use the EDSC Test Database.',
        required=False,
        action='store_true',
    )
    parser.add_argument(
        '--detail', '-v',
        help='Output additional detail.',
        action='count',
        default=0,
    )
    parser.add_argument(
        '--debug', '-w',
        help='Enable debugging output,',
        action='count',
        default=0,
    )
    parser.add_argument(
        '--no-update',
        help='Disallow distances from an existing system.',
        action='store_false',
        default=True,
        dest='allowUpdate',
    )
    parser.add_argument(
        '--extra-file',
        help='File to read/write extra stars to.',
        type=str,
        default='data/extra-stars.txt',
        dest='extraFile',
    )
    parser.add_argument(
        'destinations',
        help='System or systems to measure distance to.',
        default=[],
        nargs='*',
    )
    
    argv = parser.parse_args(sys.argv[1:])
    argv.origin = argv.origin.upper()
    if argv.origin.startswith('@'):
        argv.origin = argv.origin[1:]
    
    if not argv.cmdr:
        raise UsageError(argv, "No commander name specified")
    
    return argv

def get_system(argv, tdb):
    system = tdb.systemByName.get(argv.origin.upper(), None)
    if not system:
        return argv.origin, None
    
    if not argv.allowUpdate:
        raise UsageError(
            argv,
            "System '{}' already exists.\n"
            .format(systemName)
        )
    
    if argv.detail:
        print("EXISTING SYSTEM:", argv.origin)
    
    return argv.origin, system

def pick_destinations(argv, tdb):
    numSystems = len(tdb.systemByName)
    if numSystems < 1:
        raise UsageError(
            argv,
            "Can't --pick random systems: "
            "Your TD database doesn't contain any systems."
        )
    num = min(argv.pick, numSystems)
    systems = tdb.systemByName
    try:
        gamma = tdb.lookupAdded("Gamma")
    except KeyError:
        gamma = 20
    destinations = random.sample([
        sysName for sysName, system in systems.items()
        if system.addedID <= gamma and \
            not sysName in standardStars
    ], num)
    
    return destinations

def get_outliers(argv):
    outliers = set()
    try:
        with open(argv.extraFile, "r", encoding="utf-8") as input:
            for line in input:
                name = line.partition('#')[0].strip().upper()
                if name and name != argv.origin:
                    outliers.add(name)
    except FileNotFoundError:
        pass
    outliers = list(outliers)
    random.shuffle(outliers)
    return outliers

def get_distances(argv, clip, stars):
    distances = []
    for star in stars:
        starNo = len(distances) + 1
        # Check it's not already in the list
        star = star.upper()
        if star in distances:
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

def check_system(argv, tdb, tdbSys, name):
    system = tdb.systemByName.get(name.upper(), None)
    if system and not tdbSys:
        print("KNOWN SYSTEM")
        return
    if system:
        print("KNOWN SYSTEM: {:.2f} ly".format(
            tdbSys.distanceTo(system)
        ))

def add_extra_stars(argv, extraStars):
    if not extraStars:
        return
    if argv.detail:
        print("Saving {} to {}".format(
            str(extraStars), argv.extraFile,
        ))
    try:
        with open(argv.extraFile, "a", encoding="utf-8") as output:
            for star in extraStars:
                print(star, file=output)
    except FileNotFoundError:
        pass

def submit_distances(argv, tdb, distances):
    system = argv.origin
    cmdr = argv.cmdr
    mode = "TEST" if argv.test else "Live"
    
    print()
    print("System:", system)
    print("Database:", mode)
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
    
    print()
    print("Submitting {} {}".format(mode, system))
    
    sub = StarSubmission(
        star=system,
        commander=cmdr,
        refs=distances,
        test=argv.test,
    )
    resp = sub.submit()
    
    result = StarSubmissionResult(star=system, response=resp)
    print(str(result))
    if result.valid:
        # Check for systems we can add
        trilats = set()
        for sysName in result.systems.keys():
            code, coord = result.systems[sysName]
            sysName = sysName.upper()
            # Does it have a distance
            if isinstance(coord, (list, tuple)):
                x, y, z = coord
                system = tdb.systemByName.get(sysName, None)
                if system:
                    tdb.updateLocalSystem(system, sysName, x, y, z)
                else:
                    tdb.addLocalSystem(sysName, x, y, z)
        if result.recheck:
            return list(result.recheck.keys())
    return None

def do_rechecks(argv, clip, rechecks):
    print("\aSome systems need their distances rechecked:")
    
    distances, term = get_distances(argv, clip, rechecks)
    return distances

def send_and_check_distances(argv, tdb, clip, distances):
    if not distances:
        if argv.detail:
            print("No distances, no submission.")
        return False
    
    while distances:
        rechecks = submit_distances(argv, tdb, distances)
        if not rechecks:
            break
        
        distances = do_rechecks(argv, clip, rechecks)
    
    return True

def process_destinations(argv, tdb):
    clip = SystemNameClip()
    
    print("Distances from {}:".format(argv.origin))
    distances, _ = get_distances(argv, clip, argv.destinations)
    send_and_check_distances(argv, tdb, clip, distances)

############################################################################

def main():
    argv = parse_arguments()
    
    tdenv = tradeenv.TradeEnv(properties=argv)
    tdb = tradedb.TradeDB(tdenv)
    
    system, tdbSys = get_system(argv, tdb)
    
    if argv.pick:
        argv.destinations.extend(pick_destinations(argv, tdb))
    
    if argv.destinations:
        process_destinations(argv, tdb)
        return
    
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
    print(
        "5 distances are required for EDSC to make a first guess at a "
        "star's location. You can submit more to increase the accuracy "
        "but the only time you need to submit more than 10 is when you "
        "are trying to submit corrections."
    )
    print()
    
    clip = SystemNameClip()
    
    print()
    print("""
===================================================
STANDARD STARS: (q to skip to the next section)
  
  These are stars with well-known positions.
===================================================
""")
    distances, term = get_distances(argv, clip, standardStars)
    if distances:
        send_and_check_distances(argv, tdb, clip, distances)
    
    outliers = get_outliers(argv)
    if outliers:
        print("""
===================================================
EXTRA STARS: (q to skip to the next section)
  
  Stars from {}.
===================================================
""".format(argv.extraFile))
        distances, term = get_distances(argv, clip, outliers)
        if distances:
            send_and_check_distances(argv, tdb, clip, distances)
    
    print("""
===================================================
CHOOSE YOUR OWN: (q to stop)
  
  Specify additional stars.
  
  Prefix names with a '+' to add them to
  {}.
===================================================
""".format(argv.extraFile))
    distances = []
    newOutliers = []
    while True:
        star = input("Enter star name: ")
        star = star.strip().upper()
        if not star or star == 'Q':
            break
        # Remove surrounding quotes
        save = False
        if star.startswith('+'):
            save = True
            star = star[1:].strip()
        star = re.sub(r'\s+', ' ', star)
        star = re.sub(r"''+", "'", star)
        star = re.sub(r'^("|\')+\s*(.*)\s*\1+', r'\2', star)
        if star.find('"') >= 0:
            print("Invalid star name")
            continue
        if star.startswith('+'):
            save = True
            star = star[1:].strip()
        for ref in distances:
            if ref['name'] == star:
                print("'{}' is already listed.")
                continue
        check_system(argv, tdb, tdbSys, star)
        extras, term = get_distances(argv, clip, [star])
        if term != 'q' and len(extras) > 0:
            distances.extend(extras)
            if save and star not in outliers and star not in newOutliers:
                newOutliers.append(star)
    
    if send_and_check_distances(argv, tdb, clip, distances):
        add_extra_stars(argv, newOutliers)

if __name__ == "__main__":
    try:
        main()
    except (SubmissionError, UsageError) as e:
        print(str(e))
