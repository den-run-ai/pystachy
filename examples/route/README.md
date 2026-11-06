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
<a id="paired-measurements-2026-10-14"></a>
<a id="historical-snapshots"></a>
<a id="routing-only-timings-and-memory"></a>

## Recorded benchmarks

The 2026-10-14 comparison covered repeated and unique names in all three modes,
using five alternating CPython/AOT rounds on one CPU of a shared host, with
LLVM 18.1.3 and CPython 3.13.16. It recorded streaming process time and RSS
separately from routing time after loading a trace into memory.

The [hosted-compiler results](../../docs/benchmarks/route-2026-10-14-a12cdd6.json)
use compiler/runtime/library source from `1438ac4` plus the router validation
changes at `a12cdd6`. The
[self-hosted results](../../docs/benchmarks/route-2026-10-14-a74efdf.json)
use the source tree published as `5ec733c1` in
[PR #371](https://github.com/den-run-ai/pystachy/pull/371). Both files retain
raw rounds, hashes, environment and reports.

The [full table and analysis](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/route/README.md#current-paired-snapshot)
and [earlier snapshots](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/examples/route/README.md#historical-snapshots)
remain available in history. Rerun the command below for a current build; see the
[benchmark guidance](../README.md#benchmarks) when comparing revisions.

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
