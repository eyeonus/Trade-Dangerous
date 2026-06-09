# Slice 20 — Single Validator: retire the legacy command-layer checker

A small slice, planned in session rather than in a separate plan doc.

## What and why

`trade run` was validating arguments in two places:

- `validateRunArgumentsFast(cmdenv)` in `commands/run_cmd.py` — the legacy
  command-layer checker. Read the raw command environment, raised
  `CommandLineError`.
- `validate_run_request(request)` in `planner/validation.py` — the clean-room
  checker. Reads the neutral `RunRequest`, raises typed planner failures.

While `trade run --old` existed, both earned their keep. With the legacy path
retired, the two were redundant — and had drifted apart, so they could disagree.
This slice removes the legacy checker and leaves `validate_run_request` as the
single validator.

## What changed

**Three live rules moved across first.** The legacy checker held three
argument-pair rules the planner checker was missing. They went into
`validation.py` before anything was deleted, so nothing was lost:

- `--towards` requires `--from`
- `--start-jumps` requires `--from`
- `--end-jumps` requires `--to`

`--towards` with `--to` was *not* among them — that pair is rejected at the
argument parser (a mutually-exclusive group), so the planner checker does not
repeat it.

**Legacy checker removed.** `validateRunArgumentsFast` and its `# Helpers`
banner were deleted from `run_cmd.py`. The generic hook in `commandenv.py`
stays; for `run` it now finds no such function and does nothing, and it still
serves `nav` and `olddata`, which keep their own.

**Nothing lost on the overlap.** Everything else the legacy checker did was
already covered by `validate_run_request`: required options, limit-vs-capacity,
the gated-option rejections, the `--direct` rules, `--prune-hops` / `--routes` /
`--margin`. The one apparent disagreement — the `--insurance` rule, legacy
`credits + 42` buffer versus the planner's `>= credits` — was already a
non-event: both checkers ran, the stricter planner rule always won, so removing
the legacy copy changed no behaviour.

## Call sites

`validate_run_request` keeps both its call sites — once early in
`run_cmd.run()` (so a bad request fails before the slow galaxy-search
confirmation prompt) and once at the planner entry (`run_route.py`, its own
input contract). Same function both times, so there is no second interpretation
to drift.

## Verification

Spot-checked on live data (handed to Tromador, not run automatically):

- `--towards Sol` with no `--from` → `--towards requires --from.`
- `--start-jumps 2` with no `--from` → `--start-jumps requires --from.`
- `--end-jumps 2` with no `--to` → `--end-jumps requires --to.`
- `--from Sol --towards Colonia` → plans normally, no false rejection.

flake8 clean on both touched files (`planner/validation.py`,
`commands/run_cmd.py`).

## Deferred (unchanged)

The cross-checks for still-gated options (`--shorten` needs `--to`, `--loop`
with `--unique`, the `--loop-interval` minimum, `--x52-pro` needs `--checklist`)
were not carried over. Those options are themselves rejected as unsupported, so
the pair-checks could never fire. Each returns alongside its option when that
option is built.

The formal test suite stays off-limits during the rewrite, by standing
decision.
