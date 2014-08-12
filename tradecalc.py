#!/usr/bin/env python
# Calculator layer over TradeDB

import itertools
from math import ceil, floor

from collections import namedtuple

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
            for item in hop[0]:
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

    def __init__(self, tdb, debug=False, capacity=4, maxUnits=0, margin=0.02, unique=False):
        self.tdb = tdb
        self.debug = debug
        self.capacity = capacity
        self.margin = margin
        self.unique = unique
        self.maxUnits = maxUnits if maxUnits > 0 else capacity

    def tryCombinations(self, startCr, tradeList, capacity=None):
        startCapacity = capacity if capacity else self.capacity
        maxUnits = self.maxUnits

        firstTrade = tradeList[0]
        if maxUnits >= startCapacity and firstTrade.costCr * startCapacity <= startCr:
            return [ [ [ firstTrade, startCapacity ] ], firstTrade.gainCr * startCapacity ]
        best, bestGainCr, bestCap = [], 0, startCapacity
        tradeItems = len(tradeList)
        for handicap in range(startCapacity):
            for combo in itertools.combinations(tradeList, min(startCapacity, tradeItems)):
                cargo, credits, capacity, gainCr = [], startCr, startCapacity, 0
                myHandicap = handicap
                for trade in combo:
                    itemCostCr = trade.costCr
                    maximum = min(min(capacity, maxUnits), credits // itemCostCr)
                    if maximum > 0:
                        deduction = min(maximum, myHandicap)
                        maximum -= deduction
                        myHandicap -= deduction
                    if maximum > 0:
                        cargo.append([trade, maximum])
                        capacity -= maximum
                        credits -= maximum * itemCostCr
                        gainCr += maximum * trade.gainCr
                        if not capacity or not credits:
                            break
            if gainCr < bestGainCr:
                continue
            if gainCr == bestGainCr and capacity >= bestCap:
                continue
            best, bestGainCr, bestCap = cargo, gainCr, capacity

        return [ best, bestGainCr ]


    def getBestTrade(self, src, dst, startCr, capacity=None):
        if self.debug: print("# %s -> %s with %dcr" % (src, dst, startCr))
        if not dst in src.stations:
            raise ValueError("%s does not have a link to %s" % (src, dst))

        # Get a list of what we can buy
        return self.tryCombinations(startCr, src.trades[dst.ID], capacity)

    def getBestHopFrom(self, src, credits, capacity=None, maxJumps=None, maxLy=None, maxLyPer=None):
        """ Determine the best trade run from a given station. """
        if isinstance(src, str):
            src = self.tdb.getStation(src)
        hop = None
        for (destSys, destStn, jumps, ly, via) in src.getDestinations(maxJumps=maxJumps, maxLy=maxLy, maxLyPer=maxLyPer):
            load = self.getBestTrade(src, destStn, credits, capacity=capacity)
            if load and (not hop or (load[1] > hop.gainCr or (load[1] == hop.gainCr and len(jumps) < hop.jumps))):
                hop = TradeHop(destSys=destSys, destStn=destStn, load=load[0], gainCr=load[1], jumps=jumps, ly=ly)
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
