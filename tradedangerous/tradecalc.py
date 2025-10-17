# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Stefan 'Tromador' Morrell 2025
# Copyright (C) Jonathan 'eyeonus' Jones 2018 - 2025
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Modules :: Profit Calculator
#
# This module has been refactored from legacy SQLite raw SQL access
# to use SQLAlchemy ORM sessions. It retains the same API surface
# expected by other modules (mimicking legacy behaviour), but
# now queries ORM models instead of sqlite3 cursors.

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

from collections import defaultdict, namedtuple
import datetime
import locale
import os
import re
import sys
import time

from sqlalchemy import select

from .tradeexcept import TradeException
from .misc import progress as pbar

# ORM models (SQLAlchemy)
from tradedangerous.db.orm_models import StationItem, Station, System, Item
from tradedangerous.db.utils import parse_ts  # replaces legacy strftime('%s', modified)

# Legacy-style helpers (these remain expected by other modules)
from .tradedb import Trade, Destination, describeAge

locale.setlocale(locale.LC_ALL, '')

######################################################################
# Exceptions


class BadTimestampError(TradeException):
    """
    Raised when a StationItem row has an invalid or unparsable timestamp.
    """

    def __init__(self, tdb, stationID, itemID, modified):
        self.station = tdb.stationByID[stationID]
        self.item = tdb.itemByID[itemID]
        self.modified = modified

    def __str__(self):
        return (
            "Error loading price data from the local db:\n"
            f"{self.station.name()} has a StationItem entry for "
            f"\"{self.item.name()}\" with an invalid modified timestamp: "
            f"'{self.modified}'."
        )


class NoHopsError(TradeException):
    """Raised when no possible hops can be generated within constraints."""
    pass


######################################################################
# TradeLoad (namedtuple wrapper)


class TradeLoad(namedtuple("TradeLoad", ("items", "gainCr", "costCr", "units"))):
    """
    Describes the manifest of items to be exchanged in a trade.

    Attributes:
        items   : list of (item, qty) tuples tracking the load
        gainCr  : predicted total gain in credits
        costCr  : how much this load was bought for
        units   : total number of units across all items
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
        """Gain per ton (credits per unit)."""
        return self.gainCr / self.units if self.units else 0


# A convenience empty load (used as sentinel in fitting algorithms).
emptyLoad = TradeLoad((), 0, 0, 0)

######################################################################
# Classes


class Route:
    """
    Describes a series of hops where a TradeLoad is picked up at
    one station, the player travels via 0 or more hyperspace
    jumps and docks at a second station where they unload.

    Example:
        10 Algae + 5 Hydrogen at Station A,
        jump to System2, jump to System3,
        dock at Station B, sell everything, buy gold,
        jump to System4 and sell everything at Station X.
    """

    __slots__ = ("route", "hops", "startCr", "gainCr", "jumps", "score")

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
        return self.route[0]

    @property
    def firstSystem(self):
        return self.route[0].system

    @property
    def lastStation(self):
        return self.route[-1]

    @property
    def lastSystem(self):
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
                sum(hop.gainCr for hop in self.hops)
                // sum(hop.units for hop in self.hops)
            )
        return 0

    def plus(self, dst, hop, jumps, score):
        return Route(
            self.route + (dst,),
            self.hops + (hop,),
            self.startCr,
            self.gainCr + hop[1],
            self.jumps + (jumps,),
            self.score + score,
        )

    def __lt__(self, rhs):
        if self.score == rhs.score:
            return len(self.jumps) < len(rhs.jumps)
        return self.score > rhs.score

    def __eq__(self, rhs):
        return self.score == rhs.score and len(self.jumps) == len(rhs.jumps)

    def text(self, colorize) -> str:
        return "%s -> %s" % (
            colorize("cyan", self.firstStation.name()),
            colorize("blue", self.lastStation.name()),
        )

    def detail(self, tdenv):
        """
        Legacy helper used by run_cmd.render().
        Renders this route using cmdenv/tdenv display settings.
        """
        colorize = getattr(tdenv, "colorize", lambda *_: "{}".format)
        detail = getattr(tdenv, "detail", 0) or 0
        goalSystem = getattr(tdenv, "goalSystem", None)
        credits = getattr(tdenv, "credits", 0) or 0
        return self.render(colorize, tdenv, detail=detail, goalSystem=goalSystem, credits=credits)

    def render(self, colorize, tdenv, detail=0, goalSystem=None, credits=0):
        """
        Produce a formatted string representation of this route.
        """

        def genSubValues():
            for hop in self.hops:
                for tr, _ in hop[0]:
                    yield len(tr.name(detail))

        longestNameLen = max(genSubValues(), default=0)

        text = self.text(colorize)
        if detail >= 1:
            text += f" (score: {self.score:f})"
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
                "  Load from " + colorize("cyan", "{station}") + ":\n{purchases}"
            )
            hopStepFmt = (
                colorize("lightYellow", "     {qty:>4}")
                + " x "
                + colorize("yellow", "{item:<{longestName}} ")
                + "{eacost:>8n}cr vs {easell:>8n}cr, "
                "{age}"
            )
            if detail > 2:
                hopStepFmt += ", total: {ttlcost:>10n}cr"
            hopStepFmt += "\n"

            if not tdenv.summary:
                dockFmt = (
                    "  Unload at "
                    + colorize("lightBlue", "{station}")
                    + " => Gain {gain:n}cr "
                    "({tongain:n}cr/ton) => {credits:n}cr\n"
                )
            else:
                jumpsFmt = re.sub("  ", "    ", jumpsFmt, re.M)
                cruiseFmt = re.sub("  ", "    ", cruiseFmt, re.M)
                if distFmt:
                    distFmt = re.sub("  ", "    ", distFmt, re.M)
                hopFmt = "\n" + hopFmt
                dockFmt = "    Expect to gain {gain:n}cr ({tongain:n}cr/ton)\n"

            footer = "  " + "-" * 76 + "\n"
            endFmt = (
                "Finish at "
                + colorize("blue", "{station} ")
                + "gaining {gain:n}cr ({tongain:n}cr/ton) "
                "=> est {credits:n}cr total\n"
            )

        elif detail:
            hopFmt = "  Load from " + colorize("cyan", "{station}") + ":{purchases}\n"
            hopStepFmt = (
                colorize("lightYellow", " {qty}")
                + " x "
                + colorize("yellow", "{item}")
                + " (@{eacost}cr),"
            )
            footer = None
            dockFmt = "  Dock at " + colorize("lightBlue", "{station}\n")
            endFmt = (
                "  Finish "
                + colorize("blue", "{station} ")
                + "+ {gain:n}cr ({tongain:n}cr/ton)"
                "=> {credits:n}cr\n"
            )

        else:
            hopFmt = colorize("cyan", "  {station}:{purchases}\n")
            hopStepFmt = (
                colorize("lightYellow", " {qty}")
                + " x "
                + colorize("yellow", "{item}")
                + ","
            )
            footer = None
            dockFmt = None
            endFmt = colorize("blue", "  {station}") + " +{gain:n}cr ({tongain:n}/ton)"

        def jumpList(jumps):
            text, last = "", None
            travelled = 0.0
            for jump in jumps:
                if last:
                    dist = last.distanceTo(jump)
                    if dist:
                        if tdenv.detail:
                            text += f", {dist:.2f}ly -> "
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
                if station.blackMarket != "?":
                    details.append("BMk:" + station.blackMarket)
                if station.maxPadSize != "?":
                    details.append("Pad:" + station.maxPadSize)
                if station.planetary != "?":
                    details.append("Plt:" + station.planetary)
                if station.fleet != "?":
                    details.append("Flc:" + station.fleet)
                if station.odyssey != "?":
                    details.append("Ody:" + station.odyssey)
                if station.shipyard != "?":
                    details.append("Shp:" + station.shipyard)
                if station.outfitting != "?":
                    details.append("Out:" + station.outfitting)
                if station.refuel != "?":
                    details.append("Ref:" + station.refuel)
                details = "{} ({})".format(
                    station.name(), ", ".join(details or ["no details"])
                )
                return details

        else:

            def decorateStation(station):
                return station.name()

        if detail and goalSystem:

            def goalDistance(station):
                return (
                    f" [Distance to {goalSystem.name()}: "
                    f"{station.system.distanceTo(goalSystem):.2f} ly]\n"
                )

        else:

            def goalDistance(station):
                return ""

        gainCr = 0
        for i, hop in enumerate(self.hops):
            hopGainCr, hopTonnes = hop[1], 0
            purchases = ""
            for (trade, qty) in sorted(
                hop[0],
                key=lambda tradeOpt: tradeOpt[1] * tradeOpt[0].gainCr,
                reverse=True,
            ):
                if abs(trade.srcAge - trade.dstAge) <= (30 * 60):
                    age = max(trade.srcAge, trade.dstAge)
                    age = describeAge(age)
                else:
                    srcAge = describeAge(trade.srcAge)
                    dstAge = describeAge(trade.dstAge)
                    age = f"{srcAge} vs {dstAge}"

                purchases += hopStepFmt.format(
                    qty=qty,
                    item=trade.name(detail),
                    eacost=trade.costCr,
                    easell=trade.costCr + trade.gainCr,
                    ttlcost=trade.costCr * qty,
                    longestName=longestNameLen,
                    age=age,
                )
                hopTonnes += qty

            text += goalDistance(self.route[i])
            text += hopFmt.format(station=decorateStation(self.route[i]), purchases=purchases)

            if tdenv.showJumps and jumpsFmt and self.jumps[i]:
                startStn = self.route[i]
                endStn = self.route[i + 1]
                if startStn.system is not endStn.system:
                    fmt = jumpsFmt
                    travelled, jumps = jumpList(self.jumps[i])
                else:
                    fmt = cruiseFmt
                    travelled, jumps = 0.0, f"{startStn.name()} >>> {endStn.name()}"

                text += fmt.format(
                    jumps=jumps,
                    gain=hopGainCr,
                    tongain=hopGainCr / hopTonnes,
                    credits=credits + gainCr + hopGainCr,
                    stn=self.route[i + 1].dbname,
                )

                if travelled and distFmt and len(self.jumps[i]) > 2:
                    text += distFmt.format(
                        dist=startStn.system.distanceTo(endStn.system), trav=travelled
                    )

            if dockFmt:
                stn = self.route[i + 1]
                text += dockFmt.format(
                    station=decorateStation(stn),
                    gain=hopGainCr,
                    tongain=hopGainCr / hopTonnes,
                    credits=credits + gainCr + hopGainCr,
                )

            gainCr += hopGainCr

        lastStation = self.lastStation
        if lastStation.system is not goalSystem:
            text += goalDistance(lastStation)
        text += footer or ""
        text += endFmt.format(
            station=decorateStation(lastStation),
            gain=gainCr,
            credits=credits + gainCr,
            tongain=self.gpt,
        )

        return text

    def summary(self):
        credits, hops, jumps = self.startCr, self.hops, self.jumps
        ttlGainCr = sum(hop[1] for hop in hops)
        numJumps = sum(
            len(hopJumps) - 1 for hopJumps in jumps if hopJumps
        )
        return (
            "Start CR: {start:10n}\n"
            "Hops    : {hops:10n}\n"
            "Jumps   : {jumps:10n}\n"
            "Gain CR : {gain:10n}\n"
            "Gain/Hop: {hopgain:10n}\n"
            "Final CR: {final:10n}\n".format(
                start=credits,
                hops=len(hops),
                jumps=numJumps,
                gain=ttlGainCr,
                hopgain=ttlGainCr // len(hops),
                final=credits + ttlGainCr,
            )
        )
       
class TradeCalc:
    """
    Container for accessing trade calculations with common properties.
    """

    def __init__(self, tdb, tdenv=None, fit=None, items=None):
        """
        Constructs the TradeCalc object and loads sell/buy data.
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

        # --------------------------------------------------------------
        # Build item filter (avoidItems + specific items)
        # --------------------------------------------------------------
        itemFilter = None
        if tdenv.avoidItems or items:
            avoidItemIDs = {item.ID for item in tdenv.avoidItems}
            loadItems = items or tdb.itemByID.values()
            loadIDs = []
            for item in loadItems:
                ID = item if isinstance(item, int) else item.ID
                if ID not in avoidItemIDs:
                    loadIDs.append(ID)
            if not loadIDs:
                raise TradeException("No items to load.")
            itemFilter = loadIDs

        # --------------------------------------------------------------
        # Prepare query against StationItem (ORM, replaces raw SQL)
        # Limit front-load to stations reachable from the chosen origins
        # under the same constraints run_cmd will use for hops.
        # --------------------------------------------------------------
        demand = self.stationsBuying = defaultdict(list)
        supply = self.stationsSelling = defaultdict(list)
        dmdCount, supCount = 0, 0
        now = int(time.time())

        # --- build a restricted set of candidate stations (small front load) ---
        candidate_station_ids: set[int] = set()

        # Find starting points from env (systems or stations).
        # Fallbacks: if not provided, do NOT explode — just leave the set empty
        # and we’ll skip the restriction (behavior matches current but we still
        # benefit from maxAge/itemFilter below).
        orig_systems = list(getattr(tdenv, "origSystems", []) or [])
        orig_stations = list(getattr(tdenv, "origStations", []) or [])

        # If we only got systems, include all stations in those systems as starting docks.
        if orig_systems and not orig_stations:
            for sysobj in orig_systems:
                candidate_station_ids.update(getattr(stn, "ID", None) for stn in getattr(sysobj, "stations", ()) if getattr(stn, "ID", None))

        # If we have explicit origin stations, include them.
        if orig_stations:
            candidate_station_ids.update(getattr(stn, "ID", None) for stn in orig_stations if getattr(stn, "ID", None))

        # Expand to reachable stations using the same constraints used for hops.
        # This mirrors tradedb.getDestinations() and keeps the front-load small.
        if candidate_station_ids:
            maxJumpsPer = tdenv.maxJumpsPer
            maxLyPer = tdenv.maxLyPer
            avoidPlaces = getattr(tdenv, "avoidPlaces", None) or ()
            maxPadSize = tdenv.padSize
            noPlanet = tdenv.noPlanet
            planetary = tdenv.planetary
            fleet = tdenv.fleet
            odyssey = tdenv.odyssey
            maxLsFromStar = tdenv.maxLs or 0

            getDestinations = tdb.getDestinations

            # For each origin station (or the stations we gathered from origin systems),
            # add every reachable station’s ID into the candidate set.
            origin_iter = list(orig_stations)
            if not origin_iter and orig_systems:
                # choose one station per origin system if none explicitly selected
                for sysobj in orig_systems:
                    for stn in getattr(sysobj, "stations", ()):
                        origin_iter.append(stn)
                        break  # just one starting dock per system

            for start_stn in origin_iter:
                for dest in getDestinations(
                    start_stn,
                    maxJumps=maxJumpsPer,
                    maxLyPer=maxLyPer,
                    avoidPlaces=avoidPlaces,
                    maxPadSize=maxPadSize,
                    maxLsFromStar=maxLsFromStar,
                    noPlanet=noPlanet,
                    planetary=planetary,
                    fleet=fleet,
                    odyssey=odyssey,
                ):
                    if dest.station and getattr(dest.station, "ID", None):
                        candidate_station_ids.add(dest.station.ID)

        with tdb.Session() as session:
            stmt = select(StationItem)

            # Age filter (if set)
            if tdenv.maxAge:
                maxDays = datetime.timedelta(days=tdenv.maxAge)
                cutoff = datetime.datetime.now() - maxDays
                stmt = stmt.where(StationItem.modified >= cutoff)

            # Item filter (if set)
            if itemFilter:
                stmt = stmt.where(StationItem.item_id.in_(itemFilter))

            # Station reachability filter (only if we actually built a candidate set)
            if candidate_station_ids:
                stmt = stmt.where(StationItem.station_id.in_(candidate_station_ids))

            tdenv.DEBUG1("TradeCalc front-load: limiting StationItem query to %d stations", len(candidate_station_ids) or 0)
            tdenv.DEBUG2("sqlalchemy stmt: {}", stmt)

            for row in session.execute(stmt).scalars():
                stnID = row.station_id
                itmID = row.item_id

                modified_dt = parse_ts(row.modified)
                if not modified_dt:
                    raise BadTimestampError(self.tdb, stnID, itmID, row.modified)
                ageS = now - int(modified_dt.timestamp())

                if row.demand_price > 0:
                    if not minDemand or row.demand_units >= minDemand:
                        demand[stnID].append(
                            (itmID, row.demand_price, row.demand_units, row.demand_level, ageS)
                        )
                        dmdCount += 1

                if row.supply_price > 0 and row.supply_units:
                    if not minSupply or row.supply_units >= minSupply:
                        supply[stnID].append(
                            (itmID, row.supply_price, row.supply_units, row.supply_level, ageS)
                        )
                        supCount += 1

        tdenv.DEBUG0(f"Loaded {dmdCount} buys, {supCount} sells")

    # ------------------------------------------------------------------
    # Cargo fitting algorithms
    # ------------------------------------------------------------------

    def bruteForceFit(self, items, credits, capacity, maxUnits):  # pylint: disable=redefined-builtin
        """
        Brute-force generation of all possible combinations of items.
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

                if item.supply < maxQty and item.supply > 0:
                    maxQty = min(maxQty, item.supply)

                if maxQty > 0:
                    break

            bestLoad = _fitCombos(offset, cr, cap, level + 1)
            itemGain = item.gainCr

            for qty in range(1, maxQty + 1):
                loadGain, loadCost = itemGain * qty, itemCost * qty
                load = TradeLoad(((item, qty),), loadGain, loadCost, qty)
                subLoad = _fitCombos(offset, cr - loadCost, cap - qty, level + 1)
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
                    load.items + subLoad.items, combGain, combCost, combUnits
                )

            return bestLoad

        return _fitCombos(0, credits, capacity)

    def fastFit(self, items, credits, capacity, maxUnits):  # pylint: disable=redefined-builtin
        """
        Knapsack-like recursive load fitter.
        """

        def _fitCombos(offset, cr, cap):
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
                    gain = itemGainCr * maxQty
                    if gain > bestGainCr:
                        cost = itemCostCr * maxQty
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

    def simpleFit(self, items, credits, capacity, maxUnits):  # pylint: disable=redefined-builtin
        """
        Greedy load fitter (default).
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

    # ------------------------------------------------------------------
    # Trading methods
    # ------------------------------------------------------------------

    def getTrades(self, srcStation, dstStation, srcSelling=None):
        """
        Returns the most profitable trading options from one station to another.
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

        for sell in srcSelling:
            buy = getBuy(sell[0], None)
            if buy:
                gainCr = buy[1] - sell[1]
                if minGainCr <= gainCr <= maxGainCr:
                    addTrade(
                        Trade(
                            itemIdx[sell[0]],
                            sell[1],
                            gainCr,
                            sell[2],
                            sell[3],
                            buy[2],
                            buy[3],
                            sell[4],
                            buy[4],
                        )
                    )

        trading.sort(key=lambda trade: trade.costCr)
        trading.sort(key=lambda trade: trade.gainCr, reverse=True)

        return trading

    def getBestHops(self, routes, restrictTo=None):
        """
        Given a list of routes, try all available next hops from each route.

        Store the results by destination so that we pick the
        best route-to-point for each destination at each step.

        If we have two routes: A->B->D, A->C->D and A->B->D produces
        more profit, there's no point continuing the A->C->D path.
        """

        tdb = self.tdb
        tdenv = self.tdenv
        avoidPlaces = getattr(tdenv, "avoidPlaces", None) or ()
        assert not restrictTo or isinstance(restrictTo, set)
        maxJumpsPer = tdenv.maxJumpsPer
        maxLyPer = tdenv.maxLyPer
        maxPadSize = tdenv.padSize
        planetary = tdenv.planetary
        fleet = tdenv.fleet
        odyssey = tdenv.odyssey
        noPlanet = tdenv.noPlanet
        maxLsFromStar = tdenv.maxLs or float("inf")
        reqBlackMarket = getattr(tdenv, "blackMarket", False) or False
        maxAge = getattr(tdenv, "maxAge") or 0
        credits = tdenv.credits - (getattr(tdenv, "insurance", 0) or 0)
        fitFunction = self.defaultFit
        capacity = tdenv.capacity
        maxUnits = getattr(tdenv, "limit") or capacity

        bestToDest = {}
        safetyMargin = 1.0 - tdenv.margin
        unique = tdenv.unique
        loopInt = getattr(tdenv, "loopInt", 0) or None

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

        if tdenv.direct:
            if goalSystem and not restrictTo:
                restrictTo = (goalSystem,)
                restrictStations = set(goalSystem.stations)
            if avoidPlaces:
                restrictStations = set(
                    stn
                    for stn in restrictStations
                    if stn not in avoidPlaces and stn.system not in avoidPlaces
                )

            def station_iterator(srcStation):
                srcSys = srcStation.system
                srcDist = srcSys.distanceTo
                for stn in restrictStations:
                    stnSys = stn.system
                    yield Destination(stnSys, stn, (srcSys, stnSys), srcDist(stnSys))

        else:
            getDestinations = tdb.getDestinations

            def station_iterator(srcStation):
                yield from getDestinations(
                    srcStation,
                    maxJumps=maxJumpsPer,
                    maxLyPer=maxLyPer,
                    avoidPlaces=avoidPlaces,
                    maxPadSize=maxPadSize,
                    maxLsFromStar=maxLsFromStar,
                    noPlanet=noPlanet,
                    planetary=planetary,
                    fleet=fleet,
                    odyssey=odyssey,
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
                if not srcSelling:
                    tdenv.DEBUG1("Nothing sold at source - next.")
                    continue

                srcSelling = tuple(values for values in srcSelling if values[1] <= startCr)
                if not srcSelling:
                    tdenv.DEBUG1("Nothing affordable - next.")
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

                stations = (
                    d
                    for d in station_iterator(srcStation)
                    if (d.station != srcStation)
                    and (d.station.blackMarket == "Y" if reqBlackMarket else True)
                    and (d.station not in uniquePath if uniquePath else True)
                    and (d.station in restrictStations if restrictStations else True)
                    and (d.station.dataAge and d.station.dataAge <= maxAge if maxAge else True)
                    and (
                        (
                            (d.system is not srcSystem)
                            if bool(tdenv.unique)
                            else (d.system is goalSystem or d.distLy < srcGoalDist)
                        )
                        if goalSystem
                        else True
                    )
                )

                if tdenv.debug >= 1:

                    def annotate(dest):
                        tdenv.DEBUG1(
                            "destSys {}, destStn {}, jumps {}, distLy {}",
                            dest.system.dbname,
                            dest.station.dbname,
                            "->".join(jump.text() for jump in dest.via),
                            dest.distLy,
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
                    dstSys = dest.system
                    if goalSystem and dstSys is not goalSystem:
                        dstGoalDist = goalDistTo(dstSys)
                        score = 5000 * origGoalDist / dstGoalDist
                        score += 50 * srcGoalDist / dstGoalDist
                        if dstSys is not origSystem:
                            score += 10 * (origDistTo(dstSys) - srcOrigDist)
                        score += (trade.gainCr / trade.units) / 25
                    else:
                        score = trade.gainCr

                    if lsPenalty:
                        def sigmoid(x):
                            return x / (1 + abs(x))

                        cruiseKls = int(dstStation.lsFromStar / 100) / 10
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
                        btd = bestToDest[dstID]
                    except KeyError:
                        pass
                    else:
                        bestRoute = btd[1]
                        bestScore = btd[5]
                        bestTradeScore = bestRoute.score + bestScore
                        newTradeScore = route.score + score
                        if bestTradeScore > newTradeScore:
                            continue
                        if bestTradeScore == newTradeScore:
                            bestLy = btd[4]
                            if bestLy <= dest.distLy:
                                continue

                    bestToDest[dstID] = (
                        dstStation,
                        route,
                        trade,
                        dest.via,
                        dest.distLy,
                        score,
                    )

        if connections == 0:
            raise NoHopsError("No destinations could be reached within the constraints.")

        result = []
        for (dst, route, trade, jumps, _, score) in bestToDest.values():
            result.append(route.plus(dst, trade, jumps, score))

        return result