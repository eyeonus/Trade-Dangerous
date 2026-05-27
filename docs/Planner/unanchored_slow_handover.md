# Unanchored Slow-Case Investigation — Handover Brief

*Session date: 2026-05-27. Originally prepared for a fresh session picking up the investigation. Investigation now closed; document updated with findings and remediation. See Investigation Outcome below.*

---

## Task Purpose

Investigate why the new planner's **single-hop unanchored** `trade run` shape (no `--from`, no `--to`) does not complete in usable time, while `--old` returns comparable broader queries in seconds.

Originally framed as the Slice 9 deferred wall-clock re-baseline. Escalated to root-cause investigation when initial probes failed to return at all.

**Mode:** research project. No application code changes. Investigative probe scripts are permitted and are not committed (project memory rule).

---

## Investigation Outcome

Investigation complete (2026-05-27). Both blockers cleared. Remediation
shape settled and empirically proven against the live database.

### Headline

The unanchored slow case has two SQLite mechanisms operating together:

1. **Empty-temp pathology.** SQLite picks a query plan for the match
   step that drives a cross-join from `System × System` (bbox-filtered)
   and treats the temp tables (`td_unanchored_supply`,
   `td_unanchored_demand`) as inner probes. When either temp table has
   no rows, the match still evaluates millions of spatial pairs before
   discovering zero matches — ~5 minutes per empty walk on the live
   data. Observed across v2, v3, v6.
2. **Bad join order from missing temp-table statistics.** Even on
   non-empty temps, SQLite picks the same System-driven plan because
   the temp tables have no row-count statistics. The cost model
   anchors on `System` (which it knows from ANALYZE on database build)
   and inverts the join: a 1,800-row temp table is treated as the
   inner side of an 80,000-row scan instead of the outer driver.
   Observed in v3: 304 s for one Tritium match with non-empty temps,
   same plan as the empty case.

`ANALYZE` on the temp tables fixes mechanism 2 by giving the planner
real cardinality. Tritium drops from 304 s to 6.4 s; the full run
drops from "does not complete in usable time" to ~3 minutes
wall-clock and returns a valid route (v4, v4b). `ANALYZE` does NOT
fix mechanism 1 — running it on an empty table writes nothing useful
to `sqlite_stat1`, so the bad plan persists (v6: 256 s on walk 1 with
empty temps, same plan).

### Remediation shape (settled)

Both pieces required, inline in `tradedangerous/planner/data_gateway.py`:

1. **Empty-temp guard.** `SELECT 1 FROM <temp> LIMIT 1` on each side
   before calling `_match_via_on_demand_reach`. If either is empty,
   return the empty result tuple directly. Microsecond cost per
   skipped walk; eliminates the empty-temp pathology.
2. **`ANALYZE td_unanchored_supply; ANALYZE td_unanchored_demand;`**
   after each per-commodity reduction, before the (now-non-empty)
   match. ~0.2 ms per call on SQLite (~6 ms total across the whole
   walk in v4b). Flips the SQLite plan from System-driven
   (`SCAN System_1`) to temp-driven (`SCAN td_unanchored_supply`).

Both pieces use SQL identical across SQLite and MariaDB/MySQL
(`ANALYZE <table>`, `SELECT 1 FROM <table> LIMIT 1`), so they stay
inline in the planner — no `db/utils.py` dialect dispatch needed.
Cost characteristics differ between backends but behaviour is correct
on both.

Optional follow-up (not blocking, separate decision):

3. **SQL `LIMIT _UNANCHORED_MATCH_LIMIT` on the match query.** Every
   non-empty match in v4b had `hit_cap=True`; SQL currently
   materialises the full ORDER BY then Python takes the first 50. A
   SQL `LIMIT` would let SQLite use a top-N heap and shave the
   10-15 s tail on the densest commodities.

### Performance evidence (v4b)

End-to-end probe run, `--max-price 0` (cap disabled), realistic
station filters (`--age 3 --fc N --planetary N --pad-size L`):

```text
walks attempted              : 217
skipped (empty temp tables)  : 190   (87.6% of walks)
non-empty match calls        : 27
total ANALYZE time           : 0.006 s
total non-empty match time   : 153.4 s
mean non-empty match time    : 5.7 s
slowest non-empty match      : 15.5 s (Liquor)
route returned               : Bhattra/Levinson Orbital ->
                                Fengiri/Mille Gateway,
                                35,742,249 cr profit, 2 jumps
```

End-to-end wall-clock with remediation: ~3 minutes against the live
database under realistic filters. Down from "does not complete in
usable time".

Default `--max-price` (1.5M cap) under the same conditions (v5)
returns the identical route, reductions stay sub-second per call,
and total non-empty match time falls to 129 s — the cap excludes
carrier-noise rows from the temp tables and incidentally helps the
sort cost.

---

## Current Progress & Blockers

### Root cause

Initial proven mechanism: empty unanchored temp tables.
Later probes also proved the non-empty missing-statistics case; see Investigation Outcome above.

The hot path is `_match_via_on_demand_reach` in `tradedangerous/planner/data_gateway.py`, called once per commodity inside `fetch_unanchored_trade_candidates`.

SQLite picks a query plan that drives the cross-join from `System × System` (bbox-filtered using `idx_system_by_pos`) and treats the run-scoped temp tables (`td_unanchored_supply`, `td_unanchored_demand`) as inner probes at the *end* of the plan.

When the temp tables are empty — which happens for every carrier-only commodity at the top of the bound list under `--fc N` — SQLite still evaluates millions of `(System_1, System_2)` spatial pairs before discovering there are zero matches.

Observed per-call cost: **299.86 s** when both temp tables had 0 rows. Consistent with the 10-minutes-to-three-walks pattern from the earlier probe.

### The smoking gun — EXPLAIN QUERY PLAN

Captured by `probe_unanchored_walk.py` (probe v2) on commodity `item_id=129022398` (Titan Deep Tissue Sample), `supply=0 demand=0 match=299.860s`:

```
(7,   0, 0, 'SCAN System_1 USING COVERING INDEX idx_system_by_pos')
(9,   0, 0, 'SEARCH System_2 USING COVERING INDEX idx_system_by_pos (pos_x>? AND pos_x<?)')
(78,  0, 0, 'SEARCH td_unanchored_demand USING INDEX ix_td_unanchored_demand_sys (system_id=?)')
(87,  0, 0, 'BLOOM FILTER ON td_unanchored_supply (system_id=?)')
(99,  0, 0, 'SEARCH td_unanchored_supply USING AUTOMATIC COVERING INDEX (system_id=?)')
(154, 0, 0, 'USE TEMP B-TREE FOR ORDER BY')
```

Full probe output in `/home/stef/Fork/Trade-Dangerous/probe.log`. Probe script in `/home/stef/Fork/Trade-Dangerous/probe_unanchored_walk.py`.

### Mechanism explanation

- Temp tables are created at runtime with no statistics
- SQLite's planner has no cardinality estimate for them, so it guesses
- `System` has good stats (covering spatial index, well-known size) so the planner anchors the join on it
- The bbox filters live entirely between `supply_sys` and `demand_sys`, so SQLite can apply them as a `System × System` self-join before reaching the temp tables
- Per match call, this evaluates roughly 5-15 million spatial pairs (System ~80K rows, ~50-200 in-range neighbours each) regardless of whether the temp tables contain anything

### Structural compounding factor

`fetch_unanchored_trade_candidates` walks commodities in descending profit-per-unit bound order, with cutoff `capacity * profit_bound <= best_total_profit`. The bound list is dominated at the top by carrier-noise commodities (Titan Deep Tissue Sample, Thargoid Probe, Titan Drive Component, etc.) because their raw prices are silly-high.

Under `--fc N`, all these commodities reduce to 0 supply / 0 demand rows. `best_total_profit` therefore stays at 0 indefinitely, so the cutoff never fires. The walk plods through every commodity in the bound list (~396 commodities observed) and pays the 5-minute waste on each empty match call.

### Blockers — both cleared

1. **Non-empty case** — cleared by v3, v4, v4b. The non-empty case
   runs the same System-driven plan as the empty case under SQLite's
   default heuristic (304 s for Tritium in v3). `ANALYZE` on the temp
   tables flips the plan to temp-driven (first plan line becomes
   `SCAN td_unanchored_supply`); the same Tritium call drops to 6.4 s.
2. **Default `--max-price`** — cleared by v5. With the default 1.5M
   cap in force, supply/demand reductions stay sub-second per call
   (35 s combined total across 217 walks). The original traceback
   that landed inside `_reduce_supply_by_system` was a `^C` artefact
   caught at the next Python bytecode boundary after a prior match
   call's slow SQL — not evidence of a second pathology.

---

## Outstanding Issues

### Investigative — both cleared

1. Non-empty match case probe — done (v3, v4, v4b, v6). Plan
   identical to empty case under SQLite's default heuristic; `ANALYZE`
   flips it for non-empty cases but does not help empty cases.
2. Default-`--max-price` supply reduction probe — done (v5).
   Reductions stay sub-second under the default cap; cap is innocent
   on reductions, and incidentally beneficial on matches (24 s faster
   total than `--max-price 0`).

### Documentation — to update alongside remediation

3. `docs/Planner/ninth_slice_completion_report.md`:
   - "Performance Re-baseline (out of slice)" section needs the
     honest post-fix numbers. v4b's 153 s total non-empty match time
     and ~3 minute end-to-end wall-clock are the numbers to record
     once the remediation lands.
   - "Fixed-station multi-hop route quality (Slice 8 follow-up)"
     section is stale (describes the regression as "beam-search
     myopia"; was actually a phantom demand row per
     `slice_8_followup_handover.md` close-out). Independent of this
     investigation but worth refreshing in the same documentation
     pass.
4. `docs/Planner/SLICE_SUMMARY.md`:
   - Slice 6 caveat needs updating with the match-step query-plan
     pathology mechanism and the v4b clean-data wall-clock figures
     (no longer hand-wave estimates).
5. Unanchored confirmation prompt (in
   `tradedangerous/commands/run_cmd.py` around line 1476): with the
   remediation landed and wall-clock at ~3 minutes under realistic
   filters, the prompt's "anywhere from minutes to substantially
   longer" wording remains accurate but may want softening. Decision
   belongs to the remediation session.

### Remediation — final shape

Settled by v3-v6. Both pieces required, in this order, inline in
`tradedangerous/planner/data_gateway.py`:

1. **Empty-temp guard** before `_match_via_on_demand_reach`. Issue
   `SELECT 1 FROM <temp> LIMIT 1` on each temp; if either returns no
   row, skip the match and return `([], 0, 0, False)` directly.
   Handles the empty-temp pathology (which `ANALYZE` alone cannot
   fix — see v6 in Falsified Hypotheses).
2. **`ANALYZE td_unanchored_supply; ANALYZE td_unanchored_demand;`**
   after the guard passes, before the match. Flips the SQLite plan
   from System-driven to temp-driven; identical SQL on SQLite and
   MariaDB/MySQL so it stays inline in the planner.

Optional follow-up (separate decision; not blocking the fix):

3. **SQL `LIMIT _UNANCHORED_MATCH_LIMIT` on the match query.** Every
   non-empty match in v4b had `hit_cap=True`, so the LIMIT would map
   directly to real behaviour and let SQLite use a top-N heap instead
   of full ORDER BY materialisation. Would shave the 10-15 s tail
   observed on the densest commodities.

Query restructure and architectural reconsideration are no longer on
the table — the planner-heuristic-driven fix (`ANALYZE`) is
sufficient once the guard handles the empty case.

---

## Hypotheses Already Falsified (do not retread)

Each of these was suspected and falsified during this session. The fresh session should skip them.

1. **Slice 9 `--max-price` predicate broke the query plan.** Falsified — probe with `--max-price 0` still hangs (the empty-temp pathology is in the match step, not the reductions). 
Command used: 
```bash
trade run --capacity 720 --credits 200000000 --hops 1 --jumps-per 3 \
  --ly-per 30 --age 3 --fc N --planetary N --pad-size L --max-price 0
```
Observed still climbing after over 6 minutes.
2. **"It must just be much more data now."** Rejected as an unsupported explanation. The database is upsert-based and recently cleaned; there is no evidence that bulk data growth is the primary cause. The old path completing is an existence proof that the workload is not intrinsically multi-hour, though it does not prove the new query shape should remain fast.
3. **Beam-search myopia (Slice 8 follow-up suspicion).** Falsified earlier — was a phantom demand row in legacy data, close-out in `slice_8_followup_handover.md`.
4. **"New planner is fundamentally slower than `--old` on clean data."** Retracted. `--old`'s 17s on the harder query proves the work isn't intrinsically multi-hour. The slowness has a specific fixable mechanism.
5. **"`--old` has no early-cutoff trick".** Retracted — this was a confident pronouncement made about a quarantined module without basis. The fresh session has no need to characterise `--old` and should resist the temptation to do so.
6. **"`_reduce_supply_by_system()` is the primary hot path."** Superseded for the proven empty-temp case. Earlier traceback landed there, but later probe evidence shows the empty-temp pathology is in `_match_via_on_demand_reach`. Do not prioritise supply reduction unless the default-cap probe or new timing proves it is independently slow.
7. **"`ANALYZE` alone is enough — the empty-temp guard is redundant."**
   Falsified by v6. Running `ANALYZE` on an empty table writes
   nothing useful to `sqlite_stat1`, so the planner falls back to
   the default-cardinality heuristic and picks the same
   System-driven plan as the no-`ANALYZE` case. Walk 1 (Titan Deep
   Tissue Sample, empty temps, post-`ANALYZE`) took 256 s — same
   plan as v3's no-`ANALYZE` empty case. The guard is load-bearing;
   both pieces of the remediation are required.

---

## Context Boundaries

### Quarantine status

The quarantine on `tradedangerous/tradecalc.py` and `tradedangerous/tradedb.py` was lifted **for the diagnostic session only**, on Tromador's explicit instruction, for the purpose of reading `getBestHops` to understand `--old`'s post-preload algorithm. The lift was used for a single targeted read.

**The quarantine is back in force by default.** The fresh session must treat both files as off-limits unless Tromador explicitly authorises another lift for a specific named purpose. Do not infer that "the previous session read these" means "you can too" — every quarantine lift is per-session and per-purpose.

The new planner code in `tradedangerous/planner/` is always permitted to read and modify.

### Research mode

The session is operating in research mode at Tromador's direction. **No application code changes.** Probe scripts are permitted and live at project root as throwaway files (not committed). Tromador will lift research mode when ready to remediate.

### Other constraints

- WSL2 Ubuntu environment on Tromador's machine (the "Zen" PC). Hardware is high-end (i9-13900K, 64GB RAM, Crucial T700 PCIe 5.0). Performance observations should not assume slow hardware.
- `--age 3` was used in the failing probe because Tromador's local DB has a freshest entry of ~2 days old. Slice plans citing `--age 1` may not work locally.

---

## Active Protocols

1. **Global CLAUDE.md** — Tromador Protocol. Tone, named commands, behavioural rules.
2. **Project CLAUDE.md** — Trade-Dangerous planner side-mission. Source quarantine, slice architecture, query patterns, data-scale awareness.
3. **Memory** — `/home/stef/.claude/projects/-home-stef-Fork-Trade-Dangerous/memory/MEMORY.md`. Project-specific feedback and references.

Particularly load-bearing rules to observe early:

- **No assumptions or backfill.** This session made multiple confident pronouncements without basis (mostly about `--old`) and was correctly pulled up on them. Do not characterise quarantined code from memory or inference.
- **Verification failure rule.** Several hypotheses were falsified during diagnosis; each falsification required dropping the hypothesis cleanly rather than salvaging it. Be ready to do the same.
- **Address Tromador as "you", not "Trom".** Third-person drift was a recurring issue and was specifically corrected mid-session. Apply this to chat, task descriptions, probe scripts, and any documents written.
- **No memory changes without instruction.**

---

## File / Dependency References

### Code touched or read

- `tradedangerous/planner/data_gateway.py` — the bug surface
  - `fetch_unanchored_trade_candidates` ~ line 1080
  - `_unanchored_item_bounds` ~ line 1194
  - `_reduce_supply_by_system` ~ line 1254
  - `_reduce_demand_by_system` ~ line 1324
  - `_match_same_system_trades` ~ line 1469
  - `_match_via_on_demand_reach` ~ line 1526 — **the hot path**
- `tradedangerous/planner/run_route.py`
  - `_plan_unanchored` ~ line 1141
- `tradedangerous/commands/run_cmd.py`
  - `run` ~ line 1445 — dispatches new planner vs `--old`
  - unanchored confirmation prompt ~ line 1476
- `tradedangerous/db/orm_models.py`
  - `System` line 124, `Station` line 152, `StationItem` line 250
  - Relevant indexes: `idx_system_by_pos` (covering), `si_itm_suppr` partial, `si_itm_dmdpr` partial
  - StationItem and Station are both `WITHOUT ROWID`
- `tradedangerous/tradecalc.py` — quarantined; read once during this session for comparative reasoning; not to be re-read without authorisation
  - `getBestHops` line 1015 — the legacy hop expansion entry point

### Probes (uncommitted, on disk)

All probes monkey-patch the four hot-path functions
(`_unanchored_item_bounds`, `_reduce_supply_by_system`,
`_reduce_demand_by_system`, `_match_via_on_demand_reach`) and
auto-confirm the unanchored prompt.

- `probe_unanchored_walk.py` (v2) + `probe.log` — captured the
  empty-temp EXPLAIN and the 299.86 s match-on-empty case.
- `probe_unanchored_walk_v3.py` + `probe_v3.log` — added empty-temp
  guard plus EXPLAIN-on-first-non-empty. Proved the non-empty case
  runs the same plan as the empty case under SQLite's default
  heuristic; Tritium match at 304 s.
- `probe_unanchored_walk_v4.py` + `probe_v4.log` — v3 plus
  `ANALYZE` on temp tables before each match. Proved the plan flips
  to temp-driven; Tritium drops from 304 s to 6.4 s. Tripped 10 s
  threshold at Palladium (13.6 s — same new plan, data-shape
  outlier).
- `probe_unanchored_walk_v4b.py` + `probe_v4b.log` — v4 with the
  slow threshold raised to 60 s so the run completes naturally. 217
  walks, 27 non-empty matches, 153 s total non-empty match time,
  valid route returned (Bhattra/Levinson Orbital → Fengiri/Mille
  Gateway, 35.7M cr).
- `probe_unanchored_walk_v5.py` + `probe_v5.log` — v4b without
  `--max-price 0` (default 1.5M cap in force). Cleared blocker 2:
  reductions stay sub-second per call, identical route, total
  non-empty match time falls to 129 s.
- `probe_unanchored_walk_v6.py` + `probe_v6.log` — v4b with the
  empty-temp guard removed, `ANALYZE` still in place. Falsified the
  ANALYZE-alone hypothesis: walk 1 empty match took 256 s, same
  System-driven plan as no-`ANALYZE`.

To clean these up after the remediation lands and the doc updates
in `SLICE_SUMMARY.md` and `ninth_slice_completion_report.md` are
complete:

```bash
rm probe_unanchored_walk*.py probe*.log
```

### Planner docs

- `docs/Planner/SLICE_SUMMARY.md` — required startup reading
- `docs/Planner/trade_run_black_box_spec.md` — required startup reading
- `docs/Planner/ninth_slice_implementation_plan.md` — Slice 9 plan with the deferred re-baseline that triggered this work
- `docs/Planner/ninth_slice_completion_report.md` — contains stale sections needing update
- `docs/Planner/slice_8_followup_handover.md` — prior handover; same convention as this one
- **This file:** `docs/Planner/unanchored_slow_handover.md`

### Branch state

- Branch: `release/v1`
- Recent relevant commits visible in `git log` (no need to recite them; the file state is the truth)
- Uncommitted: `tradedangerous/planner/run_route.py` carries a small comment Tromador is deliberately not committing. Do not touch it.

---

## Behavioural Tone

For the fresh session, take from Tromador's global CLAUDE.md and his project CLAUDE.md (both will load automatically). The points that came up specifically during this session:

- Professional engineering peer. Direct, confident, dry humour encouraged. UK English throughout.
- No assistant filler ("Of course!", "Great question!", etc.).
- **Second person address.** Talk to Tromador, not about him. Third-person drift was specifically called out this session.
- Tromador has chronic pain and chronic sarcoidosis. Brain fog is a real factor. Prefer simpler explanations of complex Python concepts; he comes from a Perl background and isn't a Python programmer.
- Game-knowledge pronouncements ("X is a rare", "Y is common", etc.) — don't. Verify or label as unverified. The planner works from database values, not lore.
- Don't editorialise. Don't expand scope. Don't "for safety" extras.
- Code output style: full functions or modules in fenced blocks, not pseudo-diffs (unless explicitly asked for a patch).
- When in doubt, ask — particularly about quarantine lifts, code changes, anything destructive.

---

## Immediate Recommended Next Step

Investigation is closed; the remediation shape (empty-temp guard +
`ANALYZE` on temp tables before match) is settled and empirically
proven. Apply the remediation when Tromador lifts research mode.

Code change site: `tradedangerous/planner/data_gateway.py`, inside
`fetch_unanchored_trade_candidates` (~line 1080), around the call to
`_match_via_on_demand_reach` (~line 1131). Both edits are small and
go in the same logical step.

After the remediation lands:
- Update `docs/Planner/SLICE_SUMMARY.md` (Slice 6 caveat, with v4b
  numbers).
- Update `docs/Planner/ninth_slice_completion_report.md` (the
  Performance Re-baseline section).
- Remove probe files and logs:
  `rm probe_unanchored_walk*.py probe*.log`
