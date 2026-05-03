# PERF_NOTES

Purpose: capture live benchmark commands, before/after timings, memory notes, query plans, and checkpoint-specific performance evidence during the refactor.

## Benchmark command set

Status: fixed for checkpoint A baseline capture on 2026-04-16

Validation basis:
- validated against the live packaged SQLite database
- database refreshed via import roughly one hour before command validation
- commands below were selected only after real command execution confirmed non-empty, meaningful output

Canonical corpus:

### `local`
Purpose: preload-bound lookup and nearby-system/station discovery
Command:
```text
trade local "Colonia" --ly 20
```

### `market`
Purpose: station-specific market read path
Command:
```text
trade market "Colonia/Jaques Station"
```

### `buy`
Purpose: item lookup plus localised seller search
Command:
```text
trade buy "Fruit and Vegetables" --near "Colonia" --ly 20 --supply 1 --limit 20
```

### `sell`
Purpose: inverse item lookup plus localised buyer search
Command:
```text
trade sell "Fruit and Vegetables" --near "Colonia" --ly-per 20 --demand 1 --limit 20
```
Notes:
- accepted as representative enough for checkpoint A even though the validated top results were all in-system (`DistLy 0.00`)

### `nav`
Purpose: routing/path construction benchmark in inhabited space
Command:
```text
trade nav "Delta Pavonis" "Cemiess" --ly-per 15
```

### `rares`
Purpose: rare-goods command path
Command:
```text
trade rares "Sol" --ly 200 --limit 20
```

### `trade`
Purpose: lean direct trade comparison against preload-bound commands
Command:
```text
trade trade "Colonia/Akinyemi Horticultural Market" "Colonia/Jaques Station"
```

### `run-short`
Purpose: short constrained run baseline
Command:
```text
trade run --from "Colonia/Akinyemi Horticultural Market" --to "Colonia/Jaques Station" --capacity 64 --credits 1000000 --hops 1 --jumps-per 1 --ly-per 20
```

### `run-typical`
Purpose: representative seeded run baseline
Command:
```text
trade run --from "Colonia/Jaques Station" --capacity 128 --credits 5000000 --hops 2 --jumps-per 2 --ly-per 20
```

### `run-wide`
Purpose: broader/heavier run baseline
Command:
```text
trade run --from "Colonia/Jaques Station" --start-jumps 1 --capacity 128 --credits 5000000 --hops 3 --jumps-per 2 --ly-per 20 --routes 3
```
Notes:
- this is the exact validated command shape
- `--start-jumps 1` and `--hops 3` are the main search-broadening controls
- `--routes 3` increases displayed output count rather than search breadth, so keep that in mind when interpreting render/total timings

## Live SQLite baselines

Status: first cold/warm baseline recorded on 2026-04-17

For each baseline capture, record:

- date
- DB shape / size note
- command corpus version
- cold timings
- warm timings
- memory notes if available
- caveats

### Baseline 2026-04-17 — live packaged SQLite — checkpoint A first capture

#### Baseline ID
Date: 2026-04-17
DB note: live packaged SQLite database; benchmark executed from the instrumented local working tree on Windows after reboot
Command corpus version: checkpoint A fixed corpus validated on 2026-04-16
Notes:
- Cold and warm timings were captured by a single successful post-reboot harness run.
- A prior post-reboot attempt failed due to Windows console encoding, not command/runtime logic.
- Warm timings are recorded as observed and are not uniformly faster than cold timings.

##### Cold timings
- `local`: 9.030s
- `market`: 6.620s
- `buy`: 6.790s
- `sell`: 7.290s
- `nav`: 7.390s
- `rares`: 6.620s
- `trade`: 0.750s
- `run-short`: 26.370s
- `run-typical`: 28.380s
- `run-wide`: 32.760s

##### Warm timings
- `local`: 6.980s
- `market`: 6.920s
- `buy`: 7.100s
- `sell`: 7.770s
- `nav`: 8.180s
- `rares`: 7.090s
- `trade`: 0.860s
- `run-short`: 28.890s
- `run-typical`: 30.290s
- `run-wide`: 30.720s

##### Memory notes
- RSS after `TradeDB.load`: not captured
- RSS after `TradeCalc.__init__`: not captured
- Peak memory during `run`: not captured
- Other notes:
  - Successful Windows shell execution required UTF-8 console/Python settings (`chcp 65001`, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`) because DEBUG output included a Unicode arrow in `reloadCache` logging.
  - Harness summary/logs were written under `tmp/checkpoint_a_baseline_20260417_143221/`.

## Query plans

Status: captured on 2026-04-16 against the live packaged SQLite database

### exact `System.name = ?`
Query:
```sql
SELECT system_id FROM System WHERE name = ?
```
Parameters:
```text
('Colonia',)
```
Plan:
```text
SEARCH System USING INDEX idx_system_by_name (name=?)
```

### exact `Station.name = ?`
Query:
```sql
SELECT station_id, system_id FROM Station WHERE name = ?
```
Parameters:
```text
('CURY',)
```
Plan:
```text
SEARCH Station USING INDEX idx_station_by_name (name=?)
```

### `system/station` join lookup
Query:
```sql
SELECT st.station_id
FROM Station AS st
JOIN System AS sy ON sy.system_id = st.system_id
WHERE sy.name = ? AND st.name = ?
```
Parameters:
```text
('Col 285 Sector LE-G c11-33', 'CURY')
```
Plan:
```text
SEARCH sy USING INDEX idx_system_by_name (name=?)
SEARCH st USING COVERING INDEX idx_station_by_system_name (system_id=? AND name=?)
```

### partial system
Query:
```sql
SELECT system_id FROM System WHERE name LIKE ?
```
Parameters:
```text
('Colo%',)
```
Plan:
```text
SEARCH System USING INDEX idx_system_by_name (name>? AND name<?)
```

### partial station
Query:
```sql
SELECT station_id, system_id FROM Station WHERE name LIKE ?
```
Parameters:
```text
('CURY%',)
```
Plan:
```text
SEARCH Station USING INDEX idx_station_by_name (name>? AND name<?)
```

## Checkpoint evidence

### Checkpoint A — Instrumentation and production baselines

Evidence now present:
- timing helper exists
- top-level execution timings exist
- benchmark command set is defined and validated on the live packaged SQLite DB
- resolver candidate query plans are captured
- first live cold/warm baseline is recorded in this document

Still pending:
- none within checkpoint A baseline capture

### Checkpoint H — Migrate `local`

#### Before (checkpoint A warm baseline, 2026-04-17)
- `local`: 6.98s warm

#### After (post-H warm, 2026-04-30, live SQLite)
- `local`: 0.85s warm

#### Improvement
- ~8× faster warm. User description: "effectively instant."

#### Mechanism
- `wantsTradeDB=True` → `needs = Needs.RESOLVER`: full `TradeDB.load()` no longer invoked.
- SQL `BETWEEN` bounding-box pre-filter + Python sphere check replaces `genSystemsInRange()` (which required the full in-memory stellar grid).
- Station flag filters pushed to SQL. Age/count via single StationItem aggregate subquery.

#### Caveats
- `Mkt` column in `--detail` mode reads `station.market` directly from DB. Legacy `_loadStations()` coerced this to `Y` in-memory when `itemCount > 0`. The `--trading` filter is correct (uses EXISTS over StationItem); only the rendered display of the raw flag differs for edge-case stations where the flag and data disagree. Deliberate ORM behaviour change, not a regression.

### Checkpoint I — Migrate `market`, `buy`, `sell`

#### I2 — `market` (2026-05-01, live SQLite)

##### Before (checkpoint A warm baseline, 2026-04-17)
- `market`: not individually timed in checkpoint A baseline; estimated comparable to `local` (~6–7s warm) given same full-preload path.

##### After (post-I2 warm, 2026-05-01, live SQLite)
- `trade market "Colonia/Jaques Station"`: effectively instantaneous (sub-100ms, user description: "press enter, instant joy")
- `trade market "Colonia/Jaques Station" --detail`: 578ms warm

##### Improvement
- Basic query: preload overhead eliminated entirely; perceived as instant.
- `--detail` variant: 578ms includes two additional aggregate queries (avg buy/sell per visible item).

##### Mechanism
- `needs = Needs.RESOLVER`: full `TradeDB.load()` no longer invoked.
- `tdb.session` (SQLAlchemy ORM session) replaces ad-hoc `Session(bind=tdb.engine)`.
- StationItem rows fetched via single parameterised SQL query; item objects resolved via identity-map PK lookup (`item_by_id()`).
- No in-memory commodity index or station dict traversal.

#### I3 — `buy` (2026-05-02, live SQLite)

##### Before (checkpoint A baseline, 2026-04-17)
- `buy`: 6.79s cold, 7.10s warm
- Command:
```text
trade buy "Fruit and Vegetables" --near "Colonia" --ly 20 --supply 1 --limit 20
```

##### Regressed I3 state
- Cold: ~13.3s (two measurements post-reboot: 13348ms, 13347ms)
- Warm: ~1.8s (two measurements: 1737ms, 1888ms)
- Root cause: the first migrated buy path expanded broad candidate sets before enough filtering was applied. It also performed station-wide age aggregation unconditionally and applied `--near` too late for high-volume item/ship searches.

##### Fixed I3 state
- Command:
```text
trade buy "Fruit and Vegetables" --near "Colonia" --ly 20 --supply 1 --limit 20
```
- Cold-ish: 3.88s
- Warm: ~1.0s
- Result: faster than checkpoint A legacy cold and warm baselines.

##### Age-filtered evidence
- Command:
```text
trade buy "Fruit and Vegetables" --near "Colonia" --ly 20 --supply 1 --limit 20 --age 3
```
- Cold-ish: 3.77s
- Notes: after station-first narrowing, `--age` is no longer the dominant performance lever for this localised single-commodity search.

##### Ship-mode evidence
- Command:
```text
trade buy "Cobra Mk III" --near "Sol" --ly 50 --limit 20
```
- Cold-ish: 1.51s
- Notes: ship availability search now uses the same near-station-first candidate narrowing and no longer expands global ShipVendor candidates before applying the spatial constraint.

##### Improvement
- Canonical buy cold: 6.79s legacy baseline → 3.88s fixed I3 (~43% faster).
- Canonical buy warm: 7.10s legacy baseline → ~1.0s fixed I3 (~7× faster).
- Regressed I3 cold: ~13.3s → 3.88s fixed I3 (~71% faster).

##### Mechanism
- `needs = Needs.RESOLVER`: full `TradeDB.load()` no longer invoked.
- `--near` searches materialise nearby station IDs first, then probe `StationItem` or `ShipVendor` only for those station chunks.
- `--age` is applied during `StationItem` lookup rather than after broad result expansion.
- Unconditional station-wide age aggregation was removed.
- Station hydration is chunked defensively to avoid backend parameter limits.
- Ship sorting tolerates unknown ship costs.
- Fleet/Odyssey state is derived from `type_id`.
- Exact sphere distance check remains in Python after the database-side bounding-box cut.
- Validation: buy smoke tests passed; ship mode passed; `pytest` clean.

#### I4 — `sell` (2026-05-03, live SQLite)

##### Before (checkpoint A baseline, 2026-04-17)
- `sell`: 7.29s cold, 7.77s warm
- Command:
```text
trade sell "Fruit and Vegetables" --near "Colonia" --ly-per 20 --demand 1 --limit 20
```

##### After (post-I4, 2026-05-03, live SQLite)
- Cold: 1.23s
- Warm: 0.82s

##### Improvement
- Cold: 7.29s → 1.23s (~6× faster).
- Warm: 7.77s → 0.82s (~9.5× faster).

##### Mechanism
- `needs = Needs.RESOLVER`: full `TradeDB.load()` no longer invoked.
- `--near` bounding-box materialises nearby station IDs before `StationItem` is queried.
- `--age`, `--demand`, `--lt`, `--gt` filters pushed into SQL.
- Station hydration chunked at 900 via `joinedload(orm.Station.system)`.
- Legacy station wrapper methods replaced with ORM attributes and `type_id`-based fleet/odyssey helpers.
- Context-aware `NoDataError` includes item name and near-system.
- Validation: `pytest` clean.

### Checkpoint K — Reduce `TradeCalc` setup cost

#### K1 — Instrumentation: sub-phase timings and row counts (2026-05-03, live SQLite)

##### Sub-phase time_block phases (already present, confirmed active at -w)
- `item_filter`: <1ms across all shapes
- `query_prep`: <1ms across all shapes
- `row_scan`: dominant cost — see breakdown below
- `finalize`: 30–60ms

##### Row counts (identical across all tested shapes)
- Rows seen (SQL result): 9,137,044
- Buy-map entries kept: 9,116,973
- Sell-map entries kept: 2,652,140
- `restrict_station_ids` active: No (hook exists but never passed at the run_cmd.py call site)

##### row_scan timings by benchmark shape
| Shape | row_scan | getBestHops total | TradeCalc.__init__ total |
|-------|---------|-------------------|--------------------------|
| run-typical (--hops 2, warm) | ~21.0–21.8s | ~1.0s | ~21.4–21.8s |
| run-wide (--hops 3 --start-jumps 1, run 1) | ~21.6s | ~2.5s | ~21.7s |
| run-wide (--hops 3 --start-jumps 1, run 2) | ~44.7s | ~4.7s | ~44.7s |
| run-short (--from A --to B --hops 1, warm) | ~46.8–48.1s | ~43–45ms | ~46.9–48.2s |

##### Key findings
- Almost all `TradeCalc.__init__` time is inside `row_scan`. The phase includes SQL result streaming plus the Python row loop; the evidence proves the cost is there, but the internal split between streaming, DBAPI conversion, timestamp parsing, and Python map allocation is not yet measured.
- Every tested command shape scans the same 9,137,044 rows, including the tightly bounded `--from A --to B --hops 1 --jumps-per 1` shape. Station restriction is not currently affecting TradeCalc construction.
- `getBestHops` is fast relative to init: 1–2.5s total across all hops for the unconstrained shapes; ~43ms for the bounded one-hop shape.
- The 21s → 44–48s row_scan variance is unexplained from current evidence. GC pressure from multi-million-entry map allocation is a plausible hypothesis but not proven. It does not affect the primary diagnosis: unrestricted 9.1M-row scanning is the root problem.

##### Next step
K3 and beyond: broader candidate narrowing for multi-hop and open-ended shapes.

#### K2 — One-hop station-to-station restriction (2026-05-03, live SQLite)

##### Mechanism
`restrict_station_ids` derived before `TradeCalc` construction in `run_cmd.py` when all hold: `origPlace` is a Station, `destPlace` is a Station, `hops == 1`, no `startJumps`, `endJumps`, `viaPlaces`, `loop`, `goalSystem`, or `shorten`. Passes `[origPlace.ID, destPlace.ID]`; otherwise no restriction.

##### Results — run-short benchmark (--from A --to B --hops 1 --jumps-per 1 --ly-per 20)
| Metric | Before K2 | After K2 |
|--------|-----------|----------|
| Rows seen | 9,137,044 | 139 |
| `row_scan` | ~46–48s | ~3–4ms |
| `TradeCalc.__init__` | ~47–48s | ~8ms |
| `command_run` | ~47–48s | ~54ms |
| Route output | same | same |

Total command time is now dominated by `TradeDB.__init__` (~7–8s, legacy full load — not yet addressed).

##### Semantic safety confirmed
- `checkStationSuitability` checks presence in `calc.stationsSelling`/`stationsBuying` for the explicit origin and destination; both are included in the restricted scan, so suitability and `NoDataError` behaviour is unchanged.
- Guard conditions prevent the restriction from applying to any shape that could require intermediate stations.
