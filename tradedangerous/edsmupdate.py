#!/usr/bin/env python3.6
# Deprecated

"""
based on edscupdate.py without the submit_distance()

This tool looks for changes in the EDSM service since the most
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

import argparse
import misc.clipboard
import misc.edsm
import os
import random
import re
import sys
import tradedb
import tradeenv


# Systems we know are bad.
ignore = []

class UsageError(Exception):
    """ Raised when command line usage is invalid. """
    pass

def parse_arguments():
    parser = argparse.ArgumentParser(
            description='Review and validate incoming EDSM star data.',
            epilog='Confirmed systems are written to tmp/new.systems.csv.',
    )
    parser.add_argument(
            'refSystem',
            help='*Exact* name of the system you are *currently* in, '
                 'used as a reference system for distance validations.',
            type=str,
            metavar='"REFERENCE SYSTEM"',
            default=None,
            nargs='?',
    )
    parser.add_argument(
            '--cmdr',
            required=False,
            help='Specify your commander name.',
            type=str,
            default=os.environ.get('CMDR', None),
    )
    grp = parser.add_mutually_exclusive_group()
    if grp:  # for indentation
        grp.add_argument(
                '--random',
                action='store_true',
                required=False,
                help='Show systems in random order, maximum of --max-systems.',
        )
        grp.add_argument(
                '--distance',
                action='store_true',
                required=False,
                help='Select upto 10 systems by proximity.',
        )
    parser.add_argument(
            '--max-systems',
            dest='maxSystems',
            help='Maximum systems to query with --random/--distance.',
            required=False,
            type=int,
            default=10
        )
    parser.add_argument(
            '--max-ly',
            dest='maxLy',
            help='Maximum distance to reference systems (for --distance).',
            required=False,
            type=int,
            default=0
        )
    parser.add_argument(
            '--add-to-local-db', '-A',
            action='store_true',
            required=False,
            help='Add accepted systems to the local database.',
            dest='add',
    )
    parser.add_argument(
            '--date',
            required=False,
            help='Use specified date (YYYY-MM-DD HH:MM:SS format) for '
                 'start of update search. '
                 'Default is to use the last System modified date.',
            type=str,
            default=None,
    )
    parser.add_argument(
            '--no-splash', '-NS',
            required=False,
            action='store_false',
            help="Don't display the 'splash' text on startup.",
            dest='splash',
            default=True,
    )
    parser.add_argument(
            '--summary',
            required=False,
            help='Check for and report on new systems but do no work.',
            action='store_true',
    )
    parser.add_argument(
            '--detail', '-v',
            help='Increase level  of detail in output.',
            default=0,
            required=False,
            action='count',
    )
    parser.add_argument(
            '--debug', '-w',
            help='Enable/raise level of diagnostic output.',
            default=0,
            required=False,
            action='count',
    )
    parser.add_argument(
            '--ref',
            help='Reference system (for --distance).',
            default=None,
            dest='refSys',
            type=str,
    )
    parser.add_argument(
            '--log-edsm',
            required=False,
            help='Log the EDSM request and response in tmp/edsm.log.',
            default=False,
            dest='logEDSM',
            action='store_true',
    )
    parser.add_argument(
            '--yes',
            required=False,
            help='Answer "y" to autoconfirm all EDSM systems.',
            default=False,
            dest='autoOK',
            action='store_true',
    )
    
    argv = parser.parse_args(sys.argv[1:])
    if not argv.summary:
        if not argv.refSystem:
            raise UsageError(
                "Must specify a reference system name (when not using "
                "--summary). Be sure to put the name in double quotes, "
                "e.g. \"SOL\" or \"I BOOTIS\".\n"
            )
    if not argv.distance and argv.refSys:
        raise UsageError("--ref requires --distance")
    if not argv.distance and argv.maxLy:
        raise UsageError("--max-ly requires --distance")
    
    return argv

def is_change(tdb, sysinfo):
    """ Check if a system's EDSM data is different than TDs """
    name = sysinfo['name'] = sysinfo['name'].upper()
    if name in ignore:
        return False
    try:
        x = sysinfo['coords']['x']
        y = sysinfo['coords']['y']
        z = sysinfo['coords']['z']
        place = tdb.systemByName[name]
        if place.posX == x and place.posY == y and place.posZ == z:
            return False
    except KeyError:
        place = None
    sysinfo['place'] = place
    return True

def has_position_changed(place, name, x, y, z):
    if not place:
        return False
    
    print("! @{} [{},{},{}] changed to @{} [{},{},{}]".format(
        name, x, y, z,
        place.dbname, place.posX, place.posY, place.posZ
    ))
    
    return True

def check_database(tdb, name, x, y, z):
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

def get_distance(tdb, startSys, x, y, z):
    distance = tdb.calculateDistance(
        startSys.posX, startSys.posY, startSys.posZ,
        x, y, z
    )
    return float("{:.2f}".format(distance))

def get_extras():
    extras = set()
    try:
        with open("data/extra-stars.txt", "r", encoding="utf-8") as fh:
            for line in fh:
                name = line.partition('#')[0].strip().upper()
                if name:
                    extras.add(name)
    except FileNotFoundError:
        pass
    return extras

def add_to_extras(argv, name):
    with open("data/extra-stars.txt", "a", encoding="utf-8") as fh:
        print(name.upper(), file=fh)
        print("Added {} to data/extra-stars.txt".format(name))

def main():
    argv = parse_arguments()
    tdenv = tradeenv.TradeEnv(properties=argv)
    tdenv.quiet = 1
    tdb = tradedb.TradeDB(tdenv)
    
    if not argv.summary:
        try:
            argv.startSys = tdb.lookupSystem(argv.refSystem)
        except (LookupError, tradedb.AmbiguityError):
            raise UsageError(
                "Unrecognized system '{}'. Reference System must be an "
                "*exact* name for a system that TD already knows.\n"
                "Did you forget to put double-quotes around the reference "
                "system name?"
                .format(argv.refSystem)
            )
    
    if not argv.date:
        argv.date = tdb.query("SELECT MAX(modified) FROM System").fetchone()[0]
    dateRe = re.compile(r'^20\d\d-(0[1-9]|1[012])-(0[1-9]|[12]\d|3[01]) ([01]\d|2[0123]):[0-5]\d:[0-5]\d$')
    if not dateRe.match(argv.date):
        raise UsageError(
                "Invalid date: '{}', expecting YYYY-MM-DD HH:MM:SS format."
                .format(argv.date)
        )
    print("start date: {}".format(argv.date))
    
    edsq = misc.edsm.StarQueryMulti(
        log=argv.logEDSM,
        startDateTime=argv.date,
        submitted=1,
        showId=1,
        )
    data = edsq.fetch()
    
    systems = data
    
    print("{} results".format(len(systems)))
    # Filter out systems we already know that match the EDSM data.
    systems = [
        sysinfo for sysinfo in systems if is_change(tdb, sysinfo)
    ]
    print("{} deltas".format(len(systems)))
    
    if argv.summary or len(systems) <= 0:
        return
    
    systems = [
        sysinfo for sysinfo in systems if 'coords' in sysinfo
    ]
    
    if argv.random:
        num = min(len(systems), argv.maxSystems)
        systems = random.sample(systems, num)
    
    if argv.refSys:
        refSys = tdb.lookupPlace(argv.refSys)
    else:
        refSys = None
    startSys = argv.startSys
    for sysinfo in systems:
        x = sysinfo['coords']['x']
        y = sysinfo['coords']['y']
        z = sysinfo['coords']['z']
        sysinfo['distance'] = get_distance(tdb, startSys, x, y, z)
        if refSys:
            sysinfo['refdist'] = get_distance(tdb, refSys, x, y, z)
        else:
            sysinfo['refdist'] = None
    
    if argv.distance:
        if argv.maxLy > 0:
            if refSys:
                systems = [
                    sysinfo for sysinfo in systems if sysinfo['refdist'] <= argv.maxLy
                ]
            else:
                systems = [
                    sysinfo for sysinfo in systems if sysinfo['distance'] <= argv.maxLy
                ]
        else:
            if refSys:
                systems.sort(key=lambda sysinfo: sysinfo['refdist'])
            else:
                systems.sort(key=lambda sysinfo: sysinfo['distance'])
            systems = systems[:argv.maxSystems]
    
    if argv.splash and not argv.autoOK:
        print(
            "\n"
            "===============================================================\n"
            "\n"
            " The tool will now take you through the stars returned by EDSM\n"
            " that are new or different from your local System.csv.\n"
            "\n"
            " You will be prompted with the name and predicted distance from\n"
            " your current system so you can check for mistakes.\n"
            "\n"
            " The name will be copied into your clipboard so you can alt-tab\n"
            " into the game and paste the name into the Galaxy Map's SEARCH\n"
            " box (under NAVIGATION). Let the map zoom to the system.\n"
            "\n"
            " Check the name and distance, then use the appropriate action.\n"
            "\n"
            " (Use the -NS option to skip this text in future)\n"
            "\n"
            "===============================================================\n"
            "\n"
        )
        
        input("Hit enter to continue: ")
    
    if not argv.autoOK:
        print("""At the prompt enter:
  q
      to indicate you've suffered enough,
  y
      to accept the name/value,
  n       (or anything else)
      to skip the name/value (no confirmation),
  =name   (e.g. =SOL)
      to accept the distance but correct spelling,
""")
        print()
    
    extras = get_extras()
    
    clip = misc.clipboard.SystemNameClip()
    total = len(systems)
    current = 0
    with open("tmp/new.systems.csv", "w", encoding="utf-8") as output:
        if argv.autoOK:
            commit=False
        else:
            commit=True
        for sysinfo in systems:
            current += 1
            name = sysinfo['name']
            created = sysinfo['date']
            x = sysinfo['coords']['x']
            y = sysinfo['coords']['y']
            z = sysinfo['coords']['z']
            
            if not argv.autoOK:
                print(
                    "\n"
                    "-----------------------------------------------\n"
                    "{syidlab:.<12}: {syid}\n"
                    "{crealab:.<12}: {crts}\n"
                    .format(
                        syidlab="ID",
                        crealab="Created",
                        syid=sysinfo['id'],
                        crts=created,
                    )
                )
                if refSys:
                    print("{reflab:.<12}: {refdist}ly\n".format(
                        reflab="Ref Dist",
                        refdist=sysinfo['refdist'],
                    ))
            
            check_database(tdb, name, x, y, z)
            
            change = has_position_changed(sysinfo['place'], name, x, y, z)
            if change:
                oldDist = startSys.distanceTo(sysinfo['place'])
                print("Old Distance: {:.2f}ly".format(oldDist))
            
            distance = sysinfo['distance']
            clip.copy_text(name)
            prompt = "{}/{}: '{}': {:.2f}ly? ".format(
                current, total,
                name,
                distance,
            )
            if argv.autoOK:
                if change:
                    ok = "n"
                else:
                    ok = "y"
            else:
                ok = input(prompt)
            if ok.lower() == 'q':
                break
            if ok.startswith('='):
                name = ok[1:].strip().upper()
                if name not in extras:
                    add_to_extras(argv, name)
                ok = 'y'
            if ok.lower() != 'y':
                continue
            
            if argv.add:
                print("Add {:>6}: {:>12} {} {}".format(current, sysinfo['id'], created, name))
                tdb.addLocalSystem(
                    name,
                    x, y, z,
                    added='EDSM',
                    modified=created,
                    commit=commit
                )
            
            print("'{}',{},{},{},'EDSM','{}'".format(
                name, x, y, z, created,
            ), file=output)
        if argv.add and not commit:
            tdb.getDB().commit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("^C")
    except UsageError as e:
        print("ERROR: {}\nSee {} --help for usage help.".format(
            str(e), sys.argv[0]
        ))
