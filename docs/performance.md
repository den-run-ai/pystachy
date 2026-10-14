# Performance

Pystachy's largest measured gains are on compute-heavy loops. String processing, regex
matching, allocation and exceptions have different costs, so measure the workload you intend
to run. The tables below are published snapshots; they have not been rerun for this guide.

## Benchmarks

Published October 2026 baseline: 4-core x86-64 Linux VM, CPython 3.13.16, LLVM 18,
median of three warm runs. The source revision was not recorded with this table.
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

Speedups use the unrounded timings. The README rounds the maximum 67× to about 70×.
Run `make bench` to collect current results. Each invocation of `bench/run.sh` measures each
mode once; repeat it to obtain a median. The benchmark gate in `make verify` rejects output
mismatches, without imposing timing thresholds.

## Caching workloads

Caching event classifications skips matching entirely on repeated names. Both implementations
use the same cache policy in these comparisons; fnmatch's pattern cache alone still matches
each event. See the [router example](../examples/route/README.md) for inputs and reproduction.

| Workload | CPython | AOT | Source |
|---|---:|---:|---|
| Router, fnmatch per rule, 1M events | 2.927 s | 1.866 s | Initial [#294](https://github.com/den-run-ai/pystachy/pull/294) table |
| Router, cached classifications, 1M events | 0.236 s | 0.158 s | #294 follow-up, branch tested with main `bbf8959` |
| Memoized matrix-chain computation | 0.355 s | 0.068 s | [#308](https://github.com/den-run-ai/pystachy/pull/308), candidate `c7de6d3` |

The router measurements use a 4-core x86-64 VM and CPython 3.13.16: median of five
whole-program wall times, including startup. They correspond to 1.6× and 1.5× faster AOT
execution, rounded in the announcement. The memo workload uses a chain of 220 matrices and
3.5M cache hits, median of five runs. Its roughly 5× gain is specific to that workload.
For regex and textwrap measurements, see [caching text processing](caching.md).

<a id="where-the-gains-are-smaller"></a>
<a id="the-cost-of-exceptions"></a>

## Costs to watch

Memory-bound work and functions already implemented in CPython's C runtime often gain less.
Checked 64-bit integer arithmetic also limits some optimizations. Regex-heavy misses can be
slower than CPython's `_sre`, even when cache hits are faster.

Cross-function exceptions require stack unwinding and can be expensive in hot loops.
Same-function handlers use branches. The [extended benchmark guide](extended-performance.md)
measures these paths separately, along with object dispatch and allocation.

<a id="tuples-made-in-the-frame"></a>
<a id="the-first-part-of-a-split"></a>
<a id="inlining-under-the-jit"></a>

## Optimizations on the typed IR

| Optimization | Effect | Comparison control |
|---|---|---|
| `dictfuse` | Reuses a proven lookup of the same key | `PYSTACHY_OPT=-dictfuse` |
| `listget` | Removes bounds checks from proven sequence-loop reads | `PYSTACHY_OPT=-listget` |
| `listfast` | Inlines checked `list[int]` reads; negative/invalid indices use the runtime | `PYSTACHY_OPT=-listfast` |
| Stack tuple keys | Cache and memo hits can avoid heap allocation; escaping tuples are copied | [#308](https://github.com/den-run-ai/pystachy/pull/308) |
| First-part split | `s.split(...)[0]` produces only the required string | [#317](https://github.com/den-run-ai/pystachy/pull/317) |
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

For `list(range(4194305))`, [#201](https://github.com/den-run-ai/pystachy/pull/201) recorded
**169 MiB CPython versus 34.2 MiB AOT peak RSS**, approximately a 5× reduction. This used
CPython 3.13, LLVM 18.1.3 and a shared 4-core VM; candidate `2ccb2a6` was tested against
main `fa60123`. RSS was collected with `wait4`, with `PYSTACHY_GC=stats` for the AOT run.
Managed-heap statistics measure a different quantity from process RSS.

Memory savings depend on object representation and lifetime. The router's streaming workload
instead recorded higher AOT peak RSS because collection is deferred. Cached string hashes
also consume space; [#99](https://github.com/den-run-ai/pystachy/pull/99) records that tradeoff.

## Compile time

Compile time changes with source size, imports, optimization settings and toolchain.
Use `tools/bench_extended.py` to separate hosted/native IR generation, AOT build, JIT process
time and warmed execution. Use `tools/scaling.py` for compiler-growth probes.
The [verification guide](testing.md) describes deterministic scaling and container checks,
which catch regressions without depending on shared-host timing.
