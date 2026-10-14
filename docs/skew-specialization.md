# Guarded receiver feedback prototype

This opt-in experiment uses observed receiver classes to specialize a native
caller. It targets a standard-library workload: incremental `html.parser`
parsing with link-extraction and text-extraction callbacks. It is stacked on
[HTMLParser draft #383](https://github.com/den-run-ai/pystachy/pull/383), whose
adaptations and compatibility limits remain unchanged.

## Minimal machinery

`tools/skewprofile.py` records one named function's receiver parameter during a
CPython training run. A function-entry observation represents the context above
its downstream method calls. The collector counts exact classes; unknown types
stay in the denominator. Custom metaclasses are counted as unknown without
calling their attribute/hash hooks. Only the current thread is recorded; at most
64 named classes plus an overflow bucket are retained.

Set `PYSTACHY_SKEW_PROFILE` when compiling through either `build` or `run`. The
compiler chooses one observed class with at least 100 calls and at least 90%
share, then emits a null check and an **exact** existing object-tag check at each
direct call to the selected function. After normal argument/default binding, the
matching branch calls a receiver-specialized caller; misses call the original
native function. Arguments and side effects are evaluated once. A subclass with
its own override misses the exact-class guard.

The existing method/template compiler carries the narrower receiver through the
caller's method chain. Leaf receiver classes avoid the descendant dispatch;
non-leaf classes still retain it. Both AOT and pre-execution JIT compilation use
the same IR. No runtime representation, CPython object bridge or new interpreter
is added. This is offline feedback and guarded caller cloning, not an online
adaptive JIT or an execution-path tracing compiler.

The original body must compile independently. Eligible functions have a typed
return and ordinary typed parameters. This first slice excludes methods,
templates, closures, FFI/export functions, variadic signatures, reassigned or
captured receiver parameters, inferred receiver aliases/containers and covariant
receiver-result contracts. Receiver reads are direct attributes or None tests;
explicit local annotations can preserve result types. Callable adapters keep the
baseline ABI. These restrictions protect the original annotation/inference
contracts rather than making a narrow training sample a new API contract.

Profiles are advisory: symbolic class names are resolved to tags for each build.
Missing, malformed, duplicate, unresolved or ineligible hints are ignored. A
64 KiB input bound and 15-digit decimal counters bound profile parsing; one extra
caller per function and 16 per compilation bound seeded cloning, including
nested requests. Existing global template limits also apply. The limit does not
bound arbitrary function-body size. The recorder prints the source SHA-256 and
Python version for reproducibility; the compiler does not enforce that hash.
Stale profiles still pass normal compilation and runtime guards, but may waste
code space or predict the wrong class. There is no profitability estimator yet.

## Reproduce

Use the project's pinned CPython and LLVM toolchain, then:

```sh
make
python3 tools/skewprofile.py --function parse_documents --parameter parser \
  --output build/html.profile bench/skew_html.py train
./pystachy build bench/skew_html.py -o build/html-baseline
PYSTACHY_SKEW_PROFILE=build/html.profile \
  ./pystachy build bench/skew_html.py -o build/html-profile
./build/html-baseline bench 10000 links
./build/html-profile bench 10000 links
./build/html-baseline static 10000
python3 bench/skew_html.py bench 10000 links
PYSTACHY_SKEW_PROFILE=build/html.profile ./pystachy run bench/skew_html.py check
make skew-check
```

Training deliberately uses 199 `LinkParser` entries and one `TextParser` entry;
99.5% is a controlled fixture, not a claim about real application distributions.
The held-out check alternates both types and then reverses the skew. Checksums
include callback-derived counts, so the same final input position alone cannot
hide an incorrect dispatch. The static control explicitly types the caller's
receiver as `LinkParser`.

## Measurements and validation

Measured on 2026-10-14, a shared x86-64 AMD EPYC 9V74 host, CPython 3.13.16 and
LLVM 18.1.3. Three ASCII HTML documents are fed in fragments, 10,000 repetitions
(30,000 document parses). Timings printed by the workload cover execution inside
the process, excluding compilation/startup. Seven native samples and three
CPython samples were rotated between variants. A separate rotated three-sample
JIT run also excludes compilation/startup from the printed execution time.

| Caller | AOT median (7 samples) | JIT median (3 samples) |
|---|---:|---:|
| Ordinary base-typed | 0.601 s | 0.673 s |
| Profile-specialized | 0.600 s | 0.644 s |
| Statically concrete | 0.596 s | 0.639 s |
| CPython (3 samples) | 0.614 s | — |

There is **no demonstrated execution speedup** here, including over CPython.
The differences are smaller than shared-host variation. The clone proves the
guarded native path and downstream receiver specialization work; it does not
prove useful end-to-end acceleration. Baseline/profile builds took 5.07/5.37 s
in one hosted-frontend sample. Executables were 535,144/539,280 bytes; program IR
was 2,320,258/2,326,375 bytes. Neither build-time sample is a statistical result.

Three-stage compiler (374,522 IR lines) and runtime (10,996 lines) fixed points
match. The full native JIT/AOT corpus passes 2,818 checks with zero failures;
recording verification passes 791 recordings, 34 deviations and nine library
files. Lint passes. The 16-test dedicated suite passes with both compiler hosts and
checks safe profiling, malformed/stale hints, exact subclass/null fallback,
single argument evaluation, return/typing errors, aliases, covariance, nested
clone bounds, exceptions/finally and HTML callback results. It runs with both
compiler hosts, through JIT/AOT; HTML AOT also runs collection at every allocation.
`make skew-check` runs in the benchmark CI group. Full CI status belongs to the
draft PR; local passing checks do not imply CI has finished.

## Research and package choice

[PICs (Hölzle, Chambers and Ungar, 1991)](https://bibliography.selflanguage.org/pics.html)
collect concrete dispatch targets; [type feedback (Hölzle and Ungar, 1994)](https://bibliography.selflanguage.org/type-feedback.html)
feeds observations into guarded optimizations. [Selective Specialization (Dean,
Chambers and Grove, PLDI 1995)](https://projectsweb.cs.washington.edu/research/projects/cecil/www/Papers/specialize-pldi.html)
is the paper at DOI `10.1145/223428.207119`: it motivates selecting profitable
caller specializations instead of cloning everything. [PEP 659](https://peps.python.org/pep-0659/)
provides a modern precedent for guards, fallback and counters for instability.
Those designs inform this prototype; their published speedups are not Pystachy
measurements.

`html.parser` is the strongest immediate stdlib compatibility probe because its
existing #383 port supplies a real shared parser and typed subclass callbacks.
Its current timing is a reason to profile hot operations before expanding this
optimization. BeautifulSoup is a more substantial later application candidate,
but DOM objects, generators, dynamic attributes and heterogeneous containers
remain separate compatibility work; this draft does not port or compile it.
`json` is another broad eventual target, requiring recursive mixed-value storage
and generic operations that exact receiver tags alone do not supply.

Related: [#377 census](https://github.com/den-run-ai/pystachy/pull/377),
[#374 leaf guards](https://github.com/den-run-ai/pystachy/pull/374),
[#375 regions](https://github.com/den-run-ai/pystachy/pull/375),
[#376 scalar executor](https://github.com/den-run-ai/pystachy/pull/376),
[#379 inheritance](https://github.com/den-run-ai/pystachy/pull/379),
[#382 typing prototypes](https://github.com/den-run-ai/pystachy/pull/382),
[#264 annotation experiment](https://github.com/den-run-ai/pystachy/issues/264).
The next step is a measured hot caller from a larger application, then bounded
joint argument signatures/caller-site contexts. Online compilation, shape/version
guards and state reconstruction would be later work.
