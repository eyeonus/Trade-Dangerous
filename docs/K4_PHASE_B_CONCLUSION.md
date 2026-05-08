# K4 Phase B — Raw Edge Parity Conclusion

## Status

Complete. Raw one-hop candidate edge semantics confirmed against two fixtures.

---

## Parity fixtures

### Achenar / Dawes Hub (station_id 3222038272)

Quiet station: 1 supply row at source.

```
source supply rows       : 1
joined same-item demand  : 79,624
legacy raw edges         : 29,628
provider PRICE_AND_UNITS : 29,628   ← exact match
provider PRICE_ONLY      : 29,630   (superset by 2)
```

### Shinrarta Dezhra / Jameson Memorial (station_id 128666762)

Busy station: many supply rows, large candidate set.

```
legacy raw edges         : 1,702,258
provider PRICE_AND_UNITS : 1,702,258   ← exact match
provider PRICE_ONLY      : 1,710,804   (superset by 8,546)
```

---

## Confirmed canonical rule

Raw candidate edge eligibility at the `stationsSelling / stationsBuying / getTrades` seam:

```
source supply_price > 0
source supply_units > 0
destination demand_price > 0
destination demand_units > 0
destination demand_price - source supply_price >= min_gain_per_ton
```

Default `min_gain_per_ton`: 1 (from `max(1, tdenv.minGainPerTon or 1)`).

Provider canonical mode: **PRICE_AND_UNITS**.

---

## What is confirmed

**Semantic match**: `get_raw_profitable_edges(..., edge_mode=PRICE_AND_UNITS)` produces
the same raw candidate edge set as the legacy `stationsSelling / stationsBuying / getTrades`
seam, at both tested fixtures, before `simpleFit()`, scoring, pruning, or rendering.

This holds across a quiet station (1 supply row, 29K edges) and a busy station (1.7M edges).

---

## What is not yet measured

**Runtime viability**: whether the SQL provider can replace the legacy path at
acceptable runtime cost for a real route run.

The parity script asked Python to fetch every raw edge, construct dataclass
objects for each, normalise into comparison tuples, and compare sets. That is a
deliberately heavy verification workload, not a production route pattern.

The Jameson parity run (~36s) represents:

- execute provider query
- fetch 1,702,258 rows across DB/Python boundary
- construct `RawCandidateEdge` dataclasses for each
- normalise into 10-field comparison tuples
- build Python sets
- compare against the legacy-replicated set

It does not represent the cost of the SQL edge query alone, nor the cost of a real
route run using a frontier-driven consumption model.

The current live baseline is loading up to ~9M rows into Python structures before
route expansion begins. The parity timing is not directly comparable to that baseline
without a benchmark that isolates candidate generation from route expansion.

The right signal from the parity timing is: **naive full materialisation of every raw
edge as Python dataclass objects is a design smell for large stations**. It is not a
verdict on the SQL provider architecture.

---

## PRICE_ONLY mode

`PRICE_ONLY` is always a superset of legacy:

```
PRICE_ONLY − legacy = N > 0 in both fixtures
legacy − PRICE_ONLY = 0 in both fixtures
```

The extra edges in `PRICE_ONLY` are DB rows where `supply_units = 0` or
`demand_units = 0` but a non-zero price is recorded. Legacy zeroes those
prices via the `CASE WHEN units >= 1 THEN price ELSE 0 END` expression
before they can form an edge.

`PRICE_ONLY` is retained as a diagnostic and deliberately overinclusive mode.
It is not legacy-compatible and should not be used as the canonical route
candidate mode.

---

## Remaining timestamp / age parity

`source_modified` and `destination_modified` were excluded from the comparison.

At the legacy seam, raw timestamps are converted to ages in seconds
(`nowS - int(mod_dt.timestamp())`) via `parse_ts()`. The `Trade` object
stores `srcAge` and `dstAge`, not raw timestamps.

Age parity — including whether age filtering affects edge eligibility before or
after edge discovery — is a deferred parity task, not a blocker for the
architecture decision.

---

## Geometry

Geometry (jump range, stellar coordinates) is not part of raw edge eligibility.
At the inspected raw edge seam, geometry is not part of edge eligibility.

Geometry is applied later, during `getBestHops()` destination reachability
checks. It is not a primary optimisation path for edge generation.

---

## What comes next

The parity question is answered. The next design question is:

> How should the route engine consume SQL-generated candidate edges
> without materialising millions of low-value candidates into Python?

The runtime provider may need to consume SQL results differently from the
parity script:

- stream rows rather than materialising a full list
- per-source grouped iteration across the frontier
- SQL-side coarse ordering by `gain_per_ton`
- bounded candidate windows per source / item / destination
- feeding `simpleFit` directly from ordered candidates

The benchmark that matters next is not "how fast is the SQL query?" but
"how does a realistic frontier-driven consumption pattern compare against
the current preload-first baseline?"

That is a design and benchmarking question, not a further parity question.

---

## Artefacts

```
k4_proto/provider.py           — SQL provider (PRICE_ONLY and PRICE_AND_UNITS modes)
k4_proto/selfcheck.py          — Phase A self-check (provider diagnostics, no legacy)
k4_proto/parity.py             — Phase B comparison (legacy seam replication vs provider)
docs/K4_PHASE_B_CONCLUSION.md  — this document
```
