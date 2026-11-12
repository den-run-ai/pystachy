# Libraries and porting

Pystachy ships part of Python's standard library in [`lib/`](../lib/README.md): unchanged
CPython files, CPython modules with marked edits, and subset implementations of modules that
CPython writes in C. All of them remain valid Python. A few modules, such as `sys`, `os` and
`math`, are built into the compiler instead. Importing a module does not mean that every API in
it works: each module supports its own subset, which compiles with the program that uses it.

| Question | Reference |
|---|---|
| Which APIs of a module work? | [Module guide](../lib/README.md#module-guide) |
| How does a module differ from CPython's? | [Library compatibility](../lib/compatibility.md) |
| Which upstream files and checks back a module? | [Provenance](../lib/provenance.md) |
| Which modules does the compiler provide, and how are imports found? | [Modules and builtins](language/modules.md#builtin-modules-and-files) |
| Which third-party packages are adapted? | [Ports](../ports/README.md) |
| How are upstream test suites run? | [Porting and upstream tests](porting.md) |

<a id="the-standard-library-and-popular-packages-under-pystachy"></a>
<a id="summary"></a>
<a id="3-the-standard-library"></a>
<a id="31-what-compiles-and-runs-unmodified"></a>

## Library support at a glance

| Status | Meaning |
|---|---|
| 🟢 **Native** | The module's public API compiles and matches CPython, apart from documented differences |
| 🟡 **Bounded** | Selected APIs or argument types; the [module guide](../lib/README.md#module-guide) lists them |
| 🧪 **Experimental** | Built on a prototype: recursive JSON values, [dynamic `Any`](dynamic-any.md), collector-backed weak references, explicit big integers or an embedded CPython |
| 🔴 **Unsupported** | Not shipped: importing the module is a compile-time error |

🔴 **Major gaps** are modules or APIs that are not available. 🟠 **Minor gaps** are narrower
argument types or documented differences within a supported API. The statuses match the
[language guide's](language.md#support-at-a-glance).

| Area | Status | Modules | 🔴 Major gaps | 🟠 Minor gaps |
|---|---|---|---|---|
| [Text](../lib/README.md#text) | 🟢 Native<br>🟡 `string`, `difflib`, `gettext` | `textwrap`, `unicodedata`, `shlex`, `keyword`, `token`, `curses.ascii`, `this`, `string`, `difflib`, `gettext` | `locale`, `pprint`; `difflib.ndiff()`, `Differ` and `HtmlDiff`; `gettext` translation catalogs | No `TextWrapper` or `Template` subclasses; most `Formatter` fields that read an attribute or item raise `ValueError`; `capwords()` capitalizes ASCII letters only |
| [Regular expressions](../lib/README.md#regular-expressions) | 🟡 Bounded<br>🧪 Generated matchers | `re`, for CPython 3.13's syntax of `str` patterns, with optional [generated matchers](re-specialization.md); `fnmatch` | Bytes patterns; `findall()` with two or more groups raises `NotImplementedError` | `finditer()` returns a list; `split()` raises where an unmatched group would add `None`; no `Scanner`, `Match.regs` or `\N{...}` |
| [Data formats and markup](../lib/README.md#data-formats-and-markup) | 🟡 Bounded<br>🧪 `json`, `tomllib` | [`json`](json.md), `tomllib`, `csv`, `html` with `html.entities`, `html.parser`, `urllib.parse` | `configparser`, `xml`, `email`, `pickle`; JSON files, hooks and indentation; `tomllib.load()`, which reads a binary file | Typed JSON integers are 64-bit, and nesting stays within the recursion limit and 2,000 containers; `csv` has no `Sniffer`; `urllib.parse` takes `str` only |
| [Binary data and encodings](../lib/README.md#binary-data-and-encodings) | 🟡 Bounded | `struct`, `binascii`, `codecs` | `base64`, `hashlib`, `zlib`, `zipfile`, `array`; `bytearray` and `memoryview` buffers | `struct` formats must be known as the program compiles, and there is no `pack_into()`; `codecs` has UTF-8, Latin-1, ASCII and charmap, without `lookup()` |
| [Collections and functional tools](../lib/README.md#collections-and-functional-tools) | 🟡 Bounded<br>🟢 `itertools`, `bisect` | `collections` (`deque`, `defaultdict`, `OrderedDict`, `Counter`, `namedtuple()`), `copy`, `enum` (`Enum`, `IntEnum`, `StrEnum`, `Flag`, `IntFlag`, `str`/`int` mixins), `heapq`, `bisect`, `itertools`, `functools`, `operator`, `contextlib` | `enum`'s functional API and `boundary=`; `copy.replace()`; `ChainMap` and the `User*` classes; `heapq.merge()`; `contextlib.ExitStack`; `functools.singledispatch()` and `total_ordering()` | A container's items share one type; the mappings hold a `dict` rather than derive from it (`isinstance()` still takes them for dicts, but not in an `Any` value; `type()` is not `dict`, and the library's functions do not take them for dicts); `itertools` iterators are generators; `lru_cache` keys cannot be floats; `copy` follows static types, so an object in an `Any` value is not copied; enum members' values are literals or constant expressions, and int-like members are no ints where those are typed |
| [Numbers and randomness](../lib/README.md#numbers-and-randomness) | 🟡 Bounded<br>🧪 `mpz` | `math` (builtin), `random`, `statistics`, `colorsys`, [`mpz`](mpz.md) | `decimal`, `fractions`, `cmath`, `numbers`, `secrets`; `statistics.mean()`, `stdev()`, `variance()`, `kde()` and `NormalDist` | `kde()` passes bounded `match` but still needs heterogeneous function storage; `getrandbits()` takes at most 63 bits; no `str` seeds, `randbytes()` or `SystemRandom`; no `math.sumprod()` |
| [Dates and times](../lib/README.md#dates-and-times) | 🟡 Bounded | `datetime`; `time.time()`, `monotonic()`, `perf_counter()` and `sleep()` (builtin) | The local time zone (`date.today()`, `datetime.now()` without a zone); `strptime()`; `time.localtime()`, `gmtime()` and `strftime()`; `calendar`, `zoneinfo` | `2 * delta` and other reflected operators are rejected; `hash()` values differ from CPython's; `timedelta` arithmetic is 64-bit |
| [Files, OS and command line](../lib/README.md#files-os-and-command-line) | 🟡 Bounded | `open()` of text and binary files; `io` (`StringIO`, `BytesIO`, `TextIOWrapper`); selected `sys`, `os` and `os.path` (builtin), including `os.makedirs()`, `os.environ[name]` reads and writes and its `get()`, `pop()` and `in`; `posixpath`, `stat`, `tempfile.mkdtemp()`, `errno`, [`select.select()`](select.md), [`argparse` with literal declarations](../lib/compatibility.md#argparse), `getopt`, `pathlib` (POSIX), `glob`, `shutil` (copies, `move()`, `rmtree()`) | Runtime-defined parsers and subparsers, `os.environ` as a mapping value (iteration, `items()`) and `os.stat()`, `shutil.copytree()` | `TextIOWrapper` decodes UTF-8, Latin-1 and ASCII, without `seek()`; a dropped file closes at a later collection; no `posixpath.relpath()`; `open()` and `os` take `str(path)`, not a path object |
| [Processes and threads](../lib/README.md#processes-and-threads) | 🔴 Unsupported<br>🟡 `threading`, `_thread`, `atexit` | `threading` and `_thread` for the one thread a program runs, `atexit`; `os.system()` and `os.execv()` | Starting a thread; `multiprocessing`, `concurrent.futures`, `subprocess`, `asyncio`, `queue`, `signal` | `Thread.start()` raises `NotImplementedError`; `atexit.unregister()` raises `NotImplementedError`; a lock wait that would block for ever raises `RuntimeError` |
| [Runtime services](../lib/README.md#runtime-services) | 🟡 Bounded<br>🧪 `weakref`, `logging` | `typing`, `dataclasses` and `collections.abc` (builtin); `abc`, `types`, `warnings`, [`weakref`](weakref.md), `logging` (compiled with [dynamic `Any`](dynamic-any.md)), `traceback` | `inspect`, `ast`, `dis`, `importlib`; `logging.config`, `logging.handlers` and `LoggerAdapter`; weak containers and `weakref.finalize` | `warnings.warn()` reports `<sys>:0`; a log record's caller is unknown and an exception's text has no frames (no frames or tracebacks); a typed list or dict cannot be a log message's argument; no virtual subclasses (`ABC.register()`); most other `types` names fail where used |
| [C and CPython interop](../lib/README.md#c-and-cpython-interop) | 🧪 Experimental | `ffi` for [C calls](ffi.md#calling-c), [static ctypes declarations](ffi.md#static-ctypes-declarations), `pyobj` for an [embedded CPython](ffi.md#calling-cpython) | Dynamic ctypes signatures, structures and callbacks; native imports of CPython C extension modules | ctypes is a bounded source subset; `pyobj` converts scalars only and needs `PYSTACHY_LIBPYTHON` |

The table describes the current source tree. Other modules are not shipped, apart from private helpers
that the [module guide](../lib/README.md#module-guide) lists; [measuring
coverage](#measuring-coverage) shows how to check whether CPython's own copy of one compiles.
For parallel work today, CPython can run Pystachy-built extension modules in
[process pools](concurrency.md#process-pools-today).

<a id="shipped-coverage"></a>

## Where shipped modules come from

| Origin | Modules |
|---|---|
| Unchanged CPython 3.13.16 files | `bisect`, `colorsys`, `curses.ascii`, `this`, `stat`, `posixpath`, `genericpath`, `struct` (on a port of `_struct`) and `_weakrefset` |
| CPython modules with marked edits | `codecs`, `contextlib`, `datetime`, `difflib`, `fnmatch`, `getopt`, `gettext`, `heapq`, `html`, `html.parser`, `keyword`, `operator`, `random`, `shlex`, `statistics`, `string`, `textwrap`, `token`, `tomllib`, `urllib.parse`, `warnings`, `weakref` |
| Larger port | `re`: CPython's Python parser and compiler, plus a matcher adapted from its C engine |
| Subset implementations | `abc`, `argparse`, `collections`, `csv`, `functools`, `io`, `json` and `types`; subset versions of the C modules `atexit`, `binascii`, `itertools`, `unicodedata`, `_codecs`, `_random`, `_string`, `_struct`, `_thread` and `_weakref` |
| Compiler builtins | `sys`, `os`, `os.path`, `math`, `time`, `errno`, `tempfile`, `select`, `typing`, `collections.abc`, `dataclasses`, `builtins`, `__future__` and `ffi` |
| Outside the standard library | [`mpz`](mpz.md), explicit arbitrary-precision integers on a packed-limb C backend; `pyobj`, objects of an [embedded CPython](ffi.md#calling-cpython) |

Opt-in library code follows the [dynamic boundary policy](dynamic-any.md#admission-and-containment):
known parser state stays typed, while supported open callback and payload contracts
retain dynamic storage. The [inventory](dynamic-any-boundaries.md) records remaining
compiler and port limitations separately from interface requirements.

`mpz` does not change ordinary `int`, JSON parsing or native integer interfaces. Modules that opt
in to [promoting ints](python-int.md) get CPython's unbounded `int` instead, and the dynamic
`Any` JSON decoder promotes integer tokens beyond 64 bits; the typed `JSONValue` decoder keeps
64-bit integers (see [JSON scope](json.md)).

<a id="1-the-changes"></a>

## Library scope

Ship libraries for useful Python tools, data processing and representative CPU workloads.
A supported subset needs a working API with differential tests; import-only success,
throwing placeholders or tables for another interpreter are insufficient reasons to add it.
Keep general library dependencies even when their own API is bounded.

The following additions have been removed from the shipped distribution:

| Removed surface | Reason |
|---|---|
| `opcode`, `_opcode` and generated tables | Describe CPython bytecode; no shipped application consumer or native `dis` workflow. |
| `_imp` | Lock bookkeeping and capability queries did not provide runtime module loading or a working `importlib` workflow. |
| `_ast` | Constructor-only expression nodes had no parser, AST compilation or shipped application consumer. |
| `pyaes` port | Block-only `list[int]` API omitted cipher modes, padding and streaming. |
| `pyfiglet` port | Three embedded fonts without font discovery or a working upstream CLI. |

This deliberately reduces compatibility: programs using those former adapters need a
separate implementation or CPython. Their earlier test results remain historical evidence.
The former `pyaes` and `pyfiglet` sources remain in Git history; the ports wheel now omits them.

Retain `gettext`'s existing bounded surface; further localization work needs a working CLI
consumer. Core collection, parsing, configuration, I/O, text and numeric libraries remain
in scope. Domain-specific numeric ports can serve reproducible CPU workloads, but their
scope and adaptations must stay explicit. See the [port guide](../ports/README.md).

## Porting a library

Start with a useful API and a small application that exercises it. Compile that program,
then compare its result with CPython in both JIT and AOT modes. Add regression tests for
errors and edge cases before expanding coverage.

Prefer changes that preserve the upstream algorithm:

- Annotate empty containers, optional fields and public interfaces where inference needs help.
- Replace a dynamic object shape with a typed class, tuple or optional value when its contract
  can be preserved.
- Make unavailable accelerator imports optional, retaining the pure-Python fallback.
- Adapt unsupported expressions locally; leave unused unsupported APIs in the source when
  [deferred compilation](language/modules.md#unsupported-code-in-imported-modules) permits it.
- Mark each adaptation and record the source version, SHA-256, API limits and test evidence.

Unannotated functions and constructors can specialize for the types of their calls.
Recognized import-time guards select supported platform and fallback branches. These features
reduce port edits, but they do not make arbitrary dynamic code statically typable.

An adapted file passing upstream tests under CPython verifies the adaptation's Python behavior.
It does not prove that the compiled implementation passes those same tests. Record these
results separately, and use [differential tests](testing.md#differential-tests) for compiled APIs.

Third-party adaptations live in [ports/](../ports/). Each port's `PORT.md` describes its supported
surface and changes. Application examples show these libraries in use; the
[caching guide](caching.md) covers routing, memoization and their benchmarks.

<a id="32-what-keeps-the-rest-out"></a>
<a id="6-what-it-would-take-to-compile-more"></a>

## Remaining limits

Language features limit library coverage most: general multiple inheritance and subclasses of generic
(template) classes, arbitrary recursive value types, `bytearray` and `memoryview`, dynamic
reflection and unrestricted argument expansion. Runtime-typed values exist only in modules that
opt in to the [dynamic `Any` prototype](dynamic-any.md); its [operations](dynamic-any.md#operations)
and [iteration](dynamic-any.md#iteration) contracts list what such ports can rely on.
Its bounded [class-value prototype](dynamic-any.md#class-values-and-type-keyed-registries)
supports exact-type callback registries and `factory(*args, **kwargs)` reconstruction through existing boxed
instance adapters and compiled initializers, plus factory-only construction of
isolated classes with a fixed annotated initializer and supported fields.
Differential consumers exercise the
selected `copyreg` registration functions and reduction tuples; full `copyreg` and `pickle` remain unsupported.
Generator functions, resumable generator objects, bytes, bounded unions and per-call
function/constructor specialization already work; their remaining restrictions depend on the
operation and the concrete types involved. CPython extensions and import graphs through
unavailable modules can block otherwise suitable pure-Python functions. The
[compatibility reference](language/compatibility.md) lists the detailed restrictions.

Prioritize a small port when it offers a useful application without requiring a broad dynamic
feature. Broader inference, generic typing, library coverage and optimizations remain areas of
work; the repository's [issues](https://github.com/den-run-ai/pystachy/issues) track individual gaps.
C calls, calls into an embedded CPython (`pyobj`) and experimental CPython extension builds
have their own [FFI guide](ffi.md).

<a id="2-method"></a>
<a id="7-reproducing"></a>

## Measuring coverage

These tools answer different questions:

| Check | What its result means |
|---|---|
| `tools/import_sweep.py` | A module's import program compiles; this does not verify its functions. |
| `tools/import_sweep.py --stubs` | A module's import compiles once the modules built into CPython that it needs exist; this ranks those modules. |
| `tests/programs/library/lib_*.py` | Selected compiled APIs match CPython in the differential suite. |
| `make port-check` | Pinned upstream sources, reviewed adaptation diffs and selected upstream suites pass under CPython; compiled coverage is tracked separately. |

With CPython's standard-library sources available, run from the repository root:

```sh
python3 tools/import_sweep.py -j 2 --metadata build/import-sweep-meta.json \
  ./pystachy /usr/lib/python3.13 build/import-sweep.json
python3 tools/import_sweep.py --overlay ./pystachy /usr/lib/python3.13 build/cpython-lib
python3 tools/import_sweep.py --stubs /usr/lib/python3.13 build/import-sweep-stubs.json
PYSTACHY_PATH=build/cpython-lib ./pystachy run prog.py
make test FILES="tests/programs/library/lib_*.py"
make port-check
```

Adjust the CPython source path for your installation. The overlay excludes names provided by
Pystachy's `lib/`, so CPython's own `re`, `functools` and other files do not hide the ports.
Source-feature counts cannot establish compiler coverage: functions with the same syntax
may specialize for different types, and unused imported functions may not be compiled.
The sweep reports excluded modules separately. Preserve the compiler revision, CPython version
and overlay policy with any result; compare sweeps only when their denominators agree.
Use `--metadata build/import-sweep-meta.json` on a sweep to retain its compiler-file hash,
source-repository revision, Python environment, overlay exclusions and result counts beside
the unchanged module-to-result JSON. The source revision describes the checkout; the
compiler hash identifies the executable and does not prove which sources built it.

A plain sweep reports each module's first error, so a module built into CPython that Pystachy
lacks hides the errors behind it. `--stubs` stands a stub in for each such module that some
module imports without an `ImportError` fallback, with the names the running CPython's module
has (its functions raise `NotImplementedError`), and compiles with this checkout's
CPython-hosted compiler. Its report counts, for each stub, the modules that import with it and
those that need no other stub: these would import once Pystachy had that module, as far as
their imports go. `--only NAME,...` stubs just those modules.

Earlier sweeps are dated snapshots; rerun them after compiler or library changes. The
[2026-10-17 compatibility audit](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/compatibility-2026-10-17.md)
records a pinned main revision, execution checks, package adaptations, suite boundaries and
remaining blockers, and later checkpoints are in the
[rolling log](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/compatibility-updates.md).
The [October 22 core sweep](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/stdlib-expansion-2026-10-22.md)
separates selected import results from executed APIs and lists the remaining blockers and
exclusions. Its [CPython-derived regression guide](../tests/upstream/core-sweep.md) records the
new heterogeneous JSON, dictionary, deque and context-diff cases; these are selected adapted
tests, not execution of CPython's complete test suite.

The [development tools index](../tools/README.md) lists maintained checks and measurement
entry points. Historical surveys and superseded tool implementations remain in Git history.
