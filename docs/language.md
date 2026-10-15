# The Pystachy language

Pystachy compiles a statically typed subset of Python. Programs remain ordinary Python;
annotations, inference and specialization give the compiler the types it needs.

This guide covers the language you use to write and port programs. The detailed references
cover [typing](language/typing.md), [imports and builtins](language/modules.md),
[execution rules](language/semantics.md) and [CPython compatibility](language/compatibility.md).

## Types

| Kind | Supported forms |
|---|---|
| Scalars | `int`, `float`, `bool`, `str` |
| Containers | `list[T]`, `dict[K, V]`, `set[T]`, `frozenset[T]`, fixed-shape `tuple[A, B]`, runtime-length `tuple[T, ...]` |
| Objects | User classes, dataclasses and class-style `NamedTuple` |
| Closed scalar unions | `int \| float \| bool \| str`, optionally including `None` |
| Mixed container unions | Scalar members plus explicit `list[T]` / `dict[K, V]` members, with narrowing |
| Native reference unions | Up to four non-overlapping class/file types, such as `TextIO \| StringIO` |
| Optional values | `T \| None`, `Optional[T]`, `Union[T, None]` |
| Functions | Typed `Callable[[A, B], R]`, functions, lambdas, closures and bound methods |
| Generics | Function templates and `Generic` classes with inferred or explicit type arguments |

Integers are checked 64-bit values. Strings hold UTF-8 bytes. Dictionary keys and set elements
have a restricted set of types: integers, strings and supported tuples (whose items may
include booleans).
Fixed-shape tuples have at most nine items and require constant indices. Runtime-length
`tuple[T, ...]` values support integer indexing checked at runtime; their elements must be
`int`, `float`, `bool`, `str`, or one of these with `None`.

Explicit closed scalar unions such as `int | str`, bounded native reference unions,
and optional unions are supported. Dynamic `Any` values are not.
Generic classes can infer type arguments from construction or name them explicitly with
`Box[int]` annotations and constructor subscriptions; variadic generic classes remain inferred.

See the [type reference](language/typing.md#supported-types) for exact forms, conversions and constraints.

<a id="when-annotations-are-evaluated"></a>

## Typing rules

Annotate interfaces and containers where the type is not obvious:

```python
def total(prices: list[float]) -> float:
    return sum(prices)


counts: dict[str, int] = {}
counts["request"] = counts.get("request", 0) + 1
print(total([1.5, 2.5]), counts["request"])
# 4.0 1
```

The main rules are:

- An unannotated local or parameter can change type at a simple, unconditional assignment
  in a supported function body. An explicit annotation remains a contract; branches, loops,
  fields and globals still require consistent types. See [local bindings](language/typing.md#variables-and-empty-containers).
- Mutable containers are invariant: a `list[int]` cannot become a `list[int | None]`.
- Empty lists and dictionaries need an annotation or a use that determines their type.
- A function whose parameters are all annotated uses those types; if its return annotation is omitted,
  it returns `None`. Give value-returning functions an explicit return type.
- An unannotated module-level function or method is specialized for the argument types of each
  call. Its supported branches and return values must have consistent types.
- An unannotated constructor can specialize its class from the fields it initializes.
  Objects of different specializations cannot share one variable or container.

### Optional values

Narrow a local optional value before using it:

```python
def first(items: list[str]) -> str | None:
    return items[0] if items else None


name = first(["pystachy"])
if name is not None:
    print(name.upper())
# PYSTACHY
```

Tests such as `is not None` can narrow locals across branches and early returns. Copy an
optional global or field to a local before testing it; a call could change the original.
A value still typed as optional is rejected where a non-optional value is required.

The [typing reference](language/typing.md) covers template specialization, empty-container
inference, annotation evaluation, callable signatures and variadic arguments.

## Functions and classes

Functions support positional, keyword, default, positional-only and keyword-only parameters.
Lambdas, closures and decorators of functions are supported. Functions with `*args` or
`**kwargs` specialize for the call's argument shape; forwarding is more restricted than in
fully dynamic Python.

Classes support fields, methods, class attributes, `@staticmethod`, `@classmethod` and
supported operator and container methods. Dataclasses support `kw_only=True` and
`__post_init__`; options such as `frozen=True`, `order=True` and `dataclasses.field()` are
not supported.

Ordinary classes support single inheritance, inherited fields and constructors, instance-method
overrides, `super()` and runtime `isinstance()` checks. A base-typed receiver calls its concrete
class's override. Constructors in these hierarchies need annotated parameters; inheritance
involving class templates, dataclasses, NamedTuples or builtin types is unsupported. Exception
classes retain their separate inheritance rules, and `Generic[...]` declares a generic class.
Multiple inheritance, dynamic attribute hooks, metaclasses and general class or method
decorators remain outside the supported subset.

See [functions and classes](language/typing.md) and
[object protocols](language/semantics.md#object-protocols) for the detailed rules.

## Statements

The usual assignments, `if`, `while`, `for`, loop `else`, `break`, `continue`,
`return`, `assert`, `global` and `nonlocal` are supported. Loops can consume supported
containers, ranges, files and iterator-like objects.

Unpacking requires a fixed target shape. File context managers support `with open(...) as f:`;
arbitrary context managers are not supported. Exceptions use the normal
`try` / `except` / `else` / `finally` syntax.

## Expressions

| Feature | Scope |
|---|---|
| Arithmetic and comparisons | Checked integer arithmetic, floating point, bitwise operations, chained comparisons |
| Text formatting | F-strings and constant-string `%` formatting; no `str.format()` |
| Containers | List, dictionary, set and tuple displays; list and set comprehensions |
| Indexing and slicing | Negative indices; string and list slices without a step |
| Iterator-like expressions | `range`, `enumerate`, `zip`, `reversed` in supported loops and consumers |
| Generator expressions, `map`, `filter` | Direct arguments of supported consumers such as `sum`, `list`, `sorted`, `any` and `str.join` |
| Object operations | Supported operator and container methods, with runtime overrides in single-inheritance hierarchies |

Generator expressions consumed this way do not provide general generator objects. Functions
using `yield`, standalone iterators with `__next__`, dict comprehensions and multi-clause
comprehensions are not supported. See [execution rules](language/semantics.md) for consumer
restrictions, evaluation order and protocols.

<a id="exception-classes"></a>

## Exceptions

Builtin exceptions follow CPython 3.13's hierarchy. Runtime errors such as missing dictionary
keys, division by zero, failed file opens and integer overflow can be caught.

User-defined exception classes can derive from a supported builtin exception or another
exception class in the program. They can define fields, constructors and string
representations. `raise`, bare re-raise and `raise ... from ...` are supported.

Exception attributes such as `e.args`, exception groups and `except*` are not supported.
Uncaught exceptions print the final error line rather than a complete traceback.
Native stack exhaustion, memory exhaustion and an actual Ctrl-C do not follow ordinary
catchable exception handling. See [exception semantics](language/semantics.md#exceptions)
and [runtime differences](language/compatibility.md#errors-and-control-flow).

<a id="finding-and-running-modules"></a>
<a id="module-scope"></a>
<a id="code-pystachy-cannot-compile-in-an-imported-module"></a>

## Modules

Your own modules and packages, selected builtin modules and the libraries shipped in `lib/`
can be imported. Python module search uses the program's directory, `PYSTACHY_PATH`, then
the compiler's `lib/` directory. Package, relative and circular imports have documented
restrictions.

### Decided at compile time, as CPython decides it at import time

Imported modules' `__main__` guards, `TYPE_CHECKING` branches and recognized platform tests
are resolved at compile time. Unused functions can contain unsupported features, but syntax
checks still apply to their source.

### Optional imports

Supported `try: import ... / except ImportError:` patterns select a fallback when a module
or accelerator is unavailable. This is a restricted import mechanism, not a way to run
arbitrary CPython packages.

See [module rules](language/modules.md) for search order, scope, initialization, optional
imports and code deferred until use.

<a id="the-vendored-standard-library"></a>

## Builtins and library modules

Common numeric, text, container, sorting and file operations are supported. Builtin modules
provide selected APIs from `sys`, `os`, `math`, `time`, `errno` and `tempfile`.
An imported module name does not imply every CPython API is available.

The shipped libraries include unchanged upstream modules, localized ports such as
`fnmatch`, `textwrap` and `difflib`, and implementations such as `functools.cache` /
`lru_cache`, `io.StringIO` and `csv`. Each has its own supported operations and deviations.

Use the [builtin API reference](language/modules.md#builtins) and
[library port notes](../lib/README.md) for current coverage. C calls and experimental
CPython extension builds are documented separately in [FFI](ffi.md).

<a id="removed-on-purpose"></a>

## Unsupported features

The main gaps are multiple inheritance, general object unions and `Any`, generators, `async`,
`bytes` and binary files, complex and arbitrary-precision numbers, `match`, `:=`,
dynamic attribute access, stepped slices and unrestricted argument expansion.

Supported templates can avoid compiling unused branches containing some of these features.
An unsupported feature that the program needs produces a compile-time error.
The [detailed restriction list](language/compatibility.md#rejected-rather-than-miscompiled)
records the less common cases.

## Syntax errors

Pystachy checks syntax even in unused functions and dropped import-time branches.
Diagnostics use `file:line: error:` and aim to match CPython's location and message.
Some messages are less specific; `match` patterns and parts of newer syntax are not fully
checked. [Syntax checks](language/semantics.md#syntax-errors) describe those boundaries.

## Deviations from CPython

The most important differences for supported programs are:

| Area | Difference |
|---|---|
| Integers | Overflow raises instead of growing to arbitrary precision |
| Strings | Length and indexing count UTF-8 bytes; Unicode support varies by operation |
| Containers | Dictionary views are snapshots; string-set order differs from CPython |
| Exceptions | Uncaught errors omit the full traceback; native resource failures bypass handlers |
| Recursion | The native stack, rather than `sys.setrecursionlimit()`, limits depth |
| Lifetime | Garbage collection runs in batches; `__del__` never runs; close files explicitly |
| Evaluation | Some consumers materialize their input before processing it |

These are not the complete differences. Read the
[compatibility reference](language/compatibility.md#deviations-from-cpython) when relying on
Unicode, mutation during iteration, exception details, file buffering or object identity.
Module-specific differences remain in the [library port notes](../lib/README.md).

<a id="names-and-scopes"></a>
<a id="modules-and-imports"></a>
<a id="templates-and-empty-containers"></a>
<a id="objects-and-operators"></a>
<a id="classes-dataclasses-and-namedtuples"></a>
<a id="dict-keys-set-elements-and-bool-values"></a>
<a id="typing-forms"></a>
<a id="exceptions-and-exception-classes"></a>
<a id="builtins"></a>
<a id="source-text"></a>

## Rejected rather than miscompiled

Static types can rule out code that CPython would try to run, including bad argument shapes,
incompatible container types and unsupported operations. Such cases are compilation errors,
even if a runtime `try` could catch CPython's error.

The [diagnostic reference](language/compatibility.md#rejected-rather-than-miscompiled) groups
these restrictions by feature. [Testing](testing.md) explains how accepted programs,
documented deviations and expected rejections are checked against CPython.

