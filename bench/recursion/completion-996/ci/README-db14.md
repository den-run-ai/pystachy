# Historical db14 CI checkpoint for PR #996

This collection verifies source `db14f824da52e83ab392a0096c9dd1bbb0895c29`
against the former main commit `06e3ad5d08514ba31fb231fe4636a962fe6578e3`.
Its GitHub synthetic merge is `3c21de737512217db7739705f0786b28140880ab`;
the merge and source trees are both `b7ca39aa08a2ec08f972ec36ae8ea26ed868ddad`.
It is a closed historical checkpoint. Main subsequently advanced through PR #1000,
so these results do not satisfy the current candidate's CI or performance gates.

The collector verified all 61 check IDs against all workflow jobs: 59 successes
and two expected skips (same-repository DCO and main-only badge publication).
It independently remerged all 31 original verification reports, validated 54
logical stages and 84 group-stage records, and checked complete shard membership,
source identities, bootstrap artifacts, explicit opt-in rejections/deferrals,
and coverage parts. All 37 downloaded ZIPs passed SHA256, size and CRC checks.
Lint recorded 890 tests in 30 unittest invocations, with zero unittest skips.

`db14/summary.json` gives the verified counts and limitations.
`db14/remerged-verification.json` is the independently rebuilt complete aggregate.
`db14/artifacts/perf-smoke.json` retains the numerical CI smoke result, whose
successful completion establishes checksums and completion, not performance
acceptance. These measurements compare the old 06e3 baseline with this checkpoint.

`db14/manifest.json` hashes the larger retained local evidence collection;
`publication-files-db14.json` selects the smaller publication set. Original ZIPs,
logs and raw API responses are retained locally and are represented by hashes,
stable GitHub source URLs and artifact IDs in the curated records. Ephemeral
signed download URLs are excluded.

The unchanged collector and its general instructions are `collect_ci.py` and
`README.md`. Offline verification can be repeated with an isolated clean db14
checkout and the retained raw reports:

```sh
python3 ci-evidence/collect_ci.py verify \
  --head db14f824da52e83ab392a0096c9dd1bbb0895c29 \
  --base 06e3ad5d08514ba31fb231fe4636a962fe6578e3 \
  --merge 3c21de737512217db7739705f0786b28140880ab \
  --out ci-evidence/db14 --source ci-evidence/source-db14-validator
```

This verification enumerates the exact-head contract and validates reports. It
does not execute tests or compilers. A later head requires separate raw metadata,
artifacts, checkout and verification; its evidence must not overwrite this one.
