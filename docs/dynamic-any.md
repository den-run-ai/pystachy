# Dynamic `Any` (prototype)

Dynamic `Any` lets an opt-in module store values whose Python type is determined at
runtime. It is experimental: supported values can pass between typed and dynamic
code, but concrete storage still enforces its type and some Python operations remain
unsupported.

Put this comment before any code in each module that needs dynamic `Any`:

```python
# pystachy: dynamic-any
from typing import Any

items: list[Any] = [1, "two", 3.0]
alias: Any = items
alias.append("via alias")
print(items)  # [1, 'two', 3.0, 'via alias']
```

In that module, `typing.Any` selects dynamic storage. Modules without the comment
keep `Any`'s [inference-only meaning](language/typing.md#supported-types). Both use
the ordinary JIT/AOT pipeline: the program is compiled before it runs.
The example's typed and dynamic views share the same list; see the
[container regression](../tests/programs/inference/dynany_containers.py).

| To… | Read |
| --- | --- |
| Decide whether a boundary needs dynamic storage | [Admission and containment](#admission-and-containment) and the [library inventory](dynamic-any-boundaries.md) |
| Choose annotations and container layouts | [Selecting dynamic storage](#selecting-dynamic-storage) |
| Pass values between typed and dynamic code | [The typed/dynamic contract](#the-typeddynamic-contract) |
| Use classes, reducers and runtime argument packs | [Class values and type-keyed registries](#class-values-and-type-keyed-registries) |
| Use operators, methods, iterators and generators | [Operations](#operations) and [Iteration](#iteration) |
| Check compatibility before opting in | [Deviations](#deviations) |
| Understand identity and allocation costs | [Representation](#representation), [Identity scope](#identity-scope) and [Measurements](#measurements) |

## Admission and containment

Keep dynamic `Any` opt-in and stabilize its bounded supported subset. A named
consumer is necessary for additional breadth, but is not sufficient: show why
concrete types, specialization through generics, or a supported closed union
cannot preserve that consumer's existing API. A missing inference, union or
identity capability is compiler work to eliminate, not evidence that the operation
is inherently dynamic. This is a development rule; it does not reject existing
programs or change the meaning of their annotations.

Use concrete storage for scanning, parsing mechanics, numeric processing and
internal state with a known shape. Keep dynamic adapters where a supported API
accepts open payloads, callback results, type-keyed registries or runtime argument
packs. The [boundary inventory](dynamic-any-boundaries.md) separates those
contracts from removable implementation choices and outstanding compiler work.
For example, TOML's namespace flags use typed recursive nodes and integer sets;
its document values can still contain arbitrary supported `parse_float` results.

Before adding or widening a boundary, record its consumer, required operations,
rejected static alternatives and ownership/identity contract. `make check-fast`
fails when a shipped `lib/` or `ports/` opt-in lacks an inventory row. Preserve
mutable aliases, callback timing, laziness, exception order, numeric identity and
the supported ABI. Do not copy containers or introduce earlier rejections to make a
boundary appear static. JSON's recursive `JSONValue` is already a closed typed
alternative when the application needs only its value set; it is not a substitute
for an existing open mutable payload contract.

Containment requires generated-code and consumer evidence. Removing a pragma or
moving a function does not establish a cost reduction: identity tracking follows
imports and may restart with the entire graph tracked. Compare dynamic dispatch,
boxing and identity bookkeeping, compilation, JIT/AOT execution, allocation
requests and retained memory. Check CPython parity, GC stress, ordinary typed
controls and a negative control that restores the old footprint. Preserve the
existing [checked identity fallback](#identity-scope) until a narrower proof covers
the same observable behavior. Promoting-int policy remains independent.

## Promoting integers

Dynamic `Any` can be combined with [promoting ints](python-int.md) in the same module:

```python
# pystachy: dynamic-any
# pystachy: python-int
from typing import Any

value: Any = 9223372036854775807
value += 1
print(value, type(value) is int)  # 9223372036854775808 True
exact: int = value
items: list[int] = [exact]
print(items[0] == value)          # True
```

Wide integers can cross typed/dynamic parameters, returns, globals, closures and fields,
and occupy dynamic lists, tuples and dictionary keys and values. Numeric comparisons and
hashes stay exact, including comparisons with floats. The wide and in-range representations
both report Python type `int`; converting an exact `Any` int with `int()` keeps its object.
The combined opt-in also keeps wide values in typed integer lists, dictionaries and sets.

Integer policy belongs to the module containing an operation. With both comments, arithmetic
on two in-range `Any` ints promotes on overflow. A dynamic-only module can receive and operate
on an already wide int, but arithmetic on two in-range ints there retains checked 64-bit
overflow. Its concrete `int` annotations are also checked 64-bit boundaries. This does not
change the default integer policy or remove the remaining [typed storage limits](python-int.md#64-bit-boundaries)
and [numeric identity gaps](#deviations).

## Selecting dynamic storage

### Annotations and container layouts

In an opt-in module, `Any` selects the internal type `dyn` in parameters, returns,
locals, module variables, fields and container items. Examples include `list[Any]`,
`dict[str, Any]`, `tuple[Any, ...]` and `Callable[[Any], Any]`. `Any | None`,
`Optional[Any]` and any other union containing `Any` collapse to `Any`, which can
already hold `None`. `Annotated[Any, ...]` also selects dynamic storage
(`tests/programs/inference/dynany_annotated.py`).

Concrete annotations and unannotated code retain their static types, layouts and
templates. Boxing happens when a concrete value flows into dynamic storage, or
when numeric copies and global reads need to preserve object identity; see
[Representation](#representation).

| Form | Storage and behavior |
| --- | --- |
| Mixed list or dict display, such as `[1, "two", [3]]` | Uses `Any` items, including nested displays, instead of rejecting the mixed types. |
| List of `Any` values or containers of `Any` | Uses `list[Any]` storage. This includes `list[dict[str, Any]]`. |
| Dict with `Any` values or containers of `Any` | Uses `dict[Any, Any]` storage. Both keys and values are boxed, including in `dict[str, Any]` and `dict[str, list[Any]]` (#777). |
| Container of tuples, such as `list[tuple[str, Any]]`, or typed items, such as `dict[str, int]` | Retains its typed layout. |
| Unannotated container first holding `None`, such as `ws = [None]` followed by `ws[0] = {...}` | Retains its inferred typed layout; use an explicit dynamic annotation when it will hold `Any` values. |

A container with dynamic storage is the same object through typed and `Any` views,
so both views observe each other's mutations. Its items and keys are dynamic in
typed code too: a key from `dict[str, Any]` is checked and unboxed when a `str` is
required, and another runtime type raises `TypeError`. `list()` and `sorted()` can
unbox items into a fresh typed result; for example, `return list(d)` can satisfy a
`-> list[str]` return annotation.

Regression coverage: `tests/programs/inference/dynany_layout.py` and
`tests/programs/inference/dynany_layout_forms.py`.

### JSON values

In an opt-in module, `json.loads()` decodes into dynamic containers and
`json.dumps()` encodes `Any` values (#779). A decoded document retains the same
objects as it passes between typed functions and dynamic code. The decoder
promotes integer tokens beyond 64 bits without a caller `python-int` pragma; the
decimal digit limit and fixed-width scanner indices still apply. See the
[JSON prototype](json.md#in-modules-that-opt-in-to-dynamic-any).

Without `sort_keys`, the encoder observes a `default()` callback's changes to later
values and deletion of later keys. Structural changes can differ from CPython's
live dict-table traversal: the encoder retains queued keys in their old order and
appends newly observed keys. A deleted and reinserted key can keep its old output
position; clearing and repopulating a dict can emit replacement entries that
CPython skips (`tests/deviations/dynany_json_reinsert.py`).

### When inferred storage widens to `Any`

An unannotated variable can start with a concrete value and later receive `Any`.
Where the compiler can revise its storage safely, it uses `Any` from the first
store and recompiles the affected function. Other variables keep their inferred
types (`tests/programs/inference/dynany_widen.py`).

| Storage | Widening rule |
| --- | --- |
| Locals and unannotated parameters | A later dynamic store widens the binding. For example, `total = 0; total += x` widens `total` when `x` is `Any`, while a separate `count += 1` stays an `int`. |
| Inferred return type | Returns of an `int` and an `Any` value give `Any`. |
| Fields | A class method's visible assignment of `Any` determines the field's dynamic type before readers compile. Recognized sources include declared parameters, fields and returns, dynamic container items, and arithmetic on them. |
| Module variables | Module-code assignments can widen them when the source is visibly dynamic: a known `Any` variable, loop item, container item, arithmetic, dynamic attribute or method result, or a call declared to return `Any`. |
| Locals first assigned `None` | A later `Any` store widens them even if that store never executes (`tests/programs/inference/dynany_none_first.py`). |

Storage keeps its first type once another compiled user depends on it. This
includes closure cells, generator-frame locals, annotated variables and fields,
fields assigned `Any` only outside their class's methods, and types revealed only
during compilation. An incompatible dynamic store then raises `TypeError`. A
recursive or interdependent function whose return type has already been used by
another compiling function retains its compile-time rejection.

Typed storage represents `None` with a null pointer; dynamic storage uses a
`None` box. If the compiler cannot widen a `None`-first binding before its first
store, it rejects the program and suggests an annotation:

| Storage that will later receive `Any` | Declare it from the start |
| --- | --- |
| Closure or generator local | `last: Any = None` |
| Module variable later assigned by a function | `g: Any = None` |
| Field later assigned outside its class's methods | `self.v: Any = None` |
| List or dict initially holding `None` items | `xs: list[Any] = [None] * n` or `d: dict[str, Any] = {...}` |

These rejections are covered by `tests/errors/inference/dynany_none_*.py`.

### Annotation forms that still request inference

Some uses of `Any` cannot represent a dynamic value and retain their inference
meaning, even in an opt-in module:

| Annotation | Reason |
| --- | --- |
| `Callable[..., Any]` | No concrete `Callable` parameter types are supplied. |
| User class type argument, such as `Box[Any]` | The constructor call determines the class-template specialization. |
| `*args: Any` and `**kwargs: Any` on `__init__` | The class remains a template. |
| `__exit__` parameters | `with` supplies an exception class and exception, which cannot yet be boxed. |
| Bare `Any` return on `__iter__` or a generator | Retains concrete iterator or yield-channel inference. |

Coverage: `dynany_inferred_annotations.py`, `dynany_exit.py`,
`dynany_init_varargs.py` and `dynany_iter_any.py` in `tests/programs/inference/`.

Empty nested displays and calls to `list()`, `dict()` or `set()` keep the usual
contextual inference. An untyped empty item, as in `([], 3)`, takes its type from
preceding items. A nested display whose own items provide a type participates in
the normal common-type decision: examples include `({"a": [1], "b": []}, 1)` and
`[list([1]), []]`. Functions following a `Callable` item use that item's callable
type. These cases are covered by `dynany_display_empty.py`,
`dynany_display_empty_nested.py` and `dynany_callables.py`.

[Inferred unions](language/typing.md#inferred-unions) remain distinct from dynamic
displays. A variable or result receiving an `int` and a `float` is `int | float`;
an additional `Any` value widens it to `Any`. Boxing a union selects the member
named by its tag (`dynany_unions.py`). A mixed display such as `[1, 2.5]` still uses
`Any` items, which permit later stores of other types.

Opting in can reject programs that compile with inference-only `Any`, including
concrete-container return contexts and nested iterator/generator item types. The
[corpus sweep](testing.md#continuous-integration) tests every differential program
in JIT and AOT; its [exact exception list](../tools/dynany_optin_exceptions.json)
records current failures and their owning issues. These remain compatibility gaps.

## The typed/dynamic contract

### Values that can cross

| Into `Any` | Boundary behavior |
| --- | --- |
| Scalars, `None` and `str` | Box the value; numeric identity follows [Representation](#representation). |
| Objects of the program's classes | Retain the object and its concrete class's DynType, selected by the class tag in a hierarchy. |
| Containers with `Any` storage | Retain the same object and layout. |
| Native `list[int]` | Retain the same list, backing storage and item identities, with the checked-store rules below. |
| Tuples | Convert to a tuple of boxes; tuple identity can differ. |
| Functions, bound methods, closures and `Callable` objects | Retain their function, receiver or environment. |
| Unions of supported values | Box the member selected by the union's tag. |

A concrete annotation receiving `Any` checks the box's runtime type before
unboxing it; a union annotation accepts one of its members. A mismatch raises an
error such as `TypeError: expected int, got str`. This differs intentionally from
CPython, which does not enforce annotations; see [Deviations](#deviations).

### Native integer lists preserve aliases and check stores

Native `list[int]` can cross through parameters, returns and fields without
changing its layout. Typed aliases immediately see successful dynamic mutations.
The same `ListLayout` contract selects descriptors for boxing, unboxing and native
IR writes.

| Operation through `Any` | Result or failure contract |
| --- | --- |
| Store an item | Accepts exact ints. Bools and other incompatible types raise `TypeError` before that item is stored. Checked storage rejects wide ints with `OverflowError`; promoting storage retains them. |
| `extend` or `+=` | Keeps any compatible prefix already appended before an error. |
| Slice assignment | Validates the collected replacement before changing target slots. Callback effects already performed remain. |
| Shallow copy, slice, `list()`, concatenation or repetition | Produces a fresh unrestricted boxed list while preserving item identities. |
| `copy.deepcopy()` | Preserves native storage and its store policy. Typed and dynamic traversal of the same list share one memo entry and one copied list, in either traversal order. Boxed-list cycles and aliases remain shared too. |

`isinstance(value, list)` proves the Python type; subsequent operations still use
the actual layout. An explicit `list[int]` receiver requires the native descriptor
for the program's checked or promoting policy. A native list cannot become an
aliased `list[Any]`, and an existing boxed list cannot acquire a native constraint
because its current items happen to be ints. Those annotation crossings raise
`TypeError`. Converting `Any` to other concrete list types, such as `list[float]`,
remains a compile-time rejection.

Coverage: `dynany_native_int_list.py`, `dynany_native_int_list_callbacks.py`,
`dynany_native_int_list_promote.py`, `lib_copy_native_any.py` and
`lib_copy_native_any_promote.py`.

### Other containers and fresh results

Other mutable containers of typed items cannot become `Any` values. Reinterpreting
their slots could corrupt values or GC roots, while copying would break aliases.
Choose dynamic storage from allocation; the [layout rules](#selecting-dynamic-storage)
also cover containers whose items are themselves dynamic containers.

A display flowing into `Any` storage automatically gets dynamic items, including
an empty display and displays stored through a dynamic item or attribute:
`cont[k] = {}`, `o.kids = [1, 2]`, or `f()[k] = {}` when `f` is declared `-> Any`.
A concrete field or `__setitem__` parameter can still reject that dynamic layout
at compile time. Fresh builtin-method results, such as `str.split()` and an
`Any` dict's `items()`, can be converted because no existing alias refers to them.
See `tests/programs/inference/dynany_store_display.py` and
`tests/errors/inference/dynany_store_display_typed.py`.

Tuples convert item by item into a new tuple when typed and dynamic item layouts
differ. For example, returning `tuple[int, str]` as `tuple[int, Any]` boxes its
second item. Conversion in the other direction checks and unboxes dynamic items
(`tests/programs/inference/dynany_tuple_items.py`).

### Generator channels

`yield from` boxes compatible typed yields into an `Any` yield channel, and checks
and unboxes dynamic yields into a compatible concrete channel. Object and dynamic
container references keep their identity. Incompatible native mutable layouts
remain rejected; the wrong runtime type raises the same annotation `TypeError`
as another boundary (`tests/deviations/dynany_generator_channel_check.py`).

A direct call to a generator declared to yield `list[Any]` can instead allocate
`list[T]` yields when every yield is a fresh list display or a direct `yield from`
call meeting the same rule. The caller's generator annotation or an enclosing
`yield from` supplies the concrete context. Each list is allocated in the requested
layout from the start. Ordinary calls still yield `list[Any]`; send and return
channels keep their independent declarations. Existing generators and stored lists
cannot cross layouts this way.

For an `Any` return channel, a bare return or falling off the generator supplies
boxed `None`, even if return inference happens after an earlier bare return. An
`Any` send channel receives boxed `None` from `next()` and loops; explicit `send()`
values retain their boxes.

Coverage in `tests/programs/inference/`: `dynany_generator_context.py`,
`dynany_generator_context_protocol.py`, `dynany_generator_return_none.py`,
`dynany_generator_send_none.py` and `dynany_generator_send_protocol.py`.

### Narrowing dynamic values

`isinstance()` narrows an `Any` local or parameter to a builtin type or program
class. A list test keeps the layout-aware dynamic reference described above.
`isinstance(x, int)` retains the box because a bool also passes that test, but
proves an int or bool payload for arithmetic and comparisons. Bool `&`, `|` and
`^` with another bool, and `**`, stay dynamic because their result rules differ
(`tests/programs/inference/dynany_proven_int.py`).

## Class values and type-keyed registries

In an opted-in module, ordinary user classes and builtin classes can be stored in
`Any`, passed to functions, and used as dictionary keys. `type(value)` returns a
canonical class value; `value.__class__` does likewise unless an explicit
attribute overrides it. For example:

```python
# pystachy: dynamic-any
from typing import Any

reducers: dict[Any, Any] = {}

def register(cls: Any, reducer: Any) -> None:
    reducers[cls] = reducer

def encode_int(value: int) -> str:
    return str(value)

register(int, encode_int)
value: Any = 42
print(reducers[type(value)](value))
```

Lookup uses exact Python type: `bool` and `int` have different keys, as do a base
class and a subclass. Checked and promoting integers share the `int` key;
native `list[int]` and `list[Any]` share the `list` key without changing their
storage. Class objects retain identity and identity hashing, report metatype
`type`, and expose `__name__`, `__qualname__` and `__module__`. An instance's
`__eq__` or `__hash__` does not become the class object's operation; reflected
instance equality still runs when a class is compared with an instance.

A stored ordinary class also gives what its class body binds. A class attribute
reads as `C.name` does, and a static or class method is called as `C.name(...)`
is, with `cls` bound to the stored class; a class deriving from another gives its
own override. The lookup comes before the arguments, as in CPython, and a name
the class lacks raises `AttributeError: type object 'C' has no attribute 'name'`,
which `getattr()`'s default form takes
(`tests/programs/inference/dynany_class_members.py`). Classes of modules that do
not opt in work too: a method that no typed call compiles is compiled on demand
(`tests/programs/inference/dynany_class_members_imported.py`). A static or class
method called on an `Any` value's object likewise runs the method of the
object's own class
(`tests/programs/inference/dynany_class_members_objects.py`).

Each such case is optional. If a use cannot be compiled (a parameter or result
layout that no `Any` value holds, an object of a class nothing else boxes), the
program still compiles and that use raises `NotImplementedError` when selected.

Stored class values can reconstruct ordinary user classes whose boxed instance
adapters and matching initializers have already been compiled by the program:

```python
class Record:
    def __init__(self, value: int):
        self.value = value

original: Any = Record(7)
factory = type(original)
restored = factory(value=original.value)
print(type(restored) is Record, restored is original)  # True False
```

Boxing the original instance establishes its native adapter during compilation.
The constructor reuses its compiled initializer, including an existing
class-specific specialization for inherited `__init__`. Explicit positional and
keyword arguments and supported static unpacking use the ordinary binder.
Runtime-sized `factory(*args, **kwargs)` uses the binding contract below.
For supplied arguments, parameter layouts containing user classes require
existing boxed adapters for those classes, including optional, union and tuple
members. Omitted defaults reuse an already prepared value or a compatible
`None`, boolean, integer, float or string literal; this path does not compile
additional default expressions. Arguments run once, after capturing the class
and before binding errors; initializer exceptions and non-`None` returns retain
their ordinary behavior. Mutable arguments retain their aliases. Typed-tuple
numeric items retain the existing [identity limitation](#deviations).

An isolated ordinary class can also be used only as a factory, without a prior
instance:

```python
class Record:
    def __init__(self, value: int) -> None:
        self.value = value

factory: Any = Record
restored = factory(7)
print(type(restored) is Record, restored.value)  # True 7
```

This preparation path accepts classes outside inheritance hierarchies with no
methods other than a fixed, concretely annotated `__init__`, or the default empty
initializer. The initializer must return `None`. Other special class attributes
are excluded except for `__slots__` given as a string or tuple of strings.
Parameters and fields must use supported dynamic layouts; nominal members need
an existing boxed adapter. Positional-only and keyword-only parameters keep the
ordinary binding rules. Imported initializers and their ordinary scalar helper
functions can compile on demand. Defaults retain their definition-time evaluation
and original identity. Every optional initializer default must bind to its
parameter type, even if the call supplies that argument: an existing dynamic
lookup can also expose the new object's bound `__init__`.

Initializer preparation does not widen inferred storage or introduce new dynamic
protocol dispatchers, callable adapters or unrelated object helpers. A declined
initializer or helper discards the entire attempted compilation before the
compiler retries; an unused unsupported factory therefore does not make another
accepted path fail. Capturing a class as a value alone does not prepare its
initializer. Classes with additional methods or inheritance still use the
existing-adapter path above.

Outside these paths, an uncompiled initializer, a new nominal argument layout,
or a default that cannot bind raises `NotImplementedError` if selected. Builtin
classes, class templates, dataclasses, NamedTuples, decorated or variadic
initializers, `__init__` stored as class data, and custom `__new__` remain outside
this construction path. Runtime class creation, metaclasses, writable class
dictionaries and classes held as the second argument of `isinstance` also remain
unsupported. Overrides of `__module__` and `__qualname__` must be fixed literal
strings. Computed overrides or later writes to `__name__`, `__qualname__` or
`__module__` are rejected for a stored class value, or raise `NotImplementedError`
when reached through a dynamic type query.

Exception class values keep their existing typed representation and cannot cross
into `Any`. Fixed-signature `Callable` adapters erase whether their source was a
function, bound method or builtin class; new stored-type queries reject that
representation or raise `NotImplementedError` when it is held in `Any`. Keep
registry class values in `Any` directly. The `copyreg` tests use two unchanged
upstream registration functions and bounded reconstruction steps; they do not
establish full `copyreg` or `pickle` support.

### Runtime argument unpacking

A callable held in `Any` can receive `factory(*args, **kwargs)` with runtime-sized
arguments. This supports fixed signatures of functions, closures, ordinary user
methods and callable objects, plus the prepared class constructors above. Reducers
can therefore return `(type(value), args)` without a consumer indexing each argument.

Positional packs accept supported dynamic iterables, including lists, tuples,
ranges and generators. Native lists and homogeneous tuples whose elements can
cross `Any` contribute boxed items to fresh argument storage. Keyword packs accept
dynamic builtin dictionaries, str-keyed native dictionaries and existing fixed
kwargs records. Already boxed elements retain their identity and mutable aliases
in the fresh outer packs. Native storage retains existing typed/`Any` identity
limits; packing a native numeric dictionary does not add scalar identity to reads.

Binding checks positional-only and keyword-only parameters, repeated or unexpected
keywords, missing arguments and excess positional arguments before converting
argument values. Omitted defaults reuse definition-time values, including closure
captures; an explicit `None` remains supplied. The callable is captured first.
Multiple positional groups expand in order; a sole `*args` is expanded after
keyword evaluation. Duplicate keyword merges stop later groups.

Callees declaring variadic `*args` or `**kwargs`, erased `Callable` signatures,
builtin methods with runtime packs, custom mapping protocols and unprepared class
constructors remain explicit `NotImplementedError` boundaries. Native keyword
dictionaries with non-str keys are rejected at compilation to avoid rehashing
user keys during conversion. Existing iterator and typed/`Any` storage limits
still apply. Adapter preparation requires stable inferred layouts and existing
object helpers. An adapter needing broader inference, new object helpers or an
unsupported body raises `NotImplementedError` only when selected; unrelated
stored callbacks remain usable. See the
[boundary cases](../tests/deviations/dyn_star_reducer_boundaries.py) and
[unsupported adapter](../tests/deviations/dyn_star_reducer_unsupported_body.py).
These calls do not establish full `copyreg` or `pickle` support.

## Iteration

### Supported iterators and consumers

An `Any` value can hold a range, builtin iterator, user iterator or generator whose
yielded values are boxable. Boxing a generator retains its coroutine handle without
advancing or copying it. Typed and boxed aliases therefore share advancement,
cleanup and yielded mutable values.

| Operation | Contract |
| --- | --- |
| `iter()` | Preserves an iterator's identity. A custom `__iter__` may return a generator or an iterator without its own `__iter__`. |
| `next()` | Advances the original state; evaluates its default before advancement. |
| `for`, membership fallback, `any()`, `all()` and reductions | Consume items lazily. `__contains__` takes precedence over iteration. |
| `zip()` | Takes one item of each argument in turn, as CPython does: a `__next__` cannot change an item already taken from an earlier argument. Stops at the first exhausted argument without advancing later ones. |
| Builtin iterators | Retain their containers and observe mutations as they advance. They stay exhausted after first exhaustion; user iterators may resume after `StopIteration`. |
| `reversed()` | Supports boxed lists, tuples, dicts, strings and ranges, and objects defining `__reversed__`. |
| Range iteration | Uses constant storage even when the range is too large to materialize. |

`list()` and list extension request the source's available `__len__` after obtaining
its iterator. Sequence-fast consumers, such as `str.join()` and dictionary-pair
conversion, request the returned iterator's hint instead. A `TypeError` declines
a hint after its effects; negative lengths and other exceptions propagate. Inferred
length results are checked before allocation in a separate specialization, leaving
ordinary typed `len()` rules unchanged.

### Unsupported protocols and errors

Legacy iteration through `__getitem__` and the `__len__`/`__getitem__` reverse
fallback remain unsupported, as in typed code. This prototype does not add
`__length_hint__`, generator `send`/`throw`/`close` through `Any`, or generator
`StopIteration.value`.

A generator cannot box an aliased mutable container whose native layout is
unsupported, such as `list[float]` or a typed dict. Choose a boxable yield channel,
such as `list[Any]`, from the start. Native `list[int]` values can cross while
preserving aliases under the [ordinary list crossing rules](#native-integer-lists-preserve-aliases-and-check-stores)
([generator regression](../tests/programs/inference/dynany_generator_channel_typed_list.py)).

`str.join()` and dictionary-pair conversion preserve a user `__iter__`'s `TypeError`
instead of replacing its message as CPython does.

Explicit special-method annotations follow typed declaration rules. If an iteration
or length method cannot compile in the supported subset, calling it through `Any`
raises an explicit unsupported-operation error. Boxing an unrelated instance does
not invoke the body.

Coverage: `dynany_iteration.py`, `dynany_iter_builtins.py`, `dynany_iter_range.py`,
`dynany_iter_errors.py`, `dynany_iter_object.py`, `dynany_iter_sequence_fast.py`,
`dynany_iter_key.py`, `dynany_iter_unused.py`, `dynany_zip_*.py` and
`dynany_generator_*.py` in `tests/programs/inference/`. The
[iteration benchmark](../bench/smoke/README.md) checks laziness and checksums before timing.

## Operations

### Supported operations

The supported builtin operations use CPython's result and error rules within the
boundaries documented below and under [Deviations](#deviations).

| Category | Operations |
| --- | --- |
| Operators | Arithmetic, comparisons, truth, `is`, `in` and augmented assignment |
| Containers | Indexing; str/list/tuple slicing; item assignment and deletion; unpacking; `len()`; `list()`; `dict.update()` |
| Conversion and formatting | `str()`, `repr()`, `int()`, `float()`, `bool()`, `abs()`, `hash()`, `id()`, f-strings and `format()` |
| Reductions and ordering | `sum()`, `sorted()`, `min()` and `max()`, including streamed generators |
| Iteration | `iter()`, `next()` with an optional default, and `reversed()`; see [Iteration](#iteration) |
| Strings | `str.join()` and supported builtin methods |
| Type queries | `type(x).__name__`, `__qualname__`, `__module__`, `type(x) is C` and `type(x) == type(y)` |

For example, `int / int` and `2 ** -1` return floats, `True & False` returns a bool,
and mixed int/float comparisons are exact. Errors retain Python wording, such as
`TypeError: unsupported operand type(s) for +: 'int' and 'str'`,
`TypeError: can only concatenate str (not "int") to str`, and `KeyError: 'k'`.

Type comparisons use the value's exact Python type: bool is distinct from int, and
all functions report `function`. A typed operand is tested by its current value,
so a `list[int] | None` holding `None` reports `NoneType`. Coverage:
`tests/programs/inference/dynany_type_is_value.py` and
`tests/programs/inference/dynany_type_is_function.py`.

### Numeric reductions

`sum()` of dynamic items uses CPython 3.13's compensated float phase, including
cancellation-sensitive inputs, mixed ints/floats and nonfinite values. Lists and
streamed generators share the same reduction rules. A callback receives the
compensated partial result; leaving the float phase resumes ordinary addition.
Integer overflow follows the calling module's existing integer policy.

### Numeric conversions, indexing and absolute value

`int()` and `float()` call a boxed object's `__int__` and `__float__`, respectively,
falling back to `__index__` only when that method is absent. Return values are checked
before use, and exceptions propagate without trying the fallback.

Builtin list, tuple and
str indexing and slice bounds call a boxed index object's `__index__`; list assignment and
deletion do too. Dictionary keys and user-defined `__getitem__` arguments retain the original
object. Slicing accepts dynamic bounds: after evaluating every bound and validating
the receiver, it converts step, start and stop in that order. A dict hashes a slice
key before raising its `KeyError`. Slice conversion preserves these rules
(`tests/programs/inference/dynany_numeric_protocols.py`,
`tests/programs/inference/dynany_index_protocol.py`).

In a module with both opt-ins,
`int()` preserves supported wide integer results, including results from an imported
promoting-int method. In a dynamic-only module, `int()` still returns a checked signed-64-bit
integer. Index consumers and other explicit fixed-width destinations retain their documented
bounds; typed object conversions remain unsupported.
Invalid typed-container or `None` members of a union result raise only when returned
(`dynany_numeric_union_protocol.py`, `dynany_numeric_promoted_protocol.py`).

`abs()` calls a boxed object's `__abs__` method, including inherited methods. Builtin bools
give ints, nonnegative ints keep their identity, and floats give new float objects with a
nonnegative sign. For an in-range dynamic integer, the calling module's policy applies:
`abs(-9223372036854775808)` raises `OverflowError` in a dynamic-only module and promotes
with both opt-ins. Already-wide dynamic integers retain arbitrary-precision arithmetic;
explicit [fixed-width destinations](python-int.md#64-bit-boundaries) can still narrow.

### Dictionary union and updates

`dict.update()` accepts a dict or pairs, where each pair is an iterable of two
items. Dict union `d | e` makes a new dict, with the right dict's values taking precedence. `d |= e`
updates the existing dict through `dict.update()`, accepting a dict or builtin iterable of
pairs and preserving aliases. Its key comparisons may run user code. A dict's `|=` updates or
raises before considering a right operand's reflected operator, as CPython does (#810).

### Runtime dispatch

`runtime.c`'s generic helpers implement the builtin types' operations. The program's classes
take part through **dispatchers**: functions the compiler writes once every class whose objects
are boxed is known, recompiling them while compiling them boxes more classes. Each tests the
box's DynType against each boxed class that supports the operation, calls that class's own code
(its dunder, field, property or method), and otherwise falls back to the builtin types' helper
or CPython's `AttributeError`/`TypeError`:

| Dispatcher | Operation |
| --- | --- |
| `op<k>`, `iop<k>`, `un<k>` | Binary, in-place and unary arithmetic, with Python's reflected-method order |
| `truth`, `str`, `len` | `__bool__`/`__len__`, `__str__`/`__repr__`, and `__len__` |
| `format` | `__format__`, including an empty spec; otherwise `str()` for an empty spec or a class-naming `TypeError` |
| `slice`, `module` | Slice operations with dynamic bounds and step; `type(x).__module__` |
| `getitem`, `setitem`, `delitem`, `contains` | Container protocols |
| `get.<a>`, `set.<a>` | Named fields, properties and methods; an instance method reads as a bound method |
| `has.<m>.<n>`, `call.<m>.<shape>` | Method lookup followed by argument binding and a call |
| `callv.<shape>` | Calls of boxed functions, bound methods or objects with `__call__` |

Arithmetic first tries an in-place dunder when applicable. Otherwise, a strict
right-hand subclass's own reflected method has priority over the left operand's
method; if that does not supply the operation, the reflected method of another
right-hand type is considered, then builtin helpers. `str % x` uses formatting
instead of that reflected path. An object's dynamic slice still raises `TypeError`
because its `__getitem__` would need a slice object, which Pystachy does not have.

A call shape records the positional count and keyword names: `2-sep-end` means two
positional arguments followed by `sep=` and `end=`. Method and callable-field
lookup happens before argument evaluation, as CPython's `LOAD_ATTR` does. Each
class's case binds arguments to its own parameters as a typed call would; a
callable field is read first and passed to `callv.<shape>`.

Dispatch also covers supported methods of list, dict, str, tuple, int, bool and
float. Their positional arity errors happen after argument evaluation. Keywords
are accepted where typed code accepts them, including `list.sort()` and
`dict.update()`. Calls through `callv.<shape>` retain defaults, closure environments
and keywords; argument errors use the function's qualified name.

### Object comparisons

Each case calls the class's operation with `Any` arguments: a method whose parameters are
unannotated or `Any` takes them as they are (a template is instantiated for `Any` once), and
one annotated with a concrete type unboxes them as above.

`==` and ordering between objects of
one class (or of a class and its subclass) run the class's `__eq__`, `__lt__` and so on through
the existing `pys_obj_eq`/`pys_obj_cmp`, as typed code compares them: a subclass's `__eq__`
or reflected ordering method first, also where the base class has none, and `x == x` runs
`__eq__` too, while a container's search and a dict's lookup find an object as itself first.
`!=` runs `__ne__` the same way where the class or a subclass defines it (`pys_dyn_ne`), and
otherwise inverts `==` (`tests/programs/inference/dynany_subclass_eq.py`, `tests/programs/inference/dynany_subclass_cmp.py`,
`tests/programs/inference/dynany_ne.py`).

An object and a value of another type, an object of an
unrelated class among them, compare as CPython's rich comparison runs them: the left operand's
method, else the right operand's reflected one (a builtin type's own method declines an object),
else identity for `==` and `!=` and `TypeError` for an ordering; `!=` without `__ne__` is not
`__eq__`. The program's `@o.x.<class>` helper runs the class's method with the other value as an
`Any` argument (`tests/programs/inference/dynany_eq_other.py`). A comparison method whose parameter is
`Any` takes any operand, also between typed objects of its class
(`tests/programs/inference/dynany_eq_any_param.py`).

One whose parameter has no annotation, or
`object`, is compiled for an `Any` operand there; where its body does not compile for one (a typed
list compared with an `Any` value's field), the compiler also tries the body against the
concrete classes of boxed operands, behind exact `DynType` guards.

The adapter proves
field uses and known helper/alias flows before specializing: the receiver and operand retain
their actual layouts, including captured references and supported rebinding. The proof does
not replace the emitted helper calls or getter bodies, so their effects and exceptions keep
their execution order. A canonical body is checked once; unsupported
shapes are filtered before trying each boxed class. Failed concrete attempts have separate
retry keys and cannot remove a working typed call.

### Supported comparison bodies

When an unannotated or `object` comparison parameter cannot compile dynamically,
the guarded adapter supports the following proven cases. This is narrower than
arbitrary Python method bodies:

| Comparison-body operation | Supported boundary and regression |
| --- | --- |
| Closed builtin field equality | Numbers, strings, `None`, lists/dicts, unions and fixed/variadic tuples use separate descriptors; no source storage conversion (`dynany_cmp_builtin_fields.py`, `dynany_cmp_union_fields.py`). |
| Set equality | Matching element layouts or provably disjoint builtin key trees, including tuple keys; set/frozenset pairs (`dynany_cmp_scalar_sets.py`, `dynany_cmp_tuple_sets.py`). |
| Arithmetic and indexed comparisons | Numeric expressions, list repetition, fixed-tuple concatenation and fresh mixed-list concatenation, including `len` and indexing of the result (`dynany_cmp_mixed_list_arithmetic.py`). |
| Definitely invalid builtin operations | Exact builtin operand pairs evaluate normally, then raise CPython's `TypeError` at the invalid arithmetic, unary, ordering or indexing operation; catches, cleanup and earlier errors retain their order (`dynany_cmp_invalid_operations.py`, `dynany_cmp_invalid_cleanup.py`). User protocols and unsupported valid operations are not reclassified. |
| Mixed-list element equality | Scalar, boxed or native class elements retain identity-first comparison and reload lengths after callbacks; nullable class elements and reflected methods are respected (`dynany_cmp_mixed_list_items.py`). Guarded adapters require compatible declared leaf methods, not arbitrary generic leaf bodies or unsupported subclass layouts. |
| Nested container equality | List, tuple and dict trees recursively compare their existing native values, including class callbacks and mixed native/boxed leaves (`dynany_cmp_nested_lists.py`, `dynany_cmp_nested_tuples.py`, `dynany_cmp_nested_dicts.py`, `dynany_cmp_nested_dispatch.py`). Dict key lookup retains stored hashes, identity-first matching and callback order, and checks mutations before reusing entries (`dynany_cmp_nested_object_keys.py`, `dynany_cmp_nested_key_mutation.py`). |
| Nested object fields | List/dict/tuple indexing and nested field/property reads lead to supported scalar or builtin-container comparisons without changing object layouts (`dynany_cmp_nested_fields.py`). |
| Properties | Annotated getters and opt-in getters using ordinary native return inference, including local aliases, helper calls, branches, arithmetic and `try`/`finally`; actual calls retain effects, exceptions and aliases (`dynany_cmp_getter_bodies.py`, `dynany_cmp_getter_arithmetic.py`). The getter body must compile for its concrete receiver. |
| Helpers and escapes | Known module/local helpers and captured operands retain their concrete origins; recursive and mutually recursive calls are supported when their finite origin mapping can be proved. Saving the object to an `Any` global or appending to a global `list[Any]` retains identity (`dynany_cmp_local_helpers.py`, `dynany_cmp_recursive_helpers.py`, `dynany_cmp_global_escape.py`, `dynany_cmp_helper_escapes.py`). |
| Helper results | A proven helper's unique final return can supply an operand or its field/container/property value for a later comparison or mutation. Local aliases and supported `try`/`finally` regions retain the original calls, first exceptions and cleanup (`dynany_cmp_helper_results.py`, `dynany_cmp_helper_result_cleanup.py`). |
| Missing reads | Raise `AttributeError` at the executed read, including stable aliases and captured operands; earlier effects, first exceptions, cleanup and untaken branches are preserved (`dynany_cmp_missing_captures.py`). |
| Missing writes | Literal fields used by proven comparisons reserve native storage only on boxed candidate classes; assignment flags preserve absence until the first store. Aliases, inheritance and compatible closed-union storage retain original object identity; slots/frozen objects raise at the store after the RHS runs (`dynany_cmp_missing_write*.py`). |
| Operand rebinding | Sequential rebinding can preserve observed aliases and escapes. Supported branches and loops select native reference-union members without changing either object's layout; field/property reads, assignments and augmented setters run on the selected object (`dynany_cmp_observed_rebinding.py`, `dynany_cmp_control_rebinding.py`, `dynany_cmp_rebinding_getters.py`, `dynany_cmp_rebinding_stores.py`). Existing native fields retain their store contract. |
| Control flow and mutation | Existing loops, assertions, context managers and cleanup remain supported; differing list/dict/set fields may call `clear()` before a supported comparison. |

Fixture names in the table are under `tests/programs/inference/`. Eligibility proves the
comparison consumer as well as each input, following known helper results and native getter
return inference. Unknown call targets and arbitrary stores into annotated locals are not
inferred by this proof. New helper-result aliases within a protected `try` body are supported
when handlers, cleanup and following statements do not read those aliases, and the protected
body does not rebind an existing alias, receiver or operand. More general branch/exception
alias merges remain outside this proof. Source containers retain storage and aliases.
Mixed-list `+` in an opt-in module allocates a fresh `list[Any]` only when the two layouts
cannot use the existing native concatenation path and every item can be boxed safely.
Numeric item identity and mutable item aliases survive; typed nested containers and typed
variable-length tuples are not copied into boxes.

### Adapter limits

Still outside this proof: arbitrary runtime-name field creation, helper or alias flows whose
operand origins cannot be resolved, and native bodies or layout pairs without a supported
operation. The proof also has a size bound. It projects a helper's body once per binding state
and shares that body between calls in the same state, but still counts it at every call. More
than 4,096 bodies, or helpers nested more than 16 calls deep, exceed the bound. Differing
unsupported `NamedTuple` element layouts and equality between
`list[bytes]` and `list[Any]` retain their explicit rejections
(`tests/errors/inference/dynany_cmp_mixed_namedtuple_lists*.py`,
`tests/errors/inference/dynany_list_bytes_boxed_eq.py`,
`tests/errors/inference/dynany_list_boxed_bytes_eq.py`).

### Fields created by proven comparisons

Reserved fields use
shared compilation retries across discovered candidates; they do not change an
existing field's type or reinterpret source containers. Multiple compatible stored layouts
use a closed union, not a widened container. Immutable objects retain assignment-time
errors.

Descendants that already declare a same-named field/property retain their native
layout; hidden base storage preserves the inherited physical prefix. Direct base-typed access
to a newly created field raises explicit `TypeError` when the concrete subclass shadows it;
narrow to that concrete class before the access
(`tests/deviations/dynany_cmp_field_shadow.py`). Unknown field types remain outside this proof.

Statically named writes can introduce fields absent even from the comparison's own class;
the compiler records the actual RHS type, including computed results and successive values
of different native layouts (`dynany_cmp_missing_write_computed.py`). Specialized generic
peer classes reserve the same fields before their layouts are fixed, and constructor calls
sharing one original layout share their reservation hints (`dynany_cmp_missing_write_template.py`).

An outside typed read of a wholly undeclared computed field can still be rejected before
the comparison body discovers it; declare the field for typed consumers, or read a boxable
value through `Any`. This is an explicit rejection, not a comparison fallback.

`vars()` and `__dict__` keep their original order and value types while all reserved
fields are unassigned. Peer classes imported from ordinary typed modules are eligible
when a dynamic caller boxes them; their existing fields and methods keep their types
(`dynany_cmp_missing_write_import.py`). After one of these fields is created, these dictionary consumers
raise an explicit `TypeError` until runtime insertion order is supported (#486), including
deferred text conversion; `hasattr` and `dir` use the normal assignment flags. Iteration
already in progress retains its dictionary-size mutation check. This boundary is recorded
in `tests/deviations/dynany_cmp_field_reflection.py`.
Custom `__getattr__`/`__getattribute__` methods remain explicit compile-time rejections,
not new supported lookup paths. This matrix does not establish a complete comparison
contract or implement the broader operation-table design in #803.

### Comparison selection and failures

Adapters are emitted only when the generic
dynamic body failed, and follow classes discovered by later dispatcher generation. Failed
concrete attempts have separate `Gen.xnot` keys, so they do not suppress a working adapter or
typed call (`tests/programs/inference/dynany_eq_template.py`).

A normal instance comparison method with
one concretely annotated operand retains its typed call where that operand fits the annotation.
For a value of another type, its cross-type helper specializes the same body with an `Any`
operand, preserving method calls, side effects and exceptions instead of treating the annotation
as a reason to decline (`tests/programs/inference/dynany_eq_annotated_body.py`,
`tests/programs/inference/dynany_cmp_annotated_effects.py`). This also handles tuple shapes and
typed-container annotations when the body can operate on dynamic values. If the dynamic body
cannot compile, the original typed call remains available to matching values
(`tests/programs/inference/dynany_cmp_typed_fallback.py`).

If neither its dynamic body nor a
guarded concrete-class body compiles, executing that cross-type call raises an explicit
unsupported-comparison `TypeError`. It does not return an identity result or try a reflected
method after skipping the selected body. An absent method still permits normal reflection
and identity fallback.

Imported methods whose declarations are unsupported also report an
explicit error when selected. Same-hierarchy dynamic comparisons retain their typed helpers;
when the selected method cannot accept that operand type, those helpers raise `TypeError`
rather than substituting identity or running a lower-priority reflected method. Unused
methods, identity-first container matches and supported operand types remain available.

#### Literal-name attribute reads

A literal-name `getattr(value, "field", default)` through `Any` evaluates its default before
lookup and catches only `AttributeError`, including from a property getter. Comparison
bodies using it execute normally; a missing field is not a reason to skip the method
(`tests/programs/inference/dynany_cmp_getattr_default.py`).

A NamedTuple's `!=` is tuple's, also where its class defines `__eq__`. Arithmetic runs reflected
methods in CPython's order too (`tests/programs/inference/dynany_reflected.py`), which typed code
rejects: no method can return `NotImplemented`, so the first one that runs gives the result.

## Deviations

### Concrete storage and comparison boundaries

- A concrete annotation that receives an `Any` value raises `TypeError` where its type differs
  (CPython does not check annotations). `int` takes no `bool` and `float` no `int` this way,
  so that a typed variable never prints another value than CPython's. So does the storage that
  [keeps its first type](#selecting-dynamic-storage) when an `Any` value reaches it.

- The newly supported native `list[int]`/`Any` boundary checks dynamic writes against
  native storage. CPython accepts a str, float or bool in the annotated list; this
  prototype raises `TypeError`, preserving aliases and the existing storage. `extend`
  and `+=` may already have appended a compatible prefix; rejected slice replacements
  leave target slots unchanged. An annotation cannot reinterpret native slots or constrain
  an existing unrestricted boxed list (`tests/deviations/dynany_native_int_list_store.py`).
  This is the bounded checked-store policy for these newly accepted crossings; other
  concrete mutable layouts remain unsupported.

- A comparison operand rebound across control flow keeps either object's native field
  storage. An executed store of `list[int]` into the original operand's `list[str]`
  field raises the typed-boundary `TypeError` after evaluating its value and target;
  the same check applies to a selected property's typed setter parameter before its
  body runs. CPython instead accepts these values. An untaken incompatible store does not block
  a valid store into the rebound receiver. Existing containers and aliases retain
  their layouts (`tests/deviations/dynany_cmp_rebinding_native_store.py`).

- A cross-type comparison method whose body cannot compile for an `Any` operand and falls
  outside the supported guarded concrete adapter raises an explicit unsupported-comparison
  `TypeError` when selected. CPython runs the method, whose body may give a result or raise another error
  (the comparison acceptance matrix above defines the proven cases). Supported helper calls,
  escapes and returned aliases, native operand rebinding, inferred getters, nested container
  callbacks and finite literal missing-field writes are covered by that matrix. Unknown
  helper/alias origins and unsupported native body or layout pairs still need further work,
  and a proof past its size bound raises in the same way
  (`tests/deviations/dynany_cmp_proof_bound.py`). Concrete operand annotations alone no
  longer suppress normal cross-type instance comparison methods. Unsupported bodies remain
  a compatibility limit tracked by #803; these cross-type calls cannot silently succeed
  (`tests/deviations/dynany_cmp_uncompiled_body.py`).

- Same-hierarchy dynamic comparisons use typed helpers, so an incompatible concrete operand
  annotation raises `TypeError` even where CPython runs that body. Imported comparison
  declarations with unsupported annotations or return types also raise explicitly when
  selected (`tests/deviations/dynany_cmp_declined_annotations.py`,
  `tests/deviations/dynany_cmp_declined_declarations.py`). These methods are present for
  dispatch: their inability to compile never permits a lower-priority method to run instead.

- Searches with an `Any` query in typed numeric lists, int-keyed dictionaries and int sets
  keep the query's Python value. They compare wide ints and equal floats exactly, preserve
  comparison/hash callbacks and observe their mutations. Dictionary/set stores still check
  the declared element type; a query that equals an existing int need not be an int itself.
  Other typed container queries may still unbox the item as the container's item type,
  raising `TypeError` where CPython would answer `False`.

- `dict.keys()`, `values()` and `items()` of an `Any` dict give lists, as the typed ones do.

### Numeric identity gaps

An int or float of typed code that no variable's box slot holds is a new object where
it becomes an `Any` value, where CPython's names, containers and classes hold one
object. This affects numeric items of typed tuples, dicts and sets, including typed
variadic argument tuples; typed lists with optional or union item types
(`list[float | None]`, `list[int | float]`); and typed numeric generator yields
(`Iterator[float]`, for example).

Yielding into dynamic item storage (`Iterator[Any]`) retains the source box. The
typed-tuple case remains in `tests/deviations/dynany_identity_boundary.py`; fresh
displays with dynamic item destinations avoid that typed storage boundary. Typed
numeric lists retain their item objects as described under
[Typed numeric list items](#typed-numeric-list-items).

Numeric optional/scalar-union locals, closure cells, globals, instance fields and
class attributes retain their identity. Module-level and function-local from-import
copies retain the source global's object, including imports in non-opt-in functions.
Constant-folding forms beyond the
[bounded integer arithmetic](#constant-folding-and-comprehensions) remain gaps.

Starred displays capture numeric objects when their dynamic result can be inferred
before evaluation, or an already typed expansion supplies dynamic items. Displays
whose element types depend on earlier first bindings within that same expression
can still need an explicit `list[Any]` destination.

### Calls and builtin methods

- A function value prints as `<function>`; builtin functions and methods (`len`, `"".join`)
  cannot become `Any` values yet.

- Calls of `Any` values and their methods take positional and keyword arguments, and what a
  typed call unpacks (a tuple's items, a dict display with str keys, a function's `**kwargs`).
  [Runtime argument unpacking](#runtime-argument-unpacking) additionally supports fixed
  user callables and prepared constructors; variadic callees and custom mappings remain
  bounded. A builtin type's method takes keyword arguments only where typed code takes them
  (`list.sort()`'s `key` and `reverse`, `dict.update()`'s): another raises the `TypeError` that
  typed code reports at compile time, where CPython binds them (`s.split(sep=",")`). So does a
  call with keyword arguments of a function value whose type is a `Callable`, which has no
  parameter names (`tests/deviations/dynany_builtin_keywords.py`).

- `sorted()`, `list.sort()`, `min()` and `max()` of objects with a `key` that is an `Any` value
  holding `None` call it, and raise `TypeError`, where CPython orders the objects themselves:
  ordering them without a key would compile their class's comparison methods, which the keyed
  call never needs. Typed code rejects a `Callable | None` key over objects at compile time
  (`tests/deviations/dynany_key_none_objects.py`).

- A builtin type's method that typed code does not support either (`int.to_bytes()`,
  `int.as_integer_ratio()`) raises `AttributeError` where it is called through an `Any` value;
  typed code rejects it at compile time. Supported builtin methods evaluate their arguments
  before raising CPython's positional arity `TypeError`, while missing attributes fail before
  argument evaluation (`tests/programs/inference/dynany_builtin_arity.py`). The typed subset
  still lacks three-argument `str.replace()` and one-argument `dict.setdefault()`; those shapes
  raise an explicit unsupported-call `TypeError` after evaluating their arguments. Static
  unpacking uses the direct-call error wording: a bool's unpacked `bit_count()`/`bit_length()`
  arity error names `int` where CPython names `bool`
  (`tests/deviations/dynany_builtin_star_error.py`).

### Formatting, attributes and unsupported values

- Calls through stored classes outside the
  [bounded reconstruction contract](#class-values-and-type-keyed-registries)
  raise `NotImplementedError`, although `callable()` reports true. This includes
  classes with additional methods and no existing boxed adapter, uncompiled
  initializers and `__init__` stored as class data.

- A stored class gives its class attributes, static methods and class methods. A
  method of its objects, a property, a static or class method read without a
  call, and a member whose use cannot be compiled raise `NotImplementedError`,
  where CPython gives a function, a property object or the value; they do not
  raise the `AttributeError` of a missing name. Assigning a class attribute
  through a stored class, enum and NamedTuple classes' members, and the names
  every class object has of `type` (`__doc__`, `__dict__`, `mro`) keep the
  dynamic lookup's `AttributeError`
  (`tests/deviations/dynany_class_member_unsupported.py`).

- Stored `type()` of an erased `Callable` held in `Any` raises
  `NotImplementedError`; its existing supported calls still work. Restoring the
  original callable's identity remains tracked by #858.

- `%` of an `Any` str raises `TypeError`: printf-style formatting is implemented for a str that
  is known as such, which formats `Any` values (`tests/deviations/dynany_str_mod.py`).

- A slice of an object through an `Any` value raises `TypeError`: its `__getitem__` would take a
  slice object, which Pystachy does not have (typed code rejects the slice at compile time).

- A NamedTuple's object compares and hashes as the tuple of its fields through `Any` values
  (`tests/programs/inference/dynany_namedtuple.py`), but it is no sequence there: `len()`, indexing and
  iteration raise `TypeError`, and an object of another NamedTuple class compares with it by
  identity (an ordering raises `TypeError`), where CPython compares their fields.

- A static or class method read through an object held in `Any` without a call raises `AttributeError`
  (typed code rejects a static method as a value at compile time), and so does a call of a
  property's value (`x.p(...)`). A field's value is called as a function value is.

- Outside the proven literal comparison writes, assigning an attribute that the object's
  class does not have raises `AttributeError` (the native layout remains fixed).
  `vars()` and `__dict__` after a comparison-created field raise explicit `TypeError`
  (`tests/deviations/dynany_cmp_field_reflection.py`); general late-field insertion order
  remains unsupported (#486).

- `set`, `bytes` and exception objects cannot become `Any` values yet. Concrete
  mutable-container layouts remain unsupported except for the native `list[int]`
  boundary described in [The typed/dynamic contract](#the-typeddynamic-contract).

- Rejected at compile time where an argument is an `Any` value: `divmod()`, `round()`,
  `chr()`, `ord()`, `bin()`, `hex()`, `oct()`, `dict()`, `tuple()` (`tuple(list(x))` works),
  `hasattr()`, `setattr()` and `del` of an attribute. Literal-name `getattr()` uses
  dynamic attribute lookup, including the default form described under
  [Literal-name attribute reads](#literal-name-attribute-reads); this
  does not establish general runtime-name reflection. The supported forms of
  `iter()`, `next()` and `reversed()` are described in [Iteration](#iteration).

## Representation

This section explains boxing, numeric identity and their allocation costs. The
[typed/dynamic contract](#the-typeddynamic-contract) defines which values can
cross a boundary.

### Box layout and collection

A dynamic value points to an immutable 16-byte box, `{DynType *t, payload}`, in
`runtime.c`.

| Component | Contents |
| --- | --- |
| `DynType` | Python type identity (`kind`), `type(x).__name__` and the payload's physical descriptor (`desc`). Object types also record their `O<id>`, base DynType and method-dispatch flags (`DF_X`). |
| `payload` | Numeric bits for an in-range int, float or bool; the original pointer for a str, list, dict, tuple or object. |
| Wide integer payload | A pointer to immutable `Mpz` digits, with a second integer DynType using descriptor `j` and the same Python kind. |

Builtin DynTypes cover None, bool, int, float, str, list, dict and tuple. The program
adds one per boxed class and function value type. Object helpers `pys_obj_eq`,
`pys_obj_cmp` and `pys_obj_repr` dispatch on `O<id>`; `DF_X` records cross-type
comparison, ordering and hashing through class methods. Integer operations inspect
the physical layout before reading a payload. A wide int still needs only one
16-byte box, scanned to keep its digits alive.

`None` uses the constant `pys_dyn_none_box`, never null. Null denotes an unbound
slot, distinguished by the existing assignment flags. Bools, small ints and
integer literals have constant boxes. A str constant's box points to that
constant, so a literal key in `dict[str, Any]` allocates nothing (#777).

Other in-range numeric boxes use atomic allocations that the collector does not
scan. Reference boxes are scanned and keep their payloads alive; DynTypes remain
outside the heap. Dynamic locals, arguments and closure cells are ordinary scanned
pointer slots. Dynamic globals are registered roots.

Boxing a mutable container retains its original pointer and layout. It never
copies the container or gives an alias a second layout.

### Dynamic containers and functions

| Descriptor | Value |
| --- | --- |
| `A` | A slot holding a box |
| `LA` | `list[Any]` |
| `DAA` | `dict[Any, Any]` |
| `VA` | A tuple of boxes |
| `Z` | A boxed function |
| `Y` | An immutable class reflection record |

Generic repr, equality, ordering, hashing, sorting, searching and `KeyError`
formatting follow descriptor `A` through the box's DynType. Dynamic dict keys use
Python's numeric hash, so `1`, `1.0` and `True` are one key. Fast paths compare
boxed strs by bytes and ints/bools by value; a boxed str hashes in one call (#780).

A boxed function prints as `<function>` and compares equal to the same function
with the same receiver or closure environment. Each evaluation of `o.m` creates
a distinct bound-method box for identity. A def's box is a constant with its
DynType address as payload; a closure retains the environment created by its def.
Different function objects therefore have different IDs.

Class objects use a distinct `DK_TYPE` and descriptor `Y`. Their payload is the
existing immutable reflection record, shared by every representation of the same
Python class. Their outer type is the metatype, never an instance layout. Class
boxes and records reference only static constants; the runtime `DynType` layout is
unchanged.

Coverage: [dynany_fn_identity.py](../tests/programs/inference/dynany_fn_identity.py).

### Native integer list representation

Checked and promoting integer lists have distinct DynTypes. Both report Python
type `list` while retaining their native layout. Dynamic operations dispatch by
that layout and use existing item-identity companions; typed aliases keep their
native access path.

Either view keeps the list and companions alive, including when the `Any` box is
the only remaining owner. First exposure can visit every item and allocate missing
identity boxes. Preserving native backing does not make this boundary allocation-free.

### Identity of boxed values and constants

Two dynamic values satisfy `is` exactly when their `id()` values are equal (#797).
None, bools and references identify their payload objects. Ints, floats and bound
methods identify their boxes.

| Numeric value | Object identity |
| --- | --- |
| Int from -5 through 256 | One cached box per value |
| Integer literal | One box per value in each module, shared by that module's functions |
| Wide integer literal with `python-int` | The module shares its box and immutable digits, including equivalent decimal, hexadecimal, octal and binary spellings |
| Float literal | One box per exact bit pattern in each module, shared by its functions; positive and negative zero remain distinct |
| Runtime arithmetic and conversions | Do not generally reuse literal boxes. Cached small ints and operations that retain their operand's object are exceptions; computed floats, including NaNs, are not interned |

Converting an exact dynamic int with `int()`, applying unary `+`, or taking a
nonnegative integer's `abs()` preserves its object. Separate `int("1000")` calls
produce distinct objects, while separate `int("100")` calls share the cached small
int, as in CPython.

Coverage: [dynany_identity.py](../tests/programs/inference/dynany_identity.py),
[dynany_identity_modules.py](../tests/programs/inference/dynany_identity_modules.py),
[python_int_any_constants.py](../tests/programs/numbers/python_int_any_constants.py),
[dynany_float_identity.py](../tests/programs/inference/dynany_float_identity.py).

### Numeric variables, globals and closure cells

In a module that [tracks identity](#identity-scope), each typed numeric binding has
a companion box slot. This covers locals, parameters, closure and comprehension
variables, and module variables. The slot starts null. Crossing into `Any` reuses
its box if it still represents that binding; otherwise it creates and stores one.

A store inherits the source dynamic box, copied binding's box or literal's constant
box. A read preceding rebinding, as in `x, y = y, x`, retains the old object: its
existing box or a new snapshot box that does not replace the binding's current slot.
Copying a numeric variable materializes a box if necessary, so copies made before
either becomes `Any` still share one object.

Global reads snapshot their boxes before later operands can rebind the global.
Proven single-binding integer constants and their from-import copies initialize
their cached boxes once, so reads only load them. These rules also apply to globals
in imported typed modules that track identity. Other copies and global reads can
allocate even if no later dynamic crossing occurs.

A numeric closure cell shares its box slot with all readers and nonlocal writers,
including closures created before boxing. Reads snapshot before later operands
can rebind the cell; the box survives the creating function's return. Cells use
the existing scanned 16-byte allocation, with the second word holding the box.
Copies into or out of a cell can allocate even in a factory returning a closure
with only scalar uses.

A global or cell read needs no box when used only in a proven scalar expression
of concrete numeric names, literals, arithmetic and unshadowed numeric conversions.
User calls, assignment expressions, dynamic operands and unknown syntax retain
snapshots. Stores update identity slots; copies and values kept across calls retain
their objects.

Coverage: [dynany_identity_copy.py](../tests/programs/inference/dynany_identity_copy.py),
[dynany_identity_global_snapshot.py](../tests/programs/inference/dynany_identity_global_snapshot.py),
[dynany_identity_constants.py](../tests/programs/inference/dynany_identity_constants.py),
[dynany_identity_cells.py](../tests/programs/inference/dynany_identity_cells.py),
[dynany_identity_scalar_globals.py](../tests/programs/inference/dynany_identity_scalar_globals.py).

### Expression evaluation and dynamic displays

Local numeric bindings carry stack generation counters. Reads before assignments
in skipped branches retain their original object; equal-valued replacements remain
distinct. A conditional expression between same-typed numeric locals lazily carries
the chosen slot and generation. An assignment expression preserves its target's
provenance. These expression results alone do not force boxing.

A display with known dynamic storage captures numeric binding objects, including
optional numbers, as each item is evaluated. In `[x, x, (x := value)]`, the first two
items retain the old object. Repeated NaN keys or set items likewise stay one entry
when a later item rebinds the name. Later items and hashing keep their evaluation
order. Fresh tuple displays with `Any` item destinations retain optional numeric
identity, including nested displays. With promoting integers enabled, optional
wide integers enter that dynamic tuple storage without narrowing to 64 bits.

Starred list and runtime-length tuple displays also capture numeric items when
their resulting dynamic storage can be determined before evaluation. The lookahead
keeps first-binding assignment expressions valid and preserves inferred types.

Coverage: [dynany_identity_expressions.py](../tests/programs/inference/dynany_identity_expressions.py),
[dynany_identity_display_reads.py](../tests/programs/inference/dynany_identity_display_reads.py),
[dynany_identity_inferred_stars.py](../tests/programs/inference/dynany_identity_inferred_stars.py),
[dynany_identity_optional_tuple.py](../tests/programs/inference/dynany_identity_optional_tuple.py),
[python_int_optional_tuple_identity.py](../tests/programs/numbers/python_int_optional_tuple_identity.py).

### Optional values, unions and class attributes

Optional numeric and scalar-union locals keep lazy identity slots across stores,
narrowing and copies. Closure cells retain and snapshot the same identities after
the outer function returns. Globals do too, including imported typed globals and
from-import copies; their slots are roots, and reads snapshot before callbacks.

Numeric class attributes share a rooted box with their defining class, including
inherited attributes and imported constants. Optional/union payload layouts stay
unchanged; companion boxes follow representation-only conversions, and copies can
materialize them as for concrete locals.

Coverage: [dynany_identity_joined_locals.py](../tests/programs/inference/dynany_identity_joined_locals.py),
[dynany_identity_joined_cells.py](../tests/programs/inference/dynany_identity_joined_cells.py),
[dynany_identity_joined_globals.py](../tests/programs/inference/dynany_identity_joined_globals.py),
[dynany_identity_class_globals.py](../tests/programs/inference/dynany_identity_class_globals.py).

### Instance fields and field copies

Numeric instance fields, including optional and scalar-union fields, have scanned
companion slots. Stores retain the source object; reads snapshot before another
operand can change the field. Instance reads of defaults share the defining
class's box until an instance assignment. Inherited fields keep the same companion
through base-typed aliases. This also covers dataclasses, NamedTuples, exception
classes and class-template specializations.

Raw numeric payloads stay unboxed. A class in an identity-tracking module adds one
pointer per numeric field, including a reservation for an unresolved `None` field,
plus alignment. Reads and copies may allocate boxes. Other classes, and programs
without dynamic `Any`, keep their original layouts.

A plain numeric field read through a local or parameter can omit a snapshot when
it feeds only arithmetic, comparison, indexing or the old value of `o.f op= v`.
The class and its subclasses must have no relevant property, method, `__getattr__`
or `__getattribute__` lookup.

A copy such as `i = self.pos` can lazily share the field's object when `self` is a
parameter the function never rebinds. A runtime flag marks sharing. The first read
outside those scalar operands materializes the box in both slots. Before a
statement can run program code, live sharing locals are materialized and other
sharing ends. A write to the shared field hands the local its old box; writing
`self.pos = i` retains the shared field slot or starts sharing the local's object.

This sharing starts only in the function's own `if` and `while` blocks, excluding
code-running loop tests, `for`, `with`, `try` and generators. It supports one such
local per field name.

Coverage: [dynany_identity_fields.py](../tests/programs/inference/dynany_identity_fields.py),
[dynany_identity_field_defaults.py](../tests/programs/inference/dynany_identity_field_defaults.py),
[dynany_identity_field_kinds.py](../tests/programs/inference/dynany_identity_field_kinds.py),
[dynany_identity_field_locals.py](../tests/programs/inference/dynany_identity_field_locals.py),
[dynany_field_locals.py](../tests/ir/dynany_field_locals.py).

### Calls, defaults and return values

Typed numeric parameters, definition-time defaults and numeric returns preserve
their originating objects across non-opt-in modules, closures, `Callable` values,
virtual methods and dynamic calls. Internal calls in a dynamic program graph pass
numeric argument companions and a numeric-result output slot. Arithmetic still
uses raw numbers. Defaults retain rooted global or closure-environment companions.

Existing return boxes and constants are retained; fresh computed results defer
boxing. A computed argument with no binding, field, item, dynamic or literal
provenance passes a null companion and boxes when first observed. A standalone
assignment of a call result takes its returned object. A local's last read before rebinding can
transfer its object to a copy or argument without boxing, provided no later read
in the statement or live use afterward needs it.

Numeric-only methods can join the proof below when they use their receiver's plain
fields and locals holding its bytes or str fields. Unreturned numeric arguments
then need no companions, and such calls run no other code. Argument snapshots
still precede later argument side effects; returns retain their objects across
`finally` cleanup.

Foreign C and CPython extension entry points retain their native ABI. Graphs
without dynamic `Any` retain ordinary calling conventions. Nontracking code in a
dynamic graph follows its convention but passes null companions and returns none.

Coverage: [dynany_identity_call_moves.py](../tests/programs/inference/dynany_identity_call_moves.py),
[dynany_identity_method_proofs.py](../tests/programs/inference/dynany_identity_method_proofs.py),
[dynany_identity_call_args.py](../tests/programs/inference/dynany_identity_call_args.py),
[dynany_identity_call_defaults.py](../tests/programs/inference/dynany_identity_call_defaults.py),
[dynany_identity_call_returns.py](../tests/programs/inference/dynany_identity_call_returns.py),
[dynany_identity_call_indirect.py](../tests/programs/inference/dynany_identity_call_indirect.py),
[dynany_identity_call_imports.py](../tests/programs/inference/dynany_identity_call_imports.py),
[dynany_identity_call_edges.py](../tests/programs/inference/dynany_identity_call_edges.py).

### Typed numeric list items

Typed `list[int]` and `list[float]` preserve item objects through stores, reads,
iteration, copies, slices, repetition and reordering. Their raw numeric array is
unchanged; a separate scanned companion array holds item boxes. Copies share
boxes, and replacing an item changes only that slot's object.

Search, equality and ordering test identical objects before numeric comparison,
including NaNs. Unpacking and min/max selection retain the chosen object. Sorting
carries companions through key callbacks and exception restoration.

Native numeric list producers establish one object per item before sharing. This
costs one companion pointer per capacity slot and materialized numeric boxes.
Graphs without dynamic `Any` allocate no companion arrays. Nontracking code uses
plain list operations that keep any existing companions consistent.

Proven numeric arithmetic and comparison reads may use raw payloads when the list
receiver is a plain name and its integer index is inert. Assignments, returns,
identity tests, dynamic operands and callbacks retain the item objects.

Foreign C list calls follow the CPython FFI twin's copy-back contract: the list
remains the same object, but every numeric item is replaced after C returns,
including read-only calls and calls through `ffi.at()`.

Coverage: [dynany_identity_list_items.py](../tests/programs/inference/dynany_identity_list_items.py),
[dynany_identity_list_mutations.py](../tests/programs/inference/dynany_identity_list_mutations.py),
[dynany_identity_list_transfers.py](../tests/programs/inference/dynany_identity_list_transfers.py),
[dynany_identity_list_queries.py](../tests/programs/inference/dynany_identity_list_queries.py),
[dynany_identity_list_selectors.py](../tests/programs/inference/dynany_identity_list_selectors.py),
[dynany_identity_list_callbacks.py](../tests/programs/inference/dynany_identity_list_callbacks.py),
[c_list_identity.py](../tests/ffi/c_list_identity.py).

### Constant folding and comprehensions

Integer-literal arithmetic shares the module's constant box when both operands
and result fit int64: `999 + 1` has the same object as the literal `1000`. Covered
operations are `+`, `-`, `*`, `//`, `%`, bit operations, shifts and powers with
counts from 0 through 63, unary signs and inversion. Runtime operands and calls
remain fresh; invalid or overflowing operations keep runtime evaluation and errors.

Float arithmetic, larger shift/power counts and wide integer folding are outside
this identity guarantee (#858). For example, dynamic `2 ** 63` and the literal
`9223372036854775808` compare equal but do not share an object.

Comprehension targets have independent box slots, renewed each iteration and
restored after shadowing an enclosing binding. This also covers empty
comprehensions and short-circuit reductions.

Coverage: [dynany_identity_folded_ints.py](../tests/programs/inference/dynany_identity_folded_ints.py),
[dynany_identity_boundary.py](../tests/deviations/dynany_identity_boundary.py),
[dynany_identity_comprehensions.py](../tests/programs/inference/dynany_identity_comprehensions.py).

### When the compiler can omit identity bookkeeping

A closed function with explicit numeric parameters and return type can omit local
box slots unrelated to return identity when its entire body uses only scalar
arithmetic, comparisons, control flow, `range` and numeric conversions. A backward
alias proof keeps slots and argument boxes for names returned unchanged; arithmetic
breaks that dependency.

A separate numeric-body proof can omit unreturned argument boxes through explicitly
annotated numeric/union locals. Functions proven to return only `None`, including
inferred numeric specializations, can also print numeric values and literal strings
through the unshadowed builtin without keyword or expanded arguments. Identity
tests, dynamic storage, globals, containers, closures and other calls prevent
that proof.

Other fresh numeric results are boxed when first observed by a crossing, copy,
global read or cell read. A float narrowed from `Any` by `isinstance()` retains its
original box when boxed again. Remaining identity gaps are listed under
[Deviations](#deviations).

Coverage: [dynany_identity_scalar_expressions.py](../tests/ir/dynany_identity_scalar_expressions.py),
[dynany_numeric_locals.py](../tests/ir/dynany_numeric_locals.py),
[dynany_identity_typed.py](../tests/programs/inference/dynany_identity_typed.py).

### IR reads and effects

`dyn.type` reads a box's DynType pointer. `dyn.payload` reads the payload with the
type established by frontend narrowing. With `PYSTACHY_IRCHECK=1`, the stock IR
verifier checks both instruction shape and matching tags for every reachable
payload read, against the program's `DynType` constants: an `int` read accepts a
bool's box, whose payload is its int value, and a class read the box of a subclass
or of a class that takes it as its role. Its control-flow proof covers copies, private slots,
branches, simultaneous phis, loops, exception edges, `pys_dyn_isa` tests and
class dispatchers' switches, losing facts on rebinding and refusing to infer facts
for escaping storage. Identity comparisons use `dyn.raw` for opaque bits, which
the verifier permits only in direct integer equality comparisons. See the
[IR contracts](typed-ir.md) for the exact scope and remaining assumptions.

The optional
[Lean checker](../tools/lean_boundary/README.md) checks the guards of payload
reads of every builtin, class, function and generator type, including int/bool
sharing and class inheritance, in normalized functions exported from actual
typed IR; CI requires it to accept every such read of the dynamic-`Any` test
programs. It rejects unsupported forms and does not establish adapter
fidelity, the descriptor table, payload layouts, identity/GC preservation or
LLVM correctness. It is separate from the built-in closed-union proof and does not
justify removing `Any` or identity bookkeeping. These box reads are effect-free because boxes are
immutable. Runtime calls with an `A` descriptor receive every effect, as `O` calls
do: the box may contain an object whose equality, hashing or repr runs program code.

## Identity scope

### Which modules track numeric identity

Only code that can observe a number's identity tracks it (#969). In a program where a module
opts in, that is the code of the modules that opt in, of every module they import, directly
or not, of lib's `range`, `object()` and `iter()` modules where one of those uses them, and the
compiler's shared helpers. The code of every other module compiles as in a program without
dynamic `Any`: its classes keep their layouts, with no companion slots, and its functions keep
no box slots, take no snapshots and allocate no boxes for their calls. Typically such a module
is the main program that does not opt in but imports `tomllib` or the json_repair port.

Values cross from that code into tracking code only where they cannot carry a number's
identity: it may pass strings, bools, `None`, `Any` values (which keep their boxes), and
containers and `Callable` values of these, make `Any` values of these and of numeric
literals, receive these and plain numbers, and read numbers from the variables and objects
of tracking modules.

Any other crossing compiles the program again from the start with every module tracking identity, which
gives the same IR as before this split: one of its numbers or objects made an `Any` value, a
call of a tracking module's function, constructor or method that takes or gives back anything
else, or a store into a tracking module's variable, class attribute or object.

Without an identity-inert hint, a program whose main module opts in, or whose every
module a module that opts in imports, is unaffected; one
that falls back compiles its modules twice, the first time up to the crossing
(`tests/programs/inference/dynany_identity_scope.py`, `dynany_identity_scope_fields.py`,
`dynany_identity_scope_numbers.py`, `tests/ir/dynany_identity_scope.py`,
`tools/test_identity_scope.py`).

### The `identity-inert` hint

A module that opts in to neither dynamic `Any` nor promoting ints may start with `# pystachy: identity-inert` to request checked removal of
numeric identity bookkeeping even when tracking code imports it. This is an optimization hint,
not a change in semantics or a promise the compiler trusts. The compiler keeps tracking the
module's dependencies.

Calls may exchange strings, bytes, bools, `None`, boxed values and
representations that already carry no numeric companion, including recursive `JSONValue`
storage. Numeric scalars, scalar unions and numeric lists do not qualify.

A hinted class may
cross directly as a typed handle; observing its numeric fields, boxing it, mixing tracked and
hinted inheritance, or boxing a function makes the compiler discard the hint. Numeric list
operations inside the module also discard it, because searches and equality can observe a
shared NaN even when nothing numeric crosses a module boundary. Globals, fields and reflection
use the same checked boundaries.

The first unsafe operation restarts compilation with hints disabled and the ordinary dependency
policy above. If that policy also finds an unsafe crossing, its existing full-tracking restart
still applies. No new runtime error or rejected program is introduced. The shipped `json`
module uses this hint: the dynamic decoder calls scanner methods without borrowing its numeric
cursor fields. Direct access to those fields remains accepted and restores tracking. The
regressions in `tools/test_identity_scope.py` pin the parser layout, test independent synthetic
modules and require unsafe cases to produce the same IR as compiling with hints disabled.

## Policy and programs that do not opt in

The comment is per module: a program can mix modules that opt in with modules that do not, and
values cross between them as above. Programs without an opt-in retain their existing
behavior. The original prototype comparison against main `8990e417` recorded the same IR,
messages and exit status for each of the 3,323 programs of `make irsame`'s 3,358-program corpus that did not opt in,
after normalizing the reference compiler's own paths: the
`build/ref/` library paths that some messages name, the installation prefix that `sys.prefix`
holds, and the lengths of the strings that hold them. The 35 that opt in differ, as they should.

## What works

The tests are `tests/programs/inference/dynany_*.py` (differential, JIT and AOT, also with a collection at every
allocation), `tests/errors/inference/dynany_*.py` and `tests/deviations/dynany_*.py`.
`tests/programs/inference/dynany_graph.py` is the acceptance workload: a deepcopy-style copy of a heterogeneous
object graph. One memo, keyed by `id()`, holds lists, dicts, tuples, scalars and objects of six
unrelated classes; the graph has repeated references (a shared list in three places), cycles
(parents, a registry that holds itself), a field whose type changes (an `int`, then a `float`,
then a `str`), and a copier registered through a function parameter and chosen at run time by
`type(x)` from a class-keyed dictionary. The copy preserves sharing and cycles and is independent
of the original, as CPython's is.

The acceptance workload uses a custom copier. Pystachy's supported
[`copy` subset](../lib/compatibility.md#copy) includes `copy.deepcopy` for supported
values. Compiling unmodified CPython `copy.py` still needs
`getattr(x, "__deepcopy__", None)` and `__reduce_ex__` by run-time names (#489),
`cls.__new__(cls)`, and `object.__dict__` updates.

`tests/programs/upstream/upstream_copyreg_registry.py` uses CPython 3.13.16's
`copyreg.pickle` and `constructor` bodies unchanged. Its helper adds the dynamic
opt-in and an annotation for the empty registry. It checks exact-type reducer
lookup, callback replacement, validation order and reconstruction from reduction
tuples with one argument. `upstream_copyreg_construct.py` returns actual class
values and reconstructs base/subclass instances through `factory(*args)`, checking
exact type, fresh identity and shared mutable payloads. These consumers do not
validate state restoration, serialization memoization/cycles or pickle protocols.

`lib/tomllib` is a library compiled this way: CPython's `tomllib`, whose modules opt in, parses a
document into dicts and lists of `Any` values that programs which do not opt in read
([tomllib](../lib/compatibility.md#tomllib)).

## Measurements

These are historical measurements at the commits named below, not a benchmark of
the current checkout. Construction, processing, memory and compilation costs use
different runs and baselines.

### Workload and timing setup

`tools/dynany_bench.py` (one module that opts in) times construction and processing separately
with `process_time_ns`, excluding startup and compilation. Medians of 7 rounds, each running
every mode once for the AOT build and for CPython 3.13.16, alternating and pinned to one core
(`taskset -c 1`), on a 4-vCPU Intel Xeon 2.80 GHz Linux container with LLVM 18.1.3, compiler at
`bc79f24c`. Every run's checksum equals CPython's. On this shared host, differences under about
20% are noise.

| Mode (N) | What | AOT construct | AOT process | CPython construct | CPython process |
|---|---|---:|---:|---:|---:|
| `typed` (1,000,000) | `list[int]` summed into an `int` | 8.9 ms | 1.1 ms | 37.5 ms | 30.4 ms |
| `union` (1,000,000) | `list[int \| str]`, `isinstance()`, summed | 32.2 ms | 3.2 ms | 37.9 ms | 50.8 ms |
| `dyn` (1,000,000) | `list[Any]`, `isinstance(x, int)`, summed into an `int` | 26.6 ms | 3.2 ms | 46.8 ms | 54.3 ms |
| `generic` (1,000,000) | `list[Any]` summed into an `Any` | 26.5 ms | 17.8 ms | 39.6 ms | 30.5 ms |
| `graph` (2,000) | the acceptance graph: built, then deep-copied and checksummed | 6.7 ms | 28.9 ms | 19.2 ms | 166.9 ms |

### Reading the timing results

- **Boxing** costs construction 3.0× the typed list's (26.6 ms against 8.9 ms: a 16-byte box
  per int above 256), a little less than a closed union's (32.2 ms), which tags its boxes too.
- **Box slots**: since #800 a box takes a 16-byte heap slot rather than 24 bytes. At
  `2438e7e0`, against the same build with main `838aff6d`'s runtime (medians of 7 alternating
  runs pinned to one core of an Intel Xeon at 2.10 GHz), construction took 19.6 ms instead of
  34.9 ms (`union`), 19.3 instead of 26.6 ms (`dyn`) and 21.4 instead of 27.2 ms (`generic`),
  and the graph's copy 22.8 instead of 31.0 ms; `typed` is unchanged. A million boxes no longer
  fill the collector's 32 MiB window, so `union`, `dyn` and `graph` run without a collection.
- **Proven payloads**: after `isinstance(x, int)` the scan reads the payload with no dispatch or
  new box, 3.2 ms, as the union's tag test does. Before that path the scan took 26.2 ms, 8.4×
  as long (the same program built by the compiler at `48e31e33`, median of 7 runs interleaved
  with this build's).
- **Generic arithmetic**, a dispatch and a new box per addition, is 16× the typed sum
  (17.8 ms against 1.1 ms) and 0.6× CPython's processing time.
- **The acceptance graph** builds 2.9× and copies and checks 5.8× faster than CPython.

### Memory

Memory at `2438e7e0`, from separate `PYSTACHY_GC=stats` runs and the process's peak resident
size (`getrusage`; an empty CPython process is 10 MiB; CPython's column is from the round at
`bc79f24c`):

| Mode | Heap peak | Collections | AOT peak RSS | CPython peak RSS |
|---|---:|---:|---:|---:|
| `typed` | 13.0 MiB | 2 | 14 MiB | 48 MiB |
| `union` | 33.1 MiB | 0 | 34 MiB | 48 MiB |
| `dyn` | 33.1 MiB | 0 | 34 MiB | 48 MiB |
| `generic` | 39.1 MiB | 1 | 40 MiB | 48 MiB |
| `graph` | 34.2 MiB | 0 | 34 MiB | 18 MiB |

A million boxes take 16 MB beside the list's 8 MB: a `union` or `dyn` run's heap peaks at
33.1 MiB, 2.5× the typed list's, without a collection. With 24-byte slots, before #800, the same
runs collected once, at a peak of 34.1 MiB; at four million ints the peak is 97.2 MiB against
125.4 MiB then (peak RSS 95 against 126 MiB), with three collections each. A generic
accumulator's discarded boxes raise the peak until a collection (39.1 MiB, against 55.2 MiB with
24-byte slots), and so does the graph's copy, whose heap reaches 1.9× CPython's peak.

### Compilation and code size

Compilation and code size for the benchmark module (5 runs each, median): the IR takes 18 ms,
an AOT build 1.45 s (clang's `-O2` and the link with the runtime) for a 124,000-byte binary,
and a JIT run of `graph 1` 0.153 s end to end with the runtime cache built, where the AOT
binary starts and finishes in 2 ms and CPython in 25 ms. The module's 13 dispatchers are 332 of
its 3,037 lines of function IR: each `get.<field>` dispatcher tests the six classes, 28 or 29
lines.

## Next steps

- **Box elimination where it is proven**: beyond `isinstance()` tests, keep numeric `Any` loop
  accumulators in tag/payload slots, as #742 does for numeric unions, once identity is
  unobservable, and float payloads unboxed across a loop.
- **Widening**: a function that another function's call has taken the return type of, a
  closure's cell and a generator's frame, which would need their users compiled again too.
- **Broader typed-container crossings**: the flow analysis that selects `list[Any]` storage at the
  allocation of every alias of a container that may flow into `Any` storage.
- **Calls**: an `Any` value unpacked into a call's arguments, through a generic binding entry;
  builtin functions as values; `type(x)` as a class object.
- **Protocols**: legacy sequence iteration through `__getitem__`, reverse iteration through
  `__len__`/`__getitem__`, `__length_hint__`, and the
  builtins listed under [deviations](#deviations) that do not take `Any` values yet.
- **Guarded variants and inline caches** only where measurements justify them (#392): a
  dispatcher with one dominant case is a candidate for a guarded direct call.
