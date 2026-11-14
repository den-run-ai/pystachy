# Next v0.5.0 alpha qualification

This continuation starts from published alpha.2 commit
`80490143498d149d407343ba1cb7aedb1db2d2c5`. Publication is authorized by the
repository owner through tracker #1476; no release gate may be bypassed.

The intake inventory contains all 159 open pull requests observed on 14 November
2026. Its classifications continue the historical alpha.1/2 inventory preserved at
`3790f5ac4ca4ee660bf747bfc062b22b53d5d897`. The selected alpha.3 batch is conditional
on integration and qualification, not a claim that these PRs have shipped.

## Alpha.3 intake

The batch combines #1493's constructor, numeric identity and Lean-boundary fixes
with #1472's comparison declines, #1340/#1341's numeric protocols and bounded
Decimal module, the reflected enum change from #1426, #1408/#1409/#1421's complex
support, and #1412/#1467/#1475's optional, tuple and identity-union keys. Original
histories are retained except the single reflected-enum change, which is extracted
with its original commit recorded. Combined-tree fixes are required where these
independently developed branches interact.

Class-object registries, object/union tuple expansion, the broader composition
stack and additional Decimal operations remain conditional later work. General
async, full native mypy, broad concurrency, collector experiments and native-wheel
prototypes remain outside the committed release scope.

## Required acceptance

Each release needs independent source review, compiler/runtime bootstrap fixed
points, a complete IR/diagnostic comparison against the preceding release, a full
source-bound Lean census and strict storage checks without unexplained proof loss,
the exact-main CI/Installation/Lint/Packages/Performance/Coverage/Variants workflows,
and actual published native, Docker and PyPI artifact verification. Preserve the
19-row PR budget and 15-minute job cap. Alpha publication keeps stable defaults at
v0.4.0. No scheduled monitoring is used.

Current state: integration and focused regressions are in progress; alpha.3 is not
published. Later evidence directories will record immutable source identities and
observed results rather than replacing this initial scope record.
