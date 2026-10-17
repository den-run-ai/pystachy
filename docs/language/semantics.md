# Execution and expressions

This reference expands the [language guide](../language.md). Types, function specialization,
closures and class fields are described in [typing](typing.md); imports and builtin APIs are in
[modules](modules.md).

## Statements

| Category | Supported statements |
|---|---|
| Assignment | Simple, chained, annotated and augmented assignment; tuple/list unpacking, with one starred target or none, and swaps |
| Control flow | `if` / `elif` / `else`, `while`, `for`, loop `else`, `break`, `continue`, `return` |
| Scope and definitions | `global`, `nonlocal`, `def`, nested function definitions, lambdas, supported class definitions |
| Runtime checks | `assert`, `raise`, `try` / `except` / `else` / `finally` |
| Resources | `with` over files and [context managers](#context-managers) of the program's classes, several items, with or without parentheses |
| Deletion | `del` of a local, list item, dict key or supported object's item |
| Other | Imports, docstrings, `pass` and `...` |

`+=` on a list extends it in place. Object in-place operators use `__iadd__` and the
corresponding methods when supported. Deleting a variable makes later reads raise
`NameError` or `UnboundLocalError`; deleting a global from a function is unsupported.

A starred target, as in `head, *body, tail = xs`, gets a new list of the items the other targets
leave. It takes what a `for` loop iterates, and `range()`, `enumerate()`, `zip()`, `map()`,
`filter()` and generator expressions; every item is taken before the first target is assigned.
Too few items raise CPython's `ValueError`. Of a tuple, the starred list holds its items'
common type; items of types no one type holds need an annotation (`body: list[int | str]`).

Loops can consume ranges, lists, strings, dictionaries, sets, files, homogeneous tuples and
NamedTuples, supported objects, and dictionary `items()`, `keys()` and `values()`.
`enumerate(..., start=...)`, `zip()` and `reversed()` work in supported contexts.
A dictionary or set whose size changes while its iterator is active raises `RuntimeError`.
`zip()` creates its operands' iterators in order, before iteration starts.

Restrictions on nested iterator-like expressions, snapshots and mutation are listed in
[compatibility](compatibility.md).

## Literals and formatting

Numeric literals support decimal, hexadecimal, octal, binary and underscore separators.
Strings support raw and triple-quoted literals, implicit concatenation and escapes other
than `\N{...}`.

F-strings support `!r`, `!s`, `!a`, debug `=`, nested format specifications and the
format-spec mini-language. Replacement fields follow Python 3.12's grammar (PEP 701): they may
reuse the f-string's quote, nest f-strings, and hold backslashes, newlines and comments.

`%` formatting requires a literal format string, or a module global that one module-level
assignment binds to one (`FMT = "%8.3f"`, also `Final`) where nothing else in the program, not
even a function's local, binds its name. It supports `s r a d i u x X o e E f F g G c`, flags,
widths and precisions, but not named substitutions, `*` widths or precisions, or integer
precisions. A variable format string such as `fmt % value` is rejected.

`str.format()` and `str.format_map()` (also `str.format(FMT, ...)`) also require a literal format
string or such a module global, compiled like an f-string: automatic and manual numbering, keyword
fields, `.attr` and `[key]` lookups, `!r`, `!s`, `!a` and nested fields in a spec. The arguments
are evaluated first, then the fields are formatted left to right; a malformed format, mixed
numbering, a missing argument or an unknown conversion raises CPython's error when that field is
reached. `*` unpacks a tuple, or a list after the other positional arguments; `**` unpacks a
function's `**kwargs`, a dict display with string keys or one `dict[str, T]`. `"...".format` can
be `map()`'s function, but neither method is otherwise a value, and `fmt.format(value)` of another
variable format string is rejected.

## Operators and containers

Supported operations include arithmetic, bitwise operations, chained comparisons,
`in` / `not in`, boolean operations returning operands, conditional expressions, negative
indices, string, list and tuple slices with optional steps, and assignment to and deletion
of list slices. Integer `//` and `%` floor as in Python;
true division is correctly rounded, and int/float comparisons are exact within the
supported types.

Container expressions include list, dict, set and tuple displays; list, set and dict
comprehensions; and tuple concatenation or repetition by a constant. Set and frozenset
operations support union, intersection, difference, symmetric difference, subset ordering
and in-place forms.

A comprehension or generator expression may have several `for` and `if` clauses. As in
CPython, its first iterable is evaluated once in the enclosing scope; each later iterable and
condition is evaluated for every item of the clauses before it, and the clauses' variables
belong to the comprehension: a later `for` clause that binds an earlier clause's variable
binds the same variable. A dict comprehension evaluates each key before its value; a repeated
key keeps its first position and takes the last value. A clause or `for` target that reads a
variable which only its own or a later `for` clause binds is rejected (CPython raises
`UnboundLocalError`), as is a rebinding to another type that a clause between the two can read.
A starred item in a list or tuple display, `[a, *xs, *range(n)]`, takes the iterable's items
where it stands. A tuple display whose starred items are tuples is a tuple of their items;
with another iterable, it is a runtime-length tuple.

An assignment expression, `x := v`, assigns `v` to `x` as `x = v` would, in the function or
module code around it, also from a comprehension or generator expression (PEP 572); its value is
`v`. Tests such as `if (m := pattern.match(s)) is not None:` narrow `x` as a test of the name
does. Where the expression may not have run (after `and` or `or`, in one arm of a conditional
expression, in a comprehension over nothing), a later read of `x` raises `UnboundLocalError` or
`NameError`. This also covers assignment expressions in lambda defaults: the defaults run
when the lambda is created. A comprehension's filters run before its element. An unannotated
template parameter specialized to `None` cannot be rebound by a conditional assignment
expression; annotate that parameter as `T | None` to allow both values.

`is` and `is not` are supported for identity-bearing values, not numbers.
Booleans use their two fixed values, so `flag is True` behaves as equality.
Comparisons with `None` are supported where the static types permit them.

## Iterator-like expressions

Generator expressions, `range()`, `reversed()`, `enumerate()`, `zip()`, `map()` and
`filter()` can be direct arguments of `list`, `sorted`, `sum`, `min`, `max`, `any`,
`all`, `math.fsum`, `math.prod`, `str.join` and `list.extend`, those that give key/value pairs
of `dict`, the value assigned to a list slice or to a starred target, or a `*` item of a list
or tuple display, subject to each consumer's item types. `tuple()` also accepts generator
expressions and `range`/`map`/`filter`/`reversed` calls producing supported scalar or optional
scalar items. Direct `enumerate`/`zip` items are tuples; project a scalar in a generator
expression first ([runtime-length tuples](typing.md)).

These expressions are compiled for their consumer rather than creating a general generator.
`map()` and `filter()` evaluate their function before iteration.
`any()` and `all()` stop at the deciding item, including over files.
`list.extend()` appends each generated item as it is produced; a slice assignment takes the
items once the list and the slice's bounds are evaluated.
`x in range(...)` is also supported.

Some consumers materialize input before processing it; see the
[evaluation-order differences](compatibility.md#containers-and-evaluation-order).

## Range objects

`range()` anywhere else is a range object, CPython's: a value to assign, pass, return or store
(`r: range` annotates one), as in `codecs.make_identity_dict(range(256))`. It is an object of the
class in [`lib/_pystachy_range.py`](../../lib/_pystachy_range.py), which the compiler loads for a
program that may use one: one that reads the builtin `range` other than as a `range(...)` it steps
through itself, as above. A `for` loop or comprehension over a range object, and the consumers
above, step through its numbers as through `range(...)` itself; `enumerate()`, `zip()` and
generator expressions take them one at a time, and `range()` may be nested in `enumerate()` and
`zip()`. `len()`, `bool()`, `x in r` of an int (an `int | None` that is None is in no range),
`r[i]` with negative indices, slices (ranges), `r.start`, `r.stop` and `r.step`, `==` and `!=`
(as sequences: `range(0) == range(5, 5)`, and never equal to a value of another builtin type),
`hash()`, `r.index(x)`, `r.count(x)`, `reversed(r)` where `reversed()` is supported, `iter(r)`,
`repr()` and `str()`, `isinstance(r, range)`, `type(r).__name__` and `type(r) is range` behave
as in CPython. A range of 2**63 numbers or more is held, but `len()` of it raises CPython's
`OverflowError`, and an item or slice bound beyond 64 bits raises Pystachy's
([integers](compatibility.md#numbers)). The compiler rejects the operations that CPython would
reject at run time (ordering comparisons, assigning an attribute), `in` of other than an int or a
bool, `r[i]`, `index()` and `count()` of other than an int (also of a bool), `==` with a value
that may be `None` but is not a range, `type(r)` as a value, and the reflection of `dir()` and
`vars()`.

## Iterators

`iter(x)` returns an iterator object that shares its position with every use, as CPython's:

```python
it = iter(lines)
header = next(it)
for line in it:  # the lines after the header
    print(line)
```

`iter()` accepts lists, strings, homogeneous tuples, dictionaries and their `keys()`,
`values()` and `items()`, sets, `range(...)` and range objects, files and objects with
`__iter__`. A file is its own iterator. A builtin container's iterator is an object of a class in
[`lib/_pystachy_iterators.py`](../../lib/_pystachy_iterators.py): it reads a list's current
length at each step, fails if a dictionary or set changes size, and stays exhausted once
`StopIteration` is raised. `next(it)` calls `it.__next__()` (a file's next line);
`next(it, default)` returns the default instead of raising `StopIteration`, and has the type
of both, such as `T | None` for a `None` default. `iter(callable, sentinel)` and `iter()` of
`enumerate()`, `zip()`, `map()`, `filter()`, `reversed()` or a generator expression are
unsupported.

An iterator's type is its class. `Iterator[T]` and `Iterable[T]` annotations (`typing`'s or
`collections.abc`'s) therefore type nothing, as a class template's name does: a function with
such a parameter or return is compiled for each call's argument types, a class whose
`__init__` takes one or calls `iter()` is a class template, and an annotated variable or field
has its value's type. A `Generic[T]` class's `Iterable[T]` parameter binds `T` to the items.

## Generators

A function or method whose body contains `yield` or `yield from` is a generator function.
Calling one runs none of its body: it makes a generator object, which runs to its next `yield`
each time a consumer asks for an item. Generator functions that yield one type and take one
type from `send()` share one static type (`Generator[T]` in messages, `Generator[T, S]` where
the send type `S` is not `None`). A generator function's return annotation is `Iterator[T]`,
`Iterable[T]` or `Generator[Y, S, R]`, from `typing` or `collections.abc`; elsewhere
`Iterator[T]` and `Iterable[T]` type nothing (see [iterators](#iterators)), so a parameter
annotated so takes generators as well as iterator objects, and `Generator[T, None, None]` names
a generator's type (`holder: list[Generator[int, None, None]] = []`). A generator that takes `S`
is also one that takes `None`. An unannotated generator function is a template: its first
`yield` gives the type for each call's argument types, and its send type is `None`. An
`__iter__` or `__reversed__` that yields makes the generator that iterates its object.

| Use | Behavior |
|---|---|
| `for` loops, `enumerate()`, `zip()`, comprehensions | Each item as the generator yields it; a finished generator yields nothing |
| `next(g)`, `next(g, default)`, `g.__next__()` | The next item; `StopIteration` (or the default) once it has finished |
| `iter(g)`, `g.__iter__()`, `iter(o)` | `g` itself; the generator `o.__iter__()` makes |
| `sum`, `min`, `max`, `any`, `all`, `math.fsum`, `math.prod` | The items as they come; `any()` and `all()` stop at the deciding item |
| `list`, `tuple`, `sorted`, `set`, `frozenset`, `str.join`, `list.extend` | All the items |
| `x in g` | Iterates until an item equals `x` |
| `a, b = g`, `a, *rest = g` | One item for each target, then one more step that must find `g` finished; with a starred target, all the items |
| `yield from x` | Each item of `x`; for a generator, delegation (PEP 380: `send()`, `throw()` and `close()` go on to `x`), and `r = yield from g()` is `g`'s return value |
| `g.send(v)` | Resumes `g` with `v` as the value of the `yield` where it is suspended; returns the next item, or raises `StopIteration` once it has finished; `send(None)` is `next(g)`, and another value cannot start `g` (`TypeError`) |
| `g.throw(e)` | Raises `e` (an exception, an exception class or a call of one) at the suspended `yield`; returns the next item if `g` handles it, raises `StopIteration` if `g` finishes, and the exception if it leaves `g`. Into a generator that has not started or has finished, `e` is raised as it is |
| `g.close()` | Raises `GeneratorExit` at the suspended `yield` where a `try`, `with` or `yield from` there may see it, else finishes `g` at once; what `g` raises then comes out of `close()`, and a `yield` after `GeneratorExit` raises `RuntimeError: generator ignored GeneratorExit` |
| `x = yield v` | The value `send()` gave as it resumed the generator: `None` from `next()`, a loop or `throw()`. In a generator annotated `Generator[Y, S, R]` its type is `S \| None`; with a send type of `None`, `None` |

A generator expression that no consumer takes directly, such as one stored in a variable or
returned, is an anonymous generator: its first iterable is evaluated where it is written and
the rest as it runs. Globals are read when it runs. Variables of the enclosing function that it
reads must not be bound again (and must be assigned) where it is written: it reads their values
then.

A `for` loop over a generator that its iterable expression has just made (a call of a generator
function, or of an `__iter__` or `__reversed__` that yields, also inside `enumerate()`, `zip()`
or `reversed()`) closes the generator when the loop is left by its
end, `break`, `return` or an exception, before the code after the loop runs. Closing raises
`GeneratorExit` at the suspended `yield`, so `finally` blocks, `with` blocks and
`except GeneratorExit` run, as in CPython. What the close raises, and a `yield` after
`GeneratorExit`, are reported on stderr as CPython reports exceptions it ignores, and the loop's
exit goes on. Exceptions raised in a loop's body never enter the generator. An exception that
leaves a generator's body finishes the generator; a `StopIteration` becomes
`RuntimeError: generator raised StopIteration` (PEP 479). A generator that resumes itself raises
`ValueError: generator already executing`.

A generator suspended inside a `with` block keeps its context manager: closing it, or throwing
into it, runs the manager's `__exit__` as CPython does, and `contextlib.contextmanager` drives a
generator through these calls (see [context managers](#context-managers)).

`close()` is supported as a statement; its value (what a generator returns as it closes, in
CPython 3.13) is not. `throw(type, value, traceback)`, `async` generators and frame
introspection are not supported, nor `yield from` of an iterator that is no generator in a
generator that takes a value from `send()` (CPython sends the value on to the iterator, which has
no `send()`). A generator the program drops while it is suspended is not closed (see
[deviations](compatibility.md#memory-and-resource-lifetime)).

<a id="context-managers"></a>

## Context managers

A `with` statement takes a file (`with open(...) as f:`) or an object of a class of the program
that defines `__enter__` and `__exit__` (PEP 343). `__enter__()` gives the `as` target; an
exception in the block goes to `__exit__(type, value, traceback)`, which suppresses it by
returning a true value, and leaving the block otherwise (its end, `break`, `continue`,
`return`) calls `__exit__(None, None, None)`. Several items nest as CPython nests them, and a
name the block binds may be unbound after a suppressed exception. A class without `__enter__`
or `__exit__` is a compile-time error with CPython's message; a manager that is `None` raises
CPython's `TypeError`.

`__exit__` may be annotated as typeshed annotates it, left unannotated (each of its two calls is
compiled for its arguments), or take `*args`:

| Parameter | Annotation | Value |
|---|---|---|
| The exception's class | `type[BaseException] \| None` | `None`, or the class: `__name__`, `issubclass()`, `str()` and `repr()` (`<class 'KeyError'>`) |
| The exception | `BaseException \| None` | `None`, or the exception: `str()`, `repr()`, `isinstance()`, `is`, `raise` |
| The traceback | `TracebackType \| None` (`from types import TracebackType`) | `None`, or an object with none of a traceback's attributes |

`type(e)` of an exception is such a class value, and `sys.exception()` the exception being
handled (or `None`). `e.__cause__` is the cause that `raise ... from c` gave, or the
`StopIteration` that PEP 479's `RuntimeError` replaced.

`lib/contextlib` provides `contextmanager` (also as a decorator, `@cm()`), `closing`,
`nullcontext`, `suppress` (as a `with` statement's item, with exception classes named) and
`AbstractContextManager`; `io.StringIO`, `io.BytesIO`, `io.TextIOWrapper` and `_thread`'s locks are context managers too
([library](../../lib/compatibility.md#contextlib)).

## Object protocols

Object operations use the following methods. In supported ordinary hierarchies, instance-method
overrides dispatch on the concrete receiver; the static type still controls which operations
and fields are available. See [single inheritance](typing.md#single-inheritance).

| Operation | Methods |
|---|---|
| Binary operators `+ - * / // % @ & \| ^ << >>` | `__add__` and the corresponding methods |
| In-place operators | `__iadd__` and counterparts, otherwise the binary method |
| Unary `-`, `+`, `~` | `__neg__`, `__pos__`, `__invert__` |
| `abs(o)`, `divmod(o, x)` | `__abs__`, `__divmod__` |
| Equality and ordering | `__eq__`, `__ne__` and rich comparisons |
| Truth and length | `__bool__`, `__len__` |
| Representation | `__str__`, `__repr__`, `__format__` |
| Call, indexing, assignment, deletion | `__call__`, `__getitem__`, `__setitem__`, `__delitem__` |
| Membership and iteration | `__contains__`, or supported `__iter__` |
| `reversed()` | Supported `__reversed__` |

Rich comparisons use reflection, such as trying `b.__gt__(a)` for `a < b`.
Reflected arithmetic methods such as `__radd__` and `__rdivmod__`, and object `__pow__`, are
unsupported.
Objects in containers compare, sort and print through their methods.
Lists and tuples test items with equality before ordering them, then compare length if all
common items are equal. Sorting and `min()` use `<`; `max()` uses `>`.

Object calls accept the keyword and default arguments of `__call__`.
For `o[k] += value`, both indexing and assignment methods are used.
Membership uses `__contains__`, taking its result's truth; without it, membership searches
the supported iterator.

An `__iter__` returns an iterator object: its own object or another class's object with a
`__next__` method, whose return type gives the items. Its return annotation may be omitted
(the returns decide it), name the class (`-> "C"`, `-> Self`) or be `Iterator[T]`. Loops,
comprehensions, unpacking, `x in o`, `math.dist()` and the consumers above call `__next__`
until it raises `StopIteration` or a subclass, also from a nested `next()`; any other
exception propagates.
`__iter__` runs once before the loop, and `__next__` once per item. A comprehension also calls
the iterator's own `__iter__`, as CPython 3.13 does. `any()`, `all()`, `sum()`, `min()`,
`max()` and `in` take items as they come; `list()`, `tuple()`, `sorted()`, `str.join()` and
`set()` take them all first. `list()`, `tuple()`, `sorted()` and `list.extend()` call the
iterable's `__len__`, if present, as a length hint; a slice assignment does not, as in CPython.

An `__iter__` annotated `-> Iterator[T]` or `-> Iterable[T]` whose returns are all `iter(xs)`
of a list, tuple, string or object with such an `__iter__` keeps a faster form: a loop
steps through that list directly. A supported `__reversed__` has that form, or returns
`reversed(xs)`, whose items it copies when it returns; every consumer of `reversed(o)` steps
through the iterator it returns. Calling `o.__iter__()` is unsupported. Generator
implementations are unsupported.

A missing protocol method produces a compilation error using CPython's message.
An object that is `None` when the operation executes raises the corresponding runtime error.

<a id="reflection"></a>

## Reflection

Reflection works on values whose possible classes the compiler knows: one class, an ordinary
hierarchy (the object's class tag selects its class), or a reference union (its member tag,
then the class tag). The program's own classes and dataclasses are supported, and so are the
builtin types where noted; exception objects, NamedTuples and file objects are not, nor are
classes with private attributes (`__x`), whose names CPython mangles and Pystachy does not
(see [compatibility](compatibility.md#functions-and-object-identity)). What Pystachy cannot
match is a compile-time error that names the missing feature: a value whose type only the run
time knows (#487), names that need per-object storage (#489), or a class object as a value (#7). The compiler's side is described in [internals](../internals.md#reflection).

### Types and their names

`type(x).__name__`, `__qualname__` and `__module__`, and `x.__class__.__name__` (also
`self.__class__.__name__` in a method), give CPython's names: the class's own name, `int`,
`str`, `bytes`, `list`, `NoneType`, ... for builtin values, and `builtins` as their module. Inside an
expression, `type(a) is C`, `type(a) == type(b)`, their negations and `x.__class__ is C` compare
the exact classes (`type(True) is bool`, `type(True) is int` is false). `str()` and `repr()` of a
reference union print each object as its own class prints it. `type(x)` as a value (a class
object) is unsupported.

### Attribute names the compiler knows

`getattr(o, "name")`, `setattr(o, "name", value)` and `hasattr(o, "name")` with a literal name
read, assign and test the attribute as `o.name` would; `setattr()` evaluates `o` and the value
first, as CPython evaluates its arguments, and then assigns through a property's setter, checks
`__slots__` and raises `FrozenInstanceError` as an assignment does. `getattr(o, "name", default)`
evaluates the default first, then gives the attribute where the object's exact class has it
(a field that `__init__` may leave unassigned: where its flag says it is set) and the default
where it has not; a property's getter that raises `AttributeError` gives the default, as
CPython catches it. `hasattr()` of a property runs its getter likewise, and `hasattr()` of a value
that may be an object of one of several classes (a union of classes) answers for its class. On a
hierarchy's base,
`getattr(o, "name")` of an attribute only a subclass has reads it where the object has it and
raises CPython's `AttributeError` elsewhere.

A `for` loop, or a list comprehension, over a constant set of names unrolls where its body uses
the name with `getattr`, `setattr`, `hasattr` or `operator.attrgetter`/`methodcaller`: a tuple
or list display of `str` literals, a variable bound once to one and only iterated (a local, or a
variable of the main program), `dir(x)` and `sorted(dir(x))`, `dataclasses.fields(X)` (whose
items' `.name` is the field's name) and `vars(x).items()`. The body is compiled once per name
with the name read as that literal; the loop variable is still assigned, and `continue`, `break`
and an `else` block keep their meaning. Tests of the literal (`name.startswith("test_")`,
`name == "x"`, `name in ("a", "b")`) are decided in each copy. A function's parameter is not a
variable bound once (a loop may iterate its argument before the function binds it again). Over
`dir(x)` and `vars(x)`, one run of copies is compiled per exact class `x` may have, with a
variable `x` narrowed to that class; `dir(x)`'s list is made as the loop starts, a field
`__init__` may leave unassigned in it where it is set then. One loop, and the loops nested in
it, compile at most 256 copies of a body.

### `vars()`, `__dict__` and `dir()`

`vars(x)` and `x.__dict__` are supported where they are consumed at once: printed (`print()`,
`str()`, `repr()`, f-strings), iterated (`for k, v in vars(x).items()`, `.keys()`,
`.values()`), formatted (`"%(name)s" % vars(x)` and `"...".format_map(vars(x))` of a constant
format) or copied (`dict(vars(x))`, `vars(x).copy()`). Its keys are the attributes the object
holds in CPython's order: the order its `__init__` (a dataclass's: its fields) first assigns
them, with a field `__init__` may leave unassigned only where it is set; a class attribute is not
in it. Iteration reads each attribute as its turn comes, as CPython's iterator over the live
`__dict__` does: where the body assigns a field that was unassigned as the loop began, the next
step raises `RuntimeError: dictionary changed size during iteration`. Its values (where the loop
binds them, and in a copy) have the join of the fields' types; a loop over the names alone takes
fields of any types. A `__dict__` kept as a value, an order that depends on the run (two
attributes first assigned in one branch, or a field `__init__` may leave unassigned that other
code may assign, which CPython then inserts last, unless it is last anyway), an attribute
`__post_init__` adds, a class with `__slots__` (CPython raises) and a class attribute that the
program may also assign through an object are rejected. `hasattr(x, "__dict__")` and `"__weakref__"` are false for a class whose
names `__slots__` closes.

`dir(x)` makes a new sorted list of the names CPython lists for the object: its fields and
slots, the methods, properties and class attributes of its class and bases, the attributes
every object has, and those a class body or `@dataclass` adds (`__module__`, `__dict__`,
`__weakref__`, `__firstlineno__`, `__static_attributes__`, `__annotations__` where a class body
annotates a name, `__dataclass_fields__`, a generic class's `__orig_bases__`, `__parameters__`,
`__class_getitem__` and, with PEP 695's syntax, `__type_params__`, ...). A slot is listed whether
or not it is assigned (its descriptor is the class's). It also takes `int`, `float`, `bool`, `str`,
`bytes`, containers and `None`.

### `dataclasses`

`dataclasses.fields(X)` (of a class or an object) is supported as the iterable of a `for` loop or
list comprehension that reads each field's `.name`. `asdict()` and `astuple()` are made for the
class: they copy recursively into nested dataclasses (also of a hierarchy, by the object's
class), lists, dicts and tuples, as CPython's `_asdict_inner` does, and keep `None`, numbers,
strings and `bytes` (immutable: `copy.deepcopy()` returns them themselves);
`asdict()`'s values of different types join in a union, so a dataclass holding a tuple and
another type, or objects and scalars, is rejected. `is_dataclass()` is decided by the static
type. `dict_factory=` and `tuple_factory=` are not supported.

`string.Formatter().format()` of a constant template whose fields read attributes (`"{0.x}"`)
formats as `str.format()` does, which the base `Formatter`'s methods do; a loop over a constant
list of templates unrolls.

### Names only the run time knows

A `str` name computed at run time (read from input, taken from a list) is supported where its
consumer needs no value of the attribute, for objects whose possible classes are known:

- `hasattr(o, name)`: true for the names `dir()` lists, but for a field `__init__` may leave
  unassigned (its flag), a slot no code assigns (false) and a property (its getter runs;
  `AttributeError` means false).
- the text of `getattr(o, name)` and `getattr(o, name, default)` in `print()`, `str()`, `repr()`
  and f-string fields without a format spec: a field's or property's value, a bound method
  (`<bound method C.m of ...>`, with the object's `repr()`), the attributes of the object and its
  type (`__class__`, `__module__`, `__doc__` as CPython 3.13 cleans a docstring, `__dict__`,
  `__firstlineno__`, `__static_attributes__`: the sorted names its functions store as `self.x`,
  method wrappers), the default for a name the object does not have, and CPython's
  `AttributeError` otherwise. The lookup runs where the argument is evaluated, and the text is
  made where `print()` converts it, as CPython does. Dataclasses, generic classes, classes with
  annotated class attributes and builtin values are rejected (their `__annotations__`,
  `__dataclass_fields__`, `__orig_bases__` and methods are not printed).
- `setattr(o, name, value)` on objects whose class closes its names with `__slots__`: a slot
  field stores the value, which must fit every slot field (a run-time check would raise where
  CPython does not), a property calls its setter, a method's or other attribute's name raises
  `AttributeError: 'P' object attribute 'm' is read-only`, `__class__` raises CPython's
  `TypeError`, and a name the class does not have raises `AttributeError: 'P' object has no
  attribute 'z' and no __dict__ for setting new attributes`.

Each name is found by a binary search of the sorted name table in the class's reflection
record, and the site then switches on its index. Any other use of a run-time name (its value
kept or passed on, `setattr()` that may add an attribute, `delattr()`), and
`dataclasses.replace(obj, **changes)` of a `dict[str, T]`, is a compile-time error.

## Exceptions

### Builtin exceptions

`try` supports `except`, `else` and `finally` in CPython's combinations, except
`except*`. Handlers can name a builtin or user exception class, a tuple of classes, or use
a bare `except:`, with or without `as name`.

Handlers follow CPython 3.13's hierarchy: `LookupError` catches `KeyError`, whereas
`Exception` does not catch `SystemExit`. `IOError` is an alias for `OSError`.
Handlers catch runtime failures, explicitly raised exceptions, failures from another
function or module, and failures in callbacks such as a sort comparison.

An exception class is looked up when the handler is reached or before the exception is
constructed. If its class statement has not executed, lookup raises `NameError`.
The `as` binding is cleared on every exit from its handler and can have another type before
or after that handler.

Calling a builtin exception class produces an exception value. Values can be stored,
printed, converted to `str` / `repr`, formatted, raised, compared by identity, and tested
with `isinstance()` or `type(e).__name__`. An annotation such as `Exception` names the
builtin exception value type; it does not accept arbitrary user exception objects.
`BaseException | None` (any exception class with `| None`) is an exception that may be
`None`, which `raise` raises as CPython does (`TypeError` for `None`), and
`type[BaseException]` the class of an exception ([context managers](#context-managers)).

`OSError(errno, strerror[, filename])` selects the subclass associated with the errno.
`UnicodeDecodeError(encoding, object, start, end, reason)` (of a bytes object) and
`UnicodeEncodeError(...)` (of a str, whose characters `start` and `end` count) take CPython's
five arguments and give its message, which names the byte or character at `start` or the range
to `end`. `ImportError`, `AttributeError` and `NameError` accept their supported keyword
arguments. Exception attributes such as `args` are unsupported; `__cause__` is supported.

### Control flow

`finally` runs on normal completion, exceptions, `return`, `break` and `continue`.
A return value is computed before `finally`; a return, break or continue in `finally`
discards the exception in flight.

Bare `raise` re-raises the currently handled exception, with the prior handler restored
when an inner handler exits; `sys.exception()` returns it. `raise ... from ...` evaluates and
validates its cause, which `e.__cause__` reads, but the abbreviated error output does not show
exception chaining. A cause that is not an exception raises `TypeError`.

An exception leaving a file context closes the file. If closing fails, its `OSError`
replaces the exception being handled. A failed Python-module import leaves its imported
names unbound and is retried on a later import; see [module initialization](modules.md).

Actual memory exhaustion, native stack exhaustion and Ctrl-C bypass ordinary handlers and
cleanup. Uncaught exceptions have abbreviated output. These are documented in
[errors and control flow](compatibility.md#errors-and-control-flow).

### User exception classes

A user exception class has one base: a supported builtin exception class or another
exception class in the program. It supports fields, constructors, class-body defaults,
methods, docstrings and custom `__str__` / `__repr__`.

A subclass inherits fields and methods and can override `__init__`, `__str__` and
`__repr__`. String conversion, comparisons and uncaught error output use the object's actual
class: `x == y` of `E`-typed values runs `__eq__` of a subclass that defines it. Where that
method is annotated to take only its subclass (`__eq__(self, other: "F")`), CPython would call
it with an `E`, so the comparison, and `in`, `count()`, `index()`, `==` and sorting of
containers of `E` (or of dataclass or NamedTuple objects with an `E` field), are rejected at
compile time, as for ordinary classes. Printing such a container compiles and works.
`super().__init__`, `super().__str__`, `super().__repr__`, explicit base calls and
`super(E, self)` are supported within the documented restrictions.

Positional constructor arguments are retained for default string and repr output.
`super().__init__(...)` resets them. Without a constructor in the user class or a user
base, positional arguments are forwarded to the builtin base. An `OSError` or `SystemExit`
subclass with its own constructor keeps no builtin args (and `SystemExit` code is `None`)
until `super().__init__` is called.

An `except E as e` binding uses the nearest common user exception base of the handler's
classes, otherwise the builtin exception type. An uncaught user exception prints
`module.E: message` (`E` in the main program) and exits with status 1; a `SystemExit`
subclass exits using its code. Exception values keep identity when raised.

Additional inheritance, constructor and attribute restrictions are in
[exception restrictions](compatibility.md#exceptions-and-exception-classes).

## Syntax errors

Source checks apply to the whole file, including unused templates, imported definitions and
branches dropped at compile time. Pystachy checks tokenization, grammar, name binding and
statement placement, aiming to match CPython's error location and message.

Checks include bracket and indentation limits, unterminated literals, invalid targets,
argument-list errors, invalid `global` / `nonlocal`, misplaced control-flow statements,
late future imports and excessive statically nested blocks. Error selection follows the
parser, tokenizer where reached, symbol table, then compiler checks.

Some messages fall back to `invalid syntax` where CPython is more specific.
Patterns inside `match` statements are not checked, and the supported source syntax has
[additional restrictions](compatibility.md#source-text).
`tools/syntax_sweep.py` compares `pystachy check` with CPython's `compile()`;
`pystachy check` checks parsing and syntax, not whether a program can compile.

