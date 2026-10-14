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
AOT optimizes the program and runtime together at `-O2`. First/hot differences can reflect
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
The kernels are original implementations. Copied upstream benchmarks would need pinned
sources, licenses and documented adaptations before comparing published scores.

## Measured observations

Historical prototype snapshot at `3542d63`: Linux x86-64, LLVM 18.1.3, CPython 3.12.14,
default N, three processes per mode and three timed calls per process. Raw samples were not
retained in the repository. These shared-host diagnostics describe that revision only.

| Case | CPython hot, ms | JIT hot, ms | AOT hot, ms |
|---|---:|---:|---:|
| `object_dispatch` | 128.7 | 3.95 | 2.68 |
| `text_pipeline` | 129.9 | 49.76 | 52.30 |
| `list_churn` | 124.0 | 15.57 | 10.83 |
| `exception_local` | 149.0 | 11.46 | 5.40 |
| `exception_unwind` | 217.4 | 249.09 | 172.06 |
| `long_string_keys` | 9.94 | 498.38 | 512.96 |
| `sort_records` | 137.0 | 19.97 | 14.17 |

The long-key result predates the hash cache merged in
[#99](https://github.com/den-run-ai/pystachy/pull/99). Its separate before/after experiment
on candidate `5af35f4` recorded **498.420 → 1.825 ms AOT** and **497.959 → 1.771 ms JIT**
for this kernel: five process medians per side/mode, CPU 0 affinity, LLVM 18.1.3, Linux
Xeon Platinum 8573C. Those compare Pystachy revisions, rather than CPython. Fresh equal
strings still need their own hash, and the extra hash field increases retained string memory.

The historical cross-function exception row includes helper-call and generated-code costs;
it does not isolate unwinding. The text pipeline's similar JIT/AOT times also need a profile
before attributing the cost to GC or missing optimization. Run the suite on current revisions
to make a new performance claim.
