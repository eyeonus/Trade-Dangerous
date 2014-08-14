#!/usr/bin/env python
# Calculator layer over TradeDB

import itertools
from math import ceil, floor

from collections import namedtuple

TradeLoad = namedtuple('TradeLoad', [ 'items', 'gainCr', 'costCr', 'units' ])
emptyLoad = TradeLoad([], 0, 0, 0)

TradeHop = namedtuple('TradeHop', [ 'destSys', 'destStn', 'load', 'gainCr', 'jumps', 'ly' ])

class Route(object):
    """ Describes a series of CargoRuns, that is CargoLoads
        between several stations. E.g. Chango -> Gateway -> Enterprise
        """
    def __init__(self, stations, hops, startCr, gainCr, jumps):
        self.route = stations
        self.hops = hops
        self.startCr = startCr
        self.gainCr = gainCr
        self.jumps = jumps

    def plus(self, dst, hop, jumps):
        rvalue = Route(self.route + [dst], self.hops + [hop], self.startCr, self.gainCr + hop[1], self.jumps + [jumps])
        return rvalue

    def __lt__(self, rhs):
        if rhs.gainCr < self.gainCr: # reversed
            return True
        return rhs.gainCr == self.gainCr and len(rhs.jumps) < len(self.jumps)
    def __eq__(self, rhs):
        return self.gainCr == rhs.gainCr and len(self.jumps) == len(rhs.jumps)

    def str(self):
        return "%s -> %s" % (self.route[0], self.route[-1])

    def detail(self, verbose=False):
        src = self.route[0]
        credits = self.startCr
        gainCr = 0
        route = self.route

        str = self.str() + ":\n"
        for i in range(len(route) - 1):
            hop = self.hops[i]
            str += " >-> " if i == 0 else " -+- "
            str += "%-20s Buy" % route[i]
            for item in sorted(hop[0], key=lambda item: item[1] * item[0].gainCr, reverse=True):
                str += " %d*%s," % (item[1], item[0])
            str += "\n"
            if verbose:
                str += "   |   "
                str += " -> ".join([ jump.str() for jump in self.jumps[i] ])
                str += "\n"
            gainCr += hop[1]

        str += " <-< %s gaining %dcr => %dcr total" % (route[-1], gainCr, credits + gainCr)

        return str

class TradeCalc(object):
    """ Container for accessing trade calculations with common properties """
    emptyLoad = TradeLoad([], 0, 0, 0)

    def __init__(self, tdb, debug=False, capacity=4, maxUnits=0, margin=0.02, unique=False, fit=None):
        self.tdb = tdb
        self.debug = debug
        self.capacity = capacity
        self.margin = margin
        self.unique = unique
        self.maxUnits = maxUnits or 0
        self.defaultFit = fit or self.fast_fit

    def brute_force_fit(self, items, credits, capacity, maxUnits):
        """
            Brute-force generation of all possible combinations of items. This is provided
            to make it easy to validate the results of future variants or optimizations of
            the fit algorithm.
        """
        def _fit_combos(offset, cr, cap):
            if offset >= len(items):
                return emptyLoad
            # yield items below us too
            bestLoad = _fit_combos(offset + 1, cr, cap)
            item = items[offset]
            itemCost = item.costCr
            maxQty = min(maxUnits, cap, cr // itemCost)
            if maxQty > 0:
                itemGain = item.gainCr
                for qty in range(maxQty):
                    load = TradeLoad([[item, maxQty]], itemGain * maxQty, itemCost * maxQty, maxQty)
                    subLoad = _fit_combos(offset + 1, cr - load.costCr, cap - load.units)
                    combGain = load.gainCr + subLoad.gainCr
                    if combGain < bestLoad.gainCr:
                        continue
                    combCost, combWeight = load.costCr + subLoad.costCr, load.units + subLoad.units
                    if combGain == bestLoad.gainCr:
                        if combWeight > bestLoad.units:
                            continue
                        if combWeight == bestLoad.units:
                            if combCost >= bestLoad.costCr:
                                continue
                    bestLoad = TradeLoad(load.items+subLoad.items, load.gainCr+subLoad.gainCr, load.costCr+subLoad.costCr, load.units+subLoad.units)
            return bestLoad

        bestLoad = _fit_combos(0, credits, capacity)
        return bestLoad

    def fast_fit(self, items, credits, capacity, maxUnits):
        def _fit_combos(offset, cr, cap):
            for item in items[offset:]:
                itemCostCr = item.costCr
                maxQty = min(maxUnits, cap, cr // itemCostCr)
                if maxQty > 0:
                    loadItems, loadCostCr, loadGainCr = [[item, maxQty]], maxQty * itemCostCr, maxQty * item.gainCr
                    bestGainCr = 0
                    crLeft, capLeft = cr - loadCostCr, cap - maxQty
                    if crLeft > 0 and capLeft > 0:
                        for subLoad in _fit_combos(offset + 1, crLeft, capLeft):
                            if subLoad.gainCr >= bestGainCr:
                                yield TradeLoad(subLoad.items + loadItems, subLoad.gainCr + loadGainCr, subLoad.costCr + loadCostCr, subLoad.units + maxQty)
                                bestGainCr = subLoad.gainCr
                    if not bestGainCr:
                        yield TradeLoad(loadItems, loadGainCr, loadCostCr, maxQty)

        bestLoad = emptyLoad
        for result in _fit_combos(0, credits, capacity):
            if not bestLoad or (result.gainCr > bestLoad.gainCr or (result.gainCr == bestLoad.gainCr and (result.units < bestLoad.units or (result.units == bestLoad.units and result.costCr < bestLoad.costCr)))):
                bestLoad = result

        return bestLoad

    def getBestTrade(self, src, dst, credits, capacity=None, fitFunction=None):
        """ Find the most profitable trade between stations src and dst. """
        if self.debug: print("# %s -> %s with %dcr" % (src, dst, credits))

        if not dst in src.stations:
            raise ValueError("%s does not have a link to %s" % (src, dst))

        capacity = capacity or self.capacity
        if not capacity:
            raise ValueError("zero capacity")

        maxUnits = self.maxUnits or capacity

        items = src.trades[dst.ID]

        # Remove any items with less gain (value) than the cheapest item, or that are outside our budget.
        # This should reduce the search domain for the majority of cases, especially low-end searches.
        if items:
            firstItem = min(items, key=lambda item: item.costCr)
            firstCost, firstGain = firstItem.costCr, firstItem.gainCr
            items = [item for item in items if item.costCr <= credits and (item.gainCr > firstGain or item == firstItem)]
        if not items:
            return emptyLoad

        # Short-circuit: Items are sorted from highest to lowest gain. So if we can fill up with the first
        # item in the list, we don't need to try any other combinations.
        firstItem = items[0]
        if maxUnits >= capacity and firstItem.costCr * capacity <= credits:
            return TradeLoad([[items[0], capacity]], capacity * firstItem.gainCr, capacity * firstItem.costCr, capacity)

        # Go ahead and find the best combination out of what's left.
        fitFunction = fitFunction or self.defaultFit
        return fitFunction(items, credits, capacity, maxUnits)


    def getBestHopFrom(self, src, credits, capacity=None, maxJumps=None, maxLy=None, maxLyPer=None):
        """ Determine the best trade run from a given station. """
        if isinstance(src, str):
            src = self.tdb.getStation(src)
        hop = None
        for (destSys, destStn, jumps, ly, via) in src.getDestinations(maxJumps=maxJumps, maxLy=maxLy, maxLyPer=maxLyPer):
            load = self.getBestTrade(src, destStn, credits, capacity=capacity)
            if load and (not hop or (load.gainCr > hop.gainCr or (load.gainCr == hop.gainCr and len(jumps) < hop.jumps))):
                hop = TradeHop(destSys=destSys, destStn=destStn, load=load.items, gainCr=load.gainCr, jumps=jumps, ly=ly)
        return hop

    def getBestHops(self, routes, credits, restrictTo=None, maxJumps=None, maxLy=None, maxJumpsPer=None, maxLyPer=None):
        """ Given a list of routes, try all available next hops from each
            route. Store the results by destination so that we pick the
            best route-to-point for each destination at each step. If we
            have two routes: A->B->D, A->C->D and A->B->D produces more
            profit, then there is no point in continuing the A->C->D path. """

        bestToDest = {}
        safetyMargin = 1.0 - self.margin
        unique = self.unique
        perJumpLimit = maxJumpsPer if (maxJumpsPer or 0) > 0 else 0
        for route in routes:
            src = route.route[-1]
            if self.debug: print("# route = %s" % route.str())
            startCr = credits + int(route.gainCr * safetyMargin)
            routeJumps = len(route.jumps)
            jumpLimit = perJumpLimit
            if (maxJumps or 0) > 0:
                jumpLimit = min(maxJumps - routeJumps, perJumpLimit) if perJumpLimit > 0 else maxJumps - routeJumps
                if jumpLimit <= 0:
                    if self.debug: print("Jump Limit")
                    continue
            
            for (destSys, destStn, jumps, ly) in src.getDestinations(maxJumps=jumpLimit, maxLy=maxLy, maxLyPer=maxLyPer):
                if self.debug:
                    print("#destSys = %s, destStn = %s, jumps = %s, ly = %s" % (destSys.str(), destStn, "->".join([jump.str() for jump in jumps]), ly))
                if not destStn in src.stations:
                    if self.debug: print("#%s is not in my station list" % destStn)
                    continue
                if restrictTo and destStn != restrictTo:
                    if self.debug: print("#%s doesn't match restrict %s" % (destStn, restrictTo))
                    continue
                if unique and destStn in route.route:
                    if self.debug: print("#%s is already in the list, not unique" % destStn)
                    continue
                trade = self.getBestTrade(src, destStn, startCr)
                if not trade:
                    if self.debug: print("#* No trade")
                    continue
                dstID = destStn.ID
                try:
                    best = bestToDest[dstID]
                    oldRouteGainCr = best[1].gainCr + best[2][1]
                    newRouteGainCr = route.gainCr + trade[1]
                    if oldRouteGainCr >= newRouteGainCr:
                        continue
                except KeyError: pass
                bestToDest[dstID] = [ destStn, route, trade, jumps, ly ]

        result = []
        for (dst, route, trade, jumps, ly) in bestToDest.values():
            result.append(route.plus(dst, trade, jumps))

        return result
