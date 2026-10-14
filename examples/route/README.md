<a id="route-a-log-and-trace-router-with-its-caches-compiled"></a>

# route: cache event classifications

`route.py` sends each log or trace event to the first matching destination and counts events
per destination. Its Python source runs under CPython and compiles unchanged with Pystachy.
Names often repeat in logging and tracing: caching a classification skips matching on those hits.

## Run

From this directory:

```sh
python3 genevents.py 1000000 > events.tsv
python3 route.py rules.txt events.tsv
../../pystachy build route.py -o route
./route rules.txt events.tsv
```

Each rules line is `PATTERN DESTINATION`, in priority order; `#` starts a comment. Patterns
use case-sensitive fnmatch syntax against the whole event name. Events contain a name followed
by a tab and payload; unmatched names count as `unrouted`. For example:

```text
auth.*.failed          alerts
*.failed               errors
payments.*             billing
http.request.[45]??    http-errors
```

| Mode or option | Behavior |
|---|---|
| Default | `lru_cache(maxsize=4096)` stores each name's classification |
| `--no-cache` | Matches every name against rules precompiled by `load()` |
| `--fnmatch` | Calls `fnmatchcase()` per rule; retains fnmatch's pattern cache |
| `--names` | Also counts distinct names, using memory proportional to their number |
| `--in-memory` | Reads the trace first, then reports routing time separately on stderr |

`load()` clears classifications when rules change. A miss in default mode uses the same
precompiled regexes as `--no-cache`. Both implementations use the same caching policy.

## What the cache buys

### Current paired snapshot

A launch check on **2026-10-14 UTC** uses main `1438ac4`'s compiler/runtime/library tree
plus the router validation changes at local measured commit `a12cdd6`. It includes the regex and caching optimizations
merged since #294. The CPython-hosted compiler builds AOT with LLVM 18.1.3; compilation is
excluded from execution time. The comparison uses CPython 3.13.16, an AMD EPYC 9V74 shared
Linux x86-64 host, one assigned CPU (affinity 8), and five paired rounds that alternate
CPython/AOT order. Both implementations use the same traces and cache policies.
The [raw rounds and provenance](../../docs/benchmarks/route-2026-10-14-a12cdd6.json) include
source/executable/trace hashes, environment, all reports and peak RSS. Every report agrees.

| Trace | Mode | CPython wall | AOT wall | AOT speedup | CPython routing | AOT routing |
|---|---|---:|---:|---:|---:|---:|
| Repeated names | Cached classifications | 0.332 s | 0.185 s | 1.79× | 140 ns | 90 ns |
| Repeated names | `--no-cache` | 2.023 s | 2.903 s | 0.70× | 1,759 ns | 3,796 ns |
| Repeated names | `--fnmatch` | 3.111 s | 3.069 s | 1.01× | 2,895 ns | 3,767 ns |
| Unique names | Cached classifications | 0.212 s | 0.328 s | 0.65× | 1,755 ns | 3,263 ns |
| Unique names | `--no-cache` | 0.218 s | 0.302 s | 0.72× | 1,588 ns | 2,944 ns |
| Unique names | `--fnmatch` | 0.363 s | 0.314 s | 1.15× | 2,835 ns | 3,422 ns |

These are host-specific observations, with substantial variation: cached repeated-name wall
times span 0.299–0.381 s for CPython and 0.165–0.228 s AOT; the fnmatch row spans
2.959–4.155 s and 2.936–3.344 s respectively. This rerun **does not reproduce a 2×
fnmatch whole-program speedup**. Classification-cache hits help both runtimes; new names
still pay regex matching and eviction costs. This host differs from the historical VM, so
the old and new absolute timings alone do not establish a performance regression.

Streaming RSS is 12.2–12.8 MiB CPython and 34.4–36.3 MiB AOT. Keeping distinct names
raises unique-trace RSS to 24.1 and 47.8 MiB respectively. Reading the whole trace into
memory is only used for the routing-time column; it is not the streaming memory measurement.

The two repeated-name headline comparisons were also rerun with the **self-hosted launch
candidate `a74efdf` (local measured commit)**, which includes the import correctness fixes and setup changes from
#369. Five paired rounds use the same host, CPU, inputs and policies; all reports agree.
Its source tree is identical to published [#371](https://github.com/den-run-ai/pystachy/pull/371)
at `5ec733c1`.
Its [raw snapshot](../../docs/benchmarks/route-2026-10-14-a74efdf.json) records the native
compiler's hash and source revision separately from the router harness revision.

| Repeated-name mode | CPython wall | AOT wall | AOT speedup | CPython routing | AOT routing |
|---|---:|---:|---:|---:|---:|
| Cached classifications | 0.309 s | 0.165 s | 1.88× | 130 ns | 69 ns |
| `--fnmatch` | 2.923 s | 3.071 s | 0.95× | 2,804 ns | 3,751 ns |

The launch candidate reproduces the same conclusion: approximately equal fnmatch whole-program
time and faster cached classifications on this host, with slower regex routing on misses.
Its cached wall times span 0.288–0.331 s CPython and 0.161–0.193 s AOT; fnmatch spans
2.867–3.129 s and 2.944–3.182 s respectively. These ranges describe host variability,
not statistical confidence intervals.

### Historical snapshots

Measurements recorded in [#294](https://github.com/den-run-ai/pystachy/pull/294): 4-core x86-64 VM,
CPython 3.13.16, median of five whole-program wall-time runs including startup. AOT compilation
is excluded. Repeating traces contain 1M events over 2,476 names; unique traces contain
100,000 new names. These are published snapshots, without a rerun for this guide.

| Trace | Mode | CPython | Initial AOT | AOT speedup |
|---|---|---:|---:|---:|
| Repeated names | Cached classifications | 0.238 s | 0.165 s | 1.4× |
| Repeated names | `--no-cache` | 1.632 s | 1.596 s | 1.0× |
| Repeated names | `--fnmatch` | 2.927 s | 1.866 s | 1.6× |
| Unique names | Cached classifications | 0.197 s | 0.207 s | 1.0× |
| Unique names | `--no-cache` | 0.185 s | 0.189 s | 1.0× |
| Unique names | `--fnmatch` | 0.318 s | 0.221 s | 1.4× |

A follow-up in #294, tested with main `bbf8959` and the stack-tuple changes in #308/#315,
measured **0.236 s CPython versus 0.158 s AOT** for cached repeated names: about **1.5×**.
Routing alone measured **100 ns versus 55 ns per event**. Other rows stayed within about 6%.
The announcement's rounded fnmatch comparison uses the initial 1.6× row above.

Caching helps both runtimes; it produces the largest improvement when names repeat.
With new names it pays lookup/eviction overhead and still runs regexes. In the initial routing-only
measurements, Pystachy's precompiled-regex misses were slower than CPython's C engine.

<details>
<summary>Historical routing-only timings and memory</summary>

The same initial #294 benchmark used five `--in-memory` runs for routing time and one run
for peak RSS. Its exact tested revision was not recorded separately from the PR's later follow-up.
RSS figures originally labeled MB are MiB (`ru_maxrss` converted from KiB).

| Trace | Mode | CPython routing | AOT routing | CPython RSS | AOT RSS |
|---|---|---:|---:|---:|---:|
| Repeated | Cached | 99 ns | 60 ns | 11.3 MiB | 35.6 MiB |
| Repeated | `--no-cache` | 1,430 ns | 1,976 ns | 10.9 MiB | 35.8 MiB |
| Repeated | `--fnmatch` | 2,650 ns | 2,283 ns | 10.9 MiB | 35.6 MiB |
| Unique | Cached | 1,558 ns | 2,027 ns | 11.7 MiB | 37.8 MiB |
| Unique | `--no-cache` | 1,456 ns | 1,873 ns | 10.9 MiB | 35.7 MiB |
| Unique | `--fnmatch` | 2,653 ns | 2,200 ns | 10.9 MiB | 35.8 MiB |

For repeated names, classifications reduced routing from 1,430 to 99 ns in CPython and
1,976 to 60 ns AOT. Higher AOT RSS reflects deferred collection rather than a larger live
classification cache. The cache is bounded at 4,096 names; adding `--names` makes memory
grow with distinct names (unique trace: 23.0 MiB CPython, 48.8 MiB AOT).

</details>

A totals-only batch job could count names first and classify each distinct name once.
Streaming delivery still needs a decision for each event. Rules restricted to prefixes or
suffixes could also use string operations to reduce regex work on misses.

## Tests

`tests/example_route.py` compares routing, file processing, no-tab final lines and cache
statistics with CPython. `tests/example_route_empty.py` checks empty traces in every routing
mode, including `--in-memory`, which reports zero routing time. Small traces keep per-allocation GC checks practical. The benchmark
covers the full repeated-name trace and enough unique names to exceed the cache bound.

From this directory, reproduce with:

```sh
python3 -I bench.py ../../pystachy 5 --json ../../build/route/results.json
```

The harness writes traces and an executable to `build/route/`, compares every report across
implementations, timing modes and repetitions, and exits unsuccessfully on disagreement.
Runtime order alternates each round. It prints median wall time, routing time and RSS in MiB;
the optional JSON records raw rounds, revision/source hashes, build time and environment.
For regex, textwrap and warm
result-cache probes, see [caching text processing](../../docs/caching.md).
