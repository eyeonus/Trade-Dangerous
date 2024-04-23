#! /usr/bin/env python

# Experimental module to generate a JSON version of the .prices file.

import sqlite3
import json
import time
import collections
import os


# Set to True to allow export of systems that don't have any station data
emptySystems = True
# Set to True to allow export of stations that don't have prices
emptyStations = True

conn = sqlite3.connect("data/TradeDangerous.db")


def collectItemData(db):
    """
    Builds a flat, array of item names that serves as a table of items.
    Station Price Data refers to this table by position in the array.
    As a result, we also need a mapping for itemID -> tableID
    """
    
    items = []      # table of items
    itemIdx = {}    # mapping from itemID -> position in items
    for ID, name in db.execute("SELECT i.item_id, i.name FROM Item AS i"):
        itemIdx[ID] = len(items)
        items.append(name)
    
    return items, itemIdx


def collectSystems(
            db,
            itemIdx,
            withEmptySystems=False,
            withStations=True,
            withEmptyStations=False,
            withPrices=True
    ):
    """
    Build the System -> Station -> Price data from the supplied DB.
    
    withEmptySystems:
        True: include systems with no station data.
    
    withStations:
        False: (implies withEmptySystems=True) don't include station data.
    
    withEmptyStations:
        True: include stations with no price data.
    
    withPrices:
        False: (implies withEmptyStations=True) don't include price data.
    """
    
    systems = collections.defaultdict(dict)
    if not withStations:
        withEmptySystems = True
    
    for sysID, sys, posX, posY, posZ in db.execute("""
            SELECT  sys.system_id, sys.name,
                    sys.pos_x, sys.pos_y, sys.pos_z
            FROM  System AS sys
                    LEFT OUTER JOIN Station
                        USING (system_id)
            GROUP  BY 1
            """):
        systemData = {
                 'pos': [ posX, posY, posZ ],
        }
        if withStations:
            stations = collectStations(
                    db, itemIdx,
                    sysID,
                    withEmptyStations=withEmptyStations,
                    withPrices=withPrices,
            )
            if not stations and not withEmptySystems:
                continue
            if stations:
                systemData['stn'] = stations
        systems[sys] = systemData
    
    return systems


def collectStations(
            db,
            itemIdx,
            sysID,
            withEmptyStations=False,
            withPrices=True
    ):
    """
    Populate a station list for a given system, including price data.
    """
    stations = {}
    if not withPrices:
        withEmptyStations = True
    for stnID, name, lsFromStar, lastMod in db.execute("""
            SELECT  stn.station_id, stn.name, stn.ls_from_star,
                    MAX(si.modified)
              FROM  Station AS stn
                    LEFT OUTER JOIN StationItem si
                        USING (station_id)
             WHERE  stn.system_id = ?
             GROUP  BY 1
            """, [sysID]):
        if not lastMod and not withEmptyStations:
            continue
        stationData = {
                'ls':   int(lsFromStar),
        }
        if lastMod:
            stationData['ts'] = lastMod
            if withPrices:
                buy, sell = collectPriceData(
                        db, itemIdx,
                        stnID,
                )
                stationData['buy'] = buy
                stationData['sell'] = sell
        
        stations[name] = stationData
    
    return stations


def collectPriceData(db, itemIdx, stnID):
    """
    Collect buying and selling data for a given station. Items reference the
    position in the itemData array.
    """
    
    buying, selling = [], []
    
    for itmID, cr in db.execute("""
            SELECT  sb.item_id, sb.price
              FROM  StationBuying AS sb
             WHERE  station_id = ?
            """, [stnID]):
        buying.append([ itemIdx[itmID], cr ])
    
    for itmID, cr, units, level in db.execute("""
            SELECT  ss.item_id, ss.price, ss.units, ss.level
              FROM  StationSelling AS ss
             WHERE  station_id = ?
            """, [stnID]):
        selling.append([ itemIdx[itmID], cr, units, level ])
    
    return buying, selling


itemData, itemIdx = collectItemData(conn)
sysData = collectSystems(
        conn, itemIdx,
        withEmptySystems=emptySystems, withEmptyStations=emptyStations
)
jsonData = {
    'src': 'td/json-exp',
    'time': int(time.time()),
    'items': itemData,
    'emptySys': emptySystems,
    'emptyStn': emptyStations,
    'sys': sysData,
}

try:
    cmdrName = os.environ['CMDR']
    jsonData['cmdr'] = cmdrName
except KeyError:
    pass

print(json.dumps(jsonData, separators=(',',':')))

