# REFACTOR_PROGRESS_E_SUPERSEDING_NOTE.md

## Purpose

This note supersedes the stale Checkpoint E portions of `docs/REFACTOR_PROGRESS.md` until that tracker file is rewritten in place.

Use this file together with `docs/CHECKPOINT_E_LOCKED_DECISIONS.md` when starting or continuing Checkpoint E work.

---

## Effective snapshot override

Treat the current project state as:

- Active checkpoint: `E — Collapse RareItem into Item`
- Status: `in progress`
- Started: `2026-04-21`
- No active blocker

---

## Effective Checkpoint E acceptance criteria

The following replace the stale Checkpoint E acceptance criteria in `docs/REFACTOR_PROGRESS.md`:

- fresh DB has no `RareItem`
- v13 expects a fresh rebuilt database; no migration/backfill or old-schema assistance is provided
- rarity is modelled by `Item.rare_station_id`, with `is_rare` convenience logic only
- canonical rare identity is item-side; `StationItem` is live market overlay only
- `trade rares` is retired and any still-useful rare lookup behaviour is covered by `trade buy` filtering
- importer/cache/export logic no longer treats rares as a separate table
- `Festive Gifts` is excluded from canonical rare handling

---

## Effective Checkpoint E task list

The following replace the stale Checkpoint E tasks in `docs/REFACTOR_PROGRESS.md`:

- E1. Add `Item.rare_station_id` and only genuinely needed parity fields
- E2. Add computed `is_rare` convenience logic if useful
- E3. Remove dedicated rare command surface and cover any still-useful behaviour through `trade buy` filtering
- E4. Remove importer/cache special cases and rare-only export/template plumbing
- E5. Remove `RareItem` schema/runtime/docs/tests
- E6. Encode the `Festive Gifts` exclusion narrowly

---

## Effective locked decisions for Checkpoint E

These override any stale implication in the older tracker text:

- Checkpoint E is rebuild/reset only.
- No migration path from pre-E databases is planned.
- No backfill from old `RareItem` is planned.
- No old-schema detection, guardrails, or runtime assistance is planned.
- `trade rares` is retired.
- `Festive Gifts` is excluded from canonical rare handling.

See also:

- `docs/CHECKPOINT_E_LOCKED_DECISIONS.md`
