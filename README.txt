TradeDangerous v0.0.mumble	Copyright (C) Oliver "kfsone" Smith, July 2014
==========================

REQUIRES PYTHON 3.0 OR HIGHER.

* What is Trade Dangerous?

TradeDangerous is a cargo run optimizer for Elite: Dangerous. By "cargo run" I mean
that it's designed to optimize more than just the current hop for you.

Jumping between just two stations isn't guaranteed to give you the best bang for your
buck. 

Sure, TD can tell you what the best load is for your Cobra from Chango to Enterprise,
but it can also tell you what you should pick up at Enterprise and where you should
take that.

TD also does a more comprehensive test for what the optimal load is. Some E:D trade
optimizers will tell you that you should buy 1 Gold, 1 Tantalum, 1 Biowaste and 1
Scrap; TD will figure out that you could take 3 Tantalum and 1 Basic Medicines
and come away with twice as much profit from the run.

It also takes into account the profit earned from trades on each hop into the
subsequent hop.

* Where does it get it's data?

The data is stored in a simple Microsoft Access 2013 Database because I'm hand-editing
the database and Microsoft Access surprised me by having a really nice UI for doing
this (open the .accdb file with MS Access and open the 'StationCats' query, click the
'v' button on the 'station' header and select the station you are at to update the
prices for it).

Programmer Note: I used the pypyodbc api so you can replace it with whatever DB you
want.


* Tell me how to use it!

If you are sitting in a hauler at Chango with 20,000 credits and you have time for 2 hops,
you might run it like this:

 C:\TradeDangerous\> trade.py --from Chango --credits 20000 -capacity 16 --hops 2

And the output might look like this:

   From Chango via Any to Any with 20000 credits for 2 hops
   IBootis Chango -> Dahan Gateway:
    @ IBootis Chango       Buy 16*Fish (551cr),
    @ LHS3006 WCM          Buy 11*Gallite (1862cr), 4*Lepidolite (400cr), 1*Bauxite (28cr),
    $ Dahan Gateway 20000cr + 6228cr => 26228cr total

This is telling you that it found a trade run starting at Chango. You buy 16 fish and fly to WCM.

At WCM you sell your fish and buy 11 Gallite, 4 lepidolite and 1 bauxite. Then you fly to Dahan
and sell it for a profit of 6,228 credits.

If you leave out the '--from' option, TradeDangerous will check all stations.

    From Any via Any to Any with 20000 credits for 2 hops
    Aulin Enterprise -> Dahan Gateway:
     @ Aulin Enterprise     Buy 6*Combat Stabilisers (2452cr), 7*Bioreducing Lichen (725cr), 3*Biowaste (23cr),
     @ LHS3006 WCM          Buy 11*Indite (1992cr), 4*Lepidolite (400cr), 1*Bauxite (28cr),
     $ Dahan Gateway 20000cr + 8008cr => 28008cr total

It turns out the best route would have started from Aulin and would net us nearly 2,000 credits more.

TD also takes a "--insurance" option which tells it to put some money aside for
insurance payments. This lets you put the actual amount of credits you have without
having to remember to subtract your insurance each time:

Lets say we want to do a half dozen runs.

    C:\TradeDangerous\> trade.py --from Chango --capacity 16 --insurance 4000 --hops 6 --credits 20000


    From Chango via Any to Any with 16000 credits for 6 hops
    IBootis Chango -> Dahan Gateway:
     @ IBootis Chango       Buy 16*Fish (551cr),
     @ Aulin Enterprise     Buy 5*Combat Stabilisers (2452cr), 7*Bioreducing Lichen (725cr), 4*Biowaste (23cr),
     @ LHS3006 WCM          Buy 8*Indite (1992cr), 2*Gallite (1862cr), 4*Lepidolite (400cr), 2*Bauxite (28cr),
     @ Dahan Gateway        Buy 6*Tantalum (3829cr), 10*Aluminium (184cr),
     @ Aulin Enterprise     Buy 4*Performance Enhancers (3037cr), 5*Combat Stabilisers (2452cr), 3*Bioreducing Lichen (725cr), 4*Biowaste (23cr),
     @ LHS3006 WCM          Buy 9*Indite (1992cr), 7*Gallite (1862cr),
     $ Dahan Gateway 20000cr + 20644cr => 40644cr total

In just 6 hops, we made 20k credits, keeping 4k aside incase of disaster.

Command Line Options:

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
     Lets you specify a station that must be between start and final,
     requires that hops be at least 2
     e.g.
       --via Enterprise
       --via Chango

   --unique
     Only show routes which do not visit any station twice

   --hops <number> DEFAULT: 2
     Maximum number of hops (number of cargo pickups)
     e.g.
       --hops 8

 Ship/Trade options:
   --capacity <number> DEFAULT: 4
     Maximum items you can carry on each hop.
 
   --credits <number>
     How many credits to start with
     e.g.
       --credits 20000

   --insurance <number> DEFAULT: 0
     How many credits to hold back for insurance purposes
     e.g.
       --insurance 1000

   --limit <number> DEFAULT: 0
     If set, limits the maximum number of units of any cargo
     item you will buy on any trade hop, incase you want to
     hedge your bets or be a good economy citizen.
     e.g.
       --capacity 16 --limit 8

   --avoid <item name>
     Prevents purchase of the specified item.
     e.g.
       --avoid Gold

   --margin <decimal> DEFAULT: 0.02
     At the end of each hop, reduce the profit by this much (0.02 = 2%),
     to allow a margin of error in the accuracy of prices.
     e.g.
       --margin 0      (no margin)
       --margin 0.01   (1% margin)
 
 Other options:
   --routes <number> DEFAULT: 1
     Shows the top N routes; 

   --debug
     Gives some additional information on what TD is doing while running.


* Why did you choose MS Access, you moron?

I'm a Unix guy but I also like to push myself outside my comfort zone. During my
time at Blizzard I'd actually started to find MS Office 2010 quite bearable, so
I happened to have a free trial of MS Office 365 installed.

I wanted to throw the data together really, really quickly. So I tried Libre Office
Base. The pain was strong in that one. So, for giggles, I decided to see just how
painful it was in Access and 5 minutes later I had a working database that was really
easy to update exactly the way I wanted.

It should be trivial to convert it to a different database.

* That's nice, but I'm a programmer and I want to ...

Yeah, let me stop you there. 

  from tradedb.py import TradeDB, Station, Trade
  tdb = TradeDB("c:\\path\\to\\db")

Whatever it is you want to do, you can do from there.


