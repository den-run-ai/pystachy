# Follow-up on current main (2026-11-12)

Remeasured at `main` `8434a911` (alpha.6 feature freeze, 16 commits after
v0.4.0-alpha.5, including bounded `match` from #1272) with the parent report's method,
inputs and machine. Raw evaluation for a research branch; not for merging. Prepared with
Claude Code assistance at the repository owner's request.

## Surface per release

| Release | Methods passing (of 5,905) | Language and builtins (of 2,445) | nbody AOT build | Bootstrap |
|---|---:|---:|---:|---:|
| v0.1.0-alpha.1 | 168 | 103 | 0.55 s | 74 s |
| v0.1.0-alpha.2 | 371 | 211 | 0.68 s | 164 s |
| v0.1.0-alpha.3 | 372 | 212 | 0.74 s | 237 s |
| v0.1.0-alpha.4 | 378 | 218 | 0.94 s | 219 s |
| v0.2.0 | 396 | 218 | 1.15 s | 232 s |
| v0.3.0 | 397 | 218 | 1.16 s | 245 s |
| v0.4.0-alpha.2 | 397 | 218 | 1.08 s | 255 s |
| v0.4.0-alpha.5 | 397 | 218 | 1.13 s | 246 s |
| main `8434a911` | 492 | 310 | 1.02 s | 239 s |

The sample measured eight of the fifteen release tags; the other seven fall between measured
samples. The eleven tags after v0.1.0-alpha.4 (2 Nov) up to v0.4.0-alpha.5 (11 Nov) span 19
more passing methods and no language or builtins method. On main,
bounded `match` adds 92 `test_patma` methods and three `test_statistics` methods pass; no
method that passed at alpha.5 fails. 24 methods compile but differ (16 at alpha.5): the eight
new ones are `test_patma` functions that end after an unmatched `match` and raise
`RuntimeError` instead of returning `None`, the documented missing-return deviation
(`tests/deviations/return_missing_value.py`). The upstream pyperformance census is still 7 of
52. All 31 timing workloads match CPython in AOT and JIT (`raw/perfprep-8434a911.json`).

## What the rejected methods need

First errors of the 5,389 rejected methods on main, grouped by `scripts/groups.py`
(`raw/groups-8434a911.txt`; only the first error of each method is visible):

| Need | Methods | Largest rows |
|---|---:|---|
| A missing module or name | 2,260 | other modules 1,179 (configparser, decimal, `_pyio`, locale, pprint, queue, calendar, array); `enum.member`/`verify` 885 (all of `test_enum`); `gc` 142; `inspect` 54 |
| Class-model, inference or `match` work a static compiler can do | 1,710 | field/class-attribute types 688; classes inside functions 365; builtin bases 178; class-body statements 164; empty containers 96; generic-template bases 91; `match` patterns 88; multiple inheritance 40 |
| Runtime reflection or dynamic semantics | 475 | `pickle`/`copyreg`/`marshal` 247; modules or classes as values 73; `eval`/`exec`/`compile`, `ast`, `dis` 58; computed `str.format` 49; exception attributes 48 |
| Unassigned | 944 | value-type mismatches, missing methods and calls |

Classes inside functions (`scripts/local_classes.py`, `raw/local-classes-8434a911.txt`): 361
of the 365 methods have extracted programs; they define 627 local classes, of which 101 read a
variable of an enclosing function (`.type_params`, `__class__` for `super()`, sibling local
classes, locals). In 281 methods no local class captures anything.

Blocked tests mostly use small parts of the reflective modules: `gc.collect` (141 of 142
methods), `gc.is_tracked` (91), `gc.get_threshold`/`set_threshold` (38); `inspect.cleandoc`
(44 of 54); `pickle.dumps`/`loads` round trips (235 of 240). The upstream `gc_collect` and
`gc_traversal` benchmarks use only `gc.collect`.

Dynamic `Any` opt-in on main (`raw/methods-8434a911-dynamic-any.json.gz`, every program
prefixed with `# pystachy: dynamic-any`): 492 pass as without it. Seven rejected methods
pass and seven passing methods are rejected: two `:=` targets read after a comprehension
(`test_named_expressions`), `math.isfinite`/`isnan`/`fsum` of `Any` values (`test_random`,
`test_statistics`) and star-unpacking an `Any` into a call (`test_colorsys`). Five rejected
methods compile but differ: two treat dict views as lists (the documented view deviation,
#989) and three raise `NotImplementedError` at run time.

## What removing one blocker unlocks

First errors overstate what one feature unlocks: the next error is often another missing
feature (`raw/probes-8434a911.txt`). Measured conversions so far:

| Probe | Methods probed | Then pass | Most common next error |
|---|---:|---:|---|
| Bounded `match` (#1272), methods rejected for `match` at alpha.5 | 216 | 92 | starred sequence patterns 32, mapping patterns 27, class patterns 12, list subjects 7 |
| CPython's pure-Python stdlib on the path (parent report) | 2,429 | 0 | missing C modules, dynamic code in the stdlib |
| Local classes that capture nothing moved to module scope (`scripts/hoist_probe.py`) | 218 | 23 | builtin bases 33, async functions 11 |
| `gc` stand-in (`scripts/probe_gc.py`) | 141 | 11 | local classes 51 |
| `inspect.cleandoc` (`scripts/probe_inspect.py`) | 52 | 0 | `compile(str, str, str)` 44 |

For the hoisting probe, 113 of the 365 methods were skipped (a capturing local class, a name
clash) and 34 changed CPython's own output once hoisted; the 218 rest kept CPython's result.
With the `gc` stand-in, the upstream `gc_collect` benchmark compiles but fails its own check
that `gc.collect()` returns `None` or at least the number of objects in the cycles it made;
`gc_traversal` next needs an annotation for an empty list.

## Regressions reproduced on main

AOT, 15 interleaved repetitions pinned to one CPU of an idle 4-vCPU x86-64 VM, medians
(`raw/retime-*.json`, `scripts/retime.py`):

| Benchmark | Before | Introduced | v0.4.0-alpha.5 | main `8434a911` | CPython 3.13.18 |
|---|---:|---:|---:|---:|---:|
| `float` (pyperformance port, timed region) | 32.92 ms at `0ec827ac` | 43.62 ms at #1268 `b40ee875` | 44.02 ms | 45.11 ms (+37%) | 508.7 ms |
| `words` (`bench/words.py`, process) | 58.23 ms at `6d4ed3d1` | 73.30 ms at #667 `a355c83f` | 71.76 ms | 71.19 ms (+22%) | 179.2 ms |

`float`: instructions changed by 1.4% (350.3M to 355.3M); page faults and peak RSS are
equal. #1268's listguard versions `for i in range(n): points[i] = Point(i)` into checked and
unchecked loops, so `Point.__init__` gains a second call site and LLVM stops inlining it into
`main` (`raw/callgrind-summaries.txt`). With the compiler before #1268, adding one
never-executed second `Point(0)` call alone gives the same out-of-line constructor and
34.06 ms to 44.76 ms (`raw/float-call-sites.txt`).

`words`: instructions rose from 433M to 617M at #667 and are 539M on main.
`w.upper().startswith("L")` runs `pys_text_startswith` 400,000 times, and each call counts
the code points of its fresh receiver through `text_bounds` and `pys_text_len` (64M
instructions inclusive on main). Marking (`scan`) grew from 0.8M to 37.8M instructions; with
`PYSTACHY_GC=stats` the heap peak grew from 34.9 to 59.1 MiB and collections from one
(0.8 ms) to two (5.0 ms) (`raw/words-gc-stats.txt`).

Neither benchmark is in the Performance smoke workflow's eleven workloads.

## Paired timing of alpha.5 and main

`raw/timing-paired-a5-main.json.gz` times alpha.5 and main together with CPython (7 runs per
port, 9 per microbenchmark, the parent report's method). Main's indices were 0.986 times
alpha.5's for the core ports (11.14 against 11.29) and 1.004 times for the microbenchmarks (18.60
against 18.52). The same alpha.5 build measured 5% lower on the core index than in the history
run, and single ports up to 40% slower (raytrace), so main is compared with alpha.5 only within
this run. `barnes_hut` alternates between about 14 ms and 25-28 ms per run; 15 interleaved runs
(`raw/retime-barnes_hut.json`) give medians of 14.42-14.48 ms for Nov 10, alpha.5 and main.

## Compile cost

`pystachy ir bench/nbody.py` takes 5-15 ms at the first sample, alpha.2 and main; its IR
shrank from 946 to 842 lines. `pystachy build` of the same file, pinned to one CPU, took 0.34 s,
0.75 s and 1.19-1.37 s (`raw/aot-build-split.txt`): the growth is after the frontend, in optimizing
and linking the runtime, as #706 describes. The compiler's bootstrap on main took 239 s for
912,733 lines of compiler IR (`raw/build-8434a911.json`).
