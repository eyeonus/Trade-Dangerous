# CHECKPOINT_E_LOCKED_DECISIONS.md

## Purpose

This document records the authoritative product and modelling decisions locked for Checkpoint E.

Checkpoint E is not a migration or semantic-preservation exercise for the historical `RareItem` model. It is a simplification checkpoint.

---

## Authoritative model

- `RareItem` is removed entirely.
- The only required persisted rarity marker is `Item.rare_station_id`.
- `Item.rare_station_id IS NOT NULL` means the item is rare.
- `is_rare` is computed convenience only and is not stored schema.
- No default attempt is made to preserve the old rich `RareItem` model.
- Any extra carried-forward rare metadata must be justified by a current command requirement, not historical completeness.
- Checkpoint E is a rebuild/simplification step, not a semantic preservation exercise for old `RareItem`.

---

## Rollout policy

- Checkpoint E is rebuild/reset only.
- No migration path from pre-E databases is planned.
- No backfill from old `RareItem` is planned.
- No old-schema detection, guardrails, or runtime assistance is planned.
- Supported operator/user action on upgrade is a normal fresh rebuild / clean import.

---

## Canonical vs live data

### Canonical truth

Canonical rare identity is item-side:

- `Item.rare_station_id` answers whether an item is a rare.
- `Item.rare_station_id` answers which station is its canonical source.

### Live market overlay

`StationItem` is live market overlay only:

- if live market data exists for a rare, it belongs in `StationItem` like any other commodity
- if no `StationItem` row exists for a canonical rare, that does **not** mean it is not a rare
- if a `StationItem` row exists with zero/zero values, that is live market state, not canonical identity

So:

- `Item` answers **what the thing is**
- `StationItem` answers **what has been observed recently in market data**

This distinction is required because canonical source rares may be absent from current market snapshots for valid reasons.

---

## Command-surface decision

- `trade rares` is retired.
- Any remaining useful rare lookup behaviour moves into `trade buy` via rare filtering.
- Rares are to be treated as ordinary commodities with an extra canonical marker, not as a dedicated subsystem.

This is an intentional demotion of rares from a historically privileged model to an ordinary commodity model plus filtering.

---

## Festive Gifts exception

- `Festive Gifts` is excluded from canonical rare handling.
- `Festive Gifts` is not treated as a normal rare for Trade Dangerous purposes.
- It must not participate in normal rare classification or normal rare filters.

Reason:

- it is a Frontier event-specific seasonal commodity with bespoke behaviour
- although the market that sells it may treat it as a rare, its use is special-case and tied to the accompanying Frontier event

This exception should be implemented narrowly and should not distort normal rare modelling.

---

## Implementation implications

Checkpoint E implementation should therefore aim to:

1. add `Item.rare_station_id`
2. add computed `is_rare` convenience only if useful
3. remove `RareItem` from ORM, schema, import/export plumbing, packaged templates, and docs
4. remove rare-specific importer/cache special casing that only exists because `RareItem` is separate
5. retire `trade rares`
6. cover any still-useful rare lookup behaviour through `trade buy` rare filtering
7. encode the `Festive Gifts` exclusion explicitly

---

## Out of scope

The following are explicitly out of scope for Checkpoint E unless reintroduced by an explicit later decision:

- migration/backfill from old `RareItem`
- preserving historical legality/suppression/allocation richness for its own sake
- preserving a dedicated rare-command surface just because it existed historically
- using `StationItem` absence as evidence against canonical rarity

---

## Companion repo note

Where server/export validation is relevant, `Tromador/TradeDangerous-listener` remains part of the real validation surface for Checkpoint E.
