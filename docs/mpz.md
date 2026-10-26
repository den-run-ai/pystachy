# Explicit arbitrary-precision integers

`from mpz import mpz` provides an experimental integer type with packed limbs and
Python-style integer arithmetic. It is an explicit first integration of the
bigint backend: ordinary `int`, integer literals, JSON numbers, range/index
arguments and native integer interfaces retain their checked signed 64-bit
contract. Convert before an operation that needs a wider result.

```python
from mpz import mpz

x = mpz("18446744073709551616")
print(x * x)                       # 340282366920938463463374607431768211456
print((mpz(-7) // mpz(3)))          # -3
print((mpz(-7) % mpz(3)))           # 2
print(mpz(2).pow(128).bit_length()) # 129

values: list[mpz] = [x, x + 1]
counts: dict[mpz, int] = {x: 2}
print(counts[mpz(str(x))])          # 2
```

## Initial API

| Operation | Accepted form |
|---|---|
| Construction | `mpz()`, `mpz(int)`, `mpz(bool)`, `mpz(str, base=10)`; base 0 or 2–36 for strings |
| Arithmetic | `+`, `-`, `*`, `//`, `%`, `&`, `\|`, `^` with an `mpz` left operand and `mpz` or native `int`/`bool` right operand |
| Unary and shifts | `+x`, `-x`, `~x`, `x << count`, `x >> count`; count is a native `int` |
| Methods | `x.copy()`, `x.abs()`, `x.pow(nonnegative_int)`, `x.bit_length()`, `x.to_int()` |
| Comparisons | `==`, `!=`, `<`, `<=`, `>`, `>=` between supported integer operands, with `mpz` on the left |
| Protocols | `str`, `repr`, truth, CPython-compatible 64-bit integer hash; typed lists, dicts and sets |

`//` rounds down and `%` has the divisor's sign. Negative bitwise operations use
infinite two's-complement semantics. Parsing accepts Python-style signs, bases,
prefixes, underscores, Unicode decimal digits and surrounding whitespace.
Decimal output and input in non-power-of-two bases enforce a fixed 4,300-digit
limit; changing CPython's `sys.set_int_max_str_digits` is not mirrored here.
`to_int()` raises `OverflowError` outside signed 64-bit range. Negative shifts
raise `ValueError`; integer division or modulo by zero raises `ZeroDivisionError`.

Use `x.copy()` to construct from an existing `mpz`. The current class protocol
requires `x.pow(n)` and `x.abs()` instead of builtin `pow`/`abs`, and does not
support reflected arithmetic such as `1 + x`. True division, modular power,
negative powers, float conversion, byte conversion, radix formatting, subclasses
and configurable decimal digit limits are not provided. Constructor/operator
argument shapes outside the typed API can be rejected during compilation.

## Implementation

The class is written in Pystachy's subset, with private compiler intrinsics for
an opaque, GC-traced handle. Arithmetic returns immutable values. The C payload
has a signed limb count followed by packed `uint32_t` base-2^30 digits in one
pointer-free allocation. Containers hold class references using their existing
GC-scanned representation; no pointer is hidden in an ordinary integer slot.

The arithmetic core adapts MicroPython's compact multiplication and long division
algorithms. [Source provenance](../mpz/README.md) records the upstream version,
hashes, license and changes. It has no GMP or embedded-CPython dependency.
Multiplication follows CPython: schoolbook below 70 30-bit digits (140 for
squares, which add each cross product once) and Karatsuba above. Long division is
CPython's Knuth Algorithm D. This is a small portable implementation, not a claim of performance
parity with CPython or GMP; [bench/integers](../bench/integers/README.md) measures it against CPython
and PyPy. Text conversion uses CPython's
algorithms: power-of-two bases parse in linear time, other bases parse a group
of digits (nine decimal digits) per pass, and decimal output converts to base
10^9 in one pass per 30-bit digit. Constructing a nonzero value from a native integer allocates a wrapper and a
payload even when small. Construction from native zero shares an immutable zero
payload; copies and some arithmetic results can also share immutable payloads.
Builtin integers retain their existing native arithmetic fast path.

## Compatibility boundary

The initial API focuses on exact integer arithmetic. Automatic overflow
promotion, builtin-int identity and `isinstance(x, int)`, CPython's object ABI,
mixed floating-point arithmetic/conversion, JSON hooks and a general integer
index protocol are outside this implementation. Use explicit conversions at
those boundaries. These limits are intentional and do not establish full
CPython `int` compatibility.

CPython differential tests use an independent wrapper over its builtin `int` in
`tools/rt_cpython/mpz_oracle.py`. The native execution path uses the C arithmetic core;
the twin is only an oracle. Selected adapted upstream cases are documented in
[the test provenance guide](../tests/upstream/mpz.md), alongside original boundary,
container and allocation-pressure regressions. Passing these cases does not mean
that CPython's complete `test_int` or `test_long` suite runs unchanged.
