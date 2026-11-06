# Compiler parallelism experiments

Compare serial AOT builds, overlapping cold-runtime jobs, and full-LTO codegen
partitions using the same native compiler and sources. The defaults remain one
build job and the ordinary native-object link. This harness supplies evidence for
[#1011](https://github.com/den-run-ai/pystachy/issues/1011); it does not set a
performance threshold or change CI concurrency.

## Measured results

The source checkpoint is [`98537ca`](https://github.com/den-run-ai/pystachy/commit/98537caf64a0efe86244c3eb27f1bb8d00655892),
with a native compiler, Linux x86-64, AMD EPYC 9V74, an eight-CPU quota and 8 GiB
memory limit. LLVM/clang/LLD were 18.1.3; the CPython oracle was 3.13.16. Both runs
started from a clean tree and passed their final source/compiler identity checks.
The [small-workload report](results/linux-llvm18-small.json) retains all 90 builds
and 270 application checks; the [self-build report](results/linux-llvm18-self.json)
retains four builds and their compiler/runtime IR witnesses.
[summary.csv](results/summary.csv) contains every variant/cache state, sample
counts, ranges, CPU, both RSS measures, executable size and application medians.

### Warm build latency

Seconds are medians with **[minimum–maximum]** across three interleaved builds.
The name-generation probe uses the pinned mypyc module; it is not a full mypy build.

| Workload | Ordinary object path | LTO 1 | LTO 2 | LTO 4 |
|---|---:|---:|---:|---:|
| Tiny | 0.324 [0.314–0.337] | 0.381 [0.360–0.437] | 0.356 [0.339–0.378] | 0.331 [0.289–0.342] |
| JSON repair | 6.566 [5.740–7.655] | 6.305 [6.217–7.324] | 5.315 [5.017–5.708] | 4.865 [4.769–5.736] |
| Name generation | 1.647 [1.615–1.744] | 1.605 [1.485–1.623] | 1.274 [1.254–1.408] | 1.251 [1.151–1.341] |

Relative to ordinary builds, LTO 4 reduced median wall time by **25.9% for JSON
repair** and **24.0% for name generation**. Same-round speedup ranges were
1.204–1.350× and 1.228–1.515×. Comparing LTO 1 with LTO 4 isolates the partition
change more closely: ratios of median build times were 1.296× and 1.282×, with
same-round ranges 1.099–1.505× and 1.108–1.409×. Tiny showed no useful end-to-end
gain over the ordinary route. Three samples describe this host, not a universal
speedup guarantee.

**Cold-runtime overlap showed no consistent gain.** Serial → overlap median
seconds were 6.820 → 6.958 for tiny, 12.168 → 12.388 for JSON repair, and
7.628 → 7.556 for name generation. Their same-round speedup ranges were
0.901–1.031×, 0.935–0.998×, and 0.963–1.039×. The native runtime frontend was only
about 49–61 ms at the medians: 0.40–0.84% of cold build time. Hiding all of that
work allows less than a 1% gain before process overhead; larger differences in
these cold samples do not establish an overlap benefit.

### Compiler self-build: one warm sample per variant

These are exploratory single samples. The last column is the rebuilt compiler's
combined wall time to emit compiler and runtime IR in two invocations. All four
rebuilt compilers emitted the same IR as the input compiler.

| Variant | Build wall s | CPU s | Aggregate RSS MiB | Executable bytes | IR emission s |
|---|---:|---:|---:|---:|---:|
| serial | 77.348 | 77.324 | 1319.0 | 5,232,232 | 5.978 |
| lto-1 | 78.808 | 78.792 | 1386.2 | 5,230,640 | 6.476 |
| lto-2 | 67.086 | 81.926 | 1701.5 | 5,510,736 | 5.996 |
| lto-4 | 61.866 | 85.383 | 1695.7 | 5,510,856 | 6.319 |

LTO 4 took 20.0% less build time than ordinary codegen, with 10.4% more CPU,
28.6% more sampled aggregate RSS, and a 5.3% larger executable. Its IR-emission
witness was nominally 5.7% slower; one sample cannot characterize that variation.

### Costs, runtime quality and remaining bottlenecks

For the repeated warm workloads, LTO 4 increased CPU / sampled aggregate RSS by
8.1% / 62.2% for JSON repair and 12.1% / 66.8% for name generation. Tiny incurred
32.4% / 65.0% more, without a demonstrated build-latency benefit. Four partitions
saved only another 1.8% median wall time over two for name generation while using
15.0% more CPU; JSON repair saved another 8.5% with 6.6% more CPU.

Warm application medians (nine process runs per variant) were 37.39 → 38.65 ms
for JSON repair and 56.64 → 59.19 ms for name generation, ordinary → LTO 4:
nominal increases of **3.4% and 4.5%**. The ranges overlap (34.6–54.2 versus
35.0–48.0 ms; 51.4–63.0 versus 50.7–70.1 ms). Their executable sizes changed by
+4.0% and -0.8%. Correct output does not establish performance parity; these
measurements leave both runtime variation and a possible generated-code cost.
Sub-millisecond differences in the tiny control are inconclusive.

LLVM remains the dominant cost. LTO 1 → 4 reduced codegen/link from 2.652 to
1.304 s for JSON repair, 0.691 to 0.296 s for name generation, and 28.828 to
12.007 s for self-build. The self-build's preceding LLVM optimization still took
about 37 s. In ordinary warm builds, finalized function optimization occupied
0.186% of JSON-repair wall time, 0.011% of name generation, and 0.771% of the
single self-build (0.596 s). Ideal four-worker parallelization of only those
passes would improve total latency by at most 0.14%, 0.009%, and 0.58%, before
serialization or startup. These results support deferring function-worker
execution until a workload shows a substantial cost in those passes.

Serial and overlap builds produced identical executable hashes for every
workload; each fixed LTO partition count was also byte-stable across all its
cold/warm repetitions. Aggregate RSS is a sampled process-tree sum that counts
shared pages per process, not a precise physical-memory peak. The CSV also reports
`wait4` maximum process RSS; the two measures are not interchangeable.

Stage totals are nested. Even after selecting nonoverlapping scopes, tiny LTO
builds leave about 31–35 ms (7–12%) outside the leaf timers. Untimed clang/LLD
version probes in the driver plausibly explain much of this residual; that is
an inference from the code, not a separately timed result. `driver.total` remains
available. This experiment does not complete #1011's stage-reconciliation goal.
The controls remain opt-in, with one build job and no LTO partitions by default.

### Validation of this prototype

- 4,238 IR/diagnostic/status comparisons matched main using a common home with
  byte-identical libraries. An initial separate-home comparison had 261 differences
  from embedded absolute library paths; the common-home run resolved that setup
  mismatch without changing library or runtime sources.
- The native checker passed four paired failure scenarios (eight failed
  invocations), snapshot IR parity, and six successful build variants, including
  LTO 1/2/4, under ordinary GC and collection on every allocation.
- Cache checks passed 66 native and 68 hosted assertions. The forced compiler
  `SIGKILL` case was inconclusive because `ps` could not reliably observe its
  process in this environment; it is not counted as validated.
- Unit coverage included 125 compiler-state tests and 37 driver/controller tests.
  Final `make check-fast lint` passed 410 fast tests plus mypy, Ruff, shell and C
  checks. Earlier three-stage fixed-point bootstraps passed, followed by final
  rebuilt hosted/native byte parity for compiler and runtime IR.
- Full `make verify` and macOS were not run locally. CI remains pending; these
  focused results do not replace those gates.

### Reproduce the reports

After building the compiler and fetching the pinned `namegen` source below, use
CPython 3.13.16 and the matching LLVM 18 toolchain:

```sh
python3 bench/compiler_parallel/llvm_partitions.py --compiler ./pystachy \
  --workload tiny --workload json-repair \
  --workload namegen=bench/compiler_parallel/namegen_probe.py \
  --import-path namegen="$namegen_dir" --jobs 4 --samples 3 \
  --runtime-samples 3 --llvm /usr/lib/llvm-18/bin \
  --json /tmp/compiler-parallel.json
python3 bench/compiler_parallel/llvm_partitions.py --compiler ./pystachy \
  --workload self --cache warm --no-overlap --jobs 4 --partitions 1,2,4 \
  --samples 1 --runtime-samples 1 --llvm /usr/lib/llvm-18/bin \
  --json /tmp/compiler-self.json
```

## Run

Build the native compiler from the tested revision first, following
[installation](../../docs/install.md#build-from-source). Use the repository's
pinned CPython for the oracle and a matching LLVM 18 tool directory containing
`clang`, `opt`, `llvm-link`, `llvm-as`, and `ld.lld`. Run from the repository root
on Linux, without overlapping builds or verification jobs:

```sh
python3 bench/compiler_parallel/llvm_partitions.py --compiler ./pystachy \
  --workload tiny --workload json-repair --jobs 4 --samples 3 \
  --runtime-samples 3 --llvm /usr/lib/llvm-18/bin \
  --json /tmp/compiler-parallel.json
```

Add `--workload self` to include compiler self-builds. The built compiler must
emit the same compiler and runtime IR as the input compiler. `tiny` is the startup
control. `json-repair` uses the existing workload and checks its output against
CPython, excluding only its declared elapsed-time line. Its argument defaults to
500 iterations. Hosted bootstrap is a separate experiment; do not mix its samples
with the native compiler baseline.

The original `namegen_probe.py` exercises an unchanged, pinned mypyc module.
Fetch its source and license separately (the repository does not vendor them):

```sh
namegen_dir=$(mktemp -d)
curl -fsSL https://raw.githubusercontent.com/python/mypy/1231cf158a9cab0c41f613f3d8070c1332632f29/mypyc/namegen.py -o "$namegen_dir/namegen.py"
curl -fsSL https://raw.githubusercontent.com/python/mypy/1231cf158a9cab0c41f613f3d8070c1332632f29/LICENSE -o "$namegen_dir/LICENSE"
```

The harness verifies the upstream file's SHA-256 before measuring it:

```sh
python3 bench/compiler_parallel/llvm_partitions.py --compiler ./pystachy \
  --workload namegen=bench/compiler_parallel/namegen_probe.py \
  --import-path namegen="$namegen_dir" --arg namegen=2000 \
  --jobs 4 --partitions 1,2,4 --samples 3 \
  --json /tmp/compiler-parallel-namegen.json
```

`--arg` and `--import-path` repeat; `--stdin NAME=FILE` supplies fixed stdin.
`--python` selects the oracle command. Use `--help` for all options. The harness
removes inherited `PYSTACHY_*` settings before applying the recorded configuration.

Use `--workload self --cache warm --samples 1 --runtime-samples 1 --no-overlap`
for an initial bounded self-build comparison. It omits the redundant warm-cache
overlap variant; one sample remains exploratory. All workload caches are prewarmed
with the generated tiny control, whose source and hash are recorded.

Before measurements, run the correctness checker:

```sh
make compiler-parallel-check BENCH_ARGS=--lto
```

It checks real worker launch/failure counts, exact error precedence, cache reuse,
snapshot IR parity, cleanup, and native class/container/generator/exception/float
outputs against CPython at 1/2/4 LTO partitions, with ordinary GC and collection
on every allocation. Omitting `--lto` needs no LLD. These checks have watchdogs but
no timing thresholds.

For a single manual build, the controls are:

```sh
PYSTACHY_BUILD_JOBS=2 PYSTACHY_LTO_PARTITIONS=0 PYSTACHY_TIMING=1 \
  ./pystachy build tests/programs/containers/lists.py -o /tmp/pystachy-lists
PYSTACHY_BUILD_JOBS=4 PYSTACHY_LTO_PARTITIONS=4 PYSTACHY_CFLAGS= \
  PYSTACHY_TIMING=1 \
  ./pystachy build tests/programs/containers/lists.py -o /tmp/pystachy-lists-lto
```

## Comparisons and measurements

Each sample rotates the order of these variants:

| Variant | Build jobs | LTO partitions | Purpose |
|---|---:|---:|---|
| `serial` | 1 | 0 | Existing AOT path |
| `overlap` | `--jobs` | 0 | Isolate cold-runtime overlap |
| `lto-1`, `lto-2`, `lto-4` | `--jobs` | 1, 2, 4 within the budget | Compare the LTO path and its partition counts |

Use `lto-1` when assessing the effect of additional partitions: changing from the
ordinary object path to LTO also changes the linker/codegen route. All variants
are built sequentially by the controller. A cold sample gets a fresh runtime cache
directory; warm samples share an untimed successful serial prewarm per workload.
The OS page cache is not flushed. `--cache cold` or `--cache warm` selects one case.
A warm runtime cache still recompiles the program.

The JSON report retains raw samples, commands, outputs, stage records, source and
tool hashes, binary size, CPU affinity, host load, and available cgroup limits.
Report build wall time, total CPU time, generated size, application runtime, and
both memory measures. The process-tree RSS estimate samples living descendants
every 10 ms, counts shared pages once per process, and can miss short peaks;
`wait4` maximum RSS is the maximum of an individual process, not aggregate memory.
Application timing includes process startup. Source changes during the run fail
the report, and output/status mismatches fail rather than becoming speedups.
Keep these qualifications with any reported results.

### Read the stage timings

`PYSTACHY_TIMING=1` adds `pystachy-timing<TAB>stage<TAB>seconds` records to stderr.
The controller preserves them and computes medians by stage. The important scopes
are:

| Stage | Contents |
|---|---|
| `program.load`, `runtime.load` | Parse and load imports |
| `*.prepare` | Declarations, import graph and source-level preparation |
| `*.discover` | Specialization and helper discovery to the final retry decision |
| `*.analysis` | Whole-program effects, recursion policy and initial IR verification |
| `*.optimize` | Finalized function optimization passes |
| `*.finalize` | EH rewriting and cross-function tuple-return processing |
| `*.lower` | Function lowering and LLVM module assembly |
| `program.attempt`, `program.frontend` | One retry attempt; all program attempts |
| `runtime.cache_lookup`, `runtime.parallel` | Cache identity/hit lookup; both overlapping runtime jobs |
| `runtime.frontend`, `driver.runtime_worker` | Serial runtime frontend; separate worker duration |
| `program.llvm_optimize`, `program.late_inline`, `program.codegen`, `program.link` | Separate AOT steps when the late-allocation path applies |
| `program.optimize_codegen`, `program.lto_codegen_link` | Combined ordinary optimize/codegen; combined LTO codegen/link |
| `driver.total` | Parent invocation after entering the driver |

Repeated attempt labels include retry cost. A failed phase may have no completed
record. Parent totals contain their children, and parallel worker durations
overlap: stage medians are not an additive breakdown. `runtime.llvm_optimize` is
LLVM work, separate from `runtime.optimize`'s typed-IR passes. Warm runs omit
runtime rebuild stages. Compare whole-process wall/CPU measurements with the
appropriate parent totals to account for startup and uninstrumented work.

## Implementation boundary

A cold runtime miss can run clang on `runtime.c` while a fresh compiler process
produces `runtime.py` IR. Both use the captured source inputs. The parent waits for
both, including worker failures and handled cancellation, and replays stderr in
serial order before linking. A runtime-Python error suppresses C diagnostics from
work the serial build would not have reached. Custom `PYSTACHY_CFLAGS` keep the
serial runtime path and sanitizer ordering. Each compilation retains its private
semantic state.

The frontend remains serial. In
[`program.py`](../../src/pystachy_compiler/program.py), discovery, effects and
recursion policy precede the function optimization loop, but `charslots` and
`dictfuse` still register shared runtime declarations. Passes and verification
also read shared class/layout, string and effect summaries. Lowering writes shared
output and assigns metadata IDs; tuple-return processing is cross-function work.
A future isolated function job therefore needs private `IFn`/scratch, immutable
summaries, explicit declaration requests, and deterministic coordinator merging.
The current timing measurements are the prerequisite for deciding whether that
serialization and process overhead is worthwhile. Any extraction must retain
function order and preserve acceptance, diagnostics and emitted IR across worker
counts. Ownership remains
[#767](https://github.com/den-run-ai/pystachy/issues/767).

Concurrent callers can still duplicate the same runtime cache miss; prewarming
and same-key deduplication remain [#105](https://github.com/den-run-ai/pystachy/issues/105).
Complete native-program caching remains [#104](https://github.com/den-run-ai/pystachy/issues/104).
The budget applies to one invocation; divide available CPUs across external build
processes as well as its LLVM jobs. This experiment adds no frontend workers or
new CI matrix jobs.

## Source basis

The LTO path keeps Pystachy's existing whole-program optimization and late
allocator-inlining sequence, then uses LLD's custom `verify` pass pipeline and
codegen optimization level 2. LLVM 18.1.3's
[`LTOBackend.cpp`](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.3/llvm/lib/LTO/LTOBackend.cpp)
shows the custom-pipeline override and regular-LTO partition serialization into
separate LLVM contexts. LLD's
[`Options.td`](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.3/lld/ELF/Options.td)
and [`LTO.cpp`](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.3/lld/ELF/LTO.cpp)
connect the pass, codegen and partition controls. This experiment does not
parallelize the preceding whole-program optimizer or introduce ThinLTO modules.
Correctness and generated-program runtime must be checked for each partition
count; partitioning can change generated code.

For later ownership work, TypeScript Go's
[checker pool](https://github.com/microsoft/typescript-go/blob/89d5d5b2849a0db0957065889ca58536fa6d2e4a/internal/compiler/checkerpool.go)
uses exclusive checker access and private semantic caches, balancing file affinity
against work distribution. Zig 0.15.1's
[`Air.zig`](https://github.com/ziglang/zig/blob/0.15.1/src/Air.zig)
keeps analyzed IR per function with compact indexed instruction storage, while ZIR
is per source file. These are design references for future isolation and memory
work, not speedup estimates for Pystachy. No implementation or benchmark result
from those projects is attributed to this prototype.
