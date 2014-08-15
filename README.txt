==============================================================================
TradeDangerous v2.02
Copyright (C) Oliver "kfsone" Smith, July 2014
==============================================================================

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


==============================================================================
== Where does it get it's data?
==============================================================================

The data is stored in a simple Microsoft Access 2013 Database because I'm
hand-editing the database and Microsoft Access surprised me by having a really
nice UI for doing this (open the .accdb file with MS Access and open the
'StationCats' query, click the 'v' button on the 'station' header and select
the station you are at to update the prices for it).

Programmer Note: I used the pypyodbc api so you can replace it with whatever
DB you want.


==============================================================================
== Tell me how to use it!
==============================================================================

If you are sitting in a hauler at Chango with 20,000 credits and you have time
for 2 hops, you might run it like this:

 C:\TradeDangerous\> trade.py --from Chango --credits 20000 -capacity 16 --hops 2

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

 C:\TradeDangerous\> trade.py --credits 20000 -capacity 16 --hops 2
    ACIHAUT Cuffey -> DAHAN Gateway:
     >-> ACIHAUT Cuffey       Buy 16*Lithium (1129cr),
     -+- AULIN Enterprise     Buy 13*Combat Stabilisers (2179cr), 3*Synthetic Meat (87cr),
     <-< DAHAN Gateway gaining 20035cr => 40035cr total

By starting from Cuffey and making our way to Gateway, we'd make 2,000 credits
more.

But how was it expecting us to get from Cuffey to Aulin? For this, there is
the --detail option:

 C:\TradeDangerous\> trade.py --credits 20000 -capacity 16 --hops 2 --detail
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

The hauler can't make the above journey with cargo.

The "--ly-per" argument lets us tell TD to limit connections to a max of
5.2ly.

 C:\TradeDangerous\> trade.py --credits 20000 -capacity 16 --hops 2 --detail --ly-per 5.2
     >-> MORGOR Romaneks      Buy 14*Gallite (1376cr),
       |   Morgor -> Dahan -> Asellus
     -+- ASELLUS Beagle2      Buy 13*Advanced Catalysts (2160cr), 2*H.E. Suits (115cr), 1*Scrap (34cr),
       |   Asellus -> Dahan
     <-< DAHAN Gateway gaining 18640cr => 38640cr total

You can also control the number of jumps allowed on any given hop: --max-jumps
sets an upper limit on the total number of jumps, --jumps-per limits the
maximum jumps on each hop.

  C:\TradeDangerous\> trade.py --credits 20000 --capacity 16 --hops 2 --detail --ly-per 5.2 --jumps-per 2
    ERANIN Azeban -> DAHAN Gateway:
     >-> ERANIN Azeban        Buy 16*Coffee (1092cr),
       |   Eranin -> Asellus
     -+- ASELLUS Beagle2      Buy 11*Advanced Catalysts (2160cr), 5*H.E. Suits (115cr),
       |   Asellus -> Dahan
     <-< DAHAN Gateway gaining 13870cr => 33870cr total

TD also takes a "--insurance" option which tells it to put some money aside
for insurance payments. This lets you put the actual amount of credits you
have without having to remember to subtract your insurance each time:

Lets say we want to do a half dozen runs and keep 4000 credits aside so that
we don't get totally wiped out by a crash along the way:

    C:\TradeDangerous\> trade.py --from Chango --capacity 16 --insurance 4000 --hops 6 --credits 20000


==============================================================================
== Command Line Options:
==============================================================================

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
     Only show routes which do not visit any station twice

   --hops N
     DEFAULT: 2
     Maximum number of hops (number of cargo pickups)
     e.g.
       --hops 8

   --jumps N
     DEFAULT: 0 (unlimited)
     Limit the total number of jumps across the journey
     e.g.
       --jumps 3

   --jumps-per N
     DEFAULT: 3
     Limit the number of systems jumped to between each station
     e.g.
       -jumps-per 5

   --ly-per N.NN
     DEFAULT: 5.2
     Maximum distance your ship can jump between systems at full capacity.
     Note: You can increase your range by selling your weapons.
     e.g.
       --ly-per 19.1
       --ly-per 3

 Ship/Trade options:
   --capacity N
     DEFAULT: 4
     Maximum items you can carry on each hop.
 
   --credits N
     How many credits to start with
     e.g.
       --credits 20000

   --insurance N   DEFAULT: 0
     How many credits to hold back for insurance purposes
     e.g.
       --insurance 1000

   --limit N   DEFAULT: 0
     If set, limits the maximum number of units of any cargo
     item you will buy on any trade hop, incase you want to
     hedge your bets or be a good economy citizen.
     e.g.
       --capacity 16 --limit 8

   --avoid ITEM/SYSTEM/STATION
     Excludes the item/system/station matching the name from the database
     e.g.
       --avoid Gold
       --avoid Aulin
       --avoid Enterprise
       --avoid prise

   --margin N.NN   DEFAULT: 0.01
     At the end of each hop, reduce the profit by this much (0.02 = 2%),
     to allow a margin of error in the accuracy of prices.
     e.g.
       --margin 0      (no margin)
       --margin 0.01   (1% margin)
 
 Other options:
   --routes N   DEFAULT: 1
     Shows the top N routes; 

   --detail
     Show jumps between stations when showing routes

   --debug
     Gives some additional information on what TD is doing while running.


==============================================================================
== How can I add or update the data?
==============================================================================

A script is provided, "import.py", which processes a series of simple commands
from a file called "import.txt".

Syntax for import.txt is fairly primitive. Eventually I intend to replace the
access database with a collection of 'import.txt' files.

  # ...
    Comment lines are ignored, as are blank lines.

  #rejectUnknown
    Special comment that causes an unrecognized system in a new-star line
    to generate an error.

  *<system name>/<station name>:<system>@n.nn[ly][,<system>@n.nn[,...]]
    Adds a system with links to other systems. For EMPTY systems (with
    no stations), you can specify '*' as the station name.
    e.g.
      *Dahan/Gateway:Aulin@5.6,Eranin@9.8ly,...
      *Hermitage/*:Elsewhere@10.13ly

  @<station name>
    Selects the specified station without trying to add it.
    e.g.
      @aulin
      @gateway
      @dahan

  -<partial category name>
    Finds an item category matching the string and selects it as
    the current item category. If the match is ambiguous, an error
    will be raised.
    NOTE: the name cannot contain a space, e.g. for "Consumer Goods"
    just use "consumer" or "goods"
    e.g.
      -dru
      -DRUG
      -dRuGs
      -rug
      -ugs
      -cons
      -consumer
      -goods

  <partial item name> <buy price> [<sell price>]
    Finds an item matching the name within the current category
    and sets a buy (how much the station buys for) and/or sell
    price (how much the station sells for) for the item.
    If the match is ambiguous, an error will be raised.
    If no sell price is specified, it is assumed to be 0.
    NOTE: Name cannot contain spaces
    e.g.
      -cons
      appliances 1000
      appl 1000 0
      -chem
      pesticides 56 57
      PEST 56 57

'*' doesn't select the system, this is because I tend to keep all of
my stations at the top of my import.txt and then tack on item updates
to a single station at the end, and I wanted to make absolutely sure I
had selected the correct station.


=====================
== Example import.txt


  # Add (or update) dahan and describe it's links to Aulin and Eranin.
  # If they aren't in the database yet, they will be quietly ignored.
  # If they are in the database, a link will be added each way.
  *Dahan/Gateway:Aulin@5.6ly,Eranin@9.8ly

  # Add Eranin.
  *Eranin/Azeban:Dahan@9.8ly,Hermitage@20.21ly

  # Select Dahan.
  # Alternatively: @DAHAN, @GATEWAY or @gateway
  @Dahan

  # Select 'Chemicals' category.
  # Alternatively: -CHEMICALS, -CHEMicals, etc
  -chem

  # Hydrogen fuel is bought by this station for 56cr but not sold here.
  # Alternatively: Hydrogen 56 0, HYD 56, etc
  hydro 56

  # Station is selling pesticides for 67cr or paying 58 for them.
  # Alternatively: PESTICIDES 67 58, pesti 67 58, etc
  pest 67 58

  # Change to Consumer Goods category, which matches 'cons'
  # and specify prices for "Clothing", "Consumer Technology" and "Dom.
  # Appliances"
  -cons
  clo 306
  cons 6049
  # alternatively: dom, DOM, appliances, APPLI, appl, etc
  dom. 548


==============================================================================
== Why did you choose MS Access, you moron?
==============================================================================

I'm a Unix guy but I also like to push myself outside my comfort zone. During
my time at Blizzard I'd actually started to find MS Office 2010 quite
bearable, so I happened to have a free trial of MS Office 365 installed.

I wanted to throw the data together really, really quickly. So I tried Libre
Office Base. The pain was strong in that one. So, for giggles, I decided to
see just how painful it was in Access and 5 minutes later I had a working
database that was really easy to update exactly the way I wanted.

It should be trivial to convert it to a different database.


==============================================================================
== That's nice, but I'm a programmer and I want to ...
==============================================================================

Yeah, let me stop you there. 

    from tradedb import *
    from tradecalc import *

    tdb = TradeDB(".\\TradeDangerous.accdb")
    calc = TradeCalc(tdb, capacity=16, margin=0.01, unique=False)

Whatever it is you want to do, you can do from there.

See "cli.py" for examples.


==============================================================================
== Change Log
==============================================================================

v2.02
  "--via" will now accept the via station as the first station on
  routes when the user doesn't specify a "--from".
  Also made name matching far more flexible.

v2.01
  "--avoid" now handles stations and system names
