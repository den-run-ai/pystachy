# Builtin-module prototypes — 2026-10-19

Four merges each add a CPython built-in module that Pystachy lacked:
[#644](https://github.com/den-run-ai/pystachy/pull/644) `_imp`,
[#645](https://github.com/den-run-ai/pystachy/pull/645) `_ast`,
[#646](https://github.com/den-run-ai/pystachy/pull/646) `select` and
[#648](https://github.com/den-run-ai/pystachy/pull/648) `_weakref`.
This checkpoint measures what they changed for the standard library, the 27 pinned
PyPI probes, test runners, pyperf and pyperformance. It also adds compiled upstream
tests for the new modules and ranks the blockers that now come first.

**Summary**

- The four modules are the lowest layer of their import chains, not library ports.
  Native stdlib imports go from **142 to 144 of 475** (`_py_abc` and `_weakrefset`),
  **165** first errors change, almost all to a later stop, and no import is lost.
- No PyPI probe, test runner, pyperf probe or pyperformance census result succeeds
  where it failed before. Each now stops at the next missing layer.
- [#491](https://github.com/den-run-ai/pystachy/issues/491) predicted this for
  `_imp`, whose dependents "stop at `_io` anyway": all 32 do.
- The main blockers now are `import weakref` (54 modules), `_io` (34), `_signal`
  (26), `_opcode` (24) and a few subset patterns. Once the C modules are stubbed,
  the subset patterns dominate. See [Main blockers](#main-blockers-now).
- Three new compiled upstream test files adapt **15 CPython test methods** (6
  complete, 9 partial). They run natively in JIT and AOT.

Main and [#678](https://github.com/den-run-ai/pystachy/pull/678), the follow-up to
these merges, give the same result in every measurement here:

- 522 of 522 native and 522 of 522 stub-assisted module results;
- 27 of 27 package probes;
- 5 of 5 harness probes;
- 52 of 52 census rows.

#678 changes what the new modules do, not which imports reach them.
[Evidence](compatibility-2026-10-19-prototypes.json) holds the commands, inputs and
hashes, every per-module result, the transitions and the scripts.

## Revisions and inputs

| Item | Value |
|---|---|
| Main | [`2359de69`](https://github.com/den-run-ai/pystachy/commit/2359de695e2668a6b9d72519d195680ee0661c38), after #644, #645, #646, #648 and [#677](https://github.com/den-run-ai/pystachy/pull/677). #677 changes CI and DCO files only, so `lib/`, `src/` and the runtime equal those at `bb5ac4ab`, the #648 merge. |
| Before the four merges | [`a355c83f`](https://github.com/den-run-ai/pystachy/commit/a355c83ff7b60b64e3264867593064c3da9611a5) (#667). The first-parent merges after it are exactly #644, #645, #646, #648 and #677. |
| Previous import sweep | [`3f6f42c7`](https://github.com/den-run-ai/pystachy/commit/3f6f42c7648b952940ca806fc711d59314ee381a) ([evidence](compatibility-2026-10-18-list-repeat.json)): 142/475 native, 146/475 stub-assisted |
| Previous package and benchmark audit | `d3fbfc6f` ([packages](compatibility-2026-10-17-packages.md), [benchmarks](compatibility-2026-10-17-benchmarks.md)) |
| #678 head | `8eda0b87` |
| Toolchain | CPython 3.13.16 (`/usr/bin/python3.13`), LLVM 18.1.3, Ubuntu 24.04 x86-64, 4 CPUs. Every compiler was built from its revision; the fixed points hold. |
| Stdlib input | The 522-module inventory, 47 overlay exclusions and the same skipped directories. 521 module sources are byte-identical to the previous sweep's. `ssl.py` is CPython's upstream file and differs from the previous sweep's copy; its result is the same. Ubuntu ships `tkinter` separately; see [Caveats](#caveats). |
| Packages | The 2026-10-17 audit's 27 probes, its sdists (SHA-256 checked) and dependency versions. numpy 2.3.5, pandas 2.2.3 and pydantic 2.13.5 come from wheels. Their `__init__.py` hashes equal those of the audit's installed copies. |
| Harness and census | pyperf 2.10.0, pyperformance 1.14.0 (sdist SHA-256 `91f74393…a8aa`) and pytest 8.4.2: the archives and probe programs of 2026-10-17 |

## What the merges changed

### Standard-library imports

| Sweep | `3f6f42c7` | `a355c83f` | `2359de69` main, and #678 |
|---|---:|---:|---:|
| Native imports | 142/475 | 142/475 | **144/475** |
| Stub-assisted imports | 146/475 (4 need stubs) | 146/475 (4 need stubs) | **146/475** (2 need stubs) |

From `3f6f42c7` to `a355c83f`, every module's result is the same in both sweeps
except `turtle`'s, which is an input difference (see [Caveats](#caveats)). The
changes below are measured from `a355c83f` with the same input, so each comes from
one of the four merges.

Native first errors that moved, by the module that now loads (165 modules):

| Merge | Modules | First error before → now |
|---|---:|---|
| #648 `_weakref` | 2 | `_py_abc`, `_weakrefset` now **import** |
| #648 `_weakref` | 45 | `_weakrefset.py:5` (`_weakref`) → `_signal` 23, `_ctypes` 11, `warnings.py:262` 6, `_zoneinfo` 4, `_tokenize` 1 |
| #648 `_weakref` | 54 | `weakref.py:12`, module `_weakref` → the same line, missing name `getweakrefcount` |
| #644 `_imp` | 32 | `importlib/__init__.py:12` → `_io` at `importlib/_bootstrap_external.py:27` |
| #645 `_ast` | 31 | `ast.py:25` → `_opcode` 21, `enum.FlagBoundary` 6, `_io` 2, `termios` 1, a generic base class in `_pyrepl` 1 |
| #646 `select` | 3 | `selectors` → `hasattr(select, 'poll')` (line 412); `pty` → `termios`; `_pyrepl.unix_console` → `_signal` |

The other results are unchanged:

- 80 failures are identical.
- 86 differ only in the error text, whose list of built-in modules now includes `select`.
- 142 imports succeed in both sweeps, and 47 modules are excluded.

The stub-assisted count stays at 146 for a different reason. `--stubs` stubs only
C modules without a stand-in, and `_weakref` now has one. The six names `weakref.py`
imports that the stand-in lacks therefore stop **99** imports earlier, at
`weakref.py:12`: `getweakrefcount`, `getweakrefs`, `proxy`, `ProxyType`,
`CallableProxyType` and `_remove_dead_weakref`.

A diagnostic sweep shows that the names alone unlock no import. It ran on a scratch
worktree whose `_weakref` stand-in also has throwing stubs for the six names. The 99
imports then reach exactly the stops they had before the merges:

- `inspect.py:1725`: 42 (a namedtuple with computed field names);
- `socket.py:53`: 37 (`socketpair` bound both as a variable and by an import);
- `weakref.py:28`: 8 (`ProxyTypes = (ProxyType, CallableProxyType)`, classes as values);
- 12 more, in six smaller groups.

| Module | Before the merges | Now |
|---|---|---|
| `unittest`, `inspect`, `doctest`, `pdb` | `ast.py:25` `_ast` | `opcode.py:12` `_opcode` |
| `importlib`, `importlib.util`, `zipfile` | `importlib/__init__.py:12` `_imp` | `_io` |
| `copy`, `logging`, `asyncio`, `concurrent.futures`, `hashlib`, `weakref` | `weakref.py:12` `_weakref` | `weakref.py:12` `getweakrefcount` |
| `threading`, `queue` | `_weakrefset.py:5` `_weakref` | `warnings.py:262` |
| `multiprocessing`, `zoneinfo` | `_weakrefset.py:5` `_weakref` | `_signal`, `_zoneinfo` |
| `selectors` | `selectors.py:12` `select` | `selectors.py:412` `hasattr(select, 'poll')` |
| `ast` | `ast.py:25` `_ast` | `enum.py:1412` `FlagBoundary`, a `StrEnum` (bases `str` and `ReprEnum`) |
| `_py_abc`, `_weakrefset` | `_weakrefset.py:5` | **import** |
| Unchanged | | `argparse` (`sys.base_prefix` in `gettext`), `traceback` (`warnings.py:220`), `json` (`c_scanstring`), `decimal`/`fractions` (`_contextvars`), `pickle` (`copyreg`), `subprocess` (`_signal`), `socket` (`_socket`), `pathlib`/`glob` (`os.O_RDONLY`). `typing`, `dataclasses`, `tempfile`, `email` and `abc` still import. |

### PyPI package probes

The probes rerun the 2026-10-17 configuration: the package root, its pinned
dependencies and the shipped `lib/`. **Every first error is the same as on
2026-10-17**, on main and on #678. `sgp4` is still the only probe whose program
compiles. CPython runs all 27 probes.

A second, new configuration adds the CPython 3.13.16 stdlib overlay. It shows what
each package hits once the stdlib modules that `lib/` lacks are found:

| Package | Shipped `lib/` | With the CPython stdlib |
|---|---|---|
| requests 2.34.2 | no `warnings` | `weakref.py:12` `getweakrefcount` |
| pyaes 1.6.1 | no `copy` | `weakref.py:12` `getweakrefcount` |
| attrs 26.1.0 | no `inspect` | `_opcode` |
| pytest 9.1.1 | no `ast` | `_opcode` |
| click 8.5.0 | no `enum` | `_opcode` |
| pyfiglet 1.0.4, six 1.17.0, pydantic 2.13.5 | no `importlib` | `_io` |
| wcwidth 0.9.2 | no `enum` | `_io` |
| packaging 26.3 | no `warnings` | `warnings.py:220`: `re` imported under one `if` and read under another |
| roman 5.2 | no `argparse` | `gettext.py:62` `sys.base_prefix` |
| convertdate 2.5.1 | no `calendar` | `locale.py:109`: `localeconv` redefined |
| sortedcontainers 2.4.0 | no `traceback` | `sortedlist.py:41`: `from itertools import imap` under `if hexversion < 0x03000000` |
| numpy 2.3.5 | no `warnings` | `_multiarray_umath`, a C extension |
| pandas 2.2.3 | no `warnings` | `pickle.PickleBuffer`, which needs the C `_pickle` |

In both configurations, 11 probes stop first in their own source:

| Package | First error |
|---|---|
| pylev | `xrange` |
| jdcal | an `int` parameter given a `float` |
| snowballstemmer | a class attribute built by calling `Among()` |
| tomli-w | `types.MappingProxyType` |
| qrcode | the optional `PIL` import |
| ordered-set | `slice(None)` |
| iniconfig | `\N{...}` escapes |
| sqids | `tuple()` of a set |
| cachetools | a `tuple` subclass |
| boltons | a class inside a function |
| more-itertools | `functools.cached_property` |

### Test runners and pyperf

| Probe (IR compilation) | 2026-10-17 (`d3fbfc6f`) | Now |
|---|---|---|
| `import pyperf` (2.10.0) | `pyperf/_utils.py:4`: `select` | `contextvars.py:1`: `_contextvars` |
| pyperformance 1.14.0 CLI | `importlib`: `_imp` | `importlib/_bootstrap_external.py:27`: `_io` |
| `import pytest` (8.4.2) | `ast.py:25`: `_ast` | `opcode.py:12`: `_opcode` |
| `unittest.main()` program; unmodified `test_fnmatch.py` | `unittest/util.py:3`: `namedtuple` | `opcode.py:12`: `_opcode` |

Two merges explain the unittest row:
[#601](https://github.com/den-run-ai/pystachy/pull/601) added `namedtuple`, and #645
moved the next stop past `_ast`. None of these tools runs natively yet. pyperf and
pytest still need to run on CPython, driving native executables, as
`tools/bench_pyperformance.py` does.

### pyperformance

The census replaces each benchmark's pyperf runner and uses the shipped ports. On
main and on #678 the same **6 of 52** compile: `fannkuch`, `generators`, `nbody`,
`nqueens`, `regex_v8` and `unpack_sequence`.

A new diagnostic adds the CPython stdlib overlay. The same six compile, and the
others stop at:

| First error | Benchmarks |
|---|---|
| `weakref.py:12` | 6: `async_tree`, `asyncio_tcp`, `deepcopy`, `logging`, `pyflate`, `xml_etree` |
| `_contextvars` | 4: `decimal_factorial`, `decimal_pi`, `mdp`, `telco` |
| `_signal` | 3: `2to3`, `concurrent_imap`, `python_startup` |
| json `c_scanstring` | 2 |
| `gc` | 2 |
| `array` | 2 |
| one benchmark each | 27: 22 in the benchmark's own source (async functions, inference, inheritance and others), 5 in the stdlib or `lib/` (`_bz2`, `copyreg`, `pprint`, `_sqlite3`, `int.to_bytes`) |

No benchmark source imports `weakref`, `select`, `ast` or `_imp`: none of the 151
Python files under `data-files/benchmarks` does. The only near case is
`bm_xml_etree`, which calls `importlib.import_module` inside a function.

The merges therefore make no new benchmark adaptable by themselves. The six that
stop at `weakref.py:12` reach it through `copy` (deepcopy), `logging` (logging, and
pyflate through `hashlib`), `asyncio` (async_tree, asyncio_tcp) and
`xml.etree.ElementTree` (xml_etree).

## Compiled upstream tests added

These are CPython 3.13.16 test methods (commit `cbc944f4`) adapted to the subset,
in the style of the other `tests/upstream_*.py` files. Each header pins the source
file's SHA-256 and lists every excluded case and why. A complete method keeps every
upstream assertion, with any setup changes disclosed. The tests belong to the normal
corpus, so CI runs them in every verification group.

| Test | Upstream methods | Complete | Partial | `assert` statements |
|---|---|---:|---:|---:|
| `tests/upstream_weakref.py` | `test_weakref.py`: `test_basic_ref`, `test_ref_repr`, `test_equality`, `test_hashing`, `ModuleTestCase.test_names`, libreftest's dead-reference example | 2 | 4 | 24 |
| `tests/upstream_select.py` | `test_select.py`: `test_error_conditions`, `test_errno`, `test_returned_list_identity` | 2 | 1 | 5 |
| `tests/upstream_ast.py` | `test_ast/test_ast.py`: `test_AST_objects`, `test_classattrs`, `test_constant_subclasses`, `test_nodeclasses`, `test_no_fields`, `ASTConstructorTests.test_expr_context` | 2 | 4 | 28 |

The main adaptations:

- **Collection.** Upstream drops a referent's last owner and calls `gc.collect()`.
  Here a cohort of 64 referents dies, and the test checks upstream's assertions on
  every reference whose referent died; at least one must. The collector is
  conservative, so a stale stack word can keep a referent alive.
- **Static rejections.** CPython raises TypeErrors at run time for calls such as
  `select.select(1, 2, 3)` and `ast.AST(2)`. Here such calls are compile-time
  errors, so they are excluded. The `tests/errors/lib_select_*` and `lib_ast_*`
  fixtures cover similar calls.
- **Classes as values.** `issubclass(ast.Name, ast.expr)` and `getattr(weakref, name)`
  need [#7](https://github.com/den-run-ai/pystachy/issues/7), so they are excluded.

CPython 3.13.16 recorded the expected output. All three tests pass in JIT and AOT,
both normally and with `PYSTACHY_GC_STRESS_PROGRAM=1` and `PYSTACHY_OPT=-all`, and
with the CPython-hosted compiler.

## Main blockers now

### Standard library

These are first errors. Each can hide later blockers, so a count is not a projected
import gain. "Stubs" is the stub-assisted sweep; "diag." adds stubs for the six
missing `_weakref` names.

| First error | Native | Stubs | Diag. | What it needs |
|---|---:|---:|---:|---|
| `weakref.py:12`: six `_weakref` names missing | 54 | 99 | — | The names, then classes as values for `ProxyTypes` (`weakref.py:28`, #7), then reference callbacks and `WeakMethod`'s `__new__` |
| `_io` (`importlib/_bootstrap_external.py:27`) | 34 | — | — | An `_io` stand-in over the shipped `io`; then `importlib/_bootstrap.py:37`, a module global first set to `None` (9 under stubs) |
| `_signal` (`signal.py:1`) | 26 | — | — | `_signal`; under stubs, `signal` then stops at `enum.py:1412` |
| `_opcode` (`opcode.py:12`) | 24 | — | — | An `_opcode` stand-in. `opcode.py` uses 11 of its 15 names at import: opcode-property tests, intrinsic and binary-operator descriptions, and `stack_effect`. Under stubs, `inspect` and its users then stop at `inspect.py:1725` |
| `socket.py:53`: `socketpair` bound by a variable and an import | — | 31 | 68 | Conditional definitions and imports, [#611](https://github.com/den-run-ai/pystachy/issues/611); also behind `_socket` (8 native) |
| `inspect.py:1725`: namedtuple of computed field names | — | — | 42 | [#256](https://github.com/den-run-ai/pystachy/issues/256) |
| `email/charset.py:99`: dict of `None` values | 16 | 16 | 16 | Inference of a dict whose values are all `None` |
| `_ctypes` | 11 | 11 | 11 | — |
| `enum.py:1412` `FlagBoundary` | 9 | 13 | 13 | Full `enum`, [#610](https://github.com/den-run-ai/pystachy/issues/610) |
| `pyexpat` | 9 | — | — | Vendored expat (#491) |
| `warnings.py:262` and `:220`: names bound by imports | 13 | 13 | 16 | #611 |
| `_contextvars` | 7 | 7 | 7 | Blocks `decimal`, `fractions` and pyperf |
| `_bz2` | 7 | 10 | 10 | — |

Smaller groups:

| First error | Modules |
|---|---:|
| `_dbm` | 5 |
| json `c_scanstring` set to `None` | 5 |
| `copyreg`, for `pickle` | 4 |
| `os.O_RDONLY`, for `glob` and `pathlib` | 4 |
| `types.MappingProxyType`, for `tomllib` | 4 |
| `_zoneinfo` | 4 |
| `locale.localeconv` redefined | 3 |
| `sys.base_prefix`, for `argparse` | 3 |

Two kinds of blocker remain:

- **Missing C modules:** `_io`, `_signal`, `_opcode`, `_ctypes`, `pyexpat`, `_socket`,
  `_contextvars` and `_bz2`.
- **Subset patterns in pure-Python stdlib code:** conditional import bindings, enum,
  `None`-initialized globals and dicts, classes as values and computed namedtuple
  fields.

The stub and diagnostic sweeps remove the C-module stops, and then the subset
patterns lead. `unittest`, `doctest` and pytest sit behind several of these at once.
`inspect` alone imports `ast` (enum), `dis` (`_opcode`), `importlib.machinery` (`_io`),
`tokenize` (`_tokenize`) and `weakref`, and has its own namedtuple at line 1725.

### PyPI packages

- **With the shipped `lib/`:** the first stop is a stdlib module that `lib/` does
  not ship:
  - `warnings`: requests, packaging, numpy, pandas;
  - `importlib`: six, pyfiglet, pydantic;
  - `enum`: click, wcwidth;
  - one probe each: `inspect`, `ast`, `copy`, `traceback`, `calendar`, `argparse`.
- **With CPython's own modules:** the packages reach the stdlib blockers above:
  - `_io`: 4;
  - `_opcode`: 3;
  - `weakref.py:12`: 2;
  - one each: `warnings.py:220`, `gettext`, `locale`.
- **In their own source:** 11 probes stop at a subset gap first; see the table above.
- **C extensions:** numpy, pandas and pydantic-core need an extension strategy, not
  stdlib work. #170's CPython embedding is a separate, opt-in route.

## Next steps, by measured reach

1. **`_opcode`.** A stand-in for the 11 names `opcode.py` uses at import, with
   CPython 3.13's opcode tables generated at build time as `tools/re_tables.py` does
   for `re`. It moves 24 native stops, including `dis`, `inspect`, `unittest`,
   `doctest`, `pdb`, pytest, attrs and click. Behind it, `inspect` stops at #256's
   computed namedtuple, and its other imports need `enum` (#610), `_io` and
   `_tokenize`.
2. **`_io`.** A stand-in re-exporting the shipped `io` classes moves 34 native stops,
   including `importlib` and `zipfile`, and four packages. Then importlib needs a
   module global first set to `None` and later assigned a module.
3. **`import weakref`.** This is the largest group: 54 native modules, 2 packages and
   6 benchmarks. The diagnostic shows that the missing names alone unlock nothing.
   Classes as values (#7) come next, then callbacks for `WeakValueDictionary`,
   `WeakKeyDictionary` and `finalize`. An adapted `lib/weakref.py` with documented
   limits is the shorter route.
4. **Conditional definitions and imports (#611).** `socket.py:53` (68 in the
   diagnostic) and `warnings.py` (16) lead once the C modules are stubbed. A version
   or platform branch blocks sortedcontainers and, under stubs, `subprocess`
   (`import _winapi` under `if _mswindows`) the same way.
5. **Smaller C modules.** `_signal` (26) and a single-thread `_contextvars` (7:
   `decimal`, `fractions`, pyperf).

## Validation

- `make PY=/usr/bin/python3.13`: compiler and runtime fixed points. The rebuilt
  `./pystachy` has SHA-256 `0cb9520e…7d57`, the same as the binary of the #678 sweep.
- New tests: `tests/run.sh ./pystachy "jit aot"` gives 6 of 6. So does each of
  `PYSTACHY_GC_STRESS_PROGRAM=1`, `PYSTACHY_OPT=-all` and `make test-py`.
- `make check-recordings`: 1,251 recordings and 76 deviations, 0 failed.
- `ruff check` passes. `shellcheck` is not installed, and no shell script changed.
- #678's earlier native, opt-off, GC-stress and contract runs, and its 32 CI checks,
  cover the implementation, which these tests and reports do not change.
- Not run: full `make verify` on this head, CPython's regrtest, timing benchmarks.

## Caveats

- **Imports are IR compilation.** A successful import does not show that a module
  works, and stub-assisted imports are diagnoses, not implementations.
- **`turtle`.** Ubuntu ships `tkinter` separately, so the directory is absent from
  this input. The sweeps skip `tkinter/` either way. With the previous sweep's input,
  `turtle` stopped at `tkinter/__init__.py:38` (`_tkinter`); with this one it stops
  at `turtle.py:38` at every revision measured here. This is an input difference,
  not a compiler change.
- **`ssl`.** This run's `ssl.py` equals CPython's `v3.13.16` file; the previous
  sweep's distribution copy differed. `ssl` stops at `ssl.py:100` (`_ssl`) in both.
- **pandas and pydantic.** The first package run lacked pydantic and pandas'
  `pytz` and `dateutil`. They were installed to a separate directory and those two
  probes were rerun; the evidence keeps both runs' setup.
