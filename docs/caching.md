# Caching text processing

Pystachy's `functools.lru_cache` and `cache` are ordinary subset code. `fnmatch` caches
compiled patterns, `re` caches compiled patterns and replacement templates, and each regex
`Pattern` caches ASCII character-class membership. These caches remove different work:

| cache | a hit skips | lifetime / bound |
|---|---|---|
| `fnmatch._compile_pattern` | glob translation and regex compilation | 32,768 patterns, LRU |
| `re.compile` | parsing and compiling the regex | 512 patterns, FIFO |
| regex replacement template | parsing the replacement and finding its groups | 512 templates, FIFO |
| a `Pattern`'s ASCII classes | interpreting each character-class opcode | 128 entries per used class; owned by the pattern |
| application's `lru_cache` | the entire function body | application's `maxsize` |

Stable module integer constants now become literals in compiled code. The regex matcher's
opcode dispatch becomes LLVM switches rather than a chain of global loads. ASCII class tables
are built on first use without changing regex bytecode; non-ASCII still uses the class evaluator.
Replacement-template cache keys retain the pattern, flags and replacement as a tuple, so a hit
does not format flags or allocate concatenated key strings.

Textwrap recognizes its default whitespace table by contents and uses literal replacements for
controls that occur. Custom tables and mutations still take their own path. Tab-free input skips
tab expansion while retaining its integer-range errors. Fnmatch escapes bracket-class set-operation
characters with literal replacements, preserving the same translated regex and cache statistics.

## Reproduce the measurements

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

The first two tools report five-round median times. `--cpu` measures process CPU time;
omitting it measures wall time. They print checksums, respectively `251465` and `324635`, which
must match CPython. `re_cache_bench` uses CPU time and prints checksum `33600000`.

`textwrap_pair_bench` alternates `wrap` and `fill` on each of the same 200 paragraphs,
changing which runs first on successive inputs and rounds. It prints nine raw rounds of
1,000 calls per operation, their fill/wrap ratios, and the cost of joining precomputed lines.
Its equality checks and warm-up are outside timing; its checksum is `21212190`. Interleave
CPython and AOT process runs too. CPU time removes scheduling waits, but substantial
shared-host variability can remain; compare raw rounds before interpreting ratios.

`textwrap_bench` caches immutable `fill(text, width)` results with `maxsize=256`. It warms the
200-paragraph working set outside the timed region, then performs 100,000 hits, reporting
`CacheInfo(hits=100000, misses=200, maxsize=256, currsize=200)`. Its fnmatch no-cache row bypasses
fnmatch's wrapper; the underlying regex compile cache remains active in both implementations.

Interleaved AOT measurements against the starting `ebb0c54` build, using CPython 3.13.16 and
LLVM 18 on this shared x86-64 host. These gains compare updated Pystachy with older Pystachy:

| operation | starting AOT | updated AOT | change |
|---|---:|---:|---:|
| regex word splitter | 625 µs | 284 µs | about 55% less CPU |
| textwrap `wrap` | 520 µs | 258 µs | about 2.0× faster |
| textwrap `fill` | 516 µs | 343 µs | about 1.5× faster |
| textwrap `shorten` | 519 µs | 216 µs | about 2.4× faster |
| cached `Match.expand` | 449 ns | 175 ns | about 2.6× faster |

The regex/textwrap rows are medians of six interleaved runs; each run takes the tool's median
over 200 generated inputs. The replacement-cache row comes from paired cache microbenchmarks.
Warm cached `fill` measured 35 ns per call, versus CPython's 98 ns, about 2.8× faster. These
absolute CPU times differ substantially from the earlier VM's figures in `lib/README.md`;
use the same host and inputs for a comparison.

### CPython comparison: provisional samples

A paired follow-up on `ab12ee6`, on 2026-10-13, measured `wrap` and `fill` back-to-back,
alternating call order, on the same 200 deterministic 80-word ASCII paragraphs at width 70.
Two nine-round runs per implementation used process CPU time, in order CPython/AOT/AOT/CPython.
These are medians of the 18 round averages. `textwrap_pair_bench` provides the per-process
probe; run CPython/AOT/AOT/CPython to reproduce the comparison protocol:

| operation | CPython 3.13.16 | updated AOT |
|---|---:|---:|
| `wrap` | 171 µs | 186 µs |
| `fill` | 166 µs | 177 µs |

The median of the per-round fill/wrap ratios was 0.984 in CPython and 0.985 in AOT;
joining precomputed wrapped lines took about 0.26 µs in both. `fill` uses the same `wrap`
then one join. The earlier independent-operation sample's 343-versus-258 µs gap did not
persist in this probe. No fill-specific regression was established.

Other observations below come from the earlier six-run aggregate, with the same corpus
but operations timed in separate phases. They are not a single synchronized comparison:

| operation | CPython 3.13.16 | updated AOT |
|---|---:|---:|
| textwrap `shorten` | 151 µs | 216 µs |
| textwrap `dedent` | 18.7 µs | 26.1 µs |
| textwrap `indent` | 3.88 µs | 2.19 µs |
| cached `fill` result hit | 98 ns | 35 ns |
| warm `fnmatchcase` pattern-cache lookup and regex match | 329 ns | 338 ns |

Result-cache hits skip wrapping entirely; fnmatch pattern-cache hits still run the matcher.
These timings varied substantially, even with CPU clocks. They do not establish precise
single-digit differences against CPython, a general 2× advantage, or the original same-host
49 µs regex target in [#345](https://github.com/den-run-ai/pystachy/issues/345).

The deterministic regex work check remains `make re-probe`. For a representative paragraph,
ASCII tables reduce 1,645 class evaluations to 1,152 on first use and zero on warm reuse, across
nine class tables. `make re-fuzz` checks results and bytecode against CPython.

## An application cache

[`examples/route`](../examples/route/README.md) compiles its rules once, then caches a destination
per event name. `load()` clears the result cache when the rules change. This skips every regex
on a repeated name, while fnmatch's own cache would skip only pattern compilation.

Cache results when all inputs determining them are in the key, and clear them when external
configuration changes. Immutable formatting results fit this pattern; returning a cached mutable
list would let callers alter what later hits return. Choose a bound that holds the repeated
working set, and inspect `cache_info()` to distinguish hits, misses and evictions.
