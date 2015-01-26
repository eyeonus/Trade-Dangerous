from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.commandenv import ResultRow
from commands.exceptions import CommandLineError
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from tradedb import AmbiguityError
from tradedb import System, Station
from tradedb import TradeDB

import csvexport
import difflib
import re
import sys

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
    ParseArgument(
        '--system',
        help='Specify the full name of the system the station is in if not specified in the "station" argument.',
        type=str,
        nargs='+',
        default=[],
    ),
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
        type=float,
        default=0.0,
        dest='lsFromStar',
    ),
    ParseArgument(
        '--black-market', '--bm',
        help='Does the station have a black market (Y or N) or ? if unknown.',
        choices=['Y', 'y', 'N', 'n', '?'],
        default='?',
        dest='blackMarket',
    ),
    ParseArgument(
        '--pad-size',
        help='Maximum supported pad size (S, M, or L) or ? if unknown.',
        choices=['S', 's', 'M', 'm', 'L', 'l', '?'],
        default='?',
        dest='padSize',
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
    # The user can supply "--system Foo Bar --station Baz" or
    # "--station Foo Bar / Baz". This means that the values
    # can be arrays. We need to make strings out of the arrays,
    # and then sanitize them for the '@SYS/STN' format, and
    # build a separate system and station name out of that.
    stnName = ' '.join(cmdenv.station).strip()

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
        raise CommandLineError("Invalid station name: {}".format(
                envStnName
        ))

    if cmdenv.system:
        envSysName = ' '.join(cmdenv.system).upper()
        if sysName and envSysName != sysName:
            raise CommandLineError(
                    "Mismatch between \"--system {}\" and "
                    "system name in station specifier "
                    "(\"{}\")".format(
                        envSysName, sysName,
            ))
        sysName = envSysName

    if not sysName:
        raise CommandLineError("No system name specified")

    cmdenv.system, cmdenv.station = sysName, TradeDB.titleFixup(stnName)

    # If we're adding a station, we need to check that the system
    # exists and that it doesn't contain a close-match for this
    # system name already.
    if cmdenv.add:
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

    # We want an existing station, try looking it up by combining
    # the station and system names for precision.
    try:
        station = tdb.lookupPlace("{}/{}".format(sysName, stnName))
    except LookupError:
        raise CommandLineError("Unrecognized Station: {}/{}".format(
                sysName,
                cmdenv.station,
        ))
    cmdenv.system = station.system.name()
    cmdenv.station = station.dbname

    return station.system, station


def addStation(tdb, cmdenv, system, stationName):
    return tdb.addLocalStation(
            system=system,
            name=stationName,
            lsFromStar=cmdenv.lsFromStar,
            blackMarket=cmdenv.blackMarket,
            maxPadSize=cmdenv.padSize,
    )


def updateStation(tdb, cmdenv, station):
    return tdb.updateLocalStation(
            station=station,
            lsFromStar=cmdenv.lsFromStar,
            blackMarket=cmdenv.blackMarket,
            maxPadSize=cmdenv.padSize,
    )


def removeStation(tdb, cmdenv, station):
    db = tdb.getDB()
    db.execute("""
            DELETE FROM Station WHERE station_id = ?
    """, [station.ID])
    db.commit()
    cmdenv.NOTE("{} (#{}) removed from {} database.",
            station.name(), station.ID, tdb.dbPath)


def checkResultAndExportStations(tdb, cmdenv, result):
    if not result:
        return None
    if cmdenv.noExport:
        cmdenv.DEBUG0("no-export set, not exporting stations")
        return None

    lines, csvPath = csvexport.exportTableToFile(tdb, cmdenv, "Station")
    cmdenv.NOTE("{} updated.", csvPath)
    return None


######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    if cmdenv.lsFromStar < 0:
        raise CommandLineError("Invalid (negative) --ls option")

    system, station = checkSystemAndStation(tdb, cmdenv)

    systemName = cmdenv.system
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

    class ItemTrade(object):
        def __init__(self, ID, price, avgAgainst):
            self.ID, self.item = ID, tdb.itemByID[ID]
            self.price = int(price)
            self.avgTrade = avgAgainst[ID]

    # Look up all selling and buying by the station
    selling = [
            ItemTrade(ID, price, avgBuy)
            for ID, price in tdb.query("""
                    SELECT  item_id, price
                      FROM  StationSelling
                     WHERE  station_id = ?
            """, [station.ID])
            if price >= 10 and avgBuy[ID] >= 10
    ]
    selling.sort(
            key=lambda item: item.price - item.avgTrade,
    )
    results.summary.selling = selling[:3]

    buying = [
            ItemTrade(ID, price, avgSell)
            for ID, price in tdb.query("""
                    SELECT  item_id, price
                      FROM  StationBuying
                     WHERE  station_id = ?
            """, [station.ID])
            if price >= 10 and avgSell[ID] >= 10
    ]
    buying.sort(
            key=lambda item: item.avgTrade - item.price,
    )
    results.summary.buying = buying[:3]

    return results

def render(results, cmdenv, tdb):
    system, station = results.summary.system, results.summary.station

    newest, oldest = tdb.query("""
            SELECT JULIANDAY('NOW') - JULIANDAY(MIN(si.modified)),
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

    def makeBest(rows, explanation, alt, starFn):
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
            bestText += "\n    {:<30} @ {:7n}cr (Avg {} {:7n}cr)".format(
                    irow[0].item.name() + irow[1],
                    irow[0].price,
                    alt,
                    irow[0].avgTrade,
            )
        return bestText


    bestBuy = makeBest(
            results.summary.selling, "Buy from this station", "Sell",
            starFn=lambda price, avgCr: \
                price <= (avgCr * 0.9),
    )
    bestSell = makeBest(
            results.summary.buying, "Sell to this station", "Buy",
            starFn=lambda price, avgCr: \
                price >= (avgCr * 1.1),
    )

    siblings = ", ".join(
        stn.dbname
        for stn in system.stations
        if stn is not station
    )
    if not siblings:
        siblings = "[Only known station]"

    ls = station.distFromStar()
    if cmdenv.detail and ls == '?':
        ls = '0 [unknown]'
    bm = TradeDB.marketStates[station.blackMarket]
    if cmdenv.detail and bm == '?':
        bm += ' [unknown]'
    pad = TradeDB.padSizes[station.maxPadSize]
    if cmdenv.detail and pad == '?':
        pad += ' [unknown]'

    print("""Station Data:
System....: {sysname} (#{sysid} @ {sysx},{sysy},{sysz})
Station...: {stnname} (#{stnid})
In System.: {siblings}
Stn/Ls....: {lsdist}
B/Market..: {bm}
Pad Size..: {pad}
Prices....: {icount}
Price Age.: {prage}
Best Buy..: {bestbuy}
Best Sale.: {bestsell}
""".format(
            sysname=system.name(),
            stnname=station.dbname,
            sysid=system.ID,
            sysx=system.posX,
            sysy=system.posY,
            sysz=system.posZ,
            stnid=station.ID,
            lsdist=ls,
            bm=bm,
            pad=pad,
            icount=station.itemCount,
            prage=pricesAge,
            bestbuy=bestBuy,
            bestsell=bestSell,
            siblings=siblings,
            )
)
