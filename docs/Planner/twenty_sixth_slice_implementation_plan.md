# Slice 26 — `--loop` (Return to the Starting Station)

*Implementation plan. Status: closed, 2026-06-13. Part A (anchored loop)
delivered. Part B (unanchored loop) investigated and decided against — not
built. See `twenty_sixth_slice_completion_report.md` and
`unanchored_loop_investigation.md`.*

---

## Why

`--loop` is the classic shuttle playstyle: start at a station, trade
out for N hops, end up back where you started. It is the most
meaningful option left on the gated list.

It splits naturally in two. The **anchored loop** (`--from` named) is
cheap to build honestly: a loop is fixed-terminal multi-hop where the
terminal *is* the origin, and the fixed-terminal engine
(`route_anchored.py`) already handles everything it needs — a
pre-build oracle run (`--from X --to X --hops 2`) confirmed the engine
closes on its own origin today. The **unanchored loop** (`--from`
omitted) is part of the same contract but is a genuine search-design
problem; it gets probes before code.

---

## Contract

Spec §loop routes:

- `--loop` requires the route to finish at the starting station.
- Incompatible with `--direct` and `--unique`.
- A loop route is valid only if every hop is valid and the final
  station is the original starting station.
- Ranking should not reward longer routes purely for having more hops.

The ranking point is satisfied trivially: `--hops` is fixed per run,
so every complete loop candidate has the same hop count and the
existing practical-score ranking compares like with like. Recorded,
not built.

**The unanchored case is in the contract.** Verified 2026-06-12
against the legacy command surface (the historical
`commands/run_cmd.py`, read from git history with authorisation — the
quarantined modules were not needed): with `--from` omitted, legacy
seeded *every* suitable station (one that both sells and buys) as an
origin, pruned routes that could no longer reach back to their own
first system in the remaining range, and kept only routes whose last
station was their first. So `--loop` with no `--from` worked in
legacy, by brute force over the preloaded galaxy. The rewrite owes the
same behaviour within the new architecture's bounds.

---

## Scope

**In (Part A):** `--loop` with a named `--from` (station or system),
`--hops >= 2`, on the fixed-terminal engine. All filters and modifiers
that compose with fixed-terminal routes compose with loops.
`--start-jumps` composition is attempted (the design supports it
structurally); if its spot-check misbehaves it is gated with a clear
message and recorded — not silently shipped.

**In (Part B):** `--loop` with `--from` omitted — the galaxy-wide
loop. Joins the existing galaxy-wide family (interactive confirmation
prompt; slow by nature is acceptable, unbounded is not). Probe-gated
design below.

**Out (recorded so they stay decided):**

- **`--unique` / `--shorten` pair rules.** Both options are still
  gated, and their gates already reject any combination with `--loop`.
  The explicit pair rules land with those options, not before.
- **`--end-jumps` with `--loop`** — already rejected by the existing
  "`--end-jumps` requires `--to`" rule, and a loop has no end anchor
  distinct from its start. Nothing to build.

---

## Part A — Anchored loop

### Canonical meaning (per the architecture rule)

The option's meaning is resolved once: a loop is a fixed-terminal
route whose terminal set, per route chain, is **the chain's own origin
station**. Engines do not interpret `--loop`; the anchored engine
receives a loop mode and a per-chain terminal rule, nothing else.

### Engine changes (`route_anchored.py`)

`_plan_multi_hop` gains a loop mode (or a thin `_plan_loop` entry
sharing its body — decided at build by whichever reads cleaner):

1. **Origins.** As today: `_stations_from_endpoint(role="source")` on
   `from_endpoint`, intersected with the same endpoint's
   `role="destination"` set — an origin that can never be sold to can
   never close its loop, so its chains are dead weight from the start.
   (Legacy's origin rule was the same intersection: sells ∩ buys.)
2. **Terminal rule.** The final hop calls `best_fixed_pair_trade_from`
   with a single destination per frontier node: the node's root
   station (walk the `parent` links to `hop_index == 0`; hops <= 25,
   so the walk is trivial).
3. **Envelope anchor.** Today the destination envelope is anchored on
   the shared `--to` system. In loop mode it anchors per node on the
   node's root station's coordinates. Without `--start-jumps` every
   root shares one system, so this is the same point; with positioning
   it is what makes the composition correct. (Legacy's loop pruning
   was the same geometry: distance back to the route's own first
   system against remaining range.)
4. **Frontier dedupe key.** Today: one node per destination system.
   In loop mode: one node per `(root_station_id, destination_system)`.
   Chains with different roots have different terminals — they are not
   near-duplicates of each other, exactly as nodes aimed at different
   `--to` anchors would not be. Without this, a system `--from`'s
   dominant origin station could starve every other origin's chains
   out of the beam. The frontier width cap still applies globally.
5. **Partial routes suppressed.** An unclosed loop is not a loop. Both
   partial-route fallback sites (expansion collapse, final-hop
   collapse) raise the loop failure instead of returning a partial
   route.

### Validation (`validation.py`)

- Remove `--loop` from the unsupported-options gate.
- `--loop` without `--from` stays gated (UnsupportedRunShape, clear
  message) until Part B lands, then the gate comes out and the
  galaxy prompt takes over.
- `--loop` requires `--hops >= 2` — a 1-hop loop is buying and selling
  at the same counter. (`--hops` defaults to 2, so a bare `--loop` is
  a 2-hop loop.)
- Add an explicit `--direct` / `--loop` contradictory-options rule.
  The existing comment claims the parser rejects this pair; it does
  not (the parser groups are `--to`/`--towards`/`--loop` and
  `--direct`/`--hops`) — today the pair only fails indirectly via
  "--direct needs both --from and --to". The explicit rule gives the
  right message; the stale comment is corrected.

`--loop` with `--to` or `--towards` stays parser-rejected (existing
mutually-exclusive group).

### Dispatch (`run_route.py`)

A loop request carries `from_text` and no `to_text`, so today it would
fall into the open-anchor branch. A `request.loop` branch is added
ahead of it, routing to the anchored engine in loop mode. Single-hop
dispatch needs nothing: validation guarantees `hops >= 2`.

### Failure wording

Loop no-route failures name the loop: "No route closed the loop back
to <origin> within N hops under the supplied constraints." Mechanism
mirrors `--towards` (`NoTowardsProgress`): a loop-specific failure in
the existing no-route family, raised at the suppressed-partial sites
and on an empty finalist set. Exact type vs wording-on-existing-type
decided at build against `failures.py`.

### Renderer

No structural change expected — the route visibly starts and ends at
the same station. Spot-check the output reads sensibly; touch nothing
unless it doesn't.

### Part A verification (spot-checks, run live)

1. **Pre-build oracle** — done 2026-06-12: `--from "sol/abraham
   lincoln" --to "sol/abraham lincoln" --hops 2` closes on the origin
   today (Sol → Barnard's Star → Sol, 146ms). The engine needs no
   convincing; the slice is wiring.
2. **Station loop equivalence:** `--loop --from X --hops 2` must be
   byte-identical to `--from X --to X --hops 2` (single origin: the
   loop mode reduces to exactly that search).
3. **System loop:** `--loop --from sol --hops 3` — closes on its own
   start station; sane route.
4. **Filtered loop:** a realistic stacked-filter run (`--age`,
   `--pad-size`, `--ls-max`).
5. **Failure cases:** `--hops 1`; missing `--from` (gate wording);
   `--direct --loop`; an unreachable loop (tight `--ly-per`) and a
   demand-dead origin — each with the clear loop wording.
6. **Stretch:** `--loop --start-jumps 2`. Gate-and-record if it
   misbehaves.
7. **Non-loop regression:** loop mode is additive (a new dispatch
   branch plus loop-only conditionals), so existing shapes must be
   untouched — re-run two standard fixed-terminal baselines and
   confirm byte-identical output.

---

## Part B — Unanchored loop (probe-gated)

> **Outcome (2026-06-13): not built — decided against.** The probes below were
> run. P1 failed the seeding design (a cheap loop-fitness rank cannot contain
> the best loops within the fixed beam width of 50), and P2 showed the only
> width-50-honouring alternative (an honest loop per admitted origin) is cheap
> at the default 2 hops but explodes with depth. The galaxy-wide loop is not
> supported; `--loop` requires `--from`. Full record:
> `unanchored_loop_investigation.md`. The original design sketch below is kept
> as written, for context on what was tried.

### Semantics

The unanchored loop's answer is, by definition, the best anchored loop
over all eligible origins. The engineering question is purely how to
bound the origin set and share the search — legacy answered it with
the full preloaded galaxy, which is the one answer this architecture
forbids.

### Design sketch (probes decide the numbers)

- **Seeds.** The unanchored one-hop candidate machinery (the bounded
  temp-table design from Slices 5/15/23) already surfaces the
  galaxy's best trade pairs. Rank candidate origins by a loop-fitness
  metric — a station must buy well *now* (outbound ceiling) and sell
  well *later* (inbound ceiling) — and trim to the top K distinct
  origins. K is P1's output, not a guess.
- **Search.** Part A's loop engine generalised to multi-root seeding:
  one shared beam, the per-`(root, destination_system)` dedupe key
  from Part A, and a frontier policy that keeps roots alive (per-root
  cap vs one global width — P2 decides on evidence).
- **Prompt.** Extends the existing galaxy-wide confirmation prompt;
  non-TTY or non-affirmative exits cleanly, as the other two shapes do.
- **Failure wording.** Part A's loop family, galaxy variant ("no loop
  closed from any candidate origin …").

### Probes (scripts uncommitted, deleted at slice end)

- **P1 — seed fidelity.** Does a cheap loop-fitness rank actually
  contain the best loop origins? Run anchored loops from the top-N
  ranked stations and a control sample on a bounded region; check
  where the true best loop's origin ranks. Output: K, and the gate —
  if no affordable K reliably contains the winners, stop and decide
  with Tromador before any engine code.
- **P2 — beam policy.** Shared beam with per-root keys vs per-seed
  sequential searches: route quality, starvation, wall-clock. Output:
  the frontier policy and width arithmetic.

### Part B verification

- Closed-loop invariant on every result (last station is first).
- Seed containment evidence from P1 re-checked on the final engine.
- Filtered and unfiltered spot-checks; prompt behaviour; failure
  wording.
- Non-loop shapes untouched (no shared-path edits expected beyond the
  seeding entry; verified regardless).

---

## Docs owed at close

- Completion report (`twenty_sixth_slice_completion_report.md`)
  covering both parts.
- `SPEC_STATUS.md`: `--loop` → `[done]` only when both parts land;
  loop-routes section updated; early-validation moot list trimmed.
- `BASELINE.md`: route-modifier surface and the owed list updated.

## Order of work

1. ~~Pre-build oracle run~~ — done, engine closes on its origin.
2. Part A: validation rules + dispatch branch.
3. Part A: engine loop mode (origins, terminal rule, envelope anchor,
   dedupe key, partial suppression, failure wording).
4. Part A spot-checks 2–7.
5. *(Natural rest point — Part A is shippable alone with the
   unanchored gate in place.)*
6. Part B probes P1, P2; results recorded in this file; gate decision.
7. Part B build and verification.
8. Completion report; living docs; probes deleted; code and docs
   committed separately.
