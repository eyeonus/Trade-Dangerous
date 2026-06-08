# Slice 19 — Fuzzy name matching + duplicate-system disambiguation

## Status

Planned. Supersedes the working draft `slice19_research_for_review.md`, which
captured the research and was run past a second pair of eyes; this is the
corrected, agreed plan that incorporates the review.

`trade run` resolves **exact** names only. Partial names every commander expects
(e.g. `Sol/Abr` → *Sol / Abraham Lincoln*) fail. The fix is **not** to build a new
matcher — the fuzzy + `@N` machinery already exists in `TradeORM` and is used by
other commands. The planner just isn't wired to it, and the duplicate-system
output formatter it would expose is broken. This slice wires the planner to the
existing resolver, adds an approximate-match echo, and fixes the formatter and a
regex-safety bug it surfaces.

## What `--from Sol/Abr` does today

`Sol` resolves (exact); the station half `Abr` is matched by case-insensitive
**equality** against `Abraham Lincoln`, fails, and raises `UnknownStation`
(`planner/resolver.py:263`). Every name path in the planner's resolver is
exact-equality.

## Why it isn't already using the fuzzy resolver (root cause)

A deliberate bypass, not an accident:

- `run_cmd.py:35` sets `skipResolverPrechecks = True`, so `commandenv.py:132`
  never runs `checkFromToNearORM()` — the command layer does no place resolution
  for `run`.
- The planner receives the **raw text** (`run_request.py:89-90`, from
  `cmdenv.starting`/`cmdenv.ending`) and resolves it itself in the clean-room
  `planner/resolver.py` — which is exact-only.

The bypass exists for a real reason: the planner wants its own DTOs and failure
types, not ORM objects crossing its boundary. The catch is the planner's resolver
was built exact-first, with fuzzy left as future work, even though
`TradeORM.lookup_place` already existed (`tradeorm.py`, commit `6bea2e4d`,
2025-12-11). The planner resolver landed later (commit `13b288fe`, 2026-05-12).

The bypass **stays**. We don't re-route `run` through `commandenv`; we give the
planner's own resolution path the existing fuzzy backend.

## The existing machinery we reuse

`tradedangerous/tradeorm.py` (the new ORM layer — not quarantined):

- `lookup_system` (`:461`) — exact → prefix ILIKE → interior substring ILIKE;
  full `@N` disambiguation; candidates ordered `pos_x, pos_y, pos_z, system_id`.
- `lookup_station` (`:306`), `lookup_place` (`:532`) — every compound form
  (`@system`, `/station`, `system/station`, backslash) with the same fallback.
- Helpers: `_prefix_of`, `_list_search`, `_place_lookup`, `_resolve_place_tiers`,
  `_split_system_index`.

These already settle the matching model (exact/scoped before broad approximate,
per spec §279), and the disambiguation rules below.

## Duplicate-system disambiguation — the rules to preserve (from #224)

Genuine in-game duplicate system names exist (two distinct systems both named
*LOrionis-SOC 13*). The DB separates them by FDev id (unique), but **players
cannot see FDev ids** — only coordinates. So:

- Duplicate system names are **valid data**, not corruption; FDev ids stay
  unique; a collision must never silently discard a system.
- A bare duplicate name (no `@N`) **raises ambiguity**, listing each candidate as
  `Name@N — (x, y, z)`, ordered by ascending X (Y, Z, id tie-break) — deterministic.
- `Name@N` selects the Nth candidate.
- Two stations with the **same name in the same system** is the deferred edge
  (megaships / non-unique carrier ids): they share the system's coordinates, so
  `@N` cannot separate them. We inherit #224's behaviour — list them, never
  silent-pick. Not solved here.
- Ordinary abbreviation / partial matching still applies wherever no exact
  duplicate collision is in play.
- `@N` works on a bare system name only; it is suppressed in compound (slash)
  syntax (parity).

## Architecture — resolve once at dispatch (Option B)

Per the review, and mirroring how `--towards` already works
(`run_route.py:49-50`):

- Do **not** push the `tdb` / `TradeORM` object deep into the planner.
- `run_cmd.run()` already holds `tdb`. Resolve `--from` / `--to` / `--towards`
  **once at dispatch**, via `TradeORM.lookup_place`, into canonical resolved
  endpoint DTOs, and store them on `RunRequest`.
- The planner stays mostly pure: it receives a `session` plus a request carrying
  already-resolved endpoints, and reads that resolved state.
- No repeated endpoint resolution in: the one-hop planner, anchored multi-hop,
  single-anchor multi-hop, `--towards`, or the positioning legs.

The ORM `System`/`Station` returned by `lookup_place` is converted to the
existing `ResolvedSystem`/`ResolvedStation` DTOs inside the resolver, so no ORM
object reaches the request or the planner — the clean-room boundary holds.

## Approximate-match echo

Wanted — and not merely UX: it is test/debug observability. When testing fuzzy
matching the commander must see what the input expanded to.

- Emit a one-line confirmation when an endpoint resolved by **non-exact**
  (approximate) matching:

  ```text
  --from Sol/Abr resolved as Sol/Abraham Lincoln
  --to Colonia/Jaq resolved as Colonia/Jaques Station
  --towards Shinr resolved as Shinrarta Dezhra
  ```

- Do **not** emit for: exact matches; ambiguity failures (the error is the
  feedback); planner-chosen open / unanchored endpoints (those are route output,
  not resolver expansion).
- Scope: `--from`, `--to`, `--towards`. `--via` / `--avoid` only if those paths
  are touched later — not widened into here.

Approximate detection (no change to `lookup_place` needed): compare the supplied
name parts (after stripping any `@N`) to the resolved object's canonical
`name`/`system.name`, case-insensitively. Any difference → approximate → echo. A
pure case difference (`sol` → `Sol`) or an `@N` selection does not echo. Output
goes through the command layer's existing channel at dispatch.

## The three concrete bugs (in the existing resolver path)

### Bug 1 — user lookup text interpolated raw into a regex

`tradeorm.py` `_list_search` builds a word-boundary regex from raw user text:
`word_re = re.compile(f"\\b{lookup}\\b", re.IGNORECASE)` (`:174`). Regex
metacharacters in input or names alter match semantics; a malformed fragment can
raise `re.error`. **Fix:** `re.escape` the user input before embedding, preserving
the word-boundary intent. The "DOCUMENTED LEGACY BUG / parity" note is **not** a
reason to keep it — treated as a bug to fix, absent a concrete compatibility need.

### Bug 2 — stray literal `45` in the duplicate-system formatter

`tradeexcept.py` `AmbiguityError.__str__` emits `... @{index} 45 (x, y, z)` — the
`45` is accidental garbage. **Fix:** remove it; restore the separator. Use the em
dash (`—`), consistent with #224's shipped output and the renderer's existing text
(`render_text.py` uses `—`):

```text
LOrionis-SOC 13@1 — (378.8, -309.7, -1408.4)
```

### Bug 3 — formatter assumes retired `TradeDB.System` wrapper shape

The same branch reads `system.posX/posY/posZ` and treats `dbname` as a string
attribute. The ORM `System` has `pos_x/pos_y/pos_z` and a `dbname()` **method**
that uppercases and appends `/` (`orm_models.py:130-141`). So today the `try`
block throws `AttributeError` and silently falls to the `key()` fallback, masking
the `45` and printing the diverged `NAME/@1 (x, y, z)`. **Fix:** update the
duplicate-system special-case to ORM shape — coordinates from `pos_x/pos_y/pos_z`;
display name from `.name` (original case; **not** `dbname()`, which uppercases and
trailing-slashes). Make it object-shape-neutral / ORM-correct; do not depend on
`posX` or on `dbname` being a string.

We are not passing wrong names to the ORM — we are passing ORM objects to a
formatter that still assumes the retired wrapper. Since `TradeDB` is gone from
this path, the formatter is updated to ORM shape.

## Invalid `@N` handling

When the index is out of range (e.g. `LOrionis-SOC 13@999`), the error must state
the index is invalid, give the valid range, and list the candidates with `@N` and
coordinates — no stray `45`:

```text
System "LOrionis-SOC 13" has 2 matching entries (@1..@2).
"LOrionis-SOC 13@999" is not a valid index.

Use one of the available forms:

    LOrionis-SOC 13@1 — (378.8, -309.7, -1408.4)
    LOrionis-SOC 13@2 — (396.4, -324.0, -1473.6)
```

**Two raise sites, not one.** The out-of-range `@N` path does **not** go through
`AmbiguityError`. `lookup_system` raises a plain `TradeException` with its own
inline message (`tradeorm.py:515-518`): `System {name}@{index} does not exist
(valid range: 1-N)` — no candidate list, no coordinates. So fixing
`AmbiguityError.__str__` alone covers bare ambiguity but **not** invalid `@N`. The
invalid-index message must be fixed at its own raise site too. To stop the two
drifting apart again, the candidate-list-with-coordinates rendering goes into a
**single shared helper** that both the bare-ambiguity branch and the
invalid-index raise site call — one place that owns the `Name@N — (x, y, z)`
formatting.

## Tests — deferred (decision recorded)

The formal `tests/` suite is **not touched** in this slice. We are on a
breaking-change branch with the planner still in flux; piecemeal test edits are
wasted effort, so the suite gets one proper pass once the planner settles, not
slice-by-slice.

Consequence, accepted: the `tradeorm.py` / `tradeexcept.py` fixes (Bugs 1–3,
invalid `@N`) may turn existing tests in `test_resolver_parity.py` /
`test_tradeorm_lookup_db.py` red where they pin the old behaviour. Left failing on
purpose — the suite is not being run at the moment and is reconciled in the later
pass.

Permitted instead, at the worker's discretion: a couple of **disposable temp test
scripts** to spot-verify this specific behaviour (fuzzy resolution; the `@N`
collision and invalid-`@N` output; the ORM formatter shape; regex-metacharacter
input; the approximate-match echo). Kept on disk for the slice, **never** added to
`tests/`, deleted when the slice closes — the existing probe convention.

## Validation posture

No automated harness in this slice (above). Validation is spot-check plus flake8
on touched regions, plus the optional temp scripts. All run commands are handed to
Tromador; the worker does not run them automatically.

## Steps

One logical step at a time, review between each.

1. **Resolver → fuzzy backend.** Rework `planner/resolver.py` `resolve_endpoint`
   to take the `TradeORM` handle, call `lookup_place`, and convert the returned
   ORM `System`/`Station` to `ResolvedSystem`/`ResolvedStation` DTOs. Add the
   exact-vs-approximate signal (name-compare) for the echo.
2. **Resolve once at dispatch.** In `run_cmd.run()`, resolve `--from`/`--to`/
   `--towards` via the reworked resolver, store the resolved endpoints on
   `RunRequest` (new `from_endpoint`/`to_endpoint`; `--towards` keeps
   `towards_target`), and emit the approximate-match echo. Remove
   `_resolve_towards_target` from `plan_route`; make the shape planners and the
   positioning legs read the resolved endpoints instead of re-resolving.
3. **Collision formatting — both sites.** Put the `Name@N — (x, y, z)`
   candidate-list rendering in one shared helper (ORM shape, em dash, no `45`).
   Call it from (a) `tradeexcept.py` `AmbiguityError.__str__`'s duplicate-name
   branch (Bugs 2 and 3), and (b) the invalid-`@N` raise site in
   `tradeorm.py` `lookup_system` (`:515-518`), so the out-of-range message also
   carries the range and the candidate list. Confirm `lookup_system` raises the
   tuple form the formatter expects for the bare-ambiguity case.
4. **Regex safety.** `re.escape` the user input in `tradeorm.py` `_list_search`
   (Bug 1).
5. **End-to-end + echo channel.** Confirm `trade run` resolves partial names,
   prints the echo, and renders `@N` collisions correctly; settle the echo output
   channel against the surrounding code.
6. **Docs** (after code accepted): `SPEC_STATUS.md` (name resolution: partial
   matching + `@N` active for `trade run`), `BASELINE.md`, `INDEX.md`, completion
   report — recording the deferred-tests decision.

## Out of scope

- The formal test suite (deferred — see above).
- `--via` / `--avoid` echo (only if those paths are touched later).
- A second, planner-specific fuzzy resolver (explicitly avoided — reuse `TradeORM`).
- Re-routing `run` through `commandenv` / removing `skipResolverPrechecks`.
- The same-name-same-system station collision (inherited #224 deferral).
- Any quarantined module; any search-engine logic; the `--ls-penalty` curve.

## Acceptance — spot-checks, handed to Tromador

```text
--from Sol/Abr --to Colonia/Jaq --direct ...      -> resolves; echoes both expansions
--from Sol/Abraham Lincoln ...                    -> resolves; no echo (exact)
--towards Shinr ...                               -> resolves target; echoes expansion
--from "LOrionis-SOC 13" ...                      -> @N ambiguity list w/ coords, em dash, no 45
--from "LOrionis-SOC 13@1" ...                    -> selects first by ascending X; no echo
--from "LOrionis-SOC 13@999" ...                  -> invalid-index error, valid range, candidates
--from <name with regex metachars> ...           -> treated literally, no re.error
default exact run                                 -> unchanged
```
