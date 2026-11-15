# Alpha.3 release status

**Blocked by full main CI; v0.5.0-alpha.3 has not been published.** Final main-workflow observation: **2026-11-15 10:03:24 UTC**.

Release PR [#1494](https://github.com/den-run-ai/pystachy/pull/1494) merged normally at `6bf3f73af7edb02c5b2bdb6b2ac23fc3f5fffe93`, with tree `107460d5f89bdcf37f2741b233eac0568d82604a`, exactly matching the reviewed final source. Repairs #1496, #1498 and #1501 are integrated. The [accepted premerge evidence](https://github.com/den-run-ai/pystachy/blob/231e903a8b353ecb1595bed3002cecbc006f0d34/research/v0.5.0-alpha.3-qualification/README.md) remains an immutable record of that earlier gate; it does not supersede the subsequent runtime failures.

## Blocking optional-integer sorting failures

[Issue #1502](https://github.com/den-run-ai/pystachy/issues/1502) tracks four failed full-profile CI jobs: dynany-optin-1 and dynany-optin-2 on Linux x86-64 and ARM64. [Failure logs and exact fixtures/oracles](postmerge/main-ci-failures.json) preserve the direct evidence and its limits.

| Existing fixture under the dynamic-Any sweep | Directly observed AOT stdout difference |
|---|---|
| `tests/programs/optimizations/opt_scalar_none_sort.py` | `sorted(xs[1:])` produces `[3, 1]` where the fresh CPython oracle and committed expected output require `[1, 3]`. The later expected TypeError text matches. |
| `tests/programs/optimizations/opt_scalars_flow.py` | Line 11 is `[3, 1] [2, 1, 3] 3 1 2 2 [3, 1]`, instead of `[1, 2] [3, 2, 1] 3 1 1 3 [1, 2]`. The later expected KeyError text matches. |

Each failed job reports two failed checks. The displayed tail truncates the earlier mode header; earlier-mode details are not reconstructed from that count or from artifact metadata. Both architectures show the same directly visible AOT differences. No rerun, local reproduction, source repair or repair-validation pass is claimed.

### Source diagnosis and history

The [bounded static diagnosis](postmerge/optional-sort-static-diagnosis.json) identifies a concrete descriptor-truncation defect in `pys_list_sort_r`: the identity-companion path constructs `{'K', *d->s, 0}`, copying only one descriptor character. Optional integer/float descriptors `?i`/`?f` therefore become `K?`. The comparator consumes the K and optional markers, sees the terminator instead of the scalar type, leaves representation-box pointers unboxed, and can compare their addresses instead of numeric values. The unchanged ascending order and reversed order observed in CI fit this mechanism; allocation order itself is not guaranteed.

The [history review](postmerge/optional-sort-activation-history.json) identifies commit `f1cb384443531556a3eb61f17a93e34a4399626b` as the source change that enables optional numeric identity kinds 9/10. The entire 47-line sorting function is identical between alpha.2 baseline 8049014 and main 6bf3, and the fixture plus both oracles are unchanged. This is source-level activation attribution, not an executed first-failing-commit bisect. The defect is a strong explanation for CI, not a tested repair.

The repair boundary is to retain the full element descriptor and correct string metadata when prefixing K. Validate optional integers and floats, ascending/reverse sorting, stable item identities, and None exceptions/state. Preserve the existing oracles and add focused coverage that exercises the dynamic-Any path in ordinary PR validation.

## Exact-main workflow outcome

All observed automatic runs are terminal. The [final workflow summary](postmerge/main-workflows-final-summary.json) and [raw API snapshot](postmerge/main-workflows-final-raw.json) preserve complete pagination, every job/step/duration, all 113 checks and all 75 CI artifact metadata entries.

| Release-plan workflow | Result on exact main |
|---|---|
| [CI](https://github.com/den-run-ai/pystachy/actions/runs/43699643821) | **Failed:** 64/68 verification groups passed; four failed groups, with two derived architecture-aggregate failures. |
| [Installation](https://github.com/den-run-ai/pystachy/actions/runs/43699643829) | Passed, all 7 jobs. |
| [Lint](https://github.com/den-run-ai/pystachy/actions/runs/43699643812) | Passed. |
| [Packages](https://github.com/den-run-ai/pystachy/actions/runs/43699643867) | Passed. |
| [Performance smoke](https://github.com/den-run-ai/pystachy/actions/runs/43699643753) | Passed against alpha.2 baseline 8049014; all 49 reported metric comparisons across 11 workloads are OK. |
| [Variants](https://github.com/den-run-ai/pystachy/actions/runs/43699643750) | Passed, 25 jobs and all 28 full configuration/shard cells; zero reported failures. |
| Coverage | **Not run on this main commit.** Manual dispatch remains required. |

CI has 74 jobs: 67 successful, six failed and one source-justified PR-only skip. Its 68 consumers cover 34 groups per architecture, with 32 passing and two failing on each. Source/run/architecture, bootstrap-artifact digest and restoration checks pass for all consumers; these provenance checks do not convert the four failed tests into passes. Both fresh bootstrap producers and the main-only archive qualification passed. All 73 executed CI job logs are preserved in the [x86-64](postmerge/main-ci-x86_64-logs.json), [ARM64](postmerge/main-ci-aarch64-logs.json), and [archive/aggregate](postmerge/main-ci-qualification-aggregates-logs.json) records. The O1/O2 final compiler byte comparison passed; its performance conclusion remains inconclusive.

[Managed CodeQL](https://github.com/den-run-ai/pystachy/actions/runs/43699640898) also completed successfully, with all three analysis jobs and SARIF uploads successful. Its [full logs](postmerge/main-codeql-lint-logs.json) retain extractor limits: Python reports 6,241/6,245 files and contains 154 warning lines plus 18 extractor-error lines; C++ reports 32/33 and Actions 11/11. These totals are not a complete inventory of excluded files. No complete-analysis or no-security-alert claim is made. Issue #1502's separate Submission-format workflow passed. Third-party suite shells with no actual checks are not called passes.

[Installation/Packages review](postmerge/main-installation-packages-summary.json), [performance review](exact-main/performance-review.json), and [variants review](exact-main/variants-review.json) retain their distinct limits. These are remote workflow observations; public native/Docker/PyPI bytes have not been independently downloaded or audited.

## Preserved premerge evidence

The fresh census covers 2,699 programs and 196 strict-storage selections, with 25,816/25,816 storage obligations proved and all 38 denominator decreases reviewed. The 4,771-case IR comparison has zero new rejections and 562 explained differences. Earlier failed census attempts, source bindings, independent reviews and package integrity evidence remain intact at the pinned premerge commit. Runtime/bootstrap/build-cost executions keep their original b0 identities; the final census keeps its 0a2 identity; main executions keep their 6bf3 identity.

The bounded proof limits remain explicit: 542 added union-read obligations, 409 associated payload obligations, three added instances of an existing GC-model gap, and one Decimal field case with an unknown obligation count. Runtime tests do not discharge those limits, and the passing proof census does not supersede the full-main sorting failures.

## Infrastructure and required continuation

The execution workspace became unavailable and browser controls were withdrawn after the completed premerge evidence audit. GitHub remained available for merge verification, remote CI review and evidence preservation. Local reproduction and repair qualification, an exact-main checkout, manual Coverage/Release dispatch and actual public artifact execution/byte audits remain blocked by the unavailable environment. The observed cause of the workspace outage is not established.

Restore execution access, reproduce and repair #1502, then qualify the actual repaired source and integration commit. Recheck source/run identities and all seven release-plan workflows; do not relabel the current failed run as repaired evidence. Coverage must compare the release source with `80490143498d149d407343ba1cb7aedb1db2d2c5`. The [recorded publication plan](postmerge/README.md) retains native Release and approved PyPI dispatch inputs and public artifact requirements; reassess actual main after any repair or other change.

No native Release or PyPI dispatch has been made. The direct GitHub lookup for release tag v0.5.0-alpha.3 returned not found during final verification. Native/Docker/PyPI publication and public-byte audits are incomplete. Issue #1476 remains open. Observers have stopped; no background monitoring or scheduled task was created.
