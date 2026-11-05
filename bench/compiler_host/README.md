# Compiler hosts, LLVM workers, and scaling limits

Research on Linux x86-64, 2026-11-05. This is a draft experiment based on
[#1090](https://github.com/den-run-ai/pystachy/pull/1090), not a production backend
change. All compiler, runtime and library files are unchanged relative to #1090. New code lives in
this directory. Refs [#1089](https://github.com/den-run-ai/pystachy/pull/1089),
[#1011](https://github.com/den-run-ai/pystachy/issues/1011),
[#46](https://github.com/den-run-ai/pystachy/issues/46),
[#767](https://github.com/den-run-ai/pystachy/issues/767),
[#104](https://github.com/den-run-ai/pystachy/issues/104) and
[#105](https://github.com/den-run-ai/pystachy/issues/105).

## Scope and reproducibility

Compiler/input source: `626c3bf19ad88d575b36b418563ac1175f64e33a` (#1090), based
on #1089 and main `d81279361d847c4647e64bddb9dcb2466fd58711`. The native seed is the
previously verified ordinary-backend #1090 compiler, SHA-256
`f22ac677341a10eecda4356b66329d51277ec9eea17cd4bf06e8c2c29d689502`.
It was copied from that experiment, not freshly prepared as part of the host
comparison. New backend builds independently reproduce both compiler and runtime
raw IR from this seed.

The machine is an AMD EPYC 9V74 container with eight CPUs of quota, affinity to
nine logical CPUs, and an 8 GiB memory cap. Frontend samples use one allowed core
(CPU 8), random interleaving with seed 20261105, five fresh processes per
host/input pair, warm OS file cache and no simultaneous heavy build. Versions:
CPython 3.13.16; mypy/mypyc 2.4.0; Cython 3.3.1; PyPy 8.0.1 / Python 3.11.17;
LLVM/Clang/LLD 18.1.3; setuptools 84.2.1. Exact commands, source/import inventories,
binary hashes, stderr stage timers, CPU, load and memory samples are in the JSON
results. A pinned quota is not a dedicated physical machine; ranges are retained.

Three scopes must remain separate:

1. **Prepare a compiler host:** generate/compile C extensions or build a native
   Pystachy executable. This is excluded from frontend timings.
2. **Run that compiler frontend:** load, infer, optimize typed IR and emit raw
   LLVM IR for exactly the same original source/input. No LLVM native backend.
3. **Build a native compiler:** prepare runtime, generate/link IR, optimize LLVM,
   generate machine code and link. Backend-only timings explicitly start with
   the same linked bitcode and exclude frontend/runtime preparation.

This is not a comparison of Pystachy building itself against mypyc building mypy,
TypeScript checking VS Code, or PyPy constructing its interpreter.

## Controlled frontend results

[Raw samples](results/frontend-hosts.json): **120/120 exact raw LLVM IR matches**,
plus four CPython oracle runs. The harness verifies that all 48 compiler source
modules load from the intended `.so` files for compiled hosts, or `.py` files for
interpreters. It records and rechecks host, compiler, input and import artifacts.
No silent fallback to interpreted compiler modules was accepted.

Median elapsed seconds, including process startup and output writing:

| Compiler host | Runtime frontend | NameGenerator probe | JSON repair frontend | Compiler's own frontend | Self peak RSS, MiB |
|---|---:|---:|---:|---:|---:|
| CPython | 0.400 | 0.082 | 1.482 | 31.915 | 748.4 |
| mypyc, unchanged source | 0.170 | 0.047 | 0.593 | 17.716 | 646.3 |
| mypyc, receiver-type overlay | 0.137 | 0.047 | 0.405 | 7.206 | 644.4 |
| Cython, unchanged Python semantics | 0.387 | 0.085 | 1.433 | 29.140 | 746.4 |
| PyPy, fresh process/JIT | 1.721 | 0.199 | 5.032 | 28.598 | 1023.5 |
| Native Pystachy | 0.067 | 0.008 | 0.249 | 5.609 | 898.1 |

Native is 5.69x CPython, 3.16x unchanged mypyc, and **1.28x the explicitly typed
mypyc variant** on self frontend. The latter is the more useful mypyc engineering
comparison. It is a separately labeled preparation variant, not identical host
source: the *input being compiled* remains the same unmodified original source.
Native's self peak memory is about 39% above typed mypyc; that matters when
scheduling independent compiler processes.

The self frontend ranges are 31.78–33.78 s CPython, 16.74–18.56 s unchanged mypyc,
7.09–8.13 s typed mypyc, 29.07–31.12 s Cython, 27.43–31.52 s PyPy and 5.11–5.91 s
native. These five samples do not justify precise claims about tiny differences.
PyPy's JIT starts fresh for every compilation; a persistent warmed interpreter
could behave differently and was not tested. Cython disables `annotation_typing`
and `infer_types` and uses O2 C compilation; this is not a hand-rewritten `cdef`
compiler. Neither control is a ceiling on those systems' performance.

Self memory uses `wait4` maximum process RSS. For very small children, inherited
pre-exec parent memory gives this metric a roughly 59.7 MiB floor; do not use it
for small-workload memory rankings. Sampled process-tree RSS can miss short peaks
and counts shared pages more than once across processes. Self workloads are well
above the inherited floor.

The NameGenerator input is unchanged upstream `mypyc/namegen.py` from
`python/mypy@1231cf158a9cab0c41f613f3d8070c1332632f29`, SHA-256
`739a7bcb1c54c96a8944da8a9a4542475c56d2ee392db22ba933e74749fe23ae`, loaded by
`bench/compiler_parallel/namegen_probe.py`. JSON repair uses
`bench/json_repair/bench.py` with the repository's existing `ports` import path.
These are frontend compilation workloads, not the runtime speed of the programs.

### Why the mypyc gap changes so much

`annotate_receivers.py` adds `self: Gen` to **1,189 free-function helper receivers
in 27 modules**, with type-only imports and three `typing.cast` expressions for
existing narrowing invariants. [Exact overlay](results/receiver-overlay.diff);
[counts](results/receiver-counts.json). There is no algorithm substitution.
Mypyc's [native operations](https://mypyc.readthedocs.io/en/stable/using_type_annotations.html)
and [early binding within compilation units](https://mypyc.readthedocs.io/en/stable/compilation_units.html)
make these erased receiver types consequential. All modules remain one mypyc
compilation group with multiple C translation units.

Median instrumented self-stage seconds (nested total timers are not added):

| Stage | CPython | Unchanged mypyc | Typed mypyc | Native |
|---|---:|---:|---:|---:|
| Loading | 9.703 | 2.476 | 2.441 | 1.611 |
| Preparation | 1.741 | 0.776 | 0.700 | 0.819 |
| Discovery/inference | 13.339 | 11.670 | 1.460 | 1.412 |
| Whole-program analysis | 0.540 | 0.327 | 0.210 | 0.204 |
| Finalized function optimization | 2.140 | 0.868 | 0.714 | 0.517 |
| Finalization | 2.962 | 0.364 | 0.130 | 0.169 |
| LLVM lowering | 1.151 | 0.692 | 0.591 | 0.715 |

All self runs report one top-level program attempt. That rules out a whole-program
retry explosion in these samples, not repeated work inside discovery. The
native finalized-function optimization loop occupies only about half a second.
Even eliminating it cannot substantially shorten an approximately 80-second
native self-build. Loading and inference offer more frontend headroom, but LLVM
remains the much larger self-build target.

The annotation overlay **cannot currently be adopted as Pystachy source**:
self-hosting rejects the annotated helper receiver at `gen.py:3732` as an
unsupported parameter annotation. [Native rejection](results/overlay-self-blocker.json).
This is a concrete instance of the receiver-typing boundary in #46, not an
unconditional recommendation to annotate the production tree.

### Preparation costs and scheduling

[Preparation records](results/preparation.json) are separate single observations:
typed mypyc C generation 28.71 s, C compilation/linking 64.89 s; Cython generation
18.53 s, C compilation/linking 407.34 s. The C builds briefly overlapped under an
eight-compiler budget, so these are **not a clean cross-tool preparation ranking**.
The original unchanged-mypyc build was not timed. No preparation break-even claim
should use these as precise repeated benchmarks.

Stock `build_ext -j` schedules extensions, leaving the large shared mypyc extension's
C files serial. `prepare.py` uses a bounded pool for those individual C units and
joins before linking. Cython instead uses bounded extension parallelism. Its huge
`builtins.c` became a long serial tail after other modules finished. Generated C
size was 71.86 MB unchanged mypyc, 57.66 MB typed mypyc, and 144.57 MB Cython.
Explicit receiver annotations reduce both dynamic dispatch and generated C volume.

An optional `psutil` installation made mypy's available-thread detection fail on
this container's mismatched PID namespace. Removing optional psutil from the
isolated benchmark venv resolved setup; no mypy runtime monkeypatch was applied.
An initial Cython serial build was interrupted and the recorded parallel build
forced all modules to rebuild. An initial JSON-repair invocation lacked its
import path and was discarded; all reported frontend samples use the corrected,
fully validated configuration.

## LLVM worker experiment

`self_pipeline.py` creates explicit raw frontend, cached runtime and linked-bitcode
artifacts through the unchanged driver. A tiny cold build prepares the *entire*
runtime while the program frontend runs independently. It then invokes
`backend_workers.py` and requires the built compiler to reproduce both compiler
and runtime raw IR. One successful cold build took **80.87 s**, with **7.58 s** for
the overlapped frontend/runtime phase, **3.17 s** IR linking and **69.84 s** backend.
This is a single controller smoke result, not a repeated before/after speedup.
[Cold build evidence](results/cold-overlap.json).

`backend_scaling.py` compares four paths from the exact same linked bitcode:

- **Whole:** whole-module O2, allocator late inline, serial machine-code generation.
- **LTO4:** the same whole-module O2 and late inline, then four full-LTO codegen
  partitions with the LTO optimization pipeline limited to verification.
- **Split4 serial:** `llvm-split` before O2, four independent optimize/late-inline/
  codegen jobs, one worker.
- **Split4 parallel:** exactly the same four jobs, four workers; stable link order.

The two split variants distinguish changing optimization scope from adding
parallel execution. Early splitting is **not ThinLTO**: cross-module inlining and
other whole-program information are lost. The allocator body is no longer
available for late inlining in every partition. Correctness, executable size and
generated-compiler speed must accompany build latency.

[Raw backend measurements](results/backend-scaling.json), three interleaved builds
per variant, with **24/24 compiler/runtime IR witnesses matching**:

| Backend from frozen linked bitcode | Median wall, s | CPU, s | Sampled aggregate peak RSS, MiB | Executable bytes |
|---|---:|---:|---:|---:|
| Whole-module O2, serial codegen | 71.833 | 78.823 | 569.7 | 5,242,632 |
| Whole-module O2, full-LTO codegen x4 | 52.448 | 81.036 | 938.7 | 5,522,280 |
| Pre-O2 split x4, one worker | 44.037 | 48.411 | 369.3 | 4,892,128 |
| Same pre-O2 split x4, four workers | 16.964 | 55.562 | 724.4 | 4,892,128 |

Whole-module build ranges were 71.50–77.63 s; LTO4 51.30–56.98 s;
split serial 42.00–46.25 s; split parallel 16.61–17.21 s. The **2.60x gain from
44.04 to 16.96 s isolates parallel execution of the same jobs**, with 14.8% more
CPU and 96.1% more aggregate RSS. The 4.23x whole-to-parallel-split gain combines
parallel execution with changed optimization scope. It must not be advertised as
a pure threading speedup or a full-bootstrap timing.

All six split builds produce the same executable bytes, including across worker
counts. All ordinary builds reproduce the seed executable's exact SHA-256.
LTO4 costs 64.8% more sampled backend peak RSS and produces a 5.3% larger compiler;
split builds produce a 6.7% smaller compiler. Backend CPU/RSS include coordinator,
worker and monitoring overhead. The artifact controller exits the frontend
process before launching LLVM, so this backend memory scope excludes its earlier
approximately 0.9 GiB heap. It is not directly comparable to a driver's peak while
retaining frontend memory during backend subprocesses.

[Separate generated-compiler execution experiment](results/backend-quality.json):
five interleaved fresh-process runs per binary/input, pinned to one core, conducted
after all backend builds. All **30/30 emitted IR outputs match**. This avoids
confounding execution time with which multicore build immediately preceded it.

| Generated compiler | Self frontend, median (range), s | JSON repair frontend, median (range), s |
|---|---:|---:|
| Ordinary whole-module backend | 6.330 (5.932–6.864) | 0.355 (0.309–0.376) |
| LTO4 backend | 6.867 (6.199–7.077) | 0.353 (0.326–0.374) |
| Early split4 backend | 7.303 (6.857–7.852) | 0.375 (0.330–0.427) |

Observed self-frontend medians are **8.5% higher with LTO4 and 15.4% higher with
early splitting**. Ranges overlap and five samples on a shared machine are not a
universal generated-code ranking. JSON repair differences are smaller than its
run-to-run spread. The result supports testing early splitting for temporary
bootstrap compilers while retaining whole-module optimization for the final
compiler; it does not justify changing the default final backend. A complete
bootstrap using this new split strategy was not timed. The previous #1090 cheap
stage-1 policy also needs a direct comparison before claiming incremental savings.


Whole-module O2 remains roughly 37 seconds after LTO4, about 71% of that
backend's latency. In the early-split pipeline, serial `llvm-split` costs a median
3.52 seconds, about 21% of the new critical path. Partition 2 is the slowest in
all six split builds even though partition byte sizes are similar (3.37–3.58 MB).
Cost-balanced partitioning, avoiding repeated split work and preserving useful
cross-module optimization are now concrete priorities. Input bytes alone are a
poor scheduling cost estimate. This split does not establish stable incremental
cache units; edits could reshuffle work and invalidate many artifacts.

The four worker inputs total 13.33 MiB versus 11.11 MiB for the whole linked
module: partition declarations add about 20% input volume. Object transfer,
network latency, remote queue delay and distributed cache hits are unmeasured.
Post-timing protocol hardening added coordinator-side expected-job hash checks;
[offline revalidation](results/worker-validation.json) checked all 30 recorded jobs
and exercised wrong-input, wrong-tool, stale/misrouted-result and modified-output
rejections without executing LLVM. Recorded worker-script hashes predate that
validation-only change; LLVM commands and generated outputs are unchanged.

### Whole-runtime overlap

[Three fresh-cache pairs](results/runtime-overlap.json) compare the same self
frontend and unchanged-driver tiny runtime-preparation build, serially or as two
independent jobs. Each inner build has a one-job budget. All six raw IR outputs
match and all six tiny executables print the expected output.

| Pre-backend phase | Median wall, s | Child CPU, s | Sampled aggregate peak RSS, MiB |
|---|---:|---:|---:|
| Serial whole runtime + frontend | 12.545 | 12.531 | 948.8 |
| Overlapped whole runtime + frontend | 6.887 | 13.040 | 1093.2 |

This hides **5.66 seconds**, about 45% of this phase, at 4.1% more child CPU and
15.2% more aggregate RSS. It is materially different from overlapping C compilation
with only the approximately 50 ms runtime.py frontend in #1089. Runtime preparation
includes the tiny program's compile/link overhead; it is not a pure runtime-only
timer. The self-build LLVM backend is excluded. Cold means empty runtime caches,
with warm OS pages. A normal runtime-cache hit has little work to hide.

### LLVM pass costs, IR growth, and avoidable work

[Pass profile](results/llvm-profile.json), collected separately with Clang
`-ftime-report` on the same frozen module. This is one instrumented observation;
normal backend timings above remain the performance comparison. The profiled
object is byte-identical to the ordinary worker object.

| Phase | Largest reported pass costs, seconds |
|---|---|
| O2 optimization | InstCombine 5.850; inlining 5.549; GVN 2.565; SimplifyCFG 2.351 |
| Machine-code generation | X86 DAG instruction selection 12.097; greedy register allocation 2.820; assembly printing 1.787 |

Keep pass, analysis, selection sub-timer and top-level tables separate; they
contain overlapping scopes and cannot be summed. MemorySSA analysis took 1.746 s
and dominator-tree analysis 1.025 s in the separate analysis table. The profile
points toward IR size/inlining and instruction selection, rather than a single
cheap frontend pass, as worthwhile self-build investigations.

Whole O2 reduces functions from 3,671 to 2,201 but grows approximate LLVM
instructions from 709,659 to 886,036 (**+24.9%**) and textual IR from 44.39 to
67.15 MB. Inlining can trade compilation work and code size for execution speed;
the slower early-split compiler demonstrates why reducing these counts is not
sufficient by itself. Inspect function-level IR growth and inlining policy before
removing passes blindly.

**The late allocator-inlining stage is a confirmed no-op on this frozen
self-build.** Its disassembled output matches the O2 output after removing only
the first `llvm-dis` ModuleID filename line. There is no actual `pys_new`
definition, declaration or call remaining. Bypassing that stage and generating
code directly from O2 bitcode produced the **exact same object and final compiler
bytes**. [Bypass validation](results/skip-late.json). The ordinary backend's late
stage costs a median 3.63 s (3.77 s in the profile), so conditional elimination or
pipeline fusion is an additional concrete opportunity. This was validated for
self-build only; arbitrary programs that retain allocator calls still need the
late-inline contract. No general driver shortcut was enabled.

The initial `-mllvm -time-passes` attempt reported only parsing timers. It is
retained as [incomplete instrumentation evidence](results/llvm-profile-instrumentation.json)
and superseded by the `-ftime-report` run with required pass tables. No normal
backend timing depends on that failed profiling setup.

A separate [native GC observation](results/native-gc.json) reported 13 collections
and 955 ms of collection time during a 6.43-second frontend invocation, with
902 MiB logical heap peak and 312.8 MiB live at the last collection. These are
runtime counters, not RSS or repeated timing estimates. Allocation reduction and
releasing the frontend process before LLVM have more immediate memory value than
multiplying native frontend workers. This does not identify a historical GC
regression.


### Portable jobs and distributed compilation boundary

A [detached replay](results/detached-worker.json) copied one input/job and the
worker script outside the repository, ran Python in isolated mode from that
directory, and reproduced the exact original object bytes. This tests the local
file-based boundary, not a second host.

Each worker directory contains `input.bc` and a versioned `job.json` with its
input hash, optimization/emit settings and tool-executable hashes. A standalone
standard-library-only `--worker` mode optimizes and compiles that input, then
atomically publishes the object and a result record. The coordinator bounds
active processes and links outputs in partition order. LLVM tools run in separate
processes, which isolates their contexts and heaps without shared-heap compiler
threading. Intermediate files make work inspectable and transferable.

**All measurements here are local. No remote host, network transport or remote
speedup was tested.** A portable directory is a worker boundary, not a deployed
distributed service. Before production distribution, implement and validate:

- Target triple/CPU/ABI, sysroot, shared libraries and full toolchain identities;
  executable hashes alone do not establish cross-machine compatibility.
- Content-addressed immutable storage, atomic cache publication, cache eviction,
  deduplicated misses, retries and end-to-end failure handling. Local job/result
  binding and corrupt-output rejection are tested, but this is not a shared cache.
- Owned worker lifecycle, timeout/cancellation propagation and cleanup. The
  research measurement helper creates nested process groups; a failed coordinator
  can leave a worker group running. Successful runs were checked, but failure
  cleanup is not a production guarantee.
- One total CPU and memory budget across builds, LLVM partitions, C compilation
  and test workers. Queue bytes as well as job count; native self frontends already
  need roughly 0.9 GiB each before backend allocations.
- Transfer and queue-time accounting, authentication, machine availability and
  architecture-specific execution checks. This prototype’s portable worker interface accepts backend artifacts; inference
  still operates as one frontend process. Independent whole frontend jobs can
  also run on separate machines in principle.

[ThinLTO](https://clang.llvm.org/docs/ThinLTO.html) is the appropriate next study
when useful semantic/module boundaries and an import/cache policy exist. It
supports parallel backends and caching, but feeding an arbitrary early split
through independent O2 does not provide ThinLTO's summary-based importing.
Stable units and cache hits may save more than repeatedly distributing a whole
fresh self-build. For today's tree, independent programs/test batches and runtime
preparation are immediately separable; mutable inference/specialization state
still needs the ownership contract tracked in #767.

## Partial mypy/mypyc support: keep both directions explicit

This experiment successfully uses **mypyc to compile the entire Pystachy frontend**
into CPython extensions. It does **not** demonstrate that Pystachy compiles all of
mypy or mypyc. The reverse direction remains partial.

Existing [porting documentation](../../docs/porting.md) records an adapted stubgen
documentation parser, a CPython CLI retained around native parser workers, and
identical four `.pyi` artifacts through extension/AOT/JIT paths. It also records
unchanged upstream NameGenerator isolation and a two-module integrated mypyc
consumer with matching generated C, headers and IR. Those are component-level
consumers; they are not a complete native type checker or mypyc toolchain.

New probes use installed **mypy 2.4.0** source files with recorded hashes and the
#1090 native seed. [Exact first errors](results/mypy-support.json):

| Probe | First blocking feature/dependency |
|---|---|
| `mypy.api` | Function-local `mypy.main` import without a module-level import |
| `mypy.main` | Unsupported `platform` module |
| `mypy.fastparse` | `platform` reached through `mypy.defaults` |
| `mypy.mro` | Unsupported `librt.internal` reached through `mypy.nodes` |
| `mypyc.build` | Unsupported `hashlib` module |
| Parameterized `dict` subclass control | Unsupported class base shape |
| `globals()` control | Unsupported dynamic namespace operation |

`librt.internal` is installed as a CPython extension with stubs; this is a native
module/interface boundary, not a missing pip installation. The probe inventory
hashes package `.py` sources, not those extension binaries or stubs.

These are first failures, not an exhaustive port audit or acceptance-rate score.
The pinned source differs from earlier port prototypes, so blocker counts cannot
be interpreted as a regression. Further port work must audit CPython AST/parser and extension interfaces, native
runtime dependencies, dynamic namespace/class behavior, import graph handling
and compatible receiver annotations; these probes do not exhaust that work. Fixing one
import may expose the next dependency without enabling a working API.

Prior integrated experiments reinforce the boundary-cost warning: [#1065](https://github.com/den-run-ai/pystachy/pull/1065)
reported a faster slice/join kernel but only 72 microseconds in an 11.47-second
real build; [#1069](https://github.com/den-run-ai/pystachy/pull/1069) reported exact
consumer artifacts while a per-result native adapter slowed 5.01 to 6.73 ms.
[#1068](https://github.com/den-run-ai/pystachy/pull/1068) proved an adapted visitor
consumer across 694 functions, without a whole-build timing claim. These are
historical PR measurements, not reruns in this experiment. Batch substantial
work across a native/process boundary; packing, dispatch and serialization can
outweigh a faster isolated helper.

## Regressions and priorities

[Frozen-source history experiment](results/history.json): alpha.4 is
`9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3`; current means the pinned #1090
prototype, not a new main commit. The alpha.4 executable was prepared separately
with the same CPython 3.13.16 and LLVM 18.1.3 (one 107.90-second hosted build), then
required to match its hosted compiler and runtime IR before timing.

Three interleaved fresh-process samples per compiler/input pair, pinned to CPU 8:

| Frozen input tree | Alpha.4 compiler | #1090 compiler | Interpretation |
|---|---:|---:|---|
| Alpha.4 source | 6.168 s (6.115–6.420) | 5.599 s (5.306–5.964) | Current frontend uses 9.2% less time on the same old input |
| #1090 source | Unsupported `os.mkdir(str,int)` at driver.py:275 | 6.142 s (6.045–6.358) | No cross-version speed ranking on this input |

Every successful compiler/input pair produced stable IR and passed LLVM
verification; the newer-source rejection was stable across all three old runs.
Historical IR is allowed to differ across compiler versions and was not treated
as a byte-equality oracle. On the frozen old input, output size is 29,886,195 bytes
from alpha.4 and 29,867,470 from #1090.

**This finds no frontend slowdown on the tested frozen alpha.4 source.** It does
not establish that full native self-build or bootstrap has no regression. That
would require repeated complete builds with comparable accepted inputs, backend
profiling across versions, and a bisect if a slowdown remains. The current-source
comparison is blocked by a real historical capability gap, not a fast successful
compile. No full-build regression bisect was run.

Source growth is measurable: compiler entry plus source modules grew from
3,008,044 to 3,180,585 bytes (+5.74%), 57,902 to 61,093 lines (+5.51%), and 48 to
49 files. `runtime.c` grew 12.26%; `runtime.py` is unchanged. Comparing each
compiler only on its own source confounds these changes with compiler speed.
Also, absolute timing medians from separate experiment cohorts are not a
longitudinal regression test; the conclusions use their interleaved controls.


The engineering order supported by the evidence is: retain/reuse bootstrap
artifacts and runtime caches; overlap whole runtime preparation; make LLVM
optimizer/codegen units independently measurable; choose temporary-stage and
final-stage optimization policies separately; then build stable cached modules
and remote scheduling. Native frontend function-worker extraction has a small
self-build ceiling in the measured tree. Improve its ownership contract for
maintainability and other workloads, without presenting it as the main answer to
this self-build bottleneck.

## Reproduction

Use an isolated checkout at the recorded source SHA and an external work directory.
Provide CPython 3.13.16 and a complete LLVM 18.1.3 toolchain. Install mypy 2.4.0,
Cython 3.3.1 and setuptools 84.2.1 into the host venv; record a fresh dependency
lock if reproducing after these versions. `CC` must point to the same Clang used
in this report. Install the pinned [host dependencies](requirements.txt). Preparation commands
(run each separately for clean timings):

```sh
HOST_PY=/absolute/path/to/venv/bin/python
LLVM=/absolute/path/to/llvm-18/bin
WORK=/absolute/path/to/empty-benchmark-parent
export CC="$LLVM/clang"
"$HOST_PY" bench/compiler_host/prepare.py --kind mypyc --work "$WORK/mypyc" --jobs 4
"$HOST_PY" bench/compiler_host/prepare.py --kind mypyc --work "$WORK/mypyc-typed" --jobs 4 --receivers
"$HOST_PY" bench/compiler_host/prepare.py --kind cython --work "$WORK/cython" --jobs 4
```

Copy the `config` object in `results/frontend-hosts.json` into a separate JSON file
and replace paths with your checkout, prepared hosts, PyPy executable, verified
native compiler and upstream NameGenerator input. Preserve the import paths and
label the receiver overlay separately. Choose an actually allowed CPU:

```sh
"$HOST_PY" bench/compiler_host/run.py --config "$WORK/hosts.json" \
  --work "$WORK/frontend" --report "$WORK/frontend.json" --samples 5 --cpu 8
"$HOST_PY" bench/compiler_host/self_pipeline.py --compiler /path/to/verified/pystachy \
  --llvm "$LLVM" --work "$WORK/snapshot" --report "$WORK/cold.json" --overlap --jobs 4
"$HOST_PY" bench/compiler_host/backend_scaling.py --snapshot "$WORK/snapshot" \
  --llvm "$LLVM" --work "$WORK/backends" --report "$WORK/backends.json" --samples 3 --cpu 8
"$HOST_PY" bench/compiler_host/profile_backend.py --snapshot "$WORK/snapshot" \
  --llvm "$LLVM" --work "$WORK/profile" --report "$WORK/profile.json"
```

Preparation also supports `--phase generate` followed by `--phase compile` in the
same work directory. The latter forces C compilation and must match the recorded
kind and optimization level. Worker-only replay needs a fresh copy of a recorded
job directory, the worker script and compatible LLVM tools:

```sh
"$HOST_PY" bench/compiler_host/backend_workers.py --worker /path/to/job --llvm "$LLVM"
```

## Validation and limits

- Controlled host comparison: 120 exact raw IR matches; 48 module import origins
  checked for each interpreter/extension host; all source and host artifacts stable.
- Backend experiment: 12 builds, 24 exact compiler/runtime witnesses, identical
  split executables across worker counts; all 30 job records revalidated.
- Generated-compiler quality: 30 additional exact IR matches over two inputs.
- Cold-overlap experiment: six exact self IR matches and six working tiny binaries.
- Historical comparison: old hosted/native compiler and runtime IR parity; nine
  successful deterministic frontend runs and three stable newer-source rejections;
  LLVM verification for every successful compiler/input pair.
- Detached worker replay and no-op late-inline bypass: exact object identity;
  bypass also reproduces the original final compiler bytes.
- Protocol negative controls reject bad input/tool identity, stale/misrouted
  results and modified outputs before publication/use.
- [Corpus checks](results/corpus.json): 4,238 IR/diagnostic/exit-status comparisons
  each for the split compiler and typed-mypyc host, all identical to the seed.
- Ruff, Python syntax compilation and repository-content checks: passed.

An initial parallel corpus controller disappeared after recording the successful
split-compiler comparison; no final typed-mypyc result survived. Its cause was
not established and no OOM kill was recorded by the cgroup. That attempt is
preserved as incomplete evidence; the typed-mypyc check was rerun separately with
two workers. Do not count an interrupted or missing result as a pass.

Full local `make verify`, a new three-generation bootstrap using early splitting,
macOS, other architectures, sanitizers for every generated compiler and actual
multi-host execution were not run. Production compiler/runtime defaults and CI
limits are unchanged. This remains a research prototype, not a merge-ready
replacement for the driver.

Additional reproducible entrypoints:

```sh
"$HOST_PY" bench/compiler_host/runtime_overlap.py --compiler /path/to/verified/pystachy \
  --llvm "$LLVM" --snapshot "$WORK/snapshot" --work "$WORK/overlap" \
  --report "$WORK/overlap.json" --samples 3
"$HOST_PY" bench/compiler_host/history.py --old-home /path/to/alpha4-checkout \
  --compiler /path/to/verified/pystachy --llvm "$LLVM" --work "$WORK/history" \
  --report "$WORK/history.json" --samples 3 --cpu 8
"$HOST_PY" bench/compiler_host/support_probe.py --source /path/to/site-packages \
  --compiler /path/to/verified/pystachy --work "$WORK/support" --report "$WORK/support.json"
"$HOST_PY" bench/compiler_host/validate_workers.py --work "$WORK/backends" \
  --llvm "$LLVM" --report "$WORK/worker-validation.json"
PYSTACHY_HOME="$PWD" PYSTACHY_JOBS=2 tools/irsame.sh /path/to/seed \
  "$WORK/backends/split4-parallel-0/compiler"
PYSTACHY_HOME="$PWD" PYSTACHY_JOBS=2 tools/irsame.sh /path/to/seed \
  "$HOST_PY $WORK/mypyc-typed/pystachy.py"
```
