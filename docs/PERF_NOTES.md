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

Status: first baseline not yet recorded

For each baseline capture, record:

- date
- DB shape / size note
- command corpus version
- cold timings
- warm timings
- memory notes if available
- caveats

### Baseline template

#### Baseline ID
Date:
DB note:
Command corpus version:
Notes:

##### Cold timings
- `local`:
- `market`:
- `buy`:
- `sell`:
- `nav`:
- `rares`:
- `trade`:
- `run-short`:
- `run-typical`:
- `run-wide`:

##### Warm timings
- `local`:
- `market`:
- `buy`:
- `sell`:
- `nav`:
- `rares`:
- `trade`:
- `run-short`:
- `run-typical`:
- `run-wide`:

##### Memory notes
- RSS after `TradeDB.load`:
- RSS after `TradeCalc.__init__`:
- Peak memory during `run`:
- Other notes:

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

Still pending:
- first live cold/warm baseline capture
