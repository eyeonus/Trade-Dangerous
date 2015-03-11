#! /usr/bin/env python

"""
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

import argparse
import math
import misc.clipboard
import misc.edsc
import os
import random
import re
import sys
import tradedb
import tradeenv

DEFAULT_DATE = "2015-02-11 00:00:00"


# Systems we know are bad.
ignore = [
    "COL 285 SECTOR EC-R B18-5",
    "DITIBI (FIXED)",
    "HYADES",
    "HAREMID",
    "HYADES SECTOR VO-Q V5-1",
    "XI HUGAN",
    "LP  634-18",
    "SHU WEI SECTOR MN-S B4-4",
    "SHU WEI SECTOR MN-S B4-9",
    "THETA CARINE",
    "CORE SYS HH-M A7-3",
    "OI-T B3-9",
    "IDZ DL-X B1-1",
    "PHE ZHUA",
    "LP 937-98",
]


class UsageError(Exception):
    """ Raised when command line usage is invalid. """
    pass


def parse_arguments():
    parser = argparse.ArgumentParser(
            description='Review and validate incoming EDSC star data. '
                        'Confirmed distances are submitted back to EDSC to '
                        'increase confidence ratings.',
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
    parser.add_argument(
            '--confidence',
            required=False,
            help='Specify minimum confidence level.',
            type=int,
            default=2,
    )
    parser.add_argument(
            '--random',
            action='store_true',
            required=False,
            help='Show systems in random order, maximum of 10.',
    )
    parser.add_argument(
            '--add-to-local-db', '-A',
            action='store_true',
            required=False,
            help='Add accepted systems to the local database.',
            dest='add',
    )
    parser.add_argument(
            '--test',
            required=False,
            help='Use the EDSC test database.',
            action='store_true',
            default=False,
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

    argv = parser.parse_args(sys.argv[1:])
    dateRe = re.compile(r'^20\d\d-(0\d|1[012])-([012]\d|3[01]) ([01]\d|2[0123]):[0-5]\d:[0-5]\d$')
    if not argv.summary:
        if not argv.cmdr:
            raise UsageError("No --cmdr specified / no CMDR environment variable")
        if not argv.refSystem:
            raise UsageError(
                "Must specify a reference system name (when not using "
                "--summary). Be sure to put the name in double quotes, "
                "e.g. \"SOL\" or \"I BOOTIS\".\n"
            )
    if not argv.date:
        argv.date = DEFAULT_DATE
    if not dateRe.match(argv.date):
        raise UsageError(
                "Invalid date: '{}', expecting YYYY-MM-DD HH:MM:SS format."
                .format(argv.date)
        )

    return argv


def is_change(tdb, sysinfo):
    """ Check if a system's EDSC data is different than TDs """
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


def has_position_changed(sysinfo):
    place = sysinfo['place']
    if not place:
        return False

    print("! @{} [{},{},{}] vs @{} [{},{},{}]".format(
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


def submit_distance(argv, name, distance):
    p0 = name.upper()
    ref = argv.startSys.name().upper()
    print("Sending: {}->{}: {}ly by {}".format(
        p0, ref, distance, argv.cmdr
    ))
    sub = misc.edsc.StarSubmission(
        star=p0,
        distances={ref: distance},
        commander=argv.cmdr,
        test=argv.test,
    )
    r = sub.submit()
    result = misc.edsc.StarSubmissionResult(
        star=name.upper(),
        response=r,
    )
    print(str(result))


def add_to_extras(argv, name):
    with open("data/extra-stars.txt", "a") as fh:
        print(name.upper(), file=fh)
        print("Added {} to data/extra-stars.txt".format(name))


def main():
    argv = parse_arguments()
    tdenv = tradeenv.TradeEnv(properties=argv)
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

    print("start date: {}".format(argv.date))

    edsq = misc.edsc.StarQuery(
        test=argv.test,
        confidence=argv.confidence,
        date=argv.date,
        )
    data = edsq.fetch()

    if edsq.status['statusnum'] != 0:
        raise Exception("Query failed: {} ({})".format(
                    edsq.status['msg'],
                    edsq.status['statusnum'],
                ))

    date = data['date']
    systems = data['systems']

    print("{} results".format(len(systems)))
    # Filter out systems we already know that match the EDSC data.
    systems = [
        sysinfo for sysinfo in systems if is_change(tdb, sysinfo)
    ]
    print("{} deltas".format(len(systems)))

    if argv.summary or len(systems) <= 0:
        return

    if argv.random:
        num = min(len(systems), 10)
        systems = random.sample(systems, num)

    if argv.splash:
        print(
            "\n"
            "===============================================================\n"
            "\n"
            " The tool will now take you through the stars returned by EDSC\n"
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

    print("""At the prompt enter:
  q
      to indicate you've suffered enough,
  y
      to accept the name/value and confirm with EDSC,
  n       (or anything else)
      to skip the name/value (no confirmation),
  =name   (e.g. =SOL)
      to accept the distance but correct spelling,
  ~dist   (e.g. ~104.49)
      to submit a distance correction for the system,
""")
    print()

    clip = misc.clipboard.SystemNameClip()
    total = len(systems)
    current = 0
    with open("tmp/new.systems.csv", "w") as output:
        for sysinfo in systems:
            current += 1
            name = sysinfo['name']
            x, y, z = sysinfo['coord']

            if has_position_changed(sysinfo):
                continue

            check_database(tdb, name, x, y, z)

            created = sysinfo['createdate']

            distance = get_distance(tdb, argv.startSys, x, y, z)
            clip.copy_text(name.lower())
            prompt = "{}/{}: '{}': {:.2f}ly? ".format(
                current, total,
                name,
                distance,
            )
            ok = input(prompt)
            if ok.lower() == 'q':
                break
            if ok.startswith('~'):
                correction = float(ok[1:])
                submit_distance(argv, name, correction)
                add_to_extras(argv, name)
                continue
            if ok.startswith('='):
                name = ok[1:].strip().upper()
                add_to_extras(argv, name)
                ok = 'y'
            if ok.lower() != 'y':
                continue

            if argv.add:
                tdb.addLocalSystem(
                    name,
                    x, y, z,
                    added='Release 1.00-EDStar',
                    modified=created,
                    commit=True
                )

            print("'{}',{},{},{},'Release 1.00-EDStar','{}'".format(
                name, x, y, z, created,
            ), file=output)

            submit_distance(argv, name, distance)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("^C")
    except UsageError as e:
        print("ERROR: {}\nSee {} --help for usage help.".format(
            str(e), sys.argv[0]
        ))

