# Trade Dangerous — Internal Function Reference

> **Read this first.** This is an internal reference for developers working *on*
> Trade Dangerous. It is **not a public or stable API**. It describes the code as it
> currently stands. The internals — especially the route planner and the ORM layer —
> were rewritten for v13 and are still moving; signatures and behaviour here can change
> without notice or a deprecation cycle, and nothing in this document is a
> compatibility promise. The supported *external* surfaces are the CLI and the
> published data format, not these functions. Use this as a map for reading and
> changing the code, and check the source before you rely on a detail.

This document covers the **core engine**: the ORM/resolver layer, the route planner,
and the command framework. The periphery (importer plugins, the GUI app, the lower
`db` layer) is documented separately — see *Still to come* at the end.

For the *how and why* behind these surfaces, the narrative docs alongside this one go
deeper and are the better read for understanding design:

- [`RESOLVER_CONTRACT.md`](RESOLVER_CONTRACT.md) — the place-resolution and ambiguity
  contract (the matching algorithm, tiers, `@N`, normalisation).
- [`planner-internals.md`](planner-internals.md) — the planner's engines, the shared
  expansion machinery, the cargo optimiser, and the candidate-fetch strategy.
- [`ORM_Schema_reference.md`](ORM_Schema_reference.md) — the database schema and ORM
  models.
- [`db_engine_reference.md`](db_engine_reference.md) — the engine layer and backend
  handling.

---

## `tradeorm` — the ORM-backed data layer

`tradedangerous/tradeorm.py`. `TradeORM` is the single data handle: it owns the
SQLAlchemy engine and session, and provides all name resolution. Every command and the
planner receive one of these rather than touching the database directly.

### Construction and lifecycle

```python
TradeORM(*, tdenv: TradeEnv | None = None, debug: int | None = None,
         require_db: bool = True)
```
Builds the engine and session against the configured SQLite (or MariaDB) database.
`require_db=True` (the default) makes query commands fail fast on a missing SQLite
file; build/bootstrap commands (e.g. `buildcache`) pass `require_db=False` because they
create the file themselves.

After construction it exposes the live SQLAlchemy `session` and `engine`, plus
`tdenv`, `db_path`, and related paths.

- `commit(self)` — commit the current session.
- `close(self, final: bool = False) -> None` — close the session; `final=True` also
  disposes the engine.
- `tradingStationCount(self) -> int` *(property)* — count of stations carrying market
  data.

### Normalisation

- `TradeORM.normalize_str(s: str) -> str` *(staticmethod)* — the two-stage normaliser
  (case-fold, then strip punctuation and spaces) that produces the form stored in the
  `lookup_name` columns and used for partial matching. This is why `"CD37"` matches
  `"CD-37 15492"`.

### Name resolution

These are the resolver. They raise `LookupError` (no match), `AmbiguityError`
(multiple candidates), `TradeException` (e.g. `@N` out of range), or `TypeError` (wrong
input type). The matching algorithm and tier ordering are specified in
[`RESOLVER_CONTRACT.md`](RESOLVER_CONTRACT.md); this is the callable surface.

- `lookup_system(self, name: str | System | Station) -> System` — exact, then partial,
  with `@N` duplicate-name disambiguation. A `System` passes through; a `Station`
  returns its system.

- `lookup_station(self, name: str | Station | System, system: str | System | None = None) -> Station`
  — a `Station` passes through; a `System` returns its single station or raises
  `SystemNotStationError`. With `system` the search is scoped to that system; without
  it a dual scan (exact station, then exact system) is reconciled per the contract.

- `lookup_place(self, name: str | System | Station) -> System | Station` — the
  user-facing resolver shared by the CLI and the planner. Syntax picks the namespace,
  **with one fall-through**:
  - a **bare name** is tried as a system, then — on no system match — as a global
    station search;
  - **`@name`** is system-only (no station fallback);
  - **`/station`** is a global station search;
  - **`system/station`** is a station within the matched system(s);
  - **`system/`** is the system.

  An unambiguous system match wins before the station fallback; a duplicate-name system
  raises `AmbiguityError` rather than picking silently. `@N` is suppressed in compound
  (slash) syntax.

- `lookup_item(self, name: str | Item) -> Item` — commodity lookup.
- `lookup_category(self, name: str | Category) -> Category` — category lookup; the
  returned object carries its `items` relationship.
- `lookup_ship(self, name: str | Ship) -> Ship` — ship lookup.
- `item_by_id(self, item_id: int) -> Item` — primary-key lookup; `LookupError` on miss.

---

## `planner` — the `trade run` route engine

`tradedangerous/planner/`. A self-contained pipeline with two plain data objects at the
boundary: `CLI parser → RunRequest → plan_route → RunResult → renderer`. Nothing else
crosses in or out. The deep design is in [`planner-internals.md`](planner-internals.md);
this is the surface.

### Request and entry point

- `RunRequest` *(`run_request.py`, frozen dataclass)* — the parsed, normalised inputs of
  one run, independent of any command-layer object. Its fields group into: cargo and
  budget (`capacity_units`, `starting_credits`, `insurance_reserve`,
  `cargo_limit_per_item`, `margin`); endpoints (`from_text`/`to_text` plus the resolved
  `from_endpoint`/`to_endpoint`); shape (`hops`, `loop`, `via`, `towards_text`/
  `towards_target`, `direct`, `start_jumps`/`end_jumps`/`empty_ly_per`, `unique`/
  `loop_interval`); reachability (`max_jumps_per_hop`, `max_ly_per_jump`); trade filters
  (`min_gain_per_ton`, `max_gain_per_ton`, `min_supply`, `min_demand`, `max_price`,
  `no_bulk_cap`); station filters (`pad_size`, the `*_filter` state tuples, `max_ls`,
  `ls_penalty_percent`, `sco`); the resolved `avoid_*`/`via_*` id sets; and output
  (`summary`, `progress`, `detail`, `routes`, `checklist`).

- `run_request_from_cmdenv(cmdenv) -> RunRequest` *(`run_request.py`)* — builds a neutral
  `RunRequest` from the parsed command environment (this is where command-layer state is
  translated into planner state, including resolving `--direct`/`--sco` interactions).

- `plan_route(session: Session, request: RunRequest) -> RunResult` *(`run_route.py`)* —
  **the planner entry point.** Validates the request, dispatches to the engine for the
  route shape, and post-processes (e.g. positioning legs, `--towards` annotation).

- `validate_run_request(request: RunRequest) -> None` *(`validation.py`)* — raises a
  `PlannerFailure` subclass for an invalid or contradictory request; called by
  `plan_route`.

### Result objects

`run_result.py` defines the output DTOs, all frozen dataclasses:

- `RunResult` — the top-level result: the planned routes plus `PlannerDiagnostics` and
  any `PartialRouteWarning`.
- `PlannedRoute` — one route: a sequence of `PlannedHop`.
- `PlannedHop` — one trading hop: the `CargoPlan` to carry and the `JumpPath` to fly.
- `CargoPlan` / `CargoLine` — the hold contents (per-commodity buy/sell quantities and
  prices) and totals.
- `JumpPath` — the system-by-system jump sequence of a hop.
- `ResolvedSystem` / `ResolvedStation` — lightweight resolved-place DTOs used throughout
  (id, name, coordinates / station attributes).
- `TradeCandidate` — a candidate buy→sell trade fed to the cargo optimiser.
- `PlannerDiagnostics`, `ExpansionStats`, `FinalHopStats`, `LayerStats` — search
  diagnostics surfaced under `-ww`.

### Core services

- `plan_jump_path(source, destination, *, max_jumps_per_hop, max_ly_per_jump, session, bubble_cache, avoid_system_ids, exempt_anchor_from_avoid=True) -> JumpPath`
  *(`reachability.py`)* — the reachability primitive: a jump path between two systems
  within the range/jump limits, avoiding the given systems. This is also the public
  surface `nav` is built on. Companions: `reverse_jump_path(path)`,
  `reachable_systems_from(...)`, `is_system_pair_reachable(...)`.

- `optimise_cargo(candidates, *, capacity_units, available_credits, cargo_limit_per_item=0, prune_below_raw=None, ignore_credits=False) -> CargoPlan | None`
  *(`cargo.py`)* — the cargo optimiser: fills the hold for maximum total profit across
  several commodities, bounded by capacity, credits, supply, and demand. Returns `None`
  when the pair cannot beat `prune_below_raw` (the confident-prune path). Diagnostics:
  `reset_cargo_counters()`, `cargo_counters()`, `cargo_pruned()`, `cargo_time_ms()`.

- `score.py` — practical-value scoring: `raw_profit_score(profit)`,
  `ls_penalty_multiplier(distance_ls, penalty_percent)` (the sigmoid arrival-distance
  curve), and `score_with_destination_penalty(...)`.

- `data_gateway.py` — **all read-only planning SQL** (the planner never issues queries
  elsewhere). It is large and mostly internal; the entry points worth knowing are
  `validate_station_filters(...)`, `fetch_eligible_stations_in_system(...)`,
  `fetch_eligible_stations_in_reachable_systems(...)`,
  `fetch_station_pair_candidates(...)`, `fetch_unanchored_trade_candidates(...)`,
  `fetch_stations_by_id(...)`, and the run-scoped `QualificationCache` (qualifies market
  rows once per run into temp tables). See [`planner-internals.md`](planner-internals.md)
  for the fetch strategy.

- The per-shape engines — `route_onehop.py`, `route_anchored.py`,
  `route_single_anchor.py`, `route_unanchored.py`, `route_via.py`, over shared machinery
  in `route_common.py` — are dispatched by `plan_route` and are internal; they are
  covered in the planner-internals doc.

### Failures

`failures.py` defines the planner's exception taxonomy. All derive from
`PlannerFailure` (which carries a structured `as_dict()`), so the command layer can map
them to clean, footer-free messages:

- request problems — `InvalidRunRequest` and its kinds (`UnsupportedRunShape`,
  `MissingRequiredInput`, `ContradictoryOptions`, `InvalidNumericOption`);
- resolution — `UnknownPlace`/`AmbiguousPlace` and their system/station variants;
- data — `StationHasNoMarket`, `StationHasNoUsablePriceData` (`SourceHasNoSellingData`,
  `DestinationHasNoBuyingData`), `MarketTimestampInvalid`;
- no route — `NoReachableRoute` and its specific kinds (`NoTowardsProgress`,
  `NoLoopRoute`, `NoViaRoute`, `NoUniqueRoute`), and `NoProfitableTrades`;
- `PlannerInternalError` for "should not happen".

---

## `commands` — the command framework

`tradedangerous/commands/commandenv.py` holds the execution environment shared by every
CLI command (and reused by the GUI).

### Capability model

- `Needs` *(`Flag`)* — what backend a command requires: `Needs.NOTHING` (no backend) or
  `Needs.RESOLVER` (a `TradeORM` handle). Each command module sets a module-level
  `needs`; the CLI builds exactly that backend.

### `CommandEnv`

`class CommandEnv(TradeEnv)` — the parsed environment for one command invocation.

```python
CommandEnv(properties: dict | Namespace | None,
           argv: list[str] | None,
           cmdModule: ModuleType | None)
```

- `preflight(self) -> None` — early, backend-free validation of arguments.
- `run(self, tdb: TradeORM) -> CommandResults | bool | None` — run the command with the
  constructed backend; dispatches into the command module's own `run`.
- `checkFromToNearORM(self) -> None` — resolve `--from` / `--to` / `--near` through the
  ORM before the command runs (resolver-tier commands).
- `checkAvoidsORM(self) -> None` — resolve `--avoid` tokens to system/station/commodity
  ids.
- `checkViasORM(self) -> None` — resolve `--via` waypoints to places.
- `checkPadSize`, `checkPlanetary`, `checkFleet`, `checkSettlement` — validate the
  station-attribute filter arguments.

### Helpers and result containers

- `echo_resolution(label, raw, place)` — prints the `<arg> <input> resolved as
  <canonical>` line when a fuzzy or abbreviated token expanded to a different canonical
  name (silent on an exact or `@N` match).
- `CommandResults` / `ResultRow` — the result row container a command fills and the CLI
  renders.
- `update_database_schema(tdb: TradeORM) -> None` — schema-update helper.

### The command-module contract

Each command lives in `tradedangerous/commands/<name>_cmd.py` and is auto-registered by
its `_cmd` suffix. A module declares its `name`, `help`, argument/switch lists (argparse
definitions), and `needs`, and provides the callables the framework invokes to do the
work and render output. For the exact shape, read `TEMPLATE.py` or a small live command
such as `local_cmd.py` — that is the canonical example, and more reliable than a fixed
signature quoted here while the framework is still settling.

---

## `plugins` — data importers

`tradedangerous/plugins/`. Importers are plugin classes loaded by name. The contract
lives in `plugins/__init__.py`:

- `PluginBase` — base for all plugins. `__init__(self, tdb: TradeORM, tdenv: TradeEnv)`,
  `usage(self)`, `getOption(self, key) -> Any` (reads a value from the plugin's declared
  `pluginOptions`), `run(self) -> bool`, `finish(self) -> bool`.
- `ImportPluginBase(PluginBase)` — base for import plugins; the `run()` / `finish()`
  two-phase lifecycle is where importers do their work.
- `load(pluginName, typeName)` — resolve a plugin class (e.g.
  `load(cmdenv.plug, "ImportPlugin")`).
- `PluginException(Exception)` — plugin error type.

**Lifecycle.** `import` loads the plugin's `ImportPlugin` class, instantiates it with
`(tdb, tdenv)`, then calls `run()` and `finish()` in turn. Each plugin declares a
`pluginOptions` dict of the `--option` values it accepts.

The live importers, each a `class ImportPlugin(ImportPluginBase)` in its module:

- `spansh_plug` — seeds or rebuilds from a full Spansh galaxy dump: streams the gzipped
  dump, writes each station's market and shipyard as a whole snapshot, and writes rarity
  onto `Item.rare_station_id`.
- `eddblink_plug` — imports the published community feed (the listener server's CSVs);
  `downloadFile(...)` fetches, and listings are written with the same whole-snapshot
  station rule.
- `journal_plug` — imports the commander's ship and cargo facts from the game journal.
- `edmc_batch_plug` — batch import of EDMC data.

---

## `guiapp` — the graphical application

`tradedangerous/guiapp/`. A NiceGUI app that drives the *same* commands as the CLI —
each action runs through the shared `CommandIndex().parse → cmdenv.run(...)` path — with
each command run as its own short-lived process for isolation and instant cancel.

### Entry and backend

- `main(argv: Sequence[str] | None = None) -> int` *(`main.py`)* — the application entry
  (`tradegui.py` → `guiapp.main.main`). Starts the NiceGUI server, the native
  (pywebview) window with its close handling, and the server that opens detached
  checklist windows.
- `build_backend(cmdenv) -> TradeORM | None` *(`td_backend.py`)* — the shared backend
  builder: constructs a `TradeORM` for a command exactly as the CLI does
  (capability-aware), or returns `None` for a no-backend command.

### Command execution (`td_exec.py`)

- `GuiCommandRequest` *(dataclass)* — one GUI command request: the command plus its
  context and field values. `effective_context()`, `resolved_values()`.
- `GuiCommandResult` — the execution result container.
- `TdCommandProcess` — wraps one command run as a subprocess: `launch(request)`
  *(classmethod)*, `start()`, `pid()`, `is_active()`, `poll_result() -> GuiCommandResult | None`,
  `terminate(message)`, `close()`.
- `TdExecutor` — the executor the views call. `execute(request) -> GuiCommandResult`
  builds the argv (via the per-command builders below) and runs it through the shared
  `_execute_td_command(request, argv)`.

### Argv builders (`td_exec_commands.py`)

`build_run_argv`, `build_buy_argv`, `build_sell_argv`, `build_trade_argv`,
`build_market_argv`, `build_local_argv`, `build_nav_argv`, `build_olddata_argv`, each
with a matching `validate_*_request`. They translate GUI state into the exact CLI argv
the executor runs — this is what keeps the GUI emitting only options the commands accept.

### Import (`td_exec_import.py`, `import_runtime.py`)

- `build_import_argv(...)` and `execute_import_command(...)` *(`td_exec_import.py`)*,
  with `ImportExecutionPayload` and `ImportLogConsole`.
- `ImportMonitor` / `ImportMonitorProtocol` / `ImportProgressState`
  *(`import_runtime.py`)* — the progress channel for imports (the one command path that
  streams live progress).

### Autocomplete (`gui_search.py`)

- `GuiSearchService` — the long-lived autocomplete engine (one engine for the process
  lifetime, a fresh session per query): `suggest_systems`, `resolve_system`,
  `suggest_items`, `suggest_buy_search`, `suggest_run_avoid`, `suggest_stations`.
  `Suggestion` is the result dataclass.

### Run checklist (`run_checklist.py`, `checklist_store.py`, `native_bridge.py`)

- `RunChecklist` / `ChecklistView` — the hop-by-hop route-checklist UI;
  `checklist_page(token)` renders a detached window's page.
- `store_checklist(routes) -> token` / `get_checklist(token)` *(`checklist_store.py`)* —
  hand a route set to a detached window by token.
- `set_checklist_window_channel(queue, url_base)` / `request_checklist_window(path, title='Run Checklist')`
  *(`native_bridge.py`)* — open a detached native checklist window.

### Session state and persistence (`session.py`, `profiles.py`)

- `SessionState` — the live working state of a GUI session (current command, global
  state, ship profile), with `ExecutionState`, `WorkingGlobalState`,
  `WorkingShipProfileState`, and the `ExecutionStatus` enum.
- `GuiStore` — the persisted settings store, holding `GlobalSettings`, `ShipProfile`,
  and `CommandDraft` (each with `from_dict`/`to_dict`); `get_profile` / `require_profile`
  look profiles up.

### Journal facts (`journal_import.py`)

- `read_journal_facts(journal_dir) -> JournalFacts` — read the commander's ship and
  cargo details from the game journal directory (feeds the journal-driven ship import).

### Views

The per-command workspaces and shared UI are NiceGUI wiring built on the services above,
and are documented at the module level rather than function-by-function: `run_view`,
`buy_sell_view`, `nav_view`, `command_views`, `import_view`, `results_view`,
`settings_view`, `shared_filter_view`, `shared_draft_helpers`, the `autocomplete` widget,
and the `shell`. Read the relevant module when working on a workspace.

---

## `db` — engine and lifecycle

`tradedangerous/db/` is the SQLAlchemy plumbing under `TradeORM`. The ORM models live in
`orm_models.py` and are documented in
[`ORM_Schema_reference.md`](ORM_Schema_reference.md); the engine layer is covered in
[`db_engine_reference.md`](db_engine_reference.md). The callable surface:

### `engine.py`

- `make_engine_from_config(cfg_or_path=None) -> Engine` — build the engine from config
  (SQLite or MariaDB), applying `NullPool` and the SQLite pragmas, with credentials
  redacted in logs.
- `get_session_factory(engine) -> sessionmaker[Session]` — the session factory.

### `lifecycle.py` — create, reset, verify

- `is_sqlite(engine) -> bool`, `is_empty(engine) -> bool` — backend / state checks.
- `reset_db(engine, *, db_path, sql_path=None) -> str` — the backend-agnostic clean
  rebuild (dispatches to `reset_sqlite` / `reset_mariadb`); this is the supported
  rebuild path.
- `ensure_fresh_db(...)` — the freshness gate: verify the database and rebuild it if it
  is missing, empty, or stale.
- `verify_db(engine, data_dir, tdenv) -> dict[str, str]` — integrity, core-table, and
  seed-count checks.

### Other `db` modules

`config.py` (config loading), `import_csv.py` (CSV import into the schema),
`station_types.py` (the canonical station-type registry), `paths.py` (database-path
resolution), `locks.py` (locking), and `utils.py`.
