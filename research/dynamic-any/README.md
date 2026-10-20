# Dynamic `Any`: where it pays off today (research record, 2026-10-20)

Raw evaluation records for the question "what are good uses of the dynamic `Any` that #761
merged?". Everything here was measured at main **`ad19255e`** (the merge of #771), built with
`make PY=python3.13` (fixed point: 707,289 lines of compiler IR, 18,709 of runtime IR), with
CPython 3.13.16, clang/LLVM 18.1.3, on a shared 4-vCPU Linux container. The 37 existing
`dynany_*` cases passed first (65 checks, JIT and AOT). These are research records, not a
proposed change: nothing here edits the compiler, the runtime or `lib/`.

## Summary

1. **Ordinary heterogeneous-data code is the use that works now.** Of 60 small probes of
   everyday idioms, 34 match CPython in both JIT and AOT with `# pystachy: dynamic-any`, against
   15 without it: 25 compile only with the comment (records built from displays, dispatch tables
   of different functions, `object()` sentinels, functions returning several types, small
   interpreters, rule and query evaluators, recursive document walkers, `**kwargs: Any` bags,
   dataclass `Any` fields, csv rows of mixed values, hand-written JSON encoders).
2. **CPython 3.13.16's `tomllib` runs natively with 14 kinds of small edits** and matches
   CPython on all 62 files of CPython's own `tomllib` compliance corpus, datetime values, error
   messages and a real `pyproject.toml`, in JIT and AOT. Six of the edit kinds are dynamic-`Any`
   gaps the compiler could close; eight are general gaps. AOT parses a 526 KB document 2.0× as
   fast as CPython runs the same source, at 2.5× CPython's peak RSS.
3. **Upstream tomli-w 1.2.0 serializes mixed documents with 7 kinds of edits** (+19/−20 lines), and
   `tomllib.loads()` → edit → `tomli_w.dumps()` → `loads()` round-trips. But the shipped port's
   three differential tests then stop compiling: a typed `dict[str, str]` cannot become an `Any`
   value. Replacing the port with this copy would reject programs that compile today (#409).
4. **Dynamic `Any` is not what blocks PyPI packages.** For nine JSON/data packages (jmespath,
   jsonpointer, dictdiffer, mergedeep, toolz, flatten-json, tabulate, json-logic, tomli-w), the
   first blocker is the same with and without the comment, and none is an `Any` gap. Injecting the
   comment into all 519 stdlib modules changes one import result (`xml.etree.ElementPath`, a dict
   of different functions: 149 → 150) and breaks none.
5. **Generic `Any` code is slower than CPython where the hot loop is `Any` traffic.** An
   agent-transcript analytics pipeline (100,000 mixed JSONL events, a handler registry, session
   objects, aggregation) matches CPython byte for byte, also with a collection at every
   allocation, but AOT processing takes 1.6× CPython's time (165 ms against 101 ms; decoding is
   1.6× faster). Callgrind: `Any`-keyed dict lookups and hashing are about half of the processing
   instructions, box allocation and the collector a quarter, the dispatchers and boxing about
   10%. A 6-line runtime fast path for two boxed `str` keys removes 16% of the instructions.

## Method

- `tools/probe.py` runs each probe under CPython 3.13.16 (`-I`; module path appended after the
  standard library, so a probe never shadows it) and under `pystachy run` and `pystachy build`,
  and compares stdout and exit status. A probe "passes" only if both modes match. `--cpath` gives
  CPython the pristine upstream package while Pystachy compiles the edited copy. `--keep
  PYSTACHY_GC_STRESS_PROGRAM` passes the program GC-stress setting on; an AOT program gets it as
  `PYSTACHY_GC_STRESS` at run time, as `tests/run.sh`'s `XENV` does.
- `tools/mkdyn.py DST SRC...` copies modules or packages with the comment as their first line.
- The "without" variant of every idiom probe is the same file without the comment.
- Upstream code: wheels from PyPI (no build step runs), each extracted into its own directory;
  CPython's `Lib/` from the pinned interpreter (`/usr/lib/python3.13`, identical to the
  `Python-3.13.16.tgz` source for `tomllib`), behind `tools/import_sweep.py --overlay`'s directory
  of links (which leaves out the modules that `lib/` provides).
- Edits to upstream code are marked `# EDIT n` and kept as diffs in `patches/`.
- Timings: interleaved processes pinned to one core (`taskset -c 1`), medians of per-process
  medians, nothing else running; differences under about 20% are noise on this host.

## 1. Everyday idioms (`probes/idioms/`)

| With the comment | Without | Probes |
|---|---|---|
| pass | fail | 25: `a01` record display, `a08`/`a09` dispatch tables of different functions (annotated, lambdas), `a11` `object()` sentinel, `a13` stack interpreter, `a14` mixed tuples, `a15` `isinstance(x, (int, float))`, `a20` dataclass `Any` field, `a21` recursive document walk, `a22` flatten to dotted keys, `a24` `reduce(operator.getitem, ...)`, `a25` `**kwargs: Any`, `a27` generator of `Any`, `a28` `%`/`format`/f-string specs, `a29` `csv.DictWriter` of mixed rows, `a30` mostly-int amounts, `b01` `JSONValue` ↔ `Any` copy, `b02`/`b03` JSON encoders (annotated, unannotated #485 08e), `b09b` JSON-Logic evaluator, `b10` JMESPath-like query evaluator, `b14` `set[Any]`, `b16` sort by mixed tuple keys, `b17` `zip`/`enumerate`/dict comprehension, `b21` empty displays in a top-level display |
| pass | pass | 9: `a02`, `a10`, `a12`, `a26`, `b05` `heapq`, `b06` `re`, `b07` `string.Template`, `b08b` `str.format(**rec)`, `b26` an `Any` parameter narrowed before `textwrap` |
| fail | pass | 6 (opting in rejects them; without the comment `Any` is inferred): `a16` `type(v) is int`, `b04`/`b22` an `Any` str reaching `textwrap` (`ord(dyn)`), `b13` keyword argument in a method call of an `Any` value, `b18` slicing, `b23` `statistics.fmean(list[Any])` (`math.fsum(list[dyn])`) |
| fail | fail | 20: see the gaps below; `b11` classes as values (#7), `b12` `getattr` by run-time name (#489), `b08` `%` with a mapping, `c01`/`c02` `tuple[str, ...] + tuple[str, ...]` are not `Any` gaps |

## 2. Gaps, by how much they block (minimal repros in `probes/`)

| # | Gap | Repro | Seen in |
|---|---|---|---|
| G1 | A typed container never becomes an `Any` value: `dict[str, Any]`, the usual spelling for records, cannot be returned as `Any`; a local that holds a homogeneous display (`doc = {"x": 1}`) cannot be passed to an `Any` parameter; a typed local cannot widen when a later store gives it an `Any` | `a23`, `tomliw_tests/t_unannotated.py`, `t_typed_local.py` | `tomllib` (`NestedDict.dict`, `Flags._flags`), tomli-w's `Mapping[str, Any]` parameters, the port's tests |
| G2 | No element-wise conversion between tuples and tuples with `Any` items: `tuple[int, str]` returned as `tuple[int, Any]`, `tuple[Any, Any, bool]` stored as `tuple[str, Any, bool]` | (`tomllib`'s `parse_value`, 13 returns) | `tomllib`, tomli-w |
| G3 | `object`, bare `Mapping`, `Mapping[str, Any]`, `tuple \| list` annotations are not `Any` in a module that opts in | `a03`, `b20` (#713, #597) | tomli-w (5 annotations) |
| G4 | `isinstance(x, Mapping)` (any `collections.abc` class) of an `Any` value | (tomli-w) | tomli-w; jsonpointer, dictdiffer, mergedeep use the same tests |
| G5 | An empty display that `Any` storage receives: `cont[k] = {}`, `[]` in a record inside a list (`b24`, `b25`), `empty = {}` passed as `Any`, `set()` in a display | `b24`, `b25` | `tomllib` (3 sites) |
| G6 | Missing operations on `Any` values: slicing, `round`/`abs`/`ord`/`chr`/`divmod`, `sum()` of a `list[dyn]` or generator, `dict.update()` of a display, `type(x) is int`, keyword arguments | `a07`, `a16`, `a17`, `a18`, `b13`, `b18`, `b19` | the pipeline (W1 slicing, W2 `round`) |
| G7 | `json.loads()` gives `JSONValue` storage that cannot become `Any`; `json.dumps()` does not take `Any` | `a04`, `a05`; `b01` is the working copy | the pipeline's `to_any`/`to_json` (about a fifth of its decoding instructions) |
| G8 | `set` values (and empty `set()`) in `Any` storage | (`tomllib`'s flags) | `tomllib` |
| G9 | Storage given two incompatible concrete values (two functions) does not widen to `Any` in a module that opts in (#8) | (`tomllib`'s `parse_escapes`) | `tomllib`; `xml.etree.ElementPath` widens only because its display is mixed |
| G10 | Library templates instantiated for `dyn` hit builtins that `Any` lacks; module-level variables are not narrowed by `isinstance` | `b04`, `b22`, `b23`, `b26` (works in a function) | `textwrap`, `statistics` |

## 3. `tomllib` (`patches/tomllib-3.13.16.diff`)

Edits, in the order the blockers appeared (`dyn-tomllib/` = the unchanged module with the comment):

| Edit | Blocker | Kind |
|---|---|---|
| 1 | `types.MappingProxyType` | general (`types` subset) |
| 2 | `TOMLDecodeError.__module__ = __name__` (class attribute assigned outside the class) | general |
| 3 | `set[tuple[tuple[str, ...], int]]` elements | general (hashing) |
| 4 | `tuple[str, ...] + tuple[str, ...]` (4 sites; `list.extend(tuple)` too) | general |
| 5 | a local given two different functions | `Any` (G9) / #8 |
| 6 | `tuple[Pos, str]` returned as `tuple[Pos, Any]` (13 returns) | `Any` (G2) |
| 7 | `dict[str, Any]` cannot become `Any` (5 annotations) | `Any` (G1) |
| 8 | `re.Match[str]` annotation | general |
| 9 | `datetime \| date` return (overlapping class families) | general |
| 10 | `str \| None` regex groups passed as `str` | general (strict `Optional`) |
| 11 | `match.group()` typed `str \| None` | general (`lib/re` precision) |
| 12 | a typed local later given an `Any` value | `Any` (G1) |
| 13 | `set()` in `Any` storage | `Any` (G5, G8) |
| 14 | `{}`/`[{}]` stored into `Any` storage | `Any` (G5) |

With them, `probes/upstream/u_tomllib*.py` match CPython in JIT and AOT: a mixed document; every
value kind (offset, UTC and local datetimes, dates, times, `inf`, `nan`, hex/octal/binary
integers, escapes, multiline and literal strings, dotted keys, inline tables, arrays of tables);
seven invalid documents with CPython's exact `TOMLDecodeError` text; `ports/pyproject.toml`; and
all 62 files of `Lib/test/test_tomllib/data` (13 parsed, 49 rejected, as CPython: the driver
reads text, so one `invalid/` case with a bare carriage return parses on both). The mixed
document, the value kinds, the errors, the round trip of section 4 and the compliance corpus
also match with a collection at every allocation (`--keep PYSTACHY_GC_STRESS_PROGRAM`), in JIT
and AOT.

`bench/bench_tomllib.py` on `records.toml` (526 KB, 3,000 mixed records, `bench/gen_records.py`),
7 interleaved processes of 5 `loads()` each; the checksums match:

| | `loads()` median | range of process medians | peak RSS |
|---|---:|---:|---:|
| AOT | 95.5 ms | 80.3–124.7 ms | 40 MiB |
| CPython 3.13.16 (same source, pure Python) | 187.5 ms | 175.7–226.5 ms | 16 MiB |

JIT: 119.8 ms per `loads()` inside the program, 3.0 s end to end (compiling `tomllib`, `re` and
`datetime`). The AOT binary is 547 KB. The win comes from the typed scanner (`src: str`,
`pos: int`); only the values it produces are dynamic.

## 4. tomli-w 1.2.0 (`patches/tomli_w-1.2.0.diff`)

| Edit | Blocker | Kind |
|---|---|---|
| 1 | `types.MappingProxyType` (unchanged tomli-w's first blocker, with or without the comment) | general |
| 2 | `isinstance(v, Mapping)` of an `Any` value (3 sites) | `Any` (G4) |
| 3 | `obj: object`, `obj: Mapping`, `obj: tuple \| list` | `Any` (G3) |
| 4 | `Mapping[str, Any]` parameters given `Any` values | `Any` (G1) |
| 5 | `tuple[Any, Any, bool]` stored in `list[tuple[str, Any, bool]]` | `Any` (G2) |
| 6 | `ARRAY_TYPES = (list, tuple)` used in `isinstance` | general (#7) |
| 7 | lazy `from decimal import Decimal`; `type(obj).__qualname__` | general |

The upstream generator (`yield from`) and the `id()`-keyed inline-table cache that the port
removed both work. `probes/pkgs/p_tomli_w.py` (mixed document), `probes/tomliw_tests/t_direct.py`
(homogeneous, nested and empty displays passed directly) and `probes/upstream/u_roundtrip.py`
match pristine upstream on CPython in JIT and AOT. The port's tests
(`tests/programs/apps/port_tomli_w_*.py`, copied as `t_*.py`) fail at compile time with and
without the comment in the caller: `a dict[str,str] cannot become an Any value`.

## 5. PyPI and stdlib first blockers

| Package (wheel) | First blocker, with and without the comment |
|---|---|
| tomli-w 1.2.0 | `types.MappingProxyType` |
| jmespath 1.0.1 | `inspect` → `importlib._bootstrap_external`: no `_warnings` |
| toolz 1.0.0 | the same |
| jsonpointer 3.0.0, dictdiffer 0.9.0, mergedeep 1.3.4 | `copy` → `copyreg`: a dict keyed by the builtin `complex` |
| flatten-json 0.1.14 | `six` |
| tabulate 0.9.0 | a namedtuple field given `None` |
| json-logic 0.6.3 | Python 2 code: CPython 3.13 fails too (`'dict_keys' object is not subscriptable`) |

With `copyshim/copy.py` (deep copy of builtin values held as `Any`) ahead of CPython's `copy`, the
next blockers are still not `Any`'s: jsonpointer a class attribute bound to `re.compile(...).match`,
dictdiffer `collections.abc.MutableMapping`, mergedeep `enum`.

Stdlib modules with the comment (`probes/stdlib/`): `copy` (`copyreg`, as above), CPython's own
`json` (`int.__repr__` as a value, #247), `pprint` (class-body dispatch table), `graphlib`
(`self._node2info = {}` untyped), `logging` (`threading`: `_thread.lock` as a value) and
`dataclasses.asdict()` of an `Any` field (`CPython deep-copies it: #486`) all fail first for
reasons other than `Any`.

Import sweep (`tools/import_sweep.py -j 3`, 21 s each): 149 of 519 modules import unchanged;
with the comment injected into every module, 150. The one change is `xml.etree.ElementPath`
(`expected <function prepare_child>, got <function prepare_star>` → OK); no module regresses.

## 6. The agent-transcript pipeline (`pipeline/`)

`gen_events.py 100000` writes 100,000 JSONL events (15.2 MB, SHA-256 `e3188960…`): tool uses
with per-tool inputs of mixed types, results with `str` or block-list content and int, float or
null durations, usage records with null caches and `"n/a"` costs, text, errors with int, str or
null codes. `pipeline.py` decodes each line (`json.loads()`, then `to_any()`, G7), dispatches by
`type` through `dict[str, Callable[[Any, Any], None]]`, keeps `Session`/`ToolStats` objects with
`Any` fields and `dict[Any, Any]` tables, keys each tool's statistics by a per-tool function
returning a str, an int or a bool, and writes a JSON summary. It needed two workarounds
(W1 slicing, W2 `round()`; G6).

- Output: byte-identical to CPython for 100,000 events in AOT; for 40 events with a collection
  at every allocation in JIT (5,300 collections) and AOT (5,299).
- Time, 7 interleaved processes × 3 rounds (two such sets; the second is the fast-path run):

| | decode | process | end to end, 1 round |
|---|---:|---:|---:|
| AOT | 379 ms / 365 ms | 165 ms / 164 ms | 0.64–0.73 s |
| AOT with `patches/runtime-anykey-str-fastpath.diff` | — / 321 ms | — / 152 ms | |
| CPython 3.13.16 | 593 ms / 599 ms | 101 ms / 106 ms | 0.77–0.89 s |
| JIT | | | 0.95–1.11 s |

  The AOT build takes 2.8 s and gives a 253 KB binary.
- Callgrind, the processing of 10,000 events (the difference between 6 rounds and 1 round of
  `pipeline_proc.py`): 7,870 instructions per event; 6,607 with the fast path (−16%). With it:
  `Any`-keyed dict probing and key comparison 38%, hashing 17.5% (`pys_dyn_hash` → `hitem` →
  `hval`, four or five calls to the cached hash), allocation and collection 24% (zeroing,
  scanning; a new box for each int above 256 that `+=` makes, `split()` lists), `split`/slices 7%,
  the dispatchers (`dyn.get.*`, `dyn.call.*`, `cv.*`) and boxing 11% (9.5% without the fast
  path; code that `-O2` inlined into its callers is not counted).
- The fast path: in `dlook`, two boxed `str` keys of an `Any`-keyed dict compare as strs instead
  of through `dkeyeq` → `keyeq` → `dyn_eqitem` → `pys_dyn_eq`. It is an experiment: the output
  matched for 100,000 events, but it has no tests.

## Recommendations

1. **Lead with ordinary programs, opted in with one line.** The 25 idioms of section 1 are the
   evidence that dynamic `Any` already makes unchanged heterogeneous code compile. Close G1, G5
   and G6 next: they are the failures a user meets first, and G6's six opt-in regressions
   (section 1) should be fixed before the comment is recommended for whole programs.
2. **Make `tomllib` the library milestone, then tomli-w.** It is unchanged stdlib code whose
   result is inherently `dict[str, Any]`, it has a ready compliance corpus, it shares G1/G2/G5
   with tomli-w, and its typed scanner already beats CPython 2×. Keep the shipped tomli-w port
   until typed containers can cross into `Any` (G1), or its typed callers break.
3. **Bridge JSON (G7).** `json.loads()` building `Any` storage in a module that opts in (or
   converting its fresh result), and `json.dumps()` taking `Any`, turn the pipeline's copies into
   no-ops and connect JSON to user objects and callbacks.
4. **Optimize lookups and boxes before guards.** On the pipeline, the dispatchers and boxing
   are about 10% of processing; `Any`-keyed dict lookups with `str` keys (a boxed-str fast path,
   a precomputed hash for literal keys, shared key boxes) and box allocation for numeric fields
   and accumulators are the bulk. Guarded variants or inline caches (#392) come after those, if
   a measurement still shows dispatch.
5. **Measure with functional probes, not import sweeps.** The comment moves one stdlib import;
   PyPI's first blockers are stdlib and class-value gaps. A PyPI sweep would mostly measure those
   until `copy`, `enum`, `inspect`/`importlib`, `collections.abc` and `types.MappingProxyType`
   move.

## Reproduce

From the repository root, after `make PY=python3.13`, with `D=research/dynamic-any`:

```sh
python3.13 $D/tools/probe.py --modes jit,aot $D/probes/idioms/*.py
# the same files without their first line, for the "without" column
mkdir -p /tmp/np && for f in $D/probes/idioms/*.py; do grep -v '^# pystachy: dynamic-any$' $f > /tmp/np/${f##*/}; done
python3.13 $D/tools/probe.py --modes jit,aot /tmp/np/*.py
# CPython's Lib behind import_sweep's overlay; tomllib with the comment and the edits (the
# diffs add the comment lines too, so they apply to pristine copies)
python3.13 tools/import_sweep.py --overlay ./pystachy /usr/lib/python3.13 /tmp/cpython-lib
mkdir -p /tmp/dyn && cp -r /usr/lib/python3.13/tomllib /tmp/dyn/
(cd /tmp/dyn && patch -p1 < "$OLDPWD/$D/patches/tomllib-3.13.16.diff")
(cd $D/probes/upstream && python3.13 ../../tools/probe.py --modes jit,aot --path /tmp/dyn:/tmp/cpython-lib u_tomllib.py u_tomllib_full.py u_tomllib_errors.py u_tomllib_pyproject.py)
# tomli-w: unpack the 1.2.0 wheel into /tmp/tw (it holds tomli_w/), copy it, patch the copy, and
# give CPython the pristine one
cp -r /tmp/tw /tmp/tw-dyn && (cd /tmp/tw-dyn && patch -p1 < "$OLDPWD/$D/patches/tomli_w-1.2.0.diff")
(cd $D/probes/upstream && python3.13 ../../tools/probe.py --modes jit,aot --cpath /tmp/tw --path /tmp/dyn:/tmp/tw-dyn:/tmp/cpython-lib u_roundtrip.py)
# the runtime experiment: a PYSTACHY_HOME whose runtime.c has the fast path
mkdir -p /tmp/rt && cp runtime.c runtime.py pyext.c pyembed.c /tmp/rt/ && ln -s "$PWD/lib" "$PWD/ryu" /tmp/rt/
(cd /tmp/rt && patch -p1 < "$OLDPWD/$D/patches/runtime-anykey-str-fastpath.diff")
PYSTACHY_HOME=/tmp/rt ./pystachy build $D/pipeline/pipeline.py -o /tmp/pipeline_exp
```

`u_tomllib_compliance.py` reads the files that `compliance_files.txt` lists from
`$TOMLLIB_DATA`, the `Lib/test/test_tomllib/data/` directory of the 3.13.16 source (`Python-3.13.16.tgz`, SHA-256
`cfac63bddf956deafb1172ca131ae5dcaafd6f95056086e233fca205593ed427`, whose `Lib/tomllib` is
identical to the installed one). The pipeline's input is
`python3.13 -I pipeline/gen_events.py 100000 > big.jsonl`, the benchmark's
`python3.13 -I bench/gen_records.py`.

## Provenance

`patches/tomllib-3.13.16.diff` and `patches/tomli_w-1.2.0.diff` quote, as diff context, CPython
3.13.16's `Lib/tomllib` and tomli-w 1.2.0 (`tomli_w-1.2.0-py3-none-any.whl`, SHA-256
`188306098d013b691fcadc011abd66727d3c414c571bb01b1a174ba8c983cf90`); both are by Taneli Hukkinen
under the MIT license (`SPDX-FileCopyrightText: 2021 Taneli Hukkinen`; tomllib "Licensed to PSF
under a Contributor Agreement"). `probes/tomliw_tests/t_*.py` are this repository's
`tests/programs/apps/port_tomli_w_*.py` with the comment added. Everything else here was written
for this study. The other wheels' SHA-256s: jmespath 1.0.1 `02e2e4cc…`, jsonpointer 3.0.0
`13e088ad…`, json-logic 0.6.3 `dd873af8…`, toolz 1.0.0 `292c8f1c…`, dictdiffer 0.9.0
`442bfc69…`, flatten-json 0.1.14 `75e455db…`, mergedeep 1.3.4 `70775750…`, tabulate 0.9.0
`024ca478…`.

## Addendum: issues #772–#775 (filed the same day by another session)

Re-checked at `ad19255e`: #772's first case reproduces in JIT and AOT (`probes/check772/`).
`x == y`, `x in [y]` and `[x].count(y)` of two `Q(1)` held as `Any` give `False False 0`, where
CPython gives `True True 1`. With a `__hash__`, dict lookups miss too: `d.get(y, "missing")` gives
`missing` and `y in d` `False` (CPython: `found`, `True`). The same file without the comment, or
with `other: object`, is right. In a module that opts in, typed `a in [b]` of two such objects is
rejected at compile time (`calls __eq__() with a Q, but it takes a Any`), though it compiles and
matches CPython without the comment: a seventh opt-in regression beside section 1's six.

None of this study's passing probes or workloads defines `__eq__` with an `Any` parameter, so
their results stand. But a class whose `__eq__` takes `other: Any` is common, and #772 answers
wrongly without an error. Under #409, #772 comes before recommendation 1 below: the comment
should not be recommended for whole programs until it is fixed.

Where section 2's gaps are tracked now:

| Gap | Tracked by |
|---|---|
| G1 typed containers into `Any` (`dict[str, Any]`, locals holding displays, typed locals that later get `Any`) | none; #775 has its `[0] * n` case, and docs/dynamic-any.md lists "typed-container crossings" as a next step |
| G2 tuples with `Any` items | none |
| G3 `object`, `Mapping`, bare annotations in a module that opts in | none (#713 and #597 cover modules that do not opt in) |
| G4 `isinstance()` with `collections.abc` classes | none |
| G5 empty displays into `Any` storage | none |
| G6 slicing, `sum()` of a `list[dyn]` or generator, `dict.update()` of a display, `type(x) is int` | none (#775 lists `sum(x)` of an `Any` value as working, which it is) |
| G6 `round`, `abs`, `ord`, `chr`, `divmod`; keyword arguments | #775; #774 |
| G7 JSON bridge | none |
| G8 sets as `Any` values | #775 |
| G9 widening for incompatible concrete stores | none (docs/dynamic-any.md's "widening" next step covers closures, generators and mutual returns) |
| G10 library templates for `dyn` (`textwrap`: `ord`; `statistics`: `math.fsum`); module-level narrowing | #775 for the builtins; none for narrowing |
| Performance: `Any`-keyed dict lookups, boxes of accumulators | none (docs/dynamic-any.md's "box elimination" next step covers boxes) |
