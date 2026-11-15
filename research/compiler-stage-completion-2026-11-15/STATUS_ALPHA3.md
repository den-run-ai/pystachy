# Compiler-stage integration with alpha.3

**Published implementation: `d266e919eb0c11dbbb41918b8d212bce7872910a`; PR #1499 remains draft and unmerged.** This revision integrates current main `6bf3f73af7edb02c5b2bdb6b2ac23fc3f5fffe93`. Fresh PR CI, Lint, CodeQL and submission checks have passed. Local full-profile verification, corpus comparison, the full local Lean qualification and cost measurements have not been repeated on this combined revision because the execution environment is unavailable.

Final CI API snapshot: **10:18:14–10:18:15 UTC on November 15, 2026**. [PR #1499](https://github.com/den-run-ai/pystachy/pull/1499) · [implementation commit](https://github.com/den-run-ai/pystachy/commit/d266e919eb0c11dbbb41918b8d212bce7872910a) · [stage contract](https://github.com/den-run-ai/pystachy/blob/d266e919eb0c11dbbb41918b8d212bce7872910a/docs/typed-ir.md).

## Published source identity

| Object | Identity |
| --- | --- |
| PR head | `d266e919eb0c11dbbb41918b8d212bce7872910a` |
| PR tree | `c242877c659b89a9131d5a17b2c4b170de095f76` |
| Integrated main | `6bf3f73af7edb02c5b2bdb6b2ac23fc3f5fffe93` |
| Integrated main tree | `107460d5f89bdcf37f2741b233eac0568d82604a` |
| Previous qualified PR head | `5ccd1841e2090a6a8e4076ed22f0cb4c015a94e8` |
| GitHub test merge | `106dfa1cfa5d8ebdb457ebb1d3011e10fd7f972f` |

The implementation is a merge commit whose parents are the previous PR head and alpha.3 main. GitHub's test merge has the same tree as the published head. The source branch is `prototype/compiler-stage-boundaries`.

The merge tree starts from the complete alpha.3 tree. A recursive comparison of changed subtrees verified that exactly the intended 27 PR paths differ: eighteen modified files and nine additions, all with mode `100644`. Every other main tree entry is preserved. [The recorded tree comparison](integration/alpha3-tree-verification.json) identifies all changed blobs. Candidate contents were read back from GitHub before publication. These are source-preservation checks, not execution tests.

## Completed stage separation

The compiler retains six explicit stages: `prepare`, `discover`, `analyze`, `optimize`, `finalize` and `lower`. The finalized boundary exposes complete typed function bodies and representation metadata before consuming LLVM lowering.

The follow-up to the original PR:

- Keeps copied, validated C ABI plans through discovery and finalization. Serialization reads no AST, selects no new types, and registers no new dependencies.
- Finishes runtime-module and extension-export admission before exposing finalized IR.
- Rejects empty or unknown stage names, inconsistent predecessors, repeated stages, cross-attempt prepared inputs and resumption of partially failed work.
- Runs requested final shared-operand invariants before publishing the finalized boundary.
- Adds `tools/inspect_compiler.py --stop-after finalize`, using the real driver's retry path and producing no LLVM artifact. Full lowering remains the default.
- Binds finalized snapshot bytes to inspection reports by SHA-256 and reports partial, completed, skipped and unavailable evidence explicitly.
- Makes the Lean reporter request finalized IR and adds a bounded Lean pipeline model for stage order, terminal lowering, retries and snapshot-attempt association.

Typing, representation selection and specialization remain coupled during discovery. The retained IR contains native ABI choices. This does not provide stored typed interfaces, reusable compiler sessions, whole-compiler correctness or a semantic compatibility checker; `pystachy check` remains parse-only.

The first full local run also exposed a pre-existing JIT launcher defect: `ldd` on a symlinked LLVM executable could miss its origin-relative shared library, and the failure persisted in the negative cache. The correction resolves the executable path for discovery and changes the cache recipe to `lljit-v2`. Actual-ELF regression controls failed on the original code and passed on the corrected `5ccd1841` revision. Alpha.3 leaves the affected `jit_launcher` function byte-identical to that original baseline, so the correction remains applicable in this integration. [Detailed investigation and controls](STATUS_5ccd1841.md#a-real-issue-found-by-full-verification).

## Why the alpha.3 integration was needed

Main advanced at **09:31:15 UTC on November 15, 2026**, when [PR #1494](https://github.com/den-run-ai/pystachy/pull/1494) merged alpha.3. That merge incorporated 130 commits beyond the earlier base `8049014`. The PR API initially retained its old base SHA while reporting a conflict; reading the actual main ref established the cause.

Thirteen PR files overlapped main's changes. The integration preserves alpha.3's constructor hierarchy machinery, early declaration registration, deferred and activated hierarchy state, lazy `init_only` constructors, complex-number exclusions, comparison/container forwards, representation metadata and proof models.

The driver keeps alpha.3's `NeedHierarchy` retry policy alongside the stage and JIT changes. The entire analysis/optimization/finalization/lowering tail extracted from the old `gen_program` is unchanged between the earlier base and alpha.3, so no new tail semantics needed migration into `pipeline.py`.

A substantive inspection overlap required an explicit decision: alpha.3 introduces `dynamic_layouts` metadata. It is now captured at finalization with the other representation tables. Reading it later in `save()` would expose backend mutation rather than the retained boundary.

The Lean integration retains main's Layout, Alias and Companion models and its report-completion checks for per-function adapter errors. It also retains our Pipeline model, executable, eleven audited guarantees and finalized-only reporter invocation. Static inspection found 56 unique declarations in the combined main audit and eighteen unique default Lake targets. CI subsequently built those targets and ran the main and guard axiom audits, as recorded below.

## Integration regression coverage

A new inspection regression uses the maintained `constructor_fixed_hierarchy_base.py` fixture unchanged. Its constructor has an unannotated parameter and an annotated field; declaring a subclass activates the hierarchy through `NeedHierarchy` during preparation.

The test wraps the real preparation method, catches and rethrows actual `NeedHierarchy`, and retains every generator object. It checks fresh generator identities, the interrupted `new`/active-`prepare` state, retry/report association, the successful terminal attempt, byte-identical finalized snapshots between full and finalized-only inspection, forbidden backend entry points, and absence of LLVM and compiler stdout output.

The existing backend-mutation regression now boxes a class through dynamic `Any` and requires a nonempty `dynamic_layouts` table. Clearing backend class records therefore tests a real retained table rather than an empty case.

The inspection module contains 34 tests after this addition, retaining the previous 33. CI executed the new and modified regressions successfully as part of the 60 passing stage/inspection tests. They were not run locally after the execution environment became unavailable.

## Current integrated-head verification

| Check | Observed result on `d266e919` |
| --- | --- |
| [PR CI](https://github.com/den-run-ai/pystachy/actions/runs/43701897758) | **43/43 checks passed across fourteen groups.** |
| Compiler/runtime bootstrap | Fixed-point verification passed; the bootstrap group reports 1/1 stages passed. |
| Stage and inspection suites | **60 tests passed, no skips:** inspector 34, pipeline 12, admission 8 and ABI stages 6. |
| [Lint](https://github.com/den-run-ai/pystachy/actions/runs/43701897755) | Passed all 47 job steps, including hosted checks and compiler-state controls. |
| Lean unit coverage in Lint | **463 tests passed across nineteen invocations, with no skips.** |
| Lean builds and axiom audits | Fresh builds completed 50 Lake jobs; **60 declarations** passed axiom audits, including all eleven pipeline guarantees. |
| Bounded guard corpus in [Contracts](https://github.com/den-run-ai/pystachy/actions/runs/43701897758/job/132776356046) | Nine programs accepted with complete inventory; **476/476 counted obligations or uses proved** across its models. |
| Contracts and FFI | 22/22 group stages passed. The explicit gate requiring C, embedding and extension coverage succeeded. |
| Cache/GC | 3/3 group stages passed, including runtime-cache. |
| [CodeQL](https://github.com/den-run-ai/pystachy/actions/runs/43701893278) and submission format | Passed. |
| New full-profile verification | Not completed on this integrated revision. |
| New corpus/LLVM/diagnostic comparison against alpha.3 | Not run. |
| Original ten-program Lean report and full local `test_lean*.py` suite | Not rerun locally. |
| New cost measurements | Not run. |

The [captured API inventory](ci/alpha3/api-inventory.json) records seven workflows (six successful, one intentionally skipped), 24 jobs (22 successful, two skipped), 25 check runs (23 successful, two skipped), and one successful separate commit status. Every API collection was checked for completeness. There were no failed or pending current-head checks.

The intentional skipped jobs are the disabled legacy DCO compatibility check and the non-PR bootstrap/archive qualification job. A later description edit may add another submission-format run. These job-level skips are separate from unit-test skips: a runtime-control invocation in [variant worker 1](ci/alpha3/variant-worker-1.log) reports 94 tests with eight skipped; its nonverbose output does not identify those tests, and this report does not infer their reasons. Zero-skip claims above apply specifically to the named stage/inspection and Lean suites.

The ordinary job logs do not expose the inner FFI/runtime-cache case totals or compiler/runtime fixed-point IR line counts. Their success gates passed, but the earlier 196 FFI, 192 cache and bootstrap line-count figures are not silently reused for this new head.

### Lean coverage and trust scope

Lint ran 32 of the 33 current `test_lean*.py` files under `LEAN_BOUNDARY_REQUIRED=1`. Its target omits `test_lean_corpus.py`. The 463 tests include 21 pipeline tests and 44 report tests. Contracts repeated 119 required guard-related tests; they are a subset of the 463 and are not added as distinct tests.

Both Lint and Contracts built the Lean project and produced the same sixty axiom-audit pass entries: 56 from `Audit.lean` plus four from `GuardAudit.lean`. These are not 120 distinct guarantees.

The separate guard corpus reported:

| Recorded category | Inventoried | Proved |
| --- | ---: | ---: |
| Union reads | 61 | 61 |
| Removed null checks | 27 | 27 |
| Payload obligations | 101 | 101 |
| Field obligations | 151 | 151 |
| GC obligations | 136 | 136 |
| **Counted uses across these models** | **476** | **476** |

All nine programs were accepted; the inventory was complete, with zero erroneous, rejected, unsupported, uninventoried or vacuous programs. The count combines bounded uses across models. It is not a count of independent source-level correctness properties, and it does not replace the historical ten-program report with 535 results.

The [Lean CI audit](lean/alpha3-ci/README.md) and its [derived JSON record](lean/alpha3-ci/audit.json) identify the selections, counts, source identities, audit names and model limitations.

### Durable CI records

The following are complete decoded logs retrieved from GitHub and uploaded unchanged:

- [Bootstrap](ci/alpha3/bootstrap.log).
- [Lint](lean/alpha3-ci/lint.log).
- [Contracts and the bounded Lean corpus](lean/alpha3-ci/contracts.log).
- [Cache/GC](ci/alpha3/cache-gc.log).
- [Variant worker 1, including the recorded unit-test skips](ci/alpha3/variant-worker-1.log).
- [Final Verification aggregation](ci/alpha3/verification.log).

The [artifact metadata](ci/alpha3/artifact-metadata.json) records eighteen artifacts. Their digests are GitHub-reported metadata; the ZIP bytes were not independently downloaded, extracted or rehashed during this audit because workspace execution is unavailable. The exact uploaded log contents were read back and compared; the derived audits are explicitly separate from those original decoded logs.

## Earlier completed qualification and its limits

The [previous corrected-head report](STATUS_5ccd1841.md) records these completed observations on `5ccd1841`, before alpha.3 integration:

- Compiler and runtime bootstrap fixed points passed.
- All 4,579 corpus comparisons matched: 2,653 accepted and 1,926 matching rejections.
- All 59 stage/inspection methods passed; the local import-path invocation error and its focused replay are retained in the report.
- All 409 required Lean tests passed with zero skips.
- The original ten-program Lean report proved 535/535 bounded obligations or uses.
- PR-profile CI, Lint, CodeQL, 196 FFI checks and 192 runtime-cache checks passed.
- Timings were inconclusive. The binary grew 4,864 bytes (+0.0723%) versus original PR head `800752d8`; self-compilation median peak RSS grew about 11.3 MiB (+1.276%) in that run.

Those results remain evidence for their pinned revision. They are not new alpha.3 measurements, and the old checker binaries must not be reused as qualification for changed Lean sources.

The fresh full local run for `5ccd1841` began at 09:19:11 UTC. At its last confirmed observation, 09:24:31 UTC, bootstrap was still active with no completed stage. Workspace access then failed. Its later process and exit status are unknown; it is not counted as passing or as a confirmed test failure.

The first earlier full attempt on `eabfe7b3` completed eight passing stages and then failed 24 runtime-cache checks, leading to the JIT correction. Its interruption and available fingerprints remain documented. The original local cost archive, fresh provenance manifests and full-run archives could not be recovered after environment loss. Published raw Lean and CI records, authenticated fingerprints, and byte-identical case-result artifacts are identified in the earlier report.

## Proof scope and remaining work

The pipeline model checks bounded state transitions and recorded report association. Exporter fidelity, normalization, source provenance, native checker execution, stage semantics, object ownership, GC and LLVM correctness remain trusted or outside that model. Main's additional Layout, Alias and Companion models have their own documented assumptions; combining them does not prove the entire compiler.

Fresh CI and independent integration reviews are complete. Full-profile and same-input corpus requalification of the combined source against current main remain outstanding. The existing [CI workflow](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml) supports a manual full-profile run on Linux x86-64 and ARM64: choose `prototype/compiler-stage-boundaries` and verify its head. The connected GitHub tools can inspect and rerun existing jobs but cannot dispatch that manual workflow.

When execution access returns, inspect the existing supervisor metadata before launching a duplicate local run. On a clean checkout with pinned prerequisites, rebuild the combined compiler/runtime, run the maintained corpus comparison against `6bf3f73`, run the full required Lean suite/report, and repeat cost measurements if making a performance claim. Preserve exact source/input identities and failed attempts.

The PR remains draft and unmerged. Independent agent integration reviews completed without a remaining requested correction; earlier reviews and local measurements remain tied to their own revisions. The quota-exhausted automated Codex review was not a completed review.
