# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Profit Calculator

"""
TradeCalc provides a class for calculating trade loads, hops or
routes, along with some amount of state.

The intent was for it to carry a larger amount of state but
much of that got moved into TradeEnv, so right now TradeCalc
looks a little odd.

Significant Functions:

    TradeCalc.getBestTrade
        Figures out the best trade between two stations

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

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from collections import defaultdict

import locale
import math
import time

locale.setlocale(locale.LC_ALL, '')

######################################################################
# Stuff that passes for classes (but isn't)

from tradedb import System, Station, Trade, TradeDB
from collections import namedtuple

class TradeLoad(namedtuple('TradeLoad', [
                'items', 'gainCr', 'costCr', 'units'
                ])):
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

emptyLoad = TradeLoad([], 0, 0, 0)

######################################################################
# Classes

class Route(object):
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
        self.route = stations
        self.hops = hops
        self.startCr = startCr
        self.gainCr = gainCr
        self.jumps = jumps
        self.score = score


    def plus(self, dst, hop, jumps, score):
        """
            Returns a new route describing the sum of this route plus a new hop.
        """
        return Route(
                self.route + [dst],
                self.hops + [hop],
                self.startCr,
                self.gainCr + hop[1],
                self.jumps + [jumps],
                self.score + score,
        )


    def __lt__(self, rhs):
        if rhs.score < self.score: # reversed
            return True
        return rhs.score == self.score and len(rhs.jumps) < len(self.jumps)


    def __eq__(self, rhs):
        return self.score == rhs.score and len(self.jumps) == len(rhs.jumps)


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

        text = self.str()
        if detail >= 1:
            text += " (score: {:f})".format(self.score)
        text += "\n"
        if detail > 1:
            if detail > 2:
                text += self.summary() + "\n"
            hopFmt = "  Load from {station}:\n{purchases}"
            hopStepFmt = ("     {qty:>4} x {item:<{longestName}}"
                            " {eacost:>10n}cr each, {ttlcost:>10n}cr total,  data from {age}\n")
            jumpsFmt = ("  Jump {jumps}\n")
            dockFmt = "  Unload at {station} => Gain {gain:n}cr ({tongain:n}cr/ton) => {credits:n}cr\n"
            footer = '  ' + '-' * 76 + "\n"
            endFmt = ("  Finish at {station} "
                        "gaining {gain:n}cr "
                        "=> est {credits:n}cr total\n")
        elif detail:
            hopFmt = "  Load from {station}:{purchases}\n"
            hopStepFmt = " {qty} x {item} (@{eacost}cr),"
            jumpsFmt = "  Jump {jumps}\n"
            footer = None
            dockFmt = "  Dock at {station}\n"
            endFmt = ("  Finish {station} "
                        "+ {gain:n}cr "
                        "=> {credits:n}cr\n")
        else:
            hopFmt = "  {station}:{purchases}\n"
            hopStepFmt = " {qty} x {item},"
            jumpsFmt = None
            footer = None
            dockFmt = None
            endFmt = "  {station} +{gain:n}cr"

        if detail > 1:
            def decorateStation(station):
                ls = station.lsFromStar
                bm = station.blackMarket
                pad = station.maxPadSize
                if not ls:
                    if bm == '?' and pad == '?':
                        return station.name() + ' (no details)'
                    return '{} ({}/bm, {}/pad)'.format(
                            station.name(),
                            TradeDB.marketStatesExt[bm],
                            TradeDB.padSizesExt[pad],
                    )
                return '{} ({}/star, {}/bm, {}/pad)'.format(
                        station.name(),
                        station.distFromStar(True),
                        TradeDB.marketStatesExt[bm],
                        TradeDB.padSizesExt[pad],
                )
        else:
            def decorateStation(station):
                return station.name()

        def makeAge(value):
            value = int(value / 3600)
            if value < 1:
                return "<1hr"
            if value == 1:
                return "1hr"
            if value < 48:
                return str(value) + "hrs"
            value = int(value / 24)
            if value < 90:
                return str(value) + "days"
            value = int(value / 31)
            return str(value) + "mths"


        for i, hop in enumerate(hops):
            hopGainCr, hopTonnes = hop[1], 0
            purchases = ""
            for (trade, qty) in sorted(hop[0],
                                        key=lambda tradeOpt:
                                            tradeOpt[1] * tradeOpt[0].gainCr,
                                        reverse=True):
                # Are they within 30 minutes of each other?
                if abs(trade.srcAge - trade.dstAge) <= (30*60):
                    age = max(trade.srcAge, trade.dstAge)
                    age = makeAge(age)
                else:
                    srcAge = makeAge(trade.srcAge)
                    dstAge = makeAge(trade.dstAge)
                    age = "{} and {}".format(srcAge, dstAge)
                purchases += hopStepFmt.format(
                        qty=qty, item=trade.name(),
                        eacost=trade.costCr,
                        ttlcost=trade.costCr*qty,
                        longestName=longestNameLen,
                        age=age,
                )
                hopTonnes += qty
            text += hopFmt.format(station=decorateStation(route[i]), purchases=purchases)
            if jumpsFmt and self.jumps[i]:
                jumps = ' -> '.join([ jump.name() for jump in self.jumps[i] ])
                text += jumpsFmt.format(
                        jumps=jumps,
                        gain=hopGainCr,
                        tongain=hopGainCr / hopTonnes,
                        credits=credits + gainCr + hopGainCr
                )
            if dockFmt:
                stn = route[i+1]
                stnName = stn.name()
                text += dockFmt.format(
                        station=decorateStation(stn),
                        gain=hopGainCr,
                        tongain=hopGainCr / hopTonnes,
                        credits=credits + gainCr + hopGainCr
                )

            gainCr += hopGainCr

        text += footer or ""
        text += endFmt.format(
                        station=decorateStation(route[-1]),
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
        numJumps = sum([
                len(hopJumps)-1
                for hopJumps in jumps
                if hopJumps     # don't include in-system hops
                ])
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

        db = self.tdb.getDB()

        selling = self.stationsSelling = defaultdict(list)
        buying = self.stationsBuying = defaultdict(list)
        stnByID = self.tdb.stationByID

        lastStnID, stn = 0, None
        sellCount, buyCount = 0, 0
        avoidItemIDs = set([ item.ID for item in tdenv.avoidItems ])
        tdenv.DEBUG1("TradeCalc loading StationSelling values")
        cur = db.execute("""
                SELECT  station_id, item_id, price, units, level,
                        strftime('%s', modified)
                  FROM  StationSelling
        """)
        now = int(time.time())
        for stnID, itmID, cr, units, lev, timestamp in cur:
            if itmID not in avoidItemIDs:
                if stnID != lastStnID:
                    stn = selling[stnID]
                    lastStnID = stnID
                ageS = now - int(timestamp)
                stn.append([itmID, cr, units, lev, ageS])
                sellCount += 1
        tdenv.DEBUG0("Loaded {} selling values".format(sellCount))

        lastStnID, stn = 0, None
        tdenv.DEBUG1("TradeCalc loading StationBuying values")
        cur = db.execute("""
                SELECT  station_id, item_id, price, units, level,
                        strftime('%s', modified)
                  FROM  StationBuying
        """)
        now = int(time.time())
        for stnID, itmID, cr, units, lev, timestamp in cur:
            if itmID not in avoidItemIDs:
                if stnID != lastStnID:
                    stn = buying[stnID]
                    lastStnID = stnID
                ageS = now - int(timestamp)
                stn.append([itmID, cr, units, lev, ageS])
                buyCount += 1
        tdenv.DEBUG0("Loaded {} buying values".format(buyCount))


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
                maxQty = min(maxQty, item.stock)

            if maxQty > 0:
                itemGain = item.gainCr
                for qty in range(maxQty):
                    load = TradeLoad([(item, maxQty)], itemGain * maxQty, itemCost * maxQty, maxQty)
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
                    maxQty = min(maxQty, item.stock)

                if maxQty > 0:
                    loadItems = [(item, maxQty)]
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
            if not bestLoad or \
                    (result.gainCr > bestLoad.gainCr or \
                        (result.gainCr == bestLoad.gainCr and \
                            (result.units < bestLoad.units or \
                                (result.units == bestLoad.units and \
                                    result.costCr < bestLoad.costCr)))):
                bestLoad = result

        return bestLoad


    def getBestTrade(self, src, dst, credits=None, fitFunction=None):
        """
            Find the most profitable trade between stations src and dst.
            If avoidItems is populated, the items in it will not be considered for trading.
            'fitFunction' lets you specify a function to use for performing the fit.
        """
        tdenv = self.tdenv
        if credits is None:
            credits = getattr(tdenv, 'credits', 0) or 0
            credits -= (getattr(tdenv, 'insurance', 0) or 0)
        capacity = tdenv.capacity
        tdenv.DEBUG0("{}/{} -> {}/{} with {:n}cr",
                src.system.dbname, src.dbname,
                dst.system.dbname, dst.dbname,
                credits)

        if not capacity:
            raise ValueError("zero capacity")
        maxUnits = getattr(tdenv, 'limit') or capacity

        try:
            items = src.tradingWith[dst]
        except KeyError:
            items = None
        if not items:
            raise ValueError("%s does not trade with %s" % (src.name(), dst.name()))

        if tdenv.maxAge:
            # convert from days to seconds
            cutoffSeconds = tdenv.maxAge * (24 * 60 * 60)
            items = [ item for item in items
                        if max(item.srcAge, item.dstAge) < cutoffSeconds
            ]

        # Remove any items with less gain (value) than the cheapest item, or that are outside our budget.
        # This should reduce the search domain for the majority of cases, especially low-end searches.
        if items:
            if max(items, key=lambda item: item.costCr).costCr > credits:
                items = [
                        item for item in items
                        if item.costCr <= credits
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
                return TradeLoad([(items[0], capacity)],
                            capacity * firstItem.gainCr,
                            capacity * firstItem.costCr,
                            capacity
                        )

        # Go ahead and find the best combination out of what's left.
        fitFunction = fitFunction or self.defaultFit
        return fitFunction(items, credits, capacity, maxUnits)


    def _getTrades(self, srcStation, srcSelling, dstStation):
        try:
            dstBuying = self.stationsBuying[dstStation.ID]
        except KeyError:
            srcStation.tradingWith[dstStation] = None
            return None

        itemIdx = self.tdb.itemByID
        trading = []
        for buy in dstBuying:
            buyItemID = buy[0]
            for sell in srcSelling:
                sellItemID = sell[0]
                if sellItemID == buyItemID:
                    buyCr, sellCr = buy[1], sell[1]
                    if sellCr < buyCr:
                        trading.append(Trade(
                                itemIdx[buyItemID],
                                buyItemID,
                                sellCr, buyCr - sellCr,
                                sell[2], sell[3],
                                buy[2], buy[3],
                                sell[4], buy[4],
                        ))
                    break # from srcSelling

        trading.sort(key=lambda trade: trade.gainCr, reverse=True)
        srcStation.tradingWith[dstStation] = trading

        return trading

    def getBestHops(self, routes, restrictTo=None):
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
        avoidItems = getattr(tdenv, 'avoidItems', [])
        avoidPlaces = getattr(tdenv, 'avoidPlaces', [])
        assert not restrictTo or isinstance(restrictTo, set)
        maxJumpsPer = tdenv.maxJumpsPer
        maxLyPer = tdenv.maxLyPer
        credits = tdenv.credits - getattr(tdenv, 'insurance', 0)

        bestToDest = {}
        safetyMargin = 1.0 - tdenv.margin
        unique = tdenv.unique

        # Penalty is expressed as percentage, reduce it to a multiplier
        if tdenv.lsPenalty:
            lsPenalty = tdenv.lsPenalty / 100
        else:
            lsPenalty = 0

        restrictStations = set()
        if restrictTo:
            for place in restrictStations:
                if isinstance(place, Station):
                    restrictStations.add(place)
                elif isinstance(place, System) and place.stations:
                    restrictStations += place.stations

        for route in routes:
            tdenv.DEBUG1("Route = {}", route.str())

            srcStation = route.route[-1]
            srcTradingWith = srcStation.tradingWith
            if srcStation.tradingWith is None:
                srcTradingWith = srcStation.tradingWith = dict()
            startCr = credits + int(route.gainCr * safetyMargin)
            routeJumps = len(route.jumps)

            try:
                srcSelling = self.stationsSelling[srcStation.ID]
            except KeyError:
                if not srcSelling:
                    tdenv.DEBUG1("Nothing sold - next.")
                continue

            restricting = set(restrictStations)
            try:
                restricting.remove(srcStation)
            except KeyError:
                pass

            def considerStation(dstStation, dest):
                # Do we have something to trade?
                try:
                    trading = srcTradingWith[dstStation]
                except (TypeError, KeyError):
                    trading = self._getTrades(srcStation, srcSelling, dstStation)
                if not trading:
                    return

                trade = self.getBestTrade(srcStation, dstStation, startCr)
                if not trade:
                    return

                # Calculate total K-lightseconds supercruise time.
                # This will amortize for the start/end stations
                score = trade.gainCr
                if lsPenalty:
                    # Only want 1dp
                    cruiseKls = int(dstStation.lsFromStar / 100) / 10
                    # Produce a curve that favors distances under 1kls
                    # positively, starts to penalize distances over 1k,
                    # and after 4kls starts to penalize aggresively
                    # http://goo.gl/Otj2XP
                    penalty = ((cruiseKls ** 2) - cruiseKls) / 3
                    penalty *= lsPenalty
                    score *= (1 - penalty)

                dstID = dstStation.ID
                try:
                    # See if there is already a candidate for this destination
                    (bestStn, bestRoute, bestTrade, bestJumps, bestLy, bestScore) = bestToDest[dstID]
                    # Check if it is a better option than we just produced
                    bestTradeScore = bestRoute.score + bestScore
                    newTradeScore = route.score + score
                    if bestTradeScore > newTradeScore:
                        return
                    if bestTradeScore == newTradeScore and bestLy <= dest.distLy:
                        return
                except KeyError:
                    # No existing candidate, we win by default
                    pass
                bestToDest[dstID] = [ dstStation, route, trade, dest.via, dest.distLy, score ]

            for dest in tdb.getDestinations(
                    srcStation,
                    maxJumps=maxJumpsPer,
                    maxLyPer=maxLyPer,
                    avoidPlaces=avoidPlaces,
                    maxPadSize=tdenv.padSize,
                    ):
                dstStation = dest.station
                if dstStation is srcStation:
                    continue

                if unique and dstStation in route.route:
                    continue

                if tdenv.debug >= 1:
                    tdenv.DEBUG1("destSys {}, destStn {}, jumps {}, distLy {}",
                                    dstStation.system.dbname,
                                    dstStation.dbname,
                                    "->".join([jump.str() for jump in dest.via]),
                                    dest.distLy)

                if restricting:
                    if dstStation not in restricting:
                        continue

                considerStation(dstStation, dest)

                if restricting:
                    restricting.remove(dstStation)
                    if not restricting:
                        break

        result = []
        for (dst, route, trade, jumps, ly, score) in bestToDest.values():
            result.append(route.plus(dst, trade, jumps, score))

        return result

