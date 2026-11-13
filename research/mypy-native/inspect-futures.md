# `inspect`, `concurrent.futures` and class-keyed dicts for native mypy

Measured on 2026-11-13 against main `63e4e52d`, CPython 3.13.16 and mypy 2.4.1. These
were the three largest first errors without an owner after the `Final` stack
([final.md](final.md)).

## Outcome

| Gap | Modules stopped | Result | Where |
|---|---:|---|---|
| `import inspect` (`mypyc/ir/func_ir.py:5`) | 41 → 0 | `lib/inspect.py`: `Parameter`, `Signature`, `cleandoc` | branch `claude/confident-einstein-ep3lh6-inspect`, stacked on #1388 |
| `concurrent.futures` (`mypy/build.py:29`) | 18 → 0 | `lib/concurrent/futures/`: a one-thread `ThreadPoolExecutor` | branch `claude/confident-einstein-ep3lh6-concurrent-futures` |
| `dict[type[object], list[str]]` (`mypy/util.py:374`) | 23 → 0 | no new work: open PRs #1315, #1361 and #1372 compile it | checked on the trial tree |

No pull request is open for the two library branches.

## Sweeps

`tools/import_sweep.py` over mypy's 242 modules on a trial tree. Raw results are in
[`results/`](results/).

| Trial tree | Import | File |
|---|---:|---|
| main `0b13a21` + the `Final` stack (2026-11-12) | 30 | `mypy-sweep-2026-11-12-with-final-stack.json` |
| main `63e4e52d` + #1275, #1276, #1280 to #1282, #1286, #1288, #1298, #1315, #1321, #1342, #1346, #1348, #1361, #1372, this session's library PRs and #1388 | 36 | `mypy-sweep-2026-11-13-with-typevar-class-values.json` |
| that + #1292, #1294, #1297, #1335, #1350, #1352, #1373, #1391, `inspect` and `concurrent.futures` | 38 | `mypy-sweep-2026-11-13-with-inspect-futures.json` |

First errors in the last sweep:

| First error | Modules | Open PR |
|---|---:|---|
| `mypy/nodes.py:444` inheritance with generic class templates | 114 | the merged #1298, #1335, #1350, #1352, #1373 and #1391 do not cover it |
| `mypyc/ir/rtypes.py:321` cannot infer the type of field `_may_be_immortal` | 28 | not checked |
| `mypy/ipc.py:22` module `librt.base64` | 26 | none |
| `mypy/checker.py:3636` bare `Final` in `TypeChecker`, a class with three bases | 7 | #1280 keeps the rejection for a class that is not compiled (cause not confirmed) |
| `ast` | 7 | none |

The trial tree is evidence about first errors, not a tested integration: table and
import-list conflicts were merged by hand, and its compiler was built one commit of #1388
before `92466c25`, which only changes modules whose ints promote.

## What #1388 needed

Prototyping `inspect` showed two faults in #1388 as first pushed (`3b1c2a5b`):

- **Imported modules were not covered.** There, `default_problem` refused a class-body
  value or parameter default that read `C.k`, for the class's name. The change reached only
  the main module's classes. Fixed in `52636e89`: such a value compiles where it is made of
  constants, class-attribute reads and displays of one item type, and guess gives the
  type annotated.
- **A new rejection.** A set was typed by its first item, so an imported class that the
  program never uses, holding `{1, "a"}`, became a compile error where main leaves the
  class out. `probes/limits/unused_class_mixed_set.py` shows it. Fixed in `52636e89`: a
  set display types a field only where all its items have one type.
- CI then failed `opt-in`: where ints promote, `-3` and `1` have different internal
  types, so `{1, 2, -3}` typed nothing. Fixed in `92466c25`.

List displays keep main's behaviour: `L = [1, "a"]` in an unused imported class is a
compile error on main too.

## `inspect`

- The module opts in to dynamic `Any` so that a parameter's default and annotation hold any
  value. A module that does not opt in and constructs a `Parameter` makes the whole program
  compile with numeric identity tracking: one `re` program grew from 56,507 to 85,791 IR
  lines and from 1.6 s to 3.7 s to compile (hosted compiler, single runs).
- `Parameter.empty`, `Signature.empty` and `inspect._empty` are one marker object, not a
  class: an ordinary class is no value on main.
- Nothing that reads live objects is provided (`signature()`, `getmembers()`, `isfunction()`,
  frames, source). A missing name is a compile-time error.
- mypyc's own line `default: object = inspect.Parameter.empty` does not compile in a
  module that does not opt in (`probes/limits/inspect/r9_object_annotation.py`). The 41
  modules import because `get_text_signature()` is compiled only where it is called.
- Other shapes rejected from a consumer: a `bytes`, typed-list, typed-dict or set default,
  an `IntEnum` member as a default, an int as a kind, and a tuple of parameters.
- A program that guards `import inspect` with `except ImportError` and then tests
  `inspect is not None` took its fallback before and is rejected now
  (`probes/limits/inspect/r7_optional_inspect_guard.py`), as when `json` was added.

## `concurrent.futures`

- A program runs one thread, so `submit()` runs the call before it returns and stores the
  result or the exception in the future. For calls that do not wait for each other this is
  one of the schedules CPython's pool may take.
- `Future` is `Generic[_T]`; `submit()` gives a `Future[int]`. One list or set holds
  futures of one type, and a bare `Future()` is rejected.
- No `ProcessPoolExecutor`, no `initializer`, `map()` of at most four iterables.
- A wait without a timeout on a future that cannot finish raises `RuntimeError`, as
  `_thread`'s locks do.

## Compiler limits found

Each has a small program in [`probes/limits/`](probes/limits/). All were run against the
hosted compiler.

| Program | Limit |
|---|---|
| `futures/generic_annotation_globals.py` | Bug: naming `Box[int]` in a function annotation compiles the class's methods before module globals are visible (`name 'READY' is not defined`). |
| `futures/none_local_arg.py` | A template's `x is None` is not folded when the argument is a local that only holds `None`; `none_const_arg.py` is the control that compiles. |
| `inspect/r1_str_isidentifier.py` | `str.isidentifier()` is unsupported. |
| `inspect/r2_class_attr_diagnostic.py` | An imported class left out for one attribute reports the line of another statement. Main does the same. |
| `inspect/r3_method_alias.py` | A method alias in a class body (`__replace__ = replace`) is rejected. |
| `inspect/r4_hash_tuple_any.py` | `hash()` of a tuple that holds an `Any` value is rejected. |
| `inspect/r5_generic_field_template.py` | A class whose `__init__` calls a generic class's constructor becomes a class template and cannot be a base. |
| `inspect/r6_intenum_percent_d.py` | `"%d" % member` of an `IntEnum` is rejected. |
| `inspect/r8_module_is_not_none.py` | `module is not None` after an optional import is rejected. |
| `inspect/r9_object_annotation.py` | A local annotated `object` is rejected outside dynamic-`Any` modules. |
