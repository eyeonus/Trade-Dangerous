# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
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

from collections import defaultdict
from collections import namedtuple
from tradedb import System, Station, Trade, TradeDB, describeAge
from tradeexcept import TradeException

import locale
import math
import os
import time

locale.setlocale(locale.LC_ALL, '')

######################################################################
# Exceptions


class BadTimestampError(TradeException):
    def __init__(
            self,
            tableName,
            tdb,
            stationID, itemID,
            modified
            ):
        self.tableName = tableName
        self.station = tdb.stationByID[stationID]
        self.item = tdb.itemByID[itemID]
        self.modified = modified

    def __str__(self):
        return (
            "Error loading price data from the local db:\n"
            "{} has a {} entry for \"{}\" with an invalid "
            "modified timestamp: '{}'.".format(
                self.station.name(),
                self.tableName,
                self.item.name(),
                str(self.modified),
            )
        )


######################################################################
# Stuff that passes for classes (but isn't)

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
        if rhs.score < self.score:  # reversed
            return True
        return rhs.score == self.score and len(rhs.jumps) < len(self.jumps)

    def __eq__(self, rhs):
        return self.score == rhs.score and len(self.jumps) == len(rhs.jumps)

    def str(self):
        return "%s -> %s" % (self.route[0].name(), self.route[-1].name())

    def detail(self, tdenv):
        """
        Return a string describing this route to a given level of detail.
        """

        detail, goalSystem = tdenv.detail, tdenv.goalSystem

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
            hopStepFmt = (
                "     {qty:>4} x {item:<{longestName}}"
                " {eacost:>10n}cr each, {ttlcost:>10n}cr total,"
                "data from {age}\n"
            )
            jumpsFmt = ("  Jump {jumps}\n")
            dockFmt = (
                "  Unload at {station} => Gain {gain:n}cr "
                "({tongain:n}cr/ton) => {credits:n}cr\n"
            )
            footer = '  ' + '-' * 76 + "\n"
            endFmt = (
                "  Finish at {station} "
                "gaining {gain:n}cr "
                "=> est {credits:n}cr total\n"
            )
        elif detail:
            hopFmt = "  Load from {station}:{purchases}\n"
            hopStepFmt = " {qty} x {item} (@{eacost}cr),"
            jumpsFmt = "  Jump {jumps}\n"
            footer = None
            dockFmt = "  Dock at {station}\n"
            endFmt = (
                "  Finish {station} "
                "+ {gain:n}cr "
                "=> {credits:n}cr\n"
            )
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
                    key=lambda tradeOpt: tradeOpt[1] * tradeOpt[0].gainCr,
                    reverse=True
                    ):
                # Are they within 30 minutes of each other?
                if abs(trade.srcAge - trade.dstAge) <= (30*60):
                    age = max(trade.srcAge, trade.dstAge)
                    age = describeAge(age)
                else:
                    srcAge = describeAge(trade.srcAge)
                    dstAge = describeAge(trade.dstAge)
                    age = "{} vs {}".format(srcAge, dstAge)
                purchases += hopStepFmt.format(
                    qty=qty, item=trade.name(),
                    eacost=trade.costCr,
                    ttlcost=trade.costCr*qty,
                    longestName=longestNameLen,
                    age=age,
                )
                hopTonnes += qty
            text += goalDistance(route[i])
            text += hopFmt.format(
                station=decorateStation(route[i]),
                purchases=purchases
            )
            if jumpsFmt and self.jumps[i]:
                jumps = ' -> '.join([jump.name() for jump in self.jumps[i]])
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

        if route[-1].system is not goalSystem:
            text += goalDistance(route[-1])
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
        if "BRUTE_FIT" in os.environ:
            self.defaultFit = self.bruteForceFit

        db = self.tdb.getDB()

        avoidItemIDs = set([item.ID for item in tdenv.avoidItems])

        if tdenv.maxAge:
            loadWhere = "WHERE JULIANDAY(modified) >= JULIANDAY('NOW') - {:f}".format(
                    tdenv.maxAge
            )
        else:
            loadWhere = ""

        def load_items(tableName, index):
            lastStnID, stnAppend = 0, None
            count = 0
            tdenv.DEBUG1("TradeCalc loading {} values")
            cur = db.execute("""
                    SELECT  station_id, item_id, price, units, level,
                            strftime('%s', modified),
                            modified
                      FROM  {}
                      {where}
            """.format(tableName, where=loadWhere))
            now = int(time.time())
            for stnID, itmID, cr, units, lev, timestamp, modified in cur:
                if itmID not in avoidItemIDs:
                    if stnID != lastStnID:
                        stnAppend = index[stnID].append
                        lastStnID = stnID
                    try:
                        ageS = now - int(timestamp)
                    except TypeError:
                        raise BadTimestampError(
                            TableName, self.tdb,
                            stnID, itmID, modified
                        )
                    stnAppend((itmID, cr, units, lev, ageS))
                    count += 1
            tdenv.DEBUG0("Loaded {} selling values".format(count))

        self.stationsSelling = defaultdict(list)
        load_items("StationSelling", self.stationsSelling)

        self.stationsBuying = defaultdict(list)
        load_items("StationBuying", self.stationsBuying)

    def bruteForceFit(self, items, credits, capacity, maxUnits):
        """
        Brute-force generation of all possible combinations of items.
        This is provided to make it easy to validate the results of future
        variants or optimizations of the fit algorithm.
        """
        def _fitCombos(offset, cr, cap, level=1):
            if cr <= 0 or cap <= 0:
                return emptyLoad
            while True:
                if offset >= len(items):
                    return emptyLoad
                item = items[offset]
                offset += 1

                itemCost = item.costCr
                maxQty = min(maxUnits, cap, cr // itemCost)

                if item.stock < maxQty and item.stock > 0:  # -1 = unknown
                    maxQty = min(maxQty, item.stock)

                if maxQty > 0:
                    break

            # find items that don't include us
            bestLoad = _fitCombos(offset, cr, cap, level + 1)
            itemGain = item.gainCr

            for qty in range(1, maxQty + 1):
                loadGain, loadCost = itemGain * qty, itemCost * qty
                load = TradeLoad([(item, qty)], loadGain, loadCost, qty)
                subLoad = _fitCombos(
                    offset, cr - loadCost, cap - qty, level+1
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

    def fastFit(self, items, credits, capacity, maxUnits):
        """
            Best load calculator using a recursive knapsack-like
            algorithm to find multiple loads and return the best.
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

            # Note: both
            #  for (itemNo, item) in enumerate(items[offset:]):
            # and
            #  for itemNo in range(offset, len(items)):
            #      item = items[itemNo]
            # seemed significantly slower than this approach.
            for iNo in range(offset, len(items)):
                item = items[iNo]
                itemCostCr = item.costCr
                stock = item.stock
                maxQty = min(maxUnits, cap, cr // itemCostCr)
                if stock < maxQty and stock >= 0:  # -1 = unknown
                    maxQty = min(maxQty, stock)

                if maxQty <= 0:
                    continue

                itemGainCr = item.gainCr
                if maxQty >= cap:
                    yield TradeLoad(
                        [(item, cap)],
                        itemGainCr * cap, itemCostCr * cap,
                        cap
                    )
                    return

                bestGainCr = -1
                loadItems = [(item, maxQty)]
                loadCostCr = maxQty * itemCostCr
                loadGainCr = maxQty * itemGainCr
                crLeft, capLeft = cr - loadCostCr, cap - maxQty
                if crLeft > 0 and capLeft > 0:
                    # Solve for the remaining credits and capacity with what
                    # is left in items after the item we just checked.
                    for subLoad in _fitCombos(iNo + 1, crLeft, capLeft):
                        slGain = loadGainCr + subLoad.gainCr
                        if slGain >= bestGainCr:
                            yield TradeLoad(
                                subLoad.items + loadItems,
                                slGain,
                                subLoad.costCr + loadCostCr,
                                subLoad.units + maxQty,
                            )
                            bestGainCr = subLoad.gainCr
                if bestGainCr < 0 and loadGainCr >= bestGainCr:
                    yield TradeLoad(loadItems, loadGainCr, loadCostCr, maxQty)

        bestLoad = emptyLoad
        for newLoad in _fitCombos(0, credits, capacity):
            if bestLoad < newLoad:
                bestLoad = newLoad

        return bestLoad

    def getBestTrade(self, src, dst, credits=None, fitFunction=None):
        """
        Find the most profitable trade between stations src and dst.

        If avoidItems is populated, the items in it will not be considered
        for trading.

        'fitFunction' lets you override the default fitting function.
        """

        tdenv = self.tdenv
        if credits is None:
            credits = getattr(tdenv, 'credits', 0) or 0
            credits -= (getattr(tdenv, 'insurance', 0) or 0)
        capacity = tdenv.capacity
        tdenv.DEBUG0(
            "{}/{} -> {}/{} with {:n}cr",
            src.system.dbname, src.dbname,
            dst.system.dbname, dst.dbname,
            credits
        )

        if not capacity:
            raise ValueError("zero capacity")
        maxUnits = getattr(tdenv, 'limit') or capacity

        try:
            items = src.tradingWith[dst]
        except KeyError:
            items = None
        if not items:
            raise ValueError(
                "%s does not trade with %s" % (src.name(), dst.name())
            )

        if max(items, key=lambda itm: itm.costCr).costCr > credits:
            items = [
                item for item in items if item.costCr <= credits
            ]
            if not items:
                return emptyLoad

        # Go ahead and find the best combination out of what's left.
        fitFunction = fitFunction or self.defaultFit
        return fitFunction(items, credits, capacity, maxUnits)

    def getTrades(self, srcStation, dstStation, srcSelling=None):
        if not srcSelling:
            srcSelling = self.stationsSelling.get(srcStation.ID, None)
        if not srcSelling:
            return None
        dstBuying = self.stationsBuying.get(dstStation.ID, None)
        if not dstBuying:
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
                    break   # from srcSelling

        # SORT BY profit DESC, cost
        # So two if two items have the same profit, the cheapest
        # will be listed first.
        trading.sort(key=lambda trade: trade.costCr)
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
        avoidItems = getattr(tdenv, 'avoidItems', []) or []
        avoidPlaces = getattr(tdenv, 'avoidPlaces', []) or []
        assert not restrictTo or isinstance(restrictTo, set)
        maxJumpsPer = tdenv.maxJumpsPer
        maxLyPer = tdenv.maxLyPer
        reqBlackMarket = getattr(tdenv, 'blackMarket', False) or False
        maxAge = getattr(tdenv, 'maxAge') or 0
        credits = tdenv.credits - (getattr(tdenv, 'insurance', 0) or 0)

        bestToDest = {}
        safetyMargin = 1.0 - tdenv.margin
        unique = tdenv.unique

        # Penalty is expressed as percentage, reduce it to a multiplier
        if tdenv.lsPenalty:
            lsPenalty = tdenv.lsPenalty / 100
        else:
            lsPenalty = 0

        goalSystem = tdenv.goalSystem

        restrictStations = set()
        if restrictTo:
            for place in restrictTo:
                if isinstance(place, Station):
                    restrictStations.add(place)
                elif isinstance(place, System) and place.stations:
                    restrictStations.update(place.stations)
        restrictStations = set(restrictStations)

        for route in routes:
            tdenv.DEBUG1("Route = {}", route.str())

            srcStation = route.route[-1]
            srcTradingWith = srcStation.tradingWith
            if srcStation.tradingWith is None:
                srcTradingWith = srcStation.tradingWith = dict()
            startCr = credits + int(route.gainCr * safetyMargin)
            routeJumps = len(route.jumps)

            srcSelling = self.stationsSelling.get(srcStation.ID, None)
            if not srcSelling:
                tdenv.DEBUG1("Nothing sold - next.")
                continue

            restricting = set(restrictStations)
            try:
                restricting.remove(srcStation)
            except KeyError:
                pass

            if goalSystem:
                origSystem = route.route[0].system
                srcSystem = srcStation.system
                srcGoalDist = srcSystem.distanceTo(goalSystem)
                srcOrigDist = srcSystem.distanceTo(origSystem)

            def considerStation(dstStation, dest, multiplier):
                # Do we have something to trade?
                try:
                    trading = srcTradingWith[dstStation]
                except (TypeError, KeyError):
                    trading = self.getTrades(
                        srcStation, dstStation, srcSelling
                    )
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
                    multiplier *= (1 - penalty)

                score *= multiplier

                dstID = dstStation.ID
                try:
                    # See if there is already a candidate for this destination
                    btd = bestToDest[dstID]
                    bestRoute = btd[1]
                    bestScore = btd[5]
                    # Check if it is a better option than we just produced
                    bestTradeScore = bestRoute.score + bestScore
                    newTradeScore = route.score + score
                    if bestTradeScore > newTradeScore:
                        return
                    if bestTradeScore == newTradeScore:
                        bestLy = btd[4]
                        if bestLy <= dest.distLy:
                            return
                except KeyError:
                    # No existing candidate, we win by default
                    pass
                bestToDest[dstID] = [
                    dstStation, route, trade, dest.via, dest.distLy, score
                ]

            for dest in tdb.getDestinations(
                    srcStation,
                    maxJumps=maxJumpsPer,
                    maxLyPer=maxLyPer,
                    avoidPlaces=avoidPlaces,
                    maxPadSize=tdenv.padSize,
                    maxLsFromStar=tdenv.maxLs,
                    ):
                dstStation = dest.station
                if dstStation is srcStation:
                    continue

                if unique and dstStation in route.route:
                    continue

                if reqBlackMarket and dstStation.blackMarket != 'Y':
                    continue

                if maxAge:
                    stnDataAge = dstStation.dataAge
                    if stnDataAge is None or stnDataAge > maxAge:
                        continue

                if tdenv.debug >= 1:
                    tdenv.DEBUG1(
                        "destSys {}, destStn {}, jumps {}, distLy {}",
                        dstStation.system.dbname,
                        dstStation.dbname,
                        "->".join([jump.str() for jump in dest.via]),
                        dest.distLy
                    )

                multiplier = 1.0
                if restrictStations:
                    if dstStation not in restricting:
                        continue
                elif goalSystem:
                    # Bias in favor of getting closer
                    dstSys = dstStation.system
                    if dstSys == srcSystem:
                        if tdenv.unique:
                            continue
                    else:
                        dstGoalDist = dstSys.distanceTo(goalSystem)
                        if dstGoalDist >= srcGoalDist:
                            continue
                        dstOrigDist = dstSys.distanceTo(origSystem)
                        if dstOrigDist < srcOrigDist:
                            # Did this put us back towards the orig?
                            # It may be valid to do so but it's not "profitable".
                            multiplier *= 0.6
                        else:
                            # The closer dst is, the smaller the divider
                            # will be, so the larger the remainder.
                            multiplier *= 1 + (srcGoalDist / dstGoalDist)

                considerStation(dstStation, dest, multiplier)

                if restrictStations:
                    restricting.remove(dstStation)
                    if not restricting:
                        break

        result = []
        for (dst, route, trade, jumps, ly, score) in bestToDest.values():
            result.append(route.plus(dst, trade, jumps, score))

        return result
