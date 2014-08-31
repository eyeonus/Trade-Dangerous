==============================================================================
TradeDangerous v3.0
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
== CHANGE LOG
==============================================================================

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


==============================================================================
== Tell me how to use it!
==============================================================================

If you are sitting in a hauler at Chango with 20,000 credits and you have time
for 2 hops, you might run it like this:

 C:\TradeDangerous\> trade.py --ship hauler --from Chango --credits 20000 --hops 2

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

 C:\TradeDangerous\> trade.py --ship hauler --credits 20000 --hops 2
    ACIHAUT Cuffey -> DAHAN Gateway:
     >-> ACIHAUT Cuffey       Buy 16*Lithium (1129cr),
     -+- AULIN Enterprise     Buy 13*Combat Stabilisers (2179cr), 3*Synthetic Meat (87cr),
     <-< DAHAN Gateway gaining 20035cr => 40035cr total

By starting from Cuffey and making our way to Gateway, we'd make 2,000 credits
more.

But how was it expecting us to get from Cuffey to Aulin? For this, there is
the --detail option:

 C:\TradeDangerous\> trade.py --ship hauler --credits 20000 --hops 2 --detail
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
connections to a max jump distance, in this case of 5.2ly.

 C:\TradeDangerous\> trade.py --ship hauler --credits 20000 --hops 2 --detail --ly-per 5.2
     >-> MORGOR Romaneks      Buy 14*Gallite (1376cr),
       |   Morgor -> Dahan -> Asellus
     -+- ASELLUS Beagle2      Buy 13*Advanced Catalysts (2160cr), 2*H.E. Suits (115cr), 1*Scrap (34cr),
       |   Asellus -> Dahan
     <-< DAHAN Gateway gaining 18640cr => 38640cr total

You can also control how many jumps (connecting star systems) we'll make
on a given hop with '--jumps':

  C:\TradeDangerous\> trade.py --ship hauler --credits 20000 --hops 2 --detail --jumps 2
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

    C:\TradeDangerous\> trade.py --ship hauler --from Chango --insurance 4000 --hops 6 --credits 20000

Lastly, if you are working a long, complicated route, try the "--checklist"
argument which also honors the --detail argument.


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
   --av ITEM/SYSTEM/STATION
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

   --checklist
   --check
     Walks you through the purchases, sales and jumps of your route.
     Note: More verbose when used with --detail

   --x52-pro
   --x52
     OMFG Output the current step of the checklist on your X52 Pro MFD.
     Is that some sweetness or what?

   --detail
   -v
     Increases the amount of detail given when showing routes or running the
     checklist system. Each use increases the detail, i.e. "-v -v" will
     give you more detail than just "-v".

   --debug
     Gives some additional information on what TD is doing while running,
     each use increases the verbosity: i.e. --debug --debug is more verbose.


==============================================================================
== How can I add or update the data?
==============================================================================

For pricing changes, take a look at data/TradeDangerous.prices. This rebuilds
the entire database, a future version will allow you to update prices for
specific stations or items and be able to tell you how recent a price value
is (and use that information for adjusting how confident TD is about a
calculation).

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
