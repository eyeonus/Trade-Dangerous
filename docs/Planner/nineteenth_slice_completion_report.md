# Slice 19 — Fuzzy name matching + duplicate-system disambiguation — Completion Report

## What was delivered

`trade run` now resolves **partial endpoint names** and genuine **duplicate-system
collisions**, by reusing the existing `TradeORM` place lookup instead of the
planner's old exact-only resolver. The lookup machinery already existed (built for
the main refactor, ticket #224); this slice wired the planner to it and fixed the
defects that wiring exposed.

As built:

- **Partial / fuzzy matching** — exact → prefix → substring, for `--from`,
  `--to`, and `--towards`. `Sol/Abr` → *Sol / Abraham Lincoln*, `Colonia/Jaq` →
  *Colonia / Jaques Station*, `Sol/rah` → *Abraham*, `Sol/Lin` → *Lincoln*. No
  typo tolerance (a fragment must be a real substring of the name).
- **Approximate-match echo** — a one-line `--from Sol/Abr resolved as
  Sol/Abraham Lincoln` for non-exact matches; silent for an exact name, an `@N`
  selection, or a planner-chosen open endpoint.
- **Duplicate-system `@N` disambiguation** — a bare colliding name raises an
  ambiguity error listing each candidate as `Name@N — (x, y, z)`, ordered by
  ascending Galactic X (then Y, Z, id); `Name@N` selects one; an out-of-range
  index reports the valid range and re-lists the candidates. Coordinates are the
  only discriminator a commander can read in-game, so they are the disambiguator.
- **Two defects fixed** in the shared lookup path (now live for `trade run`):
  the duplicate-system formatter (ORM shape, em-dash separator, the stray literal
  `45` gone, the dead `posX`/`dbname`-wrapper path removed), and unescaped user
  input in the partial-match word-boundary regex (now `re.escape`'d, so
  metacharacters match literally and a malformed fragment cannot raise
  `re.error`).

## Architecture — resolve once at dispatch

Mirrors how `--towards` already worked:

- Names resolve **once**, at dispatch (`run_cmd.run`), via the `TradeORM` handle.
  The resolved endpoint DTOs ride on `RunRequest` (`from_endpoint`,
  `to_endpoint`; `--towards` keeps `towards_target`). The planner shapes read that
  canonical state; the `TradeORM` handle never enters the planner.
- `resolver.resolve_endpoint` is the thin adapter: `lookup_place` → planner DTO,
  with an `approximate` flag, and no ORM object crossing the boundary. An unknown
  name becomes a planner `UnknownPlace` (→ clean `CommandLineError`); an ambiguous
  name or a bad `@N` index propagates as the lookup's own message, which the CLI
  prints verbatim.

## The build

| File | Change |
|------|--------|
| `planner/resolver.py` | `resolve_endpoint(tdb, …)` delegates to `lookup_place`, converts to DTOs, sets the `approximate` flag; added `system_for_endpoint` (the `--towards` collapse); removed the old exact-only query helpers. |
| `planner/run_request.py` | `RunRequest` gains `from_endpoint` / `to_endpoint`. |
| `commands/run_cmd.py` | Resolves `--from`/`--to`/`--towards` once at dispatch, echoes approximate matches, stores resolved DTOs on the request. |
| `planner/run_route.py` | Removed the in-planner `--towards` resolution; positioning legs read the resolved endpoints. |
| `planner/route_onehop.py`, `route_anchored.py`, `route_single_anchor.py` | Read the resolved endpoints instead of re-resolving. |
| `tradeexcept.py` | New shared `format_system_candidates` helper; `AmbiguityError.__str__` duplicate-system branch uses it (no more `45` / `posX`). |
| `tradeorm.py` | Invalid-`@N` raise and the bare-collision raise both route through the shared formatter; `_list_search` regex `re.escape`'d. |

The candidate-list rendering lives in **one** helper, called from both the
bare-ambiguity branch and the invalid-`@N` raise site, so the two cannot drift
apart again (the drift is what produced the original `45`/`posX` mismatch).

## Verification

Spot-checks run by Tromador against live data, all passing:

- Partial names resolved with echoes; exact names resolved silently.
- `Sol/Abr → Sol/Abraham Lincoln`, `Colonia/Jaq → Colonia/Jaques Station`;
  `--direct Sol → Colonia` planned a real relocation trade.
- `LOrionis-SOC 13` (a genuine in-game duplicate) raised the `@N` list with
  coordinates; `@999` gave the invalid-index message with the range and
  candidates; `@1` resolved to one specific system and the planner grew a real
  multi-hop route from it — proof the index selected the right place.
- Regex-metacharacter input handled without `re.error`.

## Tests — deferred

The formal `tests/` suite is off-limits during the rewrite (project decision).
The `tradeorm` / `tradeexcept` fixes may turn existing parity tests red where they
pin the old behaviour; left so, to be reconciled in the single later suite pass.
A disposable probe spot-checked the DB-dependent paths and is deleted at slice
close.
