from .commandenv import ResultRow
from .exceptions import CommandLineError
from .parsing import (
    PadSizeArgument, ParseArgument, MutuallyExclusiveGroup, NoPlanetSwitch,
    PlanetaryArgument, FleetCarrierArgument, OdysseyArgument,
)
from ..formatting import RowFormat, max_len
from ..tradedb import TradeDB


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
    
    Command execution is broken into two steps:
        1. cmd.run(results, cmdenv, tdb)
            Gather all the data required but generate no output,
        2. cmd.render(results, cmdenv, tdb)
            Print output to the user.
    
    This separation of concerns allows modularity; you can write
    a command that calls another command to fetch data for you
    and knowing it doesn't generate any output. Then you can
    process the data and return it and let the command parser
    decide when to turn it into output.
    
    It also opens a future door to commands that can present
    their data in a GUI as well as the command line by having
    a custom render() function.
    
    Parameters:
        results
            An object to be populated and returned
        cmdenv
            A CommandEnv object populated with the parameters
            for the command.
        tdb
            A TradeDB object to query against.
    
    Returns:
        None
            End execution without any output
        results
            Proceed to "render" with the output.
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
    maxLy = float(cmdenv.maxLyPer or 0.)
    
    if cmdenv.illegal:
        wantIllegality = 'Y'
    elif cmdenv.legal:
        wantIllegality = 'N'
    else:
        wantIllegality = 'YN?'
    
    awaySystems = set()
    if cmdenv.away or cmdenv.awayFrom:
        if not cmdenv.away or not cmdenv.awayFrom:
            raise CommandLineError(
                "Invalid --away/--from usage. See --help"
            )
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
    for rare in tdb.rareItemByID.values():
        if rare.illegal not in wantIllegality:
            continue
        if padSize:       # do we care about pad size?
            if not rare.station.checkPadSize(padSize):
                continue
        if planetary:     # do we care about planetary?
            if not rare.station.checkPlanetary(planetary):
                continue
        if fleet:         # do we care about fleet carrier?
            if not rare.station.checkFleet(fleet):
                continue
        if odyssey:         # do we care about Odyssey?
            if not rare.station.checkOdyssey(odyssey):
                continue
        if noPlanet and rare.station.planetary != 'N':
            continue
        rareSys = rare.station.system
        # Find the un-sqrt'd distance to the system.
        dist = distCheckFn(rareSys)
        if maxLy > 0. and dist > maxLy:
            continue
        
        if awaySystems:
            awayCheck = rareSys.distanceTo
            if any(awayCheck(away) < minAwayDist for away in awaySystems):
                continue
        
        # Create a row for this item
        row = ResultRow()
        row.rare = rare
        row.dist = dist
        results.rows.append(row)
    
    # Was anything matched?
    if not results:
        print("No matches found.")
        return None
    
    if cmdenv.sortByPrice:
        results.rows.sort(key=lambda row: row.dist)
        results.rows.sort(key=lambda row: row.rare.costCr, reverse=True)
    else:
        results.rows.sort(key=lambda row: row.rare.costCr, reverse=True)
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
    If the "run" command returned a result set and we are running
    from the command line, this function will be called to generate
    the output of the command.
    """
    
    if not results.rows:
        raise CommandLineError("No items found.")
    
    # Calculate the longest station and rareitem name in our list.
    longestStnNameLen = max_len(results.rows, key=lambda row: row.rare.station.name())
    longestRareNameLen = max_len(results.rows, key=lambda row: row.rare.name(cmdenv.detail))
    
    # Use the formatting system to describe what our
    # output rows are going to look at (see formatting.py)
    rowFmt = RowFormat()
    rowFmt.addColumn('Station', '<', longestStnNameLen,
            key=lambda row: row.rare.station.name())
    rowFmt.addColumn('Rare', '<', longestRareNameLen,
            key=lambda row: row.rare.name(cmdenv.detail))
    rowFmt.addColumn('Cost', '>', 10, 'n',
            key=lambda row: row.rare.costCr)
    rowFmt.addColumn('DistLy', '>', 6, '.2f',
            key=lambda row: row.dist)
    rowFmt.addColumn('Alloc', '>', 6, 'n',
            key=lambda row: row.rare.maxAlloc)
    rowFmt.addColumn('B/mkt', '>', 4,
            key=lambda row: TradeDB.marketStates[row.rare.illegal])
    rowFmt.addColumn("StnLs", '>', 10,
            key=lambda row: row.rare.station.distFromStar())
    rowFmt.addColumn('B/mkt', '>', 4,
            key=lambda row: TradeDB.marketStates[row.rare.station.blackMarket])
    rowFmt.addColumn("Pad", '>', '3',
            key=lambda row: TradeDB.padSizes[row.rare.station.maxPadSize])
    rowFmt.addColumn("Plt", '>', '3',
            key=lambda row: TradeDB.planetStates[row.rare.station.planetary])
    rowFmt.addColumn("Flc", '>', '3',
            key=lambda row: TradeDB.fleetStates[row.rare.station.fleet])
    rowFmt.addColumn("Ody", '>', '3',
            key=lambda row: TradeDB.odysseyStates[row.rare.station.odyssey])
    
    # Print a heading summary if the user didn't use '-q'
    if not cmdenv.quiet:
        heading, underline = rowFmt.heading()
        print(heading, underline, sep='\n')
    
    # Print out our results.
    for row in results.rows:
        print(rowFmt.format(row))
