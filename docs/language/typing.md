# Types and inference

This reference expands the [language guide](../language.md). For runtime differences and
unsupported forms, see [compatibility](compatibility.md).

## Supported types

| Type | Constraint |
|---|---|
| `int` | Signed 64-bit; overflow raises `OverflowError` |
| `float`, `bool`, `str` | Double-precision floats; strings hold UTF-8 with byte-based indexing |
| `list[T]`, `dict[K, V]` | One static element type, or one key and value type |
| `set[T]`, `frozenset[T]` | Elements must use the supported dict key types |
| `tuple[A, B, ...]` | Fixed shape, up to nine items; indexing requires an integer constant |
| Classes, dataclasses, `NamedTuple` | Fields have static types |
| `Callable[[A, B], R]` | Fixed positional signature; also supports zero arguments |
| `T \| None` | Optional values, including containers and `Callable` |
| `TextIO` | Text files |

Dict keys are `int`, `str`, or tuples containing `int`, `bool`, `str`, `str | None`, and
nested tuples of these. Floats, objects and frozensets cannot be keys or set elements.

`Optional[T]`, `None | T` and `Union[T, None]` are equivalent. Repeated members of
`Union[...]` collapse: `Union[T, T, None]` is optional and `Union[T]` is `T`.
General unions such as `int | str`, and a dynamic `Any` type, are unsupported.
`None` alone can annotate a return, but cannot be a container's entire element type.

`List`, `Dict`, `Set`, `FrozenSet`, `Tuple`, `Optional`, `Union`, `Callable`, `TextIO`
and `Self` work when imported from `typing` or `typing_extensions`. String forward
references work, including `list["Node"]`. `Self` in a class's methods and fields denotes
that class or its current specialization.

The supported `collections.abc` annotations use concrete container types:

| Annotation | Compiled type |
|---|---|
| `Mapping[K, V]`, `MutableMapping[K, V]` | `dict[K, V]` |
| `Sequence[T]`, `MutableSequence[T]` | `list[T]` |
| `MutableSet[T]` | `set[T]` |
| `Callable[[A, B], R]` | The same `Callable` as `typing` |

These types are invariant. A tuple or string is not a `Sequence`, and `isinstance()`
tests of these annotations are decided using the compiled type.
`str | os.PathLike[str]` simplifies to `str`, because paths must be strings;
`os.fspath()` returns its string argument. Other `PathLike` annotations are unsupported.

## Annotations

A function whose parameters are annotated uses those types. A missing return annotation
means `-> None`, unless the function is a template. There is no implicit `int` to `float`
conversion in an assignment, argument or return: write `1.0`, or convert explicitly.
Arithmetic and numeric list searches may mix integers and floats.

Parameter, return, class-body and module-level annotations follow CPython 3.13's evaluation
timing. They are checked even in unused imported definitions. A name must be bound when its
annotation is evaluated; use `"Node"` for a forward reference or
`from __future__ import annotations` to defer evaluation.

Evaluated annotations may name classes, supported typing forms, builtin generics, unions,
and type variables. A variable may be used as the whole annotation; unsupported aliases
are rejected where used. Calls, other operators, user-defined class subscripting, and
expressions that could execute user code are rejected. `os.PathLike` and the supported
`collections.abc` names are exceptions to the restriction on builtin module attributes.

`Final[T]` uses type `T` without enforcing immutability. `x: Final = value` infers the
value's type; a class-body value must be a constant. `x: Final` alone binds nothing.
`@overload` stubs are discarded when followed by their implementation; they do not create
runtime overload dispatch. Decorators accepted on unused imported definitions are not
necessarily supported on methods the program actually uses; see [module rules](modules.md).

## Variables and empty containers

Each variable has one type for its lifetime, fixed by an annotation or inferred assignment.
Python's local, `global` and `nonlocal` scoping rules apply.

Empty `[]` and `{}` take their types from an annotated variable, parameter, field or return
context. Otherwise their first useful operation determines the type: `append`, `insert`,
`extend`, item assignment, `+=`, `setdefault`, `get(key, default)`, or reassignment.
Nested forms such as `d.setdefault(key, []).append(value)` are supported. Empty `set()`
uses the same principle with `add`, `update`, or set operators.

Before inference succeeds, length and truth tests are allowed. A read earlier in the source
may obtain its type from a later operation when that operation's item type is known.
In a template, only code that runs for the selected argument types contributes to inference.
If a local container is never filled, its use context may supply its type.

A global container can be typed by a function's first use, including a function in another
module. From-imports and module-level aliases share that inferred type. Explicit annotations
are useful when a closure fills an initially empty container, or inference depends on code
that cannot yet be typed.

## Optional values and narrowing

A local first assigned `None` becomes `T | None` when another assignment supplies a known
`T`. Earlier reads use a known later assignment or their expected type. A local assigned only
`None` reads as `None`. Module-level inference works when the later assignments can already
be typed; globals that only functions fill need an explicit optional annotation.

Class types already permit `None`: `C` and `C | None` use the same nullable type. Builtin
exception annotations such as `Exception | None` are unsupported; objects of the program's
own exception classes may be optional.

Conditional expressions combining `T` and `None`, `x or None`, mixed displays, and templates
returning both produce optional values. `d.get(key)` returns `V | None`, and
`os.getenv(name)` returns `str | None`. Their defaults can also make the result optional.

An optional argument to a supported builtin operation is checked at runtime when necessary:
calling a string method or indexing a container that is `None` raises CPython's error.
Comparisons with `None`, truth tests, formatting, `str()` and `repr()` accept it.
For a user function, field or container operation expecting a nonoptional value, narrow first:

```python
def name_length(name: str | None) -> int:
    if name is None:
        return 0
    return len(name)
```

Narrowing applies to locals and parameters in these cases:

- The appropriate branch of `x is None`, `x is not None`, truth tests, and supported
  `isinstance()` tests, including `elif` and `else`.
- The right side of `x is not None and ...`, and conditional-expression branches.
- After an assertion or a guard whose `None` branch exits with `return`, `raise`,
  `continue`, `break`, `sys.exit()` or `assert False`.
- After an assignment of a nonoptional value, or a loop where every exit proves it.

An assignment that may restore `None` ends the narrowing; loop assignments are considered
throughout the body. Comprehensions have their own variables. Globals and fields are not
narrowed, because calls can change them: copy to a local and test it.
`isinstance(x, object)` does not narrow, since `None` is also an object.

Containers are invariant: `list[T]` cannot be passed as `list[T | None]`.
Some comparisons and concatenations can combine reference-based optional item types,
such as `list[str]` and `list[str | None]`; numeric optional items need separate storage,
so a `list[int]` cannot become a `list[int | None]`. Tuples can convert item by item.
`join()` and `writelines()` check optional string items at runtime.

An optional dict lookup key equal to `None` is absent: membership is false, `get()` and
`pop()` use a supplied default, and indexing, deletion or a required `pop()` raise
`KeyError: None`. Stores require a nonoptional key. A bool can look up or delete its equal
integer key, but cannot be inserted into a dict of integer keys, since its printed value
would differ from the integer.

## Function and method templates

A module-level function with an unannotated parameter is a template, compiled once for
each argument type combination that calls it. Annotated parameters keep their declared
types; the first value-returning statement determines an inferred return type.
Unsupported code becomes an error when that specialization needs it; syntax errors are
checked regardless of use.

```python
def double(value):
    return value + value

print(double(7))
print(double("hi"))
```

Type-dependent tests such as `isinstance(x, T)`, `hasattr(x, "name")`, tests against `None`,
and comparisons of fixed tuple or `**kwargs` length with an integer constant can eliminate
branches during compilation. Only reachable branches are compiled. `isinstance()` still
looks up its class names at runtime, so a class not yet defined can raise `NameError`.
Tests against `None` respect user-defined equality rather than replacing it with an identity test.

A parameter passed as `None` can be reinitialized with a statically determined type,
including `if value is None: value = default` when the specialization resolves that branch.
Assignments that require incompatible types across runtime branches or loops are rejected.
A template returning objects or optional values returns `None`
when it falls through; a template that always raises can use the result type expected by
its caller.

Ordinary methods with unannotated parameters, `*args` or `**kwargs` also specialize, excluding
`self` or `cls`. The supported binary operator, comparison, `__call__`, `__getitem__` and
`__contains__` methods can be templates. Other special methods require annotations;
`__init__` is handled by class specialization below. A template method cannot change a field's
established type, and comparison methods must return `bool`.

Function annotations mentioning a module-level `TypeVar` or `TypeVarTuple`, or a PEP 695
function type parameter (`def identity[T](value: T) -> T`), make those parts of the signature
inferred. Generic classes bind their type variables differently, as described below.

### Variadic arguments

`*args` is a fixed tuple for each call. Iterating a nonempty tuple requires one item type.
Tuple arguments and list or tuple displays can be unpacked into any callable:
`fn(*args)` or `fn(*[a, b])`. `print()` additionally accepts a list, string or dict through `*`.
Arbitrary runtime list unpacking into other functions is unsupported.

`**kwargs` has a fixed set of keyword names and value types for each call. It supports
indexing, `get()`, membership, length, truth tests, iteration and `keys()`. If its values
share one type, it also supports `values()`, `items()` and `dict(kwargs)`. Mutating it is
rejected; make a dict copy first. `fn(**kwargs)` forwards it, and a dict display with string
keys can also supply keyword arguments. Arbitrary runtime dict expansion is unsupported.

For an empty variadic tuple or kwargs record, loops over items can compile when the
element type is supplied by the parameter annotation. In particular, an empty
`kwargs.values()` or `kwargs.items()` loop must use the original annotated `**kwargs: T`
parameter, rather than an alias.

Arguments are evaluated in CPython's order: the callable first, then positional and starred
arguments, then keyword arguments. Each unpacking operation happens at its position.

### Empty template results

An empty list or dict returned by a template can get its type from a later fill or return,
or from its caller's annotation, argument type or other expected context. If none supplies a
type, the fallback is `list[int]` or `dict[int, int]`. A resulting type error identifies the
guess; annotate the receiving value to provide the intended type.

## Class templates and generic classes

A class specializes when its `__init__` has an unannotated parameter, variadic parameters,
or a parameter or constructed field using another class template. Calls whose fields have
the same types share a specialization: `Box(1)` and `Box(2)` share one, while `Box("s")`
uses another. Methods compile when needed; non-template special methods compile when the
specialization is created.

Each specialization is a distinct static type. One variable or container cannot hold both
`Box[int]` and `Box[str]`, although both satisfy `isinstance(value, Box)` and use the name
`Box` in runtime messages. Class attributes are shared. Compiler errors show the differing
field types.

A bare class-template annotation such as `-> Box` lets a function infer which specialization
it uses. Inside the class's own fields and methods, `Box` or `Self` denotes the current
specialization. It cannot be used as a field annotation in another class or dataclass.
When a class stores functions, an explicit `Callable` annotation lets different functions
with the same signature share a specialization. This also works for
`Callable[[A, B], Result]` where `Result` is a class template: the actual returned specialization
determines the callable's result type.

### Explicit generic classes

`Generic[T]` and `Generic[*Ts, R]` support `TypeVar` and at most one unpacked `TypeVarTuple`.
The constructor's arguments bind the variables:

```python
from typing import Generic, TypeVar

T = TypeVar("T")

class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

print(Box(7).value)
```

Supported matching forms are `T`, `list[T]`, `dict[K, V]`, `set[T]`, `frozenset[T]`,
`tuple[A, *Ts]`, `T | None`, and `Callable[[A, *Ts], R]`. A direct `None` argument binds
no type variable. Repeated bindings must join to a supported common type; integer and bool
bindings can join to `int`. Callable matching uses annotated positional parameters and
returns, or an existing `Callable` signature.

The resulting fields and methods use those bindings, including `tuple[*Ts]`,
`Callable[[*Ts], R]` and `*args: *Ts`. This supports the function wrappers used by
[`functools`](../../lib/README.md#functools-pystachys-own).

`Generic[...]` must be the class's only base. Every type variable must be bound by a
constructor argument; `Box[int]()` and other explicit class subscriptions are unsupported.
Use the bare class name or `Self` inside its methods and fields. PEP 695 class syntax
(`class Box[T]`) is unsupported. A method's separate type variables make it a function
template.

Function and class specializations share a limit of 4,096 per compilation. Additional
nesting and size limits are listed in [compatibility](compatibility.md#templates-and-empty-containers).

## Functions, callables and closures

A function value initially has the type of that particular function. This includes module
functions, supported builtins, lambdas, closures and bound methods. Calls through it use
the original signature, including keyword arguments and defaults. Passing it to a template
specializes for that function; a variable or field with an inferred function type cannot
later hold a different function.

Annotate with `Callable[[A, B], R]` to store different functions with one fixed signature.
They can be used in variables, parameters, fields, returns and containers, and as sorting
keys. A `Callable` requires positional arguments and an exact return type.
`Callable[..., R]` and keyword calls through a `Callable` are unsupported.

Object methods and supported string, list, dict and file methods bind their object when read:
`handler = obj.method`, `key=str.lower`, `write=file.write`. Bound methods compare equal
when they refer to the same method of the same object; their identity test is rejected.
Static and class methods, and numeric methods, cannot be stored as method values.
Function values expose `__name__` and `__qualname__`; printing them is unsupported.

A lambda or nested `def` creates a closure on each execution. Captured variables are shared,
so later assignments and `nonlocal` updates are visible. Captured variables must already be
assigned and typed, except a function's own name for recursion; they cannot later be deleted
or unbound by the end of `except ... as`. A closure in a comprehension cannot capture its
iteration variable. Nonconstant defaults are evaluated when the closure is defined.

Function decorators run when their `def` executes: expressions from top to bottom, then
defaults, then decorator calls from bottom to top. The function name binds the final result.
Methods support the dedicated decorators `@staticmethod`, `@classmethod` and recognized
`@overload` stubs. Other method decorators, including `@property`, `@final` and `@override`,
are unsupported when the class is used.

## Fields, dataclasses and NamedTuples

Fields come from class-body annotations or assignments to `self` in `__init__`. Their types
can be inferred from parameters, literals, constructors, declared function or method results,
function values, and supported container displays and operations. A template function's
inferred result is unavailable at field declaration time; annotate that field explicitly.

A class-body default is a class attribute, read by instances until they assign their own
value. Later changes to the class attribute affect those instances. Unannotated class-body
assignments infer their type, except in dataclasses and NamedTuples, where annotations are
required. Exception subclasses also inherit their base's fields and class attributes.

An annotated `NamedTuple` class supports defaults, methods, unpacking, constant indexing,
iteration, length, comparisons with tuples, `_replace()`, `_fields` and `_asdict()` when all
fields share a type. Only construction can assign its fields. There is no functional
`NamedTuple("Name", ...)` form, `_make()`, slicing, or a NamedTuple without fields.

Static and class methods can be called through their class or an instance. General inheritance
is unsupported; exception classes may inherit, and an inherited class method can specialize
for the exception subclass. See [compatibility](compatibility.md#classes-dataclasses-and-namedtuples)
for dataclass options and further restrictions.
