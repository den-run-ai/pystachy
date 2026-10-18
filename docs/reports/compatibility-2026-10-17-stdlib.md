# Standard-library audit, 17 October 2026

This report measures the compiler/runtime/library sources at
`d3fbfc6f5f6d5650f25ffc0d97be93b512f41a6f`, using CPython **3.13.16** and LLVM **18.1.3**
on Linux x86-64. Later merging PRs are separate evidence until the affected check is
rerun. The compiler and runtime passed the native self-hosting IR fixed point
(607,640 compiler IR lines; 17,615 runtime IR lines).

## What works now

The shipped library supports useful compiled workflows across text processing,
regex, collection algorithms, caching, parsing, codecs/binary data, random numbers,
fixed-offset dates and lazy iteration. The accepted surface is described in
[`lib/README.md`](../../lib/README.md) and
[`lib/compatibility.md`](../../lib/compatibility.md); none of these results certify
whole-module CPython compatibility.

| Source category | Useful shipped surface | Important boundary |
|---|---|---|
| Unchanged CPython files | bisect, colorsys, ASCII helpers, stat predicates, POSIX path-string helpers; struct's Python facade | Compiled paths only; struct uses Pystachy's replacement for the C module and requires a compile-time format except for calcsize |
| Localized upstream ports | heapq selection; difflib matching/grouped opcodes; fnmatch/textwrap; getopt/shlex; string formatting; statistics; random; URL and HTML processing; fixed-offset datetime | Module-specific exclusions, static representations and text byte/ASCII semantics remain |
| Implementations of CPython's C-backed APIs | functools caches/partial; deque/defaultdict/OrderedDict/Counter; StringIO/BytesIO; csv; binascii; codecs; unicodedata; struct; itertools; abc; one-thread _thread | These are explicit subsets/ports; e.g. no real threads, weakrefs, arbitrary buffers or full codec registry |
| Adapted control-flow libraries | contextmanager, closing, nullcontext, suppress and ContextDecorator | No complete contextlib/async/ExitStack support |

The fresh evidence below separates importing, compiling an API, executing it, and
executing an upstream test. Hosted port tests also remain separate from compiled
tests.

## Fresh stdlib import sweep

The native compiler accepted **141 of 476 included import programs**. The source
installation contains 522 eligible `.py` modules; 46 are excluded because the
corresponding top-level name is supplied by `lib/`. There were **335 compilation
errors and zero timeouts**. A CPython-hosted compiler sweep produced the same
results. There were no compiler crashes in this sweep.

These are **IR-generation results**, not runtime success or 141 fully supported
stdlib modules. Some successes are empty packages, annotation modules, codec
facades or unused definitions. In particular, an entire upstream package is
excluded when its top-level name is replaced: excluded `urllib.request` does not
imply that Pystachy implements it.

The raw per-module results and provenance are checked in:

- [`compatibility-2026-10-17-stdlib-imports.json`](compatibility-2026-10-17-stdlib-imports.json)
- [`compatibility-2026-10-17-stdlib-metadata.json`](compatibility-2026-10-17-stdlib-metadata.json)

Machine-local paths in these files are normalized to `<PYSTACHY_ROOT>`,
`<CPYTHON_STDLIB>` and `<PYTHON>`. Error messages, names, outcomes and compiler hash
are otherwise retained. The metadata's dirty flag refers to this audit's tooling
and documentation work, not an uncommitted compiler/runtime change. Counts from
older installations, overlays or source revisions are not comparable until their
module inventories match.

| First failure | Number of import programs stopped there |
|---|---:|
| `_weakref` unavailable | 100 |
| `_imp` unavailable | 32 |
| `_ast` unavailable | 19 |
| `collections.namedtuple` unavailable | 17 |
| Cannot infer a dict of `None` values | 15 |
| `pyexpat` unavailable | 9 |
| `_contextvars`, `_bz2`, `sys.warnoptions`, `_socket` | 7 each |

A second, **hosted compile-only** sweep supplied temporary nonfunctional stubs for
25 CPython C modules. It accepted **145/476**, of which 141 needed no stub. Only
four extra imports succeeded: `_py_abc` and `_weakrefset` using `_weakref`,
`encodings.zlib_codec` using `zlib`, and `timeit` using `gc`. The stub functions
raise `NotImplementedError`; this is blocker analysis, not implementation evidence.
It also shows why implementing the first missing C module alone does not unlock
all its reported dependents.

## Real API probes beyond imports

These probes use untouched CPython stdlib sources through the overlay, unless an
adaptation is explicitly stated. Programs run under pinned CPython for their
expected result. Successful probes were then checked with native JIT and AOT.

| Probe | Result | Adaptation assessment |
|---|---|---|
| `base64.b64encode(b'hello')` | CPython-equivalent JIT and AOT | No source edits |
| `base64.b64decode('aGVsbG8=')` | CPython-equivalent JIT and AOT | No source edits; ASCII-str input |
| `ntpath.normpath(ntpath.join(...))` | CPython-equivalent JIT and AOT | No source edits |
| `stringprep.in_table_b1('\u00ad')`, `map_table_b2('A')` | CPython-equivalent JIT and AOT | No source edits |
| `encodings.cp1252.Codec().encode/decode` | CPython-equivalent JIT and AOT | No source edits; calls the shipped charmap codec |
| `base64` byte-input encode/decode | Rejected: `isinstance(s, bytes_types)` cannot use the module-level tuple alias of classes | **One-line bounded port verified:** replace that check with `isinstance(s, bytes)`; the byte-input round trip then matches CPython JIT/AOT. This proves the bytes-only probe, not bytearray/memoryview support or every base64 API |
| `encodings.utf_16.encode/decode` | Imports and compiles; JIT/AOT execution raises the documented `NotImplementedError` for `codecs.utf_16_encode` | Actual codec implementation needed; import/compile success hides this unsupported runtime surface |
| `quopri.encodestring/decode` | Rejected because the function-local import of `io` is not already imported at module level | Adding caller `import io` reveals the next failure: fallback `encode` expects int, receives bytes. One import edit is insufficient |
| `graphlib.TopologicalSorter(...).static_order()` | Rejected; after annotating the caller's graph, `_node2info` field inference still fails | Internal typed storage adaptation needed; no claim that one annotation completes the port |
| `email.utils.parseaddr` | Rejected on `AddressList` inheritance from a generic template | Inheritance/constructor typing adaptation needed; successful `email` import is insufficient |
| `mimetypes.guess_type('document.txt')` | Rejected: cannot infer `MimeTypes.encodings_map` | Internal storage/inference work; later blockers not established |
| `linecache.getline(missing_file, 1)` | Rejected: cannot infer global `linecache.cache` | Cache typing needed; later blockers not established |

The base64 experiment is an audit-only scratch adaptation. It is not installed in
`lib/`, and no broader support is claimed. Selected probe sources, outcomes and
commands are retained in the [API evidence JSON](compatibility-2026-10-17-stdlib-api-probes.json).

## Upstream suites and compiled tests

Fresh `make port-check` succeeded with pinned Python: **17/17 fnmatch** and
**66/66 textwrap** upstream methods passed against their adapted files under
CPython, with zero skips. The provenance/manifest harness's **15 unit tests** also
passed. These are hosted preservation checks; they do not mean all 83 methods run
unchanged under Pystachy.

The acceptance manifest gives the more precise compiled mapping:

| Module | Complete mappings | Partial mappings | Documented deviations | Unsupported |
|---|---:|---:|---:|---:|
| fnmatch | 12 | 2 | 0 | 3 |
| textwrap | 63 | 1 | 2 | 0 |

The compiled audit selected **322 files**: 99 `tests/lib_*.py`, 79 positive
`tests/upstream_*.py`, 143 upstream-derived rejection cases and one upstream-derived
deviation case. These exercise many more source families than the two fully
inventoried ports: regex, itertools, contextlib, datetime, random, HTMLParser,
collection types, math, operator, formatting, generators and core Python behavior.

**Compiled result: 501 checks passed, 0 failed.** This is 356 positive JIT/AOT
checks, 143 expected-rejection checks and two checks of the documented deviation.
The compiler executable is
`build/pystachy1`, built from the audited source and validated by the completed
fixed-point bootstrap. Positive cases run both JIT and AOT against recorded
CPython output. A passing rejection test means a precisely rejected unsupported
program, and a passing deviation case means the documented difference remains;
neither is counted as ordinary CPython compatibility.

The stdlib replacement algorithm validators also passed freshly under CPython:

| Validator | Fresh result | Scope |
|---|---:|---|
| `tools/itertools_check.py` | 40,000 cases; 0 differences | Port Python vs CPython C itertools; explicitly normalizes documented reads after exhaustion |
| `tools/struct_check.py` | 100,013 checks; 0 differences | Port Python vs CPython C struct |
| `tools/thread_check.py` | 263,014 checks; 0 differences | One-thread contract only; no concurrency |
| `tools/binascii_check.py` | 420,000 calls; 0 differences; 12 signatures match | Port Python vs CPython C binascii |

These validators execute the port source on CPython. The separate compiled
`lib_*.py`/upstream-derived programs test native behavior. Older hosted counts in
`lib/provenance.md` are not newly rerun results unless listed here. The full
unmodified CPython `unittest`/regrtest suite is a separate unsupported framework,
not what the adapted corpus runs.

## Remaining blockers and priorities

1. **Preserve the import/API/execution distinction in tooling.** UTF-16 is a
   concrete case that passes both import and compilation but has no implementation.
   A sidecar provenance/count report now makes source version, excluded names and
   scope explicit. General semantic multi-error analysis remains
   [#261](https://github.com/den-run-ai/pystachy/issues/261).
2. **Finish small shared import gaps, then measure the next blocker.** The audited
   revision still lacks `namedtuple`, `sys.warnoptions`, selected io names and
   module-level deletion support. Related pending work is #600/#601/#602/#606/#608;
   conditional module definitions and deletion remain
   [#611](https://github.com/den-run-ai/pystachy/issues/611) and
   [#612](https://github.com/den-run-ai/pystachy/issues/612). Their projected module
   gains cannot be added together or treated as merged results.
3. **Broader libraries need more than import shims.** `logging`/`threading` reach
   weakrefs; `inspect` reaches `_ast`; `zipfile` reaches `_imp`; `subprocess` reaches
   `_signal`; `pathlib` reaches `os.O_RDONLY`; `argparse` reaches `sys.base_prefix`;
   `configparser` lacks ChainMap; `tomllib` reaches MappingProxyType. JSON still
   needs dynamic/recursive values beyond its first `c_scanstring = None` inference
   error. Full enum class construction remains substantial work
   ([#610](https://github.com/den-run-ai/pystachy/issues/610)).
4. **Unicode correctness remains material.** String indexing/length and selected
   text operations use byte/ASCII semantics; textwrap's two upstream Unicode
   deviations are retained, not normalized into passes. See
   [#120](https://github.com/den-run-ai/pystachy/issues/120). Broad non-ASCII text
   support requires semantic work or explicit per-port character handling.
5. **Cached unannotated functions remain a shared port obstacle.**
   [#620](https://github.com/den-run-ai/pystachy/issues/620) tracks cache/lru_cache
   signature inference; accepting `Any` annotations alone does not supply a
   heterogeneous runtime representation or solve cache key/state semantics.
6. **Expand acceptance inventories by useful workflow.**
   [#361](https://github.com/den-run-ai/pystachy/issues/361) remains the owner of
   broader source-method inventories and four-way port benchmarks. Historical
   datetime slowdown figures in [#519](https://github.com/den-run-ai/pystachy/issues/519)
   were not rerun here and should not be presented as current performance.

No new native wrong-result or compiler-crash defect was found by these checks. Unsupported API probes failed with compiler diagnostics or the
explicit codec runtime error. Performance timings during this concurrent audit
are not controlled comparative benchmarks; this report makes no speedup claims.

The bodies of #11/#254/#257/#491 include historical stages that predate current
bytes, generators, formatter and C-module ports. Use their dated comments and the
current source contracts rather than treating every old “remaining” line as a
current missing feature.

## Reproduction

Use the pinned interpreter and the installation's actual stdlib directory. `LIB`
below means that directory, not Pystachy's `lib/`.

```sh
PY=/path/to/python3.13
LIB=$($PY -c 'import sysconfig; print(sysconfig.get_paths()["stdlib"])')
export PYSTACHY_LLVM=/path/to/llvm18/bin
make PY="$PY"
mkdir -p build/audit-stdlib
"$PY" tools/import_sweep.py -j 4 \
  --metadata build/audit-stdlib/import-sweep-meta.json \
  ./pystachy "$LIB" build/audit-stdlib/import-sweep-native-313.json
"$PY" tools/import_sweep.py --stubs -j 4 \
  "$LIB" build/audit-stdlib/import-sweep-stubs-313.json
"$PY" tools/import_sweep.py --overlay ./pystachy "$LIB" build/audit-stdlib/cpython-lib
make PY="$PY" port-check
PYSTACHY_JOBS=4 tests/run.sh build/pystachy1 'jit aot' \
  tests/lib_*.py tests/upstream_*.py tests/errors/upstream_*.py \
  tests/deviations/upstream_*.py
"$PY" -I tools/itertools_check.py
"$PY" -I tools/struct_check.py
"$PY" -I tools/thread_check.py
"$PY" -I tools/binascii_check.py
```

For an API probe, place its source in a directory whose filenames do not shadow
stdlib modules, then compare `"$PY" -I probe.py`,
`PYSTACHY_PATH=build/audit-stdlib/cpython-lib ./pystachy run probe.py` and
`PYSTACHY_PATH=build/audit-stdlib/cpython-lib ./pystachy build probe.py -o probe`;
execute `./probe` separately. The API evidence records the precise source used.
