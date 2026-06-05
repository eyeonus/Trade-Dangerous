# trade run — Black-Box Spec Implementation Status

`trade_run_black_box_spec.md` is the behavioural contract — an AI extraction
from the legacy path, then audited long-form by the dev team. It is the Bible.
This file is its **coverage map**: read it to see what is built, what was
deliberately varied, and what is still to do, and then open only the spec
section you actually need — instead of re-reading 33 KB each session.

Where this map and the spec disagree, the disagreement is **deliberate** (see
"Deliberate variations") — do not "fix" a varied behaviour back to the spec
without raising it.

Status as verified against `validation.py`, `run_request.py`, and the parser in
`commands/run_cmd.py`.

## Legend

```text
[done]    built, to spec
[varied]  built, deliberately different from spec — see the note
[todo]    in the spec, not yet built (gated in validation, or parses but inert)
```

---

## Option contract

### Financial and ship options

| Option | Status | Note |
|--------|--------|------|
| `--capacity` | `[done]` | Required. Rejected if missing or ≤ 0. |
| `--credits` | `[done]` | Required. Negative rejected. |
| `--insurance` | `[done]` | Reserved credits; must leave a trading budget. |
| `--limit` | `[done]` | Per-commodity unit cap; 0 = unlimited; must be ≤ `--capacity`. |
| `--margin` | `[done]` | Fraction (0–1) of accumulated profit *not* trusted as later buying power. |

### Route shape options

| Option | Status | Note |
|--------|--------|------|
| `--from` | `[done]` | Station or system; may be omitted (open origin). |
| `--to` | `[done]` | Station or system; may be omitted (open destination). |
| `--hops` | `[done]` | 1–25; an excessive count is rejected. |
| `--towards` | `[todo]` | Gated. |
| `--loop` | `[todo]` | Gated. |
| `--via` | `[todo]` | Gated. |
| `--avoid` | `[todo]` | Gated. |
| `--direct` | `[todo]` | Gated. |
| `--shorten` | `[todo]` | Gated. |
| `--unique` | `[todo]` | Gated. |
| `--loop-interval` | `[todo]` | Gated. |

### Reachability options

| Option | Status | Note |
|--------|--------|------|
| `--ly-per` | `[done]` | Required (unless `--direct`, which is gated). |
| `--jumps-per` | `[done]` | Any non-negative int. Keyed default: omitted → 2 if `--ly-per ≤ 12.5`, else 1. |
| `--start-jumps` | `[todo]` | Gated (non-zero). |
| `--end-jumps` | `[todo]` | Gated (non-zero). |
| `--empty-ly` | `[todo]` | Parses but inert — only feeds the gated `--start-jumps`/`--end-jumps`; not mapped onto the request. |
| `--show-jumps` | `[todo]` | Parses but inert — the jump path shows in expanded output regardless of the flag. |

### Station filters

| Option | Status | Note |
|--------|--------|------|
| `--planetary` | `[done]` | Y/N/? accepted-state set. |
| `--no-planet` | `[done]` | Rejected if combined with `--planetary`. |
| `--fleet-carrier` | `[done]` | Y/N/? set. |
| `--settlement` | `[done]` | Y/N/? set. |
| `--black-market` | `[done]` | Y/N/? set. |
| `--ls-max` | `[done]` | Max distance from arrival star. |
| `--age` | `[done]` | Excludes rows older than N days. No default — absent `--age` uses every row (deliberate; see BASELINE). |
| `--pad-size` | `[varied]` | Ship-fit threshold, not the legacy model — see Variations. |

### Commodity and trade filters

| Option | Status | Note |
|--------|--------|------|
| `--gain-per-ton` | `[done]` | Min profit/unit; default 1. |
| `--max-gain-per-ton` | `[done]` | Max profit/unit; default 0 = off. A *default* cap is a deferred idea (see BASELINE), the option itself works. |
| `--supply` | `[done]` | Min source supply. |
| `--demand` | `[done]` | Min destination demand. |

### Search and display controls

| Option | Status | Note |
|--------|--------|------|
| `--routes` | `[todo]` | Only `--routes 1` supported; > 1 rejected. |
| `--max-routes` | `[todo]` | Gated (non-zero). |
| `--prune-score` | `[todo]` | Gated (non-zero). |
| `--prune-hops` | `[todo]` | Gated (non-default; default 3). |
| `--checklist` | `[todo]` | Gated. |
| `--x52-pro` | `[todo]` | Gated (also requires `--checklist`). |
| `--summary` | `[todo]` | Parses but inert. |
| `--progress` | `[todo]` | Parses but inert. |

### Beyond the spec's option contract

| Option | Status | Note |
|--------|--------|------|
| `--max-price` | `[varied]` | **Added** — not in the spec. Absolute price cap (default 1,500,000 cr/t). See Variations. |
| `--ls-penalty` | `[done]` | The protected curve (spec §ls-penalty), implemented in `score.py`. |

Implementation note: option status records the shared behavioural meaning. Route
engines may apply that meaning differently for performance, but must not own
separate semantics for the same option.

---

## Behavioural sections

| Spec section | Status | Note |
|--------------|--------|------|
| Early validation | `[done]` | Static checks before planning. Some listed early-failure pairs (e.g. `--loop` with `--unique`) are moot while those options are gated. |
| Name and place resolution | `[done]` | Scoped system/station forms; unknown / ambiguous / system / station distinguished. |
| Origin selection | `[done]` | Station / system / omitted. `--start-jumps` expansion is `[todo]`. |
| Destination selection | `[done]` | Station / system / omitted. `--end-jumps` expansion is `[todo]`. |
| Avoid semantics | `[todo]` | `--avoid` gated. |
| Via semantics | `[todo]` | `--via` gated. |
| Station eligibility | `[done]` | All implemented filters applied SQL-side. |
| Market-data eligibility | `[varied]` | To spec, plus `_MIN_MEANINGFUL_DEMAND = 2` — see Variations. |
| Trade candidate generation | `[done]` | |
| Cargo fitting | `[done]` | Capacity, credits, insurance, margin, limit, supply, demand-as-cap, gain-per-ton. Avoided-commodity input is moot (`--avoid` gated). |
| Credits, insurance, margin | `[done]` | |
| Reachability | `[done]` | `--ly-per`, `--jumps-per`, same-system supercruise. `--direct` is `[todo]`. |
| Route generation | `[done]` | |
| Route ranking | `[done]` | Practical value with ls-penalty; `--to` honoured. The other shaping options (`--towards`/`--loop`/`--shorten`/`--via`/`--unique`) are gated. |
| ls-penalty | `[done]` | Protected curve. |
| towards mode | `[todo]` | |
| loop routes | `[todo]` | |
| shorten routes | `[todo]` | |
| unique and loop interval | `[todo]` | |
| Pruning controls | `[todo]` | |
| Output contract | `[done]` | Default route output plus verbose per-hop / cumulative / jump-path detail. |
| Checklist output | `[todo]` | |
| Progress output | `[todo]` | |
| Failure behaviour | `[varied]` | Distinct families implemented; affordability is folded into "no profitable trades" — see Variations. The via/towards/loop/unique no-route classes are moot (gated). |
| Data requirements | `[done]` | Database is the source of truth; only the needed scope is materialised. |
| Performance contract | `[done]` | Early narrowing, filters pushed into SQL, materially faster than legacy. |

---

## Deliberate variations from the spec

Each of these is a chosen difference, not a gap. Do not revert without raising it.

1. **`--pad-size` is a ship-fit threshold.** Spec §Station filters says "require
   compatible landing pad size". We took it to mean "the ship needs at least
   this pad": `L` = large-max only; `M` = medium/large + unknown-pad; `S` =
   every station. `?` / multi-letter values are rejected. The legacy
   "exclude large starports to find trades smaller ships can reach" use case is
   deliberately dropped — simplicity judged to outweigh it.

2. **`--max-price` added.** The spec's option contract has no absolute
   price cap. Owner-set fleet-carrier prices produce fictional multi-million
   cr/t rows that would win and distort the search, so we added one (default
   1,500,000 cr/t, sized so no legitimate non-carrier row is lost; `0`
   disables). A different axis from `--max-gain-per-ton`, which caps per-ton
   *profit*.

3. **`_MIN_MEANINGFUL_DEMAND = 2`.** Spec §Market-data eligibility accepts any
   positive demand. A stocked commodity reports its dormant buy side as 0 or 1,
   so a `demand_units = 1` destination is an unfillable sale, not a real trade —
   we decline it; legacy accepts it.

4. **No separate "cannot afford cargo" failure.** Spec §Failure behaviour lists
   distinct no-data / no-route classes; we fold "profitable trades exist but the
   commander can't afford any" into "No profitable trade was found". Proving the
   distinction is expensive and the case rarely matters in normal play.

5. **`--jumps-per` keyed default.** The spec mandates no default. Omitted
   `--jumps-per` defaults to 2 when `--ly-per ≤ 12.5` (short-range ships reach
   too little on one jump), else 1.

---

## Spec "Open decisions for supervisor" — how resolved

The spec closes with five decisions left to the supervisor. Current resolution:

1. **Demand: eligibility threshold or hard cargo cap?** → **Hard quantity cap.**
   Destination demand both gates eligibility and caps loaded quantity, with a
   further `floor(demand * 0.25)` sub-cap on Metals/Minerals to avoid the
   in-game bulk-sale penalty.
2. **Profit-comparison tolerance under market drift?** → Not formalised as a
   number. Spot-checked against `--old` while it existed; `--old` is now retired
   (Slice 14), so comparison is against route validity and the benchmark
   criteria, allowing ordinary drift.
3. **Per-benchmark wall-clock gate?** → No fixed figure; the standard is
   "materially faster", measured per change. The galaxy-wide shapes are
   confirmation-gated rather than time-bounded.
4. **Machine-readable output mode?** → Not implemented. The plain-text output
   was instead expanded (Slice 9) to expose auditable per-hop / cumulative
   figures. A structured mode remains an open idea.
5. **Safety limit on broad galaxy-wide searches?** → **Interactive confirmation
   prompt**, not a hard limit. A non-affirmative answer or non-TTY invocation
   exits cleanly without planning.

---

## Options that parse but do not act yet

Accepted by the parser — so they do **not** error — but nothing honours them yet.
Listed so a worker does not assume they work just because they run clean.

Three are output-display options carried over from the legacy path. Whether the
new planner reuses any of them is an open question for a later output / look-and-
feel pass; none is on the radar now, while output styling is not a priority.

```text
--show-jumps    output display: the jump path already shows in expanded output,
                so the flag toggles nothing today
--summary       output display: a legacy summary mode, not honoured yet
--progress      output display: a legacy progress mode, not honoured yet
```

`--empty-ly` is the odd one out — an input, not a display option. It supplies the
unladen range to `--start-jumps` / `--end-jumps`, falling back to `--ly-per` when
absent. It parses as `emptyLyPer` and is not yet mapped onto the request; Slice 16
wires it, after which it leaves this list. It is meaningful only alongside
start/end-jumps and is a deliberate no-op on its own.
