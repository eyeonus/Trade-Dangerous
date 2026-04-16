# PERF_NOTES

Purpose: capture live benchmark commands, before/after timings, memory notes, query plans, and checkpoint-specific performance evidence during the refactor.

## Required sections

### Benchmark command set
Record the exact commands used for repeatable before/after timing.

### Live SQLite baselines
Record:
- date
- DB shape / size note
- cold timings
- warm timings
- memory notes if available

### Query plans
Record:
- exact `System.name = ?`
- exact `Station.name = ?`
- `system/station`
- partial system
- partial station

### Checkpoint evidence
For each checkpoint that changes execution flow or preload scope, add:
- before
- after
- interpretation
- caveats
