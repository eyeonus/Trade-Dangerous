# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Modules :: Profit Calculator

"""
TradeCalc provides a class for calculating trade loads, hops or
routes, along with some amount of state.

The intent was for it to carry a larger amount of state but
much of that got moved into TradeEnv, so right now TradeCalc
looks a little odd.

Significant Functions:
    
    Tradecalc.getBestHops
        Finds the best "next hop"s given a set of routes.

Classes:
    
    TradeCalc
        Encapsulates the calculation functions and item-trades,
    
    Route
        Describes a sequence of trade hops.
    
    TradeLoad
        Describe a cargo load to be carried on a hop.
"""

######################################################################
# Imports

from collections import defaultdict
from collections import namedtuple
from .tradedb import System, Station, Trade, describeAge
from .tradedb import Destination
from .tradeexcept import TradeException

import datetime
import locale
import os
from .misc import progress as pbar
import re
import sys
import time

locale.setlocale(locale.LC_ALL, '')

######################################################################
# Exceptions


class BadTimestampError(TradeException):
    
    def __init__(
            self,
            tdb,
            stationID, itemID,
            modified
            ):
        self.station = tdb.stationByID[stationID]
        self.item = tdb.itemByID[itemID]
        self.modified = modified
    
    def __str__(self):
        return (
            "Error loading price data from the local db:\n"
            "{} has a StationItem entry for \"{}\" with an invalid "
            "modified timestamp: '{}'.".format(
                self.station.name(),
                self.item.name(),
                str(self.modified),
            )
        )


class NoHopsError(TradeException):
    pass

######################################################################
# Stuff that passes for classes (but isn't)


class TradeLoad(namedtuple('TradeLoad', (
        'items', 'gainCr', 'costCr', 'units'
        ))):
    """
    Describes the manifest of items to be exchanged in a
    trade.
    
    Public attributes:
        items
            A list of (item,qty) tuples tracking the load.
        gainCr
            The predicted total gain in credits
        costCr
            How much this load was bought for
        units
            Total of all the qty values in the items list.
    """
    
    def __bool__(self):
        return self.units > 0
    
    def __lt__(self, rhs):
        if self.gainCr < rhs.gainCr:
            return True
        if rhs.gainCr < self.gainCr:
            return False
        if self.units < rhs.units:
            return True
        if rhs.units < self.units:
            return False
        return self.costCr < rhs.costCr
    
    @property
    def gpt(self):
        return self.gainCr / self.units if self.units else 0


emptyLoad = TradeLoad((), 0, 0, 0)

######################################################################
# Classes


class Route:
    """
    Describes a series of hops where a TradeLoad is picked up at
    one station, the player travels via 0 or more hyperspace
    jumps and docks at a second station where they unload.
    E.g. 10 Algae + 5 Hydrogen at Station A, jump to System2,
    jump to System3, dock at Station B, sell everything, buy gold,
    jump to system4 and sell everything at Station X.
    """
    __slots__ = ('route', 'hops', 'startCr', 'gainCr', 'jumps', 'score')
    
    def __init__(self, stations, hops, startCr, gainCr, jumps, score):
        assert stations
        self.route = stations
        self.hops = hops
        self.startCr = startCr
        self.gainCr = gainCr
        self.jumps = jumps
        self.score = score
    
    @property
    def firstStation(self):
        """ Returns the first station in the route. """
        return self.route[0]
    
    @property
    def firstSystem(self):
        """ Returns the first system in the route. """
        return self.route[0].system
    
    @property
    def lastStation(self):
        """ Returns the last station in the route. """
        return self.route[-1]
    
    @property
    def lastSystem(self):
        """ Returns the last system in the route. """
        return self.route[-1].system
    
    @property
    def avggpt(self):
        if self.hops:
            return sum(hop.gpt for hop in self.hops) // len(self.hops)
        return 0
    
    @property
    def gpt(self):
        if self.hops:
            return (
                sum(hop.gainCr for hop in self.hops) // 
                sum(hop.units for hop in self.hops)
            )
        return 0
    
    def plus(self, dst, hop, jumps, score):
        """
        Returns a new route describing the sum of this route plus a new hop.
        """
        return Route(
            self.route + (dst,),
            self.hops + (hop,),
            self.startCr,
            self.gainCr + hop[1],
            self.jumps + (jumps,),
            self.score + score,
        )
    
    def __lt__(self, rhs):
        # One route is less than the other if it has a higher score,
        # or the scores are even and the number of jumps are shorter.
        if self.score == rhs.score:
            return len(self.jumps) < len(rhs.jumps)
        return self.score > rhs.score
    
    def __eq__(self, rhs):
        return self.score == rhs.score and len(self.jumps) == len(rhs.jumps)
    
    def text(self, colorize) -> str:
        return "%s -> %s" % (colorize("cyan", self.firstStation.name()), colorize("blue", self.lastStation.name()))
    
    def detail(self, tdenv):
        """
        Return a string describing this route to a given level of detail.
        """
        
        detail, goalSystem = tdenv.detail, tdenv.goalSystem
        
        colorize = tdenv.colorize if tdenv.color else lambda x, y: y
        
        credits = self.startCr + (tdenv.insurance or 0)  # pylint: disable=redefined-builtin
        gainCr = 0
        route = self.route
        
        hops = self.hops
        
        # TODO: Write as a comprehension, just can't wrap my head
        # around it this morning.
        def genSubValues():
            for hop in hops:
                for tr, _ in hop[0]:
                    yield len(tr.name(detail))
        
        longestNameLen = max(genSubValues())
        
        text = self.text(colorize)
        if detail >= 1:
            text += " (score: {:f})".format(self.score)
        text += "\n"
        jumpsFmt = "  Jump {jumps}\n"
        cruiseFmt = "  Supercruise to {stn}\n"
        distFmt = None
        if detail > 1:
            if detail > 2:
                text += self.summary() + "\n"
                if tdenv.maxJumpsPer > 1:
                    distFmt = "  Direct: {dist:0.2f}ly, Trip: {trav:0.2f}ly\n"
            hopFmt = (
                "  Load from "
                +colorize("cyan", "{station}") + 
                ":\n{purchases}"
            )
            hopStepFmt = (
                colorize("lightYellow", "     {qty:>4}") + 
                " x "
                +colorize("yellow", "{item:<{longestName}} ") + 
                "{eacost:>8n}cr vs {easell:>8n}cr, "
                "{age}"
            )
            if detail > 2:
                hopStepFmt += ", total: {ttlcost:>10n}cr"
            hopStepFmt += "\n"
            if not tdenv.summary:
                dockFmt = (
                    "  Unload at "
                    +colorize("lightBlue", "{station}") + 
                    " => Gain {gain:n}cr "
                    "({tongain:n}cr/ton) => {credits:n}cr\n"
                )
            else:
                jumpsFmt = re.sub("  ", "    ", jumpsFmt, re.M)
                cruiseFmt = re.sub("  ", "    ", cruiseFmt, re.M)
                if distFmt:
                    distFmt = re.sub("  ", "    ", distFmt, re.M)
                hopFmt = "\n" + hopFmt
                dockFmt = "    Expect to gain {gain:n}cr ({tongain:n}cr/ton)\n"
            footer = '  ' + '-' * 76 + "\n"
            endFmt = (
                "Finish at "
                +colorize("blue", "{station} ") + 
                "gaining {gain:n}cr ({tongain:n}cr/ton) "
                "=> est {credits:n}cr total\n"
            )
        elif detail:
            hopFmt = (
                "  Load from "
                +colorize("cyan", "{station}") + 
                ":{purchases}\n"
            )
            hopStepFmt = (
                colorize("lightYellow", " {qty}") + 
                " x "
                +colorize("yellow", "{item}") + 
                " (@{eacost}cr),")
            footer = None
            dockFmt = (
                "  Dock at " + 
                colorize("lightBlue", "{station}\n")
            )
            endFmt = (
                "  Finish "
                +colorize("blue", "{station} ") + 
                "+ {gain:n}cr ({tongain:n}cr/ton)"
                "=> {credits:n}cr\n"
            )
        else:
            hopFmt = colorize("cyan", "  {station}:{purchases}\n")
            hopStepFmt = (
                colorize("lightYellow", " {qty}") + 
                " x "
                +colorize("yellow", "{item}") + 
                ","
            )
            footer = None
            dockFmt = None
            endFmt = (
                colorize("blue", "  {station}") + 
                " +{gain:n}cr ({tongain:n}/ton)"
            )
        
        def jumpList(jumps):
            text, last = "", None
            travelled = 0.
            for jump in jumps:
                if last:
                    dist = last.distanceTo(jump)
                    if dist:
                        if tdenv.detail:
                            text += ", {:.2f}ly -> ".format(dist)
                        else:
                            text += " -> "
                    else:
                        text += " >>> "
                    travelled += dist
                text += jump.name()
                last = jump
            return travelled, text
        
        if detail > 1:
            
            def decorateStation(station):
                details = []
                if station.lsFromStar:
                    details.append(station.distFromStar(True))
                if station.blackMarket != '?':
                    details.append('BMk:' + station.blackMarket)
                if station.maxPadSize != '?':
                    details.append('Pad:' + station.maxPadSize)
                if station.planetary != '?':
                    details.append('Plt:' + station.planetary)
                if station.fleet != '?':
                    details.append('Flc:' + station.fleet)
                if station.odyssey != '?':
                    details.append('Ody:' + station.odyssey)
                if station.shipyard != '?':
                    details.append('Shp:' + station.shipyard)
                if station.outfitting != '?':
                    details.append('Out:' + station.outfitting)
                if station.refuel != '?':
                    details.append('Ref:' + station.refuel)
                details = "{} ({})".format(
                    station.name(),
                    ", ".join(details or ["no details"])
                )
                return details
        
        else:
            
            def decorateStation(station):
                return station.name()
        
        if detail and goalSystem:
            
            def goalDistance(station):
                return " [Distance to {}: {:.2f} ly]\n".format(
                    goalSystem.name(),
                    station.system.distanceTo(goalSystem),
                )
        
        else:
            
            def goalDistance(station):
                return ""
        
        for i, hop in enumerate(hops):
            hopGainCr, hopTonnes = hop[1], 0
            purchases = ""
            for (trade, qty) in sorted(
                    hop[0],
                    key = lambda tradeOpt: tradeOpt[1] * tradeOpt[0].gainCr,
                    reverse = True
                    ):
                # Are they within 30 minutes of each other?
                if abs(trade.srcAge - trade.dstAge) <= (30 * 60):
                    age = max(trade.srcAge, trade.dstAge)
                    age = describeAge(age)
                else:
                    srcAge = describeAge(trade.srcAge)
                    dstAge = describeAge(trade.dstAge)
                    age = "{} vs {}".format(srcAge, dstAge)
                purchases += hopStepFmt.format(
                    qty = qty, item = trade.name(detail),
                    eacost = trade.costCr,
                    easell = trade.costCr + trade.gainCr,
                    ttlcost = trade.costCr * qty,
                    longestName = longestNameLen,
                    age = age,
                )
                hopTonnes += qty
            text += goalDistance(route[i])
            text += hopFmt.format(
                station = decorateStation(route[i]),
                purchases = purchases
            )
            if tdenv.showJumps and jumpsFmt and self.jumps[i]:
                startStn = route[i]
                endStn = route[i + 1]
                if startStn.system is not endStn.system:
                    fmt = jumpsFmt
                    travelled, jumps = jumpList(self.jumps[i])
                else:
                    fmt = cruiseFmt
                    travelled, jumps = 0., "{start} >>> {stop}".format(
                        start = startStn.name(), stop = endStn.name()
                    )
                text += fmt.format(
                    jumps = jumps,
                    gain = hopGainCr,
                    tongain = hopGainCr / hopTonnes,
                    credits = credits + gainCr + hopGainCr,
                    stn = route[i + 1].dbname
                )
                if travelled and distFmt and len(self.jumps[i]) > 2:
                    text += distFmt.format(
                        dist = startStn.system.distanceTo(endStn.system),
                        trav = travelled,
                    )
            if dockFmt:
                stn = route[i + 1]
                text += dockFmt.format(
                    station = decorateStation(stn),
                    gain = hopGainCr,
                    tongain = hopGainCr / hopTonnes,
                    credits = credits + gainCr + hopGainCr
                )
            
            gainCr += hopGainCr
        
        lastStation = self.lastStation
        if lastStation.system is not goalSystem:
            text += goalDistance(lastStation)
        text += footer or ""
        text += endFmt.format(
            station = decorateStation(lastStation),
            gain = gainCr,
            credits = credits + gainCr,
            tongain = self.gpt
        )
        
        return text
    
    def summary(self):
        """
        Returns a string giving a short summary of this route.
        """
        
        credits, hops, jumps = self.startCr, self.hops, self.jumps  # pylint: disable=redefined-builtin
        ttlGainCr = sum(hop[1] for hop in hops)
        numJumps = sum(
            len(hopJumps) - 1
            for hopJumps in jumps
            if hopJumps  # don't include in-system hops
        )
        return (
            "Start CR: {start:10n}\n"
            "Hops    : {hops:10n}\n"
            "Jumps   : {jumps:10n}\n"
            "Gain CR : {gain:10n}\n"
            "Gain/Hop: {hopgain:10n}\n"
            "Final CR: {final:10n}\n" . format(
                start = credits,
                hops = len(hops),
                jumps = numJumps,
                gain = ttlGainCr,
                hopgain = ttlGainCr // len(hops),
                final = credits + ttlGainCr
            )
        )


class TradeCalc:
    """
    Container for accessing trade calculations with common properties.
    """
    
    def __init__(self, tdb, tdenv = None, fit = None, items = None):
        """
        Constructs the TradeCalc object and loads sell/buy data.
        
        Parameters:
            tdb
                The TradeDB() object to use to access data,
            tdenv [optional]
                TradeEnv() that controls behavior,
            fit [optional]
                Lets you specify a fitting function,
            items [optional]
                Iterable [itemID or Item()] that restricts loading,
        
        TradeEnv options:
            tdenv.avoidItems
                Iterable of [Item] that prevents items being loaded
            tdenv.maxAge
                Maximum age in days of data that gets loaded
            tdenv.supply
                Require at least this much supply to load an item
            tdenv.demand
                Require at least this much demand to load an item
        """
        if not tdenv:
            tdenv = tdb.tdenv
        self.tdb = tdb
        self.tdenv = tdenv
        self.defaultFit = fit or self.simpleFit
        if "BRUTE_FIT" in os.environ:
            self.defaultFit = self.bruteForceFit
        minSupply = self.tdenv.supply or 0
        minDemand = self.tdenv.demand or 0
        
        db = tdb.getDB()
        
        wheres, binds = [], []
        if tdenv.maxAge:
            maxDays = datetime.timedelta(days = tdenv.maxAge)
            cutoff = datetime.datetime.now() - maxDays
            wheres.append("(modified >= ?)")
            binds.append(str(cutoff.replace(microsecond = 0)))
        
        if tdenv.avoidItems or items:
            avoidItemIDs = set(item.ID for item in tdenv.avoidItems)
            loadItems = items or tdb.itemByID.values()
            loadItemSet = set()
            for item in loadItems:
                ID = item if isinstance(item, int) else item.ID
                if ID not in avoidItemIDs:
                    loadItemSet.add(str(ID))
            if not loadItemSet:
                raise TradeException("No items to load.")
            load_ids = ",".join(str(ID) for ID in loadItemSet)
            wheres.append(f"(item_id IN ({load_ids}))")
        
        demand = self.stationsBuying = defaultdict(list)
        supply = self.stationsSelling = defaultdict(list)
        
        whereClause = " AND ".join(wheres) or "1"
        
        lastStnID = 0
        dmdCount, supCount = 0, 0
        stmt = """
                SELECT  station_id, item_id,
                        strftime('%s', modified),
                        demand_price, demand_units, demand_level,
                        supply_price, supply_units, supply_level
                  FROM  StationItem
                 WHERE  {where}
        """.format(where = whereClause)
        tdenv.DEBUG1("TradeCalc loading StationItem values")
        tdenv.DEBUG2("sql: {}, binds: {}", stmt, binds)
        cur = db.execute(stmt, binds)
        now = int(time.time())
        for (stnID, itmID,
                timestamp,
                dmdCr, dmdUnits, dmdLevel,
                supCr, supUnits, supLevel) in cur:
            if stnID != lastStnID:
                dmdAppend = demand[stnID].append
                supAppend = supply[stnID].append
                lastStnID = stnID
            try:
                ageS = now - int(timestamp)
            except TypeError:
                raise BadTimestampError(
                    self.tdb,
                    stnID, itmID, timestamp
                ) from None
            if dmdCr > 0:
                if not minDemand or dmdUnits >= minDemand:
                    dmdAppend((itmID, dmdCr, dmdUnits, dmdLevel, ageS))
                    dmdCount += 1
            if supCr > 0 and supUnits:
                if not minSupply or supUnits >= minSupply:
                    supAppend((itmID, supCr, supUnits, supLevel, ageS))
                    supCount += 1
        
        tdenv.DEBUG0("Loaded {} buys, {} sells".format(dmdCount, supCount))
    
    def bruteForceFit(self, items, credits, capacity, maxUnits):  # pylint: disable=redefined-builtin
        """
        Brute-force generation of all possible combinations of items.
        This is provided to make it easy to validate the results of future
        variants or optimizations of the fit algorithm.
        """
        
        def _fitCombos(offset, cr, cap, level = 1):
            if cr <= 0 or cap <= 0:
                return emptyLoad
            while True:
                if offset >= len(items):
                    return emptyLoad
                item = items[offset]
                offset += 1
                
                itemCost = item.costCr
                maxQty = min(maxUnits, cap, cr // itemCost)
                
                if item.supply < maxQty and item.supply > 0:  # -1 = unknown
                    maxQty = min(maxQty, item.supply)
                
                if maxQty > 0:
                    break
            
            # find items that don't include us
            bestLoad = _fitCombos(offset, cr, cap, level + 1)
            itemGain = item.gainCr
            
            for qty in range(1, maxQty + 1):
                loadGain, loadCost = itemGain * qty, itemCost * qty
                load = TradeLoad(((item, qty),), loadGain, loadCost, qty)
                subLoad = _fitCombos(
                    offset, cr - loadCost, cap - qty, level + 1
                )
                combGain = loadGain + subLoad.gainCr
                if combGain < bestLoad.gainCr:
                    continue
                combCost = loadCost + subLoad.costCr
                combUnits = qty + subLoad.units
                if combGain == bestLoad.gainCr:
                    if combUnits > bestLoad.units:
                        continue
                    if combUnits == bestLoad.units:
                        if combCost >= bestLoad.costCr:
                            continue
                bestLoad = TradeLoad(
                    load.items + subLoad.items,
                    combGain, combCost, combUnits
                )
            
            return bestLoad
        
        return _fitCombos(0, credits, capacity)
    
    def fastFit(self, items, credits, capacity, maxUnits):  # pylint: disable=redefined-builtin
        """
            Best load calculator using a recursive knapsack-like
            algorithm to find multiple loads and return the best.
            [eyeonus] Left in for the masochists, as this becomes
            horribly slow at stations with many items for sale.
            As in iooks-like-the-program-has-frozen slow.
        """
        
        def _fitCombos(offset, cr, cap):
            """
                Starting from offset, consider a scenario where we
                would purchase the maximum number of each item
                given the cr+cap limitations. Then, assuming that
                load, solve for the remaining cr+cap from the next
                value of offset.
                
                The "best fit" is not always the most profitable,
                so we yield all the results and leave the caller
                to determine which is actually most profitable.
            """
            
            bestGainCr = -1
            bestItem = None
            bestQty = 0
            bestCostCr = 0
            bestSub = None
            
            qtyCeil = min(maxUnits, cap)
            
            for iNo in range(offset, len(items)):
                item = items[iNo]
                itemCostCr = item.costCr
                maxQty = min(qtyCeil, cr // itemCostCr)
                
                if maxQty <= 0:
                    continue
                
                supply = item.supply
                if supply <= 0:
                    continue
                
                maxQty = min(maxQty, supply)
                
                itemGainCr = item.gainCr
                if maxQty == cap:
                    # full load
                    gain = itemGainCr * maxQty
                    if gain > bestGainCr:
                        cost = itemCostCr * maxQty
                        # list is sorted by gain DESC, cost ASC
                        bestGainCr = gain
                        bestItem = item
                        bestQty = maxQty
                        bestCostCr = cost
                        bestSub = None
                    break
                
                loadCostCr = maxQty * itemCostCr
                loadGainCr = maxQty * itemGainCr
                if loadGainCr > bestGainCr:
                    bestGainCr = loadGainCr
                    bestCostCr = loadCostCr
                    bestItem = item
                    bestQty = maxQty
                    bestSub = None
                
                crLeft, capLeft = cr - loadCostCr, cap - maxQty
                if crLeft > 0 and capLeft > 0:
                    # Solve for the remaining credits and capacity with what
                    # is left in items after the item we just checked.
                    subLoad = _fitCombos(iNo + 1, crLeft, capLeft)
                    if subLoad is emptyLoad:
                        continue
                    ttlGain = loadGainCr + subLoad.gainCr
                    if ttlGain < bestGainCr:
                        continue
                    ttlCost = loadCostCr + subLoad.costCr
                    if ttlGain == bestGainCr and ttlCost >= bestCostCr:
                        continue
                    bestGainCr = ttlGain
                    bestItem = item
                    bestQty = maxQty
                    bestCostCr = ttlCost
                    bestSub = subLoad
            
            if not bestItem:
                return emptyLoad
            
            bestLoad = ((bestItem, bestQty),)
            if bestSub:
                bestLoad = bestLoad + bestSub.items
                bestQty += bestSub.units
            return TradeLoad(bestLoad, bestGainCr, bestCostCr, bestQty)
        
        return _fitCombos(0, credits, capacity)
    
    # Mark's test run, to spare searching back through the forum posts for it.
    # python trade.py run --fr="Orang/Bessel Gateway" --cap=720 --cr=11b --ly=24.73 --empty=37.61 --pad=L --hops=2 --jum=3 --loop --summary -vv --progress
    def simpleFit(self, items, credits, capacity, maxUnits):  # pylint: disable=redefined-builtin
        """
        Simplistic load calculator:
        (The item list is sorted with highest profit margin items in front.)
        Step 1: Fill hold with as much of item1 as possible based on the limiting
                factors of hold size, supply amount, and available credits.
        
        Step 2: If there is space in the hold and money available, repeat Step 1
                with item2, item3, etc. until either the hold is filled
                or the commander is too poor to buy more.
        
        When amount of credits isn't a limiting factor, this should produce
        the most profitable route ~99.7% of the time, and still be very
        close to the most profitable the rest of the time.
        (Very close = not enough less profit that anyone should care,
        especially since this thing doesn't suffer slowdowns like fastFit.)
        """
        
        n = 0
        load = ()
        gainCr = 0
        costCr = 0
        qty = 0
        while n < len(items) and credits > 0 and capacity > 0:
            qtyCeil = min(maxUnits, capacity)
            
            item = items[n]
            maxQty = min(qtyCeil, credits // item.costCr)
            
            if maxQty > 0 and item.supply > 0:
                maxQty = min(maxQty, item.supply)
                
                loadCostCr = maxQty * item.costCr
                loadGainCr = maxQty * item.gainCr
                
                load = load + ((item, maxQty),)
                qty += maxQty
                capacity -= maxQty
                
                gainCr += loadGainCr
                costCr += loadCostCr
                credits -= loadCostCr
            
            n += 1
        
        return TradeLoad(load, gainCr, costCr, qty)
    
    def getTrades(self, srcStation, dstStation, srcSelling = None):
        """
        Returns the most profitable trading options from
        one station to another (uni-directional).
        """
        if not srcSelling:
            srcSelling = self.stationsSelling.get(srcStation.ID, None)
            if not srcSelling:
                return None
        dstBuying = self.stationsBuying.get(dstStation.ID, None)
        if not dstBuying:
            return None
        
        trading = []
        itemIdx = self.tdb.itemByID
        minGainCr = max(1, self.tdenv.minGainPerTon or 1)
        maxGainCr = max(minGainCr, self.tdenv.maxGainPerTon or sys.maxsize)
        getBuy = {buy[0]: buy for buy in dstBuying}.get
        addTrade = trading.append
        for sell in srcSelling:  # should be the smaller list
            buy = getBuy(sell[0], None)
            if buy:
                gainCr = buy[1] - sell[1]
                if minGainCr <= gainCr <= maxGainCr:
                    addTrade(Trade(
                        itemIdx[sell[0]],
                        sell[1], gainCr,
                        sell[2], sell[3],
                        buy[2], buy[3],
                        sell[4], buy[4],
                    ))
        
        # SORT BY profit DESC, cost ASC
        # So if two items have the same profit, the cheapest will come first.
        trading.sort(key = lambda trade: trade.costCr)
        trading.sort(key = lambda trade: trade.gainCr, reverse = True)
        
        return trading
    
    def getBestHops(self, routes, restrictTo = None):
        """
        Given a list of routes, try all available next hops from each
        route.
        
        Store the results by destination so that we pick the
        best route-to-point for each destination at each step.
        
        If we have two routes: A->B->D, A->C->D and A->B->D produces
        more profit, there's no point continuing the A->C->D path.
        """
        
        tdb = self.tdb
        tdenv = self.tdenv
        avoidPlaces = getattr(tdenv, 'avoidPlaces', None) or ()
        assert not restrictTo or isinstance(restrictTo, set)
        maxJumpsPer = tdenv.maxJumpsPer
        maxLyPer = tdenv.maxLyPer
        maxPadSize = tdenv.padSize
        planetary = tdenv.planetary
        fleet = tdenv.fleet
        odyssey = tdenv.odyssey
        noPlanet = tdenv.noPlanet
        maxLsFromStar = tdenv.maxLs or float('inf')
        reqBlackMarket = getattr(tdenv, 'blackMarket', False) or False
        maxAge = getattr(tdenv, 'maxAge') or 0
        credits = tdenv.credits - (getattr(tdenv, 'insurance', 0) or 0)  # pylint: disable=redefined-builtin
        fitFunction = self.defaultFit
        capacity = tdenv.capacity
        maxUnits = getattr(tdenv, 'limit') or capacity
        
        bestToDest = {}
        safetyMargin = 1.0 - tdenv.margin
        unique = tdenv.unique
        loopInt = getattr(tdenv, 'loopInt', 0) or None
        
        # Penalty is expressed as percentage, reduce it to a multiplier
        if tdenv.lsPenalty:
            lsPenalty = max(min(tdenv.lsPenalty / 100, 1), 0)
        else:
            lsPenalty = 0
        
        goalSystem = tdenv.goalSystem
        uniquePath = None
        
        restrictStations = set()
        if restrictTo:
            for place in restrictTo:
                if isinstance(place, Station):
                    restrictStations.add(place)
                elif isinstance(place, System) and place.stations:
                    restrictStations.update(place.stations)
        
        # Are we doing direct routes?
        if tdenv.direct:
            if goalSystem and not restrictTo:
                restrictTo = (goalSystem,)
                restrictStations = set(goalSystem.stations)
            if avoidPlaces:
                restrictStations = set(
                    stn for stn in restrictStations
                    if stn not in avoidPlaces and
                        stn.system not in avoidPlaces
                )
            
            def station_iterator(srcStation):
                srcSys = srcStation.system
                srcDist = srcSys.distanceTo
                for stn in restrictStations:
                    stnSys = stn.system
                    yield Destination(
                        stnSys, stn,
                        (srcSys, stnSys),
                        srcDist(stnSys)
                    )
        
        else:
            getDestinations = tdb.getDestinations
            
            def station_iterator(srcStation):
                yield from getDestinations(
                    srcStation,
                    maxJumps = maxJumpsPer,
                    maxLyPer = maxLyPer,
                    avoidPlaces = avoidPlaces,
                    maxPadSize = maxPadSize,
                    maxLsFromStar = maxLsFromStar,
                    noPlanet = noPlanet,
                    planetary = planetary,
                    fleet = fleet,
                    odyssey = odyssey,
                )
        
        with pbar.Progress(max_value=len(routes), width=25, show=tdenv.progress) as prog:
            connections = 0
            getSelling = self.stationsSelling.get
            for route_no, route in enumerate(routes):
                prog.increment(progress=route_no)
                tdenv.DEBUG1("Route = {}", route.text(lambda x, y: y))
                
                srcStation = route.lastStation
                startCr = credits + int(route.gainCr * safetyMargin)
                
                srcSelling = getSelling(srcStation.ID, None)
                srcSelling = tuple(
                    values for values in srcSelling
                    if values[1] <= startCr
                )
                if not srcSelling:
                    tdenv.DEBUG1("Nothing sold/affordable - next.")
                    continue
                
                if goalSystem:
                    origSystem = route.firstSystem
                    srcSystem = srcStation.system
                    srcDistTo = srcSystem.distanceTo
                    goalDistTo = goalSystem.distanceTo
                    origDistTo = origSystem.distanceTo
                    srcGoalDist = srcDistTo(goalSystem)
                    srcOrigDist = srcDistTo(origSystem)
                    origGoalDist = origDistTo(goalSystem)
                
                if unique:
                    uniquePath = route.route
                elif loopInt:
                    pos_from_end = 0 - loopInt
                    uniquePath = route.route[pos_from_end:-1]
                
                stations = (d for d in station_iterator(srcStation)
                if (d.station != srcStation) and
                    (d.station.blackMarket == 'Y' if reqBlackMarket else True) and
                    (d.station not in uniquePath if uniquePath else True) and
                    (d.station in restrictStations if restrictStations else True) and
                    (d.station.dataAge and d.station.dataAge <= maxAge if maxAge else True) and
                    (((d.system is not srcSystem) if bool(tdenv.unique) else (d.system is goalSystem or d.distLy < srcGoalDist)) if goalSystem else True)
                )
                
                if tdenv.debug >= 1:
                    
                    def annotate(dest):
                        tdenv.DEBUG1(
                            "destSys {}, destStn {}, jumps {}, distLy {}",
                            dest.system.dbname,
                            dest.station.dbname,
                            "->".join(jump.text() for jump in dest.via),
                            dest.distLy
                        )
                        return True
                    
                    stations = (d for d in stations if annotate(d))
                
                for dest in stations:
                    dstStation = dest.station
                    
                    connections += 1
                    items = self.getTrades(srcStation, dstStation, srcSelling)
                    if not items:
                        continue
                    trade = fitFunction(items, startCr, capacity, maxUnits)
                    
                    multiplier = 1.0
                    # Calculate total K-lightseconds supercruise time.
                    # This will amortize for the start/end stations
                    dstSys = dest.system
                    if goalSystem and dstSys is not goalSystem:
                        dstGoalDist = goalDistTo(dstSys)
                        # Biggest reward for shortening distance to goal
                        score = 5000 * origGoalDist / dstGoalDist
                        # bias towards bigger reductions
                        score += 50 * srcGoalDist / dstGoalDist
                        # discourage moving back towards origin
                        if dstSys is not origSystem:
                            score += 10 * (origDistTo(dstSys) - srcOrigDist)
                        # Gain per unit pays a small part
                        score += (trade.gainCr / trade.units) / 25
                    else:
                        score = trade.gainCr
                    if lsPenalty:
                        # [kfsone] Only want 1dp
                        
                        cruiseKls = int(dstStation.lsFromStar / 100) / 10
                        # Produce a curve that favors distances under 1kls
                        # positively, starts to penalize distances over 1k,
                        # and after 4kls starts to penalize aggressively
                        # http://goo.gl/Otj2XP
                        
                        # [eyeonus] As aadler pointed out, this goes into negative
                        # numbers, which causes problems.
                        # penalty = ((cruiseKls ** 2) - cruiseKls) / 3
                        # penalty *= lsPenalty
                        # multiplier *= (1 - penalty)
                        
                        # [eyeonus]:
                        # (Keep in mind all this ignores values of x<0.)
                        # The sigmoid: (1-(25(x-1))/(1+abs(25(x-1))))/4
                        # ranges between 0.5 and 0 with a drop around x=1,
                        # which makes it great for giving a boost to distances < 1Kls.
                        #
                        # The sigmoid: (-1-(50(x-4))/(1+abs(50(x-4))))/4
                        # ranges between 0 and -0.5 with a drop around x=4,
                        # making it great for penalizing distances > 4Kls.
                        #
                        # The curve: (-1+1/(x+1)^((x+1)/4))/2
                        # ranges between 0 and -0.5 in a smooth arc,
                        # which will be used for making distances
                        # closer to 4Kls get a slightly higher penalty
                        # then distances closer to 1Kls.
                        #
                        # Adding the three together creates a doubly-kinked curve
                        # that ranges from ~0.5 to -1.0, with drops around x=1 and x=4,
                        # which closely matches ksfone's intention without going into
                        # negative numbers and causing problems when we add it to
                        # the multiplier variable. ( 1 + -1 = 0 )
                        #
                        # You can see a graph of the formula here:
                        # https://goo.gl/sn1PqQ
                        # NOTE: The black curve is at a penalty of 0%,
                        # the red curve at a penalty of 100%, with intermediates at
                        # 25%, 50%, and 75%.
                        # The other colored lines show the penalty curves individually
                        # and the teal composite of all three.
                        
                        def sigmoid(x):
                            return x / (1 + abs(x))
                        
                        boost = (1 - sigmoid(25 * (cruiseKls - 1))) / 4
                        drop = (-1 - sigmoid(50 * (cruiseKls - 4))) / 4
                        try:
                            penalty = (-1 + 1 / (cruiseKls + 1) ** ((cruiseKls + 1) / 4)) / 2
                        except OverflowError:
                            penalty = -0.5
                        
                        multiplier += (penalty + boost + drop) * lsPenalty
                    
                    score *= multiplier
                    
                    dstID = dstStation.ID
                    try:
                        # See if there is already a candidate for this destination
                        btd = bestToDest[dstID]
                    except KeyError:
                        # No existing candidate, we win by default
                        pass
                    else:
                        bestRoute = btd[1]
                        bestScore = btd[5]
                        # Check if it is a better option than we just produced
                        bestTradeScore = bestRoute.score + bestScore
                        newTradeScore = route.score + score
                        if bestTradeScore > newTradeScore:
                            continue
                        if bestTradeScore == newTradeScore:
                            bestLy = btd[4]
                            if bestLy <= dest.distLy:
                                continue
                    
                    bestToDest[dstID] = (
                        dstStation, route, trade, dest.via, dest.distLy, score
                    )
        
        if connections == 0:
            raise NoHopsError(
                "No destinations could be reached within the constraints."
            )
        
        result = []
        for (dst, route, trade, jumps, _, score) in bestToDest.values():
            result.append(route.plus(dst, trade, jumps, score))
        
        return result
