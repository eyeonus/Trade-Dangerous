# PyPI release path

## Overview

This document explains how Trade Dangerous gets from a push on the stable branch to an installable package on PyPI.

It is not a guide to commit message policy or release planning. Those are covered elsewhere. This document is specifically about the plumbing: what fires, what decides whether a release is needed, what builds the artifacts, and what actually uploads them to PyPI.

This is the **Python package** release path only. The separate Windows freeze and installer process is documented elsewhere.

---

## High-level flow

```text
git push to release/v1
    ↓
GitHub Actions runs release.yml
    ↓
test matrix must pass
    ↓
release job runs on Ubuntu
    ↓
semantic-release decides whether this push needs a new version
    ↓
if no release is needed:
    stop, nothing is uploaded
    ↓
if a release is needed:
    build sdist and wheel
    ↓
publish distributions to PyPI
    ↓
publish the matching GitHub release
```

---

## The trigger

The automatic stable release path starts with a push to:

```text
release/v1
```

That push triggers the GitHub Actions workflow:

```text
.github/workflows/release.yml
```

This is the only automatic stable publish path.

A push does **not** automatically mean a new package version will appear on PyPI. The workflow always runs, but the publish steps only run if the release logic decides that a new release should actually be cut.

---

## What the workflow does

## 1) Test job

The workflow starts by running the test matrix on the supported operating systems.

This is a gate. If the tests fail, the release job does not publish anything.

Purpose:

- prevent packaging and publishing from proceeding on a broken build
- keep stable releases tied to a passing test run

---

## 2) Release job

If the tests pass, the workflow moves on to the release job.

This job runs on Ubuntu and does the publishing work.

At a high level it:

1. checks out the repository with full history and tags
2. installs `uv`
3. installs the publishing dependencies
4. runs semantic-release to decide whether a new version is required
5. builds the package distributions if a release was created
6. uploads those distributions to PyPI
7. publishes the matching GitHub release

---

## What decides whether a release happens

The key decision point is the semantic-release step.

That step examines the repository state and commit history and decides whether the current push should produce a new release. The detailed rules for what kinds of commits count as releasable are documented in `docs/release_workflow.md` and are not repeated here.

The important behaviour is simple:

- if semantic-release decides **no new release is needed**, the workflow stops after the decision point
- if semantic-release decides **a new release is needed**, it creates the new version state and the later publish steps are enabled

In other words, the workflow always runs, but PyPI upload is conditional.

---

## What gets built

When a real release is created, the workflow runs:

```text
uv build
```

That produces the standard Python distribution artifacts:

- a source distribution (`sdist`)
- a built wheel (`.whl`)

These are the files that PyPI receives.

This is the point where the package that `pip install tradedangerous` will consume is actually assembled.

---

## What actually uploads to PyPI

This is the part that is easy to miss.

The upload is **not** done by `uv build`.
It is **not** done by semantic-release.
It is **not** done by Twine in a handwritten shell command in the workflow.

The actual upload to PyPI is performed by this GitHub Actions step:

```text
pypa/gh-action-pypi-publish@release/v1
```

That action is the component which takes the built distributions from the workflow run and publishes them to PyPI.

So the rough division of labour is:

- `semantic-release` decides whether there should be a release
- `uv build` creates the package files
- `gh-action-pypi-publish` uploads those files to PyPI

---

## How authentication to PyPI works

Trade Dangerous uses **PyPI Trusted Publishing**.

That means the workflow does **not** need a long-lived PyPI API token stored in GitHub for normal publishing.

Instead, GitHub Actions presents an OpenID Connect identity to PyPI, and PyPI checks whether that workflow is trusted to publish the `tradedangerous` project.

For this to work, PyPI must be configured with trusted publisher entries that match the GitHub workflow identity exactly.

In practice that means PyPI needs to know:

- the GitHub owner
- the repository name
- the workflow filename
- the GitHub Actions environment name used for publishing

For stable releases, that is the stable workflow and the `pypi` environment.

For prereleases, `prerelease.yml` also needs its own trusted publisher entry if prerelease publishing is intended to work.

---

## Why workflow names matter

PyPI Trusted Publishing is tied to the workflow identity, including the workflow filename.

That means renaming a publishing workflow can break PyPI publication even if the workflow logic itself is unchanged.

Example:

- if PyPI trusts `python-app.yml`
- but the repository now publishes from `release.yml`

then the GitHub workflow can build correctly, cut the GitHub release correctly, and still fail at the PyPI step because PyPI no longer recognises the publishing workflow identity.

So workflow renames on publish-capable workflows are not just cosmetic. They can require corresponding changes in PyPI trusted publisher configuration.

---

## What the GitHub release step does

After a successful PyPI publish, the workflow runs the GitHub release publishing step.

This creates or publishes the matching GitHub release so that the repository release history stays aligned with the package release.

That means the stable workflow is responsible for both sides of the public release:

- publishing the Python package to PyPI
- publishing the matching release entry on GitHub

---

## What "pip install tradedangerous" depends on

For `pip install tradedangerous` to work for a newly released version, all of the following must have happened successfully:

1. the push triggered the stable workflow
2. the tests passed
3. semantic-release decided a release was needed
4. the distributions were built successfully
5. the PyPI publish step completed successfully
6. PyPI accepted and indexed the uploaded distributions

The GitHub release on its own is not enough. A version can exist on GitHub and still be missing from PyPI if the upload step failed.

---

## Common reasons a push does not produce a PyPI release

A push to `release/v1` can run the workflow but still produce no PyPI package for several normal reasons:

- tests failed
- semantic-release decided no new release was needed
- PyPI trusted publisher configuration did not match the workflow identity
- the build failed
- the PyPI upload step failed

So "the workflow ran" and "the package was published" are not the same thing.

---

## Practical troubleshooting checklist

If a push did not result in a new version on PyPI, check these in order:

1. Did `release.yml` run on the push?
2. Did the test matrix pass?
3. Did the release job run?
4. Did the semantic-release step decide a release was needed?
5. Did `uv build` produce distributions?
6. Did the `gh-action-pypi-publish` step succeed?
7. Does PyPI trusted publishing still match the current workflow filename and environment?

That sequence usually identifies the failure point quickly.

---

## Rule of thumb

The stable PyPI publish path is:

- **triggered by** a push to `release/v1`
- **gated by** the test matrix
- **decided by** semantic-release
- **built by** `uv build`
- **uploaded by** `pypa/gh-action-pypi-publish`
- **authorised by** PyPI Trusted Publishing
- **paired with** a matching GitHub release publish step

That is the end-to-end mechanism from `git push` to `pip install tradedangerous`.