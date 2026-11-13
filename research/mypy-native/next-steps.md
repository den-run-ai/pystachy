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

## The parser has no owner

mypy 2.4.1 parses with `ast_serialize` by default (`mypy/options.py:393`, `native_parser = True`):
a Rust extension (`mypyc/ast_serialize`, version 0.13.1 on PyPI, wheel SHA-256
`9f99786e0d62082a5b121b3437f3167562133711df22128de1e9886f57f0b226`) returns the tree as bytes, and
`mypy/nativeparse.py` (2,199 lines, about 80 node tags) reads them through `librt.internal`,
which #1276 ports. `mypy/fastparse.py` over `ast` is the fallback. The mypy-port session has a
throwing stand-in for `ast_serialize.parse()`. Nothing was built or run here; three routes:

| Route | Cost | Risk |
|---|---|---|
| Call the Rust crate through Pystachy's FFI, behind a small C-ABI wrapper | A Rust build for the port; the wheel itself only exports CPython's module entry | Upstream's own parser, so no drift; not checked that the crate separates parsing from its Python bindings |
| A parser in the subset that writes the same bytes | A full Python 3.14 tokenizer and parser plus the serializer, several thousand lines; the wheel is a byte-for-byte oracle under CPython | Follows every change of the format (`cache_version`) |
| A CPython-compatible `ast` module for `fastparse.py` | The same parser, plus about 100 node classes and dispatch by computed method names | The path mypy is leaving |

The compiler's own parser cannot serve as is: its `Node` keeps a line and no columns or end
positions (`src/pystachy_compiler/syntax.py`), and it rewrites what it parses.

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

## `librt.base64`

The mypy-port session confirmed that `librt.base64` was free. It is on branch
`claude/confident-einstein-ep3lh6-librt-base64`, stacked on #1276 (`lib/librt/`, the pinned
`librt==0.16.0` for recordings), and needs `binascii` only, not the `base64` branch.

librt 0.16.0's extension is not `base64` under another name. Read from its
`base64/librt_base64.c` (sdist SHA-256
`ac38d6d8d66bf3d744148dbbc0b8e193e195a51e364ed55e224631f5721891fc`) and confirmed against the wheel:

- It decodes what `base64.b64decode()` decodes, with the same results.
- Where `base64` raises `binascii.Error`, it raises a plain `ValueError("Incorrect padding")`,
  whatever `binascii`'s message is.
- One character followed by three or more padding characters at the end (`b"a==="`) raises
  `RuntimeError("base64_decode failed")`: the C code sets a `ValueError` and then overwrites it.
- An argument of another type raises `TypeError` with its own messages; the port raises the
  decoders' at run time and makes the encoders' a compile-time error.

`tools/librt_base64_check.py` on that branch runs the port on CPython beside the extension:
1,416,764 calls agree (`--rounds 200000 --seed 99`).

On that branch `import mypy.ipc` gets past line 22 and stops at `mypy/ipc.py:36`, `import socket`:
the next first error of those modules has no owner (issue #1310 asks for `socket`).

## `signal` needs a way to run handlers

The class-objects session's sweep of CPython's `Lib` (440 modules) finds `_signal` as the first
error of 29 modules, and asked whether this session takes it; it does. What main has:

- The runtime's SIGINT handler ends the program at once, printing `KeyboardInterrupt`
  (`runtime.c`, `on_sigint`), or notes the signal while the I/O layer is busy. Nothing raises an
  exception between two statements, so there is no point at which a Python handler could run.
- `_thread.interrupt_main()` raises `KeyboardInterrupt` for SIGINT and does nothing for other
  signals.
- `os.kill()` is not on main (#1385 adds process calls for `subprocess`).

So `signal.signal(sig, handler)` with a Python function needs new runtime work: a pending-signal
flag and places where compiled code tests it. A first step that needs none of that is the
module's constants and `Signals`, `SIG_DFL` and `SIG_IGN` set through `sigaction`,
`raise_signal()`, `strsignal()`, `valid_signals()` and `getsignal()`, with a Python handler
rejected. That covers `signal.SIGKILL` in `mypy/dmypy_os.py` and the imports of `subprocess`.
Signal numbers differ between Linux and macOS, so they come from the runtime. Not started.

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
