# Caching text processing

Cache the work that repeats: compiling a pattern, parsing a replacement, or computing a
complete result. Pystachy's `cache` and `lru_cache` are written in the supported subset.
The [router example](../examples/route/README.md) shows an application result cache.

| Cache | A hit skips | Bound |
|---|---|---|
| `fnmatch._compile_pattern` | Glob translation and regex compilation | 32,768 patterns, LRU |
| `re.compile` | Regex parsing and compilation | 512 patterns, FIFO |
| Regex replacement template | Replacement parsing and group resolution | 512 templates, FIFO |
| Pattern ASCII classes | Character-class opcode interpretation | 128 entries per used class, owned by pattern |
| Regex decoded subject | Decoding the same string object again | Last subject only |
| Application `lru_cache` | Entire function body | Chosen `maxsize` |

ASCII tables are built lazily; non-ASCII characters retain the class evaluator. Stable integer
constants also allow LLVM switches in regex dispatch. Textwrap skips unnecessary tab expansion
and uses literal replacements for its default whitespace table, while preserving custom tables
and mutation behavior. These changes reduce uncached work; a result hit skips it altogether.

## An application cache

`examples/route` compiles rules once and caches each event name's destination. `load()` clears
that cache when rules change. Fnmatch's own pattern cache would still match every event.

Include every input that determines a result in the cache key, and invalidate when external
configuration changes. Prefer immutable cached results: a caller can mutate a cached list and
change subsequent hits. Choose a bound that fits the repeated working set, then inspect
`cache_info()` for hits, misses and evictions. See [functools support](../lib/README.md#functools-pystachys-own)
for the supported signatures and key rules.

## Reproduce the measurements

Run from the repository root, using the same host, inputs and toolchain for each comparison:

```sh
python3 tools/re_bench.py --time --cpu
./pystachy build tools/re_bench.py -o build/re-bench
build/re-bench --time --cpu
python3 tools/textwrap_bench.py --time --cpu
./pystachy build tools/textwrap_bench.py -o build/textwrap-bench
build/textwrap-bench --time --cpu
python3 tools/textwrap_pair_bench.py
./pystachy build tools/textwrap_pair_bench.py -o build/textwrap-pair-bench
build/textwrap-pair-bench
python3 tools/re_cache_bench.py
./pystachy build tools/re_cache_bench.py -o build/re-cache-bench
build/re-cache-bench
```

| Probe | Protocol | Expected checksum |
|---|---|---:|
| `re_bench` | Five-round median; CPU time with `--cpu`, otherwise wall time | `251465` |
| `textwrap_bench` | Same protocol; also 100,000 warmed result-cache hits | `324635` |
| `textwrap_pair_bench` | Nine raw CPU rounds, alternating wrap/fill order on identical paragraphs | `21212190` |
| `re_cache_bench` | CPU-time cache microbenchmarks | `33600000` |

The cached-fill probe warms 200 paragraphs outside timing with `maxsize=256`, then reports
100,000 hits and 200 misses. The fnmatch no-cache row bypasses its wrapper; the regex compile
cache remains active. Interleave CPython and AOT processes and inspect raw rounds: CPU clocks
exclude scheduling waits but do not eliminate shared-host variation.

## Recorded results

Published snapshots, without a new rerun for this guide. [#360](https://github.com/den-run-ai/pystachy/pull/360)
compared an updated AOT build with starting revision `ebb0c54` on a shared x86-64 host,
CPython 3.13.16 and LLVM 18. The regex/textwrap rows are medians of six interleaved process
runs, each taking a five-round median over 200 generated inputs. The replacement row is a
paired cache microbenchmark. The updated build revision was not separately recorded in the table.

| Operation | Starting AOT | Updated AOT | Change within Pystachy |
|---|---:|---:|---:|
| Regex word splitter | 625 µs | 284 µs | About 55% less CPU |
| `wrap` | 520 µs | 258 µs | About 2.0× faster |
| `fill` | 516 µs | 343 µs | About 1.5× faster |
| `shorten` | 519 µs | 216 µs | About 2.4× faster |
| Cached `Match.expand` | 449 ns | 175 ns | About 2.6× faster |

### CPython comparison: provisional samples

[#366](https://github.com/den-run-ai/pystachy/pull/366) records paired measurements at `ab12ee6`
on 2026-10-13: the same 200 deterministic 80-word ASCII paragraphs at width 70, two nine-round
runs per implementation in CPython/AOT/AOT/CPython order. Values are medians of 18 round averages.

| Operation | CPython 3.13.16 | AOT |
|---|---:|---:|
| `wrap`, paired probe | 171 µs | 186 µs |
| `fill`, paired probe | 166 µs | 177 µs |

The paired fill/wrap ratios were 0.984 in CPython and 0.985 in AOT; joining precomputed lines
cost about 0.26 µs in both. The earlier independent-operation fill gap did not persist.
The second operation can reuse the regex decoded-subject cache; alternating order balances
this advantage. These are warmed paired inputs, not cold-input measurements.

Separate-phase samples from the earlier six-run aggregate are retained below. They are not
interchangeable with the paired protocol and do not establish precise small differences.

| Operation | CPython 3.13.16 | AOT |
|---|---:|---:|
| `shorten` | 151 µs | 216 µs |
| `dedent` | 18.7 µs | 26.1 µs |
| `indent` | 3.88 µs | 2.19 µs |
| Warm cached `fill` result hit | 98 ns | 35 ns |
| Warm `fnmatchcase` pattern lookup and match | 329 ns | 338 ns |

Cached fill's roughly 2.8× hit advantage skips wrapping. The ordinary textwrap rows support
no general 2× CPython claim. `make re-probe` checks deterministic matcher work; `make re-fuzz`
checks bytecode and results against CPython. Remaining profiling work is tracked in
[#345](https://github.com/den-run-ai/pystachy/issues/345).
