# Recursive JSON prototype benchmark

`tools/bench_json.py` measures a consumer of parsed API/event records. The same
source uses CPython's standard `json` module and Pystachy's native overlay. It
checks every measured result against CPython before accepting timings. This is
a native JSON baseline, plus an **explicitly hand-written guarded control**;
there is no automatic compiler specialization or runtime profile collection.

```sh
python3.13 tools/bench_json.py --compiler ./pystachy --smoke
python3.13 tools/bench_json.py --compiler ./pystachy --profiles skewed --records 10000
```

With no arguments, `bench/json_records.py` runs a small deterministic consumer
and prints one checksum. `make bench` and the existing verification benchmark
group automatically compare this output under CPython, JIT and AOT. Its embedded
fixture covers every amount alternative, missing fields and nested Unicode;
it prints no timing values. The controller above supplies arguments to select
the full measurement mode.

The controller generates deterministic UTF-8 JSON outside the timed region. All
three profiles include nested objects/arrays, Unicode strings, floats, null,
missing amounts, strings, booleans and container-valued amounts. `skewed` has
92% integer amounts; `mixed` has no integer amounts; `changing` switches from the
skewed distribution to the mixed distribution halfway through the records.
The rare branches contribute to the checksum. Integer sums remain in int64.

Parsing, processing an already parsed document, and parsing plus processing are
timed separately. File I/O, initial validation and printing are excluded from
those timers. Full process wall time includes them, plus JIT compilation where
applicable. AOT build time and executable bytes are separate. The first native
invocation, which can build the shared runtime cache, is retained separately.
An independent native run records `PYSTACHY_GC=stats`; this reports GC and heap
statistics, **not an allocation count**. Linux peak RSS is recorded when GNU
`/usr/bin/time` exists; otherwise that field is null. JIT/build RSS includes the
compiler toolchain, and is not comparable to AOT's runtime-only memory use.

Reports include all raw samples, source/input hashes, revision and dirty-tree
status. Each process is one statistical repetition; its in-process samples are
summarized before computing across-process medians. Execution order rotates.
Use `--processes`, `--samples` and `--iterations` to increase work on an idle
host. `--smoke` checks correctness only; its times establish no speedup. Do not
run performance measurements alongside builds or broad verification.

The source guard tests a value before taking an integer path and falls back for
every other alternative. It does not copy data or assume a persistent schema.
LLVM may already optimize generic dispatch similarly, so no benefit is promised.
An adaptive compiler would additionally need profile collection, caller cloning,
representation guards, version limits and its own build/startup accounting.
