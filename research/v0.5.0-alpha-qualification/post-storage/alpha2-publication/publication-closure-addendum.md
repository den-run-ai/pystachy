# Alpha.1/alpha.2 publication and closure addendum

**Both alphas are published and independently verified across GitHub, Docker amd64/arm64 and PyPI.**

This completed addendum supplements the [immutable 180-PR inventory](https://github.com/den-run-ai/pystachy/blob/3790f5ac4ca4ee660bf747bfc062b22b53d5d897/research/v0.5.0-alpha-qualification/dispositions/README.md). The original snapshot remains unchanged: 21 included, 65 conditional, 94 deferred and zero proven superseded heads. Its recorded publication and PR states are historical. This addendum records completed publication and the following closures, not another full PR census or code review.

| Release | Exact source | Published channels |
|---|---|---|
| [v0.5.0-alpha.1](https://github.com/den-run-ai/pystachy/releases/tag/v0.5.0-alpha.1) | `a73c56c92f3aad4b490307a5d1b882e487a57f55` | GitHub, Docker amd64/arm64, [PyPI 0.5.0a1](https://pypi.org/project/pystachy/0.5.0a1/) |
| [v0.5.0-alpha.2](https://github.com/den-run-ai/pystachy/releases/tag/v0.5.0-alpha.2) | `80490143498d149d407343ba1cb7aedb1db2d2c5` | GitHub, Docker amd64/arm64, [PyPI 0.5.0a2](https://pypi.org/project/pystachy/0.5.0a2/) |

Alpha.2 [native Release #67](https://github.com/den-run-ai/pystachy/actions/runs/43626857296) and [PyPI Release #68](https://github.com/den-run-ai/pystachy/actions/runs/43630294045) completed successfully. The final independent acceptance is `7ac9e86a7d4d48482d7d2a55ae77015d04daf21381529008ea6eb50e9ebbbec3`. Actual public assets and Docker layers match tested bytes; public PyPI distributions match the tested packages and immutable source blobs. Fresh public-wheel pip/uv installs passed. Stable defaults remain v0.4.0.

## Integrated stacked PR closures

After final publication acceptance, each live complete head was rechecked. Its merge base with the published alpha.2 source equals that head and it has zero commits outside the release source. A provenance comment was added, the PR was closed, and a fresh API read confirmed the same head and closed state. These are closures of fully integrated history through #1488; they are not additional merges or source changes.

| PR | Complete included head | Closed at UTC | Evidence |
|---|---|---|---|
| [#1415](https://github.com/den-run-ai/pystachy/pull/1415) | `42f7576d77dc08273c2136b1754fc2515b465e71` | 2026-11-14T19:11:42Z | [Closure note](https://github.com/den-run-ai/pystachy/pull/1415#issuecomment-6882790845) |
| [#1281](https://github.com/den-run-ai/pystachy/pull/1281) | `869a61db4c79511235c3a1243e22c215d2d8ebeb` | 2026-11-14T19:11:45Z | [Closure note](https://github.com/den-run-ai/pystachy/pull/1281#issuecomment-6882791628) |
| [#1282](https://github.com/den-run-ai/pystachy/pull/1282) | `cc6c4cabddfc85e5a4ae759509d29331fdf42b52` | 2026-11-14T19:11:49Z | [Closure note](https://github.com/den-run-ai/pystachy/pull/1282#issuecomment-6882792450) |

The earlier alpha.1 closures of #1387, #1410, #1428 and #1429 remain recorded in `alpha1-closed-included-prs.json`; their full heads are included in alpha.1. No branch was deleted or force-pushed.

## Remaining release plan

Continue alpha.3 values/numeric protocols, alpha.4 useful library workflows, alpha.5 final integration/performance, then release candidates and stable. Conditional/deferred classifications are scoped to alpha.1/2 and do not imply blanket rejection from later 0.5 releases. Preserve dependency order and the existing exclusions, the 19-row PR budget, the 15-minute job cap and exact-commit release gates. Tracker #1476 stays open. No scheduled monitoring was created.
