# Slice 7 Plan — Bulk-Sale-Tax Safe Demand Cap

## Purpose

Correct `trade run` profit and cargo planning for commodities affected by Elite Dangerous’ bulk-sale tax.

The slice prevents the planner from recommending quantities of bulk-tax-sensitive commodities that would exceed the known full-price safe threshold.

This is a correctness slice before multi-hop routing. Multi-hop capital propagation should not be built on top of inflated sell-price assumptions.

---

## Decision

Implement a conservative **safe cap**, not a full price-penalty curve.

For affected commodities:

```text
effective_destination_demand = floor(destination_demand * 0.25)
```

The planner then uses `effective_destination_demand` as the destination-side quantity cap for cargo fitting.

The advertised sell price remains unchanged, because quantities above the safe threshold are not planned.

---

## Evidence

The attached research supports:

- no price penalty at or below 25% of destination demand;
- price reduction above 25%;
- linear decline toward a floor by roughly 80%;
- uncertain floor multiplier varying by station/state;
- provenance does not matter: bought Metals/Minerals behave like mined ones once in cargo. :contentReference[oaicite:0]{index=0}

Because the post-25% floor is not documented precisely, Slice 7 deliberately avoids modelling discounted sell prices.

---

## Commodity classification

Affected commodities are determined from the canonical EDCD/FDevIDs `commodity.csv`.

Rule:

```text
bulk-sale-tax-sensitive =
    commodity.category in {"Metals", "Minerals"}
```

This classification is accepted as source-of-truth for the project.

Do not infer affected commodities from EDDN live market rows. EDDN commodity messages carry price, stock, demand, and related market values, but not the canonical category needed for this decision. The listener already derives commodity identity via EDCD/FDevIDs during import dictionary construction. :contentReference[oaicite:1]{index=1}

---

## Implementation scope

### 1. Data availability

Verify that planner-side commodity DTOs or candidate rows have access to commodity category, or to enough item identity to cheaply test category.

If category is not already available in candidate rows, add it at the narrowest appropriate data gateway boundary.

Do not add a broad lookup pass in the cargo optimiser hot path if the category can be joined or carried once during candidate construction.

### 2. Candidate/cargo model

Add a boolean or equivalent property to candidate trades:

```text
bulk_tax_sensitive
```

Naming should avoid “mined” internally, because provenance is irrelevant.

Suggested terms:

```text
bulk_tax_sensitive
bulk_sale_tax_sensitive
uses_bulk_sale_safe_cap
```

### 3. Demand cap application

Apply the safe cap only where the commodity is bulk-tax-sensitive and destination demand is positive.

Planning quantity cap becomes:

```text
if bulk_tax_sensitive:
    effective_demand = floor(demand_units * 0.25)
else:
    effective_demand = demand_units
```

The effective demand must still compose with existing constraints:

```text
quantity <= capacity
quantity <= credits_affordable_units
quantity <= source_supply
quantity <= user --limit
quantity <= effective_destination_demand
```

### 4. Zero-cap handling

If the safe cap is zero, the candidate is not useful at full advertised price and should be removed from profitable cargo consideration.

Example:

```text
demand_units = 3
floor(3 * 0.25) = 0
```

No cargo should be planned for that commodity at that destination under Slice 7 semantics.

### 5. Output

Default output does not need noisy warnings.

Verbose/detail output may show a short note when a planned commodity quantity was capped by the bulk-sale rule, for example:

```text
Bulk-sale safe cap: quantity limited to 25% of destination demand.
```

This is useful, but secondary. Correct cargo selection is the slice’s core deliverable.

### 6. No full discount modelling

Do not implement:

```text
25%..80% discounted sell price interpolation
station-specific floor multiplier
optimistic/pessimistic price bands
```

Those remain explicitly out of scope.

Reason: the floor multiplier is not stable enough to support exact planner profit arithmetic.

---

## Behavioural examples

### Non-sensitive commodity

```text
Commodity: Consumer Technology
Destination demand: 400
Effective demand: 400
```

No change.

### Sensitive commodity

```text
Commodity: Platinum
Category: Metals
Destination demand: 400
Effective demand: 100
```

Planner may recommend at most 100t.

### Low demand sensitive commodity

```text
Commodity: Gold
Category: Metals
Destination demand: 3
Effective demand: 0
```

Planner should not recommend that trade at advertised full price.

### Mixed cargo

If a high-margin sensitive commodity hits its safe cap, the optimiser should still be free to fill remaining capacity with other profitable commodities.

---

## Acceptance criteria

Slice 7 is complete when:

1. Bulk-tax-sensitive commodities are identified from canonical category data.
2. Metals and Minerals use `floor(demand * 0.25)` as their destination-side quantity cap.
3. Other commodity categories retain existing demand-cap behaviour.
4. Cargo fitting remains optimal under the new caps.
5. Profit calculations no longer assume full advertised sell price for unsafe quantities.
6. Existing one-hop route shapes still work.
7. Existing non-sensitive benchmark behaviour is unchanged except where candidate ordering changes due to newly capped sensitive commodities.
8. No full post-threshold price curve is implemented.
9. No new broad diagnostic pass is added.
10. The implementation remains compatible with later multi-hop capital propagation.

---

## Suggested tests

### Unit-level cargo fitting

- Non-sensitive commodity demand cap unchanged.
- Sensitive commodity demand 400 caps to 100.
- Sensitive commodity demand 3 produces zero usable full-price demand.
- Sensitive commodity cap composes correctly with:
  - capacity;
  - credits;
  - source supply;
  - `--limit`.

### Candidate-ranking tests

- A sensitive commodity with huge advertised margin but low demand no longer dominates beyond its safe cap.
- The optimiser fills spare capacity with second-best cargo where available.

### Planner integration tests

- Fixed station-to-station one-hop route with affected commodity.
- Open-ended one-hop route where the prior winner was a Metals/Minerals outlier.
- Unanchored one-hop route sanity check, because this is where extreme commodity margins have previously distorted results.

### Regression tests

- Existing non-Metals/Minerals route remains unchanged.
- Existing failure messages remain unchanged.
- No change to `--age`, `--supply`, `--demand`, `--gain-per-ton`, or `--max-gain-per-ton` semantics except through the new effective demand cap.

---

## Out of scope

- Multi-hop routing.
- `--start-jumps` / `--end-jumps`.
- `--sco`.
- Default `--max-gain-per-ton`.
- Full tax curve modelling.
- Station-specific floor discovery.
- UI-heavy warning system.
- New user option to disable or tune the cap.

---

## Deferred decision

A future slice may add an explicit option if wanted, for example:

```text
--bulk-tax-mode safe|ignore|estimate
```

But Slice 7 should not add that. The current planner should prefer correct conservative full-price recommendations over exposing another tuning knob before the behaviour is fully understood.

---

## Slice 7 headline

Implement canonical Metals/Minerals bulk-sale-tax handling by capping planned sell quantity to 25% of destination demand, avoiding unsupported post-threshold price modelling and protecting future multi-hop capital propagation from inflated profit assumptions.