# Slice 32 — Trade Run Route Output Rewrite (Rich Tiered Station-Centric Default, `--raw`, `--80col`)

*Proof of completion. Planned in conversation across several sessions — no
separate plan doc, like Slices 20, 23, 28 — and tuned live against rendered
output. Built in four commits, verified by flake8, throwaway render probes, live
runs, and eyeonus sign-off.*

---

## Summary

`trade run`'s route output was rebuilt from a single plain-text renderer into a
layered presentation:

- **A rich default** — a colour table built on the `rich` library, with three
  verbosity tiers (summary / standard / verbose).
- **`--raw`** — the plain-text format kept underneath: literal, 80-column,
  hop-centric, verbosity-gated, for grep / pipe / scripts / diagnostics. A
  format, not a tier.
- **A station-centric model** — every rich tier renders a row per *stop* (sell on
  arrival, buy before leaving), so the table reads the way the route is flown
  rather than hop by hop.
- **Width adaptation** — each tier degrades to a narrow terminal by shedding or
  rearranging columns rather than folding to mush; `--80col` forces the portable
  80-column layout.

Commits:

| Commit | What |
|--------|------|
| `fb3ec853` | Rewrite the plain-text route output: hop-centric, 80-column, verbosity-gated. (This becomes `--raw`.) |
| `f4630c04` | Add the rich (colour table) renderer as the default; `--raw` selects the plain text. |
| `524615e5` | Three rich tiers — summary / standard / verbose — and `--narrow`. |
| `8e884ecf` | Convert all tiers to the station-centric per-stop model; rename `--narrow` to `--80col`; supercruise nav marker; width-adaptive columns. |

State docs (`SPEC_STATUS.md` / `BASELINE.md` / `INDEX.md`) updated in this
slice's docs commit.

---

## The output ladder

One format switch and three rich tiers:

- **`--raw`** — the plain-text format. Not styled, not a table: literal lines
  wrapped to 80 columns, hop-centric (one block per hop, aligned Buy / Travel /
  Sell, a foot `Summary:` on multi-hop routes, thousands-grouped numbers). For
  grep, pipes, scripts, diagnostics, and the GUI's intercept path. This is the
  old default output, preserved unchanged behind the flag.
- **`--summary`** — the lean glance (rich).
- **default (standard)** — the everyday view (rich).
- **`-v` verbose** — the lead-by-the-nose walk (rich).

`--80col` forces the rich output to a portable 80 columns; without it the table
uses the full terminal width, and a pipe or redirect falls back to 80
automatically (rich reports 80 for a non-tty). The flag reads `--80col` for
clarity; the internal request attribute stays `narrow` (a valid identifier).

---

## The station-centric model

All three rich tiers share one shape: a **row per stop**, not per hop. At each
station you see what you **sell** on arrival (the cargo you came in with) and
what you **buy** before leaving (the cargo for the next leg) — different
commodities at the same place. The origin has nothing to sell, the final stop
nothing to buy; a hop's profit and the running balance land on the row where the
cargo is sold (arrival). The leg leaving a station — its jumps — sits under that
station's name. Stops are unnumbered, to avoid clashing with hop numbers.

This replaced an earlier hop-centric table (one row per hop, pairing a single
commodity's buy and sell across two different places), which read awkwardly
because a row's buy and sell happened at different stations. The per-stop model
puts each action where it actually happens — the change eyeonus signed off as
"this one I like, no notes".

---

## What each tier carries

**Wide (full terminal width):**

| Tier | Columns | Loads | Nav under station |
|------|---------|-------|-------------------|
| summary | Station · Sell · Buy · Profit | both sides, comma list, no prices | none |
| standard | Station · Sell · Buy · Profit · Balance | buy side priced, sell side unpriced; capped buy flagged | the flown systems condensed to one line · distance |
| verbose | Station · Sell · Buy · Profit · Balance | both sides priced; capped buy flagged | each jump on its own line · leg distance |

**At 80 columns — each tier makes its own compromise to keep the Profit column
on screen:**

- **summary** keeps both sides (its cells are short — no prices), so nothing is
  dropped.
- **standard** drops the Sell column, keeping the priced Buy and the route line.
- **verbose** folds Sell and Buy into one tagged `Trade` column, keeping both
  sides; its trade-off is height — it can run long on a deep route.

**Numeric shedding:** wide shows Profit and Balance; Balance sheds first as the
terminal narrows, then each tier's compromise above keeps Profit. Summary never
carries Balance (the running total is a standard/verbose detail).

**Frame:** verbose rules between every stop in dim chrome; standard separates
stops with a blank line at every width; summary is a tight grid.

**Bulk-cap flag.** A Metals/Minerals buy the bulk-sale-tax cap held back gets an
amber ⚑ on the buy line, with a one-line footnote, on standard and verbose.
Summary stays clean.

**Supercruise.** A same-system leg is a supercruise to another station in the
same system — no hyperspace jump, so its distance is 0.0 ly — and shows
`↓ Supercruise · 0.0 ly` rather than a silently blank leg.

---

## Colour

The palette is grounded in Elite's HUD orange (`#f07b05`), used as **chrome** —
the table frame, the column headers, the Total label — so the data glows inside
an orange frame the way the in-game HUD does. The data colours are taken off
that orange on the colour wheel so they harmonise rather than just share screen
space: **azure** stations (orange's complement), **gold** loads (analogous),
**emerald** profit (a tetrad partner), with a soft cyan origin. Each coloured
column alternates a medium and a lighter shade of its hue row to row, in sync, so
a row reads as a whole and a folded name stays with its stop. The bulk-cap flag
is advisory **amber**; the combined-cell Sell / Buy labels sit in **dim chrome**,
set off from the gold commodity by hue. Truecolour hex throughout — `rich`
downgrades gracefully on terminals without 24-bit colour.

---

## Modules

- **`render_rich.py`** (new) — the rich renderer. `render_run_result_rich(result,
  tier, width)` builds the `rich.Group`; `_stops_table(route, tier, width)` is
  the shared station-centric table; the cell builders (`_trade_cell`,
  `_side_cell`, `_combined_trade_cell`, `_trade_entry`), the nav builder
  (`_append_nav`), the header / totals lines, the colour constants, and the
  per-tier width thresholds live here.
- **`render_text.py`** — keeps `render_raw` (the plain-text format) and
  `render_run_result` (the dispatcher: `--raw` → plain text; otherwise tier by
  `--summary` / `-v` / default → the rich renderer). The shared warning /
  positioning / diagnostics / route-note helpers feed both formats so they stay
  in step.
- **`run_cmd.py`** — the `--raw`, `--summary`, `--80col` switches; `render()`
  computes the width budget (80 under `--80col`, else `cmdenv.console.width`) and
  prints the renderable through the shared rich console.

The width budget is threaded `run_cmd.render()` → `render_run_result(…, width)` →
`render_run_result_rich(…, width)` → `_stops_table(route, tier, width)`, so the
table sheds or combines columns to match exactly what it will be printed at.

---

## Verification

- **Static.** flake8 clean on `render_rich.py`, `render_text.py`, `run_cmd.py`.
  `--80col` confirmed legal at the argparse level (a leading digit after `--` is
  accepted with an explicit `dest`); `ParseArgument` forwards verbatim, no dest
  re-derivation.
- **Render probes.** Throwaway probes built minimal result DTOs (no database) and
  rendered each tier at width 80 and 140, printed through a fixed-width console —
  used to confirm the column set and content per shape, and to settle the
  "does default show sell prices?" question: it does not. Standard's sell side is
  unpriced, and at 80 columns standard carries no sell lines at all. Probes
  deleted after use.
- **Live runs (Tromador).** All six shapes (summary / standard / verbose, each at
  full width and `--80col`) run on Sol → Lave across five hops.
- **Sign-off (eyeonus).** The verbose stops layout and the final tier set both
  signed off.

---

## Notes and variances

- **No implementation-plan doc.** Designed conversationally and tuned live
  against rendered output (and screenshots), like Slices 20 / 23 / 28. The shape
  moved as it was seen: free-form blocks → a hop-centric table → the
  station-centric per-stop model; buy/sell columns swapped and reverted ("sell
  before buy"); the standard-at-80col rule added for clarity then removed once
  standard went Buy-only and its cells were short again.
- **`--summary` graduated.** It was a parse-but-inert legacy option; it now
  selects the summary tier. `--show-jumps` and `--progress` remain inert (the
  jump path already shows in standard/verbose, so `--show-jumps` toggles
  nothing).
- **Profit attribution in the per-stop model.** Profit lands on the arrival row
  (where the incoming cargo is sold). In Buy-only standard at 80col the Buy shown
  on a row is the *next* load, so that row's profit belongs to the *previous*
  load — read as "banked on arrival, load this next", reinforced by the running
  Balance. Accepted as the cost of the buy-centric narrow view.
- **The GUI.** Most users will reach `trade run` through the GUI, which takes
  `--raw` or intercepts before the renderer — so the rich tiers are a CLI
  affordance and the plain `--raw` format remains the machine / automation path.
- **Supercruise distance.** A same-system leg's `JumpPath.distance_ly` is 0.0
  (the polyline of zero jumps), so the marker reads `· 0.0 ly`; the system is the
  one the station already sits in, so it is not named.

---

## Housekeeping

- `SPEC_STATUS.md`: `--summary` → done; `--raw` / `--80col` added (beyond the
  spec); the Output contract section rewritten; a new variation for the rich
  tiered station-centric output; open decision 4 (machine-readable output) noted
  against `--raw`; the parse-but-inert list trimmed to `--show-jumps` /
  `--progress`.
- `BASELINE.md`: `render_rich.py` added to the module map; the Route output
  bullet rewritten to the rich tiered default + `--raw` + `--80col`; the headline
  and the owed list updated.
- `INDEX.md`: this Slice 32 entry.
