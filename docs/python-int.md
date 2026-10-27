# Promoting ints (prototype)

Promoting ints are experimental. To enable them, put this comment before any code in a module:

```python
# pystachy: python-int
```

In that module, `int` behaves as CPython's: a result that needs more than 64 bits becomes a
bigger int instead of raising `OverflowError`, and a result that fits is a 64-bit value again.
Modules without the comment, including the compiler, `runtime.py` and `lib/`, keep the checked
64-bit `int` of the [language guide](language.md). The roadmap is #907; this page describes its
step 3, the compiler-level integer, and the first parts of step 6: tuples, lists, dicts and
generators. Values past 64 bits stay in variables, arguments, returns, fields, module variables,
closures, tuples, lists of ints, the values of dicts of ints and the values generators yield and
return; dict keys, sets and the other containers still hold 64-bit ints
([boundaries](#64-bit-boundaries)).

```python
# pystachy: python-int
def fact(n: int) -> int:
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


print(fact(25))                  # 15511210043330985984000000
print(fact(25) // fact(23))      # 600, a 64-bit int again
print(2 ** 100 > 1e30, hash(2 ** 64))  # True 8
print(int("123456789012345678901234567890") % 97)  # 52
```

## What a module that opts in gets

- `int` in an annotation of the module (a parameter, a return, a local, a field, a module
  variable) is a promoting int, and so is a location without an annotation that receives one:
  the function is compiled again with it promoting, as a [join](language/typing.md) widens
  other types. A literal that fits is a 64-bit int until it meets one.
- A `bool` stays a `bool`, as in a module that does not opt in: one returned or stored as an
  `int` (a variable, a field, a tuple's item), or given by a conditional expression, `and`, `or`,
  `min()` or `max()` that may give an int is rejected during compilation (CPython keeps the
  `bool`, which prints as `True`), and a location without an annotation that receives both holds
  their union. In arithmetic and comparisons a `bool` is the int it equals.
- A `bool` given to an `int` parameter is the promoting int it equals where the function reads
  the parameter only as a number, so that both give the same results and errors: in arithmetic
  with numbers (literals and the function's `int`, `float` and `bool` parameters; `&`, `|` and
  `^` with an int literal), comparisons with numbers, tests of its truth, and the builtins
  `int()`, `float()`, `abs()`, `round()`, `hash()`, `bool()`, `range()`, `chr()`, `hex()`,
  `oct()` and `bin()`. Elsewhere it is rejected, as in a module that does not opt in: where the
  function may return, store, print, format or pass on the parameter, index with it, test its
  type or identity (`is`, `in`), read it in a nested function, lambda or comprehension, or read
  its locals (`locals()`, `vars()`, `eval()`, `exec()`), and where the program or the function
  binds the name of one of those builtins (in a closure, any call of one). So is one given to a
  function through a `Callable` (a variable or parameter that holds it).
- The operators `+`, `-`, `*`, `//`, `%`, `&`, `|`, `^`, `<<`, `>>`, `**`, unary `-`, `+` and `~`,
  their augmented assignments, `abs()` and `pow(x, y)` compute CPython's result. `%`, `&`, `|`,
  `^` and `>>` of two 64-bit ints never overflow, so they stay 64-bit operations. True division
  (`/`) is CPython's: the quotient rounded once to the nearest float (halfway cases to even),
  `OverflowError` past the float range.
- Comparisons are exact, also between an int and a float (`2 ** 53 + 1 > 9007199254740992.0`),
  as are truth, `min()` and `max()`, `isinstance(x, int)` and equality with a `str`, `bytes` or
  container, which is never true.
- `sum()` of ints adds past 64 bits, from an int start, of lists, tuples, sets, dict keys,
  ranges, generators, iterators and `map()`: `sum(i * i for i in range(n))` is exact.
- Integer literals may be past 64 bits, in any base. `int()` parses text (bases 0 and 2–36,
  underscores, signs, Unicode digits and whitespace, as CPython does) and converts floats; `str()`,
  `repr()`, `float()` (correctly rounded, `OverflowError` past the float range), `hash()`
  (CPython's), `bool()`, `round(x)`, `bin()`, `hex()`, `oct()`, `x.bit_length()`,
  `x.bit_count()` and `pow(x, y, m)` (with a negative `y`, the inverse's power) take every value,
  and so do f-strings, `format()` and `%` formatting with every int specification (a float type
  converts the value to a float, as CPython does).
- Tuples hold promoting ints. A function annotated `-> tuple[int, int, int]` returns
  `g, x, y` past 64 bits, and unpacking, indexing (by a variable too), slicing by literals, `+`,
  `*` by a literal, iteration, `in`, `index()` and `count()` take them, as do comparisons (also
  with tuples of 64-bit ints, bools and floats, exactly), `hash()` (CPython's), `repr()`,
  f-strings, `format()` and `%` formatting. `divmod()` returns a tuple of promoting ints.
- A `list[int]` holds promoting ints, in a program where a module opts in and none opts in to
  [dynamic `Any`](dynamic-any.md): displays, comprehensions, `append()`, `insert()`, item and
  slice assignment, `extend()` and `+=` store values past 64 bits, and in a module that opts in,
  indexing, iteration, unpacking and `pop()` read them. `in`, `index()`, `count()` and
  `remove()` compare exactly (also with floats), and so do `==`, `<` and the other comparisons;
  `sort()`, `sorted()` (by key too), `min()`, `max()`, `sum()`, `repr()`, copies, slices, `+`,
  `*` and `reverse()` take every item.
- The values of a dict of ints are promoting ints, in a program where a module opts in and none
  opts in to [dynamic `Any`](dynamic-any.md), as a list's items are: item assignment, `+=`,
  displays, comprehensions, `setdefault()`, `update()`, `dict()` and `copy()` store values past
  64 bits, and in a module that opts in, indexing, `get()`, `pop()`, `setdefault()` and iteration
  over `values()` and `items()` read them. `values()` makes a list of ints that holds them, and
  `repr()`, `==` and `!=` take them. A memo table (`memo[n] = fib(n - 1) + fib(n - 2)`) is exact.
- A generator yields and returns promoting ints, in a program where a module opts in: a `for`
  loop, a comprehension, `next()`, unpacking, `send()` and `throw()` in a module that opts in read
  them, and so do `list()`, `sorted()`, `sum()`, `min()`, `max()`, `in`, `enumerate()`, `zip()`
  and the other consumers of a generator; `yield from` passes them on, and its value is the
  promoting int its generator returns (`Generator[int, None, int]`).
- A 64-bit int from a container, a module that does not opt in or a builtin promotes when an
  operation on it overflows: `xs[0] * xs[1]` of a `list[int]` is exact.
- An object's `__len__` and `__hash__` may return a promoting int, annotated `-> int` or not.
  `len()` and truth take it as CPython does: a negative one, however large, is a `ValueError`,
  and a positive one past 64 bits an `OverflowError` (`cannot fit 'int' into an index-sized
  integer`). `hash()`, dicts and sets take one past 64 bits as the hash of that int.

Errors are CPython's: `ZeroDivisionError` for `//` and `%` by zero, `ValueError` for a negative
shift count, `MemoryError` for a shift or power whose result could not fit in memory. As in
64-bit modules, `int ** negative int` is a `ValueError` (CPython returns a float).

## Representation

A promoting int is two words, an LLVM `{i64, ptr}` held in registers like two scalars. Where the
value fits in 64 bits, the pointer is null and the first word is the value; otherwise the pointer
is the value's immutable digits, the `Mpz` of [`mpz`](mpz.md)'s C core (30-bit digits), and the
first word is 0. Every result that fits is demoted, so a value has one representation: two
values that fit are equal exactly when their first words are.

An operation on two values that fit runs inline: `x + y` tests that both pointers are null, adds
with an overflow check and branches to `pys_big_op` (`runtime.c`) only when a pointer is set or
the addition overflows. `-`, `*`, `&`, `|`, `^`, `%`, `>>`, `//` (but by -1) and `<<` (by 0 to
63, losing no bits) have inline paths too; `**` always calls the runtime. The runtime computes
the exact result and demotes it where it fits; a 64-bit operand of a big operation is read from
the stack, not allocated. Comparisons, truth and conversions take the same two paths.

Some results fit whatever the operands: `x % y` where `y` fits (`|r| < |y|`), `x >> y` where `x`
fits, and `x & y` where one operand fits and is not negative (`0 <= r <=` it). Their pointer is
null on both paths where that holds, and a masked result's word is masked on both, so LLVM folds
the pointer tests of later operations on them wherever the operand is a constant or already known
to fit, and sees the mask's range. A loop that masks or reduces its values
(`h = (h * 31 + c) & 0xFFFFFFFF`, `x % m`) carries them as one 64-bit word.

The pointer is an ordinary pointer or null, so the conservative collector sees a big value's
digits through any variable, field or closure cell that holds it, and never mistakes a small int
for a pointer. The design and its measurements are on #907.

A tuple holds a promoting int item that fits in the item's 8-byte slot, as a tuple of 64-bit ints
holds it. An item past 64 bits holds -2\*\*63 there, and its pointer in a slot after the items
(item `i` of `n` in slot `n + i`); -2\*\*63 itself holds -2\*\*63 and a null pointer. Code reads
that pointer only where the item's slot holds -2\*\*63. So a tuple of 64-bit ints is a tuple of
promoting ints as it is, unless it holds -2\*\*63 (a test finds it, and makes a copy); and a tuple
of promoting ints that fit is the tuple of their 64-bit ints: where 64-bit storage takes it (a
list's item, a dict's key, a parameter of a module that does not opt in), it is the same tuple,
once a test has found no item past 64 bits. The runtime reads tuples of 64-bit ints alone, as it reaches them so,
and the code compiled for `repr()`, comparisons and `hash()` of a tuple of promoting ints reads
its items one by one.

A list of ints holds an item that fits in its 8-byte slot, as a list of 64-bit ints holds it. An
item past 64 bits holds -2\*\*63 there, and its pointer in a companion array beside the items,
which the collector scans and the first such item makes: the list's identity companion of
[dynamic `Any`](dynamic-any.md), of a kind of its own. Its other entries are null, -2\*\*63's
among them, so every list operation of `runtime.c` that moves, copies or drops items keeps the
companion in step as it is. A read of a list's int compares its slot with -2\*\*63 and reads the
pointer only where they are equal; that is the cost a read pays in every module of a program
that opts in. Code of a module that does not opt in reads the item as a 64-bit int and raises
`OverflowError` past 64 bits, and so do the runtime functions that take a list's ints as 64-bit
ints ([boundaries](#64-bit-boundaries)). `runtime.c`'s sorting compares a list that holds an item
past 64 bits through the ranks of its items, 64-bit ints in their order.

A dict of ints holds a value that fits in its 8-byte slot, as before, and one past 64 bits as
-2\*\*63 there, with its pointer in a companion array beside the entries, which the collector
scans and the first such value makes (`runtime.c`'s `dbig`). Every store of a value clears its
entry's word, and the dict's rebuilds, copies and `update()` carry the words with the entries. A
read of a value compares its slot with -2\*\*63 and reads the pointer only where they are equal,
as a list's read does, by the entry it found: a module that opts in gets the promoting int, other
code the 64-bit int, with `OverflowError` past 64 bits.

A generator's promise, the words where it leaves the value it yielded last and the one it
returned, holds an int in one word, as before, and in a program where a module opts in, its
pointer in a word of its own: null where the value fits, as every `yield` of an int writes it,
also in a module that does not opt in. Code of a module that opts in reads both words, and
other code raises `OverflowError` for a pointer.

An `int | None` is a pointer to a box, as one of a 64-bit int is: null for None, else runtime.c's
box of the value and a null pointer where it fits, and past 64 bits a box of -2\*\*63 and the
value's pointer, which the collector scans. Every box of a 64-bit int has that null second word,
so an `int | None` from 64-bit code (a dict's `get()`, a module that does not opt in) is one of a
promoting int as it is; and one whose value fits is the box that 64-bit code reads, where it
takes it once a test has found no pointer there. Comparisons, `min()`, `max()`, `str()`, `repr()`,
formatting, `hash()`, truth and membership in a `range` of an `int | None` are compiled for its
promoting int, and so are the status of a `SystemExit` and the `errno` that names an `OSError`'s
class, of it or of a promoting int (past 64 bits, -1 and none, as CPython's).

## 64-bit boundaries

These places keep 64-bit ints for now. A value past 64 bits that reaches one raises
`OverflowError: Python int too large to convert to C long` (CPython's message for an int too big
for a C `long`), where CPython goes on with the bigger int:

- The keys of dicts, the elements of sets, the items of lists of other types than `int` (a tuple
  or an `int | None` in a list holds 64-bit ints too), the values of dicts of other types than
  `int` and the tuples that `items()` and `popitem()` make of a dict of ints, the items and values
  of lists and dicts of ints in a program that opts in to dynamic `Any`, a tuple's `int | None`
  items, unions other than `int | None` (also where a join makes one, as
  for a location given a `bool` and an int), the items of a `tuple[int, ...]` (a tuple sliced by
  a variable), and the values sent to a generator (`send()`)
  (`tests/deviations/python_int_limits.py`). A NamedTuple that may be None, such as a parameter,
  is hashed, compared, searched, formatted with `%` and unpacked into arguments as the tuple of
  its fields or None, which holds 64-bit ints too.
- An `int` or `int | None` parameter of a function in a module that does not opt in (whose
  unannotated parameters take the promoting int, so arithmetic there promotes too), and the
  parameters and result of a `Callable`.
- A list's int, a dict's value or a generator's value read in a module that does not opt in, such
  as `lib/`'s `heapq`, `bisect`, `random.shuffle()` and `collections`' `defaultdict` and
  `Counter`, and the ints of a list given to `tuple()`, `set()` and the set operations,
  `dict.fromkeys()`, `math.prod()`, `math.fsum()`, `sum()` with a float start and `ffi`. Of a
  dict of ints that holds a value past 64 bits, `pop()` with a key that may be None, and `pop()`
  of a bool key without a default, read its values as 64-bit ints, and so raise for any such value.
- Builtins and methods that take an int: `range()`, indexing and slicing, the other `int`
  methods, `math` functions and other library calls. `sum()` takes 64-bit ints where they meet
  floats: the ints of an `int | float` list, ints added to a float start, and a start past 64
  bits with float items. `sum()`, `min()`, `max()`, `any()`, `all()`, `sorted()` and `list()` of
  a tuple take its items as a list holds them.
- [Dynamic `Any`](dynamic-any.md) values, which another module that opts in to them may pass or
  take: a promoting int becomes one as a 64-bit int, and comparing a promoting int with one is
  rejected during compilation for now.
- `x in c` where the items of `c` are not ints (a `list[float]` may hold a float equal to an int
  past 64 bits), and a tuple of promoting ints looked up in a list or as a key. Membership in a
  list of ints is exact; in another container of ints, a `range`, a generator or an iterator
  object too: an int past 64 bits is not in it. An object's `__contains__` takes `x` as its
  parameter does.

## Deviations

- A value past 64 bits at a [64-bit boundary](#64-bit-boundaries) raises `OverflowError`
  (`tests/deviations/python_int_limits.py`).
- `is` between two ints is rejected during compilation in a module that opts in
  (`tests/errors/numbers/python_int_is.py`): CPython's result depends on its small-int cache.
  `x is None` and `x is not None` of an int are `False` and `True`.
- A module cannot opt in to both promoting ints and [dynamic `Any`](dynamic-any.md) yet
  (`tests/errors/numbers/python_int_dynamic_any.py`).
- A tuple of 64-bit ints that holds -2\*\*63, also in a tuple it holds (from a container, a
  builtin or a module that does not opt in), becomes a new tuple where a tuple of promoting ints
  is expected: `is` tells the two apart, where CPython has one object
  (`tests/deviations/python_int_limits.py`). Other tuples of 64-bit ints stay the same tuple, and
  so do tuples of promoting ints going into 64-bit storage.

## Measurements

Measured on 2026-10-26 with [`bench/integers`](../bench/integers/README.md) (`--python-int`, AOT
binaries, medians of five samples pinned to one CPU) on the shared 4-vCPU Xeon VM of its
results, with the inline paths above; every variant printed CPython's checksum. Seconds, and
speed relative to CPython 3.13.16:

| Workload | CPython | promoting `int` | `mpz` | checked int64 |
|---|---:|---:|---:|---:|
| `lcg32` | 0.750 s | 0.005 s (151×) | – | 0.005 s (152×) |
| `collatz` | 0.807 s | 0.033 s (24.6×) | – | 0.045 s (18.1×) |
| `cross64` | 0.514 s | 0.174 s (2.96×) | 0.419 s (1.23×) | – |
| `arith128` | 0.893 s | 0.682 s (1.31×) | 0.735 s (1.21×) | – |
| `factorial` | 0.628 s | 0.657 s (0.96×) | 0.666 s (0.94×) | – |
| `fibadd` | 0.961 s | 1.163 s (0.83×) | 1.112 s (0.86×) | – |
| `bigmul` | 0.673 s | 0.682 s (0.99×) | 0.692 s (0.97×) | – |
| `dectext` | 0.767 s | 0.719 s (1.07×) | 0.789 s (0.97×) | – |

- **Values that fit.** `lcg32` and `collatz` never leave 64 bits. `lcg32` masks its values, so
  they are proven to fit and run as fast as checked int64. `collatz` ran faster than its
  checked-int64 build, which differs only in the comment (0.033 s against 0.045 s in every
  sample, a difference not traced yet). Before the inline paths, both ran 3.6–3.7× slower than
  checked int64.
- **Values crossing 2^63.** `cross64`'s values leave 64 bits and come back. Those that fit stay
  inline: 2.4× faster than `mpz`, which allocates every value.
- **Big values.** Within 0.83–1.31× of CPython, as `mpz` is (0.86–1.21×). A 64-bit operand of a
  big operation is read from the stack, not allocated, so `arith128` keeps up with the `mpz`
  program, which keeps its constants as `mpz` values. On this VM a workload's ratio moves by up
  to 0.15 between runs.
- `modpow` runs since three-argument `pow` takes every value: 0.865 s, 0.98× CPython's 0.850 s,
  where `mpz` takes 1.017 s (0.84×), measured separately with the same settings
  ([`results/linux-x86_64-2026-10-26-python-int-modpow.json`](../bench/integers/results/linux-x86_64-2026-10-26-python-int-modpow.json)).
- `containers` runs since lists hold promoting ints: 0.248 s, 1.86× the 0.462 s of CPython
  3.13.17 (the container's own, not the pinned 3.13.16), where `mpz` takes 0.648 s (0.71×),
  with 57, 55 and 99 MiB peak RSS, measured on 2026-10-27 with the same settings on the same
  kind of VM
  ([`results/linux-x86_64-2026-10-27-python-int-containers.json`](../bench/integers/results/linux-x86_64-2026-10-27-python-int-containers.json)).
  `runtime.c` sorts its list's 64-bit items as before and puts the items past 64 bits,
  compared as such, before and after them.

Peak RSS is `mpz`'s on every big workload (34–37 MiB) and 2 MiB on `lcg32` and `collatz`. Raw
samples are in
[`results/linux-x86_64-2026-10-26-python-int-fast-paths.json`](../bench/integers/results/linux-x86_64-2026-10-26-python-int-fast-paths.json);
the first measurements, before the inline paths, in
[`results/linux-x86_64-2026-10-26-python-int.json`](../bench/integers/results/linux-x86_64-2026-10-26-python-int.json).

## Tests

- `tests/programs/numbers/python_int_arith.py`: every operator on operands around the 64-bit
  edges, demotion, augmented assignment and mixed `bool` operands.
- `tests/programs/numbers/python_int_compare.py`: comparisons with ints, bools and floats,
  `isinstance`, `and`/`or`, membership (also in objects, iterators, generators and NamedTuples)
  and `int` methods.
- `tests/programs/numbers/python_int_text.py`: literals, `int()` of text and floats, `float()`,
  `str()`, `hash()` and their errors.
- `tests/programs/numbers/python_int_calls.py`: functions, defaults, keyword arguments, methods,
  fields, globals, closures, lambdas and modules with and without the comment
  (`tests/python_int_modules/`).
- `tests/programs/numbers/python_int_bounds.py`: the inline paths of `//`, `%`, `<<` and `>>` at
  their edges, results that always fit, and shifts past memory.
- `tests/programs/numbers/python_int_builtins.py`: `bit_length()`, `bit_count()`, `bin()`, `hex()`,
  `oct()`, format specifications, `%` formatting and `pow(x, y, m)`.
- `tests/programs/numbers/python_int_sums.py`: `sum()`, `min()` and `max()` of every iterable and
  start.
- `tests/programs/numbers/python_int_cpython_int.py` and `python_int_cpython_long.py`: `int()`
  and arithmetic assertions adapted from CPython's `Lib/test/test_int.py` and
  `Lib/test/test_long.py` ([provenance](../tests/upstream/python-int.md));
  `python_int_import.py`: a module without the comment that calls one with it; and
  `python_int_reflection.py`: `type()` and `__class__` of promoting and 64-bit ints.
- `tests/programs/numbers/python_int_truediv.py`: true division across the float range, halfway
  cases, subnormals, signed zeros and its errors.
- `tests/programs/numbers/python_int_storage.py`: values that fit in containers and unions that
  annotations name, displays, dataclass and NamedTuple fields, and `type()`.
- `tests/programs/numbers/python_int_lists.py`: lists of ints past 64 bits: stores, reads,
  searches by promoting ints and floats, sorting, `min()`, `max()`, `sum()`, comparisons, copies,
  nested lists, a field and a function's result.
- `tests/programs/numbers/python_int_dicts.py`: dicts of ints whose values are past 64 bits: a memo
  table, stores, `get()`, `pop()`, `setdefault()`, `+=`, displays, comprehensions, copies,
  `update()`, iteration, `values()`, comparisons, nested dicts, a field and bool keys;
  `python_int_dicts_nested.py`: `get()` calls nested 40 deep, in defaults and in keys, which each
  decide on their arguments' types once; `python_int_repr_limit.py`: `repr()` of lists and dicts
  whose int has more than 4,300 digits raises CPython's `ValueError`, which `try` catches.
- `tests/programs/numbers/python_int_recursion.py`: recursive functions and methods, one with a
  `dict[int, int]` memo; `python_int_forward_ref.py`: quoted annotations that name promoting ints
  ([provenance](../tests/upstream/python-int.md)).
- `tests/programs/numbers/python_int_generators.py`: generators that yield and return ints past 64
  bits, through `for` loops, `next()`, unpacking, `yield from`, `send()`, `throw()`, generator
  expressions, a method and a module that does not opt in (`tests/python_int_modules/fixed_iter.py`).
- `tests/programs/numbers/python_int_joins.py`: values that fit where a conditional expression,
  `or`, `and` or a call of overriding methods joins a promoting int with `None` or a `str`.
- `tests/programs/numbers/python_int_bools.py`: locations given a `bool` and an int, and bools in
  arithmetic, comparisons and builtins; `tests/programs/numbers/python_int_bool_args.py`: bools
  given to `int` parameters (by position, keyword and default, of functions, methods, overrides,
  a constructor and a setter) that their functions read only as numbers;
  `tests/errors/numbers/python_int_bool_*.py`: a `bool` where a promoting int is stored, joined
  with one, or given to a parameter that its function may show.
- `tests/programs/numbers/python_int_tuples.py`: tuples of promoting ints: annotated returns,
  unpacking, indexing, slicing, iteration, comparisons with 64-bit tuples, `hash()`, `repr()` and
  formatting, `divmod()`, fields, globals, closures and a NamedTuple, and tuples that fit going
  into a module that does not opt in (`tests/python_int_modules/fixed_pairs.py`).
- `tests/programs/numbers/python_int_optional.py`: `int | None` past 64 bits in variables,
  parameters, returns, defaults, fields, class attributes, globals, closures and joins, in each
  spelling, with comparisons, `min()`, `max()`, membership, formatting, `hash()`, truth and
  narrowing; `python_int_optional_keys.py`: values that fit as a dict's keys, a `pop()` default
  and a set's elements, and in the unions a join makes with a bool or a `str`, membership in
  ranges, an `OSError`'s errno and a `SystemExit`'s status; `python_int_exit.py` and
  `python_int_exit_class.py`: that status in a program without `try` and of a subclass.
- `tests/programs/numbers/python_int_special.py`: `__len__` and `__hash__` results past 64 bits,
  annotated and not, through `len()`, truth, `hash()`, dict keys and set elements.
- `tests/programs/numbers/python_int_spellings.py`: quoted and `Final` annotations, in modules
  that opt in and into one that does not.
- `tests/programs/numbers/python_int_roots.py`: values whose digits only a module variable, a
  class attribute, a field, a closure cell, a default or a generator's frame holds survive
  collections (the test runner's GC stress collects at every allocation).
- `tests/programs/upstream/upstream_micropython_*.py`: 35 of MicroPython's integer tests
  (arithmetic, bitwise operations, shifts, comparisons, `divmod()`, `pow()`, `abs()`, `bin()`,
  `hex()`, `oct()`, constant folding and slices past 64 bits), unchanged after a header that opts
  them in ([provenance and the tests left out](../tests/upstream/micropython.md)).
- `tests/deviations/python_int_limits.py` and the two rejections above.
- `tools/test_compiler_state_files.py`: the opt-in follows its file through imports, restarts and
  later compilations.
