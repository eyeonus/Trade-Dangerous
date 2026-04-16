# Trade Dangerous Schema Impact Matrix

Date: 2026-03-23
Status: Planning note
Audience: Maintainers and downstream consumers of the TD database schema
Companion documents:
- `docs/performance_optimization_plan.md`
- `docs/performance_tactical_backlog.md`

## Purpose

This document separates schema-affecting work from the wider performance roadmap so schema changes can be planned, communicated, and batched fairly for downstream consumers.

The key design principle is simple:

- do schema work first
- do it once per coherent batch
- keep the rest of the optimization work as schema-neutral as possible

## Executive Summary

Based on the current performance plan and the current codebase, there is only one schema change that is both:

- clearly justified already
- directly tied to the near-term optimization path
- suitable for a first schema batch

That change is:

- add `idx_system_by_name` to the SQLite schema and provide an in-place upgrade path for existing databases

Everything else falls into one of three buckets:

1. additive candidates that should only be included if benchmark evidence proves they matter before the schema batch is cut
2. existing ORM-versus-template drift that is real, but not currently required by the optimization roadmap
3. deferred future search redesign work that would be a larger schema event and should not be mixed into the first batch

## Important Current Facts From The Repo

### SQLite schema creation is template-driven

For SQLite, resets and rebuilds use the canonical SQL file, not ORM metadata:

- [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
- [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)

That means downstream SQLite consumers are affected primarily by changes to the canonical SQL template and any explicit in-place upgrade path.

### MariaDB reset is metadata-driven

For MariaDB/MySQL, reset uses ORM metadata:

- [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
- [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)

That matters because ORM metadata already declares some indexes and tables that are not present in the shipped SQLite SQL template.

### There is already some schema drift in the repo

Current examples visible from the code:

- `System` ORM declares `idx_system_by_name`, SQLite template does not
- `Category` ORM declares `idx_category_by_name`, SQLite template does not
- `Item` ORM declares `idx_item_by_category`, SQLite template does not
- `Item` ORM index name is `idx_item_by_fdevid`, while SQLite template uses `idx_item_by_fdev_id`
- ORM also defines `ExportControl` and `StationItem_staging`, which are not present in the shipped SQLite template

That drift is important to know about, but it does not mean all of it should be forced into the first performance-related schema batch.

## Classification Matrix

| Change | Kind | Current justification | Required for near-term speed work | Downstream impact | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Add `idx_system_by_name` | Additive index | Strong | Yes | Low | Include in first schema batch |
| In-place upgrade path for missing `idx_system_by_name` | Upgrade mechanism | Strong | Yes | Low | Include in first schema batch |
| Add `Station(system_id, name)` composite index | Additive index | Plausible but unproven | No | Low | Measure first, include only if proven before batch cut |
| Adjust `StationItem` indexes for resolver or `run` narrowing | Additive index | Hypothesis only | No | Low/Medium | Measure first, probably defer from first batch |
| Add normalized search columns | New columns | Future search design only | No | Medium | Defer to a later dedicated search schema batch |
| Add dedicated search helper table | New table | Future search design only | No | Medium/High | Defer to a later dedicated search schema batch |
| Add `idx_category_by_name` to SQLite | Additive index | Existing ORM/template drift, not tied to main speed path | No | Low | Optional cleanup, not part of first batch unless you explicitly want schema alignment work |
| Add `idx_item_by_category` to SQLite | Additive index | Existing ORM/template drift, not tied to main speed path | No | Low | Optional cleanup, not part of first batch unless item lookup work proves it useful |
| Rename `idx_item_by_fdev_id` to match ORM naming | Index rename only | Cosmetic alignment | No | Low/Medium | Do not bother in first batch |
| Add `ExportControl` to SQLite | New table | Existing ORM/template drift, server-side support concern | No | Medium | Keep out of first batch |
| Add `StationItem_staging` to SQLite | New table | Existing ORM/template drift, server-side support concern | No | Medium | Keep out of first batch |

## Recommended Batch Strategy

## Batch A: Read-Performance Index Release

This is the schema batch I would recommend doing first.

### Include

1. `idx_system_by_name` in the canonical SQLite schema
2. an idempotent in-place upgrade path for existing SQLite databases to add the index
3. verification that exact `System.name = ?` lookups use the index after upgrade

### Conditionally include only if measured before the batch is cut

1. `Station(system_id, name)` composite index

Only include that if:

- query plans and live-DB timings show it materially helps resolver lookups for `system/station`
- you decide the benefit is worth making downstream consumers ingest one more additive index in the same batch

### Explicitly exclude from Batch A

1. normalized search columns
2. search helper tables
3. staging/export tables on SQLite
4. cosmetic index-name alignment work
5. speculative `StationItem` index tuning unless the evidence is already overwhelming before the batch is cut

## Why Batch A should stay narrow

Because your goal is not merely technical neatness. Your goal is fair change management for people downstream.

A narrow additive index release has several advantages:

- no table shape changes
- no column changes
- no semantic changes to existing reads and writes
- low breakage risk for tools that inspect table layouts
- most performance work after that can proceed without further schema churn

## Existing Repo Drift: What To Do With It

The codebase already contains ORM/template mismatches, but they should not all be dragged into the first batch just because they exist.

## Drift worth fixing now

Only this item clearly meets that standard:

- `idx_system_by_name`

Why:

- it directly affects the planned resolver-first execution path
- it already exists conceptually in ORM metadata
- it is missing from the authoritative SQLite template
- it is additive and low-risk

## Drift worth acknowledging but not piggybacking into Batch A

These should be treated as separate decisions:

- `idx_category_by_name`
- `idx_item_by_category`
- `idx_item_by_fdevid` naming mismatch versus `idx_item_by_fdev_id`
- `ExportControl`
- `StationItem_staging`

Reason:

- they are not required to start the optimization roadmap
- adding them now would blur a clean performance-driven schema release into a general schema reconciliation exercise
- downstream consumers would have to react to more change than the immediate performance goal actually needs

## Proposed Policy For The Rest Of The Optimization Roadmap

After Batch A lands, use this rule:

- no further schema changes unless a packet cannot reasonably proceed without them

That means the following milestones should be treated as schema-neutral by default:

- resolver implementation
- resolver-first execution flow
- `local` migration
- `market` / `buy` / `sell` migration
- `TradeDB` load splitting
- `TradeCalc` narrowing and constructor optimization
- GUI session reuse

If one of those later packets turns out to need a schema change after all, it should trigger a fresh schema review rather than being smuggled in piecemeal.

## Future Batch B: Search Schema, Only If Needed

If later work proves that resolver quality and performance genuinely require a structural search layer, that should be handled as a separate schema event.

Possible Batch B contents:

- normalized search columns
- dedicated search helper table
- supporting indexes for prefix or tokenized search

That would be a larger schema conversation and should be communicated as such. It should not be mixed with the current index-only performance batch.

## Concrete Recommendation

If you want the fairest possible story for downstream consumers, I would recommend saying this:

1. We are making one schema batch first.
2. That batch is additive and read-performance-oriented.
3. The only guaranteed change in that batch is `idx_system_by_name`.
4. One optional extra index, `Station(system_id, name)`, may join that batch only if measurement proves it worthwhile before the batch is cut.
5. After that batch, the performance work proceeds primarily in code, not schema.

That gives downstream consumers a stable expectation and avoids death by a thousand tiny "just one more schema tweak" releases.

## Suggested Communication Note For Downstream Developers

Suggested plain-language summary:

> We intend to do a single early schema batch for read-performance improvements, then freeze schema again while the main performance refactor proceeds in code. The first batch is planned to be additive only, with `idx_system_by_name` as the one definite change. Any additional index included in that batch will be decided before release and communicated together, not dripped out piecemeal.

## Decision Table

| Question | Recommended answer |
| --- | --- |
| Should schema work happen before the rest of the optimization roadmap? | Yes |
| Should schema work be batched rather than dripped out? | Yes |
| Is `idx_system_by_name` the one definite first-batch change? | Yes |
| Should `Station(system_id, name)` be treated as definite already? | No |
| Should search columns or helper tables be folded into the first batch? | No |
| Should existing ORM/template drift all be reconciled immediately? | No |

## File References

Primary code references used for this note:

- [TradeDangerous.sql](/D:/Git/Trade-Dangerous/tradedangerous/templates/TradeDangerous.sql)
- [orm_models.py](/D:/Git/Trade-Dangerous/tradedangerous/db/orm_models.py)
- [lifecycle.py](/D:/Git/Trade-Dangerous/tradedangerous/db/lifecycle.py)
- [tradedb.py](/D:/Git/Trade-Dangerous/tradedangerous/tradedb.py)
