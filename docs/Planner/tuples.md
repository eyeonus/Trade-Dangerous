# Y/N/? State Filter Semantics

We agreed that `Y/N/?` filters should be treated as an accepted-state set, not as three unrelated absolute modes.

## Meaning

```text
Y    = accept known yes only
N    = accept known no only
?    = accept unknown only
Y?   = accept known yes or unknown
N?   = accept known no or unknown
YN   = accept known yes or known no, exclude unknown
YN?  = accept all states, equivalent to no filter
```

## Rationale

`?` is useful both as a standalone unknown-state filter and as a modifier that prevents unknown data from being excluded.

Example:

```text
--black-market Y?
```

means:

```text
stations known to have a black market, plus stations where black-market state is unknown
```

## Implementation Note

The planner helper already matches this model:

```python
(station_state or "?").upper() in requested_states.upper()
```

Command/parser normalisation should preserve this accepted-set behaviour consistently for:

```text
--black-market
--fleet-carrier
--settlement
--planetary
```

`YN?` may be normalised to `None` because it imposes no filter.

# Pad Size Filter Semantics

Revised model. Implemented as part of Slice 3 (see `third_slice_implementation_plan.md`); until that slice lands the planner still does exact membership on `max_pad_size`. It is a deliberate `--pad-size` contract change.

`--pad-size` is a ship-fit threshold: it takes the one pad size the player's ship needs, and keeps stations whose largest pad is at least that size.

## Meaning

```text
L    large-max stations only
M    medium- or large-max stations
S    small-, medium- or large-max — effectively no filter
```

`--pad-size M` means "my ship needs a medium pad", so medium-max and large-max stations both qualify — `M` includes `L`. `--pad-size S` keeps every station with a known pad size, since a small-pad requirement is met everywhere.

## Unknown pad size

`?` is not a valid input. `--pad-size ?`, `--pad-size M?` and any multi-letter value are rejected with a validation error.

A station whose own pad size is unknown is treated as ineligible and silently dropped — whether or not `--pad-size` was given. This is a deliberate guardrail: an unknown pad cannot be guaranteed to fit the ship, so a station lacking pad-size data is treated as a data fault, not a candidate. Pad size should always be known upstream.

## What is not supported

An earlier model also let `--pad-size` exclude large starports, to find trades larger ships cannot reach. That is deliberately dropped: one control serving both "what can my ship use" and "which station classes do I want" confused even its designers. The threshold model does one job clearly. If the station-class use case is wanted later, it belongs in a separate control, not in `--pad-size`.

## Implementation Note

Folded into Slice 3. The change replaces the current exact-membership behaviour: `--pad-size` is carried as a single required size; validation rejects `?` and any input that is not one of `S`/`M`/`L`; the station query keeps `max_pad_size` values at or above the required size; and unknown-pad stations are excluded by an always-on eligibility predicate, alongside the existing "no market" exclusion. The CLI help text and its `SML?` example need updating to match — a separate follow-up.
