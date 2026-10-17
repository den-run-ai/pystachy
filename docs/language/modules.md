# Modules and builtins

This reference covers import behavior and the builtins implemented by Pystachy.
Start with the [language guide](../language.md) for the supported subset and typing rules.
For individual library APIs, ports and limitations, use the [library reference](../../lib/README.md).

## Finding and running modules

For Python modules, `import NAME` searches for `NAME/__init__.py` or `NAME.py` in this order:

1. The directory of the main program's real file, with symbolic links resolved, as for
   CPython's `sys.path[0]`.
2. Directories on `PYSTACHY_PATH`, separated by `:`.
3. `lib/` beside the compiler.

Builtin modules such as `sys`, `os` and `math` are handled by the compiler. A program's own
`ffi.py` takes precedence over the builtin `ffi` module. A file named like a module built into
CPython, such as `_weakref.py` or `itertools.py`, is never imported, as CPython imports its own.
For `binascii`, `_codecs`, `atexit`, `_struct`, `_thread`, `unicodedata` and `itertools`,
Pystachy loads its ports of those C modules, `lib/_pystachy_binascii.py`,
`lib/_pystachy_codecs.py`, `lib/_pystachy_atexit.py`, `lib/_pystachy_struct.py`,
`lib/_pystachy_thread.py`, `lib/_pystachy_unicodedata.py` and `lib/_pystachy_itertools.py`
([library reference](../../lib/compatibility.md#binascii)), and the
end of the program runs `atexit`'s callbacks. For `abc`, which CPython imports as it starts, it
loads `lib/_pystachy_abc.py` ([abc](../../lib/compatibility.md#abc)).

Packages, namespace packages, submodules, relative imports, `import a.b as x`,
`from ... import`, `from m import *` and circular imports are supported. A Python module's
top-level code runs once, when its first import executes; after a failed import, a later
import runs that code again.

`__name__` and `m.__name__` are the module's name, and `__debug__` is `True`.
`__doc__`, `m.__doc__` and `from m import __doc__` give the module's docstring, cleaned as
CPython 3.13 cleans it, or `None`. A module may bind its own `__doc__`, as `datetime` does;
until it does, its code reads the docstring. Without a docstring, it reads `None` only where
the first statement that names `__doc__` is module-level code; where that statement is a `def`
or `class`, a read before the module binds `__doc__` raises `NameError`. Deleting a module's
`__doc__`, assigning another module's, and reading `__doc__` in a class body (but in its
lambdas and comprehensions) are not supported. Some `lib/` modules' docstrings differ from
CPython's (see the [library reference](../../lib/compatibility.md)).
`__file__`, `__spec__` and CPython's other module metadata are unsupported.
An imported module cannot bind `__name__`.

## Module scope

A module sees its own names and the builtins. Names in the main program do not change
another module's bindings: defining `len` in the program does not change `bisect`'s `len`.
An import of a Python module inside a function binds its names in that function only.
Nested functions resolve enclosing Python-module imports and from-imported functions or
classes. The import must have surely run before the nested `def`; enclosing imports that
may remain unbound are rejected. Builtin import aliases are not supported as closure values.
Builtin-module imports have a [documented scope deviation](../language.md#deviations-from-cpython).

| Import or binding | Behavior |
|---|---|
| `from m import x`, where `x` is a variable | Copies its value, as CPython binds it. |
| A from-import of a function or class | Names the same function or class. |
| A module-level `def` or `class` after a from-import or `import *` that bound its name to a function or class, as `socket` defines `getaddrinfo` after `from _socket import *` | Rebinds the name, as CPython does: the `def` or `class` binds it for all of the module's code, so nothing may read the import's binding in between. Code that runs from the import until the name is rebound and reads it (also the statement's decorators, defaults, annotations, bases and class body) is rejected, as is code before the `def` or `class` that names, or decorates, a function or class that uses the name, or that makes a lambda or generator expression that reads it (it may run it then). Reads during an import cycle through another module's code or a module alias (including a self-import) are not caught ([compatibility](compatibility.md#names-and-scopes)). |
| `from m import *` | Uses `__all__` when present; otherwise takes public names bound when the module's code ends. `__all__` may be extended with `+=`, `append()` and `extend()`. |
| A package's own binding, such as `from .parse import parse` | Takes precedence over a submodule with the same name. |
| A module-level alias, `name = function` | Names that function, including a from-imported function or class, for later from-imports and star imports. |
| A class rebound to its instance, `class C: ...` directly followed by `C = C()` at module level (a sentinel, as `enum._not_given`) | `C` is the class in that call and the instance from then on, also in functions and other modules; the class keeps its name (`type(C).__name__`, `__qualname__`, reprs and messages). The class may have no base but `object`, and no decorator, `__init__` or `__new__`, so that the call runs none of the program's code, which could read `C` before it is bound. |
| `from builtins import RuntimeError as error` at module level | Names that builtin exception class, also as `m.error` and through from-imports, in `except` clauses, `raise`, calls and `isinstance()`, as `_thread.error` names `RuntimeError`. |
| A module-level [type alias](typing.md#type-aliases), `Row = list[str]` or `type Row = ...` | Names that type in the annotations of modules that import it, as `m.Row` or by a from-import or star import. |

A global that module code may leave unbound is checked when a function or another module
reads it. A missing binding raises `NameError` or `AttributeError`. This includes a global
assigned only in a branch, or read during a circular import before its assignment runs.

When a template is compiled before module code has assigned a global it reads, Pystachy
infers the global's type from its first binding in the module-level branches retained by
the compiler: an annotation, a value whose type is known, or an empty container later filled
by that code. The runtime binding check still applies.

`import pkg.util as u` binds `u` to `pkg.util`, as CPython does. Usually this is the submodule;
it can instead be a value the package binds after importing that submodule.
`import collections.abc` binds `collections` to the `lib/` package and runs its code, although
`collections.abc` itself is builtin; the package binds `abc` to that module, as CPython's does.
`_collections_abc` is that builtin module too, as in CPython, whose `collections` binds
`sys.modules['collections.abc']` to `_collections_abc`: `import _collections_abc` and
`from _collections_abc import Mapping` bind it and its ABCs, without the package. The module's other
names, such as `_check_methods`, `_type_repr` and `bytes_iterator`, are rejected, also in an
optional import, whose `except ImportError` clause CPython would not run.

## Compile-time branches

Pystachy resolves these guards while compiling:

| Guard | Treatment |
|---|---|
| `if __name__ == "__main__":` in an imported module | Drops the body. |
| `if typing.TYPE_CHECKING:` or the imported `TYPE_CHECKING` | Drops the body, including the common optional `typing` import whose handler sets `TYPE_CHECKING = False`. |
| Module-level `if False:` or `if 0:` | Drops the body outside functions and classes. |
| Module-level `TYPE_CHECKING = False` followed by `if TYPE_CHECKING:` | Drops the body when that is the name's only binding; other assignments, deletion, imports, star imports or `global` declarations disable this rule. |
| Tests of the platform: `sys.platform ==` or `!=` a literal string, `in` or `not in` a tuple or list of them, `sys.platform.startswith()` of one or a tuple of them, `os.name ==` or `!=` one, `sys.implementation.name ==` or `!=` one | Resolves them for the system Pystachy compiles for, the one it runs on, with the values its runtime reports: `sys.platform` is `"linux"`, `"darwin"` or `"freebsd"`, `os.name` is `"posix"` and `sys.implementation.name` is `"pystachy"`. This also holds in conditional expressions (`sep = "\\" if sys.platform == "win32" else "/"`), in functions, and in module code for a name that the module assigns such a test once, which nothing else binds, deletes or declares global (`_MS_WINDOWS = sys.platform == "win32"`, then `if _MS_WINDOWS:`); another module may assign that name only the value it holds. |
| Version tests: `sys.version_info`, a slice, an item or an attribute of it compared with a literal int, str or tuple of those | Resolves them for CPython 3.13.16, as in `if sys.version_info < (3,):`. |
| A module-level `try:` without `finally` whose first statement reads or assigns a name (or a tuple of names) that is no builtin and that nothing but the `try` binds (no other module-level statement, `global` declaration, star import or, in a package, submodule of that name; and where the `try` binds it, no import of a Python module before the `try`, whose code could assign it through the module), with a handler that catches `NameError` without naming it or re-raising | Runs that handler instead of the `try`, as CPython does: shims such as `try: unicode` / `except NameError: unicode = str`. |
| A module-level `try:` without `finally` whose statements only read builtins or assign them to names, such as `try: text_type = str`, which nothing else binds | Runs its body and `else` block; its handlers never run. |

These tests work inside `not`, `and` and `or`, while preserving the other operands' evaluation
order. The branch that does not run is not compiled at all, as CPython never runs it: its
imports are not resolved and its code is not checked, so `import nt` under
`if sys.platform == "win32":` compiles. For example, `effect()` still runs in `if effect() and os.name == "nt":`.
They apply only when a name still refers to the imported module or constant; a parameter,
local, loop variable or another import can shadow it.

Discarding a branch does not change Python scoping. A binding in discarded code still makes
a function's name local, including bindings from `:=`, `match` captures and `type` statements.
A `global` declaration still applies to its entire function. In a class body, Pystachy rejects
`global` because its class-scope behavior is unsupported.

## Optional imports

An optional import of the form `try: <imports> / except ImportError:` supports fallback code,
including the standard library's optional C accelerators. The imports run in order until:

- Pystachy cannot find the module.
- The module's top-level code definitely reaches `raise ImportError(...)`, possibly after
  a compile-time platform test.
- A from-import requests a name that the module has not bound yet and does not provide as
  a submodule. For a builtin module, this includes names Pystachy does not implement.

Successful earlier imports keep their bindings. A failing module runs up to its raise,
then the handler runs. A later import retries the failed module. These fallback choices can
differ from CPython when CPython has a module or accelerator that Pystachy lacks.

An import in another kind of `try` statement, such as one with `finally` or other exception
clauses, follows normal import rules: a missing module is a compile-time error.
Pystachy also rejects optional imports whose outcome or exception handling it cannot resolve;
see [rejected programs](../language.md#rejected-rather-than-miscompiled).

An import inside an imported module's function need not be resolved until that function is
compiled, unless module-level imports already load it.

## Unsupported code in imported modules

Unused functions and classes can contain unsupported features. Pystachy reports an error
when the program first needs them, with the module and the reason, for example:

```text
m.total() is not supported: parameter 'xs': unsupported type annotation
```

This permits a module to keep unsupported generator forms (such as `async` generators), unsupported annotations or classes with unsupported
inheritance beside functions that compile. An unsupported special method, such as an
unannotated `__len__`, is rejected when an operation needs it, including implicit use by
printing, sorting or container comparisons.

The `def` or `class` statement still executes when module code reaches it. Function defaults,
the compilable items of otherwise unsupported default displays, and supported function
decorators are evaluated then. Annotations are checked according to the language's
[annotation rules](../language.md#types), even for unused definitions.

For an uncompiled class body, Pystachy evaluates a restricted set of operations that can raise
and whose behavior it reproduces exactly:

- Numeric `/`, `%` and `//`, except integer `//` that could evaluate `-2**63 // -1`.
- List and dict indexing.
- `int()` of an ASCII string literal with at most 18 digits.
- `min()` and `max()` of a list.

These operations may use literals and module variables, but not branches of the class body.
Evaluation stops at the first potentially raising operation it cannot evaluate, such as a
user call, `**`, string indexing or division using a class-body variable; later classes are
not evaluated this way either.

Code left uncompiled must not run the program's own code. It may read names, compute with
literals and builtin values, bind or delete class-body names, use `if`, and apply supported
builtin decorators: `staticmethod`, `classmethod`, `property`, `dataclass`, and `typing`'s
`overload`, `final`, `override`, `no_type_check` and `runtime_checkable`. `object.__new__` is
also allowed. A potentially unbound variable or function read by this code is still checked
when the statement executes.

A base that raises is diagnosed when the statement runs, including a subscript of a class
without bases. `class C(object)` is treated as having no bases only when `object` is certainly
the builtin at that point. Class creation checks that Pystachy skips are listed among the
[CPython deviations](../language.md#deviations-from-cpython).

## Library code

Pystachy reuses CPython library code in several ways. Some files, such as `bisect` and
`colorsys`, are unchanged upstream sources. Others, such as `textwrap`, `fnmatch`, `difflib`,
`urllib.parse` and `datetime`, are adapted sources with marked edits. `re` substantially ports Python
and C components to the subset; `functools`, `io` and `csv` have implementations written for
Pystachy. The [library reference](../../lib/README.md) records provenance, available APIs,
restrictions and tests for each module.

The adapted sources remain valid Python, but that does not imply every upstream API compiles.
Common limitations include unsupported generator forms, byte-oriented string positions, lack of
`bytearray` and binary files, and homogeneous container types. Check the module's reference before choosing an API.

## Builtins

These builtins are supported in the listed contexts; types and argument shapes still
determine whether a particular call compiles.

| Category | Supported functions |
|---|---|
| Output and formatting | `print`, `str`, `repr`, `ascii`, `format` |
| Conversions | `int` (including `base=`), `float`, `bool`, `ord`, `chr`, `hex`, `oct`, `bin` |
| Numeric operations | `abs`, `round`, `divmod`, `pow` (including modular powers and inverses), `sum` |
| Containers and selection | `len`, `list`, `tuple`, `dict`, `set`, `frozenset`, `sorted`, `min`, `max`, `any`, `all` |
| Iteration in supported contexts | `range` (also as a value, a [range object](semantics.md#range-objects)), `reversed`, `enumerate`, `zip`, `map`, `filter` |
| Iterators | `iter` (one argument), `next` (with or without a default) |
| Types and attributes | `isinstance`, `callable`, `getattr`, `setattr`, `hasattr`, `vars`, `dir` and `type(x)`'s names and comparisons (see [reflection](semantics.md#reflection)), `super` in supported instance methods, `hash` |
| Input and files | `input`, `open` |

`iter()` and `next()` follow the [iterator rules](semantics.md#iterators). `type(x)` as a value
(a class object) is unsupported; `type(x).__name__`, `type(a) is C` and `type(a) == type(b)` are
supported for the program's classes, builtin values and exceptions (`type(e).__name__`).
`getattr`, `setattr`, `hasattr`, `vars` and `dir` follow the [reflection rules](semantics.md#reflection);
`delattr` is unsupported. `hash()` takes the
values that can be [dict keys](typing.md#supported-types), floats and NamedTuples too, and raises CPython's
`TypeError` for a list, dict, set or unhashable object.

`print()` accepts `sep`, `end`, `file` and `flush`. Its `file` may be a file or an object with
`write()`, such as `io.StringIO`; it receives one call for each piece, as in CPython.
`min()` and `max()` accept `key=`, and `sorted()` and `list.sort()` accept `key=` and `reverse=`;
a key is a function, a `Callable`, or an object whose class defines `__call__`, and one that is
`None` where the call runs (a `Callable | None`, or an object) is no key, as `key=None` is.
`set()` and `frozenset()` take supported iterables of their element type. Their methods support
multiple iterable arguments where CPython's do.

The common `str`, `list`, `dict` and `tuple` methods are implemented, including:

- `find`, `index` and `count` with start and end bounds, including `None`.
- `startswith` and `endswith`, including a tuple of strings.
- `split`, `rsplit`, `partition`, `rpartition`, `splitlines`, `removeprefix` and `removesuffix`.
- `replace` with a count, also given as `count=`.
- `center`, `ljust` and `rjust` with a fill character; `zfill`, `expandtabs`, `capitalize`,
  `title` and `swapcase`.
- `dict.pop()` with a default; `dict.popitem()`; `dict.update()` from a dict of its type, a list
  of key/value tuples, or keyword arguments for string keys; and `dict.fromkeys(xs, v)`.
- `tuple.index()` with start and stop, and `tuple.count()`, also of NamedTuples and
  runtime-length tuples.
- `int.bit_length()` and `int.bit_count()`, including on a `bool`.
- `str.format()` and `str.format_map()` of a string literal (see
  [formatting](semantics.md#literals-and-formatting)).

`a | b` of two dicts of one type is a new dict, and `a |= b` updates `a` as `a.update(b)` does.
`dict()` takes a dict, a list or tuple of key/value tuples, or the pairs of a generator
expression, list comprehension, `zip()`, `enumerate()`, `reversed()`, `map()` or `filter()`.
Of tuples of another length, the first item raises CPython's `ValueError` (an iterator is taken
only up to it) and none makes an empty dict, of the expected dict type or else `dict[int, int]`.
Where a dict type is expected, such tuples are a type error at compile time when `map()`,
`filter()` or `reversed()` makes them, or a display, comprehension or generator expression whose
items are not tuple displays.

`dict.fromkeys()` can omit `v`, or use `None`, when an annotation provides an optional value
type. Its keys cannot be a generator expression, `zip()`, `enumerate()` or `reversed()`;
an empty `()` or `{}` takes the expected dict's key type.

A dict display with `**` merges dicts of one type into a new dict, or `**kwargs` records
(with string keys) into a record that prints as a dict and can be forwarded.
Unsupported operations include `a | b` of dicts of different types and `dict()` with keyword
arguments. Supported iteration contexts and other restrictions are in the
[language guide](../language.md#expressions).

## Builtin modules and files

| Module | Supported surface |
|---|---|
| `sys` | `argv`, `warnoptions`, `exit`, `stdin`, `stdout`, `stderr`, `maxsize`, `platform`, `implementation.name` (`"pystachy"`), `setrecursionlimit`, `getrecursionlimit`; the streams are files. `warnoptions` is `[]`, CPython's for a program run without `-W` options (an extension module's is its host's). |
| `sys.version_info` | CPython 3.13.16's, a tuple of its items, and `major`, `minor`, `micro`, `releaselevel`, `serial` read as `sys.version_info.major` and the like; `str()` shows the tuple. |
| `sys.float_info` | `max`, `max_exp`, `max_10_exp`, `min`, `min_exp`, `min_10_exp`, `dig`, `mant_dig`, `epsilon`, `radix`, `rounds`, matching CPython for IEEE 754 doubles. `sys.float_info` itself is not a value. |
| `os` | `system`, `execv`, `getpid`, `getenv`, `remove`, `rmdir`, `fspath`; `name`, `sep`, `curdir`, `pardir`, `extsep`, `pathsep`, `linesep`, `devnull`. |
| `os.path` | `exists`, `realpath`, `join`, `normcase`, `getsize`, `getmtime`, `getctime`. |
| `time` | `time`, `time_ns`, `monotonic`, `perf_counter`, `process_time`, their `_ns` forms, and `sleep`. |
| `tempfile` | `mkdtemp`. |
| `errno` | The errno constants. |
| `math` | Functions and constants with CPython's domain and range errors; restrictions below. |
| Type and compiler support | `typing`, `collections.abc` (also `_collections_abc`), `dataclasses`, `builtins`, `__future__`; [FFI](../ffi.md) provides `@ffi.extern` and `@ffi.export`. |

`open()` supports text modes, `buffering=`, `newline=` translation and positions for `"+"`
modes. Files provide `read`, `readline`, `readlines`, `write`, `writelines`, `flush`, `close`,
iteration, and `closed`, `name` and `mode`. Encoding, buffering and automatic closure differences
are documented in [CPython deviations](../language.md#deviations-from-cpython).

`math.fsum()`, `math.prod()` (including `start=`) and `math.dist()` follow CPython's algorithms.
`fsum()` and `prod()` accept the iterables accepted by `sum()`; `fsum()` also accepts a tuple
mixing ints and floats. `dist()` accepts two lists or tuples of numbers, NamedTuples, or objects
with `__iter__`. It copies the first point's items before iterating the second, as CPython's
`tuple(p)` does. `prod()`'s `start` may also be a str or list, repeated by each int item in
turn, or a dict or set, returned when there are no items. Class items may supply `__index__`
for repetition or `__rmul__` returning the same type as the start; products that change the
start type are rejected. Subclasses that change the selected multiplication protocol need
`isinstance()` narrowing. With these starts, generators and `map()` are consumed one item at
a time, stopping at the first failed multiplication.

`gamma()` and `lgamma()` are CPython's own Lanczos implementation, so their results match
CPython's bit for bit. `isclose()` takes `rel_tol=` and `abs_tol=`. `gcd()`, `lcm()` and
`hypot()` take any number of arguments, `perm(n)` and `perm(n, None)` are `factorial(n)`,
and the integer functions accept bools. `sumprod` is unsupported.
