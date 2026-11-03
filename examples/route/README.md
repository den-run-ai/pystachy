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

Cache repeated event names to avoid matching them again. For mostly unique names, compare
`--no-cache`: caching adds lookup and eviction work without avoiding many matches. A totals-only
batch job can count names first and classify each distinct name once; streaming delivery still
needs a decision for each event. Prefix or suffix rules can use string operations to reduce
regex work on misses.

<a id="current-paired-snapshot"></a>

### Paired measurements (2026-10-14)

These measurements use main `1438ac4`'s compiler/runtime/library tree plus the router
validation changes at local measured commit `a12cdd6`. The CPython-hosted compiler builds
AOT with LLVM 18.1.3; compilation is
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
2.959–4.155 s and 2.936–3.344 s respectively. Cached classifications are faster in AOT on
this host; fnmatch whole-program times are approximately equal. New names still pay regex
matching and eviction costs. Measurements from different hosts do not establish a
performance regression.

Streaming RSS is 12.2–12.8 MiB CPython and 34.4–36.3 MiB AOT. AOT's is higher because
collection is deferred, not because of the classification cache, which is bounded at 4,096
names. Keeping distinct names raises unique-trace RSS to 24.1 and 47.8 MiB respectively. Reading the whole trace into
memory is only used for the routing-time column; it is not the streaming memory measurement.

A build by the self-hosted compiler, at local commit `a74efdf` (the source tree of published
`5ec733c1`, [PR #371](https://github.com/den-run-ai/pystachy/pull/371)), gave the same
conclusion in five paired rounds with the same host, CPU, inputs and policies, and every report
agreed. Its [raw measurements](../../docs/benchmarks/route-2026-10-14-a74efdf.json) record the
native compiler's hash and source revision separately from the router harness revision.

<a id="historical-snapshots"></a>
<a id="routing-only-timings-and-memory"></a>

Earlier measurements from [#294](https://github.com/den-run-ai/pystachy/pull/294), on an older
build and another host, are on
[this page as of alpha.4](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/examples/route/README.md#historical-snapshots).

## Tests

`tests/programs/apps/example_route.py` compares routing, file processing, no-tab final lines and cache
statistics with CPython. `tests/programs/apps/example_route_empty.py` checks empty traces in every routing
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
