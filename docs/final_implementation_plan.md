# Trade Dangerous — Final Implementation Plan

Status: Working execution plan  
Scope: Legacy cleanup + ORM-first performance refactor  
Working repo: `Tromador/Trade-Dangerous`  
Working line: `release/v1` on the fork, not a separate feature branch

## 1. Working model

All refactor work for this program lands on the fork:

- canonical upstream: `eyeonus/Trade-Dangerous:release/v1`
- working repo: `Tromador/Trade-Dangerous:release/v1`

This is deliberate.

The fork exists to isolate the refactor from the live upstream branch. Do not create a second refactor branch inside the fork unless a later problem proves it necessary.

## 2. Product constraints

These are fixed for the whole program:

- CLI and GUI are equally important.
- `pip install` remains a first-class distribution method.
- Windows packaged `.exe` / installer support remains first-class.
- `python tradegui.py` must remain viable anywhere the stack supports it.
- Core engine stays OS-agnostic and frontend-agnostic.
- SQLite remains the primary performance truth for end users.
- MariaDB support must continue to work, but must not distort the design for the SQLite majority.
- No big-bang rewrite.
- Do not remove `TradeDB` until replacement seams are proven.

## 3. Locked design decisions

These are adopted unless later evidence forces review:

- Use the Option 1 ORM migration strategy.
- Shrink `TradeDB` into a compatibility shim instead of deleting it up front.
- Ship one narrow first schema batch for additive read-performance indexes.
- Remove `Added` completely.
- Remove `RareItem` completely.
- Represent rarity through `Item.rare_station_id IS NOT NULL`.
- Do not persist `is_rare`; expose it only as convenience logic in Python if useful.
- Migrate commands one command at a time.
- Attack `TradeCalc` setup cost before route maths.
- Give the GUI session-scope reuse where appropriate; keep the CLI short-lived and stateless.

## 4. Core working documents

The fork should contain and maintain these files:

- `docs/final_implementation_plan.md`
- `docs/performance_optimization_plan.md`
- `docs/performance_tactical_backlog.md`
- `docs/schema_batch_a_checklist.md`
- `docs/schema_batch_a_spec.md`
- `docs/schema_impact_matrix.md`
- `docs/PERF_NOTES.md`
- `docs/AUDIT.md`
- `docs/RESOLVER_CONTRACT.md`
- `docs/SCHEMA_BATCH_LOG.md`
- `docs/SESSION_HANDOFF_TEMPLATE.md`

Treat the fork as the canonical working set for the refactor. Future ChatGPT sessions should read these files first before planning any change.

## 5. Checkpoint map

Each checkpoint must be releasable in its own right, either as:

- a direct user-visible improvement,
- a safe schema change,
- or a necessary enabling change that leaves the codebase cleaner and more measurable than before.

### Checkpoint A — Instrumentation and production baselines
Goal: make the expensive phases visible and measurable.

Primary outputs:
- timing helper
- phase timing output
- benchmark command set
- first live baseline
- query-plan snapshot

### Checkpoint B — Schema Batch A: narrow additive index release
Goal: unblock resolver-first work with the smallest fair schema release.

Guaranteed payload:
- `idx_system_by_name`

Optional only if proven first:
- `idx_station_by_system_name`

Nothing else belongs in Batch A.

### Checkpoint C — Legacy audit and prune map
Goal: classify suspiciously ancient code as core-live, compatibility-live, dead, or unknown.

Primary output:
- `docs/AUDIT.md`

### Checkpoint D — Remove `Added`
Goal: remove the obsolete table, schema references, import/export handling, and runtime logic.

### Checkpoint E — Collapse `RareItem` into `Item`
Goal: remove the standalone rares table and model rarity through `Item.rare_station_id`.

### Checkpoint F — Resolver contract and parity tests
Goal: define and lock the lookup semantics before broad migration.

### Checkpoint G — Resolver-first execution flow
Goal: resolve command inputs before any heavy `TradeDB` path.

### Checkpoint H — Migrate `local`
Goal: first clear user-visible win.

### Checkpoint I — Migrate `market`, `buy`, `sell`
Goal: move the obvious preload-bound commands off full `TradeDB`.

### Checkpoint J — Split `TradeDB` by capability
Goal: turn monolithic preload into selective compatibility loading.

### Checkpoint K — Reduce `TradeCalc` setup cost
Goal: make `run` materially faster by narrowing preload and reshape work.

### Checkpoint L — Migrate `olddata`, `nav`, `rares`
Goal: finish the main command migration set.

### Checkpoint M — GUI session reuse and cache discipline
Goal: recover load-once benefits only where they actually belong: GUI session scope.

### Checkpoint N — Legacy prune wave 2 and closeout
Goal: remove quarantined dead code, align docs, and prepare the fork for merge or selective upstream PRs.

## 6. Session sizing rules

Each checkpoint must be broken into sub-goals that fit into small packets.

### Small task rule
A small task should usually fit within 1–4 sessions.

### Mandatory stop points
If a task begins to sprawl, split it. If a task exposes a wrong assumption, stop and reassess instead of forcing it through.

### Required end-state for any paused task
Every paused task must end with a succession packet using `docs/SESSION_HANDOFF_TEMPLATE.md`.

## 7. Release discipline per checkpoint

Every checkpoint must have:

1. explicit scope
2. explicit acceptance criteria
3. explicit rollback point
4. updated docs if behavior or process changed
5. benchmark or verification evidence where relevant

No checkpoint should leave the fork in a conceptually muddled state.

## 8. Recommended immediate execution order

If only one stream is active at a time, use this order:

1. Checkpoint A — instrumentation and baseline capture
2. Checkpoint B — Batch A schema/index release
3. Checkpoint C — legacy audit and prune map
4. Checkpoint D — remove `Added`
5. Checkpoint E — collapse `RareItem` into `Item`
6. Checkpoint F — resolver contract and parity tests
7. Checkpoint G — resolver-first execution flow
8. Checkpoint H — migrate `local`
9. Checkpoint I — migrate `market`, `buy`, `sell`
10. Checkpoint J — split `TradeDB` by capability
11. Checkpoint K — reduce `TradeCalc` setup cost
12. Checkpoint L — migrate `olddata`, `nav`, `rares`
13. Checkpoint M — GUI session reuse
14. Checkpoint N — closeout and prune wave 2

## 9. What future worker sessions should do first

Any future ChatGPT worker session should begin by establishing:

1. Which checkpoint and subtask is in scope.
2. Which files are already modified on the fork.
3. Whether the task is design-only, code, tests, docs, or release packaging.
4. What the exact acceptance criteria are for this subtask.
5. What the rollback point is.

Then the session should read the relevant planning docs from `docs/` before proposing any code work.

## 10. Program-level pause conditions

Stop and reassess if any of these happen:

1. Resolver parity starts demanding too much legacy recreation for too little value.
2. SQLite query plans do not improve after the Batch A index work.
3. `run` remains slow even after `TradeCalc` narrowing, implying route maths is now the real hotspot.
4. CLI and GUI drift into different backend semantics.
5. Any helper written for one checkpoint starts expanding into a general framework with unclear boundaries.
6. Schema work starts fragmenting into many tiny downstream-facing changes instead of coherent batches.

## 11. First five concrete moves

The recommended immediate sequence is:

1. Instrument the current execution path and capture a live baseline.
2. Land Batch A with `idx_system_by_name` unless the composite station index proves itself before cut.
3. Build the legacy audit and prune map.
4. Remove `Added`.
5. Collapse `RareItem` into `Item` and make `trade rares` work on the new model.

That produces measurement, one narrow schema release, one obsolete-table removal, one deprecated-table collapse, and leaves the resolver work starting from a cleaner foundation.
