# The Pystachy language

Pystachy compiles a statically typed subset of Python to native code, in a JIT
(`pystachy run`) or ahead of time (`pystachy build`), with CPython 3.13 as the reference for
behavior. Programs remain ordinary Python that CPython also runs: annotations, inference and
specialization give the compiler the concrete types it needs. A program that needs a feature
outside the subset fails to compile rather than running differently.

This guide is the overview: what is supported, what it costs and where the subset differs
from CPython. The detailed references define each rule:

| Reference | Defines |
|---|---|
| [Types and inference](language/typing.md) | Type forms, inference, templates, unions, generics, classes and inheritance |
| [Execution and expressions](language/semantics.md) | Statements, expressions, iterators, generators, protocols, reflection and exceptions |
| [Modules and builtins](language/modules.md) | Module search, scope, compile-time branches, optional imports and builtin APIs |
| [CPython compatibility](language/compatibility.md) | Semantic differences, compile-time restrictions and links to module/opt-in limits |
| [Performance](performance.md#representation-costs) | Representation costs, measurements and optimization guidance |

The experimental [dynamic `Any`](dynamic-any.md) and [promoting ints](python-int.md) have
their own contracts; [interoperability](ffi.md) covers C, embedded CPython and extension modules.

## Support at a glance

| Status | Meaning |
|---|---|
| 🟢 **Native** | Compiles to concrete native code and matches CPython, apart from the [listed deviations](#deviations-from-cpython) |
| 🟡 **Bounded** | Supported, with documented limits on its forms or costs that depend on the workload |
| 🧪 **Experimental** | A prototype with its own contract: a per-module `# pystachy:` opt-in, or an interop API |
| 🔴 **Unsupported** | Rejected at compile time; use a supported form, or CPython through the [bridge](ffi.md) |

🔴 **Major gaps** are Python features that are not available; most are compile-time errors.
🟠 **Minor gaps** are narrower forms or documented differences within a supported feature.

| Area | Status | Supported | 🔴 Major gaps | 🟠 Minor gaps |
|---|---|---|---|---|
| [Numbers](language/compatibility.md#numbers) | 🟢 Native<br>🧪 Big ints | Checked 64-bit `int`, `float` and `bool`; [`complex`](language/semantics.md#complex-numbers); unbounded `int` with [promoting ints](python-int.md) or explicit [`mpz`](mpz.md) | — | `int` overflow raises `OverflowError` unless the module opts in; numeric identity follows the [typed/dynamic boundary](dynamic-any.md#the-typeddynamic-contract) |
| [Text and bytes](language/compatibility.md#text-and-file-positions) | 🟡 Bounded | `str` with code-point lengths, indexing and slicing; `bytes`; f-strings, `%` and `str.format()`; UTF-8, Latin-1 and ASCII codecs; [binary files](../lib/compatibility.md#binary-files) | `bytearray`, `memoryview` | Incomplete Unicode case mapping; `%` and `str.format()` need a constant format; no `\N{...}` escapes |
| [Containers](language/semantics.md#operators-and-containers) | 🟢 Native<br>🟡 Union items | `list`, `dict`, `set`, `frozenset`, fixed-shape and runtime-length `tuple`; displays, comprehensions, slices with steps, unpacking | Slice objects | Keys and set elements are ints, strs, bytes, objects or tuples (no floats); fixed tuples hold up to nine items; dict views are snapshots |
| [Static typing](language/typing.md) | 🟢 Native<br>🟡 Unions | Inferred locals, returns and per-call specializations; closed unions; `T \| None` narrowing; `Callable`; generic functions and classes, including PEP 695; type aliases | General object unions | Mutable containers are invariant; empty containers need a type; recursive value aliases are a prototype |
| [`Any` values](dynamic-any.md) | 🟢 Native<br>🧪 Dynamic | `Any` annotations specialize to concrete types; with `# pystachy: dynamic-any`, runtime-typed values with lazy iteration, comparisons and numeric protocols | Runtime-typed values in modules that do not opt in | Unsupported cross-type comparison bodies raise `TypeError`; some typed boundaries lose numeric identity |
| [Functions](language/typing.md#functions-callables-and-closures) | 🟢 Native | Every parameter kind and default; lambdas, closures and `nonlocal`; function decorators; `*args` and `**kwargs` per call shape; `Callable` values and bound methods | — | `f(*xs)` of a list and run-time `**` expansion; `Callable[..., R]`; keyword calls through a `Callable` |
| [Classes](language/typing.md#single-inheritance) | 🟢 Native<br>🟡 Hierarchies | Fields, methods, properties, static and class methods, operator methods, dataclasses, `NamedTuple`, single inheritance with overrides and `super()`, one method-only secondary base, two plain builtin exception bases, `__slots__`, `abc` | General multiple inheritance; subclasses of builtin types; general metaclasses and class decorators; `__getattr__`-style hooks | No reflected arithmetic (`__radd__`) or `NotImplemented` results |
| [Reflection](language/semantics.md#reflection) | 🟡 Bounded | `getattr`, `setattr`, `hasattr`, `vars`, `dir` and `type(x).__name__` on classes the compiler knows | `eval`, `exec`; values of attributes named at run time | A run-time name works where only its text or a test is needed |
| [Statements](language/semantics.md#statements) | 🟡 Bounded | Assignment and unpacking, `:=`, `if`, loops with `else`, `with`, `assert`, `del`, `global`, `nonlocal`; [bounded `match`](language/semantics.md#structural-patterns) | Mapping and general sequence/class patterns; `async` and `await` | Deleting a global from a function |
| [Generators and iterators](language/semantics.md#generators) | 🟢 Direct<br>🟡 Suspended | `yield`, `yield from`, `send()`, `throw()` and `close()`; generator expressions; iterator classes; lazy `itertools` | — | A dropped suspended generator is never closed; some consumers materialize their input |
| [Exceptions](language/semantics.md#exceptions) | 🟡 Bounded | CPython 3.13's builtin hierarchy; user exception classes; `raise ... from`; `try` / `except` / `else` / `finally`; catchable `RecursionError` | `except*` and exception groups | No `e.args` or traceback objects; uncaught errors print only the last line; `MemoryError` and Ctrl-C end the program |
| [Modules](language/modules.md) | 🟡 Bounded | Modules and packages; relative, circular and optional imports; compile-time `__main__`, platform and version branches | CPython C extensions; imports chosen at run time (`importlib`, `__import__`) | A builtin module's import binds program-wide; a module whose code raises keeps its partial globals |
| [Standard library](stdlib.md#library-support-at-a-glance) | 🟡 Bounded | [Common builtins](language/modules.md#builtins); `sys`, `os`, `math`, `time`, `errno`, `tempfile`, `select`; shipped `re`, `json`, `collections`, `itertools`, `functools`, `datetime`, `tomllib`, `logging` and more | Starting threads (`threading` runs one), `asyncio`, `subprocess`, `socket`, `multiprocessing` and other unshipped modules | Each module supports its own API subset |
| [Memory and lifetime](language/compatibility.md#memory-and-resource-lifetime) | 🟡 Bounded | Automatic memory through a conservative, batched collector; `with` closes files; experimental `weakref.ref` | Finalizers: `__del__` never runs | A dropped file closes at a later collection; no weak containers |
| [Interop and concurrency](ffi.md) | 🧪 Experimental | C calls (`ffi`); CPython embedded through `pyobj`; extension modules that CPython imports, also in [process pools](concurrency.md) | Native threads; `async` | `pyobj` converts scalars only; an extension runs only on the thread that imported it |

The table describes the current source tree; the [alpha.4 release notes](releases/v0.1.0-alpha.4.md)
record that release's changes since alpha.3. [Unsupported features](#unsupported-features) and
[deviations](#deviations-from-cpython) summarize the gaps below, and the
[compatibility reference](language/compatibility.md) lists every known case.

## Performance and complexity

Every supported feature compiles through typed IR and LLVM, in the JIT and AOT alike; there
is no interpreter fallback. The cost of a construct follows the representation its types
select, not its syntax: `a + b` on two `int` values is a checked machine addition, while on
two dynamic `Any` values it dispatches on their run-time types.

The [performance guide](performance.md#representation-costs) explains the costs of tagged
unions, generators, exceptions, recursive JSON values and dynamic `Any`. These costs are
relative to concrete native code; performance against CPython depends on the workload.
Additional costs and measurements:

- **Promoting ints** keep checked-int64 speed while values fit in 64 bits; recorded
  big-value workloads ran at 0.83–1.31× CPython's speed ([measurements](python-int.md#measurements)).
- **Catchable recursion limits** add a depth check to calls that can recur. In the alpha.4
  release's instruction counts, recursion accounting and the native stack check cost
  pyperformance's `generators` 18.2% and `barnes_hut` 11.2% over alpha.3
  ([per-benchmark counts](../bench/pyperformance/README.md#alpha3-to-alpha4),
  [release notes](releases/v0.1.0-alpha.4.md#performance-and-remaining-risks)).
- **Opt-ins are per module, but some policies are program-wide:** once a module opts in to
  dynamic `Any`, every typed dictionary in the program uses CPython's hash and probe scheme,
  while identity tracking stays in the modules that can observe it
  ([representation costs](performance.md#representation-costs)).
- **Compile time** grows with each specialization of an unannotated function and with class
  hierarchies; JIT runs include it ([compile time](performance.md#compile-time)).

To keep Pythonic code fast, keep hot data concrete and homogeneous, narrow optional and `Any`
values before loops, and reserve exceptions for errors rather than per-iteration control flow.
Measure compilation and execution separately
([getting started](getting-started.md#measure-the-work-you-care-about),
[performance guide](performance.md)).

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
| Recursive values (prototype) | `type JSONValue = None \| bool \| int \| float \| str \| list[JSONValue] \| dict[str, JSONValue]` and smaller closed recursive unions, narrowed with `isinstance()`; see [recursive value aliases](language/typing.md#recursive-value-aliases-prototype) |

- **Integers** are checked 64-bit values; `x & y` keeps the low 64 bits of the arithmetic it
  masks ([numbers](language/compatibility.md#numbers)). A module that opts in to
  [promoting ints](python-int.md) gets CPython's arbitrary-precision `int` in its variables,
  arguments, returns, fields, tuples and generators, and in lists, dicts and sets of ints and
  of tuples of ints.
- **Strings** are stored as UTF-8; their lengths, indexing, slicing, iteration and search
  positions count code points, as CPython's do. A `bytes` holds bytes, and its items are ints.
- **Dictionary keys and set elements** are integers, strings, `bytes`, objects (hashed by
  identity, or by their class's `__hash__` and `__eq__`), unions of classes hashed by identity
  and supported tuples, whose items may include booleans.
- **Fixed-shape tuples** have at most nine items; a constant index gives the item's own type,
  and a variable index the union of the item types. **Runtime-length** `tuple[T, ...]` values
  check integer indexes at run time; their elements are `int`, `float`, `bool` or `str`,
  optionally with `None`.
- **Unions:** explicit closed scalar unions such as `int | str`, bounded native reference
  unions and optional unions are supported. A variable, field or return given values of
  several scalar types holds their union.
- **`Any`** in supported function and method signatures, constructor parameters and
  initialized module or local variables uses concrete inference; a module that opts in to the
  [dynamic `Any` prototype](dynamic-any.md) gets runtime-typed `Any` values instead.
- **Generic classes** infer type arguments from construction or name them explicitly with
  `Box[int]` annotations and constructor subscriptions; variadic generic classes remain
  inferred. Module-level type aliases (`Row = list[str]`, `type Pair[T] = tuple[T, T]`) name
  types in annotations.

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
  in a supported function body. An explicit annotation remains a contract. A local in branches
  or loops, a field or a global given values of several scalar types (`int`, `float`, `bool`,
  `str`, `None`) holds their union; other types must be consistent. See
  [local bindings](language/typing.md#variables-and-empty-containers) and
  [inferred unions](language/typing.md#inferred-unions).
- Mutable containers are invariant: a `list[int]` cannot become a `list[int | None]`.
- Empty lists and dictionaries need an annotation or a use that determines their type.
- Ordinary functions and methods infer an omitted return annotation from their supported returns,
  including no-argument and fully annotated parameter signatures. Parameters keep their declared
  types, explicit `-> None` stays a contract, and functions without value returns return `None`.
  Constructors and implicit special methods keep their own result contracts.
- A module-level function or ordinary method with an unannotated parameter is specialized for
  each call's argument types. Returns of several scalar types return their union; other
  branches and returns must have consistent types.
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
fully dynamic Python ([variadic arguments](language/typing.md#variadic-arguments)).

Classes support fields, methods, class attributes, `@property` with `@x.setter` and
`@x.deleter`, `@staticmethod`, `@classmethod` and supported
[operator and container methods](language/semantics.md#object-protocols).

- **Dataclasses** support `__post_init__`, `dataclasses.field()`, `KW_ONLY`,
  `dataclasses.replace()`, the documented decorator options other than `slots=True`,
  inheritance from another dataclass, and `fields()`, `asdict()`, `astuple()` and
  `is_dataclass()` ([fields and dataclasses](language/typing.md#fields-dataclasses-and-namedtuples)).
- **Construction** requires `__init__` to return `None`; a different result raises a catchable
  `TypeError` after the initializer runs.
- **`__slots__`** given as literal strings, tuples or lists restricts instance field writes
  when every base also declares slots; slot violations are compile errors
  ([slots](language/typing.md#slots)).
- **Inheritance** is single: inherited fields and constructors, overrides of instance, static
  and class methods, `super()` and runtime `isinstance()` checks. A base-typed receiver calls
  its concrete class's instance-method override. Constructors in these hierarchies need
  annotated parameters, and class templates, NamedTuples, builtin types and mixed
  dataclass/ordinary hierarchies cannot take part
  ([single inheritance](language/typing.md#single-inheritance)).
- **Generic classes** declare `Generic[...]` or PEP 695 type parameters (`class Box[T]`) and
  have no other base. Exception classes have their own [inheritance rules](#exceptions).
- **Reflection** (`getattr`, `setattr`, `hasattr`, `vars`, `dir`, `type(x).__name__`) works on
  objects whose classes the compiler knows; an attribute name computed at run time is
  supported where only its text or a test is needed ([reflection](language/semantics.md#reflection)).

Multiple inheritance, subclasses of builtin types, dynamic attribute hooks, general
metaclasses and general class or method decorators remain outside the supported subset.
See [object protocols](language/semantics.md#object-protocols) and the
[class restrictions](language/compatibility.md#classes-dataclasses-and-namedtuples).

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
| Sentinels | `object()`: a new object at each call, compared by identity (`is`, `==`, `hash`); see [sentinels](language/semantics.md#sentinels) |
| Generator expressions, `map`, `filter` | Direct arguments of supported consumers such as `sum`, `list`, `tuple`, `sorted`, `any` and `str.join`; a generator expression elsewhere is a generator object |
| Generators | Functions and methods (including `__iter__`) that `yield` or `yield from`, consumed by `for`, `next()`, `iter()`, `in` and the builtins that take iterables; `send()`, `throw()`, `close()` and the value of a `yield` expression |
| Iterators | Classes with `__iter__` and `__next__`; `iter()` and `next()` values that share their position |
| Object operations | Supported operator and container methods, with runtime overrides in single-inheritance hierarchies |

[Generators](language/semantics.md#generators) take values from `send()` where their function
is annotated `Generator[Y, S, R]`. See [execution rules](language/semantics.md) for consumer
restrictions, evaluation order, protocols and [iterators](language/semantics.md#iterators).

<a id="exception-classes"></a>

## Exceptions

- **Builtin exceptions** follow CPython 3.13's hierarchy. Runtime errors such as missing
  dictionary keys, division by zero, failed file opens and integer overflow can be caught.
- **Recursion:** exceeding `sys.setrecursionlimit()` raises a catchable `RecursionError` in
  JIT and AOT, with ordinary `finally` and context-manager unwinding. The
  [native depth policy](language/compatibility.md#errors-and-control-flow) can reach its limit
  at a different source call than CPython.
- **User-defined exception classes** derive from a supported builtin exception or another
  exception class in the program, and can define fields, constructors and string
  representations. `raise`, bare re-raise and `raise ... from ...` are supported.
- **Exception classes are values:** stored, compared, tested with `issubclass()` and
  `isinstance()`, called and raised
  ([exception classes as values](language/semantics.md#exception-classes-as-values)).

Exception attributes such as `e.args`, exception groups and `except*` are not supported.
Uncaught exceptions print the final error line rather than a complete traceback.
Native stack exhaustion outside the recursion checks, memory exhaustion and an actual Ctrl-C
do not follow ordinary catchable exception handling. See
[exception semantics](language/semantics.md#exceptions) and
[runtime differences](language/compatibility.md#errors-and-control-flow).

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
provide selected APIs from `sys`, `os`, `math`, `time`, `errno`, `tempfile` and `select`.
An imported module name does not imply every CPython API is available.

The shipped libraries include unchanged upstream modules, localized ports such as
`fnmatch`, `textwrap`, `difflib`, `random` and `datetime`, and implementations such as
`functools.cache` / `lru_cache`, `collections` (`deque`, `defaultdict`, `OrderedDict`,
`Counter`), `io.StringIO`, `io.BytesIO`, `io.TextIOWrapper`, `csv` and a bounded native `json`.
Each has its own supported operations and deviations.

Use the [builtin API reference](language/modules.md#builtins), the
[library support table](stdlib.md#library-support-at-a-glance) and the
[module guide](../lib/README.md#module-guide) for current coverage. C calls, calls into an
embedded CPython (`pyobj`) and experimental CPython extension builds are documented
separately in [FFI](ffi.md).

<a id="removed-on-purpose"></a>

## Unsupported features

A program that needs an unsupported feature gets a compile-time error. Supported templates
can avoid compiling unused branches that contain one. The main gaps:

- **Object model:** multiple inheritance beyond [one method-only secondary base](language/typing.md#a-method-only-secondary-base), subclasses of builtin types, general metaclasses and
  class decorators, dynamic attribute hooks, and attribute values looked up by names only the
  run time knows (their text and `hasattr()` are supported).
- **Values:** `bytearray`, `memoryview`, slice objects and
  general object unions; arbitrary-precision ints and dynamic `Any` values outside their opt-in
  prototypes ([promoting ints](python-int.md), [dynamic `Any`](dynamic-any.md)).
- **Syntax and calls:** mapping and general sequence/class patterns, `async` / `await`, `except*` and unrestricted argument
  expansion.
- **Run-time code:** `eval`, `exec` and imports chosen at run time.
- **Concurrency:** native threads and `asyncio`; CPython can run compiled extension modules in
  [process pools](concurrency.md) instead.

The [detailed restriction list](language/compatibility.md#rejected-rather-than-miscompiled)
records the less common cases.

## Syntax errors

Pystachy checks syntax even in unused functions and dropped import-time branches.
Diagnostics use `file:line: error:` and aim to match CPython's location and message.
Some messages are less specific, and parts of newer syntax are not fully checked.
[Syntax checks](language/semantics.md#syntax-errors) describe those boundaries.

## Deviations from CPython

The most important differences for supported programs are:

| Area | Difference |
|---|---|
| Integers | Overflow raises `OverflowError` instead of growing to arbitrary precision, unless the module opts in to promoting ints |
| Strings | Code-point length, indexing, slicing and search; Unicode case mapping and some other operations remain incomplete |
| Containers | Dictionary views are snapshots; string-set order differs from CPython |
| Exceptions | Uncaught errors omit the full traceback; native resource failures bypass handlers |
| Recursion | `sys.setrecursionlimit()` counts only calls that can recur, so the failing depth differs from CPython's; recursion that the native stack cannot hold raises `RecursionError`, even below a raised limit |
| Lifetime | Garbage collection runs in batches; `__del__` never runs; close files explicitly |
| Evaluation | Some consumers materialize their input before processing it |

These are not the complete differences. Read the
[compatibility reference](language/compatibility.md#deviations-from-cpython) when relying on
Unicode, mutation during iteration, exception details, file buffering or object identity.
The opt-in prototypes list their own [dynamic `Any`](dynamic-any.md#deviations) and
[promoting int](python-int.md#deviations) differences, and module-specific differences remain
in the [library compatibility reference](../lib/compatibility.md).

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
