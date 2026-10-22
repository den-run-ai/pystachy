# Caching text processing

Cache the work that repeats: compiling a pattern, parsing a replacement, or computing a
complete result. Pystachy's `cache` and `lru_cache` are written in the supported subset.
The [router example](../examples/route/README.md) shows an application result cache.

| Cache | A hit skips | Bound |
|---|---|---|
| `fnmatch._compile_pattern` | Glob translation and regex compilation | 32,768 patterns, LRU |
| `re.compile` | Regex parsing and compilation | 512 patterns; 256-entry FIFO front, recency refresh on front misses |
| Regex replacement template | Replacement parsing and group resolution | 512 templates; same two-level policy |
| Pattern class tables | Character-class opcode interpretation | 131 entries per used class (+128 for a memo), owned by pattern |
| Pattern search strategy | Choosing what a search may skip by, and testing alternatives' leading items per character | 5 entries per pattern, 134 for alternatives with a bit-parallel filter (+128 for a memo and 1 per item where an item may match a character from U+0080), found at its first search |
| Regex case-mapping memo | Searching the Unicode case tables | 256 recent code points per mapping, process-wide |
| Regex decoded subject | Decoding the same non-ASCII string object again (an ASCII one is read in place) | Last subject only |
| Application `lru_cache` | Entire function body | Chosen `maxsize` |

The regex front caches reference entries in their larger caches; they do not compile extra
patterns or templates. Repeated front hits only read the cache, and `re.purge()` clears both levels.

Class tables are built lazily. They handle ASCII characters directly. For non-ASCII characters,
they handle classes whose members form one range, match no code points or match every code
point directly; other classes use an evaluator and cache its recent answers. Textwrap skips unnecessary tab expansion and uses literal
replacements for its default whitespace table, while preserving custom tables and mutation
behavior. These optimizations reduce uncached work; a result-cache hit skips it altogether.

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

The measurements below compare warmed operations with CPython. They describe the recorded
builds and inputs; use the commands above to measure your own workload.

### CPython comparison: provisional samples

The [paired textwrap benchmark](https://github.com/den-run-ai/pystachy/pull/366), recorded at
`ab12ee6` on 2026-10-13, uses 200 deterministic 80-word ASCII paragraphs at width 70. Each
implementation runs twice for nine rounds, in CPython/AOT/AOT/CPython order. Values are medians
of 18 round averages.

| Operation | CPython 3.13.16 | AOT |
|---|---:|---:|
| `wrap`, paired probe | 171 µs | 186 µs |
| `fill`, paired probe | 166 µs | 177 µs |

The second operation can reuse the regex decoded-subject cache; alternating order balances
this advantage. These measurements exclude cold-input costs.

The following [separate-operation measurements](https://github.com/den-run-ai/pystachy/pull/360)
use a different protocol: six interleaved processes, each taking a five-round median on a
shared x86-64 host with CPython 3.13.16 and LLVM 18. The exact updated compiler revision was
not recorded. These samples are not directly comparable to the paired table above, and small
timing differences are inconclusive.

| Operation | CPython 3.13.16 | AOT |
|---|---:|---:|
| `shorten` | 151 µs | 216 µs |
| `dedent` | 18.7 µs | 26.1 µs |
| `indent` | 3.88 µs | 2.19 µs |
| Warm cached `fill` result hit | 98 ns | 35 ns |
| Warm `fnmatchcase` pattern lookup and match | 329 ns | 338 ns |

The cached `fill` result hit skips wrapping entirely. Measure cache hits and misses separately
when deciding whether a cache helps your application. `make re-probe` checks deterministic
matcher work; `make re-fuzz` checks bytecode and results against CPython.
