# The standard library and popular packages under Pystachy

An evaluation of how much of CPython's standard library, of PyPy's pure-Python modules and of
popular PyPI packages Pystachy can compile and run, what the minimal compiler and runtime
changes for that were, and what it would take to compile more. Measured in October 2026 with
CPython 3.13.16, PyPy 3.11 (`py3.11` branch, October 2026) and LLVM 18, on this repository's
`claude/stdlib-modules` branch.

## Summary

- **Before these changes, nothing from the standard library compiled.** Pystachy required
  annotations on every parameter, and the standard library has almost none (103 of its 2,411
  module-level functions with parameters annotate them all); and a program could not import
  Python modules at all.
- **The minimal changes (below) are compiler-side, plus two tiny builtin modules.** Importing
  modules, compiling unannotated functions as templates per call signature, deciding at compile
  time what CPython decides at import time (optional C accelerators, `__main__` guards,
  platform tests, `isinstance`/`hasattr`/`is None` on statically typed values), deferring every
  unsupported construct to the point where it is compiled, typing empty containers from their
  first use, and `for`/`while ... else`. In the runtime: `time` and `errno`, and
  `sys.platform`.
- **With them, these CPython 3.13 modules compile unmodified and print what CPython prints**
  (vendored byte for byte in `lib/`, each with a differential test): `bisect`, `colorsys`,
  `heapq` (its core), `operator` (its functions), `stat`, `posixpath` and `genericpath` (the path
  string functions), `this` and `curses.ascii`. On a harness of 189 small programs over 25
  candidate modules (written by an independent research pass), 65 compile from the unmodified
  sources and all 65 print what CPython prints; none prints something different.
- **The ceiling is the import graph, not individual functions.** Only 35 of 519 standard
  library modules can be imported. Most import, within a few hops, a C module (`_weakref` blocks
  177 modules: `abc` → `_py_abc` → `_weakrefset` → `_weakref`; `_codecs` 89, `_io` 43, `_thread`
  38) or a hub whose module-level code is dynamic (`_collections_abc`, `enum`, `typing`
  internals, `re`). Replacing all 97 C modules with stubs raises the count only from 35 to 37:
  the next layer is module-level dynamic code.
- **PyPy's `lib_pypy` is not a useful source:** its pure-Python files are mostly fallbacks PyPy
  itself does not run (hashes, `_collections`, `_marshal`, which is broken on Python 3), or
  PyPy-internal glue. CPython's own pure modules are the better source, and are tested against
  their C twins. PyPy is useful as an algorithm reference: ports of its MD5/SHA-1/SHA-256/
  SHA-512 and of RPython's Mersenne Twister to the Pystachy subset compile today and match
  `hashlib` and `random.Random` exactly (§4).
- **Popular packages:** see §5.
- **The next critical changes, by measured payoff** (§6): classes as templates (unannotated
  methods) with class attributes, single inheritance and `@property`/`@staticmethod`/
  `@classmethod`; then `try`/`except` with user exception classes; `%` formatting; `*args`
  per arity; `Optional` for `int`/`str`; function arguments (`key=`); `bytes`. For importability,
  small native shims (`_weakref`, `_thread` for one thread, `_io` over Pystachy's files,
  `itertools`, `binascii`) and support for the dynamic module-level code of `_collections_abc`,
  `enum` and `re`.

## 1. The changes

Each change is in `pystachy.py` unless noted; the bootstrap fixed point holds (the compiler
still compiles itself) and every existing test passes with both compilers, JIT and AOT.

| change | why the standard library needs it | where |
|---|---|---|
| **Python modules and packages**: search path (program directory, `PYSTACHY_PATH`, `lib/`), packages and namespace packages, relative, star (`__all__`) and circular imports, module code run once at the first import, `from m import x` copying a variable | nothing else can be imported | `Loader` (module-level names become `module$name`, so code generation sees one program); `@init.<module>` functions |
| **Templates**: a module-level function with an unannotated parameter is compiled per list of argument types, lazily, with its return type taken from its first `return` | the standard library has no annotations (82% of its functions have unannotated parameters) | `Gen.instance`, which saves and restores the generator's per-function state |
| **Static tests**: `isinstance(x, T)`, `hasattr(x, "a")`, `x is None` and truth tests of `None` decided by `x`'s static type, and only the branch that runs is compiled; a `None` argument makes the parameter a constant that may get another type outside branches | `if isinstance(c, str):`, `if hi is None: hi = len(a)`, `if key is None:` dispatch | `Gen.static` |
| **What CPython decides at import time, decided at compile time**: `try: from _accel import * / except ImportError:` (62 modules), `if __name__ == "__main__":`, `if TYPE_CHECKING:`, `sys.platform`/`os.name` tests, module-level aliases (`bisect = bisect_right`), `f.__doc__ = g.__doc__` | optional C accelerators, platform branches | `Loader.simplify` |
| **Everything is parsed; unsupported constructs are errors where compiled**: `try`, `yield`, `lambda`, sets, comprehension forms, `*args`, decorators, base classes, `async`, `match`, bytes, complex, 65-bit literals | a module is usable when the program never reaches its unsupported code | the parser builds nodes; `UNSUPPORTED` holds the messages |
| **Lazy compilation of imported code**: every function and method of an imported module is compiled only if called; classes it cannot compile, function-level imports it cannot resolve, and default values it cannot evaluate are errors only where used | one bad helper would block a whole module | `Gen.program`, `Loader.later`, `Gen.default_problem` |
| **Empty containers typed by their first use**: `out = []` then `out.append(x)`, `d = {}` then `d[k] = v` (a dict's key kind is a placeholder in the IR until then), with a look-ahead for reads before the filling use | `result = []` is everywhere | `Gen.empty`, `fill`, `refine`, `lookahead` |
| `for`/`while ... else`; `del` of variables; `x is y or x == y` on numbers; the `builtins` module | `operator.indexOf`, `_pydatetime`'s cleanup, `operator.countOf`, `operator`'s imports | |
| **Runtime**: `time` (clocks, `sleep`), `errno`, `sys.platform`, `os` path constants, `os.fspath` | `import errno`/`import time` at the top of `posixpath`, `fnmatch`, `calendar`, `_pydatetime` | `runtime.c` (about 70 lines) |

The compiler grew from 4,423 to about 6,000 lines; `runtime.c` by about 70.

## 2. Method

- **Census** (`tools/census.py`): an AST scan of every function, method, class and module top
  level, tagging the syntactic features Pystachy rejects or treats specially. It reads source
  with `ast` only and never imports it.
- **Import sweep** (`tools/import_sweep.py`): compiles `import M` for each of the 519 modules
  of CPython 3.13's `Lib/` (without tests, `idlelib`, `tkinter`, ...) with `Lib/` on
  `PYSTACHY_PATH`, and records the first error.
- **Differential programs**: the `tests/lib_*.py` tests of the vendored modules, run JIT and AOT
  against CPython's output; and a harness of 189 programs over 25 candidate modules, each
  `import M`, a call, `print`, compiled from the unmodified sources and compared with CPython.
- **Research passes** for PyPy's `lib_pypy`, prior art in other static Python compilers, and
  PyPI packages, each written up with its evidence; their findings are summarised in §4–§5.
- **Adversarial probes** of the new features against CPython, each finding independently
  reproduced before it was fixed.

## 3. The standard library

### 3.1 What compiles and runs unmodified

| module | what works (checked against CPython) | what does not, and why |
|---|---|---|
| `bisect` | `bisect_left`, `bisect_right`, `insort_left`, `insort_right`, `bisect`, `insort`, with `lo`/`hi`, on ints, floats, strings, tuples, objects | `key=<function>` (functions are not values) |
| `colorsys` | all six conversions, with float or int arguments | — |
| `heapq` | `heappush`, `heappop`, `heapify`, `heapreplace`, `heappushpop` and the `_max` forms, on any ordered type | `merge` (a generator, `*iterables`), `nlargest`/`nsmallest` (`iter`, `key=`, `try`) |
| `operator` | 49 of its functions: arithmetic, bitwise, comparisons, `not_`/`truth`, `concat`, `contains`/`countOf`/`indexOf`, item access, the in-place forms, the dunder aliases | `attrgetter`, `itemgetter`, `methodcaller` (classes with `*args`), `call`, `length_hint`, `index` (`int.__index__`); in-place forms that change the type (`itruediv(1, 2)`) |
| `stat` | every constant, `S_IS*`, `S_IMODE`, `S_IFMT` | `filemode` (iterates a tuple of tuples of different lengths) |
| `posixpath` | `normcase`, `isabs`, `split`, `splitext`, `splitdrive`, `splitroot`, `basename`, `dirname`, `normpath`, the constants | `join`, `relpath`, `commonpath`, `commonprefix` (`try`, `*args`, `map`), `abspath`, `expanduser`, `expandvars` (`os.environ`, `re`), the file tests (`try`) |
| `genericpath` | what `posixpath` uses | `commonprefix` (`map`), `exists` & co (`try`) |
| `this` | the module (prints the Zen of Python) | — |
| `curses.ascii` | all 19 functions, with `str` or `int` arguments | CPython's `curses/__init__.py` (C `_curses`): `lib/curses/__init__.py` is a stand-in |

The research pass found 17 more modules that compile with 1 to 18 small edits each (`keyword`,
`token`, `html.entities`, `html.escape`, `string` constants and `capwords`, `xml.sax.saxutils`
escaping, `ntpath`'s string functions, the date helpers of `_pydatetime` and `calendar`,
`getopt`, `email.quoprimime`, `shlex.quote`, `difflib` and `statistics` helpers). The edits
are mostly an annotation on an empty container default, removing an unavailable import, or a
`%` format rewritten as an f-string.

### 3.2 What keeps the rest out

| layer | measurement | examples |
|---|---|---|
| imports of C modules | 35 of 519 modules import; the first missing module of the rest: `_weakref` 177, `_codecs` 89, `_io` 43, `_thread` 38, `_imp` 28, `binascii` 10, `pyexpat` 8 | `functools`, `re`, `collections`, `enum`, `textwrap`, `json`, `random`, `statistics`, `difflib` |
| dynamic module-level code | with stubs for all 97 C modules, 37 of 519 import; the next errors are bytes literals and `type()` at module level (`_collections_abc`, 120 modules), `struct`, `typing` internals | `_collections_abc` builds `bytes_iterator = type(iter(b''))` |
| classes | 6,162 of the 9,726 methods have unannotated parameters; inheritance, class attributes and decorators follow | `SequenceMatcher`, `TextWrapper`, `Fraction`, `Random`, `datetime`, `ipaddress` |
| function bodies | after the changes above, 40% of module-level functions have no syntactic blocker (10% before); the remaining blockers are spread thin | `try` (19.5% of functions), `%` formatting (9%), first-class functions (6%), `*args` (5%), `bytes` (7%) |

## 4. PyPy's pure-Python modules

PyPy 3.11's `lib_pypy` re-implements some C modules in Python, but:

- `_md5`, `_collections` and `_marshal` are shadowed by RPython builtins and not run by PyPy;
  `_marshal.py` fails all 150 differential checks on Python 3; `_collections.py` describes
  itself as "BOGUS ... provided only as documentation" and has a Python 3.4-era API.
- `_sha1`, `_sha256` and `_sha512` are fallbacks behind OpenSSL. Their output matches
  `hashlib`, but their `copy()` shares state, and they use lambdas, metaclasses, inheritance,
  bytes and (SHA-512) unsigned 64-bit arithmetic.
- `_structseq`, `_contextvars`, `_immutables_map` and `_pypy_generic_alias` are PyPy-internal
  object-model glue; `audioop` and `__decimal` are cffi wrappers.

PyPy itself runs CPython's pure-Python modules (`heapq`, `bisect`, `_pydecimal`, `functools`'
fallbacks), which CPython tests against their C twins: they are the better source, and they
are what `lib/` vendors. PyPy is useful as an algorithm reference. Two ports written in the
Pystachy subset compile with Pystachy as it was before these changes:

- MD5, SHA-1, SHA-256 and SHA-512 (294 lines, from PyPy's `_md5`/`_sha*`; SHA-512 keeps each
  64-bit word as two 32-bit halves): identical to `hashlib` on 321 messages × 4 algorithms;
  hashing 1 MB takes 0.13 s compiled against 5.6 s for the same code under CPython.
- Mersenne Twister (124 lines, from RPython's `rrandom.py` and CPython's `random.py`):
  `seed`, `random()`, `randrange` and `shuffle` identical to `random.Random(seed)`.

Neither is a drop-in `hashlib` or `random` (they take `list[int]` bytes and return hex
strings); a drop-in needs `bytes` and classes as templates.

## 5. Popular packages

See the end of this file: the PyPI survey is appended when it completes.

## 6. What it would take to compile more

The order is from the census (greedy: each step unlocks the most further functions and methods
of the 12,566 in CPython 3.13's `Lib/`), cross-checked by the compiler on the harness, and
from what other static Python compilers needed first (Shed Skin, Codon, RPython, Numba,
Pythran, mypyc all infer types for unannotated code and fold type tests statically, as
Pystachy now does; every one that runs library code then added exceptions).

| step | change | functions and methods with no blocker left |
|---:|---|---:|
| | today (after the changes above) | 3,169 (25%) |
| 1 | **classes as templates**: methods with unannotated parameters compiled per call signature, a class's fields typed by its instantiation | 5,950 (47%) |
| 2 | **`try`/`except`/`else`/`finally`**, raising and catching builtin exceptions (LLVM `invoke`/landing pads, or an error flag checked after calls) | 6,405 (51%) |
| 3 | **`%` formatting** with a constant format string, and `str.format` (compiled into the existing format-spec machinery) | 6,822 (54%) |
| 4 | **`@property`**, `@staticmethod`, `@classmethod` (static desugarings) | 7,224 (57%) |
| 5 | **`isinstance` at run time** over class hierarchies | 7,607 (61%) |
| 6 | **user exception classes** (needs single inheritance from builtin exceptions) | 7,941 (63%) |
| 7 | **`bytes`** as a type sharing the byte-string runtime, with `encode`/`decode` | 8,250 (66%) |
| 8 | other **decorators** (`functools.lru_cache`, `contextlib.contextmanager`) | 8,509 (68%) |
| 9 | **single inheritance and `super()`** | 8,750 (70%) |

Further, in measured order of weight: `*args` specialised per arity (the arguments as a tuple
of the call's types, as RPython does), `with` on objects (`__enter__`/`__exit__` resolved
statically), first-class functions passed as arguments (`key=`, `map`, specialised as
compile-time constants of a template's instance), `Optional[int]`/`Optional[str]` (a null
pointer for `str` and containers, a flag and a value for scalars), generators (a heap frame
and a resume switch), sets on the dict table, and the missing `str`, `os` and `sys` API.

For importability, independently of the order above, the measured blockers are a handful of
C modules and dynamic hubs. Native shims for `_weakref` (strong references), `_thread` (one
thread), `_io` (over Pystachy's files), `itertools`, `binascii` and `_codecs` (UTF-8 and
Latin-1) would let the import graph reach `functools`, `abc`, `collections` and `codecs`; past
them, `_collections_abc` (bytes literals and `type()` at module level), `enum` (metaclasses)
and `re` (the `_sre` matching engine; CPython's `re/_parser.py` and `_compiler.py` are pure
Python, as PyPy's reuse of them shows) are the hubs that most of the library imports.

## 7. Reproducing

```
python3 -I tools/census.py cpython=/usr/lib/python3.13 --json build/census.json
python3 tools/import_sweep.py ./pystachy /usr/lib/python3.13 build/import-sweep.json
PYSTACHY_PATH=/usr/lib/python3.13 ./pystachy run prog.py   # compile against CPython's own Lib/
tests/run.sh ./pystachy                                     # includes tests/lib_*.py
```
