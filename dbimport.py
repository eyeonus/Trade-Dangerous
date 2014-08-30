#!/usr/bin/env python
# TradeDangerous :: Modules :: Cache loader
# TradeDangerous Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#   You are free to use, redistribute, or even print and eat a copy of this
#   software so long as you include this copyright notice. I guarantee that
#   there is at least one bug neither of us knew about.

import re
import sqlite3
import sys
import os
from collections import namedtuple

# Find the non-comment part of a string
noCommentRe = re.compile(r'^\s*(?P<text>(?:[^\\#]|\\.)+?)\s*(#|$)')
systemStationRe = re.compile(r'^\@\s*(.*)\s*/\s*(.*)')
categoryRe = re.compile(r'^\+\s*(.*?)\s*$')
itemPriceRe = re.compile(r'^(.*?)\s+(\d+)\s+(\d+)$')

class PriceEntry(namedtuple('PriceEntry', [ 'stationID', 'itemID', 'asking', 'paying', 'uiOrder' ])):
    pass

def price_line_negotiator(priceFile, db, debug):
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
    itemsByName = { "{}:{}".format(catID, name): itemID for (catID, itemID, name) in cur.execute("SELECT category_id, item_id, name FROM item") }

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
                if debug: print("NEW STATION: {}".format(stationName))
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
                if debug: print("NEW CATEGORY: {}".format(categoryName))
                continue
            if not categoryID:
                print("Expecting '+ Category Name'.")
                print("Got: {}".format(line))
                sys.exit(1)

            matches = itemPriceRe.match(text)
            if not matches:
                print("Unrecognized line/syntax: {}".format(line))
                sys.exit(1)
            itemName, stationPaying, stationAsking = matches.group(1), int(matches.group(2)), int(matches.group(3))
            itemID = itemsByName["{}:{}".format(categoryID, itemName)]
            uiOrder += 1
            yield PriceEntry(stationID, itemID, stationPaying, stationAsking, uiOrder)
        except (AttributeError, IndexError):
            continue

def build_db_cache(dbFilename, sqlFilename, pricesFilename, debug=0):
    """
        Rebuilds the .sq3 database from source files.

        TD's data is either "stable" - information that rarely changes like Ship
        details, star systems etc - and "volatile" - pricing information, etc.

        The stable data starts out in data/TradeDangerous.sql while other data
        is stored in custom-formatted text files, e.g. ./TradeDangerous.prices.

        We load both sets of data into an SQLite database, after which we can
        avoid the text-processing overhead by simply checking if the text files
        are newer than the database.
    """

    # Create an in-memory database to populate with our data.
    tempDB = sqlite3.connect(':memory:')

    # Read the SQL script so we are ready to populate structure, etc.
    if debug: print("* Executing SQL Script '%s'" % sqlFilename)
    with open(sqlFilename) as sqlFile:
        sqlScript = sqlFile.read()
        tempDB.executescript(sqlScript)

    # Parse the prices file
    if debug: print("* Processing Prices file '%s'" % pricesFilename)
    with open(pricesFilename) as pricesFile:
        bindValues = []
        for price in price_line_negotiator(pricesFile, tempDB, debug):
            if debug: print(price)
            bindValues += [ price ]
        stmt = """
                   INSERT INTO Price (station_id, item_id, sell_to, buy_from, ui_order)
                   VALUES (?, ?, ?, ?, ?)
                """
        tempDB.executemany(stmt, bindValues)

    # Database is ready; copy it to a persistent store.
    if debug: print("* Populating .sq3 file '%s'" % dbFilename)
    try:
        os.remove(dbFilename)
    except FileNotFoundError:
        pass
    newDB = sqlite3.connect(dbFilename)
    newDB.executescript("".join(tempDB.iterdump()))
    newDB.commit()

    if debug: print("* Finished")


if __name__ == '__main__':
    build_db_cache('testdb.sq3', 'data/TradeDangerous.sql', 'TradeDangerous.prices', debug=99)
