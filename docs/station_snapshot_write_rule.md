# Station Snapshot Write Rule — Fix Specification

*Spec. 2026-06-11. Separate from the planner Slice 24 work — this is
import/write-path, not planner. Both `spansh_plug.py` writers were
converted the same day (commit `b2c3b90e`); the audit checklist below
remains open.*

---

## The invariant

A station's market data arrives as a **whole snapshot** — one observation
of the entire market at one moment, whether it comes from an EDDN message
(via ZMQ, written by the listener) or from a spansh dump (written by
`spansh_plug.py`). It is never legitimately piecemeal.

Therefore every market row for a station must carry the **same
`modified` timestamp**. A station with mixed timestamps is the footprint
of a writer treating rows as individual sources of truth.

Live data (2026-06-11) confirms the invariant holds where writers respect
it: 99.4% of the 94,344 stations with market rows are perfectly uniform
locally; both server instances show the same shape (~0.05% mixed).

## The write rule

For any incoming station snapshot, from any source:

```text
if (newest existing modified for this station) > (snapshot timestamp):
    skip the WHOLE station — write nothing, delete nothing
else:
    DELETE every market row for the station
    INSERT the snapshot's rows, all at the snapshot timestamp
```

Never merge. No per-row timestamp guards, no keep-lists, no
who-wrote-this-row conditions. Whoever owns the newest data owns the
whole station.

Skipping is correct, not lossy: if the existing snapshot is newer, items
the old dump lists but the newer snapshot does not were **not in the
market** at the newer time. Inserting them would add stale information —
which is exactly the fault this rule removes.

## Current state of the writers

### Listener (`tradedangerous_listener.py`) — already compliant

The ZMQ market path does delete-all + insert ("Snapshot semantics (as
live): replace station market rows", ~line 1988). No change needed,
beyond confirming it also gates on "incoming newer than existing" rather
than trusting message order.

### `spansh_plug.py` market write — converted (commit `b2c3b90e`)

The per-station market write previously did per-row merging: upsert
with a `ts_sp > modified` guard per row, then delete rows missing from
the dump — but only spansh-written rows (`from_live = 0`) not newer
than the dump.

Proven consequence (from_live split on the local mixed stations:
87,290 of 87,296 stale rows were spansh-written): when a dump's
per-station data was older than fresher listener rows, the guard
correctly spared the live rows but **inserted the dump's catalogue
extras at the dump's older timestamp underneath them**. That was the
mixed-timestamp factory.

Now fixed: the upsert/keep-list/guarded-delete dance is replaced with
the write rule above — one `max(modified)` skip check, then delete-all
and insert the whole snapshot.

### `spansh_plug.py` ShipVendor write — converted (commit `b2c3b90e`)

The shipyard-stock table (`ShipVendor`, which ships each station sells)
was maintained with the same per-row merge pattern — and delisted ships
were never deleted at all. The same skip-or-replace conversion fixed
both faults in the same commit.

## Audit checklist (complete before calling the fault closed)

1. **Enumerate every writer of `StationItem` / `ShipVendor`** beyond the
   two above — the local import path (listener-produced files into the
   local DB) and any remaining import commands — and verify each is
   whole-station or a faithful copy of an upstream that is.
2. **`_cleanup_absent_stations`** (spansh_plug ~line 856): deletes rows
   at stations absent from a dump. A deleter cannot create mixed
   timestamps, but review it under the snapshot rule for consistency.
3. **Listener maintenance purge** (age-based row deletion, ~line 2580):
   uniform stations age as a block, so the purge deletes whole stations
   or nothing — consistent with the rule. Confirm, no change expected.
4. After deployment: re-run the uniformity query (in
   `docs/Planner/timing_baselines.md` session history / the MariaDB
   variants below) and watch the mixed count decay to zero as listener
   traffic replaces the residue.

## Verification queries

SQLite (local):

```sql
SELECT COUNT(*) AS stations, SUM(n_ts = 1) AS uniform, SUM(n_ts > 1) AS mixed
FROM (SELECT station_id, COUNT(DISTINCT modified) AS n_ts
      FROM StationItem GROUP BY station_id);
```

MariaDB (server): same, with a derived-table alias appended
(`... GROUP BY station_id) AS per_station;`).

## Relationship to the planner work

Independent. The planner's Slice 24 `--age` station-level cut relies on
the same invariant but is exact regardless of this fix (it retains the
row-level predicate as belt and braces). This fix makes the invariant
true by construction instead of true at 99.4%.
