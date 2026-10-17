# The Pystachy language

Pystachy compiles a statically typed subset of Python. Programs remain ordinary Python;
annotations, inference and specialization give the compiler the types it needs.

This guide covers the language you use to write and port programs. The detailed references
cover [typing](language/typing.md), [imports and builtins](language/modules.md),
[execution rules](language/semantics.md) and [CPython compatibility](language/compatibility.md).

## Types

| Kind | Supported forms |
|---|---|
| Scalars | `int`, `float`, `bool`, `str`, `bytes` |
| Containers | `list[T]`, `dict[K, V]`, `set[T]`, `frozenset[T]`, fixed-shape `tuple[A, B]`, runtime-length `tuple[T, ...]` |
| Objects | User classes, dataclasses and class-style `NamedTuple` |
| Closed scalar unions | `int \| float \| bool \| str`, optionally including `None` |
| Mixed container unions | Scalar members plus explicit `list[T]` / `dict[K, V]` members, with narrowing |
| Native reference unions | Up to four non-overlapping class/file types, such as `TextIO \| StringIO` |
| Optional values | `T \| None`, `Optional[T]`, `Union[T, None]` |
| Functions | Typed `Callable[[A, B], R]`, functions, lambdas, closures and bound methods |
| Generics | Function templates and `Generic` or PEP 695 (`class Box[T]`) classes with inferred or explicit type arguments; module-level type aliases |

Integers are checked 64-bit values. Strings hold UTF-8 bytes; a `bytes` holds its bytes, and its
items are ints. Dictionary keys and set elements
have a restricted set of types: integers, strings, `bytes`, objects (hashed by identity, or by their
class's `__hash__` and `__eq__`) and supported tuples (whose items may include booleans).
Fixed-shape tuples have at most nine items; a variable index gives an item of their union
type, and a constant index the item's own type. Runtime-length
`tuple[T, ...]` values support integer indexing checked at runtime; their elements must be
`int`, `float`, `bool`, `str`, or one of these with `None`.

Explicit closed scalar unions such as `int | str`, bounded native reference unions,
and optional unions are supported. `Any` in function parameter and return annotations is
inferred for each call; dynamic `Any` values are not supported.
Generic classes can infer type arguments from construction or name them explicitly with
`Box[int]` annotations and constructor subscriptions; variadic generic classes remain inferred.
Module-level type aliases (`Row = list[str]`, `type Pair[T] = tuple[T, T]`) name types in
annotations.

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
- Ordinary functions and methods infer an omitted return annotation from their supported returns,
  including no-argument and fully annotated parameter signatures. Parameters keep their declared
  types, explicit `-> None` stays a contract, and functions without value returns return `None`.
  Constructors and implicit special methods keep their own result contracts.
- A module-level function or ordinary method with an unannotated parameter is specialized for
  each call's argument types. Its supported branches and returns must have consistent types.
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

Classes support fields, methods, class attributes, `@property` with `@x.setter` and
`@x.deleter`, `@staticmethod`, `@classmethod` and supported operator and container methods.
Dataclasses support `__post_init__`, `dataclasses.field()`, `KW_ONLY`, `dataclasses.replace()`,
the options `init`, `repr`, `eq`, `order`, `unsafe_hash`, `frozen`, `match_args` and
`kw_only`, inheritance from another dataclass, and `fields()`, `asdict()`, `astuple()` and
`is_dataclass()` (see [reflection](language/semantics.md#reflection)); `slots=True` is not
supported.

Literal `__slots__` strings, tuples and lists restrict instance field writes when every
base also declares slots. A subclass without slots, or with an unslotted base, may add
fields. Dynamic slots, private slot names, `__dict__` and `__weakref__` slots are
unsupported. The `__slots__` class attribute remains readable through the class or an
instance; changing its value does not change the declared slots. Instance rebinding
of `__slots__` is unsupported, as are base-typed reads when subclasses use different
metadata types, or when an exception subclass overrides the metadata (read through
the concrete class instead). Slot violations are compile
errors rather than catchable exceptions. Repeated slot declarations and
class variables or methods shadowing inherited slots are also unsupported, as are
new slots shadowing inherited methods, properties or class variables.

Ordinary classes support single inheritance, inherited fields and constructors, overrides of
instance, static and class methods, `super()` and runtime `isinstance()` checks. A base-typed
receiver calls its concrete class's instance-method override. Constructors in these
hierarchies need annotated parameters; inheritance involving class templates, NamedTuples or
builtin types, or between a dataclass and a class that is not one, is unsupported. Exception
classes retain their separate inheritance rules, and `Generic[...]` or PEP 695 type
parameters (`class Box[T]`) declare a generic class, which has no other base.
Multiple inheritance, dynamic attribute hooks, metaclasses and general class or method
decorators remain outside the supported subset. Reflection (`getattr`, `setattr`, `hasattr`,
`vars`, `dir`, `type(x).__name__`) works on objects whose classes the compiler knows; an
attribute name computed at run time is supported where only its text or a test is needed
(see [reflection](language/semantics.md#reflection)).

See [functions and classes](language/typing.md) and
[object protocols](language/semantics.md#object-protocols) for the detailed rules.

## Statements

The usual assignments, `if`, `while`, `for`, loop `else`, `break`, `continue`,
`return`, `assert`, `global` and `nonlocal` are supported. Loops can consume supported
containers, ranges, files and iterator-like objects.

Unpacking takes a fixed target shape or one starred target, `first, *rest = xs`, whose name
gets a new list of the remaining items. `with` takes files and context managers of the
program's classes (`__enter__` and `__exit__`), and `lib/contextlib` provides
`@contextmanager`, `closing`, `nullcontext` and `suppress`. Exceptions use the normal
`try` / `except` / `else` / `finally` syntax.

## Expressions

| Feature | Scope |
|---|---|
| Arithmetic and comparisons | Checked integer arithmetic, floating point, bitwise operations, chained comparisons |
| Assignment expressions | `x := v` in conditions, comprehensions, arguments and other expressions, binding `x` as `x = v` does |
| Text formatting | F-strings, and `%` formatting and `str.format()` of a literal format string |
| Containers | List, dictionary, set and tuple displays, `*` items in list and tuple displays; list, set and dict comprehensions with any number of `for` and `if` clauses |
| Indexing and slicing | Negative indices; string, list and tuple slices with optional steps; list slice assignment and `del` |
| Iterator-like expressions | `range`, `enumerate`, `zip`, `reversed` in supported loops and consumers |
| Range objects | `range()` as a value: iteration, `len`, `in`, indexing and slicing, `start`, `stop` and `step`, `==`, `hash`, `index`, `count`; see [range objects](language/semantics.md#range-objects) |
| Generator expressions, `map`, `filter` | Direct arguments of supported consumers such as `sum`, `list`, `tuple`, `sorted`, `any` and `str.join`; a generator expression elsewhere is a generator object |
| Generators | Functions and methods (including `__iter__`) that `yield` or `yield from`, consumed by `for`, `next()`, `iter()`, `in` and the builtins that take iterables; `send()`, `throw()`, `close()` and the value of a `yield` expression |
| Iterators | Classes with `__iter__` and `__next__`; `iter()` and `next()` values that share their position |
| Object operations | Supported operator and container methods, with runtime overrides in single-inheritance hierarchies |

[Generators](language/semantics.md#generators) take values from `send()` where their function
is annotated `Generator[Y, S, R]`. See [execution rules](language/semantics.md) for consumer
restrictions, evaluation order, protocols and [iterators](language/semantics.md#iterators).

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

Imported modules' `__main__` guards, `TYPE_CHECKING` branches, recognized platform and
`sys.version_info` tests, and module-level `NameError` feature tests (`try: unicode` /
`except NameError:`) are resolved at compile time. Unused functions can contain unsupported
features, but syntax checks still apply to their source.

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
`fnmatch`, `textwrap`, `difflib`, `random` and `datetime`, and implementations such as
`functools.cache` / `lru_cache`, `collections` (`deque`, `defaultdict`, `OrderedDict`,
`Counter`), `io.StringIO`, `io.BytesIO`, `io.TextIOWrapper` and `csv`. Each has its own supported operations and deviations.

Use the [builtin API reference](language/modules.md#builtins) and
[library port notes](../lib/README.md) for current coverage. C calls, calls into an
embedded CPython (`pyobj`) and experimental CPython extension builds are documented
separately in [FFI](ffi.md).

<a id="removed-on-purpose"></a>

## Unsupported features

The main gaps are multiple inheritance, general object unions and dynamic `Any` values, `async`,
`bytearray`, `memoryview` and binary files, complex and arbitrary-precision numbers, `match`,
attribute values looked up by names only the run time knows (their text and `hasattr()` are
supported), slice objects and unrestricted argument expansion.

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

