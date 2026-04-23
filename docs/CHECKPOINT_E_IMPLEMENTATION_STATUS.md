# CHECKPOINT_E_IMPLEMENTATION_STATUS.md

## Purpose

This document records the current landed state of Checkpoint E implementation work.

It is a status snapshot, not a design document. For locked product and modelling decisions, use:

- `docs/CHECKPOINT_E_LOCKED_DECISIONS.md`

For stale tracker override behaviour, use:

- `docs/REFACTOR_PROGRESS_E_SUPERSEDING_NOTE.md`

Until `docs/REFACTOR_PROGRESS.md` is rewritten in place, these documents are the authoritative Checkpoint E set.

---

## Last updated

- Date: `2026-04-23`
- Branch: `release/v1`
- Scope: `repo state after the first committed Checkpoint E implementation pass`

---

## Current status

- Checkpoint: `E — Collapse RareItem into Item`
- Status: `in progress`
- Active blocker: `none`
- Rollout policy: `rebuild/reset only`

---

## Landed so far

The following are present in the current repo state:

- `Item.rare_station_id` added to ORM as the canonical persisted rarity marker
- `Item.rare_station_id` modelled as a nullable FK to `Station.station_id`
- computed `Item.is_rare` convenience property added
- standalone `RareItem` ORM model removed
- standalone `RareItem` table removed from the canonical SQLite template
- `TradeDB` bootstrap and item loading updated away from `RareItem`
- Spansh import changed from separate `RareItem` population to `Item.rare_station_id` enrichment
- `Festive Gifts` excluded in that enrichment path
- `trade rares` retired from the live command registry
- `trade buy` now supports `--rare` filtering and rare browse mode
- package data no longer ships `templates/RareItem.csv`
- `cache.py` explicit `RareItem` header special-casing removed

---

## Known incomplete or not yet proven

The following remain true as of this snapshot:

- `tradedangerous/templates/RareItem.csv` still exists in the repo tree and has not yet been evacuated
- no runtime validation pass has yet been recorded for Checkpoint E
- no fresh rebuild validation pass has yet been recorded for Checkpoint E
- no migration, backfill, old-schema detection, or compatibility assistance will be added under the locked rollout policy
- repo-wide `RareItem` eradication is not yet claimed as proven solely from the landed code edits

---

## Effective task status

These reflect the current repo position, not the stale unchecked list in `docs/REFACTOR_PROGRESS.md`.

- [x] E1. Add `Item.rare_station_id` and only genuinely needed parity fields
  - Status note: `Landed in ORM and SQLite template. Canonical rarity is now item-side.`
- [x] E2. Add computed `is_rare` convenience logic if useful
  - Status note: `Landed as `Item.is_rare` convenience logic only.`
- [x] E3. Remove dedicated rare command surface and cover any still-useful behaviour through `trade buy` filtering
  - Status note: `trade rares retired from the live registry; trade buy now carries the surviving rare lookup path.`
- [-] E4. Remove importer/cache special cases and rare-only export/template plumbing
  - Status note: `Main importer/cache/plumbing changes are landed, but the physical `templates/RareItem.csv` file still remains in-tree.`
- [-] E5. Remove `RareItem` schema/runtime/docs/tests
  - Status note: `Schema and runtime changes are largely landed, but repo hygiene and validation are not yet closed out.`
- [x] E6. Encode the `Festive Gifts` exclusion narrowly
  - Status note: `Landed in the Spansh rare-enrichment path.`

---

## Likely next steps

1. Evacuate `tradedangerous/templates/RareItem.csv` from the repo tree.
2. Run the first real Checkpoint E rebuild/validation pass.
3. Fix only observed failures from that pass.
4. Rewrite `docs/REFACTOR_PROGRESS.md` in place once the tracker can be updated cleanly.
