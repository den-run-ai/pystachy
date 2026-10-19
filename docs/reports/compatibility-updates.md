# Rolling compatibility findings

This log tracks changes after the [2026-10-17 audit](compatibility-2026-10-17.md).
Keep the original measurements as a historical baseline. Append new measurements
with the exact main SHA, merged PRs, commands, inputs and observed outcomes.
Do not replace a result merely because a PR description predicts an improvement.

**Latest evaluated main:** `898d0b95f66772774b59137b1eeb5791ff17e8e5`.
**Baseline audit PR:** [#635](https://github.com/den-run-ai/pystachy/pull/635).

## Checkpoints

| Check | Main / changes since baseline | Findings |
|---|---|---|
| 2026-10-17 initial audit | `d3fbfc6f`; includes #598, #599 and #603 | 141/476 import programs compile; 46 upstream files excluded by overlay. 501 selected stdlib checks and 62 port checks pass; all 18 adapted benchmark programs match. Detailed evidence is linked from the baseline. |
| 2026-10-17 follow-up | Same `d3fbfc6f`; no additional merges | Existing results still describe current main. No unchanged full suites were rerun. #600–#602, #604–#609, #622–#624, #629–#634, #583 and #170 remain open at this checkpoint; proposed support is not counted as shipped. |
| 2026-10-19 builtin-module prototypes | `2359de69`; #644, #645, #646 and #648 after `a355c83f`, plus CI-only #677 | **144/475** native imports, up from 142, with none lost; **146/475** stub-assisted. All 27 package probes keep their first errors, and the pyperformance census stays at 6/52. Adds three compiled upstream test files. [Report](compatibility-2026-10-19-prototypes.md). |
| 2026-10-19 merge catch-up | `5db1e4b5`; #678 integration, #670 native JSON, regex/compiler/array changes through #699, and #723 recorded benchmarks | **144/470** native, **146/470** stub-assisted; five JSON files move into the overlay, no successful imports lost. Native JSON passes 14,444 cases in each JIT/AOT mode with GC stress. Focused checks, affected ports, FFI and BLAS parity pass. [Evidence](compatibility-2026-10-19-catchup.json). |
| 2026-10-19 JSON/effect follow-up | `898d0b95`; #722 | Imports and first errors unchanged; JSON differentials, 64 focused checks, 52 GC-stressed checks and 8 adapted port checks pass. Corrected recursive equality depth boundary and alias diagnostics. Independent paired encoder medians improve **3.47–4.82x** on two bounded inputs, not whole-library coverage. [Evidence](compatibility-2026-10-19-json-followup.json). |

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
