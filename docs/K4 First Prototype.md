# K4 First Prototype Plan — Raw One-Hop Candidate Edges

Scope: **single source station, unbounded mode, minimal filters, raw profitable source→destination item edges only**.

No `tradecalc.py` or `tradedb.py` inspection yet.  
No implementation patch.

The provider returns raw database candidate facts only.

It must not return:

```text
Route objects
Hop objects
TradeDB wrapper objects
display formatting
cargo allocations
scores
rendering names as mandatory state
```

If those appear in provider output, the abstraction has started turning into `TradeCalc` v2.

---

## 1. Exact Provider Function Signature / Input Object

Prototype function contract:

```python
def get_raw_profitable_edges(
    session: Session,
    request: RawEdgeRequest,
) -> list[RawCandidateEdge]:
    ...
```

Input object:

```python
@dataclass(frozen=True, slots=True)
class RawEdgeRequest:
    source_station_id: int

    edge_mode: EdgeMode = EdgeMode.PRICE_ONLY

    min_gain_per_ton: int | None = 1
    max_gain_per_ton: int | None = None

    min_supply_units: int | None = None
    min_demand_units: int | None = None

    include_item_ids: frozenset[int] | None = None
    exclude_item_ids: frozenset[int] = frozenset()

    exclude_destination_station_ids: frozenset[int] = frozenset()
    exclude_destination_system_ids: frozenset[int] = frozenset()
```

Edge mode:

```python
class EdgeMode(Enum):
    PRICE_ONLY = "price_only"
    PRICE_AND_UNITS = "price_and_units"
```

Edge mode semantics:

```text
price-only edge mode:
    supply_price > 0
    demand_price > 0

price-and-units edge mode:
    supply_price > 0
    supply_units > 0
    demand_price > 0
    demand_units > 0
```

Do not bake either unit assumption in as final until parity is checked.

Deliberately excluded from first prototype input:

```text
geometry mode
jump range
cargo capacity
credits
age filtering
station market flag filtering
pad / planetary / fleet / settlement filters
black-market filter
ls-max filter
via / loop / unique route state
rendering names as mandatory fields
```

Rationale:

```text
This seam only tests the database-side profitable same-item join.
```

---

## 2. Exact Candidate Edge Record Shape

Output record:

```python
@dataclass(frozen=True, slots=True)
class RawCandidateEdge:
    source_station_id: int
    source_system_id: int

    destination_station_id: int
    destination_system_id: int

    item_id: int

    supply_price: int
    demand_price: int
    gain_per_ton: int

    supply_units: int
    demand_units: int
    supply_level: int
    demand_level: int

    source_modified: datetime | str
    destination_modified: datetime | str
```

Timestamp rule:

```text
modified values are returned raw from the database in the first prototype.
normalisation / parse_ts() handling / age computation is deferred until parity checking.
```

Not included in first prototype output:

```text
station names
system names
item names
distance
LS penalty fields
computed age
cargo allocation
score
Route/Hop objects
```

Names can be joined later if comparison tooling needs them, but they should not be mandatory for the provider abstraction.

---

## 3. SQLAlchemy Query Shape / SQL Pseudocode

### Base SQL Pseudocode

```sql
SELECT
    src_si.station_id AS source_station_id,
    src_st.system_id AS source_system_id,

    dst_si.station_id AS destination_station_id,
    dst_st.system_id AS destination_system_id,

    src_si.item_id AS item_id,

    src_si.supply_price AS supply_price,
    dst_si.demand_price AS demand_price,
    dst_si.demand_price - src_si.supply_price AS gain_per_ton,

    src_si.supply_units AS supply_units,
    dst_si.demand_units AS demand_units,
    src_si.supply_level AS supply_level,
    dst_si.demand_level AS demand_level,

    src_si.modified AS source_modified,
    dst_si.modified AS destination_modified

FROM StationItem AS src_si

JOIN Station AS src_st
  ON src_st.station_id = src_si.station_id

JOIN StationItem AS dst_si
  ON dst_si.item_id = src_si.item_id

JOIN Station AS dst_st
  ON dst_st.station_id = dst_si.station_id

WHERE src_si.station_id = :source_station_id
  AND dst_si.station_id <> src_si.station_id
  AND src_si.supply_price > 0
  AND dst_si.demand_price > 0
  AND dst_si.demand_price > src_si.supply_price
;
```

Same-station assumption:

```text
same-station source/destination edges are excluded in the first prototype,
but this must be checked against legacy behaviour.
```

### Dynamic Predicate Construction

The SQLAlchemy provider should build the predicate list dynamically.

Avoid real query shapes like:

```sql
AND (:min_gain_per_ton IS NULL OR ...)
```

Optional predicates should be added only when active:

```text
if min_gain_per_ton is not None:
    add gain_per_ton >= min_gain_per_ton

if max_gain_per_ton is not None:
    add gain_per_ton <= max_gain_per_ton

if edge_mode is PRICE_AND_UNITS:
    add source supply_units > 0
    add destination demand_units > 0

if min_supply_units is not None:
    add source supply_units >= min_supply_units

if min_demand_units is not None:
    add destination demand_units >= min_demand_units

if include_item_ids:
    add item_id IN (...)

if exclude_item_ids:
    add item_id NOT IN (...)

if exclude_destination_station_ids:
    add destination station_id NOT IN (...)

if exclude_destination_system_ids:
    add destination system_id NOT IN (...)
```

### SQLAlchemy Shape

Use aliases for `StationItem` and `Station`:

```text
src_si = aliased(orm.StationItem)
dst_si = aliased(orm.StationItem)
src_st = aliased(orm.Station)
dst_st = aliased(orm.Station)
```

Query shape:

```text
select requested edge columns
from src_si
join src_st on source station
join dst_si on same item_id
join dst_st on destination station
where:
    src_si.station_id == request.source_station_id
    dst_si.station_id != src_si.station_id
    src_si.supply_price > 0
    dst_si.demand_price > 0
    dst_si.demand_price > src_si.supply_price
    dynamic optional predicates
```

Destination system avoidance:

```text
exclude_destination_system_ids can be applied through dst_st.system_id.
The first prototype does not need to join System unless names, coordinates, or geometry are requested.
```

Deliberately omitted from first prototype:

```text
Station.market = 'Y'
age filtering
geometric filtering
station capability filtering
cargo fitting
scoring
rendering
```

---

## 4. Validation Method for Comparing Raw Edge Sets Against Current Behaviour

The comparison target is raw candidate-edge parity, **before** cargo fitting, scoring, pruning, or rendering.

### Provider Self-Check Before Legacy Parity

Before legacy parity exists, provider self-check should report:

```text
source supply row count
joined same-item destination demand row count
profitable edge count in price-only mode
profitable edge count in price-and-units mode
top N gain edges for manual sanity
```

This gives useful diagnostics before touching legacy internals.

Suggested diagnostic stages:

```text
1. Count source rows:
   StationItem rows for source_station_id with supply_price > 0

2. Count joined demand rows:
   same-item destination StationItem rows with demand_price > 0

3. Count profitable rows:
   demand_price > supply_price

4. Count price-and-units rows:
   profitable rows with supply_units > 0 and demand_units > 0

5. Show top N by gain_per_ton:
   useful manual sanity check
```

### Required Comparison Shape

Normalise both provider and legacy results into tuples:

```text
(
    source_station_id,
    destination_station_id,
    item_id,
    supply_price,
    demand_price,
    gain_per_ton,
    supply_units,
    demand_units,
    supply_level,
    demand_level,
    source_modified,
    destination_modified,
)
```

Then compare as sets:

```text
provider_edges - legacy_edges
legacy_edges - provider_edges
provider_edges ∩ legacy_edges
```

### Practical Validation Sequence

```text
1. Pick one known source station ID with usable supply rows.

2. Run provider in unbounded/minimal-filter mode.

3. Collect provider self-check diagnostics.

4. Run both provider edge modes:
   - price-only
   - price-and-units

5. Obtain current raw one-hop edge discovery from the existing route engine.

6. Compare normalised edge sets before simpleFit() or scoring.

7. Report:
   - source supply row count
   - joined same-item destination demand row count
   - provider price-only edge count
   - provider price-and-units edge count
   - legacy edge count
   - matching edge count
   - provider-only edges
   - legacy-only edges
   - first few mismatches grouped by reason if obvious
```

### Known Blocker

The raw current edge set may not be externally exposed without inspecting or instrumenting legacy internals.

So the validation method has two phases:

```text
Phase A — provider self-check:
    verify SQL result shape against direct relational expectations
    report counts and top-N gain edges
    no legacy inspection required

Phase B — legacy parity check:
    after architecture-first phase is accepted,
    inspect only the narrow current one-hop edge discovery seam
    expose or instrument raw edge output before cargo fitting/scoring
```

That is not a blocker for designing the provider.  
It is a blocker for claiming parity.

---

## 5. Fields Needed from Schema / Indexes

Required tables:

```text
StationItem
Station
```

Required `StationItem` fields:

```text
station_id
item_id
supply_price
supply_units
supply_level
demand_price
demand_units
demand_level
modified
```

Required `Station` fields:

```text
station_id
system_id
```

Useful existing indexes:

```text
StationItem primary key:
    (station_id, item_id)

StationItem demand-price index:
    (item_id, demand_price) WHERE demand_price > 0

StationItem supply-price index:
    (item_id, supply_price) WHERE supply_price > 0

Station by system:
    Station(system_id)
```

For this first seam, `System` is not required.

```text
exclude_destination_system_ids can be applied through Station.system_id.
System should only be joined later if names, coordinates, or geometry are requested.
```

---

## 6. Open Parity Risks Requiring Later Legacy Inspection

These are deliberately deferred until after the provider shape exists.

```text
1. Whether current one-hop discovery treats price > 0 as sufficient,
   or also requires units > 0 by default.

2. Whether price-only mode or price-and-units mode matches legacy raw edge discovery.

3. Whether supply_level / demand_level affect eligibility,
   or are only carried forward for display/scoring.

4. Whether source and destination modified timestamps are carried directly,
   transformed through parse_ts(), averaged, or converted into age fields.

5. Whether current item filters operate on item IDs, names, categories,
   partial-name matches, or avoid rules before this seam.

6. Whether same-station source→destination edges are currently impossible,
   ignored, or filtered elsewhere.

7. Whether Station.market and itemCount affect current raw edge discovery.
   This is a known trap and must not be assumed.

8. Whether explicit --from / --to anchor checks happen before or after
   trade-edge discovery in a way that affects candidate edge visibility.

9. Whether current behaviour includes stale rows then filters later,
   or excludes them before edge discovery.

10. Whether route state removes destinations before get-trades style logic,
    especially avoid/unique/loop/via semantics.

11. Whether current edge discovery includes item names or wrapper objects
    that imply additional hidden filtering.
```

---

## Prototype Success Criterion

The first prototype succeeds only if it can produce raw profitable edge sets for:

```text
single source station
unbounded mode
minimal filters
price-only edge mode
price-and-units edge mode
no cargo fitting
no scoring
no rendering
```

Parity with current behaviour is not proven until the raw legacy edge set is exposed and compared before downstream route logic mutates the observable result.

The first decision point is not “is the route identical?”

It is:

```text
Can SQL reproduce the raw one-hop candidate edge set before TradeCalc-style route logic changes the observable output?
```