# Recursive JSON prototype benchmark

`tools/bench_json.py` measures a consumer of parsed API/event records. The same
source uses each interpreter's standard `json` module and Pystachy's native
overlay. It checks every measured result against pinned CPython before accepting
timings. This is a native JSON baseline, plus an **explicitly hand-written guarded
control**; there is no automatic compiler specialization or runtime profile collection.

```sh
python3.13 tools/bench_json.py --compiler ./pystachy --smoke
python3.13 tools/bench_json.py --compiler ./pystachy --profiles skewed --records 10000
python3.13 tools/bench_json.py --compiler ./pystachy --pypy /path/to/pypy3 \
  --modes cpython pypy jit aot cpython-lib pypy-lib --texts utf8 ascii escaped
```

With no arguments, `bench/json_records.py` runs a small deterministic consumer
and prints one checksum. `make bench` and the existing verification benchmark
group automatically compare this output under CPython, JIT and AOT. Its embedded
fixture covers every amount alternative, missing fields and nested Unicode;
it prints no timing values. The controller above supplies arguments to select
the full measurement mode.

## Runtimes

| Mode | Decoder | Executes the consumer with |
|---|---|---|
| `cpython` | CPython's standard `json` (C scanner) | CPython's interpreter |
| `pypy` | PyPy's standard `json` | PyPy's tracing JIT |
| `jit`, `aot` | `json.py` that Pystachy resolves (normally `lib/json.py`) | Pystachy's JIT or native executable |
| `cpython-lib`, `pypy-lib` | the same `json.py` source | CPython's interpreter or PyPy's JIT |

The `-lib` modes compare three ways of executing one parser source. PyPy 3.11
lacks the PEP 695 `type` statement, so its copy names `JSONValue` with a plain
assignment; nothing else changes. Before measuring, the controller checks which
`json` each interpreter mode imports with `bench/` first on its module path, as
the measured runs have it: the standard library's for `cpython` and `pypy`, the
copy for the `-lib` modes. The report records those paths. The controller must
run on the pinned CPython, which provides every reference checksum; it records
the implementation, version and binary hash of each interpreter (`--pypy`
defaults to `pypy3` on `PATH`). It also records the path and hash of the
`json.py` that the compiler resolves, following the compiler's own search:
`PYSTACHY_PATH` (relative entries from the repository root, the compiler's
working directory), then `lib/` of `PYSTACHY_HOME` or of the compiler's checkout.
To compare parser revisions with one compiler binary, put a directory holding
the other `json.py` on `PYSTACHY_PATH`.

## Inputs and phases

The controller generates deterministic JSON outside the timed region. All
three profiles include nested objects/arrays, Unicode strings, floats, null,
missing amounts, strings, booleans and container-valued amounts. `skewed` has
92% integer amounts; `mixed` has no integer amounts; `changing` switches from the
skewed distribution to the mixed distribution halfway through the records.
The rare branches contribute to the checksum. Integer sums remain in int64.
`--texts` selects how the records are written: `utf8` keeps non-ASCII text raw,
`escaped` writes the same values as `\u` escapes, and `ascii` replaces each
non-ASCII character with one ASCII character, which keeps string lengths and so
the processing checksum.

The `all` phase times parsing, processing an already parsed document, and
parsing plus processing, separately. A `predecoded` run decodes once outside the
timed region and then times processing alone, without parser allocations or
garbage in the heap: the part of the workload that type specialization would
change. It also times `rebuild()`, which copies the decoded lists and dicts,
iterating their items, around the same scalars and strings. Any decoder that produces these native
values, including one for a binary format, at least allocates and fills those
containers, so the parse time minus the rebuild time bounds what a faster input
format could save. That bound holds for compiled code; on CPython, `rebuild()`
runs in the interpreter and does not bound its C decoder. The run also times
`json.dumps()` of the decoded document with the default options (`encode`); it
checks that the text decodes to the same checksum, and the controller that the
text has the length of CPython's.

Each process first runs its measured operations for `--warmup-ms` (default
2000 ms, and at least once); samples exclude that time, and the report keeps the
number of warmup rounds. PyPy's JIT compiles during warmup, while Pystachy's JIT
compiles before the program starts. File I/O, initial validation and printing are
excluded from the timers. Full process wall time includes them, the warmup, and
JIT compilation where applicable. AOT build time and executable bytes are
separate. The first native invocation, which can build the shared runtime cache,
is retained separately. An independent native run records `PYSTACHY_GC=stats`;
this reports GC and heap statistics, **not an allocation count**. Linux peak RSS
is recorded when GNU `/usr/bin/time` exists; otherwise that field is null.
JIT/build RSS includes the compiler toolchain, and is not comparable to AOT's
runtime-only memory use.

## Evidence

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
PyPy's tracing JIT already specializes the generic consumer on the types it
observes, so its generic/guarded and skewed/mixed/changing differences are a
reference point for what runtime specialization changes in this workload.
