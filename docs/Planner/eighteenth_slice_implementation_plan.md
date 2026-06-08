# Slice 18 — Direct point-to-point trade (`--direct`)

## Status

Planned. `--direct` currently parses into `request.direct` but is gated as
unsupported (`validation.py:41`), so it errors before any planning. This slice
un-gates it and gives it behaviour.

The scope was settled with Tromador after a one-off, explicitly authorised review
of the archived legacy modules to pin down what `--direct` actually used to do —
the spec is vague and the help/wiki no clearer. That trace is summarised under
"What the legacy did"; quarantine is back in force.

## What `--direct` is

The relocation run. A commander moving their operation a long way — Federation to
Empire, or out to Colonia — does not want to fly empty. `--direct` answers one
question: **given my hold and my credits, what is the single most profitable
trade between `--from` and `--to`?** The jump route is the commander's problem;
the planner does not check, or care, how far apart the two ends are.

So it is **not** a new route shape. It is the existing fixed-pair single hop with
the reachability check switched off.

## What the legacy did (authorised trace)

For the record, so the contract rests on evidence rather than memory. From the
archived `run_cmd.py` and `tradecalc.py`, under explicit one-off authorisation:

- **Forced a single hop.** `run_cmd.py:1022` — `if cmdenv.direct: cmdenv.hops = 1`
  and set jump range + jumps-per to `10000` (effectively infinite). It did not
  "skip" reachability so much as make the range so vast every check passed.
- **Skipped reachability validation.** `checkReachability` returned immediately
  under `--direct` (`run_cmd.py:1238`); the distance-to-destination pruning was
  also disabled (`run_cmd.py:1606`).
- **`--ly-per` optional, `--loop` rejected** (`run_cmd.py:1028`, `:1065`).
- **Destination did not have to be fixed.** `tradecalc.py:1104` — with no `--to`
  and no `--towards`, it iterated **every station in the preloaded galaxy**
  (`tdb.stationByID.values()`) as a candidate destination, with a heartbeat
  spinner because it was slow.

Two decisions follow from that trace:

1. **Single hop is correct** — legacy hard-set it, and `--direct`/`--hops` are
   mutually exclusive at our parser already (`run_cmd.py:115`). The spec's plural
   "hops" (line 448) was loose extraction.
2. **The open-destination "to anywhere" mode is dropped.** It was a full-galaxy
   in-Python scan — precisely the preload-first anti-pattern this rewrite exists
   to remove — and with infinite range there is no spatial bound to narrow it in
   SQL. We do not rebuild it here. It is recorded as a deferred capability, not
   silently lost; if anyone misses it, a regression report can reopen it.

## Semantics — the contract

- **Both ends anchored.** Requires `--from` **and** `--to`. `--direct` without
  `--to` was the dropped galaxy-scan; without `--from` it is a galaxy of origins.
  Either missing is a clean rejection.
- **Single hop.** `--direct` and `--hops` are mutually exclusive (parser). See
  "Validation philosophy" for why this is a rejection, not a silent override.
- **No reachability.** No jump-path check, no distance check. `--ly-per` and
  `--jumps-per` are not required, and are ignored if supplied.
- **Endpoints may be a station or a system.** A system expands to its eligible
  stations and the best pair wins — identical to the existing fixed-pair one hop.
- **`--ls-penalty` still applies.** Protected behaviour, untouched. It legitimately
  ranks between candidate destination stations (prefer one closer to the arrival
  star for equal profit). It is not a *jump* distance, so it survives `--direct`.
- **Incompatible with** `--loop` (parser, already enforced), `--towards`,
  `--start-jumps` / `--end-jumps` (empty-jump positioning is not a thing under
  `--direct`), and `--via` once `--via` is built.

## Validation philosophy — tolerate the moot, reject contradictory intent

Tromador's rule, captured because it governs more options than just this one.
Commanders keep a standard block of flags they paste in; an irrelevant flag in
that block should not fail the run. But a flag that genuinely contradicts
`--direct` should fail — and we must **not guess which of two contradictory flags
was the mistake.** That guess is exactly the backfill the protocol forbids; the
commander resolves it, not us.

Two tiers:

| Tier | Examples under `--direct` | Action |
|------|---------------------------|--------|
| **Moot** — `--direct` simply overrides it; nothing to guess | `--ly-per`, `--jumps-per` | Tolerate, ignore |
| **Contradictory route-shape intent** — two flags assert conflicting shapes | `--hops`, `--loop`, `--via`, `--towards` | Reject; do not pick a winner |

The dividing test: does the flag merely become *unused* (moot — tolerate), or does
it *assert a route shape* that a single direct hop cannot honour (contradictory —
reject)? `--ly-per` becomes unused. `--via` demands a midpoint a one-hop run
cannot service. `--hops` asserts a hop count that contradicts "single hop".

## Deliberate variations from the spec (recorded honestly)

Following the established practice — each is a chosen difference, flagged, not a
gap to be "fixed" back.

1. **Single hop only.** Spec line 448's plural "hops" leans toward multi-hop
   `--direct`. We follow the legacy behaviour (hops forced to 1) and the bounded
   reading. Multi-hop direct has no bound on its intermediate stations, so it is a
   separate, bigger thing if ever wanted.
2. **Requires both endpoints.** The spec is *silent* — its early-failure list
   (lines 223–239) spells out "X without Y" for five other options and pointedly
   omits `--direct`. We resolve the gap to the bounded two-anchor case.
3. **Open-destination mode dropped.** See "What the legacy did". Deferred, not
   lost.

## Architecture — one shared meaning, no per-engine option logic

Complies with the planner's shared-semantics rule by construction:

- `--direct`'s meaning resolves **once** into canonical request state: in
  `run_request` it sets the effective hop count to 1 and carries the `direct`
  flag. Dispatch and the planner consume that one canonical state.
- Only the fixed-pair single-hop engine consumes the flag, at the one place it
  already owns the reachability decision (`_best_pair_plan`). No parallel
  `route_*._direct()` helpers; no second engine reinterprets it.

## Where it plugs in

- **Dispatch.** `plan_route` (`run_route.py:62`) routes on `request.hops`. `--hops`
  defaults to 2, so the canonical move is to normalise `hops → 1` when `direct`
  is set, in `run_request`. That sends it through `_plan_single_hop`
  (`run_route.py:193`) → `_plan_fixed_endpoints` with no dispatch change.
- **The one functional change.** `_best_pair_plan` (`route_onehop.py:365`) calls
  `plan_jump_path` per station pair and skips pairs that are unreachable. Under
  `--direct` it bypasses that call, sets the pair's `jump_path = None`, and goes
  straight to the market query. Every other step — market fetch, cargo optimise,
  scoring, best-pair selection — is unchanged.
- **Renderer.** A `None` jump path is new; today every hop carries a real one,
  and the "Travel:" block dereferences it directly (`render_text.py:187`). A
  guard ahead of the existing two branches handles it — under `--direct` the
  Travel block becomes one honest line, the routing simply ignored:

  ```python
  if hop.jump_path is None:
      lines.append("    Direct — no jump route planned; plot your own")
  elif hop.jump_path.is_same_system:
      lines.append("    Same-system supercruise")
  else:
      ... existing jump-count / ly / path line ...
  ```

  The `From:` / `To:` blocks already name both stations either side of it, so the
  one line is enough. Output styling (a straight-line ly figure, say) is a later
  cosmetic pass, not this slice.

## Steps

One logical step at a time, review between each.

1. **Un-gate + validation.** Remove `--direct` from the unsupported tuple
   (`validation.py:41`). Make the `--ly-per` requirement (`validation.py:26`)
   conditional on `not request.direct`. Add the rejections: `--direct` without
   both `--from` and `--to`; `--direct` with `--towards`; `--direct` with
   `--start-jumps` / `--end-jumps`. (`--direct`+`--loop` already rejected at the
   parser; `--direct`+`--via` is covered while `--via` stays gated, and gets its
   own explicit rejection when `--via` lands.) Confirm
   the `--jumps-per` keyed default and the endpoint station expansion do not blow
   up when `--ly-per` is `None` under `--direct`.
2. **Canonical state.** In `run_request`, when `direct` is set, resolve the
   effective hop count to 1 so dispatch reaches the fixed-pair single-hop planner.
3. **Reachability skip.** Add the `--direct` branch to `_best_pair_plan`: no
   `plan_jump_path`, `jump_path = None`, straight to the market query. The
   selling-data / buying-data / no-profitable-trade failure families are
   unchanged; the "no reachable pair" family no longer fires under `--direct`.
4. **Renderer.** Confirm and, if needed, adjust `render_text.py` for a `None`
   jump path on a hop.
5. **Documentation** (after code accepted): `SPEC_STATUS.md`, `BASELINE.md`,
   `INDEX.md`, and the Slice 18 completion report.

## Out of scope

- **Open-destination / "to anywhere" direct** — deferred (see above).
- **Multi-hop direct** — excluded by the `--direct`/`--hops` mutual exclusion.
- **`--direct` with `--start-jumps` / `--end-jumps`** — rejected, not supported.
  Empty-jump positioning is not a thing under `--direct`. The rejection is built
  in step 1; it is named here only to mark it settled.
- **Reshaping any search engine** — none of the open or multi-hop engines is
  touched.
- **The `--ls-penalty` curve** — unchanged.

## Acceptance — spot-checks, handed to Tromador

```text
--from X --to Y --direct --capacity C --credits N   (no --ly-per)
    -> best single trade X->Y, no jump path shown, succeeds
--from X --to Y --direct ... --ly-per 15            (stray, irrelevant)
    -> still works; --ly-per ignored, no error
--from X --to Y --direct --hops 3
    -> parser rejects (mutually exclusive)
--from X --direct  (no --to)                        -> clean CommandLineError
--from X --to Y --direct --towards Z                -> clean CommandLineError
--from X --to Y --direct --start-jumps 2            -> clean CommandLineError
--from X --to Y --direct, X and Y absurdly far apart
    -> still returns the trade (no reachability rejection)
default (no --direct)                               -> fixed-pair one hop unchanged
```

## Validation posture

No automated test harness (project decision). Validation is spot-check plus
flake8 on the touched regions. All test commands are handed to Tromador to run;
the agent does not run them automatically.

## Documentation updates (after code is accepted)

- `SPEC_STATUS.md` — `--direct` option row and the Reachability section move off
  `[todo]`; record it as `[varied]` with the single-hop / both-endpoints /
  open-destination-dropped notes, and add it to "Deliberate variations".
- `BASELINE.md` — `--direct` added to "what works now"; removed from the modifier
  list in "what's still owed".
- `INDEX.md` — Slice 18 entry.
- Slice 18 completion report.
