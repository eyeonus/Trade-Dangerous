# Trade Run First Safe Slice — Completion Report

## Status

First safe slice implementation is operational and validated.

The new planner boundary is live:

```text
CLI parser
  -> RunRequest
  -> planner
  -> RunResult
  -> renderer
```

The implementation is functioning independently of the quarantined route-planning internals.

---

# Implemented

## Planner Package

Implemented modules:

```text
tradedangerous/planner/__init__.py
tradedangerous/planner/failures.py
tradedangerous/planner/run_request.py
tradedangerous/planner/run_result.py
tradedangerous/planner/validation.py
tradedangerous/planner/cargo.py
tradedangerous/planner/score.py
tradedangerous/planner/reachability.py
tradedangerous/planner/resolver.py
tradedangerous/planner/data_gateway.py
tradedangerous/planner/run_onehop.py
tradedangerous/planner/render_text.py
```

---

## Command Integration

Integrated into:

```text
tradedangerous/commands/run_cmd.py
tradedangerous/commands/commandenv.py
tradedangerous/tradeorm.py
```

Implemented behaviour:

- `trade run` uses resolver backend only
- `trade run --old` routes to comparison path
- rendering dispatches by actual result type
- resolver prechecks bypassed for planner path
- planner uses existing resolver session
- no duplicate engine/session construction

---

## Supported Command Shape

Validated working shape:

```text
trade run
  --from station
  --to station
  --capacity N
  --credits N
  --hops 1
  --jumps-per N
  --ly-per N
```

---

# Verified Behaviour

## Route Planning

Validated:

- same-system runs
- one-jump cross-system runs
- direct reachability enforcement
- unreachable-route rejection

Example validated route:

```text
Lave/Lave Station -> Diso/Bao Station
```

Produced identical cargo/profit result to comparison path.

---

## Cargo Optimisation

Validated:

- affordability constraint
- capacity constraint
- mixed commodity cargo
- quantity accounting
- exact profit arithmetic
- final credits arithmetic

Observed behaviour:

- optimiser correctly skipped unaffordable high-profit cargo
- selected affordable alternatives automatically

---

## Validation / Error Handling

Validated:

- unsupported `--hops 2`
- unsupported first-slice switches
- system-only destination rejection
- unreachable jump rejection
- no traceback on expected failures

---

## Performance Outcome

Confirmed:

- new planner path avoids comparison-path preload costs
- significant startup/runtime reduction observed
- benchmark routes return near-instantly

Important architectural conclusion preserved:

```text
Performance improvement comes primarily from:
- selecting Needs.RESOLVER
- avoiding comparison-path object construction/loading
```

Not from lazy imports.

---

# Parser / Filter Corrections Completed

## Black Market Filter

Corrected from boolean switch semantics to Y/N/? state filtering.

Now supports:

```text
--black-market Y
--black-market N
--black-market ?
--black-market Y?
```

State filters now consistently behave as accepted-state sets.

---

## Fleet Carrier / Settlement

Implemented via derived `type_id` state mapping.

No ORM schema expansion required.

---

# Quarantine Status

Still respected.

The following modules were NOT used as implementation sources:

```text
tradedangerous/tradecalc.py
tradedangerous/tradedb.py
```

`--old` exists strictly as comparison/runtime validation path.

---

# Outstanding / Deferred

## Not Yet Implemented

Not part of this slice:

- multi-hop routing
- graph search
- `--via`
- `--avoid`
- loops
- route pruning
- route ranking expansion
- system-only endpoint inference
- fuzzy route-shape expansion
- checklist/x52 output
- advanced geometry controls

---

## Known Polish Items

Deferred intentionally:

- generic NoDataError advisory text still appears for some planner failures
- renderer formatting is functional but not final-form polished
- diagnostics naming/history may still contain minor inconsistencies
- no formal benchmark harness yet
- no automated test suite yet

---

# Validation Completed

Successfully validated:

- comparison path still operational
- planner path operational
- compile/syntax pass
- planner/render integration
- resolver integration
- ORM query path
- affordability logic
- capacity logic
- route reachability
- planner failure mapping

---

# Release Assessment

Current slice is suitable for:

```text
small-project release candidate
```

with expectation of:

```text
ticket-driven iterative refinement
```

rather than large pre-release hardening.

Core architecture and execution path are now proven.