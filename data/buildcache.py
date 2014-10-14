#!/usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Cache loader
#
#  TD works primarily from an SQLite3 database, but the data in that
#  is sourced from text files.
#   data/TradeDangerous.sql contains the less volatile data - systems,
#   ships, etc
#   data/TradeDangerous.prices contains a description of the price
#   database that is intended to be easily editable and commitable to
#   a source repository.
#
#  TODO: Split prices into per-system or per-station files so that
#  we can tell how old data for a specific system is.

import re
import sqlite3
import sys
import os
from collections import namedtuple

# Find the non-comment part of a string
noCommentRe = re.compile(r'^\s*(?P<text>(?:[^\\#]|\\.)+?)\s*(#|$)')
systemStationRe = re.compile(r'^\@\s*(.*)\s*/\s*(.*)')
categoryRe = re.compile(r'^\+\s*(.*?)\s*$')
itemPriceRe = re.compile(r'^(.*?)\s+(\d+)\s+(\d+)(?:\s+(\d{4}-.*?)(?:\s+demand\s+(-?\d+)L(-?\d+)\s+stock\s+(-?\d+)L(-?\d+))?)?$')

class PriceEntry(namedtuple('PriceEntry', [ 'stationID', 'itemID', 'asking', 'paying', 'uiOrder', 'modified', 'demand', 'demandLevel', 'stock', 'stockLevel' ])):
    pass

def priceLineNegotiator(priceFile, db, debug=0):
    """
        Yields SQL for populating the database with prices
        by reading the file handle for price lines.
    """

    stationID, categoryID, uiOrder = None, None, 0

    cur = db.cursor()

    cur.execute("""
            SELECT station_id, UPPER(system.name) || "/" || station.name
              FROM System INNER JOIN Station ON System.system_id = Station.system_id
        """)
    systemByName = { name: ID for (ID, name) in cur }

    categoriesByName = { name: ID for (ID, name) in cur.execute("SELECT category_id, name FROM category") }

    # Are there any item names which appear in two categories?
    qualityItemWithCategory = cur.execute("SELECT COUNT(*) FROM (SELECT name FROM Item GROUP BY 1 HAVING COUNT(*) > 1)").fetchone()[0]
    if qualityItemWithCategory:
        itemsByName = { "{}.{}".format(catID, name): itemID for (catID, itemID, name) in cur.execute("SELECT category_id, item_id, name FROM item") }
    else:
        itemsByName = { name: itemID for (itemID, name) in cur.execute("SELECT item_id, name FROM item") }

    for line in priceFile:
        try:
            text = noCommentRe.match(line).group('text').strip()
            # replace whitespace with single spaces
            text = ' '.join(text.split())      # http://stackoverflow.com/questions/2077897
            if not text: continue

            # Check for a station assignment
            matches = systemStationRe.match(text)
            if matches:
                # Change which station we're at
                stationName = "%s/%s" % (matches.group(1).upper(), matches.group(2))
                stationID, categoryID, uiOrder = systemByName[stationName], None, 0
                if debug > 1: print("NEW STATION: {}".format(stationName))
                continue
            if not stationID:
                print("Expecting: '@ SYSTEM / Station'.")
                print("Got: {}".format(line))
                sys.exit(1)

            # Check for a category assignment
            matches = categoryRe.match(text)
            if matches:
                categoryName = matches.group(1)
                categoryID, uiOrder = categoriesByName[categoryName], 0
                if debug > 1: print("NEW CATEGORY: {}".format(categoryName))
                continue
            if not categoryID:
                print("Expecting '+ Category Name'.")
                print("Got: {}".format(line))
                sys.exit(1)

            matches = itemPriceRe.match(text)
            if not matches:
                print("Unrecognized line/syntax: {}".format(line))
                sys.exit(1)
            itemName, stationPaying, stationAsking, modified = matches.group(1), int(matches.group(2)), int(matches.group(3)), matches.group(4)
            demand, demandLevel, stock, stockLevel = int(matches.group(5) or -1), int(matches.group(6) or -1), int(matches.group(7) or -1), int(matches.group(8) or -1)
            itemID = itemsByName["{}:{}".format(categoryID, itemName)] if qualityItemWithCategory else itemsByName[itemName]
            uiOrder += 1
            yield PriceEntry(stationID, itemID, stationPaying, stationAsking, uiOrder, modified, demand, demandLevel, stock, stockLevel)
        except (AttributeError, IndexError):
            continue


def processPricesFile(db, pricesPath, stationID=None, debug=0):
    global currentTimestamp

    if debug: print("* Processing Prices file '{}'".format(str(pricesPath)))

    if stationID:
        if debug: print("* Deleting stale entries for {}".format(stationID))
        db.execute("DELETE FROM Price WHERE station_id = {}".format(stationID))

    with pricesPath.open() as pricesFile:
        bindValues = []
        for price in priceLineNegotiator(pricesFile, db, debug):
            if debug > 2: print(price)
            bindValues += [ price ]
        stmt = """
                   INSERT OR REPLACE INTO Price (station_id, item_id, sell_to, buy_from, ui_order, modified, demand, demand_level, stock, stock_level)
                   VALUES (?, ?, ?, ?, ?, IFNULL(?, CURRENT_TIMESTAMP), ?, ?, ?, ?)
                """
        db.executemany(stmt, bindValues)
    db.commit()


def buildCache(dbPath, sqlPath, pricesPath, debug=0):
    """
        Rebuilds the SQlite database from source files.

        TD's data is either "stable" - information that rarely changes like Ship
        details, star systems etc - and "volatile" - pricing information, etc.

        The stable data starts out in data/TradeDangerous.sql while other data
        is stored in custom-formatted text files, e.g. ./TradeDangerous.prices.

        We load both sets of data into an SQLite database, after which we can
        avoid the text-processing overhead by simply checking if the text files
        are newer than the database.
    """

    # Create an in-memory database to populate with our data.
    if debug: print("* Creating temporary database in memory")
    tempDB = sqlite3.connect(':memory:')

    # Read the SQL script so we are ready to populate structure, etc.
    if debug: print("* Executing SQL Script '%s'" % sqlPath)
    with sqlPath.open() as sqlFile:
        sqlScript = sqlFile.read()
        tempDB.executescript(sqlScript)

    # Parse the prices file
    processPricesFile(tempDB, pricesPath)

    # Database is ready; copy it to a persistent store.
    if debug: print("* Populating SQLite database file '%s'" % dbPath)
    if dbPath.exists():
        if debug: print("- Removing old database file")
        dbPath.unlink()

    newDB = sqlite3.connect(str(dbPath))
    importScript = "".join(tempDB.iterdump())
    if debug > 3: print(importScript)
    newDB.executescript(importScript)
    newDB.commit()

    if debug: print("* Finished")


def commandLineBuildCache():
    # Because it looks less sloppy that doing this in if __name__ == '__main__'...
    from tradedb import TradeDB
    dbFilename = TradeDB.defaultDB
    sqlFilename = TradeDB.defaultSQL
    pricesFilename = TradeDB.defaultPrices

    # Check command line for -w/--debug inputs.
    import argparse
    parser = argparse.ArgumentParser(description='Build TradeDangerous cache file from source files')
    parser.add_argument('--db', help='Specify database file to build. Default: {}'.format(dbFilename), default=dbFilename, required=False)
    parser.add_argument('--sql', help='Specify SQL script to execute. Default: {}'.format(sqlFilename), default=sqlFilename, required=False)
    parser.add_argument('--prices', help='Specify the prices file to load. Default: {}'.format(pricesFilename), default=pricesFilename, required=False)
    parser.add_argument('-f', '--force', dest='force', help='Overwite existing file', default=False, required=False, action='store_true')
    parser.add_argument('-w', '--debug', dest='debug', help='Increase level of diagnostic output', default=0, required=False, action='count')
    args = parser.parse_args()

    import pathlib

    # Check that the file doesn't already exist.
    dbPath, sqlPath, pricesPath = pathlib.Path(args.db), pathlib.Path(args.sql), pathlib.Path(args.prices)
    if not args.force:
        if dbPath.exists():
            print("{}: ERROR: SQLite3 database '{}' already exists. Please remove it first.".format(sys.argv[0], args.db))
            sys.exit(1)

    if not sqlPath.exists():
        print("SQL file '{}' does not exist.".format(args.sql))
        sys.exit(1)

    if not pricesPath.exists():
        print("Prices file '{}' does not exist.".format(args.prices))

    buildCache(dbPath, sqlPath, pricesPath, args.debug)


if __name__ == '__main__':
    commandLineBuildCache()
