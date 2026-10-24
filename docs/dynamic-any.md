# Dynamic `Any` (prototype)

Dynamic `Any` is experimental. To enable it, put this comment before any code in a module:

```python
# pystachy: dynamic-any
```

In that module, `typing.Any` can hold values whose Python type is determined at runtime.
Modules without the comment keep `Any`'s
[inference-only meaning](language/typing.md#supported-types). Both use the ordinary JIT/AOT
pipeline: the program is compiled before it runs.

The sections below explain supported values, conversions between typed and dynamic code,
[limitations](#deviations), and [measured costs](#measurements).

## Selecting dynamic storage

In a module that opts in, `Any` in an annotation is the internal type `dyn` wherever it
appears: parameters, returns, locals, module variables, fields, and the items of containers
(`list[Any]`, `dict[str, Any]`, `tuple[Any, ...]`, `Callable[[Any], Any]`). `Any | None` and
`Optional[Any]` are `Any`, which may hold `None`; a union with `Any` is `Any`. A list or dict
display whose items have no one type (`[1, "two", [3]]`) is a container of `Any` values instead
of a compile error, and so are the displays among its items. Concrete annotations and
unannotated code keep their static types, layouts and templates: boxing is selective, at the
boundary where a concrete value flows into `Any` storage, and when numeric copies or global
reads need to preserve its object identity (see [representation](#representation)).

A list whose items are `Any` values or `Any`'s containers is a `list[Any]`, and a dict whose
values are is a `dict[Any, Any]`: `dict[str, Any]`, `list[dict[str, Any]]`, `dict[str, list[Any]]`
and the records and lists of records that JSON-like code annotates have the layout of `Any`'s
containers, whose items, and keys, are boxes, however they are built (#777). So such a container
becomes an `Any` value, and an `Any` value becomes one, as the same object, and typed and `Any`
code see each other's changes (`tests/programs/inference/dynany_layout.py`,
`tests/programs/inference/dynany_layout_forms.py`). Its items and keys are `Any` values to typed
code too: a key of a `dict[str, Any]` is unboxed where code needs a `str`, and raises `TypeError`
where it holds another type, as an annotation that receives an `Any` value does. `list()` and
`sorted()` of its items give a list of them unboxed where a typed list is expected (`return
list(d)` from a function declared `-> list[str]`). A container of tuples (`list[tuple[str,
Any]]`) or of typed items (`dict[str, int]`), and one that holds `None` items before its first
value types it (`ws = [None]`, then `ws[0] = {...}`), keep their typed layouts.

`json.loads()` decodes into these containers, and `json.dumps()` encodes `Any` values, in a module
that opts in, where the document is `Any` values (#779; [the JSON prototype](json-prototype.md#in-modules-that-opt-in-to-dynamic-any)):
a document decoded once is the same objects to the typed functions and the `Any` code it passes
through. Without `sort_keys`, a `default()` callback's changes to later values and deletion of
later keys are observed. Structural changes can differ from CPython's live dict-table traversal:
the encoder keeps queued keys in their old order and appends newly observed keys. A deleted and
reinserted key can therefore keep its old output position, and clearing and repopulating the
dict can emit replacement entries that CPython skips (`tests/deviations/dynany_json_reinsert.py`).

Storage that an unannotated first value types, and that a later store gives an `Any` value, is
`Any` from that first store, as a CPython variable holds whatever was assigned last
(`tests/programs/inference/dynany_widen.py`):

- **Locals and unannotated parameters** (`total = 0`, then `total += x` with an `Any` `x` in a
  loop): the function is compiled again with them dynamic. Other locals keep their types: in
  the same loop, `count += 1` stays an `int`.
- **Return types**: a function without a return annotation whose returns give an `int` and an
  `Any` value returns `Any`, compiled again.
- **Fields**: a field that `__init__` gives a concrete value is `Any` where a method of its class
  assigns it an `Any` value, as the declarations show it: an `Any` parameter, field or return,
  an item of a container of `Any` items, or arithmetic on one. A field's type is fixed before
  any code that reads it is compiled.
- **Module variables**: one that module code assigns an `Any` value after its first value, as
  far as the types known before module code runs show: an `Any` variable, the target of a loop
  over `Any` items, an item of a container of `Any` items, arithmetic, an attribute or a method
  result of an `Any` value, or a call of a function declared to return `Any`.
- **Locals first assigned `None`**: `found = None`, then `found = x` with an `Any` `x`, also
  where the code that assigns the `Any` value never runs (`tests/programs/inference/dynany_none_first.py`).

Where something besides the function being compiled has already taken the first type, the
storage keeps it, and storing an `Any` value of another type raises `TypeError` (a
[deviation](#deviations)): a local that a closure takes (its cell is shared), a generator's
local (its frame's layout), an annotated variable or field, a field that only code outside its
class's methods assigns an `Any` value, or a value whose type only compiling shows. A return
type that a call from another function took while the function was compiled (functions that
call each other) stays the compile error it was.

Storage of another type holds `None` as a null pointer, not as the box of `None` that an `Any`
value is, so storage that holds `None` first and cannot become `Any` before its first store is
rejected at compile time, with the annotation that makes it `Any` from the start: a generator's
or closure's local (`last: Any = None`), a module variable that holds `None` until a function
gives it an `Any` value (`g: Any = None`), a field that `__init__` sets to `None` and code outside
its class's methods gives an `Any` value (`self.v: Any = None`), and a display of `None` items
that an `Any` value fills (`xs: list[Any] = [None] * n`, `d: dict[str, Any] = {...}`;
`tests/errors/inference/dynany_none_*.py`).

An annotation that mentions `Any` where no `Any` value can stand requests inference, as in a
module that does not opt in. These annotation forms retain inference:
`Callable[..., Any]`, whose parameters no `Callable` type names, a type argument of a class of the
program (`box: Box[Any] = Box(3)`: a specialization is its constructor call's), `*args: Any` and
`**kwargs: Any` of an `__init__` (its class is a class template), the parameters of `__exit__`,
which a `with` statement gives an exception class and an exception (no `Any` value holds one yet),
and the return of `__iter__` and of a generator, whose objects no `Any` value holds yet either
(`tests/programs/inference/dynany_inferred_annotations.py`, `tests/programs/inference/dynany_exit.py`,
`tests/programs/inference/dynany_init_varargs.py`, `tests/programs/inference/dynany_iter_any.py`). `Annotated[Any, ...]` is `Any`
(`tests/programs/inference/dynany_annotated.py`). The items of a display that hold an empty display (or
`list()`, `dict()`, `set()`) that nothing in them types (`([], 3)`) take their type from the items
before them, as elsewhere (`tests/programs/inference/dynany_display_empty.py`); one whose own items
type it, by an item before it of the same kind (`({"a": [1], "b": []}, 1)`, `[list([1]), []]`),
decides with the others whether the items have one type
(`tests/programs/inference/dynany_display_empty_nested.py`). Functions after a `Callable` item are
`Callable`s of its type (`tests/programs/inference/dynany_callables.py`).

Opting in can still reject programs that compile with inferred `Any`, including concrete
container return contexts and nested iterator/generator item types. The
[corpus sweep](testing.md#continuous-integration) tests every differential program in JIT and
AOT; its [exact exception list](../tools/dynany_optin_exceptions.json) records current failures
and their owning issues. These exceptions are compatibility gaps, not equivalent behavior.

[Inferred unions](language/typing.md#inferred-unions) work as in modules that do not opt in: a
variable or result given an `int` and a `float` is an `int | float`. One that is given an `Any`
value too is `Any` instead, and a union's value becomes an `Any` value by the member its tag
selects (`tests/programs/inference/dynany_unions.py`). A display of items of several types (`[1, 2.5]`) is still a
container of `Any` values, as above, which any later store fits.

## Representation

A dynamic value is a pointer to an immutable 16-byte box `{DynType *t, payload}`
(runtime.c's dynamic values):

- **The DynType** is a constant that tells the value's Python type identity (`kind`), its
  `type(x).__name__`, the payload's physical layout as runtime.c's descriptor walks read it
  (`desc`), and, for an object, its class's `O<id>` (which the program's `pys_obj_eq`,
  `pys_obj_cmp` and `pys_obj_repr` dispatch on), its base class's DynType and whether the
  class compares, orders or hashes through its own methods, also with values of other types
  (`DF_X`). runtime.c defines the builtin
  DynTypes (`None`, `bool`, `int`, `float`, `str`, `list`, `dict`, `tuple`); the program
  defines one for each class whose objects it boxes, and one for each function value type.
- **The payload** is an `int`'s, `float`'s or `bool`'s bits, or the original pointer of a
  `str`, list, dict, tuple or object. Boxing never copies a mutable container and never gives
  an alias a second layout.
- **`None` is the constant box `pys_dyn_none_box`, never null.** Null is an unbound variable's
  slot, and the existing "is assigned" flags still tell unbound reads apart. `True`, `False`,
  the ints from -5 to 256 and the program's int literals are constant boxes too, one per value
  (a literal's in each module), and so is each str constant's, whose payload is that constant: a
  literal key of a `dict[str, Any]` allocates nothing (#777). Other numbers' boxes are atomic
  allocations, which the collector does not scan; a reference's box is a scanned allocation,
  so the box keeps its payload alive. DynTypes are constants outside the heap. Dynamic locals,
  arguments and closure cells are ordinary pointer slots, which the conservative collector
  scans; dynamic module variables are registered roots like every pointer-typed global.
- **Containers of boxes**: `list[Any]` (descriptor `LA`), `dict[Any, Any]` (`DAA`, its keys
  hashed by CPython's numeric hash so that `1`, `1.0` and `True` are one key) and tuples of
  boxes (`VA`). Descriptor `A` is a box in a slot: runtime.c's generic `repr`, `==`, ordering,
  hashing, sorting, searching and `KeyError` messages follow it through the box's own DynType,
  so every existing list and dict operation works on containers of `Any` values. A dict with
  `Any` keys compares two boxed strs by their bytes, and two boxed ints or bools by value,
  without that generic path, and hashes a boxed str in one call (#780). `Z` is a
  boxed function, which prints as `<function>` and equals a box of the same function with the
  same object (a bound method's) or env (a closure's), as CPython's methods compare. A bound
  method's box is its own identity for `is` and `id()`, as each evaluation of `o.m` makes a new
  method object; a def's box is a constant, whose payload is its DynType's address, and a
  closure's holds the env its def made for it, so different functions have different `id()`s
  (`tests/programs/inference/dynany_fn_identity.py`).
- **Identity**: two `Any` values are one object, for `is`, exactly where their `id()`s are equal
  (#797). `None`, a bool and a reference are their payload's object. An int, a float and a
  bound method are their box, as an int or float object is in CPython. An int from -5 to 256
  has one constant box per value, and an int literal one per value in each module, its
  functions included, as CPython caches the former and makes a module's equal constants one
  object, and another module's another; an int computed at run time gets a new box, as
  `int("1000") is int("1000")` is `False` in CPython (`tests/programs/inference/dynany_identity.py`
  and `dynany_identity_modules.py`). A float literal likewise has one constant box per exact
  value in each module, shared by its functions. Positive and negative zero have distinct
  boxes; computed floats, including NaNs, are not interned
  (`tests/programs/inference/dynany_float_identity.py`). An int or float variable of typed code
  (a local, parameter, closure cell or comprehension variable of a module that opts in,
  or any module's variable in a program where one does)
  holds one object, as CPython's name does. Beside it is a box
  slot, null until the variable has a box. Each time the variable becomes an `Any` value, it
  gives the slot's box where that box holds its value, else a new box, which the slot then
  holds. A value read before a store gives the variable a new binding (`x, y = y, x`) keeps the
  object it read: the box the slot held at the read, else a new one that the slot does not take.
  A store gives the slot the box of the `Any` value it unboxes, the slot's box of the
  variable it copies, or a numeric literal's constant box. Copying a numeric variable materializes
  its box if needed, so copies made before either variable crosses into `Any` still share one
  object (`tests/programs/inference/dynany_identity_copy.py`). A module variable's read also
  materializes and snapshots its box, before later operands can call code that rebinds the
  variable (`tests/programs/inference/dynany_identity_global_snapshot.py`). Proven single-binding
  integer constants and their from-import copies have their cached or literal box ready at
  initialization, so their reads only load it and cannot allocate
  (`tests/programs/inference/dynany_identity_constants.py`). This applies to
  numeric globals in imported typed modules too when the program uses dynamic `Any`. These
  copies and global reads can allocate before an `Any` crossing, even if none follows.
  A numeric closure cell shares its box slot with every reader and nonlocal writer,
  including closures created before its first box. Its reads also snapshot before
  later operands can rebind the cell. The box remains reachable after the creating
  function returns (`tests/programs/inference/dynany_identity_cells.py`). Cells use
  the existing 16-byte scanned allocation class; the second word now holds the box.
  Copies into or out of a cell can materialize a box even when no `Any` crossing
  follows, including in a factory that returns a closure with only scalar uses.
  A global or closure-cell read used only by a proven scalar arithmetic expression does not materialize
  a box. The expression must contain only concrete numeric names, literals, arithmetic
  and unshadowed numeric conversions; calls to user code, assignment expressions,
  dynamic operands and unknown syntax retain snapshots. Global and cell stores still update
  their identity slots, and copies or values kept across calls retain their objects
  (`tests/programs/inference/dynany_identity_scalar_globals.py`).
  Local numeric bindings carry stack generation counters, so a read before an assignment
  in a skipped branch still shares its binding's object; equal-valued replacements remain
  distinct. A conditional selection between same-typed numeric locals carries the selected slot and
  generation lazily, and a local assignment expression keeps its target's provenance
  (`tests/programs/inference/dynany_identity_expressions.py`). No box is materialized solely
  to produce these expression results.
  Displays whose item storage is already dynamic capture int- or float-typed binding objects as
  each item is evaluated. Thus repeated reads in `[x, x, (x := value)]` keep the old
  object together, and a repeated NaN key or set item stays one entry even when a
  later item rebinds its name. Later items and hashing retain their evaluation order
  (`tests/programs/inference/dynany_identity_display_reads.py`).
  Comprehension targets have their own box slots, renewed for each iteration and
  restored to the enclosing scope after shadowing, including empty comprehensions
  and short-circuit reductions (`tests/programs/inference/dynany_identity_comprehensions.py`).
  Closed functions with explicit numeric parameters and numeric return types omit local box
  slots when their entire body only uses scalar arithmetic, comparisons, control flow, `range`,
  and numeric conversions. Functions proven to return only `None`, including inferred numeric
  specializations, may also omit them and print numeric
  values and literal strings through the unshadowed builtin, without keyword or expanded
  arguments (`tests/ir/dynany_identity_scalar_expressions.py`). Identity tests, `Any` storage, globals, containers, closures and
  other calls prevent that proof (`tests/ir/dynany_numeric_locals.py`). This relies on the
  existing typed numeric return boundary; extending identity preservation across that
  boundary must revisit this proof. Any
  other value, such as an int computed there, is a new object, which its first crossing, copy
  or global or closure-cell read boxes. A float that `isinstance()` narrows an
  `Any` value to is that value's box again where it becomes one
  (`tests/programs/inference/dynany_identity_typed.py`). Where typed code's numbers still cross
  into `Any` as new objects, see the [deviations](#deviations).

Two typed IR operations read a box: `dyn.type` its DynType pointer and `dyn.payload` its
payload, declaring the type a test proved it holds. Neither has a memory effect: a box never
changes. Runtime calls whose descriptor holds an `A` get every effect, as an `O` does, since a
box may hold an object whose `__eq__`, `__hash__` or `__repr__` runs the program's code.

## The typed/dynamic contract

- **Into `Any`**: scalars, `None`, `str`, objects of the program's classes (boxed with their
  concrete class's DynType, chosen by the object's class tag in a hierarchy), containers of
  `Any` items, tuples (made a tuple of boxes: only their identity differs), function values,
  bound methods, closures and `Callable` objects, and unions of these (boxed as the member the
  value's tag selects).
- **Mutable containers of typed items never become `Any` values** (a container whose items hold
  `Any` values has `Any`'s layout: [above](#selecting-dynamic-storage)). A `list[int]` boxed into `Any` would
  either read boxes as ints through its typed aliases, store boxes into memory the collector does
  not scan, or have to be copied (breaking identity). The compiler rejects the crossing and says
  to make the container a `list[Any]` from the start; a display that flows into `Any` storage is
  made one automatically, an empty one too: also one stored into an `Any` value's item or
  attribute (`cont[k] = {}`, `o.kids = [1, 2]`, and in a module that opts in `f()[k] = {}` where
  `f` is declared `-> Any`: `tests/programs/inference/dynany_store_display.py`), which a field or
  `__setitem__` parameter of typed items then rejects at compile time
  (`tests/errors/inference/dynany_store_display_typed.py`). Fresh lists that a builtin method returns
  (`str.split()`, `dict.items()` of an `Any` dict) are converted, since nothing else refers to
  them yet.
- **Between tuple types**: a tuple whose items one side holds as `Any` values and the other as
  typed ones converts item by item into a new tuple: a typed item is boxed where an `Any` item is
  declared (`tuple[int, str]` returned as `tuple[int, Any]`), and an `Any` item is checked and
  unboxed where a typed one is, as below (`tests/programs/inference/dynany_tuple_items.py`).
- **Out of `Any`**: `isinstance()` narrows an `Any` local or parameter to the payload's type for
  the builtin types and classes. `isinstance(x, int)` keeps the box, since a `bool` passes it
  too, but proves that its payload is an int's or a bool's: arithmetic and comparisons on it
  read the payload as an int, whose results are a bool's too but for `&`, `|` and `^` of two
  bools and `**`, which stay dynamic (`tests/programs/inference/dynany_proven_int.py`). A concrete annotation that
  receives an `Any` value checks the box's type where it unboxes it (a union's: one of its
  members), raising
  `TypeError: expected int, got str` where CPython, which does not check annotations, would go
  on: the one kind of runtime error that CPython never raises, a [deviation](#deviations).

## Operations

Arithmetic, comparisons, truth, `is`, `in`, indexing, slicing (of a `str`, list or tuple, with
`Any` bounds too, which convert as CPython converts them: once every bound is evaluated and the
receiver tested, the step first; a dict's slice hashes the slice, then raises its `KeyError`),
item assignment and deletion, `len()`, `str()`, `repr()`, `int()`, `float()`, `bool()`, `abs()`, `hash()`,
`id()`, `sum()` (also of a generator), `sorted()`, `min()`, `max()`, `list()`, `str.join()`,
`dict.update()` (of a dict or of pairs, each an iterable of two), f-strings and `format()`,
iteration, unpacking, augmented assignment, `type(x).__name__`,
`__qualname__` and `__module__`, and `type(x) is C` and `type(x) == type(y)` (exact types: a
bool's is no int's, and every function's is `function`; a typed `y`'s by the value it holds,
`NoneType` for a `list[int] | None` that is `None`: `tests/programs/inference/dynany_type_is_value.py`,
`tests/programs/inference/dynany_type_is_function.py`) work on `Any` values with CPython's
results and errors: `int / int` and `2 ** -1` give floats, `True & False` is a bool, mixed
`int`/`float` comparisons are exact, and the error messages are CPython's
(`TypeError: unsupported operand type(s) for +: 'int' and 'str'`,
`TypeError: can only concatenate str (not "int") to str`, `KeyError: 'k'`, ...).

`abs()` calls a boxed object's `__abs__` method, including inherited methods. Builtin bools
give ints, nonnegative ints keep their identity, and floats give new float objects with a
nonnegative sign. The [signed-64-bit integer limit](language/compatibility.md#numbers) still
applies: `abs(-9223372036854775808)` raises `OverflowError`.

Dict union `d | e` makes a new dict, with the right dict's values taking precedence. `d |= e`
updates the existing dict through `dict.update()`, accepting a dict or builtin iterable of
pairs and preserving aliases. Its key comparisons may run user code. A dict's `|=` updates or
raises before considering a right operand's reflected operator, as CPython does (#810).

runtime.c's generic helpers implement the builtin types' operations. The program's classes
take part through **dispatchers**: functions the compiler writes once every class whose objects
are boxed is known, recompiling them while compiling them boxes more classes. Each tests the
box's DynType against each boxed class that supports the operation, calls that class's own code
(its dunder, field, property or method), and otherwise falls back to the builtin types' helper
or CPython's `AttributeError`/`TypeError`:

| Dispatcher | Operation |
|---|---|
| `op<k>`, `iop<k>`, `un<k>` | binary, in-place and unary arithmetic in CPython's order: the class's in-place dunder; else the reflected dunder of a right operand of a strict subclass that has its own, then the class's dunder; else the reflected dunder of a right operand of another type (not for `str % x`, which formats `x`); then the builtin types' |
| `truth`, `str`, `len` | `__bool__`/`__len__`, `__str__`/`__repr__`, `__len__` |
| `format` | `__format__`, also with an empty spec; else `str()` for an empty spec, and the TypeError that names the class for another |
| `slice`, `module` | a slice, of its bounds and step as `Any` values (an object's `__getitem__` would take a slice object, which Pystachy does not have: `TypeError`), `type(x).__module__` |
| `getitem`, `setitem`, `delitem`, `contains` | the container protocol |
| `get.<a>`, `set.<a>` | attribute `a`: a field or property of the class, or a method, which reads as its bound method |
| `has.<m>.<n>`, `call.<m>.<shape>` | method `m`, called with `n` positional arguments, then the keyword arguments that `<shape>` names (`2-sep-end`: two positional arguments, then `sep=` and `end=`): found before the arguments are evaluated, as CPython's `LOAD_ATTR` finds it, then called, each class's case binding the arguments to its own method's parameters as a typed call binds them, or raising CPython's `TypeError` where they do not fit; a field's value, read before the arguments as `LOAD_ATTR` reads it (`has.<m>.<n>` gives it) and called as `callv.<shape>` calls it; also supported methods of `list`, `dict`, `str`, `tuple`, `int`, `bool` and `float`, whose positional arity errors run after argument evaluation, with keyword arguments where typed code takes them (`list.sort()`'s and `dict.update()`'s) |
| `callv.<shape>` | a call of a boxed function value, bound method or object with `__call__`, with the arguments `<shape>` describes, through the function's own calling code (defaults, a closure's env, keyword arguments), or CPython's `TypeError` where the arguments do not fit, worded by the function's qualified name |

Each case calls the class's operation with `Any` arguments: a method whose parameters are
unannotated or `Any` takes them as they are (a template is instantiated for `Any` once), and
one annotated with a concrete type unboxes them as above. `==` and ordering between objects of
one class (or of a class and its subclass) run the class's `__eq__`, `__lt__` and so on through
the existing `pys_obj_eq`/`pys_obj_cmp`, as typed code compares them: a subclass's `__eq__`
or reflected ordering method first, also where the base class has none, and `x == x` runs
`__eq__` too, while a container's search and a dict's lookup find an object as itself first.
`!=` runs `__ne__` the same way where the class or a subclass defines it (`pys_dyn_ne`), and
otherwise inverts `==` (`tests/programs/inference/dynany_subclass_eq.py`, `tests/programs/inference/dynany_subclass_cmp.py`,
`tests/programs/inference/dynany_ne.py`). An object and a value of another type, an object of an
unrelated class among them, compare as CPython's rich comparison runs them: the left operand's
method, else the right operand's reflected one (a builtin type's own method declines an object),
else identity for `==` and `!=` and `TypeError` for an ordering; `!=` without `__ne__` is not
`__eq__`. The program's `@o.x.<class>` helper runs the class's method with the other value as an
`Any` argument (`tests/programs/inference/dynany_eq_other.py`). A comparison method whose parameter is
`Any` takes any operand, also between typed objects of its class
(`tests/programs/inference/dynany_eq_any_param.py`). One whose parameter has no annotation, or
`object`, is compiled for an `Any` operand there; where its body does not compile for one (a typed
list compared with an `Any` value's field), the compiler also tries the body against the
concrete classes of boxed operands, behind exact `DynType` guards. This bounded adapter requires
the operand to be used exclusively through direct instance fields. Present fields must have the
same types as the annotated operand class (or the receiver class for an unannotated parameter),
or both types must be closed builtin value trees: numbers, strings, `None`, and lists, dicts
or tuples of these, including optional and union members. A field with a different type
may only appear as a direct `==` or `!=` operand against another closed builtin instance
field. Arithmetic, indexing, calls and other uses of that field retain the fallback.
The new allowance also excludes top-level union and variable-length tuple operands,
whose existing comparison coercions can reject a different field type; these types
may still occur inside a supported container field.
Direct equality also supports nonoptional `set` and `frozenset` fields with
`int`, `str` or `bytes` elements. Different element types in this group can only
compare equal when both sets are empty; their lengths are read without probing
one set with the other set's key layout. Set ordering and other element types
do not gain this allowance (`tests/programs/inference/dynany_cmp_scalar_sets.py`).
Equality reads each tree with
its own descriptor, so differently typed empty containers can be equal and numeric leaves
retain exact comparison. It neither converts nor copies their storage. Existing tuple-shape
conversion restrictions and unboxed numeric identity limitations still apply.
A missing field read raises `AttributeError` only when execution reaches that read, preserving
earlier effects and exceptions and branches that never read it. This uses a separate concrete
specialization and does not change an ordinary typed call. Properties, custom attribute lookup,
missing-field writes, whole-operand uses, nested scopes and unsupported syntax retain the fallback.
A canonical field-typed body is checked once; unsupported field types and uses of differently
typed fields are filtered before specialization, avoiding a failed whole-program restart per
boxed class. A concrete body that needs an unsupported operation still retains the fallback. Typed container fields keep
their existing storage and aliases: these adapters neither copy nor box their items
(`tests/programs/inference/dynany_cmp_concrete_body.py`, `dynany_cmp_builtin_fields.py`
and `dynany_cmp_incompatible_body.py`). Missing reads, their evaluation order,
and reflected comparisons are covered by `tests/programs/inference/dynany_cmp_missing_fields.py`,
`dynany_cmp_missing_effects.py` and `dynany_cmp_missing_order.py`. Adapters are emitted only when the generic
dynamic body failed, and follow classes discovered by later dispatcher generation. Failed
concrete attempts have separate `Gen.xnot` keys, so they do not suppress a working adapter or
typed call (`tests/programs/inference/dynany_eq_template.py`). A normal instance comparison method with
one concretely annotated operand retains its typed call where that operand fits the annotation.
For a value of another type, its cross-type helper specializes the same body with an `Any`
operand, preserving method calls, side effects and exceptions instead of treating the annotation
as a reason to decline (`tests/programs/inference/dynany_eq_annotated_body.py`,
`tests/programs/inference/dynany_cmp_annotated_effects.py`). This also handles tuple shapes and
typed-container annotations when the body can operate on dynamic values. If the dynamic body
cannot compile, the original typed call remains available to matching values
(`tests/programs/inference/dynany_cmp_typed_fallback.py`). If neither its dynamic body nor a
guarded concrete-class body compiles, the cross-type call still uses the documented
identity/ordering fallback below. Typed calls and same-hierarchy comparison
helpers retain their existing behavior.
A NamedTuple's `!=` is tuple's, also where its class defines `__eq__`. Arithmetic runs reflected
methods in CPython's order too (`tests/programs/inference/dynany_reflected.py`), which typed code
rejects: no method can return `NotImplemented`, so the first one that runs gives the result.

## Policy and programs that do not opt in

The comment is per module: a program can mix modules that opt in with modules that do not, and
values cross between them as above. A program without the comment produces the same IR,
messages and exit status as before: compiled by the prototype and by main `8990e417`, which it
merges, each of the 3,323 programs of `make irsame`'s 3,358-program corpus that do not opt in
gave the same output, once the reference compiler's own paths were normalized: the
`build/ref/` library paths that some messages name, the installation prefix that `sys.prefix`
holds, and the lengths of the strings that hold them. The 35 that opt in differ, as they should.

## What works

The tests are `tests/programs/inference/dynany_*.py` (differential, JIT and AOT, also with a collection at every
allocation), `tests/errors/inference/dynany_*.py` and `tests/deviations/dynany_*.py`.
`tests/programs/inference/dynany_graph.py` is the acceptance workload: a deepcopy-style copy of a heterogeneous
object graph. One memo, keyed by `id()`, holds lists, dicts, tuples, scalars and objects of six
unrelated classes; the graph has repeated references (a shared list in three places), cycles
(parents, a registry that holds itself), a field whose type changes (an `int`, then a `float`,
then a `str`), and a copier chosen at run time by `type(x).__name__` from a dict of
`Callable[[Any, dict[int, Any]], Any]`. The copy preserves sharing and cycles and is independent
of the original, as CPython's is.

This is not `copy.deepcopy` itself. Running the unchanged module still needs `type(x)` as a
value with class objects as dict keys (#7), `getattr(x, "__deepcopy__", None)` and
`__reduce_ex__` by run-time names (#489), `cls.__new__(cls)`, and `object.__dict__` updates.

`lib/tomllib` is a library compiled this way: CPython's `tomllib`, whose modules opt in, parses a
document into dicts and lists of `Any` values that programs which do not opt in read
([tomllib](../lib/compatibility.md#tomllib)).

## Deviations

- A concrete annotation that receives an `Any` value raises `TypeError` where its type differs
  (CPython does not check annotations). `int` takes no `bool` and `float` no `int` this way,
  so that a typed variable never prints another value than CPython's. So does the storage that
  [keeps its first type](#selecting-dynamic-storage) when an `Any` value reaches it.
- A cross-type comparison method whose body cannot compile for an `Any` operand and falls
  outside the supported guarded concrete adapter still does
  not run with that operand: the comparison is identity's, or `TypeError` for an ordering, where
  CPython runs the method, whose body may give another result or raise another error
  (`tests/deviations/dynany_cmp_uncompiled_body.py`, whose operand has an incompatible typed
  tuple-element set field). Closed builtin container-field comparisons, scalar-set equality
  and missing-field reads now execute
  through guarded concrete adapters. Concrete operand annotations alone no
  longer suppress normal instance comparison methods; the remaining unsupported-body fallback
  is a correctness gap tracked by #803, not a stable comparison contract.
- An object is not iterable through an `Any` value yet (iteration of objects is under
  [next steps](#next-steps)): a `for` loop over one, and a pair of `dict.update()` that is one,
  raise `TypeError` where CPython calls its `__iter__` (`tests/deviations/dynany_iter_object.py`).
- `in` of an `Any` item in a typed container (`x in xs` with `xs: list[int]`) unboxes the item
  as the container's item type, raising `TypeError` where CPython would answer `False`.
- `dict.keys()`, `values()` and `items()` of an `Any` dict give lists, as the typed ones do.
- An int or float of typed code that no variable's box slot holds is a new object where it
  becomes an `Any` value, where CPython's names, containers and classes hold one object: an
  argument or a parameter's default value (the parameter receives a new object), a return
  value, an item of a typed container, a typed field or class variable, and the name
  that `from m import x` binds. So is an expression
  of literals, which CPython's compiler folds into a constant (`999 + 1` is the object of the
  literal `1000` there) (`tests/deviations/dynany_identity_boundary.py`). Displays
  whose dynamic item storage is known before evaluating their items preserve the
  int- or float-typed binding objects; this does not change typed container storage
  or calling conventions. Numeric locals whose inferred storage joins different
  types can still lose identity in displays. An inferred starred display that discovers dynamic storage only
  after evaluating its items can still split repeated reads before rebinding:
  `[x, *dynamic_items, x, (x := value)]`. An explicit `list[Any]` destination avoids
  this remaining display case.
- A function value prints as `<function>`; builtin functions and methods (`len`, `"".join`)
  cannot become `Any` values yet.
- Calls of `Any` values and their methods take positional and keyword arguments, and what a
  typed call unpacks (a tuple's items, a dict display with str keys, a function's `**kwargs`);
  an `Any` value unpacked into a call's arguments (`f(*xs)`) is rejected at compile time. A
  builtin type's method takes keyword arguments only where typed code takes them
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
- `%` of an `Any` str raises `TypeError`: printf-style formatting is implemented for a str that
  is known as such, which formats `Any` values (`tests/deviations/dynany_str_mod.py`).
- A slice of an object through an `Any` value raises `TypeError`: its `__getitem__` would take a
  slice object, which Pystachy does not have (typed code rejects the slice at compile time).
- A NamedTuple's object compares and hashes as the tuple of its fields through `Any` values
  (`tests/programs/inference/dynany_namedtuple.py`), but it is no sequence there: `len()`, indexing and
  iteration raise `TypeError`, and an object of another NamedTuple class compares with it by
  identity (an ordering raises `TypeError`), where CPython compares their fields.
- An object is not iterable through an `Any` value yet: `for`, `list()` and `in` (where its
  class has no `__contains__`) raise `TypeError` instead of calling `__iter__`. `int()` and
  `float()` of an object raise `TypeError` instead of calling `__int__`, `__index__` or
  `__float__`.
- A static or class method read through an `Any` value without a call raises `AttributeError`
  (typed code rejects a static method as a value at compile time), and so does a call of a
  property's value (`x.p(...)`). A field's value is called as a function value is.
- Assigning an attribute that the object's class does not have raises `AttributeError` (a
  class's fields are fixed), as for typed objects.
- `set`, `bytes` and exception objects, and typed containers other than tuples, cannot become
  `Any` values yet.
- Rejected at compile time where an argument is an `Any` value: `divmod()`, `round()`,
  `chr()`, `ord()`, `bin()`, `hex()`, `oct()`, `dict()`, `tuple()` (`tuple(list(x))` works),
  `reversed()`, `iter()`, `next()`, `getattr()`, `hasattr()`, `setattr()` and `del` of an
  attribute.

## Measurements

`tools/dynany_bench.py` (one module that opts in) times construction and processing separately
with `process_time_ns`, excluding startup and compilation. Medians of 7 rounds, each running
every mode once for the AOT build and for CPython 3.13.16, alternating and pinned to one core
(`taskset -c 1`), on a 4-vCPU Intel Xeon 2.80 GHz Linux container with LLVM 18.1.3, compiler at
`bc79f24c`. Every run's checksum equals CPython's. On this shared host, differences under about
20% are noise.

| Mode (N) | What | AOT build | AOT process | CPython build | CPython process |
|---|---|---:|---:|---:|---:|
| `typed` (1,000,000) | `list[int]` summed into an `int` | 8.9 ms | 1.1 ms | 37.5 ms | 30.4 ms |
| `union` (1,000,000) | `list[int \| str]`, `isinstance()`, summed | 32.2 ms | 3.2 ms | 37.9 ms | 50.8 ms |
| `dyn` (1,000,000) | `list[Any]`, `isinstance(x, int)`, summed into an `int` | 26.6 ms | 3.2 ms | 46.8 ms | 54.3 ms |
| `generic` (1,000,000) | `list[Any]` summed into an `Any` | 26.5 ms | 17.8 ms | 39.6 ms | 30.5 ms |
| `graph` (2,000) | the acceptance graph: built, then deep-copied and checksummed | 6.7 ms | 28.9 ms | 19.2 ms | 166.9 ms |

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
- **Typed-container crossings**: the flow analysis that selects `list[Any]` storage at the
  allocation of every alias of a container that may flow into `Any` storage.
- **Calls**: an `Any` value unpacked into a call's arguments, through a generic binding entry;
  builtin functions as values; `type(x)` as a class object.
- **Protocols**: iteration of objects (`__iter__`), `__int__`/`__index__`/`__float__`, and the
  builtins listed under [deviations](#deviations) that do not take `Any` values yet.
- **Guarded variants and inline caches** only where measurements justify them (#392): a
  dispatcher with one dominant case is a candidate for a guarded direct call.
