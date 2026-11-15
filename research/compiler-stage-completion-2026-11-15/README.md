# Compiler stage completion and qualification

> **Corrected-head update:** This page records the historical `eabfe7b3` checkpoint. See [the current status and recovered evidence](STATUS_5ccd1841.md) for published head `5ccd1841`, the JIT discovery fix, fresh qualification, and the unconfirmed full local run after the execution environment became unavailable.

This report records the follow-up to [PR #1499](https://github.com/den-run-ai/pystachy/pull/1499). The implementation is published at `eabfe7b3d8f1be3e4615442423c7d3fbab10285b`, with tree `4deb05cd2f645d516dd37480d5510d0920747b6f`. The earlier local commit `527dc89a02e8e8866fc4d83997847663a6e7c0aa` has exactly that tree. The connected GitHub app published the tree because the local shell had no push credentials; every uploaded blob and the complete remote tree were checked against Git before the branch was advanced with an expected-head lease and no force.

The direct comparison baseline is the original PR tip, `800752d8a582bff77d4c375039af786b82a96f73`. Its [initial qualification report](https://github.com/den-run-ai/pystachy/blob/64c894424b43ff69a3601c78f9b0d25fba91371c/research/compiler-stages-2026-11-15/README.md) remains historical evidence. This report does not relabel earlier tests as new runs.

## Architectural changes

The six stages remain explicit and owned by one compilation attempt:

| Stage | Boundary |
| --- | --- |
| `prepare` | Module declarations, aliases, class records and flow analysis. |
| `discover` | Reachability, specialization and typed-IR construction. |
| `analyze` | Effects, recursion policy and initial requested verification. |
| `optimize` | Enabled typed-IR passes. |
| `finalize` | Exception lowering, tuple-return ABI selection, module/export admission and final requested invariants, with function bodies retained. |
| `lower` | Consuming function lowering and LLVM serialization, including C ABI adapters. |

The follow-up closes two backend leaks in the first separation. C externs now retain copied, validated ABI plans rather than rendered LLVM adapters. Discovery still validates annotations and registers dependencies in the original order; lowering serializes those plans without reading the AST or registering additional runtime/link dependencies. Extension export and runtime module admission now finish before finalized typed IR is exposed.

Stage completion rejects empty or unknown names and inconsistent predecessors. With `PYSTACHY_IRCHECK=1`, finalization checks shared numeric operands before publishing retained IR, in addition to the existing backend check.

`tools/inspect_compiler.py --stop-after finalize` exercises the real driver and retry path, preserves the finalized snapshot and source inventory, and emits no LLVM artifact. The default remains full lowering. The Lean corpus reporter uses the finalized target, avoiding an LLVM output it does not consume. Reports bind typed snapshot bytes with SHA-256 and distinguish completed, skipped, unavailable and interrupted work.

This is still an incremental separation. Typing, representation choice and specialization remain coupled during discovery. The retained IR includes native representation decisions and symbols; it is not a portable frontend IR, reusable compiler session, independent source type checker, or implementation of stored typed interfaces.

## Qualification status

**Full local qualification in progress.** The 58-stage local verification is still running. The completed exact-tree checks below are preserved in this evidence checkpoint; the PR remains draft pending the final local results.

Completed checks on the final source tree:

- Compiler bootstrap fixed point: all three compiler stages emitted identical 934,358-line LLVM IR. Runtime bootstrap fixed point: all three emitted identical 21,214-line IR.
- All 59 stage, admission, C ABI and inspection test methods passed on the final tree.
- Ruff, mypy over 59 files, runtime declaration consistency and `git diff --check` passed.
- Focused hosted comparisons matched the original PR on all 11 C ABI cases and all 10 module-admission cases, including accepted and rejected programs.
- The complete retained corpus comparison passed all 4,579 inputs against the original PR compiler: 2,653 accepted by both and 1,926 matching rejections, with zero LLVM/comparator, raw diagnostic or exit-status differences and no new rejections. Both compilers used identical absolute input paths and a common library home after all 105 actual library/runtime files were checked equal. Before/after snapshots confirm unchanged binaries, sources, fixtures and corpus. See the [summary](ir/full-corpus/summary.json), [all case results](ir/full-corpus/case-results.json.gz), [exact command](ir/full-corpus/command.json), and [retained comparator](ir/full-corpus/irsame-retain.sh). This is corpus parity, not an all-program equivalence proof.
- The full required Lean-related suite passed 409/409 test methods with zero skips. A fresh report from the original ten programs proved all 535 obligations or uses, with no rejected or unsupported records. Strict source inventories and all four checker hashes matched before and after.
- Required PR CI, Lint, CodeQL and submission checks passed on the published head. The CI merge checkout has the identical tested tree. CI's PR profile completed 43/43 checks across 14 groups; this is separate from the ongoing full local 58-stage profile.
- CI exercised all 196 FFI checks without skips or failures; the JSON-repair extension replay matched 943/943 cases. See the [CI qualification](ci/README.md), [complete inventory](ci/final-eabfe7b3.json), and [original FFI log](ci/contracts-ffi.log).

The initial native bootstrap exposed missing explicit annotations on the new `ExternDecl` record: the compiler rejected iteration over a field it had inferred as `int`. The record fields were annotated, then hosted self-compilation and the complete compiler/runtime fixed points passed. Both the preliminary failure and the final passing log are retained under [validation](validation/).

## Lean verification

The new `PystachyPipeline.lean` model checks stage sequencing and report/snapshot association. All 11 public pipeline guarantees passed the axiom audit. The focused suite passed 21 test methods, including 208 Python/Lean comparisons over all 13 reachable states, both transition operations, six valid stage names, and empty/unknown names.

The report bridge rejects incomplete stage inventories, malformed mappings, duplicate JSON keys, changed or absent source evidence, mismatched snapshot bytes, foreign or reused attempt indices, incomplete requested IR verification, inconsistent artifact inventories, and a terminal stage different from the requested target. Retry controls reject idle traces disguised as aborted work and retries that cross the requested finalization boundary into lowering.

The proof scope is recorded sequencing and association. Stage semantics, Python object ownership, exporter authenticity, the Python bridge, source provenance, native Lean execution, IR equivalence, GC and LLVM correctness remain trusted or outside the model. These are not whole-compiler correctness proofs. See [the detailed Lean review](lean/review.md), [pipeline build and axiom audit](lean/pipeline-build.log), and [focused tests](lean/pipeline-tests.log).

An earlier combined build was interrupted after proof checking but before executable completion. A diagnostic wrapper also failed because child PIDs were unavailable through `/proc`. Successful final sequential builds superseded both attempts; neither was a Lean counterexample.

The final ten-program report initially refused the active verification checkout because ignored, importable library copies under `build/verify/home/lib` made its strict corpus inventory unclean. No tests ran in that attempt. The successful qualification used a detached checkout of the exact published commit and byte-verified copies of the four existing checker executables, without rebuilding. Both the failed preflight and successful clean-source run are retained under [lean/final](lean/final/).

## Cost measurements

The [measurement runner](cost/measure_costs.py) uses one warm-up per variant followed by five alternating pairs, sequentially pinned to one CPU. Both native compilers consume the same absolute source paths and byte-identical common libraries. It checks exact emitted bytes, records per-child wall/CPU time and peak RSS with `wait4`, captures GC/stage diagnostics, and hashes the source files, runner and binaries before and after. No other owned local build/test job ran during these measurements. The host is shared; unrelated activity was not controlled.

| Workload | Comparison | Median paired wall ratio | Pair range |
| --- | --- | ---: | ---: |
| Compiler self IR | New / original PR | 1.0020 | 0.9428–1.0423 |
| Runtime IR | New / original PR | 1.0445 | 0.9324–1.1251 |
| C FFI fixture IR | New / original PR | 1.1457 | 0.9078–1.2251 |
| Library inspection | Finalize only / full lowering | 0.9753 | 0.9304–1.1546 |
| C FFI inspection | Finalize only / full lowering | 0.9723 | 0.5559–1.0386 |

These timings are inconclusive. The native FFI samples last only about 6–9 milliseconds, and the inspection comparison includes process startup, snapshot serialization and output writes. For library inspection, the ratio of separate medians is 1.0146 even though the median paired ratio is 0.9753. Neither statistic supports a general speedup claim from five pairs on this host. GC instrumentation was enabled identically for both native compilers; allocation counts and execution performance were not measured.

The new compiler binary is 6,729,184 bytes versus 6,724,320 bytes for the original PR: **+4,864 bytes (+0.0723%)**. Median self-compilation peak RSS increased from 902,728 to 915,408 KiB, approximately 12.4 MiB or 1.4%. Its recorded GC heap peak increased from 875.2 to 888.7 MiB, with 14 collections and 192.6 MiB live at the last collection in both versions. This is a measurable memory cost of the follow-up on this workload; its cause was not isolated by these measurements.

Library inspection's reported peak RSS decreased by approximately 0.85%. The FFI inspection high-water mark was exactly 231,768 KiB throughout, after the runner had parsed the large library snapshot. Native FFI likewise remained at 20,100 KiB. Independent review identified a likely inherited parent-memory floor before child `exec`; these measurements therefore cannot resolve the small workloads' own peak memory. The self-compilation peaks greatly exceed that floor and are corroborated by compiler GC counters. None of these RSS figures is a process-tree total or a general memory guarantee.

Every native warm-up and measured output matched its reference exactly. Every finalized snapshot matched the full-lowering snapshot exactly, and every finalized-only run was checked for absence of LLVM artifacts. A separate negative control found 15 rendered extern strings totaling 6,817 LLVM text bytes at the original PR's finalized boundary, versus 15 plans and zero rendered LLVM text bytes after this change. That establishes phase placement, not a memory or performance benefit.

The initial all-mode measurement completed all three native workloads, then stopped because the first library inspection warm-up took 5.67 seconds, exceeding its five-second guard. That failed overall report is preserved in [native and preliminary inspection data](cost/native-and-preliminary-inspection.json.gz). Only the inspection portion was repeated, with an explicit ten-second warm-up limit; the [inspection run](cost/inspection.json.gz) completed. No native timing sample was discarded or repeated to improve a result.

## Reviews and reproducibility

Independent agents reviewed the ABI planning, finalization admission, stage/inspection behavior and Lean report bridge. The bridge review found a malformed nested mapping that could raise `AttributeError`; the adapter now rejects it with a controlled diagnostic and a regression test. Review scopes and remaining limitations are recorded with the test evidence. Automated Codex review was unavailable because the account's review quota was exhausted; that is not a completed review or a code finding.

All implementation files remain on the PR branch. This `research/` directory exists only on the evidence branch and must not be merged into main.

Large JSON records are stored as deterministic gzip files. [The compression manifest](compressed-artifacts.json) records their original byte lengths and SHA-256 digests as well as the compressed digests; decompressing restores the original records exactly. The [raw corpus archive](ir/full-corpus/raw-cases.tar.gz) retains the ordered corpus and every case's two diagnostics, exit statuses and comparison report. Matching LLVM files were deleted only after the maintained comparator checked them; the sources, binaries, harness and reproduction command are pinned by their recorded identities.
