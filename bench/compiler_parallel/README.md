# Compiler parallelism experiments

Compare serial AOT builds, overlapping cold-runtime jobs, and full-LTO codegen
partitions using the same native compiler and sources. The defaults remain one
build job and the ordinary native-object link. This harness supplies evidence for
[#1011](https://github.com/den-run-ai/pystachy/issues/1011); it does not set a
performance threshold or change CI concurrency.

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
