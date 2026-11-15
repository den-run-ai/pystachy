# Compiler-stage boundary evidence — 2026-11-15

This experiment separates the existing compiler into explicit, attempt-owned
stages and makes finalized typed IR an inspectable boundary before consuming
LLVM lowering. The checks below support preservation of existing compilation
and execution behavior on the measured inputs. They do not establish broader
Python compatibility or a new compiler correctness theorem.

## Code and scope

The reference is main/alpha.2 commit
`80490143498d149d407343ba1cb7aedb1db2d2c5`. The published implementation is
`5557064d54b78efa4cdbcfe9e055394ab5158a50`; the final reviewed code head is
`800752d8a582bff77d4c375039af786b82a96f73`, tree
`f85536e8286db9a585fdb4d6606e8b8af8f67eb8`.

The stages are `prepare`, `discover`, `analyze`, `optimize`, `finalize` and
`lower`. Their checked order is owned by one `Gen` attempt. A failure leaves the
active stage incomplete; a retry creates a fresh attempt. Prepared declarations
retain their owner, so they cannot be passed to another attempt. Finalization
completes exception lowering and tuple-return ABI selection while the typed
function bodies remain available. Lowering then consumes those bodies. The
inspector captures all selected functions and representation tables at finalization
and reports the actual stage history, active stage and partial/unavailable evidence on failure.
See the [stage contract](../../docs/compiler-inspection.md#compiler-stage-boundaries)
and [implementation](../../src/pystachy_compiler/pipeline.py).

Preparation and discovery still combine name resolution, inference, semantic
typing, representation choices, folding and specialization. The prepared
program borrows mutable syntax; it is not a reusable serialized semantic IR.
The prototype does not make `Gen` reusable or concurrent, introduce stored typed
interfaces, or turn the parse-only `pystachy check` command into a compatibility
checker. It establishes a boundary on which those future investigations can
build without changing this experiment's language contract.

Some logs predate final commit publication. Local implementation commit
`6f8b2998a93e1e8770f98f78e51d26505ccd06be` has the same tree as `5557064d`.
Local ownership-fix commit `c153493a7c5a11196fd42a8591bcf7e062f5ac34` has the same
tree as `800752d8`. The latter follow-up changes only the ownership-test inventory
and comment for `Gen.pipeline` in `tools/test_frame_fields.py`. Compiler,
inspector, library, runtime and corpus sources did not change in that follow-up.
Historical metadata is preserved with its original commit names.

## Validation inventory

Development tools were CPython 3.13.16, LLVM 18.1.3, Lean 4.35.0 and the pinned
development dependencies. Native checks used the ordinary native compiler and
the CPython-hosted compiler. Heavy local qualification and cost measurement ran
separately; corpus comparison and bounded Lean reporting used two workers.

| Check | Recorded result | Evidence |
|---|---|---|
| Native bootstrap | Three compiler generations emit identical 933,173-line IR; three runtime generations emit identical 21,214-line IR | [bootstrap.log](bootstrap.log) |
| Stage and inspection tests | 40 local tests passed: 10 stage tests and 30 inspection tests; both files are registered in `check-fast` | `tools/test_compiler_pipeline.py`, `tools/test_inspect_compiler.py`; current-head CI evidence below |
| Static checks | Ruff, mypy on 59 source files, and runtime signature/effect inventory passed | [initial-static-checks.log](initial-static-checks.log) |
| State ownership | Initial audit exposed missing classifications; corrected global-ownership suite passed 65 tests | [initial failures](state-initial.log), [corrected run](state-ownership-final.log) |
| Full IR comparison, identical home | 4,579 of 4,579 cases equal, including raw diagnostics and exit statuses | [summary](ir/ordinary-summary.json), [final log](ir/shared-home-ordinary.log) |
| Compiled execution | 56 JIT/AOT executions passed, plus two independent CPython FFI reference executions | [corpus results](native/results.json), [FFI results](native/ffi-results.json) |
| Existing Lean adapter/checker tests | 387 tests passed, zero failures/errors/skips, with `LEAN_BOUNDARY_REQUIRED=1` | [unit-tests.log](lean/unit-tests.log) |
| Final-head bounded Lean report | 10 of 10 selected programs complete; 535 obligations/uses proved; compiler, checker and corpus inputs all clean | [report](lean/report.md), [records](lean/records.jsonl), [comparison](lean/final-comparison.json) |

The initial ownership failures are retained as development evidence, not reported
as passing gates. A later CI failure identified the separate `Gen.pipeline`
frame-inventory omission; the final-head follow-up records that attempt-owned
state explicitly. The 40-test local stdout was not retained; the [final CI excerpts](ci/stage-inspection.log)
and [complete Lint log](ci/lint.log.gz) are the retained source for those tests.
The [log metadata](ci/lint-log-metadata.json) records its current head, job URL
and compressed/original hashes. The [initial CI failure](ci/initial-ownership-failure.json)
and [18-test local follow-up](frame-fields-final.log) preserve the frame audit correction. The Lean unit log contains resource-cleanup
warnings, so its passing result is not a claim of warning-free execution.

The 56 executions consist of ten maintained cases in JIT and AOT through each
compiler (40), four of those cases under program GC stress (8), and libc/libm
FFI cases through each compiler and execution mode (8). The maintained cases
cover distinct generic layouts, promoting-integer storage and variable-tuple
materialization, recursion depth, iterator/generator exceptions, dynamic
containers/identity and a dictionary alias barrier. FFI executions also used GC
stress. [The exact case plan](native/plan.json) and result files retain the
selection; this is a focused qualification, not an execution of the full corpus.

## Full IR comparison and the library-home control

The first ordinary `make irsame REF=80490143` compared compilers using their own
library homes and reported **284 differences out of 4,579 inputs**. The official
harness prints only the first three differences and removes its temporary
directory on exit. That cleanup had already happened when preservation was
attempted. Consequently only the three displayed excerpts are inspectable:
`byte_bpe.py`, `example_linediff.py` and `example_mailmerge.py`. Each displayed
change embeds the different `build/ref/lib/types.py` versus `lib/types.py` path
in an import-error string, with the corresponding string length change. The
[original log](irsame-original.log.gz) is retained. These excerpts do **not** identify
or individually classify all 284 original differing cases.

A second complete comparison controls that concrete location difference. Before
using a common `PYSTACHY_HOME`, an independent inventory verified identical
contents for all 105 actual files under `lib`, `runtime.c`, `runtime.py`, `ryu`
and `mpz` in the reference and current homes. Only `__pycache__` and `.pyc` files
were excluded. The [identity inventory](library-runtime-identity.json) records
file kind, size and SHA-256, as well as symlink targets where applicable; neither
tree contained a symlink in those inputs. The source inventories and both
compiler hashes were checked again after comparison and were unchanged.

The exact compiler identities are in [compiler-identities.json](ir/compiler-identities.json):

| Compiler | SHA-256 of native executable |
|---|---|
| Reference `80490143` | `ab6eab3cd16a215ae483a4bd8ca6a5219cecbcff62f89e58e6b01d9f08a9233a` |
| Staged compiler | `33c0fb45f19776c5f1f9c96252f4c82af89e267ffbfc82f376eff165823dd757` |

All inherited `PYSTACHY_*` settings were removed. The complete ordinary replay
set only `PYSTACHY_HOME` to the current checkout and `PYSTACHY_JOBS=2`.
`PYSTACHY_IRCHECK` remained **unset**, and compiler optimization settings remained
at their defaults, matching the first comparison. The ordinary harness still
prepares each case's `.path` fixture and uses runtime mode for the runtime cases.
The [recorded command](ir/ordinary-replay-command.json) preserves the actual paths.

The [scratch harness](ir/irsame-retain.sh) is an exact retained copy of the run's
script. Its [documented changes](ir/harness-changes.json) fix the working and
output directories, retain reports and changed IR, record per-case exit statuses,
and raise the display limit. Its comparison logic is unchanged. The official
harness can normalize diagnostic source-location prefixes, but the additional
per-case audit confirmed that **every pair of raw diagnostic files was already
byte-identical**; this result did not depend on that normalization. LLVM IR was
compared byte for byte with no normalization.

The complete ordinary replay exited 0: 2,653 cases exited 0 in both compilers;
1,926 exited 1 in both. There were no missing reports, new rejections, raw
diagnostic differences or IR differences. This establishes equality for the
entire selected corpus under identical library/runtime location and content.
It supplies stronger controlled evidence than extrapolating from the three
original excerpts, while leaving the original 284-case classification limitation
visible. It does not assert that every possible source program is unchanged.

An earlier replay accidentally enabled `PYSTACHY_IRCHECK=1`. It was interrupted
at 1,449 completed cases to restore the original configuration; its zero
differences are **partial evidence only**, not the complete replay. Both its
[command](ir/replay-command.json) and [interruption record](ir/verifier-replay-interrupted.json)
are retained separately.

The full ordered [case results](ir/ordinary-case-results.json.gz) preserve all
4,579 input paths, statuses, diagnostic hashes and comparison outcomes. This is
reproducible gzip with `mtime=0` and no original-filename header. The
[packaging record](ir/packaging.json) gives both compressed and original byte
counts and hashes; decompression was verified byte-exact. Equal LLVM files were
discarded by the harness after comparison, so they are regenerated rather than
stored in this evidence package. The scratch script retains historical absolute
paths; use the repository's `tools/irsame.sh` for a new checkout, with the same
settings and independently verified library/runtime identity.

## Lean scope and final-head provenance

The existing proof sources and checker adapters are unchanged from `80490143`.
The [baseline Lean build](lean/build-baseline.log) completed all 29 targets,
including the two axiom audits.
The three resulting executable hashes were verified on reuse; the final bounded
run's [command and checker identities](lean/command.json) record them. No proof
executable was silently rebuilt from modified source.

The final report was generated from a separate detached checkout of `800752d8`
with `--jobs 2 --start-method spawn`. It reports `clean: true` for compiler,
checker and corpus inputs. All ten requested programs completed. Their check
result objects exactly match the baseline and the development run. Counts are
12 dynamic-payload reads, 38 unchecked accesses, 17 null-check removals, 31
closed-union reads, 46 union-payload obligations, 168 field-initialization
obligations, 75 collector-scanning obligations, 32 inline-integer uses and 116
integer-storage obligations. No promoting-integer fit claims occur in this
selected inventory. These categories total 535; they are not 535 independent
whole-program theorems.

Earlier development records had uncommitted inputs. Two final-head attempts
also had dirty corpus provenance: the main checkout contained ignored
`build/ref/lib` Python files, and the evidence checkout contained an ignored
Python cost runner. The reporter includes such files in its namespace-import
lookup audit. The [preliminary provenance](lean/preliminary-provenance.json) is
retained honestly; no provenance check was disabled. The separate final checkout
resolved those ambient inputs without moving another task's files.

The earlier [snapshot comparison](lean/snapshot-comparison.json) found all ten
finalized typed snapshots identical to baseline after replacing only the two
known checkout prefixes. That is explicitly a development-stage comparison.
The [LLVM comparison](lean/llvm-comparison.json) was equal for nine; `field_init`
had only the two embedded path strings and length changes shown in the retained
[diff](lean/field-init-llvm.diff). The later full native IR replay above uses
exact byte equality and does not apply this prefix substitution.

The bounded models establish the safety properties documented in
[tools/lean_boundary](../../tools/lean_boundary/README.md), not general aliasing,
collector correctness, Python object semantics or compiler equivalence. The
exporter, normalization, lowering and native execution remain trust boundaries.
The selected ten-case report is complete for its explicit inventory, not the
repository-wide canonical Lean report. Its generated model links are relative
to `tools/lean_boundary`, where those documents live. These model documents are
pinned to the tested final head so the relocated report remains interpretable:

- [Dynamic payload guards](https://github.com/den-run-ai/pystachy/blob/800752d8a582bff77d4c375039af786b82a96f73/tools/lean_boundary/README.md)
- [Unchecked access](https://github.com/den-run-ai/pystachy/blob/800752d8a582bff77d4c375039af786b82a96f73/tools/lean_boundary/ACCESS.md)
- [Null, union and field guards](https://github.com/den-run-ai/pystachy/blob/800752d8a582bff77d4c375039af786b82a96f73/tools/lean_boundary/GUARDS.md)
- [Collector scanning](https://github.com/den-run-ai/pystachy/blob/800752d8a582bff77d4c375039af786b82a96f73/tools/lean_boundary/GC.md)
- [Promoting integers](https://github.com/den-run-ai/pystachy/blob/800752d8a582bff77d4c375039af786b82a96f73/tools/lean_boundary/INT.md)
- [Integer storage](https://github.com/den-run-ai/pystachy/blob/800752d8a582bff77d4c375039af786b82a96f73/tools/lean_boundary/STORAGE.md)

## Current-head CI and cost measurement

Final head `800752d8` passed [CI run 43686263857](https://github.com/den-run-ai/pystachy/actions/runs/43686263857)
and [Lint run 43686263943](https://github.com/den-run-ai/pystachy/actions/runs/43686263943).
The CI run contains 16 jobs: 15 successful, including the aggregate Verification
gate, and one expected conditional archive-qualification skip. Across all
current-head check runs, 21 of 23 succeeded; the two expected skips are archive
qualification and the legacy DCO compatibility job. Submission format also
passed. All returned jobs/checks pages were accounted for; none remained queued,
running, failed or cancelled.

The [status and step inventory](ci/status.json) records the exact head/base,
workflow IDs, job URLs and conclusions. The [aggregate Verification log](ci/verification.log.gz)
retains its evidence checks; the [Lint log](ci/lint.log.gz) and [40-test excerpts](ci/stage-inspection.log)
show that the stage and inspection tests actually ran. The [raw-log packaging metadata](ci/raw-log-packaging.json) records compressed
and original hashes; excerpt lines have trailing whitespace removed. Credential
placeholders in the public logs remain masked. The [initial failed ownership audit](ci/initial-ownership-failure.json)
is preserved separately from this passing final-head qualification.

This is the repository's required pull-request profile. Full local `make verify`
and the exhaustive main/manual matrix were not run. Independent implementation
and evidence reviews found no outstanding issue within this prototype's scope.

The independent [cost probe](cost/README.md) records five alternating pairs after
warmup, per-stage timings, peak RSS, collector summaries and executable size.
It measures native source-to-LLVM self-compilation and excludes LLVM code
generation, linking and resulting-program execution. The overlapping noisy
samples do not establish a speedup or precise overhead. Allocation request
counts were not measured. See [its raw report](cost/report.json) for exact
settings, source/binary identities and the timing limitations.
