# Dynamic `Any` (prototype)

A module whose first lines, before any code, hold the comment

```python
# pystachy: dynamic-any
```

compiles `typing.Any` as a dynamic type: a value whose Python type is known only when the
program runs. Every other module, and every program without the comment, compiles exactly as
before: there `Any` keeps its [inference-only meaning](language/typing.md#supported-types). The
prototype runs through the ordinary JIT/AOT pipeline; there is no interpreter, profiling or
online compilation. It establishes the generic representation and operations that later
optimization (box elimination, guarded variants, inline caches) would need, and measures what
they cost.

This page describes the representation, the typed/dynamic contract, what works, what is
rejected, the deviations, and measurements. Design input: #108 (contract), #487 (descriptor
box), #488 and #489 (dispatch and attribute lookup), #392 (specialization evidence).

## Selecting dynamic storage

In a module that opts in, `Any` in an annotation is the internal type `dyn` wherever it
appears: parameters, returns, locals, module variables, fields, and the items of containers
(`list[Any]`, `dict[str, Any]`, `tuple[Any, ...]`, `Callable[[Any], Any]`). `Any | None` and
`Optional[Any]` are `Any`, which may hold `None`; a union with `Any` is `Any`. A list or dict
display whose items have no one type (`[1, "two", [3]]`) is a container of `Any` values instead
of a compile error, and so are the displays among its items. Concrete annotations and
unannotated code keep their static types, layouts and templates: boxing is selective, at the
boundary where a concrete value flows into `Any` storage.

Storage that an unannotated first value types, and that a later store gives an `Any` value, is
`Any` from that first store, as a CPython variable holds whatever was assigned last
(`tests/dynany_widen.py`):

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
  where the code that assigns the `Any` value never runs (`tests/dynany_none_first.py`).

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
`tests/errors/dynany_none_*.py`).

[Inferred unions](language/typing.md#inferred-unions) work as in modules that do not opt in: a
variable or result given an `int` and a `float` is an `int | float`. One that is given an `Any`
value too is `Any` instead, and a union's value becomes an `Any` value by the member its tag
selects (`tests/dynany_unions.py`). A display of items of several types (`[1, 2.5]`) is still a
container of `Any` values, as above, which any later store fits.

## Representation

A dynamic value is a pointer to an immutable 16-byte box `{DynType *t, payload}`
(runtime.c's dynamic values):

- **The DynType** is a constant that tells the value's Python type identity (`kind`), its
  `type(x).__name__`, the payload's physical layout as runtime.c's descriptor walks read it
  (`desc`), and, for an object, its class's `O<id>` (which the program's `pys_obj_eq`,
  `pys_obj_cmp` and `pys_obj_repr` dispatch on), its base class's DynType and whether the
  class compares, orders or hashes through its own methods. runtime.c defines the builtin
  DynTypes (`None`, `bool`, `int`, `float`, `str`, `list`, `dict`, `tuple`); the program
  defines one for each class whose objects it boxes, and one for each function value type.
- **The payload** is an `int`'s, `float`'s or `bool`'s bits, or the original pointer of a
  `str`, list, dict, tuple or object. Boxing never copies a mutable container and never gives
  an alias a second layout.
- **`None` is the constant box `pys_dyn_none_box`, never null.** Null is an unbound variable's
  slot, and the existing "is assigned" flags still tell unbound reads apart. `True`, `False`
  and the ints from -5 to 256 are constant boxes too. Other numbers' boxes are atomic
  allocations, which the collector does not scan; a reference's box is a scanned allocation,
  so the box keeps its payload alive. DynTypes are constants outside the heap. Dynamic locals,
  arguments and closure cells are ordinary pointer slots, which the conservative collector
  scans; dynamic module variables are registered roots like every pointer-typed global.
- **Containers of boxes**: `list[Any]` (descriptor `LA`), `dict[Any, Any]` (`DAA`, its keys
  hashed by CPython's numeric hash so that `1`, `1.0` and `True` are one key) and tuples of
  boxes (`VA`). Descriptor `A` is a box in a slot: runtime.c's generic `repr`, `==`, ordering,
  hashing, sorting, searching and `KeyError` messages follow it through the box's own DynType,
  so every existing list and dict operation works on containers of `Any` values. `Z` is a
  boxed function, which prints as `<function>` and equals a box of the same function with the
  same object (a bound method's) or env (a closure's), as CPython's methods compare. A bound
  method's box is its own identity for `is` and `id()`, as each evaluation of `o.m` makes a new
  method object.

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
- **Typed mutable containers never become `Any` values.** A `list[int]` boxed into `Any` would
  either read boxes as ints through its typed aliases, store boxes into memory the collector does
  not scan, or have to be copied (breaking identity). The compiler rejects the crossing and says
  to make the container a `list[Any]` from the start; a display that flows into `Any` storage is
  made one automatically. Fresh lists that a builtin method returns (`str.split()`,
  `dict.items()` of an `Any` dict) are converted, since nothing else refers to them yet.
- **Out of `Any`**: `isinstance()` narrows an `Any` local or parameter to the payload's type for
  the builtin types and classes. `isinstance(x, int)` keeps the box, since a `bool` passes it
  too, but proves that its payload is an int's or a bool's: arithmetic and comparisons on it
  read the payload as an int, whose results are a bool's too but for `&`, `|` and `^` of two
  bools and `**`, which stay dynamic (`tests/dynany_proven_int.py`). A concrete annotation that
  receives an `Any` value checks the box's type where it unboxes it (a union's: one of its
  members), raising
  `TypeError: expected int, got str` where CPython, which does not check annotations, would go
  on: the one kind of runtime error that CPython never raises, a [deviation](#deviations).

## Operations

Arithmetic, comparisons, truth, `is`, `in`, indexing, item assignment and deletion, `len()`,
`str()`, `repr()`, `int()`, `float()`, `bool()`, `hash()`, `id()`, `sum()`, `sorted()`,
`min()`, `max()`, `list()`, `tuple()`, `str.join()`, f-strings and `format()`, iteration,
unpacking, augmented assignment and `type(x).__name__` work on `Any` values with CPython's
results and errors: `int / int` and `2 ** -1` give floats, `True & False` is a bool, mixed
`int`/`float` comparisons are exact, and the error messages are CPython's
(`TypeError: unsupported operand type(s) for +: 'int' and 'str'`,
`TypeError: can only concatenate str (not "int") to str`, `KeyError: 'k'`, ...).

runtime.c's generic helpers implement the builtin types' operations. The program's classes
take part through **dispatchers**: functions the compiler writes once every class whose objects
are boxed is known, recompiling them while compiling them boxes more classes. Each tests the
box's DynType against each boxed class that supports the operation, calls that class's own code
(its dunder, field, property or method), and otherwise falls back to the builtin types' helper
or CPython's `AttributeError`/`TypeError`:

| Dispatcher | Operation |
|---|---|
| `op<k>`, `iop<k>`, `un<k>` | binary, in-place and unary arithmetic: the class's dunder, then the right operand's reflected one, then the builtin types' |
| `truth`, `str`, `len` | `__bool__`/`__len__`, `__str__`/`__repr__`, `__len__` |
| `getitem`, `setitem`, `delitem`, `contains` | the container protocol |
| `get.<a>`, `set.<a>` | attribute `a`: a field or property of the class |
| `has.<m>.<n>`, `call.<m>.<n>` | method `m` with `n` positional arguments: found before the arguments are evaluated, as CPython's `LOAD_ATTR` finds it, then called; also the methods of `list`, `dict`, `str`, `tuple`, `int`, `bool` and `float` |
| `callv.<n>` | a call of a boxed function value, bound method or object with `__call__` with `n` positional arguments, through the function's own calling code (defaults, a closure's env), or CPython's `TypeError` for a wrong count |

Each case calls the class's operation with `Any` arguments: a method whose parameters are
unannotated or `Any` takes them as they are (a template is instantiated for `Any` once), and
one annotated with a concrete type unboxes them as above. `==` and ordering between objects of
one class (or of a class and its subclass) run the class's `__eq__`, `__lt__` and so on through
the existing `pys_obj_eq`/`pys_obj_cmp`, as typed code compares them: a subclass's `__eq__`
first, also where the base class has none, and `x == x` runs `__eq__` too, while a container's
search and a dict's lookup find an object as itself first (`tests/dynany_subclass_eq.py`).
Objects of unrelated classes compare by identity.

## Policy and programs that do not opt in

The comment is per module: a program can mix modules that opt in with modules that do not, and
values cross between them as above. A program without the comment produces the same IR,
messages and exit status as before: compiled by the prototype and by main `611af05e`, which it
merges, each of the 3,239 programs of `make irsame`'s 3,262-program corpus that do not opt in
gave the same output, once the reference compiler's own paths were normalized: the
`build/ref/` library paths that some messages name, the installation prefix that `sys.prefix`
holds, and the lengths of the strings that hold them. The 23 that opt in differ, as they should.

## What works

The tests are `tests/dynany_*.py` (differential, JIT and AOT, also with a collection at every
allocation), `tests/errors/dynany_*.py` and `tests/deviations/dynany_annotation_check.py`.
`tests/dynany_graph.py` is the acceptance workload: a deepcopy-style copy of a heterogeneous
object graph. One memo, keyed by `id()`, holds lists, dicts, tuples, scalars and objects of six
unrelated classes; the graph has repeated references (a shared list in three places), cycles
(parents, a registry that holds itself), a field whose type changes (an `int`, then a `float`,
then a `str`), and a copier chosen at run time by `type(x).__name__` from a dict of
`Callable[[Any, dict[int, Any]], Any]`. The copy preserves sharing and cycles and is independent
of the original, as CPython's is.

This is not `copy.deepcopy` itself. Running the unchanged module still needs `type(x)` as a
value with class objects as dict keys (#7), `getattr(x, "__deepcopy__", None)` and
`__reduce_ex__` by run-time names (#489), `cls.__new__(cls)`, and `object.__dict__` updates.

## Deviations

- A concrete annotation that receives an `Any` value raises `TypeError` where its type differs
  (CPython does not check annotations). `int` takes no `bool` and `float` no `int` this way,
  so that a typed variable never prints another value than CPython's. So does the storage that
  [keeps its first type](#selecting-dynamic-storage) when an `Any` value reaches it.
- `in` of an `Any` item in a typed container (`x in xs` with `xs: list[int]`) unboxes the item
  as the container's item type, raising `TypeError` where CPython would answer `False`.
- `dict.keys()`, `values()` and `items()` of an `Any` dict give lists, as the typed ones do.
- An object's `__format__` is not called through an `Any` value; a format spec raises
  `TypeError` for it.
- A function value prints as `<function>`; builtin functions and methods (`len`, `"".join`)
  cannot become `Any` values yet.
- Calls of `Any` values and their methods take positional arguments only; keywords and
  unpacking are rejected at compile time.
- A builtin type's method that typed code does not support either (`int.to_bytes()`,
  `int.as_integer_ratio()`) raises `AttributeError` where it is called through an `Any` value;
  typed code rejects it at compile time.
- Objects of unrelated classes compare by identity even where `__eq__` would accept the other
  object (CPython calls it); `__eq__` between an object and a builtin value is not called.
- Assigning an attribute that the object's class does not have raises `AttributeError` (a
  class's fields are fixed), as for typed objects.
- `set`, `bytes` and exception objects, and typed containers other than tuples, cannot become
  `Any` values yet.

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
- **Proven payloads**: after `isinstance(x, int)` the scan reads the payload with no dispatch or
  new box, 3.2 ms, as the union's tag test does. Before that path the scan took 26.2 ms, 8.4×
  as long (the same program built by the compiler at `48e31e33`, median of 7 runs interleaved
  with this build's).
- **Generic arithmetic**, a dispatch and a new box per addition, is 16× the typed sum
  (17.8 ms against 1.1 ms) and 0.6× CPython's processing time.
- **The acceptance graph** builds 2.9× and copies and checks 5.8× faster than CPython.

Memory, from separate `PYSTACHY_GC=stats` runs and the process's peak resident size
(`getrusage`; an empty CPython process is 10 MiB):

| Mode | Heap peak | Live at the last collection | AOT peak RSS | CPython peak RSS |
|---|---:|---:|---:|---:|
| `typed` | 13.0 MiB | 4.0 MiB | 13 MiB | 48 MiB |
| `union` | 34.1 MiB | 24.0 MiB | 33 MiB | 48 MiB |
| `dyn` | 34.1 MiB | 24.0 MiB | 33 MiB | 48 MiB |
| `generic` | 55.2 MiB | 24.0 MiB | 56 MiB | 48 MiB |
| `graph` | 34.2 MiB | 8.6 MiB | 35 MiB | 18 MiB |

The boxes of a million ints retain 16 MiB beside the list's 8 MiB: a heap peak 2.6× the typed
list's (34.1 MiB against 13.0 MiB), the same as the union's. A generic accumulator's discarded
boxes raise the peak until a collection, and so does the graph's copy: its live data, 8.6 MiB,
is close to CPython's 8 MiB above an empty process, but the heap grows to 1.9× CPython's peak
before the collector runs.

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
- **Calls**: keyword arguments and `*args` through a generic binding entry; builtin functions
  as values; `type(x)` as a class object.
- **Guarded variants and inline caches** only where measurements justify them (#392): a
  dispatcher with one dominant case is a candidate for a guarded direct call.
