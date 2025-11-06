from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from datetime import datetime, timezone

# Legacy wrapper types (strong typing of public inputs/outputs).
from .tradedb import Trade as TradeRow
from .tradedb import System, Station, Item  # for type annotations only
from .tradeexcept import TradeException

# ORM models/utilities used for snapshot building
from .db.orm_models import StationItem as SA_StationItem
from sqlalchemy.orm import Session as SASession  # type: ignore


# ---------------------------------------------------------------------------
# Lightweight options container (no algorithm).
# When options is None, TradeCalc will read values opportunistically from
# the provided cmdenv (attributes may or may not exist there).
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RunOptions:
    # Wallet / cargo
    capacity: int = 0                  # --capacity
    credits: int = 0                   # --credits
    insurance: int = 0                 # --insurance
    margin: float = 0.0                # --margin (fraction of prior gains withheld)
    limit: int = 0                     # --limit per item (0 = unlimited)

    # Search budget
    hops: int = 2                      # --hops
    jumps_per: int = 2                 # --jumps-per
    ly_per: Optional[float] = None     # --ly-per
    empty_ly: Optional[float] = None   # --empty-ly
    start_jumps: Optional[int] = None  # --start-jumps
    end_jumps: Optional[int] = None    # --end-jumps

    # Filtering & behaviour
    direct: bool = False               # --direct
    towards: Optional[str] = None      # --towards SYSTEM (name as given; resolution occurs elsewhere)
    via: List[str] = field(default_factory=list)    # --via ... (names; resolution occurs elsewhere)
    avoid: List[str] = field(default_factory=list)  # --avoid ... (names; resolution occurs elsewhere)

    unique: bool = False               # --unique
    loop_interval: int = 0             # --loop-interval
    gpt: Optional[int] = None          # --gpt (min gain/tonne)
    mgpt: Optional[int] = None         # --mgpt (max gain/tonne)
    ls_penalty: float = 0.125          # --ls-penalty (per 1 kls), default 12.5%
    ls_max: Optional[int] = None       # --ls-max (ls ceiling)

    # Price-row prefilters (new in Session 2)
    supply_min: Optional[int] = None   # --supply
    demand_min: Optional[int] = None   # --demand
    max_days_old: Optional[int] = None # --age / --max-days-old

    # Beam/pruning (declared here; not used yet)
    routes: int = 1                    # --routes (final to print)
    max_routes: Optional[int] = None   # --max-routes (beam width per hop)
    prune_score: Optional[int] = None  # --prune-score (% to drop after prune_hops)
    prune_hops: int = 3                # --prune-hops (activation hop index)

    # Telemetry (calculator-owned; outer hop banners remain CLI-owned)
    progress: bool = False             # enable inner progress bar surface

    @classmethod
    def from_cmdenv(cls, cmdenv) -> "RunOptions":
        """
        Best-effort projection of a cmdenv/argparse namespace into RunOptions.
        Missing attributes are ignored — this is intentionally permissive.
        """
        return cls(
            capacity=getattr(cmdenv, "capacity", 0),
            credits=getattr(cmdenv, "credits", 0),
            insurance=getattr(cmdenv, "insurance", 0),
            margin=getattr(cmdenv, "margin", 0.0),
            limit=getattr(cmdenv, "limit", 0),

            hops=getattr(cmdenv, "hops", 2),
            jumps_per=getattr(cmdenv, "jumpsPer", getattr(cmdenv, "jumps_per", 2)),
            ly_per=getattr(cmdenv, "lyPer", getattr(cmdenv, "ly_per", None)),
            empty_ly=getattr(cmdenv, "emptyLy", getattr(cmdenv, "empty_ly", None)),
            start_jumps=getattr(cmdenv, "startJumps", getattr(cmdenv, "start_jumps", None)),
            end_jumps=getattr(cmdenv, "endJumps", getattr(cmdenv, "end_jumps", None)),

            direct=getattr(cmdenv, "direct", False),
            towards=getattr(cmdenv, "towards", None),
            via=list(getattr(cmdenv, "via", [])),
            avoid=list(getattr(cmdenv, "avoid", [])),

            unique=getattr(cmdenv, "unique", False),
            loop_interval=getattr(cmdenv, "loopInterval", getattr(cmdenv, "loop_interval", 0)),
            gpt=getattr(cmdenv, "gpt", None),
            mgpt=getattr(cmdenv, "mgpt", None),
            ls_penalty=getattr(cmdenv, "lsPenalty", getattr(cmdenv, "ls_penalty", 0.125)),
            ls_max=getattr(cmdenv, "lsMax", getattr(cmdenv, "ls_max", None)),

            # New prefilters
            supply_min=getattr(cmdenv, "supply", getattr(cmdenv, "supply_min", None)),
            demand_min=getattr(cmdenv, "demand", getattr(cmdenv, "demand_min", None)),
            max_days_old=(
                getattr(cmdenv, "age", getattr(cmdenv, "maxDaysOld", getattr(cmdenv, "max_days_old", None)))
            ),

            routes=getattr(cmdenv, "routes", 1),
            max_routes=getattr(cmdenv, "maxRoutes", getattr(cmdenv, "max_routes", None)),
            prune_score=getattr(cmdenv, "pruneScore", getattr(cmdenv, "prune_score", None)),
            prune_hops=getattr(cmdenv, "pruneHops", getattr(cmdenv, "prune_hops", 3)),
            progress=getattr(cmdenv, "progress", False),
        )


# ---------------------------------------------------------------------------
# Route declaration (shape only; values populated by future implementation)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Route:
    # Totals & score used for ordering/tie-breaks
    score: float = 0.0
    gainCr: int = 0
    costCr: int = 0
    units: int = 0

    # Structure
    hops: int = 0                      # station-to-station hops
    legs: int = 0                      # total jump legs (for tie-breaks)

    # Journey
    path: List[System] = field(default_factory=list)     # systems visited (in order)
    stops: List[Station] = field(default_factory=list)   # stations per hop (in order)
    # Loads per hop: list of [(Item, qty), ...]
    loads: List[List[Tuple[Item, int]]] = field(default_factory=list)

    # Per-hop FSD paths for -J/--show-jumps; one inner list per hop.
    # For same-system hops, leave the inner list empty.
    jump_paths: List[List[System]] = field(default_factory=list)

    # Convenience
    lastSystem: Optional[System] = None
    lastStation: Optional[Station] = None

    def header(self, detail: int = 0) -> str:
        """
        Minimal header used by CLI rendering: "SRC -> DST" +
        optional score. This is a placeholder mirroring the legacy
        surface; full formatting lives elsewhere.
        """
        src = self.stops[0].name() if self.stops else "?"
        dst = self.stops[-1].name() if self.stops else "?"
        return f"{src} -> {dst}" + (f" (score: {self.score:f})" if detail >= 1 else "")

    # Reserved for later parity with legacy Route.detail(cmdenv).
    def detail(self, cmdenv) -> str:  # pragma: no cover - placeholder only
        return self.header(getattr(cmdenv, "detail", 0))


# ---------------------------------------------------------------------------
# Main calculator façade (database owned by caller).
# ---------------------------------------------------------------------------

class TradeCalc:
    """Facade for trade/run calculations.

    Parameters
    ----------
    tdb
        A TradeDB instance (owns the SQLAlchemy engine/session).
    cmdenv
        Parsed command environment holding user options. Values are read
        opportunistically and stored in a RunOptions when required.
    """

    # ----- snapshot shapes (Session 2) ---------------------------------
    # self._eligible_stations: set[int]
    #     Station IDs that pass static suitability filters (pad/planetary/
    #     fleet/odyssey + LS ceiling). Computed once per calculator.
    #
    # self._sell_map: Dict[int, List[Tuple[Item,int,int,int,int]]]
    # self._buy_map : Dict[int, List[Tuple[Item,int,int,int,int]]]
    #     Keyed by station_id. Each entry is a tuple containing:
    #         (Item, price, units, level, age_seconds)
    #     SELL map uses supply_* columns; BUY map uses demand_* columns.
    #     Item avoids and price-row prefilters (age/supply/demand minima)
    #     are applied when building these maps.

    def __init__(self, tdb, cmdenv) -> None:
        self.tdb = tdb
        self.cmdenv = cmdenv

        # Options are bound lazily on first use
        self.options: Optional[RunOptions] = None

        # Session-2 caches
        self._prefilters_built: bool = False
        self._eligible_stations: Set[int] = set()
        self._sell_map: Dict[int, List[Tuple[Item, int, int, int, int]]] = {}
        self._buy_map: Dict[int, List[Tuple[Item, int, int, int, int]]] = {}

    # --- Public API -----------------------------------------------------

    def getTrades(self, srcStation: Station, dstStation: Station) -> List[TradeRow]:
        """Return profitable trade rows from *srcStation* to *dstStation*.

        Shape: tradedb.Trade (item, costCr, gainCr, supply, supplyLevel,
        demand, demandLevel, srcAge, dstAge). Deterministic ordering and
        selection logic will be added in a later session.

        For Session 2, this returns an empty list so callers can wire up
        CLI surfaces without special-casing the not-yet-implemented path.
        """
        # Implementation intentionally deferred.
        return []

    def find_routes(
        self,
        origins: Optional[Sequence[Station]] = None,
        dest_set: Optional[Sequence[Station]] = None,
        options: Optional[RunOptions] = None,
    ) -> List[Route]:
        """Explore multi-hop routes under the given *options*.

        If *options* is None, values are projected from *cmdenv* using
        RunOptions.from_cmdenv(...). Return value is a list of Route
        objects ready for rendering; ordering and tie-breaks follow the
        clean-room spec in later sessions.

        For Session 2, this returns an empty list after ensuring the
        pre-filter snapshots are initialised.
        """
        opts = options or self._get_options()
        self._ensure_prefilters(opts)
        # Implementation intentionally deferred.
        return []

    # --- Session 2 internals -------------------------------------------

    def _get_options(self) -> RunOptions:
        """Bind or return cached RunOptions."""
        if self.options is None:
            self.options = RunOptions.from_cmdenv(self.cmdenv)
        return self.options

    # Station suitability against static constraints (pad/planetary/fleet/odyssey + LS).
    def _station_is_suitable(self, stn: Station, ls_max: Optional[int]) -> bool:
        cmdenv = self.cmdenv
        # Pad size (string like "SML?" or None)
        pad = getattr(cmdenv, "padSize", None)
        if pad and not stn.checkPadSize(pad):
            return False
        # Planetary filter
        planetary = getattr(cmdenv, "planetary", None)
        if planetary and not stn.checkPlanetary(planetary):
            return False
        # Fleet carriers
        fleet = getattr(cmdenv, "fleet", None)
        if fleet and not stn.checkFleet(fleet):
            return False
        # Odyssey
        ody = getattr(cmdenv, "odyssey", None)
        if ody and not stn.checkOdyssey(ody):
            return False
        # LS ceiling
        if ls_max and stn.lsFromStar and stn.lsFromStar > int(ls_max):
            return False
        return True

    def _ensure_prefilters(self, options: RunOptions) -> None:
        """
        Build cached station eligibility set and price maps if not already built.

        Guards:
        - If not --direct and ly_per is None → raise TradeException
        - If --start-jumps/--end-jumps set with no ly_per and no empty_ly → raise TradeException
        """
        if self._prefilters_built:
            return

        # --- validation / runtime guards --------------------------------
        if not options.direct and options.ly_per is None:
            raise TradeException(
                "Non-direct search requires '--ly-per' (max LY per jump). "
                "Use '--direct' to skip path-finding."
            )
        if (options.start_jumps or options.end_jumps) and (options.ly_per is None and options.empty_ly is None):
            raise TradeException(
                "When using '--start-jumps' or '--end-jumps', provide '--ly-per' "
                "or '--empty-ly' so jump expansion has a range."
            )

        # --- station suitability set -------------------------------------
        eligible: Set[int] = set()
        ls_max = options.ls_max
        for stn in self.tdb.stationByID.values():  # wrappers are preloaded by TradeDB.load()
            if self._station_is_suitable(stn, ls_max):
                eligible.add(stn.ID)
        self._eligible_stations = eligible

        # --- avoid lists (items only for this stage) ---------------------
        avoid_items = getattr(self.cmdenv, "avoidItems", []) or []
        avoid_item_ids = {itm.ID for itm in avoid_items}

        # --- price map snapshots -----------------------------------------
        # Date/time for age calculations (convert to seconds)
        now = datetime.now(timezone.utc)
        max_age_secs: Optional[int] = None
        if options.max_days_old is not None:
            try:
                max_age_secs = int(options.max_days_old) * 86400
            except Exception:
                # Be forgiving; a non-int still means "apply no age filter"
                max_age_secs = None

        supply_min = int(options.supply_min) if options.supply_min is not None else None
        demand_min = int(options.demand_min) if options.demand_min is not None else None

        sell_map: Dict[int, List[Tuple[Item, int, int, int, int]]] = {}
        buy_map: Dict[int, List[Tuple[Item, int, int, int, int]]] = {}

        # Build maps with one pass per side. We intentionally read ORM rows directly
        # here to avoid baking any selection logic into TradeDB.
        SessionFactory = self.tdb.Session  # sessionmaker set by TradeDB
        assert SessionFactory is not None, "TradeDB Session factory not initialised"

        def _age_seconds(modified) -> int:
            # Handle naive datetimes by assuming UTC
            if modified is None:
                return 0
            if modified.tzinfo is None:
                # Treat as UTC-naive
                delta = now - modified.replace(tzinfo=timezone.utc)
            else:
                delta = now - modified.astimezone(timezone.utc)
            secs = int(delta.total_seconds())
            return secs if secs >= 0 else 0

        with SessionFactory() as sess:  # type: SASession
            # SELLING rows (source has supply)
            q = (
                sess.query(
                    SA_StationItem.station_id,
                    SA_StationItem.item_id,
                    SA_StationItem.supply_price,
                    SA_StationItem.supply_units,
                    SA_StationItem.supply_level,
                    SA_StationItem.modified,
                )
                .filter(SA_StationItem.supply_price > 0)
            )
            for stn_id, item_id, price, units, level, modified in q:
                if stn_id not in eligible:
                    continue
                if item_id in avoid_item_ids:
                    continue
                if supply_min is not None and (units is None or units < supply_min):
                    continue
                age_s = _age_seconds(modified)
                if max_age_secs is not None and age_s > max_age_secs:
                    continue
                item = self.tdb.itemByID.get(item_id)
                if not item:
                    continue
                sell_map.setdefault(stn_id, []).append((item, int(price), int(units or 0), int(level or 0), age_s))

            # BUYING rows (destination has demand)
            q = (
                sess.query(
                    SA_StationItem.station_id,
                    SA_StationItem.item_id,
                    SA_StationItem.demand_price,
                    SA_StationItem.demand_units,
                    SA_StationItem.demand_level,
                    SA_StationItem.modified,
                )
                .filter(SA_StationItem.demand_price > 0)
            )
            for stn_id, item_id, price, units, level, modified in q:
                if stn_id not in eligible:
                    continue
                if item_id in avoid_item_ids:
                    continue
                if demand_min is not None and (units is None or units < demand_min):
                    continue
                age_s = _age_seconds(modified)
                if max_age_secs is not None and age_s > max_age_secs:
                    continue
                item = self.tdb.itemByID.get(item_id)
                if not item:
                    continue
                buy_map.setdefault(stn_id, []).append((item, int(price), int(units or 0), int(level or 0), age_s))

        self._sell_map = sell_map
        self._buy_map = buy_map
        self._prefilters_built = True

    # --------------- convenience accessors (used by tests/tools) ----------------

    @property
    def eligible_station_ids(self) -> Set[int]:
        """IDs of stations that pass static suitability filters (computed in Session 2)."""
        # Ensure prefilters exist if someone introspects without calling find_routes()
        self._ensure_prefilters(self._get_options())
        return self._eligible_stations

    @property
    def sell_map(self) -> Dict[int, List[Tuple[Item, int, int, int, int]]]:
        """Snapshot of selling rows keyed by station id (see module docstring for shape)."""
        self._ensure_prefilters(self._get_options())
        return self._sell_map

    @property
    def buy_map(self) -> Dict[int, List[Tuple[Item, int, int, int, int]]]:
        """Snapshot of buying rows keyed by station id (see module docstring for shape)."""
        self._ensure_prefilters(self._get_options())
        return self._buy_map


__all__ = ["TradeCalc", "RunOptions", "Route"]
