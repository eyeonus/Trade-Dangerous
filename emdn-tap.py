#! /usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Elite Market Data Network :: EMDN Tap
#  Taps into the Elite Market Data Net to retrieve prices observed
#  by other players.
#  For more information on EMDN see Andreas' post:
#   http://forums.frontier.co.uk/showthread.php?t=23585
#
#  TODO: Use a LOCAL .prices file so that we don't get conflicts,
#  or stop storing the .prices file in the repository entirely.

# v0.1 -- First, crude version. Using old EMDN CSV format.

######################################################################
# imports

import argparse
import re
import sys
import time
import pathlib

from tradedb import TradeDB
from tradecalc import localedNo
from emdn.firehose import Firehose
from data import prices

######################################################################
# global variables: jeebus doesn't love me anymore.

warnOnly = False
warningFh = sys.stderr

blackMarketItems = frozenset([
    'battleweapons',
])

######################################################################
# process command line

def processCommandLine():
    """
        Process the command line with argparse.
    """

    global warnOnly, warningFh

    parser = argparse.ArgumentParser(description='Pull updates from the EMDN firehose to the TradeDangerous DB')
    parser.add_argument('--firehose', '-u',  help='URI for the firehose. Default={}'.format(Firehose.defaultURI), default=None)
    parser.add_argument('--file',     '-f',  help='Filename for the firehose. Default=None.', default=None)
    parser.add_argument('--db',       '-d',  help='SQLite database to write to. Default={}'.format(TradeDB.defaultDB))
    parser.add_argument('--seconds',  '-s',  help='Maximum seconds to run for. Default=unlimited.', type=int, default=0)
    parser.add_argument('--minutes',  '-m',  help='Maximum minutes to run for. Default=unlimited.', type=int, default=0)
    parser.add_argument('--records',  '-r',  help='Maximum records to retrieve. Default=unlimited.', type=int, default=0)
    parser.add_argument('--verbose',  '-v',  help='Increase verboseness.', action='count', default=0)
    parser.add_argument('--no-writes',       help='Don\'t actually write to the database.', action='store_true', default=False, dest='noWrites')
    parser.add_argument('--warn',            help='Demote unrecognized items/stations to warnings.', action='store_true', default=False)
    parser.add_argument('--warn-to',         help='Same as --warn but specifies file to write to.', dest='warnTo')
    parser.add_argument('--commit',          help='Automatically commit after this many seconds, 0 disables. Default: 90', type=int, default=90)

    pargs = parser.parse_args()

    if pargs.firehose and pargs.file:
        print("--firehose and --file are mutually exclusive.")
        sys.exit(1)

    pargs.firehoseURI = pargs.firehose
    if pargs.file and (pargs.file[0] in [ '/', '.', '\\' ]):
        pargs.firehoseURI = re.sub(r'\\', '/', 'file://' + pargs.file)
    elif pargs.file:
        pargs.firehoseURI = 'file://./' + pargs.file

    pargs.duration = pargs.minutes * 60 + pargs.seconds

    print("* Fetching EMDN data from {} to {}.".format(
            pargs.firehoseURI or '['+Firehose.defaultURI+']',
            pargs.db or '['+TradeDB.defaultDB+']'
        ))
    print("* Automatic commits {}.".format(
            'every {} seconds'.format(pargs.commit) if pargs.commit else 'disabled'
        ))

    if pargs.warnTo:
        pargs.warn = True
        warningFh = open(pargs.warnTo, 'w')

    warnOnly = pargs.warn

    return pargs


######################################################################
# UI Order tracking: items that weren't in the DB need to have a
# useful UIOrder attached to them, this makes a best guess.

uiOrders = {}
def getStationCat(stationID, catID):
    global uiOrders
    key = "{}.{}".format(stationID, catID)
    try: result = uiOrders[key]
    except KeyError:
        result = uiOrders[key] = {}
    return result


def getItemUIOrder(stationID, catID, itemID):
    global uiOrders
    cat = getStationCat(stationID, catID)
    try: result = cat[itemID]
    except KeyError:
        lastOrder = max(cat.values()) if cat else 0
        result = cat[itemID] = lastOrder + 1
    return result


def loadUIOrders(db):
    # Get the current list of ui orders.
    stmt = """
        SELECT  Price.station_id, Item.category_id, Price.item_id, Price.ui_order
        FROM  Price INNER JOIN Item ON Price.item_id = Item.item_id
    """
    cur = db.execute(stmt)
    for (stationID, catID, itemID, uiOrder) in cur:
        getStationCat(stationID, catID)[itemID] = uiOrder


######################################################################

def bleat(category, name, *args, **kwargs):
    """
        Throttled (once per category+name only) reporting
        of errors. Exit after first report if not warnOnly.
        Bleat: rhymes with 'tweet'.
    """
    bleatKey = '{}:{}'.format(category, name)

    if not bleatKey in bleat.bleated:
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        print(now, '[{} >> {}]'.format(category, name), *args, file=warningFh, **kwargs)
        warningFh.flush()
        bleat.bleated.add(bleatKey)

    if not warnOnly:
        sys.exit(1)


bleat.bleated = set()


######################################################################
# Save data to the db

commitStmt = """
    INSERT OR REPLACE INTO Price (item_id, station_id, ui_order, sell_to, buy_from, modified)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
"""

def commit(tdb, db, recordsSinceLastCommit, pargs):
    """
        Write uncommitted records to the database and rebuild the prices file.

        If --no-writes was specified, does everything except the actual commit.
    """
    if not recordsSinceLastCommit:
        return

    if pargs.verbose:
        print("-> commit {} records".format(len(recordsSinceLastCommit)) + (" [disabled]" if pargs.noWrites else ""))
        if pargs.verbose > 2:
            print("\n".join(['#  {}'.format(str(items)) for items in recordsSinceLastCommit]))
    if not pargs.noWrites:
        # Save the records.
        db.executemany(commitStmt, recordsSinceLastCommit)
        db.commit()

        # Rebuild prices
    dbFilename = tdb.dbURI
    if pargs.verbose:
        print("- Rebuid prices file" + (" [disabled]" if pargs.noWrites else ""))

    if not pargs.noWrites:
        with tdb.pricesPath.open("w") as pricesFile:
            prices.dumpPrices(dbFilename, withModified=True, file=pricesFile)
        time.sleep(0.001)
        pathlib.Path(dbFilename).touch()


######################################################################

def main():
    records = 0

    pargs = processCommandLine()

    # Open the local TradeDangerous database
    dbFilename = pargs.db or TradeDB.defaultDB
    tdb = TradeDB(dbFilename=dbFilename, debug=1 if pargs.verbose else 0)
    db = tdb.getDB()

    loadUIOrders(db)

    # Open a connection to the firehose.
    firehose = Firehose(pargs.firehoseURI, debug=pargs.verbose)

    if pargs.verbose: print("* Capture starting.")

    lastCommit, duration = time.time(), pargs.duration
    recordsSinceLastCommit = []
    try:
        for rec in firehose.drink(records=pargs.records, timeout=duration):
            if pargs.commit:
                now = time.time()
                if now >= lastCommit + pargs.commit:
                    commit(tdb, db, recordsSinceLastCommit, pargs)
                    recordsSinceLastCommit = []
                    lastCommit = now

            records += 1

            if pargs.verbose and (records % 1000 == 0):
                print("# At {} captured {} records.".format(rec.timestamp, records))
            if pargs.verbose > 1:
                paying = localedNo(rec.payingCr)+'cr' if rec.payingCr else '    -    '
                asking = localedNo(rec.askingCr)+'cr' if rec.askingCr else '    -    '
                print("{} {:.<65} {:>9} {:>9}".format(rec.timestamp, '{} @ {}/{}'.format(rec.item, rec.system, rec.station), paying, asking))

            # Find the item in the price database to get its data and make sure
            # it matches the category we expect to see it listed in.
            try:
                item = tdb.lookupItem(rec.item)
                if TradeDB.normalizedStr(item.category.dbname) != TradeDB.normalizedStr(rec.category):
                    bleat("item", rec.item, "\aCATEGORY MISMATCH: {}/{} => item: {}/{} aka {}".format(rec.category, rec.item, item.category.dbname, item.dbname, item.altname or 'None'))
                    continue
            except LookupError:
                if not rec.item in blackMarketItems:
                    bleat("item", rec.item, "UNRECOGNIZED ITEM:", rec.item)
                continue

            # Lookup the station.
            try: system = tdb.lookupSystem(rec.system)
            except LookupError:
                bleat("system", rec.system, "UNRECOGNIZED SYSTEM:", rec.system)
                continue

            try: station = tdb.lookupStation(rec.station, system=system)
            except LookupError:
                bleat("station", rec.station, "UNRECOGNIZED STATION:", rec.system, rec.station)
                continue

            uiOrder = getItemUIOrder(station.ID, item.category.ID, item.ID)
            recordsSinceLastCommit.append([ item.ID, station.ID, uiOrder, rec.payingCr, rec.askingCr ])
    except KeyboardInterrupt:
        print("Ctrl-C pressed, stopping.")

    if pargs.verbose:
        print("Captured {} records total.".format(records))

    commit(tdb, db, recordsSinceLastCommit, pargs)


if __name__ == "__main__":
    main()

