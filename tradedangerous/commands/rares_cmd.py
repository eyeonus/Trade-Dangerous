from .commandenv import ResultRow
from .exceptions import CommandLineError
from .parsing import (
    PadSizeArgument, ParseArgument, MutuallyExclusiveGroup, NoPlanetSwitch,
    PlanetaryArgument, FleetCarrierArgument, OdysseyArgument,
)
from ..formatting import RowFormat, max_len
from ..tradedb import TradeDB, select, SA_Category, SA_RareItem, SA_Station

import time


######################################################################
# Parser config

# Displayed on the "trade.py --help" command list, etc.
help='Find rares near your current local.'
# Should match the name of the module minus the _cmd.py
name='rares'
# Displayed at the end of the "trade.py rares --help"
epilog=None
# Set to False in commands that need to operate without
# a trade database.
wantsTradeDB=True
# Required parameters
arguments = [
    ParseArgument(
            'near',
            help='Your current system.',
            type=str,
            metavar='SYSTEMNAME',
    ),
]
# Optional parameters
switches = [
    ParseArgument('--ly',
            help='Maximum distance to search.',
            metavar='LY',
            type=float,
            default=180,
            dest='maxLyPer',
    ),
    ParseArgument('--limit',
            help='Maximum number of results to list.',
            default=None,
            type=int,
    ),
    PadSizeArgument(),
    MutuallyExclusiveGroup(
        NoPlanetSwitch(),
        PlanetaryArgument(),
    ),
    FleetCarrierArgument(),
    OdysseyArgument(),
    ParseArgument('--price-sort', '-P',
            help='Sort by price not distance.',
            action='store_true',
            default=False,
            dest='sortByPrice',
    ),
    ParseArgument('--reverse', '-r',
            help='Reverse the list.',
            action='store_true',
            default=False,
    ),
    ParseArgument('--away',
            help='Require "--from" systems to be at least this far from primary system',
            metavar='LY',
            default=0,
            type=float,
    ),
    MutuallyExclusiveGroup(
        ParseArgument('--legal',
            help='List only items known to be legal.',
            action='store_true',
        ),
        ParseArgument('--illegal',
            help='List only items known to be illegal.',
            action='store_true',
        )
    ),
    ParseArgument('--from',
            help='Additional systems to range check candidates against, requires --away.',
            metavar='SYSTEMNAME',
            action='append',
            dest='awayFrom',
    ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    """
    Fetch all the data needed to display the results of a "rares"
    command. Does not actually print anything.
    """
    # Lookup the system we're currently in.
    start = cmdenv.nearSystem
    # Hoist the padSize, noPlanet and planetary parameter for convenience
    padSize = cmdenv.padSize
    noPlanet = cmdenv.noPlanet
    planetary = cmdenv.planetary
    fleet = cmdenv.fleet
    odyssey = cmdenv.odyssey
    # How far we're want to cast our net.
    maxLy = float(cmdenv.maxLyPer or 0.0)
    
    awaySystems = set()
    if cmdenv.away or cmdenv.awayFrom:
        if not cmdenv.away or not cmdenv.awayFrom:
            raise CommandLineError("Invalid --away/--from usage. See --help")
        minAwayDist = cmdenv.away
        for sysName in cmdenv.awayFrom:
            system = tdb.lookupPlace(sysName).system
            awaySystems.add(system)
    
    # Start to build up the results data.
    results.summary = ResultRow()
    results.summary.near = start
    results.summary.ly = maxLy
    results.summary.awaySystems = awaySystems
    
    distCheckFn = start.distanceTo
    
    # Look through the rares list.
    stmt = select(
        SA_RareItem.rare_id,
        SA_RareItem.station_id,
        SA_RareItem.name,
        SA_RareItem.cost,
        SA_RareItem.max_allocation,
        SA_RareItem.illegal,
        SA_RareItem.suppressed,
        SA_Category.name
    ).join(SA_Category)
    if cmdenv.illegal or cmdenv.legal:
       stmt = stmt.where(SA_RareItem.illegal == ('Y' if cmdenv.legal else 'N'))
    if noPlanet:
        stmt = stmt.join(SA_Station).where(SA_Station.planetary != 'Y')
    
    awaySystems = set()

    started = time.time()
    with tdb.Session() as session:
        rows = session.execute(stmt).all()

    for rare in rows:
        stn = tdb.stationByID[rare.station_id]
        if padSize and not stn.checkPadSize(padSize):
            continue
        if planetary and not stn.checkPlanetary(planetary):
            continue
        if fleet and not stn.checkFleet(fleet):
            continue
        if odyssey and not stn.checkOdyssey(odyssey):
            continue
        
        rareSys = stn.system
        dist = distCheckFn(rareSys)
        if maxLy > 0.0 and dist > maxLy:
            continue
        
        if awaySystems:
            awayCheck = rareSys.distanceTo
            if any(awayCheck(away) < minAwayDist for away in awaySystems):
                continue
        
        row = ResultRow()
        row.rare = rare
        row.station = stn            # <-- IMPORTANT: used by render()
        row.dist = dist
        results.rows.append(row)
        
    cmdenv.DEBUG0("Found {:n} rares in {:.3f}s", len(results.rows), time.time() - started)
    
    # Was anything matched?
    if not results.rows:
        print("No matches found.")
        return None
    
    # Sort safely even if rare.costCr is None (treat None as 0)
    price_key = lambda row: (row.rare.cost or 0)
    
    if cmdenv.sortByPrice:
        results.rows.sort(key=lambda row: row.dist)
        results.rows.sort(key=price_key, reverse=True)
    else:
        results.rows.sort(key=price_key, reverse=True)
        results.rows.sort(key=lambda row: row.dist)
    
    if cmdenv.reverse:
        results.rows.reverse()
    
    limit = cmdenv.limit or 0
    if limit > 0:
        results.rows = results.rows[:limit]
    
    return results




#######################################################################
## Transform result set into output

def render(results, cmdenv, tdb):
    """
    Render output for 'rares' with robust None-handling.
    Keeps existing column order/labels.
    """
    from ..formatting import RowFormat, max_len
    
    rows = results.rows
    if not rows:
        return
    
    # Helpers to coalesce possibly-missing attributes
    def _cost(row):
        try:
            v = row.rare.cost
            return int(v) if v is not None else 0
        except Exception:
            return 0
    
    def _rare_name(row):
        try:
            n = row.rare.name
            return n or "?"
        except Exception:
            return "?"
    
    def _alloc(row):
        val = row.rare.max_allocation
        return str(val) if val not in (None, "") else "?"
    
    def _rare_illegal(row):
        val = row.rare.illegal
        return val if val in ("Y", "N", "?") else "?"
    
    def _stn_ls(row):
        try:
            v = row.station.distFromStar()
            return v if v is not None else "?"
        except Exception:
            return "?"
    
    def _dist(row):
        try:
            return float(getattr(row, "dist", 0.0) or 0.0)
        except Exception:
            return 0.0
    
    def _stn_bm(row):
        key = getattr(row.station, "blackMarket", "?")
        return TradeDB.marketStates.get(key, key or "?")
    
    def _pad(row):
        key = getattr(row.station, "maxPadSize", "?")
        return TradeDB.padSizes.get(key, key or "?")
    
    def _plt(row):
        key = getattr(row.station, "planetary", "?")
        return TradeDB.planetStates.get(key, key or "?")
    
    def _flc(row):
        key = getattr(row.station, "fleet", "?")
        return TradeDB.fleetStates.get(key, key or "?")
    
    def _ody(row):
        key = getattr(row.station, "odyssey", "?")
        return TradeDB.odysseyStates.get(key, key or "?")
    
    # Column widths based on safe key functions
    max_stn = max_len(rows, key=lambda r: r.station.name())
    max_rare = max_len(rows, key=lambda r: _rare_name(r))
    
    rowFmt = RowFormat()
    rowFmt.addColumn('Station', '<', max_stn, key=lambda r: r.station.name())
    rowFmt.addColumn('Rare', '<', max_rare, key=lambda r: _rare_name(r))
    rowFmt.addColumn('Cost', '>', 10, 'n', key=lambda r: _cost(r))
    rowFmt.addColumn('DistLy', '>', 6, '.2f', key=lambda r: _dist(r))
    rowFmt.addColumn('Alloc', '>', 5, key=lambda r: _alloc(r))
    # First B/mkt: rare legality flag (Y/N/?)
    rowFmt.addColumn('B/mkt', '>', 4, key=lambda r: _rare_illegal(r))
    rowFmt.addColumn('StnLs', '>', 10, key=lambda r: _stn_ls(r))
    # Second B/mkt: station black market availability via mapping
    rowFmt.addColumn('B/mkt', '>', 4, key=lambda r: _stn_bm(r))
    rowFmt.addColumn('Pad', '>', 3, key=lambda r: _pad(r))
    rowFmt.addColumn('Plt', '>', 3, key=lambda r: _plt(r))
    rowFmt.addColumn('Flc', '>', 3, key=lambda r: _flc(r))
    rowFmt.addColumn('Ody', '>', 3, key=lambda r: _ody(r))
    
    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')
    
    for row in rows:
        print(rowFmt.format(row))
