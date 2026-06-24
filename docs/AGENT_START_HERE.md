# AGENT_START_HERE.md
## Trade Dangerous refactor programme bootstrap

This document is for future agent sessions working on the Trade Dangerous modernization/refactor effort.

Do not treat this as optional background. Read this first, then read the referenced docs in `docs/`.

---

## 1. Repository and working line

Primary upstream:
- `eyeonus/Trade-Dangerous`

Working repo for this programme:
- `Tromador/Trade-Dangerous`

Working line:
- `release/v1` on the **fork**
- there is **no separate refactor branch inside the fork**
- the fork itself is the isolation boundary

Reason:
- the point was to avoid polluting upstream `release/v1`
- using the fork directly is deliberate
- do not invent a second branch unless a later problem proves it necessary

---

## 2. Product constraints

These are fixed constraints, not suggestions.

- CLI and GUI are equally important.
- The app must remain cross-platform.
- `pip install` remains first-class.
- Windows packaged `.exe` / installer remains first-class.
- `python tradegui.py` should remain viable anywhere the underlying stack supports it.
- The core engine must stay OS-agnostic and frontend-agnostic.
- Do not let Windows packaging assumptions leak into core architecture.
- Do not let NiceGUI/web-ish assumptions leak into core architecture.
- GUI and CLI must continue to share the same engine and business logic wherever possible.

---

## 3. Architecture direction already agreed

The governing strategy is **Option 1 ORM migration**.

Meaning:
- shrink `TradeDB` into a compatibility shim
- move core lookups and common queries to ORM-backed resolution
- migrate commands one command at a time
- preserve CLI/GUI parity through shared resolver/query logic
- do not big-bang rewrite the app
- do not delete `TradeDB` up front

This project is not “make a new engine”.
It is “systematically remove preload-heavy legacy obligations while keeping the product working”.

> **Status (2026-06): Checkpoints K, L, M, and N complete.** `trade run` was the
> preload-heaviest obligation. The K4 review concluded the preload-first
> `TradeDB` / `TradeCalc` model should be replaced rather than narrowed, and the
> clean-room planner rewrite (Slices 1–14, `docs/Planner/`) did so. `trade run`
> is now planner-only, and `tradecalc.py` / `tradedb.py` are retired to
> `archive/`. The "do not delete `TradeDB` up front" rule (§16) was honoured —
> the deletion came at the end, once the replacement was proven. L migrated the
> remaining command surfaces (`olddata`, `nav`, `trade direct`); M restored the
> GUI on the TradeORM-only backend and reconciled it with the post-L CLI surface.
> N pruned the post-refactor leftovers and aligned docs/comments with reality.
> Next: O (rebuild the test suite), then P (document the project). See
> `REFACTOR_PROGRESS.md` §1 for live status.

---

## 4. Schema decisions already locked

These are already adopted unless later evidence forces a review.

### 4.1 Added
`Added` is obsolete and must be removed entirely.

Required result:
- no `Added` table
- no `System.added_id`
- no import/export/template/runtime support for it

### 4.2 RareItem
`RareItem` must be removed as a separate table.

Rarity is represented by:
- `Item.rare_station_id IS NOT NULL`

Do **not** persist `is_rare`.

If useful, expose `is_rare` as computed Python/ORM convenience only:
- `item.is_rare := item.rare_station_id is not None`

Important:
- station linkage is the real rarity predicate
- avoid dual-source-of-truth schema design

---

## 5. Current planning docs

Read this document:

1. `docs/final_implementation_plan.md`

Working-note documents:
- `docs/PERF_NOTES.md`
- `docs/AUDIT.md`
- `docs/RESOLVER_CONTRACT.md`

If any of the substantive planning docs are missing from the fork, ask for them or ask the user to upload/push them. Do not pretend they exist if they do not.

---

## 6. What matters most

### 6.1 Primary bottleneck
The main cost is repeated setup and reshaping, not route maths first.

High-value targets include:
- full `TradeDB` construction
- preload-heavy lookup behavior
- station/item reshaping during `TradeCalc.__init__()`
- command paths that load far more data than they need

### 6.2 Resolver-first migration
Lookup and resolution are the foundation.

Do not broadly migrate commands until resolver semantics are explicitly defined and tested.

### 6.3 Measure before heroics
Instrumentation and baseline capture come before ambitious refactor claims.

SQLite is the main performance truth.
MariaDB parity matters, but SQLite evidence drives the decisions.

---

## 7. Resolver contract direction

The resolver is the first-class lookup subsystem for both CLI and GUI.

It must eventually cover:
- `lookup_system`
- `lookup_station`
- `lookup_place`
- later `lookup_item`

The contract must define:
- accepted syntax
- normalization behavior
- ambiguity behavior
- duplicate system `@N` handling
- not-found behavior
- fast vs slow tiers

Current agreed ladder direction:
1. syntax parse and disambiguation handling
2. exact raw
3. exact normalized
4. prefix raw
5. prefix normalized
6. broader fallback only if still required

Do not default to global `%term%` scans.

The old `TradeDB.lookupPlace()` behavior is not “just a lookup”; it is a parser + ranking engine + ambiguity explainer. Treat it accordingly.

---

## 8. Query composition direction

Move away from Python-side ID shuffling and user-space joins.

Prefer:
- SQLAlchemy filters
- subqueries
- CTEs
- DB-native narrowing

Only use temp tables later if connection/session lifetime is already disciplined enough to support them safely.

---

## 9. GUI-specific direction

The GUI is long-running.
The CLI is short-lived.

Do not solve that by making the core engine GUI-shaped.

Instead:
- keep long-lived lightweight resolver/cache objects where useful in GUI scope
- keep DB sessions request/task scoped
- do not keep one giant ORM session alive forever
- keep CLI and GUI on the same business logic

The GUI is NiceGUI-based, but future possible web/service thoughts are not the primary driver.
The real driver is shared, frontend-neutral core behavior.

---

## 10. Legacy audit direction

Ancient-looking code is not automatically dead, but it is suspect.

Audit candidates include:
- discontinued pickle snapshot relics
- `.prices` era leftovers
- OCR/correction-era code if it still exists
- deprecated commands/workflows
- old import/export special cases
- stale comments that describe no-longer-true runtime behavior

Use `docs/AUDIT.md` to classify:
- Core live
- Compatibility live
- Dead
- Unknown — needs runtime tracing

Do not delete based on vibes.

---

## 11. Checkpoint map

These are the agreed major checkpoints.

### A — Instrumentation and baselines
Goal:
- make expensive phases visible and measurable

### B — Schema Batch A
Goal:
- land the narrow first additive index batch

Guaranteed:
- `idx_system_by_name`

Optional only if proven:
- `idx_station_by_system_name`

Nothing else belongs in Batch A unless new evidence forces it.

### C — Legacy audit and prune map
Goal:
- classify suspicious code paths before deletion

### D — Remove `Added`
Goal:
- remove obsolete table and all live references

### E — Collapse `RareItem` into `Item`
Goal:
- remove standalone rares table
- rework `trade rares`

### F — Resolver contract + parity tests
Goal:
- write and lock the resolver behavior

### G — Resolver-first execution flow
Goal:
- resolve command inputs before heavy `TradeDB` paths

### H — Migrate `local`
Goal:
- first clear user-visible win

### I — Migrate `market`, `buy`, `sell`
Goal:
- move obvious preload-bound commands off full `TradeDB`

### J — Split `TradeDB` by capability
Goal:
- turn monolithic preload into selective compatibility loading

### K — Reduce `TradeCalc` setup cost
Goal:
- narrow preload/reshape work before touching route maths

**Complete — by replacement, not narrowing.** The clean-room planner rewrite
(`docs/Planner/`) eliminated the preload-first model for `trade run`; see
`docs/REFACTOR_PROGRESS.md` Checkpoint K and the Slice 14 completion report.

### L — Migrate remaining legacy command surfaces
Goal:
- finish the main command migration set
- migrate `olddata` and `nav`
- complete the post-E rare lookup cutover
- refactor `trade trade` into `trade direct` as a direct market comparison command

### M — GUI session reuse and cache discipline
Goal:
- recover “load once, answer many questions” only where it actually belongs

### N — Legacy prune wave 2 and closeout (complete)
Goal:
- remove proven-dead code
- align docs/comments with reality
- (the original "prepare for upstream merge / selective PRs" goal was retired —
  the K ground-up rewrite changed the upstream picture; documenting the project
  succeeds it as Checkpoint P)

### O — Rebuild the test suite against the post-rewrite codebase
Goal:
- restore a green, meaningful suite after the planner rewrite retired the modules
  the old tests targeted (`tradedb.py`, `tradecalc.py`, the preload model)
- rebuild tests against the current architecture rather than patch the obsolete ones

### P — Document the project
Goal:
- document the project; detailed scope to be defined with Tromador

---

## 12. Immediate execution order

If only one stream is active, use this order:

1. A — instrumentation and live baseline
2. B — Batch A index work
3. C — audit/prune map
4. D — remove `Added`
5. E — collapse `RareItem`
6. F — resolver contract/tests
7. G — resolver-first execution flow
8. H — `local`
9. I — `market`, `buy`, `sell`
10. J — `TradeDB` capability splitting
11. K — `TradeCalc` narrowing
12. L — remaining legacy command surfaces
13. M — GUI session reuse
14. N — closeout/prune wave 2
15. O — rebuild the test suite against the post-rewrite codebase
16. P — document the project

---

## 13. Session operating rules

Every worker session must establish:

1. which checkpoint and subtask is in scope
2. which files are already modified
3. whether the task is design, code, tests, docs, or release packaging
4. what the exact acceptance criteria are
5. what the rollback point is

Then read the relevant docs before proposing any code.

If required source/code context is missing, ask for it.
Do not infer unknown implementation details.
Do not backfill missing code structure from guesswork.

---

## 14. Session sizing

Small tasks should usually fit into 1–4 sessions.

If a task starts to sprawl:
- stop
- split it
- update docs
- emit a succession packet

Use:
- `docs/SESSION_HANDOFF_TEMPLATE.md`

Do not let one session silently turn into a mega-refactor.

---

## 15. Program-level stop conditions

Stop and reassess if any of these happen:

1. resolver parity starts demanding too much legacy recreation for too little gain
2. SQLite query plans do not improve after Batch A
3. `run` remains slow even after `TradeCalc` narrowing, implying route maths is now the real hotspot
4. CLI and GUI drift into different backend semantics
5. a small helper starts expanding into a vague general framework
6. schema work fragments into many tiny user-facing changes instead of coherent batches

---

## 16. What not to do

- Do not start by optimizing route maths.
- Do not start by rewriting the GUI.
- Do not start by inventing a service architecture.
- Do not delete `TradeDB` up front.
- Do not casually change lookup semantics without updating the resolver contract and tests.
- Do not drip random schema changes into unrelated checkpoints.
- Do not treat the GitHub fork as “just a scratch copy”; it is the working line for this programme.

---

## 17. First five concrete tasks if no other instruction is given

1. Add instrumentation and capture a real baseline.
2. Land Batch A with `idx_system_by_name` unless evidence proves the composite station index first.
3. Build the legacy audit/prune map.
4. Remove `Added`.
5. Collapse `RareItem` into `Item` and make `trade rares` work on the new model.

---

## 18. Truthfulness rule

If you do not know, say so.
If a required file/module is missing, ask for it.
If a conclusion is only a hypothesis, label it as a hypothesis.
Do not invent code structure or behavior you have not verified.
