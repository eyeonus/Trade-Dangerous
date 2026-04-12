# Release workflow

## Overview

The release process is now split into three separate workflows with clear responsibilities:

- **`rehearsal.yml`** — manual-only safe sandbox for testing workflow changes
- **`prerelease.yml`** — manual prerelease workflow for `alpha`, `beta`, or `rc`
- **`release.yml`** — automatic stable release workflow on pushes to `release/v1`

This separation exists to avoid testing release plumbing by accidentally exercising the real publish path.

---

## 1) Rehearsal workflow

**Workflow:** `rehearsal.yml`  
**Trigger:** manual only (`workflow_dispatch`)

Use this workflow when you want to validate workflow behaviour safely.

### What it does

- runs the full test matrix
- can optionally build source and wheel artifacts
- uploads build artifacts when requested

### What it does not do

- no semantic-release versioning
- no git tags
- no GitHub release creation
- no PyPI publish

### How to use it

1. Open **GitHub → Actions**
2. Open **Rehearsal via uv**
3. Click **Run workflow**
4. Choose whether to enable **Build source and wheel artifacts for rehearsal only**
5. Run the workflow

Use this as the first place to test workflow edits before trusting the prerelease or stable release paths.

---

## 2) Manual prerelease workflow

**Workflow:** `prerelease.yml`  
**Trigger:** manual only (`workflow_dispatch`)

Use this when you want to produce a real prerelease, or rehearse the prerelease path without publishing anything.

### Available channels

- `alpha`
- `beta`
- `rc`

### Inputs

- **Prerelease channel** — selects `alpha`, `beta`, or `rc`
- **Rehearse versioning and build without publishing**
  - checked = dry run only
  - unchecked = live prerelease publish path
- **Build and upload distribution artifacts**
  - controls whether `uv build` runs and artifacts are uploaded

### Safe dry-run path

To test the prerelease workflow without publishing:

1. Open **GitHub → Actions**
2. Open **Manual prerelease publish**
3. Click **Run workflow**
4. Choose a channel, usually `rc`
5. Leave **Rehearse versioning and build without publishing** checked
6. Optionally leave **Build and upload distribution artifacts** checked
7. Run the workflow

Expected result:

- the test matrix runs
- the **Rehearse prerelease** job runs
- the **Publish prerelease** job is skipped
- no tag is created
- nothing is uploaded to PyPI
- no GitHub release is published

### Live prerelease path

To publish a real prerelease:

1. Open **Manual prerelease publish**
2. Choose `alpha`, `beta`, or `rc`
3. **Uncheck** **Rehearse versioning and build without publishing**
4. Run the workflow

That path can publish a real prerelease to PyPI and GitHub Releases.

---

## 3) Stable automatic release workflow

**Workflow:** `release.yml`  
**Branch:** `release/v1`  
**Trigger:** automatic on push to `release/v1`

This is the only automatic publish path.

### What it does

- runs the full test matrix
- runs semantic-release for a stable release decision
- builds distributions when a release is actually created
- publishes to PyPI and GitHub Releases only when a new release was cut

If semantic-release determines that no release is needed, the publish steps are skipped.

---

## Commit message rules

Trade Dangerous now uses the **Conventional Commits** parser explicitly.

### Commits that trigger releases

- `feat:` → **minor** release, a new feature or capability
- `fix:` → **patch** release, a bug fix
- `perf:` → **patch** release, a performance improvement
- `BREAKING CHANGE:` footer or `type!:` → **major** release,  e.g. an incompatible API change

### Commits that do not trigger a release by themselves

These commit types are valid and useful, but they do not cause semantic-release to cut a version on their own:

- `build:` changes that affect the build system or external dependencies
- `chore:` routine maintenance or housekeeping
- `ci:` changes to CI configuration files, workflows, or automation scripts
- `docs:` documentation-only changes
- `refactor:` code restructuring without changing behaviour
- `style:` formatting or stylistic cleanup with no behavioural change
- `test:` adding or changing tests without changing runtime behaviour

They may still appear in the changelog for a release that was triggered by a releasable commit.

### Squash commit evaluation

Common squash-merge commit bodies are supported.

That means a squash commit such as:

```text
feat(config): add new config option (#123)

* refactor(config): change config loading
* docs(configuration): document the new option
```

can contribute multiple categorized changelog entries while still taking its version bump from the releasable commit content.

---

## Examples

- `fix: correct rare commodity distance filter` → next patch release
- `perf: reduce route search overhead in tradecalc` → next patch release
- `feat: add installer workflow plumbing` → next minor release
- `refactor!: change release metadata handling` → next major release
- `docs: update release workflow guide` → no release by itself
- `ci: switch workflow actions to v6` → no release by itself

---

## Rule of thumb

- Want to **test workflow behaviour safely**?  
  Run **`rehearsal.yml`**.

- Want to **test the prerelease path without publishing**?  
  Run **`prerelease.yml`** with **Rehearse versioning and build without publishing** checked.

- Want a **real prerelease**?  
  Run **`prerelease.yml`** with the rehearse checkbox cleared and choose `alpha`, `beta`, or `rc`.

- Want a **stable release**?  
  Push releasable commits to `release/v1` and let **`release.yml`** handle it automatically.
