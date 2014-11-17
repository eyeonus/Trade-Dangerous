# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Profit Calculator
#
#  Provides functions for calculating the most profitable trades and
#  trade runs based based on a set of encapsulated criteria.

######################################################################
# Imports

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

import math
import locale
locale.setlocale(locale.LC_ALL, '')

######################################################################
# Stuff that passes for classes (but isn't)

from tradedb import System, Station
from collections import namedtuple

class TradeLoad(namedtuple('TradeLoad', [
                'items', 'gainCr', 'costCr', 'units'
                ])):
    def __bool__(self):
        return self.units > 0

emptyLoad = TradeLoad([], 0, 0, 0)

class TradeHop(namedtuple('TradeHop', [
                'destSys', 'destStn', 'load', 'gainCr', 'jumps', 'ly'
                ])):
    pass

######################################################################
# Classes

class Route(object):
    """
        Describes a series of CargoRuns, that is CargoLoads
        between several stations. E.g. Chango -> Gateway -> Enterprise
    """
    __slots__ = ('route', 'hops', 'startCr', 'gainCr', 'jumps')

    def __init__(self, stations, hops, startCr, gainCr, jumps):
        self.route = stations
        self.hops = hops
        self.startCr = startCr
        self.gainCr = gainCr
        self.jumps = jumps


    def plus(self, dst, hop, jumps):
        """
            Returns a new route describing the sum of this route plus a new hop.
        """
        return Route(self.route + [dst], self.hops + [hop], self.startCr, self.gainCr + hop[1], self.jumps + [jumps])


    def __lt__(self, rhs):
        if rhs.gainCr < self.gainCr: # reversed
            return True
        return rhs.gainCr == self.gainCr and len(rhs.jumps) < len(self.jumps)


    def __eq__(self, rhs):
        return self.gainCr == rhs.gainCr and len(self.jumps) == len(rhs.jumps)


    def str(self):
        return "%s -> %s" % (self.route[0].name(), self.route[-1].name())


    def detail(self, detail=0):
        """
            Return a string describing this route to a given level of detail.
        """

        credits = self.startCr
        gainCr = 0
        route = self.route

        hops = [
                hop for hop in self.hops[0:len(self.hops)]
            ]

        # TODO: Write as a comprehension, just can't wrap my head
        # around it this morning.
        def genSubValues(key):
            for hop in hops:
                for (tr, qty) in hop[0]:
                    yield key(tr)
        longestNameLen = max(genSubValues(key=lambda tr: len(tr.name())))

        text = self.str() + ":\n"
        if detail > 1:
            if detail > 2:
                text += self.summary() + "\n"
            hopFmt = "  Load from {station}:\n{purchases}"
            hopStepFmt = ("     {qty:>4} x {item:<{longestName}}"
                            " {eacost:>10n}cr each, {ttlcost:>10n}cr total\n")
            jumpsFmt = ("  Jump {jumps} => "
                        "Gain {gain:n}cr "
                        "({tongain:n}cr/ton) "
                        "=> {credits:n}cr\n")
            footer = '  ' + '-' * 76 + "\n"
            endFmt = ("  Finish at {station} "
                        "gaining {gain:n}cr "
                        "=> est {credits:n}cr total\n")
        elif detail:
            hopFmt = "  Load from {station}:{purchases}\n"
            hopStepFmt = " {qty} x {item} (@{eacost}cr),"
            jumpsFmt = "  Jump {jumps}\n"
            footer = None
            endFmt = ("  Finish {station} "
                        "+ {gain:n}cr "
                        "=> {credits:n}cr\n")
        else:
            hopFmt = "  {station}:{purchases}\n"
            hopStepFmt = " {qty} x {item},"
            jumpsFmt = None
            footer = None
            endFmt = "  {station} +{gain:n}cr"

        for i, hop in enumerate(hops):
            hopGainCr, hopTonnes = hop[1], 0
            purchases = ""
            for (trade, qty) in sorted(hop[0],
                                        key=lambda tradeOpt:
                                            tradeOpt[1] * tradeOpt[0].gainCr,
                                        reverse=True):
                purchases += hopStepFmt.format(
                                    qty=qty, item=trade.name(),
                                    eacost=trade.costCr,
                                    ttlcost=trade.costCr*qty,
                                    longestName=longestNameLen)
                hopTonnes += qty
            text += hopFmt.format(station=route[i].name(), purchases=purchases)
            if jumpsFmt:
                jumps = ' -> '.join([ jump.name() for jump in self.jumps[i] ])
                text += jumpsFmt.format(
                            jumps=jumps,
                            gain=hopGainCr,
                            tongain=hopGainCr / hopTonnes,
                            credits=credits + gainCr + hopGainCr
                            )

            gainCr += hopGainCr

        text += footer or ""
        text += endFmt.format(
                        station=route[-1].name(),
                        gain=gainCr,
                        credits=credits + gainCr
                        )

        return text


    def summary(self):
        """
            Returns a string giving a short summary of this route.
        """

        credits, hops, jumps = self.startCr, self.hops, self.jumps
        ttlGainCr = sum([hop[1] for hop in hops])
        numJumps = sum([len(hopJumps)-1 for hopJumps in jumps])
        return (
            "Start CR: {start:10n}\n"
            "Hops    : {hops:10n}\n"
            "Jumps   : {jumps:10n}\n"
            "Gain CR : {gain:10n}\n"
            "Gain/Hop: {hopgain:10n}\n"
            "Final CR: {final:10n}\n" . format(
                    start=credits,
                    hops=len(hops),
                    jumps=numJumps,
                    gain=ttlGainCr,
                    hopgain=ttlGainCr / len(hops),
                    final=credits + ttlGainCr
                )
            )


class TradeCalc(object):
    """
        Container for accessing trade calculations with common properties.
    """

    def __init__(self, tdb, tdenv, fit=None):
        self.tdb = tdb
        self.tdenv = tdenv
        self.defaultFit = fit or self.fastFit


    def bruteForceFit(self, items, credits, capacity, maxUnits):
        """
            Brute-force generation of all possible combinations of items. This is provided
            to make it easy to validate the results of future variants or optimizations of
            the fit algorithm.
        """
        def _fitCombos(offset, cr, cap):
            if offset >= len(items):
                return emptyLoad
            # yield items below us too
            bestLoad = _fitCombos(offset + 1, cr, cap)
            item = items[offset]
            itemCost = item.costCr
            maxQty = min(maxUnits, cap, cr // itemCost)

            # Adjust for age for "M"/"H" items with low units.
            if item.stock < maxQty and item.stock > 0:  # -1 = unknown
                level = item.stockLevel
                if level > 1:
                    # Assume 2 units per 10 minutes for high,
                    # 1 unit per 15 minutes for medium
                    units = level - 1
                    interval = (30 / level) * 60
                    speculativeRecovery = units * math.floor(item.srcAge / interval)
                else:
                    # Low / Unknown - don't try to guess
                    speculativeRecovery = 0
                maxQty = min(maxQty, item.stock + speculativeRecovery)

            if maxQty > 0:
                itemGain = item.gainCr
                for qty in range(maxQty):
                    load = TradeLoad([[item, maxQty]], itemGain * maxQty, itemCost * maxQty, maxQty)
                    subLoad = _fitCombos(offset + 1, cr - load.costCr, cap - load.units)
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
                    bestLoad = TradeLoad(
                                    load.items + subLoad.items,
                                    load.gainCr + subLoad.gainCr,
                                    load.costCr + subLoad.costCr,
                                    load.units + subLoad.units
                                )
            return bestLoad

        bestLoad = _fitCombos(0, credits, capacity)
        return bestLoad


    def fastFit(self, items, credits, capacity, maxUnits):
        """
            Best load calculator using a recursive knapsack-like
            algorithm to find multiple loads and return the best.
        """

        def _fitCombos(offset, cr, cap):
            """
                Starting from offset, consider a scenario where we
                would purchase the maximum number of each item
                given the cr/cap limitations. Then, assuming that
                load, solve for the remaining cr+cap from the next
                value of offset.

                The "best fit" is not always the most profitable,
                so we yield all the results and leave the caller
                to determine which is actually most profitable.
            """

            # Note: both
            #  for (itemNo, item) in enumerate(items[offset:]):
            # and
            #  for itemNo in range(offset, len(items)):
            #      item = items[itemNo]
            # seemed significantly slower than this approach.
            for item in items[offset:]:
                itemCostCr = item.costCr
                maxQty = min(maxUnits, cap, cr // itemCostCr)

                # Adjust for age for "M"/"H" items with low units.
                if item.stock < maxQty and item.stock > 0:  # -1 = unknown
                    level = item.stockLevel
                    if level > 1:
                        # Assume 2 units per 10 minutes for high,
                        # 1 unit per 15 minutes for medium
                        units = level - 1
                        interval = (30 / level) * 60
                        speculativeRecovery = units * math.floor(item.srcAge / interval)
                    else:
                        # Low / Unknown - don't try to guess
                        speculativeRecovery = 0
                    maxQty = min(maxQty, item.stock + speculativeRecovery)

                if maxQty > 0:
                    loadItems = [[item, maxQty]]
                    loadCostCr = maxQty * itemCostCr
                    loadGainCr = maxQty * item.gainCr
                    bestGainCr = -1
                    crLeft, capLeft = cr - loadCostCr, cap - maxQty
                    if crLeft > 0 and capLeft > 0:
                        # Solve for the remaining credits and capacity with what
                        # is left in items after the item we just checked.
                        for subLoad in _fitCombos(offset + 1, crLeft, capLeft):
                            if subLoad.gainCr > 0 and subLoad.gainCr >= bestGainCr:
                                yield TradeLoad(
                                            subLoad.items + loadItems,
                                            subLoad.gainCr + loadGainCr,
                                            subLoad.costCr + loadCostCr,
                                            subLoad.units + maxQty
                                        )
                                bestGainCr = subLoad.gainCr
                    # If there were no good additions, yield what we have.
                    if bestGainCr < 0:
                        yield TradeLoad(loadItems, loadGainCr, loadCostCr, maxQty)
                offset += 1

        bestLoad = emptyLoad
        for result in _fitCombos(0, credits, capacity):
            if not bestLoad or (result.gainCr > bestLoad.gainCr or (result.gainCr == bestLoad.gainCr and (result.units < bestLoad.units or (result.units == bestLoad.units and result.costCr < bestLoad.costCr)))):
                bestLoad = result

        return bestLoad


    def getBestTrade(self, src, dst, credits=None, fitFunction=None):
        """
            Find the most profitable trade between stations src and dst.
            If avoidItems is populated, the items in it will not be considered for trading.
            'fitFunction' lets you specify a function to use for performing the fit.
        """
        tdenv = self.tdenv
        if credits is None: credits = tdenv.credits - getattr(tdenv, 'insurance', 0)
        capacity = tdenv.capacity
        avoidItems = tdenv.avoidItems
        self.tdenv.DEBUG0("{}/{} -> {}/{} with {:n}cr",
                src.system.dbname, src.dbname,
                dst.system.dbname, src.dbname,
                credits)

        if not dst in src.tradingWith:
            raise ValueError("%s does not have a link to %s" % (src.name(), dst.name()))

        if not capacity:
            raise ValueError("zero capacity")

        maxUnits = getattr(tdenv, 'limit') or capacity

        items = src.tradingWith[dst]
        if avoidItems:
            items = [ item for item in items if not item.item in avoidItems ]

        # Remove any items with less gain (value) than the cheapest item, or that are outside our budget.
        # This should reduce the search domain for the majority of cases, especially low-end searches.
        if items:
            firstItem = min(items, key=lambda item: item.costCr)
            firstCost, firstGain = firstItem.costCr, firstItem.gainCr
            items = [ item
                        for item
                        in items
                        if item.costCr <= credits and (
                            item.gainCr > firstGain or
                            item == firstItem)
                    ]

        # Make sure there's still something to trade.
        if not items:
            return emptyLoad

        # Short-circuit: Items are sorted from highest to lowest gain. So if we can fill up with the first
        # item in the list, we don't need to try any other combinations.
        # NOTE: The payoff for this comes from higher-end searches that would normally be more expensive,
        # at the cost of a slight hitch in lower-end searches.
        firstItem = items[0]
        if maxUnits >= capacity and firstItem.costCr * capacity <= credits:
            if firstItem.stock < 0 or firstItem.stock >= maxUnits:
                return TradeLoad([[items[0], capacity]],
                            capacity * firstItem.gainCr,
                            capacity * firstItem.costCr,
                            capacity
                        )

        # Go ahead and find the best combination out of what's left.
        fitFunction = fitFunction or self.defaultFit
        return fitFunction(items, credits, capacity, maxUnits)


    def getBestHops(self, routes, restrictTo=None):
        """
            Given a list of routes, try all available next hops from each
            route.

            Store the results by destination so that we pick the
            best route-to-point for each destination at each step.

            If we have two routes: A->B->D, A->C->D and A->B->D produces
            more profit, there's no point continuing the A->C->D path.
        """

        tdenv = self.tdenv
        avoidItems = getattr(tdenv, 'avoidItems', [])
        avoidPlaces = getattr(tdenv, 'avoidPlaces', [])
        assert not restrictTo or isinstance(restrictTo, set)
        maxJumpsPer = tdenv.maxJumpsPer or 0
        maxLyPer = tdenv.maxLyPer
        credits = tdenv.credits - getattr(tdenv, 'insurance', 0)

        bestToDest = {}
        safetyMargin = 1.0 - tdenv.margin
        unique = tdenv.unique

        stationsNotYetLoaded = [
                src.ID for src in [ route.route[-1] for route in routes ] 
                    if src.tradingWith is None
        ]
        if stationsNotYetLoaded:
            self.tdb.loadStationTrades(stationsNotYetLoaded)

        for route in routes:
            tdenv.DEBUG1("Route = {}", route.str())

            src = route.route[-1]
            startCr = credits + int(route.gainCr * safetyMargin)
            routeJumps = len(route.jumps)

            for dest in src.getDestinations(
                                maxJumps=maxJumpsPer,
                                maxLyPer=maxLyPer,
                                avoidPlaces=avoidPlaces,
                    ):
                tdenv.DEBUG2("destSys {}, destStn {}, jumps {}, distLy {}",
                                dest.system.dbname,
                                dest.station.dbname,
                                "->".join([jump.str() for jump in dest.via]),
                                dest.distLy)
                if not dest.station in src.tradingWith:
                    tdenv.DEBUG3("{} is not in my station list", dest.station.name())
                    continue
                if restrictTo:
                    if not dest.station in restrictTo and not dest.system in restrictTo:
                        tdenv.DEBUG3("{} doesn't match restrict {}",
                                        dest.station.name(), restrictTo)
                        continue
                if unique and dest.station in route.route:
                    tdenv.DEBUG3("{} is already in the list, not unique", dest.station.name())
                    continue

                trade = self.getBestTrade(src, dest.station, startCr)
                if not trade:
                    tdenv.DEBUG3("No trade")
                    continue

                dstID = dest.station.ID
                try:
                    # See if there is already a candidate for this destination
                    (bestStn, bestRoute, bestTrade, bestJumps, bestLy) = bestToDest[dstID]
                    # Check if it is a better option than we just produced
                    bestRouteGainCr = bestRoute.gainCr + bestTrade[1]
                    newRouteGainCr = route.gainCr + trade[1]
                    if bestRouteGainCr > newRouteGainCr:
                        continue
                    if bestRouteGainCr == newRouteGainCr and bestLy <= dest.distLy:
                        continue
                except KeyError:
                    # No existing candidate, we win by default
                    pass
                bestToDest[dstID] = [ dest.station, route, trade, dest.via, dest.distLy ]

        result = []
        for (dst, route, trade, jumps, ly) in bestToDest.values():
            result.append(route.plus(dst, trade, jumps))

        return result

