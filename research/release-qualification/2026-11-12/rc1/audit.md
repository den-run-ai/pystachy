# RC.1 candidate qualification

Candidate: `886ed9153e954b387f2afd39578a21168771ae6e`, tree `64f1fb7295efd25401052d61a22823681e5669ab`. Baseline: `0b13a2121014d8256954c6af50339ff0de8dac62`. The local integrated commit `7c75948747090c7d6a0a0bf76f9aecee8de90a15` has the identical candidate tree.

Source integration, independent review and evidence adjudication used ChatGPT. [PR #1389](https://github.com/den-run-ai/pystachy/pull/1389) tracks the current candidate, required reviews and remaining release qualification.

## Frozen corrections

| Correction | Provenance | Retained IR cases |
|---|---|---:|
| Exception field fallback and assignment flags | Isolated `b27908f4` from #1278; regression #1333 | 7 |
| GC scanning for lists constructed from empty tuples | Isolated `e7ec9bb8` from #1278 | 15 |
| Inherited dynamic-Any classmethod defaults | #1357 | 1 |
| Enum empty-format custom string behavior | #1349 | 3 |
| Void-return union calls such as time.sleep | #1363 | 1 |
| Inlining preserved through listguard duplication | #1336 | 4 |

Full-profile CI redistribution changes Python-free and UBSan shard counts, relocates ASan controls and increases hosted Coverage shards. The PR profile remains at 19 rows with unchanged process and 15-minute limits.

## Complete compiler comparison

[Diagnostic run 43304687640](https://github.com/den-run-ai/pystachy/actions/runs/43304687640), attempt 1, independently bootstrapped each source and retained sealed same-run bundles. Both compiler and runtime fixed points passed. Source-specific homes and libraries were kept separate.

All **4,464 inputs and 8,928 compiler records** are complete. Both versions returned status 0 for 2,554 inputs and status 1 for 1,910 inputs. There are no exit-status changes, new rejections, missing records or unexplained differences.

[adjudication.json](adjudication.json) accounts for all 351 raw-different cases: 250 source-home literals in IR, 70 source-library paths in diagnostics, and the 31 intended IR corrections above. The original conservative diagnostic normalizer removes 56 path-only diagnostic differences and leaves 14 visible for explicit review. Raw IR and diagnostic files remain unchanged. Every source/input/sidecar identity and all 14,036 raw IR/log hashes were checked. All seven exception-field deltas received an additional independent review in [retained-exception-review.json](retained-exception-review.json).

The full raw archive remains in the workflow artifact. Its SHA-256 is `5a22a18cbc8239da6cc4ce2c7945cb5fa5c5ce49c43f72ec6bec1539984410da`; the downloaded outer artifact ZIP is `1a5da3ed226aa7bda6b4e86999afd34bcfd2efaaa80967ecdeabb631b5ca9b08`.

## Native and local evidence

Pinned CPython 3.13.16 and LLVM 19.1.7 produced three identical compiler stages (914,514 IR lines) and three identical runtime stages (21,214 lines). Twelve new behavioral cases passed normal and program-GC-stressed JIT/AOT: **48 successful checks**. The two isolated safety corrections also have 28 effective baseline controls that reproduce the unfixed failures. The independent source review covered 32 cases and 30 CPython fixture-oracle comparisons.

[The local logs](local/) preserve the checks as executed. The LLVM 19 runtime-effect checker reports 57 wL/wD diagnostics identically on the baseline and candidate; its paired baseline comparison is retained. [Hosted LLVM 18 Lint](https://github.com/den-run-ai/pystachy/actions/runs/43304014306) passed. This report makes no claim that a full local make verify passed.

[safety-handoff.json](safety-handoff.json) records the earlier isolated safety-fix phase at `897d96b2`, including stages that had not run then. The combined candidate fixed points, full compiler comparison and CI are subsequent evidence with their own source identities.

## Performance

For the original float workload, 11 alternating AOT pairs pinned to CPU 3 on an AMD EPYC 9V74 yielded median times of **45.598 ms versus 40.100 ms**, a 12.06% reduction. All 22 outputs matched CPython; the candidate was faster in ten pairs. The slow 55.912 ms sample is retained.

Program IR differs by one alwaysinline attribute, the candidate removes the constructor call/symbol, and runtime IR is identical after module/source-filename metadata removal. [Commands and raw samples](performance/) retain build identities and load observations. This evidence covers Linux x86-64 with LLVM 19; it does not independently re-establish #1300's historical pre-regression baseline or other-platform results.

## CI and release requirements

[PR CI](https://github.com/den-run-ai/pystachy/actions/runs/43304014521) and Lint passed on the candidate. [Full candidate CI](https://github.com/den-run-ai/pystachy/actions/runs/43307321551), attempt 1, passed all 73 required jobs, with one expected PR-only skip and no retries or cancellations. Both platform aggregates ran their complete-report and every-group checks. Each combined full-profile report passes with 35 groups (bootstrap plus 34 verification groups) and 58 checks. Complete GC groups, contract probes and generated ASan controls passed before the PR was marked ready.

[The full CI receipt](ci/candidate-ci-receipt.json) indexes source identity, all 74 jobs and retained report hashes. [The timing audit](ci/full-ci-audit.json) preserves the mixed CPU profiles. The longest job took 717 seconds on znver3; the znver3 GC self-compilation step took 295.764 seconds. These are single-run measurements, not the required repeated all-znver3 cohorts or a source-size scaling sweep. Independent review of the CI plans, failure propagation and release notes found no blocking issues.

Release publication additionally requires CI, Installation, Lint and Packages on the exact merged-main commit, followed by tested-versus-public archive, Docker and PyPI verification. The candidate report is evidence for its stated source only. #1178, #1179 and #1181 remain open until their repeated-run headroom and GC scaling criteria are met.

## Separate follow-up

Review of newly opened #1392 confirmed a pre-existing IntEnum/IntFlag sys.exit status limitation on both the baseline and this frozen candidate. Its proposed repair also consults overridable or mutable enum state. A separate correction is under development and is not included in RC.1. The original proposal and follow-up must pass their own semantic, layout and GC qualification before inclusion in a later candidate. Existing eager exception formatting is a separately retained limitation.
