# route: a log and trace router, with its caches compiled

`route.py` sends each event of a trace or log to the first destination whose rule matches the
event's name, and counts the events per destination: the routing step of a log shipper or a
tracing pipeline, where a few hundred span or event names come back millions of times. It is
ordinary Python, which CPython runs as it is and Pystachy compiles as it is, and it shows the two
caches of the standard library that a program like it leans on:

- `fnmatch` keeps each rule's compiled regular expression (`_compile_pattern()`, an
  `lru_cache(maxsize=32768)`), so a pattern is compiled once however many events it is matched
  against ([`lib/fnmatch`](../../lib/README.md#fnmatch-a-port-of-cpythons));
- `route()` is an `lru_cache(maxsize=4096)` of its own: an event's destination depends only on
  its name, so a name seen before skips the rules altogether
  ([`lib/functools`](../../lib/README.md#functools-pystachys-own)).

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
1000000 events, 2476 names, 21 rules
   363895 unrouted
   156197 billing
   121460 errors
   ...
      173 slow-queries
route: CacheInfo(hits=997524, misses=2476, maxsize=4096, currsize=2476)
patterns: CacheInfo(hits=34746, misses=21, maxsize=32768, currsize=21)
```

CPython and the executable print the same report, the caches' statistics included.

`--no-cache` routes each event again (`route.__wrapped__`, so fnmatch's cache still compiles each
pattern once), and `--precompiled` compiles each rule's pattern itself, once, and matches without
fnmatch: the baseline of a program that knows its patterns are fixed.

## What the caches buy

`bench.py`, on a 4-core x86-64 VM: median wall time of 5 runs with process start-up, peak RSS of
one, a trace of 1,000,000 events over 2,476 names and one of 100,000 events whose names are all
new. Pystachy as the caching PRs leave it (#265 to #269), and with the two runtime PRs that this
router's profile led to, #267 (tuple keys hashed in place) and #270 (readline):

| trace | mode | CPython 3.13.16 | Pystachy AOT | with #267, #270 | CPython RSS | AOT RSS |
|---|---|---:|---:|---:|---:|---:|
| names repeat | cached | 0.277 s | 0.242 s | 0.172 s | 10.8 MB | 35.9 MB |
| names repeat | `--no-cache` | 2.976 s | 1.981 s | 1.925 s | 10.9 MB | 35.9 MB |
| names repeat | `--precompiled` | 1.613 s | 1.756 s | 1.681 s | 10.9 MB | 36.1 MB |
| names all new | cached | 0.343 s | 0.266 s | 0.253 s | 22.2 MB | 48.8 MB |
| names all new | `--no-cache` | 0.334 s | 0.246 s | 0.248 s | 21.8 MB | 47.8 MB |
| names all new | `--precompiled` | 0.196 s | 0.222 s | 0.222 s | 21.8 MB | 48.8 MB |

- **The cache is the speedup**, compiled or not: where names repeat, `route()`'s cache routes a
  million events in a tenth of the time it takes to route each again (CPython 2.98 s to 0.28 s;
  Pystachy 1.98 s to 0.24 s, or 0.17 s), and in a sixth of the time of precompiled patterns.
  Where names are all new it cannot help, and costs little: a miss, an eviction past 4,096 names.
- **Compiled, the router is 1.1 to 1.6 times as fast as CPython, not more.** What is left per
  event once its name is cached is a line read, a split and two dict operations, which CPython
  does in C too; #270 made Pystachy's line reading faster than CPython's. A miss matches regular
  expressions, where CPython's C engine `_sre` is about 1.6 times faster than `lib/re`: so the
  modes that match every event (`--precompiled`, and new names) run at CPython's speed or a
  little slower, and `--no-cache` gains from fnmatch's cache lookups being cheaper compiled.
- **Memory stays bounded**, but the executable's peak is about 3 times CPython's: Pystachy's
  collector runs when its heap has grown, where CPython frees each line as its last reference
  goes. The trace of new names peaks higher in both because `route.py` counts the distinct names
  in a dict of its own; `route()`'s cache stays at its 4,096 names.
- Building the executable takes 3 to 5 s, most of it `lib/re` (3,500 lines of the subset).

## Tests

`tests/example_route.py` routes a generated trace in-process, then one whose names are all new,
which pushes `route()`'s cache past its 4,096 names, and compares the counts and both caches'
statistics with CPython's (`tests/example_route.path` puts this directory on the module path).
`bench.py` runs the table above: `python3 -I bench.py ../../pystachy 5`, from anywhere; it
writes its traces and executable to `build/route/`.
