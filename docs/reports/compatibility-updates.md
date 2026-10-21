# Rolling compatibility findings

This log tracks changes after the [2026-10-17 audit](compatibility-2026-10-17.md).
Keep the original measurements as a historical baseline. Append new measurements
with the exact main SHA, merged PRs, commands, inputs and observed outcomes.
Do not replace a result merely because a PR description predicts an improvement.

**Latest evaluated main:** `3c63613b9ad4748dfc030fc923f7704e26b21ba9`.
**Baseline audit PR:** [#635](https://github.com/den-run-ai/pystachy/pull/635).

**Source-provenance correction (2026-10-20):** historical evidence/replay scripts
that use `git status --porcelain --untracked-files=no` establish only tracked-file
cleanliness. Their `dirty: false` / `source_dirty: false` fields do **not** rule out
untracked library or test inputs. The old working trees were pruned, so this missing
observation cannot be reconstructed or retroactively certified. Dated reports and
JSON are preserved, with this qualification applying wherever that command occurs.
Before replaying those scripts, use a fresh evaluated checkout and run the new
[preflight](compatibility-2026-10-20-release-replay.py) with
`python3.13 -B REPLAY.py --preflight CHECKOUT`, before producing build outputs.
It rejects tracked modifications, all untracked files and ignored files, with no
blanket build-directory exemption. Keep the driver/output outside that checkout.
Five regression controls cover clean, modified tracked, untracked `lib/`, untracked
`tests/` and ignored inputs. Subsequent build products are not evidence that the
pre-build snapshot was dirty; retain pre/post snapshots and exact selected inputs.
This corrects [review finding](https://github.com/den-run-ai/pystachy/pull/743#discussion_r4319518176),
not a claim that historical untracked inputs were present or absent.

**Historical replay prerequisite (corrected 2026-10-19):** before running any
embedded GC-budget, BLAS-fold or Unicode driver from its evaluated checkout, run
`mkdir -p build/audit-gc build/audit-blas build/audit-unicode`. Their historical
scripts assume those directories already exist; bootstrap alone does not create
them. Continue to relocate the explicit toolchain/compiler/fixture paths as each
report describes. The dated JSON is preserved unchanged. The #690 checkpoint
below records four clean-directory controls for this correction.

## Checkpoints

| Check | Main / changes since baseline | Findings |
|---|---|---|
| 2026-10-17 initial audit | `d3fbfc6f`; includes #598, #599 and #603 | 141/476 import programs compile; 46 upstream files excluded by overlay. 501 selected stdlib checks and 62 port checks pass; all 18 adapted benchmark programs match. Detailed evidence is linked from the baseline. |
| 2026-10-17 follow-up | Same `d3fbfc6f`; no additional merges | Existing results still describe current main. No unchanged full suites were rerun. #600–#602, #604–#609, #622–#624, #629–#634, #583 and #170 remain open at this checkpoint; proposed support is not counted as shipped. |
| 2026-10-19 builtin-module prototypes | `2359de69`; #644, #645, #646 and #648 after `a355c83f`, plus CI-only #677 | **144/475** native imports, up from 142, with none lost; **146/475** stub-assisted. All 27 package probes keep their first errors, and the pyperformance census stays at 6/52. Adds three compiled upstream test files. [Report](compatibility-2026-10-19-prototypes.md). |
| 2026-10-19 merge catch-up | `5db1e4b5`; #678 integration, #670 native JSON, regex/compiler/array changes through #699, and #723 recorded benchmarks | **144/470** native, **146/470** stub-assisted; five JSON files move into the overlay, no successful imports lost. Native JSON passes 14,444 cases in each JIT/AOT mode with GC stress. Focused checks, affected ports, FFI and BLAS parity pass. [Evidence](compatibility-2026-10-19-catchup.json). |
| 2026-10-19 JSON/effect follow-up | `898d0b95`; #722 | Imports and first errors unchanged; JSON differentials, 64 focused checks, 52 GC-stressed checks and 8 adapted port checks pass. Corrected recursive equality depth boundary and alias diagnostics. Independent paired encoder medians improve **3.47–4.82x** on two bounded inputs, not whole-library coverage. [Evidence](compatibility-2026-10-19-json-followup.json). |
| 2026-10-19 coverage tooling | `5dcb4859`; #733 README badges and #731 hosted coverage | 9 selected checks pass with all 10 compiler processes captured; a missing-JIT-data control correctly fails. No compiler/runtime/lib/port/test source changes and no new library-support claim. [Evidence](compatibility-2026-10-19-coverage-tooling.json). |
| 2026-10-19 module bindings | `681bdd17`; #690 | Silent wrong function/exception bindings corrected; local module calls and same-named type parameters now work. 404 focused, 28 API and 8 port checks pass; imports remain 144/470 native, 146/470 stub-assisted. Only four corrected fixtures differ in the 3,109-program IR oracle. [Evidence](compatibility-2026-10-19-module-bindings.json). |
| 2026-10-19 Unicode empty replacement | `946ce035`; #728 | Empty-pattern string replacement no longer splits UTF-8 bytes: all 1,328 supplementary cases match CPython (532 differed before). 215 focused, 58 API and 16 port checks pass; 4,560 Unicode audit controls pass. Imports and first errors stay unchanged. [Evidence](compatibility-2026-10-19-unicode-replace.json). |
| 2026-10-19 conditional imports / power | `53c17bad`; #692, #735 and incorporated #665 | Conditional-import wrong results fixed; 450,000 power values match CPython (185 old AOT differences). Five import first errors advance, totals remain 144/470 native and 146/470 stub-assisted. 210 focused, 36 API and 12 port checks pass. [Evidence](compatibility-2026-10-19-imports-power.json). |
| 2026-10-19: field alias metadata, tuple returns and shared JIT runtime (#724/#727/#730) | `4a1a29aa` | [Evidence](compatibility-2026-10-19-field-tuples.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19: empty-string exception representations and binding diagnostics (#729/#726; audit #669) | `e33c560e` | [Evidence](compatibility-2026-10-19-exception-diagnostics.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19: unsupported generic annotations (#697) | `ca7688dd` | [Evidence](compatibility-2026-10-19-generic-diagnostics.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19: exception class values (#721) | `3609a5f0` | [Evidence](compatibility-2026-10-19-exception-classes.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19: shared CI bootstrap harness (#741) | `552d7301` | [Commands and results](#2026-10-19-shared-ci-bootstrap-harness-741). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19: native opcode metadata and stack effects (#686) | `b7e869f8` | [Evidence](compatibility-2026-10-19-opcode.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19: tuple-return regression coverage (#747) | `837843bc` | [Evidence](compatibility-2026-10-19-tuple-return-coverage.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19: compile-time sys installation prefixes (#719) | `633cdf1a` | [Evidence](compatibility-2026-10-19-sys-prefix.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19: numeric-union local slots (#742) | `a1f3b6a7` | [Evidence](compatibility-2026-10-19-union-slots.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19 — collector-backed weakref callbacks (#694) | `c71d4ca5` | [Evidence](compatibility-2026-10-19-weakref-callbacks.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19 — #725 warnings and #740 regex specialization | `c8439d40` | [Evidence 1](compatibility-2026-10-19-warnings.json); [Evidence 2](compatibility-2026-10-19-regex-specialization.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19 — #738 numeric-union reductions and #736 None inference | `f9eaba8f` | [Evidence](compatibility-2026-10-19-union-none.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19 — #689 native `_io` stand-in | `b85f0f3c` | [Evidence](compatibility-2026-10-19-io-standin.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-19 — #749 virtual-environment recording portability | `be822311` | [Evidence](compatibility-2026-10-19-prefix-venv.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #750 percent conversion order and malformed-text counts | `9392fddf` | [Evidence](compatibility-2026-10-20-format-counts.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #753 regex profile exit/traceback fidelity | `45e88b6f` | [Evidence](compatibility-2026-10-20-record-exits.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #720 localized gettext port | `d87a215d` | [Evidence](compatibility-2026-10-20-gettext.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #696 public weakref module | `88013afb` | [Evidence](compatibility-2026-10-20-weakref-module.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #737 inferred scalar unions and builtin splitting | `611af05e` | [Evidence](compatibility-2026-10-20-inferred-unions.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #755: empty-container results through forwarding recursion | `17c7e1ff` | [Evidence](compatibility-2026-10-20-forwarding-recursion.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #718: object sentinels and three additional imports | `11f4681a` | [Evidence](compatibility-2026-10-20-object-sentinels.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #760: UTF-8 file-write counts and dropped-result lowering | `727b88ce` | [Evidence](compatibility-2026-10-20-text-write-counts.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #763: tuple exits, instrumented file flushing and coverage tooling | `8990e417` | [Evidence](compatibility-2026-10-20-coverage-runtime.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #732: syntax rejection and continuation correctness | `5a915947` | [Evidence](compatibility-2026-10-20-syntax-validation.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #764: starred type-parameter default acceptance corrected | `4f71b5a0` | [Evidence](compatibility-2026-10-20-starred-defaults.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #765: less compiler allocation, unchanged compatibility | `3ab11f03` | [Evidence](compatibility-2026-10-20-compiler-allocations.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 — #761: opt-in dynamic Any, not general library compatibility | `3c63613b` | [Evidence](compatibility-2026-10-20-dynamic-any.json). Completed checkpoint; detailed findings and limits below. |
| 2026-10-20 release validation (#762), **incomplete** | `afb59cd3`; fully evaluated marker remains `3c63613b` | Hosted checks and historical CI verified; local LLVM/native execution unavailable. [Evidence](compatibility-2026-10-20-release-partial.json). |
| 2026-10-20 test-area layout (#771), bounded tooling evaluation complete | `ad19255e`; #762 native work still incomplete, full marker remains `3c63613b` | 3,301 cases preserved; 180 tooling tests, 158 path-sensitive expected rejections and six CPython recordings/hosted IR programs pass. [Evidence](compatibility-2026-10-20-test-layout.json). |
| 2026-10-20 hierarchy comparison dispatch (#785), **partial** | `554f3d13`; docs-only #776/#788 also inspected | Hosted raw IR at 80 subclasses: exception 357,105 → 9,317 lines, ordinary 353,611 → 6,063. 135 tooling tests, 56 positive compilations and 30 rejections pass; native evaluation remains incomplete. [Evidence](compatibility-2026-10-20-hierarchy-partial.json). |
| 2026-10-20 comparison-operand widening (#792), **partial** | `452a0864`; follows #785 | The retained 80-subclass `other: object` probe moves from #785's 4,096-specialization rejection to 13,220 raw IR lines; 40 subclasses shrink 73,420 → 6,860. Declared-`Base` controls are byte-identical. 135 tooling tests, 57 before/after hosted compilations, 30 rejections and four CPython 3.12 recordings pass; native evaluation remains incomplete. [Evidence](compatibility-2026-10-20-comparison-widening-partial.json). |
| 2026-10-20 concurrency contract (#789), bounded tooling evaluation complete | `870bfa15`; no compiler/runtime/library implementation paths | Five registration checks and both 25-line source-twin clients pass; exact-tree native CI and FFI coverage jobs succeeded. This records contracts and probes, not a new native concurrency or import-compatibility claim. [Evidence](compatibility-2026-10-20-concurrency-contract.json). |
| 2026-10-20 dominated null-check elimination (#791), **partial** | `10097965`; compiler/typed-IR pass changes after #789 | On the same prior compiler source, hosted IR falls **710,837→621,696 lines** and null tests **36,182→13,978**; disabling the pass is byte-identical to the previous compiler. 137 hosted tests, three call contracts, the new reference and linear-scaling controls pass. Native/import evaluation remains incomplete. [Evidence](compatibility-2026-10-20-nullcheck-partial.json). |
| 2026-10-20 JIT landing pads and dynamic Any follow-up (#793/#790), **partial** | `3d48ce8c`; #793 intermediate `a79e6bbc`, both exact PR-head trees | 29/29 new CPython references, 31/31 new positive/deviation hosted compilations, one exact rejection, 19/19 targeted unit tests and six retained consumer compilations pass. The retained depth-199 compiler input finishes in 7.96s where `10097965` exceeds 20s. Exact-tree CI is green; local native/import evaluation remains incomplete. [Evidence](compatibility-2026-10-20-dynamic-any-followup-partial.json). |
| 2026-10-20 tomllib prerequisite blockers (#794), **partial** | `387059ba`; follows #793/#790 | 14/14 new positive CPython references, 17/17 positive/deviation hosted compilations, 6/6 changed rejections, 25/25 targeted unit tests and six retained consumer compilations pass. MappingProxyType and five compiler/runtime capabilities land; exact-tree CI is green. Local native/import evaluation remains incomplete. [Evidence](compatibility-2026-10-20-tomllib-blockers-partial.json). |
| 2026-10-20 `tomllib.loads()` port (#795), **partial** | `1cf6a676`; library/test/docs port on #794 | All five selected sources move from unsupported-module rejection to checked hosted IR; 5/5 CPython references match, including 62 upstream data documents (12 valid, 50 invalid). Exact-tree CI is green. Binary-file `load()`, local native/import evaluation and the full upstream suite remain incomplete. [Evidence](compatibility-2026-10-20-tomllib-port-partial.json). |
| 2026-10-20 dynamic `Any` in-place dispatch (#806), **partial** | `20d1aa29`; compiler/runtime change after #795 | 66/66 selected CPython references and hosted compilations pass. All 64 retained inputs have byte-identical hosted IR; only the two new regression programs change, fixing typed `Any` operands' in-place dunder dispatch and CPython operator messages. Exact-tree CI is green; local pinned native/import evaluation remains incomplete. [Evidence](compatibility-2026-10-20-dynamic-inplace-partial.json). |
| 2026-10-20 dynamic `Any` class-id dispatcher switch (#811), **partial** | `730886ea`; compiler/test change after #806 | 70/70 selected positive/deviation inputs emit hosted IR and 10/10 retained rejections remain exact. Of 69 common positive inputs, 57 change only inside `@dyn.*` dispatchers and 12 are byte-identical. Synthetic 2/16/128-class getters use one class-id switch with 2/16/128 cases; the 128-class dispatcher shrinks 1,809→1,429 IR lines. Exact-tree CI is green; local pinned native/import evaluation remains incomplete. [Evidence](compatibility-2026-10-20-dynamic-dispatch-switch-partial.json). |

## 2026-10-17 — #583: compiled float64 array example

Evaluated [main `c916ca6c`](https://github.com/den-run-ai/pystachy/commit/c916ca6c02061f427c72c92741fa446f7e2e626b),
which merges [#583](https://github.com/den-run-ai/pystachy/pull/583). It is the only
merge since the previous evaluated `d3fbfc6f`. The diff adds example, test and
license files only. Compiler/runtime/lib/port implementation sources are unchanged,
so the baseline native compiler was reused, with its SHA-256 independently checked:
`5a0261e7c6cc269720dbf84d77306578ac8969ee3253798e758772d86a3bb99c`.
Its build source remains `d3fbfc6f`; the evaluated example source is `c916ca6c`.
Unchanged import, stdlib, port and pyperformance suites were not rerun. Their
baseline counts are retained, not presented as fresh measurements.

[Normalized evidence](compatibility-2026-10-17-ndarray.json) includes changed-file
hashes, commands, environment, outputs and the benchmark table. Inputs: CPython
3.13.16, LLVM 18.1.3, NumPy 2.3.5, Linux x86-64. The adapted test's header preserves
its upstream NumPy 2.5.3 source provenance; this run checks those adaptations
against installed NumPy **2.3.5**, not an installed 2.5.3 suite.

| Evidence category | Fresh result |
|---|---|
| CPython reference programs | `example_ndarray`, `example_ndarray_edges`, `example_ndarray_upstream`: all three match checked-in recordings exactly, with no stderr. |
| Native JIT/AOT | All three programs pass in both modes: **6/6** checks. |
| Native per-allocation GC | Same **6/6** checks pass with `PYSTACHY_GC_STRESS_PROGRAM=1`, compiler stress interval 1000. Total normal + stressed native checks: **12/12**. |
| Compiled adapted upstream cases | The upstream program executes **432 assertions** per mode/run; these are included in the 12 program checks, not additional independent suite runs. |
| CPython-hosted NumPy reference | `check_upstream.py`: the same 432 adapted assertions hold against NumPy itself. `check_numpy.py`: **124 exact**, **6 tolerance**, **4 summation-policy**, **7 checker** checks pass. This checker is hosted, not compiled. |

The shipped example supports float64 views, broadcasting, `out=`/in-place
arithmetic, selected reductions, 2-D matrix products and fused lazy expressions.
This is a maintained typed implementation with substantial API restrictions,
not a minor source patch to upstream NumPy. NumPy itself, its extension loader,
and its general pytest suite have not become native-compatible through this PR.
Slices, reflected arithmetic, boolean/fancy indexing, other dtypes and
rank-dependent indexing results remain outside this example's supported API;
see [#582](https://github.com/den-run-ai/pystachy/issues/582),
[#501](https://github.com/den-run-ai/pystachy/issues/501) and
[#113](https://github.com/den-run-ai/pystachy/issues/113).

One advisory benchmark run uses 4,000,000 1-D items, fixed 1000×1000 strided
workloads, 256×256 matmul, best of five within each process and single-threaded
NumPy (`OPENBLAS_NUM_THREADS=1`). AOT/JIT checksums agree. Selected milliseconds:

| Workload | AOT | JIT | NumPy |
|---|---:|---:|---:|
| `a + b`, allocate | 24.369 | 31.301 | 2.691 |
| `a + b`, `out=` | 6.376 | 20.151 | 2.804 |
| squared-distance reduction, eager | 60.835 | 85.179 | 11.015 |
| squared-distance reduction, lazy compensated | 5.873 | 24.651 | — |
| 256×256 matmul | 11.191 | 75.921 | 0.646 |

Build wall time was 1.44 seconds; JIT table values exclude compilation. The host
is shared, and the NumPy version differs from the historical example benchmark:
these numbers do **not** establish an improvement/regression since its earlier
revision. Allocation, strided-loop and unaccelerated matmul costs remain useful
optimization targets. The old README explanation that all these numeric payloads
are scanned predates #603; [#210](https://github.com/den-run-ai/pystachy/issues/210)
now records the narrower residual paths. This run does not measure peak memory or
prove that GC scanning explains the remaining allocation cost; #582/#615 retain
that follow-up.

Tooling limitation: `bench.py` prints checksum disagreement without failing, and
its checksum compares selected native outputs, not full NumPy arrays. It is an
advisory timing tool; use the separate differential/reference tests as the
correctness gate. No new implementation crash or correctness failure was found
in these checks. No new issue was filed; remaining array/performance scope is
already tracked by #582/#210/#615.

Reproduce from the evaluated checkout with the toolchain on `PATH`:

```sh
PYTHONPATH=examples/ndarray python3.13 tests/example_ndarray.py
PYTHONPATH=examples/ndarray python3.13 tests/example_ndarray_edges.py
PYTHONPATH=examples/ndarray python3.13 tests/example_ndarray_upstream.py
PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/example_ndarray.py tests/example_ndarray_edges.py tests/example_ndarray_upstream.py
PYSTACHY_JOBS=2 PYSTACHY_GC_STRESS_PROGRAM=1 PYSTACHY_GC_STRESS=1000 tests/run.sh ./pystachy 'jit aot' tests/example_ndarray.py tests/example_ndarray_edges.py tests/example_ndarray_upstream.py
# CPython 3.13.16 environment with numpy==2.3.5:
python examples/ndarray/check_numpy.py
python examples/ndarray/check_upstream.py
python -I examples/ndarray/bench.py ./pystachy 4000000 5
```

## 2026-10-17 — #609: typed calls into C libraries

Evaluation target: main `cad7e04206d3743ac18284a5e33f49da86aa6206`, merging
[#609](https://github.com/den-run-ai/pystachy/pull/609) after evaluated `c916ca6c`.
This merge changes compiler annotation resolution and C-call lowering, and the
CPython ctypes twin; runtime and shipped library/port sources are unchanged.
The compiler was rebuilt from the target source before native measurements.

The measured new capability is a typed C-library adapter: `list[float]` passes
as `double *`, `list[ffi.c_int64]`/`list[ffi.c_ssize_t]` as `int64_t *`, and scalar
`ffi.c_float` calls the C float32 ABI. Qualified imports, aliases, quoted
annotations and `typing.List` spellings work in the selected calls. Existing C
kernels with these simple signatures need a small explicit declaration rather
than per-element shims. The CPython twin copies distinct lists in/out while
preserving alias identity; native calls borrow list storage for the duration of
the call. These are different performance models.

Remaining boundaries: float32 **arrays** are still rejected, as are narrower
integer arrays, optional lists, list return values and arbitrary containers.
The C function still needs the correct ABI and separately supplied length; it
must not retain the borrowed pointer. General NumPy/PyPI extension imports,
callbacks, structs and CPython embedding do not follow from this change.
[#582](https://github.com/den-run-ai/pystachy/issues/582) tracks optional BLAS
integration into the array example; this merge does not accelerate its existing
matmul. [#614](https://github.com/den-run-ai/pystachy/issues/614)'s qualified FFI
annotation case is now accepted; the prior compiler's rejection is retained.

No timing or peak-memory claim is made here. The previous ndarray benchmark
remains a separate snapshot; BLAS adapter correctness is not a speed comparison.

[Normalized evidence](compatibility-2026-10-17-ffi.json) retains compiler/source
identity, source hashes, exact programs, commands, outputs and sweep metadata.
Inputs: CPython **3.13.16**, LLVM **18.1.3**, Linux x86-64, system `libblas.so.3`
(hash recorded). The compiler/runtime bootstrap reached **608,154 / 17,615**
IR-line fixed points. Compiler SHA-256:
`659b844a8167b6d3674595612d88ff2df3cc37eb9ef8dcaca4a4ce7e197c5b19`.

| Evidence category | Result |
|---|---|
| Native FFI suite | **61 passed, 0 failed**, no extension skips. Includes 18 C-call JIT/AOT checks, 32 expected compile rejections, and 11 extension build/client checks hosted by CPython. |
| Focused fresh CPython references | `c_lists`, `c_float`, `c_qualified`, `c_lists_typing` all match their checked-in recordings. The same sources are rejected by the baseline native compiler, with exact first errors retained. |
| Per-allocation-GC native probes | Those four programs plus a system-BLAS adapter match CPython in JIT/AOT: **10/10**. The first eight repeat suite programs under stronger program-GC stress, not eight new workloads. |
| System-BLAS adapter | `cblas_daxpy` gives `[12.0, 24.0, 36.0]` for distinct output, `[3.0, 6.0, 9.0]` for aliased input/output, and `[]` for length zero in CPython/JIT/AOT. Previous compiler rejects its `list[float]` signature. |
| Existing ndarray regression programs | **6/6** JIT/AOT checks with collection at every program allocation; includes the 432 adapted upstream assertions per upstream-program execution. |
| Isolated stdlib import IR | **141/476**, with **46 exclusions**, **335 errors**, **0 timeouts**. All 522 inventory entries and every normalized result/first error equal the original baseline. |

The unchanged import results also retain the existing `unittest`/harness first
blockers. An FFI improvement is not an import-count improvement. The stub sweep,
full stdlib/API/port suites and pyperformance census were not repeated: no new
FFI use was added to those workloads. No new correctness failure or compiler
crash was observed in this focused evaluation; existing #582/#210/#615 scope
remains separate and was not remeasured or closed.

Reproduction (LLVM 18 on `PATH`, `PY` below selects CPython 3.13.16):

```sh
make PY=/root/.local/bin/python3.13
PY=/root/.local/bin/python3.13 CC=clang tests/ffi/run.sh ./pystachy 'jit aot'
PYSTACHY_JOBS=2 PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' tests/example_ndarray.py tests/example_ndarray_edges.py tests/example_ndarray_upstream.py
# Use PR #635's metadata-enabled tool with the evaluated compiler and its lib/:
python3.13 ../pystachy/tools/import_sweep.py -j 4 --metadata build/audit-609/imports-metadata.json ./pystachy <CPYTHON_STDLIB> build/audit-609/imports.json
```

The JSON contains the BLAS program and precise per-probe invocations. Build
`tests/ffi/ffitest.c` as `libpystachy-ffitest.so` on `LD_LIBRARY_PATH`; CPython uses
`PYTHONPATH=tools/rt_cpython`. The native probes use
`PYSTACHY_GC_STRESS_PROGRAM=1` for JIT and `PYSTACHY_GC_STRESS=1` for AOT execution.

## 2026-10-17 — #600/#601/#602/#604/#606/#622: imports, APIs and replacement memory

Evaluated [main `e939cf89`](https://github.com/den-run-ai/pystachy/commit/e939cf89a585efeee01016d7005c9e7fcdda70a9),
after `cad7e042`. All six merge commits were fetched and verified in its first-parent
history: [#600](https://github.com/den-run-ai/pystachy/pull/600) (`8640eea8`),
[#601](https://github.com/den-run-ai/pystachy/pull/601) (`9f34bc95`),
[#602](https://github.com/den-run-ai/pystachy/pull/602) (`08315030`),
[#604](https://github.com/den-run-ai/pystachy/pull/604) (`97037665`),
[#606](https://github.com/den-run-ai/pystachy/pull/606) (`9d3f1d54`) and
[#622](https://github.com/den-run-ai/pystachy/pull/622) (`e939cf89`).

[Machine-readable evidence](compatibility-2026-10-17-import-api-delta.json) retains
full import results/deltas, metadata, exact API programs, commands, input hashes,
raw performance samples and reproduction drivers. CPython **3.13.16**, LLVM
**18.1.3**, Linux x86-64; rebuilt compiler/runtime fixed points **616,258 / 18,388**
IR lines. Compiler SHA-256:
`05767f036b370a37a38544b268b67574dcd4353830dd5050adef5b742eace152`.
The previous comparison compiler is the retained `cad7e042` build.

| Evidence category | Fresh result |
|---|---|
| Native isolated imports | **142/476**, up from 141; unchanged 522-file inventory and 46 exclusions; 334 errors, zero timeouts. `wave` is the sole new success; no previously successful import is lost. 30 normalized entries change. |
| Hosted imports with throwing C-module stubs | **146/476**, up from 145; 142 need no stub, four require stubs. No lost imports or timeouts; 138 normalized entries change. This remains dependency diagnosis, not C-module execution. |
| Selected native regression checks, collection at every program allocation | **125 passed, zero failed** across 83 files: 80 positive JIT/AOT, 41 expected compile rejections, four documented-deviation executions. Includes **14 checks over seven adapted pyfiglet/tomli-w/sgp4 workloads**; do not add these again. |
| Fresh CPython recordings | All **12** new/changed executable test programs match the checked-in stdout/exit/error recordings, including decorator names, namedtuple, TextIOWrapper and dense replacement. |
| FFI/extension regression suite | **61 passed, zero failed**, no skips; includes the updated extension client's host `sys.warnoptions` copy. |
| Hosted runtime differential checks | `tools/rtcheck.py 100 23`: **14,072 cases, zero failed**. These directly exercise runtime.py with CPython twins, not compiled upstream suites. |
| Adapted benchmark smoke | `regex_dna`, `regex_effbot`, `regex_v8`: all three match CPython in JIT/AOT. Tiny smoke timings are not performance evidence. Controller/source checkout is audit `6343c524`; unchanged benchmark source hashes and evaluated compiler hash are recorded separately. |

An intermediate hosted stub sweep at `9f34bc95` already gains `wave`; later
#602/#606 move blockers without adding another successful import. The final
native sweep is measured with the rebuilt six-merge compiler.

### What now executes, and what still needs adaptation

- **Literal module-level `collections.namedtuple`** calls now execute, including
  defaults, field access and a selected `_replace` call. The fresh program matches
  CPython in JIT/AOT. Dynamic field specifications, namedtuple subclasses and
  the recorded mixed/None cases remain expected compile rejections.
- **Unmodified sgp4 2.27 `earth_gravity`** now executes in JIT/AOT and matches
  CPython for all three shipped gravity models and `EarthGravity._fields`.
  The previous compiler rejects its namedtuple import. This removes the need for
  that port's old namedtuple workaround for this measured module; it does not
  establish that the whole upstream sgp4 package or extension runs unchanged.
- **`wave`'s private parameter tuple** executes correctly, but a valid two-frame
  in-memory WAV still fails through both `wave.open` and direct `Wave_read`:
  `_i_opened_the_file` needs field-type inference/annotation. Import success is
  therefore not a working WAV-reader claim. No minimal source adaptation was
  validated for the full reader.
- **`io.TextIOWrapper`** works over the selected custom buffers and BytesIO,
  including decoding, newline processing and writes. Rejections/deviations remain
  for seek/tell/detach/reconfigure, added attributes and mixed-newline tuples.
  Non-UTF-8/Latin-1/ASCII codecs and automatic finalizer flushing remain documented
  limitations; these merges do not provide general file-object compatibility.
- **`sys.warnoptions`** supports the standalone empty mutable list and a copied
  host list in extensions. Rebinding remains rejected; Python warning environment
  options are not implemented by this change.
- **Imported decorated function names** now match fresh CPython output, including
  aliases, `wraps` and nested qualified names. #622 fixes observable metadata
  ([#613](https://github.com/den-run-ai/pystachy/issues/613)), not just diagnostics.

The library-overlay context matters: the selected `statistics.linear_regression`
call without the CPython overlay still rejects a `Generator[float]` where a
`list[float]` is required, in both comparison compilers. With the overlay it fails
earlier through decimal/contextvars (`_contextvars`). Neither attempt establishes
new linear-regression API support.

Native `unittest` and the unmodified fnmatch test still encounter missing `_ast`;
with C stubs, `unittest`, inspect and tokenize reach token's computed `__all__`
([#608](https://github.com/den-run-ai/pystachy/pull/608)'s scope). Native pyperf
2.10.0 stops at `select`, pyperformance 1.14.0 at `_imp`, and pytest 8.4.2 at `_ast`.
With stubs, socket advances to mixed `socketpair` bindings; warnings reaches mixed
`m` bindings or conditional `re` imports. First-error movement is progress, but
these module hubs and native test runners still require major compatibility work;
see [#491](https://github.com/den-run-ai/pystachy/issues/491).
Full CPython regrtest and the 52-source benchmark census were not rerun.

Fresh retained controls also reconfirm [#120](https://github.com/den-run-ai/pystachy/issues/120)
(Unicode length/span: CPython `4 (3, 4)`, native `5 (3, 5)`) and
[#620](https://github.com/den-run-ai/pystachy/issues/620) (unannotated cached function
rejected; fully annotated control matches in JIT/AOT). Other baseline gaps were
not remeasured in this batch and retain their original dated evidence.

### Dense replacement: measured memory improvement

Five samples per mode, alternating process order, no forced GC. Linux `wait4`
records CPU (user + system) and peak RSS; inputs, allocation and printed checksum
are included, AOT compilation is excluded. Every sample's output matches CPython.
One-minute host load ranged about **1.97–2.06**; this is a shared machine.

| Workload | Previous AOT CPU / RSS | Current AOT CPU / RSS | CPython CPU / RSS |
|---|---:|---:|---:|
| Delete 10M stars, retain `end` | 0.209 s / 160.9 MiB | **0.053 s / 21.0 MiB** | 0.098 s / 28.6 MiB |
| Replace 5M commas in 10M bytes | 0.110 s / 81.0 MiB | **0.056 s / 21.0 MiB** | 0.028 s / 28.8 MiB |
| Delete 9,999,999 of 10M stars | 0.182 s / 151.3 MiB | **0.047 s / 15.0 MiB** | 0.088 s / 19.0 MiB |
| `tools/rtbench/replace_limit.py` | 1.350 s / 216.4 MiB | **0.351 s / 52.0 MiB** | 0.640 s / 38.0 MiB |

The existing `replace.py`/`replace_text.py` rows have nearly unchanged medians;
the bounded-small case is also similar. The clear peak-memory reduction supports
#604/#36's dense-occurrence fix. These short CPU samples do not establish universal
speedups or exclude the PR's documented costly-candidate trade-off. Current comma
replacement remains slower than CPython in this workload. No new correctness
failure or compiler crash was found in the valid checks.

Initial scratch harness attempts had name-shadowing/path/toolchain errors; they
were invalidated and rerun, with corrections retained in JSON. They are not
Pystachy regressions. Reproduce using the JSON's drivers and selected file list:
`make PY=python3.13`; metadata-enabled normal and `--stubs` import sweeps;
`PYSTACHY_JOBS=4 PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' <selected files>`;
`PY=python3.13 CC=clang tests/ffi/run.sh ./pystachy 'jit aot'`; and
`python3.13 tools/rtcheck.py 100 23`, with LLVM 18 on `PATH`.

## 2026-10-17 — #605: retained string capacity

Evaluated [main `c2705aee`](https://github.com/den-run-ai/pystachy/commit/c2705aee72d865583627202340de67f5eca163cd),
the next first-parent commit after `e939cf89`, merging
[#605](https://github.com/den-run-ai/pystachy/pull/605) at **07:12:43 UTC**.
Its seven changed files affect runtime.c string allocation/trimming, two regression
programs, the runtime-contract checker and documentation. Compiler Python sources,
shipped modules and ports are unchanged. The compiler was nevertheless rebuilt
with the new C runtime: fixed points **616,258 / 18,388** IR lines; binary SHA-256
`8aa03dd4a0240bb339c4b276985cccf4ea4dbe622d6e8fcea8e6ac694bd3a9d9`.

[Normalized evidence](compatibility-2026-10-17-string-capacity.json) records the
CPython **3.13.16** / LLVM **18.1.3** environment, changed-file hashes, commands,
selected programs, full raw samples and reproduction scripts.

- **20/20 JIT/AOT checks**, collection at every program allocation, cover ten
  string-append, GC and dense-replacement programs, including aliasing and regrowth.
- **14/14 normal JIT/AOT checks** cover the same seven adapted text/sgp4 port
  workloads as the previous checkpoint. These are fresh repeats, not new ports.
- Both new append programs match fresh CPython recordings. The runtime-contract
  checker passes: **427 entries, 70 exception classes, 170 functions**.
- The fresh native import sweep remains **142/476**, with 46 exclusions, 334 errors
  and zero timeouts; **every result equals the previous checkpoint**. No new API
  acceptance is claimed. The stub sweep and unrelated upstream suites were not repeated.

Five alternating-order AOT/CPython samples per workload use Linux `wait4` for
CPU and peak RSS. Compilation is excluded; construction, retained strings and
checksummed output are included. No forced GC; shared-host load is recorded for
each row (one-minute load about 2.01–3.28 across the run). All sample outputs
match CPython. Selected medians:

| Workload | Previous AOT CPU / RSS | Current AOT CPU / RSS | CPython CPU / RSS |
|---|---:|---:|---:|
| Keep 10,000 strings just past the 8,200-byte boundary | 0.125 s / 286.4 MiB | **0.088 s / 173.4 MiB** | 0.044 s / 88.7 MiB |
| Keep 2,000 strings of 40,000 bytes, each built by 1,000 appends | 0.152 s / 204.9 MiB | **0.148 s / 152.7 MiB** | 0.106 s / 86.3 MiB |
| Read an alias every third append, 20,000 appends of 32 bytes | 0.399 s / 37.8 MiB | 0.438 s / 37.8 MiB | 0.801 s / 14.7 MiB |

The first two rows reproduce the retained-capacity improvement tracked by the
now-closed [#567](https://github.com/den-run-ai/pystachy/issues/567). This measures
process **peak** memory, not the resident memory after two stable sweeps; it does
not independently isolate how many pages `madvise` returned. Current retention
still uses substantially more peak memory than CPython. General heap-growth
policy [#615](https://github.com/den-run-ai/pystachy/issues/615) and dead-string
allocation [#127](https://github.com/den-run-ai/pystachy/issues/127) remain separate.

The read-between-appends row is an advisory possible slowdown, not a confirmed
regression: previous CPU samples span **0.371–0.449 s**, current **0.414–0.454 s**.
Those ranges overlap on this shared host; do not extrapolate a universal 10%
regression from the medians. Exact samples are retained for targeted follow-up.
The additional module-level continuous-append control has CPU medians 5.899 s
(previous), 5.998 s (current), 14.369 s (CPython), with unchanged native peak RSS.
It uses a global string, not the optimized local append path; it is not a
linear-scaling claim.
No new correctness failure or crash was found, and no duplicate issue was filed.

Reproduction: rebuild with `make PY=python3.13`, run the JSON's two explicit
selected-file lists via `tests/run.sh ./pystachy 'jit aot'` (GC interval one for
the string/GC list), `python3.13 tools/check_runtime.py`, and the same
metadata-enabled import sweep. The JSON's `perf.py` compares the retained
`e939cf89` compiler with `c2705aee` on the four embedded exact programs.

## 2026-10-17 — #607: inferred Any signatures and affected ports

Evaluated [main `765564a3`](https://github.com/den-run-ai/pystachy/commit/765564a34fdbf7abfb807df236a43f93f1bfe06f),
merging [#607](https://github.com/den-run-ai/pystachy/pull/607) at
2026-10-17 07:29:02 UTC. It is the only main merge since the completed `c2705aee`
checkpoint. The 48-file diff changes compiler annotation/template handling,
tests, documentation and three ports; runtime and shipped stdlib implementations
are unchanged. Rebuilt with CPython 3.13.16 and LLVM 18.1.3: bootstrap fixed points
are **617,068 compiler / 18,388 runtime IR lines**. Native compiler SHA-256:
`849d62bf19635fd9e180c4f81329f9b6886a62a3ec406c96ee4db390c2da5009`.

[Normalized evidence](compatibility-2026-10-17-any-signatures.json) retains
source/binary/input hashes, exact programs and commands, both compiler diagnostics,
CPython/JIT/AOT outputs, import metadata and explicit unsuccessful setup attempts.
The previous compiler is rebuilt `c2705aee`, hash
`8aa03dd4a0240bb339c4b276985cccf4ea4dbe622d6e8fcea8e6ac694bd3a9d9`.

| Evidence category | Fresh result |
|---|---|
| Isolated import IR | **142/476**, 46 exclusions; every module result identical to `c2705aee`. |
| CPython-hosted compiler with throwing C-module stubs | **146/476**, including 142 without stubs; every result identical to the retained `e939cf89` stub sweep. No timeout. |
| Changed signature/diagnostic tests | **25 checks pass**: 10 positive JIT/AOT checks with per-allocation program GC and 15 expected compile rejections, over 20 source files. |
| Affected adapted ports | **14/14 JIT/AOT** checks across seven ordered-set, tomli-w and pyfiglet programs. Six upstream Any annotations are restored in these ports. |
| Fresh CPython recordings | All six selected positive recordings match. Two initially lacked `typing_extensions`; both pass with existing pip-vendored **4.12.2**, whose source hash is retained. |
| Retained/custom differential programs | 23 programs: 10 compile and execute in JIT/AOT; 8 match CPython and 2 retain known Unicode/integer-width deviations. 13 stop at explicit compile blockers. All 23 CPython references execute successfully. |
| Adapted benchmark smoke | Richards and Richards-super match CPython/JIT/AOT checksums at argument `1`. One shared-host sample each is a correctness smoke, not evidence of a speed change. |

Four differential programs change from rejection to successful execution: the
retained Any identity/signature case; `Mapping[str, Any]` plus variadic Any
parameters; a namedtuple `_replace` helper taking/returning Any; and the adapted
ordered-set's comparison with a list. Both native execution modes match CPython,
including per-allocation GC. The ordered-set comparison includes its shipped
port edit as well as the compiler change; it is not a compiler-only attribution.
The one-edit iniconfig section-iteration probe succeeds with both old and new
compilers, so this particular probe establishes **no new gain**.

Any in an eligible function/method signature now requests concrete per-call
inference. It does not provide dynamically boxed storage or runtime validation
of the erased annotation. This removes some annotation edits from maintained
ports; it does not remove their other adaptations. Four pinned **unmodified**
upstream package probes still fail at the same earlier first errors:

| Package | First native blocker, unchanged |
|---|---|
| tomli-w 1.2.0 | `types.MappingProxyType` |
| ordered-set 4.1.0 | `slice(None)` |
| pyfiglet 1.0.4 | unavailable `importlib` |
| iniconfig 2.3.1 | `\N{...}` escape; the retained one-edit BOM replacement remains a minor adaptation for the selected successful operations |

These first-error checks cannot establish that later Any uses or whole upstream
suites work. Existing minor/major adaptation assessments remain in the baseline.
No general PyPI/NumPy compatibility, native pyperf/pytest support or full CPython
regrtest result is inferred from these measurements. The unchanged 52-source
upstream benchmark census and broader hosted suites were not rerun.

Known gaps were retested: Any variable storage (#617), constructors (#618),
non-generator `__iter__` returns (#619), cached Any/unannotated signatures (#620),
and forwarding recursion (#595/#621) still reject. In
`Generator[int, Any, None]`, sending a string still rejects and asks for an
annotation already present: retain #616/#633 as the owner of that diagnostic/
inference limitation. Mixed numeric `sum` (#596), bare list annotations (#597),
Unicode length/offset behavior (#120), and integer-width differences also persist;
concretely annotated cache, recursion and float-sum controls pass. The current
coordination discussions in #491/#616 and #607 were read; pending #629–#634 are
not counted as shipped. No uncovered crash or new correctness regression was
observed, and no duplicate issue was filed. Runtime/performance sources are
unchanged, so the prior memory measurements remain historical, not fresh results.

Reproduce using the evidence's exact selected file lists and embedded scripts:

```sh
make PY=python3.13
PYSTACHY_JOBS=4 PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' <gc_tests files from JSON>
PYSTACHY_JOBS=4 tests/run.sh ./pystachy 'jit aot' <normal_ports files from JSON>
python3.13 /path/to/audit/tools/import_sweep.py -j 4 --metadata imports-metadata.json ./pystachy "$CPYTHON_STDLIB" imports.json
# Run retained stub_sweep.py and probes.py from the JSON, adjusting checkout paths.
# Benchmark tool/source is audit 50fc4a11; select the freshly built 765564a3 compiler:
python3.13 /path/to/audit/tools/bench_pyperformance.py --compiler "$NATIVE_COMPILER" --benchmarks richards richards_super --smoke --json bench.json
```

Set `PYSTACHY_LLVM` or put LLVM 18 on `PATH` before these commands. An initial
benchmark warmup omitted that setting and failed before measuring anything;
the successful rerun and invalid attempt are retained separately. The benchmark
metadata's `git_revision` describes its audit tool/source checkout, while its
compiler hash identifies the evaluated main build. Both Richards sources are
unchanged between these revisions.

The audit branch also incorporates this evaluated main and resolves its
`docs/stdlib.md` conflict, preserving the merged Any wording and the audit's
corrections about supported generators and bounded unions. No implementation
branch was modified and no implementation PR was merged by this audit.

## 2026-10-17 — #629: initialized Any variables

Evaluated [main `dbac05d7`](https://github.com/den-run-ai/pystachy/commit/dbac05d7d4ab02ffdc737497cff940b4e95ec278),
which merges [#629](https://github.com/den-run-ai/pystachy/pull/629). Its merge
was re-fetched and verified in main's history. This is the only merge since the
previous evaluated `765564a3`. The diff changes compiler annotation normalization,
tests and typing documentation; runtime, library, port and benchmark sources are
unchanged. Current #491/#616 and #629 coordination comments were read; #630 and
later stack members are not counted as shipped.

[Normalized evidence](compatibility-2026-10-17-any-variables.json) preserves the
exact programs, commands, selected tests, package hashes, import metadata and
compiler hashes. CPython 3.13.16 and LLVM 18.1.3 are retained. The compiler was
rebuilt at this exact main revision and reached compiler/runtime bootstrap fixed
points (**617,419 / 18,388** IR lines).

| Evidence category | Fresh result |
|---|---|
| Isolated import programs | **142/476** compile, with the same 46 overlay exclusions; every result is identical to `765564a3`, with no timeout. |
| Hosted compiler with throwing C-module stubs | **146/476**, including 142 without stubs; every result is identical to `765564a3`, with no timeout. |
| Focused native checks | **19/19**: 14 positive JIT/AOT checks with per-allocation GC plus five expected rejections. These cover three new variable programs and four retained signature programs. |
| Adapted port checks | **14/14** normal JIT/AOT checks across seven ordered-set, tomli-w and pyfiglet programs. |
| Fresh CPython recordings | All seven selected positive programs match their checked-in recordings; typing_extensions 4.12.2's retained source supplies the reference dependency. |
| Differential probes | 19 programs compare the prior and rebuilt compilers; nine execute in JIT/AOT and match fresh CPython results. Two previously rejected programs now pass: an initialized Any module variable, and nested inferred containers/local retyping. |

Initialized module/local annotations containing Any now use assignment inference.
The new programs cover aliases, quoted/future annotations, imports, empty
containers filled later, concrete generic instances, nested functions and local
retyping. The entire Any-containing annotation is inferred; its concrete parts
do not become runtime checks. This is a useful removal of source annotations/
adaptations, but it does not provide arbitrarily mixed storage. The tests still
reject class fields and annotation-only Any declarations, changing a global's
inferred type, and appending a string to an inferred integer list. Keep
[#617](https://github.com/den-run-ai/pystachy/issues/617) narrowed to the remaining
annotation-only scope, with dynamic storage tracked separately.

Retained constructor, non-generator iterator-return, cached Any/unannotated
function and generator-send probes still reject (#618/#619/#620/#616); forwarding
recursion remains blocked (#595/#621), while its annotated control passes. The
four pinned unmodified upstream package probes retain their earlier first errors:
tomli-w `MappingProxyType`, ordered-set `slice(None)`, pyfiglet `importlib`, and
iniconfig's named Unicode escape. The one-edit iniconfig iterator and maintained
ordered-set/list equality controls still pass. First-error probes cannot establish
whether later Any variables or whole upstream suites work; prior minor/major
adaptation assessments remain unchanged.

No new uncovered bug or regression was observed. This run makes no new
performance claim. Unchanged broad benchmarks, the 52-source upstream census,
full hosted suites and full CPython regrtest were not repeated. Prior measurements
remain historical evidence. No implementation branch or PR was changed by this
audit.

Reproduce with the retained toolchain and the exact selected file lists/scripts
embedded in the JSON:

```sh
make PY=python3.13
PYSTACHY_JOBS=4 PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' <gc_tests files>
PYSTACHY_JOBS=4 tests/run.sh ./pystachy 'jit aot' <normal_ports files>
python3.13 /path/to/audit/tools/import_sweep.py -j 4 --metadata imports-metadata.json ./pystachy "$CPYTHON_STDLIB" imports.json
# Run retained stub_sweep.py and probes.py, adjusting checkout paths.
```


## 2026-10-17 — #643/#640/#624, then #623/#638/#639

Two measured checkpoints cover all six merges since `dbac05d7`:

- [Main `99879455`](https://github.com/den-run-ai/pystachy/commit/99879455b3db5ad4ccdbd014250aba484b4a240c):
  [#643](https://github.com/den-run-ai/pystachy/pull/643) CI cancellation,
  [#640](https://github.com/den-run-ai/pystachy/pull/640) optional ndarray CBLAS,
  [#624](https://github.com/den-run-ai/pystachy/pull/624) regex subject-cache release.
- [Main `08e437b6`](https://github.com/den-run-ai/pystachy/commit/08e437b6e63f67de65aaea5b5ca08280a866807f):
  [#623](https://github.com/den-run-ai/pystachy/pull/623) shared short strings,
  [#638](https://github.com/den-run-ai/pystachy/pull/638) object powers,
  [#639](https://github.com/den-run-ai/pystachy/pull/639) adapted microGPT benchmark.

All merges were re-fetched and verified in main's history; #491/#616 and the
relevant PR discussions were read. [Normalized evidence](compatibility-2026-10-17-regex-blas-microgpt.json)
retains exact commands, selected programs, reproduction scripts, hashes, import
metadata, numerical comparisons, raw timing/RSS samples and one unsuccessful
optional probe. CPython **3.13.16**, LLVM **18.1.3** and NumPy **2.3.5** are pinned.

The first checkpoint changes no compiler/runtime source: it reuses the verified
`dbac05d7` compiler (`d2973670…`) with `99879455` library/example files. The second
rebuilds at `08e437b6` (`c46436b3…`), reaching compiler/runtime bootstrap fixed
points of **617,984 / 18,388 IR lines**. Full compiler hashes are in the evidence.

| Evidence category | Fresh result |
|---|---|
| Isolated imports, both checkpoints | **142/476** native, **146/476** with throwing C-module stubs; the same 46 exclusions. Every normalized module result matches its previous checkpoint; no timeout. |
| Regex/array checkpoint | **28** normal JIT/AOT checks across regex APIs, four maintained iniconfig/pyfiglet workloads and three ndarray programs; **12** GC-stressed checks, including six documented-deviation checks. All 14 fresh CPython recordings match. Three adapted regex benchmark smoke programs match CPython/JIT/AOT. |
| Final string/power checkpoint | **36** focused checks: 26 recorded JIT/AOT checks with per-allocation GC and ten expected compile rejections. All 13 fresh CPython recordings match. Eight affected port checks and four additional GC-stressed regex-policy checks pass. Runtime signatures/effects agree. |
| Optional CBLAS, both checkpoints | Per checkpoint, **24 matrix cases + 15 invalid inputs** pass under CPython, JIT, AOT and both GC-stressed native modes (195 case checks). Every matrix element matches NumPy within `1e-12`; maximum absolute difference is approximately `3.55e-15`. |
| microGPT | Original/adapted CPython and native JIT/AOT all verify **10 training steps, 73 tokens, three names**, with **58,698 numeric comparisons per process** including every gradient. JIT/adapted CPython are exact; AOT maximum absolute difference is approximately `8.47e-22`. Three hosted controller tests, including 26 graph cases, pass. |

Object `**`, two-argument `pow` and `**=` with builtin numeric exponents now work
in the two retained object-power programs that the previous compiler rejected.
Nullable receivers, variadic binding, inherited overrides and evaluation order
are covered. Reflected/object/optional exponents, modular object `pow` and
`NotImplemented` remain outside this bounded support; #113 stays relevant.

Unmodified microGPT still stops at `urllib.request` in both compilers. Its
maintained adaptation preserves model/math/RNG behavior but changes annotations,
recursive child storage, scalar boxing, sums and selected generator expressions.
That is substantial source adaptation, not unmodified-source or general
micrograd/PyPI compatibility. The pinned names dataset hash is retained. This
ten-step run is a correctness check during concurrent audit work: its single-run
timings do not replace #639's separately pinned performance study or establish
full-training convergence. The controller and graph tests are CPython-hosted.

The optional array module calls **LP64 `libblas.so.3:cblas_dgemm`** on float64
buffers, with packing for unsupported views and disjoint output. This host uses
Debian reference BLAS **3.12.0-3build1.1**, with its binary hash recorded; these
checks make no optimized-BLAS speed claim. Native runs require that shared library,
but not embedded CPython/NumPy. Neither this adapter nor the hosted NumPy checker
establishes native NumPy import/suite support. #582 retains the remaining scope.

Five alternating-order AOT samples per workload use normal GC, no CPU affinity,
and a shared host. Raw ranges and load averages are retained; values below are
medians. Regex comparisons isolate `dbac05d7 → 99879455`; split comparisons use
`99879455 → 08e437b6`. All workload outputs match fresh CPython references.

| Workload | Previous | Current | Interpretation |
|---|---:|---:|---|
| Full-scan regex, then retain 150 MB of unrelated strings: end RSS | 404.7 MiB | 297.2 MiB | Released decoding no longer remains live after later collections. Peak RSS falls less: 404.7 → 389.7 MiB. |
| 20 full scans of one 2.16 MB nonmatching subject: process CPU | 0.1268 s | 0.4782 s | Documented re-decoding trade-off, **3.77× on this workload**; five ranges do not overlap. Peak RSS rises 36.0 → 68.5 MiB. This is not a universal regex slowdown. |
| Ten million empty split parts: peak RSS / process CPU | 383.1 MiB / 0.2845 s | 151.3 MiB / 0.1851 s | Shared empty strings remove per-part allocations. |
| Ten million one-byte split parts: peak RSS / process CPU | 392.7 MiB / 0.2985 s | 160.9 MiB / 0.2217 s | Shared one-byte strings reduce allocations; alias/hash checks still pass. |

Regex compact decoding, large `search`/`match` cache retention, exception exits
and the repeated-full-scan cost remain under #589. Growing bounded windows retain
their cache and pass the stressed regression tests. An optional cross-revision
counter probe failed because old `dbac05d7` has no `re._KEEP`; the evidence records
that probe-version mismatch. Both complete memory/timing groups were saved before
that optional failure. No product correctness failure was observed. Large split
result-list overhead remains #628; one CPython correctness reference used about
95.5/105.0 MiB for the empty/one-byte cases, not a repeated CPython timing baseline.

#643 changes only the final CI report's cancellation condition. The audit branch
incorporates evaluated main, preserving that fix and both import-sweep and
microGPT lint checks when resolving their insertion conflict. No implementation
branch or PR was changed by this audit. The three affected audit/controller test
modules pass on the combined branch (**10 + 16 + 3** tests).

Baseline reports and JSON remain unchanged. No full CPython regrtest, full
upstream package suites, 52-source census or unrelated broad benchmarks were
rerun; no new import capability is inferred from the passing adaptations.

## 2026-10-17 — token port (#608)

Evaluated [main `dcdee6ba`](https://github.com/den-run-ai/pystachy/commit/dcdee6ba396b970b469bbf26a63a29a288b3deeb)
after [#608](https://github.com/den-run-ai/pystachy/pull/608) merged at 08:43:03 UTC.
This is the only new merge since `08e437b6`; ancestry and the six changed files
were checked. #491/#616 and #608 comments were reviewed before testing.
[Normalized evidence](compatibility-2026-10-17-token.json) retains the programs,
commands, source/input hashes, metadata, full per-module results and exact deltas.

No compiler/runtime source changed. The verified `08e437b6` compiler is reused
(SHA-256 `c46436b382a00acf7596dc9111d607b6586dea3b4bd0ea410e6f273c339ff84b`),
with library sources from `dcdee6ba`. CPython **3.13.16** and LLVM **18.1.3** are
unchanged. This is not presented as a fresh compiler bootstrap.

| Evidence | Result |
|---|---|
| Native token API | The full retained table/export recording matches fresh CPython: 73 exports, 68 token names, 48 exact-token entries and three predicates. **Four native checks pass**: JIT/AOT with normal GC and with per-allocation GC. The previous checkout rejects the same source at computed `token.__all__`. |
| Isolated native imports | **142/475**, no timeout or lost successful imports. Same 522-file inventory; **47 exclusions**, up from 46 because shipped `lib/token.py` now replaces upstream `token.py`. The previous denominator was 476; this is an overlay change, not a regression or an extra successful upstream-source import. |
| Stub-assisted imports | **146/475**, including 142 without stubs; same 47 exclusions, no timeout. Throwing stubs remain dependency diagnostics, not native module implementations. |
| Native first errors | `tokenize` and `tabnanny` advance from computed token exports to missing **`_tokenize` at tokenize.py:37**. `inspect`, `doctest` and `unittest` still stop earlier at missing `_ast`. |
| Stub-assisted first errors | **42 modules** advance past token exports to **`inspect.py:1725`**, where `namedtuple('_FrameInfo', ('frame',) + Traceback._fields)` exceeds the literal-field rule. `tokenize` and `tabnanny` instead reach module-level **`del token` at line 45**. |
| API/blocker programs | Six small programs pass on CPython. Both previous/current native JIT and AOT-build attempts reject them before execution: tokenize, inspect, doctest, the retained unittest harness, module deletion and a minimal computed-namedtuple-fields reproduction. Exact first errors are retained; these are expected limitations, not six successful native APIs. |

The new `token` port is a **minor maintained adaptation**: explicit tables replace
two import-time computations; constants and predicates retain upstream behavior.
It does not make upstream `tokenize`, reflection or test runners work. Missing
`_tokenize` belongs with #491, module-name deletion with #612, and computed
namedtuple fields with the existing #256 collections scope. These observations
correct the stale prediction that module deletion would be the next *native*
error for all token-dependent importers. Full CPython regrtest remains unrun.

Reproduction uses the retained `evaluate.py` and `probes.py` scripts, notably:

```sh
python3.13 /path/to/audit/tools/import_sweep.py -j 4 --metadata imports-metadata.json ./pystachy /path/to/cpython3.13/Lib imports.json
# For --stubs, set the imported sweep module's ROOT to the evaluated checkout;
# evaluate.py records the exact hosted invocation and metadata.
tests/run.sh ./pystachy 'jit aot' tests/lib_token.py
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' tests/lib_token.py
python3.13 -I tests/lib_token.py
```

The audit branch incorporates this main revision without conflicts; import-sweep
tool tests pass again (**10 tests**). No direct token/tokenize imports were found
in maintained ports, benchmarks or examples, so unrelated port/performance suites
were not repeated. There is no new timing claim or uncovered correctness bug.
Historical reports and JSON remain unchanged.

## 2026-10-17 — explicit CPython embedding (#170)

Evaluated [main `cffa9934`](https://github.com/den-run-ai/pystachy/commit/cffa99346bc1a920a0c609d6c6b4468fe193d867)
after [#170](https://github.com/den-run-ai/pystachy/pull/170) merged at 08:55:28 UTC.
This is the only new merge after `dcdee6ba`; ancestry, changed files and the
#491/#616/#170 discussions were checked. [Normalized evidence](compatibility-2026-10-17-pyobj.json)
retains input hashes, compiler and libpython hashes, commands, programs, metadata,
bootstrap output and full import results.

Compiler/runtime changes require a fresh build. CPython **3.13.16** and LLVM
**18.1.3** reach fixed points of **620,366 / 18,388 IR lines**. The resulting
compiler hash is `79df1005ae2fa5634d92c822db019f5497b3a72d8bdd32444ec168e094adbef7`.
The build and evaluated source revisions are both `cffa9934`.

| Evidence category | Fresh result |
|---|---|
| Full FFI runner | **123 passed, zero failed, no skipped cases**: 18 C-call JIT/AOT checks, 42 expected compile rejections, 42 embedded-CPython JIT/AOT checks, 10 extension builds and 11 CPython-hosted extension-client comparisons. Includes finalization/output, SystemExit, reference release, nested extension reentry and borrowed buffers. |
| Native regression programs | **24 per-allocation-GC JIT/AOT checks** across 12 retained string, token, Any, power, ndarray, warning-options, numeric-container, TextIOWrapper and iniconfig programs. |
| Explicit stdlib bridge | JSON round trip including UTF-8 text, JSON exception mapping, and Decimal addition match the CPython twin in JIT/AOT with per-allocation GC. |
| Explicit PyPI bridge | NumPy **2.3.5** matrix multiplication, shared view mutation and shape-error mapping match the CPython twin in JIT/AOT with per-allocation GC. Both bridge programs are rejected by the previous checkout, which has no pyobj module. |
| Direct native NumPy control | The same simple upstream program runs on CPython 3.13.16 but is rejected by both previous/current native compilers at `numpy._core._multiarray_umath`. Its wheel source and stdlib overlay are explicit. No transparent NumPy support is claimed. |
| Native import sweep | **142/475**, with the same 47 exclusions and 522-file inventory; every normalized result equals `dcdee6ba`, no timeout. |
| Stub-assisted sweep | **146/475**, including 142 without stubs; every normalized result equals `dcdee6ba`, no timeout. This is still dependency diagnosis only. |

The two bridge programs add **four executed JIT/AOT checks**. They use explicit
`import_module`/`Object`/scalar adapters: JSON, Decimal and NumPy execute inside
installed CPython, not as compiled upstream package source. AOT links the pinned
`libpython3.13.so.1.0`; `readelf` confirms it, while the standalone compiler has
no libpython dependency. A NumPy Python object and its view preserve mutation
identity across these calls; `of_list` remains an explicit copy, not automatic
native-container interoperability. This is a useful opt-in route for selected
library calls, not an implementation of general native dynamic Python (#108).

The FFI runner's two memory checks were also repeated independently, asserting
the printed bounds are **True**, not merely equal to the twin. In both JIT and
AOT, 1,500 successive 1 MiB bytearrays (1,572,864,000 cumulative bytes) remain
below **200 MiB process peak RSS** with normal GC, and 100,000 dropped wrapped
integers leave fewer than 5,000 extra CPython allocated blocks with stress period
50. These **four additional checks** show bounded behavior for those workloads;
they are not repeated performance benchmarks or proof against all cross-runtime
cycles. Accounting is shallow and release/finalizer timing remains delayed.

Remaining contract boundaries are important: CPython 3.12+ shared-library setup;
tested embedding platform x86-64 Linux/glibc; positional-only bridge calls;
restricted extension exports and host-thread/subinterpreter behavior; no implicit
container conversions; absent Python caller frames; and documented Ctrl-C/exit
ordering differences. JIT adds `RTLD_DEEPBIND`; AOT is the reference tier. Native
unittest/pytest/pyperf and full CPython regrtest have not become supported merely
because their host interpreter can now be called. No full upstream suite or
performance trend is claimed, and no new correctness failure was observed.

Reproduction uses the retained `evaluate.py`, `bridges.py` and `memory.py`:

```sh
make PY=/root/.local/bin/python3.13
PY=/root/.local/bin/python3.13 tests/ffi/run.sh ./pystachy 'jit aot'
python3.13 build/audit-pyobj/evaluate.py
python3.13 build/audit-pyobj/bridges.py
python3.13 build/audit-pyobj/memory.py
```

The scripts retain exact `PYSTACHY_LIBPYTHON`, `PYTHONHOME`, module paths and GC
settings; NumPy is pinned through `uv --with numpy==2.3.5`. Runtime contracts pass
(430 entries, 70 exception classes, 170 functions). The audit branch incorporates
evaluated main without conflicts; its import-sweep and benchmark-controller tests
pass (**10 + 16**). The audit diff against evaluated main passes whitespace checks.
Historical reports and JSON remain unchanged.

## 2026-10-17 — #630: constructor inference without dynamic fields

Evaluated [main `91407759`](https://github.com/den-run-ai/pystachy/commit/91407759c9a3e3e0efc4a5b46dd1625f1506d64f)
after [#630](https://github.com/den-run-ai/pystachy/pull/630) merged at 09:46:44 UTC.
It is the only new merge after `cffa9934`; merge ancestry, changed files and the
#491/#616/#630 coordination notes were checked. Compiler declaration and class
specialization changed; runtime, library, port and benchmark sources did not.
[Normalized evidence](compatibility-2026-10-17-constructors.json) retains exact
programs, commands, outputs, input/compiler hashes, metadata and reproduction scripts.

Fresh CPython **3.13.16** / LLVM **18.1.3** bootstrap reaches **620,426 compiler /
18,388 runtime IR lines**. Compiler build and evaluated source are both `91407759`;
binary SHA-256 is `13c73ecb5679d61c8056860883528a6a4a86ffc8a556eaba78fe3d3e463849b9`.
The previous `cffa9934` compiler's source and retained binary hash were verified
before differential measurements.

| Evidence category | Fresh result |
|---|---|
| Focused native tests | **37 passed**: 28 positive JIT/AOT checks under per-allocation GC, plus nine expected compile rejections. Covers constructor annotations/imports/defaults/variadics, existing Any inference, singleton/object power and namedtuple integration. |
| CPython recordings | All **14 positive programs** match the checked-in recordings using pinned CPython; the typing_extensions 4.12.2 source hash is retained. |
| Retained adapted ports | **18 JIT/AOT checks** pass over nine iniconfig, ordered-set, pyfiglet and tomli-w workloads. |
| Differential API programs | All **21 CPython references** execute. Eleven programs match in both native JIT and AOT (**22 checks**); ten remain rejected at IR generation. Two programs change from previous rejection to matching execution: `Any` and direct `object` constructor parameters. |
| FFI integration | **123 passed, zero failures/skips**, including embedded CPython and extension/client tests. These remain explicit interoperability, not native upstream-package execution. |
| Native stdlib imports | **142/475**, 47 exclusions, 522-file inventory; every normalized result is unchanged, no timeouts. |
| Stub-assisted diagnosis | **146/475**, 142 without stubs; no acceptance changes or timeouts. Four existing inheritance errors gain the guidance “with concrete types (not Any or object)”; this is diagnostic improvement, not newly compiled modules. |

Ordinary explicit constructors can now keep these upstream annotations rather
than deleting them or choosing a concrete type. Each call still creates a concrete
class specialization. Nested `Any`, aliases, quoted annotations and imported
constructors are covered by the focused tests. This removes a **minor annotation
adaptation** for suitable classes; it does not supply uniform heterogeneous fields.
The independently run dataclass-`Any` probe still rejects. Field retyping, rebinding
between specializations, inheritance and `Any` constructor returns remain rejected;
concrete parameter constraints and Annotated metadata boundaries remain enforced.
[#618](https://github.com/den-run-ai/pystachy/issues/618) and
[#616](https://github.com/den-run-ai/pystachy/issues/616) already reflect the merge
and retain the residual scope; dynamic storage is separate work in #487.

The same unmodified upstream package programs remain blocked at the same first
errors, under their retained package-only module-path configuration:

| Pinned package | First native blocker |
|---|---|
| tomli-w 1.2.0 | `types.MappingProxyType` in `_writer.py:21` |
| pyfiglet 1.0.4 | Missing `importlib` on the configured module path |
| ordered-set 4.1.0 | Unsupported `slice(None)` |
| iniconfig 2.3.1 | Unsupported `\N{...}` escape in `_parse.py:8` |

These are first-error observations, not claims that fixing them completes each
package. Retained iterator-return, generator-send, unannotated/Any cache and
forwarding-recursion probes still reject (#619/#633/#620/#595); the annotated
cache/recursion and minimally adapted iniconfig controls still execute correctly.
Native unittest/pytest/pyperf and full CPython regrtest are not established by this
merge. No new uncovered correctness bug or lost successful probe was observed.
No performance/memory trend is measured; unchanged broad benchmark and hosted
compiler suites were not repeated.

Reproduce from the evaluated checkout (scripts are embedded in the JSON):

```sh
PATH=$LLVM18/bin:$PATH make PY=/root/.local/bin/python3.13
/root/.local/bin/python3.13 build/audit-constructors/evaluate.py
/root/.local/bin/python3.13 build/audit-constructors/build_evidence.py
```

Both sweeps use the retained audit's `import_sweep.py --metadata`, unchanged
CPython inventory and shipped-library overlay; stub mode uses the hosted compiler
and throwing stand-ins, not working C modules. The audit-tool tests pass **10 + 16**.
An initial `python -m unittest tools...` invocation lacked `tools` on `sys.path`;
the evidence records that setup failure and the successful direct-script reruns.
Historical dated reports/JSON are unchanged. Evaluated main integrates cleanly
into the audit branch; its diff against evaluated main passes whitespace checks.

## 2026-10-17 — #631: iterator-return inference and a remaining loader hole

Evaluated [main `2497bd1f`](https://github.com/den-run-ai/pystachy/commit/2497bd1f64156e1ac9e84e880bfda76b5e5829f6),
merging [#631](https://github.com/den-run-ai/pystachy/pull/631) at 11:22:21 UTC.
This is the only new main merge since `91407759`; ancestry and #491/#616/#631
coordination notes were checked. The six-file diff adds non-generator iterator
return inference, tests and documentation. Runtime, libraries, ports and benchmark
sources are unchanged. [Normalized evidence](compatibility-2026-10-17-iterators.json)
retains all exact probes, commands, results, source/input/compiler hashes and metadata.

Rebuilt with CPython **3.13.16** and LLVM **18.1.3**: bootstrap fixed points are
**620,535 compiler / 18,388 runtime IR lines**. Build and evaluated source are both
`2497bd1f`; compiler SHA-256 is
`bbfa3644306ede2762b5c6a64ec01ccb87e36654e31b8c067408859e30ee711e`.
The prior compiler's retained hash was verified, and all 57 runtime/library source
files used by the old/current comparison are byte-identical.

| Evidence category | Fresh result |
|---|---|
| Focused native suite | **29 passed**: 26 positive JIT/AOT checks with per-allocation GC plus three expected rejections (invalid iterator result, mixed next returns, Any property). Covers inferred/inherited iterator methods, constructor specializations, nested annotations, generator consumers and upstream-derived protocol cases. |
| CPython recordings | All **13 positive programs** match the checked-in recordings. |
| Retained adapted ports | **18 JIT/AOT checks** over nine iniconfig, ordered-set, pyfiglet and tomli-w workloads pass. |
| Differential programs | All **23 CPython references** execute; twelve match in JIT/AOT (**24 checks**). The direct `__next__() -> Any` counter changes from rejection to matching execution. Eleven programs still reject, including the retained structured iterator annotation described below. |
| Isolated loader controls | Six small CPython programs distinguish the remaining bug from working inference. Five execute correctly on current main in both modes (**10 checks**); three also execute correctly on the previous compiler (**six checks**). Original failing forms are checked with both JIT invocation and AOT build. |
| Native import sweep | **142/475**, 47 exclusions, 522-file inventory; every normalized result is unchanged and there are no timeouts. |
| Stub-assisted sweep | **146/475**, including 142 without stubs; every normalized result is unchanged, no timeouts. This remains hosted compiler diagnosis with throwing stand-ins, not native C-module support. |

### Confirmed remaining bug: inferred return needs a helper that was not loaded

The retained program is valid CPython and prints `[1, 2]`:

```python
from typing import Any, Iterator

class Values:
    def __iter__(self) -> Iterator[Any]:
        return iter([1, 2])

print(list(Values()))
```

At `91407759` it stops at the unsupported Any annotation. At `2497bd1f` that
annotation is accepted, but JIT and AOT compilation stop with
`internal error: iter() needs lib/_pystachy_iterators.py (not loaded for this program)`.
This is a **newly exposed acceptance hole**, not evidence that a previously
executing program regressed. The larger merged test also calls `iter()` elsewhere
and therefore does not expose the missing helper.

| Local change to that program | Previous compiler | Current compiler |
|---|---|---|
| Remove the return annotation | Matches CPython in JIT/AOT | Matches CPython in JIT/AOT |
| Use `Iterator[int]` | Matches CPython in JIT/AOT | Matches CPython in JIT/AOT |
| Use plain `Any` as the return annotation | Annotation rejected | Matches CPython in JIT/AOT |
| Keep `Iterator[Any]`, consume with `list(iter(Values()))` | Annotation rejected | Matches CPython in JIT/AOT |

Source inspection explains the interaction: `analysis.reads_builtin` treats an
`Iterator[...]`/`Iterable[...]` return as a special list-stepping path and skips
the inner `iter()` dependency. #631 subsequently erases an Any-containing return
annotation, so lowering now needs an iterator object and its library helper.
These two decisions disagree. Existing [#619](https://github.com/den-run-ai/pystachy/issues/619)
owns this remaining Any-iterator scope; no duplicate issue or implementation
branch change is needed. The minimal reproducer and working controls are retained.

Supported iterator methods need fewer **minor annotation adaptations**, but this
particular structured annotation still needs a local workaround. The new
generator-bodied `__iter__() -> Iterator[Any]` control remains rejected in both
compilers, as the merge deliberately excludes generators. Properties, mixed
iterator returns and the retained generator-send/cache/forwarding-recursion/
dataclass probes retain their documented limits. The four unmodified upstream
packages keep the same first errors: MappingProxyType (tomli-w), missing importlib
on the selected path (pyfiglet), slice(None) (ordered-set), and named Unicode
escapes (iniconfig). Do not infer whole-package acceptance from the adapted tests.

Native unittest/pytest/pyperf and full CPython regrtest are not established by this
merge. No previously passing retained probe was lost. No performance/memory trend
is claimed; unchanged FFI, broad benchmark and full hosted compiler suites were
not rerun. Both audit-tool suites pass again (**10 + 16**).

Reproduction scripts are embedded in the JSON:

```sh
PATH=$LLVM18/bin:$PATH make PY=/root/.local/bin/python3.13
/root/.local/bin/python3.13 build/audit-iterators/evaluate.py
/root/.local/bin/python3.13 build/audit-iterators/loader_probe.py
/root/.local/bin/python3.13 build/audit-iterators/build_evidence.py
```

Environment recovery is explicit: the prior checkout's shared Git object alternate
and LLVM installation expired. A fresh independent clone and scratch-extracted
Ubuntu **18.1.3-1ubuntu1** LLVM packages restored the pinned setup; download origins
and package hashes are retained. A system-package update failed at `setgroups`;
no privilege override or system package installation was used. Four untracked
test files matching main's blobs were preserved before clean branch integration.
These setup failures are not product failures. The audit preserves every earlier
dated report/JSON and changes only this rolling log and the new evidence file.

## 2026-10-17 — #632: item assignment/deletion inference

Evaluated [main `92a33b48`](https://github.com/den-run-ai/pystachy/commit/92a33b481d582f45ea8a8bfbf4f17ccfc9e072ac),
the only first-parent merge since evaluated `2497bd1f`. GitHub confirms
[#632](https://github.com/den-run-ai/pystachy/pull/632) merged at
**2026-10-17 12:47:38 UTC**, and its merge commit is in main's history.
Its six-file diff adds mutation-method tests/docs and changes the compiler's
template-method allowlist. Runtime and all 55 library Python files are unchanged.

Rebuilt from that exact source with **CPython 3.13.16 / LLVM 18.1.3**.
Compiler/runtime fixed points pass: **620,535 / 18,388 IR lines**.
The new compiler SHA-256 is
`9c1567d534ded166bf5de1293dd4d335580bc756c58f1293b99ecde60dbfbeb0`;
the comparison compiler remains the verified `2497bd1f` build
`bbfa3644306ede2762b5c6a64ec01ccb87e36654e31b8c067408859e30ee711e`.
[Normalized evidence](compatibility-2026-10-17-item-methods.json) retains programs,
commands, source/compiler/tool/input hashes, import metadata and raw outcomes.

| Evidence category | Fresh result |
|---|---|
| Focused native checks | **40 pass**: 36 positive JIT/AOT checks with per-allocation program GC and four expected compile rejections. Includes imported/inherited mutation templates, evaluation order, augmented assignment, typed empty values, fixed-storage rejection, existing power methods, ndarray edges and iterator regressions. |
| CPython references | **18/18** selected positive programs match checked-in recordings under CPython 3.13.16. |
| Adapted ports | **22/22** JIT/AOT checks over 11 workloads: iniconfig, ordered-set, pyfiglet, sortedcontainers and tomli-w. Sortedcontainers deletion/index checks are included because of the changed dispatch allowlist. |
| Differential API/boundary programs | All **25** CPython controls pass. **14** programs match CPython in both native modes (28 execution checks); 11 retain explicit compilation blockers. Two newly accepted mutation programs are detailed below. |
| Native isolated imports | **142/475**, 47 overlay exclusions in the unchanged 522-file inventory; no timeout and every normalized module result unchanged. |
| Throwing-stub diagnostic sweep | **146/475**, including 142 without stubs; same inventory/exclusions and every normalized result unchanged. Stub success is not implemented C-module support. |
| Isolated iterator-loader controls | The original structured-return program still fails JIT and AOT compilation with the same missing-helper internal error on both compilers. All five alternate controls match CPython in JIT/AOT on both revisions. |

The two new mutation programs use concrete `dict[str, int]` storage and
`__setitem__`/`__delitem__` parameters annotated Any/object, or left unannotated.
Both previously failed at method annotation validation; both now print
`{'1': 12, 'x': 3}` then `{'x': 3}`, matching CPython in GC-stressed JIT/AOT.
This removes a **minor parameter-annotation adaptation** for supported mutation
methods. It does not make fields/containers dynamically typed: the merged
incompatible-string assignment test still produces its expected rejection.
Properties and other unsupported special methods remain separate limitations.

The [#619](https://github.com/den-run-ai/pystachy/issues/619) iterator-helper bug
from the preceding checkpoint is **not fixed by #632**. Its minimal
`__iter__() -> Iterator[Any]: return iter([1, 2])`, consumed directly by
`list(Values())`, still reaches the internal missing-`_pystachy_iterators`
error. The six full controls are retained again. The implementation owner has
acknowledged this and is preparing a fix in **unmerged #633**; no prospective
fix is counted as supported. No implementation branch was changed.

The four unmodified upstream package probes retain their prior first errors:
tomli-w 1.2.0 (`MappingProxyType`), pyfiglet 1.0.4 (missing `importlib` on the
configured package-only path), ordered-set 4.1.0 (`slice(None)`), and iniconfig
2.3.1 (named Unicode escapes). Passing adapted workloads is not whole-package
acceptance. The retained forwarding recursion, unannotated cache, dataclass Any,
generator-send and generator-bodied Any iterator probes remain rejected.
No previously accepted retained program or import was lost.

Native unittest/pytest/pyperf and full CPython regrtest are not established by
this merge. No performance/memory trend is claimed; broad benchmarks, FFI and
full hosted compiler/upstream suites were not rerun because their implementations
did not change. Both audit-tool suites pass again (**10 + 16**).
Historical reports and JSON are unchanged.

Reproduction scripts are embedded in the new JSON:

```sh
PATH=$LLVM18/bin:$PATH make PY=/root/.local/bin/python3.13
/root/.local/bin/python3.13 build/audit-item-methods/evaluate.py
/root/.local/bin/python3.13 build/audit-item-methods/loader_probe.py
/root/.local/bin/python3.13 build/audit-item-methods/build_evidence.py
```

## 2026-10-17 — #633: generator channels and isolated iterator loading

Evaluated [main `90dcffa1`](https://github.com/den-run-ai/pystachy/commit/90dcffa17d7221e7ab34b32d1ca0752ecd7fcd16),
the only first-parent merge since evaluated `92a33b48`.
[#633](https://github.com/den-run-ai/pystachy/pull/633) merged at
**2026-10-17 14:52:41 UTC**, verified in main's history. The 27-file diff changes
compiler inference/dependency scanning and tests/docs; runtime and all 55 library
Python sources remain byte-identical to the previous compiler's source tree.
Coordination #491/#616 and PR comments were read; no implementation branch was changed.

Rebuilt with **CPython 3.13.16 / LLVM 18.1.3**. Compiler/runtime fixed points pass:
**620,445 / 18,388 IR lines**. The new native compiler SHA-256 is
`bf8f98aa5e8c1b341925c191f7f50e1a1122ca7b58477870344ae2a64e323cab`.
The comparison uses the verified `92a33b48` compiler
`9c1567d534ded166bf5de1293dd4d335580bc756c58f1293b99ecde60dbfbeb0`.
[Normalized evidence](compatibility-2026-10-17-generators.json) retains exact
programs, commands, inputs, source/compiler hashes, metadata and raw outputs.

| Evidence category | Fresh result |
|---|---|
| Focused native checks | **62 pass**: 54 positive JIT/AOT checks with per-allocation program GC and eight expected compile rejections, across 35 files. Covers generator channels, delegation/closing, optional returns, isolated aliases, mutation regression controls and properties. |
| CPython references | **27/27** positive programs match checked-in recordings under CPython 3.13.16. |
| Adapted ports | **22/22** JIT/AOT checks over 11 iniconfig, ordered-set, pyfiglet, sortedcontainers and tomli-w workloads. |
| Adapted benchmark regression | Included in the focused checks: `tests/gen_pyperf.py` matches CPython, traversing a 1,000-item recursive tree three times. This is a bounded adaptation of pyperformance 1.14.0's generators workload, not native pyperf or a new full benchmark census. |
| Differential API programs | All **26** CPython controls pass. **17** programs match CPython in JIT/AOT (34 execution checks); nine remain rejected. Three programs newly execute, listed below. |
| Isolated loader controls | All **six** current programs match CPython in JIT/AOT (12 execution checks). The original fails both compile paths on previous main; its five workarounds pass on both revisions. |
| Type-contract comparison | All **seven** new negative probes receive their expected diagnostics; five compiled on previous main. Three now enforce yield/return contracts, two reject Any-containing send channels at declaration. |
| IR call contracts | Both changed `passes_types`/`tupleiter` snapshots pass compiler IR validation and LLVM assembly. |
| Import sweeps | **142/475 native**, **146/475 with throwing diagnostic stubs**, unchanged 522-file inventory and 47 exclusions. Every normalized result is unchanged; no timeouts. |

### Measured gains and limits

The audit's standalone `__iter__() -> Iterator[Any]: return iter([1, 2])`
reproducer now prints `[1, 2]` in both native modes. It no longer needs an
extra outer `iter()` or removal of the return annotation. Separate merged
tests also verify quoted/aliased and nested-alias forms without another call
masking the dependency. This independently confirms the
[#619](https://github.com/den-run-ai/pystachy/issues/619) loader fix.

Three differential programs change from rejection to matching execution:

- The retained non-generator structured Any iterator return.
- The retained generator-bodied `__iter__() -> Iterator[Any]`.
- A `Generator[Any, str | None, int]` delegated through `yield from`, which
  preserves its string send channel and integer return while inferring yields.

The broader positive generator recording also checks Any return inference,
nested annotations, initialized generator variables and optional returns.
This removes localized annotation workarounds for these native programs.
**Any send remains unsupported**: the retained send probe now gives an actionable
declaration error, rather than silently losing its annotation and failing later.
Properties, annotation-only variables, dataclass Any, cache inference, forwarding
recursion and heterogeneous storage retain their separate limits.

The five newly rejected negative controls are intentional contract enforcement,
not losses among the positive API probes. Previous main accepted a wrong string
yield despite an integer yield annotation, a wrong string return despite an
integer return annotation, a value return from `Iterator[Any]`, and direct/nested
Any send declarations. Current main rejects all five precisely. No retained
positive execution or successful import regressed.

The helper is now loaded conservatively even for some concrete iterator returns.
The two changed IR snapshots include `pys_eh_on` in main; their other call
sequences still satisfy the checked-in contracts. No timing/memory trend is
inferred from this static change or the correctness runs.

The four unmodified upstream package probes still stop at their prior first
errors: tomli-w 1.2.0 `MappingProxyType`, pyfiglet 1.0.4 missing `importlib`
on its configured package-only path, ordered-set 4.1.0 `slice(None)`, and
iniconfig 2.3.1 named Unicode escapes. These first errors can hide later blockers.
The adapted workloads and native language gains do not establish whole-package
acceptance. Native unittest/pytest/pyperf and full CPython regrtest remain
unestablished; broad upstream/FFI/performance suites were not rerun.
Both audit-tool suites pass again (**10 + 16**). Historical reports/JSON are preserved.

Reproduction scripts are embedded in the evidence:

```sh
PATH=$LLVM18/bin:$PATH make PY=/root/.local/bin/python3.13
/root/.local/bin/python3.13 build/audit-generators/evaluate.py
/root/.local/bin/python3.13 build/audit-generators/loader_probe.py
/root/.local/bin/python3.13 build/audit-generators/contracts_probe.py
/root/.local/bin/python3.13 build/audit-generators/build_evidence.py
```

## 2026-10-17 — #634: recursive operand diagnostics, not new inference

Evaluated [main `63977813`](https://github.com/den-run-ai/pystachy/commit/6397781363e6edea98c61d294a2425eb4df05cc3),
which merges [#634](https://github.com/den-run-ai/pystachy/pull/634) at
2026-10-17 16:21:57 UTC. This is the only first-parent merge since evaluated
`90dcffa1`; its ancestry in main was verified. The 14-file diff changes four
compiler files, language documentation and recursion tests; runtime, library
and port implementations are unchanged. Read #491/#616 coordination, #621/#595
and #634 comments before testing. The review bot's failure banner accompanies
a usage-limit error; the fresh review-thread response is empty. The four
exact-head implementation workflows succeeded; this is separate from the
audit PR's fresh checks.

Rebuilt with **CPython 3.13.16 / LLVM 18.1.3**. Compiler and runtime bootstrap
fixed points pass at **620,602 / 18,388 IR lines**. Compiler SHA-256:
`e208cae457917e7c4ea6ce2a56fb6b5af44469b58a9c4fad00786bbbad4db725`.
The previous compiler is the independently hashed `90dcffa1` build.
[Normalized evidence](compatibility-2026-10-17-recursion.json) preserves exact
programs, commands, input/tool/compiler hashes, import metadata, diagnostics
and reproduction scripts. All evaluation commands completed successfully.

| Evidence category | Fresh result |
|---|---|
| Focused native checks | **77 pass** across 58 files: 38 positive JIT/AOT executions under per-allocation program GC, plus 39 expected compile rejections. Includes direct/mutual recursion, valid void results, explicit return contracts, Any diagnostics, mutation and isolated iterator/generator regressions. |
| CPython references | **19/19** positive programs match their checked-in recordings under CPython 3.13.16. |
| Adapted ports | **28/28** JIT/AOT checks across 14 workloads in iniconfig, ordered-set, pyfiglet, sortedcontainers, tomli-w and pylev. The pylev controls include recursive distance, typed sequence and memo behavior. |
| Retained differential programs | All **26** CPython controls pass; the same **17** programs match in JIT/AOT (34 execution checks). All nine remaining programs still reject; no acceptance status changes. |
| Recursion boundary comparisons | **12 programs** compared with CPython and both compiler revisions. Four direct-operand errors improve; two real None errors stay accurate; three alias/forwarding cases remain rejected; three annotated controls match CPython in JIT/AOT on both revisions. |
| Import sweeps | **142/475 native**, **146/475 with throwing diagnostic stubs** (142 need no stubs), same 522-file inventory and 47 overlay exclusions. Every normalized result is unchanged; no timeout. |

### What changed, and what still needs adaptation

Four rejected programs now name the unresolved recursive return and ask for a
return annotation: unannotated direct multiplication, Any direct multiplication,
Any mutual recursion and Any unary negation. Each runs successfully in CPython;
each still requires adaptation for native execution. **This is diagnostic
progress, not four newly compatible programs or a new inference algorithm.**

Local aliases and completed forwarding helpers still produce the old
`int * NoneType` diagnostic. The boundary controls independently reproduce
both shapes; adding `-> int` makes both match CPython on both revisions.
The valid base-case-first, concrete-return, void-recursion and operator-accepting-None
cases in `tests/any_recursion.py` also match CPython. Explicit-None and unrelated
None negative controls correctly retain ordinary operand errors; CPython itself
raises TypeError for those two programs.

[#595](https://github.com/den-run-ai/pystachy/issues/595)'s list forwarding
regression remains rejected, and the separate dictionary variant is also still
rejected. Concrete `list[int]` / `dict[int, int]` return annotations restore the
selected calls in JIT/AOT. These are minor localized workarounds for the measured
programs, not a general solution for recursive or heterogeneous values.
[#621](https://github.com/den-run-ai/pystachy/issues/621) retains the alias/forwarded
diagnostic scope; neither existing issue is closed by this audit.

The #633 loader and generator-channel gains, #632 mutation cases and earlier
Any constructor/variable/signature cases remain passing. Cache inference,
annotation-only variables, dataclass Any and Any send retain their separate
limits. The four unmodified upstream package first errors are unchanged:
tomli-w 1.2.0 `MappingProxyType`, pyfiglet 1.0.4 missing `importlib` on its
configured package-only path, ordered-set 4.1.0 `slice(None)`, and iniconfig 2.3.1
named Unicode escapes. These first errors can hide additional failures.

No retained positive execution or import regressed, and no new uncovered bug was
confirmed. The adapted pyperformance generator tree walk is included among the
positive checks; this is not a new full benchmark census. Native
unittest/pytest/pyperf, general native NumPy/PyPI acceptance and full CPython
regrtest remain unestablished. Broad FFI/upstream suites and timing/memory
measurements were not repeated for this diagnostic-only behavior change.
Both audit-tool suites pass (**10 + 16**). Historical reports and JSON are unchanged.

```sh
PATH=$LLVM18/bin:$PATH make PY=/root/.local/bin/python3.13
/root/.local/bin/python3.13 build/audit-recursion/evaluate.py
/root/.local/bin/python3.13 build/audit-recursion/boundaries.py
/root/.local/bin/python3.13 build/audit-recursion/build_evidence.py
```

## 2026-10-18 — #657: faster list repetition, preserved compatibility

Evaluated [main `3f6f42c7`](https://github.com/den-run-ai/pystachy/commit/3f6f42c7648b952940ca806fc711d59314ee381a),
which merges [#657](https://github.com/den-run-ai/pystachy/pull/657) at
2026-10-18 03:36:49 UTC (October 17 in America/Los_Angeles).
The only preceding merge since evaluated `63977813` is the audit itself,
[#635](https://github.com/den-run-ai/pystachy/pull/635), whose merged tree equals
the already tested publication. No implementation gain is attributed to that merge.
#657 changes `runtime.c` plus one recorded regression test: list repetition
copies a doubling prefix, and a new one-element zero-bit pattern needs no fill.
Ancestry was verified; #491/#616 coordination and #657 comments were read.
The fresh review-thread list is empty; the bot failure banner accompanies a
review quota error, not a retrieved code finding.

[Normalized evidence](compatibility-2026-10-18-list-repeat.json) retains source
and compiler revisions separately, hashes, programs, commands, import metadata,
CPython stdlib file hashes, paired samples and reproduction scripts.
CPython **3.13.16** was restored after its previous installation expired; its
binary hash is identical to the previous audit. With LLVM **18.1.3**, the fresh
bootstrap fixed points pass at **620,602 compiler / 18,388 runtime IR lines**.
Compiler SHA-256:
`66cd62d0a803e0a1d21c50b83e3e0043068c295e10560905e78284470bd6d6f4`.
The previous compiler is the verified `63977813` build; 231 compiler/Python
runtime/library/port/example/microGPT source files are byte-identical.

| Evidence category | Fresh result |
|---|---|
| Focused native correctness | **22/22** normal JIT/AOT checks over 11 list/storage/ndarray programs. |
| Per-allocation program GC | **6/6** checks for repetition, allocation kinds and ndarray edges. |
| Adapted ports | **14/14** JIT/AOT checks over seven pylev, pyaes, qrcode and sortedcontainers workloads. |
| CPython reference recordings | All **18** selected focused/port programs match their recordings. |
| Prior-runtime control | The new repetition program also passes JIT/AOT on the previous runtime: **2/2**, preserving behavior rather than adding API acceptance. |
| Allocation/runtime contracts | `listprobe` passes normally and with GC stress; all **430** runtime entry contracts agree. |
| Adapted microGPT | Original/adapted CPython and native JIT/AOT verify ten steps, 73 training tokens and three generated names: **58,698 numeric comparisons per run**, including every gradient; maximum AOT absolute difference `8.47e-22`. |
| Isolated imports | **142/475 native**, **146/475 stub-assisted**, same 522-file inventory and 47 exclusions. Every normalized result is unchanged; no timeout. |

The repetition test covers signed zero, NaN/infinities, integer bounds,
non-power-of-two counts, reused nonzero storage, shared object/nested-list
references, aliases, zero/negative/empty counts and MemoryError boundaries.
The three ndarray programs retain their recorded subset behavior; this remains
a native float64 example, not general native NumPy. The microGPT run is a
correctness check under concurrent audit load; its single-sample phase timings
do **not** establish a training speedup or regression.

### Paired performance: strong improvement, workload-dependent CPython comparison

After correctness jobs completed, both runtimes and CPython ran on CPU 0 in
seven alternating-order process rounds. Inputs are `n=8192` and 2,000 allocations
per pattern. Checksums match in every sample. Raw samples and load are retained;
these shared-host observations are not universal performance guarantees.

The **exact source from [#649](https://github.com/den-run-ai/pystachy/issues/649)**
uses best-of-five wall times within each process. Medians of seven processes,
nanoseconds per output item:

| Exact issue workload | Previous AOT | Current AOT | CPython 3.13.16 |
|---|---:|---:|---:|
| `[0.0] * n` | 3.85 | 0.36 | 0.95 |
| `[1.5] * n` | 3.73 | 0.58 | 0.91 |
| `[0.0, 1.0] * (n // 2)` | 2.17 | 0.56 | 1.28 |

This independently reproduces #649's acceptance criterion for those exact loops:
approximately **3.9–10.7× faster** than previous AOT and below CPython.

A separate **function-scoped** loop, with 100 warmups and one timed 2,000-iteration
body per process, measures process CPU time rather than selecting the best wall
sample. It improves substantially, but is not below CPython in every median:

| Function-scoped workload | Previous AOT ns/item | Current AOT ns/item | CPython ns/item | Median paired current/previous CPU |
|---|---:|---:|---:|---:|
| Zero singleton | 5.08 | 1.58 | 0.93 | 0.308 |
| Nonzero singleton | 4.97 | 1.56 | 1.09 | 0.324 |
| Two-item pattern | 3.17 | 1.64 | 1.32 | 0.496 |
| In-place singleton | 5.10 | 1.54 | 0.97 | 0.295 |
| In-place two-item pattern | 3.54 | 1.53 | 1.48 | 0.446 |

These variants use about **50–70% less paired CPU time**, without establishing
CPython parity for every allocation/lifetime/timing configuration. Large outliers
remain (current zero-fill: 1.18–11.62 ns/item). Scope and timing method differ;
no cause for that difference or regression is inferred from the cross-comparison.
The exact issue acceptance is confirmed, but broader performance claims must
stay qualified. No RSS trend or unmerged nanoGPT speed result is claimed.

No retained correctness/import regression or new uncovered bug was confirmed.
Import compilation, executed APIs, adapted ports and hosted upstream references
remain separate. Full CPython regrtest, broad PyPI compatibility, native test
runners and general native NumPy were not evaluated by this update. Unchanged
inference/Unicode/cache/encoding gaps were not individually rerun.
Both audit-tool suites pass (**10 + 16**). Evidence records the initial missing
Python bootstrap attempt and unavailable optional `/usr/bin/time` wrapper;
restoration and a full timing restart succeeded. Final timings use in-program
CPU/wall clocks, not the absent wrapper. Historical reports/JSON are preserved.

Reproduction scripts are embedded in the evidence. Restore the pinned names
dataset from its retained URL/hash before the microGPT check.

```sh
uv python install 3.13.16 --install-dir /workspace/scratch/3ba735e28fa7/python-audit-31316
PATH=$LLVM18/bin:$PATH make PY=/root/.local/bin/python3.13
/root/.local/bin/python3.13 build/audit-list-repeat/evaluate.py
/root/.local/bin/python3.13 build/audit-list-repeat/performance.py
/root/.local/bin/python3.13 build/audit-list-repeat/exact_benchmark.py
/root/.local/bin/python3.13 build/audit-list-repeat/build_evidence.py
```

## 2026-10-18 — #641/#642: native adapted nanoGPT inference and training

Evaluated [main `43fb4007`](https://github.com/den-run-ai/pystachy/commit/43fb4007320c8bf2851e7cfcb6f32d66dc637fef),
after measured `3f6f42c7`. This covers [#641](https://github.com/den-run-ai/pystachy/pull/641)
(inference, merged 04:04:22 UTC as `1055a65f`) and
[#642](https://github.com/den-run-ai/pystachy/pull/642)
(backward/AdamW, merged 04:05:56 UTC as `43fb4007`).
Intervening [#662](https://github.com/den-run-ai/pystachy/pull/662) changes only README;
no implementation gain is attributed to it. All merge ancestors were verified.
Read #491/#616 coordination and both PR discussions before evaluation.

These merges add example code, tests, an offline checker and documentation,
not compiler/runtime/library implementations. Reused the verified compiler built
at `3f6f42c7`, SHA-256
`66cd62d0a803e0a1d21c50b83e3e0043068c295e10560905e78284470bd6d6f4`.
Compiler/runtime/lib/port Python sources, ndarray and import tooling are unchanged
(the ports notice gains attribution). Source revision and compiler build revision
are deliberately separate.

[Normalized evidence](compatibility-2026-10-18-nanogpt.json) retains both checkpoints,
commands, source/input/compiler/library hashes, fresh references, comparison
counts/errors, raw timing samples and reproduction scripts. Large deterministic
reference vectors are represented by hashes and exact export instructions.
Inputs: **CPython 3.13.16, LLVM 18.1.3, PyTorch 2.14.1+cpu**, pinned upstream nanoGPT
`3adf61e154c3fe3fca428ad6bc3818b27a3b8291` (`model.py` SHA-256
`7c01703240dbec5d554527dc666e35b3df8391d0b117fddc07afcf325a21d11c`).
PyTorch exports were freshly generated at both checkpoints, with one CPU thread,
float64, dropout zero, fixed seeds, one warmup and three inference repeats.
The optional native BLAS path uses this host's reference LP64
`/lib/x86_64-linux-gnu/libblas.so.3`, not the optimized OpenBLAS provider in
the example's historical performance table.

| Fresh evidence | #641 checkpoint | #642 checkpoint |
|---|---|---|
| Native recorded regression checks | **8/8** JIT/AOT over nanoGPT and three ndarray programs | **10/10**, adding training |
| Per-allocation program GC regression checks | **2/2** nanoGPT JIT/AOT | **4/4** inference + training |
| Fresh CPython recordings | **4/4** match | **5/5** match |
| Hosted checker contract tests | **7/7** | **7/7** |
| Upstream-reference parity, normal | **15/15** case/tier comparisons; **1,965** numeric comparisons | **15/15**; **405,185** numeric comparisons |
| Upstream-reference parity, program GC every allocation | Same **15/15**, **1,965** | Same **15/15**, **405,185** |
| Maximum absolute parity error, either GC setting | `8.33e-17` | `3.74e-15` |

Each parity run covers three models (one-token, batched bias, batched no-bias)
and five tiers: scalar CPython, scalar JIT/AOT and BLAS JIT/AOT. Thus 12 of the
15 comparisons per setting are native; the three CPython runs are hosted
controls, not extra native coverage. Each model/tier has 27/229/137 numerical
inference values at #641 and 9,343/37,331/34,363 values with training at #642.
Training models contain 1,032 / 4,080 / 3,780 unique parameters. Two successive
steps compare **every gradient, updated parameter and both Adam moments**,
as well as logits/loss and all-ignored-target zero gradients.
The normal regression separately checks directional finite differences across
every parameter, tied embeddings, causality/batch isolation and malformed inputs.
Four CPython CLI controls and **eight native CLI comparisons** also pass for
scalar/BLAS, full/last logits and loss. Those CLI/model sources are unchanged by #642.

### Compatibility gain and boundaries

This is a substantial new **adapted native workload**, not a new unmodified
PyPI import. Standalone execution of the CPU FP64 transformer now supports
inference, model-specific analytic backward and AdamW without embedding
CPython or loading NumPy/PyTorch. Only the offline exporter/oracle needs PyTorch;
the optional native BLAS runner needs the explicitly selected LP64 library.

Upstream nanoGPT still requires **major adaptation**: typed ndarray operations
and explicit backward replace the dynamic PyTorch model/runtime. This is not
general tensor autodiff, native PyTorch/NumPy compatibility, GPU/AMP/DDP,
dropout, the original data pipeline or direct `.pt` checkpoint loading.
Two random-model updates do not establish training convergence or long-run
throughput. Existing ndarray dtype/indexing/ownership gaps remain in
[#582](https://github.com/den-run-ai/pystachy/issues/582) and its linked issues.

No correctness regression or new uncovered implementation bug was confirmed.
The historical larger-model performance table in #642 was **not rerun**:
this audit's tiny, concurrently executed checks (including GC stress) are not
valid speedup/regression evidence. No memory trend is claimed.
The initial audit selection named a nonexistent BLAS test and was corrected;
an optional every-allocation *compiler* GC attempt was interrupted during
compilation. Successful retries use compiler interval 1000 and program interval
1. Both incomplete attempts remain explicit in the evidence.

Native stdlib imports remain the **last measured 142/475**, or **146/475** with
throwing stubs, at `3f6f42c7`; these unchanged inputs were **not reswept**.
Broad port suites, unchanged Unicode/inference/cache gaps, native unittest/pytest/
pyperf and full CPython regrtest were not rerun. No broader library acceptance
is inferred from the new model example.

Reproduce at each retained checkpoint with LLVM 18 on PATH, using the pinned
upstream file and a PyTorch 2.14.1+cpu environment:

```sh
python3.13 tools/check_nanogpt.py --upstream-model UPSTREAM/model.py \
  --torch-python TORCH_ENV/bin/python --export-only build/audit-nanogpt/fixtures \
  --warmups 1 --repeats 3
python3.13 tools/check_nanogpt.py --fixtures build/audit-nanogpt/fixtures \
  --compiler COMPILER --python PY --blas-library /lib/x86_64-linux-gnu/libblas.so.3 \
  --warmups 1 --repeats 3 --json build/audit-nanogpt/parity.json
# #642 defaults to two training steps; #641 is inference-only.
# For GC, set PYSTACHY_GC_STRESS_PROGRAM=1 and PYSTACHY_GC_STRESS=1,
# and use --compiler "env PYSTACHY_GC_STRESS=1000 COMPILER".
```

## 2026-10-18 — #658: large pointer-free allocation budget

Evaluated [main `0e6392b2`](https://github.com/den-run-ai/pystachy/commit/0e6392b22217cc84baf5ece6d51203cfdfe6f71c),
merging [#658](https://github.com/den-run-ai/pystachy/pull/658).
Since the previous evaluated `43fb4007`, #664 and #666 changed onboarding/docs
and the PR template; #663 merged the audit itself. Those documentation-only
changes are accounted for but do not imply compatibility improvements.
Only #658 changes runtime behavior; its other changes register/document the
deterministic allocation probes. No implementation branch was modified.

[Normalized evidence](compatibility-2026-10-18-gc-budget.json) retains commands,
selected programs, source/tool/input hashes, full per-module import results,
model comparisons, C probe source, three fresh processes per allocation case,
and the deliberately defective scratch-only negative control.
Toolchain: **CPython 3.13.16**, **LLVM 18.1.3**, Linux x86-64.
The compiler was rebuilt from `0e6392b22217cc84baf5ece6d51203cfdfe6f71c`;
compiler/runtime fixed points match at **620,602 / 18,388** IR lines.
Compiler SHA-256:
`8ad34ce1b632dfaa0d5e251dfed4eda6c5f3bff018366e83191306cb31eaadd8`.

### Compatibility and correctness

| Check | Fresh result |
|---|---|
| Selected list/string/GC/ndarray/nanoGPT regressions | **40/40** native JIT/AOT checks across 20 programs. |
| Same selection, program GC every allocation | **40/40**, compiler GC interval 1000. |
| Adapted ports | **14/14** JIT/AOT checks over seven iniconfig, pyaes, pyfiglet and sortedcontainers workloads. |
| Fresh CPython references | All **27/27** selected recordings match, including expected exceptions. |
| Allocation/container/file probes | `listprobe`, `dictprobe`, `eqprobe`, `fileprobe` pass with their normal/stress controls; **430** runtime contracts and **70** exception classes agree. File buffers still collect four times with at most **35,971,072** outstanding bytes in the normal controls. |
| Isolated native imports | **142/475**; same 522-file inventory and 47 overlay exclusions. All input hashes and normalized results unchanged; no timeout. |
| Throwing-stub import diagnosis | **146/475**, 142 needing no stub; every normalized result unchanged, no timeout. This sweep uses the CPython-hosted compiler, not a native C-module implementation. |
| Adapted regex benchmark correctness | `regex_dna`, `regex_effbot`, `regex_v8` all match CPython in JIT/AOT at retained smoke inputs. |
| Adapted microGPT | Ten steps, 73 training tokens, three samples, all-gradient checks pass against the original/adapted CPython references. |
| Adapted nanoGPT | Three retained models × five tiers pass normally and under program GC every allocation: **405,185 numeric comparisons per setting**, max absolute error **3.74e-15**. |

NanoGPT includes every gradient, two AdamW updates, updated parameters and both
moment vectors. Of its 15 case/tier comparisons per setting, 12 are native
scalar/BLAS JIT/AOT and three are hosted scalar CPython controls. The exact
previously exported PyTorch **2.14.1+cpu** fixtures are reused and hashed, not
claimed as newly exported. Upstream remains pinned to nanoGPT `3adf61e`;
BLAS is the same LP64 reference `/lib/x86_64-linux-gnu/libblas.so.3`.
These CPU FP64, dropout-free adapted models are not unmodified PyTorch/NumPy
or general autodiff support.

### Deterministic memory improvement and regression controls

The independent C probe compares the previous runtime (source `3f6f42c7`,
byte-identical through pre-merge `cbac6787`) with the merged runtime. Each case
runs in three fresh processes; all three observations agree.

| Allocation workload | Collections before → after | Peak managed heap before → after |
|---|---:|---:|
| Drop 512 numeric arrays of 8,192 items | 1 → **8** | 36,700,032 → **5,517,312 bytes** (35.0 → 5.26 MiB; about 85% less) |
| Same churn with 128 such arrays retained (8 MiB item data) | 1 → **3** | 45,629,312 → **19,050,752 bytes** (43.52 → 18.17 MiB) |
| 48 MiB of small atomic objects | 1 → 1 | 34,738,176 → 34,738,176 bytes |
| 40 MiB mixed: 64 KiB numeric array per 192 KiB small objects | 1 → 1 | 35,246,080 → 35,246,080 bytes |
| Drop 512 pointer-bearing arrays of 8,192 items | 1 → 1 | 36,700,032 → 36,700,032 bytes |

The trade-off is intentional: collect more often around cheap-to-scan numeric
storage to reduce peak managed heap. These numbers are **not RSS** or whole-model
peak memory, and no fresh throughput/speedup claim is made. GC-disabled numeric
churn remains at zero collections and 36,769,792 heap bytes in both runtimes.

The review's candidate-accounting bug is independently confirmed **fixed**:
a 5 MiB scanned allocation on an empty heap and 3 MiB atomic + 2 MiB scanned
history each cause **zero** collections on merged main, as before #658.
Restoring only the defective `gc_big + n` formula in a scratch copy makes
each cause **one** collection. Positive controls also pass: a 5 MiB atomic
candidate now collects once, and a 32 MiB scanned candidate still collects once.
The shipped list probe independently passes its lifetime, allocation-kind,
live-set and budget assertions under normal and stress settings.

No retained correctness regression or new uncovered bug was found.
[#650](https://github.com/den-run-ai/pystachy/issues/650)'s small-object tuning
and [#591](https://github.com/den-run-ai/pystachy/issues/591)'s small-string
concerns are not resolved by this large-object policy.
The minor/major adaptation assessments remain unchanged. Dynamic library
loading/object-model gaps, Unicode/UTF16, cache inference, broad unmodified
PyPI suites and full CPython regrtest were not reevaluated by this focused
runtime audit. Import acceptance remains a first-error/IR metric, not proof
that all APIs in those modules execute correctly.

Reproduction: the JSON embeds `evaluate.py`, `budget_probe.c` and
`budgets.py`; run them at the recorded source with LLVM 18 on PATH after
`make PY=python3.13`. Both import sweeps use `--metadata`, the same
CPython installation and overlay. Model commands retain exact input paths/hashes;
recreate the prior fixture export using the preceding checkpoint if needed.
Short concurrent timings are retained only as diagnostics.
This was a focused audit, **not** another full local `make verify`.
The four implementation-head workflows were independently observed successful
at `e712e091`; follow-up audit PR checks are a separate publication gate.

## 2026-10-19 — #644/#645/#646/#648: builtin-module prototypes

Evaluated [main `2359de69`](https://github.com/den-run-ai/pystachy/commit/2359de695e2668a6b9d72519d195680ee0661c38).
Its first-parent merges after [`a355c83f`](https://github.com/den-run-ai/pystachy/commit/a355c83ff7b60b64e3264867593064c3da9611a5)
are [#644](https://github.com/den-run-ai/pystachy/pull/644) (`_imp`),
[#645](https://github.com/den-run-ai/pystachy/pull/645) (`_ast`),
[#646](https://github.com/den-run-ai/pystachy/pull/646) (`select`),
[#648](https://github.com/den-run-ai/pystachy/pull/648) (`_weakref`) and the CI-only
[#677](https://github.com/den-run-ai/pystachy/pull/677). Both import sweeps were rerun
at `a355c83f` with the same input, so each change is attributed to the four merges.
[#678](https://github.com/den-run-ai/pystachy/pull/678)'s head `8eda0b87` gives the
same result as main in every check. Main has since moved to `83b5835c`, adding the
docs-only [#675](https://github.com/den-run-ai/pystachy/pull/675). The [report](compatibility-2026-10-19-prototypes.md)
has the tables, blockers and caveats. The [evidence](compatibility-2026-10-19-prototypes.json)
has the commands, hashes, per-module results and scripts. Toolchain: CPython 3.13.16,
LLVM 18.1.3, Linux x86-64.

| Check | Result |
|---|---|
| Native imports | **144/475**, up from 142 at `3f6f42c7` and `a355c83f`. `_py_abc` and `_weakrefset` are new; none lost. 165 first errors move. The inventory is 522 files with 47 exclusions; 521 sources are byte-identical to the previous sweep's, and `ssl.py` is upstream's. |
| Stub-assisted imports | **146/475**, 2 needing stubs (was 4). 99 now stop at `weakref.py:12`, where six `_weakref` names are missing. A diagnostic stubbing those names unlocks no import. |
| 27 package probes | Every first error is as on 2026-10-17. With the CPython stdlib overlay, a new configuration, 14 probes then stop in the stdlib or a C extension, and sortedcontainers in its own Python 2 branch. |
| Harness probes | pyperf now stops at `_contextvars`, the pyperformance CLI at `_io`, and pytest, unittest and unmodified `test_fnmatch.py` at `_opcode`. |
| pyperformance | The census stays at **6/52**. With the stdlib overlay, `weakref.py:12` stops 6 benchmarks. |
| Compiled upstream tests | `tests/upstream_{weakref,select,ast}.py`: 15 CPython test methods, 6 of them complete. They pass in JIT and AOT, with GC stress and with optimizations off. |

Native blockers now:

| First error | Modules |
|---|---:|
| `weakref.py:12` | 54 |
| `_io` | 34 |
| `_signal` | 26 |
| `_opcode` | 24 |
| `email/charset.py:99`, a dict of `None` values | 16 |

With the C modules stubbed, subset patterns lead:

| First error | Modules |
|---|---:|
| `socket.py:53` ([#611](https://github.com/den-run-ai/pystachy/issues/611)) | 68 |
| `inspect.py:1725` ([#256](https://github.com/den-run-ai/pystachy/issues/256)) | 42 |
| `enum.py:1412` ([#610](https://github.com/den-run-ai/pystachy/issues/610)) | 13 |

Not run: full `make verify` on the audit head, CPython regrtest and timings.

## Checks to run when the pending work lands

These are impact targets, not assertions that the PR will make the whole module
or package work. Combine consecutive relevant merges into one measured revision
when practical, preserving attribution and the previous result.

| Pending work | Focused remeasurement |
|---|---|
| #619 remaining property inference | Retained property rejection; keep the now-passing #633 isolated iterator and generator-channel programs as regression controls. |
| #621 / #595 remaining recursion gaps | Keep the now-verified #634 direct-operand diagnostics distinct from alias/forwarded-result diagnostics and recursive inference. Retain annotated controls, #632 mutation and #633 generator regressions. |
| Further ndarray/nanoGPT/interop work after #583/#609/#640/#170 | Example/FFI checks, adapted inference/training correctness and explicit interop calls. Classify standalone compiled arrays and embedded CPython separately from native NumPy/PyPI compatibility. |
| Other compiler/runtime/library/port/test-tool merges | Read the actual changed files and run the matching retained probes. Documentation-only merges do not require another compiler build or unchanged sweep. |

## Recording rules

- Verify the event's PR is merged into the main history and read current main;
  overlapping events may refer to the same already-evaluated source state.
- Compare file changes before choosing tests. Rebuild the compiler when its
  sources/runtime change; retain compiler-file hash, source SHA and toolchain.
- Use `tools/import_sweep.py --metadata` when repeating imports. Keep the same
  CPython version, module inventory and overlay, or explain the denominator change.
- Keep import IR, executed JIT/AOT APIs, adapted programs, upstream tests hosted
  by CPython, and actual compiled upstream suites as separate evidence categories.
- Add compact result deltas and links to normalized evidence. Include failures,
  timeouts, newly exposed blockers and regressions; retain exact reproduction
  commands and relevant existing issue owners. Single noisy timing samples are
  not regression measurements.
- Update the open audit PR with findings. After it merges, use a small follow-up
  PR for material changes. Do not edit another session's implementation branch or
  merge its PR as part of the audit. Read its current coordination notes first
  when a finding overlaps active work.
- If no relevant source or measured outcome changed, avoid another commit or
  repeated no-change comment. Keep the latest *evaluated* SHA distinct from a
  newer revision whose evaluation is blocked or incomplete.

## 2026-10-18 — #647: folded BLAS bias, safety cases and hosted NumPy baseline

Evaluated [main `6d4ed3d1`](https://github.com/den-run-ai/pystachy/commit/6d4ed3d1171ad76c1f3a0377654c30deaa1b79d6),
which merges [#647](https://github.com/den-run-ai/pystachy/pull/647) at
**2026-10-18 05:37:44 UTC**. Fresh PR metadata and git ancestry confirm the merge;
it is the only first-parent merge since evaluated `0e6392b2`. Read #491/#616 and
the implementation review before testing. The 20-file diff changes example,
checker, setup and CI files. Compiler/runtime/lib/ports implementation sources
are byte-identical to `0e6392b2`, so the verified compiler built at that revision
is reused (SHA-256 `8ad34ce1b632dfaa0d5e251dfed4eda6c5f3bff018366e83191306cb31eaadd8`).
The compiler source remains `0e6392b2`; evaluated example/tool source is `6d4ed3d1`.
`PYSTACHY_HOME` explicitly points to the evaluated checkout.

[Machine-readable evidence](compatibility-2026-10-18-blas-fold.json) retains
commands, outputs, driver source, changed-file and fixture hashes, provider
identity, reference provenance, tolerances and comparison counts. Toolchain:
CPython **3.13.16**, LLVM **18.1.3**, Linux x86-64; isolated hosted reference
environment with **NumPy 2.3.5 / SciPy 1.16.3**. Actual native calls resolve to
`/usr/lib/x86_64-linux-gnu/blas/libblas.so.3.12.0`, Ubuntu package
`libblas3:amd64 3.12.0-3build1.1`, explicit **LP64** ABI. NumPy's wheel BLAS is a
separate hosted reference provider, not the library used by Pystachy's FFI.

| Fresh check | Result / scope |
|---|---|
| BLAS views, aliases, storage bounds and folded bias | **24 matrix + 15 linear + 32 expected-rejection cases per tier**, all pass in CPython twin, JIT, AOT, per-allocation JIT GC and AOT GC. Maximum absolute error against independent NumPy interpretation: **3.55e-15**. |
| End-to-end `make blas-check` | Passes; repeats the preceding case checker and runs nanoGPT folded/unfolded/scalar parity in all five tiers. **4,022 values per tier**, exact agreement on these fixtures. Includes full/last logits, training loss and every gradient, with and without bias. Do not double-count the repeated case checker as new coverage. |
| Retained PyTorch-reference nanoGPT fixtures | All **15 case/tier runs** pass normally and all **15** in the GC configuration: **405,185 numeric comparisons in each configuration**, max error **3.738329090730019e-15**. Each configuration includes 12 native and 3 hosted runs. All gradients, two AdamW updates and both moment vectors remain checked. |
| New CPython NumPy inference baseline | All three retained cases pass: **27 / 229 / 137 values** for one-token / batched-bias / batched-no-bias; maximum error **4.44e-16** against retained PyTorch references. SciPy supplies exact GELU `erf`. Hosted reference only. |
| Checker contract tests | **8/8** pass, including AST checks that every generated BLAS forward/training call passes the folded-linear backend and scalar calls do not. |

The retained fixture manifest and full reference contents are identical to the
previous audit, including weights/input hashes. References were generated with
PyTorch **2.14.1+cpu** from upstream nanoGPT
`3adf61e154c3fe3fca428ad6bc3818b27a3b8291`; they were **not freshly exported** here.
The full checker uses one warmup, three repeats and two training steps. Its GC
run uses compiler interval 1000 and program/AOT interval 1. The standalone BLAS
checker and make target use program/AOT interval 1.

### Functional delta and safety boundary

`ndarray_blas.linear(x, weight, bias)` now computes `x @ weight.T + bias` with
one `cblas_dgemm` call and `beta=1`, starting with repeated bias storage. The
nanoGPT BLAS runner selects it via an optional trailing backend argument;
existing scalar callers remain valid. This is a **minor integration change for
the already-adapted example**, not reduced adaptation of upstream NumPy or
PyTorch: those packages still require their existing major native adaptations
or explicit CPython hosting.

The pre-merge review found an undersized-bias storage hazard. The merged code
validates rank/stride count, offset and reachable storage extent before reading
the bias or invoking BLAS. Fresh checks reject short storage, missing/extra
strides, negative/past-end offsets, overflowing positive/negative extents and
malformed empty-product biases; valid reversed, broadcast and singleton-stride
bias views still pass. No unsafe pre-fix native call was executed. No new
uncovered bug or retained correctness regression was found, so no duplicate
issue was filed and no unrelated issue was closed.

### Commands, limitations and CI

Run the retained JSON's `test_driver` from the evaluated checkout; its absolute
compiler/LLVM/fixture paths identify the inputs and can be relocated together.
The principal commands are `make blas-check PY=<isolated-python>
BENCH_COMPILER=<verified-compiler>`, `examples/ndarray/check_blas.py --stress 1
--compiler <verified-compiler> --json <output>`, `tools/check_nanogpt.py --fixtures
<retained-fixtures> --blas-library /lib/x86_64-linux-gnu/libblas.so.3 --warmups 1
--repeats 3 --compiler <verified-compiler> --json <output>` (normal and GC),
`tools/nanogpt_numpy_baseline.py --fixtures <retained-fixtures> --case <case>
--warmups 1 --repeats 3 --json <output>`, and `python -m unittest discover -s
tools -p test_check_nanogpt.py`. Full argv/environment are in JSON.

All eight command groups finished successfully with no test timeout. Initial
global Python lacked NumPy; installing the pinned packages in a new isolated
environment resolved this setup gap. The existing torch environment lacked pip
and was left unchanged. Configuration capture warned only that optional PyYAML
would improve display formatting; numeric execution was unaffected.

Only reference BLAS was executed locally; OpenBLAS coverage is not claimed as
a fresh local measurement. The implementation head `1ae2374b` has four completed
successful workflows, including [CI run 39099852656](https://github.com/den-run-ai/pystachy/actions/runs/39099852656),
whose changed benchmark job specifies both reference BLAS and OpenBLAS. That is
upstream implementation CI evidence, separate from this audit PR's checks.

The retained short timings ran on a shared host with two concurrent correctness
jobs. They establish neither speedup nor regression; no paired performance,
RSS or memory-allocation experiment was run. Previous PR timing artifacts are
not substituted for fresh measurements. The NumPy baseline is CPython-hosted;
no NumPy/SciPy upstream suite or general package compatibility was established.
Unchanged stdlib import/API, other ports, pyperformance and CPython suite probes
were not rerun. The prior **142/475 native, 146/475 stub-assisted** import counts
remain historical measurements at `0e6392b2`, not new counts here. Full CPython
regrtest and local `make verify` were not run. Existing unrelated blockers and
performance issues were not reclassified by this example-only checkpoint.

## 2026-10-18 — #667: code-point strings and downstream Unicode API gains

Evaluated [main `a355c83f`](https://github.com/den-run-ai/pystachy/commit/a355c83ff7b60b64e3264867593064c3da9611a5),
merging [#667](https://github.com/den-run-ai/pystachy/pull/667) at
**2026-10-18 05:43:19 UTC**. Fresh PR metadata and git ancestry confirm it is
the only first-parent merge since evaluated `6d4ed3d1`. Read #491/#616 and the
implementation comments before selecting probes. The 85-file diff changes
compiler/runtime, string ABI, decoded IO, iterators, embedding, tests and tooling.
Rebuilt the compiler and runtime from this exact source using CPython **3.13.16**,
LLVM **18.1.3**, Linux x86-64, two build workers. Three-stage fixed points:
**621,418 compiler / 18,388 runtime IR lines**. Executable SHA-256:
`6282b36345e91ae49eefeed10b43c8adff331c4835b2bec3a217a42b77fc90f5`.

[Machine-readable evidence](compatibility-2026-10-18-unicode.json) retains the
driver, commands, source/compiler/input/fixture hashes, outputs, previous/current
comparisons and harness failures. Paired old runs use the verified `0e6392b2`
compiler with **`6d4ed3d1` runtime/library home**, not the updated checkout.
Those compiler/runtime sources were unchanged by #647. New runs explicitly use
the rebuilt `a355c83f` compiler and source home.

### Measured gains, not merely a stable import count

All seven programs below newly match the pinned CPython reference in **both
JIT and AOT**; the same programs did not match before the merge. Port probes use
the repository's maintained adaptations under both CPython and Pystachy, not
unmodified installed upstream packages.

| Retained/targeted API | Before | After / CPython |
|---|---|---|
| Core text `café日本😀` | Length 15; byte-wise indexing/iteration | Length 7; matching iteration, reverse slice, search and `chr(233)` |
| `textwrap.wrap("aa ää-ää", 7)` | Three lines: `aa`, `ää-`, `ää` | Two lines: `aa ää-`, `ää` |
| Retained `len("café"), re.search("é", "café").span()` | `5 (3, 5)` | **`4 (3, 4)`** |
| `StringIO("é日本😀").read(2)` | `é`, then `日本😀` | `é日`, then `本😀`; position 2 |
| Three pylev algorithms: café/cafe, 日本/日, 😀/x | Distances 2, 3, 4 | All distances 1 |
| `wcwidth.wcswidth("中文", len("中"))` | 4 | 2; ordinary CJK/accent widths also remain correct |
| English Snowball `stemWord("boñing")` | `boñ` | `boñe` |

This corrects important non-ASCII behavior within already importable libraries.
It does not by itself remove their static typing,
dynamic-object, loader or C-extension adaptations. In particular, native
NumPy/PyPI compatibility cannot be inferred from string FFI or explicit CPython
embedding. No blanket minor-adaptation reclassification is made for a whole
package from these selected operations.

| Fresh evidence category | Result and boundary |
|---|---|
| Isolated stdlib imports, with `--metadata` | **142/475 native**, **146/475 with throwing C-module stubs**; same 522-file CPython inventory and 47 overlay exclusions. All inventory hashes and normalized per-module results unchanged; zero timeouts. IR generation only, not API execution; stubs do not implement missing modules. |
| Selected native text/library programs | **42/42 JIT/AOT** checks over 21 programs; the same **42/42** with compiler GC interval 1000 and program interval 1. Includes Latin-1, HTML parser positions, regex, IO, textwrap, Unicode iteration and string append/slicing. |
| Remaining recorded deviations | **20/20** checks over 10 programs. These pass their deviation recordings, not CPython equivalence. |
| Affected maintained ports | **18/18** checks over nine pylev/wcwidth/Snowball/pyfiglet programs. All 30 selected focused+port CPython programs independently match their exact recordings. |
| Unicode audit/control tool | **2,280 operation/control checks** pass with normal/audit/normal execution, JIT/AOT and GC stress; runtime IR remains identical. This is targeted instrumentation coverage, not 2,280 upstream tests. |
| Native mapping/GC probe and contracts | `unicodeprobe` passes normal and per-allocation GC locality/cache/seam controls; **446 runtime entries / 70 exception classes** and 170 runtime.py function contracts agree. IR + llvm-as accept **1,366 programs**. |
| Native/hosted boundary | **125/125 FFI checks** pass, including Unicode round trips through explicit CPython embedding/extension boundaries. This does not establish a native upstream extension loader. |
| Hosted upstream suites / compiled mapped subset | fnmatch **17/17 hosted**; mapping 12 compiled, three unsupported, two partial. textwrap **66/66 hosted**; mapping now **65 compiled + one partial**, previously 63 compiled + two deviations + one partial. The two promoted methods are `test_umlaut_followed_by_dash` and `test_narrow_non_breaking_space`; their compiled programs are included above. Hosted totals are not compiled-suite totals. |
| Adapted benchmark correctness | `regex_dna`, `regex_effbot`, `regex_v8` smoke checks match across CPython/JIT/AOT. No full pyperf/pyperformance suite or performance regression claim. |

### Remaining gaps and stale issue/documentation claims

Fresh paired minimal programs still show **ASCII-only case/classification**
(`é.upper()`, `É.lower()`, `ß.casefold()`, `é.isalpha()`), empty-pattern
`"é".replace("", "x")` splitting UTF-8 storage rather than producing `xéx`, and
native UTF-8 file `write("é")` returning **2 rather than 1**. UTF-16 encoding
still raises **NotImplementedError** in both native modes, while CPython returns
encoded bytes. Keep [#120](https://github.com/den-run-ai/pystachy/issues/120)
open for measured Unicode follow-ups, but its old blanket byte-index/length
claim is superseded by #667. Strict invalid decoding remains separately scoped
by [#29](https://github.com/den-run-ai/pystachy/issues/29), not newly resolved
here. No new uncovered issue was needed for these already-described gaps.

Three port notes are stale: `ports/pylev/PORT.md`'s byte-distance example,
`ports/wcwidth/PORT.md`'s bounded-length caveat, and
`ports/snowballstemmer/PORT.md`'s `boñing` example now contradict measured
results. Also, the byte-column `expandtabs` claims in
`docs/language/compatibility.md` and `lib/compatibility.md` are stale:
**30 selected cases** (BMP/astral/combining/newline/multiple-tab strings, five
tab widths) match CPython in both old and new JIT/AOT. The prior runtime already
counts non-continuation bytes as columns. Do **not** count this as a new fix or
a confirmed remaining failure. These documentation corrections are recorded
here without changing implementation/port branches.

### Cost, reproduction and limits

Source/ABI inspection shows the LP64 string storage header growing **16 → 24
bytes**, before allocator rounding, and 64 weak position hints occupying
**1,536 bytes**. These are structural costs, not measured RSS. The deterministic
C probe validates bounded nearby-mapping work and GC clearing; uncached distant
Unicode indexing can still require an O(n) scan. No paired speed/RSS experiment
was run. Shared-host smoke timings with concurrent correctness work are retained
for provenance only, not evidence of speedup or regression.

Reproduce with the JSON's `bootstrap_command`, then its `test_driver` from the
evaluated checkout using the pinned Python (`-I` for the controller). Driver
modes are default, `references`, `probes`, and `probes textwrap tabs`; exact argv,
source/port paths, selections and environments are retained. Principal commands
are `tests/run.sh ./pystachy 'jit aot' <selection>`, the metadata-enabled native
and `--stubs` import sweeps, `make unicodeprobe check-runtime check-ir`,
`tools/unicode_audit.py -c native=./pystachy`, `make test-ffi`,
`tools/port_check.py --json <output>`, and
`tools/bench_pyperformance.py --compiler ./pystachy --smoke --benchmarks regex_dna
regex_effbot regex_v8 --json <output>`. Relocate retained absolute paths together.

An initial audit-generated `textwrap.py` shadowed the library and caused both
CPython and native probe failures. Two retry invocations still encountered the
lingering shadow; isolation in a `programs/` subdirectory plus prefixed filenames
and controller `-I` resolved it. Failed initial output is preserved in JSON,
not classified as a Pystachy bug. A separate capture-name collision overwrote
the first successful port/regex raw reports; the driver now separates command
envelopes and both tools were rerun to retain their raw reports. No test timeout
or retained correctness regression occurred. Malformed old string output was
captured with UTF-8 replacement decoding; those traces are not raw-byte oracles.

The implementation head `3abdefc2` has four successful workflows, including
[CI run 39099912261](https://github.com/den-run-ai/pystachy/actions/runs/39099912261).
That is separate from this audit PR's checks. Local full `make verify`, full
CPython regrtest, unrelated inference/recursion blockers and other package suites
were not rerun. Historical global suite counts remain historical, not newly
measured totals. The audit PR remains draft pending contributor DCO sign-off.

## 2026-10-19 — native JSON, regex and array catch-up through #723

Evaluated exact [main `5db1e4b5`](https://github.com/den-run-ai/pystachy/commit/5db1e4b5e14e4da6d8bfa5e0952cd191fbc08959),
after the latest completed main checkpoint `2359de69`. The triggering
[#723](https://github.com/den-run-ai/pystachy/pull/723) merged at
2026-10-19 17:05:10 UTC and is documentation/recorded-results only. Its merge is
in main's history; implementation remains that of #699 (`d97a60c4`). This audit
also covers the intervening implementation changes, not just the wake-up PR:

| Merges | Selected evidence |
|---|---|
| #678 | AST constructors, reference equality/hash, file-descriptor select, three compiled upstream-derived files and rejection cases; native C probes |
| #676, #680, #682, #683, #685 | Regex branch/repeat/class/Unicode/raw-subject and ownership checks; bytes reads and string length; four affected ports; three adapted regex benchmarks; operation-count controls |
| #670 | Recursive aliases and native JSON, accepted/rejected/deviation cases; differential corpus; JSON records benchmark; two affected upstream benchmark sources |
| #681, #684, #695 | Stack index keys, cold/noreturn lowering and varargs/generator ownership; focused normal/GC checks, runtime contracts, IR validation and bootstrap |
| #687, #688, #691, #693, #698, #699 | Array indexing/elementwise/matmul, nanoGPT reads, BLAS packing/view offsets and `ffi.at`; array/nanoGPT fixtures, FFI and LP64 BLAS parity |
| #675, #673, #679, #723 | Instructions/install docs, README, docs-only CI routing and recorded benchmarks; no new compatibility numerator assigned |

The [machine-readable evidence](compatibility-2026-10-19-catchup.json) retains
every intervening first-parent merge and changed-file list, selections, fixture
and tool hashes, exact commands, output, compiler provenance and reproduction
drivers. It preserves the other session's merged prototype audit and this PR's
earlier GC/BLAS/Unicode measurements; no implementation branch was changed.

### Fresh results and input controls

Rebuilt from the evaluated SHA with **CPython 3.13.16 / LLVM 18.1.3**. Compiler
and runtime reach three-way fixed points at **630,644 / 18,388 IR lines**;
executable SHA-256 is
`33f66f7e745cd8581d1f743cc3085381173b6b613b63ba695de83f4dbaf59f75`.
Source revision and executable hash are recorded separately. CPython was restored
from its pinned uv distribution after the earlier executable disappeared.

| Evidence category | Fresh outcome |
|---|---|
| Isolated native imports, with metadata | **144/470**, 52 exclusions from the same 522-module inventory; zero timeouts and no successful import lost |
| Throwing C-module stand-ins, with metadata | **146/470**; diagnostic IR compilation, not implemented APIs |
| Selected stdlib/compiler/array fixtures | **112/112**: 74 positive JIT/AOT checks, 14 recorded-deviation checks and 24 expected compiler rejections, across 68 files |
| Per-allocation program GC | **46/46** selected positive JIT/AOT checks (23 files); compiler stress interval 1000 |
| Adapted ports | **18/18** JIT/AOT checks over nine pylev, wcwidth, pyfiglet and Snowball programs |
| CPython fixture controls | **46/46** recordings match, including stdout, exit and final exception where present |
| Native JSON differential corpus | **14,444 cases in each JIT and AOT run**, both with GC every allocation; **22,449** hosted differential/limit checks, seed 391 |
| FFI | **138/138** native harness checks |
| LP64 BLAS | **24 matrix + 15 linear + 32 invalid-input cases per tier**, passing CPython FFI twin, JIT, AOT and both native GC tiers; reference BLAS 3.12.0, NumPy 2.3.5 |
| Adapted nanoGPT BLAS parity | **4,022 values per tier**, all five tiers pass with exact agreement for these fixtures |
| Structural/runtime controls | **451 runtime entries / 70 exception classes** agree; **1,418** programs pass IR validation and llvm-as; weakref/select C probes pass normally and under GC stress |
| Adapted benchmarks | Three regex smoke workloads match CPython; JSON records smoke passes skewed/mixed/changing UTF-8 profiles, generic and hand-guarded paths, parse/end-to-end and predecoded phases |

The import numerator deliberately excludes shipped replacements. Adding `lib/json`
removes upstream `json`, `json.decoder`, `json.encoder`, `json.scanner` and
`json.tool` from the swept denominator, **475 → 470**. This is one new bounded
native library surface, not five new successful upstream imports or five
regressions. Every shared normalized result is unchanged except `turtle`'s
environment-dependent first error: this CPython distribution includes tkinter,
so it reaches missing `_tkinter` instead of missing `tkinter`. **521/522 stdlib
file hashes match** the prototype checkpoint; only distribution `ssl.py` differs,
and its `_ssl` first error is unchanged. Both differences are recorded rather
than attributed to compiler changes.

### Useful JSON support, but not general dynamic Python

Native `json.loads`/`dumps` now execute recursive mixed null/bool/int/float/string,
list and string-keyed dict values; retained tests exercise mutation, identity,
Unicode/surrogates and error positions. This materially improves the previous
blanket recursive-JSON blocker. It does **not** make `Any` arbitrary dynamic
storage: this is a bounded nominal recursive union with explicit narrowing.

The documented limits remain significant: signed 64-bit integers, 256-container
JSON depth, string input only, and no `load`/`dump`, encoder/decoder classes,
hooks/default conversion, indentation, tuple serialization or arbitrary objects.
Unsupported types/APIs can be compile-time errors instead of CPython runtime
exceptions. See [the contract](../json-prototype.md). Selecting a supported
call and giving a concrete type can be a minor adaptation; replacing a dynamic
framework/object model remains major work.

Fresh runner-replaced **pyperformance 1.14.0** checks cover only the five affected
JSON/regex sources, with the pinned sdist and source hashes verified:

| Source | Fresh native compilation |
|---|---|
| `json_dumps` | Now reaches empty-dict inference at line 7, instead of missing `json` |
| `json_loads` | Now reaches `expected int, got str` at line 50, instead of missing `json` |
| `regex_dna` | Still rejects `bytearray()` |
| `regex_effbot` | Still rejects the function's `.data` attribute |
| `regex_v8` | Still compiles |

Only **1/5** of this affected subset compiles unchanged apart from runner
replacement. The earlier **6/52** full census and 27 package-probe outcomes were
not rerun and remain dated, not new totals. Nor does a compiled adapted array or
BLAS program establish native NumPy/PyTorch import or upstream-suite support.
The three upstream-derived AST/select/weakref files pass inside the selected
suite, with their documented exclusions; CPython regrtest was not run.

Fresh imports still expose `_opcode` for inspect/unittest, `_io` for importlib,
and missing `getweakrefcount` for upstream weakref. `_py_abc` and `_weakrefset`
retain their import gains, but that is not proof their complete APIs work.
General runners, reflection and dynamic object/storage work remain substantial
blockers. Existing #491/#616/#9/#487 and the API-specific trackers own these
boundaries; this pass found no confirmed uncovered correctness bug requiring a
new issue. Unrelated cache, numeric-union, recursion and codec probes were not
rerun, so their historical failures are not relabeled as fresh findings.

### Performance evidence and limitations

Fresh regex operation counters pass their bounds (including zero temporary
charset bit lists over 787,450 calls and no warm Unicode charset/mapping work).
These are hosted structural controls, not a new native timing or RSS study.
Concurrent correctness-run timings are retained for provenance only.

For #723, independently recomputed **30 nanoGPT statistics**, **135 ndarray
rounded summary values** and **seven after-source hashes**, all matching its
committed records. The recorded #699 head and merge have the same Git tree.
This validates artifact arithmetic/provenance, **not an independent rerun** of
its benchmark. Its ten rotated/interleaved rounds on one pinned CPU of a shared
2.1 GHz host report full-logits/loss BLAS AOT **1.227 → 0.564 ms**, JIT
**1.676 → 0.730 ms**, scalar AOT **5.200 → 2.492 ms**, scalar JIT
**15.852 → 4.288 ms**. The 108,288-parameter float64 model uses batch 2, length
16; 20 warmups/300 repeats, single-threaded SciPy OpenBLAS. NumPy 2.5.4/SciPy
1.18.1/PyTorch 2.14.1+cpu and mixed CPython 3.12.3/3.13.16 reference roles are
part of that experiment, not this audit's reference-BLAS/NumPy 2.3.5 environment.
The constructed before tree reverts #657 from #642's merge. BLAS output changes
in last bits are disclosed with maximum difference 3.3e-16; scalar outputs are
byte-identical. Do not turn these workload-specific results into general package
speed claims. [nanoGPT record](../../examples/nanogpt/results/ndarray-work-paired.json)
and [ndarray record](../../examples/ndarray/results/bench-2026-10-19.json).

### Reproduction and report maintenance

Use the evidence's bootstrap command, then `audit-current-driver.py` (first with
`references`, then default), `audit-aux.py`, and `audit-artifacts.py`, with pinned
CPython and relocated ROOT/LLVM/NumPy paths. The primary driver intentionally
retains the original failed benchmark invocation: `json_dumps/json_loads` were
mistakenly requested as delivered adaptations, and CLI validation rejected them
before execution. The corrected three-regex smoke run and separate native JSON
smoke/affected-census runs pass. This is an explicit audit invocation error, not
a compiler failure; the primary driver's aggregate exit 1 is explained by it.
The affected census changes only the controller's in-memory source selection,
not repository files or upstream programs beyond its existing runner replacement.

No full local `make verify`, full upstream package suite, new PyTorch training
fixture export, or independent paired speed/RSS experiment is claimed. Optional
broad testing stopped after these concrete affected risks were checked. The
older DCO draft notes above describe the policy at those checkpoints: current
[contribution policy](../../CONTRIBUTING.md#rights-and-sign-off) exempts this
same-repository branch from the fork DCO check. No sign-off was fabricated.
Applicable checks and maintainer review remain required before merge.
The report-only diff passes `git diff --cached origin/main --check`. Checking
the integration against the old audit head also reports nine trailing blank
lines in already-merged JSON/recursive-alias test fixtures; those inherited
implementation files are unchanged by this audit.

## 2026-10-19 — #722: JSON encoder, recursive diagnostics and effects

Evaluated [main `898d0b95f66772774b59137b1eeb5791ff17e8e5`](https://github.com/den-run-ai/pystachy/commit/898d0b95f66772774b59137b1eeb5791ff17e8e5).
Live [#722](https://github.com/den-run-ai/pystachy/pull/722) metadata and local
ancestry agree that it merged at 18:32:13 UTC. It is the only first-parent merge
after the preceding evaluated `5db1e4b5`. The audit's own docs are not counted as
new compatibility. Reviewed the changed-file list, PR discussion and #491/#616
coordination comments; no implementation branch or issue state was changed.

[Machine-readable evidence](compatibility-2026-10-19-json-followup.json) retains
commands, exact fixture/tool/input hashes, output, source and compiler identities,
the before/after controls, source census and timing samples. Rebuilt from clean
`898d0b95` using CPython **3.13.16** and LLVM **18.1.3**. Compiler SHA-256:
`db27087b4f26a178852401e2b2ef266b72f6757a7ef0710c5b88b42d84abe52e`.
Compiler/runtime three-stage fixed points pass at **629,754 / 18,388** IR lines.
The old control binary remains identified separately as the `5db1e4b5` build,
SHA-256 `33f66f7e745cd8581d1f743cc3085381173b6b613b63ba695de83f4dbaf59f75`;
each control explicitly uses its own checkout's `PYSTACHY_HOME`.

### Correctness and compatibility deltas

| Check | Fresh result and boundary |
|---|---|
| Isolated imports with metadata | **144/470** native; **146/470** stub-assisted. Same 522 hashed CPython inputs and 52 overlay exclusions. No result or first-error changes, no timeouts. Import/IR acceptance is not API execution. |
| Selected JSON/recursive-alias/container fixtures | **64/64** checks: 23 CPython-recorded positive programs and 3 documented deviations in both JIT/AOT, plus 12 compiler rejections. |
| Program GC stress | **52/52**, the same 26 executable cases in both native modes. |
| Adapted ordered-set/sortedcontainers APIs | **8/8** JIT/AOT checks across four retained programs. These are adapted ports, not unmodified installed PyPI suites. |
| CPython reference recordings | **27/27**, the 23 positive programs plus four port programs. Deviations are deliberately not counted as CPython matches. |
| JSON differential tool | **22,449** hosted checks; **14,444** cases per native mode with collection at every allocation. |
| Runtime / IR / equality contracts | **451** runtime entries and **70** exception classes; **1,420** IR programs accepted; shared-DAG equality/search budget probe passes normally and with GC stress. |
| JSON benchmark correctness gates | **7/7** controller unit tests; nine profile/text combinations pass CPython/JIT/AOT, generic/handguarded, end-to-end/predecoded checks. Encoding is checked against CPython's length and order-sensitive digest as well as decoded checksum. Smoke times are not performance evidence. |
| Upstream pyperformance 1.14.0 JSON sources | Both remain blocked after the census's existing runner replacement: `json_dumps` at line 7 (empty-dict inference), `json_loads` at line 50 (`expected int, got str`). No whole-package or upstream-suite improvement inferred. |

The before/after depth control catches a real contract correction: distinct
recursive lists ending in a string now compare successfully at **512** alias
edges, like integer leaves; the previous compiler raised early for the string
case. Equality and repr reject **513**, and unwind/reuse and cyclic-container
checks pass. This is the documented native budget, **not** CPython recursion-limit
parity or a resolution of general recursion issue #595.

Diagnostics now say `list[JSONValue]` instead of `list[rec[json.JSONValue]]`, and
the string-join rejection names alias `V` instead of `rec`. Quoted user text
`'rec[1]'` is unchanged in old and new output. The new IR effect contract keeps
raising effects for recursive comparisons/membership/count/repr while removing
them from equivalent nonrecursive operations and str-key dictionary storage.
This is compiler-effect precision, not additional runtime dynamic typing.

### Performance evidence and scope

The merged [encoder report](native-json-encoder-2026-10-19.md) reports
3.6–6.3x faster JIT/AOT encoding for its 5,000-record inputs. Recomputed its
per-process medians, ranges and MADs from the stored samples and regenerated
both input hashes. Its before/after compiler binary is the same, but the metadata
records dirty earlier revisions and seven compiler/runtime source hashes differ
from this evaluated main. Its encoder and benchmark source hashes match. Therefore
those numbers remain attributed to the author's experiment, not relabeled as a
fresh current-main measurement. Its 44.4/43.5 MiB UTF-8/ASCII heap peaks are unchanged
between before/after; this is not evidence of a memory reduction.

After correctness jobs finished, independently ran the same current compiler and
runtime with `lib/json.py` from `5db1e4b5` versus `898d0b95`, selected through
`PYSTACHY_PATH`. Three rounds alternate before/after order; each has one process
per mode/algorithm, three samples of three documents after 200 ms warmup, pinned
to one available CPU. Inputs are 5,000 skewed records in UTF-8 and ASCII; native
`dumps()` uses its default `ensure_ascii=True`. All runs pass checksum, encoded
length and order-sensitive digest gates. Generic-path results, milliseconds per
document (median of each round's process median):

| Input / mode | Before ms | After ms | Median paired speedup | Paired range |
|---|---:|---:|---:|---:|
| UTF-8 / JIT | 25.31 | 7.26 | 3.47x | 2.65–3.80x |
| UTF-8 / AOT | 25.38 | 5.92 | 4.29x | 3.96–4.74x |
| ASCII / JIT | 19.97 | 4.59 | 4.35x | 4.13–4.86x |
| ASCII / AOT | 19.02 | 3.81 | 4.82x | 4.60–7.96x |

The unchanged CPython encoder controls have paired medians 1.08x / 0.95x;
the shared host and short warmup still produce noise, notably the first ASCII
AOT before run. No isolated single sample is used as a regression claim. Current
median encoding remains about **1.07–2.03x CPython's time** across these cells;
UTF-8 escaping is the slower relative case. This confirms a substantial bounded
encoder improvement, not a full application speedup, pyperf-quality distribution,
memory reduction or general JSON compatibility. Raw samples, load, affinity,
compiler/module hashes and the handguarded control are retained in JSON.

### Reproduction and limits

The evidence embeds `audit-722.py` (run `references`, default, `controls`, and
`census`), `audit-722-artifacts.py`, `audit-722-timing.py` and the aggregation
script; relocate the explicit checkout/LLVM paths. Core commands are
`tools/import_sweep.py --metadata` (native and `--stubs`),
`tools/json_check.py --compiler ./pystachy --native --gc-stress`,
`make check-runtime check-ir eqprobe`, and
`tools/bench_json.py --compiler ./pystachy --smoke --texts utf8 ascii escaped`.
Fixtures and source selection are explicit in JSON, including the two upstream
sources from the retained pinned sdist. The census edits its controller's
in-memory selection only, not the upstream code beyond the existing runner shim.

All **31 jobs** in the four PR workflows on implementation head `196c95ce` were
read fresh and succeeded, including the full CI merge-verification job
([CI run](https://github.com/den-run-ai/pystachy/actions/runs/39298259734)). This is
remote implementation evidence, separate from this audit's focused local checks
and from the audit PR's own docs-only checks. No full local `make verify`, CPython
regrtest, 27-package sweep, full 52-source census, UBSan rerun or NumPy assessment
is claimed. General JSON/PyPI blockers and minor/major adaptation boundaries from
the preceding checkpoint remain; no new uncovered bug was confirmed by this pass.

## 2026-10-19 — #731: validate hosted-compiler coverage, not library coverage

Evaluated [main `5dcb4859d363267bb2c8ce851a4476a2b75a2c36`](https://github.com/den-run-ai/pystachy/commit/5dcb4859d363267bb2c8ce851a4476a2b75a2c36).
Re-fetched [#731](https://github.com/den-run-ai/pystachy/pull/731), confirmed its
merge at 2026-10-19 19:23:44 UTC and ancestry in main, and inspected every changed
file since evaluated `898d0b95`. The only intervening first-parent merges are
[#733](https://github.com/den-run-ai/pystachy/pull/733) (`057b12335b681d02ba585badad7e5991d33d77fa`,
README workflow/release badges) and #731 (coverage configuration, script, workflow,
Makefile target, development dependency and documentation). Source under `src/`,
`runtime.c`, `runtime.py`, `lib/`, `ports/` and `tests/` is byte-identical to the
preceding checkpoint. #491/#616 coordination and #731 review comments were read;
the harness path-filter concern is addressed by including `tests/run.sh` and
calling `tools/coverage.sh` directly in CI.

### Fresh focused measurement

Used a clean detached checkout at this exact main and the **CPython-hosted compiler
from that checkout**, CPython **3.13.16**, LLVM **18.1.3**, coverage.py **7.16.2**,
two workers and a new empty runtime cache. The pinned base Python lacked coverage;
installed the pinned package into an isolated venv. No native compiler was used or
rebuilt because implementation sources are unchanged. The previous native compiler
provenance remains `898d0b95`, not relabeled as this source revision.

With inherited compiler/coverage options removed, ran:

```sh
tools/coverage.sh tests/json_encoder_strings.py tests/recursive_alias_values.py \
  tests/errors/recursive_alias_compare_message.py \
  tests/deviations/recursive_alias_limits.py tests/port_ordered_set_api.py
```

The exact `env -i` settings, fixture/recording hashes, report summaries and
aggregation program are retained in [JSON evidence](compatibility-2026-10-19-coverage-tooling.json).
All **9 checks pass**: six positive JIT/AOT checks, two documented-deviation checks
and one expected diagnostic rejection. The script validates **10 coverage data
files**, one per check plus runtime warmup, before combining them. HTML, JSON,
summary and badge generation complete successfully. This selected subset reports
**40.0%** combined line/branch coverage; it is deliberately not a full-corpus
number. The script's 16 seconds covers warmup and tests, excludes report
generation, and is not a performance comparison.

Preserved the positive artifacts, then repeated only `tests/port_ordered_set_api.py`
with an external alternate configuration omitting `patch = execv`. Both program
checks still pass, but only **1 of 3** expected compiler data files survives:
JIT and runtime warmup replace CPython with `lli`. The coverage script correctly
exits **1**, reports missing data and writes no badge. This is an intentional
negative control, not a product regression. No repository implementation or
coverage configuration was modified by the control.

### Remote evidence and remaining scope

Read the completed [implementation Coverage run](https://github.com/den-run-ai/pystachy/actions/runs/39302676725)
and [job logs](https://github.com/den-run-ai/pystachy/actions/runs/39302676725/job/118232267886):
**4,583 checks passed**, zero failed, **93.3%** combined compiler coverage. Its
tested PR merge is `258b9df`, head `b410472469e3f8a9288dda0bdbc0d6c992c34310` on
base `5db1e4b5e14e4da6d8bfa5e0952cd191fbc08959`; it is not a fresh full run on this
checkpoint. The badge-publishing job is correctly skipped on that PR run. No claim
is made here that main's separate badge-publishing job has completed.

The new daily/on-demand workflow measures **CPython-executed compiler source only**.
It does not measure execution of `runtime.c`, `runtime.py`, `lib/`, native compiled
programs or upstream CPython suites. In particular, **93.3% compiler coverage is
not 93.3% CPython compatibility**. Updated existing [#45](https://github.com/den-run-ai/pystachy/issues/45)
to remove its stale "no scheduled workflow" statement, mark the compiler lane
implemented and retain native-runtime coverage and broader nightly work as open.
No new issue or uncovered bug was needed.

The preceding **144/470 native imports** and **146/470 stub-assisted imports**
(522-source inventory, 52 overlay exclusions) are retained historical results,
not fresh sweeps. No implementation changes require repeating import/API/port/
package/benchmark suites for this merge; no additional library support, performance
or memory improvement is inferred. Full local corpus coverage and CPython regrtest
were not run. The dated baseline and all previous evidence remain unchanged.

## 2026-10-19 — #690: module attributes retain their own bindings

Evaluated [main `681bdd1712799e1b4af24a8b64219bd0adf723a7`](https://github.com/den-run-ai/pystachy/commit/681bdd1712799e1b4af24a8b64219bd0adf723a7),
the only first-parent merge after evaluated `5dcb4859`. Re-fetched
[#690](https://github.com/den-run-ai/pystachy/pull/690), verified its 2026-10-19
19:30:00 UTC merge and ancestry in main, and read #491/#616 coordination and the
implementation's review comments. The diff changes only `loader.py` and adds four
differential fixtures/recordings. No other session's branch was modified.

### Correctness and acceptance changes

Rebuilt a clean exact-main checkout with **CPython 3.13.16 / LLVM 18.1.3**.
Compiler and runtime IR fixed points pass at **629,802 / 18,388 lines**. Native
executable SHA-256 is
`858844616e4ad8954e15d86929a4934f9c56601b07b469824b664fb3b02cfa98`;
both its build source and evaluated source are `681bdd17`. The old-control binary
is the separately verified `898d0b95` build
`db27087b4f26a178852401e2b2ef266b72f6757a7ef0710c5b88b42d84abe52e`.
Its compiler/runtime/lib/port/test sources equal previous checkpoint `5dcb4859`;
the intervening changes were coverage tooling and documentation.

Fresh CPython versus old/new native JIT and AOT controls confirm:

| Probe | Old native behavior | Current native behavior / CPython |
|---|---|---|
| Local `dirname as basename`, then `posixpath.basename(p)` | Wrong function called: `/a/b /a/b` | `/a/b c.txt` |
| `_thread.error` with a shadowing program class or local import named `RuntimeError` | Caught as the program's class or `re.error` | Builtin `RuntimeError` |
| Function-local `fnmatch.fnmatch` and `bisect.bisect` | Rejected at the first call | `True False`, then `2` |
| `token.OP` / `token.NL` with same-named type parameters | TypeVar-as-value rejection | Module constants and ordinary values preserved |
| Additional probe: own `RuntimeError` raised under `except _thread.error` | Wrong builtin handler catches it | Not caught by builtin handler |
| Additional probe: local `datetime.datetime(...).isoformat()` | Rejected as undefined `datetime` | `2026-10-19T12:30:00` |

The first two fixtures and the additional exception-handler probe correct silent
wrong answers; the other controls remove unnecessary rejection/porting edits.
These are general module-binding fixes, not new replacement libraries. One known
boundary from #690's discussion remains: a local **variable** named `RuntimeError`
still makes `except _thread.error` fail with "an except clause needs exception
classes" in both old and new native compilers; CPython prints `caught 1`. The
retained reproduction records that remaining limitation without calling it a new
regression or opening a duplicate issue.

### Focused verification

- **404 checks over 295 selected import/module/typeparam/exception cases pass**.
- **28 checks over 14 affected stdlib/API programs pass**, including bisect,
  datetime, fnmatch, token and the retained compiled upstream-derived
  fnmatch/datetime programs. This is not an unmodified full upstream test suite.
- **8 checks over four adapted ordered-set/sortedcontainers programs pass**.
- The four new fixtures pass **8/8 each** with program GC every allocation,
  optimizations disabled, and the CPython-hosted compiler.
- **22 CPython recordings match** for the new fixtures, affected APIs and ports;
  three additional independent CPython controls are recorded separately.

Commands include `make PY=/root/.local/bin/python3.13`, selected
`tests/run.sh ./pystachy "jit aot"`, `PYSTACHY_GC_STRESS_PROGRAM=1`,
`PYSTACHY_OPT=-all`, hosted `python3.13 -m pystachy`, and isolated old/new
`run` / `build` plus AOT execution. The evidence retains exact selectors,
fixture hashes, programs, outputs and sanitized compiler-option settings.

### Import census, IR comparison and limits

Fresh isolated `tools/import_sweep.py --metadata` runs, native and `--stubs`, retain
**144/470 native imports** and **146/470 stub-assisted imports**. All 522 CPython
input hashes and 52 overlay exclusions match the preceding measurements. The full
per-module results and first errors are unchanged; no timeout, lost success or
newly exposed import blocker. Stubs remain throwing diagnostic stand-ins, not
implementations. The evidence references the unchanged prior result maps and
stores fresh metadata, raw-result hashes, normalization and empty delta maps.

`tools/irsame.sh OLD NEW` compares the full **3,109-program** current corpus using
the same current `PYSTACHY_HOME` for both binaries: **3,105 identical**, **four
different**, exactly this merge's new fixtures. The stock tool's exit **1** is
expected here, not suppressed or relabeled as zero differences. Its first three
detailed differences show the corrected call/exception binding and removed local
import rejection; the fourth type-parameter case is independently covered by
the old/new JIT/AOT controls above. No other corpus IR, diagnostics or exit status
differs. This is a compile-time comparison, not execution of every corpus program.

All **31 jobs across four implementation PR workflows** at `e207149c` were read
fresh and succeeded, including [the complete verification summary](https://github.com/den-run-ai/pystachy/actions/runs/39303785336).
That head's compiler/runtime/lib/port/test sources equal evaluated main; only
the later #731/#733 tooling/documentation files differ. This remote evidence is
separate from local focused checks and from this report PR's own checks.

Full commands, inputs, controls, source/binary identities and reproduction scripts
are in [the measured evidence](compatibility-2026-10-19-module-bindings.json).
Initial aggregation hit a syntax error and then a baseline-path normalization
mismatch; both bookkeeping problems were corrected before publication, without
changing or rerunning the successful test outputs. Raw old/new import maps were
already identical. No full local `make verify`, CPython regrtest, broad PyPI sweep,
full upstream pyperformance census, performance or memory comparison is claimed.
Prior minor/major adaptation assessments and first-error limitations remain;
this removes specific import-placement workarounds, not general dynamic typing.

### Historical reproduction correction

[Review comment on #669](https://github.com/den-run-ai/pystachy/pull/669#discussion_r4316745001)
correctly identified that the embedded historical GC, BLAS and Unicode drivers
assume their output directories already exist. Preserved those dated JSON files
and added the mandatory `mkdir -p` prelude at the top of this rolling record,
before all historical replay instructions. Four isolated temporary-directory
checks (GC evaluator, GC budget probe, BLAS driver, Unicode driver) reproduce
`FileNotFoundError` without the prelude and pass their initial file write with it.
These validate directory setup only; the historical suites were not rerun.
The control code/results are included in the new evidence, and all new audit
drivers already create their own output directories before saving results.

## 2026-10-19 — #728: empty-pattern replacement preserves Unicode characters

Evaluated [main `946ce035c2b7f720bd53f3789bcabf5b040929af`](https://github.com/den-run-ai/pystachy/commit/946ce035c2b7f720bd53f3789bcabf5b040929af),
which merges [#728](https://github.com/den-run-ai/pystachy/pull/728) at
**2026-10-19 20:30:18 UTC**. Fresh PR metadata and local ancestry agree; it is the
only main merge since evaluated `681bdd17`. Read #491/#616 coordination and #728's
review comments before work. The diff changes runtime replacement, the compiler's
Unicode-audit operation list, their probes and compatibility documentation. No
stdlib overlay or port implementation changed. No implementation branch was edited.

### Measured functional delta

A clean exact-main rebuild with **CPython 3.13.16 / LLVM 18.1.3** reaches compiler
and runtime IR fixed points of **629,802 / 18,851 lines**. Native compiler SHA-256:
`762659eac68d8f8462a53469ce1cba3c77e88f9f9150d0571bf8befb4549ccd7`.
Compiler build source and evaluated source are both `946ce035`; the old control is
the retained exact-`681bdd17` compiler
`858844616e4ad8954e15d86929a4934f9c56601b07b469824b664fb3b02cfa98`.

The new recorded fixture fails its CPython output comparison on the old native
compiler and matches on current main, in both JIT and AOT. A separate original
audit program exercises 12 strings, eight insertion strings and 11 explicit
counts plus the default, together with 176 byte-replacement controls: **1,328
output rows**, not 1,328 separate programs. Cases include NUL, combining marks,
CJK, emoji, surrogates, U+10FFFF, empty input/separator, repeated text, INT64_MIN
and INT64_MAX. Each row uses one replacement and bounded output/length/iteration
observations. CPython output is ASCII-escaped for an unambiguous comparison.

| Observation | Old `681bdd17` | Current `946ce035` / CPython |
|---|---|---|
| `ascii("é".replace("", "-"))` | `'-\xc3-\xa9-'`: insertion splits stored UTF-8 bytes | `'-\xe9-'`: insertion is between characters |
| Additional 1,328-row program | 532 rows differ in each of JIT, AOT and GC-stressed AOT | All rows match in each mode |
| 176 byte-replacement rows | Match CPython | Still match CPython; insertion remains between bytes |
| Runtime-input regression | Malformed text, wrong length/search and split/list consistency | Matches checked-in CPython recording |

This removes a silent wrong-result boundary from a fundamental text API. It does
not add an importable replacement library or establish general PyPI compatibility.
No broad port adaptation classification changes follow from this narrow fix.

The first ad hoc differential attempt reused the same module variable for strings
and then bytes; the old compiler rejected the incompatible rebinding. That attempt
is retained explicitly as incomplete. Renaming only the byte-loop variables made
the probe compatible with both compilers; all comparisons above use that corrected
probe. It was a probe construction limitation, not evidence of a new regression.

### Retained checks and remaining gaps

- **215 focused checks over 144 selected cases pass**, including string, bytes,
  Unicode, expected-rejection and documented-deviation fixtures.
- **58 checks over 29 API programs pass**: textwrap, shlex, urllib.parse and regex,
  including retained compiled upstream-derived shlex cases. This is not execution
  of a complete unmodified upstream suite.
- **16 checks over eight adapted port programs pass**: pyfiglet, tomli-w and wcwidth.
- Four replacement/string fixtures pass **8/8 each** under per-allocation program
  GC, disabled optimizations, and the CPython-hosted compiler.
- **41 CPython recordings match**; the supplementary differential and residual
  programs have separate CPython references.
- Hosted-runtime `tools/rtcheck.py`: **529,601 cases, zero failures**. This tests
  runtime algorithms through the CPython primitive adapter, not native execution.
- `tools/unicode_audit.py`: **4,560 operation/control checks pass**, hosted and
  native compilers, normal/audit/normal builds, JIT/AOT and AOT with GC stress.
  Replacement now matches CPython even with the audit enabled; runtime IR is
  unchanged by audit mode. Other audited operations retain their diagnostics.
- Adapted `regex_dna`, `regex_effbot` and `regex_v8` smoke workloads match CPython
  under JIT and AOT. Only correctness is claimed: single-run timings were taken
  on a shared loaded host alongside other checks, not paired old/new benchmarks.

Fresh old/new native JIT, AOT and GC-stressed AOT controls reconfirm the two
remaining categories in [#120](https://github.com/den-run-ai/pystachy/issues/120):

| Remaining operation | CPython | Both old and current native |
|---|---|---|
| `"é".upper(), "É".lower(), "ß".casefold(), "é".isalpha()` | `É é ss True` | `é É ß False` |
| UTF-8 ordinary file `write("é")` return value | `1` | `2` |

#120 stays open; its original reproductions and dated observations are historical
evidence, not proof that replacement remains broken. Its merge comment already
identifies this partial fix, so no duplicate issue is warranted.

### Imports, compiler comparison and reproduction

Both fresh isolated `tools/import_sweep.py --metadata` runs retain **144/470
native imports** and **146/470 stub-assisted imports**, **52 overlay exclusions**,
the same **522 CPython source hashes**, and **zero changed per-module first
errors/results**. No timeout or lost success. Stub assistance still means throwing
diagnostic stand-ins, not implementations. This explains why import totals can
remain flat while API semantics materially improve.

`tools/irsame.sh OLD NEW`, using the same current `PYSTACHY_HOME`, reports all
**3,110 corpus programs identical** in IR, diagnostics and exit status. That is a
compiler comparison, not execution of all 3,110 programs; the runtime changes are
validated by the execution checks above.

All **31 jobs across four implementation workflows** on `cb05edc6` succeeded when
read, including [the full verification summary](https://github.com/den-run-ai/pystachy/actions/runs/39311555190).
That head's entire Git tree equals evaluated main's tree. This remote evidence is
separate from local selected tests and the audit PR's own checks.

[Machine-readable evidence](compatibility-2026-10-19-unicode-replace.json) retains
source/compiler/runtime hashes, exact selectors and fixture hashes, commands,
outputs, comparison hashes and first differing rows, CI jobs, baseline result-map
references, the incomplete initial probe and complete reproduction scripts.
Extract `audit-728.py`, the two supplementary probe files and the assembler into
one parent directory; relocate their explicit checkout, prior-control and
toolchain paths. The driver creates `build/audit-728` before saving results.
Run its `build`, `references`, `controls`, `extra`, `checks`, `sweeps`, `unicode`,
`oracle` and `benchmarks` modes with the pinned interpreter. Native controls use
each compiler's own source home; the IR oracle deliberately uses one shared home.
For re-aggregation, also extract this evidence's `implementation_ci` and
`incomplete_initial_probe` objects into `build/audit-728/implementation-ci.json`
and `build/audit-728/initial-probe-attempt.json` respectively; these are retained
historical records, not outputs generated by the successful replay. Refresh CI
through GitHub separately when making a new current-state claim. The assembler
also reads the preserved `compatibility-2026-10-19-json-followup.json` baseline
from the report checkout named by `DEST`.

No full local `make verify`, CPython regrtest, broad PyPI/package sweep, full
upstream benchmark census, paired timing or memory-regression conclusion is
claimed. First-error limitations and minor/major adaptation assessments from the
dated baseline remain applicable. Historical reports and JSON are unchanged.

## 2026-10-19 — #692 conditional imports and #735/#665 AOT power rounding

Evaluated [main `53c17bad9cd30120b8e0a3831797f3b22e9a9e87`](https://github.com/den-run-ai/pystachy/commit/53c17bad9cd30120b8e0a3831797f3b22e9a9e87).
Since the previous checkpoint `946ce035`, the first-parent merges are
[#692](https://github.com/den-run-ai/pystachy/pull/692) at `07951c99` and
[#735](https://github.com/den-run-ai/pystachy/pull/735) at `53c17bad`.
[#665](https://github.com/den-run-ai/pystachy/pull/665)'s test commit
`7bb4e7fce0ca83803bd06cb96fd97943b3b5191f` is an ancestor through #735,
not a third independent implementation merge. All three PRs were re-fetched as
merged and their history membership checked. #659's broad compiler flag did not land.

Changed-file selection covers function-import analysis/loading, closure/default/
decorator bindings, float power runtime behavior and affected math/API/port probes.
A build at `07951c99` completed before the power merge was incorporated; its log
is retained separately. The final **exact-`53c17bad` rebuild** again reaches
compiler/runtime fixed points: **630,274 / 18,851 IR lines**, CPython **3.13.16**,
LLVM **18.1.3**, Linux x86-64. Final native compiler SHA-256:
`f937af1d9089d961ee5bcc1abf99e777194333d17c9f578ab5e5c4c3d5a787d1`.
The old control is exact `946ce035`, binary SHA-256
`762659eac68d8f8462a53469ce1cba3c77e88f9f9150d0571bf8befb4549ccd7`.
Compiler identity and source identity are recorded separately.

### Measured correctness gains

| Probe | Previous main | Evaluated main / CPython |
|---|---|---|
| Conditional or not-yet-run imports in a function, including dotted imports | Compile-time rejection | Executes bound paths and raises the correct unbound-local error on unbound paths |
| Lambda reading a skipped conditional `import re` | Silently calls `re.escape` anyway | Raises CPython's free-variable `NameError` |
| Nested-function defaults and decorators reading a skipped import | Silently use the imported object | Raise CPython's `UnboundLocalError` |
| 50,000 seeded inputs × nine float-power expressions | AOT differs on 185 of 450,000 values; JIT matches | Both JIT and AOT match all 450,000 values exactly |

The four new import fixtures match their CPython recordings in both native modes.
Three were rejected by the old compiler; the nested-default/decorator fixture
compiled but silently produced incorrect results. A separate minimal lambda
program isolates the previously silent wrong result that the combined closure
fixture's earlier rejection would otherwise hide.

The power scan reuses [#656](https://github.com/den-run-ai/pystachy/issues/656)'s
deterministic seed 7 and exact nine-expression program. Old AOT differences by
expression are **38** for `x ** 2`, **44** for `x ** -1.0`, **65** for
`2.0 ** y`, and **38** for `math.pow(x, 2.0)`; the five other columns match.
New AOT and both JIT controls have zero differing values. Output shape is checked
before comparison; command, full source, output hashes and first differences are
retained. The runtime-input regression additionally checks built-in `pow`, signed
zero, infinities, NaN and the distinct zero-to-negative-power errors.

This is CPython parity, not a claim that libm returns the mathematically best
rounded answer. #735 keeps libm calls in only the two power helpers. Its author's
instruction-count result (55.0 M versus 9.6 M in a constant-power loop, with
unchanged counts on nine other benchmarks) is **PR evidence, not remeasured here**.
This audit makes no new speed-ratio claim: restoring libm rounding can cost work
in power-heavy loops.

### Retained validation and residual boundaries

- **210 focused checks over 170 cases**, **36 API checks over 18 programs**, and
  **12 adapted port checks over six programs** pass in the selected JIT/AOT
  and expected-rejection modes.
- Five import/power fixtures pass **10/10 each** with per-allocation program GC,
  optimizations disabled, and the CPython-hosted compiler.
- All **28 selected CPython recordings match**. The supplementary lambda,
  generator-expression, builtin-import and annotation programs and power scan
  have their own CPython references.
- Adapted pyperformance **1.14.0** `float`, `spectral_norm` and `nbody`
  smoke workloads match CPython in JIT and AOT. Small single-run timings on a
  shared host alongside other checks are correctness diagnostics, not comparable
  steady-state performance measurements.
- Runtime signature/effect check: **451 entries / 70 exception classes** agree.
- The compiler oracle compares **3,114 programs**; **only the four new import
  regressions differ**. Its raw exit status 1 is expected and retained, not
  reported as an all-identical pass. The stock tool displays the first three
  differences; old/new executions independently cover all four.

Fresh old/new JIT and AOT controls confirm remaining limits:

| Residual case | CPython | Both old and new native behavior |
|---|---|---|
| `list(x for x in re.findall(".", text))` after a conditional import | Outer iterable evaluated eagerly; bound path works | Compile-time rejection |
| Nested-def annotation `pmod.Thing` after a skipped import | Unbound-local error when the def executes | Annotation not runtime-evaluated; function returns normally |
| Conditional builtin `import math`, then `math.sqrt` | Unbound-local error on skipped path | Builtin binding is program-global, a documented deviation |

The generator-expression case is the existing [P2 review finding](https://github.com/den-run-ai/pystachy/pull/692#discussion_r4318716373),
acknowledged as pre-existing and deferred in the [maintainer response](https://github.com/den-run-ai/pystachy/pull/692#discussion_r4318726083).
The annotation limitation is already identified in #692. These are not new
regressions, and no duplicate issue or implementation change was made.

### Why the library count remains flat

Fresh isolated sweeps with `--metadata` retain **144/470 native imports** and
**146/470 stub-assisted imports**, **52 overlay exclusions**, the same **522
CPython source hashes**, no timeouts and no lost successes.

Five native first errors advance: `code`, `traceback`, `sre_constants`,
`wsgiref.validate` and `_pyrepl._threading_handler` no longer stop at
`warnings.py:220`'s conditional `re` import. They now stop at
`warnings.py:262`: `m` is bound both by an import and as a variable in
`_getcategory`. This is a removed blocker, not five newly working libraries.
The precise per-module deltas, including the separate stub-assisted sweep,
are retained in the evidence. Throwing stubs are not native implementations.

### Evidence and replay

[Machine-readable evidence](compatibility-2026-10-19-imports-power.json) includes
all selected fixture/source hashes, commands, output, old/new controls, sweep
metadata/deltas, the 450,000-value comparison, benchmark configuration and the
complete drivers. The full baseline result maps are referenced from the preserved
`compatibility-2026-10-19-json-followup.json`; only the five changed native
results need replacing when reconstructing that map.

Both implementation PR heads have **31 successful jobs across four workflows**:
[#692 CI](https://github.com/den-run-ai/pystachy/actions/runs/39314545384) at
`6cf83634`, and [#735 CI](https://github.com/den-run-ai/pystachy/actions/runs/39313591361)
at `edf06492`. Neither head equals the combined evaluated tree. These are
historical implementation CI results plus fresh combined-main selected checks,
not a new full local verification matrix or the audit PR's own checks.

For replay, extract `audit-692.py`, `audit-692-pow.py` and the assembler into
one parent directory and relocate their explicit checkout/toolchain paths.
The main driver creates `build/audit-692`. Run its `build`, `references`,
`controls`, `extra`, `checks`, `sweeps`, `oracle`, `benchmarks` and
`rtcheck` modes with pinned Python; run the power driver separately.
For re-aggregation, extract `implementation_ci` into
`build/audit-692/implementation-ci.json`, and the retained
`completed_pre_power_rebuild.command` into `build-before-power-merge.json`
in that directory. These two are historical records, not newly regenerated
measurement results. Refresh CI through GitHub for any new current-state claim.

No full local `make verify`, unmodified CPython regrtest, general PyPI sweep,
full upstream benchmark census or paired performance/memory comparison was run.
Compiled upstream-derived math cases, adapted ports, import compilation and hosted
compiler checks remain distinct. Existing minor/major adaptation assessments and
first-error limitations remain applicable. Dated reports and JSON are unchanged.

## 2026-10-19: field alias metadata, tuple returns and shared JIT runtime

Evaluated source: `4a1a29aac08a35f13c2ecbf933d507db083802d5`, following
`53c17bad9cd30120b8e0a3831797f3b22e9a9e87`. Fresh PR metadata and first-parent
history verify all three merges in this interval:

- [#724](https://github.com/den-run-ai/pystachy/pull/724), merge
  `eea79f3d0085d37b40cdda6f263227c9733f6e62`: declaring-class field alias metadata.
- [#727](https://github.com/den-run-ai/pystachy/pull/727), merge
  `547d502027888e5c7392e18a499844ce1bf017c1`: fresh fixed-tuple return values
  passed as aggregates where callers only read their slots; escaping calls stay boxed.
- [#730](https://github.com/den-run-ai/pystachy/pull/730), merge
  `4a1a29aac08a35f13c2ecbf933d507db083802d5`: Linux JIT loads a cached shared
  runtime, with object-callback registration and object-file fallback.

These are execution/compiler improvements, not new native library implementations.
Changed compiler, driver, cache and IR-contract files selected field/inheritance,
tuple/unpack, property, exception/callback, collections/operator and affected port
probes. The #491/#616 coordination comments and all three PR review discussions
were read. No implementation branch was edited or PR merged by this audit.

### Correctness and code-generation boundaries

Fresh CPython **3.13.16** / LLVM **18.1.3** rebuild reaches compiler/runtime fixed
points at **634,597 / 18,851 IR lines**. Compiler SHA-256:
`d4f9951fa0387182db43d529fc9ab5d9c7ee294fb97208dc610bbdb1077d2f3c`.
The previous-main control binary remains separately identified in the evidence.

- **283 focused checks** pass: 89 executed cases in JIT/AOT and 105 expected
  rejections. This is not 283 newly supported APIs.
- **38 API checks** over 19 programs and **12 adapted-port checks** over six
  ordered-set/sortedcontainers/jdcal programs pass. **34 CPython recordings** match.
- The field-alias, tuple-return and callback regressions pass **6/6 each** with
  program GC stress, all optimizations disabled, only field TBAA disabled, only
  tuple returns disabled, and the CPython-hosted compiler. Explicit MCJIT passes
  **3/3**; the separate native/hosted JIT-boundary probe checks ORC and MCJIT,
  callback unwinding, argument handling, collection and signal status.
- The six recently merged Unicode-replacement, conditional-import and power
  fixtures pass **12/12 JIT/AOT checks with GC stress** on the combined tree.
- **138 FFI/embedding/extension checks** pass. This exercises the new shared
  runtime beside libpython, but is explicit CPython embedding, not native NumPy
  or general PyPI compatibility.
- **1,434 IR programs** pass the internal checker and LLVM assembler, including
  the new field-tag and tuple-allocation contracts. With
  `PYSTACHY_OPT=-fieldtbaa,-tupleret` on the new compiler only, **all 3,118 corpus
  programs** have identical IR, diagnostics and exit status to the previous
  compiler. This off-control isolates the new optimizations; it does not claim
  that enabled optimized IR is unchanged.
- Runtime declarations/effects agree: **451 entries / 70 exception classes**.
- Four adapted benchmark smoke programs (`float`, `nbody`, `chaos`, `regex_dna`)
  match CPython in JIT/AOT. Their smoke timings overlap other checks and are not
  used as speedup evidence.

No new correctness regression was found in these selected checks. Existing
first-error and minor/major adaptation limits are not reclassified by passing
compiler optimizations.

### Cache behavior and measured performance

`make test-cache` passes **65 native + 67 hosted checks**, including `.so`
publication, recreation from an existing `.o`, invalidation, failed/killed builds,
and fallback to the object when the cached library has no execute bits. The latter
rechecks the condition identified in #730's review. This audit did **not** remount
a filesystem `noexec`; that separate experiment remains attributed to the author.

After all other owned checks finished, timings used CPU 0 on a shared AMD EPYC
9V74 host (9 visible CPUs, cgroup quota 8 CPU equivalents), LLVM 18.1.3, alternating
paired order. Load averages were 2.89/3.92/2.40 before and 2.97/3.91/2.41 after.
Outputs match pinned CPython exactly, including both JIT and AOT variants.

| Workload / comparison | Rounds | Control median | Enabled/current median | Interpretation |
|---|---:|---:|---:|---|
| `bench/nbody.py`, 500,000 steps, AOT; same compiler with `-fieldtbaa` vs default | 9 | 46.35 ms | 39.94 ms | 13.8% lower median; samples overlap and two paired rounds reverse, so magnitude remains advisory |
| Adapted `barnes_hut.py 1 10 500`, AOT; same compiler with `-tupleret` vs default | 9 | 22.70 ms | 13.94 ms | 38.6% lower median; every paired sample improves |
| `print(1)`, warmed JIT; prior `53c17bad` compiler vs current combined main | 15 | 58.56 ms | 37.29 ms | 36.3% lower median; every paired sample improves |

AOT measurements include executable startup but exclude compilation. The JIT row
includes process startup, program compilation and execution, with runtime caches
warmed twice; it is not steady-state Python execution. It compares the complete
three-merge batch, although the tiny program has no object fields or tuple-return
optimization sites. The benchmark smoke timings above are excluded from this table.
These are bounded results, not general compiler or library speed claims.

Separate `PYSTACHY_GC=stats` runs report **Barnes-Hut managed-heap peak 21.1 →
2.0 MiB**, about **90.5% lower**, when tuple-return optimization is enabled.
Both perform zero collections for this input. N-body remains **1.0 MiB / zero
collections** with field metadata on or off. These are rounded managed-heap
statistics, not process RSS or a general memory-saving guarantee. Raw stderr,
all timing samples, flags, commands and source hashes are retained.

### Import accounting, CI and replay

Isolated native and stub-assisted sweeps with `--metadata` retain **144/470** and
**146/470**, respectively: same **522 CPython source hashes**, **52 exclusions**,
zero timeouts, zero lost successes and **zero changed first errors** against
`53c17bad`. The five first-error advances in the previous checkpoint remain in
place. Reconstruct prior result maps by applying the deltas in
`compatibility-2026-10-19-imports-power.json` to the full maps in
`compatibility-2026-10-19-json-followup.json`; this checkpoint adds no deltas.
Throwing C-module stubs are diagnostic aids, not working native modules.

All three implementation PR heads have **31 successful jobs across four
workflows**, including the verification gate:
[#724 CI](https://github.com/den-run-ai/pystachy/actions/runs/39315556899),
[#727 CI](https://github.com/den-run-ai/pystachy/actions/runs/39315562155), and
[#730 CI](https://github.com/den-run-ai/pystachy/actions/runs/39315568585).
Heads `8776f71b`, `00e60738` and `7ab0cefd` predate the subsequent Unicode,
binding and power changes, so **none equals the combined evaluated tree**.
Local combined-main checks complement this historical CI; no new full local
`make verify`, unmodified CPython regrtest or broad PyPI sweep was run.

[Machine-readable evidence](compatibility-2026-10-19-field-tuples.json) includes
selection/fixture hashes, toolchain and compiler identities, full command outputs,
import metadata, CI jobs, benchmark records and complete reproduction drivers.
To replay, extract the three `audit-724*.py` scripts, relocate explicit paths to
the evaluated/previous checkouts and toolchain, and use pinned Python. The main
driver creates `build/audit-724`; run `build`, `references`, `checks`, `integration`,
`sweeps`, `ir`, `oracle`, `cache`, `jitprobe`, `ffi`, `benchmarks` and `rtcheck`.
Run the performance driver only after other jobs finish. For aggregation, restore
the retained `implementation_ci` object to `build/audit-724/implementation-ci.json`
or fetch fresh GitHub results; the stored object is historical evidence. All
dated baseline reports and JSON remain unchanged. Existing trackers
[#701](https://github.com/den-run-ai/pystachy/issues/701),
[#703](https://github.com/den-run-ai/pystachy/issues/703) and
[#704](https://github.com/den-run-ai/pystachy/issues/704) cover this work;
no new issue is warranted by these measurements.

## 2026-10-19: empty-string exception representations and binding diagnostics

Evaluated source: `e33c560e801af86879727fd5f99f5981b84d5046`, after
`4a1a29aac08a35f13c2ecbf933d507db083802d5`. Evaluation completed before advancing
the latest-evaluated marker; the previous audit is now merged as #669.

Fresh PR metadata and ancestry checks identify the intervening merges:

- [#729](https://github.com/den-run-ai/pystachy/pull/729),
  `d34a2260e109750068b0468669b6b938b2337c56`: preserve the empty string argument
  in builtin exception `repr`, distinguishing `ValueError('')` from `ValueError()`.
- [#726](https://github.com/den-run-ai/pystachy/pull/726),
  `e33c560e801af86879727fd5f99f5981b84d5046`: locate binding-conflict diagnostics
  at the assignment, including a nested function's declared-global assignment.
- #734 (`b040f45e`) changes only three CI setup workflows. #669 (`b83c4e73`)
  merges the previous audit reports. Neither adds compiler/runtime/library behavior;
  the audit's own documentation merge is not treated as another implementation gain.

The #491/#616 coordination comments and both implementation PR discussions were
read. In particular, #726's earlier nested-global review finding is fixed in its
merged `fe96a14` head. This audit changes no implementation branch and merges no PR.

### Measured behavior

Fresh CPython **3.13.16** / LLVM **18.1.3** rebuild reaches compiler/runtime
three-stage fixed points at **635,430 / 18,851 IR lines**. Compiler SHA-256:
`348ae135b80e951892be480572a8b6e8c45700fb9d4d4803d3e80160aad9b413`.
The previous binary was built from `4a1a29aa`; the current binary was built from
the exact evaluated source above. Library/runtime sources are unchanged by these
two implementation merges.

- **1,170 output cases across 65 builtin exception names match CPython** in each
  JIT/AOT mode with program GC stress. The old compiler differs on **192 cases in
  each mode**; the new one differs on zero. Cases include constant/dynamic empty
  strings, no arguments, nonempty strings, quotes, a backslash, newline, NUL,
  Unicode, and raising/catching each exception. This is a bounded API comparison,
  not CPython's upstream exception suite; aliases are counted as separate names.
- **185 focused checks** pass over 105 fixtures: 80 executed JIT/AOT programs
  and 25 expected rejections. **2 contextlib API checks**, **12 adapted-port
  checks** over six ordered-set/sortedcontainers/jdcal programs, and **8 CPython
  recordings** pass. These validation views must not be added into a count of
  supported libraries or treated as whole-package support.
- The new exception fixture passes **2/2** with GC stress and **2/2** with all
  optimizations disabled. The CPython-hosted compiler passes **27 checks**: the
  fixture in JIT/AOT plus the 25 binding rejections. These are hosted-compiler
  checks, not unmodified upstream suites.
- The previous compiler fails both executions of the new exception fixture and
  all five exact-location regressions. New diagnostics point to lines **7, 7,
  11, 13 and 15**, instead of **6, 5, 12, 17 and 20**. Rejection policy is not
  relaxed: monkey-patching module functions and conflicting global bindings
  remain unsupported.
- Runtime declaration/effect checks agree for **451 entries / 70 exception
  classes**. No new runtime function or allocation is introduced by #729.
- The internal IR checker and LLVM assembler accept **1,435 programs**. Across
  **3,122 corpus programs**, old/new compiler exit statuses are identical; only
  the five intended diagnostic locations differ. **2,906** programs are identical
  in IR, messages and exit status; **211** have changed IR. The evidence retains
  hashes for changed IR and selected 35-line excerpts, not an exhaustive semantic proof.
  The compiler's own program and runtime IR are identical between old/new compilers
  when both compile the current sources.
- All six benchmarks whose IR changes pass small CPython/JIT/AOT correctness
  controls: `chaos`, `hexiom`, `regex_dna`, `regex_effbot`, `regex_v8`, and
  `json_records` (exact checksum **256384**). The first five are adapted workloads;
  these are not unmodified upstream suites. Recorded smoke timings overlap other
  checks and are not used for a performance comparison.

Isolated `--metadata` sweeps retain **144/470 native imports** and **146/470
stub-assisted imports**, using the same 522-file CPython inventory and 52 overlay
exclusions. Both result maps are unchanged, including first errors: no lost
successes or timeouts. Throwing stubs remain diagnostic aids, not native modules.

### Scope and replay

Both historical implementation PR heads have **31 successful jobs across four
workflows**, including the verification gate:
[#729 CI](https://github.com/den-run-ai/pystachy/actions/runs/39296976013) and
[#726 CI](https://github.com/den-run-ai/pystachy/actions/runs/39306456185).
These heads predate later main changes; neither is the combined evaluated tree.
Fresh local selected checks complement, but do not replace, a full current-tree
verification matrix.

No full local `make verify`, unmodified CPython regrtest, broad PyPI census or
dedicated performance/memory comparison was run. Existing minor/major adaptation and
first-error limitations remain. The initial audit-driver selector encountered
a deliberately non-UTF8 fixture before starting any build/test; searching bytes
fixed the selector, and the restarted run is the measured run. That setup failure
is retained separately from implementation results.

[Machine-readable evidence](compatibility-2026-10-19-exception-diagnostics.json)
retains source/compiler identities, fixtures, commands, outputs, comparisons and
replay scripts. Extract `audit-729.py` and `audit-729-assemble.py`, relocate their
explicit paths, then run the driver modes `build`, `references`, `checks`,
`differential`, `old-control`, `rtcheck`, `sweeps`, `oracle`, `ir`, `benchmarks`
and `json-smoke` with pinned Python. `old-control` intentionally returns 1 and
demonstrates the prior bug.
Restore the historical `implementation_ci` object to
`build/audit-729/implementation-ci.json` before aggregation, or retrieve fresh CI
when making a current-state claim. All dated baseline reports/JSON are preserved.
Repeated differential stdout is stored once in `stdout_blobs`, keyed by SHA-256;
each command names its output hash. The oracle input-inventory digest can be
reconstructed by the retained driver on the exact source revision.

## 2026-10-19: unsupported generic annotations (#697)

Evaluated `ca7688dd75b5385dea42a0054566a2033e417505`, the sole main merge after
`e33c560e801af86879727fd5f99f5981b84d5046`. Fresh metadata and ancestry confirm
[#697](https://github.com/den-run-ai/pystachy/pull/697) merged into main. Read its
review discussion and #491/#616 coordination before testing; implementation branches
were not changed. This checkpoint is completed, independently of the next merge.

- Rebuilt with CPython **3.13.16** and LLVM **18.1.3**: compiler/runtime fixed points
  **635,461 / 18,851 IR lines**. Compiler SHA-256:
  `e1be7b6de032c77ffd82b7e9d11de299dbef06e6f34f1d07b0e99c359b76e9ee`.
- **142 focused checks**, **16 functools API checks**, **8 adapted ordered-set /
  sortedcontainers checks**, and **5 hosted-compiler checks** pass. CPython recordings
  match **47/47** programs. The selected syntax sweep agrees on **102/102** files.
- Independent direct, module-qualified, aliased and quoted `Box[int]` annotations
  previously crash with `KeyError: 'boxmod$Box'`. Both rebuilt native and hosted
  compilers now report the unsupported decorated special method with file/line.
  All six independent programs execute under CPython; Pystachy still rejects them.
  Bare `Box` already had this diagnostic. `Annotated[Box[int], "metadata"]` keeps
  its earlier `unsupported type annotation` error. This is diagnostic coverage,
  **not new support for decorated generic classes**.
- Old/new comparison over **3,123 corpus programs** finds **3,122 identical** in
  IR/messages/status. The sole difference is the new rejection fixture's diagnostic;
  all exit statuses and emitted IR are unchanged. No newly affected benchmark was
  selected. No performance claim follows from this comparison.
- Isolated `--metadata` sweeps remain **144/470 native** and **146/470 stub-assisted**:
  identical result maps, first errors, 522 CPython source hashes and 52 exclusions;
  no lost successes or timeouts. Stubs remain diagnostic aids.

Initial CPython references matched 45/47; the two remaining fixtures failed because
`typing_extensions` was missing. Repeating all 47 with an existing **4.16.0** copy on
explicit `PYTHONPATH` passed. Its file hash and the failed attempt are retained; no
dependency was installed and no implementation failure is inferred from that setup.

The historical implementation head `6399d46c` has **31 successful jobs** across
CI, Installation, Packages and Lint ([CI](https://github.com/den-run-ai/pystachy/actions/runs/39221083750)).
It is not the combined evaluated tree. No full local `make verify`, unmodified
CPython regrtest, broad PyPI census or performance/memory experiment was run.
Existing adaptation and first-error limitations remain.

[Evidence and replay scripts](compatibility-2026-10-19-generic-diagnostics.json)
retain commands, complete outputs, fixtures, identities, CI and comparisons. Extract
`audit-697.py` / `audit-697-assemble.py`, relocate explicit paths, and run `build`,
`references`, `checks`, `variants`, `oracle` and `sweeps`. Keep the initial reference
failure as `references-initial.json` and restore historical `implementation-ci.json`
from the evidence for aggregation. The assembler compares the previous #729 sweep
maps (replay that checkpoint or reconstruct its documented baseline/deltas). All
dated baseline reports and JSON are preserved.

## 2026-10-19: exception class values (#721)

Evaluated `3609a5f0830f7997f8b2f6e6463313e3aea9e091`, the sole main merge after
the completed #697 checkpoint above. Fresh PR metadata and git ancestry confirm
[#721](https://github.com/den-run-ai/pystachy/pull/721) merged. Read its review
discussion and the #491/#616 coordination records; no implementation branch was
modified. Both checkpoints are published together in the existing audit #743.

**Measured progress is executable behavior, not additional importable modules.**

- Fresh CPython **3.13.16** / LLVM **18.1.3** bootstrap reaches identical compiler
  and runtime fixed points of **644,955 / 18,851 IR lines**. Compiler SHA-256:
  `945034c7c3f8d7d2780eb578005076a1bcc687596f11647876d9d180f7891d72`.
- **406 focused checks**, **14 contextlib/I/O API checks**, **14 adapted-port checks**
  (ordered-set, sortedcontainers, tomli-w), and **2 additional generic-alias checks**
  pass. The hosted compiler passes **178 checks**. The 36 selected positive
  programs pass **72 JIT/AOT checks under per-allocation GC** and **72 with
  optimizations disabled**. CPython reference recordings match **50/50**.
- An independent **397-line matrix** across 18 builtin/user exception-class entries
  matches CPython under GC-stress JIT/AOT and optimization-off JIT/AOT: class values,
  identity, hashing, dict/set keys, construction, type metadata, 18-by-18 subclass
  and instance relations, and stored `contextlib.suppress` managers. The previous
  compiler rejects the program. **Minor adaptation:** nested tuples are assigned
  to a local variable, not supplied as direct tuple displays (see #748 below).
- Independent old/new controls confirm two corrected results: `raise E from cause()`
  evaluates the cause before constructing E (old output reversed that order;
  [#739](https://github.com/den-run-ai/pystachy/issues/739)), and an alias of a
  user-defined `len` returns **99**, not the builtin's **3**. New results match
  CPython in all four execution configurations. Old-control outputs are retained.
- The retained **1,170-output / 65-builtin-exception** string/repr matrix still
  matches CPython in both old/new JIT and AOT. This is preservation of #729's gain,
  not another newly fixed set of 1,170 cases.
- The IR checker and LLVM assembler accept **1,458 programs**; runtime signature,
  coverage and effect checks pass (**457 entries, 70 exception classes, 171 functions**).
- Old/new comparison of **3,148 current-source corpus programs** finds **3,110
  identical** in IR/messages/status, **22 rejected-to-accepted** programs, **12
  already-accepted programs with changed IR**, and **4 rejection diagnostics changed**.
  No previously accepted program becomes rejected. Three of the 22 transitions are
  explicit deviation fixtures, so this is not a count of 22 CPython-compatible
  libraries. All changed-IR accepted tests are covered by the selected checks.
  No benchmark IR changed; no additional benchmark execution was selected.
- Both isolated `--metadata` import sweeps have **zero result/first-error deltas**:
  **144/470 native**, **146/470 stub-assisted**, the same **522** source hashes and
  **52** overlay exclusions, no lost successes and no timeouts. The unchanged import
  count does not measure the new operations inside already-importable modules.

### Confirmed boundaries and failed attempts

[**#748**](https://github.com/den-run-ai/pystachy/issues/748) records a newly exposed
compile rejection: `issubclass(ValueError, ((b,),))` and
`isinstance(ValueError("x"), ((b,),))`, with `b: type[BaseException]`, work in CPython
but fail in the rebuilt compiler. Assigning `nested = ((b,),)` first makes both
programs match CPython in JIT/AOT. Four minimal programs and the original failed
matrix attempt are retained. This is a gap in the new support, **not a regression
from previously executing code**; the old compiler rejects every variant.

Known [#744](https://github.com/den-run-ai/pystachy/issues/744), comparing
`type(E) is type` for an exception class object, is independently reconfirmed and
reuses its existing tracker. Dynamic construction with an incompatible initializer
argument type, calling the NoneType class object, and SyntaxError-family argument
truth evaluation retain the PR's explicit deviations. Variable except clauses,
general class objects and all exception attributes are not claimed as supported.

The initial raise-order probe also read `e.__cause__` on a user-defined E; both old
and new compilers reject that attribute. The narrowed order-only control passes
and demonstrates the ordering fix. The original failed attempt is retained rather
than counted as an implementation regression or as passing attribute coverage.

Historical implementation head `f8b74dcf` has **31 successful jobs** across four
workflows ([CI](https://github.com/den-run-ai/pystachy/actions/runs/39333947268)); it
does not equal the combined evaluated main tree or this audit PR's head. No full
local `make verify`, unmodified CPython regrtest, broad PyPI census or dedicated
performance/memory experiment was run. Timings overlap other checks on a shared
host and are not performance evidence. Native imports, executed APIs, adapted ports,
hosted compiler checks and actual upstream suites remain distinct; historical
minor/major adaptation and first-error limits remain.

[Exact evidence and replay scripts](compatibility-2026-10-19-exception-classes.json)
retain identities, commands, fixtures, outputs, import deltas, oracle differences,
controls, failures and CI. Extract the four `audit-721*.py` scripts and relocate
explicit paths. Run the main driver's `build`, `references`, `checks`, `extra`,
`oracle`, `sweeps`, `ir`, `rtcheck` and `differential` modes, then the independent
probe and nested-tuple drivers. Preserve the two historical failed-attempt records
and implementation-CI snapshot before aggregation. Reconstruct previous sweep maps
from the linked #729/#697 evidence or replay those checkpoints. Repeated stdout
is stored once in `stdout_blobs`, keyed by SHA-256; the oracle inventory digest is
reconstructed from the exact revision. No dated baseline report/JSON was changed.

## 2026-10-19: shared CI bootstrap harness (#741)

Evaluated `552d7301eee771a61759b601867d5bc9b40eef28`, the sole first-parent merge
after `3609a5f0830f7997f8b2f6e6463313e3aea9e091`. Fresh metadata and git ancestry
confirm [#741](https://github.com/den-run-ai/pystachy/pull/741) merged. Its seven
changed paths are CI workflow, verification harness/bundle/gate tools and tests,
and testing documentation. Compiler, runtime, Makefile, library and port sources
are byte-identical to the previous evaluated revision. Read the PR review and
#491/#616 coordination; the CI implementation branch remains untouched.

Affected retained checks on a clean detached checkout, CPython **3.13.16**:

```sh
/root/.local/bin/python3.13 -m unittest discover -s tools -p 'test_*verif*.py' -v
sh -n tests/verify.sh
tests/verify.sh --list
git diff --exit-code 3609a5f0830f7997f8b2f6e6463313e3aea9e091 HEAD -- src runtime.c runtime.py pystachy.py Makefile lib ports
```

Results: **47 tests passed, 0 failures** (`Ran 47 tests in 36.819s`, `OK`);
shell syntax and source-equality checks exit 0. The plan retains all **23 consumer
groups** and adds a bootstrap-only producer. Tests cover complete suite counts,
GC/UBSan modes, failed/missing reports, bundle provenance, source/toolchain/run
identity, corrupt payloads, fixed-point evidence, symlinks and executable modes.
These are harness unit/contract tests, not 47 newly compatible Python programs.

Replay inputs are pinned by the exact source revision above. Key SHA-256 hashes:

| Input | SHA-256 |
|---|---|
| `tools/verification_bootstrap.py` | `2df4b2d28d19331abd5ddaba95584c3bcfb7ecd8521086fd26cd65605030a8b5` |
| `tools/test_verification_bootstrap.py` | `f2b1dcab2a92e3de275944cc79d2dbbfe096352a7950f6e995f965582674f2a3` |
| `tools/merge_verification.py` | `387d49151a87c1c4b4acbaa7f09d2491d23bddd2d9ee4c2f64dba77065df0f44` |
| `tools/test_merge_verification.py` | `b4b688d2ee208c7a808b6f0d9313fbf3834120934bdae55bfaaeec43dd5d492c` |
| `tests/verify.sh` | `ba478075afae4096c3330385dc5cdd41193812eaa65633a1dccc2d151ab1a24a` |

No compiler was rebuilt or executed for this tooling-only checkpoint; LLVM was not
needed by these mocked harness tests. The last measured compiler remains built
from **3609a5f0**, SHA-256
`945034c7c3f8d7d2780eb578005076a1bcc687596f11647876d9d180f7891d72`, using LLVM **18.1.3**.
The previous **144/470 native / 146/470 stub-assisted** import counts are carried
forward by source identity, **not freshly rerun**. APIs, adapted ports, benchmarks
and full upstream suites were not repeated. No new compatibility or performance
gain is inferred from this CI-only change; #741's reported hosted timing comparison
is separate evidence and was not independently remeasured here. All historical
reports/JSON and adaptation/first-error limitations remain unchanged.

## 2026-10-19: native opcode metadata and stack effects (#686)

Evaluated [main `b7e869f8e324a30c59cbe36720a0f4d2e9f4f9c1`](https://github.com/den-run-ai/pystachy/commit/b7e869f8e324a30c59cbe36720a0f4d2e9f4f9c1),
the sole first-parent merge after `552d7301eee771a61759b601867d5bc9b40eef28`.
Fresh metadata and git ancestry confirm [#686](https://github.com/den-run-ai/pystachy/pull/686)
merged. Read its completed review and #491/#616 coordination before measuring.
The 21 changed paths add `_opcode`'s native stand-in, generated CPython tables,
`opcode`/`_opcode_metadata`, six fixtures, verification tools and documentation;
the only compiler change registers the stand-in. No implementation branch was edited.

Rebuilt with **CPython 3.13.16 / LLVM 18.1.3**, reaching compiler/runtime fixed
points **644,960 / 18,851 IR lines**. Compiler source is the evaluated main SHA;
executable SHA-256 is
`12288231f46f77db1034d1afd59647fabe13e61452fd230577bbc6223897ff84`.
The comparison executable remains built from `3609a5f0830f7997f8b2f6e6463313e3aea9e091`,
SHA-256 `945034c7c3f8d7d2780eb578005076a1bcc687596f11647876d9d180f7891d72`;
its compiler/runtime/lib/port sources are byte-identical at the preceding #741
checkpoint. Compiler identity and checkout revision are not conflated.

### Executed behavior and adaptation

| Measurement layer | Observed result |
|---|---|
| Six retained opcode fixtures | **9/9 checks pass** in each of native JIT/AOT, program GC stress, optimization-off and CPython-hosted compiler modes. Each group includes two positive API/adapted-upstream programs, one documented-deviation program and three expected compile-time rejections. |
| CPython reference executions | Both positive fixture outputs match their retained recordings exactly. The library test exercises **20,400** stack-effect combinations plus opcode predicates, exported tables, overflow boundaries, list freshness and executor errors. |
| Independent native differential | **29,890 output lines** match CPython exactly in each GC-stressed JIT/AOT and optimization-off JIT/AOT run. Covers 610 opcode integers, 16 signed-64-bit/boundary operands, three jump settings, flags and exact error text. |
| Port implementation under CPython | `tools/opcode_check.py`: **1,431,973 checks, zero differences** against CPython's C `_opcode`. This runs the port as Python, not native code. |
| Table regeneration | `tools/opcode_tables.py`: **2,708,100 checks** against the installed pinned CPython headers; generated database is byte-identical to the committed file. Header/database hashes are retained. This is separate from native API execution. |
| Retained corpus comparison | **3,154 programs, 3,148 identical** in normalized IR/messages/exit status. Only the six new opcode fixtures differ: two positive programs and one explicit deviation move from rejection to acceptance; three rejection fixtures advance to intended argument-type errors. No accepted-to-rejected transitions. |

All **31 adapted port probes** and **32 benchmark sources** in that comparison
retain identical IR/results; no affected port/benchmark execution was selected
beyond the new opcode workload. This is an IR/control-flow selection result, not
a fresh performance measurement or a complete semantic proof for arbitrary callers.

`_opcode_metadata.py` remains an unmodified CPython file. `opcode.py` needs the
minor `hasjabs: list[int] = []` annotation; the `_opcode` stand-in itself is a
native reimplementation, not unmodified extension support. The upstream-derived
fixture replaces unittest's runner/assertions and `dis` dependencies, rewrites
one filter/lambda and omits specified bool-type/Py_STATS assertions. It is an
**adapted upstream test**, not an unmodified CPython suite or working `unittest`.

The APIs describe **CPython 3.13 bytecode metadata**, not Pystachy bytecode.
`ENABLE_SPECIALIZATION = 0` remains an explicit deviation. No code-object/executor
support is claimed; representable non-code executor arguments raise errors.
Float operands and integer `jump` values reach documented compile-time rejections.
The documented bool-as-int and function-type boundaries remain outside the
positive scope; they were not newly expanded by this audit.

### Import accounting and remaining blockers

Fresh isolated sweeps use `--metadata`, two workers, the same overlay policy and
all **522 unchanged CPython source hashes**. `opcode` and `_opcode_metadata` now
come from `lib/`, increasing exclusions **52 → 54** and reducing the included
denominator **470 → 468**. `_opcode_metadata` was previously an `OK` source import;
its removal from the sweep explains the one lower raw success count. `opcode`
was previously rejected and is now directly executed by the checks above.
Neither transition is a lost working module. `_opcode`, a C-module name outside
the 522-source inventory, is measured separately by those API programs.

Native sweep: **143/468**, previously **144/470**, with **zero timeouts** and no
previous success becoming an error. There are **25 map changes**: the two overlay
exclusions plus **23 advanced first errors**. `dis` now stops at `types.MethodType`;
the other 22, including `inspect`, `unittest` and its submodules, `doctest`,
`pdb` and `modulefinder`, stop at `_io`. These remain blocked libraries, not
23 new compatible modules. Exact per-module native/stub deltas and provenance
are in the evidence; throwing C-module stubs are not native implementations.

Stub-assisted sweep: **145/468**, previously **146/470**, with **zero timeouts**.
Its four map changes are the two exclusions plus `dis` and `modulefinder`
advancing from opcode-table inference to `types.MethodType`. The extra two
stub-assisted successes are unchanged; no new success is credited to a throwing
stub. The same underlying source inventory and two newly supplied overlay modules
explain both sweeps' denominator changes.

### Reproduction and scope

`make check-recordings PY=/workspace/scratch/cca24c0adfdd/devtools/bin/python`
passes: **1,312 recordings, 83 deviations, 10 pinned lib files, zero failures**;
the six pinned AskMe files also verify. This dev interpreter is the same
**CPython 3.13.16**, with **typing_extensions 4.16.0** (hash retained).
Three initial attempts each report eight checks failing across four unrelated
typing-extensions fixtures: the base interpreter lacks the dependency, the
recording script clears inherited PYTHONPATH, and the Makefile derives PYTHON
from PY. Selecting the dev interpreter via **PY** resolves the setup failures.
All failed command outputs remain explicit in the evidence; no fixture was
rewritten to hide them.

From the clean evaluated checkout, with the explicit toolchain paths in the
embedded driver:

```sh
make PY=/root/.local/bin/python3.13
tests/run.sh ./pystachy 'jit aot' tests/lib_opcode.py tests/upstream_opcode.py tests/deviations/lib_opcode_specialization.py tests/errors/lib_opcode_*.py
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' tests/lib_opcode.py tests/upstream_opcode.py tests/deviations/lib_opcode_specialization.py tests/errors/lib_opcode_*.py
PYSTACHY_OPT=-all tests/run.sh ./pystachy 'jit aot' tests/lib_opcode.py tests/upstream_opcode.py tests/deviations/lib_opcode_specialization.py tests/errors/lib_opcode_*.py
tests/run.sh '/root/.local/bin/python3.13 -m pystachy' 'jit aot' tests/lib_opcode.py tests/upstream_opcode.py tests/deviations/lib_opcode_specialization.py tests/errors/lib_opcode_*.py
/root/.local/bin/python3.13 -I tools/opcode_check.py
```

[Evidence and replay scripts](compatibility-2026-10-19-opcode.json) retain exact
commands, environments, source/fixture/header hashes, regenerated-table identity,
the independent matrix, previous/new oracle results and both import metadata/maps'
deltas. Extract `audit-686.py` and `audit-686-assemble.py`, relocate explicit paths,
run `build`, `references`, `checks`, `port-check`, `tables`, `matrix`, `oracle`,
`sweeps` and `recordings-final`, then aggregate. The historical failed recording
attempts and implementation-CI snapshot must also be retained. Long stdout is
stored once as gzip+base64 in `stdout_blobs`, keyed by SHA-256 of decoded UTF-8
bytes. The oracle inventory digest is reconstructed from the exact revision.

Historical implementation-head `7269102b055abbea578dd82ad0aa5232d2f92ded` has four
successful workflows ([CI](https://github.com/den-run-ai/pystachy/actions/runs/39202974370),
Lint, Packages and Installation), freshly read. That is not the combined main or
audit head. No full local `make verify`, unmodified CPython regrtest, broad PyPI or
NumPy census, or dedicated memory/performance experiment was run. Shared-host
timings overlap other checks and establish no speedup/regression. No new uncovered
bug was confirmed; no duplicate issue was filed. Dated baseline reports and JSON
are unchanged.

## 2026-10-19: tuple-return regression coverage (#747)

Evaluated [main `837843bcc82ae088ad92b61c8fdb0e6eeb37c2ed`](https://github.com/den-run-ai/pystachy/commit/837843bcc82ae088ad92b61c8fdb0e6eeb37c2ed),
the only first-parent merge after `b7e869f8`. Fresh metadata and ancestry confirm
[#747](https://github.com/den-run-ai/pystachy/pull/747) merged. Its four added files
are the tuple-return closure/starred-target/generator differential test, recording,
IR probe and allocation-call contract. Compiler, runtime, library, ports, tools,
Makefile and test harness are byte-identical to the preceding evaluated revision.

The verified **b7e869f8** compiler was reused, SHA-256
`12288231f46f77db1034d1afd59647fabe13e61452fd230577bbc6223897ff84`, with
**CPython 3.13.16 / LLVM 18.1.3** and `PYSTACHY_HOME` set to the clean **837843bc**
checkout. No rebuild is needed for this tests-only merge. Read #491/#616 and the
PR review: its P2 finding noted that differential output alone cannot prove
by-value lowering; `4310685` added the IR contract. The checks below independently
validate that response, not a new completed bot review.

Affected retained validation:

| Check | Result |
|---|---|
| New `tuple_return_closures.py` plus retained `tuple_return_values.py` | **4/4 checks pass** in each of native JIT/AOT, GC stress, optimization-off, tuple-return optimization disabled, and hosted compiler modes: **20 checks total**. |
| CPython reference executions | **2/2 outputs** exactly match retained recordings with arguments `a1 a2`. |
| New and existing tuple-return IR contracts | **2/2 programs** pass the compiler IR checker, exact runtime-call contracts and LLVM assembler. By-value bodies have no tuple allocation; wrappers retain allocation. |
| Negative contract control | A scratch copy omitting `@v.f.three` is correctly rejected, exit 1: `OTHER CALLS`, extra `@v.f.three: pys_raise`. No tracked fixture was modified. |
| Optimization-disabled IR control | Compiles successfully with `PYSTACHY_OPT=-tupleret` and contains no `@v.` bodies, while the differential execution still matches CPython. |

Commands use `COMPILER=/workspace/scratch/3ba735e28fa7/pystachy-audit-686/pystachy`
and the explicit environment in the evidence. Run from the evaluated checkout:

```sh
tests/run.sh "$COMPILER" 'jit aot' tests/tuple_return_closures.py tests/tuple_return_values.py
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh "$COMPILER" 'jit aot' tests/tuple_return_closures.py tests/tuple_return_values.py
PYSTACHY_OPT=-all tests/run.sh "$COMPILER" 'jit aot' tests/tuple_return_closures.py tests/tuple_return_values.py
PYSTACHY_OPT=-tupleret tests/run.sh "$COMPILER" 'jit aot' tests/tuple_return_closures.py tests/tuple_return_values.py
tests/run.sh '/root/.local/bin/python3.13 -m pystachy' 'jit aot' tests/tuple_return_closures.py tests/tuple_return_values.py
tools/check_ir.sh "$COMPILER" tests/ir/tuple_return_closures.py tests/ir/tuple_return.py
```

[Exact evidence and replay scripts](compatibility-2026-10-19-tuple-return-coverage.json)
retain command outputs, fixture hashes, compiler/source identities and the positive
and negative controls. Extract and relocate the two `audit-747*.py` scripts, run
the driver, then aggregate. No new implementation behavior, library coverage,
speedup or heap-size measurement is claimed. The preceding **143/468 native /
145/468 stub-assisted** import results, **522-source inventory / 54 exclusions**,
are carried forward by implementation identity, **not rerun**. Unrelated API,
port and benchmark suites, full `make verify` and unmodified upstream suites were
not repeated. Dated reports/JSON, adaptation assessments and first-error limits
remain unchanged; no new issue was needed.

## 2026-10-19: compile-time sys installation prefixes (#719)

Evaluated [main `633cdf1aeceae65cb9fa94d420ae50562e6c1b7a`](https://github.com/den-run-ai/pystachy/commit/633cdf1aeceae65cb9fa94d420ae50562e6c1b7a),
the only first-parent merge after `837843bc`. Fresh metadata and ancestry confirm
[#719](https://github.com/den-run-ai/pystachy/pull/719) merged. Four compiler files
add the prefix attributes and canonicalize the compiler's home; the other changes
are the compatibility explanation and one test/recording pair. Runtime, library,
port and benchmark sources are unchanged. Read #491/#616 and #719's review and
comments before measuring; no implementation branch was edited.

Rebuilt clean source with **CPython 3.13.16 / LLVM 18.1.3**: compiler/runtime IR
fixed points are **645,062 / 18,851 lines**, byte-identical across all three stages.
Native compiler SHA-256:
`18382171c96a1ce0ee6048d868439b4a823b9abfa36138d941c1e890d07e2154`.
The comparison compiler is separately identified as built from `b7e869f8`, hash
`12288231f46f77db1034d1afd59647fabe13e61452fd230577bbc6223897ff84`;
its implementation equals preceding evaluated main `837843bc` (#747 was tests only).

### Executed APIs and bounded regression checks

- **76/76 retained checks pass:** five `sys_*` programs plus six opcode
  positive/deviation/rejection fixtures, **19 checks in each** of native JIT/AOT,
  GC-stress, optimization-off and CPython-hosted compiler configurations.
- The new recording agrees with **base CPython 3.13.16**. A separate raw-path
  program prints all four attributes and checks their from-import aliases. All
  **six native JIT/AOT executions** (normal, GC-stress and optimization-off) return
  the canonical compile-time Pystachy home. Changing `PYSTACHY_HOME` at AOT run
  time does not change the embedded strings; a symlinked compiler home with an
  extra import path resolves to the same canonical directory. The old compiler
  rejects the new import. These are native API executions, not an upstream suite.
- **3,157-program old/new compilation comparison:** **3,156 identical** normalized
  IR/message/status results; only `tests/sys_prefix.py` changes, from rejection to
  acceptance. No accepted-to-rejected transition, changed benchmark IR or changed
  retained adapted-port IR. This bounds the selection; unrelated port/benchmark
  execution and timing experiments were not repeated.
- The compiler IR checker and LLVM assembler accept **10 selected programs**,
  including compiler/runtime sources. Runtime checks pass: **457 RUNTIME entries,
  70 exception classes and 171 functions**.

The four strings deliberately describe **Pystachy's compile-time home**, not a
CPython installation or a virtual environment. Independent raw-path outputs are
checked against that documented native contract, not falsely reported as exact
CPython path parity. Joining `share/locale` produces a path but supplies no catalog.

### Import first errors, not newly importable libraries

Both isolated sweeps were rerun with `--metadata`, two workers, the same
**522 CPython source hashes** and **54 overlay exclusions**. Native imports remain
**143/468**; the separate CPython-hosted throwing-stub diagnostic remains
**145/468**, with **zero timeouts** in either. There are no lost successes and no
denominator changes. Both maps advance the same four first errors:

| Module | Previous first error | Newly exposed first error |
|---|---|---|
| `gettext`, `argparse`, `optparse` | `gettext.py:62`: unsupported `sys.base_prefix` | `gettext.py:114`: cannot iterate over a tuple whose tuple items have different types |
| `site` | `site.py:81`: unsupported `sys.prefix` | `site.py:715`: unsupported `sys.flags.no_site` |

None of these four imports succeeds yet. The first-error limit still applies;
removing these next errors would not by itself establish full library support.

### Existing recording limitation and reproduction

Freshly reproduced the already-reported
[venv recording problem](https://github.com/den-run-ai/pystachy/pull/719#issuecomment-6278932791):
the fixture assumes `prefix == base_prefix == exec_prefix == base_exec_prefix`.
Base CPython prints `True`; the existing **CPython 3.13.16 development venv** prints
`False` on the first line (both remaining lines agree). Thus the merged recording
is not portable to that documented development setup. This is a known test-harness
limitation, not a new native runtime failure. No fixture was rewritten and no
duplicate issue was filed; full recording validation was not claimed.

From the clean evaluated checkout, using the explicit toolchain environment in
the [evidence and replay scripts](compatibility-2026-10-19-sys-prefix.json):

```sh
make PY=/root/.local/bin/python3.13
tests/run.sh ./pystachy 'jit aot' tests/sys_*.py tests/lib_opcode.py tests/upstream_opcode.py tests/deviations/lib_opcode_specialization.py tests/errors/lib_opcode_*.py
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' tests/sys_*.py tests/lib_opcode.py tests/upstream_opcode.py tests/deviations/lib_opcode_specialization.py tests/errors/lib_opcode_*.py
PYSTACHY_OPT=-all tests/run.sh ./pystachy 'jit aot' tests/sys_*.py tests/lib_opcode.py tests/upstream_opcode.py tests/deviations/lib_opcode_specialization.py tests/errors/lib_opcode_*.py
tests/run.sh '/root/.local/bin/python3.13 -m pystachy' 'jit aot' tests/sys_*.py tests/lib_opcode.py tests/upstream_opcode.py tests/deviations/lib_opcode_specialization.py tests/errors/lib_opcode_*.py
make check-runtime PY=/root/.local/bin/python3.13
/root/.local/bin/python3.13 tools/import_sweep.py -j 2 --metadata build/audit-719/imports-metadata.json ./pystachy "$STDLIB" build/audit-719/imports.json
/root/.local/bin/python3.13 tools/import_sweep.py -j 2 --metadata build/audit-719/stubs-metadata.json --stubs "$STDLIB" build/audit-719/stubs.json
```

`STDLIB` is the pinned interpreter's stdlib directory, recorded in the JSON.
Extract and relocate `audit-719.py` and `audit-719-assemble.py`, run driver modes
`build`, `references`, `checks`, `probes`, `oracle`, `sweeps`, `verify`, then aggregate.
The evidence retains the initial failed sweep invocation (exit 2: options placed
after a variadic positional argument); no module was tested by that attempt.
The corrected invocations above completed both full sweeps. Exact commands,
outputs, source/fixture/tool hashes, input inventory digest, import deltas and
independent probe source are retained. Historical failed-attempt and implementation-CI
snapshots must be retained separately when replaying the assembler.

Freshly read historical implementation head `3bd4fd4db85e9df28333f30a9b3e2eb860e13a83`:
four workflows succeeded ([CI](https://github.com/den-run-ai/pystachy/actions/runs/39338142015),
Lint, Packages and Installation). They are not combined-main or audit-head CI.
No full local `make verify`, unmodified CPython regrtest, broad PyPI/NumPy census or
performance/memory experiment was run. Shared-host timings are command durations,
not speedup/regression evidence. Dated baseline reports/JSON and adaptation
assessments are preserved unchanged.

## 2026-10-19: numeric-union local slots (#742)

Evaluated [main `a1f3b6a7379510d7ece2d168e576313d5fa8c6cf`](https://github.com/den-run-ai/pystachy/commit/a1f3b6a7379510d7ece2d168e576313d5fa8c6cf),
the only first-parent merge after `633cdf1a`. Fresh metadata and ancestry confirm
[#742](https://github.com/den-run-ai/pystachy/pull/742) merged. Its ten changed paths
add the `unionslots` IR pass, dispatch/configuration, a cache-key test update, two
positive/IR fixtures and their contracts, and documentation. Runtime, library,
port and benchmark sources are unchanged. Read #491/#616 and the PR discussion;
the completed no-findings review covers implementation head `4aa2297c`, not this
audit's later combined tree. No implementation branch was edited.

This optimizes the representation of already-supported **closed numeric unions**:
eligible locals keep a numeric tag and payload in separate slots, and values that
escape are boxed subject to the pass's allocation-budget rule. It does **not** add
general runtime `Any`, new inference, arbitrary union consumers or generator-frame
slot splitting. Existing rejection/deviation fixtures retain their meaning.

### Build, execution and regression evidence

Fresh **CPython 3.13.16 / LLVM 18.1.3** bootstrap reaches compiler/runtime fixed
points of **650,584 / 18,851 IR lines**, with all three stages byte-identical.
Compiler SHA-256:
`114c2495ec213cd94dbf1494df7f2e05fd6557888281ab58fc1e1f0a91f90f15`.
The old comparison compiler was built from **633cdf1a**, hash
`18382171c96a1ce0ee6048d868439b4a823b9abfa36138d941c1e890d07e2154`;
compiler build identity and evaluated source identity are retained separately.

- **3,159-program three-way compilation comparison:** **3,136 identical** old/new
  IR/message/status results, **23 with changed IR**, and **no changed acceptance or
  rejection diagnostics**. Every result is identical to the old compiler with
  `PYSTACHY_OPT=-unionslots`. This isolates the new pass rather than attributing
  unrelated frontend changes to it.
- **470/470 focused checks pass:** 34 union fixtures give **56 checks per mode**;
  the changed-IR selector adds 19 previously unselected fixtures, **38 per mode**.
  Each selection runs native JIT/AOT, GC stress, pass-disabled, all-optimizations-off
  and CPython-hosted compiler configurations. The additional programs cover
  datetime, random, string formatting, mixed-list/template/type-alias cases and
  Unicode library consumers. All 22 changed-IR executable test programs are covered;
  the remaining changed program is the IR contract probe.
- **38/38 CPython reference recordings** match (21 initial and 17 additional
  positive programs). Expected-rejection and documented-deviation checks are
  separate and are not mislabeled CPython parity. Repository `upstream_*` fixtures
  are adapted case programs, not unmodified upstream suites.
- An independent **eight-input matrix** exercises mixed accumulations, repeated
  saved snapshots, exception recovery and generator suspension, including empty
  input, signed-zero inputs, infinity and NaN. Its output exactly matches CPython
  in **ten JIT/AOT executions**: old compiler, new pass on, pass off, GC stress and
  all optimizations off. No source adaptation was needed for this probe.
- IR checking and LLVM assembly pass for **44 programs** (25 initial, 19 additional).
  Runtime checks pass for **457 RUNTIME entries, 70 exception classes, 171 functions**.
  Native runtime-cache tests pass **65/65**, including equivalence of `-all` to the
  complete named-pass list containing `-unionslots`. Hosted-only source-component
  cache checks were not run by this native invocation.

### Allocation mechanism, not a timing claim

The retained `tests/ir/unionslots.py` contract passes. Independent counts of
`pys_ubox` call sites in its emitted LLVM IR show:

| Function | Old / pass disabled | Pass enabled |
|---|---:|---:|
| `acc` (float-list accumulator returning a union) | 2 | 1 |
| `mixed` (numeric-union-list accumulator) | 4 | 1 |
| `paid` (one escaping read between updates) | 4 | 1 |
| `shown` (print the narrowed float accumulator) | 2 | 0 |
| `twice` (multiple escaping reads) | 4 | 4 |
| `passed`, `param`, `item` (already-boxed inputs) | 0 each | 0 each |

No function in that probe gains a box call site. For `acc`, the sole remaining
box call is after the loop at the return; the loop body contains none. Selected
function bodies, complete IR hashes and all per-function counts are preserved in
the [machine-readable evidence](compatibility-2026-10-19-union-slots.json).
These are **static IR observations**, not dynamic allocation totals, peak memory
measurements or a reproduced wall-time speedup. A scratch contract omitting the
required return box correctly fails with `OTHER CALLS`, exit 1.

The initial negative-control attempt incorrectly expected `check_ir.sh` to honor
`PYSTACHY_OPT=-unionslots` for a `.calls` fixture. That harness deliberately clears
the option for contracts and passed with optimizations on. The failed audit
assertion is retained explicitly; the corrected scratch-contract control above
does not edit any tracked fixture. Pass-disabled compilation is independently
verified directly by the three-way oracle and the box-count comparison.

### Library counts, workload and limits

Both isolated import sweeps were rerun with `--metadata`: **143/468 native** and
**145/468 stub-assisted**, **zero timeouts**, identical per-module outcomes and
first errors. All **522 CPython source hashes**, **54 exclusions** and overlay
policy match the preceding checkpoint. There is no newly importable library.

No retained adapted-port or benchmark source changes IR in the oracle. The
existing **adapted float `spectral_norm`** workload was nevertheless smoke-tested:
one loop, `N=130`, CPython reference plus JIT/AOT with the pass on and off. All four
native results are exactly `1.6236422398020804`, matching CPython (the driver permits
relative tolerance `1e-12`). This does not test the author's separately annotated
numeric-union timing variant or establish unmodified upstream compatibility.
Concurrent shared-host command/benchmark durations are retained only as diagnostics;
no performance ratio is inferred from these single samples.

Exact commands, inputs, fixture/tool hashes and replay scripts are in the JSON.
Long stdout is preserved as gzip+base64 in `stdout_blobs`, keyed by SHA-256 of its
decoded UTF-8 bytes; each `stdout_blob_sha256` refers to that map.
From the clean evaluated checkout, set the explicit environment from the driver,
then run `audit-742.py` modes `build`, `references`, `checks`, `oracle`,
`changed-checks`, `changed-references`, `verify`, `changed-ir`, `probes`,
`negative-contract`, `cache`, `benchmark`, `sweeps`, followed by the assembler.
The historical failed negative-control invocation and implementation-CI snapshot
are separate inputs to preserve when replaying the assembler. The sweeps are:

```sh
/root/.local/bin/python3.13 tools/import_sweep.py -j 2 --metadata build/audit-742/imports-metadata.json ./pystachy "$STDLIB" build/audit-742/imports.json
/root/.local/bin/python3.13 tools/import_sweep.py -j 2 --metadata build/audit-742/stubs-metadata.json --stubs "$STDLIB" build/audit-742/stubs.json
```

`STDLIB` is the pinned interpreter's stdlib directory, retained in the evidence.
Freshly read implementation head `4aa2297cb0d4809e4c775c509e2969a68d5e390a` has four
successful workflows ([CI](https://github.com/den-run-ai/pystachy/actions/runs/39338453023),
Lint, Packages and Installation); this is historical, not combined-main/audit-head
CI. No full local `make verify`, full recording rerun, unmodified CPython regrtest,
broad PyPI/NumPy census or dedicated performance/memory experiment was run. No new
uncovered bug was confirmed and no issue filed. Dated baselines, upstream-suite
distinctions and minor/major adaptation assessments remain unchanged.

## 2026-10-19 — collector-backed weakref callbacks (#694)

Evaluated main **`c71d4ca5413645c8094f306d727a8f18059bb722`**, after
**`a1f3b6a7379510d7ece2d168e576313d5fa8c6cf`**. Fresh GitHub metadata and local
ancestry verify that [#694](https://github.com/den-run-ai/pystachy/pull/694)
merged at **2026-10-20 00:16:51 UTC** (2026-10-19 locally); it is the only
first-parent merge since the previous checkpoint. Main was fetched again before
publication and still identifies this revision. The audit continues in
[#743](https://github.com/den-run-ai/pystachy/pull/743); #635 is already merged.

The 25 changed files add the callback queue and roots to `runtime.c`, update the
private weakref ABI/compiler effects and wrapper, and add callback tests and C
probe guards. No port or benchmark source changed. Read #491/#616 and #694's
current discussion before testing; no implementation branch was modified.
[Evidence, exact commands and replay scripts](compatibility-2026-10-19-weakref-callbacks.json)
retain source and compiler identities separately, including the previous compiler.

### Measured API and collector results

Rebuilt from clean tracked sources with **CPython 3.13.16 / LLVM 18.1.3** on Linux
x86-64, two workers per test group. Compiler and runtime fixed points pass:
**650,777 / 18,851 IR lines**, all three stages byte-identical. The compiler SHA-256
is **`8f9e8d02d7a9311ef396f4e32b684afa98fe235bafb51575304be2468b0c3ef7`**.
The old compiler is the verified #742 build from `a1f3b6a7`, SHA-256
`114c2495ec213cd94dbf1494df7f2e05fd6557888281ab58fc1e1f0a91f90f15`.

| Check | Measured result |
|---|---|
| Retained weakref cohort | **27 cases / 38 checks** in each of native JIT/AOT, program GC stress, all optimizations off and CPython-hosted compilation: **152/152 pass**. Eleven positive programs and sixteen expected rejections remain distinct. |
| CPython references | **11/11 recordings match** full stdout and exit status, plus the last stderr line where present. Callback traceback text is deliberately not claimed identical. |
| Sanitized runtime executions | All eleven positive programs pass JIT and AOT with UBSan-instrumented `runtime.c`: **22/22**, with JIT's sanitizer runtime explicitly preloaded. This does not claim a sanitized compiler bootstrap or full verification matrix. |
| Adjacent collector controls | Four GC/container fixtures, `sys.warnoptions`, exception-class behavior, and two adapted ordered-set/sortedcontainers workloads pass stressed JIT/AOT: **16/16**. Total focused checks above: **190/190**. |
| IR and ABI | **13 programs** pass IR checks and LLVM assembly; **458 runtime entries / 70 exception classes / 171 functions** agree in signatures, coverage and effects. |
| Collector C probe | Passes normally and under GC stress, then both again with UBSan. Covers live/dead targets, cycles, large objects, address reuse, registry pruning, tracked owners, callback queue rooting and orphaned handles. |

The five new callback programs now compile where the old compiler rejects them.
They execute the supported behaviors: `None` means no callback, a live reference
is notified once after its referent dies, newest references run first, nested
reference operations do not recursively drain the queue, dead references do not
call back, and a raising callback does not stop later callbacks or the program.
Tests use cohorts rather than assuming that conservative GC must free a particular
object immediately. Reclamation and callback timing remain different from CPython:
callbacks drain when the program next makes or calls a reference after collection.

**3,166-program old/new compilation comparison:** **3,149 identical** in IR,
messages and exit status; all **17 differences are weakref fixtures**. Five new
callback programs move from rejection to acceptance, six existing positive
programs change IR without output changes, and six rejection diagnostics change
for the new argument contract or wrapper locations. **No accepted-to-rejected
transition** occurs. No retained adapted-port or benchmark IR changes. The obsolete
callback-rejection fixture removed by the merge is not counted as a lost positive
program. Exact changed results and inventory hash are in the evidence.

### Safety guards and failed audit attempt

The reviewed stale-pointer finding is linked in
[#694's thread](https://github.com/den-run-ai/pystachy/pull/694#discussion_r4319331351),
with the [fix response](https://github.com/den-run-ai/pystachy/pull/694#discussion_r4319690142).
Independent scratch-only negative controls remove one guard at a time:

- Without clearing an unmarked fire pointer, the isolated orphaned-handle probe
  exits **1** with `dead fire function kept by a live handle`, normally and under
  GC stress.
- Without scanning the pending callback queue as roots, the probe exits **1**
  because the queued fire function is not retained, normally and under GC stress.

The first orphan-control attempt exited 1 as intended, but failed the audit
driver's diagnostic assertion: the earlier `fired()` test caught the same removed
guard as `dead reference's fire function queued` before `orphaned()` ran. That
result is retained under `incomplete_attempts`. The corrected scratch probe omits
the earlier `fired()` invocation to isolate the intended guard; tracked runtime
and fixtures remain unchanged. This was an audit expectation mismatch, not a
failure of the unmodified merged runtime. No new uncovered bug or issue was filed.

### Imports, adapted workloads and remaining limits

Fresh isolated sweeps with `--metadata` remain **143/468 native** and
**145/468 stub-assisted**, **zero timeouts**, identical per-module results and
first errors to #742. The same **522 CPython source hashes / 54 overlay exclusions**
are verified. `import weakref` still stops at missing `_weakref.getweakrefcount`;
the callback addition alone does not unblock full weakref, logging or unittest.
Proxies, registry helpers, weak containers and `__callback__` remain outside this
prototype. Callback arguments must be functions or `None`, not arbitrary callable
objects; keyword callback arguments are rejected at compile time.

Two retained **adapted** pyperformance workloads also pass stressed native JIT/AOT
against CPython: `richards` (one loop, **9297 / 23246**) and `raytrace` (one loop,
20×20, checksum **46535**). These are four successful native smoke executions,
not new unmodified upstream-suite support. Shared-host single-sample durations
are preserved as diagnostics only: **no timing regression, speedup or peak-memory
claim**. The adapted `upstream_weakref.py` case program is not CPython's full test
suite. Historical adaptation assessments and dated reports/JSON are unchanged.

Replay from the clean source revision: rebuild with the pinned environment, then
run the embedded `audit-694.py` modes `references`, `checks`, `contracts`,
`sanitized`, `negative`, `adjacent`, `oracle`, `sweeps`, and the assembler. Preserve
the historical negative-control attempt when replaying the assembler; it is not
recreated by the corrected driver. The two sweep commands are:

```sh
/root/.local/bin/python3.13 tools/import_sweep.py -j 2 --metadata build/audit-694/imports-metadata.json ./pystachy "$STDLIB" build/audit-694/imports.json
/root/.local/bin/python3.13 tools/import_sweep.py -j 2 --metadata build/audit-694/stubs-metadata.json --stubs "$STDLIB" build/audit-694/stubs.json
```

`STDLIB` is the exact pinned interpreter path recorded in JSON. Freshly fetched
implementation-head `a03d394348587c54486ac33a2729de8cd3e1bdf6` workflow summaries
show CI, Lint, Packages and Installation successful
([CI run](https://github.com/den-run-ai/pystachy/actions/runs/39341839705)). Those
are historical implementation-head results, **not combined-main or audit-head
CI**. No full local `make verify`, full recording rerun, unmodified CPython
regrtest, general NumPy/PyPI census or dedicated performance/memory experiment was
run. Optional broader testing stopped after the concrete callback/collector risks
and adjacent controls above were resolved.

## 2026-10-19 — #725 warnings and #740 regex specialization

Evaluated consecutive main revisions
[`d24710304245efa101bb8d44010174c7aa99ee90`](https://github.com/den-run-ai/pystachy/commit/d24710304245efa101bb8d44010174c7aa99ee90)
([#725](https://github.com/den-run-ai/pystachy/pull/725)) and
[`c8439d40b749817077d6565d0735a87ee6c90c0c`](https://github.com/den-run-ai/pystachy/commit/c8439d40b749817077d6565d0735a87ee6c90c0c)
([#740](https://github.com/den-run-ai/pystachy/pull/740)), following `c71d4ca5`.
Both are verified ancestors of current main. Compiler/runtime sources are unchanged
at both checkpoints: the verified #694 compiler is reused, with build source
`c71d4ca5413645c8094f306d727a8f18059bb722` and SHA-256
`8f9e8d02d7a9311ef396f4e32b684afa98fe235bafb51575304be2468b0c3ef7`.
CPython **3.13.16**, LLVM **18.1.3**, and the same **522 upstream source hashes**
are retained. Read #491/#616 and both PRs' review discussions before testing.

### Warnings: new execution surface and first-error progress

[Warnings evidence](compatibility-2026-10-19-warnings.json) retains exact commands,
fixtures, independent programs, negative controls and old/new compilation results.

- **18 cases / 29 checks** in each of native JIT/AOT, program GC stress,
  optimizations off and CPython-hosted compilation: **116/116 pass**. Nine
  CPython reference recordings match stdout/status and the last stderr line.
  Eleven programs also pass IR checks and LLVM assembly.
- An independent matrix covers six filter actions, three categories, repeated
  locations, message/module/line matching and nested recording-context restoration.
  Stressed and unoptimized JIT/AOT match CPython's complete stdout/stderr.
- Scratch-only controls removing the reviewed `__main__` filter anchor and
  skip-prefix element validation are both detected by retained fixtures. See
  [filter review](https://github.com/den-run-ai/pystachy/pull/725#discussion_r4319721910)
  and [prefix review](https://github.com/den-run-ai/pystachy/pull/725#discussion_r4319721921).
- **3,178-program** compile comparison: **3,166 identical**, seven warning
  fixtures become accepted (five positives, two explicit deviations), and five
  rejection diagnostics advance. No accepted-to-rejected transition; no retained
  port or benchmark IR changes.
- Fresh isolated `--metadata` sweeps improve **143/468 → 144/467 native** and
  **145/468 → 146/467 stub-assisted**, zero timeouts. The denominator decreases
  because `warnings` moves into the overlay: **54 → 55 exclusions**. Newly
  successful import compilation is **`wsgiref.validate`**. Eleven other first
  errors advance, including `code`, `codeop`, `queue`, `sched`, `threading`,
  `traceback` and `sysconfig`; their remaining blockers are preserved in JSON.

This is a **major semantic/structural port**, not an annotation-only adaptation.
`warn()` has no Python stack frames and uses `<sys>:0` with a shared main registry;
`warn_explicit()` accepts explicit location. Warning records/registries are typed,
and recording contexts swap a static log. Replacement hooks, arbitrary messages,
category tuples, the deprecated decorator, recorded file/source and arbitrary
category imports remain outside this port. Intrinsic bool/regex warning emission
is still absent; the retained datetime/urllib warning-consumer rejections remain.

### Regex specialization: dispatch proven, not inferred from output

[Regex evidence](compatibility-2026-10-19-regex-specialization.json) separates
hosted generator checks, native executions and adapted benchmarks.

| Layer | Measured result |
|---|---|
| Hosted tooling | **14/14 unit tests**; seed 19, 1,000 candidates: 988 valid patterns, 987 specialized, **313,910 matcher comparisons**, zero declines/failures. These are CPython-hosted, not native executions. |
| Native recordings | **129/129** selected checks; **92/92** additional changed-IR checks. Six focused cases pass 12 checks each under GC stress, optimizations off and hosted compilation. Total retained checks: **257/257**. |
| CPython references | **45/45** selected positive recordings match. |
| Instrumented dispatch | JIT and AOT each make **2,815 calls**, use **28 generated matchers**, and exercise **107 fallback declines**. Removing trace lines reproduces the 616-line recording. Disabling lookup preserves ordinary output but removes all dispatch markers: output parity alone would not prove specialization. |
| Adapted benchmark correctness | `regex_effbot` (1 loop, checksum 636833), `regex_dna` (1 loop, 1,000 FASTA units; complete checksum tuple retained), and `regex_v8` (1 loop, checksum 369067584475) match CPython in default and specialized JIT/AOT. Generated modules contain 17, 21 and 231 matchers respectively. |
| Compile/import controls | **3,179 programs: 3,072 identical, 107 IR differences, no exit-status transitions**. All affected retained executable cases and the three benchmarks above pass. Native/stub sweeps remain **144/467 / 146/467**, 55 exclusions, zero timeouts, identical per-module first errors to #725. |

This is opt-in profile-guided **AOT pattern-value specialization**, not online JIT
tiering or general runtime `Any`. Decoded multibyte subjects, missing/mismatched
patterns, conditional group references and deep repeats retain interpreter
fallback. One generated fixture pattern is exercised only by CPython's fnmatch,
not by the native port; it is not counted among the 28 observed native matchers.
The already-documented recorder traceback gap is independently reproduced with
`GeneratorExit`: profile collection succeeds, but tool/runpy frames remain in
stderr. Reuse the [existing review thread](https://github.com/den-run-ai/pystachy/pull/740#discussion_r4320067995);
no duplicate issue is filed.

Replay scripts are embedded in the JSON. Run `audit-725.py` modes `references`,
`checks`, `ir`, `matrix`, `negative`, `oracle`, `sweeps`; run `audit-740.py` modes
as recorded by each command, including `extras` after `oracle`, then the shared
assembler. Both sweeps use `tools/import_sweep.py -j 2 --metadata ...` with the
same pinned CPython stdlib path; `--stubs` remains diagnostic, not native support.
Fresh historical implementation-head workflow summaries show CI, Lint, Packages
and Installation successful ([#725 CI](https://github.com/den-run-ai/pystachy/actions/runs/39341833933),
[#740 CI](https://github.com/den-run-ai/pystachy/actions/runs/39344132702)); these
are not combined-main or audit-head CI. Shared-host concurrent durations are
operational logs only: **no speedup, regression or peak-memory inference**.
No full local verify, CPython regrtest or general NumPy/PyPI census was run.
Historical adaptation assessments and baseline reports/JSON are unchanged.

## 2026-10-19 — #738 numeric-union reductions and #736 None inference

Evaluated combined main
[`f9eaba8f4d1ff9aef96b3351d74db4c2a0df19f3`](https://github.com/den-run-ai/pystachy/commit/f9eaba8f4d1ff9aef96b3351d74db4c2a0df19f3):
[#738](https://github.com/den-run-ai/pystachy/pull/738) at
`9503bffbaa8e95c30690e03413421a622f7f3be3`, then
[#736](https://github.com/den-run-ai/pystachy/pull/736), after the completed #740
checkpoint. [Evidence and replay drivers](compatibility-2026-10-19-union-none.json)
retain both merge SHAs, the changed-file selection and each build identity.

Rebuilt compiler/runtime with **CPython 3.13.16 / LLVM 18.1.3**. The intermediate
#738 build passes its fixed points (**652,744 / 18,851 IR lines**) and runtime/IR/C
contracts. The final #736 build passes all three byte-identical compiler stages
(**663,506 IR lines**) and runtime stages (**18,851 lines**). Final binary SHA-256:
`cc299a6f18dd3ba2e71094f1e05c802c03515c9c1dcd651cda39a44a56b8de89`.
Executions and sweeps below measure the final combined tree, not two independent
complete audits. Previous binary build source remains `c71d4ca5`.

### Measured improvements and boundaries

- The exact dated `mixed_numeric_sum` probe now prints **6.5** in JIT and AOT,
  matching CPython; the old compiler rejects it. Retained fixtures exercise
  numeric-union sum/generator sum, min/max, sort, exact int/float comparisons in
  containers, `math.fsum()` and `math.dist()`.
- **201 selected cases / 394 checks per mode**, with native JIT/AOT, GC stress,
  all optimizations off and hosted compilation; **1,576/1,576 pass**. Two extra
  changed-IR cases pass another **4/4** checks. **193/193 CPython references**
  agree with recordings. Four retained ordered-set/sortedcontainers workloads are
  included as adapted ports, not unmodified upstream suites.
- Independent numeric matrix: **196 ordered pairs** around ±2**53, signed zero,
  infinities and NaN, plus **16 sum/distance rows**. In each stressed/unoptimized
  JIT/AOT execution, **211 rows match exactly** and **one matches the documented
  NaN-identity deviation**: shared NaN payloads do not gain identity through a
  union box, unlike CPython's identity shortcut in container comparisons.
  No tolerance or broad output normalization hides other differences.
- **27 None fixtures plus two reduction programs** pass IR checks and LLVM
  assembly. Runtime contracts agree for **459 entries, 70 exception classes and
  171 functions**; `runtime.c` passes clang `-Wall -Wextra -Werror` syntax checks.
- **3,203-program compile comparison: 3,172 identical**, 24 newly accepted
  fixtures (22 None-related plus two reduction programs), four rejection
  diagnostics advance, and three already-accepted cases change IR. **No
  accepted-to-rejected transition**. All changed executable fixtures are covered.

None inference now handles tested module globals, fields across inheritance,
later typed setters, and first fills of None-valued lists/dicts, including the
reviewed `+=` and chained-multiplication fixes. This does not establish arbitrary
dynamic storage: numeric bulk extension of a None list still needs annotations,
and templates or reads before a useful type can be found retain diagnostics.
The independently reproduced **typed non-self unrelated receiver** limitation is
already documented in [#736's review](https://github.com/den-run-ai/pystachy/pull/736#discussion_r4319956547):
an unrelated `set_b(b: B)` can still prevent reading `A.value` as None. The
explicit optional annotation remains the workaround; no duplicate issue filed.

[#596](https://github.com/den-run-ai/pystachy/issues/596) remains open: the tested
list reductions improve, but direct scalar union ordering still requires
narrowing, and the tracker includes other consumers. The matrix's initial scalar
comparison rejection is preserved, not reclassified as supported behavior.

### Imports versus APIs and upstream workloads

Fresh sweeps over the unchanged **522-source inventory / 55 exclusions** improve
**144/467 → 146/467 native**, **146/467 → 148/467 stub-assisted**, zero timeouts,
no successful imports lost. **`email.charset` and `reprlib`** newly compile as
isolated imports. Fifteen other email modules advance from the None-dictionary
blocker to using `Charset` as a class value.

The newly accepted imports do **not** establish their general APIs. With the same
CPython overlay, CPython executes both independent API programs, but native JIT
and AOT compilation still reject:

| API | Next observed blocker |
|---|---|
| `reprlib.repr([1, 2, 3])` | `type(x)` as a class value in `Repr.repr1()` (#7/#486) |
| `email.charset.Charset("utf-8")` | Cannot infer `input_charset` field type |

Three existing **adapted** benchmarks match CPython in JIT/AOT: `float` (one loop,
1,000 points), `go` (one loop, checksum **0 / 21121**) and `spectral_norm` (one loop,
**1.6236422398020804**, tool's existing numeric comparison policy). The pinned
pyperformance **1.14.0** sdist has SHA-256
`91f74393997b604375ad5b79bf569a24076d70181c076a53abad5383a238a8aa`.
An affected-source census of its unadapted `float` and `go` sources, with runner
replacement, still rejects both: `Point.x` inference and `pos_child` inference,
respectively. This is **0/2 compiled upstream sources**, not a fresh full 52-source
census or executed upstream suite. All timings are concurrent shared-host
correctness diagnostics; no performance or memory claim.

### Audit attempts, replay and CI

Preserved incomplete attempts include missing CPython fixture import paths, a
scratch `reprlib.py` shadowing mistake and omitted stdlib overlay, bool members
in an explicit int/float matrix, scalar union ordering, and an exact assertion
that exposed the already-documented NaN deviation. Corrected references and API
setup were rerun; the unsupported shapes and deviation remain explicit. A wrapper
replacement also briefly supplied multiple arguments to `Path.glob()` after the
extra execution checks; corrected invocation reran the four checks and 27 IR
programs. These are not concealed merged-source regressions.

Replay the embedded `audit-736.py` modes `build`, `references`, `checks`,
`contracts`, `oracle`, `extras`, `sweeps`; `audit-736-probes.py` modes `matrix`,
`api`, `census`, `bench`; then the assembler. The imported helper drivers are
included. Historical failed attempts are preserved by the assembler but not
recreated by the corrected scripts. Fresh implementation-head workflow summaries
show CI/Lint/Packages/Installation successful for
[#738](https://github.com/den-run-ai/pystachy/actions/runs/39340512005) and
[#736](https://github.com/den-run-ai/pystachy/actions/runs/39342529887), not combined
main/audit-head CI. No full local verify, CPython regrtest, general NumPy/PyPI
census or dedicated performance/memory experiment was run.

## 2026-10-19 — #689 native `_io` stand-in

Evaluated main
[`b85f0f3c00f7c6a65892b3a90ebe391b606a1b9b`](https://github.com/den-run-ai/pystachy/commit/b85f0f3c00f7c6a65892b3a90ebe391b606a1b9b),
merging [#689](https://github.com/den-run-ai/pystachy/pull/689) after #736.
[Evidence and replay drivers](compatibility-2026-10-19-io-standin.json) retain
the exact commands, input hashes, compiler identity, outputs and first-error deltas.

Rebuilt with **CPython 3.13.16 / LLVM 18.1.3** because the compiler's stand-in
table changed. All three compiler stages agree (**663,515 IR lines**); runtime
stages agree (**18,851 lines**). Compiler binary SHA-256:
`f2f64dd2eab1fa930551f5ab7dc3265eac64c337400f3a8b2afab7445682cd37`.
Compiler build source and evaluated source are both `b85f0f3c`; the old binary's
build source is `f9eaba8f`.

- **32 selected cases / 50 checks per configuration** pass under native JIT/AOT,
  GC stress, optimizations off and hosted compilation. Six additional changed-IR
  cases pass **12/12** native checks: **212/212 retained checks** in total.
  **14/14 CPython references**, **18 IR programs** and runtime contracts pass.
- The independent decoder matrix covers two translation settings, two final
  settings and all ordered pairs of seven chunks, including split CR/LF and
  multibyte text, plus reset/setstate: **392 output rows** match in each of four
  stressed/unoptimized JIT/AOT runs. This is **normalized** parity: CPython's
  multiple-newline tuple and the native port's documented `NotImplementedError`
  both render `multiple`. Retained deviation fixtures separately verify the
  actual API difference; it is not counted as exact tuple support.
- `tools/io_check.py` passes **200,769 CPython-hosted comparisons**, zero
  differences. Those execute the port under CPython, not the native compiler,
  and are kept separate from the native matrix above.
- **3,211-program comparison: 3,186 identical**, five newly accepted fixtures
  (including two explicit deviations), three rejection diagnostics advance and
  17 accepted programs change IR. No acceptance regression. All affected retained
  executables are covered. The sole affected benchmark, adapted `hexiom`, matches
  CPython's complete solved board in JIT/AOT (one loop, default level 25).
  Its single shared-host sample is correctness evidence, **not a speedup claim**.

Fresh isolated `--metadata` sweeps retain **146/467 native / 148/467
stub-assisted**, 55 exclusions, zero timeouts and all 522 input hashes. No import
success is lost. **56 native first errors** advance from missing `_io` to missing
`_warnings` through importlib, including the unittest family. `_compression`
advances from absent `DEFAULT_BUFFER_SIZE` to absent `BufferedIOBase`; that is
also the only stub-assisted first-error change. These are next-blocker advances,
not 57 newly supported libraries or a working upstream unittest/regrtest harness.

This is a **major native reimplementation/stand-in**, not an annotation-only
adaptation or loading CPython's C extension. It adds the selected `_io` names,
buffer-size constant, `text_encoding()` and a text-only newline decoder, and
corrects reflected type module names. Decoder objects and multiple-newline tuples
remain explicit runtime `NotImplementedError` deviations; bytes decoder input
is rejected at compile time. Binary files, buffered/base classes, `open_code`
and `UnsupportedOperation` remain absent, and `text_encoding()` does not emit
`EncodingWarning`. None of this establishes general C-extension/NumPy/PyPI support.

Replay `audit-689.py` modes `build`, `references`, `checks`, `hosted`, `ir`,
`matrix`, `oracle`, `extras`, `bench`, `sweeps`, then its assembler; helper scripts
are embedded. The `extras` and benchmark selection follow the compile comparison.
Historical implementation-head CI/Lint/Packages/Installation all succeeded
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39342072767)); this is
not combined-main/audit-head CI. No full local verify, CPython regrtest or broad
upstream-suite census was run.

## 2026-10-19 — #749 virtual-environment recording portability

Evaluated main
[`be822311f751a32cb75660ac41b914ea1a52bf6a`](https://github.com/den-run-ai/pystachy/commit/be822311f751a32cb75660ac41b914ea1a52bf6a),
merging [#749](https://github.com/den-run-ai/pystachy/pull/749) after #689. Only
`tests/sys_prefix.py` and its recording change. Compiler/runtime/library/tools/
ports/benchmark source equality was checked; the verified #689 binary is reused.
Its build source remains `b85f0f3c`, distinct from evaluated source `be822311`.

[Evidence and driver](compatibility-2026-10-19-prefix-venv.json) confirm the
corrected recording under both base and venv **CPython 3.13.16**. The old fixture
prints `False` on its first line under that same venv, while the corrected test
prints `True True` under both interpreters. This resolves the previously recorded
#719 venv test failure, not a compiler semantics bug. Native, GC-stress,
optimization-off and hosted configurations each pass two JIT/AOT checks:
**8/8**, plus one IR/LLVM-assembly check. The raw path probes from #719 still
describe Pystachy's compile-time home behavior; no CPython venv path parity claimed.

Imports carry forward **146/467 native / 148/467 stub-assisted**, 55 exclusions,
by unchanged implementation identity, not a fresh sweep at this test-only SHA.
No full recording suite or runtime suite was repeated for #749. Historical head
CI/Lint/Packages/Installation succeeded
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39345045649)); audit-head
checks are reported separately after publication. Dated baselines remain intact.

## 2026-10-20 — #750 percent conversion order and malformed-text counts

Evaluated main
[`9392fddf2b87b18e278abfc4f48f0f889ac99b16`](https://github.com/den-run-ai/pystachy/commit/9392fddf2b87b18e278abfc4f48f0f889ac99b16),
the only merge after `be822311`, incorporating
[#750](https://github.com/den-run-ai/pystachy/pull/750). This is October 19 locally;
the heading uses the UTC date. Reviewed its 12 changed files, review comments,
and existing issues [#223](https://github.com/den-run-ai/pystachy/issues/223) and
[#29](https://github.com/den-run-ai/pystachy/issues/29), plus #491/#616 coordination.
No implementation branch was changed.

[Machine-readable evidence and replay drivers](compatibility-2026-10-20-format-counts.json)
retain exact sources, fixtures including binary stdin/stdout, commands, environment,
old/new comparisons and compiler identity. CPython **3.13.16**, LLVM **18.1.3**,
two workers per group. Rebuilt compiler SHA-256:
`6f20c9a0d69f458beeb895a1160a7ed9a4caf26f93224cbada29ad394c7bccaf`.
Compiler and runtime three-stage fixed points pass at **663,923 / 18,709 IR lines**.
The prior binary was built at `b85f0f3c`, with evaluated sources `be822311`.

- **#223 corrected:** literal `%s`/`%r`/`%a` tuple displays now evaluate and
  convert each item in CPython's order. Independent **44-case / 244-output-row**
  probes cover side effects, conversion exceptions, flags, escaped percent,
  two-/three-digit width and precision boundaries, and mixed numeric conversions.
  All four GC-stressed/optimization-off JIT/AOT runs match CPython **byte for byte**;
  the old compiler differs. Retained tests additionally cover tuple variables,
  module format constants, argument exceptions and mismatched conversion counts.
- **#29 corrected within the documented byte model:** independent **169 raw-input
  cases / 1,352 output rows** cover valid, mixed, truncated, overlong, continuation,
  out-of-range and invalid-lead bytes. Length, slicing, alignment, zero-fill,
  precision and five tab sizes match CPython's UTF-8 `surrogateescape` stdin
  behavior in all four native configurations. The old runtime differs. No output
  normalization is applied to these matrices. The separate retained fixture
  normalizes only `\udcXX` versus `\xXX` in presentation-error spelling;
  raw base64 evidence preserves that distinction.
- **94 retained cases / 159 checks** pass in each of native, GC-stress,
  optimization-off and hosted configurations. **53 additional changed-IR cases /
  106 checks** and **20 adapted wcwidth/pyfiglet checks** pass: **762 retained
  checks** total. Also **56 CPython recordings**, **65 IR/LLVM checks**, runtime
  contracts and native Unicode cache/GC probes pass.
- The **3,213-program compiler comparison** has **3,149 identical / 64 changed
  IR programs**, with **no exit-status or diagnostic changes**. All affected
  retained executables are covered, including ordered-set, QR and SGP4 cases.
  The three affected adapted pyperformance workloads (`chaos`, `float`, `raytrace`)
  match CPython in JIT/AOT at smoke inputs `1 200`, `1 1000`, `1 20 20`.
  These concurrent single samples are **correctness evidence, not performance
  or memory comparisons**.
- `tools/rtcheck.py` passes **569,601 hosted comparisons**, zero failures. It
  executes runtime.py through CPython stand-ins and is not native or full
  upstream-library-suite coverage.

Fresh isolated `--metadata` sweeps retain **146/467 native / 148/467 stub-assisted**,
**55 overlay exclusions**, zero timeouts, identical first errors and the same
**522 CPython input hashes**. No import success or broader library support is added
by these correctness fixes.

Remaining boundaries were rerun, not assumed fixed: raw `ED A0 80` still has
native length **1**, versus CPython surrogateescape length **3**. Reading one
character from raw `C0 80 Z` returns native length **2** with **1** remaining,
versus CPython stdin lengths **1 / 2**. This is the documented malformed
`read(n)` behavior; ordinary strict-decoding CPython files are a different contract.
Computed percent format strings, catalog/PyPI support and general Unicode parity
are not claimed. Existing minor/major adaptation and first-error limits remain.

Replay `audit-750.py` modes `build`, `references`, `checks`, `hosted`, `ir`,
`oracle`, `extras`, `negative`, `ports`, `unicode`, `bench`, `sweeps`, plus
`audit-750-matrix.py` and the assembler; embedded scripts include the shared helper.
An initial benchmark command used comma-separated names and was rejected by
argparse before running; the corrected invocation passed, and the failed attempt
is retained. No full local verify, CPython regrtest or new upstream-suite census.
Historical implementation-head CI/Lint/Packages/Installation succeeded
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39349830821)); these are
not audit-head checks.

## 2026-10-20 — #753 regex profile exit/traceback fidelity

Evaluated main
[`45e88b6fa0898c5aee62ba220f63781bdc1e4702`](https://github.com/den-run-ai/pystachy/commit/45e88b6fa0898c5aee62ba220f63781bdc1e4702),
merging [#753](https://github.com/den-run-ai/pystachy/pull/753) after #750.
Only `tools/re_specialize.py` and its unit tests change; compiler/runtime/library/
ports/benchmark/recording sources are identical. #750's compiler and import/API
results carry forward by that identity, not by a repeated native sweep.

[Evidence and driver](compatibility-2026-10-20-record-exits.json): **14 hosted
unit tests** and focused Ruff checks pass under CPython 3.13.16. Four independent
programs exercise subclasses of `BaseException`, `KeyboardInterrupt`, both
`KeyboardInterrupt` and `Exception`, and `GeneratorExit`. Current `record` matches
plain CPython's exit status, stdout and full stderr in all four, preserving the
one-call regex profile. The old tool adds its own frames in three; the hybrid
already worked and remains correct. This directly checks the
[review finding](https://github.com/den-run-ai/pystachy/pull/753#discussion_r4320290493).
Plain `KeyboardInterrupt` remains distinct: SIGINT is preserved, but extra tool
frames remain; its retained test compares only the final exception line.

An initial audit-driver filename collision overwrote its profile with its command
record and caused a driver `KeyError`; separate profile filenames fixed it and
the full checks were rerun. This was not an implementation failure. Tooling fidelity
does not add compiled regex/library coverage. Historical implementation-head
[CI](https://github.com/den-run-ai/pystachy/actions/runs/39348809947), Lint, Packages
and Installation succeeded; publication checks are separate.

## 2026-10-20 — #720 localized gettext port

Evaluated main
[`d87a215df913828337e522e367a7c2e1d38bbf5f`](https://github.com/den-run-ai/pystachy/commit/d87a215df913828337e522e367a7c2e1d38bbf5f),
merging [#720](https://github.com/den-run-ai/pystachy/pull/720) after #753. This
completes the three-merge interval after `be822311`: #750, #753, #720. The ten-file
diff adds a library port, documentation and four fixtures; compiler/runtime sources
are unchanged. The verified #750 binary is reused with current library sources:
**compiler build `9392fddf`**, separately from **evaluated source `d87a215d`**.

[Evidence, commands, hashes and replay drivers](compatibility-2026-10-20-gettext.json)
retain CPython **3.13.16**, LLVM **18.1.3** and the unchanged 522-file inventory.
The upstream `gettext.py` hash is independently verified as
`7178d6ebdd0647b003da0ccdffb9431bc5fcf5c3822a247b578fdb745162865d`.
Its source diff is a **minor localized adaptation**: replace the type-changing
global initialization with the equivalent ordered operator dictionary, and add
field/recursive-return annotations. Dictionary values **and order** match CPython.
This assessment describes source edits, not full API compatibility.

- **6 retained cases / 9 checks** pass in each of native JIT/AOT, GC-stress,
  optimization-off and hosted configurations: **36 checks**, plus **3 CPython
  recordings** and **3 IR/LLVM checks**.
- The independent API program combines **20 message/fallback-depth pairs**
  (including empty, multibyte and newline text), three domain bindings and the
  operator table. Its **38 output rows** match CPython in all four stressed/
  unoptimized native JIT/AOT runs. Identity `gettext`/`pgettext`, metadata and
  domain binding are exercised; identity fallbacks do **not** prove overriding
  translations or catalog parsing.
- The **3,217-program comparison** leaves **3,213 unchanged**. Only the four new
  gettext fixtures differ: one newly accepted API program and three diagnostic
  advances from missing module to explicit remaining blockers. No previously
  accepted program is rejected and no benchmark IR changes.

Fresh isolated native and stub-assisted `--metadata` sweeps give **146/466** and
**148/466**, respectively, with **56 exclusions** and zero timeouts. The successful
counts are unchanged: the denominator falls from 467 because `lib/gettext.py` now
replaces the upstream file. Its separately executed port is not silently counted
as an unchanged upstream import. Both sweeps have exactly these three map changes:

| Module | Measured result after #720 |
|---|---|
| `gettext` | Excluded upstream file; supplied by the tested localized port. |
| `argparse` | First error advances to `argparse.py:879`, unsupported `object()`. It still does not import. |
| `optparse` | First error advances to inability to infer `gettext._localedirs` during its import-time catalog lookup. It still does not import. |

The three retained error programs confirm catalog lookup rejection, the plural
method's `operator.index(int)` blocker, and inability to subclass the generic
`NullTranslations` base. These limits directly address the PR's
[argparse claim](https://github.com/den-run-ai/pystachy/pull/720#discussion_r4320296283)
and [fallback review](https://github.com/den-run-ai/pystachy/pull/720#discussion_r4320296290).
No working catalog translations, plural-form compiler, full upstream gettext
suite, argparse API or general PyPI support is claimed. Existing issue #491 remains
the library umbrella; no duplicate issue was opened.

Replay `audit-720.py` modes `provenance`, `references`, `checks`, `matrix`, `ir`,
`oracle`, `sweeps`, then `audit-720-assemble.py`; copy the hash-verified #750 binary
into this checkout first. No rebuild or broad port/benchmark repetition was needed
for this library-only change. No full local verify, regrtest or performance/memory
claim. Historical implementation-head CI/Lint/Packages/Installation succeeded
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39350427632)); audit-head
checks are read separately after publication. Dated baseline files are unchanged.

## 2026-10-20 — #696 public weakref module

Evaluated main
[`88013afb321048ef1edb92638f3dbc438b9e3c8d`](https://github.com/den-run-ai/pystachy/commit/88013afb321048ef1edb92638f3dbc438b9e3c8d),
the sole merge after `d87a215d`: [#696](https://github.com/den-run-ai/pystachy/pull/696).
The 22-file diff adds the weakref overlay, documentation and fixtures, with no
compiler/runtime/port/benchmark implementation changes. The verified compiler
built from `9392fddf` is reused (SHA-256
`6f20c9a0d69f458beeb895a1160a7ed9a4caf26f93224cbada29ad394c7bccaf`),
separately from the evaluated source revision. CPython **3.13.16**, LLVM **18.1.3**.

[Evidence, exact commands, hashes and replay scripts](compatibility-2026-10-20-weakref-module.json)
record **39 retained cases / 55 checks** in each of normal JIT/AOT, GC-stress,
optimization-off and hosted compiler configurations: **220 passing checks**.
These include positive APIs, 23 rejection cases and one documented `__all__`
deviation. All **15 CPython recordings** and **16 IR/LLVM checks** pass.

Three additional programs use the public import: a six-value live-reference
equality/hash/identity matrix, the retained nested-callback ordering probe, and
the adapted upstream weakref tests with only their import changed. All match
CPython in **12 native JIT/AOT runs**, under GC stress and optimization-off; the
previous source rejects all three at `import weakref`. The upstream-derived
program is still adapted, including conservative-GC cohort handling; it is not
CPython's full upstream suite. Reclamation timing, callback dispatch timing and
reference-cache identity retain their documented differences.

The **3,227-program oracle** leaves **3,217 identical**: only the ten new weakref
fixtures differ (three now compile, including the deviation; seven reach explicit
API rejections). No accepted-to-rejected transition, existing-program IR change,
or benchmark change. No affected retained port imports weakref; unrelated port
and benchmark execution was not repeated.

Fresh isolated `--metadata` sweeps use the same **522 source hashes**:

| Metric | Before | After |
|---|---:|---:|
| Native upstream imports | 146/466 | 145/464 |
| Stub-assisted upstream imports | 148/466 | 147/464 |
| Overlay exclusions | 56 | 58 |
| Timeouts | 0 | 0 |

`weakref` and `_weakrefset` move into the overlay. `_weakrefset` previously counted
as an upstream success, so the one-count decrease is **not a regression**. No
remaining included module loses success, and none newly completes import.
After normalizing only checkout path prefixes, native results change for the two
exclusions and **53 dependent modules**; stub-assisted results change for the two
exclusions and **98 dependent modules**. First errors advance, not full packages:

| Native next stop | Modules |
|---|---:|
| Missing `_socket` | 36 |
| `copyreg.py:15` class/function-valued dict keys | 4 |
| Generic base class in `concurrent.futures` | 3 |
| Missing `_elementtree` | 3 |
| `traceback.py:133` unsupported `object()` (`hashlib`, `logging`) | 2 |
| `_thread.lock` as a class value; `_signal`, `zlib`, `urllib.request`, `pyexpat` | 5 |

With stubs, the largest next stops are computed namedtuple fields in
`inspect.py:1725` (42) and conditional definitions in `socket.py:53` (37).
All exact per-module deltas are retained; the author's older sweep is not reused.

Pristine history is verified against installed pinned CPython: `b48358b` holds
both original files; `_weakrefset.py` remains byte-identical (SHA-256
`91895a451d06e9f521a1171b31b9b19bc9740f35af00d4fa106338ab7167c9ac`).
The weakref adaptation restricts imports/exports, omits `finalize`, disables ABC
registration, and adds a Python deletion helper. These are localized source edits
for the narrow reference workload, not implementation of the major missing weak
container/proxy/finalizer APIs. `WeakSet`, both weak dictionaries, `WeakMethod`,
`finalize`, `proxy` and `getweakrefcount` remain checked rejections; existing #491
owns the gaps. No duplicate issue or implementation change.

Replay `audit-696.py` modes `provenance`, `references`, `checks`, `api`, `sweeps`,
`oracle`, `ir`, then the assembler, after copying the hash-verified #750 binary.
Read-only inspection/coordination setup mistakes are recorded explicitly. No full
local `make verify`, regrtest, performance or memory comparison. Historical
implementation-head [CI](https://github.com/den-run-ai/pystachy/actions/runs/39354020237),
Lint, Packages and Installation succeeded; its tree equals this evaluated main,
but those are not audit-head checks. Baseline reports and JSON are preserved.

## 2026-10-20 — #737 inferred scalar unions and builtin splitting

Evaluated main
[`611af05e4c21ab736d59501a2d7db12cbfb70d22`](https://github.com/den-run-ai/pystachy/commit/611af05e4c21ab736d59501a2d7db12cbfb70d22),
the sole merge after `88013afb`: [#737](https://github.com/den-run-ai/pystachy/pull/737).
All merges since the previous published checkpoint `d87a215d` are covered by this
and the #696 entry above. Compiler changes require a fresh build: **CPython
3.13.16 / LLVM 18.1.3** reaches three-stage compiler/runtime IR fixed points of
**669,783 / 18,709 lines**. Source and compiler-build revision both equal
`611af05e`; compiler SHA-256 is
`9d6cacbb6b785ad767bc77b0ca15b3f6af364764b246815fbbf9f50ed63a4b4d`.

[Evidence, complete commands, input hashes and replay drivers](compatibility-2026-10-20-inferred-unions.json)
retain the old compiler identity separately. The selected **145 cases** contain
86 positive and 59 expected-rejection programs. Each normal native JIT/AOT,
GC-stress, optimization-off and hosted-compiler configuration passes **231
checks**, totaling **924**. All **86 CPython recordings**, **86 IR/LLVM checks**
and runtime signature/effect checks pass. The extra changed `accumulate` rejection
outside the initial selection also passes its diagnostic check.

The **3,238-program old/new compiler comparison** has **3,191 identical results**,
**38 rejected-to-accepted programs** and **nine changed rejection diagnostics**.
No accepted-to-rejected transition or changed IR among previously accepted
programs. All newly accepted retained tests were executed; the compared corpus
uses current source fixtures, including positive successors to removed errors.
The old and new compiler/home pair are separate, not the new binary with two
library paths. Existing benchmark IR stays identical.

Measured behavior gains include inferred mixed locals/globals/fields and returns,
compatible fresh-container results across function and eligible method chains,
mixed `Any` returns/iterator results, `statistics.median()` on integers,
`random.triangular()` with integer bounds, heterogeneous `zip_longest` fill values,
mixed `string.Formatter` arguments and textwrap's bool-to-int field reassignment.
These are finite inferred unions, **not arbitrary runtime Any storage/dispatch**.

An independent **98-line matrix** verifies scalar result types, pairwise numeric
ordering, builtin splitting, once-only operand evaluation/order and isolated
constructor specializations in **six native JIT/AOT configurations** (GC stress,
all optimizations off, union slots off). A separate **144-pair edge matrix**
matches CPython in four native runs, including integers above 2**53 and at the
signed-64-bit boundary, bools, signed zero, infinities and NaN. The old compiler
rejects the inferred-return matrix.

### Upstream sources and adapted workloads

The pinned **pyperformance 1.14.0** archive and 52 source hashes are verified.
Rerunning both compilers with the same census tool changes **6/52 to 7/52**
runner-replaced upstream sources accepted as IR: `spectral_norm` newly compiles,
with its integer-zero accumulators and integer-one initial vector unchanged.
`barnes_hut` advances from an int/float assignment rejection to unresolved
`QuadTree.particles` field inference; it remains blocked. The other 50 statuses
and first errors are identical. This is not seven complete upstream test suites.

The upstream spectral program itself only returns elapsed time and has no numeric
assertion. A **separate checksum-instrumented probe**, preserving its algorithm
and N=130, prints **1.274222209743**, matching CPython in six native JIT/AOT runs
(normal, GC stress, union slots off); the prior compiler rejects it. Runner
replacement and checksum instrumentation are explicitly retained as adaptations.
The existing adapted spectral benchmark also passes CPython/JIT/AOT smoke checks.
No timing or memory ratio is inferred from overlapping correctness workloads.

All **31 adapted port workloads / 62 native checks** pass, as do the **seven
mapped CPython-subset programs / 14 native checks**. Separately, the hosted
upstream tests pass **17 fnmatch + 66 textwrap** cases, and the mapping tool's
15 unit tests pass. Textwrap's manifest deliberately retains one partial method
because its primary compiled fixture still adapts setup, even though the original
field-rebinding shape now passes separately. Hosted test counts are not native
upstream-suite counts.

### Remaining boundaries and import results

Fresh isolated `--metadata` sweeps retain exactly **145/464 native** and
**147/464 stub-assisted** successes, **58 overlay exclusions**, zero timeouts,
and the identical 522-source inventory. After checkout-prefix normalization,
**no import result or first error changes** from #696. Working additional APIs
do not imply additional importable packages or general NumPy/PyPI support.

Independent small programs reconfirm #596's remaining union `hash`, power and
`divmod` rejections and heterogeneous numeric list/tuple ordering rejections;
`divmod` now explains the incompatible tuple result types. Existing mixed-list
`sum`/`min`/`max`/sort behavior still matches CPython. Forwarding recursion #595
and unannotated cache inference #620 still reject. The retained quantiles probe
advances to `list[float | int]` versus `list[int]` return conversion. Annotated
storage contracts, existing mutable aliases and non-leaf method-return inference
remain constrained. The reviewed chained-target and method-inheritance regression
fixtures pass. Existing #596/#595/#620/#616 and the library tracker own these
known limits; no new issue or implementation change was made.

Replay `audit-737.py` modes `build`, `references`, `checks`, `sweeps`, `oracle`,
`extras`, `ir`, `runtime`, `ports`, and `audit-737-probes.py` modes `matrix`, `edges`,
`boundaries`, `census`, `benchmark`, then the assembler. Reference execution needs
the recorded pure-Python **typing_extensions 4.16.0** module on its isolated
`PYTHONPATH`. Its hash is retained. Missing-dependency, disappeared historical
interpreter and scratch tool-import setup failures are explicit; corrected reruns
pass. No full local `make verify`, CPython regrtest or performance/memory study.
Historical implementation-head CI/Lint/Packages/Installation succeeded
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39352237792)); that head
is not this merged main or the publication head. Audit checks are read separately.
Dated baseline reports and JSON remain unchanged.

## 2026-10-20 — #755: empty-container results through forwarding recursion

Evaluated [main `17c7e1ff`](https://github.com/den-run-ai/pystachy/commit/17c7e1ff4b8510912d1829c967ae2691d03da0ea),
the sole merge after `611af05e`: [#755](https://github.com/den-run-ai/pystachy/pull/755).
The merge is in main's history and its tree equals implementation head
`0fdfc792f73abff5a06acd101b2aa50749b4a256`. The changed `calls`, `gen` and
`variables` compiler modules require a fresh bootstrap. **CPython 3.13.16 /
LLVM 18.1.3** reaches three-stage compiler/runtime IR fixed points of
**670,901 / 18,709 lines**. Evaluated source and compiler-build revision both
equal `17c7e1ff`; compiler SHA-256 is
`cf8769bc70729eca9f6ef20a17e788811d18d5544db53c01bfacbee08258e508`.

[Evidence, exact commands, source/fixture hashes and replay drivers](compatibility-2026-10-20-forwarding-recursion.json)
retain the previous compiler identity separately. Selection by changed files and
adjacent empty-container, forwarding, return-context, Any-recursion and join
families gives **101 cases: 50 positive and 51 expected rejections**. Native
JIT/AOT, per-allocation program GC, all optimizations off and hosted compilation
each pass **151 checks**, totaling **604**. The 14 changed cases additionally
pass **24 UBSan/GC checks** (20 executions and four rejection diagnostics).
All **50 CPython recordings**, **50 IR/LLVM checks** and runtime signature/effect
checks pass.

### Measured fix and retained boundaries

The exact original list and dictionary forwarding programs from the dated
`compatibility-2026-10-17-recursion.json` now compile and print CPython's
`[1, 2, 3]` and `{1: 1, 2: 2, 3: 3}`. The previous `611af05e` compiler rejects
both. Their annotated controls and the annotated scalar-forwarding control also
match CPython: **five accepted replay programs, each in GC-stressed JIT/AOT and
optimization-off JIT/AOT**, or 20 native executions. The unannotated scalar
`completed_forwarder` still rejects its unresolved `int * NoneType` operand in
both compilers; this is not arbitrary recursive-return inference. All six replay
programs execute under CPython. [#595](https://github.com/den-run-ai/pystachy/issues/595)
is closed as completed following #755; this checkpoint independently confirms
its original container regression is fixed rather than inferring that from closure.

The **3,251-program old/new compiler comparison** has **3,241 identical results**
and exactly **10 rejected-to-accepted programs**, all executed in the focused
checks. There is no accepted-to-rejected transition, changed rejection diagnostic
or changed IR among previously accepted programs. Retained adapted port and
benchmark IR remains identical. Current source fixtures are used for both
compiler/home pairs; the former forwarding-error fixture is represented by its
positive successor, not counted twice.

The four changed adopting/layout-conflict/two-root rejection programs still
reject. Incompatible concrete layouts and unresolved competing roots are not
silently accepted. These changes keep concrete native representations and do not
implement general runtime Any, arbitrary mixed storage or broad PyPI support.

### Review-sensitive layout control and workload checks

Read [the dict/set alias review](https://github.com/den-run-ai/pystachy/pull/755#discussion_r4320585712)
and its [fix follow-up](https://github.com/den-run-ai/pystachy/pull/755#discussion_r4320747325).
The retained `finally` programs read string-key containers through a global alias
while a forwarding return is still unwinding. An isolated copied hosted compiler
with **only forwarding key-layout-hole propagation disabled** returns false for
existing `k1`/`k2` members in both dict and set controls. The unmodified hosted
compiler and CPython return the correct true memberships; native configurations
above also pass. This negative control detects the actual layout corruption even
though the final sorted container contents look correct. Tracked implementation
sources and all implementation branches remain untouched.

Six adapted qrcode, sortedcontainers and tomli-w workloads pass **12 GC-stressed
JIT/AOT checks**. Together with focused/sanitized checks, this is **640 retained
configuration checks**, not 640 unique upstream tests. Adapted hexiom, nqueens and
meteor-contest smoke outputs match CPython in JIT/AOT. Their recorded single smoke
timings overlap other correctness work and support **no performance or memory
claim**. No full hosted or compiled upstream suite was added. The prior 7/52
runner-replaced source census is historical, not rerun here.

Fresh isolated `--metadata` import sweeps remain **145/464 native** and
**147/464 stub-assisted**, **58 overlay exclusions**, zero timeouts, with the
same **522 source hashes**. After checkout-prefix normalization, no result or
first error changes. Executed recursive APIs improve without increasing import
counts; general NumPy/CPython-extension compatibility is not implied.

Replay `audit-755.py` modes `build`, `references`, `checks`, `sanitize`, `ir`,
`runtime`, `oracle`, `extras`, `sweeps`, and `audit-755-probes.py` modes `retained`,
`negative`, `ports`, `benchmark`, then the assembler. The evidence gives the
isolated negative-control copy/one-line mutation setup. Initial wrapper setup and
benchmark CLI-choice errors are explicit; corrected measurements complete.
Historical implementation-head CI, Lint, Packages and Installation succeeded
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39357393358)); audit-head
checks are read separately after publication. No full local `make verify`,
CPython regrtest or timing/memory study. Other unaffected known gaps retain their
dated evidence. Dated baseline reports and JSON are preserved; no new issue or
implementation change was needed.

## 2026-10-20 — #718: object sentinels and three additional imports

Evaluated [main `11f4681a`](https://github.com/den-run-ai/pystachy/commit/11f4681adfc19404a0b4f97fdd015d3a01b301e6),
the sole merge after `17c7e1ff`: [#718](https://github.com/den-run-ai/pystachy/pull/718).
The merge is in main's history; its tree equals implementation head
`eae2a9183d6277e68561fa046332107ca26b0ecd`. Twelve compiler modules change and
`lib/_pystachy_object.py` is added. A fresh **CPython 3.13.16 / LLVM 18.1.3**
bootstrap reaches compiler/runtime fixed points of **672,243 / 18,709 IR lines**.
Compiler-build and evaluated-source revision both equal `11f4681a`; compiler
SHA-256 is `edf26ee1d2b52ac7e033e509f07a4d7d0c9d10d3bd4a14fad6f65f98a1b3b943`.

[Evidence, exact commands, input hashes and replay drivers](compatibility-2026-10-20-object-sentinels.json)
retain the previous compiler identity separately. The selected **86 cases**
contain 72 positive programs and 14 expected rejections: the changed sentinel
fixtures plus adjacent equality, identity, optional-scalar, reflection, iterator,
callable, range and alias cases. Each native JIT/AOT, GC-stress, optimization-off
and hosted-compiler configuration passes **158 checks**, totaling **632**.
The changed 12 cases pass **16 UBSan/GC checks** (eight executions, eight expected
rejections). All **72 CPython recordings**, **72 IR/LLVM checks** and runtime
signature/effect checks pass.

### Identity, nullable comparisons and remaining sentinel limits

An independent **36-case nullable matrix / 288 comparison results** matches
CPython in GC-stressed and optimization-off JIT/AOT. It checks both operand
orders for equality/inequality and identity/non-identity across nine optional
types, with the sentinel and other operand independently null/non-null. A copied
hosted compiler with only the nullable equality safeguard disabled differs on
**nine of 36 rows**; the unmodified hosted compiler matches. This reproduces the
[reviewed silent-result risk](https://github.com/den-run-ai/pystachy/pull/718#discussion_r4320291782)
and verifies its [fix](https://github.com/den-run-ai/pystachy/pull/718#discussion_r4320379840),
not merely successful compilation. No tracked compiler source was edited.

A separate lifetime/identity probe retains **128 distinct objects**, clears the
original list, creates 512 more objects, checks all pairwise identities and stable
hash/dictionary lookup, then removes 32 keys. It matches CPython in **six native
runs**: GC-stressed, UBSan plus GC, and optimization-off JIT/AOT. Sentinel defaults,
repr shape and type metadata are checked without comparing process-specific
addresses or hash numbers.

Qualified, imported-alias and assigned-alias construction still reject when no
module calls the bare `object()` name. An independent two-module program confirms
all three spellings work once another module triggers that load, matching CPython
in four native runs. The boundary is program-wide, not per module.

[#251](https://github.com/den-run-ai/pystachy/issues/251) remains open. Its original
mixed int/sentinel-return shape now reaches `get() returns both int and object`;
dict default lookup still rejects `expected int, got object`, and appending a
sentinel to a string list rejects `expected str, got object`. All three work in
CPython. Thus the shipped fnmatch port's `None`-for-STAR adaptation is still
needed; native construction does not establish class-bearing unions or runtime Any.

### Import gains versus usable APIs

Fresh isolated `--metadata` sweeps improve **145/464 → 148/464 native** and
**147/464 → 150/464 stub-assisted**, with the same **522 source hashes**, **58
overlay exclusions** and zero timeouts. No successful included import is lost.
Newly accepted imports are **argparse, traceback and _pyrepl._threading_handler**.
The stub sweep labels argparse with `_operator`; the independent native sweep
already accepts it, so that label is not evidence it requires a stub natively.

With the same overlay and **unedited CPython 3.13.16 module sources**, argparse
constants and traceback's private `_safe_string(ValueError(...))` match CPython
in GC-stressed and optimization-off JIT/AOT (eight executions). Full public API
support does not follow:

| Executed/reference probe | Current native boundary |
|---|---|
| `argparse.ArgumentParser(...).parse_args(...)` | Multiple inheritance rejected |
| `argparse.Namespace(count=3)` | Generic/template base-class inheritance rejected |
| `argparse.HelpFormatter(...)` | Unsupported statements in class body |
| `traceback.format_exception_only(ValueError("bad"))` | `expected _Sentinel, got BaseException` |

All four reference programs execute under CPython; the old compiler stopped at
`object()` before reaching these API errors. `_pyrepl._threading_handler` is only
import-compiled here, not a working threading hook. Native `code` advances to
`__future__.all_feature_names`; `hashlib` and `logging` advance to `_thread.lock`
as an unsupported class value. Stub-assisted `hmac` advances to that same latter
blocker. These remain first-error observations, not complete compatibility claims.

### Corpus result and an explicit compatibility loss outside it

The **3,263-program old/new comparison** has **3,254 identical results**, four
newly accepted sentinel programs and five changed rejection diagnostics. No
previously accepted corpus program changes IR or becomes rejected. All nine
changed programs are covered by the selected execution/diagnostic checks.

**Do not generalize this to zero regressions:** a user module named
`_pystachy_object.py` containing `VALUE = 37` imports and prints 37 under CPython
and the previous compiler, but the new compiler rejects it as unavailable. The
name is newly reserved for the helper. This is an independently reproduced,
[reviewed and documented compatibility loss](https://github.com/den-run-ai/pystachy/pull/718#discussion_r4319731036),
outside the retained corpus. It is not a newly uncovered bug; no duplicate issue
or implementation change was made.

Four adapted ordered-set/sortedcontainers workloads and four retained native
fnmatch programs pass **16 GC-stressed JIT/AOT checks**. Together with the focused
and sanitized checks, this totals **664 retained configuration checks**, not
unique upstream tests. The two adapted Richards benchmark variants match CPython
in JIT/AOT smoke runs; recorded timings overlap correctness work and support no
performance or memory conclusion. No full upstream suite or 52-source census was
rerun. Imports, executed APIs, adapted workloads and hosted compilation stay
distinct; no general NumPy/PyPI or CPython regrtest claim.

Replay `audit-718.py` modes `build`, `references`, `checks`, `sanitize`, `ir`,
`runtime`, `oracle`, `extras`, `imports`, `stubs`; then `audit-718-probes.py` modes
`matrix`, `identity`, `apis`, `reserved`, `aliases`, `negative`, `ports`,
`benchmark`, and the assembler. Run matrix before its negative control; the
evidence retains the copied-compiler mutation setup. All selected evaluations
complete, with no failed test attempts. Historical implementation-head CI, Lint,
Packages and Installation succeeded
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39359741663)); audit-head
checks are read separately after publishing. Full local `make verify` was not
run. Dated baseline reports/JSON and other sessions' work are preserved.

## 2026-10-20 — #760: UTF-8 file-write counts and dropped-result lowering

Evaluated [main `727b88ce`](https://github.com/den-run-ai/pystachy/commit/727b88ce5e12dc5d7b569aba0c0c1e2b34360df5),
the sole merge after `11f4681a`: [#760](https://github.com/den-run-ai/pystachy/pull/760).
Verified the merge is in main's history. It changes `runtime.c`, two compiler
modules, four regression programs/recordings and the compatibility reference.
The combined merged source includes #718, unlike the implementation head
`3413c3068b63a9f055ee567cf8bbbacd893f39b5`; historical implementation CI is not
represented as verification of this combined tree.

A fresh **CPython 3.13.16 / LLVM 18.1.3** three-stage bootstrap reaches compiler
and runtime fixed points of **672,348 / 18,709 IR lines**. Compiler-build and
evaluated-source revisions both equal `727b88ce`; compiler SHA-256 is
`2462b648e77bf8fee31c8bea153d2125feca53809523f30a13e35f8f9614920b`.
[Evidence and replay scripts](compatibility-2026-10-20-text-write-counts.json)
retain the previous compiler identity, exact commands, environments, outputs,
fixture hashes and explicit incomplete attempts.

### Correctness and mechanism

- **572 retained configuration checks pass:** 58 selected IO/consumer cases
  yield **114 checks** in each native, GC-stressed, optimization-off and hosted
  compiler configuration (**456 total**); seven focused cases pass **14
  UBSan/GC checks**; 51 additional changed-IR cases pass **102 JIT/AOT checks**.
  These include expected rejections and documented deviations, not 572 unique
  unmodified upstream tests. All four new CPython recordings match; the IR
  checker and LLVM assembler accept 56 selected positive/deviation programs.
- **An independent 57-row differential** covers UTF-8 and Latin-1, four newline
  modes, empty/ASCII/non-ASCII/NUL/dynamically constructed strings, append mode,
  direct writes, nested method-value calls, saved return values, lists of counts,
  writelines and print-to-file. It compares both return values and actual encoded
  byte sequences, plus a supplementary-plane/combining-character case. All
  **six native runs** (GC, UBSan plus GC and optimization-off, JIT/AOT) match
  CPython exactly. The previous compiler differs on **17 of 57 rows**.
  For the wide-character case, the old result is `15 5 11`; both CPython and
  merged main give `5 5 4` for write count, length and sliced-string write count.
- An independent Latin-1 error/partial-write probe matches CPython in the same
  six configurations: encoding errors in direct dropped/used/aliased calls,
  writelines preserving earlier successful writes, newline-adjusted error text,
  and closed-file failure. Its **first attempt was rejected** because it read
  `e.start`, `e.end` and `e.reason`; exception attributes are unsupported. The
  original program/reference/diagnostic are retained. Changing only the
  observation to `str(e)` is a **minor probe adaptation**, not newly working
  exception-attribute APIs.
- Runtime contracts pass: **460 RUNTIME entries, 70 exception classes, 171
  functions**. The existing native file-buffer accounting probe passes ordinary,
  extension-style initialization and stressed modes. Across 128 dropped files
  and 136,314,880 cumulative buffer bytes, outstanding tracked buffer bytes stay
  below the 41,975,808-byte bound; open/close/collection/exit accounting balances.
  This deterministic allocation bound is **not process RSS or a memory speedup**.

Five independent IR probes verify direct discarded `f.write(s)` and
`print(s, file=f)` call void `pys_file_put`, while used results and a discarded
method-value call still call counting `pys_file_write`. The writelines probe calls
`pys_file_writelines`; source inspection confirms its loop now uses `pys_file_put`.
The retained nested/after-statement/template regressions guard against discarding
a return value merely because stale compiler call context remains. Correctness
does not imply all aliased/indirect discarded calls avoid counting.

### Compatibility scope and retained limits

The **3,267-program old/new comparison** has **3,184 identical results** and
**83 changed IR results**, with **no exit-status or rejection-message changes**.
The changed compiler is covered by the bootstrap; every changed executable test
is covered by the focused or additional run. The evidence preserves hashes and
the complete changed-file list, not an exhaustive semantic proof of IR equality.
Existing benchmark IR is unchanged. Five adapted iniconfig/tomli-w workloads
are included in the four focused configurations; an affected qrcode workload is
in the additional run. All **18 adapted benchmark smoke programs** also match
CPython in JIT/AOT. Their overlapping correctness-run timing samples do not
establish performance regressions or gains. The author's callgrind cost table
was not independently replicated; consumed counts may require an extra text scan.

Fresh isolated sweeps with `--metadata` remain **148/464 native** and
**150/464 stub-assisted**, with the same **522 source hashes**, **58 overlay
exclusions**, zero timeouts and identical first errors after checkout-path
normalization. This is an executed file/stream API correction, not another
importable library or an increase in complete upstream-suite support.

[#120](https://github.com/den-run-ai/pystachy/issues/120) remains open for non-ASCII
case mapping and character predicates. A fresh old/new execution of
`print("é".upper(), "É".lower(), "ß".casefold(), "é".isalpha())` gives
`é É ß False` in both native compilers versus CPython's `É é ss True`.
Other unrelated gaps retain their dated evidence and were not all rerun. No new
uncovered bug or duplicate issue was filed, and no implementation branch changed.

Replay `audit-760.py` modes `build`, `references`, `runtime`, `checks`, `sanitize`,
`ir`, `fileprobe`, `oracle`, `extras`, `imports`, `stubs`, `benchmark`; then
`audit-760-probes.py` modes `matrix`, `errors`, `unicode-gap`, `mechanism`, and
the assembler. The scripts embed their shared `audit-737.py`/`audit-725.py`
dependencies. The original exception-attribute attempt is retained separately
from the successful adapted replay. Initial #491/#616 PR-endpoint lookups
returned 404; correct issue-comment lookups succeeded before work proceeded.

Historical implementation-head CI, Lint, Packages and Installation passed
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39361584023)); audit-head
checks are read separately after publication. Full local `make verify`, CPython
regrtest and a broad PyPI/NumPy census were not run. Native imports, executed
APIs, adapted workloads and hosted compilation remain distinct. Dated baseline
reports/JSON and concurrent edits are preserved.

## 2026-10-20 — #763: tuple exits, instrumented file flushing and coverage tooling

Evaluated [main `8990e417`](https://github.com/den-run-ai/pystachy/commit/8990e41776e8e74f57812120f81ec3e897065eda),
the sole first-parent merge after `5a91594740a78bb1d3bb32d8ab7d757d8b0f3ea3`.
[#763](https://github.com/den-run-ai/pystachy/pull/763) was re-fetched and its merge
verified in main's ancestry. Its tree equals implementation head
`15a4a4d18335836bb0e566cc8d377a5e292ad70d`. #635 is merged; this update reuses
audit #743. Coordination #491/#616 and the PR discussion were read before work;
no implementation branch was changed.

[Machine-readable evidence](compatibility-2026-10-20-coverage-runtime.json) retains
commands, full outputs, fixture/source hashes, coverage summaries, independent
probes and replay scripts. The changed-file review selected 11 new Python fixtures
and 16 adjacent exit/file/container/generator fixtures, then bounded tooling checks.
Compiler/runtime sources changed, so a fresh CPython **3.13.16** / LLVM **18.1.3**
build was required: compiler stages 2/3 agree at **677,903 IR lines**, and all three
runtime bootstrap stages agree at **18,709 lines**. Compiler source is `8990e417`;
binary SHA-256 is
`6969b66e38efa0619afaaaadb634caf76a56b5488503fc08d6577f588d3b1dee`.
The old compiler was separately built from `5a915947`, SHA-256
`31653d9c17c2c595d0036636d8eecd53ff1b9fdc2808d19bd3afd3b5b2a673b1`.

### Measured behavior and retained boundaries

* **Fixed-shape tuple `sys.exit` is corrected.** Eight independent expressions
  cover empty, None, int, string, multiple, nested-tuple, bool and list-containing
  tuples. Seven old JIT outcomes differ from CPython; all eight now match exact
  stdout, stderr and status in JIT/AOT with per-allocation GC and with optimizations
  disabled (**32 new execution comparisons**). For example, `(3,)` now exits 3
  silently instead of printing `(3,)` and exiting 1.
* **Instrumented `open()` no longer retains a dead writer and misses its flush.**
  With plain `-fprofile-instr-generate -fcoverage-mapping`, the unchanged
  `rt_list_vacated.py` fixture reads empty text at six old JIT/AOT points after
  dropping list-held writers. Both new tiers match CPython exactly. Isolated old
  and new runtime caches prevent cross-revision reuse. This is a real output
  correction exposed by profiling counters, not a throughput measurement.
* **Two pre-existing boundaries remain**, independently reproduced on both
  revisions. `t: tuple[int, ...] = tuple([]); sys.exit(t)` prints `()` and exits 1
  rather than 0; `tuple([3])` prints `(3,)` and exits 1 rather than 3, in JIT/AOT.
  `print(list(iter(b"ab")))` is rejected in both compile modes instead of printing
  `[97, 98]`. These are also explicitly disclosed by #763's report. Retain them
  under exception/bytes-iterator tracking [#10](https://github.com/den-run-ai/pystachy/issues/10)
  and [#12](https://github.com/den-run-ai/pystachy/issues/12), not as new regressions
  or duplicate issues. The fixed-shape result does not establish all tuple support.

| Fresh evidence category | Result |
|---|---|
| CPython recordings | All **11** new fixtures match output, exit status and final error line. |
| Selected differential cases | **54/54** each: native, GC-stressed, optimization-disabled and CPython-hosted JIT/AOT (**216** checks). |
| UBSan + GC | **24/24** checks on the 11 new fixtures plus the file-lifetime regression. |
| Configuration variants | All six rows pass **24** checks each (**144**): five pairwise IR-pass rows and CFLAGS `-O0`. |
| IR validation and compile comparison | LLVM/IR checker accepts all **27** selected programs. Of **3,322** retained programs, **3,320** outcomes/normalized IR hashes are identical; only the two intended exit fixtures differ, with no new rejection. |
| Adapted port smoke | **8/8** JIT/AOT checks across iniconfig, tomli_w, roman and pylev. This is not an upstream suite. |
| Runtime contracts | **460** runtime entries, **70** exception classes and **171** functions agree. |
| Direct file/memory probe | Normal, library and GC-stressed modes pass. For 128 dropped files / 136,314,880 allocated buffer bytes, peak outstanding is **35,971,072** bytes normally and **4,194,304** stressed, under the **41,975,808** limit; 4 versus 640 collections. No old/new performance ratio inferred. |
| Tool tests and negative controls | **16** coverage + **4** workflow-limit unit tests pass. Both report formats reject wrong/mixed revisions and missing shards; three invalid shard specifications reject. The two valid shards are disjoint and complete, **1,627 + 1,627 = 3,254** cases. |

### Coverage results and an explicit failed attempt

The successful **scoped** native coverage run executes three cases / six checks:
all **7/7 changed C lines** run, **14/18** associated branches taken. Its overall
15.2% line / 10.4% branch figures are for this tiny selection, **not** a regression
against #763's repository-wide historical report. Native C coverage excludes
`runtime.py` and direct C probes; signal deaths and exec can omit profiles.

The first hosted run selected two corpus cases **and the cache suite**. Its four
corpus checks and **67 cache assertions pass**, but **report generation fails**:
33 processes produce 33 coverage files, whereas the harness expects 32 after one
intentional kill. `tests/cache.sh` uses `ps` to decide whether its intermediate
`os.system` shell and Python parent both need killing. A separate read-only PID
control records namespace PIDs different from `/proc` IDs and `ps` errors
(`fatal library error, lookup self`); this points to this execution environment's
PID/proc mismatch invalidating the kill/count assumption. No upstream compiler
regression or passing cache coverage report is claimed. The failed command,
cache log and diagnostic control are retained; no implementation workaround was
applied and no issue was filed for an environment-dependent diagnosis.

A separate **corpus-only rerun succeeds**, with all **5/5 compiler processes**
captured, four checks passing, and **3/3 changed compiler statements / 2/2 changed
branches** covered. Its scoped totals are 32.2% statements / 23.2% branches, not
whole-repository percentages. Both runs use the existing CPython 3.13.16 virtual
environment with pinned **coverage.py 7.16.2**; the base interpreter lacks coverage.

### Imports, reproduction and limits

Fresh isolated `--metadata` sweeps remain **148/464 native** and **150/464
stub-assisted**, with **58 exclusions**, the identical **522-source CPython hash
inventory**, zero timeouts and unchanged first errors after checkout-prefix
normalization. Throwing stubs remain diagnostics, not C-module implementations.
No adaptation was removed or reclassified; existing minor/major assessments and
first-error limits remain. Other unrelated known gaps retain dated results rather
than being asserted re-tested here. No general NumPy/PyPI support or full CPython
regrtest claim follows from these measurements.

Replay embedded `audit-763.py` modes `build`, `references`, `tool-tests`, `checks`,
`sanitize`, `variants`, `runtime`, `fileprobe`, `ir`, `oracle`, `extras`, `imports`,
`stubs`, `consumer-smoke`, `runtime-coverage`, `hosted-coverage`, `pid-control`,
`hosted-corpus`; `audit-763-probes.py` modes `exit-matrix`, `writer-control`, `gaps`,
`report-controls`; then the assembler. The full hosted-cache attempt is expected
to be environment-sensitive as documented above, not silently treated as passed.
Scripts include `audit-737.py`/`audit-725.py` dependencies. Correctness groups ran
concurrently on a shared host; wall times do not establish performance changes.

Historical implementation-head **CI, Coverage, Variants, Packages, Installation
and Lint all succeed** ([CI](https://github.com/den-run-ai/pystachy/actions/runs/39372380481),
[Coverage](https://github.com/den-run-ai/pystachy/actions/runs/39372380620)); these
are separately attributed to its tree-identical implementation head, not local
full-suite reruns. Audit-head checks are read after publication. Full local
`make verify`, broad benchmarks and actual upstream package suites were not
repeated. Only report/evidence changes are added beyond current main; dated files
and concurrent edits are preserved. The inherited sort recording's two trailing
spaces are exact CPython output, not altered to satisfy a whitespace-only check.

## 2026-10-20 — #732: syntax rejection and continuation correctness

Evaluated [main `5a915947`](https://github.com/den-run-ai/pystachy/commit/5a91594740a78bb1d3bb32d8ab7d757d8b0f3ea3),
the sole merge after `727b88ce`: [#732](https://github.com/den-run-ai/pystachy/pull/732).
Verified the merge is in main's history and its tree equals implementation head
`08fe3c50d5345cbdb3b52c2cf69587f0723e2603`. The 53-file diff changes the lexer,
parser, syntax documentation, 40 rejection fixtures, four positive programs and
recordings, and the existing upstream-derived type-parameter program's comments.
No runtime or library implementation changed.

A fresh **CPython 3.13.16 / LLVM 18.1.3** three-stage bootstrap reaches compiler
and runtime fixed points of **677,819 / 18,709 IR lines**. Compiler-build and
evaluated-source revisions both equal `5a915947`; compiler SHA-256 is
`31653d9c17c2c595d0036636d8eecd53ff1b9fdc2808d19bd3afd3b5b2a673b1`.
[Evidence and replay scripts](compatibility-2026-10-20-syntax-validation.json)
retain the previous compiler identity, exact programs, input hashes, commands,
environments, outputs and diagnostic boundaries.

### Measured corrections

- **A silent continuation error is corrected.** The independent program
  `x = 0; if x: ...` with a line-start backslash continuing into the indented
  `x = 2` assignment prints `2` with the previous native compiler, but `0` with
  CPython and merged main. All **six new executions** (ordinary, GC-stressed and
  optimization-off, JIT/AOT) match CPython. The complete multiline program is in
  the evidence; the new retained fixtures also exercise blank/comment continuation
  lines, indentation columns and an empty function block.
- **58 independent syntax programs reduce acceptance mismatches from 33 to 2.**
  They cover sequence, mapping, class, OR/as/capture patterns, repeated names,
  unreachable cases and guards, numeric/boolean/complex/string/bytes duplicate
  keys, mixed-base large integer keys, complex-real overflow, type-parameter
  bounds and import-star placement. The two remaining mismatches are the known
  plain-TypeVar and ParamSpec starred defaults, tracked by
  [#541](https://github.com/den-run-ai/pystachy/issues/541). This is **31 corrected
  acceptance outcomes in this matrix**, not a count of newly compatible packages.
- Equal keys written in different bases are rejected for **2^64, 2^1000, 2^4001,
  2^14285 and 2^15000**; adjacent distinct values remain accepted in
  unused functions. This independently covers the review's missing duplicate
  detection above 1,000 written digits. At the two largest values CPython raises
  `ValueError` because printing the key exceeds its 4,300-decimal-digit limit;
  Pystachy reports the duplicate in hexadecimal. Both reject, but their diagnostics
  are intentionally different. No native arbitrary-precision arithmetic is implied.

### Retained checks and diagnostic precision

**403 selected syntax/generic/import cases pass 689 checks per configuration**:
native, program-GC-stressed, optimization-off and hosted compiler, **2,756 total**.
These include execution, expected rejection and parse-only checks, not 2,756
unique upstream tests. The five changed positive programs additionally pass
**14 UBSan/GC checks** (including syntax checks). All five CPython recordings
match, and the IR checker plus LLVM assembler accept 51 selected positive programs.
Runtime contracts still pass: **460 entries, 70 exception classes, 171 functions**.
Four adapted iniconfig/tomli-w/roman/pylev consumers pass **8 JIT/AOT smoke checks**.

CPython rejects all **40 new negative fixtures** and accepts the five changed
positive files. `tools/syntax_sweep.py` compares line/message as well as acceptance:
**43/45 agree exactly**. The two differences are a less-specific `expected an
indented block` message (same line) and the huge-key rendering exception described
above. Neither is an acceptance regression; exact diagnostic parity is not claimed.

The **3,311-program old/new comparison** has **3,269 identical results** and
**42 changes**: 34 accepted-to-rejected programs, six rejection-message changes,
one rejected-to-accepted valid continuation program, and one corrected continuation
IR result. **Every newly rejected program was independently confirmed invalid by
CPython.** All changes are among the selected new fixtures; no additional executable
test required a follow-up run. Existing port and benchmark IR is unchanged, which
is compile-only evidence. Broad benchmark reruns were unnecessary for this parser
delta and were not performed.

After the correctness groups finished, three fresh `check` samples for an
8,000-digit hexadecimal expression took **1.85–2.27 ms**, and three samples for
two equal 8,000-digit mapping keys took **4.56–5.21 ms**. The expression is valid
for parsing, not for native integer evaluation; the duplicates are rejected.
These bounded parser probes preserve the review's large-input risk check, not a
growth-complexity proof or a before/after performance ratio. The shared host was
not load-controlled; the author's timing table was not independently replicated.

### Scope, remaining gaps and reproducibility

Fresh isolated sweeps with `--metadata` remain **148/464 native** and
**150/464 stub-assisted**, with the same **522 CPython source hashes**, **58 overlay
exclusions**, zero timeouts and identical first errors after checkout-path
normalization. The correction is source-language behavior, not an increase in
importable libraries or complete upstream-suite support. Throwing stubs remain
dependency diagnostics, not module implementations.

An independent executed-match program is still rejected with **`'match' statements
are not supported`**. Valid patterns inside an unused function being accepted does
not establish working pattern-matching execution. The two #541 starred-default
cases remain wrongly accepted; #661 is not counted as merged. Other unrelated gaps
retain their dated evidence and were not all rerun. No new uncovered bug or duplicate
issue was filed; no implementation branch or other session's work was modified.

Replay `audit-732.py` modes `build`, `references`, `runtime`, `checks`, `sanitize`,
`ir`, `consumer-smoke`, `syntax-sweep`, `oracle`, `extras`, `imports`, `stubs`;
`audit-732-probes.py` modes `fixtures`, `syntax`, `execution`, `oracle-verdicts`,
then `cost` after other measurements finish; and the assembler. Embedded scripts
include their `audit-737.py`/`audit-725.py` dependencies. All selected evaluations
completed, with no failed test attempts. Completing the audit requires separate
CPython-invalid verification of every new rejection from the corpus oracle.

Historical implementation-head CI, Lint, Packages and Installation now pass
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39364806949)). Its initial
GC self-compile hit the 600-second bound; the rerun succeeded, as recorded in the
[PR discussion](https://github.com/den-run-ai/pystachy/pull/732#issuecomment-6282884171).
That history is preserved rather than recast as a local performance regression.
Audit-head checks are read separately after publishing. Full local `make verify`,
CPython regrtest and a broad PyPI/NumPy census were not run. Native imports, executed
APIs, adapted workloads and hosted compilation remain distinct. Dated baseline
reports/JSON and concurrent edits are preserved.

## 2026-10-20 — #764: starred type-parameter default acceptance corrected

Evaluated [main `4f71b5a0`](https://github.com/den-run-ai/pystachy/commit/4f71b5a013ddcce19ab12c282690106467faf4df),
the only first-parent merge after the last evaluated `8990e417`:
[#764](https://github.com/den-run-ai/pystachy/pull/764). Re-fetched the PR, verified
its merge in main's history and verified its tree equals implementation head
`9e09520cd8701bfb22cd56ae50269a5d356fb9e3`. #635 is merged; #743 remains the open
audit destination. Latest #491/#616 coordination, #541 and the PR review were read;
no implementation branch or external contributor work was modified.

The diff changes one parser rule, eight rejection fixtures, a valid-default
program/recording and comments in the adapted upstream type-parameter test.
Plain TypeVar and ParamSpec defaults now use the expression rule; only a
TypeVarTuple can start with a starred expression. No library/runtime implementation
changes. Selection: those **10 changed Python files plus 68 adjacent generic and
type-parameter cases**, not a repeat of the entire syntax execution suite.

A fresh **CPython 3.13.16 / LLVM 18.1.3** bootstrap reaches compiler/runtime fixed
points **677,917 / 18,709 IR lines**. Compiler-build and evaluated-source revision
both equal `4f71b5a0`; compiler SHA-256:
`dbe44e25653a36004511aeedddec03bdcb0084178b62b1a492793e64b3b8d121`.
The comparison binary is separately retained at source `8990e417`, SHA-256
`6969b66e38efa0619afaaaadb634caf76a56b5488503fc08d6577f588d3b1dee`.
[Evidence and replay scripts](compatibility-2026-10-20-starred-defaults.json)
include commands, exact programs, input hashes, diagnostics and both identities.

### Measured change

- **The retained 58-program matrix goes from two acceptance mismatches to zero.**
  Replayed the exact program text and verified every recorded SHA-256 from the
  #732 evidence. `starred-default-T` and `starred-default-P` now reject like
  CPython; all other acceptance results are unchanged. This is acceptance parity,
  not a claim that every syntax diagnostic matches: two huge-key cases retain
  CPython's integer-rendering `ValueError` versus the compiler's syntax diagnostic.
- **An independent 144-case boundary matrix goes from 32 acceptance mismatches
  to zero.** All three parameter kinds, six default expressions, aliases/classes/
  functions/async functions and single/multiline lists are covered. Valid nested
  unpacking and TypeVarTuple starred defaults remain accepted. **128/144** also
  match exact diagnostic line/message. The other **16** are def/async rejections:
  CPython reports `expected '('` at the opening line, while Pystachy reports
  `invalid syntax`, on the default's later line in eight multiline cases.
- CPython rejects all **eight new negative fixtures**, which the old parser's
  `check` command accepts; the new parser rejects all eight. Across the ten
  changed files, syntax-sweep exact line/message agreement is **6/10**; four
  def/async cases retain the wording difference, with no acceptance disagreement.

These residual diagnostics remain within
[#541](https://github.com/den-run-ai/pystachy/issues/541)'s wording/position scope;
the audit does not close it. Separate malformed-def and malformed-alias controls
reconfirm the pre-existing recovery/heuristic differences on both revisions.
Actual async calls and ParamSpec class compilation remain explicitly rejected on
both revisions. Parsing unused declarations is not execution, reflection or
default-driven inference support. The upstream-derived test keeps its existing
adaptations and omissions; this is not an unmodified CPython type-parameter suite.

### Regression checks and import boundaries

| Fresh check | Result |
|---|---|
| Selected native / GC / optimization-off / hosted configurations | **118/118 each, 472 total**, across 78 programs; includes execution, expected rejection and syntax checks, not 472 unique upstream tests. |
| Changed positive recordings | Both match CPython exactly. |
| UBSan with per-allocation program GC | **5/5** checks on the two changed positive programs. |
| IR validation | Checker and LLVM assembler accept **18/18** selected positive programs. |
| Runtime contracts | **460** entries, **70** exception classes, **171** functions agree. |
| Adapted port smoke | **8/8** JIT/AOT checks over iniconfig, tomli_w, roman and pylev. |
| Retained compile comparison | **3,323/3,331 identical** normalized IR/message/status results. Only the eight new rejection fixtures differ: seven previously compiled invalid programs now reject, and one former unsupported-ParamSpec-class error becomes a syntax error. CPython independently rejects every newly rejected program; no valid-program acceptance regression observed. |

No extra executable changed outside the selected files. Port and benchmark IR
remain identical, which is compile-only evidence, not a fresh upstream execution
or performance result. Broad benchmark reruns were not warranted for this delta.

Fresh isolated sweeps with `--metadata` remain **148/464 native / 150/464
stub-assisted**, the same **58 overlay exclusions**, all **522 CPython source
hashes**, zero timeouts and identical first errors after checkout-prefix
normalization. Throwing stubs are still dependency diagnostics. No new native
library, general PyPI/NumPy or full regrtest support is inferred. Prior minor/major
adaptation assessments and unrelated dated gaps remain; the #763 hosted-cache
coverage limitation was not rerun or erased by this parser-only checkpoint.

Replay `audit-764.py` modes `build`, `references`, `checks`, `sanitize`, `ir`,
`runtime`, `consumer-smoke`, `syntax-sweep`, `oracle`, `extras`, `imports`, `stubs`;
`audit-764-probes.py` modes `retained`, `boundaries`, `fixtures`, `limits`,
`oracle-verdicts`; then the assembler. Scripts retain their `audit-737.py` and
`audit-725.py` dependencies. Every selected evaluation completed; no failed test
attempts. Concurrent shared-host wall times are descriptive, not performance
regression evidence. No full local `make verify` or broad upstream suite was run.

Historical implementation-head **CI, Lint, Packages and Installation all pass**
([CI](https://github.com/den-run-ai/pystachy/actions/runs/39374862632)); the head's
tree equals evaluated main. Those results are separately attributed, not called
local full-matrix runs. Audit-head checks are read after publication. Only report
and evidence changes are added beyond evaluated main, preserving dated baselines
and concurrent edits. No duplicate issue or external-contributor attestation was
created, and no PR was merged by this audit.

## 2026-10-20 — #765: less compiler allocation, unchanged compatibility

Evaluated [main `3ab11f03`](https://github.com/den-run-ai/pystachy/commit/3ab11f03a9b1deedd90141cdf5d7e6345b0af5f0),
the sole first-parent merge since evaluated `4f71b5a0`:
[#765](https://github.com/den-run-ai/pystachy/pull/765). Re-fetched the PR, verified
the merge is in main's history and the tree equals implementation head
`5e997c7548c5a6893d1c5b69ee3007a56b2a2ad9`. Read current audit state and #491/#616
coordination plus the PR review. #743 remains the audit destination; no other
session's implementation branch was modified.

Only `local_versions.py` and `optimizations.py` change: the former builds its
excluded-node-kind dictionary once, rather than splitting the same string at
every visited syntax node; the latter skips definition/use-table construction
when a function has no numeric-union local-slot candidates. No runtime/library
source or supported API is added. Retained selection covers 43 retyping/rebinding
and scalar-union cases, 12 local-flow cases and three union IR-contract programs.

Fresh **CPython 3.13.16 / LLVM 18.1.3** bootstrap reaches both fixed points:
**677,993 compiler / 18,709 runtime IR lines**. Compiler build source and evaluated
source both equal `3ab11f03`; compiler SHA-256:
`8bda6dead36bf97d9208cbd2773f5fd3df224cd71b32e444da1ab87f5a230e87`.
Reference compiler build source is `4f71b5a0`, SHA-256
`dbe44e25653a36004511aeedddec03bdcb0084178b62b1a492793e64b3b8d121`.
[Evidence and replay scripts](compatibility-2026-10-20-compiler-allocations.json)
retain both identities, commands, selected fixture hashes, import metadata,
paired GC samples and all validation results.

### Compatibility and correctness

| Fresh check | Result |
|---|---|
| Native / program-GC-stress / optimization-off / hosted | **78/78 each, 312 total** across 55 programs: 63 checks in the union/rebinding selection and 15 local-flow checks per configuration. Counts include expected rejections, not 312 unique upstream tests. |
| CPython recordings | **22/22** selected positive programs match. |
| UBSan plus per-allocation program GC | **38/38** JIT/AOT checks over 19 union/rebinding programs. |
| Typed IR and LLVM validation | **3/3** union-contract programs pass, including `unionslots.calls`. |
| Runtime contracts | **460** entries, **70** exception classes, **171** functions agree. |
| Consumer execution | **12/12** JIT/AOT checks: four adapted iniconfig/tomli_w/roman/pylev workloads and textwrap/regex consumers. |
| Retained compile oracle | **3,331/3,331 identical** IR, diagnostic and exit-status results after replacing only old/new checkout prefixes. Compiler, runtime, ordinary/rejection/deviation/IR tests and benchmark inputs are included. No newly accepted or rejected program. |

Fresh isolated sweeps with `--metadata` remain **148/464 native** and **150/464
with throwing C-module stubs**, with **58 overlay exclusions**, all **522** pinned
CPython source hashes unchanged, zero timeouts and unchanged first errors after
checkout-prefix normalization. Stubs remain dependency diagnostics. No new
whole-library, PyPI, NumPy or upstream-suite support follows from these results.
Existing adaptation assessments and unrelated gaps retain dated evidence rather
than fresh pass/fail claims; they were not all rerun in this checkpoint.

### Independent compiler-GC sample

After all other audit jobs finished, compiled four retained inputs using both
native compilers with `PYSTACHY_GC=stats PYSTACHY_GC_STRESS=1000`. Three paired
rounds alternate old/new, new/old, old/new, pinned to one CPU on the same shared
Linux host. Every one of the **24 compilations** emits identical normalized IR
for its input. Collection counts are identical across each compiler's three
repetitions; timings below are medians, not CI thresholds.

| Input compiled | Collections, old → new | Wall seconds, old → new | Collector heap peak MiB, old → new |
|---|---|---|---|
| `tests/retype.py` | 10 → 9 | 0.0048 → 0.0035 | 4.0 → 4.0 |
| `tests/union_slots.py` | 57 → 51 | 0.0119 → 0.0107 | 4.1 → 4.1 |
| `tests/upstream_textwrap_wrap.py` | 3,067 → 2,080 | 22.061 → 11.047 | 35.7 → 35.7 |
| `tests/lib_re_ignorecase_repeat.py` | 2,782 → 1,871 | 15.524 → 8.942 | 33.0 → 32.0 |

The larger consumers show **32.2–32.7% fewer collections** and **42.4–49.9% lower
median wall time under this artificial compiler-GC stress**. This is not normal
bootstrap latency, application execution speed, regex matching speed or RSS.
Millisecond-scale small-input timings are noise-sensitive. CPU quota/affinity,
CPU model, per-sample load, raw GC time/heap statistics and timing spread are
retained; no performance regression or universal speedup is inferred.

Replay `audit-765.py` modes `build`, `references`, `checks`, `sanitize`, `ir`,
`runtime`, `consumer-smoke`, `oracle`, `imports`, `stubs`; `audit-765-flow.py`
modes `references`, `checks`; then `audit-765-gc.py` without other audit jobs,
and `audit-765-assemble.py`. The embedded wrappers retain their `audit-737.py`
and `audit-725.py` dependencies. All selected evaluations completed, with no
failed/incomplete attempts. Correctness-group wall times overlap other work and
are not used as performance evidence.

Implementation-head CI, Lint, Packages and Installation all pass. The separately
verified [CI run](https://github.com/den-run-ai/pystachy/actions/runs/39378331400)
includes successful `gc-self` and combined verification-report gates on a tree
identical to evaluated main. Full local `make verify`, full `gc-self`, broad
benchmark execution and CPython regrtest were not repeated. Audit-head checks are
read after publication. Only reviewed report/evidence changes are published
beyond evaluated main; dated baseline files and concurrent edits are preserved.

## 2026-10-20 — #761: opt-in dynamic Any, not general library compatibility

Evaluated [main `3c63613b`](https://github.com/den-run-ai/pystachy/commit/3c63613b9ad4748dfc030fc923f7704e26b21ba9),
the sole first-parent merge after evaluated `3ab11f03`:
[#761](https://github.com/den-run-ai/pystachy/pull/761). Re-fetched the PR, verified
its merge is in main's history and its tree equals implementation head
`b57c93d9ad8f1dd380b4b45f2c170dcbf8b3f469`. Read the latest rolling record,
#491/#616 coordination and the PR's review/fix discussion. #743 remains the
destination; implementation branches were not edited.

The 101-file delta adds a per-module `# pystachy: dynamic-any` pragma, runtime
boxes/dispatch and 37 retained programs: 26 positive, nine rejection and two
documented-deviation cases. Ordinary modules retain inference-only `Any`.
Selected adjacent coverage is 77 existing Any, retyping and scalar-union cases.
The allocation changes already evaluated in #765 are not counted again.

Fresh **CPython 3.13.16 / LLVM 18.1.3** bootstrap reaches **707,289 compiler /
18,709 runtime IR lines** at both fixed points. Compiler build source and
evaluated source are `3c63613b`; executable SHA-256:
`f4d0362a9abd39e18a5457e9ba2beb3f202bc643269288bd050249bd51bf3f31`.
The reference compiler was built from `3ab11f03`, SHA-256
`8bda6dead36bf97d9208cbd2773f5fd3df224cd71b32e444da1ab87f5a230e87`.
[Evidence, programs, fixture hashes and replay scripts](compatibility-2026-10-20-dynamic-any.json)
retain source identity separately from compiler identity.

### Measured behavior

| Check | Fresh result |
|---|---|
| Native / program-GC-stress / optimization-off / hosted | **176/176 each, 704 total**, across 114 programs. Each configuration has 120 positive JIT/AOT checks, four documented-deviation checks and 52 expected rejections. |
| CPython references | **60/60** positive recordings match, including all 26 new positive programs. |
| UBSan plus per-allocation program GC | **56/56** JIT/AOT checks over the 28 new positive/deviation programs. |
| Typed IR / LLVM validation | **26/26** new positive programs accepted by the internal checker and LLVM assembler. |
| Runtime contracts | **488** entries, **70** exception classes and **171** runtime functions agree. |
| Consumer smoke | **12/12** JIT/AOT checks: four adapted iniconfig/tomli_w/roman/pylev workloads plus textwrap and regex consumers. |
| Compile-only corpus comparison | **3,332/3,368 identical** IR, diagnostics and exit statuses; all 36 differences are opt-in fixtures. Every non-opt-in program is identical after checkout-prefix normalization. |
| Benchmark correctness, not timing | All five modes of `tools/dynany_bench.py` agree under CPython, JIT, AOT and GC-stressed AOT: four numeric modes at N=1,000 give checksum **499500**, and the custom graph mode at N=3 gives **729753**. |

Of the 36 changed corpus results, **23** previously rejected sources now emit IR,
**six** previously accepted sources reject in opt-in mode, **five** remain accepted
with changed IR and **two** keep rejecting with changed diagnostics. The six
rejections cover keyword method calls, mutual-return widening, None-first field/
global/list storage and dynamic-to-typed-list conversion. Each was executed under
CPython, the old compiler, and the new compiler with only the pragma removed:
all three produce identical successful outputs. These are explicit opt-in
boundaries, not newly rejected ordinary programs. The unchanged no-pragma-field
rejection is included in the 3,332 identical results.

Two independent programs now match CPython in JIT/AOT, with GC stress and
optimizations disabled, where the reference compiler rejected them: shared list/
dict aliases preserve identity and cycles; an Any closure retains changing values,
and a callable field is captured before a side-effecting argument replaces it.
Eight independent pragma-removal controls retain the old compiler's exit/output.

The six-class cyclic graph copier in `tests/dynany_graph.py` passes, but is a
**purpose-built, major adaptation**, not unchanged `copy.deepcopy`. With the
same stdlib overlay as the sweep, an actual `copy.deepcopy` consumer still fails
JIT/AOT compilation in `copyreg.py:15` on unsupported dispatch-dictionary key
types, identically before and after. This is the first error, not a complete
inventory of that library's blockers. Without an upstream module path, `copy`
is simply unavailable.

### Confirmed boundaries and unchanged import coverage

Independent opt-in probes reproduce the documented limits in native, GC-stressed
and optimization-off JIT/AOT:

- An existing `list[int]` cannot become an Any container; start with
  `list[Any]`. Dynamic keyword calls are rejected.
- A user object boxed as Any is not iterable through its `__iter__` protocol:
  CPython yields `1`; the native probe catches `TypeError`.
- Object-versus-builtin equality skips the object's `__eq__`: CPython prints
  two calls and `True True`; native execution prints `False False`.
- `%` formatting of an Any string raises `TypeError` where CPython prints
  `hello`. The retained annotation-check deviation also continues to pass its
  documented native expectation, not CPython equivalence.

These are already documented prototype boundaries, not newly filed duplicate
bugs. Refs #108/#487/#488/#489; no tracker is treated as complete solely because
#761 merged.

Fresh isolated `--metadata` sweeps stay **148/464 native** and **150/464 with
throwing C-module stubs**, with **58 overlay exclusions**, zero timeouts and
unchanged first errors. All **522** pinned CPython input hashes match the retained
inventory. Stub-assisted import compilation is dependency diagnosis; it is not
execution or an implemented C module. Existing minor/major adaptation assessments
remain scoped to their measured workloads. No general PyPI/NumPy, full upstream
suite or CPython regrtest claim follows.

Replay `audit-761.py` modes `build`, `references`, `checks`, `sanitize`,
`ir`, `runtime`, `consumer-smoke`, `oracle`, `imports`, `stubs`, then
`audit-761-probes.py`, `audit-761-controls.py` and `audit-761-assemble.py`.
Embedded wrappers include their `audit-737.py` and `audit-725.py` dependencies.
Place the retained `typing_extensions` 4.16.0 module on the isolated reference
PYTHONPATH; its hash is recorded. Initial missing-dependency results (three
failures) are preserved; all 60 references passed after correction. A first copy
control incorrectly put raw stdlib ahead of the native overlay, reaching a
different weakref error; that attempt is retained separately, and the corrected
overlay control agrees with the sweep.

Correctness jobs overlapped on a shared host. Benchmark timing fields are retained
but not interpreted; no fresh performance, peak-memory or universal speedup claim
is made. Unrelated gaps were not all rerun. Historical implementation-head CI,
Lint, Packages and Installation all pass; the [CI run](https://github.com/den-run-ai/pystachy/actions/runs/39379732167)
includes successful gc-self and combined verification-report gates on a tree
equal to evaluated main. This is separate from local focused testing, not a local
full `make verify`. Audit-head checks are read after publication. Only reviewed
report/evidence changes are added beyond evaluated main; dated baselines and
concurrent edits are preserved.

## 2026-10-20 — #762: release validation; local native evaluation incomplete

Inspected [main `afb59cd3`](https://github.com/den-run-ai/pystachy/commit/afb59cd3c32eecaa38e4dd6b38ccff17f020ba24),
the sole first-parent merge since fully evaluated `3c63613b`:
[#762](https://github.com/den-run-ai/pystachy/pull/762), merged 2026-10-20 11:11:26 UTC.
Fresh PR metadata, git ancestry and tree comparison confirm the merge and equality
with implementation head `e4613eda2d2f3fa3386e477a2a434a35f1c9ed6e` (tree
`d7b582fa8b1a1101292ca5bc31d87a8835c22d4d`). Read the rolling record, baseline,
#491/#616 coordination and #762/#743 review discussions. No implementation branch
was changed; #743 remains the report destination.

The 38-file delta changes release version/notes, release gating and smoke tools,
documentation, and adds a difflib differential fixture. Compiler/runtime/library
implementation sources are unchanged. The allocation change mentioned in the PR
was already evaluated in #765. This is not a new library-support gain.

[Evidence](compatibility-2026-10-20-release-partial.json) and the
[replay/preflight driver](compatibility-2026-10-20-release-replay.py) distinguish
fresh hosted checks from historical CI. A new checkout was clean before and after
the hosted checks, including untracked and ignored paths. CPython **3.13.16** was
available; no native compiler or complete LLVM 18 toolchain survived locally.
`apt-get update` failed with exit 100 (`setgroups: Operation not permitted`,
`setegid/seteuid: Invalid argument`, apt HTTPS method exit 112). No privileged
retry or permission workaround was attempted. This is an environment blocker,
not a Pystachy compilation failure. **Latest evaluated main remains `3c63613b`.**

| Fresh local check | Result and boundary |
|---|---|
| `python3.13 -B -m unittest discover -s tools -p 'test_release*.py' -v` | **33/33** pass. Includes missing Packages, wrong commit/branch/event, stale success, cancelled runs and missing-workflow diagnostics. Registry/publication operations are mocked; no release was published or promoted. |
| `python3.13 -B -m unittest discover -s tools -p test_workflow_limits.py -v` | **4/4** pass; `sh -n tools/docker_smoke.sh` also passes. This is syntax/contract validation, not a Docker execution. |
| Retained difflib programs | `lib_difflib`, `lib_difflib_grouped`, `lib_difflib_unified`: **3/3** CPython outputs match checked-in recordings; all **3** emit IR through the CPython-hosted compiler. No LLVM assembly or native execution was performed locally. |
| Independent difflib boundary probes | All **4** run under CPython and reject hosted IR compilation: `context_diff` at unsupported `dict(insert=...)`; `ndiff`/`Differ.compare` at recursive `_fancy_helper` yield inference; `HtmlDiff.make_table` at `_file_template` inference. Exact sources/first errors are retained. |
| Provenance regression controls | **5/5** pass, including untracked library/test and ignored-file rejection. No source-clean claim relies on `--untracked-files=no`. |

The new difflib fixture covers unified diff names/dates/context/line endings and
`restore` with a prepared ndiff-style delta. It is upstream-derived selected
coverage, not the full upstream difflib suite. The four failures remain documented
boundaries; no duplicate issues were filed. IR generation is not execution.

Historical CI was re-fetched for the exact implementation head whose tree equals
the inspected main tree: CI, Installation, Lint, Packages and Release all succeeded.
The [CI run](https://github.com/den-run-ai/pystachy/actions/runs/39382506276)
includes successful `gc-self`, complete-report and every-required-group gates.
The [Release run](https://github.com/den-run-ai/pystachy/actions/runs/39382506187)
has successful prepare, container and all three binary-platform jobs; publication
is **skipped**, as expected for a PR. This corroborates the changed archive smoke
on CI, including Linux shared-runtime caching and relocated JSON/Unicode checks;
it does not substitute for the missing local native run or prove a release exists.

Remaining local work: obtain an authorized complete LLVM 18 environment, rebuild
at this source SHA, run the three difflib cases in JIT/AOT (normal and program-GC
stress), and run `tools/release.py` plus `tools/release_smoke.py` on the produced
archive. Keep native compiler hash/build source separate from evaluated source.
Do not advance the evaluated marker until those checks finish. No fresh import
sweep, port/benchmark timings, general NumPy/PyPI claim, full upstream suite or
CPython regrtest is reported. Prior import counts remain historical, not rerun.

The checkpoint index now includes every completed section after `53c17bad`,
including `e33c560e` and latest `3c63613b`, plus this explicitly incomplete attempt.
The dated evidence is unchanged. Audit-head checks are read after publication;
no PR merge or release action is part of this update.

## 2026-10-20 — #771: test-area layout and retained-probe discovery

Evaluated [main `ad19255e448be45ac098443936798755053139d7`](https://github.com/den-run-ai/pystachy/commit/ad19255e448be45ac098443936798755053139d7)
after [#771](https://github.com/den-run-ai/pystachy/pull/771) merged at
2026-10-20 11:38:47 UTC. Fresh PR metadata, git ancestry and tree comparison
confirm implementation head `fdc903f561d64655690f0c1de06ce7335431f9a3` and main
share tree `c9a749176053e0b0cbe67c7dad677e32c0f11523`. First-parent history since
the last fully evaluated main contains #762 and #771 only. #762's preceding
partial evaluation remains explicit above; this bounded tooling evaluation does
not complete its native/release-archive work or advance **latest evaluated main
`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**. Read #491/#616 coordination and
#771 review comments, including the fixed orphan-sidecar finding and final clean
review. No implementation branches were edited.

The 5,671-file merge reorganizes test programs/rejections, moves helper packages,
and updates runners, corpus discovery, shard/coverage/IR/port tools and citations.
The sole changed compiler source, `specs.py`, has an identical parsed AST; its
changes are comment citations. Runtime and library implementations are unchanged.
This is test-tool compatibility, not a new library/API-support claim.

[Machine-readable evidence](compatibility-2026-10-20-test-layout.json) retains
commands, outputs, selected paths/blob hashes, before/after source snapshots and
the exact executed replay driver. Both old `afb59cd3` and new `ad19255e` checkouts
were pristine before generation, including untracked and ignored files. After
hosted checks, tracked/untracked status was empty but ignored
`build/runtime-py.hashes` had been generated; the post-run snapshot is **not**
claimed pristine. CPython was **3.13.16**; there was no local native compiler or
complete LLVM 18 toolchain. Compiler build/hash fields remain null, separate from
the evaluated source SHA. The previously recorded permission blocker was not
bypassed or retried with privileges.

| Fresh local measurement | Result and boundary |
|---|---|
| Old/new suite-and-basename census | **3,301** cases each: **1,458** programs + **1,753** rejections + **90** deviations, identical sets with no duplicates or missing retained sidecars. **265** changed/new sidecars comprise 262 `.path` and three `.out` files. Not all test files are byte-identical; changed-source hashes are retained. |
| Unit tests via `python3.13 -B -m unittest discover -s tools -p PATTERN -v` | **180/180**: `test_*verif*.py` 53 (including six layout controls), `test_typed*.py` 78, `test_port_check.py` 15, `test_re_specialize.py` 14, `test_coverage_report.py` 16, `test_workflow_limits.py` 4. These are tooling tests, not 180 native programs. |
| Corpus and shard contracts | `corpus` selects exactly 3,301; `corpus_strays` is empty. Two shards contain **1,651/1,650** and three **1,101/1,100/1,100**, with exact union and no duplicates. Nine changed shell scripts pass `sh -n`; `tests/verify.sh --list` passes. |
| Planned verification counts | Actual old/new `checks()` functions both yield **5,093** dual-mode and **3,545** single-mode checks. These are calculated planned counts, **not executed JIT/AOT checks**. |
| Moved rejection helper paths | Actual `tests/run.sh` with the CPython-hosted compiler selects **158** `.path` rejection cases: **158 passed, 0 failed**. The `jit aot` argument does not make expected compile-time rejections native executions. |
| Affected recordings and hosted IR | `lib_difflib`, `lib_difflib_grouped`, `lib_difflib_unified`, `os_path_stat`, `realpath`, `module_doc`: all **six** CPython recordings match, including the two expected nonzero exits/final error lines, and all **six** generate hosted IR. No LLVM assembly or native execution follows from IR emission. |

The two program AST changes are the moved-path fixtures `os_path_stat` and
`realpath`; `module_doc`'s helper docstring/recording changes with the new citation.
Other changed program sources have identical ASTs. Sidecar and source hashes in
the evidence retain the exact input differences rather than treating moves as
automatically content-preserving. Shared-host wall times are advisory, not a
performance or memory comparison.

Future retained-probe selection must resolve old `tests/NAME.py` to the unique
`tests/programs/AREA/NAME.py`, and old `tests/errors/NAME.py` to the unique
`tests/errors/AREA/NAME.py`, by **suite plus basename**, failing on zero or multiple
matches. Prefer `tests/corpus.sh` for full selection. Keep adjacent sidecars and
honor `.path` for both programs and rejections; helpers now live under `tests/`.
Historical reports and embedded dated paths remain unchanged: replay them at
their exact evaluated checkout, or explicitly record any relocation. In particular,
#762's three difflib cases now live in `tests/programs/library/`; its outstanding
release validation should retain its own source/version identity.

Replay by extracting `replay_source` from the JSON to `audit-771.py` outside the
clean checkouts, with the retained #762 preflight driver at the relative path
specified in `audit_context.replay` (or explicitly relocate that dependency):
`python3.13 -B audit-771.py NEW_AD19255E OLD_AFB59CD3 OUTPUT.json`.
The driver strips inherited `PYSTACHY_*`, `PYTHONPATH` and `PYTHONHOME`, sets
`PYTHONDONTWRITEBYTECODE=1`, `LC_ALL=C`, `PYSTACHY_JOBS=2`, and verifies preflight
before generating anything. Use fresh trees for replay, not a post-build tree
with the generated hash cache.

Historical implementation-head CI was separately re-fetched: **CI, Lint,
Coverage, Variants, Packages and Installation succeeded** on the identical tree.
The [CI run](https://github.com/den-run-ai/pystachy/actions/runs/39413973802)
has all 27 jobs successful, including gc-self and the final complete-report /
every-required-group gate. This corroboration is not local native validation.
The prior audit-head [Lint](https://github.com/den-run-ai/pystachy/actions/runs/39414015290)
also completed successfully; new audit-head checks are read after publication.
No fresh full `make verify`, import sweep, native port/benchmark execution, full
upstream suite or CPython regrtest was run. Existing import totals and unrelated
gap assessments remain historical, not assumed freshly verified. No duplicate
issue or release action is needed for the measured layout change.

## 2026-10-20 — #785: shared hierarchy comparisons; hosted evidence, native gap

Inspected [main `554f3d1344720dc307b99a6ffa6f8f5a76a2a3ab`](https://github.com/den-run-ai/pystachy/commit/554f3d1344720dc307b99a6ffa6f8f5a76a2a3ab)
after [#785](https://github.com/den-run-ai/pystachy/pull/785) merged at
2026-10-20 18:17:50 UTC. Fresh metadata and ancestry verify the merge; main and
implementation head `e647b02447df971cf1696119715f7b28f6d3fc3b` share tree
`0edfdeca7819e8e401bdd5d9ec1c4c7481adba99`. Since the last full checkpoint, #762
remains partial and #771 has bounded tooling coverage above. Intervening #776 and
#788 change only `AGENTS.md`; they require no compatibility rerun. Read the latest
rolling/baseline records, current guide, #491/#616 coordination, #785 review and
#625/#786/#787 before selecting affected work. No implementation branch was edited.

The change shares comparison arms with the same method instance, operand side,
inversion and coercion types, and adds typed-IR `switch` for ordinary class tags.
Exception class-pointer tests remain comparisons. Runtime/library/port sources
are unchanged, but this is a code-generation change requiring a native rebuild
before native claims. Local **CPython 3.13.16 is now also missing**, along with
LLVM 18: the known paths and a search of available installations found neither.
Available **CPython 3.12.14** can host this compiler. It is explicitly not the
pinned reference, and no recordings were regenerated. No privileged setup or
permission workaround was attempted.

[Evidence and exact embedded replay](compatibility-2026-10-20-hierarchy-partial.json)
retain commands, source hashes, outputs, IR hashes/line counts, versions and
pre/post snapshots. Both evaluated `554f3d13` and reference `16141879` trees were
pristine before generation, including untracked and ignored inputs. Afterwards,
only new-tree ignored `build/runtime-py.hashes` was generated; tracked/untracked
status remained empty. Native compiler build/hash fields are null and separate
from the source revisions. Reference compilation used its own compiler/runtime/lib
and the new selected test source, including the new pairwise regression; `.path`
helpers are unchanged between the two revisions.

| Fresh local check under CPython 3.12.14 | Result and boundary |
|---|---|
| `python3 -B -m unittest discover -s tools -p 'test_typed*.py' -v` | **82/82** pass, including four new `switch` tests: terminator/lowering, invalid shape/cases/labels, duplicate edges into phi, and actual class-tag dispatch. This is the project's typed verifier, not LLVM assembly. |
| Same discovery with `-p 'test_*verif*.py'` | **53/53** harness tests pass; **135** unit tests total. |
| Selected hierarchy/class/dataclass/exception/dynamic-Any inputs | **28/28** compile under both old and new hosted compilers (**56** compilations), with IR checking enabled. **13** have fewer raw IR lines, **15** equal counts, none grow: total **45,166 → 40,233**. Equal line counts are not a byte-equality claim. No whole-corpus acceptance claim follows. |
| `sh tests/run.sh 'python3 -B -m pystachy' 'jit aot' SELECTED_ERRORS` | **30/30** expected compile-time rejections pass. Despite the modes argument, these do not execute native programs. |
| Eight affected reference recordings | CPython **3.12.14** outputs and expected stderr match all eight checked-in recordings: dataclass/hierarchy comparisons, pairwise methods/None/reflected priority, container comparisons, exception comparisons, and dynamic-Any subclass equality/order. This does not establish native parity or a pinned-3.13 rerun. |

The retained `tools/inheritprobe.py::compare_source` generator uses **eight**
comparison sites; both compilers receive each identical generated source. Raw
emitted LLVM line counts (not optimized IR or executable size):

| Base / subclasses | Before `16141879` | After `554f3d13` |
|---|---:|---:|
| Exception / 40 | 95,625 | 4,957 |
| Exception / 80 | 357,105 | 9,317 |
| Ordinary, declared `other: Base` / 40 | 93,851 | 3,263 |
| Ordinary, declared `other: Base` / 80 | 353,611 | 6,063 |

Doubling subclasses now grows these outputs **1.88x / 1.86x**, versus
**3.73x / 3.77x** before. This independently confirms the bounded IR-growth
improvement in [#625](https://github.com/den-run-ai/pystachy/issues/625); it does
not establish universal linear compilation. Pair-key analysis is still quadratic,
and ordinary methods specialized for each receiver/`object` argument pair can
retain quadratic instances. Field-name error dispatch is separately tracked in
[#786](https://github.com/den-run-ai/pystachy/issues/786), compiler receiver-null
checks in [#787](https://github.com/den-run-ai/pystachy/issues/787). Neither issue
was independently remeasured or closed here.

Preserve the implementation PR's explicitly accepted trade-off: it reports
**8.7–18.3% slower AOT wall time** for exception equality calling `str(self)`,
despite fewer instructions, attributed to shared indirect-call targets. Those
are **author-reported measurements, not this audit's timings**. This audit's
shared-host elapsed fields are advisory; no speed, binary-size, peak-memory or
new library-support claim follows from smaller raw IR.

Historical CI was re-fetched on the exact implementation head with main's tree:
Lint, Packages, Installation and [CI](https://github.com/den-run-ai/pystachy/actions/runs/39471120331)
all succeeded. The returned CI list contains all **27** jobs, all successful,
including gc-self and the complete-report/every-required-group gates. Conditional
steps skipped within unrelated groups are retained in the evidence. This is
separate historical CI evidence, not a local rebuild or native correctness run.

Replay the JSON's `replay_source` outside fresh worktrees:
`python3 -B audit-785.py NEW_554F3D13 OLD_16141879 OUTPUT.json`.
The script removes inherited `PYSTACHY_*`, `PYTHONPATH` and `PYTHONHOME`, then sets
`PYSTACHY_IRCHECK=1`, `PYSTACHY_JOBS=2`, `LC_ALL=C` and
`PYTHONDONTWRITEBYTECODE=1`. Inputs/selectors and generated source are retained.
It must not be presented as running all native stages of `tools/inheritprobe.py`.

**Incomplete:** restore an authorized pinned CPython 3.13.16 / complete LLVM 18
environment, rebuild the changed compiler, run selected JIT/AOT and program-GC
comparisons, rerun the pinned inventory/overlay import sweeps with `--metadata`,
and affected native port/benchmark correctness. #762's native difflib/release-smoke
work also remains pending. No replacement 3.12 inventory was used to manufacture
an import delta. Latest fully evaluated main stays
**`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**. Full CPython regrtest and compiled
upstream suites were not run; unrelated known gaps were not freshly checked.

## 2026-10-20 — #792: comparison operand widening; hosted evidence, native gap

Inspected [main `452a0864986b632980f1a23783bdd5b4e4001e5c`](https://github.com/den-run-ai/pystachy/commit/452a0864986b632980f1a23783bdd5b4e4001e5c)
after [#792](https://github.com/den-run-ai/pystachy/pull/792) merged at
2026-10-20 20:18:11 UTC. Fresh metadata and ancestry verify the merge; main and
implementation head `570eb4e5259d4dac7ae86c7ceb333f3e2a663c60` share tree
`4e19388d3fe959c45b34ebefaffab33fdc41a34f`. This is the sole first-parent
merge after the #785 checkpoint. No implementation branch was edited.

The compiler now widens the comparison method's other operand to the method's
declared static type when dispatch analysis proves that the same method, side,
inversion and coercion are selected. This extends #785's shared hierarchy arms
to `other: object` and unannotated comparison parameters. Runtime, libraries and
ports are unchanged, but compiler code generation changed and requires a native
rebuild before native compatibility claims.

[Machine-readable evidence](compatibility-2026-10-20-comparison-widening-partial.json)
retains exact commands, selected source hashes, stdout/IR hashes and line counts,
the prior/current source identities, recordings, rejection output, environment
and pre/post snapshots. Both trees had empty tracked/untracked status before and
after; prior hosted runs had already generated ignored `build/` contents, which
are explicitly recorded rather than called pristine. CPython **3.12.14** hosted
the compiler. Pinned CPython **3.13.16**, LLVM 18 and native execution remain
unavailable, so the latest fully evaluated main stays
**`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**.

| Fresh hosted measurement | #785 `554f3d13` | #792 `452a0864` |
|---|---:|---:|
| Exception base, 40 subclasses / eight sites | 4,957 IR lines | 1,549 |
| Exception base, 80 subclasses / eight sites | 9,317 | 2,509 |
| Ordinary `other: Base`, 40 / 80 subclasses | 3,263 / 6,063 | **byte-identical** 3,263 / 6,063 |
| Ordinary `other: object`, 40 subclasses | 73,420 | 6,860 |
| Ordinary `other: object`, 80 subclasses | rejects above 4,096 specializations | 13,220 |

The 80-subclass result independently confirms that this retained shape now
compiles instead of failing at the specialization limit. Its new 40→80 growth is
1.93x. Raw emitted LLVM line counts are not optimized IR, binary size, compile
time, run time or peak-memory measurements. The declared-`Base` controls'
byte-identical hashes isolate the widening to the intended parameter shape.

| Additional check | Result and boundary |
|---|---|
| Typed/verifier unit discovery | `test_typed*.py` **82/82** and `test_*verif*.py` **53/53** pass; **135** hosted tests total. These do not assemble LLVM. |
| Selected affected sources | All **29** current inputs compile to hosted IR; all **28** that exist at #785 also compile there (**57** successful compilations). Three retained outputs shrink: `inheritance_compare_pairs` 2,698→2,431, `exc_eq_subclass` 7,401→5,174 and `dynany_subclass_eq` 1,200→1,194 lines. The new differential emits 3,640 lines. |
| Expected rejections | **30/30** selected hierarchy/dataclass/exception/generator cases pass through `tests/run.sh`. The `jit aot` label does not turn expected compile-time rejections into native execution. |
| Reference recordings | Four affected programs, including the new 354-line comparison matrix, match checked-in stdout/exit recordings under CPython **3.12.14**. This is not a pinned-3.13 regeneration or native parity. |

Historical workflows on the identical implementation tree all succeeded:
[CI](https://github.com/den-run-ai/pystachy/actions/runs/39483737387),
[Lint](https://github.com/den-run-ai/pystachy/actions/runs/39483737523),
[Packages](https://github.com/den-run-ai/pystachy/actions/runs/39483737509) and
[Installation](https://github.com/den-run-ai/pystachy/actions/runs/39483737540).
The preceding audit-head [Lint](https://github.com/den-run-ai/pystachy/actions/runs/39474255499)
also completed successfully. These are separately labeled historical CI results,
not local native execution.

No fresh import sweep, native JIT/AOT or GC-stress comparison, affected native
port/benchmark execution, full `make verify`, full upstream suite or CPython
regrtest was run. Existing import totals and unrelated gaps remain historical.
The implementation PR's timing tables are not adopted as audit measurements;
no speed or memory claim is made from shared-host elapsed fields. #625 remains
the relevant optimization tracker, and no new uncovered correctness bug was
confirmed, so no new issue was filed. Complete this checkpoint only after an
authorized pinned CPython 3.13.16 / LLVM 18 rebuild, selected native parity and
the pinned metadata-enabled import sweep; #762's release validation remains
independently incomplete.

## 2026-10-20 — #789: concurrency contract and process-pool probes

Inspected [main `870bfa154f940026a7135f5c285fb0df7148ee88`](https://github.com/den-run-ai/pystachy/commit/870bfa154f940026a7135f5c285fb0df7148ee88)
after [#789](https://github.com/den-run-ai/pystachy/pull/789) merged at
2026-10-20 21:40:51 UTC. Fresh ancestry checks confirm implementation head
`208be867a4bebfc6a64e6e726d575ad8e755e2ee` is in main; the implementation and
merge commits share tree `caab22cbf374eac3babc73df0a3c6db477e39d0f`.
It is the only first-parent merge after the #792 checkpoint.

This merge changes documentation, the FFI test runner and clients, a registration
checker, and Lint workflow wiring. It does **not** change compiler, runtime,
library or port implementation sources. Therefore no compiler rebuild, retained
metadata import sweep, API sweep or port/benchmark rerun was warranted for this
bounded tooling checkpoint. Historical import totals and first errors are not
presented as fresh measurements.

[Machine-readable evidence](compatibility-2026-10-20-concurrency-contract.json)
retains the exact source and tree identities, changed-path hashes, commands,
outputs and hashes, environment and clean pre/post snapshots. The fresh checkout
had no tracked, untracked or ignored files before or after the checks.

| Fresh check | Result and boundary |
|---|---|
| Contract registration | `python3 -B -m unittest discover -s tools -p test_concurrency_contract.py -v`: **5/5 pass** under CPython **3.12.14**. This proves the documented capability rows name registered probes on this tree. |
| FFI runner syntax | `sh -n tests/ffi/run.sh`: pass. |
| Process-pool client | With `PYTHONPATH=tools/rt_cpython`, `pwclient.py a b`: exit 0, **25 output lines**. It checks owner-thread refusal before argument conversion, per-process call accounting, maps, exception propagation, continued service after ordinary exceptions, clean shutdown, abrupt-worker `BrokenProcessPool`, and explicit process exit codes. |
| Async bridge client | With the same source twin, `aioclient.py a b`: exit 0, **25 output lines**. It checks thread/default-executor refusal, event-loop progress, await/gather/errors, timeout behavior, and the cancellation boundary between started, dispatched and pending calls. |

The client runs above use Pystachy's CPython source twin, not the compiled native
extension and not JIT/AOT. Native evidence is separately historical: exact-tree
[CI](https://github.com/den-run-ai/pystachy/actions/runs/39495106554) completed
successfully, including `verify (contracts)`, and exact-tree
[Coverage](https://github.com/den-run-ai/pystachy/actions/runs/39495106610) completed
successfully, including `native runtime coverage (ffi)` and
`hosted compiler coverage (ffi, ir)`. Lint, Packages and Installation workflows
on that tree also succeeded. The preceding audit-head
[Lint](https://github.com/den-run-ai/pystachy/actions/runs/39492325867) succeeded.
These workflow results are not relabeled as fresh local native execution.

The result makes the supported source/extension/process behavior and its probes
more explicit; it does not add native threads, parallel loops, or compiled async
execution. No speed, memory, import, package or broad library-compatibility gain
is inferred. The implementation PR's documented `multiprocessing.Pool` limits
were not independently rerun as a negative probe here. No new uncovered
correctness bug was confirmed, so no issue was filed.

Pinned CPython **3.13.16** and local LLVM 18/native extension execution remain
unavailable. That does not make the bounded test-tooling checkpoint incomplete,
because implementation sources did not change and the native contract jobs ran
successfully on the identical tree. It also does not complete #762 or #792's
outstanding native/release work. Latest fully evaluated main therefore remains
**`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**; full CPython regrtest and compiled
upstream suites were not run, and unrelated known gaps were not rechecked.

## 2026-10-20 — #791: dominated null-check elimination; hosted evidence

Inspected [main `100979652775ab55ff2ecfd83750270395ece789`](https://github.com/den-run-ai/pystachy/commit/100979652775ab55ff2ecfd83750270395ece789)
after [#791](https://github.com/den-run-ai/pystachy/pull/791) merged at
2026-10-20 22:21:37 UTC. Fresh history and ancestry checks establish it as the
sole first-parent merge after #789. Implementation head
`c4d28c11d41c8ed876c5cafb5f2140e9db6c0d30` and the merge share tree
`56c70c4875a633b20a0590c1767836c5b0b8c580`.

The compiler gains a typed-IR `nullcheck` pass that removes a repeated null test
only when a passed test of the same canonical value dominates it. It retains
checks after joins, possibly skipped branches/loops, handlers, reassignment and
cell-writing calls. Compiler and typed-IR implementation changed; runtime,
libraries and ports did not.

[Machine-readable evidence](compatibility-2026-10-20-nullcheck-partial.json)
retains exact commands, source and output hashes, changed-path hashes, workflow
links, environment and clean pre/post snapshots. The fresh checkout had no
tracked, untracked or ignored files before or after the run. CPython **3.12.14**
hosted these local compiler checks; pinned CPython 3.13.16 and LLVM 18 were not
available.

The same prior-main `pystachy.py` source was compiled three ways:

| Hosted compiler | Raw LLVM lines | Null-pointer tests | `pys_raise` calls |
|---|---:|---:|---:|
| Previous `870bfa15` compiler | 710,837 | 36,182 | 16,911 |
| Current `10097965`, `PYSTACHY_OPT=-nullcheck` | 710,837 | 36,182 | 16,911 |
| Current `10097965`, pass enabled | **621,696** | **13,978** | **9,403** |

The disabled output is byte-identical to the previous compiler. Enabling the
pass independently reduces raw IR lines by **12.54%** and null-pointer tests by
**61.37%** on this input. These are unoptimized hosted LLVM-text counts, not
binary size, compile time, runtime, memory, JIT machine code or universal
scaling measurements.

The new path-sensitive program provides a smaller disable control: previous and
current-disabled outputs are byte-identical at 1,214 lines, 22 null tests and 16
raise calls; enabled output has 1,184 lines, 14 null tests and 14 raise calls.
Its CPython 3.12.14 output exactly matches the checked-in recording after the
recording's exit marker is separated.

| Additional fresh hosted check | Result and boundary |
|---|---|
| Typed-IR tests | `test_typed*.py`: **84/84 pass**, including both new dominance/cold-block tests. |
| Verification tooling | `test_*verif*.py`: **53/53 pass**. Combined hosted unit/verification total: **137/137**. |
| Changed call contracts | `index_key`, `init_hasattr` and `reflect_effects` compile with the internal IR checker; extracted runtime calls match all three updated `.calls` fixtures. LLVM assembly was not run locally. |
| Scaling controls | Hosted `nulls`, `fields` and `long` at N=500/1000 pass `--ops --check`. Executed-line and flow counts grow exactly 2.0x; item work grows 1.0x for `nulls` and 2.0x for both controls. One-run elapsed values are retained only as advisory output. |

Historical workflows on the identical implementation tree all succeeded:
[CI](https://github.com/den-run-ai/pystachy/actions/runs/39503338365) has
**27/27 successful jobs**, including bootstrap, gc-self, contracts, scaling,
native, hosted, GC, UBSan, runtime-cache and final `make verify` gates;
[Coverage](https://github.com/den-run-ai/pystachy/actions/runs/39503338411)
has 19 successful jobs with only the main-only badge publication skipped.
[Lint](https://github.com/den-run-ai/pystachy/actions/runs/39503338360),
[Packages](https://github.com/den-run-ai/pystachy/actions/runs/39503338413) and
[Installation](https://github.com/den-run-ai/pystachy/actions/runs/39503338340)
also succeeded. The preceding audit-head
[Lint](https://github.com/den-run-ai/pystachy/actions/runs/39502760660) succeeded.
These are historical exact-tree CI results, not relabeled local execution.

The PR's Codex review completed without findings at `0cf7de2`; later commits
merged newer main revisions. No substantive review thread was present. This
audit verified the final tree and behavior above but does not treat that earlier
review as a review of a different final commit.

Preserve the implementation PR's performance risk as **author-reported, not
independently timed here**: it reports about +2.9% frontend instructions and
+10% median frontend wall time for self-compilation, largely from one extra
collection, while whole AOT-build and selected runtime differences were within
that setup's noise. The independent audit claims only the deterministic IR
reductions and disable controls above.

No local native JIT/AOT, GC-stressed execution, LLVM assembly, cache suite,
metadata-enabled import sweep, adapted port/benchmark run, full upstream suite
or CPython regrtest was run. Existing import totals and first errors remain
historical; no new library-support, runtime-speed or peak-memory claim follows.
No uncovered correctness bug was confirmed, so no new issue was filed. Complete
the compiler checkpoint with an authorized pinned CPython 3.13.16 / LLVM 18
rebuild, selected native parity and the pinned import sweep. #762 and #792's
outstanding native/release work also remains. Latest fully evaluated main stays
**`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**.

## 2026-10-20 — #793/#790: JIT landing pads and dynamic Any follow-up

Inspected [main `3d48ce8c8f24fe15f42ba3fa0491fabdd6e7fa15`](https://github.com/den-run-ai/pystachy/commit/3d48ce8c8f24fe15f42ba3fa0491fabdd6e7fa15)
after [#793](https://github.com/den-run-ai/pystachy/pull/793) and
[#790](https://github.com/den-run-ai/pystachy/pull/790) merged in that order at
2026-10-20 23:21:06 and 23:23:47 UTC. Fresh ancestry checks put both implementation
heads in main. #793 head `72d6941e` and merge `a79e6bbc` share tree `a8e2778a`;
#790 head `8706e3f9` and merge `3d48ce8c` share tree `3a5a386c`. #790 incorporates
the #793 driver change, so the final main diff contains one copy rather than a
second behavioral change.

#793 adds `lli -profile-guided-section-prefix=false` to the JIT driver. It keeps
cold functions in `.text`; on LLVM 18 ORC this preserves landing pads moved into
`main` by inlining, so the selected dynamic-call `try` catches its `KeyError`
instead of terminating. This changes JIT code placement, not compiler IR. A
hosted before/after oracle confirms all **138/138** selected dynamic-Any and
exception programs emit byte-identical IR, **53/53** verification-tool tests
pass, and the new CPython 3.12.14 reference matches its recording. Local LLVM 18
was unavailable, so the actual JIT result is retained separately from exact-tree
CI rather than relabeled as a local native reproduction.

#790 extends the explicitly opt-in dynamic `Any` prototype. The measured changes
cover `Any`-parameter comparison methods and CPython rich-comparison order,
container/dictionary search, structural NamedTuple equality and hashing, equality
between typed and `Any` items, `format()` dispatch, slices, selected type metadata,
`sum(generator)` and `dict.update`. Dry-run memoization also removes the retained
nested-display compilation blow-up. These results remain opt-in prototype scope,
not general Python, PyPI or NumPy compatibility.

[Machine-readable evidence](compatibility-2026-10-20-dynamic-any-followup-partial.json)
retains exact source/tree identities, commands, key input hashes, results,
workflow links, review state, environment and source snapshots.

| Fresh local hosted measurement | Result and boundary |
|---|---|
| New positive references | **29/29** CPython 3.12.14 stdout/exit recordings match. This is not a pinned-3.13 regeneration. |
| New compiler inputs | All **29** positive and **2** deviation programs emit checked hosted IR: **31/31**, 35,570 raw lines total. The new expected rejection exits 1 with the exact diagnostic. |
| Targeted unit tests | `test_typed_comparisons`, `test_typed_nullcheck` and `test_concurrency_contract`: **19/19** pass (12 + 2 + 5). |
| Retained adapted consumers | iniconfig, tomli-w, roman, pylev, textwrap and regex: **6/6** emit checked hosted IR. A local `tests/run.sh` JIT/AOT attempt ran **0/12** native checks because `clang`/LLVM 18 was absent; hosted compilation is not counted as a port pass. |
| Deep nested displays | The current compiler finishes the retained depth-199/wider-tree input in **7.96s**, emitting 3,343 raw lines; `10097965` exceeds a **20s** bound. One shared-host run proves bounded progress/completion, not a stable speed ratio or universal linear scaling. |
| Non-opt-in oracle | **1,467/1,467** pre-existing positive programs present at both revisions, excluding dynamic-Any headers, emit byte-identical hosted IR after absolute roots are normalized with equal-length paths. A broader 3,336-source attempt exposed path and rejected-output harness artifacts and is retained as incomplete, not counted as an equality result. |

Two deviations are explicit rather than counted as passes. A comparison method
with a concrete/unsupported annotation, or a body that cannot compile for `Any`,
can fall back to identity or generic ordering where CPython runs the method.
Custom objects still are not iterable through `Any`, so a custom pair object in
`dict.update` raises `TypeError` rather than being iterated. The implementation
PR's review had seven earlier threads: six were fixed with tests and one became
the documented deviation; all are resolved. Its final Codex review completed
without findings. #793 had no inline thread and its Codex review completed
without findings before later main merges.

Historical workflows on both identical implementation trees succeeded. For
#793, [CI](https://github.com/den-run-ai/pystachy/actions/runs/39509843577)
has **27/27 successful jobs**, and Installation, Lint and Packages succeeded.
For #790, [CI](https://github.com/den-run-ai/pystachy/actions/runs/39509136079)
also has **27/27 successful jobs**, and Installation, Lint and Packages succeeded.
Those matrices include native, hosted, GC/UBSan, Python-free, optimization-off,
runtime-cache, benchmark and final `make verify` gates. They are exact-tree
historical CI evidence, not fresh local JIT/AOT execution.

No new uncovered correctness bug was confirmed, so no issue was filed. Pinned
CPython **3.13.16** and LLVM 18 were unavailable locally. No local native JIT/AOT,
GC-stress, metadata-enabled import sweep, native adapted-port benchmark, full
upstream suite or CPython regrtest completed. Existing import totals and unrelated
gaps remain historical; no runtime-speed, peak-memory or broad library-support
claim follows. Complete this checkpoint after an authorized pinned rebuild,
selected native parity and the retained import sweep. The latest fully evaluated
main therefore remains **`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**.

## 2026-10-20 — #794: MappingProxyType and five tomllib prerequisites

Inspected [main `387059bac6f2eec2940d66cdaa435e3132e92890`](https://github.com/den-run-ai/pystachy/commit/387059bac6f2eec2940d66cdaa435e3132e92890)
after [#794](https://github.com/den-run-ai/pystachy/pull/794) merged at
2026-10-21 00:32:50 UTC. Fresh history and ancestry checks establish it as the
only first-parent merge after the #793/#790 checkpoint. Implementation head
`afcaca9059a5ad453465c89191d26a929164f1c1` is in main, and the head and merge
share tree `97c5f199045a949d02737d5bbfa549ffbd443eea`.

This merge removes five of [#783](https://github.com/den-run-ai/pystachy/issues/783)'s
general `tomllib`/tomli-w blockers and #778's two tuple cases:
`types.MappingProxyType`; runtime-length tuple `+`/`+=`; item-wise opt-in
dynamic-`Any` tuple conversions; `GenericAlias` annotation subscripts including
`re.Pattern[str]`/`re.Match[str]`; base/subclass union pruning, including nested
union aliases; and the exception-class `__module__` assignment that `tomllib`
uses. The merge does **not** include stacked #795, so this checkpoint does not
claim that `tomllib.loads()` has shipped.

[Machine-readable evidence](compatibility-2026-10-20-tomllib-blockers-partial.json)
retains exact source/tree identities, commands, selected input hashes, results,
workflow links, review state, environment and clean pre/post source snapshots.

| Fresh local hosted measurement | Result and boundary |
|---|---|
| New positive references | **14/14** CPython 3.12.14 stdout, final stderr line and exit recordings match. This is not a pinned-3.13 regeneration. |
| New compiler inputs | All **14** positive and **3** documented-deviation programs emit checked hosted IR: **17/17**. |
| Changed rejection contracts | **6/6** exact diagnostics pass through `tests/run.sh`. These are compile-time checks; its `jit aot` label does not make them native executions. |
| Targeted compiler tests | `test_typed_comparisons`, `test_typed_module_lowering`, `test_typed_fields` and `test_typed_complete`: **25/25** pass. |
| Retained adapted consumers | iniconfig, tomli-w, roman, pylev, textwrap and regex: **6/6** emit checked hosted IR and **6/6** CPython recordings match. This is not an upstream-suite or native port pass. |
| Library initialization controls | The retained regex input grows **55,138→55,346** raw hosted IR lines (+208), and the retained `types` input **658→694** (+36). The retained tomli-w table input stays byte-identical at **10,653** lines. These are LLVM-text counts, not runtime, compile-time, binary-size or memory measurements. |

The focused programs cover a live read-only mapping view whose backing dictionary
is not program-visible, tuple concatenation on either side of fixed tuples and
optional-`None` widening, dynamic tuple boxing/unboxing with aliases, generic
annotations, flat and nested class-family unions, and exception-module display
and declared-field behavior. Three cases remain explicit deviations rather than
being counted as CPython parity: an incompatible `Any` tuple item, assigning an
exception class to the `builtins` module, and mapping-proxy equality with a custom
reflected object.

[#783](https://github.com/den-run-ai/pystachy/issues/783) remains the appropriate
tracker for the unshipped `tomllib`/tomli-w boundaries: sets containing a
runtime-length tuple, whole-match `Match.group()` typed as optional, function-level
imports in an imported module, tuples of classes held in variables, binary
`load(fp)` ([#493](https://github.com/den-run-ai/pystachy/issues/493)), and
`list.extend()` from a runtime-length tuple. General post-class attribute writes
remain [#244](https://github.com/den-run-ai/pystachy/issues/244). No duplicate
issue was filed.

All **8/8** Codex inline review threads are resolved. Seven findings were fixed
with regressions; the reflected proxy comparison became the documented deviation.
The exception-module allocation finding was only partly fixed: assigning the same
name reuses its buffer, but assigning a different string retains the old native
buffer, so a loop of distinct names grows by one short string each time. The final
head `afcaca90` fixes the eighth, nested-union finding and has exact-tree CI, but
was not itself sent through a sixth Codex review; this audit does not represent it
as a final no-findings review.

Historical workflows on the identical implementation tree succeeded:
[CI](https://github.com/den-run-ai/pystachy/actions/runs/39520378605) has
**27/27 successful jobs**, including bootstrap, native/hosted, GC, UBSan,
Python-free, optimization-off, contracts, runtime-cache, benchmark and final
`make verify` gates; [Installation](https://github.com/den-run-ai/pystachy/actions/runs/39520379785)
has **3/3** successful platform jobs; [Lint](https://github.com/den-run-ai/pystachy/actions/runs/39520378614)
and [Packages](https://github.com/den-run-ai/pystachy/actions/runs/39520378556)
succeeded. These are exact-tree external results, not relabeled as fresh local
native execution.

Pinned CPython **3.13.16** and LLVM 18 were unavailable locally. Therefore no
local native JIT/AOT, GC-stress, AOT build, metadata-enabled isolated import
sweep, native adapted-port benchmark, full upstream suite or CPython regrtest
completed. Existing import totals and first errors remain historical. No broad
tomllib, PyPI, NumPy, runtime-speed or peak-memory claim follows. Complete this
checkpoint after an authorized pinned rebuild, selected native parity and the
retained import sweep. The latest fully evaluated main remains
**`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**.

## 2026-10-20 — #795: CPython tomllib.loads() port

Inspected [main `1cf6a676633a5d3e703648d26e3fe328d884b726`](https://github.com/den-run-ai/pystachy/commit/1cf6a676633a5d3e703648d26e3fe328d884b726)
after [#795](https://github.com/den-run-ai/pystachy/pull/795) merged at
2026-10-21 00:37:17 UTC. Fresh first-parent history and ancestry checks establish
it as the only merge after #794. Implementation head
`b607b51f4a2cb8a5e3cee19736c8ac9d219c5736` is in main, and the head and merge
share tree `d42da0970158788551dc6be77bcb7aebf077b534`.

This merge adds the maintained CPython 3.13.16 `tomllib` parser as a Pystachy
library port, including `loads()`, `TOMLDecodeError` and dynamically typed TOML
values. It changes library, tests and documentation only; compiler, runtime and
test-runner sources are unchanged from #794. Binary-file `load()` is deliberately
not exposed because binary file support remains
[#493](https://github.com/den-run-ai/pystachy/issues/493).

[Machine-readable evidence](compatibility-2026-10-20-tomllib-port-partial.json)
retains exact source/tree identities, commands, input and landed-file hashes,
results, upstream provenance, workflow links, review state, adaptations,
limitations and clean pre/post source snapshots.

| Fresh local hosted measurement | Result and boundary |
|---|---|
| Reference recordings | **5/5** stdout, final stderr line and exit recordings match hosted CPython 3.12.14. This is not a pinned-3.13 regeneration. |
| Hosted compiler inputs | All **5/5** emit checked hosted IR. Raw LLVM-text sizes are 66,494; 64,480; 61,622; 62,417; and 62,995 lines. These are not runtime, compile-time, binary-size or memory measurements. |
| Acceptance transition | Against exact prior source `387059ba`, all **5/5** inputs change from the exact unsupported-`tomllib` module rejection to successful checked IR. |
| Upstream-derived data corpus | **62** documents are exercised: **12** valid and **50** invalid, with exact result or error-message recordings. |
| API scope | The focused cases cover strings, integers, floats, booleans, dates, times, datetimes, arrays, tables, inline tables, dotted keys, dynamic access and uncaught parse errors. Binary `load(fp)` is not tested or supported. |

The landed `lib/tomllib/__init__.py` hash matches the upstream-package hash
recorded in its README, and the evidence file records hashes for all four shipped
library files and all five retained programs. This is an adapted, hosted parser
and data-corpus check, not a run of CPython's full `test_tomllib` suite. Decimal
hooks, copy/deepcopy, binary `load()`, `test.support` helpers and recursion-limit
scaffolding are outside this checkpoint.

Exact-tree external workflows succeeded:
[CI](https://github.com/den-run-ai/pystachy/actions/runs/39521093627) has
**27/27 successful jobs**, including bootstrap, native/hosted, GC, UBSan,
Python-free, optimization-off, contracts, runtime-cache, benchmark and final
`make verify` gates; [Installation](https://github.com/den-run-ai/pystachy/actions/runs/39521093470)
has **3/3** successful platform jobs; [Lint](https://github.com/den-run-ai/pystachy/actions/runs/39521093578)
and [Packages](https://github.com/den-run-ai/pystachy/actions/runs/39521093573)
succeeded. These validate the identical implementation tree but are not relabeled
as fresh local native execution.

The PR has no inline review threads. Its Codex review completed without findings
at `ce1071f1aeabc9f40eba73d5fd286344d9b46810`; later changes only merged the #794
implementation heads and moved explanatory documentation. The final exact tree
has the green workflow set above, but this audit does not represent the earlier
review as a second review of those later merge commits.

The port retains documented adaptations: tables use the existing empty-helper
pattern ([#777](https://github.com/den-run-ai/pystachy/issues/777)); flags and
pending containers use typed list-backed forms
([#775](https://github.com/den-run-ai/pystachy/issues/775),
[#783](https://github.com/den-run-ai/pystachy/issues/783)); a local callable
boundary remains [#782](https://github.com/den-run-ai/pystachy/issues/782); and
regex group optionality is narrowed at the parser boundary under #783. Dynamic
`Any` behavior remains intentionally distinct from general CPython/PyPI
compatibility.

Pinned CPython **3.13.16** and LLVM 18 were unavailable locally. Therefore no
local native JIT/AOT, GC-stress, AOT build, metadata-enabled isolated import
sweep, native port benchmark, full upstream suite or CPython regrtest completed.
Existing import totals and unrelated first errors remain historical. No broad
PyPI, NumPy, runtime-speed or peak-memory claim follows. Complete this checkpoint
after an authorized pinned rebuild, selected native parity and the retained import
sweep. The latest fully evaluated main remains
**`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**.

## 2026-10-20 — #806: dynamic Any in-place dispatch and operator messages

Inspected [main `20d1aa299f99737447633b4f6bfae7c75be14774`](https://github.com/den-run-ai/pystachy/commit/20d1aa299f99737447633b4f6bfae7c75be14774)
after [#806](https://github.com/den-run-ai/pystachy/pull/806) merged at
2026-10-21 06:30:53 UTC. Fresh first-parent history and ancestry checks establish
it as the only merge after #795. Implementation head
`4fd6775bcdbb3ff717d8fdfe8a8123c8b0d32b3a` is in main, and the head and merge
share tree `3bfbdbbe436eb7c20b81ee489ffa4e34ab542803`.

This merge fixes a silent wrong result as well as diagnostic text in modules that
opt in to dynamic `Any`. When an annotated or otherwise typed target has an `Any`
right operand, an in-place operation now keeps the in-place dispatcher: the
selected `P.__ipow__` and subclass `R.__iadd__` cases mutate and retain the
original object as CPython does, instead of running `__pow__`/the annotated base's
`__add__` and producing a new object. Unsupported dynamic arithmetic also names
all twelve `OP=` forms, binary exponentiation as `** or pow()`, and the special
dict/object `*=` path as CPython does. [#798](https://github.com/den-run-ai/pystachy/issues/798)
is the original tracker; no new issue was filed.

[Machine-readable evidence](compatibility-2026-10-20-dynamic-inplace-partial.json)
retains exact source/tree identities, commands, hashes, before/after results,
workflow jobs, review state, setup corrections, environment and clean source
snapshots.

| Fresh local hosted measurement | Result and boundary |
|---|---|
| Selected references | **66/66** CPython 3.12.14 stdout, final stderr line and exit recordings match: 59 `dynany_*`, two scalar-union arithmetic and five `tomllib` programs. This is not a pinned-3.13 regeneration. |
| Hosted compiler inputs | All **66/66** emit checked hosted IR. This is compilation, not native execution. |
| Retained before/after oracle | All **64/64** pre-existing selected inputs emit byte-identical hosted IR after equal-length checkout-root normalization. |
| New in-place regression | `dynany_inplace_typed` changes **593→633** raw IR lines; three binary-dispatch sites become in-place sites and emit `P.__ipow__` plus subclass `R.__iadd__`. |
| New message regression | `dynany_op_messages` remains **1,693** raw IR lines while four typed/attribute/item call sites switch from `dyn.op` to `dyn.iop`; `runtime.c` provides the corrected operator text. |
| Targeted unit tests | `tools.test_typed_comparisons`: **12/12** pass. |

The two raw LLVM-text counts describe emitted IR, not runtime speed, compile time,
binary size or memory. The first reference comparison omitted the checked-in
`[exit N]` marker and therefore falsely classified all 66 recordings as different;
the corrected replay appended the marker and passed 66/66. The first IR comparison
also used unequal-length checkout roots, making five `tomllib` files look different
only in embedded path-string lengths. Recompiling the prior source from an
equal-length root made those five byte-identical. Both corrections and the failed
attempts are retained in the JSON rather than silently discarded.

Exact-final-tree external workflows succeeded:
[CI](https://github.com/den-run-ai/pystachy/actions/runs/39552578062) has
**27/27 successful jobs**, including bootstrap, native/hosted, GC, UBSan,
Python-free, optimization-off, contracts, runtime-cache, benchmarks and final
`make verify`; [Installation](https://github.com/den-run-ai/pystachy/actions/runs/39552578042)
has **3/3** successful platform jobs; [Lint](https://github.com/den-run-ai/pystachy/actions/runs/39552578043)
and [Packages](https://github.com/den-run-ai/pystachy/actions/runs/39552578080)
each succeeded. These validate the identical implementation tree but are not
relabeled as fresh local native execution. The implementation PR separately
records a pinned CPython 3.13.16/LLVM 18.1.3 build, 140 selected JIT/AOT checks,
four new-program GC-stressed JIT/AOT checks and a 3,429/3,431 byte-identical
`irsame` result; those are retained as PR-reported evidence, not audit-local runs.

Codex reviewed the first head and the final `4fd6775b` head and reported no major
issues; there are no inline threads. The final exact tree has the green workflow
set above. [#810](https://github.com/den-run-ai/pystachy/issues/810) remains the
dynamic dict `|`/`|=` gap, and [#797](https://github.com/den-run-ai/pystachy/issues/797)
tracks the remaining dynamic `is`/`id()` mismatches found by the fuzzer.

Pinned CPython **3.13.16** and LLVM 18 were unavailable locally. Therefore no
fresh local native JIT/AOT, fixed-point build, GC stress, metadata-enabled isolated
import sweep, full `make verify`, FFI/cache suite or CPython regrtest completed.
Existing import totals and unrelated first errors remain historical. No broad
dynamic-Python, PyPI, runtime-speed or peak-memory claim follows. Complete this
checkpoint after an authorized pinned rebuild, selected native parity and the
retained import sweep. The latest fully evaluated main remains
**`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**.

## 2026-10-20 — #811: dynamic Any class-id dispatcher switch

Inspected [main `730886ea84d9f8d655e2da0d6b0ec98804b43e8b`](https://github.com/den-run-ai/pystachy/commit/730886ea84d9f8d655e2da0d6b0ec98804b43e8b)
after [#811](https://github.com/den-run-ai/pystachy/pull/811) merged at
2026-10-21 06:50:56 UTC. Fresh first-parent history and ancestry checks establish
it as the only merge after #806. Final implementation head
`33a99f0a7ed6779477b32f3e034ee485a6684cea` and merged main share tree
`68f6497fa3fb9424e84f17d5893fcec2e9ac527f`.

This is step 1 of [#799](https://github.com/den-run-ai/pystachy/issues/799).
Every generated `@dyn.*` dispatcher previously compared its receiver's
`DynType` with each supported boxed class in sequence. It now loads the dense
class id stored in the `DynType` and selects one exact class case with an LLVM
`switch`; builtin and function values retain the generic fallback. This removes
the class-position-dependent branch chain. It does not yet make the dispatcher
constant-size: each supported class still has an emitted operation arm.

[Machine-readable evidence](compatibility-2026-10-20-dynamic-dispatch-switch-partial.json)
retains exact source/tree identities, commands, selected inputs, landed-file
hashes, before/after IR hashes, synthetic probe source hashes, workflow jobs,
review state, environment, limitations and clean pre/post source snapshots.

| Fresh local hosted measurement | Result and boundary |
|---|---|
| Selected hosted compiler inputs | All **69/69** common positive/deviation inputs compile both before and after; the new differential test also compiles, for **70/70** on current main. Compiler stdout/stderr remain equal for all 69 common inputs. |
| Retained rejection contracts | **10/10** dynamic-`Any` rejections keep the exact status, stdout and diagnostic text. |
| Before/after IR isolation | **12/69** common positive inputs are byte-identical. All **57/57** changed inputs become byte-identical after removing only `@dyn.*` function definitions; no non-dispatch IR difference remains. |
| New differential reference | Hosted CPython 3.12.14 output, empty stderr and exit marker match the checked-in `dynany_dispatch_switch.out`. This is not a pinned-3.13 regeneration. |
| Two-class synthetic getter | The dispatcher changes from **0 switches / 45 lines** to **one two-case switch / 43 lines**; whole-program IR is 259→257 lines. |
| Sixteen-class synthetic getter | The dispatcher changes from **0 switches / 241 lines** to **one 16-case switch / 197 lines**; whole-program IR is 1,085→1,041 lines. |
| 128-class synthetic getter | The dispatcher changes from **0 switches / 1,809 lines** to **one 128-case switch / 1,429 lines**; whole-program IR is 7,693→7,313 lines. |

The synthetic results establish emitted dispatcher structure and bounded LLVM
text size only. They do not establish LLVM's eventual jump-table lowering,
executed instruction counts, runtime speed, binary size or memory. The PR's
separate pinned LLVM 18.1.3 callgrind measurements report a 128-class field read
at approximately 140 instructions for last, mixed and skewed receiver sets,
versus 524, 333 and 505 on the preceding chain; the first receiver changes
117→119. Those figures are PR-reported, not independently re-timed here, and the
PR correctly makes no application-wide speedup claim.

Exact-final-tree external workflows succeeded:
[CI](https://github.com/den-run-ai/pystachy/actions/runs/39555933460) has
**27/27 successful jobs**, including bootstrap, native/hosted, GC, UBSan,
Python-free, optimization-off, contracts, runtime-cache, benchmarks and final
`make verify`; [Installation](https://github.com/den-run-ai/pystachy/actions/runs/39555933520)
has **3/3** successful platform jobs; [Lint](https://github.com/den-run-ai/pystachy/actions/runs/39555933495)
and [Packages](https://github.com/den-run-ai/pystachy/actions/runs/39555933430)
each succeeded. These validate the identical final implementation tree but are
not relabeled as fresh local native execution. Codex reviewed the implementation
commit `f98d583a` and reported no major issues; the later final head merges #806
without changing the #811 implementation patch.

The remaining work stays under #799: one lookup per method call, per-selector
field tables, selective dispatcher recompilation and a deterministic native
instruction-count guard. The merge hand-off also notes that
`docs/dynamic-any.md` still describes the old linear `DynType` chain and
recommends recording each emitted class id with its `DynType` to make any future
id desynchronization fail loudly. Neither note reproduces a current wrong result,
so no duplicate issue was filed.

Pinned CPython **3.13.16** and LLVM 18 were unavailable locally. Therefore no
fresh local native JIT/AOT, fixed-point build, GC stress, metadata-enabled isolated
import sweep, callgrind measurement, full `make verify`, FFI/cache suite or
CPython regrtest completed. Existing import totals and unrelated first errors
remain historical. No broad dynamic-Python, PyPI, runtime-speed or peak-memory
claim follows. Complete this checkpoint after an authorized pinned rebuild,
selected native parity and the retained import sweep. The latest fully evaluated
main remains **`3c63613b9ad4748dfc030fc923f7704e26b21ba9`**.
