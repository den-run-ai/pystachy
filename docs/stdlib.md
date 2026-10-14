# Libraries and porting

Pystachy reuses existing Python library code where it fits the typed subset. Some shipped
modules are unchanged CPython sources, some have localized edits, and others are implemented
in the subset. All remain valid Python. Importing a module does not imply that every API works.

The [library reference](../lib/README.md) records supported APIs, provenance, upstream hashes,
adaptations, deviations and tests. The [language guide](language.md) explains the subset;
[imports and builtins](language/modules.md) covers module search and compiler-provided APIs.

<a id="the-standard-library-and-popular-packages-under-pystachy"></a>
<a id="summary"></a>
<a id="3-the-standard-library"></a>
<a id="31-what-compiles-and-runs-unmodified"></a>

## Shipped coverage

| Approach | Modules and useful APIs |
|---|---|
| Unchanged CPython sources | `bisect`, `colorsys`, selected `operator` functions, `stat` constants and predicates, path-string helpers from `posixpath` / `genericpath`, `curses.ascii`, `this` |
| Localized CPython ports | `heapq` selection helpers, `difflib.SequenceMatcher`, `getopt`, `fnmatch`, `textwrap`, `string.Template`, selected `statistics` operations, `urllib.parse` |
| Larger port | `re`: CPython's Python parser/compiler plus a matcher adapted from its C engine |
| Subset implementations | `functools.cache` / `lru_cache`, `io.StringIO`, `csv` |

The library reference is the authority for each module's limits. For example, `difflib`
supports matching strings and lists of strings, while its generator-based diff APIs do not
compile. `textwrap` supports its public operations, but widths count UTF-8 bytes.

Selected APIs from `sys`, `os`, `math`, `time`, `errno` and `tempfile` are compiler builtins.
`typing`, `collections.abc` and `dataclasses` also have compiler support; this does not provide
the full dynamic `collections` package. See the [builtin module table](language/modules.md#builtin-modules-and-files).

<a id="1-the-changes"></a>

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

General inheritance, arbitrary unions and `Any`, generator functions and first-class
generator objects, `bytes`, dynamic reflection and unrestricted argument expansion still
limit library coverage. CPython extensions and import
graphs through unavailable modules can block otherwise suitable pure-Python functions.
The [compatibility reference](language/compatibility.md) lists the detailed restrictions.

Prioritize a small port when it offers a useful application without requiring a broad dynamic
feature. Broader inference, generic typing, library coverage and optimizations remain areas of
work; the repository's [issues](https://github.com/den-run-ai/pystachy/issues) track individual gaps.
C calls and experimental CPython extension builds have their own [FFI guide](ffi.md).

<a id="2-method"></a>
<a id="7-reproducing"></a>

## Measuring coverage

These tools answer different questions:

| Check | What its result means |
|---|---|
| `tools/census.py` | Historical source-feature heuristic; inspect candidates, then verify with the current compiler. |
| `tools/import_sweep.py` | A module's import program compiles; this does not verify its functions. |
| `tests/lib_*.py` | Selected compiled APIs match CPython in the differential suite. |
| Upstream tests on an adapted file under CPython | The adaptations preserve the tested Python behavior. |

With CPython's standard-library sources available, run from the repository root:

```sh
python3 -I tools/census.py cpython=/usr/lib/python3.13 --json build/census.json
python3 tools/import_sweep.py ./pystachy /usr/lib/python3.13 build/import-sweep.json
python3 tools/import_sweep.py --overlay ./pystachy /usr/lib/python3.13 build/cpython-lib
PYSTACHY_PATH=build/cpython-lib ./pystachy run prog.py
make test FILES="tests/lib_*.py"
```

Adjust the CPython source path for your installation. The overlay excludes names provided by
Pystachy's `lib/`, so CPython's own `re`, `functools` and other files do not hide the ports.
The census model predates shipped features and can flag constructs now supported; its
results do not measure current compiler coverage.
The sweep reports excluded modules separately. Preserve the compiler revision, CPython version
and overlay policy with any result; compare sweeps only when their denominators agree.

<a id="4-pypys-pure-python-modules"></a>
<a id="5-popular-packages"></a>

## Earlier surveys

The [October 2026 survey](archive/stdlib-survey.md) retains the original CPython, PyPy and PyPI
measurements and feature projections. It predates many shipped features and ports, including
class templates, exceptions, optional types, sets, closures and caching. Its package verdicts
and projected percentages describe those recorded revisions, not current support.
