---
name: release
description: Plan, qualify, publish and audit a Pystachy alpha, release candidate or stable release, including PyPI and Docker. Use when asked to cut, continue, finish or verify a release, or to decide whether a version is ready for its next stage.
---

# Releases

[Releasing](../../../docs/releasing.md) is the reference for the workflows, gates and
recovery; this skill is the order of work. Each step needs the maintainer's authorization
for its outward actions: merging, dispatching workflows and publishing.

## Choose the stage and scope

1. Apply the [release stages](../../../docs/releasing.md#release-stages): at most three
   alphas and two candidates per minor version; a candidate takes fixes only; the stable
   release waits until no major bug from the alpha merges remains open.
2. Read every page of open issues and pull requests. Classify each bug as major or not,
   and whether an alpha merge introduced it; reproduce reports on current main before
   relying on them. A candidate defers features to the next minor version.
3. Build the scope on one integration branch: merge each pull request with a merge commit
   after its own CI, fix review findings with regressions, and run
   `make irsame REF=<previous release commit>`, explaining every difference (#409).

## Prepare the integration pull request

4. Set `VERSION` and add `docs/releases/VERSION.md` per the
   [writing guide](../../../docs/writing.md#release-notes); run
   `python3 tools/release_notes.py check docs/releases/VERSION.md`.
5. Refresh `tools/lean_boundary/REPORT.md` with `make lean-report` (Lean from `elan`, about
   20 minutes with `LEAN_REPORT_FLAGS="--jobs 3"`). It refuses untracked importable files,
   so keep `irsame` references outside the checkout. Compare its rejected and unproved
   counts with the previous release's report.
6. Validate locally, then run **CI** manually on the branch: only a run that is not for a
   pull request executes the full profile (#1502). Open the pull request per the
   submission format, wait for its checks and merge with a merge commit at the expected
   head SHA.

## Qualify the exact main commit

7. On the merge commit, require **CI** (both architecture aggregates), **Installation**,
   **Lint** and **Packages**; the Release workflow waits only for these four. Also record
   **Performance smoke** from the push, and dispatch **Variants** and **Coverage** with
   `base` set to the previous release's commit. Read every job page (`per_page=100`) and
   tell expected conditional skips from missing or cancelled jobs.

## Publish

8. Dispatch **Release** from `main` with `version` set to `VERSION` and `pypi` set to
   `off`. It publishes the GitHub release, archives, `SHA256SUMS` and Docker tags; a
   prerelease never moves `latest`.
9. Dispatch **Release** again from a ref the `pypi` environment allows (so far
   `release/pypi-v0.2.0`), with the same `version` and `pypi` set to `publish`.

## Audit what was published

10. Download each archive and `SHA256SUMS` (its names may carry a `./` prefix), check the
    hashes, and run the archive's `bin/pystachy --version`: it must report the version
    and the release commit.
11. Check that the Docker version manifest lists amd64 and arm64, and that
    `docker run --rm IMAGE:VERSION --version` reports the version and commit. Retry
    anonymous registry requests after rate limits.
12. Check that PyPI holds the tested sdist and wheel, and compare the sdist's files with
    the Git blobs at the tag. A pip installation reports `commit unknown` by design.
    For a stable version, also check that GitHub's latest release, Docker's `latest` tag
    and PyPI's current version all name it.
13. Comment on the issues the release advances, with `Refs` for partial work, and file
    follow-ups for anything the audit found.
