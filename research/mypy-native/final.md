# `Final` and `@final`: what CPython does, who uses them, what Pystachy lacks

Measured on 2026-11-12 against main `0b13a21`, CPython 3.13.16 and mypy 2.4.1.
Raw data is in [`final/`](final/): the census script and its JSON, the hashes of the
22 wheels it read, 50 probe programs and the [probe matrix](final/matrix.txt).

## Answers

- **`Final` is not specific to mypy or mypyc.** It is [PEP 591](https://peps.python.org/pep-0591/),
  in `typing` since Python 3.8. 18 of 28 other packages sampled use it, 3,197 times.
- **It generalizes to CPython because CPython does nothing with it.** `typing.Final` is
  a special form whose docstring says "There is no runtime checking of these properties";
  `@final` only tries to set `__final__ = True`. A rebound `Final` name, or a subclass of
  a `@final` class, runs unchanged. Supporting it therefore means: accept every spelling
  and type the name by `T` in `Final[T]`, or by its value for a bare `Final`.
- **What is specific to mypyc is giving `Final` meaning.** mypyc folds final constants
  (`mypyc/irbuild/constant_fold.py:56`), loads them as statics
  (`mypyc/irbuild/expression.py:192`) and marks `@final` classes
  (`mypyc/irbuild/prepare.py:110`). Pystachy cannot trust the qualifier that way: a
  program that rebinds a `Final` name compiles today and matches CPython, and the ground
  rule (#409) forbids changing that.
- **The remaining gaps are not about `Final`.** A bare `Final` has no type to fall back
  on, so it needs the value's type inferred. Every residual rejection below is the same
  rejection without the annotation (`S = {1, 2}` in a class body fails on main too).

## Who uses it

`final/census.py` parses sources with `ast` and counts annotations and decorators whose
name the file imports from `typing` or `typing_extensions`. Nothing is imported or run.

| Form | CPython stdlib | mypy + mypyc | 28 other packages | packages |
|---|---:|---:|---:|---:|
| module `X: Final = v` | 1 | 701 | 2,405 | 13 |
| module `X: Final[T] = v` | 1 | 161 | 419 | 13 |
| class `X: Final = literal` | 2 | 58 | 20 | 5 |
| class `X: Final = other value` | 0 | 14 | 10 | 7 |
| class `X: Final[T] = v` | 0 | 2 | 14 | 5 |
| class `X: Final[T]` | 3 | 9 | 13 | 2 |
| `self.x: Final = v` | 0 | 44 | 44 | 5 |
| `self.x: Final[T] = v` | 0 | 0 | 18 | 6 |
| local `x: Final…` | 0 | 0 | 8 | 5 |
| `@final` class | 7 | 57 | 67 | 7 |
| `@final` method | 4 | 0 | 179 | 3 |
| `@final` function | 2 | 0 | 0 | 0 |
| total | 20 | 1,046 | 3,197 | 18 |

- The stdlib column is CPython 3.13.16's `Lib` (1,770 files). 18 of its 20 uses are
  tests of `typing`; the others are `tomllib/_parser.py:28` and `asyncio/timeouts.py:27`.
- The other packages are aiohttp, anyio, attrs, black, click, coverage, django, fastapi,
  flask, homeassistant, httpx, hypothesis, jinja2, packaging, pathspec, pip, pluggy,
  pydantic, pygments, pytest, requests, rich, setuptools, sqlalchemy, starlette, trio,
  typer and urllib3. Ten of them never use `Final` or `@final`.
- homeassistant alone has 2,570 of the 3,197 uses (171 of the 179 `@final` methods).
  Without it the other 27 packages have 627.
- Module-level constants are 82% of mypy and mypyc's uses and 88% of the others'.

## What Pystachy accepts

Each probe is one small program, run under CPython and under the hosted compiler of
three trees. "ok" means the same stdout and exit status.

| Tree | 40 forms | 10 class-body shapes from packages |
|---|---:|---:|
| main `0b13a21` | 17 | 0 |
| main + #1275, #1280, #1281, #1282 (another session's open PRs) | 26 | 3 |
| that + the set-fields change of this session | 29 | 6 |

- **Works on main:** every module-level and local form, quoted, qualified and aliased
  spellings, `typing_extensions.Final`, `self.x: Final = v` and `self.x: Final[T] = v`
  in `__init__`, `Final[T]` in class bodies and dataclasses, and rebinding.
- **Rejected on main:** a class-body `X: Final = v` unless `v` is an int, float, str or
  bool literal. `N: Final = -1` is rejected too.
- **#1280 to #1282** make that a class attribute typed by its value, and let later
  class-scope values read earlier constants. They clear mypy's two sites
  (`mypy/nodes.py:3863`, `mypyc/ir/ops.py:1461`). #1275 accepts `@final` on classes.
  Draft #1244 accepts `@final` and `@override` on functions and methods (#712).
- **Set-fields change (this session):** fields and class attributes typed by set
  displays and by another class's class attributes, enum members included. With the
  stack it clears `mypy/checker.py:3636`, `mypy/stubutil.py:583` and `:609`, and
  `mypyc/ir/pprint.py:82`.

## Still rejected with everything above

| Probe | Shape | Owner or note |
|---|---|---|
| `cls_name`, `bl_list` | `A: Final = MODULE_CONSTANT`, a list of them | #1295 and #1375 type these (checked on their branches with unannotated twins) |
| `dec_final_fn`, `dec_final_attr`, `cls_final_dec` | `@final` on a function or method; reading `__final__` | draft #1244; #1275 rejects `__final__` on purpose |
| `my_maketrans` | `X: Final = str.maketrans(...)` (`mypy/report.py:484`) | no PR |
| `pt_name_attr` | a module-global object as the value (pytest) | no PR |
| `tr_none` | `encoding: Final = None` (trio) | no PR |
| `cls_expr` | `D: Final = A + 1` where `A` is itself computed | no PR; #1282 reads literal constants only |
| `cls_nested`, `cls_in_fn` | a non-literal bare `Final` in a nested or local class | #1280 keeps the rejection |
| `dc_classvar_final` | `ClassVar[Final[int]]` in a dataclass | #1281 keeps the rejection |
| `mod_annotated` | `Final[Annotated[int, "meta"]]` | no PR; not seen in the census |
| `self_other_method` | `self.x: Final = v` outside `__init__` | fields come from `__init__`; the typing spec requires that for `Final` too |
| `param_final` | `Final` on a parameter | invalid for type checkers; not seen in the census |

## mypy import sweep with the stack

`tools/import_sweep.py` over mypy 2.4.1's 242 modules, on a trial tree: main plus
#1275, #1276, #1280 to #1282, #1288, #1342 and this session's seven library PRs.
Raw results: [`results/mypy-sweep-2026-11-12-with-final-stack.json`](results/mypy-sweep-2026-11-12-with-final-stack.json).

- Modules whose first error is a `Final` field: 111 before, 0 after.
- Modules that import: 30 before, 30 after. Each of the 111 stops at a later error.

| First error after | Modules | Open PR |
|---|---:|---|
| `mypy/expandtype.py:118` TypeVar constraints and bounds | 72 | #1346 |
| `mypyc/ir/func_ir.py:5` `inspect` | 41 | none; see [subprocess-inspect.md](subprocess-inspect.md) |
| `mypy/util.py:374` unsupported annotation | 23 | not checked |
| `mypy/build.py:29` `concurrent.futures` | 18 | none |
| `mypy/nodes.py:444` generic base classes | 12 | #1298 |
| `mypyc/ir/deps.py:115` `self.x: Final = a or []` | 11 | #1286 |

The trial tree union-merged two documentation tables and two source hunks by hand; it
is evidence about first errors, not a tested integration.
