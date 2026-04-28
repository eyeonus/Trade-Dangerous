# RESOLVER CONTRACT

Purpose: define the lookup and ambiguity behavior that must be preserved or deliberately changed during ORM-first migration.

All facts in this document are derived by reading the current implementation in `tradedangerous/tradedb.py` and `tradedangerous/tradeexcept.py`. Nothing here is inferred or assumed.

---

## 1. Data structures required

All lookup functions operate on in-memory dicts populated by `TradeDB.load()`. An ORM-first resolver must either replicate these or replace them with direct DB queries.

| Structure | Type | Populated by | Content |
|-----------|------|-------------|---------|
| `tdb.systemByID` | `dict[int, System]` | `_loadSystems()` | system_id → System wrapper |
| `tdb.systemByName` | `dict[str, list[System]]` | `_loadSystems()` | UPPERCASE_NAME → list of System, sorted by (posX, posY, posZ, ID) |
| `tdb.stationByID` | `dict[int, Station]` | `_loadStations()` | station_id → Station wrapper |
| `system.stations` | `list[Station]` | Station constructor | Stations belonging to a System, in insertion order |
| `tdb.itemByID` | `dict[int, Item]` | `_loadItems()` | item_id → Item |
| `tdb.itemByName` | `dict[str, Item]` | `_loadItems()` | name → Item (exact case-sensitive key) |

The `systemByName` dict can hold multiple System objects per key — systems with identical names are stored together.

---

## 2. Normalization pipeline

Used throughout lookups. Two translation tables applied in sequence:

**Stage 1 — normalizeTrans**
- Uppercases `a-z` → `A-Z`
- Deletes the characters: `[ ] ( ) * + - . , { } :`

**Stage 2 — trimTrans**
- Deletes: space (` `) and apostrophe (`'`)

`normalizedStr(s)` applies both stages. The two stages are distinct and not interchangeable — many match comparisons use stage 1 only (the normalized form), and apply stage 2 only for the fallback trim comparison.

---

## 3. Input syntax and parsing

### Accepted syntax forms (for `lookupPlace`)

| Form | Example | Meaning |
|------|---------|---------|
| bare name | `Sol` | Try as system first; fall back to station |
| `@system` | `@Sol` | Explicitly a system name (annotation only; `@` is stripped before lookup) |
| `/station` | `/Abraham Lincoln` | Explicitly a station name; system is not searched |
| `system/station` | `Sol/Abraham Lincoln` | Both parts are partial-matchable; system narrows station search |
| `@system/station` | `@Sol/Abraham Lincoln` | Same as `system/station`; `@` annotation is stripped |
| backslash variant | `Sol\Abraham Lincoln` | Legacy; treated identically to forward slash |
| `system@N` | `Lorionis-SOC 13@2` | Disambiguate duplicate-name system by 1-based position index |

### `@N` disambiguation suffix

Handled by `_split_system_index(name)` via `name.rfind('@')`:
- If `@` is found at position > 0 and the substring after it is all digits: `(base_name, index)` where index is 1-based.
- Leading `@` (at position 0) is left intact — it is the explicit-system annotation, not a disambiguation index.
- A non-numeric suffix (e.g. `Name@Dock`) is returned as-is with `index=None`.
- The `@N` suffix only works in `lookupSystem` and `lookupPlace`'s fast path. It is not available in the slow path or in `lookupStation`.

---

## 4. `listSearch` — the partial-match engine

Used as the fallback in `lookupSystem` and as the primary engine in `lookupStation` and `lookupItem`.

```
listSearch(listType, lookup, values, key=identity, val=identity)
```

**Algorithm:**

1. Normalize the needle: `lookup.translate(normalizeTrans).translate(trimTrans)` (both stages).
2. Build a word-boundary regex: `re.compile(f"\\b{lookup}\\b", re.IGNORECASE)` using the **original** `lookup` (not normalized). Note: `re.match` is used, which anchors to the start of the string.
3. Iterate all candidates. For each, normalize the key (both stages).
4. Match checks in order:
   - **Exact** (`normVal == needle` and `len(normVal) == len(needle)`): return immediately — no ambiguity check. This means an exact-normalized-length match always wins regardless of other candidates.
   - **Word match**: `wordRe.match(entryKey)` where `entryKey` is the **un-normalized** key. Because `re.match` anchors to position 0, this is "key starts with `lookup` at a word boundary". Accumulates to `wordMatch` list.
   - **Partial match**: needle found as a substring of normalized candidate. Accumulates to `partialMatch` list.
5. Resolution:
   - `wordMatch` takes priority over `partialMatch`.
   - If the winning list has exactly 1 entry: return it.
   - If the winning list has > 1 entry: raise `AmbiguityError`.
   - If no matches at all: raise `LookupError`.

**Important**: The word-boundary regex uses the original `lookup` as a regex pattern. If `lookup` contains regex metacharacters, legacy behaviour follows Python regex semantics because the lookup string is not escaped. Do not escape it unless deliberately changing behaviour and updating tests.

---

## 5. `lookupSystem(name)`

### Input handling

| Input type | Result |
|------------|--------|
| `System` instance | Returned directly (pass-through) |
| `Station` instance | Returns `station.system` |
| Non-str, non-System, non-Station | Raises `TypeError` |
| `str` | Proceeds to string lookup |

### String lookup (two-tier)

**Pre-processing**: `_split_system_index(name)` extracts any `@N` suffix, giving `(base_name, index)`.

**Tier 1 — exact dict lookup (fast path):**
- Key = `base_name.upper()`
- Looks up `systemByName[key]`

If found:
- No `@N` index, single result → return it
- No `@N` index, multiple results → raise `AmbiguityError` with `(1, system), (2, system), ...` pairs
- `@N` index in range → return `systems_list[index - 1]`
- `@N` index out of range → raise `TradeException` with full list of valid forms

**Tier 2 — `listSearch` fallback (slow path, triggered by `KeyError` in Tier 1):**
- Calls `TradeDB.listSearch("System", name, self.systems(), key=lambda s: s.dbname)`
- Uses the **full original `name`** including any `@N` suffix (not stripped — `listSearch` does not understand `@N`)
- This means `@N` disambiguation is unavailable in the fallback path
- Result: the `listSearch` algorithm as described in section 4

### Not-found errors from Tier 2

`listSearch` raises `LookupError` if nothing matched. `lookupSystem` does not catch this; it propagates to the caller.

---

## 6. `lookupPlace(name)`

The primary user-facing lookup. Resolves a string to either a `System` or `Station`.

### Input handling

| Input type | Result |
|------------|--------|
| `System` or `Station` instance | Returned directly |
| Non-str | Raises `TypeError` |

### Fast path (bare name — no `/`, no `\`, not starting with `/`)

1. Strip leading `@` if present: `sys_key = name[1:] if name.startswith("@") else name`
2. Call `lookupSystem(sys_key)`
   - If it returns: pass it through.
   - If it raises `LookupError`: fall through to the slow path (the `@` annotation is discarded at this point).
   - If it raises `AmbiguityError` or `TradeException`: these propagate immediately — they are **not** caught by `lookupPlace`.
3. This fast path means: for a bare name (or `@name`), a system match always wins over any potential station match. If the system lookup is unambiguous, the station path is never consulted.

### Slow path — combined system/station resolution

Entered when:
- The name contains `/` or `\` (compound form), OR
- The name starts with `/` (explicit station), OR
- The fast path fell through via `LookupError`.

**Step 1 — syntax parse:**

```
slash_pos = first '/' or '\' in name (-1 if absent)
name_off  = 1 if name starts with '@', else 0
```

| Condition | sys_name | stn_name |
|-----------|----------|----------|
| `slash_pos > name_off` | `name[name_off:slash_pos].upper()` | `name[slash_pos+1:]` |
| `slash_pos == name_off` (i.e. leading `/`) | `None` | `name[name_off+1:]` |
| `name_off > 0` and no slash | `name[1:].upper()` | `None` |
| no slash, no `@` (fast-path fallback) | `name.upper()` | `name` |

**Step 2 — system resolution (if `sys_name` is set):**

- Tries `systemByName.get(sys_name)` — exact uppercase dict key, same key as Tier 1 of `lookupSystem`.
  - If found: adds all results directly to `exact_match`. Handles legacy single-System and list-of-System values.
- If not found: calls `_lookup(sys_name, systemByID.values())`.

Note: `@N` disambiguation is NOT available in the slow path. The system name is used as-is (already uppercased).

**Step 3 — station resolution (if `stn_name` is set):**

- If compound form (`slash_pos > name_off + 1`) AND any system matches exist: restricts candidates to the union of all matched systems' `stations` lists. Then resets all four tier lists.
- Otherwise: uses `stationByID.values()` as candidates.
- Calls `_lookup(stn_name, candidates)`.

**Step 4 — tier resolution:**

```python
for tier in (exact_match, close_match, word_match, any_match):
    if len(tier) == 1:
        return tier[0]
```

- Checks each tier in priority order. Returns immediately if a tier has **exactly** 1 entry.
- A tier with 0 entries is skipped; a tier with 2+ entries is also skipped — the next tier may still yield a unique match.
- If no tier yields a unique match:
  - All tiers empty → `LookupError("Unrecognized place: {name}")`
  - Any tier non-empty → `AmbiguityError` with all candidates combined (`exact + close + word + any`)

### `_lookup` — four-tier matching

Used internally in the slow path. Operates on `place.dbname` for all candidates.

```
token_norm = token.translate(normalizeTrans)          # stage 1 only
token_trim = token_norm.translate(trimTrans)           # stage 1 + 2
```

For each candidate `place`:

```
place_norm = place.dbname.translate(normalizeTrans)   # stage 1 only
```

Guard: if `len(token_trim) > len(place_norm)`, skip.

| Tier | Condition | Outcome |
|------|-----------|---------|
| **exact** | `len(place.dbname) == len(token)` AND `place_norm == token_norm` | `exact_match` |
| **close** | `len(place_norm) == len(token_norm)` AND `place_norm == token_norm` | `close_match` |
| **substring** (word/any) | `len(token_norm) < len(place_norm)` | see below |
| **trim** (close/any) | fallback when token and place are same normalized length after trimming | see below |

Substring tier (only when `token_norm` is shorter than `place_norm`):
- `pos = place_norm.find(token_norm)`
- `pos == 0` and next char is space → `word_match`
- `pos == 0` and next char is not space → `any_match`
- `pos > 0`, prev char is space AND next char is space → `word_match`
- `pos > 0`, otherwise → `any_match`

Word boundary detection uses **space characters in the stage-1-normalized string** (not a regex). Apostrophes and other trimmed characters that were removed by stage 1 do not appear here.

Trim tier (reached only if none of the above conditions fired):
- `place_trim = place_norm.translate(trimTrans)`
- If `len(place_trim) == len(place_norm)`: stage 2 changed nothing → skip (no new information).
- If `len(place_trim) == len(token_trim)` and `place_trim == token_trim` → `close_match`
- If `token_trim` found in `place_trim` → `any_match`

---

## 7. `lookupStation(name, system=None)`

### Input handling

| Input type | Result |
|------------|--------|
| `Station` instance | Returned directly |
| `System` instance with 1 station | Returns that station |
| `System` instance with ≠ 1 station | Raises `SystemNotStationError` |

### With `system` argument

1. Resolve `system` via `lookupSystem(system)`.
2. Call `listSearch("Station", name, system.stations, key=lambda s: s.dbname)`.
3. Returns a station or raises `LookupError` / `AmbiguityError`.

### Without `system` argument (dual scan)

1. `listSearch` across all systems (by `system.dbname`). Captures result as `system` or `None` on `LookupError`.
2. `listSearch` across all stations (by `station.dbname`). Captures result as `station` or `None` on `LookupError`.
3. If neither matched: `LookupError("'{name}' did not match any station or system.")`
4. If both matched AND `system != station.system`: `AmbiguityError` (different system/station pair).
5. If both matched AND `system == station.system`: station takes priority (the Aulin/Aulin Enterprise case).
6. If only `station` matched: return it.
7. If only `system` matched:
   - 1 station in system → return it.
   - Other → `SystemNotStationError`.

---

## 8. `lookupItem(name)`

Delegates directly to `listSearch`:

```python
TradeDB.listSearch("Item", name, self.itemByName.items(),
    key=lambda kvTup: kvTup[0],
    val=lambda kvTup: kvTup[1])
```

`itemByName` keys are the raw item name strings (exact case as stored in DB). The `listSearch` normalization handles case-insensitive and partial matching.

---

## 9. Error types and semantics

| Exception | Class | Meaning |
|-----------|-------|---------|
| `LookupError` | Python built-in | Nothing matched the input |
| `AmbiguityError` | `TradeException` | Multiple candidates; user must be more specific |
| `SystemNotStationError` | `TradeException` | System matched but has multiple stations; user must name the station |
| `TradeException` | Base | Used for `@N` out-of-range in `lookupSystem` |
| `TypeError` | Python built-in | Wrong type passed to a lookup function |

`AmbiguityError` serializes to a human-readable message listing candidates (up to `AMBIGUITY_LIMIT`). For system-name collisions (where `anyMatch` contains `(int, System)` pairs), it renders the `@N` disambiguation form with coordinates.

Callers in `commandenv.py` catch `LookupError` and convert it to `CommandLineError`. `AmbiguityError` and `TradeException` propagate to the top-level handler for display.

---

## 10. Behavioral notes and edge cases

### Fast path always prefers system over station

`lookupPlace("Aulin")` returns the Aulin System, not Aulin Enterprise station. The fast path calls `lookupSystem` and returns on any successful match — the station path is never consulted. Use `lookupStation("Aulin")` or `lookupPlace("/Aulin Enterprise")` to reach the station.

### Exact match in `listSearch` bypasses ambiguity

If the exact normalized form of a candidate matches the needle and their lengths are equal, `listSearch` returns it immediately without checking other candidates. This means an exact match always wins, even if multiple partial matches also exist.

### Bare name fallback searches both systems and stations

When `lookupSystem` raises `LookupError` for a bare name, the slow path of `lookupPlace` searches both `systemByID.values()` and `stationByID.values()` with the same name, and accumulates results in shared tier lists. A unique match in any tier wins regardless of whether it is a System or Station.

### `@` annotation vs `@N` disambiguation

These are distinct mechanisms:
- `@Sol` as input to `lookupPlace`: the `@` is an annotation meaning "this is a system name, not a station". It is stripped before calling `lookupSystem("Sol")`.
- `Lorionis-SOC 13@2` as input to `lookupSystem`: the `@2` is a disambiguation index into the list of systems with that name.

They do not interact. `@Sol@1` passed to `lookupPlace` strips the leading `@`, calls `lookupSystem("Sol@1")`, and then `lookupSystem` interprets `@1` as a duplicate-system index for base name `"Sol"`.

### `@N` disambiguation order

Duplicate-name systems are ordered by `(posX, posY, posZ, ID)` — lowest X coordinate first. This ordering is established when `systemByName` is built in `_loadSystems()` and when `addLocalSystem()` inserts a new system.

### Slow path `_lookup` word boundaries are space-based

Unlike `listSearch` which uses a regex `\b` word boundary, `_lookup` uses literal space characters in the stage-1-normalized string. Removing punctuation (`[]()*+-.,{}:`) happens before this check, but spaces are preserved through stage 1. This means `\bfoo\b` and space-delimited "foo" are not equivalent in the two implementations.

### `lookupStation` dual scan is O(n) × 2

`lookupStation` without a `system` arg runs two full `listSearch` passes over all systems then all stations. No DB indexes are used. This is the most expensive of the lookup paths.

---

## 11. Behaviour classification

Each notable quirk is classified so future sessions can distinguish what must be preserved from what is a bug candidate.

- **PRESERVE FOR PARITY** — must match legacy behaviour exactly in the ORM-first resolver; any change requires an explicit decision and test update.
- **DOCUMENTED LEGACY BUG** — known defect; should not be intentionally replicated, but do not silently fix without a decision and a test update.
- **CANDIDATE FOR DELIBERATE CHANGE** — behaviour that could reasonably change; must not change silently; requires decision + test update.
- **DELIBERATE ORM CHANGE** — the ORM-first resolver intentionally diverges from legacy here; decision recorded, tests updated.

| Behaviour | Classification |
|-----------|---------------|
| `lookupPlace` bare name prefers system over station | PRESERVE FOR PARITY |
| Exact normalized match in `listSearch` bypasses all ambiguity checking | PRESERVE FOR PARITY for `lookupSystem`; see DELIBERATE ORM CHANGE entry below for `lookup_station` |
| `@N` disambiguation only works in `lookupSystem` / `lookupPlace` fast path | PRESERVE FOR PARITY unless explicitly extended |
| `@` annotation is a `lookupPlace` concept, not a `lookupSystem` concept | PRESERVE FOR PARITY |
| Duplicate-name system ordering by (posX, posY, posZ, ID) | PRESERVE FOR PARITY |
| `_lookup` word boundaries are space-based; `listSearch` uses regex `\b` — two different implementations | PRESERVE FOR PARITY (both); they are not interchangeable |
| `listSearch` word-boundary regex uses unescaped `lookup` — regex metacharacters in the lookup string follow Python regex semantics | DOCUMENTED LEGACY BUG |
| `lookupStation` dual scan is O(n) × 2 with no DB index | DELIBERATE ORM CHANGE — `lookup_station` uses two indexed exact queries instead |
| `lookupSystem` `listSearch` fallback passes the full `name` including `@N` suffix — `@N` silently stops working for partial matches | DOCUMENTED LEGACY BUG |
| `lookupPlace` slow path system resolution does not support `@N` | PRESERVE FOR PARITY (limitation is consistent with the fast path owning `@N`) |
| `listSearch` short-circuits on the first exact station-name match — no ambiguity check even when duplicate rows exist | DELIBERATE ORM CHANGE — `TradeORM.lookup_station` raises `AmbiguityError` for multiple exact DB rows; returning an arbitrary duplicate is less correct than asking the caller to disambiguate |

---

## 12. What requires full `TradeDB.load()`

Every lookup function listed above operates on in-memory dicts. These dicts are populated by `_loadSystems()`, `_loadStations()`, `_loadCategories()`, `_loadItems()` — all called from `TradeDB.load()`.

An ORM-first resolver for Checkpoint F must provide the same behavior via direct DB queries without requiring the full in-memory load. The minimum required for system and station resolution:

| Capability needed | DB equivalent |
|-------------------|---------------|
| Exact system name lookup | `SELECT ... FROM System WHERE UPPER(name) = :key` using `idx_system_by_name` |
| All systems with a given name (for @N) | Same query with `ORDER BY pos_x, pos_y, pos_z, system_id` |
| System prefix/partial match | `SELECT ... FROM System WHERE UPPER(name) LIKE :prefix` or full table scan |
| Station lookup within system | `SELECT ... FROM Station WHERE system_id = :id AND ...` using `idx_station_by_system_name` |
| Station global lookup | `SELECT ... FROM Station WHERE UPPER(name) LIKE :prefix` or scan |

**Caveat**: Direct DB queries may retrieve candidate supersets, but final matching and ambiguity resolution must run through a Python implementation of the legacy matcher unless and until normalised or generated columns are added and tested for parity. A simple `UPPER(name) LIKE ...` query is not equivalent to the legacy tier logic (stage-1 punctuation deletion, stage-2 space/apostrophe deletion, exact-length priority, word-boundary detection, ambiguity tier ordering).

---

## 13. Parity test matrix

These cases must become tests for the ORM-first resolver, verifying matching behavior against the legacy implementation.

### System lookup

| Test case | Input form | Expected result |
|-----------|------------|-----------------|
| Exact match (case-insensitive) | `"sol"` → `lookupSystem` | Returns Sol system |
| Exact match (mixed case) | `"i BootiS"` → `lookupSystem` | Returns i Bootis |
| Partial match | `"ibootis"` → `lookupSystem` | Returns i Bootis (listSearch fallback, trim match) |
| Pass-through System | `System(...)` → `lookupSystem` | Returns same object |
| Pass-through Station | `Station(...)` → `lookupSystem` | Returns station.system |
| Not found | `"xxxxxxxx"` → `lookupSystem` | Raises `LookupError` |
| Ambiguous bare name | duplicate-name system → `lookupSystem` | Raises `AmbiguityError` |
| `@N` exact | `"SomeName@1"` → `lookupSystem` | Returns first system in duplicate group |
| `@N` out of range | `"SomeName@99"` → `lookupSystem` | Raises `TradeException` |
| Leading `@` not annotation in `lookupSystem` | `"@Sol"` → `lookupSystem` | Raises `LookupError` (not found as `@SOL`) |

### Place lookup — fast path

| Test case | Input form | Expected result |
|-----------|------------|-----------------|
| Bare system name | `"Sol"` → `lookupPlace` | Returns Sol System |
| `@system` annotation | `"@Sol"` → `lookupPlace` | Returns Sol System |
| Ambiguous via fast path | duplicate-name system name → `lookupPlace` | Raises `AmbiguityError` (from `lookupSystem`) |
| Name misses system, falls to station | unique station name → `lookupPlace` | Returns Station |
| Name misses system, misses station | garbage → `lookupPlace` | Raises `LookupError` |

### Place lookup — slow path / compound forms

| Test case | Input form | Expected result |
|-----------|------------|-----------------|
| Explicit station | `"/Abraham Lincoln"` → `lookupPlace` | Returns Abraham Lincoln station |
| Compound exact | `"Sol/Abraham Lincoln"` → `lookupPlace` | Returns station in Sol |
| Compound partial both parts | `"so/haml"` → `lookupPlace` | Returns station via partial match on both |
| Compound partial station only | `"sol/abrahamlincoln"` → `lookupPlace` | Returns Abraham Lincoln (trim match) |
| `@system/station` form | `"@Sol/Abraham Lincoln"` → `lookupPlace` | Returns Abraham Lincoln in Sol |
| Backslash separator | `"Sol\Abraham Lincoln"` → `lookupPlace` | Returns Abraham Lincoln in Sol |
| Ambiguous station in compound | `"Sol/a"` → `lookupPlace` | Raises `AmbiguityError` if multiple match |
| Unknown system, existing unique station | `"xxxxxxxx/Abraham Lincoln"` → `lookupPlace` | Returns the station via global fallback — station search is unrestricted when system part matches nothing |
| Not found (compound, nonexistent station) | `"Sol/xyzzy"` → `lookupPlace` | Raises `LookupError` — station not found within scoped system |

### Station lookup

| Test case | Input form | Expected result |
|-----------|------------|-----------------|
| Exact station name | `"Abraham Lincoln"` → `lookupStation` | Returns station |
| Pass-through Station | `Station(...)` → `lookupStation` | Returns same object |
| System passed, 1 station | `System(1-station)` → `lookupStation` | Returns that station |
| System passed, >1 stations | `System(multi)` → `lookupStation` | Raises `SystemNotStationError` |
| With system arg | `"Abraham Lincoln", sol` → `lookupStation` | Returns station scoped to Sol |
| Dual scan reconciles | `"Aulin"` → `lookupStation` | Returns Aulin Enterprise (station.system == matched system) |
| Not found | `"xxxxxxxx"` → `lookupStation` | Raises `LookupError` |
| Exact duplicate station name (ORM) | two stations with identical names → `lookup_station` | Raises `AmbiguityError` — deliberate ORM divergence from legacy `listSearch` short-circuit |

### Normalization edge cases

| Test case | Input | Expected normalized form |
|-----------|-------|--------------------------|
| Punctuation stripped | `"Foo[1]"` → normalize | `"FOO"` |
| Apostrophe stripped | `"O'Brien"` → normalize | `"OBRIEN"` |
| Space stripped (trim) | `"Foo Bar"` → trim | `"FOOBAR"` |
| Case fold | `"shinRARTA"` → normalize | `"SHINRARTA"` |

### Negative tests — `@N` not supported outside fast path

These lock down that `@N` disambiguation is NOT silently "improved" into paths that do not currently support it. An ORM-first resolver must not accidentally extend `@N` support without an explicit decision.

| Test case | Input form | Expected result |
|-----------|------------|-----------------|
| `@N` in slow path compound form | `"DuplicateName@1/Station"` → `lookupPlace` | Does NOT apply `@1` as system index; treats `DuplicateName@1` as a literal system name string |
| `@N` in `lookupStation` | `"DuplicateName@1"` → `lookupStation` | Does NOT apply `@1` as disambiguation; passes string as-is to `listSearch` |
| `@N` on partial match fallback | `"PartialDupName@1"` → `lookupSystem` where `PartialDupName@1` misses the exact dict | `listSearch` fallback does not strip `@1`; treats it as part of the search string |

---

## 14. Test fixture requirements

Parity tests require specific data shapes in order to exercise the awkward resolver paths. Fixtures must include:

- At least one **duplicate-name system group** with at least two members having deterministic coordinate ordering (to test `@N` index, `AmbiguityError`, and ordering stability).
- At least one **system with exactly one station** (to test the "system implies station" path in `lookupStation`).
- At least one **system with multiple stations** (to test `SystemNotStationError`).
- At least one **station whose name partially matches its parent system name** — to test `lookupStation` dual scan reconciliation (the Aulin/Aulin Enterprise pattern).
- At least one **compound system/station case** where both parts are partial matches only (no exact).
- Names containing **punctuation** (`[1]`, `+`, `.`), **apostrophes** (`O'Brien`), and **spaces** — to exercise both normalization stages.
- At least one **ambiguous station within a scoped system** — compound form with multiple partial station matches inside the same system.
