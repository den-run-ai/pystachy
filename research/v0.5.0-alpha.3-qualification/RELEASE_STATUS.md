# Alpha.3 release status

**Blocked at main qualification; not published.** Observed 2026-11-15 09:55:50 UTC.

PR [#1494](https://github.com/den-run-ai/pystachy/pull/1494) merged normally at `6bf3f73af7edb02c5b2bdb6b2ac23fc3f5fffe93`, with tree `107460d5f89bdcf37f2741b233eac0568d82604a`, exactly matching the reviewed final source. [Premerge qualification](https://github.com/den-run-ai/pystachy/blob/231e903a8b353ecb1595bed3002cecbc006f0d34/research/v0.5.0-alpha.3-qualification/README.md) remains preserved as its own historical gate; it is not completion of the later main/release gates.

## Blocking main CI failures

[CI run43699643821](https://github.com/den-run-ai/pystachy/actions/runs/43699643821) has four failed full-profile jobs: dynany-optin-1 and dynany-optin-2 on Linux x86_64 and ARM64. Other CI consumers were still finishing at this checkpoint. [Failure logs, exact fixtures/oracles and bounded observations](postmerge/main-ci-failures.json) retain the evidence without a rerun or source change.

| Fixture under the dynamic-Any sweep | Directly displayed AOT stdout mismatch |
|---|---|
| `tests/programs/optimizations/opt_scalar_none_sort.py` | `sorted(xs[1:])` produces `[3, 1]` where the fresh CPython oracle and committed expected output require `[1, 3]`. The later expected TypeError text matches. |
| `tests/programs/optimizations/opt_scalars_flow.py` | Optional-int sorting yields line11 `[3, 1] [2, 1, 3] 3 1 2 2 [3, 1]` instead of `[1, 2] [3, 2, 1] 3 1 1 3 [1, 2]`; the later expected KeyError text matches. |

Each failed job reports two failed checks. The summarized log tail truncates the earlier mode header; the exact earlier-mode bytes are not reconstructed from artifact metadata. Both architectures show the same directly visible AOT differences. This points to optional-int sorting under dynamic Any; a compiler root cause has not been established. No local reproduction or repair is claimed. Preserve the existing oracles and all failed evidence.

## Completed remote gates

- Installation and Packages passed on the exact main commit. [Review](postmerge/main-installation-packages-summary.json), [raw logs/API/source](postmerge/main-installation-packages-raw.json), [exact commit response](postmerge/main-installation-packages-commit-raw.json).
- Performance smoke passed against alpha.2 commit `80490143498d149d407343ba1cb7aedb1db2d2c5`: all49 reported comparisons across11 workloads are OK. [Bounded review](exact-main/performance-review.json).
- Variants passed all25 jobs and all28 configuration/shard cells with zero reported failures. [Full-profile review](exact-main/variants-review.json).
- Lint passed. Both fresh CI bootstrap producers and the main-only archive qualification passed, but the overall CI gate remains blocked by the failed groups. Managed CodeQL was still running at this checkpoint.

Remote workflow reviews do not claim independently downloaded public artifact bytes. The public native/Docker/PyPI audit remains unperformed.

## Infrastructure and next required work

The execution workspace became unavailable and browser controls were withdrawn after the completed premerge evidence audit. GitHub metadata, logs and evidence publication remain accessible. Local reproduction, an exact-main working checkout, manual Coverage/Release dispatch, and actual public artifact execution/byte audits cannot proceed through the currently available environment.

First reproduce and repair the two optional-int sorting failures; qualify the repair on its actual source and integration commit. Do not relabel prior source/run evidence or weaken the failing tests. Then require all seven exact-main workflows, including Coverage dispatched from main with baseline `80490143498d149d407343ba1cb7aedb1db2d2c5`. The [recorded publication plan](postmerge/README.md) preserves native and approved PyPI dispatch inputs and complete artifact verification requirements. Reassess actual main if a repair or any other commit changes it.

No native Release or PyPI dispatch has started, and no alpha.3 public artifact verification is claimed. The broader release tracker #1476 remains open.
