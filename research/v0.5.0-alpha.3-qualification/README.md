# v0.5.0-alpha.3 qualification evidence

**Status: release qualification remains blocked pending the fresh full census on the reviewed storage-adapter repair. Alpha.3 is not published.**

This research branch preserves evidence for [release PR #1494](https://github.com/den-run-ai/pystachy/pull/1494), [enum repair #1496](https://github.com/den-run-ai/pystachy/pull/1496), [sparse-tag/report repair #1498](https://github.com/den-run-ai/pystachy/pull/1498), and [nested optional-tuple storage repair #1501](https://github.com/den-run-ai/pystachy/pull/1501). Build and publication inputs are the pinned source commits below. This research branch must not be merged into main.

## Source identities

| Role | Commit | Tree |
| --- | --- | --- |
| Published alpha.2 baseline | `80490143498d149d407343ba1cb7aedb1db2d2c5` | `717a8c9386ae9f5f6545cc3686a9e22282fc560c` |
| Integrated enum repair and retained runtime/IR executions | `b0bda81ec2b9954c3c5e0f658c051439126a5c22` | `e027b37c888326e3d8a3e8b89522a6b397dcb86d` |
| Complete but strict-storage-blocked proof census | `94f472d6de5350fc9481ecf3b9ec019d2ecdb4f2` | `51f6c150748b2d17945e4d1c6779d8080b6edd6a` |
| Integrated release branch before #1501 | `bbc8c8c38858ea2d90859751e34b885fdea1ca1d` | `51f6c150748b2d17945e4d1c6779d8080b6edd6a` |
| Reviewed storage-adapter repair | `0a2fe77a580106c197face4d2904be80e3f85dbc` | `107460d5f89bdcf37f2741b233eac0568d82604a` |

Both proof repairs change eight tool, test and documentation files. The other 10,485 tracked files, all 4,771 IR inputs and all three build-cost workloads retain their verified bytes and modes. Earlier executions retain their original b0 source identity. The [complete source-equivalence receipt](final-source-equivalence.md) does not waive strict bootstrap source/run checks or identify future public artifacts.

## Completed runtime and source evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh b0 bootstrap | Compiler 959,093 IR lines and runtime 21,214 IR lines; three identical stages each | [Receipt](bootstrap.json), [log](bootstrap.log) |
| Full retained IR/diagnostic comparison | 4,771 cases; 562 changed records fully explained; zero new rejections or abnormal statuses | [Disposition](ir/full-disposition.md), retained-record archive |
| Original-input compatibility supplement | 13 executions, 129 original source/helper/sidecar files; zero new rejections | [Disposition](ir/original-input-disposition.md) |
| Bounded build costs | Three paired builds per workload for three workloads; correctness checked; timing ranges overlap | [Results](build-cost.md) |
| Integrated bbc PR checks | CI, Lint, Submission and managed CodeQL passed; conditional skips accounted for | [Every job](integrated-pr-checks.md), workflow archive |
| Independent source/model review | No blocking finding in the frozen storage repair | [Primary](reviews/optional-storage-root.md), [independent](reviews/optional-storage-independent.md) |
| Residual-fixture native execution | All 12 new residual fixtures passed actual JIT and AOT, 24 executions across six digest-verified report artifacts | [Receipt](residual-native-coverage.md) |

The native executions do not discharge rejected or unsupported proof results. The complex-null deviation uses its explicit handwritten TypeError oracle, not a CPython-parity claim.

## Complete proof census that remains blocked

The 94f4 census includes all **2,699 programs and 196 selected storage programs**. Every alpha.2 program (2,550) and storage selection (175) remains present. All source, input, checker, coverage and completion checks pass. No individual inspection or nested adapter error remains. The independent strict-storage check fails.

The report process first exited -9 after 2,562 records. Its cause remains unproven. The full prefix, log and receipt were preserved before the maintained `--resume` path verified unchanged source, Python, Lean checkers, inputs and inventories. The resumed run appended exactly 137 records. Final record SHA256: `396f4b02ede94afda93ecc796f1da3aa1d3cb022a78939c51c4fc34a22101bbe`. It is a complete resumed census, not an uninterrupted run. [Structural result](lean-94/acceptance.json), [report](lean-94/report.md), [freeze receipt](lean-94/complete-blocked-census.json).

The optional tuple-key fixture has 8/8 counted storage obligations but also three unsupported functions with unknown counts. Therefore the full-corpus known count of 25,682/25,682 is **not strict-storage success**. [Repair diagnosis and validation](optional-storage-repair.md) retains the first refusal, additional masked sites, intermediate rejected results and final focused result.

On the frozen repair, all seven selected target storage functions are accepted and **142/142 obligations** are proved, with no unknown, unsupported, rejected or error result. All **69 storage tests** pass without skips. Replaying the final regression methods with the exact old adapter fails as expected. The focused snapshot is a fresh typed-only inspection; it is distinguished from the full census snapshot. The complete fresh repaired-source census remains required.

## Explicit proof limits and semantic review

The completed 94f4 comparison has 38 decreases in obligation/proved counts, no new residual dictionary among shared programs, and no increase in shared counted or unknown gaps. Exact typed-site attribution and binding to the fresh final census remain pending. A smaller denominator is not accepted without explanation.

The added programs retain **542 rejected union reads and 409 associated unproved payload-bit obligations** in 21 functions across nine complex fixtures. Both counters use the same joint union verdict; their residual functions are listed once under union. Source/IR review explains each first conservative-null-domain failure and does not prove later obligations. [Review](complex-residuals.md).

The new `complex_values.py` fixture contributes three more instances of the existing copy memo-get GC model gap; the full known GC gap rises from 375 to 378. This is distinct from the three gaps in the focused enum check. The new Decimal fixture also retains an unsupported field-inference result with unknown count. All these limits remain explicit. Bounded models and runtime tests do not prove whole-compiler or collector correctness.

The initial b0 attempt remains separately preserved as incomplete and failed: 1,865/2,699 programs, two inspection subprocess kills and 18 nested adapter errors. The corrected 94f4 run resolves all 18 adapter errors and completes both previously killed cases; their kill causes remain unproven. [Historical comparison](lean-94/historical-attempt-comparison.json).

## Evidence correction

Seven TOML IR descriptions previously misidentified receiver checks as tuple-pointer checks and named the wrong exception. The corrected descriptions identify `Output.flags` receivers and `AttributeError`, with exact branch/call/string evidence. Raw IR, statuses and counts are unchanged. [Correction](ir/tomllib-guard-attribution-correction.md) and the correction archive preserve the previous versions and hashes.

## Remaining release gates

Finish the fresh full census and exact denominator/semantic review on 0a2fe77a; finish repair/integrated-head checks and review; merge the release through the normal expected-head path; require all seven exact-main workflows; then publish and verify actual native archives, Docker layers and PyPI distributions. Previous automated Codex attempts were quota-blocked and are not counted as completed review. Stable defaults remain v0.4.0. No monitoring is scheduled.

## Retained records

Each archive has a manifest of every member's byte length and SHA256. `SHA256SUMS` identifies the published files. The initial archives remain as historical evidence; the corrected IR descriptions and complete blocked-census/storage-repair archives supersede their provisional status text. The alpha.2 full baseline records are included as a gzip file with their original uncompressed hash. Large reproducible full retained LLVM outputs and built executables/caches remain excluded from the original IR archive; exact identities and raw differences are retained.

Prepared with ChatGPT assistance. Agent reviews are not claimed human approvals.
