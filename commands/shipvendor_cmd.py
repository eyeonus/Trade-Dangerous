from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.commandenv import ResultRow
from commands.exceptions import CommandLineError
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from itertools import chain
from tradedb import AmbiguityError
from tradedb import System, Station
from tradedb import TradeDB

# Original by Dirk Wilhelm

import csvexport
import re
import sys

######################################################################
# Parser config

help='Add (or update) a ship vendor entry'
name='shipvendor'
epilog=None
arguments = [
    ParseArgument(
        'origin',
        help='Specify the full name of the station '
            '(SYS NAME/STN NAME is also supported).',
        metavar='STATIONNAME',
        type=str,
    ),
    ParseArgument(
        'ship',
        help='Comma or space separated list of ship names.',
        nargs='+',
    ),
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument(
            '--remove', '-rm',
            help='Indicates you want to remove an entry.',
            action='store_true',
        ),
        ParseArgument(
            '--add', '-a',
            help='Indicates you want to add a new station.',
            action='store_true',
        ),
    ),
    ParseArgument(
        '--no-export',
        help='Do not update the .csv files.',
        action='store_true',
        dest='noExport',
    ),
]

######################################################################
# Helpers


def addShipVendor(tdb, cmdenv, station, ship):
    db = tdb.getDB()
    db.execute("""
                INSERT INTO ShipVendor (
                    ship_id, station_id
                ) VALUES (
                    ?, ?
                )
        """, [
                ship.ID, station.ID
        ])
    db.commit()
    cmdenv.NOTE("{} added to {} in local {} database.",
            ship.name(), station.name(), tdb.dbPath)
    return ship
    

def removeShipVendor(tdb, cmdenv, station, ship):
    db = tdb.getDB()
    db.execute("""
            DELETE FROM ShipVendor WHERE ship_id = ? and station_id = ?
    """, [ship.ID,station.ID])
    db.commit()
    cmdenv.NOTE("{} removed from {} in local {} database.",
            ship.name(), station.name(), tdb.dbPath)
    return ship


def maybeExportToCSV(tdb, cmdenv):
    if cmdenv.noExport:
        cmdenv.DEBUG0("no-export set, not exporting stations")
        return

    lines, csvPath = csvexport.exportTableToFile(tdb, cmdenv, "ShipVendor")
    cmdenv.NOTE("{} updated.", csvPath)

def checkShipPresent(tdb, station, ship):
    # Ask the database how many rows it sees claiming
    # this ship is sold at that station. The value will
    # be zero if we don't have an entry, otherwise it
    # will be some positive number.
    cur = tdb.query("""
        SELECT  COUNT(*)
          FROM  ShipVendor
         WHERE  ship_id = ? AND station_id = ?
    """, [ship.ID, station.ID]
    )
    # Get the first result of the row and get the first column of that row
    count = int(cur.fetchone()[0])

    # Test if count > 0, if so, we'll return True, otherwise False
    return (count > 0)


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):

    station = cmdenv.startStation
    if not isinstance(station, Station):
        raise CommandLineError("{} is a system, not a station".format(
            station.name()
        ))

    if cmdenv.add:
        action = addShipVendor
    elif cmdenv.remove:
        action = removeShipVendor
    else:
        ###TODO:
        ### if not cmdenv.ship:
        ###  List ships at this station.
        raise CommandLineError(
            "You must specify --add or --remove"
        )

    ships = {}
    shipNames = chain.from_iterable(
        name.split(",") for name in cmdenv.ship
    )
    for shipName in shipNames:
        try:
            ship = tdb.lookupShip(shipName)
        except LookupError:
            raise CommandLineError("Unrecognized Ship: {}".format(shipName))

        # Lets see if that ship sails from the specified port.
        shipPresent = checkShipPresent(tdb, station, ship)
        if cmdenv.add:
            if shipPresent:
                raise CommandLineError(
                        "{} is already listed at {}"
                        .format(ship.name(), station.name())
                )
            ships[ship.ID] = ship
        else:
            if not shipPresent:
                raise CommandLineError(
                        "{} is not listed at {}"
                        .format(ship.name(), station.name())
                )
            ships[ship.ID] = ship

    # We've checked that everything should be good.
    dataToExport = False
    for ship in ships.values():
        if action(tdb, cmdenv,station, ship):
            dataToExport = True

    maybeExportToCSV(tdb, cmdenv)

    return None
