==============================================================================
TradeDangerous
Copyright (C) Oliver "kfsone" Smith, July 2014
REQUIRES PYTHON 3.4 OR HIGHER.
==============================================================================

[For recent changes see CHANGES.txt]

== What is Trade Dangerous?
==============================================================================

TradeDangerous is a cargo run optimizer for Elite: Dangerous that calculates
everything from simple one-jump stops between stations to calculating complex
multi-stop routes with light-year, jumps-per-stop, and all sorts of other
things.

For multi-stop routes, it takes into account the money you are making and
factors that into the shopping for each subsequent hop.

TradeDangerous data is manually entered: The tool provides an easy editor
for correcting prices at a given station, but you can also retrieve ".prices"
files from other commanders to fill out your database.


==============================================================================
== TRADE DANGEROUS: USAGE
==============================================================================

Lets start with a fully fleshed out example command line and then I'll walk
you through some simpler cases.

  I have a Lakon Type 6 and 50,000 credits. I want to keep 20,000 credits
  aside for insurance incase bad things happen. My ship is kitted out so
  it is limited to 12 light year jumps, but I'll try 3 jumps between each
  station. I don't like the long drive to Anderson's escape so don't go
  there, and I want to avoid Gold because it's usually scarce.

  I have a mission at Cuffey and I want to finish at Aulin to outfit.

  Plan me a route from Chango with 6 stops to make money.

  Show me the route in detail, walk me through each step and put the
  instructions for the current step on the multi-function display of my
  X52 throttle...

  trade.py run --detail --detail --detail --ship type6 --credits 50000 --insurance 20000 --ly-per 12 --jumps 3 --avoid anderson --avoid gold --via cuffey --to aulin --from chango --hops 6 --checklist --x52-pro
or
  trade.py run -vvv --sh type6 --cr 50000 --ins 20000 --ly 12 --ju 3 --av anderson,gold --via cuffey --to aulin --fr chango --hops 6 --check --x52

Lets dial it back and start with something simpler:

You're sitting in a hauler at Chango with 20,000 credits and you have time
for 2 hops, you might run it like this:

 C:\TradeDangerous\> trade.py run --ship hauler --from Chango --credits 20000

The 'run' keyword indicates you want to calculate a trade run. Trade tries to
be flexible, so you could shorten this down to:

  trade.py --sh hauler --fr chan --cr 20000

And the output might look like this:

    I BOOTIS Chango -> DAHAN Gateway:
     >-> I BOOTIS Chango      Buy 16*Fish (389cr),
     -+- LHS3006 WCM          Buy 13*Bertrandite (1871cr), 3*Lepidolite (323cr),
     <-< DAHAN Gateway gaining 13806cr => 33806cr total

The route goes from Chango to Gateway via LHS 3006. At Chango, you pick up 16
fish at 389 credits each. Fly to LHS 3006 and dock at WCM and sell your fish,
and pick up 13 Bertrandite and 3 units of Lepidolite. Set sail for Gateway in
Dahan ... and profit.

To the tune of 13,806cr.

If you leave out the '--from' option, TradeDangerous will do the same
calculation for every station in the database and tell you where the best
possible 2-hop run is:

 C:\TradeDangerous\> trade.py run --ship hauler --credits 20000
    ACIHAUT Cuffey -> DAHAN Gateway:
     >-> ACIHAUT Cuffey       Buy 16*Lithium (1129cr),
     -+- AULIN Enterprise     Buy 13*Combat Stabilisers (2179cr), 3*Synthetic Meat (87cr),
     <-< DAHAN Gateway gaining 20035cr => 40035cr total

By starting from Cuffey and making our way to Gateway, we'd make 2,000 credits
more.

But how was it expecting us to get from Cuffey to Aulin? For this, there is
the --detail option. This is one of the options common to all commands, and
so it has to be specified before the command. It can be abbreviated "-v"
(think: verbose)

 C:\TradeDangerous\> trade.py run --detail --ship hauler --credits 20000
    ACIHAUT Cuffey -> DAHAN Gateway:
     >-> ACIHAUT Cuffey       Buy 16*Lithium (1129cr),
       |   Acihaut -> LHS3006 -> Aulin
     -+- AULIN Enterprise     Buy 13*Combat Stabilisers (2179cr), 3*Synthetic Meat (87cr),
       |   Aulin -> Eranin -> Dahan
     <-< DAHAN Gateway gaining 20035cr => 40035cr total

The route starts at Cuffey station in Acihaut. Then you jump to LHS 3006 and
then Aulin, where you dock at Enterprise. Then you jump from Aulin to Eranin
and finally to Dahan to dock at Gateway.

I use the term "hop" to describe picking up goods at one station, crossing
systems and docking at another station and selling the goods; the term "jump"
to describe a hyperspace trip between two individual star systems.

One problem:

The hauler can't make the above journey with cargo and weapons.

The "--ly-per" argument (or it's --ly abbreviation) lets us tell TD to limit
connections to a max jump distance, in this case of 5.2ly. Note that this
time I'm using "-v" as a short-cut for "--detail"

 C:\TradeDangerous\> trade.py run -v --ship hauler --credits 20000 --ly-per 5.2
     >-> MORGOR Romaneks      Buy 14*Gallite (1376cr),
       |   Morgor -> Dahan -> Asellus
     -+- ASELLUS Beagle2      Buy 13*Advanced Catalysts (2160cr), 2*H.E. Suits (115cr), 1*Scrap (34cr),
       |   Asellus -> Dahan
     <-< DAHAN Gateway gaining 18640cr => 38640cr total

Maybe you don't want to make multiple jumps between systems? Use the "--jumps"
switch to lower or increase the number of jumps between systems on each hop:

  C:\TradeDangerous\> trade.py run -v --ship hauler --credits 20000 --jumps 1
    ERANIN Azeban -> DAHAN Gateway:
     >-> ERANIN Azeban        Buy 16*Coffee (1092cr),
       |   Eranin -> Asellus
     -+- ASELLUS Beagle2      Buy 11*Advanced Catalysts (2160cr), 5*H.E. Suits (115cr),
       |   Asellus -> Dahan
     <-< DAHAN Gateway gaining 13870cr => 33870cr total

TD also takes a "--insurance" option which tells it to put some money aside
for insurance payments. This lets you put the actual amount of credits you
have without having to remember to subtract your insurance each time.


==============================================================================
== COMMAND LINE OPTIONS
==============================================================================

trade.py is a front-end to several tools - a trade run calculator, a tool for
updating prices at a given station, and more to come.

You can type "trade.py -h" for basic usage, or for help on a specific sub-
command, you can use "trade.py command -h" for example

  trade.py run -h

will show you how to use the 'run' sub-command.

Common Options:
  These can be used with any command, so they must be specified before the
  command itself.

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

Sub Commands:
  trade.py run ...
    Calculates a trade run.

  trade.py update ...
    Provides an interface for updating the prices at a station.


RUN sub-command:

  This command provides the primary trade run calculator functionality (it provides
  the functionality of the older TradeDangerous versions prior to 3.1)

   Route options:
     --from <station or system>
       Lets you specify the starting station
       e.g.
         --from Dahan
         --from Gateway

     --to <station or system>
       Lets you specify the final destination. If you specify a station, it
       will finish at that exact station. If you specify a system, it will
       try all the stations in the target system.
       e.g.
         --to Beagle2
         --to lhs64

     --end <station or system>
       Instead of --to, allows you to specify multiple destinations and
       TD will attempt to find a route that ends at one of them:
       e.g.
         --end beagle2
           ^_ equivalent to "--to beagle2"
         --end beagle2 --end freeport
           ^_ finds a route terminating at EITHER beagle2 OR freeport

     --via <station or system>
       Lets you specify a station that must be between the second and final hop.
       Requires that hops be at least 2.
       e.g.
         --via Enterprise
         --via Chango

     --unique
     --uni
       Only show routes which do not visit any station twice

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

     --ly-per N.NN
     --ly N.NN
       DEFAULT: based on --ship
       Maximum distance your ship can jump between systems at full capacity.
       NOTE: You can increase your range by selling your weapons.
       e.g.
         --ly-per 19.1
         --ly-per 3

   Ship/Trade options:
     --capacity N
     --cap N
       DEFAULT: based on --ship
       Maximum items you can carry on each hop.
   
     --credits N
     --cr N
       How many credits to start with
       e.g.
         --credits 20000

     --insurance N   DEFAULT: 0
     --ins N
       How many credits to hold back for insurance purposes
       e.g.
         --insurance 1000
         --ins 5000

     --limit N   DEFAULT: 0
       If set, limits the maximum number of units of any cargo
       item you will buy on any trade hop, incase you want to
       hedge your bets or be a good economy citizen.
       e.g.
         --capacity 16 --limit 8

     --avoid ITEM/SYSTEM/STATION
     --avoid AVOID,AVOID,...,AVOID
     --av ITEM/SYSTEM/STATION
     --av AVOID,AVOID,...,AVOID
       Excludes the item/system/station matching the name from the database
       e.g.
         --avoid Gold
         --avoid Aulin
         --avoid Enterprise
         --avoid prise
         --av gold,aulin,enterprise,anderson

     --margin N.NN   DEFAULT: 0.01
       At the end of each hop, reduce the profit by this much (0.02 = 2%),
       to allow a margin of error in the accuracy of prices.
       e.g.
         --margin 0      (no margin)
         --margin 0.01   (1% margin)
   
   Other options:
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

UPDATE sub-command:

  For maintenance on your local prices database. The default is to walk
  you through a list of all the prices known for the station. You can either
  hit enter or type the correction.

  Alternatively, if you specify one of the editing switches, it will put
  the prices for a given station into a text file and let you edit it
  with your favorite editor.

  trade.py update

    --editor <executable name or path>
      e.g. --editor "C:\Program Files\WibbleEdit\WibbleEdit.exe"
      Saves the prices in a human-readable format and loads that into
      an editor. Make changes and save to update the database.

    --timestamps
    -T
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
    trade.py update --sub --sup --time --zero aulin
  aka:
    trade.py update --sub -ST0 aulin

IMPORT sub-command:

  Provides a way to import prices data from a file or a web site. You can use this
  to import data for a few stations or an entire .prices file from a friend.

  For instance, if you 'update'd a station and there was an error importing it,
  the data is usually saved as "prices.last". You can open this file and correct
  the error and then import it, rather than having to re-enter all of the data.

  NOTE: Items not listed for a station in an import are considered unavailable at
  that station. If you have an entry for Beagle2/Food and you import a file that
  does not include Beagle2/Food, Beagle2/Food will be removed from your db.

  trade.py import [-q | -v] [filename | url | --maddavo] [--ignore-unknown]

    filename
      Specifies the name of the file to load
      e.g.
        import.prices

    url
      Specifies web adress to retrieve the data from
      e.g.
        http://kfs.org/td/prices

    --maddavo
      Like 'url' but specifies the URL for maddavo's .prices file

    --ignore-unknown
    -i
      Any systems, stations, categories or items that aren't recognized
      by this version of TD will be reported but import will continue.
 


BUY sub-command:

  Looks for stations selling the specified item: that means they have a non-zero
  asking price and a stock level other than "n/a".

  trade.py buy [-q | -v] [--quantity Q] [--near N] [--ly-per N] item [-P | -S]

    --quantity Q
      Requires that the stock level be unknown or at least this value,
      --quantity 23

    --near system
    --near station
      Only considers stations within reach of the specified system.
      --near chango

    --limit N
      Limit how many results re shown
      --limit 5

    --ly-per N.N
      Sets the range of --near (requires --near)
      --near chango --ly 10

    --prices-sort
    -P
      Keeps items sorted by price when using --near
      (otherwise items are listed by distance and then price)

    --stock-sort
    -S
      Sorts items by stock available first and then price


NAV sub-command:

  Provides details of routes without worrying about trade. By default, if
  given a ship, it uses the max dry range of the ship. Use --full if you
  want to restrict to routes with a full cargo hold.

  trade.py nav [-q | -v] [--ship name [--full]] [--ly-per] from to

    --ship name
      Uses the values for an empty ship to constrain jump ranges,
      --ship=ana
      --ship type6
      --ship 6

    --full
      Used with --ship, uses the max range of the ship with a full load,
      --ship cobra --full

    --ly-per N.NN
      Constrains jumps to a maximum ly distance
      --ly-per 3.2

    from
      Name of the starting system or a station in the system,

    to
      Name of the destination system or a station in the system,

  Examples:
    > trade.py nav --ship=type6 5287 2887
    From LHS 5287 to LHS 2887 with 29.36ly per jump limit.
    System                         (Jump Ly)
    ----------------------------------------
    LHS 5287                       (   0.00)
    I BOOTIS                       (  19.94)
    LHS 2887                       (  17.14)

    > trade.py -v nav --ship=type6 --full 5287 2887
    From LHS 5287 to LHS 2887 with 15.64ly per jump limit.
    Action | System                         | Jump Ly | Total Ly
    ------------------------------------------------------------
    Depart | LHS 5287                       |    0.00 |     0.00
    Via    | ASELLUS PRIMUS                 |   14.47 |    14.47
    Via    | BD+47 2112                     |   11.81 |    26.28
    Arrive | LHS 2887                       |   11.73 |    38.01

LOCAL sub-command:

  Provides details of local stations without worrying about trade. By default, if
  given a ship, it uses the max dry range of the ship. Use --full if you
  want to restrict to systems with a full cargo hold.

  trade.py local [-q | -v] [--ship name [--full]] [--ly N.NN] [--pill | --percent] system

    --ship name
      Uses the values for an empty ship to constrain jump ranges,
      --ship=ana
      --ship type6
      --ship 6

    --full
      Used with --ship, uses the max range of the ship with a full load,
      --ship cobra --full

    --ly N.NN
      Constrains local systems to a maximum ly distance
      --ly 20.0
    
    --pill
      Show estimated length along the Pill in ly

    --percent
      Like --pill but shows percentage instead

    -v
      Show stations
      
    system
      Name of the system or a station in the system,

  Examples:
    > trade.py local --ly 11.0 dahan
    Local systems to DAHAN within 11.0 ly.
  	--------------------------------------
  	 4.66 Asellus Primus
  	 5.12 Morgor
  	 6.41 Eranin
  	 8.26 Meliae
  	 8.58 LHS 2884
  	 8.60 LP 98-132
  	 9.20 Aulis
  	 9.75 GD 319
  	10.08 BD+47 2112
  	10.33 i Bootis
    
    > trade.py local -v --ly 11.0 sur
    Local systems to SURYA within 11.0 ly.
    --------------------------------------
     9.22 [  2.2] 14 Herculis
     9.23 [  1.0] Vaccimici
     9.35 [ 10.0] CM Draco
    10.59 [ 10.3] V1090 Herculis
    10.69 [ -1.6] Chi Herculis
    
    > trade.py local -vv --ly 10.0 3006
    Local systems to LHS 3006 within 10.0 ly.
    -----------------------------------------
     5.64 [  0.4] Acihaut
          <Cuffey Plant>
          <Mastracchio Base>
     6.00 [  5.1] G 239-25
          <Bresnik Mine>
     6.47 [  1.1] Nang Ta-khian
          <Hay Point>
          <Hadwell Orbital>
     7.51 [ -0.0] Eranin
          <Azeban City>
          <Azeban Orbital>
          <Eranin 4 Survey>
     7.74 [ -4.9] Aulin
          <Aulin Enterprise>
          <Harbaugh Station>
          <Onufrienko Station>
     8.12 [ -2.8] i Bootis
          <Chango Dock>
          <Maher Stellar Research>
     8.52 [ -6.4] BD+47 2112
          <Olivas Settlement>
     8.78 [  7.9] Lalande 29917
     9.40 [  5.7] DN Draconis
     9.72 [  4.9] LP 98-132
          <Freeport>
          <Prospect Five>

EXPORT sub-command:

  This command generates the CSV data files of the current database. It
  defaults to export all tables and overwrites the files in the data directory.
  CAUTION: If you have changed any CSV file and didn't rebuild the database, they
           will be lost. Use the 'buildcache' command first to rebuild the database.

  trade.py export [-q | -v] [--path PATH] [--tables TABLE[,TABLE,...]]

    --path PATH
      Specify the save location of the CSV files. Default to './data'

    --tables TABLE[,TABLE,...]
    -T TABLE[,TABLE,...]
      Specify a comma separated list of tablenames to export.

    --delete-empty
      Delete CSV files without content.

  Examples:
    > trade.py export --path misc
    Using database './data/TradeDangerous.db'
    Export Table 'Added' to 'misc\Added.csv'
    Export Table 'AltItemNames' to 'misc\AltItemNames.csv'
    Export Table 'Category' to 'misc\Category.csv'
    Export Table 'Item' to 'misc\Item.csv'
    Export Table 'Ship' to 'misc\Ship.csv'
    Export Table 'ShipVendor' to 'misc\ShipVendor.csv'
    Export Table 'Station' to 'misc\Station.csv'
    Export Table 'StationBuying' to 'misc\StationBuying.csv'
    Export Table 'StationItem' to 'misc\StationItem.csv'
    Ignore Table 'StationLink'
    Export Table 'StationSelling' to 'misc\StationSelling.csv'
    Export Table 'System' to 'misc\System.csv'
    Export Table 'Upgrade' to 'misc\Upgrade.csv'
    Export Table 'UpgradeVendor' to 'misc\UpgradeVendor.csv'

    > trade.py export -T System,Station
    Using database './data/TradeDangerous.db'
    Export Table 'Station' to 'data\Station.csv'
    Export Table 'System' to 'data\System.csv'

==============================================================================
== ADDING OR CHANGING PRICE DATA
==============================================================================

*** Experimental GUI in 6.0 ***
*******************************


As of v6.0 I've added an experimental GUI for updating prices. I'm still
working out some of the issues, in particular you currently have to manually
size and scroll the window.

To use it, simply type:

  trade.py update Aulin

or whichever station you need to update. While it is in experimental status,
you'll be asked to provide an extra switch.

- To save your changes:

Click the window's close button, don't alt-f4 or command-q.

- To remove an item:

Set the 'paying' and 'asking' values to 0

- To move around

 . Use tab/shift-tab to cycle thru cells,
 . Use up/down arrows to move between rows,
 . Press ENTER to move to the first column of the next line,

- To add items to a station:

Use the "-A" switch and leave the items you don't want empty.


*** Other ways of editing Price Data ***
****************************************


TradeDangerous uses a human-readable text format for price information. This
is designed to closely resemble what we see in the market screens in-game.

To edit the data for a single station, use the "update" sub-command, e.g.

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
The remaining lines are items.

  Explosives    50    0    ?    -

These fields are:
  <item name>
  <sale price> (how much the station pays)
  <buying price> (how much the station charges)
  <demand> ('?' means "we don't care")
  <stock>  ('-' means "not available")

So you can see the only item this station is selling is Consumer Tech, which 
the station wants 1111 credits for. The demand wasn't recorded (we generally
aren't interested in demand levels since E:D doesn't seem to use them) and
the items wasn't available for purchase *from* the station.

TD will use the 'stock' values to limit how many units it can buy. For
example, if you have money to buy 30 units from a station but the .prices
data says only 10 are available, TD only tell you to buy 10 units and it
will fill the rest of your hold up with other stuff.

Demand and Stock both take a "supply level" value which is either "?", "-"
or the number of units followed by the level: L for Low, M for Medium,
H for High or ? for "don't care".

   ?
   -
   1L
   23M
   3402H
   444?

Best Practice:

 - Leave demand as ?, neither E:D or TD use it,
 - Stock quantities over 10k are usuall irrelevant, leave them as ?,
 
For more details of the .prices format, see the wiki page:
https://bitbucket.org/kfsone/tradedangerous/wiki/Price%20Data

NOTE: The order items are listed within their category is saved between edits,
so if you switch "Explosives" and "Hydrogen Fuels" and then save it, they
will show that way when you edit this station again.

See "trade.py update -h" for more help with the update command.


==============================================================================
== That's nice, but I'm a programmer and I want to ...
==============================================================================

TradeDangerous is organized into modules, the key of which are:

  trade.tradedb.TradeDB
    Presents the main database API; it loads stations, systems, ships, items
    and provides query APIs for these.

  trade.tradeenv.TradeEnv
    Container for a bag of "properties" used across TD, such as debug level.

  trade.tradecalc.TradeCalc
    The best profit calculator

  trade.tradeexcept.TradeExcept
    Exception definitions

  trade.mfd
  trade.mfd.saitek
    Multi-function display wrappers

  trade.commands.commandenv.CommandEnv
    Arg-parsing variant of TradeEnv

  trade.commands.parsing
    Helpers for creating argument lists for sub-commands

  trade.commands.exceptions
    Exceptions for sub-commands

  trade.formatting:
    Helper classes for presenting result sets


Minimalist usage example:

  import trade
  tdb = trade.TradeDB()

This creates a TradeDB instance using all-default parameters. It will take
a while to complete because it loads the /entire/ database.

You can override the environment by passing a "TradeEnv", which itself can
be initialized with an argparse namespace or by passing default overrides:

  import tradeenv
  # Defaulted:
  tdenv = TradeEnv()
  # Use with argparse to use command-line switches for defaults
  tdenv = TradeEnv(my_parser.parse())
  # Override defaults directly
  tdenv = TradeEnv(debug=1, detail=2)

  import tradedb
  tdb = tradedb.TradeDB(tdenv)

Construction of a wholly-default TradeDB can take a while because it loads
a lot of data that you often probably won't need. You can speed it up by
disabling the bulk of this with:

  tdb = TradeDB(tdenv, buildLinks=False, includeTrades=False)

If you subsequently need this data, call

  tdb.buildLinks()
or
  tdb.loadTrades()

As of TD 6.0 you should need to load this data less and less. A lot of
work went into refactoring the SQLite DB and introducing more "lazy
loading" by functions like TradeCalc.getBestHops().

When TradeDB and TradeCalc do not currently provide built-in queries for
the information you need, you can revert to the SQL Database with the
TradeDB.query() and TradeDB.fetch_all() commands.

