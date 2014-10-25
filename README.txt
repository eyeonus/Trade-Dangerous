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

TradeDangerous data is manually entered: The tool provides an easy editor
for correcting prices at a given station, but you can also retrieve ".prices"
files from other commanders to fill out your database.


== CHANGE LOG
==============================================================================

v4.6.1 Oct 25/2014
. (kfsone) Added "--supply" (-S) which shows supply (demand and stock) fields when editing,
. (kfsone) Added "--timestamps" (-T) which shows timestamp field when editing,
. (kfsone) Added "--force-na" (-0) which replaces 'unk' values with 'n/a' (use with care),
. (kfsone) Deprecated "--all" and "--zero",
. (kfsone) Minor fixes to new .prices format

v4.6.0 Oct 24/2014
. (kfsone) New extended .prices format:
  <item name> <sell> <buy> <demand> <stock> [<time>]
  Demand/stock can be:
   unk     :-  "unknown" - treat as though always available
   n/a     :-  "not available" - ignore in trade calcs
   0       :-  alias for "n/a"
  or the number of units followed by L, M or H, e.g.
   10L     :- 10 units at Low
   500M    :- 500 units at Medium
   9000H   :- 9000 units at High
  Note that the time has moved to the end of the line.
  When updating data, you can either remove the time and have it
  default to 'now' or you can explicitly write the word now.
. (smacker65) Couple of station name corrections
. (kfsone) Better feedback when price data could not be found
. (kfsone) .prices wiki page
. (smacker65) More star data and corrections
. (gazelle) Fix for "--zero" and, e.g., "-1L0"

v4.5.1 Oct 20/2014
. (kfsone) Added --dir (-C) command line for specifying which directory you
  want trade.py to look in for it's files.
. (kfsone) trade.py will now default to trying to look for files relative
  to where the "trade.py" script was called from. So if you run
  "c:\tradedangerous\trade.py" it will look for the data directory as
  "c:\tradedangerous\data\" (Issue #39)

v4.5.0 Oct 20/2014
. (Smacker65/Community) Smacker brings the star database up to 567 systems.

v4.4.0 Oct 19/2014
. (Gazelle/Community) Merged Gazelle's update with community sources Star/Station
  data. Thanks to Gazelle, Smacker, RedWizzard, Haringer, Wolverine.
  It's only data but it's a big update and a lot of work went into it :)

(See end of file for older changes)


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

  trade.py update

    --editor <executable name or path>
      e.g. --editor "C:\Program Files\WibbleEdit\WibbleEdit.exe"
      Saves the prices in a human-readable format and loads that into
      an editor. Make changes and save to update the database.

    --supply
    -S
      Exposes the "demand" and "stock" columns.

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

LOCAL sub-command:

  Provides details of local stations without worrying about trade. By default, if
  given a ship, it uses the max dry range of the ship. Use --full if you
  want to restrict to systems with a full cargo hold.

  trade.py [-q | -v] local [--ship name [--full]] [--ly N.NN] [--pill | --percent] system

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
    
    > trade.py -v local --ly 11.0 sur
    Local systems to SURYA within 11.0 ly.
    --------------------------------------
     9.22 [  2.2] 14 Herculis
     9.23 [  1.0] Vaccimici
     9.35 [ 10.0] CM Draco
    10.59 [ 10.3] V1090 Herculis
    10.69 [ -1.6] Chi Herculis
    
    > trade.py -vv local --ly 10.0 3006
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

==============================================================================
== ADDING OR CHANGING PRICE DATA
==============================================================================

TradeDangerous uses a human-readable text format for price information. This
is designed to closely resemble what we see in the market screens in-game.

To edit the data for a single station, use the "update" sub-command, e.g.

  trade.py update --notepad Aulin

This will open notepad with the data for Aulin, which will look something like:

  @ AULIN/Aulin Enterprise
     + Chemicals
        Explosives                 50      0
        Hydrogen Fuels             19      0
        Mineral Oil               100      0
        Pesticides                 21      0
     + Consumer Items
        Clothing                  300      0
        Consumer Tech            1112   1111

"@" lines specify a system/station.
"+" lines specify a category.
The remaining lines are items.

  Explosives    50    0

These fields are:
  <item name>
  <sale price> (how much the station pays)
  <buying price> (how much the station charges)

So you can see the only item this station is selling is Consumer Tech, which 
the station wants 1111 credits for.

TradeDangerous can also leverage the "DEMAND" and "STOCK" values from the
market UI. To expose those when using "trade.py update", use the "--all"
option. For more details of the extended format, see the Prices wiki page:
https://bitbucket.org/kfsone/tradedangerous/wiki/Price%20Data

NOTE: The order items are listed within their category is saved between edits,
so if you switch "Explosives" and "Hydrogen Fuels" and then save it, they
will show that way when you edit this station again.

See "trade.py update -h" for more help with the update command.

Note: My personal editor of choice is "Sublime Text", which is why there is
a command line option (--sublime or just --subl) for invoking it.


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

== Change Log Archive
==============================================================================

v4.3.0 Oct 17/2014
. (gazelle) Added "--zero" option to "update --all" which makes the default
   value for demand/stock levels "0" instead of "-1". (-1 means 'unknown'.
   Use this option if you are editing timestamps and stock levels and all
   those '-'s get in your way)
. (gazelle) Moved Star, System, etc data out of ".sql" file and into
   per-table ".csv" files. This should make it much easier for people to
   share and synchronize data and make it less daunting for people to
   maintain their data files. Great work, Gazelle!

v4.2.3 Oct 17/2014
. (ShadowGar, Smacker65) Imported Harbinger and RedWizzard system data,
  also added tracking of where data has come from. Thanks also to Wolverine
  for his work identifying data sources.

v4.2.2 Oct 16/2014
. (kfsone) user-friendlified errors generated by TD
. (kfsone) gave "update" sub-command a "--npp" option (notepad++)
. (kfsone) gave "update" sub-command a "--vim" option (vim editor)

v4.2.1 Oct 15/2014
. (ShadowGar) Added more Stars and corrected HAGALAZ
. (kfsone) sort items by name rather than id when building .prices files
. (kfsone) improved the instructional comments in .prices files
. (kfsone) Big README.txt cleanup

v4.2.0 Oct 15/2014
. (Smacker65) Added "local" sub-command (lists systems within jump range of you)

v4.1.0 Oct 15/2014
. (gazelle) ".prices" file is no-longer included in the git repository,
  instead you'll need to download one or populate your own
. (gazelle) added the "--all" option to the "update" sub-command,
. (kfsone) fixed problems caused when the .prices file is missing and there is
  limited or no data available - user should get better feedback now.

v4.0.4 Oct 15/2014
. (kfsone) Issue #20 Improved fuzzy-matching of system/star names
. (gazelle) Fixed "Lacaille Prospect"
. (kfsone) "trade.py" is now executable by default on Linux/MacOS

v4.0.3 Oct 12/2014
. (kfsone) Issue #17 "--avoid gold" conflicted with "Goldstein Mines"
. (Smacker65) Issue #13 "Nelson Port" was listed as "Nelson Point"
. (kfsone) Issue #12 "-w" was failing because Rigel has no links
. (kfsone) Issue #11 Partial name matches weren't generating an ambiguity (e.g. 'ra' or 'ross')
. (kfsone) Issue #19 Beryllium and Gallium were incorrectly identified as Minerals

v4.0.2 Oct 06/2014
. (ShadowGar) More systems/stations from

v4.0.1 Oct 06/2014
. (kfsone)  Improved "--sublime" option, now supports Sublime Text 2 and works under Mac/Lin

v4.0 Oct 05/2014
. (ShadowGar) Updated to Beta 2 - All credit to ShadowGar

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

