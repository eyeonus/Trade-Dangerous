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
import re
import sys
import tradedb


# Systems we know are bad.
ignore = []


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
            'refsystem',
            help='*Exact* name of the system you are *currently* in, '
                 'used as a reference system for distance validations.',
            type=str,
            default=None,
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

    argv = parser.parse_args(sys.argv[1:])
    if not argv.cmdr:
        raise UsageError("No --cmdr specified / no CMDR environment variable")
    dateRe = re.compile(r'^20\d\d-(0\d|1[012])-([012]\d|3[01]) ([01]\d|2[0123]):[0-5]\d:[0-5]\d$')
    if argv.date and not dateRe.match(argv.date):
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


def main():
    argv = parse_arguments()

    tdb = tradedb.TradeDB()
    if not argv.date:
        argv.date = tdb.query("SELECT MAX(modified) FROM System").fetchone()[0]

    try:
        startSys = tdb.lookupSystem(argv.refsystem)
    except (LookupError, tradedb.AmbiguityError):
        raise UsageError(
            "Unrecognized system '{}'. Reference System must be an existing "
            "system that TD already knows about.\n"
            "Did you forget to put double-quotes around the refsystem name?"
            .format(argv.refsystem)
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
    clip = misc.clipboard.SystemNameClip()

    print("{} results".format(len(systems)))
    # Filter out systems we already know that match the EDSC data.
    systems = [
        sysinfo for sysinfo in systems if is_change(tdb, sysinfo)
    ]
    print("{} deltas".format(len(systems)))

    if len(systems) <= 0:
        return

    print("At the prompt enter y, n or q. Default is n")
    print(
        "To correct a typo'd name that has the correct distance, "
        "use =correct name"
    )
    print()

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

            distance = get_distance(tdb, startSys, x, y, z)
            clip.copy_text(name.lower())
            prompt = "{}/{}: '{}': {:.2f}ly? ".format(
                current, total,
                name,
                distance,
            )
            ok = input(prompt)
            if ok.lower() == 'q':
                break
            if ok.startswith('='):
                name = ok[1:].strip().upper()
                ok = 'y'
                with open("data/extra-stars.txt", "a") as fh:
                    print(name, file=fh)
                    print("Added to data/extra-stars.txt")
            if ok.lower() != 'y':
                continue

            print("'{}',{},{},{},'Release 1.00-EDStar','{}'".format(
                name, x, y, z, created,
            ), file=output)

            sub = misc.edsc.StarSubmission(
                star=name.upper(),
                commander=argv.cmdr,
                distances={startSys.name(): distance},
                test=argv.test,
            )
            r = sub.submit()
            result = misc.edsc.StarSubmissionResult(
                star=name.upper(),
                response=r,
            )

            print(str(result))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("^C")
    except UsageError as e:
        print("ERROR: {}\nSee {} --help for usage help.".format(
            str(e), sys.argv[0]
        ))

