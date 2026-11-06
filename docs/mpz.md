# Explicit arbitrary-precision integers

`mpz` is Pystachy's experimental, immutable class for explicitly chosen
arbitrary-precision calculations. Import it in any module and construct operands
before an operation that may exceed signed 64-bit range:

```python
from mpz import mpz

x = mpz("18446744073709551616")
print(x * x)                        # 340282366920938463463374607431768211456
print(mpz(-7) // 3)                 # -3
print(mpz(-7) % 3)                  # 2
print(mpz(2).pow(128).bit_length())  # 129

values: list[mpz] = [x, x + 1]
counts: dict[mpz, int] = {x: 2}
print(counts[mpz(str(x))])           # 2
```

For code that should keep the builtin `int` interface and promote on overflow,
use [promoting ints](python-int.md). Both interfaces share the C arithmetic core,
but `mpz` remains a separate class. Importing it does not change a module's
integer policy or its JSON behavior.

<a id="initial-api"></a>

## Supported API

| Operation | Accepted form |
|---|---|
| Construct | `mpz()`, `mpz(value)` for signed 64-bit `int` or `bool`, `mpz(text, base=10)` for `str`; base 0 or 2–36 |
| Copy | `x.copy()`; constructing from another `mpz` is not supported |
| Arithmetic | `+`, `-`, `*`, `//`, `%`, `&`, `\|`, `^`; `mpz` on the left, `mpz` or signed 64-bit `int`/`bool` on the right |
| Unary | `+x`, `-x`, `~x`, `x.abs()` |
| Shifts and powers | `x << count`, `x >> count`, `x.pow(exponent)`; nonnegative signed 64-bit counts/exponents |
| Inspect and convert | `x.bit_length()`, `x.to_int()`, decimal `str(x)` and `repr(x)` |
| Compare | `==`, `!=`, `<`, `<=`, `>`, `>=` with the arithmetic operand types above |
| Protocols and storage | Truth testing, integer hashes matching 64-bit CPython, typed fields, lists, dictionaries and sets; [dynamic `Any`](dynamic-any.md) class dispatch |

`//` rounds down and `%` has the divisor's sign. Negative bitwise operations use
infinite two's-complement semantics. Arithmetic leaves existing values unchanged,
so aliases and dictionary keys remain valid when another expression uses them.

## Text conversion and errors

String input accepts Python-style signs, base prefixes, underscores, Unicode
decimal digits and surrounding whitespace. Use a string for an initial value
outside signed 64-bit range. Input in a non-power-of-two base and decimal output
have a fixed 4,300-digit limit. Power-of-two input bases avoid that digit limit,
but printing the result can still exceed it. `sys.set_int_max_str_digits()` does
not change this limit.

| Boundary | Error |
|---|---|
| `x.to_int()` outside `-2**63` through `2**63 - 1` | `OverflowError` |
| Negative shift count or exponent | `ValueError` |
| Division or modulo by zero | `ZeroDivisionError` |
| Invalid text/base or exceeded text digit limit | `ValueError` |
| A non-string constructor argument with a base other than 10 | `TypeError` |

Argument shapes outside the typed API can be rejected during compilation.

## Compatibility boundary

Use `x.pow(n)` and `x.abs()`; `**`, builtin `pow()` and builtin `abs()` are not
provided for this class. Keep `mpz` on the left of mixed arithmetic: reflected
operations such as `1 + x` are unsupported. There is no true division, modular
power, negative power, float conversion, byte conversion, radix formatting or
subclass support.

An `mpz` is not a builtin `int` and does not provide the general integer index
protocol. Use `to_int()` for fixed-width native or index arguments when the value
fits. JSON does not treat it as an integer automatically. The separate
[dynamic JSON path](json.md#in-modules-that-opt-in-to-dynamic-any) can already preserve wide builtin
integers without an `mpz` wrapper or a caller `python-int` pragma.

## Implementation

The [subset class](../lib/mpz.py) holds an opaque, GC-traced handle to a
pointer-free C payload: a signed limb count followed by packed `uint32_t`
base-2^30 digits. Containers retain the class reference through their usual
GC-scanned storage.

Constructing a nonzero value from a native integer allocates both a wrapper and
a payload, even when small. Native zero uses a shared immutable payload; copies
and some arithmetic results can share payloads too. Promoting `int` avoids this
wrapper API and keeps small values on its native arithmetic path.

The core uses CPython's arithmetic and text-conversion algorithms with a
MicroPython-derived multiply-add helper. [Backend provenance](../mpz/README.md)
records the algorithms, upstream versions, hashes and licenses. No GMP or
embedded CPython is needed. The [integer benchmarks](../bench/integers/README.md)
retain workloads and dated comparisons with CPython and PyPy.

## Validation coverage

CPython differential tests use an independent wrapper over its builtin `int` in
[`mpz_oracle.py`](../tools/rt_cpython/mpz_oracle.py). The native path uses the C
core. [Test provenance and reproduction commands](../tests/upstream/mpz.md)
cover adapted CPython assertions, arithmetic/text boundaries, typed and dynamic
storage, and allocation pressure. These are selected cases, not unchanged runs
of CPython's complete `test_int` or `test_long` suites.
