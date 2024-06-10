# Deprecated
# Can already use buy command for ship searching
from .commandenv import ResultRow
from .exceptions import CommandLineError
from .parsing import MutuallyExclusiveGroup, ParseArgument
from ..formatting import RowFormat, ColumnFormat, max_len
from itertools import chain
from ..tradedb import Station

# Original by Dirk Wilhelm

from .. import csvexport

######################################################################
# Parser config

help = 'List, add or update available ships to a station'
name = 'shipvendor'
epilog = None
arguments = [
    ParseArgument(
        'origin',
        help = 'Specify the full name of the station '
            '(SYS NAME/STN NAME is also supported).',
        metavar = 'STATIONNAME',
        type = str,
    ),
    ParseArgument(
        'ship',
        help = 'Comma or space separated list of ship names.',
        type = str,
        nargs = '*',
    ),
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument(
            '--remove', '-rm',
            help = 'Indicates you want to remove an entry.',
            action = 'store_true',
        ),
        ParseArgument(
            '--add', '-a',
            help = 'Indicates you want to add a new station.',
            action = 'store_true',
        ),
        ParseArgument(
            '--name-sort',
            help = 'Sort listed ships by name.',
            action = 'store_true',
            dest = 'nameSort',
        ),
    ),
    ParseArgument(
        '--no-export',
        help = 'Do not update the .csv files.',
        action = 'store_true',
        dest = 'noExport',
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
    cmdenv.NOTE("At {} adding {}", station.name(), ship.name())
    return ship


def removeShipVendor(tdb, cmdenv, station, ship):
    db = tdb.getDB()
    db.execute("""
            DELETE FROM ShipVendor WHERE ship_id = ? and station_id = ?
    """, [ship.ID, station.ID])
    db.commit()
    cmdenv.NOTE("At {} removing {}", station.name(), ship.name())
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


def listShipsPresent(tdb, cmdenv, station, results):
    """ Populate results with a list of ships present at the given station """
    cur = tdb.query("""
        SELECT ship_id
          FROM ShipVendor
         WHERE station_id = ?
    """, [station.ID]
    )
    
    results.summary = ResultRow()
    results.summary.station = station
    ships = tdb.shipByID
    addShip = results.rows.append
    
    for (ship_id,) in cur:
        ship = ships.get(ship_id, None)
        if ship:
            addShip(ResultRow(ship = ship))
    
    if cmdenv.nameSort:
        results.rows.sort(key = lambda row: row.ship.name())
    else:
        results.rows.sort(key = lambda row: row.ship.cost, reverse = True)
    
    return results

######################################################################
# Perform query and populate result set


def run(results, cmdenv, tdb):
    station = cmdenv.startStation
    if not isinstance(station, Station):
        raise CommandLineError(
            "{} is a system, not a station"
            .format(station.name())
        )
    if station.shipyard == 'N' and not cmdenv.remove:
        raise CommandLineError(
            "{} is flagged as having no shipyard."
            .format(station.name())
        )
    
    if cmdenv.add:
        action = addShipVendor
    elif cmdenv.remove:
        action = removeShipVendor
    else:
        return listShipsPresent(tdb, cmdenv, station, results)
    
    if not cmdenv.ship:
        raise CommandLineError(
            "No ship names specified."
        )
    
    cmdenv.NOTE("Using local database ({})", tdb.dbPath)
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
                cmdenv.DEBUG0("{} is already listed at {}",
                    ship.name(), station.name()
                )
            else:
                ships[ship.ID] = ship
        else:
            if not shipPresent:
                cmdenv.DEBUG0("{} is not listed at {}",
                    ship.name(), station.name()
                )
            else:
                ships[ship.ID] = ship
    
    if len(ships) == 0:
        cmdenv.NOTE("Nothing to do.")
        return None
    
    # We've checked that everything should be good.
    dataToExport = False
    for ship in ships.values():
        if action(tdb, cmdenv, station, ship):
            dataToExport = True
    
    cmdenv.DEBUG0("dataToExport = {}", dataToExport)
    
    maybeExportToCSV(tdb, cmdenv)
    
    return None

######################################################################
# Transform result set into output


def render(results, cmdenv, tdb):
    if not results or not results.rows:
        raise CommandLineError(
            "No ships available at {}"
            .format(results.summary.station.name())
        )
    
    maxShipLen = max_len(results.rows, key = lambda row: row.ship.name())
    
    rowFmt = RowFormat().append(
        ColumnFormat("Ship", '<', maxShipLen,
            key = lambda row: row.ship.name())
    ).append(
        ColumnFormat("Cost", '>', 12, 'n',
            key = lambda row: row.ship.cost)
    )
    
    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep = '\n')
    
    for row in results.rows:
        print(rowFmt.format(row))
