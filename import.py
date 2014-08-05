import re
from tradedb import *
import pprint

tdb = TradeDB(r'.\TradeDangerous.accdb')

categories = dict()
for row in tdb.fetch_all("""
    SELECT  Categories.category, Items.item
      FROM  Categories INNER JOIN Items ON Categories.ID = Items.category_id
"""):
    (cat, item) = row
    if not cat in categories:
        categories[cat] = []
    categories[cat].append(item)

def list_search(listType, lookup, values):
    match = None
    needle = lookup.casefold()
    for val in values:
        if val.casefold().find(needle) > -1:
            if match:
                raise ValueError("Ambiguity: %s '%s' could match %s or %s" % (
                                    listType, lookup, match, val))
            match = val
    if not match:
        raise ValueError("Error: '%s' doesn't match any %s" % (lookup, listType))
    return match

import sys

def changeStation(name):
    global tdb
    station = tdb.getStation(name)
    print("Station Select: ", station)
    return station

def changeCategory(name):
    cat = list_search('category', name, categories)
    print("Category Select: ", cat)
    return cat

def parseItem(station, cat, line, uiOrder):
    fields = line.split()
    itemName, sellCr, buyCr = fields[0], int(fields[1]), int(fields[2] if len(fields) > 2 else 0)
    item = list_search('item', itemName, categories[cat])
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

with open('import.txt', 'r') as f:
    curStation = None
    curCat = None
    uiOrder = 0
    for line in f:
        line = line.strip()
        if not line:
            next
        if line[0] == '@':
            curStation = changeStation(line[1:])
        elif line[0] == '-':
            curCat = changeCategory(line[1:])
            uiOrder = 0
        else:
            if curStation == None or curCat == None:
                raise ValueError("Expecting station and category before items: " + line)
            uiOrder += 1
            parseItem(curStation, curCat, line, uiOrder)
