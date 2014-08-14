#!/usr/bin/env python
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

import re
from tradedb import *

rejectUnknown = False

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

import sys

def addStar(line):
    global tdb
    fields = line.split(':')
    sys, station = fields[0].split('/')
    sys, station = sys.strip(), station.strip()
    srcID = None
    if station == '*':
        station = sys.upper() + '*'
    try:
        srcID = tdb.getStation(station).ID
    except ValueError:
        tdb.query("INSERT INTO Stations (system, station) VALUES ('%s', '%s')" % (sys, station)).commit()
        print("Added %s/%s" % (sys, station))
        tdb.load()
        srcID = tdb.getStation(station).ID

    for dst in fields[1].split(','):
        dst, dist = dst.strip(), 1
        m = re.match(r'(.+)\s*@\s*(\d+\.\d+)(\s*ly)?', dst)
        if m:
            dst, dist = m.group(1), m.group(2)
        try:
            dstID = tdb.getStation(dst).ID
            try:
                tdb.query("INSERT INTO Links (`from`, `to`, `distLy`) VALUES (%d, %d, %s)" % (srcID, dstID, dist)).commit()
            except pypyodbc.IntegrityError:
                tdb.query("UPDATE Links SET distLy=%s WHERE from=%d and to=%d" % (dist, srcID, dstID)).commit()
            try:
                tdb.query("INSERT INTO Links (`from`, `to`, `distLy`) VALUES (%d, %d, %s)" % (dstID, srcID, dist)).commit()
            except pypyodbc.IntegrityError:
                tdb.query("UPDATE Links SET distLy=%s WHERE from=%d and to=%d" % (dist, dstID, srcID)).commit()
        except ValueError as e:
            if rejectUnknown:
                raise e
            print("* Unknown star system: %s" % dst)

def changeStation(name):
    global tdb
    station = tdb.getStation(name)
    print("Station Select: ", station)
    return station

def changeCategory(name):
    cat = tdb.list_search('category', name, categories)
    print("Category Select: ", cat)
    return cat

def parseItem(station, cat, line, uiOrder):
    fields = line.split()
    itemName, sellCr, buyCr = fields[0], int(fields[1]), int(fields[2] if len(fields) > 2 else 0)
    item = tdb.list_search('item', itemName, categories[cat])
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
        elif line[0] == '*':
            addStar(line[1:])
        elif line[0] == '@':
            curStation = changeStation(line[1:])
        elif line[0] == '-':
            curCat = changeCategory(line[1:])
            uiOrder = 0
        else:
            if curStation == None or curCat == None:
                raise ValueError("Expecting station and category before items: " + line)
            uiOrder += 1
            parseItem(curStation, curCat, line, uiOrder)
