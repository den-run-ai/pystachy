# route: a log and trace router, with its caches compiled

`route.py` sends each event of a trace or log to the first destination whose rule matches the
event's name, and counts the events per destination: the routing step of a log shipper or a
tracing pipeline, where a few hundred span or event names come back millions of times. It is
ordinary Python, which CPython runs as it is and Pystachy compiles as it is.

- The rules' patterns are fnmatch's, each compiled once as the rules load
  (`re.compile(fnmatch.translate(pattern))`, [`lib/fnmatch`](../../lib/README.md#fnmatch-a-port-of-cpythons)).
- `route()` is an `lru_cache(maxsize=4096)`: an event's destination depends only on its name,
  so a name seen before skips the rules altogether
  ([`lib/functools`](../../lib/README.md#functools-pystachys-own)). A name it has not seen goes
  through the compiled patterns.
- An event's name is its line up to the first tab, found with `line.find("\t")` and sliced off:
  `line.split("\t", 1)[0]` would also make a list and a str of the rest of the line.

```
$ cat rules.txt
auth.*.failed           alerts
*.failed                errors
payments.*              billing
http.request.[45]??     http-errors
...
$ python3 genevents.py 1000000 > events.tsv     # db.search.locked<TAB>1760000000<TAB>4685 ...
$ python3 route.py rules.txt events.tsv          # CPython
$ pystachy build route.py -o route && ./route rules.txt events.tsv
1000000 events, 21 rules
   363895 unrouted
   156197 billing
   121460 errors
   ...
      173 slow-queries
route: CacheInfo(hits=997524, misses=2476, maxsize=4096, currsize=2476)
```

CPython and the executable print the same report, the cache's statistics included. The other
modes are the baselines:
- `--no-cache` routes each event through the compiled patterns again (`route.__wrapped__`);
- `--fnmatch` calls `fnmatchcase()` for each rule, as a program that matches with fnmatch does,
  so each pattern is looked up in fnmatch's own cache of compiled patterns.

Two options change what is measured, not the routing:
- `--names` also counts the distinct names (`1000000 events, 2476 names, 21 rules`). That takes
  memory for each of them. Without it, what the router keeps is bounded by its cache.
- `--in-memory` reads the whole trace first, then reports on stderr how long the routing alone
  took, which separates the cache and the compiled code from reading the input.

## What the cache buys

`bench.py` ran on a 4-core x86-64 VM, against CPython 3.13.16:
- the whole program: the median wall time of 5 runs, with process start-up;
- the routing alone: the median of 5 `--in-memory` runs, per event;
- the peak RSS of one run.

The traces are 1,000,000 events over 2,476 names, and 100,000 events whose names are all new.

| trace | mode | CPython | Pystachy AOT | | routing: CPython | Pystachy AOT | | RSS: CPython | Pystachy AOT |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| names repeat | cached | 0.238 s | 0.165 s | 1.4× | 99 ns | 60 ns | 1.6× | 11.3 MB | 35.6 MB |
| names repeat | `--no-cache` | 1.632 s | 1.596 s | 1.0× | 1,430 ns | 1,976 ns | 0.7× | 10.9 MB | 35.8 MB |
| names repeat | `--fnmatch` | 2.927 s | 1.866 s | 1.6× | 2,650 ns | 2,283 ns | 1.2× | 10.9 MB | 35.6 MB |
| names all new | cached | 0.197 s | 0.207 s | 1.0× | 1,558 ns | 2,027 ns | 0.8× | 11.7 MB | 37.8 MB |
| names all new | `--no-cache` | 0.185 s | 0.189 s | 1.0× | 1,456 ns | 1,873 ns | 0.8× | 10.9 MB | 35.7 MB |
| names all new | `--fnmatch` | 0.318 s | 0.221 s | 1.4× | 2,653 ns | 2,200 ns | 1.2× | 10.9 MB | 35.8 MB |

**The cache is the speedup, compiled or not.** Where names repeat, routing an event takes:
- in CPython, 99 ns from the cache against 1,430 ns through the patterns, 14 times less;
- compiled, 60 ns against 1,976 ns, 33 times less.

Where every name is new, the cache cannot help, and it costs little: a miss, then an eviction
once it holds 4,096 names.

**Compiled, a cached event routes 1.6 times as fast as in CPython; the whole program is 1.4
times as fast.**
- The rest of each event's time is reading its line, about 100 ns compiled and 120 ns in
  CPython, which reads lines in C.
- A cached event takes about 500 instructions (callgrind):
  - a third hashes its name, a new str each time, one multiply per byte (FNV-1a);
  - a third is the dict probe, with its key comparison;
  - most of the rest is the least-recently-used bookkeeping.
- Where events miss, routing is regular-expression matching, where CPython's C engine `_sre`
  beats `lib/re`. So the rows that match every event run at 0.7 to 0.8 times CPython's speed.

**Compiling the patterns once is the other half.** `--fnmatch` pays fnmatch's cache lookup for
each rule tried, in Python code under CPython:
- in CPython, 2,650 ns per event against 1,430 ns for the compiled patterns;
- compiled, 2,283 ns against 1,976 ns.

Before these two changes (fnmatch on misses, `split()` for the name), the cached router took
0.282 s in CPython and 0.180 s compiled.

**Memory stays bounded without `--names`.** The trace of new names peaks where the trace of
repeating names does, since `route()`'s cache stays at its 4,096 names. With `--names`, the dict
of distinct names grows with the trace: the trace of new names then peaks at 23.0 MB in CPython
and 48.8 MB compiled. The executable's peak is about 3 times CPython's, because Pystachy's
collector runs once 32 MiB have been allocated, where CPython frees each line as its last
reference goes.

**Two designs this example does not take:**
- A report of totals alone could count the names first and route each distinct name once,
  without a least-recently-used cache at all. A router that delivers each event as it comes
  needs a decision per event, which is what this example measures.
- Most of these rules are `prefix.*` or `*.suffix`, which `startswith()` and `endswith()` could
  test without a regular expression. That would help exactly the rows where events miss.

Building the executable takes about 3 s, most of it `lib/re` (3,500 lines of the subset).

## Tests

`tests/example_route.py` (`tests/example_route.path` puts this directory on the module path):
- routes a generated trace in-process with `route()` and with `route_fnmatch()`;
- routes names that are all new, each a miss;
- runs `run()` over a trace file in each mode, a last line without a tab included.

It compares the counts and both caches' statistics with CPython's. Its traces are small, since
`make verify` also runs it with a collection at every allocation; `bench.py` routes the million
events, and the trace of new names that fills `route()`'s cache past its 4,096 names.

`bench.py` runs the table above: `python3 -I bench.py ../../pystachy 5`, from anywhere. It
writes its traces and executable to `build/route/`.

For reproducible regex, textwrap and warm result-cache benchmarks, see
[`docs/caching.md`](../../docs/caching.md). It measures cache hits separately from regex work
on misses and documents the current character-class and replacement-template caches.
