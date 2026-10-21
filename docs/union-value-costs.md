# Explicit union costs

These compatibility changes retain native concrete values. Crossing into a union
allocates an immutable tag/payload box; widening reuses it. A container member's
payload is its original pointer, never a copied mutable container. Generic scalar
operations select existing typed operations by tag. This is not runtime
specialization and does not promise faster execution.

## Boxing measurement

`tools/union_values_bench.py` builds one million integers and sums them. The two paths
differ only in the list's element type and the boxed scan's explicit narrowing.
Both return 499999500000. Seven alternating AOT process pairs, pinned to one core of
a shared x86-64 Linux host (Intel Xeon at 2.10 GHz) with LLVM 18.1.3, at `2438e7e0`,
produced these median **process CPU times**, excluding startup; heap peaks and
collections come from separate untimed `PYSTACHY_GC=stats` runs.

| Representation | Construction | Scan | Heap peak | Collections |
|---|---:|---:|---:|---:|
| `list[int]` | 9.197 ms | 0.775 ms | 13.0 MiB | 2 |
| `list[int \| str]`, all integer payloads | 19.043 ms | 2.392 ms | 33.1 MiB | 0 |

For this workload, boxing costs 2.1 times the construction CPU time and 2.5 times
the peak heap. This measures the existing union representation's cost, not a
slowdown introduced by adding operations. GC thresholds, list growth and retained
objects affect the ratios; they are not universal per-value memory multipliers.
The concrete run collects twice as its pointer-free item array grows. Each box takes
a 16-byte heap slot (#800). With the 24-byte slots before, the same build took
32.5 ms to construct the boxed list (against 19.4 ms, in 7 runs alternating the two),
and it collected once, at the same heap peak.

```sh
python3 -m pystachy build tools/union_values_bench.py -o build/union-values
build/union-values typed 1000000
build/union-values boxed 1000000
PYSTACHY_GC=stats build/union-values typed 1000000
PYSTACHY_GC=stats build/union-values boxed 1000000
```

Repeat the first two executions seven times, alternating their order. Each prints
the checksum, construction CPU nanoseconds and scan CPU nanoseconds.

## Existing typed controls

Against storage parent `58b812d`, all 27 benchmark/IR probe programs, plus three
generated extended-benchmark drivers, emit byte-identical LLVM IR. The runtime's
generic descriptor handlers do change, so runtime measurements are still needed.
Seven alternating AOT process pairs, each with one warmup and five samples, gave
the following medians of process medians; checksums independently match CPython.

| Existing kernel | N | Parent CPU time | Stack CPU time |
|---|---:|---:|---:|
| `object_dispatch` | 20000 | 4.367 ms | 4.640 ms |
| `text_pipeline` | 10000 | 90.516 ms | 88.163 ms |
| `list_churn` | 10000 | 10.254 ms | 10.294 ms |

The observations range from 2.6% faster to 6.3% slower. This shared host was also
running validation; these advisory samples establish neither an improvement nor
a strict performance-regression bound. No timing threshold is added to CI.

To reproduce the controls, use `tools/bench_extended.py`'s `driver(name)` with
`perf_counter_ns` replaced by `process_time_ns`. Compile the same source with the
parent and stack, setting `PYSTACHY_PATH=bench/extended`; run each executable with
`N 1 5`, alternate the two binaries, and compare emitted checksums. The unchanged
standard extended benchmark also reports startup, compilation and wall time.

## Follow-up mixed-value operations

Against prior value stack `e22cb90`, follow-up `c6f5b67` emits byte-identical LLVM
for all 27 existing controls (12 benchmarks, 14 IR probes and the relocated
`tools/union_values_bench.py`), plus the same three generated drivers. The mixed
truth, formatting, equality and search changes retain the existing tag/payload
box representation; the boxing measurements above remain separate from operation
costs.

Using the process-CPU procedure above, seven alternating AOT process pairs with
one warmup and five samples each produced these medians of process medians.
Every checksum matched CPython independently.

| Existing kernel | N | `e22cb90` CPU time | Follow-up CPU time |
|---|---:|---:|---:|
| `object_dispatch` | 20000 | 4.751 ms | 4.411 ms |
| `text_pipeline` | 10000 | 98.015 ms | 96.143 ms |
| `list_churn` | 10000 | 15.114 ms | 15.775 ms |

Timing binaries were built from the tree published as `10ecf90`; the compiler-only
correction in `c6f5b67` leaves their runtime sources and all 30 control IR outputs unchanged.
The shared host was running other validation and showed substantial variability.
These advisory observations, from 7.2% faster to 4.4% slower, establish neither a
performance improvement nor a strict regression bound. No timing threshold is
added to CI.

## Remaining boundary

Explicit finite-depth list/dict unions preserve mutable identity. Recursive JSON
aliases still require finite type-graph references and cycle-safe equivalence and
descriptor traversal; see `docs/typed-ir.md`. Replacing AskMe's `JsonNode` wire
codec must additionally preserve numeric lexemes, duplicate-key/Unicode rejection
and its size/depth limits. This stack does not replace that codec, introduce `Any`,
or infer unions at unrelated branches and returns.
