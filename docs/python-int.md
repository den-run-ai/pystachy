# Promoting ints (prototype)

Promoting ints are an experimental way to use arbitrary-precision Python integers.
Arithmetic keeps a signed 64-bit value while it fits, allocates a larger integer on
overflow, and returns to the small representation when the result fits again.

The opt-in is per module. Supported containers can retain large values across
modules, but some operations still require a 64-bit integer. Check the
[boundary reference](#64-bit-boundaries) before using this feature in a port.
The [integer roadmap](https://github.com/den-run-ai/pystachy/issues/907) tracks
remaining work; [`mpz`](mpz.md) is the separate, explicit big-integer API.

## Enable promoting ints

Put `# pystachy: python-int` before any code in the module. CPython ignores the
comment, so the same source runs under CPython and Pystachy:

```python
# pystachy: python-int
def fact(n: int) -> int:
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


print(fact(25))                      # 15511210043330985984000000
print(fact(25) // fact(23))           # 600, a 64-bit value again
print(2 ** 100 > 1e30, hash(2 ** 64))  # True 8
print(int("123456789012345678901234567890") % 97)  # 52
```

Modules without the comment keep the [checked 64-bit integer policy](language.md#types).
This includes the compiler, `runtime.py` and most library code. The
[library and generic-class rules](#libraries-and-generic-classes) below describe
the exceptions. A module can also enable [dynamic `Any`](#dynamic-any).

Use this page to check [supported operations](#what-a-module-that-opts-in-gets),
[limits](#64-bit-boundaries) and [deviations](#deviations). Maintainer details are
under [representation](#representation), [measurements](#measurements) and
[tests](#tests).

## What a module that opts in gets

### Variables and arithmetic

An `int` annotation in an opted-in module selects a promoting integer for
parameters, returns, locals, fields and module variables. Unannotated locations
that receive a promoting integer widen to that type through
[inference](language/typing.md#inferred-unions). A fitting literal remains a
64-bit value until it meets a promoting value. Scalar `int | None` locations can
also hold large integers; optional values inside containers have separate limits.

Arithmetic in the opted-in module can promote even when its operands came from a
64-bit module, container or builtin. For example, `xs[0] * xs[1]` is exact once
both reads succeed. A read that crosses a [64-bit boundary](#64-bit-boundaries)
can still fail before arithmetic starts.

| Operation | Behavior |
|---|---|
| `+`, `-`, `*`, `//`, `%`, bitwise operators, shifts and `**` | Exact integer results, including augmented assignments and unary `+`, `-` and `~`; negative integer exponents remain restricted below. |
| `/` | Rounds the quotient once to the nearest float, with halfway cases rounded to even; raises `OverflowError` outside the float range. |
| Comparisons, truth, `min()` and `max()` | Exact, including mixed int/float comparisons: `2 ** 53 + 1 > 9007199254740992.0` is true. |
| `sum()` with an integer start and integer items | Exact for lists, tuples, sets, dict keys, ranges, generators, iterators and `map()`. A float start or mixed float items introduces a boundary. |
| `abs()`, `pow(x, y)`, `pow(x, y, m)` | Accept large integers. Three-argument `pow` supports negative exponents through modular inversion. |
| Type and equality checks | Both representations have Python type `int`; `isinstance(x, int)` works. An int never equals a string, bytes value or container. |

Division or remainder by zero raises `ZeroDivisionError`; a negative shift count
raises `ValueError`. A shift or power whose result cannot fit in memory raises
`MemoryError`. As with checked integers, `int ** negative_int` raises `ValueError`
where CPython returns a float.

### Conversion and formatting

| API | Supported behavior |
|---|---|
| Integer literals and `int()` | Large literals in every supported base; text parsing with bases 0 and 2–36, underscores, signs, Unicode digits and whitespace; conversion from floats. |
| `float()` and `math.isclose()` | Correctly rounded conversion; `OverflowError` outside the float range. `math.isclose()` compares the converted floats. |
| `str()`, `repr()`, `bin()`, `hex()`, `oct()` | Format large values. Decimal conversion retains the native 4,300-digit limit. |
| F-strings, `format()` and `%` formatting | Integer format specifications accept large values; float specifications convert to a float, as CPython does. |
| `hash()`, `bool()`, `round(x)`, `bit_length()`, `bit_count()` | Accept large values; integer hashing matches CPython. |

### Booleans

`bool` remains a distinct type. Arithmetic and comparisons use its numeric value,
but storing or returning a bool as an annotated `int` is rejected. Conditional
expressions, `and`, `or`, `min()` and `max()` cannot silently turn a bool result
into an int. An unannotated location receiving both types holds their union,
which has the [closed-union limit](#storage-boundaries).

A bool can be passed to an `int` parameter only when the compiler proves that the
function uses the parameter numerically. Accepted uses are:

- Arithmetic and comparisons with numeric literals or the function's numeric
  parameters, truth tests, and `&`, `|` or `^` with an int literal.
- `int()`, `float()`, `abs()`, `round()`, `hash()`, `bool()`, `range()`, `chr()`,
  `hex()`, `oct()` and `bin()`.

The call is rejected if the parameter can be returned, stored, printed,
formatted, passed on, used as an index, tested for type or identity, used with
`in`, or read inside a nested function, lambda or comprehension. Reading locals
through `locals()`, `vars()`, `eval()` or `exec()` also prevents the proof.
Rebinding one of the listed builtin names prevents it; in a closure, any call
of one prevents it. Calls through a `Callable` do not accept a bool for an
`int` parameter.

### Containers

In an opted-in module, the storage forms below retain large integers. Once any
module opts in, integer lists, dictionaries and sets also preserve large stored
values across modules, including ints inside fixed tuples. Ordinary reads in
fixed-width modules still narrow, except through the
[iterator and library helpers](#iteration) below. A standalone tuple follows
its item types and annotated boundaries.

| Storage | Supported operations on large values |
|---|---|
| Fixed-shape tuples | Returns, unpacking, constant or variable indexing, literal slices, concatenation, literal repetition, iteration, membership, `index()`, `count()`, comparisons, hashing and formatting. `divmod()` returns promoting ints in its tuple. |
| `list[int]` | Displays, comprehensions, append/insert, item and slice assignment, extend/`+=`, indexing, iteration, unpacking, `pop()`, searches, comparisons, sorting with or without a key, reductions, copies, slices, `+`, `*`, reverse and repr. Searches and comparisons against floats are exact. |
| Lists of tuples containing ints | Includes mixed and nested tuples such as `list[tuple[int, str]]` and `list[tuple[tuple[int, int], int]]`. Supports displays, comprehensions, append/insert, item assignment, extend/`+=`, reads, `pop()`, sorting, searches, comparisons and repr. Tuple sort keys and comparisons against float tuples work; search keys may be optional tuples. |
| Dict integer keys | Construction, comprehensions, assignment, augmented assignment, update, copies, `fromkeys()` and `setdefault()` preserve the keys. Lookup, membership, deletion, `get()` and `pop()` compare exactly, including `int \| None` lookup keys. |
| Dict integer values | Assignment, augmented assignment, construction, comprehensions, update, `setdefault()` and copies preserve values. Indexing, `get()`, `pop()`, `setdefault()`, `popitem()` and value/item iteration return them. Repr and equality preserve the values. |
| Dict tuple values | Tuples containing ints retain large values through construction, stores, updates, `fromkeys()`, copies and method defaults, as well as reads, sorting, searches, repr and equality. Optional tuple results have a [boundary](#storage-boundaries). |
| Tuple dict keys and set/frozenset elements | Includes mixed and nested tuples. Hashing, lookup, stores, deletion, copies, comparisons and set algebra preserve the ints. Lookup tuples may be optional or use a bool for an integer item. |
| Integer sets and frozensets | Construction, comprehensions, updates and set algebra preserve values; searches, removal, iteration, `pop()`, sorting, reductions, copies, comparisons and repr use them. Hashes and iteration/`pop()` order follow CPython. |

The normal mutability rules still apply: `add()`, `discard()`, `remove()` and
`pop()` belong to mutable sets. Tuple comparisons are exact against supported
64-bit-int, bool and float tuples.

Dictionary materialization also preserves these values: `keys()` and `values()`
produce typed lists. `items()` produces a list of key/value tuples; `popitem()`
returns one such tuple.
`dict()` and `update()` accept pairs from lists, `zip()`, `enumerate()`, generators
and other dictionaries' `items()`. NamedTuple `_asdict()` and `dict(vars(o))`
preserve supported integer and tuple fields. Lists materialized from dictionaries
and sets use the same integer/tuple rules.

### Iteration

Generators can yield and return promoting ints. In opted-in code, `for`,
comprehensions, `next()`, unpacking, `send()` and `throw()` read those values.
Consumers such as `list()`, `sorted()`, `sum()`, `min()`, `max()`, membership,
`enumerate()` and `zip()` preserve them. `yield from` forwards yielded values and
retains the generator's return value, as in `Generator[int, None, int]`.
Values **sent into** a generator still cross a 64-bit boundary.

The builtin `iter()` helpers for lists, tuples, dictionaries and their snapshots,
and sets preserve promoting ints in **every** module, including ints inside
tuples. They stay exhausted after exhaustion and raise `RuntimeError` when a
dict or set changes size. The helpers use `specs.READ_HELPERS`; their own
positions and counts stay 64-bit.

### Libraries and generic classes

| API | Integer policy when any module opts in |
|---|---|
| `heapq`, `bisect` | Preserve ints and tuple-contained ints in the lists they modify; aliases see the same changes. `nsmallest()`/`nlargest()` also preserve generator values, with or without a key. `specs.READ_HELPERS` keeps their positions and counts 64-bit. |
| `collections.Counter` | Counts promote through stores, reads, `update()`, `subtract()`, arithmetic/set-style operators, totals and `most_common()`. Its definitions use `specs.INT_HELPERS`; keys follow the generic-class rule below. |
| Generic classes bound to `int` | `Box[int]`, `Box(1)` and `Box(2 ** 70)` select one promoting-int specialization across modules. Fields, parameters, results and containers of that type variable preserve large ints. |
| Generic library containers and caches | The same rule covers `deque`, `defaultdict`, `OrderedDict`, Counter keys, and results retained by `functools.cache` and `lru_cache`. |

Methods of a generic class specialized for ints read their containers with
`bigints.read_policy`. Class templates with unannotated `__init__` parameters and
generic functions keep their own module's policy; each call binds the argument's
actual type.

### Callable boundaries

`Callable` signatures share promoting `int` and `int | None` parameters and
results across the program. This covers functions, builtins, lambdas, closures
and bound methods, including overridden methods and callables kept in fields,
containers or a `defaultdict` factory.

The adapter still honors the wrapped function's policy. A function with an `int`
parameter in a module without the opt-in receives a checked 64-bit value; an
oversized argument raises `OverflowError`. Its result promotes on return. Ints
inside other callable parameter/result types, such as `tuple[int, int]`, remain
64-bit boundaries. See `calls.adapter` in the compiler.

### Object protocols

- Comparison methods, including reflected comparisons and overrides, follow
  their declared parameter policy. An opted-in `int` parameter accepts large
  ints when comparing objects or searching tuples with `in`, `count()` and
  `index()`. A fixed-width parameter narrows. `object()` and ranges never equal an int.
- `__len__` may return a promoting int. `len()` and truth testing reject a
  negative result with `ValueError`, and a positive result past 64 bits with
  `OverflowError: cannot fit 'int' into an index-sized integer`.
- `__hash__` may return a promoting int. `hash()`, dicts and sets hash an
  oversized result as an integer.
- `vars()` and `__dict__` expose promoting-int fields, optional ints and tuples
  containing them.
- `SystemExit` status and `OSError` errno accept promoting or optional ints.
  Outside signed 64-bit range, `SystemExit` uses status `-1`, while an `OSError`
  errno selects no specialized subclass. `None` remains supported.

### Dynamic `Any`

Enable both `# pystachy: dynamic-any` and `# pystachy: python-int` to make boxed
integer arithmetic promote on overflow. Boxing, unboxing to a promoting type,
field reads, dynamic containers, comparisons, hashing and conversions preserve
large values; both representations have Python type `int`.

A dynamic-only module can operate exactly on an already large integer, but two
in-range dynamic ints still use checked 64-bit arithmetic there. An explicitly
fixed-width destination still narrows.

Supported numeric identity channels keep the same box, including `int()` of an
exact `Any` int and typed numeric list items. Typed tuple, dict, set and generator
identity gaps remain in the [dynamic `Any` deviations](dynamic-any.md#deviations).

## 64-bit boundaries

These destinations still require an integer in `[-2**63, 2**63 - 1]`. A supported
conversion of a larger value raises:

```text
OverflowError: Python int too large to convert to C long
```

Some of these boundaries reject values CPython accepts. The
[deviation tests](../tests/deviations/python_int_limits.py) give small examples.

### Storage boundaries

| Destination | Limit |
|---|---|
| Closed unions other than scalar `int \| None` | Int members stay 64-bit, including inferred bool/int joins and mixed int/float/bool/str container displays. |
| Unsupported list items, dict keys/values and set elements | Int storage promotes only in the supported integer and tuple forms above. An `int \| None` inside a list or tuple remains 64-bit, including nested tuple items. |
| Optional tuple results | Dict `get()`/`pop()` results that may be `None`, such as `d.get(k)` for tuple values, retain the 64-bit tuple boundary. |
| Runtime-length tuples | `tuple[int, ...]` items, including a tuple sliced by a variable, stay 64-bit. |
| Optional NamedTuple operations | Hashing and argument unpacking of a NamedTuple that may be `None`, such as a parameter's, use the 64-bit tuple-or-None representation. Comparison, tuple search and `%` formatting test it for `None` first and keep its promoting ints. |
| `dataclasses.astuple()` | Has the same optional-tuple boundary. |
| Generator input | Values passed to `send()` stay 64-bit; yielded and returned ints can promote. |

`dataclasses.asdict()` preserves promoting scalar and fixed-tuple fields when
they share a supported dictionary value type. Heterogeneous fields needing a
closed union with a promoting int are rejected at compile time, even if the
particular integer fits in 64 bits. Dynamic `Any` containers can hold large ints;
these closed-union limits do not apply to them.

### Calls, reads and conversions

| Boundary | Where narrowing still occurs |
|---|---|
| Fixed-width function parameters | An `int` or `int \| None` annotation in a module without the opt-in, including comparison methods and wrapped `Callable`s. Unannotated parameters can specialize for a promoting argument. |
| Nested `Callable` types | Ints inside types other than scalar `int`/`int \| None`, such as a tuple parameter or result. |
| Container/generator reads in fixed-width modules | Ordinary list, dict, set and generator reads, including tuple-contained ints; examples include `random.shuffle()` and generic functions. The iterator/library exceptions above still apply. |
| Library and builtin inputs | `range()`, indexes, slices and integer-taking methods/math/library calls outside the supported APIs above; list ints consumed by `tuple()`, `math.prod()`, `math.fsum()` and FFI. |
| Mixed numeric `sum()` | Ints in an `int \| float` list, ints added to a float start, or a large integer start with float items. |
| Tuple consumers | `sum()`, `min()`, `max()`, `any()`, `all()`, `sorted()` and `list()` use the corresponding list-item representation and its limits. |
| Fixed-width `Any` unboxing | Assigning to an explicit fixed-width `int` or `int \| None` in a module without the opt-in. Passing the value through `Any` itself preserves it. |
| Some non-integer container searches | Searching `list[float]` can narrow even when a float equals the large int. Fixed-tuple, generator and iterator searches compare items individually and can compare large ints with floats exactly. |

Membership searches compare full integer values in supported integer lists,
dictionaries, sets, fixed tuples, generators and iterator objects. A large
integer is absent from a `range`, whose bounds remain 64-bit. An object's
`__contains__` follows its parameter's integer policy.

## Deviations

| Case | Difference from CPython |
|---|---|
| [64-bit boundaries](#64-bit-boundaries) | Oversized values raise `OverflowError`; unsupported heterogeneous dataclass fields can be rejected at compile time. |
| Integer identity | Direct `is` between typed ints is rejected in an opted-in module; CPython's result depends on its small-int cache. `x is None` and `x is not None` remain false and true for an int. |
| Tuple identity at the minimum int64 value | A fixed-width tuple containing `-2**63`, even nested, is copied when converting to a promoting tuple layout. This includes storing it in an integer-tuple list, dict or set from any module. Equality is preserved, but identity differs. |
| Negative integer exponent | Two-argument integer power raises `ValueError` instead of returning a float. |
| Bool-to-int storage and calls | The [boolean rules](#booleans) reject cases that would erase an observable bool. |

Other fitting fixed-width tuples retain their identity. Promoting tuples whose
values all fit also retain identity when passed into fixed-width storage.

## Representation

These details describe compiler/runtime storage. Programs use ordinary `int`
annotations and the opt-in comment.

### Scalars and inline paths

A scalar is an LLVM `{i64, ptr}`, held in registers as two words:

| Value | Integer word | Pointer word |
|---|---|---|
| Fits in signed 64 bits | The value | Null |
| Outside signed 64 bits | Zero | Immutable `Mpz` digits from the [`mpz` C core](mpz.md#implementation), using 30-bit digits |

Every fitting result demotes, so the representation is canonical. The collector
sees ordinary pointers through variables, fields and closure cells; the small
integer word is not used as a pointer.

For `+`, the compiler checks both pointers, performs checked 64-bit addition,
and calls `pys_big_op` only for overflow or an already large operand. Subtraction,
multiplication, bitwise operations, remainder, right shift, floor division except
by `-1`, and left shifts by 0–63 that lose no bits also have inline paths.
Power always calls the runtime. Large operations read a small operand from the
stack without allocating it; comparisons, truth and conversions use similar paths.

Some operations prove a small result: remainder by a fitting divisor, right shift
of a fitting value, and a mask with a fitting nonnegative operand. LLVM can then
fold later pointer tests and use the mask's range. Loops such as
`h = (h * 31 + c) & 0xFFFFFFFF` can carry their values as one 64-bit word.
[Lean proofs](../tools/lean_boundary/INT.md) cover these claims and the inline
paths' fit rules, and `make check-lean-int` checks every such claim of the test
programs that opt in.

The [Lean storage checker](../tools/lean_boundary/STORAGE.md) checks low-word uses,
tuple digit-slot guards and fixed-width tuple boundaries, including programs
that import an opted-in module. Run it with `make check-lean-storage`.

### Tuples and runtime traversal

A tuple keeps each fitting int in its 8-byte item slot. A large item uses
`-2**63` as a sentinel and places its pointer in trailing slot `n + i` for item
`i` of an `n`-item tuple. The actual value `-2**63` has a null trailing pointer.
Code reads that pointer only after seeing the sentinel.

This permits sharing most fixed-width tuples with promoting code. A fixed-width
tuple containing the sentinel needs a copy to provide the trailing slots, causing
the identity deviation above. Conversion back checks that no large items remain.

The runtime descriptor `J` carries the slot and pointer through printing,
equality, ordering and hashing. Descriptor walks cover tuples containing ints,
floats, bools, strings, None, and nested tuples/lists/dicts of those types. Other
tuple shapes, or ordering comparisons of different types/lengths, use compiled
item reads.

Containers of integer tuples use this layout recursively (`bigints.held`). Every
store and lookup prepares the same layout, including stores from fixed-width
modules. Dict `items()` and `popitem()` transfer key/value pointers into their
result tuples; `pys_dict_update_pairs_big` reads them back when constructing or
updating a dict. Descriptors preserve large values in runtime searches and sorts
regardless of the calling module; an ordinary fixed-width read still checks them.

### Container companions

Primary integer slots stay 8 bytes. A separately allocated companion holds digit
pointers and is scanned by the collector. Copies, moves, rebuilds and removals
must keep it aligned with the primary storage.

Digit-pointer companions are allocated when the first large value is stored.
Numeric identity tracking can create a list identity companion separately.

| Container | Layout |
|---|---|
| Integer list | A large item uses sentinel `-2**63` and a pointer in the companion array. Other companion entries are null. The header remains 32 bytes. Observing numeric identity changes the digits-only companion into `Any` boxes whose wide values own the digits. |
| Dict values | `dbig` supplies a per-entry pointer for values whose primary slot is `-2**63`; writes clear or replace the companion entry. Rebuilds, copies and updates carry it with the value. |
| Dict keys | `Dict.kb`/`kbig` supplies the pointer for a large key with sentinel `-2**63`. Lookup compares digits only on the large-key path. |
| Set elements | `Set.kb`/`sbig` has one pointer per table slot. A large value uses sentinel `-2**63`, or `-2**63 + 1` when its hash collides with the minimum int64 value's hash (`-4`). |

List/dict reads check for the sentinel before loading the pointer. Set reads test
for a slot at or below `-2**63 + 1`. Fixed-width readers raise on a non-null digit
pointer. Sorting an integer list orders its small items normally and places large
items before or after them by value.

Ordinary integer dicts mix a large value's CPython hash with their integer-key
hash function. The sentinel `-2**63` cannot have the same hash as a large key,
so fixed-width lookup cannot mistake a large key's stored sentinel for that
integer. Dynamic-`Any` dicts use CPython hashes directly; a large key can share
the minimum int64 value's hash (`-4`), so fitting-key lookup explicitly skips
large-key entries before comparing stored words. The alternate set sentinel
provides the corresponding collision protection for set lookups.

### Generators and optional ints

A generator's yielded and returned values each gain a pointer word when any
module opts in. Every integer yield writes that word, including a null pointer
from fixed-width code. Promoting readers load both words; fixed-width readers
reject a non-null pointer.

An `int | None` is null for None, otherwise a pointer to a two-word box. Fitting
ints use their value and a null digit pointer; large ints use sentinel `-2**63`
and a scanned pointer. Fixed-width boxes already have the null second word, so
conversions can share them after the appropriate range check. Comparisons,
formatting, hashing, truth, `min()`/`max()` and range membership use the promoting
value when the optional type is promoting.

### Inference retries

An ordinary function whose unannotated local widens from int64 to a promoting
int can retry its own body once, including for a `Callable` or generic-class
result in a fixed-width module. This follows the
[local-join rules](language/typing.md#inferred-unions) and avoids reloading
unrelated code.

Other pending joins, captured locals, generators, recursive return inference and
new dependencies retain whole-program retries. Dynamic `Any` programs also retain
that retry and its dispatcher/identity state. Retrying changes neither the
module's integer policy nor an annotated boundary. The
[integer retry](../tools/test_python_int_retry.py) and
[local-join retry](../tools/test_local_join_retry.py) tests check pass counts.

## Measurements

These are historical microbenchmarks, not results for every application or the
current compiler. The main run used AOT binaries on 2026-10-26, a shared 4-vCPU
Xeon VM, CPython 3.13.16, and medians of five samples pinned to one CPU. Every
variant matched CPython's checksum. Startup and compilation are excluded;
parentheses show speed relative to CPython.

| Workload | CPython | Promoting `int` | `mpz` | Checked int64 |
|---|---:|---:|---:|---:|
| `lcg32` | 0.750 s | 0.005 s (151×) | – | 0.005 s (152×) |
| `collatz` | 0.807 s | 0.033 s (24.6×) | – | 0.045 s (18.1×) |
| `cross64` | 0.514 s | 0.174 s (2.96×) | 0.419 s (1.23×) | – |
| `arith128` | 0.893 s | 0.682 s (1.31×) | 0.735 s (1.21×) | – |
| `factorial` | 0.628 s | 0.657 s (0.96×) | 0.666 s (0.94×) | – |
| `fibadd` | 0.961 s | 1.163 s (0.83×) | 1.112 s (0.86×) | – |
| `bigmul` | 0.673 s | 0.682 s (0.99×) | 0.692 s (0.97×) | – |
| `dectext` | 0.767 s | 0.719 s (1.07×) | 0.789 s (0.97×) | – |

The masked `lcg32` loop matched checked-int64 speed. `collatz` was faster than its
checked-int64 build in each sample, but the reason was not traced. Before inline
paths, both were 3.6–3.7× slower than checked int64. `cross64`, which repeatedly
crosses the limit, was 2.4× faster than allocating an `mpz` for every value.

Large-value workloads ranged from 0.83–1.31× CPython's speed; `mpz` ranged from
0.86–1.21×. The stack representation of small operands avoids allocations in
workloads such as `arith128`. Ratios on this shared VM varied by up to 0.15
between runs. Promoting-int peak RSS was 34–37 MiB on large-value workloads,
similar to `mpz`, and 2 MiB on `lcg32` and `collatz`.

Separate runs used the same sampling settings:

| Workload and date | CPython | Promoting `int` | `mpz` | Evidence |
|---|---:|---:|---:|---|
| `modpow`, 2026-10-26 | 0.850 s | 0.865 s (0.98×) | 1.017 s (0.84×) | [Raw results](../bench/integers/results/linux-x86_64-2026-10-26-python-int-modpow.json) |
| `containers`, 2026-10-27 | 0.462 s | 0.248 s (1.86×) | 0.648 s (0.71×) | [Raw results](../bench/integers/results/linux-x86_64-2026-10-27-python-int-containers.json) |

The container run used CPython 3.13.17 and the same kind of VM. Peak RSS was
55 MiB for CPython, 57 MiB for promoting ints and 99 MiB for `mpz`.

See the [benchmark workloads and reproduction commands](../bench/integers/README.md),
the [main raw samples](../bench/integers/results/linux-x86_64-2026-10-26-python-int-fast-paths.json),
and the [earlier run without inline paths](../bench/integers/results/linux-x86_64-2026-10-26-python-int.json).
Use the runner's `--python-int` option to include this representation.

## Tests

After building the compiler, run the focused differential cases in native and
hosted modes:

```sh
make test FILES="tests/programs/numbers/python_int_*.py"
make test-py FILES="tests/programs/numbers/python_int_*.py"
```

The [numbers corpus](../tests/programs/numbers/) contains the full `python_int_*`
test family. Use these entry points for specific contracts:

| Contract | Tests and provenance |
|---|---|
| Arithmetic, boundaries, conversions and formatting | [Arithmetic](../tests/programs/numbers/python_int_arith.py), [bounds](../tests/programs/numbers/python_int_bounds.py), [true division](../tests/programs/numbers/python_int_truediv.py), [builtins](../tests/programs/numbers/python_int_builtins.py), [CPython adaptations](../tests/upstream/python-int.md) |
| Containers, comparisons and hashing | [Lists](../tests/programs/numbers/python_int_lists.py), [dict values](../tests/programs/numbers/python_int_dicts.py), [dict keys](../tests/programs/numbers/python_int_dict_keys.py), [tuple keys](../tests/programs/numbers/python_int_tuple_keys.py), [sets](../tests/programs/numbers/python_int_sets.py), [collisions](../tests/programs/numbers/python_int_hash_collisions.py) |
| Calls, classes, libraries and module boundaries | [Calls](../tests/programs/numbers/python_int_calls.py), [callables](../tests/programs/numbers/python_int_callables.py), [generics](../tests/programs/numbers/python_int_generics.py), [library generics](../tests/programs/numbers/python_int_generic_lib.py), [helper modules](../tests/python_int_modules/) |
| Iteration and suspended values | [Generators](../tests/programs/numbers/python_int_generators.py), [iterators](../tests/programs/numbers/python_int_iterators.py), [heapq](../tests/programs/numbers/python_int_heapq.py), [Counter](../tests/programs/numbers/python_int_counter.py) |
| Optional values, bool rules and rejected forms | [Optionals](../tests/programs/numbers/python_int_optional.py), [bool parameters](../tests/programs/numbers/python_int_bool_args.py), [documented deviations](../tests/deviations/python_int_limits.py), [numeric rejections](../tests/errors/numbers/) |
| GC and compiler state | [GC roots](../tests/programs/numbers/python_int_roots.py), [per-file opt-in state](../tools/test_compiler_state_files.py), [retry counts](../tools/test_python_int_retry.py) |
| Upstream integer behavior | [36 MicroPython tests and exclusions](../tests/upstream/micropython.md), unchanged apart from the opt-in header |

`make python-int-gate` applies the opt-in to every `tests/programs` case and
compares JIT and AOT output with fresh pinned-CPython recordings. The reviewed
manifest permits only exact compiler rejections linked to known limitations.
Crashes, runtime errors, changed output or diagnostics, and obsolete exceptions
fail. Full verification uses three disjoint shards; PR verification uses a
deterministic sample in its `opt-in` worker. The report gate checks the selected
cases, both modes and compiler identity. See the
[gate contract](testing.md#make-verify) and
[baseline review](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/python-int-compatibility-2026-10-28.md).
Passing establishes the supported experimental surface, not compatibility for
programs the manifest still rejects.

`make python-int-optin` is the exploratory sweep and can compare an earlier
report. Its report is not CI evidence. `tools/test_python_int*.py` and the
verification aggregation tests exercise the gate's negative controls.
