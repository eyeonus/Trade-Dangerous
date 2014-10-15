==============================================================================
TradeDangerous
Copyright (C) Oliver "kfsone" Smith, July 2014
REQUIRES PYTHON 3.0 OR HIGHER.
==============================================================================

== What is Trade Dangerous?
==============================================================================

TradeDangerous is a cargo run optimizer for Elite: Dangerous that calculates
everything from simple one-jump stops between stations to calculating complex
multi-stop routes with light-year, jumps-per-stop, and all sorts of other
things.

For multi-stop routes, it takes into account the money you are making and
factors that into the shopping for each subsequent hop.

== CHANGE LOG
==============================================================================

v4.0.4 Oct 15/2014
  Issue #20 Improved fuzzy-matching of system/star names
  Fixed "Lacaille Prospect"
  "trade.py" is now executable by default on Linux/MacOS

v4.0.3 Oct 12/2014
  Issue #17 "--avoid gold" conflicted with "Goldstein Mines"
  Issue #13 "Nelson Port" was listed as "Nelson Point"
  Issue #12 "-w" was failing because Rigel has no links
  Issue #11 Partial name matches weren't generating an ambiguity (e.g. 'ra' or 'ross')
  Issue #19 Beryllium and Gallium were incorrectly identified as Minerals

v4.0.2 Oct 06/2014
  More systems/stations from ShadowGar!

v4.0.1 Oct 06/2014
  Improved "--sublime" option, now supports Sublime Text 2 and works under Mac/Lin

v4.0 Oct 05/2014
  Updated to Beta 2 - All credit to ShadowGar

v3.9 Sep 21/2014
  NOTE: '--detail' (-v) is now a common option, i.e. must come before sub-command
    trade.py cleanup -v    << won't work any more
    trade.py -v cleanup    << new order
  Added 'nav' sub-command for navigation assistance:
    trade.py nav [--ship name [--full]] [--ly-per] from to
  Added '--quiet' (-q) common option for reducing level of detail, e.g.
    trade.py -q cleanup

v3.8 Sep 17/2014
  Fix for Issue #7: --avoid not working with systems that have no stations,
  Additional help text,
  General cleanup,
  Running "emdn-tap.py -v" will show price changes,

v3.7 Sep 15/2014
  Fixed excessive CPU usage in emdn-tap.py (ty, jojje)
  Added 'cleanup' command to help remove bad data from emdn
    EMDN isn't foolproof, and sometimes receives invalid or
    deliberately poisoned data. The best way to detect this
    is currently to look for prices that are somewhat older
    than the rest of the information received for the same
    station. This command checks for those records and
    removes them.
  emdn-tap now tries harder to honor commit intervals.
API Changes:
  makeSubParser now takes an epilog  

v3.6 Sep 12/2014
  Added DB support for tracking item stock/demand levels,
  TradeCalc will now factor stock levels when present,
  Minor performance/memory tweak
  emdn-tap:
    Now accepts --warn-to argument,
    Applies filters to what data it will accept,
    Records item stock/demand levels to the DB

v3.5 Sep 06/2014
  The emdn-tap tool now uses the compressed JSON stream rather than
  the CSV stream - saves you bandwidth.

v3.4 Sep 05/2014
  Added emdn-tap.py script which pulls data from EMDN network.
  "--via" now accepts multiple and/or comma separated stations so you can plan
  a very specific shopping-list route.

v3.3 Sep 04/2014
  Updated README to include sub-commands,
  Fixed a 'file not found' error running trade.py the first time with no arguments,
  Made specific CATEGORY/Item lookups possible (e.g. "Metals/Gold"),
  Added games internal names for items to the database,
  Enabled internal-name lookups for items (e.g. 'heliostaticfurnaces'),
  Fixed a bug where two names for the same thing caused ambiguity (duh!),
API changes:
  TradeDB.listSearch() now also takes a val() argument,
  Added a simple EMDN access module (emdn directory),
  Cleaned up various __repr__ functions now I know what __repr__ is for,

v3.2 Sep 03/2014
  Internal cleanup of how we process sub-commands

v3.1 Sep 01/2014
  Introduced sub-commands:
  - "run" command provides the old default behavior of calculating a run,
  - "update" command provides ways to update price database easily,

v3.0 Aug 30/2014
  Major overhaul. No-longer requires Microsoft Access DB. To update prices,
  edit the data/TradeDangerous.prices file. When you next run the tool, new
  data will be loaded automatically.
  Cleaned up code, normalized the way I name functions, etc.
  Added more ship data, etc.


==============================================================================
== Where does it get it's data?
==============================================================================

The data is stored as human-readable text in a .SQL file and a .Prices file.
When this data is loaded, it is saved into an SQLite database file which the
tools use directly until you change either the .SQL or .Prices file.

As of version 3.4 it also supports pulling data from the Elite Market Data
Network (EMDN) by means of the emdn-tap.py script (see emdn-tap.py --help
for command line usage)


==============================================================================
== Tell me how to use it!
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

  trade.py --detail --detail --detail run --ship type6 --credits 50000 --insurance 20000 --ly-per 12 --jumps 3 --avoid anderson --avoid gold --via cuffey --to aulin --from chango --hops 6 --checklist --x52-pro
or
  trade.py -vvv run --sh type6 --cr 50000 --ins 20000 --ly 12 --ju 3 --av anderson,gold --via cuffey --to aulin --fr chango --hops 6 --check --x52

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

 C:\TradeDangerous\> trade.py --detail run --ship hauler --credits 20000
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

 C:\TradeDangerous\> trade.py -v run --ship hauler --credits 20000 --ly-per 5.2
     >-> MORGOR Romaneks      Buy 14*Gallite (1376cr),
       |   Morgor -> Dahan -> Asellus
     -+- ASELLUS Beagle2      Buy 13*Advanced Catalysts (2160cr), 2*H.E. Suits (115cr), 1*Scrap (34cr),
       |   Asellus -> Dahan
     <-< DAHAN Gateway gaining 18640cr => 38640cr total

Maybe you don't want to make multiple jumps between systems? Use the "--jumps"
switch to lower or increase the number of jumps between systems on each hop:

  C:\TradeDangerous\> trade.py -v run --ship hauler --credits 20000 --jumps 1
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
== Command Line Options:
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
       Lets you specify the final destination
       e.g.
         --to Beagle2
         --to Aulin

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

  trade.py update [--editor <executable> | --sublime | --notepad] station

    --editor <executable name or path>
      e.g. --editor "C:\Program Files\WibbleEdit\WibbleEdit.exe"
      Saves the prices in a human-readable format and loads that into
      an editor. Make changes and save to update the database.

    --sublime
    --subl
      Like "--editor" but finds and uses the Sublime Text editor (2 and 3).
      You can use "--editor" to tell it exactly where the editor
      is located if it fails to find it.

    --notepad
    --note
      Like "--editor" but uses notepad as the editor.

  Examples:
    trade.py update "aulin enterprise" --notepad
    trade.py update chango --subl
    trade.py update anderson --editor "C:\Program Files\Microsoft Office\WordPad.exe"
    trade.py update wcm

NAV sub-command:

  Provides details of routes without worrying about trade. By default, if
  given a ship, it uses the max dry range of the ship. Use --full if you
  want to restrict to routes with a full cargo hold.

  trade.py [-q | -v] nav [--ship name [--full]] [--ly-per] from to

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


==============================================================================
== How can I add or update the data?
==============================================================================

You can either edit the "data/TradeDangerous.prices" file or you can use the
"update" sub-command.

Alternatively, you can use the "emdn-tap.py" script to monitor the Elite
Market Data Network to pull prices observed by other players. Use

   emdn-tap.py --help

for command line arguments.

CAUTION: EMDN is not fool proof and frequently includes bad data. This is
mostly because of the way EMDN obtains its data and how the Elite Dangerous
UI displays it, but it can also be the result of people deliberately injecting
bad data to spoil your day.

If you use "emdn-tap.py" you will occasionally want to run the trade.py cleanup
command to remove prices that are somewhat older than other prices for the same
station.

You can use the "--dry-run" option to see what this is going to do:

    $ trade.py cleanup --dry-run
    * Performing database cleanup, expiring 10 minute orphan records. DRY RUN.
    - DAHAN Dahan Gateway @ Indium : 2014-09-15 07:10:57 vs 2014-09-15 09:10:32
    # DRY RUN: Database unmodified.

What this tells us is that we haven't seen a price for Indium at Dahan Gateway
since 07:10, but we have more recent prices for other items. Since this is
a single item, chances are it's either no-longer sold there or was a bad
data entry ('fake' items sometimes show up when someone is carrying a mission
item in their cargo hold).

In this case, it looks ok to do cleanup:

    $ trade.py cleanup
    * Performing database cleanup, expiring 10 minute orphan records.
    - Removed 1 entry.

If you prefer no output from your cleanup, use -qq

    $ trade.py -qq cleanup


==============================================================================
== That's nice, but I'm a programmer and I want to ...
==============================================================================

Yeah, let me stop you there. 

    from tradedb import *
    from tradecalc import *

    tdb = TradeDB()
    calc = TradeCalc(tdb, capacity=16, margin=0.01, unique=False)

Whatever it is you want to do, you can do from there.

See "cli.py" for examples.
