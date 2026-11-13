# Next steps after `inspect` and `concurrent.futures`

Written on 2026-11-13 against main `63e4e52d`, CPython 3.13.16 and mypy 2.4.1.

## Generic base classes are owned

The largest first error of the last sweep, `mypy/nodes.py:444` (114 modules), is not free work.

| Piece | Owner |
|---|---|
| `nodes.py:444`: `MypyFile` stores `defaultdict(set)` in its `__init__` and becomes a class template | #1277 (mypy-port session, branches `claude/gifted-ride-6d430y-*`) |
| Classes deriving from a specialized generic class, several generic bases, traits, implicit `Generic`, covariant overrides, `Iterator[...]` bases | #1298, #1335, #1350, #1352, #1373, #1391 (same session) |
| A hierarchy class whose `__init__` takes a class template (`TypeChecker(errors: Errors)`, mypyc's emitter classes) | #1415 and issue #1404 (hard-blockers session, branches `claude/blissful-hawking-ve4fwg-*`) |
| `set[None]`, `AbstractSet`, the shared `_EMPTY` frozensets of mypyc's dataflow | #1412, #1413 (same session) |
| `complex` | #1408, #1409 (mypy-port session) |

Sources: the open pull requests' descriptions and the mypy-port session's
`research/mypy-native/PROGRESS-2026-11-12.md` at `0ca56dba`. That file's last table of blockers
"that no other session owns" names `ast` as the only one left without a pull request.

## Standard-library modules mypy imports that are not shipped

A static census of `import` statements in mypy and mypyc outside their tests, against main's
`lib/` and builtin modules.

| Module | Imported by | State |
|---|---|---|
| `pprint`, `gc`, `platform`, `importlib` and its submodules, `sysconfig`, `subprocess`, `inspect`, `concurrent.futures` | the build path | #1344, #1351, #1356, #1365, #1371, #1385, #1417, #1416 |
| `hashlib` | `mypy/util.py`, `mypyc/build.py` | #1288 |
| `base64` (through `librt.base64`) | `mypy/ipc.py`, the daemon | `base64` on branch `claude/confident-einstein-ep3lh6-base64`; `librt.base64` needs #1276's `lib/librt/` |
| `configparser` | `mypy/config_parser.py` | none; see below |
| `ast` | `mypy/fastparse.py`, `evalexpr.py`, `modulefinder.py` | none; mypy 2.4.1 parses with `ast_serialize`, a Rust extension, by default (`options.py:393`) and falls back to `ast` |
| `socket` | `mypy/ipc.py` | none; issue #1310 asks for `socket` for HTTP clients |
| `signal` | `mypy/dmypy_os.py` (`signal.SIGKILL`) | none |
| `tokenize` | `mypy/report.py`, `stubdoc.py` | none; 3.13's `tokenize` wraps the C tokenizer |
| `pickle`, `sqlite3`, `resource`, `multiprocessing`, `queue`, `pkgutil`, `pdb`, `site`, `symtable`, `urllib.request`, `xml.sax.saxutils`, `_curses` | the daemon, reports, stubgen, stubtest, optional imports | none |

## `base64`

`lib/base64.py` adapts CPython 3.13.16's file: every function of `__all__`, for `bytes` data.
Under CPython the edited file passes the 40 tests of `test_base64`; 19 cases (30 checks) pass in
JIT/AOT, hosted and GC-stressed, and 3,000 pseudo-random inputs give CPython's checksum.

What the port had to replace is in [`probes/limits/base64/`](probes/limits/base64/), each
checked against main's compiler:

| Program | Limit |
|---|---|
| `r1_bytearray.py` | No `bytearray`. |
| `r2_int_from_bytes.py` | No `int.from_bytes()`; `int.to_bytes()` is missing too. `random.randbytes()` needs them (`bench/pyperformance/README.md`). |
| `r3_bytes_pattern.py` | `re` takes no bytes pattern. |
| `r4_function_doc.py` | A function's `__doc__` cannot be read. |
| `r5_function_level_import.py` | A function cannot import a module that module-level code does not import (`base64.main()`). |

## `configparser` waits for mapping wrappers

Issue #1328 lists `configparser` and `ChainMap` as remaining. A port that keeps CPython's
structure does not compile on main, for four reasons in
[`probes/limits/configparser/`](probes/limits/configparser/):

| Program | Limit | Tracked |
|---|---|---|
| `r1_mutablemapping_subclass.py` | A class cannot derive from `MutableMapping`: `RawConfigParser`, `SectionProxy` and `ConverterMapping` do, and take `keys()`, `items()`, `get()` and `update()` from it. | #256 (mapping wrappers) |
| `r2_object_sentinel_default.py` | `fallback=_UNSET` with `_UNSET = object()`: a function returning the fallback has two return types. | #1362 covers annotated parameters |
| `r3_str_subclass.py` | `class _Line(str)` with `__new__`. | none |
| `r4_chainmap.py` | No `collections.ChainMap` (`_unify_values`). | #256 |

mypy also holds the parser where `MutableMapping[str, Any]` is declared, beside a `dict` read
from TOML, and calls `section.getboolean()` on it: that needs dynamic dispatch as well as the
module. A port today would be a rewrite with its own mapping methods, not an adaptation.

## Other gaps met

- `sys.executable` is unsupported ([`probes/limits/sys_executable.py`](probes/limits/sys_executable.py)).
  What a native program should report is a contract question: CPython allows an empty string.
- `signal` is not shipped ([`probes/limits/signal_module.py`](probes/limits/signal_module.py)).
- #1418: a generic class named in a `def` annotation compiles `__repr__` before module globals
  are declared ([`probes/limits/futures/generic_annotation_globals_min.py`](probes/limits/futures/generic_annotation_globals_min.py)).
