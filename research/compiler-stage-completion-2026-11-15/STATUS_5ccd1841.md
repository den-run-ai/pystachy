# Corrected compiler-stage status and recovered evidence

**Implementation is published; full local qualification is incomplete.** [PR #1499](https://github.com/den-run-ai/pystachy/pull/1499) is open, draft and unmerged at `5ccd1841e2090a6a8e4076ed22f0cb4c015a94e8`, tree `b8c3b7b1a6d6517f716934b1600e31caf434bd7a`.

The execution environment became unavailable during the fresh 58-stage local verification. At its last confirmed observation, 09:24:31 UTC on November 15, 2026, bootstrap was still active and no stage had completed. The run began at 09:19:11 UTC. Its later process state and exit status cannot be established. This report does not count it as a pass.

The code, documentation and tests were already published before the outage. Several substantial qualification runs also completed before it. This update distinguishes observed results, recovered original records, and local records that could not be published after workspace access failed. The [earlier comprehensive report](README.md) describes the preceding `eabfe7b3` revision and remains historical.

## What changed

The six explicit stages remain:

| Stage | Responsibility |
| --- | --- |
| `prepare` | Declarations, aliases, class records and flow analysis. |
| `discover` | Reachability, specialization and typed-IR construction. |
| `analyze` | Effects, recursion policy and initial requested verification. |
| `optimize` | Enabled typed-IR passes. |
| `finalize` | Exception lowering, tuple-return ABI selection, module/export admission and final requested invariants; function bodies remain available. |
| `lower` | Consuming function lowering and LLVM serialization, including C ABI adapters. |

The follow-up closes two leaks across those boundaries. C externs retain copied, validated ABI plans until serialization; discovery registers their dependencies in the original order, and serialization needs no AST or additional dependency registration. Extension export and runtime module admission finish before finalized typed IR is exposed.

Stage completion rejects empty or unknown names and inconsistent predecessors. Requested IR verification checks shared numeric operands before publishing finalized IR, as well as after backend lowering.

`tools/inspect_compiler.py --stop-after finalize` follows the real driver and retry path, retains the finalized snapshot and consumed-source inventory, and emits no LLVM artifact. Full lowering remains the default. The Lean reporter uses the finalized target. Reports bind snapshot bytes by SHA-256 and distinguish completed, skipped, unavailable and interrupted work.

The new Lean pipeline model checks ordering and report/snapshot association. Its eleven public guarantees were axiom-audited; the focused tests compare all 208 combinations of thirteen reachable states, two operations and eight valid/invalid stage names with the Python implementation. The report bridge rejects malformed or incomplete evidence, inconsistent attempts and targets, source changes, incomplete requested verification and snapshot mismatches.

Typing, representation selection and specialization remain coupled during discovery. The retained IR contains native representation choices and symbols. This work does not implement stored typed interfaces or a reusable compiler session, and `pystachy check` remains parse-only. The Lean results cover bounded models and recorded contracts. Stage semantics, exporter fidelity, Python object ownership, the normalization bridge, provenance, native checker execution, GC and LLVM correctness remain outside these proofs or trusted.

## A real issue found by full verification

The first full local attempt used `eabfe7b3`. It completed eight passing stages, including the ordinary native and optimizer-disabled sweeps, each with 7,272 passing checks. Runtime-cache then failed 24 of 192 checks: twelve native and twelve CPython-hosted launcher checks. The run was stopped after preserving its evidence.

Investigation reproduced a pre-existing driver defect. The real LLVM executable and its symlink both ran successfully, but `ldd` applied to the symlink could not find the executable's `$ORIGIN/../lib` dependency. Direct `ldd` resolved it. The complete affected `jit_launcher` function was byte-identical on main `8049014`, the original PR `800752d8`, and `eabfe7b3`. The discrepancy is consistent with [glibc's documented explicit-loader/symlink behavior](https://sourceware.org/pipermail/glibc-bugs/2019-December/046908.html).

The correction passes the resolved executable path to `ldd` and changes the discovery recipe from `lljit-v1` to `lljit-v2`. The version change is necessary because a persisted `- no-libLLVM` entry does not include driver-source identity. Invocation paths and script-wrapper fallback remain intact.

Two new tests use actual ELF executables and unique shared libraries, including a tool path containing spaces. They distinguish successful library discovery from a missing-library fallback, test canonical cache reuse, and seed an old negative entry. The controls observed before publication were:

| Driver variant | Result |
| --- | --- |
| Original driver | Both new tests fail with the expected missing-library result; actual executable invocation succeeds. |
| Canonicalized lookup with the old cache recipe | Fresh discovery passes; stale-cache migration fails. |
| Complete correction | Both new tests and the existing real-LLVM cache/wrapper test pass. |

Independent review checked the correction and the fixture. The fixture was refined to preserve Clang's loader environment during compilation, then isolate loader variables for execution and discovery. Current-head CI also passes all seven LLJIT tests. This change does not promise atomic protection against concurrent tool or symlink replacement.

## Completed qualification on the corrected source tree

| Check | Observed result |
| --- | --- |
| Separate local compiler bootstrap | Stage 1 = stage 2 = stage 3, 934,363 LLVM lines. |
| Separate local runtime bootstrap | All three stages identical, 21,214 LLVM lines. |
| Comparison against the original PR | 4,579/4,579 inputs match: 2,653 accepted and 1,926 matching rejections; no LLVM/comparator, raw diagnostic or exit-status differences. |
| Source and input controls for that comparison | 105 actual library/runtime files per home match; 61 compiler source files and 9,045 fixture/dependency files checked; before/after identities unchanged. |
| Stage/inspection methods | 59 pass in CI; locally 53 passed first, then all six ABI methods passed after correcting the test import path. |
| Static checks | Ruff, mypy over 59 source files, and runtime-table consistency pass. The latter checks 672 entries, 70 exception classes and 193 runtime-subset functions. |
| Required Lean unit suite | 409/409 tests pass, with zero skips, failures or errors. |
| Fresh original ten-program Lean report | 535/535 bounded obligations or uses proved; no rejected or unsupported records. |
| PR-profile CI | 43/43 verification checks across fourteen groups. |
| Full FFI qualification in CI | 196 passed, zero failed, no skipped modes. |
| Runtime-cache qualification in CI | 192/192 checks pass: 95 native and 97 hosted. |
| JSON-repair extension replay | 943/943 recorded cases match. |
| Full local 58-stage profile | **Completion unconfirmed after environment loss; not a pass.** |

The focused local test invocation initially used package-qualified module names without the tests' import path. One ABI module could not load; 53 actual methods passed. Only the six missing methods were replayed with the correct import path and passed. The original failed invocation was retained locally. CI ran all 59 methods successfully in its maintained invocation.

The fresh Lean run used a clean detached checkout of the exact published commit. All four checker binaries were copied only after their source tree and hashes matched the earlier audited build; proof sources, bridges, tests and reporter were unchanged. Source and checker identity checks passed before, between and after the unit suite and report. The report used two workers with `spawn`.

The comparison's candidate native binary SHA-256 is `4c2112aff1193b50bd07a222e80fb4758498ae7a90438bcbf20c4cc4602fa81f`; the original PR binary is `33c0fb45f19776c5f1f9c96252f4c82af89e267ffbfc82f376eff165823dd757`. Both compilers consumed identical absolute paths and a common byte-verified library home. This is corpus parity, not an all-program equivalence proof.

## Current CI records

[CI](https://github.com/den-run-ai/pystachy/actions/runs/43697221888), [Lint](https://github.com/den-run-ai/pystachy/actions/runs/43697221818), [CodeQL](https://github.com/den-run-ai/pystachy/actions/runs/43697217840), and the submission checks passed. At the captured final inventory there were 24 check runs: 22 successful and two intentional skips, with no pending or failed checks. Subsequent description edits can add another submission-format run.

The test merge `b08a344558fc87aeb211470c8e58f154e76d4c5b` combines base `80490143498d149d407343ba1cb7aedb1db2d2c5` with the corrected head and has the same tree as the tested head. Before the outage, all 61 source hashes in CI's bootstrap record matched the clean local checkout.

Recovered records:

- [Normalized API inventory](ci/final-head/api-inventory.json).
- [Bootstrap job log](ci/final-head/bootstrap-job.log).
- [Aggregate verification job log](ci/final-head/verification-job.log).
- [Contracts/FFI job log](ci/final-head/contracts-job.log).
- [Cache/GC job log](ci/final-head/cache-gc-job.log).
- [Lint job log](ci/final-head/lint-job.log).
- [GitHub artifact metadata](ci/final-head/artifacts-api.json).

The CI artifact ZIPs were downloaded and their digests checked before the outage. GitHub currently records their expiry as November 22, 2026:

| Artifact in the CI run | ID | SHA-256 |
| --- | ---: | --- |
| Aggregate verification | 14154489108 | `6f9ba7aa9900aa852411eb365de347df90b8885793816b0bddb45569f50c362a` |
| Contracts/FFI | 14154804525 | `0978921a37a6e04aa06a343860d94e38b302fae0fa0a92d79ca89362c9277caa` |
| Cache/GC | 14154918314 | `64877f4638f64ec613b178bce0ea8e98bac424e87787b94117745974e80d3308` |
| Bootstrap verification | 14154573890 | `964d2c15700711a240db33bb91bd612841412136144a723abda0cecf0cf6b524` |

## Fresh cost observations

The completed run used one warmup per variant and five alternating measured pairs per workload, sequentially pinned to one CPU. All fifty measured samples and ten warmups were retained in its records, including slow samples. Exact native outputs and finalized snapshots matched, and finalized-only inspections emitted no LLVM. Recorded sources, binaries and the measurement script were unchanged.

| Workload | Comparison | Median paired wall ratio | Pair range |
| --- | --- | ---: | ---: |
| Compiler self IR | New / original PR | 0.9563 | 0.8466–2.9120 |
| Runtime IR | New / original PR | 0.9768 | 0.9426–1.8890 |
| C FFI fixture IR | New / original PR | 0.9735 | 0.8434–1.0743 |
| Library inspection | Finalize / full lowering | 0.8723 | 0.7490–1.1109 |
| C FFI inspection | Finalize / full lowering | 0.8492 | 0.2218–0.9933 |

These timings are inconclusive. One self-compilation sample took 19.78 seconds and 17.24 CPU seconds; its cause was not established, so it cannot be attributed only to scheduling delay. Five pairs on this shared host do not justify a general speedup or regression claim. No sample was discarded or repeated to improve the result.

The new binary is 6,729,184 bytes versus 6,724,320 for the original PR: **+4,864 bytes (+0.0723%)**. Self-compilation median peak RSS increased from 904,228 to 915,764 KiB: approximately **11.3 MiB (+1.276%)**. GC heap peak increased from 876.8 to 889.3 MiB, with fourteen collections and 192.6 MiB live at the last collection in both variants. The memory cost is measurable on this workload; its cause was not isolated.

Library inspection's reported median RSS decreased from 318,224 to 315,536 KiB. Native FFI stayed at 20,092 KiB and inspection FFI at 230,340 KiB. Those small-workload high-water marks are subject to an inherited pre-exec parent-memory floor, so their equality does not establish equal target-only memory consumption. These are not process-tree totals or general memory guarantees.

The earlier `eabfe7b3` measurements remain in the historical report. This fresh run was needed because the code changed. It completed with the explicitly chosen ten-second warmup guard. Its original report and full raw archive were verified locally before workspace access failed, but their bytes are not recovered in this publication.

## Evidence availability and fingerprints

The [fresh raw Lean report](lean/final-head/report.md) was recovered from complete captured output, authenticated against its previously recorded hash, and uploaded without modification: 3,780 UTF-8 bytes, SHA-256 `7a9eea3f7debac147ab825d7ec1f92b26ffe5464d24a42273fbbdc33cdb2ffa5`. A [separate navigation copy](lean/final-head/linked-report.md) repairs model links while preserving the raw original.

The corrected-head comparison's [raw case archive](ir/full-corpus/raw-cases.tar.gz) was verified byte-identical to the one already published for the previous run. The uncompressed contents of the [case-result JSON](ir/full-corpus/case-results.json.gz) also matched exactly; the linked gzip container is the earlier published copy. Those recorded outputs remain available. The [two comparison helpers used for the fresh run](ir/final-head/README.md) were authenticated from complete captured text and match their earlier published versions. The current run's provenance is separate: its before/after JSON both had SHA-256 `5cfde68dd0206ee061c8db355c00f67ba83fa2806bbe177c963fb3b92f522329`, 2,843,321 bytes each. Those new manifest bytes were checked before the outage but are not recovered here.

Other recorded recovery fingerprints:

- Corrected raw case archive: SHA-256 `3e0d48225fb929587f1a425f5d7691ed264a346202d0960e8e3c403f137394b3`; all 18,317 members were verified.
- Uncompressed case-result JSON: SHA-256 `ceb012126ce637d88c51a4ca5587f58cd8890870f0ec75e926ed3012d5d4cee5`.
- Fresh cost report: 449,629 bytes, SHA-256 `ba0644254c78d7a94ec7770403d8b47fb44fe02d3fcba39474c98cad584e5239`.
- Fresh cost archive: 2,628,805 bytes, SHA-256 `f4e12b30143cecb7f2f1cac50eeafd254fcfb1acc2535251d9725801f0166b8b`; 219 original members totaling 71,310,814 uncompressed bytes were verified.
- First interrupted full-run archive: 289,696 bytes, SHA-256 `a82324525f6dd3c7012fef36de5848f2a542ac7faa3f44d3155400566246407f`; 45 members were verified locally.

Fingerprints do not substitute for unavailable original files. Local raw provenance, unit logs, the cost archive and the interrupted-run archive should be recovered from the existing workspace if access returns. They have not been reconstructed or silently relabeled as published evidence.

## Remaining completion step

Run the full profile on the corrected head, verify its complete report and source identity, then mark PR #1499 ready for review. The existing [CI workflow](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml) supports manual execution: select `prototype/compiler-stage-boundaries` in **Run workflow** and confirm its head remains `5ccd1841`. Manual runs select the full profile on Linux x86-64 and ARM64. The available GitHub tools in this session can inspect or rerun existing jobs but cannot dispatch a new manual run.

If the original environment returns, inspect the existing supervisor metadata and process state before restarting work. A portable local invocation after installing the repository's pinned prerequisites is:

```sh
PYSTACHY_JOBS=2 VERIFY_PROFILE=full make PY=python3.13 verify
```

The PR remains draft and unmerged. Independent agent reviews completed; the automated Codex review was unavailable because the account's review quota was exhausted, which is not a completed review or a code finding.
