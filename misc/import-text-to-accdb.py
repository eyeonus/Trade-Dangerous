#!/usr/bin/env python
# TradeDangerous :: Scripts :: Importer
# TradeDangerous Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#   You are free to use, redistribute, or even print and eat a copy of this
#   software so long as you include this copyright notice. I guarantee that
#   there is at least one bug neither of us knew about.
#
# Tool for importing data into the TradeDangerous database from a fairly
# simple text file, 'import.txt'.
#
# The first none white-space character of a line determines the line type:
#  '#' = comment,
#  '*' = add star and distances,
#  '@' = select station,
#  '-' = select item category,
# All other lines are treated as specifying an item price:
#  <item name> <station paying cr>
# or for an item that can be bought here:
#  <item name> <station paying cr> <station asking cr>
# Blank lines are ignored.
#
# Add star line:
#  *<star name>/<system name>:<other star>@<lightyears>
# Examples:
#  *Aulin/Enterprise:Dahan@9.6
#  *Dahan/Gateway:Aulin@9.6,Eranin@8.4ly,Hermitage@14ly,Ross1015@21.00
#
# Category and Item names use partial matching.
#   -che, -CheMiCAlS, -micals
# all match the "chemicals" category
# Don't include whitespaces, so
#   dom., dom.a, dom.appl
# would match the "dom. appliances" item (but only if you have selected
# the category at the moment)

from tradedb import *

# Assume that we're going to allow unknown stars for pre-declarations
rejectUnknown = False

tdb = TradeDB(r'.\TradeDangerous.accdb')

# Fetch a list of item categories, since TradeDB doesn't load it yet.
categories = dict()
for row in tdb.fetch_all("""
    SELECT  Categories.category, Items.item
      FROM  Categories INNER JOIN Items ON Categories.ID = Items.category_id
"""):
    (cat, item) = row
    if not cat in categories:
        categories[cat] = []
    categories[cat].append(item)


def addLinks(station, links):
    """ Add a list of links to nearby stars. DEPRECATED. """
    global tdb

    srcID = station.ID
    for dst in links.split(','):
        dst, dist = dst.strip(), 1
        m = re.match(r'(.+)\s*@\s*(\d+(\.\d+)?)(\s*ly)?', dst)
        if m:
            dst, dist = m.group(1), m.group(2)
        try:
            dstID = tdb.lookupStation(dst).ID
            try:
                tdb.query("INSERT INTO Links (`from`, `to`, `distLy`) VALUES (%d, %d, %s)" % (srcID, dstID, dist)).commit()
            except pypyodbc.IntegrityError:
                tdb.query("UPDATE Links SET distLy=%s WHERE from=%d and to=%d" % (dist, srcID, dstID)).commit()
            try:
                tdb.query("INSERT INTO Links (`from`, `to`, `distLy`) VALUES (%d, %d, %s)" % (dstID, srcID, dist)).commit()
            except pypyodbc.IntegrityError:
                tdb.query("UPDATE Links SET distLy=%s WHERE from=%d and to=%d" % (dist, dstID, srcID)).commit()
        except LookupError as e:
            if rejectUnknown:
                raise e
            print("* Unknown star system: %s" % dst)


def changeStation(line):
    global tdb

    matches = re.match(r'\s*(.*?)\s*/\s*(.*?)(:\s*(.*?))?\s*$', line)
    if matches:
        # Long format: system/station:links ...
        sysName, stnName, links = matches.group(1), matches.group(2), matches.group(4)
        if stnName == '*':
            stnName = sysName.upper().join('*')
        try:
            station = tdb.lookupStation(stnName)
        except LookupError:
            tdb.query("INSERT INTO Stations (system, station) VALUES (?, ?)", [sysName, stnName]).commit()
            print("Added %s/%s" % (sysName, stnName))
            tdb.load()
            station = tdb.lookupStation(stnName)
        if links:
            addLinks(station, links)
    else:
        # Short format: system/station name.
        station = tdb.lookupStation(line)

    print("Station: ", station)
    return station


def changeCategory(name):
    cat = tdb.listSearch('category', name, categories)
    print("Category Select: ", cat)
    return cat


def parseItem(station, cat, line, uiOrder):
    fields = line.split()
    itemName, sellCr, buyCr = fields[0], int(fields[1]), int(fields[2] if len(fields) > 2 else 0)
    item = tdb.listSearch('item', itemName, categories[cat])
    print("Item: ", item, sellCr, buyCr)

    stationID, itemID = int(station.ID), int(tdb.itemIDs[item])
    try:
        tdb.query("""
            INSERT INTO Prices (station_id, item_id, sell_cr, buy_cr, ui_order)
            VALUES (%d, %d, %d, %d, %d)""" % (stationID, itemID, sellCr, buyCr, uiOrder)).commit()
    except pypyodbc.IntegrityError as e:
        if int(e.value[0]) == 23000:
            tdb.query("""
                UPDATE Prices SET sell_cr=%d, buy_cr=%d, ui_order=%d
                 WHERE station_id = %d AND item_id = %d
                """ % (sellCr, buyCr, uiOrder, stationID, itemID)).commit()
        else:
            raise e


def main():
    with open('import.txt') as f:
        curStation = None
        curCat = None
        uiOrder = 0
        for line in f:
            line = line.strip()
            if not line or len(line) < 1:
                continue
            if line[0] == '#':
                if line == '#rejectUnknown':
                    rejectUnknown = True
                if line == '#stop':
                    break
                if line[0:5] == '#echo':
                    text = line[6:].strip()
                    print(text)
                continue    # comment
            elif line[0] == '*' or line[0] == '@':
                curStation = changeStation(line[1:])
            elif line[0] == '-':
                curCat = changeCategory(line[1:])
                uiOrder = 0
            else:
                if curStation is None or curCat is None:
                    raise ValueError("Expecting station and category before items: " + line)
                uiOrder += 1
                parseItem(curStation, curCat, line, uiOrder)

if __name__ == "__main__":
    main()
