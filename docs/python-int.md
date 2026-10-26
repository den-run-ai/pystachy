# Promoting ints (prototype)

Promoting ints are experimental. To enable them, put this comment before any code in a module:

```python
# pystachy: python-int
```

In that module, `int` behaves as CPython's: a result that needs more than 64 bits becomes a
bigger int instead of raising `OverflowError`, and a result that fits is a 64-bit value again.
Modules without the comment, including the compiler, `runtime.py` and `lib/`, keep the checked
64-bit `int` of the [language guide](language.md). The roadmap is #907; this page describes its
step 3, the compiler-level integer. Values past 64 bits stay in variables, arguments, returns,
fields, module variables and closures; containers still hold 64-bit ints
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
- The operators `+`, `-`, `*`, `//`, `%`, `&`, `|`, `^`, `<<`, `>>`, `**`, unary `-`, `+` and `~`,
  their augmented assignments, `abs()` and `pow(x, y)` compute CPython's result. `%`, `&`, `|`,
  `^` and `>>` of two 64-bit ints never overflow, so they stay 64-bit operations.
- Comparisons are exact, also between an int and a float (`2 ** 53 + 1 > 9007199254740992.0`),
  as are truth, `min()` and `max()` of int arguments, `isinstance(x, int)` and equality with a
  `str`, `bytes` or container, which is never true.
- Integer literals may be past 64 bits, in any base. `int()` parses text (bases 0 and 2–36,
  underscores, signs, Unicode digits and whitespace, as CPython does) and converts floats; `str()`,
  `repr()`, `f"{x}"`, `float()` (correctly rounded, `OverflowError` past the float range), `hash()`
  (CPython's), `bool()` and `round(x)` take every value.
- A 64-bit int from a container, a module that does not opt in or a builtin promotes when an
  operation on it overflows: `xs[0] * xs[1]` of a `list[int]` is exact.

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

## 64-bit boundaries

These places keep 64-bit ints for now. A value past 64 bits that reaches one raises
`OverflowError: Python int too large to convert to C long` (CPython's message for an int too big
for a C `long`), where CPython goes on with the bigger int:

- The items of lists, dicts, sets and tuples, `int | None` and other unions, and the values a
  generator yields or receives (`tests/deviations/python_int_limits.py`).
- An `int` parameter of a function in a module that does not opt in. Its unannotated parameters
  take the promoting int, so arithmetic there promotes too.
- Builtins and methods that take an int: `range()`, indexing and slicing, `bin()`, `hex()`,
  `oct()`, `divmod()`, `pow(x, y, m)`, format specifications (`f"{x:x}"`, `"%d" % x`), `int`
  methods (`x.bit_length()`), `math` functions and other library calls. `sum()` adds 64-bit
  values, and raises `OverflowError` where the sum passes 64 bits.
- [Dynamic `Any`](dynamic-any.md) values, which another module that opts in to them may pass or
  take: a promoting int becomes one as a 64-bit int, and comparing a promoting int with one is
  rejected during compilation for now.
- `x in c` where the items of `c` are not ints (a `list[float]` may hold a float equal to an int
  past 64 bits). Membership in a container of ints or a `range` is exact: an int past 64 bits is
  not in it.

True division (`/`) of two ints that fit gives CPython's correctly rounded float; with an operand
past 64 bits it raises `NotImplementedError`.

## Deviations

- A value past 64 bits at a [64-bit boundary](#64-bit-boundaries) raises `OverflowError`, and
  true division with an operand past 64 bits raises `NotImplementedError`
  (`tests/deviations/python_int_limits.py`).
- `is` between two ints is rejected during compilation in a module that opts in
  (`tests/errors/numbers/python_int_is.py`): CPython's result depends on its small-int cache.
  `x is None` and `x is not None` of an int are `False` and `True`.
- A module cannot opt in to both promoting ints and [dynamic `Any`](dynamic-any.md) yet
  (`tests/errors/numbers/python_int_dynamic_any.py`).

## Measurements

Measured on 2026-10-26 with [`bench/integers`](../bench/integers/README.md) (`--python-int`, AOT
binaries, medians of five samples pinned to one CPU) on the shared 4-vCPU Xeon VM of its
results; every variant printed CPython's checksum. Seconds, and speed relative to CPython
3.13.16:

| Workload | CPython | promoting `int` | `mpz` | checked int64 |
|---|---:|---:|---:|---:|
| `lcg32` | 0.765 s | 0.019 s (40.6×) | – | 0.005 s (150×) |
| `collatz` | 0.890 s | 0.168 s (5.28×) | – | 0.047 s (18.9×) |
| `cross64` | 0.489 s | 0.221 s (2.22×) | 0.557 s (0.88×) | – |
| `arith128` | 0.902 s | 0.864 s (1.04×) | 0.646 s (1.40×) | – |
| `factorial` | 0.528 s | 0.637 s (0.83×) | 0.621 s (0.85×) | – |
| `fibadd` | 0.922 s | 1.101 s (0.84×) | 1.056 s (0.87×) | – |
| `bigmul` | 0.644 s | 0.669 s (0.96×) | 0.682 s (0.94×) | – |
| `dectext` | 0.703 s | 0.810 s (0.87×) | 0.715 s (0.98×) | – |

- **Values that fit.** `lcg32` and `collatz` never leave 64 bits, and the promoting int runs them
  3.6–3.7× slower than checked int64: each operation tests both operands' pointers and keeps
  both words of its result, and nothing proves yet that a masked or bounded value fits. The
  representation proxy measured 1.00–1.02× with such range facts (#907), which come next.
- **Values crossing 2^63.** `cross64`'s values leave 64 bits and come back. Those that fit stay
  inline: 2.5× faster than `mpz` here (1.7× in an earlier run), which allocates every value.
- **Big values.** Within 0.83–1.04× of CPython, as `mpz` is. `arith128` is slower than `mpz`
  because each operation with a 64-bit operand turns it into a fresh `Mpz`, where the `mpz`
  program keeps its constants as `mpz` values. On this VM a workload's ratio moves by up to
  0.15 between runs.
- `modpow` and `containers` do not run yet: their values past 64 bits reach three-argument `pow`
  and containers, which keep 64-bit ints.

Peak RSS is `mpz`'s on every big workload (35–37 MiB) and 2 MiB on `lcg32` and `collatz`. Raw
samples are in
[`results/linux-x86_64-2026-10-26-python-int.json`](../bench/integers/results/linux-x86_64-2026-10-26-python-int.json).

## Tests

- `tests/programs/numbers/python_int_arith.py`: every operator on operands around the 64-bit
  edges, demotion, augmented assignment and mixed `bool` operands.
- `tests/programs/numbers/python_int_compare.py`: comparisons with ints, bools and floats,
  `isinstance`, `and`/`or`, membership and `int` methods.
- `tests/programs/numbers/python_int_text.py`: literals, `int()` of text and floats, `float()`,
  `str()`, `hash()` and their errors.
- `tests/programs/numbers/python_int_calls.py`: functions, defaults, keyword arguments, methods,
  fields, globals, closures, lambdas and modules with and without the comment
  (`tests/python_int_modules/`).
- `tests/programs/numbers/python_int_bounds.py`: the inline paths of `//`, `%`, `<<` and `>>` at
  their edges, results that always fit, and shifts past memory.
- `tests/programs/numbers/python_int_storage.py`: values that fit in containers, tuples and unions
  that annotations name, displays, dataclass and NamedTuple fields, and `type()`.
- `tests/programs/numbers/python_int_spellings.py`: quoted and `Final` annotations, in modules
  that opt in and into one that does not.
- `tests/programs/numbers/python_int_roots.py`: values whose digits only a module variable, a
  class attribute, a field, a closure cell, a default or a generator's frame holds survive
  collections (the test runner's GC stress collects at every allocation).
- `tests/deviations/python_int_limits.py` and the two rejections above.
- `tools/test_compiler_state_files.py`: the opt-in follows its file through imports, restarts and
  later compilations.
