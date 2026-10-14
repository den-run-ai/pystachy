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
`ffi.py` takes precedence over the builtin `ffi` module.

Packages, namespace packages, submodules, relative imports, `import a.b as x`,
`from ... import`, `from m import *` and circular imports are supported. A Python module's
top-level code runs once, when its first import executes; after a failed import, a later
import runs that code again.

`__name__` and `m.__name__` are the module's name, and `__debug__` is `True`.
`__file__`, `__doc__`, `__spec__` and CPython's other module metadata are unsupported.
An imported module cannot bind `__name__`.

## Module scope

A module sees its own names and the builtins. Names in the main program do not change
another module's bindings: defining `len` in the program does not change `bisect`'s `len`.
An import of a Python module inside a function binds its names in that function only.
Builtin-module imports have a [documented scope deviation](../language.md#deviations-from-cpython).

| Import or binding | Behavior |
|---|---|
| `from m import x`, where `x` is a variable | Copies its value, as CPython binds it. |
| A from-import of a function or class | Names the same function or class. |
| `from m import *` | Uses `__all__` when present; otherwise takes public names bound when the module's code ends. `__all__` may be extended with `+=`, `append()` and `extend()`. |
| A package's own binding, such as `from .parse import parse` | Takes precedence over a submodule with the same name. |
| A module-level alias, `name = function` | Names that function, including a from-imported function or class, for later from-imports and star imports. |

A global that module code may leave unbound is checked when a function or another module
reads it. A missing binding raises `NameError` or `AttributeError`. This includes a global
assigned only in a branch, or read during a circular import before its assignment runs.

When a template is compiled before module code has assigned a global it reads, Pystachy
infers the global's type from its first binding in the module-level branches retained by
the compiler: an annotation, a value whose type is known, or an empty container later filled
by that code. The runtime binding check still applies.

`import pkg.util as u` binds `u` to `pkg.util`, as CPython does. Usually this is the submodule;
it can instead be a value the package binds after importing that submodule.

## Compile-time branches

Pystachy resolves these guards while compiling:

| Guard | Treatment |
|---|---|
| `if __name__ == "__main__":` in an imported module | Drops the body. |
| `if typing.TYPE_CHECKING:` or the imported `TYPE_CHECKING` | Drops the body, including the common optional `typing` import whose handler sets `TYPE_CHECKING = False`. |
| Module-level `if False:` or `if 0:` | Drops the body outside functions and classes. |
| Module-level `TYPE_CHECKING = False` followed by `if TYPE_CHECKING:` | Drops the body when that is the name's only binding; other assignments, deletion, imports, star imports or `global` declarations disable this rule. |
| Windows tests of `sys.platform` or tests of `os.name` | Resolves them for POSIX. `sys.platform` tests support `==`, `!=`, `startswith()` (including tuple prefixes), and membership in a tuple or list of Windows names. |

These tests work inside `not`, `and` and `or`, while preserving the other operands' evaluation
order. For example, `effect()` still runs in `if effect() and os.name == "nt":`.
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

This permits a module to keep generators, unsupported annotations or classes with unsupported
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
`colorsys`, are unchanged upstream sources. Others, such as `textwrap`, `fnmatch`, `difflib`
and `urllib.parse`, are adapted sources with marked edits. `re` substantially ports Python
and C components to the subset; `functools`, `io` and `csv` have implementations written for
Pystachy. The [library reference](../../lib/README.md) records provenance, available APIs,
restrictions and tests for each module.

The adapted sources remain valid Python, but that does not imply every upstream API compiles.
Common limitations include unsupported generators, byte-oriented string positions, lack of
`bytes`, and homogeneous container types. Check the module's reference before choosing an API.

## Builtins

This is the supported builtin surface; types and argument shapes still determine whether a
particular call compiles.

| Category | Supported functions |
|---|---|
| Output and formatting | `print`, `str`, `repr`, `ascii`, `format` |
| Conversions | `int` (including `base=`), `float`, `bool`, `ord`, `chr`, `hex`, `oct`, `bin` |
| Numeric operations | `abs`, `round`, `divmod`, `pow` (including modular powers and inverses), `sum` |
| Containers and selection | `len`, `list`, `dict`, `set`, `frozenset`, `sorted`, `min`, `max`, `any`, `all` |
| Iteration in supported contexts | `range`, `reversed`, `enumerate`, `zip`, `map`, `filter` |
| Input and files | `input`, `open` |

`print()` accepts `sep`, `end`, `file` and `flush`. Its `file` may be a file or an object with
`write()`, such as `io.StringIO`; it receives one call for each piece, as in CPython.
`min()` and `max()` accept `key=`, and `sorted()` and `list.sort()` accept `key=` and `reverse=`.
`set()` and `frozenset()` take supported iterables of their element type. Their methods support
multiple iterable arguments where CPython's do.

The common `str`, `list` and `dict` methods are implemented, including:

- `find`, `index` and `count` with start and end bounds, including `None`.
- `startswith` and `endswith`, including a tuple of strings.
- `split`, `rsplit`, `partition`, `rpartition`, `splitlines`, `removeprefix` and `removesuffix`.
- `center`, `ljust` and `rjust` with a fill character; `zfill`, `expandtabs`, `capitalize`,
  `title` and `swapcase`.
- `dict.pop()` with a default; `dict.update()` from a dict of its type, a list of key/value
  tuples, or keyword arguments for string keys; and `dict.fromkeys(xs, v)`.
- `int.bit_length()` and `int.bit_count()`, including on a `bool`.

`dict.fromkeys()` can omit `v`, or use `None`, when an annotation provides an optional value
type. Its keys cannot be a generator expression, `zip()`, `enumerate()` or `reversed()`;
an empty `()` or `{}` takes the expected dict's key type.

Unsupported methods include `str.format()`, `dict.popitem()`, `dict()` from pairs, and tuple
`index()` and `count()`. Supported iteration contexts and other restrictions are in the
[language guide](../language.md#expressions).

## Builtin modules and files

| Module | Supported surface |
|---|---|
| `sys` | `argv`, `exit`, `stdin`, `stdout`, `stderr`, `maxsize`, `platform`, `setrecursionlimit`, `getrecursionlimit`; the streams are files. |
| `sys.float_info` | `max`, `max_exp`, `max_10_exp`, `min`, `min_exp`, `min_10_exp`, `dig`, `mant_dig`, `epsilon`, `radix`, `rounds`, matching CPython for IEEE 754 doubles. `sys.float_info` itself is not a value. |
| `os` | `system`, `execv`, `getpid`, `getenv`, `remove`, `rmdir`, `fspath`; `name`, `sep`, `curdir`, `pardir`, `extsep`, `pathsep`, `linesep`, `devnull`. |
| `os.path` | `exists`, `realpath`, `join`, `normcase`, `getsize`, `getmtime`, `getctime`. |
| `time` | `time`, `time_ns`, `monotonic`, `perf_counter`, `process_time`, their `_ns` forms, and `sleep`. |
| `tempfile` | `mkdtemp`. |
| `errno` | The errno constants. |
| `math` | Functions and constants with CPython's domain and range errors; restrictions below. |
| Type and compiler support | `typing`, `collections.abc`, `dataclasses`, `builtins`, `__future__`; [FFI](../ffi.md) provides `@ffi.extern` and `@ffi.export`. |

`open()` supports text modes, `buffering=`, `newline=` translation and positions for `"+"`
modes. Files provide `read`, `readline`, `readlines`, `write`, `writelines`, `flush`, `close`,
iteration, and `closed`, `name` and `mode`. Encoding, buffering and automatic closure differences
are documented in [CPython deviations](../language.md#deviations-from-cpython).

`math.fsum()`, `math.prod()` (including `start=`) and `math.dist()` follow CPython's algorithms.
`fsum()` and `prod()` accept the iterables accepted by `sum()`; `fsum()` also accepts a tuple
mixing ints and floats. `dist()` accepts two lists or tuples of numbers, NamedTuples, or objects
with `__iter__`. It copies the first point's items before iterating the second, as CPython's
`tuple(p)` does. `gamma`, `isclose`, `lgamma` and `sumprod` are unsupported.
