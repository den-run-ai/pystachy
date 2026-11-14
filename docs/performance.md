# Performance

Pystachy's largest measured gains are on compute-heavy loops. String processing, regex
matching, allocation and exceptions have different costs, so measure the workload you intend
to run. The [language guide](language.md#support-at-a-glance) summarizes supported features;
the representation and operation determine their costs.

## Benchmarks

Run `PYSTACHY_PROGRAM_CACHE=0 make bench` to compare CPython, uncached JIT and AOT on your build. Each invocation measures each
mode once; repeat it to obtain a median. The benchmark gate in `make verify` checks output
agreement, without imposing timing thresholds.

The table gives v0.4.0-alpha.3's whole-process times on 11 November 2026: medians of five runs
per mode, in rotating order, with every process pinned to one CPU of a shared 4-vCPU Intel Xeon
@ 2.10 GHz VM, CPython 3.13.18 and LLVM 18.1.3. As in `make bench`, JIT times include
compilation and process startup, AOT times exclude the build, and every output matched CPython's.
The runtime compilation cache was primed first. The measured commit, `f07472a5`, has the
release's compiler, runtime and library sources.

| Workload | CPython | JIT | AOT | AOT speedup |
|---|---:|---:|---:|---:|
| `spectral.py`: nested numeric loops | 1.352 s | 0.094 s | 0.019 s | 72× |
| `nbody.py`: floats and objects | 1.859 s | 0.107 s | 0.035 s | 53× |
| `listindex.py`: checked `list[int]` reads | 0.298 s | 0.053 s | 0.006 s | 49× |
| `mandel.py`: float loops | 1.407 s | 0.092 s | 0.050 s | 28× |
| `fib.py`: recursive calls | 1.008 s | 0.092 s | 0.052 s | 20× |
| `sieve.py`: 4M-element list | 0.833 s | 0.203 s | 0.128 s | 6.5× |
| `dictcount.py`: counting with repeated key lookups | 0.964 s | 0.216 s | 0.153 s | 6.3× |
| `memo.py`: memoized recursion with `functools.cache` | 0.455 s | 0.189 s | 0.095 s | 4.8× |
| `dictkeys.py`: adversarial keys | 0.586 s | 0.240 s | 0.157 s | 3.7× |
| `itertools_loops.py`: `product`, `combinations`, `groupby`, `chain` | 0.599 s | 0.439 s | 0.165 s | 3.6× |
| `setdisplay.py`: constant set displays | 0.454 s | 0.223 s | 0.160 s | 2.8× |
| `dictlookup.py`: integer and string keys | 1.037 s | 0.503 s | 0.418 s | 2.5× |
| `words.py`: strings and dicts | 0.224 s | 0.141 s | 0.094 s | 2.4× |

- **Speedups** divide the unrounded medians. A mode's slowest run took up to 1.4 times its
  fastest, so the smaller ratios are approximate.
- **These JIT measurements include compilation on every run** (`PYSTACHY_PROGRAM_CACHE=0`). The
  Linux native CLI uses a [program cache](program-cache.md) by default;
  measure first fills and hits separately. Prebuilt AOT also avoids validation.
- **`json_records.py`, `list_reads.py` and `optional_scalars.py`**, the other programs
  `make bench` runs, are left out: their default runs take 16 to 25 ms under CPython, too short
  to time this way. See the [JSON benchmarks](json.md#benchmarks).
- **Data.** The [raw samples](../bench/results/bench-run-v0.4.0-alpha.3-2026-11-11.json) give every
  run's time, CPU time and peak RSS, and the executables' hashes. The
  [README's first program](../bench/results/readme-checkout-v0.4.0-alpha.3-2026-11-11.json) was
  measured the same way. The v0.1.0-alpha.4 table these replace, measured on 3 November 2026, is on
  [this page as of `f07472a5`](https://github.com/den-run-ai/pystachy/blob/f07472a535f165f939fdda774b1fcd4813e5c66d/docs/performance.md#benchmarks),
  which also links the table before it.

The [pyperformance results](../bench/pyperformance/README.md#recorded-results) compare alpha.3 and alpha.4 AOT instruction
counts on the benchmarks adapted from pyperformance 1.14.0. These are comparisons on adapted
sources, not official pyperformance scores. The [port notes](../bench/pyperformance/README.md)
describe adaptations, unsupported benchmarks and how to time CPython, JIT and AOT.

For numerical workloads, the [nanoGPT measurements](../examples/nanogpt/README.md#recorded-inference-performance)
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
more than a quarter of it is unused, and returns the unused whole pages to the operating system.

Cross-function exceptions require stack unwinding and can be expensive in hot loops.
Same-function handlers use branches. The [extended benchmark guide](extended-performance.md)
measures these paths separately, along with object dispatch and allocation.

## Representation costs

Keep concrete storage for homogeneous hot data where its semantics fit. Mixed values,
generators and exceptions remain useful; measure the paths the application actually uses.

| Execution path | Costs to measure | Contract |
|---|---|---|
| Concrete scalars and homogeneous containers | Native storage avoids dynamic boxes; allocation, hashing and string scans still cost work. | [Types and inference](language/typing.md) |
| Closed unions and recursive JSON | Numeric locals can use split tag/payload slots; union-valued container items can allocate boxes. Narrowing preserves the original container and its aliases. | [Mixed unions](language/typing.md#mixed-scalar-and-container-unions), [JSON ownership](json.md#values-and-ownership) |
| Dynamic `Any` | Boxing, runtime dispatch and identity tracking; supported identity observations can also affect typed code in the same program. | [Typed/dynamic boundaries](dynamic-any.md#the-typeddynamic-contract), [identity scope](dynamic-any.md#identity-scope) |
| Promoting integers | Inline arithmetic while values fit, then runtime calls and immutable digit storage; check conversions at 64-bit boundaries. | [Representation](python-int.md#representation), [boundaries](python-int.md#64-bit-boundaries) |
| Generators and exceptions | Direct iteration can avoid suspended frames; stored generators need state. Local handlers use branches, while cross-function exceptions unwind. | [Generators](internals.md#generators), [extended benchmarks](extended-performance.md) |
| Specialization and compilation | Frontend work, LLVM time and generated code size are separate from execution and heap costs. | [Compile time](#compile-time), [compiler inspection](compiler-inspection.md) |

Crossing a typed/dynamic boundary must preserve aliases and identity. Measure outputs and
effects before timing; keep execution, memory, compilation and generated-code size separate.
The [historical support maps](https://github.com/den-run-ai/pystachy/blob/a2cb8a3638d715577a7ab1cd1e4a0d6b01b6cdf2/docs/support-surface.md)
retain their checkpoint-specific classifications and measurements.

### Measure union boxing

`tools/union_values_bench.py` constructs and sums one million integers as `list[int]`
or `list[int | str]`; the boxed scan narrows explicitly. Both print checksum `499999500000`.
The [historical measurement](https://github.com/den-run-ai/pystachy/blob/a2cb8a3638d715577a7ab1cd1e4a0d6b01b6cdf2/docs/union-value-costs.md#boxing-measurement)
at `2438e7e0` reports medians from seven alternating AOT process pairs, pinned to one core
of a shared Intel Xeon 2.10 GHz Linux host with LLVM 18.1.3:

| Storage | Construction CPU | Scan CPU | Peak managed heap |
|---|---:|---:|---:|
| `list[int]` | 9.197 ms | 0.775 ms | 13.0 MiB |
| `list[int \| str]`, all integer payloads | 19.043 ms | 2.392 ms | 33.1 MiB |

CPU times exclude startup. Heap peaks came from separate untimed runs; they are neither
retained live memory nor RSS. List growth and GC thresholds affect the ratios, which are
specific to this workload and revision. Rerun on the build being evaluated:

```sh
./pystachy build tools/union_values_bench.py -o build/union-values
build/union-values typed 1000000
build/union-values boxed 1000000
PYSTACHY_GC=stats build/union-values typed 1000000
PYSTACHY_GC=stats build/union-values boxed 1000000
```

Repeat the two ordinary executions seven times, alternating their order. Each prints the
checksum, construction CPU nanoseconds and scan CPU nanoseconds. Keep GC-stat runs separate.

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
after `llvm-link --only-needed` (with `allocelide`, the first of two: `-emit-llvm`, then
`prog-late.bc` once the fast path is inlined). The transparent Clang wrapper in
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
capture machine-code instructions. For executed JIT bitcode, the wrappers of the JIT runner and `lli`
in [`tools/jitprobe.py`](../tools/jitprobe.py) read their bitcode input descriptor before execution;
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
| `listguard` | Runs a range loop's item reads and assignments without per-item checks where its bounds and one test of the lists' lengths before it prove them in range, so that LLVM can vectorize it | `PYSTACHY_OPT=-listguard` |
| `listget` | Removes bounds checks from proven sequence-loop reads, of lists and `bytes` | `PYSTACHY_OPT=-listget` |
| `listfast` | Inlines checked `list[int]` and `bytes` reads; negative/invalid indices use the runtime | `PYSTACHY_OPT=-listfast` |
| `allocelide` | Lets LLVM delete the allocation of an object or fixed tuple that holds only `int`, `float` and `bool` values and that nothing keeps; AOT builds then inline the allocator's fast path into the allocations left ([#1017](https://github.com/den-run-ai/pystachy/issues/1017)) | `PYSTACHY_OPT=-allocelide` |
| Stack tuple keys | Cache and memo hits can avoid heap allocation; escaping tuples are copied. `o[i, j]` of a class whose `__getitem__` and `__setitem__` only read the key makes the key in the caller's frame | [#308](https://github.com/den-run-ai/pystachy/pull/308), [#660](https://github.com/den-run-ai/pystachy/issues/660) |
| First-part split | `s.split(...)[0]` produces only the required string | [#317](https://github.com/den-run-ai/pystachy/pull/317) |
| In-place str append | `s += t` and `s = s + t` on a str local grow its str in place while only the local holds it; past 8,200 bytes a second copy leaves room for as much again, trimmed after its length is unchanged across two sweeps | [#544](https://github.com/den-run-ai/pystachy/pull/544), [#567](https://github.com/den-run-ai/pystachy/issues/567); no switch |
| JIT helper inlining | Runs user-function inlining for programs of at most 20,000 IR lines by default | `PYSTACHY_JIT_INLINE=0` disables it |
| Runtime functions in JIT loops | Gives those programs copies of the small runtime functions they call (a `list[float]` read or assignment, float division, `math.sqrt()`, a shift, an int `%`), which the inliner then inlines, as AOT builds inline the runtime ([#705](https://github.com/den-run-ai/pystachy/issues/705)) | `PYSTACHY_OPT=-jithelpers` |

`PYSTACHY_OPT=-all` disables the typed-IR passes, and the runtime's copies for JIT loops. JIT
inlining has a separate control: `PYSTACHY_JIT_INLINE=N` changes the size limit, for the program's
functions and those copies alike; the rest of the separately compiled runtime stays calls, where
AOT optimizes the program and the whole runtime together. The measured tradeoffs are recorded in
[#333](https://github.com/den-run-ai/pystachy/pull/333); the pipeline is described in
[compiler internals](internals.md).

The copies cut the instructions a loop executes where it reads `list[float]` items, divides floats
or calls `math.sqrt()`: pyperformance's spectral_norm runs 0.45× as many, scimark 0.58×, nbody
0.59× and the UMAP probe 0.73× (callgrind, of the program cache's executables). A program cache
hit, which compiles nothing, then takes 0.61× the time for spectral_norm and 0.78× for the UMAP
probe. An uncached launch also compiles the inlined code: the JIT corpus took 4% longer, and a
program up to 75 ms (scimark: 1.38× the time at its default size, 0.84× with ten times its loops).
Times are paired medians on one x86-64 core ([results](../bench/results/jit-helpers-2026-11-14.json)).

## Start-up and memory

JIT execution includes frontend and LLVM work; a built AOT executable starts directly.
The first JIT run after a runtime rebuild also pays for compiling the runtime cache.
Separate process startup, first calls and warmed execution when reporting results.
For startup-sensitive runs, `PYSTACHY_JIT_CODEGEN=0` opts into `-O0` code generation, which
the [JIT runner](internals.md#the-jit-runner) does itself (with `lli`, an object of `llc`'s,
whose extra process costs tiny programs). It can reduce large-program startup while slowing
execution; benchmark the complete workload. Unset or `2` retains ORC's own level of code
generation. See [#430](https://github.com/den-run-ai/pystachy/issues/430) for the measured
tradeoff; it is independent of `PYSTACHY_JIT_INLINE`.

A program that builds `list(range(4194305))` peaks at **34.2 MiB RSS in v0.4.0-alpha.3's AOT
executable, against 171.2 MiB in CPython 3.13.18**, a 5.0× reduction. The JIT's processes,
which include LLVM's, peak at 91.1 MiB. These are medians of five runs per mode,
from `wait4`, on the VM and commit of the [benchmark table](#benchmarks)
([raw data](../bench/results/range-list-rss-v0.4.0-alpha.3-2026-11-11.json)). With `PYSTACHY_GC=stats`,
the AOT run reports two collections and a 32.3 MiB managed-heap peak; managed-heap statistics
measure a different quantity from process RSS.
[#201](https://github.com/den-run-ai/pystachy/pull/201) made `list(range())` allocate its list at
its final length.

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
