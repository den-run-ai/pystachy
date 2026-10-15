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
| `tuple[A, B]` | Fixed shape, up to nine items; indexing requires an integer constant |
| `tuple[T, ...]` | Runtime length; `T` is `int`, `float`, `bool`, `str`, or one of these with `None`; integer indexing checked at runtime |
| Classes, dataclasses, `NamedTuple` | Fields have static types |
| `Callable[[A, B], R]` | Fixed positional signature; also supports zero arguments |
| `A \| B` | Explicit scalar unions, or up to four non-overlapping native class/file members |
| `T \| None` | Optional values, including containers and `Callable` |
| `TextIO` | Text files |

`tuple(xs)` copies a supported homogeneous list or a string into an immutable
runtime-length tuple; later list mutation does not change it. String conversion follows
the existing UTF-8 byte iteration rules ([compatibility](compatibility.md)). `tuple(t)` returns an
existing tuple unchanged unless an annotation requests a representation conversion
([identity limitations](compatibility.md#functions-and-object-identity)). A fixed tuple literal can initialize `tuple[T, ...]`,
including `()`. Supported operations are `len`, truth tests, integer indexing,
iteration (also `enumerate`, `zip`, and `reversed`), `list(t)`, representation and
same-element-type equality and ordering. Bounds errors raise `IndexError` at runtime.
Optional scalar elements use boxes when needed; widening an immutable tuple to
optional elements copies its slots rather than reinterpreting numeric bits as pointers.

Runtime-length tuples currently do not support slicing, concatenation, repetition,
membership, unpacking, dictionary keys, or set elements. Their annotation is distinct
from the fixed shape used by `*args`; arbitrary iterators and generators are not yet
accepted by `tuple()`. This enables the existing `re.Match.groups()` implementation
without rewriting its capture loop or knowing the pattern's capture count at compile time.

Dict keys are `int`, `str`, or tuples containing `int`, `bool`, `str`, `str | None`, and
nested tuples of these. Floats, objects and frozensets cannot be keys or set elements.

`Optional[T]`, `None | T` and `Union[T, None]` are equivalent. Repeated members of
`Union[...]` collapse: `Union[T, T, None]` is optional and `Union[T]` is `T`.
Explicit closed scalar unions such as `int | str` are supported, including `None`.
Bounded native reference unions are also supported; a dynamic `Any` type is unsupported.
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

A function whose parameters are annotated uses those types. Ordinary functions and methods
infer a missing return annotation from their supported return statements, even when every
parameter is annotated or no arguments are taken. A function without a value return keeps
its `None` result type; an explicit `-> None` still rejects returning a value.
Unannotated `__str__` and `__repr__` use their required `str` result type and `__bool__`
uses `bool`; their bodies are checked against those contracts. An unannotated `__len__`
infers `int` or `bool`. Constructors keep their `None` result contract.
There is no implicit `int` to `float`
conversion in an assignment, argument or return: write `1.0`, or convert explicitly.
Arithmetic and numeric list searches may mix integers and floats. Equality and
membership also compare matching list, dict and tuple shapes with different numeric
item types exactly, including nested containers. This does not widen their stored types;
ordering between containers with different numeric item types remains unsupported.

Parameter, return, class-body and module-level annotations follow CPython 3.13's evaluation
timing. They are checked even in unused imported definitions. A name must be bound when its
annotation is evaluated; use `"Node"` for a forward reference or
`from __future__ import annotations` to defer evaluation.

Evaluated annotations may name classes, supported typing forms, builtin generics, unions,
and type variables. Aliases of supported classes can name those classes; other aliases are
not supported. Parameterized aliases such as `Row = list[str]` are rejected at their
definition, even when unused; value aliases such as `Pos = int` fail when used as annotations.
Generic class subscriptions such as `Box[int]` are supported
when they use the standard `typing.Generic` hook. Calls, other operators, custom class
subscripting, and expressions that could execute user code are rejected. `os.PathLike` and the supported
`collections.abc` names are exceptions to the restriction on builtin module attributes.

`Final[T]` uses type `T` without enforcing immutability. `x: Final = value` infers the
value's type; a class-body value must be a constant. `x: Final` alone binds nothing.
`@overload` stubs are discarded when followed by their implementation; they do not create
runtime overload dispatch. Decorators accepted on unused imported definitions are not
necessarily supported on methods the program actually uses; see [module rules](modules.md).

## Variables and empty containers

An unannotated local or parameter can change type at a simple assignment at the top
level of a function body. The compiler gives the new binding its own native slot;
the right-hand side still reads the previous binding. Expressions that need a
target type retain the previous context: for example, `items = [1]` followed by
`items = ["x"]` is still rejected. The new slot is created only after the RHS has
a concrete type. This works in ordinary AOT
and JIT compilation without a flag, runtime profiling, or a dynamic value box.

```python
def parse_count(value):
    value = value.strip()
    value = int(value)
    return value + 1

print(parse_count(" 41 "))  # 42
```

An explicit local or parameter annotation remains a contract for every assignment.
Stores inside branches and loops, augmented assignments, tuple/chained assignments,
globals and object fields retain their existing consistent-type rules. A simple
assignment after a branch or loop can start a new binding when the existing
unbound-variable analysis proves the name safe.

This bounded pass leaves a function unchanged when it contains nested functions or
lambdas, comprehensions, exception handlers, context managers, imports, `global`,
`nonlocal`, assignment expressions, generators, async constructs, or pattern
matching. Closures and variadic functions retain the existing rules. `None` and
initially untyped empty bindings retain the existing inference machinery. A name
that is deleted or may be read before assignment is not retyped. Python's scoping
rules and the compiler's existing unbound-variable checks continue to apply.

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

## Closed scalar unions

Explicit `A | B` and `Union[A, B]` annotations may combine `int`, `float`, `bool`
and `str`, optionally including `None`. Nested and repeated members normalize to
one type. These annotations are supported by default in both AOT and JIT modes.
They may appear in arguments, returns, local variables, fields and container values:

```python
def config_value(value: int | str | None) -> str:
    if value is None:
        return "missing"
    if isinstance(value, str):
        return value.upper()
    return str(value + 1)
```

A union stores an immutable tagged box; `None` is a null pointer. `isinstance()`
checks the tag and narrows a local or parameter in either branch, including through
assertions and exiting guards. `bool` remains a separate member and is an instance
of `int`, as in Python: test `bool` first if the following integer branch needs one
concrete type. Assignment updates the known type, and control-flow joins retain it
only when every incoming path agrees.

Globals, fields and cells assigned by a `nonlocal` closure are not narrowed across
calls. Copy their value to an ordinary local before testing it. The copy remains
valid when the original storage is changed because the tagged box is immutable.
Container types stay invariant: `list[int]` cannot become `list[int | str]`.

Truth tests, `bool()`, `str()`, `repr()`, printing, plain f-strings and `==`/`!=`
operate on scalar unions without narrowing. Lists, dictionaries and tuples containing
scalar-union values support printing and equality; lists also support membership, `count`,
`index` and `remove`. Search queries may name another scalar type: `True` and `1.0`
find an integer `1`. Numeric equality uses the existing exact int/float comparison,
including integers above the exact range of a float. `None` equals only `None`.

These operations select the existing native operation by the tag. A concrete value
keeps its native representation until it enters a union; widening a union reuses
its box. A concrete equality/search operand may allocate a temporary box. The boxes
do not create Python numeric object identity: the existing [NaN identity
deviation](compatibility.md#deviations-from-cpython) also applies to union payloads.

Numeric unions of `int`, `float` and `bool`, optionally including `None`, support
`+`, `-`, `*`, `/`, `//`, `%` and unary `+` or `-` without narrowing. Tag dispatch
reuses the native typed operations and their checked 64-bit integer, division and
exception behavior. Each operand evaluates once, left to right, before dispatch;
`None` raises `TypeError`. Results remain `int` or `float` according to the actual
operands; when both are possible the result is `int | float`, including when all
current calls happen to pass integers. Declare that result bound explicitly in
returns and mutable storage. Power, bitwise operations, and unions containing
strings or other nonnumeric members still require narrowing.

`format(value, spec)` and f-string format specifications select the native member's
formatter after evaluating the value and specification once. Numeric and string
members retain their supported formats; `None` accepts only an empty specification.

Narrow before other arithmetic, ordering and member methods. No union is inferred from unrelated assignments or
return values; annotate it explicitly. Arbitrary `Any`, recursive
JSON types, runtime compilation and speculative type assumptions are out of scope.
Boxing may allocate; this feature expands supported programs and makes no performance
claim.

## Mixed scalar and container unions

Explicit unions may also combine scalar types with `list[T]` and `dict[K, V]`,
optionally including `None`. Their elements and values may themselves be unions:

```python
def count(value: int | str | list[int | str] | dict[str, int | str]) -> int:
    if isinstance(value, list):
        value.append("seen")
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, str):
        return len(value)
    return value

print(count([1, "event"]))
```

The tagged box holds the original container pointer. Narrowing returns that same
list or dictionary, so identity, aliases and mutations are preserved. The collector
traces the box and its container using existing allocation rules. Concrete values
keep their ordinary native representation; boxing occurs at a union boundary.

A fresh list/dict display or list comprehension uses the expected union's single
matching container member, including empty displays. Existing mutable containers
remain invariant: `list[int]` cannot become `list[int | str]`, even through a union.
`isinstance(value, list)` cannot distinguish `list[int]` from `list[str]`; a union
containing both retains both members after that test and cannot be used as either
concrete list type.

This supports explicitly typed, finite-depth JSON-shaped data. Recursive aliases
such as `type Value = None | int | str | list[Value] | dict[str, Value]` remain
unsupported; this is not yet arbitrary-depth JSON or `Any`. Native class/file
members retain the separate reference-union restrictions below.

Truth tests, `bool()`, `str()`, `repr()`, printing and f-strings support these mixed
unions without narrowing, including nested containers and different list/dict
member types. Each operation dispatches to the original native value; truth tests
observe its current length, and formatting preserves the existing recursive
container representation guards. `format()` accepts an empty specification for
containers; a nonempty one raises the selected container's `TypeError`. A string
member uses string formatting, and a numeric member uses numeric formatting.

Equality and list membership, `count`, `index` and `remove` also work for finite
builtin value trees: scalars, lists, dictionaries and nested tuples. Each operand
retains its own descriptor, so `[1]` can equal `[1.0]` without interpreting integer
storage as floats. Separately boxing one container preserves its identity, including
when it is searched for inside another container; scalar boxes still do not create
numeric object identity. Fresh homogeneous search needles infer their own storage
type; heterogeneous displays still use explicitly declared element unions. Empty
or `None`-only displays retain context from an unambiguous declared member.

Dictionary equality keeps hashed lookup for matching key layouts. Different key
layouts compare keys pairwise, which can take quadratic time; ordinary string-keyed
JSON-shaped dictionaries use hashed lookup. User objects, files, functions and sets
inside mixed-value equality remain unsupported. Narrow before ordering, container
methods on a union receiver or indexing; there is no generic method dispatch.

## Native reference unions

Explicit unions can also hold up to four native class or `TextIO` types. This lets an
ordinary AOT/JIT-compiled function accept either a file or `io.StringIO`, or objects
from unrelated classes that implement the same method:

```python
from io import StringIO
from typing import TextIO

def read_character(stream: TextIO | StringIO) -> str:
    return stream.read(1)
```

Arguments, returns, fields, locals, list elements and dict values may use these
unions. A tagged box retains the original object or file pointer: passing through
storage preserves object identity, mutation and file position. The box and referenced
object remain reachable through normal GC roots. As with other Pystachy class types,
a union containing a class permits `None`; method calls on it raise `AttributeError`
before evaluating their arguments.

Method calls dispatch on the union member and use ordinary native class dispatch
within that member's family. Every member must declare the requested method, and
all implementations must return the same static type. Positional and keyword
arguments run once; each selected method uses its own defaults. A subclass may be
stored under one base member, but a union cannot contain overlapping class families
such as `Base | Child`. `isinstance()` checks the actual subclass; narrowing to a
whole declared member is supported, while narrowing a base member to a subclass is
not yet implemented.

Reference unions cannot mix with scalar or container members or exception types.
Callable fields, bound-method extraction and unpacked method arguments
are unsupported. Use a typed local for an empty-container argument that needs an
expected type. Narrow a local to a member before field access, identity/equality
comparison, truth testing or formatting. Containers remain invariant, and no union
is inferred from unrelated assignments. This adds deterministic native execution,
without profiles, an interpreter, runtime compilation or speculative assumptions;
boxing and dispatch have costs, so no performance improvement is claimed.

## Function and method templates

A module-level function with an unannotated parameter is a template, compiled once for
each argument type combination that calls it. Annotated parameters keep their declared
types; the first value-returning statement determines an inferred return type.
An ordinary function or method with fully annotated parameters, including one with no
arguments, uses the same inference when it has no return annotation and returns a value.
Its recursive calls can retain the existing `None` signature; value-returning recursion
before a result type is known requires an explicit return annotation.
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

### Contextual template results

An empty list, dict or set returned by a template can get its type from a later fill or return,
or from its caller's annotation, argument type or other expected context. If none supplies a
type, the fallback is `list[int]`, `dict[int, int]` or `set[int]`. A resulting type error identifies the
guess; annotate the receiving value to provide the intended type.
This also applies to direct `return []`, `return {}` and `return set()` results. Direct list
and dict empties can share an open-result specialization across caller container types.
Direct forwarding wrappers (`return empty(n)`) retain that result context, including through
multiple wrappers. When a forwarded empty result joins `None`, its caller context or the
same fallback supplies the optional container's layout. A recursive call may consume an
empty result before later inference only when that inference preserves the consumed layout.
A caller can also type fresh returned list, dict, set and tuple displays,
including homogeneous or nested displays and calls inside their items:

```python
def pair(a, b):
    return [a, b]

values: list[int | float] = pair(1, 2.5)
integers: list[int | float] = pair(1, 2)
```

Such contextual results specialize for both argument types and result context; scalar values
retain their original types. Fresh return branches can use the same explicitly named element
union; unrelated return types still do not infer a union. Stored mutable containers, fields
and declared function results are never widened. Context follows direct displays and calls;
other operations retain their existing inference. A comparison's context is a hint: an
incompatible fresh display keeps its own element types, preserving exact integer comparisons.

A template consisting of simple local assignments and a final return may assign a fresh
display or call to a local and return it, with up to 32 single-assignment aliases. Each alias
may only be read by the next alias or the final return. Mutations, escapes, captures,
reassignments, annotated locals and control flow retain their existing inference rules;
stored parameters, fields and globals are never widened.
User method calls, bound method values and callable fields retain the same expected result context.
A union context supplies a list or dict result's type when exactly one member has the same
container kind; ambiguous contexts retain the fallback above.

For mixed scalar list literals, an error names a supported union annotation, such as
`xs: list[int | float] = [1, 2.5]`. Rows can use unions within tuple fields:
`rows: list[tuple[str, int | float]] = [("a", 1), ("b", 2.5)]`.
The annotation preserves the individual values' types; it does not convert integers to floats.

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
`tuple[A, *Ts]`, `T | None`, `Iterable[T]` (or `Iterator[T]`), and
`Callable[[A, *Ts], R]`. Iterable matching uses the item type of a supported list, set,
dict, string or homogeneous tuple; an empty tuple binds nothing. `None` alone cannot determine
a type variable. Repeated bindings must preserve the values’ types and join to a supported common type,
or use the direct-scalar fallback below (mixed int/bool values never become plain int). Callable matching uses annotated positional parameters and
returns, or an existing `Callable` signature.

The resulting fields and methods use those bindings, including `tuple[*Ts]`,
`Callable[[*Ts], R]` and `*args: *Ts`. This supports the function wrappers used by
[`functools`](../../lib/README.md#functools-pystachys-own).

`C[X, Y]` names a specialization for a generic class whose `__init__` annotates every
parameter and has no `*args`, `**kwargs` or `TypeVarTuple`. It works in variable, field,
parameter and return annotations, including nested types such as `list[C[int]]`, and in
constructor calls such as `C[int]()`. The class statement must precede the annotation.

Constructor arguments bind first; the named specialization or surrounding annotation fills
variables the arguments leave unbound. Thus `q: Stack[int] = Stack()` and
`Stack[int]([])` can type empty containers, while `Box[float](1)` still infers `Box[int]`.
An enclosing annotation remains a contract and rejects a conflicting specialization.
Nonempty homogeneous displays infer the same types as stored arguments. Empty and nested
empty displays use contextual types where their contents do not already determine a type.
Heterogeneous displays with known item types can use an explicit union context. Opaque
calls and operations infer normally; their syntax alone does not request a union layout.
A variable that neither arguments nor context bind is an error.

When ordinary argument matching cannot bind the type variables consistently,
fitting named union or optional parameter types resolve the conflict:
`Pair[int | float](1, 2.5)`, `Pair[int | None](1, None)` and
`p: Pair[int | float] = Pair(1, 2.5)` bind both parameters annotated `T` to
their named type. Existing conversions preserve each value's representation,
including integer precision, and handle defaults and unpacked arguments too.
An enclosing generic annotation requires its named storage even for homogeneous
arguments: `p: Pair[int | float] = Pair(1, 2)` stores union-valued fields that can
later accept a float. This also works for annotated parameters, returns and fields,
including calls with explicit type arguments. A constructor subscription alone remains
a hint: `Box[int | str]("x")` still stores a concrete `str`, and
`Pair[int | float](1, 2)` still makes `Pair[int]`. Use
`p: Pair[int | float] = Pair(1, 2)` when later field writes need to accept floats.
Existing objects stay invariant, and container members must fit exactly: neither `Box[int]` nor `list[int]`
can be reinterpreted with wider mutable contents.

Without a named specialization or surrounding generic annotation, conflicting direct
scalar `T` arguments can infer a closed union: `Pair(1, 2.5)` and `Pair(1, "x")`
retain both Python value types. This fallback supports `int`, `float`, `bool`, `str`
and `None`, including existing scalar unions. Ordinary consistent inference still wins.
Every constructor annotation that mentions a type variable must be a direct type
variable; nested forms such as `list[T]`, variadic bindings, and non-scalar conflicts
still need annotations. This does not add container covariance, mixed-display or
function-return union inference. Nested generic parameter forms still require their
arguments' container types to match; this does not infer wider mutable contents.

A method's `-> T` promises the same bound type as its fields. With
`Pair(True, 2.5)`, that type is `bool | float`; a method adding its two `T` fields
can also produce `int` (from `bool + bool`), so `-> T` is rejected. Annotate this
numeric result as `-> int | float`, or use an enclosing
`Pair[bool | int | float]` annotation when the fields and result need all three
members. The compiler does not track correlations between individual union fields.
The inferred union uses the existing tagged boxes; per-argument unboxed generic
fields are separate work, and operations outside the supported union surface
still require narrowing.

`Generic[...]` must be the class's only base. Use the bare class name or `Self` inside its
methods and fields, or an explicit specialization such as `"Pair[V, K]"`. PEP 695 class
syntax (`class Box[T]`) is unsupported. A method's separate type variables make it a
function template.

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
Methods support the dedicated decorators `@staticmethod`, `@classmethod`, read-only
`@property` and recognized `@overload` stubs. Other method decorators, including `@final` and `@override`,
are unsupported when the class is used.

A property getter takes only `self` and needs a return annotation. Reading `obj.value`
calls the getter each time; inherited getters, property overrides and `super().value`
use the ordinary method dispatch. A callable-valued property can be called as `obj.value(args)`.
Assignment, setters/deleters, property objects read through the class, and replacing a
property with a field or method are unsupported. `hasattr(obj, "value")` on a property
is rejected because it must run the getter; read it in `try/except AttributeError` instead.

## Fields, dataclasses and NamedTuples

Fields come from class-body annotations or assignments to `self` in `__init__`. Their types
can be inferred from parameters, literals, constructors, declared function or method results,
function values, and supported container displays and operations. When specializing a class
template, a field can also use an ordinary generic function's inferred return type if its
positional arguments and omitted defaults have known types. This uses normal function
specialization and does not execute the helper or its defaults during inference. Keyword or
unpacked arguments, local call targets, and helpers whose return is needed before class
specialization still require an explicit field annotation.

A class-body default is a class attribute, read by instances until they assign their own
value. Later changes to the class attribute affect those instances. Unannotated class-body
assignments infer their type, except in dataclasses and NamedTuples, where annotations are
required. Supported subclasses also inherit their base's fields and class attributes.

An annotated `NamedTuple` class supports defaults, methods, unpacking, constant indexing,
iteration, length, comparisons with tuples, `_replace()`, `_fields` and `_asdict()` when all
fields share a type. Only construction can assign its fields. There is no functional
`NamedTuple("Name", ...)` form, `_make()`, slicing, or a NamedTuple without fields.

Static and class methods can be called through their class or an instance, subject to the
inheritance restrictions below. See [compatibility](compatibility.md#classes-dataclasses-and-namedtuples)
for dataclass options and further restrictions.

## Single inheritance

An ordinary class may derive from one previously declared ordinary class, including an
imported class. Annotate its `__init__` parameters; constructor-inferred class templates and
`Generic` classes cannot participate in a hierarchy. Fields retain their declared or inferred
types, and the existing field-inference rules still apply.

Subclasses inherit fields, class attributes, methods and `__init__` when they do not define
their own. Instance methods can override inherited methods. Calls through a base annotation
or `list[Base]` select the receiver's concrete implementation, including calls made inside
inherited methods and bound methods. Each possible implementation must accept the call's
arguments, and its results must have a common supported type.
Converting a bound method to `Callable` also requires compatible parameter types and
annotated return types throughout that method's hierarchy, preserving method equality
across base and derived views of the same receiver.

`super().method(...)` starts at the base of the class defining the method, even when a further
subclass inherits that method. `super(C, self)` may name that class or one of its ancestors;
`Base.method(obj, ...)` explicitly selects the named base's implementation. These forms keep
the concrete receiver for further method calls. Runtime `isinstance(obj, Derived)` checks the
hierarchy and narrows a base-typed local or parameter on the matching path, exposing derived
fields and methods. This also works after `assert isinstance(obj, Derived)` and a guard such
as `if not isinstance(obj, Derived): return`. The reference and its native representation stay
unchanged; calls still select the actual subclass's override. Reassignment and control-flow
joins discard refinements that no longer hold. Globals, fields and locals assigned by a
`nonlocal` closure are not refined; copy a reference to a stable local and test that local.
Only a single named derived class refines a base type; tuple/union tests and exception-class
narrowing retain their existing restrictions.

Instance reads of class attributes honor subclass defaults and instance assignments. A class
attribute may be rebound through its defining class; assigning an inherited attribute through
a subclass that has not declared its own default is unsupported.

Multiple inheritance, builtin subclasses, dataclass and NamedTuple inheritance, decorated
subclasses, field/method name collisions, and overriding static or class methods are
unsupported. Inherited class methods
using `cls` retain restrictions on default values, imports and calls through a base-typed
object. Exception classes follow the [exception rules](semantics.md#user-exception-classes).
