# Rolling compatibility findings

This log tracks changes after the [2026-10-17 audit](compatibility-2026-10-17.md).
Keep the original measurements as a historical baseline. Append new measurements
with the exact main SHA, merged PRs, commands, inputs and observed outcomes.
Do not replace a result merely because a PR description predicts an improvement.

**Latest evaluated main:** `cad7e04206d3743ac18284a5e33f49da86aa6206`.
**Baseline audit PR:** [#635](https://github.com/den-run-ai/pystachy/pull/635).

## Checkpoints

| Check | Main / changes since baseline | Findings |
|---|---|---|
| 2026-10-17 initial audit | `d3fbfc6f`; includes #598, #599 and #603 | 141/476 import programs compile; 46 upstream files excluded by overlay. 501 selected stdlib checks and 62 port checks pass; all 18 adapted benchmark programs match. Detailed evidence is linked from the baseline. |
| 2026-10-17 follow-up | Same `d3fbfc6f`; no additional merges | Existing results still describe current main. No unchanged full suites were rerun. #600–#602, #604–#609, #622–#624, #629–#634, #583 and #170 remain open at this checkpoint; proposed support is not counted as shipped. |

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

## Checks to run when the pending work lands

These are impact targets, not assertions that the PR will make the whole module
or package work. Combine consecutive relevant merges into one measured revision
when practical, preserving attribution and the previous result.

| Pending work | Focused remeasurement |
|---|---|
| #600 import rebinding, #601 namedtuple | Stdlib import sweep with identical CPython inventory; `unittest` and unmodified fnmatch harness probes; inspect/socket-related first errors. Record subsequent blockers instead of declaring the harness supported. |
| #602 `sys.warnoptions` | Warnings-dependent imports and package probes. Preserve whether a probe uses the stdlib overlay or only package/dependency roots. |
| #606 TextIOWrapper, #608 token | Tokenize/inspect/doctest import and selected API probes; distinguish remaining module-level `del` (#612) from completed io/token support. |
| #607 Any signatures and #629–#631 variable/constructor/iterator inference | Exact upstream and minimal-adaptation package probes, especially tomli-w/ordered-set/pyfiglet/iniconfig; retained port workloads; Any metadata and iterator contracts. Cache signature inference (#620) remains a separate question. |
| #632 item mutation templates, #633 generator channels, #634 recursive diagnostics | Mutation and generator-channel tests; iniconfig iterator probe; forwarding recursion (#595) versus improved diagnostics. Do not treat an improved diagnostic as acceptance. |
| #604 replace, #605 owned-string capacity trim | Bounded/unbounded replacement correctness, selected port text workloads and memory probes. Separate capacity/peak-memory results from throughput; retain input sizes and GC settings. |
| #623 shared short strings, #624 regex subject retention | Regex tests, split/subject-retention probes and selected regex timings; distinguish allocation/cache lifetime changes from matcher speed. |
| #622 imported decorator names | Decorated imported-function diagnostics and affected API probes. Record diagnostic improvements separately from compatibility gains. |
| #170 CPython embedding; follow-ups to merged #583/#609 | Example/FFI checks and explicit interop calls. Classify standalone compiled arrays and embedded CPython separately from native NumPy/PyPI compatibility. |
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
