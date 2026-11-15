# Alpha.3 publication continuation

Recorded 2026-11-15 09:35:07 UTC. **Release code is merged and premerge qualification is accepted; publication is not complete.** The execution workspace became unavailable and browser controls were withdrawn after the completed evidence audit. GitHub remains available for preserving evidence and observing automatic CI. No Coverage, native Release or PyPI dispatch has been made, and no public artifact verification is claimed.

## Completed source and review gates

- PR [#1494](https://github.com/den-run-ai/pystachy/pull/1494) merged normally at `6bf3f73af7edb02c5b2bdb6b2ac23fc3f5fffe93` on 2026-11-15T09:31:16Z. The expected release head was `328b945f02788b296d9981d1b44706a2a0092255`.
- The main tree is `107460d5f89bdcf37f2741b233eac0568d82604a`, identical to the reviewed proof source `0a2fe77a580106c197face4d2904be80e3f85dbc`. Main parents are baseline `80490143498d149d407343ba1cb7aedb1db2d2c5` and release head `328b945f02788b296d9981d1b44706a2a0092255`.
- [Accepted, integrity-audited premerge evidence](https://github.com/den-run-ai/pystachy/blob/231e903a8b353ecb1595bed3002cecbc006f0d34/research/v0.5.0-alpha.3-qualification/README.md) preserves all earlier failed census attempts and source roles. The fresh final census covers 2,699 programs and 196 storage selections, with 25,816/25,816 strict storage obligations and no storage unknown-count entries. All 38 denominator decreases are reviewed.
- Retained bootstrap, IR and build-cost executions remain pinned to b0. Exact-main CI must produce its own fresh per-architecture bootstrap evidence; source equivalence does not waive source/run identity checks.
- [Ready-review summary](pr1494-ready-review-summary.json) and [raw evidence](pr1494-ready-review-raw.json) preserve all applicable checks, the setup-only cancelled Submission run and its successful replacement, and the quota-failed Codex review. The independent reviews are completed agent reviews, not a completed Codex or human review.

The accepted bounded-model limits remain 542 added union-read obligations, 409 associated payload obligations, three added GC gaps and one unknown-count Decimal field case. Native passes do not discharge these proof limits.

## Remaining exact-main gates

Six main-push workflows started on `6bf3f73af7edb02c5b2bdb6b2ac23fc3f5fffe93`: [CI](https://github.com/den-run-ai/pystachy/actions/runs/43699643821), [Installation](https://github.com/den-run-ai/pystachy/actions/runs/43699643829), [Lint](https://github.com/den-run-ai/pystachy/actions/runs/43699643812), [Packages](https://github.com/den-run-ai/pystachy/actions/runs/43699643867), [Performance smoke](https://github.com/den-run-ai/pystachy/actions/runs/43699643753), and [Variants](https://github.com/den-run-ai/pystachy/actions/runs/43699643750). [Managed CodeQL](https://github.com/den-run-ai/pystachy/actions/runs/43699640898) also started. Preserve all job pages, actual steps and any failures; select the newest applicable exact-head runs. The initial snapshot is not a terminal-success claim.

Coverage needs a manual dispatch of `coverage.yml` from `main`, with `base=80490143498d149d407343ba1cb7aedb1db2d2c5`. Its default origin/main would compare the merged head against itself. Verify the resulting run actually uses main commit `6bf3f73af7edb02c5b2bdb6b2ac23fc3f5fffe93`. Coverage percentages are advisory; the workflow and tests must pass. All seven named workflows are required by this release plan, even though release_gate.py automatically enforces only CI, Installation, Lint and Packages.

CI must show fresh unreused bootstrap producers on x86_64 and aarch64 in its own run, the full 34 verification groups on each architecture, both architecture aggregates, and the main-only bootstrap-tier/native-archive qualification. Commit, complete tracked source bytes/modes, ABI/toolchain/Python, run ID, checksums and fixed-point witnesses must agree. Do not reuse b0 results under the main identity.

## Publication after the gates pass

1. Recheck live main and the exact tree. Use a clean checkout of the actual main release commit when workspace execution is restored. If main changed, reassess the release source and gates rather than silently relabeling evidence.
2. Dispatch `release.yml` from `main`, with `version=v0.5.0-alpha.3` and `pypi=off`. Verify the native Release run's actual source commit. Require its complete native and container jobs, public prerelease and tag to identify that same commit.
3. Download the actual public Linux x86_64/ARM64 and macOS x86_64/ARM64 archives, checksums/ABI reports, and both Docker architectures. Verify public bytes against successful workflow artifacts and source identity. Check actual Linux launcher/binary version, relocation, read-only resources, JIT/AOT, GC/cache behavior; remote platform jobs support the other architectures only when their tested/public bytes match. Verify Docker manifests/configs, compressed layer digests and decompressed DiffIDs. Metadata alone is insufficient.
4. Once the native release is public, recheck approved publisher branch `release/pypi-v0.2.0` at `6e5544cfa3eecb8329e4f4cb19d2e0ac3e99b1bf` and its publishing logic. Dispatch `release.yml` there with `version=v0.5.0-alpha.3`, `pypi=publish`. The workflow-logic commit and package-source commit differ intentionally; package source must be the public alpha.3 tag at the actual main release commit. Preserve environment restrictions.
5. Verify public PyPI `0.5.0a3` wheel/sdist bytes against tested artifacts and source; perform fresh isolated pip and uv installs and actual console/runtime checks. Preserve any hosted version output such as commit unknown rather than replacing it with an assumed SHA.
6. Reconfirm stable defaults: GitHub v0.4.0, PyPI 0.4.0, Docker latest `sha256:037f5691b17c9ae9a8afb6be79bf6870a1a81fb9ada67ec5e3d9dd5b08d60d01`. Record actual public audit evidence and update the alpha.3 tracker status; broader issue #1476 stays open.

The unavailable workspace/browser is an infrastructure blocker, not a proof waiver or permission request. All release and artifact gates remain intact. No unrelated PR, including #1495, is part of this work.
