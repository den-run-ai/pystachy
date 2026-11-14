<a id="extended-subset-performance-prototype"></a>

# Extended performance diagnostics

`tools/bench_extended.py` measures supported-subset kernels across CPython, JIT and AOT.
It separates compiler/startup costs from execution and saves raw samples and provenance.
Use it to locate expensive paths alongside the [main benchmarks](performance.md).
These small original kernels do not constitute a representative application score.

| Case | Work exercised | Default N |
|---|---|---:|
| `object_dispatch` | Field access and methods on 64 persistent objects | 20,000 |
| `text_pipeline` | Split/strip/lower, conversion and dict aggregation | 10,000 |
| `list_churn` | Growth, slices, extend, pop, reductions and allocation | 10,000 |
| `exception_local` | Raise every eight iterations, handled locally | 2,000,000 |
| `exception_unwind` | Same raise rate across a function boundary | 2,000,000 |
| `long_string_keys` | Reused 64 string keys, roughly 1 KiB each | 5,000 |
| `sort_records` | Object allocation, comparisons and stable sorting | 2,000 |

N counts batches within each case, not comparable units across cases. Input sizes stay
bounded as N grows; each call includes setup and returns a deterministic checksum.

## Run

With the normal LLVM 18 setup (`PYSTACHY_LLVM` if needed), run from the repository root:

```sh
make
make bench-extended-check
python3 tools/bench_extended.py --json build/extended-performance.json --keep build/extended
python3 tools/bench_extended.py --cases text_pipeline long_string_keys --scale 4 --processes 5 --samples 5 --warmups 2 --json build/extended-large.json
```

| Option | Purpose |
|---|---|
| `--smoke` | N=2, one process, two samples; correctness only |
| `--cases NAME ...` | Select kernels |
| `--scale N` | Multiply default workload sizes, except in smoke mode |
| `--processes`, `--samples`, `--warmups` | Control repetitions and calls within each process |
| `--keep DIR` | Retain drivers, kernels, IR and executables in a new directory |
| `--compiler COMMAND` | Shell-split compiler command, without shell evaluation |
| `--timeout SECONDS` | Bound each command and its LLVM children; default 120 |

The default report is `build/extended-performance.json`. It includes raw output, commands,
checksums, first/sample times, summary statistics, revision/dirty status, source/driver hashes,
platform/toolchain data and environment overrides. Failures return nonzero with `status: failed`;
partial or failed reports are not results. `make bench-extended BENCH_ARGS='--scale 2'`
collects timings; CI runs the correctness smoke and controller tests only.

## What the measurements include

### JSON byte-scanning controls

`bench/extended/json_scan.py` measures direct dynamic JSON decoding and the
maintained JSON-repair facade. It checks complete expected values outside timing,
consumes every result inside timing, and checks each batch's checksum. Each `case`
row records API, workload, requested size, source character/byte counts and calls;
`first`, `warmup`, `sample` and `verified` rows separate execution phases.
Durations are nanoseconds. This standalone driver is separate from the kernel
controller above so that both APIs and all cases can share one JIT compilation.

```sh
PYTHONPATH=ports python3 bench/extended/json_scan.py suite all 4096 1 3 7
PYSTACHY_PATH=ports ./pystachy run bench/extended/json_scan.py suite all 4096 1 3 7
PYSTACHY_PATH=ports ./pystachy build bench/extended/json_scan.py -o build/json-scan
build/json-scan suite all 4096 1 3 7
PYTHONPATH=ports pypy3 bench/extended/json_scan.py suite no-direct-control 4096 1 3 7
```

`all` runs 18 cases; `no-direct-control` omits only the direct malformed-control
case. PyPy 8.0.1 reports that control one character earlier than CPython 3.13.16,
so that comparison fails the exact diagnostic oracle. The oracle remains strict.
Long strings use N/2N/4N. Other cases use size 8192, except fixed small short/mixed
inputs. Batch counts are 2000 for long strings, 200000 short, 40000 mixed, 3000
sparse escapes, 300 dense escapes, 300 Unicode, 300 direct-control and 100
repair-control, multiplied by the fourth argument. The last arguments select
warmup and measured batches. A single case uses
`direct|repair CASE SIZE CALLS WARMUPS SAMPLES`.

Use interleaved independent processes pinned to one CPU, compare medians of
per-process medians, and retain raw samples and source/executable/toolchain hashes.
Keep startup, compilation and instrumented memory runs separate. Both APIs compile
into this driver, so its startup is not a decoder-only import or compilation cost.

### Kernel timing boundaries

| Measurement | Included work |
|---|---|
| `hosted_ir` / `native_ir` | Compiler process startup, loading/lowering and IR output |
| `aot_build` | Native frontend, runtime linking, optimization, code generation and executable link |
| `jit` wall | Fresh process, frontend, LLVM cleanup/ORC, all calls and output |
| `aot` / `cpython` wall | Fresh process, all calls and output; AOT compilation excluded |
| `first` | First kernel call, excluding process/frontend startup and printing |
| `hot` | Median of subsequent timed calls per process, then median across processes |

Every driver imports the full kernels module, so compilation includes that shared module.
Independently measured phases cannot be subtracted to obtain an exact backend cost.
The runner primes the runtime compilation cache and the hosted frontend's bytecode cache
before timing; these are warm-cache measurements, excluding clean-install cost.

Within each fresh process, the first measured call precedes extra warmups and timed samples.
Execution order rotates between modes and processes run sequentially. Every first, warmup
and sample checksum must agree with an independent CPython oracle.

A separate `PYSTACHY_GC=stats` AOT probe records collection count/time, peak managed heap
and last-collection live bytes; it is excluded from timing. This probe forces normal GC
statistics even if timed samples used `PYSTACHY_GC=off`. Last-live is not final live memory
and can be zero when there was no collection. The runner does not measure process RSS.

The JIT uses LLVM ORC with a precompiled runtime and limited program-function inlining.
AOT optimizes the program at `-O2` with the bodies of the runtime functions it may inline. First/hot differences can reflect
cache, allocator and GC state; the JIT does not adaptively tier from an interpreter.

## Compare and investigate

Use two worktrees at explicit revisions with identical runner and kernel files. Build and run
each side from its own checkout with its own `PYSTACHY_HOME`, source, libraries and runtime
cache. Pointing only `--compiler` at another checkout mixes provenance. Record intentionally
copied files as dirty changes, hold inputs/flags/toolchain constant, and alternate runs.

Increase N until calls are long enough to measure, inspect variation and repeat on an idle
machine with the same CPU affinity. There is no automatic duration calibration or timing gate.
Optimization/GC environment overrides are honored and recorded.

```sh
python3 tools/scaling.py -s funcs,fields,lookups,gdicts -n 500,1000,2000 -r 3 --ops
python3 -m cProfile -o build/frontend.prof -m pystachy ir build/extended/text_pipeline.py -o build/frontend.ll
python3 -m pstats build/frontend.prof
perf record -g -- build/extended/text_pipeline.exe 10000 1 3
perf report
```

`--ops` needs CPython 3.12+. `cProfile` measures the CPython-hosted frontend, not compiled
execution; `perf` requires Linux support and permission. A separate profiling build can use
`PYSTACHY_CFLAGS='-g -fno-omit-frame-pointer'`; this adds no Python source debug information.
Keep profiling runs separate from baseline timings. Controls such as `PYSTACHY_OPT=-dictfuse`
or `-all` can test a hypothesis before deeper profiling.

<a id="relationship-to-existing-work"></a>
<a id="source-review-and-scope"></a>

## Scope and correctness

This suite complements `bench/run.sh`, `tools/scaling.py` and the deterministic container
probes described in [testing](testing.md). Checksums do not replace differential tests.
The kernels are original implementations. Adapted upstream benchmarks, with pinned sources,
licenses and documented adaptations, are measured separately in [pyperformance results](../bench/pyperformance/README.md#recorded-results).

<a id="measured-observations"></a>

## Earlier measurements

No measurement of a current compiler is recorded here: run the suite on the revisions you
compare. A prototype snapshot at `3542d63` (10 October 2026, CPython 3.12.14, raw samples not
retained) is on [this page as of alpha.4](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/docs/extended-performance.md#measured-observations).
It predates, among other changes, the string-hash cache of
[#99](https://github.com/den-run-ai/pystachy/pull/99), so its rows do not describe later builds.
