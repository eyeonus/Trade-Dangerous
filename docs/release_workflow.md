# Release workflow

## 1) Stable automatic release path

**Branch:** `release/v1`

Push to `release/v1` as normal. The workflow runs automatically.

Semantic-release decides whether a new stable version should be cut from the commit messages:

- `fix:` → patch release
- `feat:` → minor release
- `BREAKING CHANGE:` or `type!:` → major release
- `chore:` → no release
- `docs:` → no release
- `refactor:` → no release unless marked as breaking

### Examples

- `fix: correct rare commodity distance filter` → next patch release
- `feat: add shiny new function` → next minor release
- `refactor!: move backend to SQLAlchemy` → next major release
- `docs: update README` → no release
- `chore: tidy CI workflow` → no release

### Result

If semantic-release decides a release is needed, it creates the new version/tag and the stable release is published.

---

## 2) Manual release-candidate path

**Branch:** `rc/*` development branch  
Examples:

- `rc/gui-polish`
- `rc/sqla-followup`
- `rc/import-rework`

Use this when work is **not ready for stable release** and you want a release candidate first.

### How to trigger it

1. Open **GitHub → Actions**
2. Open **Python application via uv**
3. Click **Run workflow**
4. Choose the RC branch, for example `rc/gui-polish`
5. Set `mode` to `rc`
6. Click **Run workflow**

### Result

The workflow attempts a **prerelease / release candidate** from that RC branch.

Typical shape:

- `12.13.3-rc.1`
- `12.13.3-rc.2`

After testing is complete, merge the finished work to `release/v1` for the normal stable release path.

---

## Rule of thumb

- Want a **stable release**?  
  Commit to `release/v1` using normal semantic-release commit messages.

- Want a **release candidate first**?  
  Work on an `rc/*` branch and trigger the workflow manually with `mode=rc`.

- Do **not** put a `feat:` commit straight onto `release/v1` if you want RC testing first, because that branch is the stable auto-release line.
