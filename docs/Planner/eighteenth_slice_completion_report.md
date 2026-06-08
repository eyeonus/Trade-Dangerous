# Slice 18 — Direct Point-to-Point Trade (`--direct`) — Completion Report

## What was delivered

`--direct` is live. It plans the single most profitable trade between a fixed
`--from` and `--to`, with no jump-path or distance checks — the relocation run
(Federation to Empire, or out to Colonia) where the commander flies the route
themselves and just doesn't want to deadhead. It is not a new route shape: it is
the existing fixed-pair single hop with reachability switched off.

Scope, as built:

- Requires both `--from` and `--to`. An open end is rejected.
- Single hop. `--direct` and `--hops` are mutually exclusive at the parser.
- No reachability: no jump-path check, no distance check. `--ly-per` and
  `--jumps-per` are not required and are ignored if supplied.
- Endpoints may be a station or a system; a system expands to its eligible
  stations and the best pair wins, exactly as the normal fixed-pair hop does.
- Incompatible with `--loop` (already enforced), `--towards`, and empty-jump
  positioning (`--start-jumps` / `--end-jumps`).
- `--ls-penalty` still applies and is untouched.

## The contract, pinned by an authorised legacy trace

The spec is vague on `--direct` and the help/wiki no clearer, so with Tromador's
explicit one-off authorisation the archived legacy modules were read solely to
settle what the switch did. Findings (quarantine restored afterwards):

- `run_cmd.py:1022` forced `cmdenv.hops = 1` and set jump range + jumps-per to
  `10000` — effectively infinite, so every jump trivially passed rather than
  reachability being "skipped".
- `checkReachability` returned immediately under `--direct`; distance-to-target
  pruning was disabled.
- `tradecalc.py:1104` — with neither `--to` nor `--towards`, it iterated **every
  station in the preloaded galaxy** as a candidate destination, with a heartbeat
  spinner because it was slow.

Two decisions followed. The single hop is faithful to legacy and matches the
relocation use case. The open-destination "to anywhere" mode is **dropped**: it
was the full-galaxy in-Python scan this rewrite exists to remove, and with
infinite range there is no spatial bound to narrow it in SQL. It is recorded as a
deferred capability, not silently lost.

## The validation philosophy

A rule captured because it governs more than this option: **tolerate what
`--direct` overrides; reject only what it cannot service — and never guess which
of two contradictory flags the commander meant.**

- Moot under `--direct` (`--ly-per`, `--jumps-per`): tolerated and ignored, so a
  standard paste-in block of flags is not punished for an irrelevant entry.
- Contradictory route-shape intent (`--hops`, `--loop`, `--towards`, empty-jump
  positioning, and `--via`/`--shorten` when they land): rejected outright.

The test is whether honouring `--direct` makes the option merely *unused* (moot)
or demands something a single direct hop *cannot deliver* (contradictory).

## The build

| File | Change |
|------|--------|
| `run_request.py` | Resolve the canonical hop count to 1 when `--direct`, set at construction (the parser already excludes `--hops`, so the `--hops` default must not flow through). |
| `validation.py` | `--ly-per` no longer required or range-checked under `--direct`; `--direct` removed from the unsupported list; reject `--direct` without both endpoints, with `--towards`, or with empty-jump positioning. |
| `run_cmd.py` | The same un-gate and the same three rejections in the command-layer early validation, beside their siblings. |
| `route_onehop.py` | `_best_pair_plan`: under `--direct`, skip `plan_jump_path`, carry `jump_path = None`, go straight to the market query. The non-direct `else` branch is the original code, unchanged. |
| `render_text.py` | The hop's "Travel:" block shows `Direct: plot your own jump route` when there is no jump path. |
| `run_result.py` | `PlannedHop.jump_path` annotation is now `JumpPath \| None` — honest: it is `None` under `--direct`. |

Every change is gated behind `request.direct`, so the other lanes are
unaffected: the non-direct fixed-pair hop is byte-for-byte the original, the
renderer guard fires only on a `None` path, and the request/validation changes
are no-ops when `direct` is false.

## Two validation layers — the redundancy surfaced here

The first attempt un-gated only `validation.py` and the command still rejected
`--direct`. Cause: `trade run` validates in two places — the command-layer
`validateRunArgumentsFast` (the legacy-complete suite, raises `CommandLineError`)
and the planner's `validation.py` (the in-progress new-planner validator) — and
each keeps its own copy of the "unsupported" list. The command layer fires first.
Both were updated to land `--direct`.

This is leftover structure from the retired `--old` split: `run_cmd.py` had to
fully validate for the legacy planner, while `validation.py` is built out slice by
slice for the new one. With one path now, the two are redundant and have diverged
in spots (the `--insurance` rule differs between them). Consolidating onto
`validation.py` is the agreed next slice, recorded in `BASELINE.md`. It is not
folded in here — `--direct` is small and complete on its own, and a
codebase-wide validator merge is its own work.

## Deliberate variations from the spec

1. **Single hop only.** The spec's plural "hops" leans multi-hop; legacy forced
   `hops = 1` and the parser excludes `--hops`. We follow the bounded reading.
2. **Both endpoints required.** The spec is silent (its early-failure list omits
   `--direct`); an open end has no spatial bound, so we reject it.
3. **Open-destination mode dropped.** The legacy full-galaxy in-Python scan;
   deferred, not rebuilt.

Recorded in `SPEC_STATUS.md` (variation 7) and `BASELINE.md`.

## Verification

No automated harness (project decision). Spot-checks handed to Tromador and run
by him, all passing: the core happy path (no `--ly-per`, far-apart system
endpoints, the direct travel line shown); the rejection set (no `--to`;
`--direct --hops`; `--direct --start-jumps`; `--direct --towards`); the stray
`--ly-per` tolerated; and the fixed-pair one-hop regression unchanged. flake8
clean on every touched file.
