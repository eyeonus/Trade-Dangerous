# Slice 33 — Close Out the Remaining `trade run` Options (`--checklist`, `--progress`; X52 MFD and `--show-jumps` removed)

*Proof of completion. Planned in conversation — no separate plan doc, like Slices
20, 23, 28, 32. Built in two code commits, verified by flake8, an import
smoke-check, and live runs.*

---

## Summary

The last of the `trade run` option surface, closed out in three moves:

- **`--checklist`** *(added)* — an interactive walk through one planned route, a
  hop at a time, waiting for the commander between hops.
- **X52 Pro MFD support and `--show-jumps`** *(removed)* — the Windows-only
  flight-deck display integration and an inert display flag, both taken out
  rather than carried.
- **`--progress`** *(added)* — an opt-in live search bar for the long-running
  shapes.

After this slice no `trade run` option is gated, and none parses-but-does-nothing.

Commits:

| Commit | What |
|--------|------|
| `016ce206` | Interactive `--checklist`; drop the X52 Pro MFD package and `--show-jumps`. |
| `03797ad6` | `--progress` search bar across every route shape. |

State docs (`SPEC_STATUS.md` / `BASELINE.md` / `INDEX.md`) updated in this slice's
docs commit.

---

## `--checklist`

Steps through a **single** planned route one hop at a time. Each hop is a
self-contained panel — where you are, what to buy before you leave, the jumps to
fly, what to sell when you arrive — printed on its own, with the driver waiting
for `Enter` before revealing the next. `-v` thickens each step with the
supply/demand behind every trade and a dock/refuel/repair reminder.

- A new renderer, `render_checklist.py`, builds the ordered list of step
  renderables (warning → start-positioning → one panel per hop → end-positioning
  → route summary); it borrows the rich renderer's palette and jump-leg helpers
  so the two read alike.
- The print-and-wait loop (`_drive_checklist`) lives in the command layer.
- Rich-only: mutually exclusive with `--raw` at the parser. Mutually exclusive
  with `--routes > 1` (a checklist walks one route) — rejected in
  `validate_run_request`.

---

## X52 Pro MFD and `--show-jumps` removed

The MFD code was the legacy 2014 Saitek X52 Pro multifunction-display
integration: a Windows-only `DirectOutput` path that wrote route steps to the
joystick's small text panel. It is unreachable from the current WSL environment,
of marginal value, and a maintenance weight. We researched what the device can
actually do and decided to drop it rather than keep carrying it.

Removed:

- the `tradedangerous/mfd/` package (the Saitek driver and the MFD scaffolding);
- the `checkMFD()` path and the `mfd` handle in `commandenv.py`;
- the `--x52-pro` option and its `--checklist`-companion gate;
- the stale `tox.ini` per-file flake8 ignore for the deleted driver.

`--show-jumps` went in the same pass. It parsed but toggled nothing — the jump
path already shows in the standard and verbose output — so rather than leave an
inert flag it is removed. Both `--x52-pro` and `--show-jumps` now reject as
unknown options. The GUI is left untouched (a separate, later concern).

---

## `--progress`

Opt-in (`--progress` / `-P`) live feedback during the search, reusing the
`misc.progress` rich facade so it matches the spinners used elsewhere (eddblink,
spansh). The display adapts to the shape:

- **Multi-hop (all four shapes — anchored, single-anchor open, unanchored,
  `--via`).** A `CountingBar` **hop spine**: hop *M of N*, elapsed, and the
  best-so-far profit in the description. Beneath it a **per-node sub-row** counts
  the beam's frontier nodes as each layer expands, so a slow layer shows motion
  instead of a frozen count. The sub-row spawns fresh each hop, fills to the beam
  width, and clears as the spine steps; the final hop shows its own
  ("matching destinations" / "reaching the endpoint").
- **Single-hop.** The candidate scan has no known total, so an `ElapsedBar`
  (spinner + elapsed) instead of *M/N*. The open-ended scan counts candidate
  stations as they stream past; the unanchored search shows a "working" spinner
  around its one blocking galaxy-wide fetch.
- **Positioning.** The empty-jump `--start-jumps` / `--end-jumps` BFS runs after
  the hop spine has cleared, and a wide `--empty-ly` can stall it long enough to
  look like a hang (the failure mode being `^C` on a finished search). It gets
  its own spinner.

Refused with `--raw`: a rich bar has no place in the plain-text path, so the pair
errors at the command layer.

**Architecture.** `plan_route` owns the bar's whole life — it builds the bar
styled for the shape it is about to dispatch, hands it to the engine, and clears
it in a `finally` before any result renders. Engines tick a **passed-in** bar;
when `--progress` is off the bar is disabled and every progress call is a no-op,
so the default path is untouched. Two helpers were added to the progress facade —
`open_subtask` / `close_subtask` — to bracket a hot loop with a sub-task row
without re-indenting the loop body.

---

## Verification

- **Static.** flake8 clean across `run_cmd.py`, `misc/progress.py`, and the six
  planner modules touched (`run_route`, `route_anchored`, `route_common`,
  `route_via`, `route_single_anchor`, `route_unanchored`, `route_onehop`). An
  import smoke-check confirmed the new `..misc.progress` imports resolve with no
  circular dependency.
- **Live runs (Tromador).** `--checklist` walked hop-by-hop with `-v`. `--progress`
  confirmed on the multi-hop shapes (spine + per-node sub-row), the single-hop
  open-ended count-up, and the positioning spinner.

---

## Notes and variances

- **No plan doc.** Designed and tuned conversationally, like Slices 20 / 23 / 28
  / 32.
- **The sketched "fetch/solve" sub-task didn't fit `--progress`.** The candidate
  fetch runs per frontier node *inside* each layer, not as one up-front phase, so
  there is no clean fetch-then-solve to bracket. The per-node sub-row (node *X* of
  the beam width) is the honest intra-layer signal that replaced it.
- **Single-hop is a looser shape.** No known candidate total, so a spinner +
  count-up rather than an *M/N* bar — a deliberate difference from the multi-hop
  spine, not a gap.
- **Best-so-far is optimistic on the open shapes.** During an open-anchor / `--via`
  search the beam ranks on an upper-bound profit, so the mid-search "best" can
  read higher than the final corrected route; the closing tick shows the real
  number. Anchored shows the real figure throughout.
- **GUI untouched.** The `--checklist` removal of the MFD did not touch the GUI
  path; both stay future work.

---

## Housekeeping

- `SPEC_STATUS.md`: `--checklist` → done; `--x52-pro` → removed; `--show-jumps` →
  removed; `--progress` → done; the Checklist-output and Progress-output
  behavioural rows → done; the "parses but does not act yet" section emptied (no
  inert options remain).
- `BASELINE.md`: "Where we are" — the option surface is now complete, nothing
  gated or inert; "What's still owed" — `--checklist` / `--x52-pro` /
  `--show-jumps` / `--progress` removed from the owed and parse-but-inert lists.
- `INDEX.md`: this Slice 33 entry.
