# CHANGELOG


## v12.14.2 (2026-03-20)

### Bug Fixes

- Spansh_plug.py Regressions - download and stdin pathways
  ([`71050ae`](https://github.com/eyeonus/Trade-Dangerous/commit/71050aed83338561d2494f2590fc33f2e93e56dc))

No idea how long these have been broken. Listener uses file injection with -O=/the/spansh/file.json
  which has been just fine. Now we can download or if necessary direct inject.


## v12.14.1 (2026-03-20)

### Bug Fixes

- Rare items cost now populates properly
  ([`e156308`](https://github.com/eyeonus/Trade-Dangerous/commit/e156308a82e926c96f45439206bfab0eeac1908b))

We still use EDCD to verify our rares list, but now also populate the cost field from market data,
  as we always should have. This will propagate via eddblink to ensure `trade rares` will not show
  zero cost for all items


## v12.14.0 (2026-03-20)

### Bug Fixes

- Cli.py - repair CPROF profiling hook in main()
  ([`97e74c7`](https://github.com/eyeonus/Trade-Dangerous/commit/97e74c79121b1f70623cac59a1bd7e85344f6542))

### Chores

- **deps**: Bump nicegui from 3.8.0 to 3.9.0
  ([#293](https://github.com/eyeonus/Trade-Dangerous/pull/293),
  [`06d75aa`](https://github.com/eyeonus/Trade-Dangerous/commit/06d75aaf1951100ff687c6f8d4b850f28b4710e1))

Bumps [nicegui](https://github.com/zauberzeug/nicegui) from 3.8.0 to 3.9.0. - [Release
  notes](https://github.com/zauberzeug/nicegui/releases) -
  [Changelog](https://github.com/zauberzeug/nicegui/blob/main/release.dockerfile) -
  [Commits](https://github.com/zauberzeug/nicegui/compare/v3.8.0...v3.9.0)

--- updated-dependencies: - dependency-name: nicegui dependency-version: 3.9.0

dependency-type: direct:production ...

Signed-off-by: dependabot[bot] <support@github.com>

Co-authored-by: dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>

### Documentation

- Update copyright years in README.md
  ([`397a084`](https://github.com/eyeonus/Trade-Dangerous/commit/397a08402e8d2d4e39566de085ed43915c1f6861))

Belated update for 2026

### Features

- Local now honours --age
  ([`a30ef0d`](https://github.com/eyeonus/Trade-Dangerous/commit/a30ef0d3901a31119e9d61ff03f3bf7737b89b09))

With carriers and planetary and Odyssey, the output from local can get huge when using any detailed
  output.

This gives a useful lever to limit that output to only list more recently updated stations, rather
  than pages of data.


## v12.13.7 (2026-03-19)

### Bug Fixes

- Market_cmd.py average prices
  ([`4d5bdf2`](https://github.com/eyeonus/Trade-Dangerous/commit/4d5bdf22be110fe7824d9cf700dc27f06365b1fd))

Market was massively over querying and taking minutes to return results.

We now only compute averages when we need to (--detail) and only for those items actually in the
  market.

Down to ~30s for results. Big improvement.


## v12.13.6 (2026-03-18)

### Bug Fixes

- Fix TradeORM data_dir initialisation in __init__
  ([`c5a31d6`](https://github.com/eyeonus/Trade-Dangerous/commit/c5a31d6287a545e7e4bf229f14e283741d620430))

### Chores

- Fix new bug causing attempted double uploads
  ([`a17f1f3`](https://github.com/eyeonus/Trade-Dangerous/commit/a17f1f33b216eab91373ab7f9d129137206166d4))


## v12.13.5 (2026-03-18)

### Bug Fixes

- Use local data_dir when deriving TradeORM fallback db path
  ([`1ac2066`](https://github.com/eyeonus/Trade-Dangerous/commit/1ac2066a44c0cf953ae9dca3b0a3d9e774e27b91))

Correct the TradeORM constructor fallback path logic to use the already-available local data_dir
  value instead of self.data_dir before that attribute exists.

This fixes the AttributeError introduced while removing the bogus pre-engine SQLite file gate for
  non-SQLite backends.

### Chores

- We don't need attestations. Maybe later.
  ([`c38c482`](https://github.com/eyeonus/Trade-Dangerous/commit/c38c482d198b365cc755b02f8973e247e40c7628))


## v12.13.4 (2026-03-18)

### Bug Fixes

- Added a comment, but need to trigger a release, so fix.
  ([`d17841b`](https://github.com/eyeonus/Trade-Dangerous/commit/d17841b4b5c8dd1fdf46ec89a5987bae5939ccfe))

### Chores

- Fix regression not uploading from auto-trigger
  ([`62d1114`](https://github.com/eyeonus/Trade-Dangerous/commit/62d1114279e22003b3c7a7ecc2097d17ba29d790))


## v12.13.3 (2026-03-18)

### Bug Fixes

- Remove legacy db/cwd CLI overrides and unblock TradeORM on MariaDB
  ([`f565c7c`](https://github.com/eyeonus/Trade-Dangerous/commit/f565c7c868fc373dfffd9f55042170e674e04ecc))

Drop the obsolete shared --db and --cwd command-line switches and remove the residual CommandEnv
  working-directory override path.

Also fix TradeORM initialisation so non-SQLite backends are no longer blocked by a bogus local
  TradeDangerous.db existence check before the real configured backend is resolved.

### Chores

- Fix release workflow and document prerelease path
  ([`365545b`](https://github.com/eyeonus/Trade-Dangerous/commit/365545bda3c981a51c454681fc43d81781807569))

Prevent duplicate PyPI publish attempts when the branch lands on an already-tagged release commit.
  Split stable auto-release on release/v1 from manual RC runs on rc/* branches, and add simple docs
  for both paths.


## v12.13.2 (2026-03-18)

### Bug Fixes

- Trade_cmd.py - Poor quality output and maths error
  ([`862c71b`](https://github.com/eyeonus/Trade-Dangerous/commit/862c71b6e9bc19989f3ea9a4169b1d22ad9821b9))

Outputting minutes with capital M is misleading and suggests months. Changed age to show as min, hr,
  d.

There's 24 hours in a day, not 7. That's weeks.

### Chores

- Archive final legacy gui.py and remove live copy
  ([`bfbe33e`](https://github.com/eyeonus/Trade-Dangerous/commit/bfbe33edd4584aff09b468eb56ac29e1ea96e377))

- Merge both archive folders into one top-level archive
  ([`c706497`](https://github.com/eyeonus/Trade-Dangerous/commit/c706497ce3d40cb2364d390646fca031d6153603))

### Documentation

- Update archive readme
  ([`1985eb6`](https://github.com/eyeonus/Trade-Dangerous/commit/1985eb61bed023a399e7f1ffd9969bf486fabb0f))


## v12.13.1 (2026-03-17)

### Bug Fixes

- Fix non-functioning --away and clean up misleading help
  ([`9890f35`](https://github.com/eyeonus/Trade-Dangerous/commit/9890f35b332db291fa0917ceffc16cd132a4d3b8))

### Documentation

- Added (hopefully) useful comments to GUI code
  ([`cc9ce01`](https://github.com/eyeonus/Trade-Dangerous/commit/cc9ce01df691f7c3e733f2b50f7eaf9e3f8cedbb))


## v12.13.0 (2026-03-16)

### Bug Fixes

- Pyproject.toml bare dotted key should be quoted
  ([`6e1bfec`](https://github.com/eyeonus/Trade-Dangerous/commit/6e1bfec0ea8cb120e841ae52a09c2caaf1c252eb))

### Features

- Gui New functionality
  ([`395a6f9`](https://github.com/eyeonus/Trade-Dangerous/commit/395a6f951bebca26e84f48916d88dea0ba592222))

GUI: Added commands buy & sell Added import functionality (eddblink backend) Added basic settings &
  POC theming.

eddblink: Added code to support GUI import (does not affect CLI function) Removed `bootstrap`
  command completely.


## v12.12.0 (2026-03-14)

### Chores

- **deps**: Bump orjson from 3.11.5 to 3.11.6
  ([#292](https://github.com/eyeonus/Trade-Dangerous/pull/292),
  [`6308f7f`](https://github.com/eyeonus/Trade-Dangerous/commit/6308f7f630a611ebbc8a5d56be9d3f2efa2eaf5b))

Bumps [orjson](https://github.com/ijl/orjson) from 3.11.5 to 3.11.6. - [Release
  notes](https://github.com/ijl/orjson/releases) -
  [Changelog](https://github.com/ijl/orjson/blob/master/CHANGELOG.md) -
  [Commits](https://github.com/ijl/orjson/compare/3.11.5...3.11.6)

--- updated-dependencies: - dependency-name: orjson dependency-version: 3.11.6

dependency-type: direct:production ...

Signed-off-by: dependabot[bot] <support@github.com>

Co-authored-by: dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>

### Features

- Initial GUI Test release
  ([`f3b41d4`](https://github.com/eyeonus/Trade-Dangerous/commit/f3b41d474df2fe23f6ae5230847c1f34e9b17334))

GUI Test release. Based on NiceGUI interface

Ensure your venv is up to date with new modules.

Invoke with `tradegui.py` from command line.

Limited functionality and nowhere near complete design. Any complaints about it "doesn't do that" or
  "looks bad" will be treated with utter contempt. It's not finished!

What is now in place: - launch GUI through the new `tradegui.py` entry path - saves state to
  `tradegui_state.json` in datadir - supports multiple ship profiles - `trade run` implemented -
  other commands NOT implemented - defaults to NiceGUI native mode

Web application mode:

You can mess with the json to make it be a web server app. I'm not telling you how right now, but if
  you're that clever, you can work it out, it's not hard. However if you mess with json and break
  it, you shoulda backed up.

Outside of "I tried to make it be a web server and now it's broken" I am very open to any blatant
  bugs in functionality you manage to surface.


## v12.11.8 (2026-03-14)

### Bug Fixes

- `trade run` pre-validation
  ([`11f9378`](https://github.com/eyeonus/Trade-Dangerous/commit/11f93785b2f1a3c0d4947ebbd9af01c7d0132a0b))

This should now catch ALL missing or bad combinations of arguments before doing any heavy lifting
  and this feed back to user immediately, instead of two minutes later.

### Chores

- Make notebooks python-version limited
  ([`11a546e`](https://github.com/eyeonus/Trade-Dangerous/commit/11a546eeccb7776a99e531399899bc58e3bc0b38))

dependabot has itself in a twist over an optional feature of an optional component of an optional
  group, and the fix for the vulnerability in that component is not currently available as a binary
  wheel for windows 64 bit. next step, if this doesn't appease dependabot, simply remove the
  dependency; it was there as a convenience

- Python dependency prune
  ([`851b0dc`](https://github.com/eyeonus/Trade-Dangerous/commit/851b0dc1009ffeb42c923413900fbdbcb5d3b336))

- removed the notebooks group entirely; uv add jupyter if you need command-line use of
  jupyter/notebooks; - removed sphinx, mistune, and m2r dependencies (we're not using sphinx,
  mistune and m2r were related to it)

- **deps**: Bump cryptography from 46.0.3 to 46.0.5
  ([#289](https://github.com/eyeonus/Trade-Dangerous/pull/289),
  [`bb14de9`](https://github.com/eyeonus/Trade-Dangerous/commit/bb14de912bbbf928fac1d345f36c631e51c8ef14))

Bumps [cryptography](https://github.com/pyca/cryptography) from 46.0.3 to 46.0.5. -
  [Changelog](https://github.com/pyca/cryptography/blob/main/CHANGELOG.rst) -
  [Commits](https://github.com/pyca/cryptography/compare/46.0.3...46.0.5)

--- updated-dependencies: - dependency-name: cryptography dependency-version: 46.0.5

dependency-type: indirect ...

Signed-off-by: dependabot[bot] <support@github.com>

Co-authored-by: dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>

### Refactoring

- Basic functionality
  ([`186c867`](https://github.com/eyeonus/Trade-Dangerous/commit/186c867ec313e9db4aeab6287486a16cb56e4977))

output redirection isn't working so it still goes to the console but all the things work now.

- Remove tools and test_derp
  ([`ca0f69a`](https://github.com/eyeonus/Trade-Dangerous/commit/ca0f69ace7f540b817af77d94ad9b8e735d18ead))

- removed ocrDerp checking functionality (which would break on various extant system and station
  names), - removed accompanying tests,


## v12.11.7 (2026-02-20)

### Bug Fixes

- Spansh Plugin for Listener
  ([`06d22bd`](https://github.com/eyeonus/Trade-Dangerous/commit/06d22bdb909e2612c8fbcea313c5de04e07092df))

Various necessary changes for compatibility/interoperability with the MP listener for TD server.

### Build System

- Complete pyproject.toml migration - remove setup.py/setup.cfg, consolidate configs
  ([`2ac8d5b`](https://github.com/eyeonus/Trade-Dangerous/commit/2ac8d5b3b21ddccdd536662c37c7eafa71ae2116))

refactor: Consistent line length setting for 180 characters

refactor: standardize pyproject.toml formatting with PEP 518/660 compliance

Single source of truth in pyproject.toml following PEP 517/518/621.

- Update tox.ini testenv matrix for Python 3.10-3.14 support - Remove requirements files - Move
  [tool.pytest.ini_options], [tool.coverage.*] to pyproject.toml - Delete legacy setup.py/setup.cfg
  (all config now in pyproject.toml)

chore: add dependabot rules to reduce noise (.github/dependabot.yml)

chore: git ignore python notebook checkpoints and files-in-top-level

chore: remove github workflow_dispatch path (was used to test transition)

refactor: ruff detected issues

chore: adapt ruff to our style, solve unaddressed issues

this should bring ruff bleating more into alignment with our style, it addresses the various
  warnings/issues that ruff otherwise pointed out, it continues to attempt to normalize import
  ordering to reduce the ways we set ourselves up for import conflicts

refactor: fixed/squelched current pylint issues

This change does not activate pylint, so quality will decay.

Consider increasing the files covered by pylint.

chore: expose orm models from .db

refactor: Session being exposed as a global allowed it to be misused

fix: tdb Session being used incorrectly caused runtime errors

chore: streamline workflow

- reduces steps/moving parts in CI workflow, - increases test coverage to include ruff, pylint
  [strike], and py 3.15 by default[/strike] - runs tox on a single runner-per-platform covering all
  pythons in parallel

not done: - [strike]adds python 3.15 to the environments,[/strike] pending PyO3 3.15 support


## v12.11.6 (2026-01-30)

### Bug Fixes

- Really use services[] instead of hasX as primary source of truth
  ([`2bcc45e`](https://github.com/eyeonus/Trade-Dangerous/commit/2bcc45ec4e37c757a211f81425f2104acb53c451))


## v12.11.5 (2026-01-30)

### Bug Fixes

- Press save then push, you numpty.
  ([`10ce48f`](https://github.com/eyeonus/Trade-Dangerous/commit/10ce48f2b7fcdbbfb00c3aec23f70396244c663e))


## v12.11.4 (2026-01-30)

### Bug Fixes

- Various fixes based on spansh schema release
  ([`877f0b4`](https://github.com/eyeonus/Trade-Dangerous/commit/877f0b4fbc9df361d54628832852291b4532da84))

- Update Spansh station-type mapping to cover newly documented station `type` values: - Dodec
  Starport, Dockable Planet Station, Planetary/Space Construction Depots, Surface Settlement -
  Prevents these from falling through to Unknown (type-id=0), which can be misinterpreted
  downstream. - Derive station service flags from schema-backed `services[]`: -
  blackmarket/refuel/repair/rearm now come from `services` (Black Market / Refuel / Repair /
  Restock) - Retain legacy `hasX` fallback only when `services` is missing/non-list. - Use
  schema-correct system timestamp: - `System.date` is now used for system `modified` (with
  `updateTime` fallback for any legacy dumps).


## v12.11.3 (2026-01-28)

### Bug Fixes

- Correct the indentation in _mirror_csv_exports()
  ([`0443c81`](https://github.com/eyeonus/Trade-Dangerous/commit/0443c8174dca736f7b3c541893463de7daef45ca))

Be careful how you cut and paste, padawan.


## v12.11.2 (2026-01-28)

### Bug Fixes

- Correct excess mirroring on server
  ([`21d2427`](https://github.com/eyeonus/Trade-Dangerous/commit/21d2427d1cfc33c946ee711a86c51e6d5139de46))

We have been mirroring all of TD_DATA a lot of which is entirely unecessary. This ensures we only
  mirror what eddblink needs to TD_CSV and nothing else.


## v12.11.1 (2026-01-27)

### Bug Fixes

- Report actual database connection mode in export command
  ([`12ab024`](https://github.com/eyeonus/Trade-Dangerous/commit/12ab024515da74b310574a0fa769313224d970bc))

Ensure database reporting reflects the real connection details used by the engine, including unix
  socket connections, rather than blindly echoing host/port values.

This keeps user-facing output accurate and avoids misleading connection diagnostics.

chore: harden MariaDB config parsing and socket/TCP precedence

Make the MariaDB configuration more tolerant of user error by prioritising unix socket configuration
  when present and safely handling missing or empty host/port values.

This prevents crashes from empty config stubs and ensures a single, well-defined connection mode is
  selected.


## v12.11.0 (2026-01-27)

### Features

- Unix sock support for mysql/mariadb backend
  ([`0c60221`](https://github.com/eyeonus/Trade-Dangerous/commit/0c60221f34c2b057f28eee0a150aa88eafeb9cf6))

Add support for connecting to MariaDB/MySQL via a Unix domain socket in addition to the existing TCP
  host/port configuration.

A new optional `socket` key is recognised in the [mariadb] config section. When present and
  non-empty, the engine passes the socket path to the DBAPI (PyMySQL) via SQLAlchemy connect_args,
  causing connections to use the local Unix socket instead of TCP.

TCP behaviour is unchanged when `socket` is unset, allowing easy switching between connection styles
  via config.ini without code changes.


## v12.10.1 (2026-01-27)

### Bug Fixes

- We no longer emit TradeDangerous.prices from this plugin
  ([`a4257ac`](https://github.com/eyeonus/Trade-Dangerous/commit/a4257acc38f8b1d007fb17b9e3c14a15f6ff293a))

As far as server goes, we've had this deprecated for a while and now we're getting rid. If something
  needs it, the function in cache.py remains unchanged.


## v12.10.0 (2026-01-27)

### Chores

- Add 3.13 and 3.14 to versions we actually test
  ([`8cfe000`](https://github.com/eyeonus/Trade-Dangerous/commit/8cfe00012255789d18fcfce3636014b6e66bd263))

- Add benchmarking for parse_ts
  ([`b5ba552`](https://github.com/eyeonus/Trade-Dangerous/commit/b5ba552e00cf60c99b2a94d7c82594fde5cbf80d))

- Enhance fix-indent.sh with usage info and recursion
  ([`f1878ae`](https://github.com/eyeonus/Trade-Dangerous/commit/f1878aefb21a7fe5627a9c52ee0eab3dccb85c5e))

The script now provides usage instructions and supports recursive indentation fixing for Python
  files.

- **deps**: Bump urllib3 from 2.6.2 to 2.6.3
  ([`3edb517`](https://github.com/eyeonus/Trade-Dangerous/commit/3edb517f4a4f3d28a42f8add33f01a0b8460ae05))

Bumps [urllib3](https://github.com/urllib3/urllib3) from 2.6.2 to 2.6.3. - [Release
  notes](https://github.com/urllib3/urllib3/releases) -
  [Changelog](https://github.com/urllib3/urllib3/blob/main/CHANGES.rst) -
  [Commits](https://github.com/urllib3/urllib3/compare/2.6.2...2.6.3)

--- updated-dependencies: - dependency-name: urllib3 dependency-version: 2.6.3

dependency-type: indirect ...

Signed-off-by: dependabot[bot] <support@github.com>

- **deps**: Bump virtualenv from 20.35.4 to 20.36.1
  ([`86868d0`](https://github.com/eyeonus/Trade-Dangerous/commit/86868d0a5c906bfd6c1cd9f98e5e8fffb6ad084a))

Bumps [virtualenv](https://github.com/pypa/virtualenv) from 20.35.4 to 20.36.1. - [Release
  notes](https://github.com/pypa/virtualenv/releases) -
  [Changelog](https://github.com/pypa/virtualenv/blob/main/docs/changelog.rst) -
  [Commits](https://github.com/pypa/virtualenv/compare/20.35.4...20.36.1)

--- updated-dependencies: - dependency-name: virtualenv dependency-version: 20.36.1

dependency-type: indirect ...

Signed-off-by: dependabot[bot] <support@github.com>

- **deps**: Bump wheel from 0.45.1 to 0.46.2
  ([`4de2128`](https://github.com/eyeonus/Trade-Dangerous/commit/4de21285a5fb6dc1e90d1ecca7e2b9889040ce5a))

Bumps [wheel](https://github.com/pypa/wheel) from 0.45.1 to 0.46.2. - [Release
  notes](https://github.com/pypa/wheel/releases) -
  [Changelog](https://github.com/pypa/wheel/blob/main/docs/news.rst) -
  [Commits](https://github.com/pypa/wheel/compare/0.45.1...0.46.2)

--- updated-dependencies: - dependency-name: wheel dependency-version: 0.46.2

dependency-type: direct:production ...

Signed-off-by: dependabot[bot] <support@github.com>

### Features

- Optimize timestamp parsing during imports etc
  ([`b1f134c`](https://github.com/eyeonus/Trade-Dangerous/commit/b1f134c35e30dda6708549f167be923462df0fce))

style: fixup type hints etc,

chore: separator out the string-specific parsing handler so that parse_ts is general

benchmarks on 13th gen i7

before: ``` $ python ./research/perf/bench_parse_ts.py Iteration 5,003 iters took 94.265s, bench
  94.283s ex-best: 3.007ms, best: 3.046ms, avg: 18.815ms, worst: 166.830ms, ex-worst: 167.929ms,

p10: 15.679ms, p25: 15.745ms, p50: 16.125ms, p90: 31.464ms, p99: 33.577ms, ```

after: ``` $ python ./research/perf/bench_parse_ts.py Iteration 5,003 iters took 53.305s, bench
  53.315s ex-best: 0.000ms, best: 0.000ms, avg: 10.652ms, worst: 27.355ms, ex-worst: 31.672ms,

p10: 0.000ms, p25: 9.012ms, p50: 11.756ms, p90: 15.937ms, p99: 21.487ms, ```

### Testing

- Add unit tests for parse_ts
  ([`008ffa4`](https://github.com/eyeonus/Trade-Dangerous/commit/008ffa46e95e13e826e29b0e4e6049418d161825))


## v12.9.0 (2026-01-25)

### Features

- Modernization of python tooling
  ([`fa41e9e`](https://github.com/eyeonus/Trade-Dangerous/commit/fa41e9e6743f2bfa714d842ab33c45dd738d705f))

This change modernizes the internal package management to center on pyproject.toml, enabling support
  for several package managers including 'uv'.

Should not require any changes by developers or end users, but using something like mamba or uv will
  significantly reduce wait times when running things like tests/linters etc.

chore: refactor pyproject.toml, setup.cfg, setup.py with modern practices,

chore: tox testing is now uv-driven for speed and flexibility, - can test multiple python versions
  even if not installed, chore: transition dependencies/etc into pyproject.toml following modern
  python conventions,

docs: add a runbook covering how you can leverage this with uv package manager,

feat: use github uv tooling to build/distribute this change switches to the uv-based workflow
  actions for building releases. leaving both in-place would lead to conflicts.

chore: fixed several deprecation warnings/etc during build,

chore: gets version number from version.py as before,

docs: updated credits,

to test:

```sh python -m venv .setup-venv . ./.setup-venv/scripts/activate.ps1 python -m build --out-dir
  setup-build deactivate ```

and/or

```sh uv build --out-dir uv-build ```

Should be similar for other package managers.

Follow on actions: - remove requirements files,


## v12.8.4 (2026-01-25)

### Bug Fixes

- From_live fix. Also maybe flake doesn't moan.
  ([`f0270a1`](https://github.com/eyeonus/Trade-Dangerous/commit/f0270a10050fa376fd1558c0fcf1028ebaad180c))

- Various fixes to support MP listener.
  ([`d257f33`](https://github.com/eyeonus/Trade-Dangerous/commit/d257f3386494f16470100311d28bb12ff3bd1a2c))


## v12.8.3 (2026-01-18)

### Bug Fixes

- Make parse_ts reliably parse Spansh-style offset timestamps
  ([`8997dd7`](https://github.com/eyeonus/Trade-Dangerous/commit/8997dd751fe8c3d0a5af6aef1740ee21f7ade2fb))

Our runtime’s datetime.fromisoformat() rejects strings like YYYY-MM-DDTHH:MM:SS.xx+00:00, causing
  parse_ts() to return None. This was previously masked by -O maxage, but without maxage it leads to
  NOT NULL violations when spansh upserts StationItem rows with modified=NULL. Implement
  deterministic parsing for Z, +HH, +HHMM, +HH:MM (dropping fractional seconds as we normalise to
  microsecond=0), preserving UTC-naive output.

Fixes #278

### Code Style

- Tradeenv debloat ([#277](https://github.com/eyeonus/Trade-Dangerous/pull/277),
  [`a2a1e5d`](https://github.com/eyeonus/Trade-Dangerous/commit/a2a1e5d66a06737753de620f2c7bbeb78854ea2c))

these methods aren't used anywhere and don't seem appropriate for the context object.

### Refactoring

- Add type hint base to CSVDialect
  ([`1af1475`](https://github.com/eyeonus/Trade-Dangerous/commit/1af14759da16d128f05d97738f5ae87f0721571c))

No functional change, just makes python 3.12+ linters happier.


## v12.8.2 (2026-01-13)

### Bug Fixes

- Add missing orjson dependency in distribution
  ([`7152c74`](https://github.com/eyeonus/Trade-Dangerous/commit/7152c745a3c5ef99379c64a77c6778ccaf173e87))


## v12.8.1 (2026-01-13)

### Bug Fixes

- Trade_cmd --reverse flag is supposed to be -r not -R
  ([`1f6db34`](https://github.com/eyeonus/Trade-Dangerous/commit/1f6db3413da350105534b6739f22f9349b7d795e))


## v12.8.0 (2026-01-13)

### Features

- Network log/Journal reading module tradegame.py
  ([#252](https://github.com/eyeonus/Trade-Dangerous/pull/252),
  [`ab5a89b`](https://github.com/eyeonus/Trade-Dangerous/commit/ab5a89b6d3de2fc231027221afe75539d4b6ec0f))

* Incorporate basic game log file reading

feat: add tradegame.py and EliteGame class for reading journal/network log - Designed to be
  extensible with only minimal journal knowledge, - Uses `orjson` for super-fast parsing/load times,
  - Crude understanding of cargo capacity, - Crude understanding of current system/station, -
  Exposes journal/log file data as dictionaries without curation, - Default paths for Windows and
  MacOS; use ELITE_JOURNAL_PATH environment var to set/override

feat: 'journal' import plugin

`trade.py import -P journal` will import the last market prices you saw in-game if they are newer
  than the ones in the database.

refactor: add non-tradedb methods for duration normalization

feat: allow trade_cmd to read data from the game

preliminary syntax: - When docked, "~" = current system/current station, - When not docked, use
  "~/station name", - With a route selected, "~@" expands to target *system* name

feat: add --fill, --load, --full-load to trade command

these (mutually-exclusive) options all require live game data access to read your cargo capacity and
  load.

"--fill": for each available item, show the maximum profit you could make based on supply and
  maximum cargo capacity: ``` Win|pwsh> python trade.py trade ~ ~@/hole --fill 7 trades found
  between Kamitra/Hammel Terminal and Kuwemaki/The Jet's Hole. Item Profit Cost Buying | Units
  Profit -------------------------------------------------------------------- Water 686 22 708 | 108
  74,088 Fish 566 293 859 | 30 16,980 Wine 527 162 689 | 55 28,985 Grain 517 122 639 | 74 38,258
  Beer 513 92 605 | 81 41,553 Liquor 420 474 894 | 12 5,040 Hydrogen Fuel 52 88 140 | 108 5,616 ````

"--load": - fetches cargo capacity from game journal, - fetches current cargo quantity from game
  journal, - lists the most profitable items with sufficient supply/demand until cargo hold is full,

"--full-load": - as "--load" but ignores your current cargo (e.g if you're going to sell everything)

Examples, assuming you have 50 units of cargo in a hold with 251 capacity:

``` trade.py trade "Loha/Bell" "Byzan/Const" ... shows all items tradeable Bell Plant ->
  Constantinople

trade.py trade "Loha/Bell" "Byzan/Const" --load -vv 7 trades found between Loha/Bell Plant and
  Byzantine/Constantinople. Item Profit Cost Buying Supply Demand SrcAge DstAge | Units Profit
  --------------------------------------------------------------------------------------------------------------------------------------------
  Chemicals/Gold 51,581 4,945 56,526 1 103,828 1.7M 67.9M | 1 51,581 Chemicals/Silver 45,337 4,089
  49,426 8 415,091 1.7M 67.9M | 8 362,696 Chemicals/Beryllium 39,133 3,959 43,092 2 48,168 1.7M
  67.9M | 2 78,266 Chemicals/Gallium 24,888 2,479 27,367 384 247,010 1.7M 67.9M | 190 4,728,720
  ^^^-------------------------------------^^^ ```

here there are more items available, (supply of Gallium = 382) but it only counted enough *units* to
  fill your hold.

However, if you are going to sell the 50 units already in your hold first, --full-load would
  produce:

``` trade.py trade "Loha/Bell" "Byzan/Const" --full-load -vv 7 trades found between Loha/Bell Plant
  and Byzantine/Constantinople. Item Profit Cost Buying Supply Demand SrcAge DstAge | Units Profit
  --------------------------------------------------------------------------------------------------------------------------------------------
  Chemicals/Gold 51,581 4,945 56,526 1 103,828 1.7M 67.9M | 1 51,581 Chemicals/Silver 45,337 4,089
  49,426 8 415,091 1.7M 67.9M | 8 362,696 Chemicals/Beryllium 39,133 3,959 43,092 2 48,168 1.7M
  67.9M | 2 78,266 Chemicals/Gallium 24,888 2,479 27,367 384 247,010 1.7M 67.9M | 240 5,973,120
  ^^^-------------------------------------^^^ ```

"--load" and "--full-load" include a total unless you use "-q": ``` Win|pwsh> python trade.py trade
  "Zlotrimi/Alvarez de Pineda Prospect" "LB 3303/Poindexter Horizons" --full-load -v 2 trades found
  between Zlotrimi/Alvarez de Pineda Prospect and LB 3303/Poindexter Horizons. Item Profit Cost
  Buying SrcAge DstAge | Units Profit
  ------------------------------------------------------------------------------------------
  Metals/Gold 25,076 41,914 66,990 7D 10D | 773 19,383,748 Metals/Tantalum 2,297 12,527 14,824 7D 8D
  | 315 723,555
  ------------------------------------------------------------------------------------------ Total
  Units: 1,088. Total Profit: 20,107,303. ```

style: various hinting/cleanup

* review feedback: additional None checks

* Replace assertion with RuntimeError for max_journals

If it needs to be a real guard, it needs to not be an assertion.

* Add GameDataError for data inconsistency handling

Introduced GameDataError exception to handle inconsistencies in imported or journal data.

* Raise error for inconsistent cargo load

Add error handling for negative cargo space after deduction.

* Fix class definition for GameDataError

* Add GameDataError exception to trade_cmd.py

---------

Co-authored-by: Stefan Morrell <38956076+Tromador@users.noreply.github.com>


## v12.7.6 (2026-01-11)

### Bug Fixes

- Missing import of TradeDB could block run commands
  ([`10215e6`](https://github.com/eyeonus/Trade-Dangerous/commit/10215e6fe4fa02e785b93056ae7ad364a25ac57a))

### Chores

- Update rare list to match edcd 20260801
  ([`9e80831`](https://github.com/eyeonus/Trade-Dangerous/commit/9e808314df400285e7600fd241e4e3de8652330c))

### Code Style

- Fix inconsistent line-endings
  ([`69b2db8`](https://github.com/eyeonus/Trade-Dangerous/commit/69b2db88153a460399395285bee85c1e169ce771))

assorted files had both CRLF and LF in them, causing git to insist the files were modified if you
  checked them on on windows with core.autocrlf enabled.


## v12.7.5 (2026-01-08)

### Bug Fixes

- Eddblink - prevent template clobber; track server-sync state; fix MySQL clean
  ([`f90d75b`](https://github.com/eyeonus/Trade-Dangerous/commit/f90d75bba21cf74120e4abccc19fbe29595e7710))

Client-side hardening to ensure server exports remain authoritative:

- Add sync-state sidecar (eddblink_state.json in TD_DATA) using ETag/Last-Modified to decide
  freshness; stop using mtime so pip template updates can't “win”. - Ensure Category/RareItem
  refresh correctly when server dumps change. - Fix MariaDB/MySQL regression where -O clean removed
  CSV/state but left DB rows; clean now resets schema (sqlite recreates .db; MySQL drops+recreates
  tables). - Fix RareItem refresh by rebuilding RareItem (wipe then import) to avoid UNIQUE(name)
  collisions from legacy DB contents / PK drift.

### Chores

- Fix indents
  ([`e43fe19`](https://github.com/eyeonus/Trade-Dangerous/commit/e43fe196825c9ea4b3276f248c6e1bda89c36d75))

- Make tradegui able to launch
  ([`4c6d260`](https://github.com/eyeonus/Trade-Dangerous/commit/4c6d260c1b8bfdc8129e2e45ee6dc868e9d9f267))

IT DOES NOT WORK But at least it doesn't error anymore Functionality to come when I have time.


## v12.7.4 (2026-01-07)

### Bug Fixes

- Don’t overwrite bootstrap CSV templates on upgrade
  ([`8927127`](https://github.com/eyeonus/Trade-Dangerous/commit/8927127b3eb321b4164a64dcbb5a3792de8c1c94))

- Add fs.copy_if_missing() helper - Use copy_if_missing for Added.csv, Category.csv, RareItem.csv
  seeding in TradeDB - Prevent pip/packaging mtimes from clobbering existing user/server CSVs

### Chores

- Change category template to match server side truth
  ([`43a46bf`](https://github.com/eyeonus/Trade-Dangerous/commit/43a46bff5b77a246d9080834a093a19e26d8cfa5))

The cat order on the server is different due to importing from edcd and not using the old template,
  which helped with causing #270.

This brings the template in line what what the server has, to avoid that happening when templating
  is used.

Hate templates.


## v12.7.3 (2026-01-07)

### Bug Fixes

- Spansh csv exports (categories + mirror logic)
  ([`581726d`](https://github.com/eyeonus/Trade-Dangerous/commit/581726d33b9b5e6a51cc35f26555a4fb9c040c12))

- Freeze canonical Category IDs (deterministic, append-only) - Export Category.csv from DB (was
  missing) - Write exports to TD_DATA, then mirror to TD_CSV (for server use) - Stop stale TD_DATA
  CSVs overwriting fresh public files

Import/DB logic untouched; export-side fix only.

### Chores

- And a definition of our CSV Dialect
  ([`dfd21fb`](https://github.com/eyeonus/Trade-Dangerous/commit/dfd21fb5bcd9393e28b570f49a88ccaec6c73580))

Not wired in anywhere yet because I don't know where it's safe to use, but if Python gets
  opinionated about the format at some point, we can use this.

- For the love of blank lines, we cannot proceed.
  ([`3254447`](https://github.com/eyeonus/Trade-Dangerous/commit/3254447a889209b9e17521c7b7ae0af3db367a72))


## v12.7.2 (2026-01-05)

### Bug Fixes

- Edblink - upsert refreshed dump tables before importing listings
  ([`4d9e498`](https://github.com/eyeonus/Trade-Dangerous/commit/4d9e4988625bce4fca1609f082f16146d89ed44b))

When eddblink downloads updated core dump CSVs (System/Station/Category/Item/etc), the ORM DB could
  remain stale and listings import would silently skip rows for unknown station_id/item_id.

eddblink now upsert-refreshes any newly-downloaded dump tables (merge semantics, no deletes/rebuild)
  prior to processing listings, and shows proper per-table row-count progress bars during the upsert
  pass.

Fixes #268

### Chores

- Reseat max-link-ly into tradeenv
  ([`217c909`](https://github.com/eyeonus/Trade-Dangerous/commit/217c909bde588708c1a122bf0f89b49b054da5e0))

currently it's in tradedb which is not where it should be and would be an annoyance for working with
  TradeORM.

This also gives it a new default of 64, and a default that's in the same place as other tradeenv
  parameters...

chore: make maxSystemLinkLy a formal property of TradeEnv

chore: get maxSystemLinkLy from tradeenv, not tradedb

review feedback


## v12.7.1 (2026-01-03)

### Bug Fixes

- (perf) stellar grid had off-by-1 clumping
  ([`ad60bb4`](https://github.com/eyeonus/Trade-Dangerous/commit/ad60bb44687811b3613efa0f0b0835b3b77a3fdf))

chore: minor stellar grid tear-up optimization (~20ms)

dev: adds an Ipython notebook containing my research on distance calculations, as at one time
  "**0.5" was faster than "math.sqrt" but in current Python it seems that sqrt is, once again,
  faster. chore: type hinting

### Chores

- Minor cleanup: type hinting, flake/ruff warnings
  ([`4414d7d`](https://github.com/eyeonus/Trade-Dangerous/commit/4414d7dcd268fe272cda86e8415a75171ca01aa8))

- Normalize line endings
  ([`1fc3d76`](https://github.com/eyeonus/Trade-Dangerous/commit/1fc3d76bbaf757d56fa2fb9d6ac26dcab01d3c22))

chore: add .gitattributes to define line endings for particular files,

chore: normalize two files that had mixed line endings in them

- Remove the 'persist' file code ([#261](https://github.com/eyeonus/Trade-Dangerous/pull/261),
  [`628c03c`](https://github.com/eyeonus/Trade-Dangerous/commit/628c03cec5d58edf27bd2a649d009fe92113791f))

Now that we routinely optimize the database during use, two things happen: 1- the optimizations
  cause the db filestamp to change *after* we write the pickle data, invalidating it, 2- the speed
  improvement of pickle vs load is small enough that we don't need this extra code in the way,
  already.

chore: remove reference to the persist code

review feedback: collapse the pickle stuff more completely

- Type hinting
  ([`eed7c4f`](https://github.com/eyeonus/Trade-Dangerous/commit/eed7c4f119011f75e8ef1d42d79f2c5f3d1caab0))

- Type hinting cleanup
  ([`7bbcd41`](https://github.com/eyeonus/Trade-Dangerous/commit/7bbcd415b5125ffaff50314a81d5de458293c95c))


## v12.7.0 (2025-12-31)

### Features

- Make ctrl-c during trade run show the route as-calculated
  ([#254](https://github.com/eyeonus/Trade-Dangerous/pull/254),
  [`666a56c`](https://github.com/eyeonus/Trade-Dangerous/commit/666a56c21a6fa6a4ecde5e8c38533f25a37c5eea))

* feat: make ctrl-c during trade run show the route as-calculated

This feature allows you to interrupt a long running multi-hop route calculation without losing all
  that processing work...

``` Win|pwsh> python trade.py run --from shinrar/memorial --ly 150 --jumps 1 --hops 4 --cr 370m
  --cap 1088 --gpt 8000 --age 3 --pad l --fc=n --detail --detail --progress --prune-score=40
  Searching for quality trades. This may take a few minutes. Please be patient. \ Scanning market
  data… rows 1,392,753 kept: buys 1,384,326, sells 418,838 | Scanning stations… examined 1 kept 1 *
  Hop 1: .........1 origins | origin 1/1 destinations checked: 1 best score: 0 * Hop 2: ........45
  origins .. 9,095,680-27,890,880cr gain, 8,360-25,635cr/ton / origin 43/45 destinations checked:
  3,537 best score: 27,688,173 NOTE: Pruned 299 origins

* Hop 3: .......450 origins .. 23,700,992-40,815,232cr gain, 10,892-18,757cr/ton \ origin 31/450
  destinations checked: 2,353 best score: 32,072,684 *** Ctrl-C Interrupt, stopping search...

User aborted route calculation.

Shinrarta Dezhra/Jameson Memorial -> Tionisla/Ing Ring (score: 68326125.735657) Load from Shinrarta
  Dezhra/Jameson Memorial (345ls, Pad:L, Plt:N, Flc:N, Ody:N, Shp:Y, Out:Y): 1088 x Legal
  Drugs/Agronomic Treatment 2,860cr vs 15,427cr, <1 hr vs <1 hr Unload at Barnard's Star/Pohl
  Metallurgic Station (61ls, Pad:L, Plt:Y, Flc:N, Ody:Y, Shp:N, Out:N) => Gain 13,672,896cr
  (12,567cr/ton) => 383,672,896cr Load from Barnard's Star/Pohl Metallurgic Station (61ls, Pad:L,
  Plt:Y, Flc:N, Ody:Y, Shp:N, Out:N): 639 x Consumer Items/Cryolite 10,510cr vs 29,428cr, <1 hr vs 1
  hr 449 x Consumer Items/Pyrophyllite 9,822cr vs 28,537cr, <1 hr vs 1 hr Unload at Puppis Sector
  UO-R b4-0/Democracy Space Station (4ls, Pad:L, Plt:N, Flc:N, Ody:N, Shp:Y, Out:Y) => Gain
  20,491,637cr (18,834.2cr/ton) => 404,164,533cr Load from Puppis Sector UO-R b4-0/Democracy Space
  Station (4ls, Pad:L, Plt:N, Flc:N, Ody:N, Shp:Y, Out:Y): 1088 x Legal Drugs/Agronomic Treatment
  452cr vs 28,495cr, 1 hr vs 2 hrs Unload at Tionisla/Ing Ring (576ls, Pad:L, Plt:N, Flc:N, Ody:N,
  Shp:Y, Out:Y) => Gain 30,510,784cr (28,043cr/ton) => 434,675,317cr
  ---------------------------------------------------------------------------- Finish at
  Tionisla/Ing Ring (576ls, Pad:L, Plt:N, Flc:N, Ody:N, Shp:Y, Out:Y) gaining 64,675,317cr
  (19,814cr/ton) => est 434,675,317cr total ```

review feedback

- feat: add SimpleAbort exception for tidying up "expected error" output

SimpleAbort should only be intercepted at the top level of an application.

incorporated feedback review

- fixed typos, - one way to describe ctrl-c, an exception type, - leverage SimpleAbort and
  UserAbortedRun, - allow Ctrl-C to be Ctrl-C if there are no results to preserve, it simplifies
  logic a lot

That's not the greatest user experience, but it's no worse than hitting ctrl-c already was, and has
  the advantage that if you do it when there are results, you get *something* rather than nothing.

* review feedback


## v12.6.4 (2025-12-30)

### Bug Fixes

- Commandenv colorizing was overly expensive
  ([#257](https://github.com/eyeonus/Trade-Dangerous/pull/257),
  [`e0fc3ee`](https://github.com/eyeonus/Trade-Dangerous/commit/e0fc3ee630a61e30f03c255a1d8e8ac9c77a62dc))

- eliminate a system call in a hot loop on windows (calling the 'color' command), - - rich console
  should already have handled this for us much earlier, - - if there IS a console that ACTUALLY
  requires this, it is esoteric and should be handled separately, - - do nothing when there's no
  color, - - trivial optimization of the clear code against every output, - improve documentation of
  the colorize method/ansi codes, - some type hinting

### Chores

- Clean up exception throw ([#253](https://github.com/eyeonus/Trade-Dangerous/pull/253),
  [`1b60caa`](https://github.com/eyeonus/Trade-Dangerous/commit/1b60caaee4657aed94fe70f84d227ffd3263b5d3))

I thought this logic was more complex, it's an unlink, there's no buried path here.

- Tradecalc touch-up
  ([`458dbe8`](https://github.com/eyeonus/Trade-Dangerous/commit/458dbe827a5de3aec565f6aa61773123ed6b9825))

chore: increase debug tracing of route calculation,

opt: trivial improvements to performance of route calculation

feat: trade run --demand and --supply now reduce the amount of trade-rows viewed while calculating a
  route (caveat: this can cause products to appear unavailable if used too aggressively, which it
  did anyway, but I found the way it concluded that much faster made me think it wasn't working)

chore: repr for TradeDB System and Station - I know, we're deprecating these, but that makes it even
  more helpful to be able to *see* them in rich/debugging for now. fix: run: handle finding no
  trades to route better - I was noticing an error/exception when no routes-with-trades were found
  when using certain filters (--demand/--supply) or using an overly-aggressive --gpt (I may have
  typoed 10000, no you typoed) - Also, using routes[:] acts as an in-place
  truncate/crop/reassignment and reduces memory pressure a little. - This is mostly cosmetic, any
  perf gains are negligible. chore: missing __all__ from plugins/__init__

- Update advisory locks for mp listener
  ([`1246520`](https://github.com/eyeonus/Trade-Dangerous/commit/1246520851995224c6c1f783a39df67508cd83e3))


## v12.6.3 (2025-12-20)


## v12.6.2 (2025-12-18)

### Bug Fixes

- Pythonic cleanup/type hinting/heartbeats
  ([#248](https://github.com/eyeonus/Trade-Dangerous/pull/248),
  [`6425358`](https://github.com/eyeonus/Trade-Dangerous/commit/6425358653019200b081cce19e184a2d2341dcf4))

chore: reduce IDE squiggles by providing type hints for TradeEnv (tradeenv.pyi)

chore: optimized a couple of hot-path loop appends

chore: remove some unused imports and moved some inline imports to top-of-file; lazy importing is
  usually a smell

chore: hoist invariant conditions out of path_iter in get destinations (why execute the same 'if'
  for every row)

chore: consistency/hinting pass on TradeEnv

### Chores

- Add tradeenv.pyi and py.typed to package data
  ([`eb19090`](https://github.com/eyeonus/Trade-Dangerous/commit/eb19090eb69295ace544f3b0a78b240b21c5d666))


## v12.6.1 (2025-12-15)

### Bug Fixes

- Correctly run fast CLI validation *before* loading TradeDB
  ([`ed2b8aa`](https://github.com/eyeonus/Trade-Dangerous/commit/ed2b8aa358895fb96657f02f26c99852351f0967))

PR1 (discussion #245): reorder CLI startup so validateRunArgumentsFast can short-circuit invalid
  invocations before any heavy TradeDB(load=True) work.

- Add CommandEnv.preflight() to run validateRunArgumentsFast once. - Call preflight from cli.trade()
  before constructing TradeDB(load=...). - Ensure CommandEnv.run() also calls preflight for non-CLI
  entrypoints. - Add regression tests proving TradeDB is not constructed when preflight fails and
  that preflight can flip wantsTradeDB to avoid load=True.


## v12.6.0 (2025-12-14)

### Features

- 'units' option for eddblink import ([#244](https://github.com/eyeonus/Trade-Dangerous/pull/244),
  [`d095394`](https://github.com/eyeonus/Trade-Dangerous/commit/d09539440ca53bebf7200ecd0c64e17393936c72))

Somehow eddb data has lots of bogus listing entries with a supply price but a units value of 0, such
  as 'thardgoid probe' appearing at stations that clearly do not sell it.

This change makes it so that running eddblink import with -O units will treat those entries as
  having a supply-price of zero or demand-price of zero depending on which field it is.

This has the knock-on effect of hiding lines that just arent' present at a station, but this may
  have the consequence of making it impossible to look up good buyers for rare items like Guardian
  Orb etc, which will only appear in the list if you have them in inventory


## v12.5.1 (2025-12-12)

### Bug Fixes

- Progress bars ([#242](https://github.com/eyeonus/Trade-Dangerous/pull/242),
  [`d232951`](https://github.com/eyeonus/Trade-Dangerous/commit/d2329511880ac5bd9a0b72406e0572db610eed22))

* fix: missing progress bar for optimize

* fix: 'Working...' and bad progress bars

- Adds ElapsedBar to progress bars, which is just a timer, - Adds a 'label=' field to ProgressBar
  constructor, which sets a label without waiting for a bump (default label=Working...), - Fixed
  eddblink progress bars that were just printing 'Working...'


## v12.5.0 (2025-12-12)

### Documentation

- Update documentation to reflect application database usage
  ([`8b44887`](https://github.com/eyeonus/Trade-Dangerous/commit/8b448870a2a4261155cb85d3476e9b577775ddf2))

It's still not just sqlite :p

### Features

- Add td version to help ([#243](https://github.com/eyeonus/Trade-Dangerous/pull/243),
  [`2976efd`](https://github.com/eyeonus/Trade-Dangerous/commit/2976efd2534af8384347125c500f95e76c85d86e))

Fixes #220


## v12.4.0 (2025-12-12)


## v12.3.0 (2025-12-11)

### Bug Fixes

- Allow lookupSystem to accept System/Station objects again
  ([`95a6d04`](https://github.com/eyeonus/Trade-Dangerous/commit/95a6d045154ba58a739f9d3b1335313797772906))

- restore legacy behaviour where lookupSystem(System) returns the System - fixes test_peek failure
  on py311 caused by _split_system_index assuming str - ensures lookupStation(..., system) paths
  work correctly

### Features

- Improved logging, leaner code, automatic sqlite3 db tune on import
  ([`915c7d8`](https://github.com/eyeonus/Trade-Dangerous/commit/915c7d8ddede53d20778eec85b3170df84f2b0d0))

* feat: improved logging, leaner code

-- add's 'INFO' level log (gear icon in color mode), -- streamlines the logger-generation code with
  a match statement, and a simple function body implementation,

* feat: automatic sqlite3 db tune on import

- when an eddblink import finishes, ask sqlite to optimize the data if it believes there is value
  ('PRAGMA optimize') - when an eddblink --opt=optimize finishes, ask sqlite to vacuum AND optimize
  aggressively ('analyze') - when forced to build cache, follow pragma_optimize guidance and set
  0x10002, - added a 'bench' decorator that tells us how long the operations take while wrapping
  them with a pbar - move the optimize to a 'tuning' so it is always done regarless of whether there
  are updates, - - this makes it possible to run the eddblink plugin solely to peform an optimize
  without any data updates

- Support disambiguating duplicate system names with @N
  ([`2819024`](https://github.com/eyeonus/Trade-Dangerous/commit/28190241b6727707ac6bd2b2459fefc7f97475d1))

- fix: treat multiple systems with the same name as an ambiguity instead of a single entry. Fixes
  #224 - change systemByName to support 1→many mapping with deterministic ordering - allow "System
  Name@N" to select a specific system by index - add structured ambiguity messages with coordinates
  and @N hints - preserve existing behaviour for normal abbreviations (e.g. "james")


## v12.2.0 (2025-12-07)

### Chores

- Expose top-level objects from module
  ([`a9bd556`](https://github.com/eyeonus/Trade-Dangerous/commit/a9bd5563a8378addccbc663a3ec4924acc10beee))

- Pythonic cleanup
  ([`44051e7`](https://github.com/eyeonus/Trade-Dangerous/commit/44051e755b4f7f6753ab8c9e9408346c499707cd))

### Features

- '7days' option to eddblink plugin
  ([`3d2943a`](https://github.com/eyeonus/Trade-Dangerous/commit/3d2943ab03201ceb4a2a201efb4a7f5dda8d8635))

running the import eddblink plugin with -O7days will only import entries 7-days or newer and will
  then prune any older entries from the StationItem table, making many run operations faster.

- Improve eddblink import performance
  ([`e8cf541`](https://github.com/eyeonus/Trade-Dangerous/commit/e8cf541b822f816765bacbd204f6a160775465f5))

in testing, this reduces a full listings.csv from 11 minutes to 8 minutes.


## v12.1.1 (2025-12-01)

### Bug Fixes

- Need to be more careful about expiring the persist file
  ([`9263784`](https://github.com/eyeonus/Trade-Dangerous/commit/92637845d44447dc9907f54e8899101b6211b99f))

- Remove unused ensureflag method/tests
  ([`7185d78`](https://github.com/eyeonus/Trade-Dangerous/commit/7185d78e2f5bf961117da7ed3fbceb9bdfa123b9))

- Unbreak unit tests
  ([`452a7cb`](https://github.com/eyeonus/Trade-Dangerous/commit/452a7cb87665c137124fdb6c9e132fe5a7c83a85))

this includes various chore: items I went thru finding the issue, removed some dead code, added
  various type hints, reorganized some issues that were causing yellow and orange squiggles in
  vscode ide.

fundamentally tho this causes the unit tests to force a clean shutdown of tdb/sqa objects that are
  dead but haven't yet given up the ghost and are holding on to the database file handle.

### Chores

- Defer added and ships to the database
  ([`3b13b9c`](https://github.com/eyeonus/Trade-Dangerous/commit/3b13b9ccc8b4f7aefa5e9385e9f682bcf647e01f))

These tables are rarely used, and loading them explicitly is a waste. Deprecating them helps reduce
  the number of obstacles toward having TradeDB be a layer over the database access.

- Fix-indents
  ([`032fee0`](https://github.com/eyeonus/Trade-Dangerous/commit/032fee0dc4b478f370f106584dcaceb3e85208ea))

- Migrate Rares to a pure db table
  ([`c5bc22c`](https://github.com/eyeonus/Trade-Dangerous/commit/c5bc22c2247d2f2083589045d419835601cdd036))

Defer rare lookups to the dbapi directly, reimplementing 'rares' subcommand to use it.

- Type hinting, comments, cleanup
  ([`991c08c`](https://github.com/eyeonus/Trade-Dangerous/commit/991c08cf51d0d741b69985d2329db20710b55b1a))

adds several type hints and modernizes some typing, moves various imports to the top level, removes
  the now unused RareItem type in favor of the db type, fixes unused/masked imports from SQLAlchemy,

- Type hints for fs.py
  ([`48b2bd4`](https://github.com/eyeonus/Trade-Dangerous/commit/48b2bd4f880e22e9bae29b65bbeef7b5e124737f))


## v12.1.0 (2025-11-30)

### Bug Fixes

- Use raw CLI flags (starting/ending) in fast-fail instead of DB-resolved fields
  ([`63cda00`](https://github.com/eyeonus/Trade-Dangerous/commit/63cda0071ce4f912727a5687fccab860a3ebf994))

### Features

- Add some basic trade run validation early.
  ([`95c024c`](https://github.com/eyeonus/Trade-Dangerous/commit/95c024c043b629f77b107a2dda2885dd274e9f87))

Really we want to do this before even making the TradeDB() object, but this helps a lot for the
  particular errors in question.


## v12.0.18 (2025-11-25)

### Bug Fixes

- Fix slow station loading
  ([`84b479e`](https://github.com/eyeonus/Trade-Dangerous/commit/84b479effbb37cd16d3a8f73ba38c8d3ba3d259e))

array lookups are not cached, so for every station it was having to do two dictionary table lookups
  to find the list of possible type ids. every time I hit ctrl-c (out of 16) it as on isFleet =
  'Y'...

It would actually be best to eliminate the named values entirely in favor of type_id in (24, 0) and
  type_id == 25 to avoid doing an additional value lookup - global comparison is faster in this
  scenario, but not of big enough value to lose the named constants now.

- If main is called with an argv, use it
  ([`25d46e2`](https://github.com/eyeonus/Trade-Dangerous/commit/25d46e24f3e6cfd49773d2a9c5bdd209d0cf8e0d))

- Minor trade calculation overheads
  ([`a5a6015`](https://github.com/eyeonus/Trade-Dangerous/commit/a5a6015d0de531895a79a084f6da4bc5f541845d))

- list.append is slower than list += [] since Python 3.7, - calling heartbeat unconditionally was
  extra expensive in non-progress runs, - calling heartbeat incurred a call to time.time() (~300ns)
  for every station seen, so only call it intermittently,

- Missing indent
  ([`489761f`](https://github.com/eyeonus/Trade-Dangerous/commit/489761ff14645cb42a281bcd8e7cd8e5f5c4742c))

### Chores

- Update CHANGELOG
  ([`e0c0f5e`](https://github.com/eyeonus/Trade-Dangerous/commit/e0c0f5e31f3e844a1608306ca8843f253981afe1))


## v12.0.17 (2025-11-11)

### Bug Fixes

- Expandforjumps stations are never src
  ([`60a1884`](https://github.com/eyeonus/Trade-Dangerous/commit/60a1884206afb0c3cb3c4984477b86d60f3379ec))


## v12.0.16 (2025-11-10)

### Bug Fixes

- Credit parser should not be case-sensitive
  ([`cd5373d`](https://github.com/eyeonus/Trade-Dangerous/commit/cd5373d4275f97fc259c7a2512a32078f30f4dda))


## v12.0.15 (2025-11-07)

### Bug Fixes

- Speed up `trade` subcommand by restricting preload to target stations
  ([`186679f`](https://github.com/eyeonus/Trade-Dangerous/commit/186679f66247c2d9b4841b477009633e669b40c5))

- Reordered `trade_cmd.run()` to resolve origin/destination BEFORE constructing `TradeCalc`. - Added
  optional `restrict_station_ids` parameter to `TradeCalc.__init__` and applied `WHERE station_id IN
  (...)` in Core SQL when provided. - Fixed `item_id IN (...)` filter to enumerate placeholders
  (SQLAlchemy `text()` won’t expand tuples), ensuring the item filter path executes correctly. -
  Behaviour for all other subcommands remains unchanged (parameter defaults to None). - Observed
  improvement on sample run: 90.68s → 5.69s elapsed; MaxRSS ~2.06 GB → ~0.61 GB.


## v12.0.14 (2025-11-06)

### Bug Fixes

- Put back the long maths comments chatgpt ate.
  ([`9b9fc85`](https://github.com/eyeonus/Trade-Dangerous/commit/9b9fc8574d726032dbdac2a8cdd8a0bacd082422))


## v12.0.13 (2025-11-06)

### Bug Fixes

- Ensure trade runs reach intended destinations; correct `--to` system scans; make `--direct`
  sensible without `--to`
  ([`e151391`](https://github.com/eyeonus/Trade-Dangerous/commit/e1513919a67f9de934b2fcdf23d3050503010d3e))

- tradecalc.py :: getBestHops - Replace ORM isinstance checks with duck typing so `restrictTo` works
  with either ORM or tradedb objects. - When `--direct` is used without `--to`/`--towards`, iterate
  all eligible stations (excluding `--avoid`) instead of none. - Build `restrictStations` from
  `.stations` (systems) or direct station objects; reliably honour `--to` restrictions. - No change
  to scoring/heartbeat; only destination enumeration logic corrected.

- run_cmd.py :: expandForJumps - Fix inverted trading maps: `--to` uses `stationsBuying`; `--from`
  uses `stationsSelling`. - Pass `srcName` to `checkStationSuitability` so endpoints are validated
  with correct buy/sell expectations.

- run_cmd.py :: checkDestinations - For `--to SYSTEM`, scan **all** stations in the system; **skip**
  those failing `--to` suitability (age/pad/market/etc.) instead of aborting on the first failure. -
  For `--to STATION`, remain strict (hard-fail if unsuitable). - Progress heartbeat preserved.

- run_cmd.py :: filterStationSet - Make filtering tolerant for `--to`/`--from` (skip unsuitable
  stations), but keep `--via` strict (still raises to honour explicit constraints). - Fix message
  formatting; return tuple like legacy behaviour.

- Behavioural outcomes - Routes now consistently end at requested `--to` system/station when a
  viable path exists. - `--direct` produces sensible single-hop routes: targets `--to` if given;
  otherwise considers all eligible destinations. - `--to SYSTEM` no longer dies on a single bad
  station (e.g., one port in Sol out-of-age).

- Unchanged - No new flags; existing constraints (pad, planetary, Odyssey, fleet, black market,
  max-ls, age) are applied as before. - Name ambiguity still errors with existing disambiguation. -
  Fleet carriers remain excluded unless explicitly allowed by flags.

- Ensure trade runs reach intended destinations; correct `--to` system scans; make `--direct`
  sensible without `--to`
  ([`41a2fdd`](https://github.com/eyeonus/Trade-Dangerous/commit/41a2fdd11633acfab60bdf50e65aa65e76a05be9))

- tradecalc.py :: getBestHops - Replace ORM isinstance checks with duck typing so `restrictTo` works
  with either ORM or tradedb objects. - When `--direct` is used without `--to`/`--towards`, iterate
  all eligible stations (excluding `--avoid`) instead of none. - Build `restrictStations` from
  `.stations` (systems) or direct station objects; reliably honour `--to` restrictions. - No change
  to scoring/heartbeat; only destination enumeration logic corrected.

- run_cmd.py :: expandForJumps - Fix inverted trading maps: `--to` uses `stationsBuying`; `--from`
  uses `stationsSelling`. - Pass `srcName` to `checkStationSuitability` so endpoints are validated
  with correct buy/sell expectations.

- run_cmd.py :: checkDestinations - For `--to SYSTEM`, scan **all** stations in the system; **skip**
  those failing `--to` suitability (age/pad/market/etc.) instead of aborting on the first failure. -
  For `--to STATION`, remain strict (hard-fail if unsuitable). - Progress heartbeat preserved.

- run_cmd.py :: filterStationSet - Make filtering tolerant for `--to`/`--from` (skip unsuitable
  stations), but keep `--via` strict (still raises to honour explicit constraints). - Fix message
  formatting; return tuple like legacy behaviour.

- Behavioural outcomes - Routes now consistently end at requested `--to` system/station when a
  viable path exists. - `--direct` produces sensible single-hop routes: targets `--to` if given;
  otherwise considers all eligible destinations. - `--to SYSTEM` no longer dies on a single bad
  station (e.g., one port in Sol out-of-age).

- Unchanged - No new flags; existing constraints (pad, planetary, Odyssey, fleet, black market,
  max-ls, age) are applied as before. - Name ambiguity still errors with existing disambiguation. -
  Fleet carriers remain excluded unless explicitly allowed by flags.


## v12.0.12 (2025-11-06)

### Bug Fixes

- Overwrite whole line when showing calcuations with --progress
  ([`74017fa`](https://github.com/eyeonus/Trade-Dangerous/commit/74017faebf95a145fe31791a22eb8d71e1bfa8ad))


## v12.0.11 (2025-11-02)

### Bug Fixes

- Replace StationItem.csv in database imports
  ([`f713597`](https://github.com/eyeonus/Trade-Dangerous/commit/f713597f9cd84b49ce9301a3b48d79f13a2ade99))


## v12.0.10 (2025-10-31)

### Bug Fixes

- Utils.py - Timing parity.
  ([`5515e58`](https://github.com/eyeonus/Trade-Dangerous/commit/5515e58265f50f83fadfc0e4182fe4caf76f9961))

1: SQLite age calculation Per Gazelle
  https://forums.frontier.co.uk/threads/trade-dangerous-est-2015-power-users-highly-configurable-trade-optimizer.441509/post-10731134
  - **Change:** `func.julianday(func.current_date())` → `func.julianday()` - **Reason:**
  `current_date` anchors to midnight, causing negative ages for same-day timestamps. `julianday()`
  with no argument correctly uses the current timestamp.

2: Relaxed modified guard

- **Change:** `>` → `>=` in both `sqlite_upsert_modified()` and `mysql_upsert_modified()` -
  **Reason:** SQLite truncates timestamps to whole seconds, so identical timestamps can represent
  newer data. Allowing equality prevents missed updates and maintains cross-backend parity.


## v12.0.9 (2025-10-30)

### Bug Fixes

- Tradecalc time calculations for max days
  ([`cf99181`](https://github.com/eyeonus/Trade-Dangerous/commit/cf9918143e8d70264e2b50b7ad2b9c8491266464))

If I was in Star Trek hours could seem like days. But as we're in an entirely different IP, perhaps
  we better calculate a day properly instead of just using hours.


## v12.0.8 (2025-10-30)

### Bug Fixes

- Bytecounts now correctly show decimal portion in cyan.
  ([`b81e986`](https://github.com/eyeonus/Trade-Dangerous/commit/b81e986b346b0485662f3a3b822cbf268875132b))


## v12.0.7 (2025-10-29)

### Bug Fixes

- Typo in spansh plugin
  ([`cdacda9`](https://github.com/eyeonus/Trade-Dangerous/commit/cdacda9dddd4e5f75490ebcd3f3e4ff77db5b067))

### Refactoring

- `start time` only time not date too
  ([`860a94f`](https://github.com/eyeonus/Trade-Dangerous/commit/860a94f7d6d45c4f40e4d8a4452919a61d671bc2))

self.now() now returns only the "HH:MM:SS" portion of the full `datetime`

So no more showing the date or the mircoseconds in the status output.


## v12.0.6 (2025-10-29)

### Bug Fixes

- Make EDDBlink not redundant
  ([`f38a952`](https://github.com/eyeonus/Trade-Dangerous/commit/f38a952dab1246f371a42220f5e755abc01a4d3a))

Just fixing AI idiocies such as not enabling `clean` option when building a new DB, building the DB
  twice per import, doing a *lot* of redundant functions that should really be a call to the method
  that already does all that, etc., etc.

Oh and fixing the indentation.

- Rm TradeDangerous.prices
  ([`893bcc4`](https://github.com/eyeonus/Trade-Dangerous/commit/893bcc4d9e7879237d381fe821743db687f9d7ab))

The `TradeDangerous.prices` file is actually a hindrance not a boon nowadays, so with the new DB
  backend in place it's time to stop using it.

[NOTE: It is still possible to import data using `.prices` files, this only removes the dependence
  on the internally used file.]

- Void Opal is singular
  ([`9fc52ac`](https://github.com/eyeonus/Trade-Dangerous/commit/9fc52acdeb99a387aed083817913c834def3a398))

### Chores

- Add fix-indent script to repo
  ([`539b4e7`](https://github.com/eyeonus/Trade-Dangerous/commit/539b4e75ac5c8f4374c63035cb2bb58267568d71))

- Update gitignore
  ([`937b707`](https://github.com/eyeonus/Trade-Dangerous/commit/937b707a4992030d6de4dcd18fb93f80ac5f2683))

### Code Style

- Fix indent
  ([`e43141e`](https://github.com/eyeonus/Trade-Dangerous/commit/e43141e0e605311892da9397ed5eb20d7743ca81))

### Refactoring

- Better DB build message.
  ([`1637811`](https://github.com/eyeonus/Trade-Dangerous/commit/16378112329e1373f3467569ca9b1ec8ce3c8f8e))

- Cache build finished = note
  ([`6746780`](https://github.com/eyeonus/Trade-Dangerous/commit/674678019b884c31da46eb4712094e4e2fbb1859))

it was a debug message so it would only print if debug is on, changed it to a NOTE that always
  prints unless quiet.

- Explicit cast from_live
  ([`62efa45`](https://github.com/eyeonus/Trade-Dangerous/commit/62efa45ea7301adf25a2b00026b30523c05b9eda))

Cast the from_live to integer before inserting, to make sure that the DB doesn't get cranky trying
  to pass a Bool to fill an Int field.

Because this is easier than fixing the DB to have it be a Bool there too.

- Remove unneeded cache build
  ([`1f4cd3d`](https://github.com/eyeonus/Trade-Dangerous/commit/1f4cd3d4df9a98fc1bf5dba396a1a975cbad054b))

With the changes to how things are done since this was originally written, the initial DB build that
  occurs when doing a `clean` run is no longer needed.


## v12.0.5 (2025-10-29)

### Bug Fixes

- Cache.py deprecation 2nd attempt
  ([`58c17d9`](https://github.com/eyeonus/Trade-Dangerous/commit/58c17d94e55c4d9fcc6698a8ca732c447063e454))

importer: inline deprecation corrections; keep processing; gate warnings to -vv; prices path fixes

- processImportFile - Apply deprecation corrections in-row before uniqueness/FK/type coercion so
  corrected values are what get merged. - Run uniqueness check after correction; in tolerant mode
  (ignoreUnknown) downgrade post-correction duplicates to WARNING and continue; strict mode still
  raises. - Replace exception-driven deprecation path with explicit DEBUG1 messages (only shown at
  -vv). Deleted entries: skip in tolerant mode, remain fatal in strict.

- processPricesFile - Add missing `from sqlalchemy import tuple_`. - Use tuple_(station_id, item_id)
  to delete zero-pairs. - Report `removedItems` correctly.

- importDataFromFile - Use a proper ORM Session; fix bad `db=` kwarg; commit via session.

Why: Deprecated names (e.g. "Void Opal" → "Void Opals") were warning then tripping
  uniqueness/exception paths pre-correction, giving the illusion of aborting mid-file. Now we
  correct+upsert and continue; deprecation chatter is quiet unless -vv.

Notes: - Strict-mode semantics preserved. - Prices path is still deprecated but now robust. -
  Progress bar no longer appears to stall on deprecation logs.

- Cache.py Don't overwrite buildCache with cut and paste
  ([`2a3bcae`](https://github.com/eyeonus/Trade-Dangerous/commit/2a3bcaec0f3e388bb6c8d9dc276fd900461efa13))


## v12.0.4 (2025-10-29)

### Bug Fixes

- Cache.py - Not applying corrections (regression)
  ([`66886c1`](https://github.com/eyeonus/Trade-Dangerous/commit/66886c18e2a1e6eb6666b63499fd4c8400be71a2))

Instead of dropping rows, or quitting work, cache.py will again use corrections.py to fix up
  deprecated item names etc.


## v12.0.3 (2025-10-28)

### Bug Fixes

- We kinda need sqlalchemy to run this.
  ([`5182b0d`](https://github.com/eyeonus/Trade-Dangerous/commit/5182b0d703a662be990a2f004c35b80f0f5d935a))


## v12.0.2 (2025-10-28)

### Bug Fixes

- Ensure db_config.ini and data directories resolve relative to user cwd, not venv
  ([`4dee702`](https://github.com/eyeonus/Trade-Dangerous/commit/4dee702d4982ead98be4051b1cf56d38b5981f92))


## v12.0.1 (2025-10-27)

### Bug Fixes

- Update setup.py with new package & Python Version
  ([`e3608cd`](https://github.com/eyeonus/Trade-Dangerous/commit/e3608cd4729fd2ef1da77dc09031efb1ccb6b0d7))

Added 'tradedangerous.db' package. Adjusted Python version requirements and added support for Python
  3.11 and 3.12. Added minimum required Python 3.10


## v12.0.0 (2025-10-27)

### Chores

- Fix artifact error in workflow
  ([`08e2765`](https://github.com/eyeonus/Trade-Dangerous/commit/08e2765d3fa528ad4aa5772be3e738a1d806e864))

- Fix cache error in workflow
  ([`3042ec9`](https://github.com/eyeonus/Trade-Dangerous/commit/3042ec94d76f4ddce7ccf43840e9bc28c2e2f714))

- Fix python-semantic-release workflow error
  ([`0db870e`](https://github.com/eyeonus/Trade-Dangerous/commit/0db870ec1d433cba244be1093311fb05fe8f67c5))

- **cache**: Enforce canonical ORM import; remove AI numpty code
  ([`b8638d2`](https://github.com/eyeonus/Trade-Dangerous/commit/b8638d270987f19ea4ebba75d76b43d5bbadf3ce))

### Documentation

- Remove all maddavo
  ([`7748478`](https://github.com/eyeonus/Trade-Dangerous/commit/7748478e4a19cfff9973b9c6c23b159167e2c1d6))

- Update about.md (download site) and index.md (copyrights)
  ([`d3ff62b`](https://github.com/eyeonus/Trade-Dangerous/commit/d3ff62bf3b60bff4051d45c8b4563216f6af096c))

- Update issue templates
  ([`cdb5d7e`](https://github.com/eyeonus/Trade-Dangerous/commit/cdb5d7e032f2ffd37a9ccf595c63ba2ca7b3e41c))

bug reports now have a template to make things easier for myself

- Update minimum python version to 3.8
  ([`84a56f2`](https://github.com/eyeonus/Trade-Dangerous/commit/84a56f2cb7a7674d357ca7b8681dbe7ab7c62a5f))

Ubuntu no longer supports earlier versions, and Windows/MacOS users are unlikely to have such an old
  version as well, so it's not worth the headache to support it.

### Features

- Migrate TradeDangerous to SQLAlchemy from sqlite3
  ([`1a24983`](https://github.com/eyeonus/Trade-Dangerous/commit/1a2498355920b44b9e91251b81b96a60ba8b277a))

Update CHANGES_SQLA.md to reflect completion of ORM migration.

BREAKING CHANGE: replaces all direct sqlite3 calls with SQLAlchemy, breaking legacy plugin
  compatibility

### Refactoring

- **cache**: Migrate to SQLAlchemy adapter and validate with real backend smoke test
  ([`b34d2d8`](https://github.com/eyeonus/Trade-Dangerous/commit/b34d2d827da6b6fa954dbd62ed812b1ce7bc7d91))

### Testing

- Add sanity_check.txt
  ([`a289977`](https://github.com/eyeonus/Trade-Dangerous/commit/a289977d63568c6eb7bcbdb0b6a55cc7921ced7a))

### Breaking Changes

- Replaces all direct sqlite3 calls with SQLAlchemy, breaking legacy plugin compatibility


## v11.5.3 (2025-01-30)

### Bug Fixes

- Update `trade import` help message
  ([`7fdba6e`](https://github.com/eyeonus/Trade-Dangerous/commit/7fdba6ed775628e6698f229cf881df79d02f99ac))

Updated `trade import --help` message with Tromador's server address.

### Chores

- Remove py37 from testing
  ([`bd66c6c`](https://github.com/eyeonus/Trade-Dangerous/commit/bd66c6c585f8348d1fb29b9dc331ff153f91e7de))

Ubuntu no longer supports it, so the tests fail when py37 can't be installed.

### Refactoring

- Remove DB changes
  ([`12f2adb`](https://github.com/eyeonus/Trade-Dangerous/commit/12f2adbff64d2b016dec6baa0e092debd1455bac))

Two versions should be long enough that everyone's DB has been updated, no need to have this
  anymore. If errors encountered, run eddblink with the `clean` option.


## v11.5.2 (2024-06-15)

### Bug Fixes

- Spansh- fix overzealous download
  ([`5a8dd2a`](https://github.com/eyeonus/Trade-Dangerous/commit/5a8dd2a3676c48fd95c73ca1dbc72e098428960d))

spansh plugin now will not download the source file if the source has not been modified more
  recently than the local copy downloaded previously if the source file has been modified more
  recently, it is downloaded, overwriting the local copy, if any


## v11.5.1 (2024-06-14)

### Bug Fixes

- Can't change if doesn't exist yet
  ([`59512b0`](https://github.com/eyeonus/Trade-Dangerous/commit/59512b0a61565bbe3164a4cfbfc72983b07a20cb))


## v11.5.0 (2024-06-11)

### Chores

- Fix Path error
  ([`5f5db6e`](https://github.com/eyeonus/Trade-Dangerous/commit/5f5db6e05ed911ea89cbb51ac8ca0dadf9c1572c))

### Code Style

- Fix white-space
  ([`c07eb91`](https://github.com/eyeonus/Trade-Dangerous/commit/c07eb912ba092e39d7f24c07e0b048eb9f0522dc))

- Whitespace edits
  ([`9f6c2b6`](https://github.com/eyeonus/Trade-Dangerous/commit/9f6c2b6b1a6384ac38df4a5e376babed2e5a660b))

### Features

- Include more tables in spansh import
  ([`da1ee03`](https://github.com/eyeonus/Trade-Dangerous/commit/da1ee0324744294f8f26e7ddef2f4dfa8d9352c8))

Added processing spansh source for Ship, ShipVendor, Upgrade, and UpgradeVendor tables.

### Refactoring

- `ingest_stream()` -> `self.ingest_stream()`
  ([`0f18d10`](https://github.com/eyeonus/Trade-Dangerous/commit/0f18d10e4039f63c7f38e4593e9f7eeb9df912b4))

- Accurate progress bar
  ([`293c35b`](https://github.com/eyeonus/Trade-Dangerous/commit/293c35b34631767afce43325c018f106416c4f92))

- Accurate progress bar
  ([`a90a216`](https://github.com/eyeonus/Trade-Dangerous/commit/a90a216ff2c6f386d7801d68a6b6ddc54e948455))

- Correct `get_timings()` return hint
  ([`beeaea7`](https://github.com/eyeonus/Trade-Dangerous/commit/beeaea7fd0cb3bbb39b910afc3535cae3617220f))

- Correct `load_known_stations` return hint
  ([`0eaed90`](https://github.com/eyeonus/Trade-Dangerous/commit/0eaed909f1da4238dc3417abaebd73a4b0096e5d))

- Include system name in "updated"/"added" logs
  ([`4e403fe`](https://github.com/eyeonus/Trade-Dangerous/commit/4e403fef24c002f0953f0894fde8fed88f2f91ea))

#177

- Move eddblink_plug downloads to ./tmp
  ([`dee11c2`](https://github.com/eyeonus/Trade-Dangerous/commit/dee11c23738347329a46db23460b9b549345ad8f))

- Output sample system json if debug
  ([`3688683`](https://github.com/eyeonus/Trade-Dangerous/commit/36886837472d24f513fce6485ae94131fedb5341))

The entire galaxy_stations.json is too big and unwieldy to look at directly, so turning on debug
  will output only the `Shinrarta Dezhra` system to `./tmp/shin_dez.json`, making it much easier to
  see the data structure, and since `Jameson Mermorial` has all the things, we can also use it to
  check those things against the DB.


## v11.4.0 (2024-05-12)

### Documentation

- Remove Merge line from changelog
  ([`02ac0c6`](https://github.com/eyeonus/Trade-Dangerous/commit/02ac0c6eada715c127555837fde7dd9df2213539))

### Features

- Add `--maxage` to `sell` command
  ([`ab34568`](https://github.com/eyeonus/Trade-Dangerous/commit/ab34568ba1bdd4aca5f236595f0c519d0f8e0f64))


## v11.3.0 (2024-05-06)

### Bug Fixes

- Progress bar display/updates and linting
  ([`ec94c0b`](https://github.com/eyeonus/Trade-Dangerous/commit/ec94c0b18efd1ea2f2324f67d01de6260e790099))

- advance progress bars properly, - actually display the text of the progress bar, duh

- Python version <3.9 does not support parenthesized context expressions
  ([`aab81db`](https://github.com/eyeonus/Trade-Dangerous/commit/aab81dba2b4364c5a5bb954602182c26927b9c31))

### Chores

- Fix linting error about collections.abc
  ([`1358479`](https://github.com/eyeonus/Trade-Dangerous/commit/1358479c766bae220d6df748505506db21281c5e))

### Features

- Better eddblink progress reporting
  ([`f3af244`](https://github.com/eyeonus/Trade-Dangerous/commit/f3af244d6940a2394b4b05725c412b1f1a0796da))

- small tweaks to improve performance of eddblink import, - commit batching to try and improve
  eddblink import speed, - use rich progress bars to give better insight into commit rate

one interesting thing to try is to change the progress bar description around the COMMIT while
  importing prices:

``` prog.increment(description="COMMIT") cursor.execute("COMMIT") transaction_items = 0
  cursor.execute("BEGIN TRANSACTION") prog.increment(description="Processing") ```

and then adjust the batch size. when batchsize is too low, this makes the description flicker, but
  you can get a sense for how increasing the batch size reduces the total import time until the
  amount of memory/wal etc starts to make the commit time excessively long

- Database schema update
  ([`32a7db1`](https://github.com/eyeonus/Trade-Dangerous/commit/32a7db15ffd041d9b47463d54c4f7e87b3f08651))

- Remove ROWID from Station table to improve performance, - Introduce StationDemand and
  StationSupply tables for breaking up StationItem, - Reduce size of station/system index,

- Nicer transfer progress bars
  ([`bd4738a`](https://github.com/eyeonus/Trade-Dangerous/commit/bd4738a497ebd121fa9b3bfda42cde61a0843144))

uses the new rich-based progress bars to display download speed information etc.

- Rich progress bars
  ([`156904b`](https://github.com/eyeonus/Trade-Dangerous/commit/156904b9eca9c3090873dba787914fae2a98a6f2))

This introduces an enhancement over the old progress bars, using rich to provide colorful, live
  bars. Base types for skinning them are included.

- Swap out homebrew progress bars for Rich
  ([`52bb7f4`](https://github.com/eyeonus/Trade-Dangerous/commit/52bb7f456990a047b0292198d40b3b29ebc0e8d9))

- make bars hideable, - polish, - default the progress bar to visible, require show=False
  explicitly. - add more bar styles, - use some of the bars,

### Refactoring

- Make transfers use the rich bars properly.
  ([`ca12c5f`](https://github.com/eyeonus/Trade-Dangerous/commit/ca12c5fdf18e762da59de45fa18456b6060d69df))

- Move file_line_count into fs
  ([`8a9989b`](https://github.com/eyeonus/Trade-Dangerous/commit/8a9989be17cdd0e578d9bfff40b8a96e2850e91a))


## v11.2.1 (2024-05-06)

### Bug Fixes

- Linter warnings from moving the shebang from line 1
  ([`73d4a0d`](https://github.com/eyeonus/Trade-Dangerous/commit/73d4a0d25a633b6cd622459369b8ca9ef044f83a))

- Multiple options to --pad-size and others was no-longer working
  ([`f69dffd`](https://github.com/eyeonus/Trade-Dangerous/commit/f69dffd66c7c0e2f0b0acb7227bf9d96a9d380fd))

### Refactoring

- Simplify the system-purge operation to not copy/move data and abuse the db
  ([`ab75113`](https://github.com/eyeonus/Trade-Dangerous/commit/ab75113ed910ad1301e60376ed0f3d4ae8de6891))


## v11.2.0 (2024-05-05)

### Chores

- Additional deprecation
  ([`93d91c9`](https://github.com/eyeonus/Trade-Dangerous/commit/93d91c9ab48e1268e0a0448efd52d85f0532a072))

For #157

- Fix github actions cache warnings
  ([`fda2c26`](https://github.com/eyeonus/Trade-Dangerous/commit/fda2c26ca259cc7fc885ce7f5707ebb516ea6830))

I'd used an older github actions of mine as a basis for the cache blocks, and they referenced an
  out-of-date cache version.

contributes to #147

### Documentation

- Fix help message for trade command
  ([`a6ca423`](https://github.com/eyeonus/Trade-Dangerous/commit/a6ca4231049cd1b028daae27081fe9e2baf484f6))

### Features

- Add rename_file and remove_file to TradeEnv
  ([`778278d`](https://github.com/eyeonus/Trade-Dangerous/commit/778278db89964f38c92740b6be9868b361406be5))

This adds normalizing methods for removing and renaming files that will log the operation at DEBUG1,
  and in the case of rename will ensure a .old backup of the existing file.

Committing separately of other work that leverages it.

- Enable repeat http requests over a single session
  ([`8039aab`](https://github.com/eyeonus/Trade-Dangerous/commit/8039aab384285793d246040d06276117b1e08cf9))

If we need to make multiple requests to a single http server, we have to repeat the overhead of
  connection-tear up which can be significant for a remote https connection. 'requests' solves for
  this by letting you create a 'Session' object that uses http keep-alive to send followup requests
  over an existing connection.

Commiting this separately from changes that make use of it.


## v11.1.6 (2024-05-01)

### Bug Fixes

- Not using fdev_id for ships, as internal id is same now
  ([`38e4ac9`](https://github.com/eyeonus/Trade-Dangerous/commit/38e4ac9c8e66640615dad863e64008841bc253d2))

Fixes #152

- Typo caused buy command to error
  ([`f016cec`](https://github.com/eyeonus/Trade-Dangerous/commit/f016cec41f5ced2b18bd682b1e2fee0d00457d8a))

- the code that should render the Average line at the end of a buy report had a typo that caused a
  string to become a list of strings, and the subsequent code could not handle that.

### Chores

- Mark deprecated code
  ([`2afd5d6`](https://github.com/eyeonus/Trade-Dangerous/commit/2afd5d67fbf299f7121c01b43f72f315584fc875))

For #157


## v11.1.5 (2024-05-01)

### Bug Fixes

- Parse the dates in a locale-agnostic manner
  ([`1743f9f`](https://github.com/eyeonus/Trade-Dangerous/commit/1743f9f2609105b604e9db48b8df1a8973eb8c6c))

fixes #149

### Documentation

- Correct web page
  ([`f71dca3`](https://github.com/eyeonus/Trade-Dangerous/commit/f71dca3b1d8a98edc5b5adf7964b56473b87e088))


## v11.1.4 (2024-04-30)

### Bug Fixes

- Fix linter errors in trade.py
  ([`f8effe4`](https://github.com/eyeonus/Trade-Dangerous/commit/f8effe482b96017fd291316e93a3e30495bb9688))

- Fix linter paths to trade.py and tradegui.py
  ([`d6f92cc`](https://github.com/eyeonus/Trade-Dangerous/commit/d6f92ccc502a008584c8fe3cab5180def0c5cf60))

### Chores

- Don't try to publish if you're not the bossmang, sassa
  ([#145](https://github.com/eyeonus/Trade-Dangerous/pull/145),
  [`dce2563`](https://github.com/eyeonus/Trade-Dangerous/commit/dce2563ac0dac7ebd6248802bb814ec89088c860))

* chore: lint fixes

* chore: only try to publish from eyeonus repos

fixes #134

This makes the publish job dependent on being the eyeonus repository. It also moves the requirements
  files into the top-level directory and organizes them into requirements, requirements-dev, and
  requirements-publish which incrementally reference the previous requirements file to simplify
  them.

It's unusual for requirements*.txt to be in a subdirectory these days, and various tools are lazy
  about it, which can make these chained-references problematic as some tools will intepret them
  relatively and some won't; ergo having them in the tld together is less likely to suddenly not
  work one day.

---------

Co-authored-by: Jonathan Jones <eyeonus@gmail.com>

### Documentation

- Changelog.md cleanup
  ([`2885059`](https://github.com/eyeonus/Trade-Dangerous/commit/28850597e90126d02890ec55768393f60014907f))

- More CHANGELOG cleanup
  ([`77c54b0`](https://github.com/eyeonus/Trade-Dangerous/commit/77c54b0926eda542b5d9a99e5615ccc345f8d23d))

### Refactoring

- Use the rfc-correct Accept-Encoding
  ([`6c31521`](https://github.com/eyeonus/Trade-Dangerous/commit/6c3152110e03a3fb1ae6e4d766ed5916e4e23bf5))


## v11.1.3 (2024-04-29)

### Bug Fixes

- Eddblink retrieval (progress, bandwidth)
  ([#144](https://github.com/eyeonus/Trade-Dangerous/pull/144),
  [`af5b993`](https://github.com/eyeonus/Trade-Dangerous/commit/af5b9938b6b15334f6539a94b32d7db216a050df))

- reduce the amount of data transferred to determine if there is new eddblink data, previously we
  were downloading each file twice roughly, - capture the uncompressed file-length during the probe,
  so we can show the user an accurate progres bar

Co-authored-by: Jonathan Jones <eyeonus@gmail.com>


## v11.1.2 (2024-04-29)

### Bug Fixes

- Assume stations with unknown type are Fleet Carriers
  ([`aa9cad1`](https://github.com/eyeonus/Trade-Dangerous/commit/aa9cad12b0b77e0cf5291f8eab4ed9e4658f6b95))

- Don't assume machine has 'en_US.UTF-8' installed.
  ([`b3a1e29`](https://github.com/eyeonus/Trade-Dangerous/commit/b3a1e291b6bf7f5648a81b375fc7cdd80ede184c))

- Locale-dependant strptime()
  ([`8cd5ede`](https://github.com/eyeonus/Trade-Dangerous/commit/8cd5edef43621ace16f9e2cc850952c9a9ab0a4f))

- No '.UTF-8' on windows
  ([`aee07ef`](https://github.com/eyeonus/Trade-Dangerous/commit/aee07efd63e68cb5ce4e39edc4c55c73b0ad9676))


## v11.1.1 (2024-04-28)


## v11.1.0 (2024-04-27)

### Bug Fixes

- Commit before processPrices, only close tempDB if no prices file
  ([`5a421bd`](https://github.com/eyeonus/Trade-Dangerous/commit/5a421bda45d43b33eeec0c33bf921dccf396e6c9))

### Features

- Add --age to buy command
  ([`fbf6c47`](https://github.com/eyeonus/Trade-Dangerous/commit/fbf6c476bf6ea7f2d187099f56d3b7152a68d1c3))

fixes #136


## v11.0.6 (2024-04-27)

### Bug Fixes

- Linter errors in jsonprices.py
  ([`193b34e`](https://github.com/eyeonus/Trade-Dangerous/commit/193b34eab862f915f1d737f633e5d7ab8eb46e97))

- Missing f-string prefix
  ([`390e00a`](https://github.com/eyeonus/Trade-Dangerous/commit/390e00a8604ad8d5f7a63021bbe1a2205c49c887))

running build-cache without force printed the mustached text rather than the path it was supposed to

### Refactoring

- Mark scripts as deprecated
  ([`b976088`](https://github.com/eyeonus/Trade-Dangerous/commit/b976088573b393855261bb6ccfaf21999bf865f5))

jsonprices.py and submit-distances.py appear to be unused and unworkable, so mark them as deprecated
  in order to remove them soon.


## v11.0.5 (2024-04-27)

### Bug Fixes

- Update Station info when source timestamp newer
  ([`fa63e94`](https://github.com/eyeonus/Trade-Dangerous/commit/fa63e94a106088d28292a79829131cf938be34bc))

### Refactoring

- Move entry points to top level
  ([`100e417`](https://github.com/eyeonus/Trade-Dangerous/commit/100e4179c77ceed40cab5b0f88b6f06c8b7e5846))

fixes #137


## v11.0.4 (2024-04-26)

### Bug Fixes

- From_live calculation
  ([`631758c`](https://github.com/eyeonus/Trade-Dangerous/commit/631758cc37f1b64711760ba341b937d535298e8e))

Need to include `self.dataPath` or it will always return False, which is not what we want.

### Documentation

- Update comments, method annotations to be accurate
  ([`87c74ba`](https://github.com/eyeonus/Trade-Dangerous/commit/87c74bad86ad6a0d05ccaf9533d8ec9de0cf2b6b))

### Performance Improvements

- Improve eddb import performance.
  ([`7716bf2`](https://github.com/eyeonus/Trade-Dangerous/commit/7716bf2e492111874dddfb1a3584c00daf5d5464))

small tweaks, but it redunce time to import the listings on my machine from 40 minutes to 23

### Refactoring

- `request_url()` to `_request_url()`
  ([`2b0d5dc`](https://github.com/eyeonus/Trade-Dangerous/commit/2b0d5dc33da5a4954d2f840ca049686528ccffc2))

Have all the methods external to the class have matching naming convention

- Add `purge` to options prevent enabling default options
  ([`18782be`](https://github.com/eyeonus/Trade-Dangerous/commit/18782be674d6d5bf87a34ee38193b42248446695))

- Clear progbar, do final commit, etc., after closing file
  ([`9b21109`](https://github.com/eyeonus/Trade-Dangerous/commit/9b211092a8e167f42c7e6f28c2795f18b6286960))

- Fix pylint warnings
  ([`61c159a`](https://github.com/eyeonus/Trade-Dangerous/commit/61c159a4b15fd74088ec743a908aa7af21c20aef))

- Remove unused methods, use db.* rather than self.*
  ([`5e4a9de`](https://github.com/eyeonus/Trade-Dangerous/commit/5e4a9ded335a660402b38dbe170b0b1ccac85722))

Don't use self.execute() or self.commit() in some cases and db.execute() or db.commit() in others,
  use db.* in all cases.

### Testing

- Extend tox coverage with pylint and cleanup various pylint findings to make that useful
  ([`9b4e91c`](https://github.com/eyeonus/Trade-Dangerous/commit/9b4e91cf21e87f6f985e7cefdfae4b1708c2cf0a))


## v11.0.3 (2024-04-26)

### Bug Fixes

- Issue#130: lowercase cmd options
  ([`fd2370b`](https://github.com/eyeonus/Trade-Dangerous/commit/fd2370b3733d16ce9e3ec82c0b014c15cf0eb8e6))

### Refactoring

- Requests is installed by requirements, don't need code to faff with it
  ([`48c0382`](https://github.com/eyeonus/Trade-Dangerous/commit/48c0382ec0149febac279ac8dd75409677d487e5))


## v11.0.2 (2024-04-24)

### Bug Fixes

- Check for existence of the DB itself
  ([`3dee4cb`](https://github.com/eyeonus/Trade-Dangerous/commit/3dee4cb3aeaf0810d6565f4aee00284f292a3c6e))

The plugins don't export the prices cache anymore, so that's a bad thing to check for to determine
  if the DB needs to be built.

Do the smart thing and check for the existence of the actual DB file itself.


## v11.0.1 (2024-04-24)

### Bug Fixes

- Don't enable default options if `prices`
  ([`3302fa5`](https://github.com/eyeonus/Trade-Dangerous/commit/3302fa515a4238190a647b43e331b16b6cac1640))

revert: use the `newItemPriceRe` that works


## v11.0.0 (2024-04-24)

### Bug Fixes

- Improve compressed download progress bars
  ([`1801216`](https://github.com/eyeonus/Trade-Dangerous/commit/180121632b386bf5994dbf82ab81b11e155154c9))

when downloading a large and extremely compressed file, user feedback would stop after we had
  received an uncompressed amount of data equal to the compressed size of the data.

Downloading the spansh galaxy data, for example, only transfers 1.5GB of data after compression, but
  the file itself expands to over 9GB, resulting in the progress bar sticking at 1.5GB and looking
  as though it has failed/hung.

- Overridable timeout transfers w/sane default
  ([`3687a6b`](https://github.com/eyeonus/Trade-Dangerous/commit/3687a6b689b0eead480213a20026e1e4225e8831))

5 minutes was a bit long, 90s seems more reasonable tho it could probably go as low as 30.

### Features

- 'prices' option in spansh and eddblink
  ([`257428a`](https://github.com/eyeonus/Trade-Dangerous/commit/257428aded8962b2a85920188e14525aa0d72863))

spansh and eddblink plugins no longer regenerate the `TradeDangerous.prices` cache file by default

The cache file is used to rebuild the database in the event it is lost, corrupted or otherwise
  damaged.

Users can manually perform a backup by running eddblink with the 'prices' option. If not other
  options are specified, eddblink will only perform the backup

If any other options are specified, eg. `-O listings,prices`, eddblink will perform the backup after
  the import process has completed.

- 'prices' option in spansh and eddblink
  ([`2e1fe85`](https://github.com/eyeonus/Trade-Dangerous/commit/2e1fe85449144c684810d815f835e73124d8ed77))

spansh and eddblink plugins no longer regenerate the `TradeDangerous.prices` cache file by default

The cache file is used to rebuild the database in the event it is lost, corrupted or otherwise
  damaged.

Users can manually perform a backup by running eddblink with the 'prices' option. If not other
  options are specified, eddblink will only perform the backup

If any other options are specified, eg. `-O listings,prices`, eddblink will perform the backup after
  the import process has completed.

- Multiple improvements from kfsone
  ([`7c60def`](https://github.com/eyeonus/Trade-Dangerous/commit/7c60def3c9465a44b368d624d00f78f03d48a9c9))

* chore: increase the line limit in the .editorconfig

* chore: relax tox warnings by disabling spaces-after-:

* refactor: Cleanup pass on cache and spansh_plug

- introduce type annotations, - Small performance considerations,

* refactor: flake and pylint rules

- ignore warnings that are overly opinionated for our needs, - tell pylint to quit complaining about
  lines > 100

* fix: ensure db gets closed before trying to rename it.

* perf: modernize small performance factors in spansh

- lookup systems and stations by id rather than name, - move several 'is it registered' tests out of
  ensure_ methods so we can avoid calling the method if there is no work to do (calling a function
  in python is expensive) - fix ingest_stream looking up body ids rather than system ids

* chore: remove vestigial numpy stuff that annoyed linters

I couldn't see any evidence of this code still being useful.

* chore: move uprint into a mixin

tradeenv was already hard enough to read, but the utf8 wrapping of uprint made it worse, and less
  pythonic.

this change moves the io behavior into a base Mixin class, then provides the non-utf8 variant as an
  optional override mixin. finally, we do a simple if on which one to use as the favored
  implementation to mixin to TradeEnv.

This should be far more readable to both humans and linters etc. At least, on my machine, PyCharm
  no-longer catches fire. (* it's possible that it never caught fire and that I just ate an overly
  hot chilli last night, but who are we to question the universe? not deflecting enough, well LOOK A
  SQUIRREL)

* chore: appease the gods of pylint

pylint gives deeper code warnings than flake8 can, but is slower and more spammy.

* chore: change terribly misnamed 'str' to 'text'

* chore: tox/pylint: now we've appeased, lets ask for more

this will enable some more useful pylint warnings/messages, and also making it think a little harder
  about others so they're more useful.

* feat: introduce theming in tradeenv

two fold reasoning: 1- so people can opt out of any kind of decoration if it becomes
  inconvenient/problematic, 2- localization and style

In particular: the colors people want for light-vs-dark background terminals might vary, and this
  would make it easy to switch; second, this makes it possible to configure various strings to be
  localizable through the theme.

The demo-case included here is that when you use --color the word "NOTE" will be replaced with the
  "information-source" emoji and the word "WARNING" will be replaced with a warning-symbol emoji,
  the '#' for bugs will be replaced with a bug emoji.

* chore: cleanup/performance tradedb.py

this eliminates some dead methods, and switches some of the math operations to their favored
  modern-python/performant/64-bit versions

specifically:

%timeit 2 ** 2 94ns %timeit 2 * 2 24ns

Also, when I originally feared math_sqrt vs ** it was probably because I didn't realize that
  "math.sqrt" was having to lookup math and sqrt each time it was called, duh.

* feat: spansh import presentation

- Adds Progresser to spansh_plugin as an experimental ui presentation layer using rich, -- active
  progress bars with timers that run asynchronously (so they shouldn't have a significant
  performance overhead), -- opt-out to plain-text mode incase it needs turning off quickly, -
  present statistics with the view to give you a sense of progress, - small perf tweaks

* style: blank lines have same indent as following non-blank line

* fix: Use same supply/demand levels as before

* fix: having the fdev_id listed as a unique column causes dump prices to break.

* refactor: tox was configured to give flake8 its own environment

The idea is that flake8 is really fast, so you give it it's own environment and it comes back and
  says "YA MADE A TYPO OLIVER YA DID IT AGAIN WHY YOU ALWAYS..." *cough*, sorry, anyway.

I usually run tox one of two ways:

``` tox -e flake8 # for a quick what-did-I-type-wrong check tox --parallel # run em all, but, like,
  in parallel so I don't retire before you finish ```

* test: flake8 appeasement

turning on flake8 made linters very shouty

* refactor: tox.ini

flake8 now runs its own environment that is JUST flake8 so it's fast, it doesn't install the package
  for itself; added lots of flake8 ignores for formatting issues I'm unclear on

* chore: flake8 warnings

added a lot more ignores and some file-specific ignores, but generally got it to a point where
  flake8 becomes proper useful.

* chore: fix all the tox warnings

This fixes all of the tox warnings that I haven't disabled, and several that I did.

* chore: bump pylint score up to 9.63/10

fixed a few actual problems while I was at it.

* fix: formatting needs __str__ methods

When I first created the 'str' methods, it was because I wanted a display name but repr and str both
  confused me at the time; I've now renamed it text but apparently I forgot that in Py2.x def str()
  worked like __str__...

* refactor: use ijson instead of simdjson to reduce memory use in big imports

* refactor: logic reversal for plugin option handling

* fix: presentation was a bit wonky with doubled progress bars

---------

Co-authored-by: eyeonus <eyeonus@panther>

Co-authored-by: Jonathan Jones <eyeonus@gmail.com>

- Multiple improvements from ksfone
  ([`31bcb4f`](https://github.com/eyeonus/Trade-Dangerous/commit/31bcb4f78e7e3d0daafb7eef2d69c84fd6762f87))

BREAKING CHANGE: semantic release thinks we're on 10.16.7 rather than 10.17.0, and these are a lot
  of improvements, so bump to 11.0.0

- Multiple improvements from ksfone
  ([`c63e757`](https://github.com/eyeonus/Trade-Dangerous/commit/c63e7570f793849f151367e7e01f8a04c1baca5e))

### Breaking Changes

- Semantic release thinks we're on 10.16.7 rather than 10.17.0, and these are a lot of improvements,
  so bump to 11.0.0


## v10.16.17 (2024-04-24)

### Bug Fixes

- No such file or directory error
  ([`3bf1167`](https://github.com/eyeonus/Trade-Dangerous/commit/3bf1167e08ba0c68f89b2ad5a17a36ae1c34fade))

listings_path, not listings_file


## v10.16.16 (2024-04-24)

### Performance Improvements

- Reduce the time to load large listing files etc by a factor of 4:
  ([`ff7a57b`](https://github.com/eyeonus/Trade-Dangerous/commit/ff7a57b9eea46e1cec8fa24124d78f74581bb057))

https://gist.github.com/kfsone/dcb0d7811570e40e73136a14c23bf128


## v10.16.15 (2024-04-24)

### Performance Improvements

- (eddblink) get the timestamp for all station commodities at once
  ([`6c7b8d7`](https://github.com/eyeonus/Trade-Dangerous/commit/6c7b8d73bb382f07e4281b3ad5079c5a9e506157))

Do one SQL query before processing the listings file to get every timestamp, rather than doing a SQL
  query for the timestamp on each individual listing as we come to it.

This cuts the number of SQL statements being made during processing -- and thus the time taken to
  process -- roughly in half.


## v10.16.14 (2024-04-23)

### Bug Fixes

- Excessive RAM usage on eddblink listings import
  ([`91a71c0`](https://github.com/eyeonus/Trade-Dangerous/commit/91a71c075d352cae91bc9cf6e5f9659cc88b2dcd))

fixes #125

Instead of building a list during processing of the listings file (which uses a *lot* of RAM on
  large source files) and updating the DB after processing, update the DB as each line is processed.

This keeps RAM usage very low, especially in comparison.

### Refactoring

- Make skipping station message more clear
  ([`3434b53`](https://github.com/eyeonus/Trade-Dangerous/commit/3434b53b821f0f9d7791004066ebb2da89e46982))

- Removed unneeded loading of DB
  ([`532342e`](https://github.com/eyeonus/Trade-Dangerous/commit/532342e68c7222cf9d431ed75e4f53098f0a310f))


## v10.16.13 (2024-04-22)

### Bug Fixes

- Remove fdev_id from Ships
  ([`8a67162`](https://github.com/eyeonus/Trade-Dangerous/commit/8a67162571e6dfd706b7be056d75529208f8f471))

### Refactoring

- Load DB after doing rebuild rather than before.
  ([`aaabdd1`](https://github.com/eyeonus/Trade-Dangerous/commit/aaabdd19eb395ce1f3b9f3a89789acccf23363ec))


## v10.16.12 (2024-04-22)


## v10.16.11 (2024-04-22)

### Bug Fixes

- Don't generate StationItem table
  ([`5d50c84`](https://github.com/eyeonus/Trade-Dangerous/commit/5d50c843e9dbfe44bbe8a09aeb5033b1a7ada043))

It's just a bad idea, even if it didn't break things because csvexport doesn't know what to do with
  two unique keys in the same table.

- Release lock on DB before rebuilding
  ([`031eb51`](https://github.com/eyeonus/Trade-Dangerous/commit/031eb51515371ff9e42e37c226619059a9c48f03))

fixes #123

### Chores

- Add rich to install_requires in setup.py
  ([`5822a4c`](https://github.com/eyeonus/Trade-Dangerous/commit/5822a4c853602d94e7b7e621145276cc069f66ab))

Will automatically install rich module if needed when installing TD via pip

- Additional IDE folders added to .gitignore
  ([#120](https://github.com/eyeonus/Trade-Dangerous/pull/120),
  [`79db6f1`](https://github.com/eyeonus/Trade-Dangerous/commit/79db6f1e7f3acad3e37c3913ba1311364723a55a))

- Tox test environments needs to require the packages that tradedangerous is going to be depending
  on ([#122](https://github.com/eyeonus/Trade-Dangerous/pull/122),
  [`1e15bbf`](https://github.com/eyeonus/Trade-Dangerous/commit/1e15bbf000c05bc57a57aea3a1e33192d038ae11))

The tox testenv's need to import the same set of packages as dependencies that trade is going to
  want. using "-r requirements/dev.txt" tells it to do this.

I also added "flake8" as an env so that you can use tox to get flake results with tox -e flake8; the
  value there is that you get apples-to-apples. I hate running flake in my ide / vim and then tox
  has a slightly different config :)

### Refactoring

- Account for FDevShipyard and FDevOutfitting changes
  ([`5eae43d`](https://github.com/eyeonus/Trade-Dangerous/commit/5eae43da8154b3e9d6a5aeb6e726c750b8418a1e))

FDevShipyard now has entitlements, and FDevOutfitting has entitlements that are more than 10 char
  long, .sql updated to reflect these changes.

Changes will automatically take effect when eddblink is run after upgrading to this version.

correct eddblink plugin to download the source for both to the correct location.


## v10.16.10 (2024-04-22)

### Bug Fixes

- "database image malformed" error in eddblink
  ([`67b2410`](https://github.com/eyeonus/Trade-Dangerous/commit/67b24103fbff47cd24684e398ea5636cce946c8a))

caused by self.commit() method, which isn't actually needed

- Make downloaded file have correct timestamp
  ([`b34ba66`](https://github.com/eyeonus/Trade-Dangerous/commit/b34ba6663437b77b5c57199c043e485743bea74f))

force the modification time to be that of the timestamp from the server, because the downloaded file
  will have a different timestamp based on the time it was created


## v10.16.9 (2024-04-21)

### Bug Fixes

- The actual problem is there is self.updated anymore
  ([`8f0b3ba`](https://github.com/eyeonus/Trade-Dangerous/commit/8f0b3ba180bdf98d5861ac142521356bc0fcfc9b))

Switched to checking if listings option is set instead.


## v10.16.8 (2024-04-21)

### Bug Fixes

- Mysteriously appeared "Listings" should be "listings"
  ([`0153410`](https://github.com/eyeonus/Trade-Dangerous/commit/0153410cce05e14e270d77b4e52ba5e5482fc21f))


## v10.16.7 (2024-04-21)

### Bug Fixes

- Getoption(...), not getOption[...]
  ([`bcbc05f`](https://github.com/eyeonus/Trade-Dangerous/commit/bcbc05f74e6ca76cc54016ba2d49893d7947040c))


## v10.16.6 (2024-04-21)


## v10.16.5 (2024-04-21)

### Bug Fixes

- Use corrections DB when adding commodities
  ([`d070a7c`](https://github.com/eyeonus/Trade-Dangerous/commit/d070a7c7c1a7fe18995d34ffbbb223e1d5e1fb03))

### Performance Improvements

- Skip station if commodity in DB is not older
  ([`9560dc7`](https://github.com/eyeonus/Trade-Dangerous/commit/9560dc7647c363652cfa7f390cf41f914623512a))

Instead of checking all the commodities, skip the whole station if the first doesn't pass, because
  all commodities are always updated at the same time.

Also don't increment number of stations if commodities were skipped.

Also don't increment number of systems if all stations in it were skipped.


## v10.16.4 (2024-04-21)

### Bug Fixes

- Correct commodity count
  ([`b5d17b6`](https://github.com/eyeonus/Trade-Dangerous/commit/b5d17b6f2418da5244840a27c7732febf1064dd5))

fix: close DB when finished with import


## v10.16.3 (2024-04-21)

### Bug Fixes

- Don't crash when trying to perform unneeded commit
  ([`afce0e2`](https://github.com/eyeonus/Trade-Dangerous/commit/afce0e287acdace7d7bd24867ee10850f6f2beca))

### Refactoring

- Include FDevShipyard.csv and FDevOutfitting.csv
  ([`b2398cb`](https://github.com/eyeonus/Trade-Dangerous/commit/b2398cbedc992a4b9bffb10efc46bf4cf9a7d42d))


## v10.16.2 (2024-04-21)

### Bug Fixes

- Check for prices cache file, not db file
  ([`3be19bf`](https://github.com/eyeonus/Trade-Dangerous/commit/3be19bf7bf92e81578a0ce44df59af7e12243b75))

### Refactoring

- Use WAL and VACUUM
  ([`0a329ee`](https://github.com/eyeonus/Trade-Dangerous/commit/0a329ee9e5abfe2a892c6ff4298084c8d0e346bf))


## v10.16.1 (2024-04-21)

### Bug Fixes

- Copy Category.csv into data on new build
  ([`51a1964`](https://github.com/eyeonus/Trade-Dangerous/commit/51a19641b2f701d226efa687d89179c3a5667093))


## v10.16.0 (2024-04-21)

### Chores

- Remove eddblink test
  ([`c0b14fd`](https://github.com/eyeonus/Trade-Dangerous/commit/c0b14fdeeef807634e95f080e14f86c2e130f9ad))

### Features

- Spansh doesn't crash when run on new install
  ([`bad945c`](https://github.com/eyeonus/Trade-Dangerous/commit/bad945c86fea3ccc74787f5fd5f972c9dc99f1fd))

feat: spansh imports directly to database, rather than creating a .prices file and then importing
  that

fix: strip trailing whitespace from system and station names, if any, when pulling from the source

refactor: include station type for *all* stations, not just fleet carriers and odyssey settlements

refactor: determine if station is planetary based on station type, rather than assuming based on
  format of source file

refactor: use id provided by source for systems and stations when inserting new into DB, search for
  same by id instead of by name

refactor: eddblink now uses csv files from server instead of the old EDDB files that no longer exist

chore: include `Categories.csv` in templates


## v10.15.2 (2024-04-19)


## v10.15.1 (2024-04-19)

### Bug Fixes

- Fix formatting of station skip message
  ([`906227d`](https://github.com/eyeonus/Trade-Dangerous/commit/906227d74dda67fc4a51296372ea75eade95a8c8))

- Maxage errors if not set
  ([`3d7e330`](https://github.com/eyeonus/Trade-Dangerous/commit/3d7e33033b274a49bec63c61ab317c8fcfb2d011))

`float(null)` doesn't work, obviously, make sure to only cast to float is maxage has been set. Also
  make sure maxage is set before doing the math to see if a station should be skipped.

fix: Make sure the cache is updated if a system, station, or commodity was added to the DB.

fix: Use fdev_id as item_id when adding new commodity to the DB.

fix: Update the ui_order for commodities when a new one is added to the DB.

refactor: Use a better method for removing spaces from a prices file.


## v10.15.0 (2024-04-17)

### Features

- Add maxage option to spansh plugin
  ([`0063e12`](https://github.com/eyeonus/Trade-Dangerous/commit/0063e12d24fc72b5e2673a28956d5262371e8e8c))

By specifying maxage, any station from the source that is older than the age will be skipped. So if
  a full update was done using galaxy_stations.json on 13th May (which is updated every ~24 hours),
  doing a new update on 20th of May with a max_age of 7 will skip anything in the source that wasn't
  updated later than 13th May


## v10.14.4 (2024-04-15)


## v10.14.3 (2024-04-15)

### Bug Fixes

- Don't overwrite TradeDangerous.prices
  ([`2c5080b`](https://github.com/eyeonus/Trade-Dangerous/commit/2c5080b76d5e5c497a56fbb0de60f3e4ae204f93))

spansh import plugin now writes to `<TD_path>/tmp/spansh.prices` rather than overwriting the cache
  file, and automatically imports the resulting spansh.prices file when processing has completed,
  rather than asking the user to import it via the import dialog box.

Also added the `listener` option to the spansh plugin to forego the import when run from
  TD-listener.

- Download file when using spansh url option
  ([`f6e1a9a`](https://github.com/eyeonus/Trade-Dangerous/commit/f6e1a9aa59373cdbc200b008dddbd7f4bce07fb9))

If there is a connection error whilst streaming from the url, it results in a crash. Downloading the
  file first and then streaming from the local file instead results in a much more stable import
  process.


## v10.14.2 (2024-03-23)

### Bug Fixes

- Bump again
  ([`3cc5254`](https://github.com/eyeonus/Trade-Dangerous/commit/3cc5254a2bd5ed0ea354c394df0edeef9929af91))

- Bump version for pypi publication
  ([`e05853f`](https://github.com/eyeonus/Trade-Dangerous/commit/e05853ff0d12f5117bb4e94813cba4c779c285d9))

- Create pyproject.toml
  ([`bd54be8`](https://github.com/eyeonus/Trade-Dangerous/commit/bd54be86cbe0a967f8fee06a0e9b16b4d77f4ee8))

- Update publish.txt
  ([`1dc4031`](https://github.com/eyeonus/Trade-Dangerous/commit/1dc4031a4c9d3b31bdc06cb51f188387b1d4ea8f))

- Update pyproject.toml
  ([`c25e778`](https://github.com/eyeonus/Trade-Dangerous/commit/c25e778df27540420d40909831f3baf4e6012794))

- Update python-app.yml
  ([`0320312`](https://github.com/eyeonus/Trade-Dangerous/commit/0320312d1d1ae1c9023e690e7603e41d72b85997))

- Update python-app.yml
  ([`d523382`](https://github.com/eyeonus/Trade-Dangerous/commit/d5233828b405148acd8f3a28762e93c0896d0231))

- Update python-app.yml
  ([`15fa4ca`](https://github.com/eyeonus/Trade-Dangerous/commit/15fa4ca952754ce148e35ae02b69396b5b2608d6))

- Update python-app.yml
  ([`7e118a8`](https://github.com/eyeonus/Trade-Dangerous/commit/7e118a865fa2dd23ec7a6b1e8b79ce4c5e2d4aee))

- Update python-app.yml
  ([`39b2fbc`](https://github.com/eyeonus/Trade-Dangerous/commit/39b2fbcf242cb4d8a1d9d476ba9c8fbd2ef481c3))

- Update python-app.yml
  ([`890bba8`](https://github.com/eyeonus/Trade-Dangerous/commit/890bba87796cb636554b21a81f327f3ce118e527))

- Update python-app.yml
  ([`229db1f`](https://github.com/eyeonus/Trade-Dangerous/commit/229db1fec29dbc9196f0fb341596d67dd9977a9f))

- Update python-app.yml
  ([`b79a47b`](https://github.com/eyeonus/Trade-Dangerous/commit/b79a47b535d62863be7d2157aad1e8ee54b5fd73))

- Update python-app.yml
  ([`41962ef`](https://github.com/eyeonus/Trade-Dangerous/commit/41962efb685822f5c3dcf2e9a336dbcdc024e315))

- Update python-app.yml
  ([`c7141ca`](https://github.com/eyeonus/Trade-Dangerous/commit/c7141cab3cbc92fe995a27582f4e5dfd7c690c0f))

- Update python-app.yml
  ([`432631e`](https://github.com/eyeonus/Trade-Dangerous/commit/432631e1c1ec6acce4bdc2754ee0bcf869bdb1c3))

- Update python-app.yml
  ([`96c29bd`](https://github.com/eyeonus/Trade-Dangerous/commit/96c29bdbb884036ce96e0e67abc8d490f3ac83b2))

- Update python-app.yml
  ([`7a4ce3b`](https://github.com/eyeonus/Trade-Dangerous/commit/7a4ce3b19ada8dc1c2f76048d9d54428063e3f95))

- Update python-app.yml
  ([`46288d9`](https://github.com/eyeonus/Trade-Dangerous/commit/46288d9c535234259ee5f1501343972ad1d6678e))

- Update python-app.yml
  ([`d6b956c`](https://github.com/eyeonus/Trade-Dangerous/commit/d6b956c2b56ac7fc128c6725d9194a47ecb322dd))

- Update python-app.yml
  ([`85491b9`](https://github.com/eyeonus/Trade-Dangerous/commit/85491b923db25c8ca0f2914252b022c1efed9568))

- Update python-app.yml
  ([`45a420a`](https://github.com/eyeonus/Trade-Dangerous/commit/45a420ad817bc1566bb86146bef53f9b68771db7))

- Update python-app.yml
  ([`70a80a1`](https://github.com/eyeonus/Trade-Dangerous/commit/70a80a17b56de3cb989225c8a256525599d83d01))

- Update python-app.yml
  ([`69d3806`](https://github.com/eyeonus/Trade-Dangerous/commit/69d3806a6f0617316e723a136c454edbf8ee0dc4))

- Update python-app.yml
  ([`482462d`](https://github.com/eyeonus/Trade-Dangerous/commit/482462d55ccfb673a8ea765684d9fd693a1631d0))

- Update python-app.yml
  ([`563d447`](https://github.com/eyeonus/Trade-Dangerous/commit/563d447252c53e738f62afacfe65b1d7dea4b816))

- Update python-app.yml
  ([`94f5e3d`](https://github.com/eyeonus/Trade-Dangerous/commit/94f5e3d14fd365482a0a48eed43a1dbac434734e))

- Update python-app.yml
  ([`5d098fb`](https://github.com/eyeonus/Trade-Dangerous/commit/5d098fbcd0a5de9f0162fe6d9f4a3b60dc27217c))

### Refactoring

- Update publish.txt
  ([`d8ae0b7`](https://github.com/eyeonus/Trade-Dangerous/commit/d8ae0b76409d77bec68069080bba90bcc798e337))


## v10.14.1 (2024-03-18)

### Bug Fixes

- Remove incorrect cast to boolean for the modified timestamp values
  ([#118](https://github.com/eyeonus/Trade-Dangerous/pull/118),
  [`6f2027a`](https://github.com/eyeonus/Trade-Dangerous/commit/6f2027aefbf2210821358cfcb4eae8a2f8375452))

also include distance from star from stations


## v10.14.0 (2024-03-17)

### Features

- Plugin to ingest pricing data from https://downloads.spansh.co.uk/galaxy_stations.json
  ([`7dd32b5`](https://github.com/eyeonus/Trade-Dangerous/commit/7dd32b514d6aa88368e2648565410998005a02f1))

* fix station name matching

sqlite's `upper()` function doesn't support non-ascii characters, so letters like "ñ" do not get
  capitalised correctly. move that transform to the python side, which has full unicode support

* feat: plugin to ingest pricing data from https://downloads.spansh.co.uk/galaxy_stations.json


## v10.13.10 (2023-02-13)

### Bug Fixes

- Make gui work again
  ([`f0a95c3`](https://github.com/eyeonus/Trade-Dangerous/commit/f0a95c3950783c6377df0c0ef3fce0f24769c4c9))


## v10.13.9 (2022-12-27)

### Bug Fixes

- Make tox work on windows again ([#106](https://github.com/eyeonus/Trade-Dangerous/pull/106),
  [`5309181`](https://github.com/eyeonus/Trade-Dangerous/commit/53091817c5274589b54ed41fe099ba68531fa1d1))

* fix: fix funky ssl for urllib on windows

* chore: re enable test for windows

* tests: run tox differently

* chore: coverage is great to have when developing

* style: cleanup and typing

* fix: close tdb and/or cursors

* style: remove debug print infor

* tests: add update_gui to bootstrap test

### Refactoring

- Use raw strings for regex
  ([`74a4c31`](https://github.com/eyeonus/Trade-Dangerous/commit/74a4c3190eb300981d5c578fe3105c7edaf8f122))

Fixes #107


## v10.13.8 (2022-12-27)

### Bug Fixes

- New Sementic release
  ([`1b2a46c`](https://github.com/eyeonus/Trade-Dangerous/commit/1b2a46c29eef708e439abea86d863409edc350ef))

### Refactoring

- Update ship index message.
  ([`6f63d4d`](https://github.com/eyeonus/Trade-Dangerous/commit/6f63d4dde6de10aeca9b80aee3dcfcf0a95ef2ed))

Minor comment changes as well.


## v10.13.7 (2022-06-15)

### Bug Fixes

- Forgot to remove some debug code.
  ([`8b1b889`](https://github.com/eyeonus/Trade-Dangerous/commit/8b1b889823365b337ac9657cfbf034c0373ee76c))


## v10.13.6 (2022-06-09)

### Bug Fixes

- Strip microseconds off timestamps which have them
  ([`17b603d`](https://github.com/eyeonus/Trade-Dangerous/commit/17b603d52517d1bfdf9956993bec656a3e8b6673))


## v10.13.5 (2022-06-01)

### Bug Fixes

- Set default argv to None
  ([`4b44458`](https://github.com/eyeonus/Trade-Dangerous/commit/4b444581844a356c7cf65c1d4301bac83cf93436))


## v10.13.4 (2022-06-01)

### Bug Fixes

- Pypi authentication error
  ([`87e2c82`](https://github.com/eyeonus/Trade-Dangerous/commit/87e2c82a3deee9f0679f76723f420c24b79ff8b9))

Added PYPI_TOKEN to Actions workflow


## v10.13.3 (2022-06-01)

### Bug Fixes

- Don't run version, publish does that
  ([`f873a82`](https://github.com/eyeonus/Trade-Dangerous/commit/f873a8224d1df938bd9bb94904ee3c17ab4e47fd))

running `semantic-release version` before running `semantic-release publish` causes publish to think
  it doesn't need to publish when it does: ``` Run semantic-release version Creating new version
  Current version: 10.13.2, Current release version: 10.13.2 Bumping with a patch version to 10.13.3
  Run semantic-release publish -v debug . . . Current version: 10.13.3, Current release version:
  10.13.3 . . . No release will be made. ```

As per the semantic-release doc, publish will run version, so doing it ourselves, it turns out, is a
  BAD thing

- Remove Travis, separate GUI
  ([`4557d7b`](https://github.com/eyeonus/Trade-Dangerous/commit/4557d7bb7dd65b2aab1c3e2e34494e305ebd73bb))

### Refactoring

- Remove Travis
  ([`0b28406`](https://github.com/eyeonus/Trade-Dangerous/commit/0b2840633e8e30e95a1d0f0efc4aa8481cbcce6c))


## v10.13.2 (2022-02-07)

### Bug Fixes

- Minor fixes
  ([`154db36`](https://github.com/eyeonus/Trade-Dangerous/commit/154db361ce739ff22db63f84c2bc5cd2691046b0))

fixes #98

fix potential fail when using TD_DATA but not TD_CSV

### Chores

- Add support for gh-action
  ([`25869f3`](https://github.com/eyeonus/Trade-Dangerous/commit/25869f3adb7df80b92542007a3aaa71b9c37598c))

- Add supported version classifiers
  ([`0bebda5`](https://github.com/eyeonus/Trade-Dangerous/commit/0bebda5a7b977d98fe29f90a0f3d28991b928d6c))

- Editorconfig with trim trailing ws disabled
  ([`eebe677`](https://github.com/eyeonus/Trade-Dangerous/commit/eebe677cdaa0d7fadb94337c858f0a42c0a6d7d4))

### Testing

- Fix locking files during tests
  ([`deb7317`](https://github.com/eyeonus/Trade-Dangerous/commit/deb7317c437184284976dbef2dadf481d4da7e44))


## v10.13.1 (2022-01-31)

### Bug Fixes

- Make semantic tell me what's broke
  ([`0c328ca`](https://github.com/eyeonus/Trade-Dangerous/commit/0c328ca49556958438621f5ff84aba7cde39dbdd))


## v10.13.0 (2022-01-31)

### Bug Fixes

- (maybe) remove test that travis keeps failing on
  ([`9e23361`](https://github.com/eyeonus/Trade-Dangerous/commit/9e23361b43d5068c0ef2c5ce13489a74275d653a))

Possibly revert later once I figure out how this works

### Features

- Add TD_CSV environment variable detection to csv export
  ([`9537082`](https://github.com/eyeonus/Trade-Dangerous/commit/95370829da9b25e3d6aba0e9161c92716be82633))

Allows saving the the TD cache in a location other than TD_DATA


## v10.12.0 (2021-11-20)

### Bug Fixes

- Buy command var "maxLS" not named consistently ("maxLS", "maxLs")
  ([`1f4989a`](https://github.com/eyeonus/Trade-Dangerous/commit/1f4989a8280702110b68f8b52c08b60a27c41e33))

All instances have been changed to "mls" to match other commands.

### Features

- Added --max-ls parameter to the buy command.
  ([#96](https://github.com/eyeonus/Trade-Dangerous/pull/96),
  [`ff371eb`](https://github.com/eyeonus/Trade-Dangerous/commit/ff371eb25b91f745e872dce953001c3644a4db2c))

Here's hoping TravisCL doesn't break. Again.


## v10.11.3 (2021-10-04)

### Bug Fixes

- Publish the new version!
  ([`d8f0dd7`](https://github.com/eyeonus/Trade-Dangerous/commit/d8f0dd700f46c73ba9505ce0dbb6fa726ebd931b))

### Refactoring

- Add TODO, hopefully make Travis publish again.
  ([`2946b9c`](https://github.com/eyeonus/Trade-Dangerous/commit/2946b9c559a84a604d46aac8c8395c78af0b5d42))


## v10.11.2 (2021-10-03)

### Bug Fixes

- Correct typo in olddata.
  ([`8cd12c5`](https://github.com/eyeonus/Trade-Dangerous/commit/8cd12c5875566728c0ff79299004b6f19406ebfe))

Fixes #94.

### Chores

- Hopefully fix semantic-release not publishing
  ([`d3b4485`](https://github.com/eyeonus/Trade-Dangerous/commit/d3b44856600b8974d0fb9e77a8470268f4cc21ee))

### Documentation

- Update README.md
  ([`d38a096`](https://github.com/eyeonus/Trade-Dangerous/commit/d38a09641eac6ab5f25fa59e9b8187c686267b47))

Update copyright dates.


## v10.11.1 (2021-06-28)

### Performance Improvements

- Avoid excessive loops ([#93](https://github.com/eyeonus/Trade-Dangerous/pull/93),
  [`f457db5`](https://github.com/eyeonus/Trade-Dangerous/commit/f457db5c9a6b46ce3610d993ff629d2a579e7ce8))

Evaluate all filter conditions instead of looping over all stations separately for condition
  provided. This leads to a quite substantial speedup if multiple filter conditions are provided.


## v10.11.0 (2021-06-22)

### Features

- Add switch to filter Odyssey Settlements ['--odyssey'|'--od'].
  ([`396d9f0`](https://github.com/eyeonus/Trade-Dangerous/commit/396d9f0876bcb2c1c4cf7ecb7e164c5139df5c8c))

Fixes #91

### Refactoring

- Broke a test case
  ([`f7a4a32`](https://github.com/eyeonus/Trade-Dangerous/commit/f7a4a32ded2c75e06d9eefaa01f121a523db0a61))

- Missing comma
  ([`87d53ff`](https://github.com/eyeonus/Trade-Dangerous/commit/87d53ffbec3c32ba6613b406d55e360cc32bdb47))


## v10.10.0 (2021-03-26)

### Features

- Allow for capacities above 1500
  ([`76537b9`](https://github.com/eyeonus/Trade-Dangerous/commit/76537b9d84fc55994970f55f3cf39649c9c6bc5f))

See #89

There is no longer an upper limit, capacities >1500 will trigger a warning, not an error.

This also forces jumps per hop to 1 and adds '--supply' and '--demand', if not already provided, to
  ignore stations that do not have supply/demand of at least 10*capacity. This has the effect of
  filtering out many stations, with the effect of making it more likely it will find a route that
  not only will fill the hold and also more likely the route can be repeated multiple times.

1 hop with the above settings is about long enough to shop for, prepare, and eat dinner.

2 hops is multiple days without '--loop'. With '--loop', it took ~150% of the time as 1 hop to
  finish, reporting failure to find a route.

It is extremely unlikely that any station not only has a large quantity of something another station
  needs a large quantity of, but also needs needs a large quantity of something that same other
  station has a large quantity of, so not finding a 2-hop loop route isn't surprising.

It might be possible to find a loop route of 3+ hops, this has not been tested and is not
  recommended. A 3-hop loop route might be possible to find reliably, user discretion is advised.

Doing an unsupported >1500 capacity trade with >3 hops will trigger a special warning with
  instructions on how to SIGTERM using a keyboard.


## v10.9.8 (2021-02-05)

### Bug Fixes

- Update the build semantic, you jerk
  ([`8ca4e39`](https://github.com/eyeonus/Trade-Dangerous/commit/8ca4e392f7949e106636a1fee90a0d381b8a03e0))

### Refactoring

- Small change to trigger the build again.
  ([`b9ebcb5`](https://github.com/eyeonus/Trade-Dangerous/commit/b9ebcb54fca6d9c003013fde50811fa42132b84b))

Last fix commit didn't build because it was pushed before the previous one was finished building.


## v10.9.7 (2021-02-05)

### Bug Fixes

- Add 'VOID OPAL' to corrections
  ([`f208023`](https://github.com/eyeonus/Trade-Dangerous/commit/f20802319a503f569d836c8d46ca7231779f5024))

fixes #84


## v10.9.6 (2021-01-18)

### Bug Fixes

- Edmc_batch_plug Path issues ([#83](https://github.com/eyeonus/Trade-Dangerous/pull/83),
  [`ef06684`](https://github.com/eyeonus/Trade-Dangerous/commit/ef06684e0534d1d969658e9b55f3a752c502475e))

This fixed two bugs in the EDMC Batch set_environment method. The method used `pathlib.Path` while
  `pathlib` was not imported as a module which threw a NameError. Secondly, the method set the
  environments filename to a Path object when it should be a string.


## v10.9.5 (2021-01-09)

### Bug Fixes

- Maxgainperton shouldn't be set by default.
  ([`00c558c`](https://github.com/eyeonus/Trade-Dangerous/commit/00c558cf7f31fb82deb4ca176b43ca16db130559))


## v10.9.4 (2020-12-19)

### Bug Fixes

- Galactic Travel Guides are not deleted, just rare.
  ([`b20b9d0`](https://github.com/eyeonus/Trade-Dangerous/commit/b20b9d0abbcf4fb1d371715bc47da2e625a2cb23))


## v10.9.3 (2020-12-16)

### Bug Fixes

- Ensure folder exists before attempting to write file
  ([`2de883f`](https://github.com/eyeonus/Trade-Dangerous/commit/2de883f62b1460c28da006d972da6225a9bd882f))

fixes #78

- Hopefully actually fix Travis this time.
  ([`970d721`](https://github.com/eyeonus/Trade-Dangerous/commit/970d721c2b512fff096f4bc76c15716f35a03633))

- Make Travis work again.
  ([`13addad`](https://github.com/eyeonus/Trade-Dangerous/commit/13addad48d2bb5f58b7e5c09c0ebdd5eedd74bd0))

Also add new 3.8 and remove soon to be unsupported 3.4 python versions


## v10.9.0 (2020-07-17)

### Bug Fixes

- One more go at properly fixing required arguments.
  ([`79ba4f3`](https://github.com/eyeonus/Trade-Dangerous/commit/79ba4f3b65925098f5160e6042dd4e7336a15e69))

### Refactoring

- Remove redundant code.
  ([`bf27c3e`](https://github.com/eyeonus/Trade-Dangerous/commit/bf27c3e43f0644dbb572de3cd467766595d79790))


## v10.8.2 (2020-07-17)

### Bug Fixes

- Make certain hopRoute is a list.
  ([`27eba0d`](https://github.com/eyeonus/Trade-Dangerous/commit/27eba0d61895380058628fd0eeb6cdebe304fce6))


## v10.8.1 (2020-07-17)

### Bug Fixes

- Required args now pass correctly in gui
  ([`b21aba8`](https://github.com/eyeonus/Trade-Dangerous/commit/b21aba84766e9a7377875e89227eccd418f8814a))

### Features

- Add '--fleet-carrier' ('--fc') option
  ([`339b2af`](https://github.com/eyeonus/Trade-Dangerous/commit/339b2af4e58ef9296a84548605359517511425be))

Functions exactly like '--planetary', but for fleet carriers.

Allowed values are 'YN?'

Fixes 74.


## v10.8.0 (2020-07-01)

### Bug Fixes

- Make recent systems also separate, optional update.
  ([`20fb696`](https://github.com/eyeonus/Trade-Dangerous/commit/20fb696335d65773df216f5283fef896951aa496))

Use 'systemrec' option in eddblink import plugin.

### Features

- Add purge option to eddblink plugin.
  ([`9689ed7`](https://github.com/eyeonus/Trade-Dangerous/commit/9689ed7fc3762084661ebded7e198e335f543403))

The 'purge' option will remove all system listings which do not have any stations in them, such as
  uninhabited systems that used to have a Fleet Carrier in them but no longer do.

It is also run whenever using the 'systemrec' option.

### Refactoring

- Better gui entry method.
  ([`9b5b175`](https://github.com/eyeonus/Trade-Dangerous/commit/9b5b1750f104c10209bd8adc414cf68723f8c684))


## v10.7.1 (2020-06-30)


## v10.7.0 (2020-06-30)

### Bug Fixes

- Always check for new populated systems dump.
  ([`cce11af`](https://github.com/eyeonus/Trade-Dangerous/commit/cce11afd8f7c398767efa9a29d4bd093ac3e95ac))

### Features

- 'systemfull' option added to eddblink import plugin
  ([`9b27a99`](https://github.com/eyeonus/Trade-Dangerous/commit/9b27a9985ff2360c2da5ec65dccea1308a475b63))

Added 'systemfull' option, which uses systems.csv, the list all currently recorded systems, to build
  the Systems table, which should mean no FC shows up as being in Unknown Space.

'systemfull' is purely optional and not recommended.

Added systems_recently.csv to processing of Systems. systems_recently contains all systems-
  populated or not- that have been update within the previous 7 days. This will make it less likely
  a FC will be marked as being in Unknown Space.

### Refactoring

- Don't turn off 'system' when 'systemfull' is on.
  ([`a2b9153`](https://github.com/eyeonus/Trade-Dangerous/commit/a2b9153d6e41cba97950fdd9187d22b0d64eef03))


## v10.6.3 (2020-06-30)

### Bug Fixes

- Fleet Carriers can be in an unpopulated system.
  ([`27ab8b3`](https://github.com/eyeonus/Trade-Dangerous/commit/27ab8b397b1276732f1b915cc956792b03bd47ea))

Added "Unknown Space" system for FCs in a system not in the DB. "Unknown Space" systems are added
  with x,y, and z pos of 0.

### Refactoring

- Updated server address to use https.
  ([`9a77295`](https://github.com/eyeonus/Trade-Dangerous/commit/9a77295b39d9368f2ff824a814c701020a3d3ca9))


## v10.6.2 (2020-06-30)

### Documentation

- Pyenv/pyenv#1375 with Mojave ([#67](https://github.com/eyeonus/Trade-Dangerous/pull/67),
  [`2edbdf4`](https://github.com/eyeonus/Trade-Dangerous/commit/2edbdf4eec37e605d71a7e88fd4afd818c25e7d8))

Document fix for Mac users who use pyenv Python installation, to get the latest tcl/tk version
  working on Mac OS 10.14.6 (Mojave).

- Update README.md ([#71](https://github.com/eyeonus/Trade-Dangerous/pull/71),
  [`192502d`](https://github.com/eyeonus/Trade-Dangerous/commit/192502d6d9a443b6e6cee90faf24f24f3d61404e))

http://elite.tromador.com/

### Performance Improvements

- Raise warning rather than exiting.
  ([`3f0b6ff`](https://github.com/eyeonus/Trade-Dangerous/commit/3f0b6ff24982560fb8ccaf5e74d0dad1b2b28fdf))


## v10.6.1 (2019-09-01)

### Bug Fixes

- Only run the color command on Windows machines.
  ([`7538e98`](https://github.com/eyeonus/Trade-Dangerous/commit/7538e9869a225f0e94857900eea77fbe9cc0731a))

It's not needed on *nix or OSX and throws shell errors when int's run on OSX.


## v10.6.0 (2019-08-31)

### Bug Fixes

- Missing argument in method call
  ([`004a6d8`](https://github.com/eyeonus/Trade-Dangerous/commit/004a6d853f89b1b605bd34e78fe2431e65d6f555))

### Features

- Color output (only implemented in 'run' command thus far.)
  ([`3cf1dc8`](https://github.com/eyeonus/Trade-Dangerous/commit/3cf1dc8eb623f3a9776243ce38b6fc5405f5e9ea))

When running TD in terminal (command prompt/ powershell for windows users), adding the '--color'
  argument to the run command will output the text in color. Color output will be enabled for the
  other commands as time permits.

(Thanks go to skorn for idea and initial coding.)


## v10.5.7 (2019-08-31)

### Bug Fixes

- Properly implement options with multiple choices.
  ([`ba9a940`](https://github.com/eyeonus/Trade-Dangerous/commit/ba9a940dc102de7c0a0438106a83a967f972583b))

Was comparing against the wrong var.

### Refactoring

- Formatting fixes. (Indentation)
  ([`9da641b`](https://github.com/eyeonus/Trade-Dangerous/commit/9da641b38203ad44ba5d87a58d84b9372bc536cd))


## v10.5.6 (2019-08-31)

### Bug Fixes

- Append the argnames for required arguments
  ([`0617187`](https://github.com/eyeonus/Trade-Dangerous/commit/0617187874670630d32791ed7dce930362890f7d))

Don't know why I did that, but it was the wrong thing to do.


## v10.5.5 (2019-06-21)

### Bug Fixes

- Remove unused imports
  ([`4049f57`](https://github.com/eyeonus/Trade-Dangerous/commit/4049f573e1d7c6e9f311582badf177ef7e60742c))


## v10.5.4 (2019-06-21)

### Bug Fixes

- Use 127.0.0.1, not 127.2.0.1, Because Apple computers are evil.
  ([`1dacb3b`](https://github.com/eyeonus/Trade-Dangerous/commit/1dacb3b6816b6480c3360f8abea7bbb4bf2511c4))

Fixes #63


## v10.5.3 (2019-06-20)

### Bug Fixes

- Implement plugin options subwindow
  ([`a471b7a`](https://github.com/eyeonus/Trade-Dangerous/commit/a471b7a107880c915f1ff14f8db63c829ab1217d))

Now you don't need to type in every option. Push the button, and a window will pop up allowing you
  to simply select which options you'd like.

Plugin options which require a value, such as the filename to test json importing with in the case
  of the edapi plugin's 'test' option, will show as a text field for typing that parameter in.


## v10.5.2 (2019-06-17)

### Bug Fixes

- Set width of tab fields, no more output weirdness.
  ([`dfca779`](https://github.com/eyeonus/Trade-Dangerous/commit/dfca7791a40c4e70b21a4a6cfc8aa4225c960b3e))

Hooray. Figured it out.


## v10.5.1 (2019-06-17)


## v10.5.0 (2019-06-17)

### Bug Fixes

- Make the gui actually work when TD is pip installed.
  ([`5c36944`](https://github.com/eyeonus/Trade-Dangerous/commit/5c3694442e5cbf977e5235dcb4b9345c320ef98b))

### Documentation

- Update copyright notices with current year.
  ([`1cf29ad`](https://github.com/eyeonus/Trade-Dangerous/commit/1cf29ad183eaab61f4d417f09b2f26bc6c7e5237))

Man there are a lot. I'm considering removing all but the one on trade.py and README.md

### Features

- Beta release of GUI
  ([`4d56509`](https://github.com/eyeonus/Trade-Dangerous/commit/4d565091aa081eebca1bcc5ccab941cdd0b75b3c))

Just run "trade gui" and tell me what you think.


## v10.4.8 (2019-05-29)


## v10.4.7 (2019-05-28)

### Bug Fixes

- Don't set fallback on failure of ship or live listings dl...
  ([`ab6e48e`](https://github.com/eyeonus/Trade-Dangerous/commit/ab6e48e5b3a1bca82a4b7a3d7c5962b9d3f77606))

Completely ignore fallback option wrt ships index, now will always try to download, only uses
  template on failure to open.

refactor: Switch back to beta for the ships index. Better suited so says Trom. :)

- Stop always using the template ship index when fallback enabled
  ([`54897cb`](https://github.com/eyeonus/Trade-Dangerous/commit/54897cb0e8ffb20c0fc6455f4bcdca482ff1f5ed))

Check to see if the attempt to download the ship index was successful, and if so, do not use the
  template, even if the fallback option is enabled.

### Refactoring

- Update ship index to not use the beta site.
  ([`49ce095`](https://github.com/eyeonus/Trade-Dangerous/commit/49ce095416be1e505307f3bac14b4b5867c38c13))


## v10.4.6 (2019-05-23)

### Bug Fixes

- Give TD web requests a User-Agent header.
  ([`0a10cec`](https://github.com/eyeonus/Trade-Dangerous/commit/0a10ceceebc4228b39494310d88b6997f8a36028))

Fixes #61


## v10.4.5 (2019-05-23)

### Bug Fixes

- Update ship index URL.
  ([`c455594`](https://github.com/eyeonus/Trade-Dangerous/commit/c4555942c2cca0da8a49a470f2165402f50e5457))


## v10.4.4 (2019-05-23)

### Bug Fixes

- Don't crash when attempting to download non-existent file.
  ([`97c254d`](https://github.com/eyeonus/Trade-Dangerous/commit/97c254de2f18cc45cb341ba3e7f34127baef5136))

Fixes #21.

Specifically, it fixes the crash that happens because of the ship's index file no longer existing of
  the EDCD coriolois data github.

So the Ships database won't be getting updated until a new source is found to download from.

For now the latest version available before the removal is stored as a template.

TD will get another update once we have a new site from which to get the index again.

### Chores

- Include fix-indent.sh bash script
  ([`f088f25`](https://github.com/eyeonus/Trade-Dangerous/commit/f088f256c28da2e0767c12b6009b0a86fe46587b))

May not have figured out how to get pylint to correctly detect missing indentation on blank lines,
  or how to get any of the auto-formatters to correctly indent them, but at least there's now a bash
  script that will take care of the indentation for all the .py files when it's run.

### Testing

- Remove test_transfers.py from tests
  ([`4867f3b`](https://github.com/eyeonus/Trade-Dangerous/commit/4867f3bb50ba8dab3099c9c5d476e2d8bbe82c27))

It fails when Tromador's server isn't up, even though there's nothing wrong with the code.

Since the code it supposedly checks is never touched anyway, and it can easily put out a false
  positive, it's gone now.


## v10.4.3 (2019-02-26)

### Bug Fixes

- Properly set profile save path
  ([`55274fe`](https://github.com/eyeonus/Trade-Dangerous/commit/55274fefda798124714015f89d6dc803ce24544d))

Need to make sure it works correctly with non-TDH profile saving too, Jon.

Fixes #57

### Code Style

- Found a few more missing indents
  ([`2aa12d0`](https://github.com/eyeonus/Trade-Dangerous/commit/2aa12d01840fffd5b3657609a38a020a7ae5f6d1))


## v10.4.2 (2019-02-26)


## v10.4.1 (2019-02-26)

### Bug Fixes

- Unable to save tdh profile
  ([`248a4fb`](https://github.com/eyeonus/Trade-Dangerous/commit/248a4fba804e7ac99e279a678d622ce5acbc4577))

Reverts change introduced unintentionally by fca7f2698a5ac83dd4011c4dcd3379d9cbed0274


## v10.4.0 (2019-02-26)

### Bug Fixes

- Error when trying to insert rare items that already exist in table
  ([`20d64c6`](https://github.com/eyeonus/Trade-Dangerous/commit/20d64c6f999e0108f4f1e4e56f6ac92facc08a52))

In this case, I don't think "INSERT OR REPLACE" is a horrible idea.

- Generate RareItem table after import
  ([`6425188`](https://github.com/eyeonus/Trade-Dangerous/commit/6425188d46ab1b8f11e85f3d616b1b1540ee1e6a))

The RareItem table never got filled in, now it is. Oops.

### Code Style

- Apply preferred indenting to all files.
  ([`14c84c6`](https://github.com/eyeonus/Trade-Dangerous/commit/14c84c66554167ba8edf8109f81b76027ea0af79))

Blank lines should be indented to the same level as the line immediately after.

Ex: ``` ........return .... ....def newFunc() ```

Performed automatically on all files using the following Linux bash command: ``` find * -type f
  -name "*.py" -print0 | xargs -0 sed -i -e '/^ *$/{N;s/^ *\n\( *\)\(.*\)/\1\n\1\2/}' ```

- Whitespace normalizing
  ([`32c75d2`](https://github.com/eyeonus/Trade-Dangerous/commit/32c75d28317b5ea7f63f1956d1915901a478f96b))

### Features

- Allow rare items to be in the normal item table.
  ([`6a8ddef`](https://github.com/eyeonus/Trade-Dangerous/commit/6a8ddefb6d68e219bd95f615a18e5f20a774b27c))

This change will enable rare items to be included in the market listings.

### Refactoring

- 'option == x or option == y ...' => 'option in (x,y,z)'
  ([`601355d`](https://github.com/eyeonus/Trade-Dangerous/commit/601355d0eae03617e39edfd7e747b9198537f3d7))

- Correct Fdev warning in edcd plugin
  ([`e80a3ad`](https://github.com/eyeonus/Trade-Dangerous/commit/e80a3adbd1e855d4032a81b93f3409438b20f85b))

- Update journal plugin wrt station types
  ([`070fb84`](https://github.com/eyeonus/Trade-Dangerous/commit/070fb843d948c1c8175c23c6329185432e656346))

Correctly identify CraterPort and CraterOutpost station types as planetary.

Future planetary station types can be included by simply adding them to planetTypeList.


## v10.3.1 (2019-02-25)


## v10.3.0 (2019-02-20)

### Bug Fixes

- Skip stations that are not in the DB when importing listings
  ([`34220dc`](https://github.com/eyeonus/Trade-Dangerous/commit/34220dc3b201c4471f117a091944c0884f670c22))

Thanks go to Bernd for the code work.

Fixes #56

### Features

- Add 'TD_SERVER', 'TD_FALLBACK', and 'TD_SHIPS' env_vars
  ([`5e92257`](https://github.com/eyeonus/Trade-Dangerous/commit/5e92257dd6f45bb653bfb128572f78b838c5241d))

TD_SERVER = Location of the TD server. (Currently 'http://elite.tromador.com/files/'.)

TD_FALLBACK = Location of the EDDB.io server. (Currently 'https://eddb.io/archive/v6/'.)

TD_SHIPS = Location of EDCD ship info file. (Currently 'https://raw.githubusercontent.com/EDCD/
  coriolis-data/master/dist/index.json '.)

Setting the environment variable allows updating these web addresses by the user without needing to
  wait for TD to update.

refactor: set BASE_URL default to 'http://elite.tromador.com/files/' fixes #55

revert: 1c4d186 Apparently caused by developer error and wasn't a necessary change.


## v10.2.2 (2019-02-15)

### Bug Fixes

- Correctly check for $TD_EDDB
  ([`1c4d186`](https://github.com/eyeonus/Trade-Dangerous/commit/1c4d186be29379217eab1d27cf72915c5c74e5c0))

In python's 'x if true else y', x is evaluated first, then the if statement is evaluated, and only
  when the if statement is false does y get evaluated.

Path(os.environ.get('TD_EDDB') = NoneType) will cause the program to error before even getting to
  the if statement.


## v10.2.1 (2019-02-15)

### Bug Fixes

- Avoid TypeError if TD_EDDB is not set
  ([`cd41144`](https://github.com/eyeonus/Trade-Dangerous/commit/cd41144a1f875dda2fea189dc97831c5edd762ad))

Path(None) raises a TypeError. Test for missing TD_EDDB as well as set.

fixes #51

### Code Style

- Restore whitespace to eddblink_plug.py
  ([`6d0de5f`](https://github.com/eyeonus/Trade-Dangerous/commit/6d0de5faba85dbe51f47f8e888b16d2c39a844ac))


## v10.2.0 (2019-02-14)

### Bug Fixes

- Make sure eddb path is path, not string, when set via env_var
  ([`6204486`](https://github.com/eyeonus/Trade-Dangerous/commit/620448696c88ee209768b696383d2811e9d62a0c))

- Revert d7a4fb3
  ([`2f553a8`](https://github.com/eyeonus/Trade-Dangerous/commit/2f553a81f08008145838facd941d31307d3c0659))

TEST BEFORE YOU PUSH, PETER

### Chores

- Stop trying to deploy pull-request
  ([`d7a4fb3`](https://github.com/eyeonus/Trade-Dangerous/commit/d7a4fb3dbd74ecbea4c04a79216796820d69b966))

Trying to deploy a pull request will fail the job.

### Features

- Add environment variable for setting location of 'eddb' folder.
  ([`930e2e5`](https://github.com/eyeonus/Trade-Dangerous/commit/930e2e5ba3571ff477b234800cc8598c046bcc4f))

If set, the "dump files" will be stored to the path set by TD_EDDB. It will not be in an 'eddb'
  sub-folder, but the specific path set by the environment variable.

(listings.csv => $TD_EDDB\listings.csv)

If not, the "dump files" will be stored in the 'data' folder (which itself may be set via TD_DATA)
  in an 'eddb' sub-folder.

(listings.csv => $TD_DATA\eddb\listings.csv)

### Refactoring

- Remove maddavo.
  ([`75d6f36`](https://github.com/eyeonus/Trade-Dangerous/commit/75d6f364bb09d3fc2f7cb6f4fe5b92683705dd0b))

It's not used anymore. It doesn't work with the site being inactive.

It is therefore useless and shall be deleted forthwith.


## v10.1.2 (2019-02-14)

### Bug Fixes

- Unable to save profile.<current_time>.json"
  ([`fca7f26`](https://github.com/eyeonus/Trade-Dangerous/commit/fca7f2698a5ac83dd4011c4dcd3379d9cbed0274))

### Code Style

- Restore whitespace on all top-level files
  ([`d509fda`](https://github.com/eyeonus/Trade-Dangerous/commit/d509fda783970ee0754752a79369b4d36c346258))

I'll get to the rest eventually.

Blank lines should have whitespace to the same level as the line immediately following:

``` if something: #This is the wrong amount of whitespace stuff() more_stuff() #This is the wrong
  amount of whitespace while happening: ```

``` if something: #This is the correct amount of whitespace stuff() more_stuff() #This is the
  correct amount of whitespace while happening: ```


## v10.1.1 (2019-02-14)

### Bug Fixes

- Unable to save tdh_profile.json
  ([`a2abe01`](https://github.com/eyeonus/Trade-Dangerous/commit/a2abe01ec25347191ac792f56ac966ff8533dfdc))


## v10.1.0 (2019-02-13)

### Features

- Automatically update Added.csv, RareItem.csv, TradeDangerous.sql
  ([`fe82c3a`](https://github.com/eyeonus/Trade-Dangerous/commit/fe82c3a503679bc63fdc1a95fd06849c377b89f4))

refactor: restore whitespace to tradedb.py

The template files may need updating, and if that is the case, any TD database will need their copy
  updated as well.

Since TD detects changes to the 'cache', any updates to these files will be integrated into TD the
  next time it is run.

Changes to the SQL will likely require doing a 'clean' run with the eddblink plugin as they are
  often breaking changes.

### Refactoring

- Remove template folder environment variable
  ([`b388f60`](https://github.com/eyeonus/Trade-Dangerous/commit/b388f606cd8b4ce8d765034ff661e27e1cb1ee68))

The template folder contains the .sql file that is needed to build TD's database.

TD copies these files whenever it needs to create a new database.

It is vital that these files exist and be correctly pointed to in order for TD to work.

It makes absolutely no sense to make it possible for the user to even accidentally point TD at a
  non-existant path or even an existing one that simply doesn't have those files, and there is no
  need to have these template files for any purpose other than that of TD using them to create a new
  database.

In summary: having this environment variable: usefulness: <=0

potential harm: >0


## v10.0.3 (2019-02-13)

### Bug Fixes

- Correct entry point.
  ([`c65f3bf`](https://github.com/eyeonus/Trade-Dangerous/commit/c65f3bf14891d2671ae56c2b70dd4fbf83cc984d))

- Include all packages
  ([`1595a3c`](https://github.com/eyeonus/Trade-Dangerous/commit/1595a3c096319eb419d24e746d2ebd503bcd1f7f))

find_packages doesn't find misc or templates.

I don't think templates is needed, but batter safe than sorry, and misc /IS/ needed.

M<anually creating the packages list should fix the problem.

- Package_data no longer pointing to wrong files.
  ([`efc28f7`](https://github.com/eyeonus/Trade-Dangerous/commit/efc28f7dd3824a3e984e6d71c62e31af20dc5021))

This fixes the problem where the .sql file is not installed.

### Chores

- Change autoversioning commit message.
  ([`24f26c6`](https://github.com/eyeonus/Trade-Dangerous/commit/24f26c68ab523a219b0e1888b7ad266d24d0ea54))

This and previous commits combined fixes #32

- Fix same typo in setup.py
  ([`d53bb14`](https://github.com/eyeonus/Trade-Dangerous/commit/d53bb1414b231d250c184b12a8975ddfd3430b8a))

### Documentation

- Fix typo in README.md
  ([`de0f4dc`](https://github.com/eyeonus/Trade-Dangerous/commit/de0f4dc378e467f1cb8fdb4a532d2120e38da4b8))

### Refactoring

- Don't include templates
  ([`d1c4226`](https://github.com/eyeonus/Trade-Dangerous/commit/d1c4226d67c45fde5f59edba4ffd143aa5218d63))


## v10.0.0 (2019-02-09)

### Bug Fixes

- Add module 'typing' to the requirements.
  ([`f8b3f13`](https://github.com/eyeonus/Trade-Dangerous/commit/f8b3f1391ac699ed753706d5cd0a0fb2ced5a2c1))

- Apparently can't test 3.7 because error 403.
  ([`735234d`](https://github.com/eyeonus/Trade-Dangerous/commit/735234dd7fcc7ecd4bc5a3048f748bd8e9858a61))

Thanks upstream.

- Bump version
  ([`34da73a`](https://github.com/eyeonus/Trade-Dangerous/commit/34da73a55ec4eb77d89ac45472a983d1757a19df))

### Chores

- Check value of $PYPI_USERNAME before and after publish
  ([`d619bfb`](https://github.com/eyeonus/Trade-Dangerous/commit/d619bfb78d982aa21d45a6de9bab395af4202429))

The env is definitely set, so why is it acting like it's not?

- Fix semantic-release
  ([`23420f8`](https://github.com/eyeonus/Trade-Dangerous/commit/23420f861914f1bf67a3310e53ef414d2bbe4805))

- Okay, try it fully local.
  ([`1803de4`](https://github.com/eyeonus/Trade-Dangerous/commit/1803de4769fff81f437d8c7d993997a9f8f4e7f5))

- Print $PYPI_USERNAME
  ([`0f241f5`](https://github.com/eyeonus/Trade-Dangerous/commit/0f241f52763a7b3f475be47262cbb28412f2f198))

For some reason it's trying to push to 'https://github.com/$PYPI_USERNAME/Trade-Dangerous.git/'

Which is wrong.

- Publish to pypi
  ([`5e55d0f`](https://github.com/eyeonus/Trade-Dangerous/commit/5e55d0f8209c35dbaaabdbe972269b620488cc37))

Update how to publish to pypi and some documentation about requirements.

- Remove debug prints from travis.yml
  ([`5dd2d6d`](https://github.com/eyeonus/Trade-Dangerous/commit/5dd2d6d7c6b7c85dd5e47b4d6d7471a230cb9e75))

- Revert last two commits
  ([`a44ca91`](https://github.com/eyeonus/Trade-Dangerous/commit/a44ca9149a0d8c06bab398fec8b383b71664f351))

Time to ask about this upstream.

- Try assigning the env again.
  ([`5798f4c`](https://github.com/eyeonus/Trade-Dangerous/commit/5798f4c5c22902492d8b82a7a0326cffe4adae00))

### Features

- Publish to pypi
  ([`097dbf6`](https://github.com/eyeonus/Trade-Dangerous/commit/097dbf67e13fc5a8876a088462d05494b28f208a))

Assuming everything actually works now.

BREAKING CHANGE:

API now accessed as 'cli.trade', rather than 'trade.main'.

### Refactoring

- Don't publish until build works.
  ([`b5b2f88`](https://github.com/eyeonus/Trade-Dangerous/commit/b5b2f88e4048f05dc90caf9884806641de084718))

### Testing

- Travis with py3.7
  ([`a1626cd`](https://github.com/eyeonus/Trade-Dangerous/commit/a1626cdcadf73621500a9526448f58140ef73e60))

test: travis use dist: xenial

chore: resync tag and version

docs: add info about deploy

chore: configure ci


## v9.5.3 (2019-02-06)

### Refactoring

- Add deprecation NOTE to progbar option.
  ([`73ae3af`](https://github.com/eyeonus/Trade-Dangerous/commit/73ae3af8d9be226b7dd3d7a3ccb2e87dbe7f8809))

Passing the progbar option now results in a NOTE: being printed informing the user that the option
  has been deprecated and no longer functions.
