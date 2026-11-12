# `subprocess` and `inspect` for mypy: what other Pythons do, and what fits here

Date: 2026-11-12. Base: main `655bab5`. This note belongs to the research branch and is not
for main. The primary-source survey is in
[other-pythons-subprocess-inspect.md](other-pythons-subprocess-inspect.md); it was written by a
research agent from the projects' repositories at pinned commits, and three of its claims were
re-read here against the cited files (micropython-lib's `inspect.py`, PyPy's
`interp_subprocess.py`, GraalPy's `PosixSubprocessModuleBuiltins.java`). Nothing in it was
run.

## What the three implementations do

| | `subprocess` | `inspect` |
|---|---|---|
| MicroPython | None. A 0-byte dummy shipped from 2014 and was removed in 2020; the maintainers' answer is `os.system`. The unmaintained `unix-ffi/os` adds `fork`, `pipe`, `execvp`, `waitpid`, `kill` and `popen` through FFI to libc. | A 149-line subset. The `is*` predicates and `getmembers` are real; `getargspec` raises; `getsource`, `getfile`, `getmro`, `currentframe` return constants; `Signature` is an empty class and `signature()` reports arity only. |
| PyPy | CPython's `subprocess.py`, nearly unchanged. `_posixsubprocess.fork_exec` is an RPython module over a C file copied from CPython; plain `fork()`, `preexec_fn` supported. | CPython's `inspect.py` with about 146 added lines, because builtins have code objects there. Frames are real. |
| GraalPy | CPython's `subprocess.py`. `fork_exec` is a Java builtin that rejects `preexec_fn`; the native backend is a C `fork_exec` adapted from CPython, the Java backend uses a process builder and supports less. | CPython's `inspect.py`, two hunks changed. Builtins get signatures from their Java annotations. |

The pattern: an implementation that has frames, code objects and dynamic values reuses
CPython's Python source and reimplements only the C-level primitive. MicroPython, which has
none of the three in full, ships a small subset or nothing, and withdrew its empty stand-in
modules.

## `subprocess` here

Pystachy can follow PyPy and GraalPy for the process half and MicroPython for scope. Draft PR
for #1309: `lib/subprocess.py` keeps CPython's steps and messages over private runtime
primitives that mirror `_posixsubprocess.child_exec()`, with `fork()` and no `preexec_fn`, as
GraalPy. What had to change is what static typing forces:

- **Text mode is a compile-time property.** `run()` and `check_output()` are templates over the
  types of `text`, `universal_newlines`, `encoding` and `errors`, as typeshed's overloads are.
- **`Popen` is one concrete class.** As a class template it could not be named by an annotation
  or held in another class's field built with keyword arguments, which `mypy/build.py` does
  (`self.proc = subprocess.Popen(command, env=env)`). So it carries bytes only.
- **`CalledProcessError.output` is bytes.** An exception class cannot be a template, and a closed
  union does not hold `bytes` (`unions.py`: `gen_umember_problem`, `gen_value_union`,
  `gen_ueq_type`). Letting unions hold `bytes` would remove this deviation.

Effect on mypy 2.4.1, by `tools/import_sweep.py` on a trial tree (main `0b13a21` with the open
PRs #1275, #1276, #1288, #1342, #1344, #1347, #1351, #1356, #1365, #1371 and #1385; raw result in
[results/mypy-sweep-2026-11-12-with-subprocess.json](results/mypy-sweep-2026-11-12-with-subprocess.json)):
30 of 242 modules import, one more (`mypy.git`), and none stops at `subprocess`, where 79 did.
Those 79 now stop at a `Final` field without a type (`mypy/nodes.py:3863`, 49), at
`concurrent.futures` (`mypy/build.py:29`, 18), at `inspect` (9), and one each at `ast` and
`__file__`. The first errors overall: `Final` fields without a type 111 (`mypy/nodes.py:3863`
86, `mypyc/ir/ops.py:1461` 25), `inspect` 41, `concurrent.futures` 18, the annotation of
`mypy/util.py:374` 9, `ast` 5.

## `inspect` here: not yet

mypy needs `inspect` in one place that blocks 35 modules at import, `mypyc/ir/func_ir.py`: a
module-level dict of `inspect.Parameter.POSITIONAL_OR_KEYWORD` and its siblings, and
`get_text_signature()`, which builds `inspect.Parameter(name, kind, default=default)` with
`default: object = inspect.Parameter.empty` and prints `inspect.Signature(parameters)`.
(`mypy/util.py` also calls `getmembers()` with descriptor predicates, which is reflection.)

Those shapes need three things the compiler does not have, on main and on a trial tree of
main plus the open PRs #1315, #1372, #1281, #1361 and #1280 (probes in
[probes/inspect/](probes/inspect/), run with the hosted compiler):

1. **A class attribute whose value is an enum member.** `POSITIONAL_ONLY =
   _ParameterKind.POSITIONAL_ONLY` in `Parameter`'s body: "cannot infer the type of class
   attribute"; annotated, "class '_ParameterKind' cannot be used as a value".
2. **A class attribute whose value is a class.** `empty = _empty`: "class '_empty' cannot be
   used as a value", also as `type[_empty]`, `type[object]` and `Any`. The trial tree holds an
   ordinary class in a `type[object]` variable, parameter or field, but not in a class body.
3. **A slot that holds that class or any other value.** `Parameter.default` is `_empty` or an
   arbitrary object. `d: object = _empty` followed by `d = 5` is "unsupported type annotation"
   on the trial tree; dynamic `Any` does not take `bytes`.

Also: `_ParameterKind` sets `description` in `__new__` (#1348), and an enum body takes no
property.

Workarounds exist (int constants for the kinds, an instance for `empty`), and each is a
visible deviation in the two names the consumer uses. A module that imports but cannot give
`Parameter.empty` moves mypyc's first error by a few lines and does not make
`get_text_signature()` compile. MicroPython's removed dummies are the precedent against that.

Order that would work: class-body attributes that hold enum members and classes, then
`object` storage that holds a class; then `inspect` is a port of `_ParameterKind`,
`Parameter`, `Signature` and `cleandoc()` from `Lib/inspect.py`
(SHA-256 `b56e92a94bd48d89e44b8a4cdaa3a16f4d69df06c8500fce737c7cc879b0c982`), with
`signature()`, `getmembers()`, frames and source left out, as MicroPython leaves them.
