# Deprecated
from .commandenv import ResultRow
from .exceptions import CommandLineError
from .parsing import MutuallyExclusiveGroup, ParseArgument
from ..tradedb import AmbiguityError
from ..tradedb import Station
from ..tradedb import TradeDB
from .. import utils
from ..formatting import max_len

from .. import cache
from .. import csvexport
import difflib
import re


######################################################################
# Parser config

help='Add (or update) a station entry'
name='station'
epilog=None
arguments = [
    ParseArgument(
        'station',
        help='Specify the full name of the station (SYS NAME/STN NAME is also supported).',
        type=str,
        nargs='+',
    ),
]
switches = [
    MutuallyExclusiveGroup(
        ParseArgument(
            '--update', '-u',
            help='Indicates you expect the entry to already exist.',
            action='store_true',
        ),
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
        '--ls-from-star',
        help='Number of light seconds between station and star.',
        type=int,
        dest='lsFromStar',
    ),
    # Note: these are not the usual arguments, they're asking the
    # user to assign rather than select values.
    ParseArgument(
        '--black-market', '--bm',
        help='Does the station have a black market (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
        dest='blackMarket',
    ),
    ParseArgument(
        '--market',
        help='Does the station have a commodities market (Y or N), ? for unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--shipyard',
        help='Does the station have a shipyard (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--pad-size',
        help='Maximum supported pad size (S, M, or L) or ? if unknown.',
        choices=['S', 's', 'M', 'm', 'L', 'l', '?'],
        dest='padSize',
    ),
    ParseArgument(
        '--outfitting',
        help='Does the station provide outfitting (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--rearm', '--arm',
        help='Does the station provide rearming (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--refuel',
        help='Does the station provide refueling (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--repair',
        help='Does the station provide repairs (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--planetary',
        help='Is the station on a planet (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--fleet-carrier', '--fc',
        dest='fleet',
        help='Is the station a Fleet Carrier (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--odyssey', '--od',
        help='Is the station an Odyssey Settlement (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
    ),
    ParseArgument(
        '--confirm',
        help='For confirmation suspicious looking station names.',
        metavar='CONFIRMATION CODE',
        type=str,
    ),
    ParseArgument(
        '--no-export',
        help='Do not update the .csv files.',
        action='store_true',
        dest='noExport',
    )
]

######################################################################
# Helpers

def makeConfirmationCode(base, candidates):
    """
    Makes a four-digit hex checksum of a station list.
    """
    checksum = base
    for cand in candidates:
        for character in cand:
            checksum <<= 4
            checksum += ord(character)
    
    # python integers don't overflow, so we only need
    # to modulo at the end of the checksum.
    checksum %= 65521       # arbitrary prime < 2^32
    
    return hex(checksum).upper()[2:]


def checkStationDoesNotExist(tdb, cmdenv, system, stationName):
    if not system.stations:
        return
    
    upperName = stationName.upper()
    similarities = set()
    try:
        station = tdb.lookupStation(stationName, system)
        if station.dbname.upper() == upperName:
            raise CommandLineError(
                    "Station \"{}\" "
                    "in system \"{}\" "
                    "already exists.".format(
                        stationName, system.name(),
            ))
        similarities.add(station.dbname.upper())
    except LookupError:
        pass
    except AmbiguityError as e:
        for cand in e.anyMatch:
            similarities.add(e.key(cand).upper())
    
    # Check to see if there are stations with somewhat
    # similar names, but allow the user to get around
    # cases where difflib matches 'X Port' to 'Y Port'.
    stationNames = [
        stn.dbname.upper()
        for stn in system.stations
    ]
    cmdenv.DEBUG0("Comparing {} to {}".format(
            upperName, list(stationNames),
    ))
    candidates = difflib.get_close_matches(
            upperName, stationNames, cutoff=0.6,
    )
    for cand in candidates:
        similarities.add(cand)
    
    if not similarities:
        return
    
    confCode = makeConfirmationCode(system.ID, similarities)
    
    if not cmdenv.confirm:
        raise CommandLineError(
                "\"{}\" contains similar station names:\n"
                "  {}\n"
                "\n"
                "If you want to add this station anyway, re-run the "
                "command and add:\n"
                "  --conf {}".format(
                    system.name(),
                    ', '.join(candidates),
                    confCode
        ))
    
    if cmdenv.confirm.upper() != confCode:
        raise CommandLineError(
            "Wrong confirmation code."
        )
    
    cmdenv.NOTE("Confirmation code accepted.")


def checkSystemAndStation(tdb, cmdenv):
    # In add mode, the user has to be more specific.
    stnName = ' '.join(cmdenv.station).strip()
    
    if not cmdenv.add:
        try:
            station = tdb.lookupPlace(stnName)
        except LookupError:
            raise CommandLineError("Unrecognized Station: {}".format(
                cmdenv.station
            ))
        if not isinstance(station, Station):
            raise CommandLineError(
                "Expecting a STATION, got {}".format(stnName)
            )
        cmdenv.system = station.system.name()
        cmdenv.station = station.dbname
        
        return station.system, station
    
    # Clean up the station name and potentially lift the system
    # name out of it.
    stnName = re.sub(r" +", " ", stnName)
    stnName = re.sub(r"[ /]*/[ /]*", "/", stnName)
    while stnName.startswith('/'):
        stnName = stnName[1:]
    slashPos = stnName.find('/')
    if slashPos > 0:
        sysName, stnName = stnName[:slashPos], stnName[slashPos+1:]
        sysName = sysName.upper()
    else:
        sysName = None
    
    if not stnName:
        raise CommandLineError("Invalid station name: {stnName}")
    
    if not sysName:
        raise CommandLineError("No system name specified")
    
    cmdenv.system, cmdenv.station = sysName, utils.titleFixup(stnName)
    try:
        system = tdb.lookupSystem(sysName)
    except LookupError:
        raise CommandLineError(
                "Unknown SYSTEM name: \"{}\"".format(
                    sysName
        ))
    
    # check the station does not exist
    checkStationDoesNotExist(tdb, cmdenv, system, stnName)
    
    return system, None


def addStation(tdb, cmdenv, system, stationName):
    return tdb.addLocalStation(
            system=system,
            name=stationName,
            lsFromStar=cmdenv.lsFromStar or 0,
            market=cmdenv.market or '?',
            blackMarket=cmdenv.blackMarket or '?',
            shipyard=cmdenv.shipyard or '?',
            outfitting=cmdenv.outfitting or '?',
            rearm=cmdenv.rearm or '?',
            refuel=cmdenv.refuel or '?',
            repair=cmdenv.repair or '?',
            maxPadSize=cmdenv.padSize or '?',
            planetary=cmdenv.planetary or '?',
            fleet=cmdenv.fleet or '?',
            odyssey=cmdenv.odyssey or '?',
            commit=True,
    )


def updateStation(tdb, cmdenv, station):
    return tdb.updateLocalStation(
            station=station,
            lsFromStar=cmdenv.lsFromStar,
            market=cmdenv.market,
            blackMarket=cmdenv.blackMarket,
            shipyard=cmdenv.shipyard,
            outfitting=cmdenv.outfitting,
            rearm=cmdenv.rearm,
            refuel=cmdenv.refuel,
            repair=cmdenv.repair,
            maxPadSize=cmdenv.padSize,
            planetary=cmdenv.planetary,
            fleet=cmdenv.fleet,
            odyssey=cmdenv.odyssey,
            force=True,
            commit=True,
    )


def removeStation(tdb, cmdenv, station):
    db = tdb.getDB()
    db.execute("""
            DELETE FROM Station WHERE station_id = ?
    """, [station.ID])
    db.commit()
    cmdenv.NOTE("{} (#{}) removed from {} database.",
            station.name(), station.ID, tdb.dbPath)
    cmdenv.stationItemCount = station.itemCount
    return True


def checkResultAndExportStations(tdb, cmdenv, result):
    if not result:
        cmdenv.NOTE("No changes.")
        return None
    if cmdenv.noExport:
        cmdenv.DEBUG0("no-export set, not exporting stations")
        return None
    
    lines, csvPath = csvexport.exportTableToFile(tdb, cmdenv, "Station")
    cmdenv.NOTE("{} updated.", csvPath)
    
    if cmdenv.remove:
        if cmdenv.stationItemCount:
            cmdenv.NOTE("Station had items, regenerating .prices file")
            cache.regeneratePricesFile(tdb, cmdenv)
    
    return None


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    if cmdenv.lsFromStar and cmdenv.lsFromStar < 0:
        raise CommandLineError("Invalid (negative) --ls option")
    
    system, station = checkSystemAndStation(tdb, cmdenv)
    
    stationName = cmdenv.station
    
    if cmdenv.add:
        result = addStation(tdb, cmdenv, system, stationName)
        return checkResultAndExportStations(tdb, cmdenv, result)
    elif cmdenv.update:
        result = updateStation(tdb, cmdenv, station)
        return checkResultAndExportStations(tdb, cmdenv, result)
    elif cmdenv.remove:
        result = removeStation(tdb, cmdenv, station)
        return checkResultAndExportStations(tdb, cmdenv, result)
    
    # Otherwise, it's just a query
    results.summary = ResultRow()
    results.summary.system = station.system
    results.summary.station = station
    
    avgSell = results.summary.avgSelling = tdb.getAverageSelling()
    avgBuy = results.summary.avgBuying = tdb.getAverageBuying()
    
    class ItemTrade:
        def __init__(self, ID, price, avgAgainst):
            self.ID, self.item = ID, tdb.itemByID[ID]
            self.price = int(price)
            self.avgTrade = avgAgainst.get(ID, 0)
    
    # Look up all selling and buying by the station
    selling, buying = [], []
    cur = tdb.query("""
        SELECT  item_id, demand_price, supply_price
          FROM  StationItem
         WHERE  station_id = ?
                AND (demand_price > 10 or supply_price > 10)
    """, [station.ID])
    for ID, demand_price, supply_price in cur:
        if demand_price > 10 and avgSell.get(ID, 0) > 10:
            buying.append(ItemTrade(ID, demand_price, avgSell))
        if supply_price > 10 and avgBuy.get(ID, 0) > 10:
            selling.append(ItemTrade(ID, supply_price, avgBuy))
    selling.sort(
            key=lambda item: item.price - item.avgTrade,
    )
    results.summary.selling = selling[:5]
    buying.sort(
            key=lambda item: item.avgTrade - item.price,
    )
    results.summary.buying = buying[:5]
    
    return results

def render(results, cmdenv, tdb):
    system, station = results.summary.system, results.summary.station
    
    if cmdenv.detail:
        sysDetail = "(#{} @ {},{},{})".format(
            system.ID, system.posX, system.posY, system.posZ
        )
    else:
        sysDetail = "(#{})".format(system.ID)
    
    print("Station Data:")
    print("System....:", system.name(), sysDetail)
    print("Station...:", station.dbname, "(#{})".format(station.ID))
    
    if cmdenv.detail:
        siblings = ", ".join(
            stn.dbname
            for stn in system.stations
            if stn is not station
        )
        if siblings:
            print("Also Here.:", siblings)
    
    ls = station.distFromStar()
    if cmdenv.detail and ls == '?':
        ls = '0 [unknown]'
    print("Stn/Ls....:", ls)
    
    def _detail(value, source):
        detail = source[value]
        if cmdenv.detail and detail == '?':
            detail += ' [unknown]'
        return detail
    print("Pad Size..:", _detail(station.maxPadSize, TradeDB.padSizes))
    print("Market....:", _detail(station.market, TradeDB.marketStates))
    print("B/Market..:", _detail(station.blackMarket, TradeDB.marketStates))
    print("Shipyard..:", _detail(station.shipyard, TradeDB.marketStates))
    print("Outfitting:", _detail(station.outfitting, TradeDB.marketStates))
    print("Rearm.....:", _detail(station.rearm, TradeDB.marketStates))
    print("Refuel....:", _detail(station.refuel, TradeDB.marketStates))
    print("Repair....:", _detail(station.repair, TradeDB.marketStates))
    print("Planetary.:", _detail(station.planetary, TradeDB.planetStates))
    print("Fleet.....:", _detail(station.fleet, TradeDB.fleetStates))
    print("Odyssey...:", _detail(station.odyssey, TradeDB.odysseyStates))
    print("Prices....:", station.itemCount or 'None')
    
    if station.itemCount == 0:
        return
    
    newest, oldest = tdb.query("""
            SELECT JULIANDAY('NOW') - JULIANDAY(MAX(si.modified)),
                   JULIANDAY('NOW') - JULIANDAY(MIN(si.modified))
              FROM StationItem si
             WHERE station_id = ?
    """, [station.ID]).fetchone()
    if newest or oldest:
        # less than a quarter hour difference? ignore?
        if abs(newest - oldest) < (1 / (24 * 4)):
            pricesAge = "{:.2f} days".format(oldest)
        else:
            pricesAge = "{:.2f}-{:.2f} days".format(newest, oldest)
    else:
        pricesAge = "[n/a]"
    
    print("Price Age.:", pricesAge)
    
    def makeBest(rows, explanation, alt, maxLen, starFn):
        if not rows:
            return "[n/a]"
        best = []
        for irow in rows:
            star = '*' if starFn(irow.price, irow.avgTrade) else ''
            best.append([irow, star])
        
        if not cmdenv.detail:
            return ', '.join(irow[0].item.name() + irow[1] for irow in best)
        
        bestText = "("+explanation+")"
        for irow in best:
            bestText += "\n    {:<{len}} @ {:7n}cr (Avg {} {:7n}cr)".format(
                    irow[0].item.name(cmdenv.detail) + irow[1],
                    irow[0].price,
                    alt,
                    irow[0].avgTrade,
                    len=maxLen + 1,
            )
        return bestText


    longestNameLen = max(
        max_len(results.summary.selling, key=lambda row: row.item.name(cmdenv.detail)),
        max_len(results.summary.buying, key=lambda row: row.item.name(cmdenv.detail)),
    )
    print("Best Buy..:", makeBest(
            results.summary.selling, "Buy from this station", "Sell", longestNameLen,
            starFn=lambda price, avgCr: price <= (avgCr * 0.9),
    ))
    print("Best Sale.:", makeBest(
            results.summary.buying, "Sell to this station", "Cost", longestNameLen,
            starFn=lambda price, avgCr: price >= (avgCr * 1.1),
    ))
