from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.commandenv import ResultRow
from commands.exceptions import CommandLineError
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
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
        'station',
        help='Specify the full name of the station (SYS NAME/STN NAME is also supported).',
        metavar='STATIONNAME',
        type=str,
    ),
    ParseArgument(
        'ship',
        help='Ship name',
        metavar='SHIPTYPE',
        type=str,
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


def checkResultAndExportShipVendors(tdb, cmdenv, result):
    if not result:
        return None
    if cmdenv.noExport:
        cmdenv.DEBUG0("no-export set, not exporting stations")
        return None

    lines, csvPath = csvexport.exportTableToFile(tdb, cmdenv, "ShipVendor")
    cmdenv.NOTE("{} updated.", csvPath)
    return None

def checkShipPresent(tdb, ship, station):
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

    try:
        station = tdb.lookupStation(cmdenv.station)
    except LookupError:
        raise CommandLineError("Unrecognized Station: {}".format(cmdenv.station))

    try:
        ship = tdb.lookupShip(cmdenv.ship)
    except LookupError:
        raise CommandLineError("Unrecognized Ship: {}".format(cmdenv.station))

    # Lets see if that ship sails from the specified port.
    shipPresent = checkShipPresent(tdb, ship, station)

    if cmdenv.add:
        if shipPresent:
            raise CommandLineError(
                    "{} is already listed at {}"
                    .format(ship.name(), station.name())
            )
        result = addShipVendor(tdb, cmdenv, station, ship)
        return checkResultAndExportShipVendors(tdb, cmdenv, result)   
    elif cmdenv.remove:
        if not shipPresent:
            raise CommandLineError(
                    "{} is not listed at {}"
                    .format(ship.name(), station.name())
            )
        result = removeShipVendor(tdb, cmdenv, station, ship)
        return checkResultAndExportShipVendors(tdb, cmdenv, result)
    else:
        raise CommandLineError(
            "You must specify --add or --remove"
        )

