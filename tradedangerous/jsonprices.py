# Deprecated
from tradedangerous import tradedb
from tradedangerous.tradeexcept import TradeException

import json
import sys


sys.stderr.write("*** WARNING: jsonprices.py is deprecated; if you rely on it, please post a github issue\n")


class UnknownSystemError(TradeException):
    def __str__(self):
        return "Unknown System: " + ' '.join(self.args)

class UnknownStationError(TradeException):
    def __str__(self):
        return "Unknown Station: " + ' '.join(self.args)


def lookup_system(tdb, tdenv, name, x, y, z):
    try:
        system = tdb.systemByName[name.upper()]
    except KeyError:
        system = None
    if not system:
        try:
            system = tdb.lookupSystem(name)
        except LookupError:
            pass
    
    if system:
        if system.posX != x or system.posY != y or system.posZ != z:
            raise Exception("System {} position mismatch: "
                    "Got {},{},{} expected {},{},{}".format(
                        name,
                        x, y, z,
                        system.posX, system.posY, system.posZ
            ))
        return system
    
    candidates = []
    for candidate in tdb.systemByID.values():
        if candidate.posX == x and candidate.posY == y and candidate.posZ == z:
            candidates.append(candidate)
    
    if len(candidates) == 1:
        candidate = candidates[0]
        if candidate.casefold() != name.casefold():
            if not tdenv.quiet:
                print("System name mismatch: "
                        "Local: {}, "
                        "Remote: {}, "
                        "Coords: {}, {}, {}".format(
                            name,
                            candidate.dbname,
                            candidate.posX,
                            candidate.posY,
                            candidate.posZ,
                ))
        return candidates[0]
    
    if candidates:
        options = ', '.join([s.name for s in candidates])
        raise RuntimeError(f"System {system.name} matches co-ordinates for systems: {options}")
    
    if tdenv.addUnknown:
        return tdb.addLocalSystem(name, x, y, z)
    
    return None

def lookup_station(
        tdb, tdenv,
        system, name,
        lsFromStar, blackMarket, maxPadSize
        ):
    station = None
    normalizedName = tradedb.TradeDB.normalizedStr(name)
    for stn in system.stations:
        stnNormalizedName = tradedb.TradeDB.normalizedStr(stn.dbname)
        if stnNormalizedName == normalizedName:
            station = stn
            break
    
    if not station:
        if not tdenv.addUnknown:
            return None
        station = tdb.addLocalStation(system, name)
    
    # Now set the parameters
    tdb.updateLocalStation(
            station, lsFromStar, blackMarket, maxPadSize
    )
    return station

def load_prices_json(
        tdb,
        tdenv,
        jsonText
        ):
    """
    Take data from a prices file and load it into the database.
    """
    
    data = json.loads(jsonText)
    
    sysData = data['sys']
    sysName = sysData['name']
    pos = sysData['pos']
    
    stnData = data['stn']
    stnName = stnData['name']
    lsFromStar = stnData['ls']
    
    try:
        blackMarket = stnData['bm'].upper()
        if blackMarket not in [ 'Y', 'N' ]:
            blackMarket = '?'
    except KeyError:
        blackMarket = '?'
    
    try:
        maxPadSize = stnData['mps'].upper()
        if maxPadSize not in ['S', 'M', 'L']:
            maxPadSize = '?'
    except KeyError:
        maxPadSize = '?'
    
    system = lookup_system(
            tdb, tdenv,
            sysName,
            pos[0], pos[1], pos[2],
            )
    if not system:
        if not tdenv.ignoreUnknown:
            raise UnknownSystemError(sysName)
        if not tdenv.quiet:
            print("NOTE: Ignoring unknown system: {} [{},{},{}]".format(
                    sysName,
                    pos[0], pos[1], pos[2],
            ))
        return
    if system.dbname != sysName and tdenv.detail:
        print("NOTE: Treating '{}' as '{}'".format(
                sysName, system.dbname
        ))
    tdenv.DEBUG1("- System: {}", system.dbname)
    
    station = lookup_station(
            tdb, tdenv,
            system,
            stnName,
            lsFromStar,
            blackMarket,
            maxPadSize,
            )
    if not station:
        if tdenv.ignoreUnknown:
            raise UnknownStationError(stnName)
        if not tdenv.quiet:
            print("NOTE: Ignoring unknown station: {}/{}".format(
                    sysName.upper(), stnName
            ))
        return
    tdenv.DEBUG1("- Station: {}", station.dbname)

def generate_prices_json(
        tdb,
        tdenv,
        station,
        ):
    """
    Generate a JSON dump of the specified station along
    with everything we know about the station and the system
    it is in. 
    
    tdb:
        The TradeDB object to use
    tdenv:
        Settings
    station:
        Station to dump
    """
    
    system = station.system
    
    stationData = {
        'cmdr': tdenv.commander or "unknown",
        'src': 'td/price-json',
        'sys': {
            'name': system.dbname,
            'pos': [ system.posX, system.posY, system.posZ ],
        },
        'stn': {
            'name': station.dbname,
            'ls': station.lsFromStar,
        },
        'items': {}
    }
    
    conn = tdb.getDB()
    cur = conn.cursor()
    cur.execute("""
            SELECT  si.item_id,
                    si.modified,
                    sb.price, sb.units, sb.level,
                    ss.price, ss.units, ss.level
              FROM  StationItem AS si
                    LEFT OUTER JOIN StationBuying AS sb
                        ON (
                            sb.station_id = si.station_id
                            AND sb.item_id = si.item_id
                        )
                    LEFT OUTER JOIN StationSelling AS ss
                        ON (
                            ss.station_id = si.station_id
                            AND ss.item_id = si.item_id
                        )
             WHERE  si.station_id = ?
    """, [station.ID])
    
    items = {}
    
    lastModified = "0"
    for (
            itemID, modified,
            sbPrice, sbUnits, sbLevel,
            ssPrice, ssUnits, ssLevel
    ) in cur:
        lastModified = max(lastModified, modified)
        item = tdb.itemByID[itemID]
        itemData = items[item.dbname] = {
            'm': modified,
        }
        if sbPrice and (sbUnits >= 0 or sbLevel >= 0):
            itemData['b'] = [ sbPrice, sbUnits, sbLevel ]
        elif sbPrice:
            itemData['b'] = sbPrice
        if ssPrice and (ssUnits >= 0 or sbLevel >= 0):
            itemData['s'] = [
                ssPrice, ssUnits, ssLevel
            ]
        elif ssPrice:
            itemData['s'] = ssPrice
    
    # dedupe timestamps.
    for itemData in items.values():
        if itemData['m'] == lastModified:
            del itemData['m']
    
    stationData['m'] = lastModified
    stationData['items'] = items
    
    return json.dumps(stationData, separators=(',',':'))
