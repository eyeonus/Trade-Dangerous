
----------
TradeDangerous
Copyright (C) Oliver "kfsone" Smith, July 2014
REQUIRES PYTHON 3.4 OR HIGHER.

----------

[For recent changes see CHANGES.txt]

#What is Trade Dangerous?

TradeDangerous is set of powerful trading tools for Elite Dangerous, organized around one of the most powerful trade run optimizers (TRO) available.

The TRO is a heavy hitter that can calculate complex routes with multiple-stops while taking into account the profits you make along the route.

The price data in TradeDangerous is either manually entered (by you) or crowd sourced (e.g. [http://www.davek.com.au/td](http://www.davek.com.au/td)).


#What can it do for me?

I'm at Mokosh/Bethe Station with 5000cr, room for 8 cargo units and a ship that can go 8.56ly per jump.

We ask:


    trade.py run --from Mokosh/Bethe --credits 5000 --capacity 8 --ly-per 8.56
or in abbreviated form:

    trade.py run --fr Mok/Beth --cr 5000 --cap 8 --ly 8.56

And TD will give us a 2-leg trade run that may more than double our money:

    1:  MOKOSH/Bethe Station -> GRANTHAIMI/Parmitano Colony:
    2:  MOKOSH/Bethe Station: 8 x Mineral Extractors,
    3:  V774 HERCULIS/Mendel Mines: 4 x Gallite, 4 x Rutile,
    4:  GRANTHAIMI/Parmitano Colony +6,340cr

Line 1 tells us the start and end stations for this route.

Line 2 tells us what to pick up at our first station.

Line 3 tells us the first hop of our run. When we get here, we sell all the
cargo we are carrying and pick up a new load.

Line 4 tells us the last hop of our run and how much we gain when we sell our
remaining cargo here.


**but how do I get there?**

There's a command for that

    trade.py nav mok/beth herc/mendel --ly 8.56
    System         JumpLy
    ---------------------
    MOKOSH           0.00
    LTT 15449        6.23
    V774 HERCULIS    4.90

But we could also just ask TD to give us more detail with our trade run ("-v"):

    trade.py run -v --fr Mok/Beth --cr 5000 --cap 8 --ly 8.56
    1: MOKOSH/Bethe Station -> GRANTHAIMI/Parmitano Colony:
    2:  Load from MOKOSH/Bethe Station: 8 x Mineral Extractors (@491cr),
    3:  Jump MOKOSH -> LTT 15449 -> V774 HERCULIS
    4:  Load from V774 HERCULIS/Mendel Mines: 4 x Gallite (@1663cr), 4 x Rutile (@223cr),
    5:  Jump V774 HERCULIS -> LTT 15449 -> GRANTHAIMI
    6:  Finish GRANTHAIMI/Parmitano Colony + 6,340cr => 11,340cr

Lines 2 and 4 now include the expected buying prices so you don't get shafted
by out of date price data.

Lines 3 and 5 tell us our jump routes between legs.

(For even more detail "-v -v" or "-vv" or "-vvv")

At this point, you probably have a lot of questions.


#TradeDangerous: Setup
At the moment, the primary interface to TradeDangerous' goodness is through a command line tool, "trade.py". I've built TD in a modular, open source way so that other programmers can use it to power their own tools; hopefully
tools with web or graphical interfaces.

For instructions on how to get setup with TD see the wiki at: [http://bitbucket.org/kfsone/tradedangerous/wiki/](http://bitbucket.org/kfsone/tradedangerous/wiki/) and click the "Setup Guide" link.


#Command Line Options
TD functionality is broken up into "sub-commands". For instance, when we refer to the `update` command, we mean `trade.py update …`.

If you run `trade.py` without any commands or options, it will give you a list of the sub-commands available. You can find out more details about a specific command, such as 'local', by typing:

    trade.py local --help

Each command has a number of optional/required arguments that can be specified.

Optional arguments are denoted by a keyword that starts with one or two dashes (`--from`, `-S`). The difference between long and short versions? Readability. You can also 'stack' short versions, for example `update -F -G -A` can be written as `update -FGA`

There are "switches" which turn a feature on or off, such as `--detail` which makes the command more verbose or --quiet` which makes it less noisy.

Other options are "parameters" which take a value, for example `--from Sol` would state the starting location for a command. You can write these as `--param value` or `--param=value`. You can often get away with just the first couple of letters, e.g. `--cr` for `--credits`.

In the list below, you'll see `--detail` and `-v` listed together. This indicates that `-v` is the short-form for `--detail`.

##Basic Usage:

    trade.py command arguments


###Common Options:
  These can be used with ALL TD commands

     --detail
     -v
       Increases the amount of detail given when showing routes or running the
       checklist system. Each use increases the detail, i.e. "-v -v" will
       give you more detail than just "-v". Short version stacks, e.g.
       "-v -v -v" is the same as "-vvv"

     --quiet
     -q
       Reduces the verbosity of the program. For example,
         trade.py -qq cleanup
       Will run the command with no output unless an error occurs.
       NOTE: --detail and --quiet are mutually exclusive.

     --debug
     -w
       Gives some additional information on what TD is doing while running,
       each use increases the verbosity: i.e. --debug --debug is more verbose.
       Short version is stackable, e.g. "-w -w -w" or "-www"


###Sub Commands:

For additional help on a specific command, such as 'update' use

    trade.py run …
    Calculates a trade run

    trade.py update …
    Provides a way to enter/update price data for a station

    trade.py nav …
    Calculates a route between two systems

    trade.py import …
    Reads prices from a file and loads them into the cache

    trade.py buy …
    Finds places to buy a given item/ship

    trade.py sell …
    Finds places to sell a given item

    trade.py local …
    Lists systems (and optionally, stations) in the vicinity of a given system

    trade.py rares …
    Helps to find rare items.

    trade.py olddata …
    Lists old data

###Advanced Commands:

    trade.py buildcache
    Rebuilds the cache (data/TradeDangerous.db)

    trade.py export …
    Exports data from the db to .csv files

    trade.py station …
    Query, add, update or remove stations

##RUN sub-command:

  This command provides the primary trade run calculator functionality (it provides   the functionality of the older TradeDangerous versions prior to 3.1)

###Ship/Trade options:
     --capacity N
     --cap N
       Maximum items you can carry on each hop.

     --credits N
     --cr N
       How many credits to start with, where N can be an exact number or
       can use a suffix such as 20k for 20,000, 2.5m for 2.5 million or
       1.25b for 1.25 billion
       e.g.
         --credits 20000
         --credits 20k
         --credits 15.2m

     --ly-per N.NN
     --ly N.NN
       Maximum distance your ship can jump between systems at full capacity.
       NOTE: You can increase your range by selling your weapons.
       e.g.
         --ly-per 19.1
         --ly-per 3

     --empty-ly N.NN
     --emp N.NN
       DEFAULT: same as --ly-per
       How far your ship can jump when empty (used by --start-jumps)

     --limit N   DEFAULT: 0
       If set, limits the maximum number of units of any cargo
       item you will buy on any trade hop, in case you want to
       hedge your bets or be a good economy citizen.
       e.g.
         --capacity 16 --limit 8

     --insurance N   DEFAULT: 0
     --ins N
       How many credits to hold back for insurance purposes
       e.g.
         --insurance 1000
         --ins 5000
         --ins 1.2m

     --margin N.NN   DEFAULT: 0.01
       At the end of each hop, reduce the profit by this much (0.02 = 2%),
       to allow a margin of error in the accuracy of prices.
       e.g.
         --margin 0      (no margin)
         --margin 0.01   (1% margin)

###Route options:
     --from <station or system>
       Lets you specify the starting station
       e.g.
         --from @Asellus/Beagle2
         --fr beagle2
         --fr asellusprim

     --to <station or system>
       Lets you specify the final destination. If you specify a station, it
       will finish at that exact station. If you specify a system, it will
       try all the stations in the target system.
       e.g.
         --to Beagle2
         --to lhs64

	 --shorten" (requires --to)
       Will show routes with fewer hops than the maximum if they produce a better gpt
	   e.g.
	     --to Beagle2 --hops 4 --shorten
				
     --towards <goal system>
       Builds a route that tries to shorten the distance from your origin
       and goal. Destinations that would increase the distance are ignored.
       Tries to avoid routes that go backwards or detour. If you want to
       avoid multiple visits in the same system, use --unique.
       e.g.
         --from iBootis --to LiuBese

     --loop
       Look for routes which loop back on themselves within the given number
       of hops, but it may also find shorter routes.
       e.g.
         --from iBootis --loop
         --loop --hops 4   (looks for 2, 3 and 4 hop loops)
		 
	 --loop-int N
	 -li N
       Will require a minimum of N hops before visiting the same station.
	   e.g.
	     --from iBootis --loop-int 3
				
     --via <station or system>
       Lets you specify a station that must be between the second and final hop.
       Requires that hops be at least 2.
       e.g.
         --via Enterprise
         --via Chango

     --hops N
       DEFAULT: 2
       Maximum number of hops (number of cargo pickups)
       e.g.
         --hops 8

     --jumps-per N
     --jum N
       DEFAULT: 2
       Limit the number of systems jumped to between each station
       e.g.
         -jumps-per 5

     --direct
       Assumes a single hop and doesn't worry about travel between
       source and destination.
       e.g.
         --from achenar --to lave --direct

     --start-jumps N
     -s N
       Considers stations from systems upto this many jumps from your
       specified start location.
         --from beagle2 --ly-per 7.56 --empty 10.56 -s 2

     --end-jumps N
     -e N
       Considers stations from systems upto this many jumps from your
       specified destination (--to).
         --to lave -e 3      (find runs that end within 3 jumps of lave)
     
###Filter options:
     --max-days-old N.NN
     -MD N.NN
       Filters out price data that exceeds a specified age in days
       e.g.
         --max-days-old 7     (data less than a week old)
         -MD=2                (data less than 2 days old)

     --gain-per-ton credits
     --gpt credits
       Only consider trades which generate at least this much profit
       per ton of cargo traded. Be aware that this can prevent TD from
       finding highly profitable routes that would require you to take
       a drop in profit to reach, so you may want to consider using this
       in conjunction with --start-jumps or --end-jumps.
       e.g.
         --gpt 1200
         --gpt 1.5k

     --max-gain-per-ton credits
     --mgpt credits
       DEFAULT: 10,000
       Sets an upper threshold on the maximum profit/ton that TD will
       believe. This is a way to avoid bad data.
       e.g.
         --mgpt 2000
         --mgpt 2k

     --supply N
       Only consider sales where the station has this many units in stock,
       e.g.
         --supply 1000

     --pad-size SML?
     --pad SML?
     -p
       Limit results to stations that match one of the pad sizes
       specified.
         --pad ML?            (medium, large, or unknown only)
         -p ML?               (medium, large, or unknown only)
         --pad ?              (unknown only)
         --pad L              (large only, ignores unknown)

     --black-market
     --bm
       Only consider stations that have a black market.

     --ls-penalty N.NN
     --lsp N.NN
       DEFAULT: 0.5
       Reduces the score of routes by this percentage for every 1000ls
       you have to travel to stations, which helps prioritize routes
       with a shorter supercruise time.
       e.g.
         --ls-penalty 2.5
         --lsp=0              (disables this feature)

     --ls-max N
       DEFAULT: 0
       Filter stations by their distance-to-star. Stations for which
       distance-to-star is known that have a distance above this will
       not be considered for trading.
       e.g.
         --ls-max 10000
         --ls-m 32000

     --prune-score N.NN
       DEFAULT: 0
       After a number of hops (controlled by --prune-hops), eliminate
       a percentage of the routes from the lowest up by score.
       NOTE: This can speed up long run calculations, but it can also
       cause you to miss gold-mines that are a just a few hops away…
       e.g.
         --prune-score 12.5   Removes the bottom 1/8th of (12.5%) of routes
         --prune-score 50     Only keep the upper 50% of routes

     --prune-hops N
       DEFAULT: 3
       Being applying "--prune-score" from this hop onward. Set 0 to disable.
       NOTE: This can speed up long run calculations, but it can also
       cause you to miss gold-mines that are a just a few hops away…
       e.g.
         --prune-hop 4 --prune-score 22.5

     --avoid ITEM/SYSTEM/STATION
     --avoid AVOID,AVOID,…,AVOID
     --av ITEM/SYSTEM/STATION
     --av AVOID,AVOID,…,AVOID
       Excludes the item/system/station matching the name from the database
       e.g.
         --avoid Gold
         --avoid Aulin
         --avoid Enterprise
         --avoid prise
         --av gold,aulin,enterprise,anderson

     --unique
     --uni
       Only show routes which do not visit any station twice

###Other options:
     --summary
       Uses a slightly different format for showing trade routes,
       especially useful for longer routes in conjunction with -vvv

     --routes N   DEFAULT: 1
       Shows the top N routes;

     --checklist
     --check
       Walks you through the purchases, sales and jumps of your route.
       Note: More verbose when used with --detail

     --x52-pro
     --x52
       OMFG Output the current step of the checklist on your X52 Pro MFD.
       Is that some sweetness or what?

##TRADE sub-command:

Lists trades between two stations. Specify `-v`, `-vv`, or `-vvv` for more data.

    trade.py trade [-v | -vv | -vvv] <from station> <to station>

  e.g.

    trade.py trade "sol/daedalus" "groom/frank"
    Item                  Profit       Cost
    ---------------------------------------
    Superconductors        1,331      6,162
    Indium                 1,202      5,394
    Beryllium              1,021      8,051
    Gold                   1,004      9,276
    Silver                   838      4,631
    …

    trade.py trade "sol/daedalus" "groom/frank" -v
    Item                  Profit       Cost      Stock     Demand   SrcAge   DstAge
    -------------------------------------------------------------------------------
    Superconductors        1,331      6,162  1,229,497    621,964     1.17     2.37
    Indium                 1,202      5,394  1,397,354    683,398     1.17     2.37
    Beryllium              1,021      8,051     68,181    529,673     1.17     2.37
    …

    trade.py trade "sol/daedalus" "groom/frank" -v -vv
    Item                  Profit       Cost    AvgCost     Buying     AvgBuy      Stock     Demand   SrcAge   DstAge
    ----------------------------------------------------------------------------------------------------------------
    Superconductors        1,331      6,162       6461       7493       6813  1,229,497    621,964     1.17     2.37
    Indium                 1,202      5,394       5640       6596       5961  1,397,354    683,398     1.17     2.37
    Beryllium              1,021      8,051       7998       9072       8404     68,181    529,673     1.17     2.37
    Gold                   1,004      9,276       9212      10280       9600     82,951    938,765     1.17     2.37


##UPDATE sub-command:

For maintenance of your local prices database. The default is to walk you through a list of all the prices known for the station. You can either   hit enter or type the correction.

Alternatively, if you specify one of the editing switches, it will put the prices for a given station into a text file and let you edit it with your favorite editor.

    trade.py update

Options:

    --gui
    -G
      Enables the new built-in GUI.

    --front
    -F
      [With --gui/-G]
      If ED is running in windowed mode, keeps the TD gui infront of
      of the ED window.

    --window-x nnn, --window-y nnn
    -wx nnn, -wy nnn
      [With --gui/-G]
      Lets you position the update window. Use negative values to
      anchor to the right/bottom of the screen.
      e.g.
        trade.py update -GF -wx=-220 -wy=200

    --height nnn
    -H nnn
      [With --gui/-G]
      Specifies the default heigh tof the update window.

    --all
    -A
      Shows all items including those not currently available at the station.

    --editor <executable name or path>
      e.g. --editor "C:\Program Files\WibbleEdit\WibbleEdit.exe"
      Saves the prices in a human-readable format and loads that into
      an editor. Make changes and save to update the database.

    --timestamps
    -T
      [With text editor only]
      Exposes the "timestamp" column.

    --force-na
    -0
      Changes the default demand/stock to be "n/a".
      CAUTION: "n/a" indicates that the item is either not bought
      or not sold at this station, and TD will ignore it accordingly.

    --sublime
    --subl
      Like "--editor" but finds and uses the Sublime Text editor (2 and 3).
      You can use "--editor" to tell it exactly where the editor
      is located if it fails to find it.

    --notepad
    --note
      Like "--editor" but uses notepad as the editor.

    --npp
      Like "--editor" but tries to use Notepad++ as the editor.
      NOTE: You will have to exit notepad++ completely before trade
      is able to process the changes you have made.

    --vim
      Like "--editor" but tries to use the VI iMproved editor.
      Mostly applies to Linux, Mac and Cygwin/Git installs.

  Examples:

    trade.py update "aulin enterprise" --notepad
    trade.py update chango --subl --supply
    trade.py update anderson --editor "C:\Program Files\Microsoft Office\WordPad.exe"
    trade.py update wcm --timestamps
    trade.py update --sup --time --zero aulin

  aka:

    trade.py update --sub -T0 aulin


##IMPORT sub-command:

Provides a way to import prices data from a file or a web site. You can use this to import data for a few stations or an entire .prices file from a friend. For instance, if you updated a station and there was an error importing it, the data is usually saved as "prices.last". You can open this file and correct the error and then import it, rather than having to re-enter all of the data.

**NOTE:** Items not listed for a station in an import are considered unavailable at that station. If you have an entry for Beagle2/Food and you import a file that does not include Beagle2/Food, Beagle2/Food will be removed from your db.

  
    trade.py import [-q | -v] [filename | url | --maddavo] [--ignore-unknown]

Options:

    filename
      Specifies the name of the file to load
      e.g.
        import.prices

    url
      Specifies web address to retrieve the data from
      e.g.
        http://kfs.org/td/prices

    --maddavo
      Like 'url' but specifies the URL for maddavo's .prices file

      This has also additional options:
      --option=<option> where option is one of the following:
        systems:      Merge maddavo's System data into local db,
        stations:     Merge maddavo's Station data into local db,
        shipvendors:  Merge maddavo's ShipVendor data into local db,
        csvs:         Merge all of the above
        exportcsv:    Regenerate System and Station .csv files after
                      merging System/Station data.
        csvonly:      Stop after importing CSV files, no prices,
        skipdl:       Skip doing any downloads.
        force:        Process prices even if timestamps suggest
                      there is no new data.
        use3h:        Force download of the 3-hours .prices file
        use2d:        Force download of the 2-days .prices file
        usefull:      Force download of the full .prices file

     Options can be comma separated, the following are equivalent:
       --option systems --option stations --option shipvendors --option csvonly
       --opt=csvs --opt=csvonly
       -O csvs,csvonly

    --ignore-unknown
    -i
      Any systems, stations, categories or items that aren't recognized
      by this version of TD will be reported but import will continue.

      Unrecognized stations in the ".prices" file, or an import, will
      have a placeholder station entry automatically created for them.

      Note: When the cache is rebuilt, these stations will be lost, so
      you may need to add the "-i" flag to the buildcache command.

Provides mechanisms for loading data, epsecially price data, into the local database, using either "import" or "merge" modes.

Both modes operate on a station-by-station basis: you can import data for a single station or every station.

For instance, if you "updated"d a station and there was an error importing it, your data is saved as "prices.last". Edit this file, correct the errors and then "import" it, rather than having to re-enter all of the data.

###Import Mode (default):
- Overwrites local data even if the import data is older,
- Items are removed from stations when there is an explicit "0 0" entry or there is no entry for the item at the station in the import file.

###Merge Mode (--merge):
- Items are only imported if they are newer than the local data,
- Items are removed from stations only when there is an explicit "0 0" entry that is newer than the local data.

###Plugins:

TD also supports the concept of an "import plugin". These are user-contributed extensions to TD that will fetch data from a 3rd party, such as Maddavo's Market Share, and populate the local database with that information.  (see http://www.davek.com.au/td/)

Plugins are specified with the "-P" option and can have their own options, not listed here, with the "-O" option. See "-O=help" for a list of the options provided by a particular plugin.

    trade.py import [-q | -v] [filename | url | -P <plugin> -O <options>] [--ignore-unknown]

Options:

    filename
      Specifies the name of the file to load
      e.g.
        import.prices

    url
      Specifies web address to retrieve the data from
      e.g.
        http://kfs.org/td/prices

    ".prices" import mode options:
      --ignore-unknown
      -i
        Any systems, stations, categories or items that aren't recognized
        by this version of TD will be reported but import will continue.

        Unrecognized stations in the ".prices" file, or an import, will
        have a placeholder station entry automatically created for them.

        Note: When the cache is rebuilt, these stations will be lost, so
        you may need to add the "-i" flag to the buildcache command.

      --merge-import
      --merge
      -M
        Existing data is only overwritten by entries from the .prices file
        that have a newer timestamp and data is only removed if there is
        an explicit entry in the file with 0 demand/supply prices.

      --reset-all
        CAUTION: DANGER ELITE ROBINSON
        Deletes all existing prices from the database.

    --plug <plugin>
    -P <plugin>
      Specifies a plugin to use instead of the default .prices importer,
      By default "TD" comes with a plugin that supports Maddavo's Market Share
      (http://www.davek.com.au/td/)
      e.g.
        -P maddavo

    --option <option>
    --option <option1>,<option2>,...<optionN>
    -O <option>,...
      Passes options to a plugin.
      e.g.
        -O left,right
        -O help

##MADDAVO's "import" plugin:

Maddavo's Market Share is a 3rd party Elite Dangerous crowd sourcing project that gathers system, station, item and other data. This is the recommended way for TradeDangerous users to get their data.

The "maddavo" plugin provides a simple way to fetch and import updates from Maddavo's site.

To take maximum advantage of Maddavo's services, you should consider using "-O csvs" periodically.

###Basic usage:

    trade.py import -P maddavo
      This will check for and import new data from Maddavo's site. If
      you have newer data of your own, it will not be overwritten.

    trade.py import -P maddavo -O csvs
      Starts by checking for new Systems, Stations, ShipVendors, etc,
      listed in the ".csv" files Maddavo makes available.
      Then imports prices.

###Options (-O):
    csvs:         Merges all supported .CSVs (Systems, Stations,
                  ShipVendors, RareItems) and implies "exportcsv".
    systems:      Merge maddavo's System data into local db,
    stations:     Merge maddavo's Station data into local db,
    shipvendors:  Merge maddavo's ShipVendor data into local db,
    exportcsv:    Regenerate System and Station .csv files after
                  merging System/Station data.
    csvonly:      Stop after importing CSV files, no prices,
    skipdl:       Skip doing any downloads.
    force:        Process prices even if timestamps suggest
                  there is no new data.
    use3h:        Force download of the 3-hours .prices file
    use2d:        Force download of the 2-days .prices file
    usefull:      Force download of the full .prices file


##MARKET sub-command:

Lists items bought / sold at a given station; with --detail (-v) also includes the average price for those items.


    trade.py market <station> [--buy | --sell] [--detail]

Options:

    station
      Name of the station to list, e.g. "paes/ramon" or "ramoncity",

    --buy
    -B
      List only items bought by the station (listed as 'SELL' in-game)

    --sell
    -S
      List only items sold by the station (listed as 'BUY' in-game)

    --detail
    -v
      Once: includes average prices
      Twice: include demand column and category headings

    trade.py market --buy ramoncity
    Item                    Buying
    ------------------------------
    Hydrogen Fuel               90
    Clothing                   221
    Domestic Appliances        417
    Food Cartridges             35
    …

    trade.py market --buy --sell ramoncity -v
        Item                    Buying     Avg Age/Days Selling     Avg   Supply Age/Days
    -------------------------------------------------------------------------------------
    +CHEMICALS
        Hydrogen Fuel               90     100     0.01      94     102  74,034H     0.01
    +CONSUMER ITEMS
        Clothing                   221     361     0.01     237     238   1,706M     0.01
        Domestic Appliances        417     582     0.01     437     436   1,022M     0.01
    +FOODS
        Food Cartridges             35     125     0.01      45      50  32,019H     0.01

    …

##NAV sub-command:

Provides details of routes without worrying about trade. By default, if given a ship, it uses the maximum dry range of the ship. Use `--full` if you want to restrict to routes with a full cargo hold.

    trade.py nav [-q | -v] [--ly-per] from to [--avoid] [--stations]

Options:

    --ly-per N.NN
      Constrains jumps to a maximum ly distance
      --ly-per 3.2

    --avoid place
      Produces a route that does not fly through place. If place is a
      station, the system it is in will be avoided.

    --stations
      Lists stations at each stop

    --refuel-jumps N
    --ref N
      Specify the maximum consecutive systems which do not have stations
      you can pass through. For example "--ref 1" would require every
      jump on the route have a station. "--ref 2" would require that
      you not make more than one stationless jump after another.

    from
      Name of the starting system or a station in the system,

    to
      Name of the destination system or a station in the system,

  Examples:

    trade.py nav mok/be v7/me --ly 8.56
    System         JumpLy
    ---------------------
    MOKOSH           0.00
    LTT 15449        6.23
    V774 HERCULIS    4.90

    > trade.py nav mok/be v7/me --ly 8.56 -vv --stations
    Action System         JumpLy Stations  DistLy   DirLy
      /  Station                               StnLs Age/days BMkt Pad Itms
    -----------------------------------------------------------------------
    Depart MOKOSH           0.00        2    0.00   10.73
      /  Bethe Station                         2,500        -    ?   ?   67
      /  Lubin Orbital                             ?        -    ?   ?   67
    Via    LTT 15449        6.23        9    6.23    4.90
      /  Barry Terminal                           21        -    ?   ?   54
      /  Binet Port                               14        -   No   ?   54
      /  Bose Station                             53        -    ?   ?   53
      …
    Arrive V774 HERCULIS    4.90        2   11.13    0.00
      /  Lazutkin Colony                         704        -    ?   ?    0
      /  Mendel Mines                            473        -    ?   ?   61

    ('DirLy' is the direct distance left to the destination)


##LOCAL sub-command:

Provides details of local stations without worrying about trade. By default, if given a ship, it uses the maximum dry range of the ship. Use `--full` if you want to restrict to systems with a full cargo hold.

    trade.py local [-q | -v] [--ly N.NN] system

Options:

    --ly N.NN
      Constrains local systems to a maximum ly distance
      --ly 20.0

    --pad-size SML?
    --pad SML?
    -p
      Limit stations to those that match one of the pad sizes specified.
        --pad ML?            (medium, large, or unknown only)
        -p ML?               (medium, large, or unknown only)
        --pad ?              (unknown only)
        --pad L              (large only, ignores unknown)

    --stations
      Limit results to systems which have stations

    --trading
      Limit stations to those which which have markets or trade data.

    --shipyard
      Limit stations to those known to have a shipyard.

    --black-market
    --bm
      Limit stations to those known to have a black market.

    --outfitting
      Limit stations to those known to have outfitting.

    --rearm
      Limit stations to those known to rearm.

    --refuel
      Limit stations to those known to refuel.

    --repair
      Limit stations to those known to repair.

    -v
      Show stations + their distance from star

    -vv (or -v -v or --detail --detail)
      Include count of items at station

    system
      Name of the system or a station in the system,

  Examples:

    trade.py local mokosh --ly 6
    System        Dist
    ------------------
    MOKOSH        0.00
    GRANTHAIMI    2.24
    LHS 3333      5.54

    > trade.py local mokosh --ly 6 -v
    System              Dist
      /  Station                                Dist Age/days BMkt Pad
    ------------------------------------------------------------------
    MOKOSH              0.00
      /  Bethe Station                        2500ls     8.27    N   M
      /  Lubin Orbital                             ?     0.85    Y   L
    GRANTHAIMI          2.24
      /  Parmitano Colony                          ?     5.88    ?   ?
    LHS 3333            5.54

Mokosh/Bethe Station is 2500ls from its star, the data is 8 days old, there is no black market, and the largest pad size is Medium. 

Lubin Orbital's distance is not known, the data is less than a day old, it has a black market, and it has Large pads.

Parmitano Colony distance unknown, data nearly 6 days old, the black market status is unknown as is the pad size.

Adding detail ('-vv' or '-v -v' or '--detail --detail') would add a count of the number of items we have prices for at each station.

    trade.py local LAVE --trading --ly 4 -vv
    System    Dist
      /  Station            StnLs Age/days Mkt BMk Shp Pad Itms
    -----------------------------------------------------------
    LAVE      0.00
      /  Castellan Station  2.34K     2.57 Yes  No  No Med   37
      /  Lave Station         299     7.79 Yes Yes Yes Lrg   33
      /  Warinus              863     7.76 Yes Yes  No Med   38
    DISO      3.59
      /  Shifnalport          284     0.57 Yes Yes Yes Lrg   34
    LEESTI    3.91
      /  George Lucas         255     0.58 Yes Yes Yes Lrg   52
      /  Kolmogorov Hub     2.96K     1.61 Yes Yes  No Med   53

##STATION sub-command:

This command can be used to add a new station:

    trade.py station --add "i bootis/nowhere port"
    trade.py station -a "i bootis/nowhere port" --ls 123 --pad m

Or it can be used to delete a station:

    trade.py station --remove "i bootis/nowhere port"
    trade.py station -rm "i bootis/nowhere port"

Or it can be used to update the ls-from-star, pad-size, or blackmarket flags of an existing station:

    trade.py station --update "i bootis/nowhere port" --pad=L --ls-from-star=123 --black-market=N
    trade.py station -u "i bootis/nowhere port" --pad L --ls 123 --bm=N

It can also be used to show some basic data about a given station:

    trade.py station -v i bootis/chango
    Station Data:
    System….: I BOOTIS (#10438 @ -22.375,34.84375,4.0)
    Station…: Chango Dock (#1288)
    Also here.: Maher Stellar Research
    Stn/Ls….: 1,095
    B/Market..: Yes
    Pad Size..: Lrg
    Prices….: 33
    Price Age.: 6.77 days
    Best Buy..: (Buy from this station)
        Tea*                           @   1,217cr (Avg Sell   1,570cr)
        Coffee*                        @   1,047cr (Avg Sell   1,369cr)
        Fish*                          @     296cr (Avg Sell     482cr)
    Best Sale.: (Sell to this station)
        Marine Equipment*              @   4,543cr (Avg Buy   3,937cr)
        Crop Harvesters*               @   2,568cr (Avg Buy   1,997cr)
        Domestic Appliances*           @     714cr (Avg Buy     445cr)


This shows that 'Tea' is a star buy at this station: it is being sold by the station for 1217cr but the average selling price is 1570 credits. A star trade (indicated by '*') is at least 10% better than the average trading price for that commodity.

##BUY sub-command:

Finds stations that are selling / where you can buy, a named list of items or ships.

    trade.py buy
        [-q | -v] [--quantity Q] [--near N] [--ly-per N]
        [-P | -S] [--limit]
        [--one-stop | -1]
        item [item item,item …]
        ship [ship ship,ship …]

Options:

    --quantity Q
      Requires that the stock level be unknown or at least this value,
      --quantity 23

    --near system
    --near station
      Only considers stations within reach of the specified system.
      --near chango

    --ly N.N
      Sets the range of --near (requires --near)
      --near chango --ly 10

    --avoid <system|station>[,<system|station>,...]
      Don't show entries for the specified systems/stations
      e.g.
        --avoid sol --avoid ross154 --avoid abrahamlincoln,marshigh

    --one-stop
    -1
      When multiple items or ships are listed, only lists stations
      which have all of them.

    --limit N
      Limit how many results re shown
      --limit 5

    --lt credits
    --gt credits
      Specify min (gt) and max (lt) credit cost for items
      e.g.
        --gt 100
        --lt 1.2k

    --pad-size SML?
    --pad SML?
    -p
      Limit results to stations that match one of the pad sizes
      specified.
        --pad ML?            (medium, large, or unknown only)
        -p ML?               (medium, large, or unknown only)
        --pad ?              (unknown only)
        --pad L              (large only, ignores unknown)

    --prices-sort
    -P
      Keeps items sorted by price when using --near 
     (otherwise items are listed by distance and then price)

    --supply-sort
    -S
      Sorts items by units available first and then price

  Example:

    trade.py buy --near achenar food
    trade.py buy asp
    trade.py buy --near achenar food,clothing,scrap --one-stop
    trade.py buy --near achenar type6,type7 -1


##SELL sub-command:

Looks for stations buying the specified item.

    trade.py sell [-q | -v] [--quantity Q] [--near N] [--ly-per N] item [-P] [--limit]

Options:

    --quantity Q
      Requires that the stock level be unknown or at least this value,
      --quantity 23

    --near system
    --near station
      Only considers stations within reach of the specified system.
      --near chango

    --ly N.N
      Sets the range of --near (requires --near)
      --near chango --ly 10

    --avoid <system|station>[,<system|station>,...]
      Don't show entries for the specified systems/stations
      e.g.
        --avoid sol --avoid ross154 --avoid abrahamlincoln,marshigh

    --limit N
      Limit how many results re shown
      --limit 5

    --lt credits
    --gt credits
      Specify min (gt) and max (lt) credit prices for items
      e.g.
        --gt 100
        --lt 1.2k

    --pad-size SML?
    --pad SML?
    -p
      Limit results to stations that match one of the pad sizes
      specified.
        --pad ML?            (medium, large, or unknown only)
        -o ML?               (medium, large, or unknown only)
        --pad ?              (unknown only)
        --pad L              (large only, ignores unknown)

    --prices-sort
    -P
      Keeps items sorted by price when using --near
      (otherwise items are listed by distance and then price)


##EXPORT sub-command:

This command generates the CSV data files of the current database. It defaults to export all (except the price) tables and overwrites the files in the data directory.

**CAUTION:** If you have changed any CSV file and didn't rebuild the database, they will be lost. Use the `buildcache` command first to rebuild the database.

    trade.py export [-q | -v] [--path PATH] [--tables TABLE[,TABLE,…] | --all-tables ] [--delete-empty]

Options:

    --path PATH
      Specify the save location of the CSV files. Defaults to './data'

    --tables TABLE[,TABLE,…]
    -T TABLE[,TABLE,…]
      Specify a comma separated list of tablenames to export.

    --all-tables
      Include the price tables for export.

    --delete-empty
      Delete CSV files without content.

  Examples:

    trade.py export --path misc
    Using database './data/TradeDangerous.db'
    Export Table 'Added' to 'misc/Added.csv'
    Export Table 'Category' to 'misc/Category.csv'
    Export Table 'Item' to 'misc/Item.csv'
    Export Table 'Ship' to 'misc/Ship.csv'
    Export Table 'ShipVendor' to 'misc/ShipVendor.csv'
    Export Table 'Station' to 'misc/Station.csv'
    Ignore Table 'StationBuying'
    Ignore Table 'StationItem'
    Ignore Table 'StationSelling'
    Export Table 'System' to 'misc/System.csv'
    Export Table 'Upgrade' to 'misc/Upgrade.csv'
    Export Table 'UpgradeVendor' to 'misc/UpgradeVendor.csv'

    trade.py export -T System,Station
    Using database './data/TradeDangerous.db'
    Export Table 'Station' to 'data/Station.csv'
    Export Table 'System' to 'data/System.csv'


##RARES sub-command:

This command looks for known rare items within the space around a specified system.

    trade.py rare [-q] <system> [--ly N.NN] [--limit N] [--price-sort] [--reverse]

Options:

     <system>
       System to center search on
       e.g.
         Lave
         @Sol

     --ly N.NN
       DEFAULT: 42
       Maximum distance to search from center system.
       e.g.
         --ly 0     (unlimited)
         --ly 21.2

     --limit N
       Maximum number of results to show
       e.g.
         --limit 10

     --reverse
     -r
       Reverse the order, can be used with "--ly" and "--limit" to find
       the furthest-away rares

    --away N.NN
    --from SYSTEM1 --from SYSTEM2 … --from SYSTEMN
      Limits results to systems that are at least a given distance away
      from additional systems.
      e.g.
        trade.py rare --ly 160 sol -r --away 140 --from lave
          Shows systems starting at 160ly or less from sol,
          but that are also 140ly or more from lave.
        trade.py rare --ly 160 sol -r --away 140 --from lave --from xihe
          As above but also compares for <= 140ly from xihe

    --pad-size SML?
    --pad SML?
    -p
      Limit results to stations that match one of the pad sizes
      specified.
        --pad ML?            (medium, large, or unknown only)
        -o ML?               (medium, large, or unknown only)
        --pad ?              (unknown only)
        --pad L              (large only, ignores unknown)

     --price-sort
     -P
       Sort by price rather than proximity

     --quiet
     -q
       Don't include the header lines


  Examples:

    trade.py rare sol --ly 10
    Station                       Rare                    Cost DistLy  Alloc
    ------------------------------------------------------------------------
    ALPHA CENTAURI/Hutton Orbital Centauri Mega Gin      3,319   4.38      7

    trade.py rare @neto --ly 50 --price --limit 5
    Station                   Rare                             Cost DistLy  Alloc
    -----------------------------------------------------------------------------
    XIHE/Zhen Dock            Xihe Biomorphic Companions      4,482  48.10      7
    VEGA/Taylor City          Vega Slimweed                   2,398  33.44      0
    LFT 1421/Ehrlich Orbital  Void Extract Coffee             2,357  26.45      0
    ALTAIR/Solo Orbiter       Altairian Skin                    489  39.78     18
    V1090 HERCULIS/Kaku Plant Herculis Body Rub                 160  37.33     20

 Finding where to take a rare from Bast:

    trade.py rare bast --ly 180 -r --limit 4
    Station                      Rare                        Cost DistLy  Alloc      StnLs Pad
    ------------------------------------------------------------------------------------------
    DELTA PHOENICIS/Trading Post Delta Phoenicis Palms        412 179.42     17      3,743 Lrg
    DEURINGAS/Shukor Hub         Deuringas Truffles         1,892 174.22      0          ? Lrg
    HR 7221/Veron City           HR 7221 Wheat                415 173.57      0          ? Lrg
    ANY NA/Libby Orbital         Any Na Coffee              1,790 170.32     11          ?   ?



#Adding or Changing Price Data
##Experimental GUI in 6.0 
As of v6.0 I've added an experimental GUI for updating prices. I'm still working out some of the issues, in particular you currently have to manually size and scroll the window.

To use it, simply type:

    trade.py update Aulin

or whichever station you need to update. While it is in experimental status, you'll be asked to provide an extra switch.

To **save** your changes, click the window's close button, *don't* alt-f4 or command-q.

To **remove** an item, set the 'paying' and 'asking' values to 0

To **navigate**

 * Use tab/shift-tab to cycle through cells
 * Use up/down arrows to move between rows
 * Press ENTER to move to the first column of the next line

To **add** items to a station, use the "-A" switch and leave the items you don't want empty.


##Other ways of editing Price Data

TradeDangerous uses a human-readable text format for price information. This is designed to closely resemble what we see in the market screens in-game.

To edit the data for a single station, use the `update` sub-command, e.g.

    trade.py update --notepad beagle2

This will open notepad with the data for Aulin, which will look something like:

    @ I BOOTIS/Beagle 2 Landing
     + Chemicals
        Explosives                 50      0        ?      -
        Hydrogen Fuels             19      0        ?      -
        Mineral Oil               100      0        ?      -
        Pesticides                 21      0        ?      -
     + Consumer Items
        Clothing                  300      0        ?      -
        Consumer Tech            1112   1111        ?    30L

"@" lines specify a system/station.

"+" lines specify a category.

The remaining lines are items, such as

    Explosives    50    0    ?    -


The fields used to populate items are:

 * `<item name>`
 * `<sale price>` (how much the station pays)
 * `<buying price>` (how much the station charges)
 * `<demand>` ('?' means "we don't care")
 * `<stock>`  ('-' means "not available")

So you can see the only item this station is selling is Consumer Tech, which the station wants 1111 credits for. The demand wasn't recorded (we generally aren't interested in demand levels since E:D doesn't seem to use them) and
the items wasn't available for purchase *from* the station.

TD will use the 'stock' values to limit how many units it can buy. For example, if you have money to buy 30 units from a station but the `.prices` data says only 10 are available, TD only tell you to buy 10 units and it will fill the rest of your hold up with other stuff.

Demand and Stock both take a "supply level" value which is either "?", "-" or the number of units followed by the level: L for Low, M for Medium, H for High or ? for "don't care".

    ?
    -
    1L
    23M
    3402H
    444?

Best Practice:

 * Leave demand as ?, neither E:D or TD use it
 * Stock quantities over 10k are usually irrelevant; you may leave them as ?,

For more details of the .prices format, see the wiki page: [https://bitbucket.org/kfsone/tradedangerous/wiki/Price%20Data](https://bitbucket.org/kfsone/tradedangerous/wiki/Price%20Data)

NOTE: The order items are listed within their category is saved between edits, so if you switch "Explosives" and "Hydrogen Fuels" and then save it, they will show that way when you edit this station again.

See `trade.py update -h` for more help with the update command.

#That's nice, but I'm a programmer and I want to …

TradeDangerous is organized into modules, the key of which are:

 * trade.tradedb.TradeDB
   * Presents the main database API; it loads stations, systems, ships, items and provides query APIs for these.
 * trade.tradeenv.TradeEnv
   * Container for a bag of "properties" used across TD, such as debug level.
 * trade.tradecalc.TradeCalc
   * The best profit calculator
 * trade.tradeexcept.TradeExcept
   * Exception definitions
 * trade.mfd & trade.mfd.saitek
   * Multi-function display wrappers
 * trade.commands.commandenv.CommandEnv
   * Arg-parsing variant of TradeEnv
 * trade.commands.parsing
   * Helpers for creating argument lists for sub-commands
 * trade.commands.exceptions
   * Exceptions for sub-commands
 * trade.formatting:
   * Helper classes for presenting result sets

Minimalist usage example:

    import trade
    tdb = trade.TradeDB()

This creates a TradeDB instance using all-default parameters. It will take a while to complete because it loads the /entire/ database.

You can override the environment by passing a "TradeEnv", which itself can be initialized with an argparse namespace or by passing default overrides:

    import tradeenv
    # Defaulted:
    tdenv = TradeEnv()
    # Use with argparse to use command-line switches for defaults
    tdenv = TradeEnv(my_parser.parse())
    # Override defaults directly
    tdenv = TradeEnv(debug=1, detail=2)

    import tradedb
    tdb = tradedb.TradeDB(tdenv)

Construction of a wholly-default TradeDB can take a while because it loads a lot of data that you often probably won't need. You can speed it up by disabling the bulk of this with:

    tdb = TradeDB(tdenv, loadTrades=False)

If you subsequently need this data, call

    tdb.loadTrades()

As of TD 6.0 you should need to load this data less and less. A lot of work went into refactoring the SQLite DB and introducing more "lazy loading" by functions like `TradeCalc.getBestHops()`.

When TradeDB and TradeCalc do not currently provide built-in queries for the information you need, you can revert to the SQL Database with the `TradeDB.query()` and `TradeDB.fetch_all()` commands.
