# PR #996 CI checkpoint after integrating current main

This collection verifies source `ea68529b8a590eb8f3df7200b857e1d16becd7a3`
against main `07b26e02425d023288ed95a9d2a5077be5aeb45e`, which includes PR #1000.
The GitHub synthetic merge `f5c491ddf1627a35a715ae71167fb5c5126309de` has the
same tree as the source head: `62ad6bb99fbc3e1625f36f167d664f2d8f221801`.
All observations here belong to those revisions; earlier db14/06e3 records
remain separate historical checkpoints.

## Verified CI evidence

All 61 check IDs match the complete workflow-job lists: 59 successes and two
expected skips (same-repository DCO and main-only coverage badge publication).
All seven workflow runs are complete. The collector independently remerged all
31 original verification reports and checked 54 logical stages, 84 group-stage
records, complete corpus/shard membership, source identities, explicit opt-in
rejections/deferrals and coverage parts. The repeated bootstrap records are
30 consumer validations of one producer bundle, not 31 independent bootstraps.

All 37 downloaded ZIPs, totaling 31,795,673 bytes, passed GitHub SHA256, size and
ZIP CRC checks. The CI compiler IR hash is
`4c64d1337da57bc0d88b936d19e9e49da5bf74c241092d80f37621e96e2ac5f1`, matching
the independently recorded local fresh build. The runtime IR hash is
`940a694da5ea93214d1308a8eb635b47d8d0a9d4256c63d084c24f5099f8aa5f`.
The CI and local native binaries have their own recorded hashes and toolchains;
they are not relabeled as the same build.

Lint completed all 32 expected unittest commands exactly once, totaling 919 tests
with zero unittest skips. This includes 213 typed-IR tests, eight diagnostic
capture tests, 20 inspector tests and 108 compiler-state tests. The exact command
membership is derived from this head's Makefile and Lint workflow, then matched
against completed log records in `ea685/lint-command-membership.json`.
Mypy checked 48 source files; CPython 3.13.16 recordings reported zero failures.

`ea685/summary.json` records the complete counts and limitations.
`ea685/remerged-verification.json` retains the independently rebuilt aggregate.
`ea685/artifacts/perf-smoke.json` preserves the numerical CI smoke observations
against current main. A successful smoke workflow verifies completion and
checksums; it does not establish performance acceptance.

## Readiness snapshot and limits

`ea685/readiness.json` records the separate read-only live GitHub check after CI
completed. Main and the PR head still matched the revisions above. The PR was
open, draft, unmerged and mergeable clean, with no review threads or review
submissions and only the two known author comments. The #1000 handoff comment
expressly does not establish performance acceptance or authorize merging.

This collection does not claim completion of the separate local full-corpus
comparison, paired elapsed measurements, native profiling or a performance
acceptance decision. Those records must be evaluated separately on this same
head. Any later source or base change requires renewed binding and validation.

## Reproduction and publication

The unchanged `collect_ci.py` verifier enumerates the exact-head verification
contract and validates retained reports. It runs no tests or compilers:

```sh
python3 ci-evidence/collect_ci.py verify \
  --head ea68529b8a590eb8f3df7200b857e1d16becd7a3 \
  --base 07b26e02425d023288ed95a9d2a5077be5aeb45e \
  --merge f5c491ddf1627a35a715ae71167fb5c5126309de \
  --out ci-evidence/ea685 --source ci-evidence/source-ea685-validator
```

`ea685/manifest.json` hashes every retained local evidence file except itself.
`publication-files-ea685.json` selects the smaller publication set. Raw ZIPs,
logs and API payloads remain represented by recorded hashes, stable GitHub URLs
and artifact IDs; ephemeral signed download URLs are excluded. The full rebuilt
aggregate and numerical smoke JSON are included in the curated publication set.
