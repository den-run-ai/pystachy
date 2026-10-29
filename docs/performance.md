# Performance

Pystachy's largest measured gains are on compute-heavy loops. String processing, regex
matching, allocation and exceptions have different costs, so measure the workload you intend
to run.
The [support-surface diagrams](support-surface.md) connect these costs to concrete storage,
boxed unions, dynamic `Any`, generators and exceptions.

## Benchmarks

Run `make bench` to compare CPython, JIT and AOT on your build. Each invocation measures each
mode once; repeat it to obtain a median. The benchmark gate in `make verify` checks output
agreement, without imposing timing thresholds.

The following measurements were recorded in October 2026 on a 4-core x86-64 Linux VM with
CPython 3.13.16 and LLVM 18, using the median of three warm runs. The source revision was not
recorded, so these figures are examples of workload differences, not results for the latest build.
JIT times include compilation and process startup; AOT times exclude compilation.
The runtime compilation cache is primed first, and outputs are checked against CPython.

| Workload | CPython | JIT | AOT | AOT speedup |
|---|---:|---:|---:|---:|
| `fib.py`: recursive calls | 0.80 s | 0.08 s | 0.04 s | 23× |
| `mandel.py`: float loops | 1.26 s | 0.09 s | 0.04 s | 34× |
| `nbody.py`: floats and objects | 1.82 s | 0.10 s | 0.03 s | 59× |
| `spectral.py`: nested numeric loops | 1.07 s | 0.09 s | 0.02 s | 67× |
| `sieve.py`: 4M-element list | 0.76 s | 0.21 s | 0.15 s | 5× |
| `words.py`: strings and dicts | 0.17 s | 0.10 s | 0.05 s | 3× |
| `dictlookup.py`: integer and string keys | 0.90 s | 0.47 s | 0.39 s | 2× |
| `dictkeys.py`: adversarial keys | 0.50 s | 0.25 s | 0.16 s | 3× |
| `setdisplay.py`: constant set displays | 0.40 s | 0.20 s | 0.12 s | 3× |
| `itertools_loops.py`: `product`, `combinations`, `groupby`, `chain` | 0.65 s | 0.43 s | 0.17 s | 4× |

The `itertools_loops.py` row uses five runs per mode on a shared 4-core VM on 2026-10-16,
with `lib/_pystachy_itertools.py`'s generators. Speedups use unrounded timings.

The [pyperformance results](pyperformance.md) compare CPython, JIT and AOT on 18 benchmarks
adapted from pyperformance 1.14.0, including regex workloads. These are comparisons on adapted
sources, not official pyperformance scores. The [port notes](../bench/pyperformance/README.md)
describe adaptations and unsupported benchmarks.

For numerical workloads, the [nanoGPT measurements](../examples/nanogpt/README.md#paired-measurement-after-the-array-and-blas-work)
compare inference with CPython, NumPy and PyTorch. The
[ndarray benchmark](../examples/ndarray/README.md#recorded-benchmark) compares elementwise
operations, reductions and matrix products with NumPy. Both document inputs, threading,
compilation costs and reproduction commands.

## Caching workloads

Caching event classifications skips matching entirely on repeated names. Fnmatch's pattern
cache only skips compilation; it still matches every event. The
[router measurements](../examples/route/README.md#current-paired-snapshot) compare both runtimes
using the same inputs and cache policies, including repeated names, unique names and misses.

Measure the hit rate as well as the cost of a hit. A cache that rarely hits adds lookup and
eviction work. See [caching text processing](caching.md) for cache bounds, invalidation and
regex/textwrap benchmarks, or the [matrix-chain benchmark](https://github.com/den-run-ai/pystachy/pull/308)
for memoization of recursive computation.

<a id="where-the-gains-are-smaller"></a>
<a id="the-cost-of-exceptions"></a>

## Costs to watch

Memory-bound work and functions already implemented in CPython's C runtime often gain less.
Checked 64-bit integer arithmetic also limits some optimizations. Regex-heavy misses can be
slower than CPython's `_sre`, even when cache hits are faster.

Appending to a str local with `+=` is linear while the loop reads the local only through `len()`.
Any other read (printing, comparing, slicing, passing or storing it) may share the str, so the
next append copies it, where CPython copies only when another reference remains; such a loop is
quadratic. `"".join(parts)` stays linear. A str that appends keep growing past 8,200 bytes, the
largest size class, gets room for as much again from its second copy on. After its length is
unchanged across two consecutive sweeps, the collector trims excess capacity in place when
more than a quarter of it is unused. On Linux, this also returns unused whole pages to the
operating system; other platforms may retain those pages in RSS until the str is freed.

Cross-function exceptions require stack unwinding and can be expensive in hot loops.
Same-function handlers use branches. The [extended benchmark guide](extended-performance.md)
measures these paths separately, along with object dispatch and allocation.

## Inspecting emitted LLVM calls

`tools/ir_cost_report.py` inventories static call sites by function, records the
input bytes' SHA-256, and distinguishes runtime declarations from definitions.
It accepts the canonical text produced by Pystachy and LLVM; it does not compile,
run, or validate a program. Function headers and call instructions must be on one
line. Unknown call targets are counted as `<unresolved>` with their line numbers.

```sh
./pystachy ir bench/sieve.py -o /tmp/sieve.raw.ll
python3 tools/ir_cost_report.py --ir raw=/tmp/sieve.raw.ll \
  --function '^(main|f\.|m\.)' -o /tmp/sieve.calls.json
```

Repeat `--ir LABEL=FILE` to compare raw, JIT, and AOT optimized modules in one
report. Labels are supplied by the caller; record the source revision, toolchain
versions, flags, and commands beside the report. Keep the exact module used by
each compilation stage. `opt` on raw program IR cannot inline C helper bodies
that are only declarations. AOT's driver links the needed runtime bitcode before
running Clang's optimizer; a GCC object sidecar is a different experiment. The
`runtime_symbols` entries expose headers and referenced attribute groups so this
distinction can be checked for the helpers under investigation.

For AOT, capture the driver's `prog.bc` at the `clang -O2 -c` invocation,
after `llvm-link --only-needed`. The transparent Clang wrapper in
[`tools/aotprobe.py`](../tools/aotprobe.py) demonstrates that capture; the
driver normally deletes its temporary files. Do not select an arbitrary cached
`runtime*.bc`, which may belong to another compiler or configuration. Once that
module has been saved as `/tmp/program.linked.bc`, use the **same LLVM toolchain**:

```sh
llvm-dis /tmp/program.linked.bc -o /tmp/program.linked.ll
clang -O2 -S -emit-llvm /tmp/program.linked.bc -o /tmp/program.aot-replay.ll
python3 tools/ir_cost_report.py --ir raw=/tmp/program.raw.ll \
  --ir linked=/tmp/program.linked.ll --ir aot-replay=/tmp/program.aot-replay.ll \
  --function '^(main|f\.|m\.)' -o /tmp/program.calls.json
```

Here `/tmp/program.raw.ll` must be emitted from the same source and settings as
the captured build. The Clang command replays the default AOT optimizer; preserve
any extra compilation flags when investigating a non-default build. It does not
capture machine-code instructions. For executed JIT bitcode, the `lli` wrapper
in [`tools/jitprobe.py`](../tools/jitprobe.py) reads `/dev/fd/9` before execution;
do not label raw-IR `opt -O2` output as the JIT pipeline.

Read `modules[LABEL].functions[NAME].calls` for a specific function, and compare
`runtime_symbols` to check whether its callees have bodies. A filter that matches
nothing reports `selected_functions: 0`; check that field before drawing a
conclusion. The `f.`/`m.` prefixes can also select linked runtime functions, so
use exact function names when attributing a change to application code.

Follow an interesting surviving call with a correctness check and a profile:

```sh
(
  set -e
  python3.13 bench/words.py > /tmp/words.expected
  ./pystachy build bench/words.py -o /tmp/words
  /tmp/words > /tmp/words.actual
  cmp /tmp/words.expected /tmp/words.actual
  valgrind --tool=callgrind --callgrind-out-file=/tmp/words.callgrind /tmp/words
  callgrind_annotate --tree=both --inclusive=yes /tmp/words.callgrind
)
```

An inclusive profile charges callees to their caller, so do not add overlapping
subtrees. For example, `counts[w] = counts.get(w, 0) + 1` can leave one `get` and
one `set` site, each executed once per word. The profile establishes whether the
duplicate lookup matters; a single static site cannot establish its frequency.

Counts are **static sites, not dynamic calls, allocations, or timings**. Inlining
`pys_alloc` can leave free-list updates and `gc_slow` calls, and inlining list access
can leave bounds checks and pointer reloads. Fewer helper calls do not prove less
work. The function filter does not establish reachability, and attribute presence
does not establish that adding those attributes to a collector would be safe.
Use the existing correctness-gated benchmarks and profilers for execution cost.
This inventory does not implement source-line annotations or explain missed passes.

<a id="tuples-made-in-the-frame"></a>
<a id="the-first-part-of-a-split"></a>
<a id="inlining-under-the-jit"></a>

## Optimizations on the typed IR

| Optimization | Effect | Comparison control |
|---|---|---|
| `dictfuse` | Reuses a proven lookup of the same key | `PYSTACHY_OPT=-dictfuse` |
| `listget` | Removes bounds checks from proven sequence-loop reads, of lists and `bytes` | `PYSTACHY_OPT=-listget` |
| `listfast` | Inlines checked `list[int]` and `bytes` reads; negative/invalid indices use the runtime | `PYSTACHY_OPT=-listfast` |
| Stack tuple keys | Cache and memo hits can avoid heap allocation; escaping tuples are copied. `o[i, j]` of a class whose `__getitem__` and `__setitem__` only read the key makes the key in the caller's frame | [#308](https://github.com/den-run-ai/pystachy/pull/308), [#660](https://github.com/den-run-ai/pystachy/issues/660) |
| First-part split | `s.split(...)[0]` produces only the required string | [#317](https://github.com/den-run-ai/pystachy/pull/317) |
| In-place str append | `s += t` and `s = s + t` on a str local grow its str in place while only the local holds it; past 8,200 bytes a second copy leaves room for as much again, trimmed after its length is unchanged across two sweeps | [#544](https://github.com/den-run-ai/pystachy/pull/544), [#567](https://github.com/den-run-ai/pystachy/issues/567); no switch |
| JIT helper inlining | Inlines program functions up to 20,000 IR lines by default | `PYSTACHY_JIT_INLINE=0` disables it |

`PYSTACHY_OPT=-all` disables the typed-IR passes. JIT inlining has a separate control:
`PYSTACHY_JIT_INLINE=N` changes the size limit. It excludes the separately compiled runtime;
AOT optimizes the program and runtime together. The measured tradeoffs are recorded in
[#333](https://github.com/den-run-ai/pystachy/pull/333); the pipeline is described in
[compiler internals](internals.md).

## Start-up and memory

JIT execution includes frontend and LLVM work; a built AOT executable starts directly.
The first JIT run after a runtime rebuild also pays for compiling the runtime cache.
Separate process startup, first calls and warmed execution when reporting results.
For startup-sensitive runs, `PYSTACHY_JIT_CODEGEN=0` opts into MCJIT `-O0` code
generation. It can reduce large-program startup while slowing execution; benchmark
the complete workload. Unset or `2` retains the default ORC path. See [#430](https://github.com/den-run-ai/pystachy/issues/430)
for the measured tradeoff; it is independent of `PYSTACHY_JIT_INLINE`.

For `list(range(4194305))`, [#201](https://github.com/den-run-ai/pystachy/pull/201) recorded
**169 MiB CPython versus 34.2 MiB AOT peak RSS**, approximately a 5× reduction. This used
CPython 3.13, LLVM 18.1.3 and a shared 4-core VM; candidate `2ccb2a6` was tested against
main `fa60123`. RSS was collected with `wait4`, with `PYSTACHY_GC=stats` for the AOT run.
Managed-heap statistics measure a different quantity from process RSS.

Memory savings depend on object representation and lifetime. The router's streaming workload
instead recorded higher AOT peak RSS because collection is deferred. Cached string hashes
also consume space; [#99](https://github.com/den-run-ai/pystachy/pull/99) records that tradeoff.

A collection runs when the bytes allocated since the last one reach the larger of 32 MiB and
the bytes live after it. Pointer-free large objects (8,200 bytes or more: strs and the arrays
of lists of numbers past 1,024 items) also start one when they are at least half of what was
allocated since and reach 4 MiB, or as many bytes as were live. Only a collection frees one,
so without that budget a program that mostly makes and drops big arrays goes through 32 MiB of
them, cold in cache and zeroed again, between collections. Programs that mostly allocate small
objects or lists of objects keep the 32 MiB window.

## Compile time

Compile time changes with source size, imports, optimization settings and toolchain.
Use `tools/bench_extended.py` to separate hosted/native IR generation, AOT build, JIT process
time and warmed execution. Use `tools/scaling.py` for compiler-growth probes.
The [verification guide](testing.md) describes deterministic scaling and container checks,
which catch regressions without depending on shared-host timing.
