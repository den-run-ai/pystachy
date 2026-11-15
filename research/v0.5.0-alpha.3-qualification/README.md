# v0.5.0-alpha.3 qualification evidence

**Status: qualification in progress; this snapshot does not authorize publication.**

This research branch preserves completed evidence for [release PR #1494](https://github.com/den-run-ai/pystachy/pull/1494), the integrated [enum repair #1496](https://github.com/den-run-ai/pystachy/pull/1496), and the reviewed [proof-adapter repair #1498](https://github.com/den-run-ai/pystachy/pull/1498). It must not be merged into main.

## Source identities

| Role | Commit | Tree |
| --- | --- | --- |
| Published alpha.2 baseline | `80490143498d149d407343ba1cb7aedb1db2d2c5` | `717a8c9386ae9f5f6545cc3686a9e22282fc560c` |
| Integrated alpha.3 enum repair | `b0bda81ec2b9954c3c5e0f658c051439126a5c22` | `e027b37c888326e3d8a3e8b89522a6b397dcb86d` |
| Reviewed proof-adapter repair | `94f472d6de5350fc9481ecf3b9ec019d2ecdb4f2` | `51f6c150748b2d17945e4d1c6779d8080b6edd6a` |

The adapter repair changes four files under tools. It changes no compiler, runtime, corpus, or Lean theorem source. Existing executions retain their original source identity; the new full census uses the corrected committed source and fresh records.

## Completed evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh bootstrap on integrated source | Compiler 959,093 IR lines and runtime 21,214 IR lines; three identical stages each | [Receipt](bootstrap.json), [log](bootstrap.log) |
| Full retained IR/diagnostic comparison | 4,771 cases; 562 changed records fully explained; zero new rejections or abnormal statuses | [Disposition](ir/full-disposition.md), retained records/review archives |
| Original-input compatibility supplement | 13 executions, 129 original source/helper/sidecar files; zero new rejections | [Disposition](ir/original-input-disposition.md) |
| Bounded build costs | Three paired samples for each of three workloads; correctness checked; overlapping timing ranges | [Results](build-cost.md), command archive |
| Integrated PR checks | CI and Lint pass on b0bda81ec; expected conditional archive job skipped | [Every job](integrated-pr-checks.json) |
| Proof-adapter regression tests | 49 tests pass; new tests fail on the original code; retained complex-decline snapshot now proves 21/21 union reads, 21/21 payload obligations and 4/4 removed checks | Lean repair archive and independent reviews |
| Independent source review | No blocking source/IR issue in reviewed scopes | [Enum](reviews/enum-repair.md), [integration](reviews/integration.md), [adapter](reviews/lean-adapter.md), [qualification](reviews/lean-qualification.md) |

## Incomplete original proof attempt

The first full census on b0bda81ec was intentionally interrupted after 1,865 of 2,699 programs when the reviewed checker repair was available. It retains two inspection subprocess exits of -9 and 18 nested adapter errors across four dynamic-complex programs. Its cause-of-kill remains unproven. It is **incomplete and failed**, and cannot qualify the release. Its observed strict-storage subset is 52 of 196 programs with 14,118/14,118 observed obligations; that subset is not presented as full storage coverage.

A fresh complete census started on 94f472d6 with one worker, all 2,699 programs, all 196 selected storage programs, and no resumed old records. Its results are not included in this snapshot. Existing bounded-model residuals, including complex nullability and three copy-helper GC obligations, remain explicit unproved results until dispositioned against the complete census.

## Remaining release gates

The corrected full census, semantic proof delta, exact-current PR checks/review, exact-main seven-workflow qualification, and public native/Docker/PyPI artifact verification must complete before release closure. Automated Codex review was quota-blocked and is not counted as review. No stable default is advanced by this alpha and no monitoring is scheduled.

## Retained records

Each archive has a manifest with every member's byte length and SHA256. `SHA256SUMS` identifies all published files. The IR archive preserves every case status/diagnostic plus complete raw differences; large reproducible full LLVM files and compiled executables/caches are excluded. Per-case records retain their hashes and source/compiler identities. Review and original-input archives preserve the detailed semantic dispositions and raw supplemental results. The original interrupted proof records and before/after repair evidence are preserved separately from the future corrected census.

Prepared with ChatGPT assistance. These are bounded tests and models, not a proof of whole-compiler or collector correctness.
