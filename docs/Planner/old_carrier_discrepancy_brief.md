# Brief: why does `--old` not surface the B0V-84N carrier trade?

## Background
Trade-Dangerous' `trade run` route planner is being rewritten. The legacy
planner is still reachable as `trade run --old` and is used as a comparison
baseline for the new one. A validation run has turned up a discrepancy between
the two that cannot be explained from the new-planner side, because explaining
it requires reading the legacy modules. You are **not** under the new planner's
clean-room source quarantine — reading the legacy code is the whole point of
this task.

## The discrepancy
Two commands, same database, **no `--age` supplied on either**:

```
trade run --from "Lave" --capacity 64 --credits 1000000 --hops 1 --ly-per 20
```

- **New planner:** `Lave/B0V-84N -> Ritila/Kennedy Dock`, total gain 435,096 cr.
- **`--old`:** `Lave/Lave Station -> Placet/Fletcher Base`, total gain 184,064 cr.

Also note: `--old --from "Lave"` returns the *identical* result to
`--old --from "Lave/Lave Station"` (Lave Station -> Placet, 184,064 cr). That
equality is itself a clue.

## Established facts (DB-verified — do not re-derive)
- `B0V-84N` is a **fleet carrier** (`Station.type_id = 5`) in Lave. Its station
  row and all eight of its market rows were last modified **2026-03-26**; today
  is 2026-05-17, so the data is ~52 days stale, and every market row has
  `from_live = 0`.
- `Ritila/Kennedy Dock` is a normal station, data from **2026-05-15**,
  `from_live = 1`, with large genuine demand.
- The new planner expands `--from <system>` to **every eligible station in the
  system** (Lave has 28 stations, ~24 of them fleet carriers); fleet-carrier
  filtering is opt-in, so carriers are included; it applies **no default age
  cutoff**. That is how it reaches the stale B0V-84N rows. The new-planner side
  is fully understood and **out of scope** for you.

## The question
With no `--age`, both planners read the same database. **Why does
`--old --from "Lave"` return Lave Station -> Placet and never consider the
B0V-84N carrier trade?**

## Hypotheses to test (not exhaustive, none assumed correct)
1. `--old` does not expand a `--from <system>` argument to all stations — it
   selects one (the equality with `--from "Lave/Lave Station"` hints at this).
2. `--old` excludes fleet carriers from origin selection by default.
3. `--old` applies an implicit freshness/age filter even without `--age`.
4. `--old` filters on `from_live` or data provenance.
5. `--old`'s in-memory galaxy preload drops carriers or stale rows at load time.
6. `--old` does see B0V-84N's market but the trade loses for some other reason
   (profit calc, carrier supply not treated as buyable, etc.).

## Specifically confirm or refute
The maintainer's recollection is that **`--old` only age-gates market data when
`--age` is explicitly supplied**. Verify that against the code and state it
plainly either way.

## What you may read
Everything. Explicitly including `tradedangerous/tradecalc.py`,
`tradedangerous/tradedb.py`, `tradedangerous/commands/run_cmd.py`, and the whole
legacy `trade run` path. No quarantine applies to you.

## Constraints
- **Read-only diagnosis. Change no code.**
- Scope is the legacy `--old` path only.
- You may run `trade run --old ...` with verbosity/detail flags to see what it
  considered, and query `data/TradeDangerous.db` directly.

## Environment
Repo root `D:\Fork\Trade-Dangerous`, non-packaged mode, shared venv at
`D:\Fork\.venv` (`D:/Fork/.venv/Scripts/python.exe`), database
`data\TradeDangerous.db`. Date 2026-05-17.

## Deliverable
A short findings report: the precise mechanism by which `--old` excludes or
fails to surface the B0V-84N trade, with `file:line` citations, plus a clear
yes/no on the age-gating recollection. State whether `--old` skips this trade
*deliberately* (a policy worth matching in the new planner) or *incidentally*
(so `--old` is not a reliable model here).
