# Slice 30 — `--shorten` (Reach the Destination in Fewer Hops)

*Implementation plan — audited and corrected. `--shorten` lets the planner
return a route **shorter** than `--hops` when the shorter route is the better
result, judged per hop. It is a fixed-`--to` feature only. The audit's two
blockers (open-origin harvesting, early-collapse failure ordering) are folded in;
see §10 for the resolved decisions.*

---

## 1. What the contract asks

Three sources, reconciled — they agree on the shape, and the legacy code pins
the exact metric.

**Spec** (`trade_run_black_box_spec.md` §shorten routes, lines 576–582):

- `--shorten` requires `--to`.
- Incompatible with `--loop`.
- "Prefer routes that reach the requested destination sooner when profit is
  comparable. A much worse route should not win solely because it is shorter."

**Wiki:** "Allows TD to return a shorter route than `--hops` if that route
produces a better result." Arg help: *"Find the shortest route with the best
gpt."*

**Legacy** (`archive/.../run_cmd.py`), authorised and read — the actual
mechanism:

1. `--hops N` becomes a **ceiling**, not a fixed length.
2. At every hop the search captures any chain that has *reached the
   destination* into a `pickedRoutes` list (`:1733`) — arrivals of length
   1, 2, … up to N.
3. After the search, everything that did not reach the destination is discarded
   (`routes = pickedRoutes`, `:1740`).
4. Each surviving route's score is **normalised per hop**: `score /=
   len(hops)` (`:1747`).
5. The winner is the best normalised (per-hop) score.

So "shorter wins when it is the better result" means **best practical score per
hop**, among routes that reach `--to`. Shortness is not the primary key — a
2-hop route at 50/hop beats a 1-hop route at 45/hop. The wiki's "shortest route"
is loose; the real rule is "best per-hop, ties to the shorter."

---

## 2. The ranking decision — the audit's main question

This is the one judgement call. The spec's "prefer sooner when comparable; a
much-worse route should not win on shortness" can be read two ways.

**Option A (recommended) — legacy-faithful per-hop normalisation.**
Rank arriving routes by `total_practical_score / hop_count`. The route with the
best per-hop value wins; ties break to fewer hops, then to higher total score.

- Matches shipped legacy behaviour exactly, and matches the wiki's "best gpt"
  (a per-effort measure).
- Deterministic and parameter-free. It reuses the score the engines already
  compute — no new constant.
- It *satisfies the spec guard* when "comparable / much worse" is read **per
  hop**, which is the natural reading given legacy normalises per hop: a short
  route with much-worse per-hop value loses; a comparable one wins on the
  division; a long route still wins if its per-hop value is genuinely higher.

**Option B — soft preference with a profit tolerance.** Keep total profit
primary, let a shorter route win only when its total is within X% of the best.
Rejected as the default: it needs a tolerance constant (a fresh magic number and
a fresh source of surprise), and it diverges from the legacy users already know.

**Recommendation: Option A.** "Comparable / much worse" in the spec is read in
per-hop terms, so A honours the spec's intent without a tolerance knob.
**Audit verdict: accepted** — Option A, no tolerance constant.

**The metric, precisely** — a ranking key, higher sorts better:

```text
shorten route key:  (total_practical_score / max(len(hops), 1),
                     -len(hops),
                     total_practical_score)
shorten node key:   (accumulated_practical_score / max(hop_index, 1),
                     -hop_index,
                     accumulated_practical_score)
```

Primary: per-hop practical score. Tiebreak: fewer hops (the "shorten" spirit).
Final tiebreak: higher total score, for determinism.

`--shorten` and `--towards` are mutually exclusive (§6), so the rank family has
three clean modes — towards / shorten / plain — with no cross-interaction.

---

## 3. Why this is a fixed-`--to` feature, and the shapes in scope

`--shorten` is defined relative to a destination: "reach `--to` sooner." With no
`--to` there is no arrival event to capture, and per-hop normalisation collapses
to "best single trade" (1 hop always wins on per-hop with no dilution). So the
`--to` requirement is structural, not arbitrary — legacy, spec, and wiki all
demand it.

Shapes that carry `--to`, and the engine each runs on:

| Shape | Engine | Part |
|-------|--------|------|
| `--from X --to Y --hops N` (fixed-terminal) | `route_anchored._plan_multi_hop` | **A** |
| `--to Y --hops N`, `--from` omitted (open-origin) | `route_common._plan_open_anchor_route` (`open_role="source"`) | **B** |

`--via` + `--shorten` is **deferred** this slice (§6) — `--via` runs its own
lane-diversity engine and composing the two needs its own pass.

---

## 4. The mechanism

The pattern is the same in both engines: **harvest every arriving route of every
length, then pick the winner by the shorten key.** Today each engine grows to
exactly N hops and selects one winner; `--shorten` widens the candidate pool to
the shorter arrivals as well. The precedent is `--towards`, which already
captures off-frontier "arrived" chains into a side list and folds them into the
final selection (`route_common.py:881, 936, 1071`).

### 4.1 Fixed-terminal (`route_anchored._plan_multi_hop`) — Part A

The arrival event here is the **final-pair close** onto Y
(`best_fixed_pair_trade_from`). Today it runs once, after the intermediate loop,
on the depth-(N-1) frontier. To get a K-hop arrival, close the depth-(K-1)
frontier onto Y.

Gated on `request.shorten`, add a harvest at the **top of each intermediate
iteration** (`for hop_layer in range(1, request.hops)`), where `frontier` holds
the depth-(hop_layer-1) nodes:

```text
iteration hop_layer=1:  frontier = seed (origin stations, depth 0)
                        close onto Y  -> 1-hop arrivals
iteration hop_layer=2:  frontier = depth 1
                        close onto Y  -> 2-hop arrivals
...
iteration hop_layer=N-1: frontier = depth N-2 -> (N-1)-hop arrivals
after loop (existing):   frontier = depth N-1 -> N-hop arrivals
```

Each close reuses the existing final-hop code path — `best_fixed_pair_trade_from`
per frontier node against Y's stations, wrapped in `_make_child_node` — into a
single `arrivals` pool. The existing final hop is the K=N entry of that same
pool.

**Winner:** `max(arrivals, key=<shorten or plain key>)` instead of
`max(finalists, key=accumulated_practical_score)`. With `--shorten` off,
`arrivals` is just the existing `finalists` and the key is `(score,)` — the
current winner, unchanged.

**Cost:** the close now runs N times (once per length), each over the ≤50-node
trimmed frontier against Y. Bounded, and gated — non-shorten runs pay nothing.

**Beam-fidelity note:** the best K-hop arrival can only be found among the
depth-(K-1) nodes that survived the width-50 trim. That is the same beam limit
the existing final hop already lives under; `--shorten` does not widen or worsen
it. Stated, not fixed.

### 4.2 Open-origin (`route_common._plan_open_anchor_route`, `open_role="source"`) — Part B

**Corrected after audit.** The first draft claimed "every completed node
(`hop_index ≥ 1`) is already a valid route ending at Y, so just harvest the
frontier." That is wrong. The intermediate frontier is built with
`terminal_hop=False` (`route_common.py:915`), which in source mode keeps only
stations that still have **onward demand** — viable as an *earlier* (intermediate)
hop. But a shorter route's origin is **terminal**: it only needs to *sell into*
the next station, not be a viable intermediate destination for a still-earlier
hop. A **source-only** origin is a legal shorter-route start that the
`terminal_hop=False` frontier filters out — so harvesting that frontier would
silently miss those routes.

The harvest must therefore be a **terminal close**, mirroring Part A exactly.
Gated on `request.shorten`, at each layer:

1. **Harvest arrivals** — run a terminal open-source expansion from the current
   frontier with `terminal_hop=True`. Its children are valid K-hop routes whose
   origin need only sell into the chain; add them to `shorten_pool`.
2. **Continue deeper** — run the existing `terminal_hop=False` expansion
   *separately*, used only to grow chains into the next (deeper) layer.

The existing final layer (`terminal_hop=True`, `:1054`) is the K=N harvest, so
the closes cover K=1..N — the same coverage as Part A.

`shorten_pool` is folded into `finalist_nodes` before the correction/selection
pass (alongside the existing `finalist_nodes.extend(arrivals)` at `:1071`), and
the shorten key is injected into the shared rank family (§4.3). Credit correction
applies per candidate, so a shorter chain is ranked on its **corrected** per-hop
score, consistent with how the engine already picks winners.

**Cost:** under `--shorten` each layer runs the expansion twice — one terminal
close for arrivals, one intermediate expansion for deepening. Same call shape as
today's expansion, gated; non-shorten runs pay nothing.

### 4.3 Shared ranking — unify the contract, not the engines

Add a `--shorten` branch to `_node_progress_rank` and `_route_progress_rank`
(`route_common.py:278, 299`), the family `--towards` already keys through:

```text
plain     -> (score,)                 # unchanged, today's behaviour
towards   -> (-distance, -hops, score)
shorten   -> (score/hops, -hops, score)
```

The fixed-terminal winner selection (§4.1) is routed through `_node_progress_rank`
too, so both engines read the same meaning. **Inert proof:** with `--shorten`
and `--towards` both off the key is `(score,)`, identical ordering to the
current scalar `max`, so every non-shorten run is byte-identical — the same proof
`--towards` and `--unique` used.

---

## 5. Partial-route and failure semantics under `--shorten`

A route shorter than `--hops` is normally a **partial route** — a shortfall,
flagged with `PartialRouteWarning`. Under `--shorten` that inverts: a shorter
route is the **deliberate, successful** result and must carry **no** partial
warning.

So under `--shorten`:

- The per-layer "frontier collapsed" early-returns that today emit a partial
  warning instead feed the collapsed-but-completed chains into the arrivals
  pool; selection happens over the pool at the end.
- A shorter winner is returned clean, no warning.
- The **failure** case is "no route reached `--to` at *any* length 1..N" — then
  the existing `NoReachableRoute` / `NoProfitableTrades` families apply,
  unchanged.

No new failure class is needed; `--shorten` reuses the no-route families. The
revisit (`NoUniqueRoute`) and loop classes are untouched.

### 5.1 Early-collapse ordering — arrivals before failure (corrected after audit)

Both engines today raise `NoUniqueRoute` **early** when a layer collapses and the
revisit-skip counter fired (`route_anchored.py:321, 454`;
`route_common.py:953, 1121`). Under `--shorten` that is wrong if the arrivals
pool already holds a valid shorter route: `--hops N` is a ceiling, so failing to
extend to a longer no-revisit route must not kill an already-valid shorter one.

Under `--shorten`, every early-collapse branch must check the pool **first**, in
this order:

1. **Valid arrivals exist** → stop deepening and select the best arrival by the
   shorten key. A collapse in shorten mode just caps the depth; it is not a
   failure.
2. **No arrivals, and revisit skips explain the collapse** → raise
   `NoUniqueRoute`.
3. **Otherwise** → the normal no-route / no-profitable-trades family.

Applied to **both** `route_anchored._plan_multi_hop` and
`route_common._plan_open_anchor_route`. The natural realisation: in shorten mode
a per-layer collapse `break`s to the unified final selection over the pool, and
only the pool-empty case reaches the existing failure logic (which already raises
`NoUniqueRoute` vs the no-route family correctly).

---

## 6. Validation, un-gate, and option interactions

In `validation.py`:

- **Un-gate:** remove `("--shorten", request.shorten)` from the `unsupported`
  tuple (`:204`).
- **`--shorten` requires `--to`** → `MissingRequiredInput` (spec line 578),
  mirroring the `--start-jumps`/`--end-jumps` checks already there.
- **`--shorten` with `--loop`** → `ContradictoryOptions` (spec lines 246, 580).
  Not currently a parser-level exclusion, so it is added here.

Interactions, stated:

- **`--towards`** — naturally excluded: `--towards` excludes `--to` (parser),
  `--shorten` requires `--to`, so the combination cannot arise. No extra rule;
  the `--shorten`-requires-`--to` check rejects `--towards --shorten` (no `--to`)
  on its own.
- **`--unique` / `--loop-interval`** — compose cleanly. The revisit history
  rides on each chain and the arrivals/closes already pass
  `forbidden_station_ids`; a shorten route still honours no-revisit. Allowed.
- **`--direct`** — `--direct` canonicalises to a single hop (mutually exclusive
  with `--hops` at the parser), and shortening a forced one-hop route is
  meaningless. **Audit verdict: reject** as contradictory — a clear error beats a
  silent no-op.
- **`--via`** — **deferred this slice** (audit accepted). `--via` runs the lane-diversity engine
  in `route_via.py`; harvesting shorter via-satisfying arrivals needs its own
  design. Until then `--shorten` + `--via` is rejected with a "not yet combined"
  message, matching how `--via` + `--towards` is handled (`validation.py:195`).
  Legacy did compose them (`filterByVia` then per-hop sort); revisiting that is a
  follow-up, noted not owed.

---

## 7. What this does NOT touch

- **No SQL / candidate-fetch change.** `--shorten` is a search-time selection
  rule over routes already fetched; it changes which *completed routes* compete,
  not which rows are read.
- **No cargo-optimiser change.**
- **No `score.py` / ls-penalty change** — the per-hop normalisation divides the
  existing practical score; the curve is untouched.
- **No beam-width or galaxy-prompt change.**
- **No renderer change** beyond suppressing the partial-route warning for a
  deliberately-shorter winner (§5) — the route renders with its own hop count as
  any route does.

---

## 8. Touch-point summary

| File | Change |
|------|--------|
| `validation.py` | Un-gate `--shorten`; add requires-`--to`, `--shorten`+`--loop`, `--shorten`+`--via` (deferred), and the `--direct` decision. |
| `route_common.py` | `--shorten` branch in `_node_progress_rank` / `_route_progress_rank`; open-origin per-layer `terminal_hop=True` harvest into `shorten_pool` (separate from the `terminal_hop=False` deepening expansion) folded into `finalist_nodes`; early-collapse arrivals-before-failure ordering (§5.1); partial-warning suppression under shorten. |
| `route_anchored.py` | Gated per-layer fixed-pair close into an `arrivals` pool; winner selection over the pool via the shared rank key; early-collapse arrivals-before-failure ordering (§5.1); partial-warning suppression under shorten. |
| `render_text.py` | Suppress the partial-route warning when `--shorten` selected a shorter route deliberately (verify the exact seam during build). |
| `route_via.py` | None this slice — `--shorten` + `--via` deferred at validation. |
| `failures.py` | None — reuses the no-route families. |
| `run_result.py` | None expected; confirm no new stat field is needed during build. |

Living docs (`BASELINE.md`, `SPEC_STATUS.md`, `INDEX.md`) updated on completion.

---

## 9. Verification and probes

- **Inert proof:** non-shorten benchmark shapes byte-identical before/after (the
  rank key is `(score,)` when shorten is off) — the proof `--towards` /
  `--unique` used.
- **Fixed-terminal validity:** `--from X --to Y --hops N --shorten` returns a
  route of ≤ N hops ending at Y; confirm the winner has the best per-hop
  practical score among the arrivals (instrument the pool at `-ww`).
- **Open-origin validity:** `--to Y --hops N --shorten` (no `--from`) returns a
  ≤ N-hop route ending at Y, origin chosen by the planner.
- **No spurious shortening:** a shape where the full-N route genuinely has the
  best per-hop value — confirm `--shorten` returns the full-length route, i.e.
  it does not shorten when shortening is worse.
- **Failure:** a `--to` that no route can reach within N hops fails in the
  no-route family, not as a partial.
- **Validation:** `--shorten` without `--to` rejected; `--shorten --loop`
  rejected; `--shorten --via` rejected (deferred); the `--direct` decision as
  settled.

Three targeted probes (the metric and the two corrected blockers are the risks):

1. **Per-hop selection probe** — a fixed-terminal shape where a shorter route
   has a higher per-hop score but lower total profit than the best N-hop route.
   Confirm `--shorten` picks the shorter (per-hop wins) while the plain run
   picks the longer (total wins) — proving the metric is wired and the two paths
   diverge exactly where intended.
2. **Open-origin source-only probe** (Blocker 1) — `--to Y --hops N --shorten`
   where a shorter origin can sell into Y but would *not* qualify as an
   intermediate node because it lacks onward demand. Confirm `--shorten`
   considers and can return that shorter route — i.e. it is not missed because
   the origin failed `terminal_hop=False`. This is the probe that proves the
   terminal-close harvest (§4.2), not the frontier harvest, is in place.
3. **No-revisit collapse-after-arrival probe** (Blocker 2) —
   `--from X --to Y --hops N --shorten --unique` (or `--loop-interval K`) where a
   valid shorter arrival exists but deeper expansion later collapses under the
   revisit rule. Confirm the planner returns the shorter arrival and does **not**
   raise `NoUniqueRoute`. Run on both engines (add a `--from`-omitted variant for
   the open-origin path).

---

## 10. Decisions — resolved by audit

1. **Ranking metric** → **Option A** (legacy per-hop normalisation), no tolerance
   constant. §2.
2. **`--direct` + `--shorten`** → **reject** as contradictory. §6.
3. **`--via` + `--shorten`** → **deferred** this slice (rejected at validation
   like `--via` + `--towards`). §6.

Two blockers raised by the audit, both folded into the plan above:

- **Blocker 1** — open-origin harvesting must be a `terminal_hop=True` close, not
  a frontier harvest, or source-only origins are missed. Fixed in §4.2.
- **Blocker 2** — under `--shorten`, an early revisit-collapse must not override
  an already-valid shorter arrival. Fixed in §5.1.
