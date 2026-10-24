# Explicit mpz compatibility cases

The `mpz` fixtures run through Pystachy's ordinary differential corpus in JIT
and AOT, including its GC-stressed and sanitizer configurations. They exercise
an explicit arbitrary-precision class; ordinary `int` remains checked signed
64-bit. They do not establish full CPython `int` or C-API compatibility.

The fixtures first import the native `mpz` module. Under CPython, where that
module is absent, they import [mpz_oracle.py](../../tools/rt_cpython/mpz_oracle.py),
an independent wrapper around CPython's own `int`. The `.path` sidecars expose
that oracle without providing a file named `mpz.py` that could shadow the native
module. Native generated IR must contain calls to `pys_mpz_*`; compiling the
oracle would not validate the C backend. Expected `.out` files are recorded with
the pinned interpreter, never from the native implementation.

## Selected upstream cases

The two adapted fixtures use CPython 3.13.16 at commit
[`cbc944f4bc59639a444dd971c737788ba2283a91`](https://github.com/python/cpython/tree/cbc944f4bc59639a444dd971c737788ba2283a91).
The complete original files were fetched before adaptation. Their license is
[the PSF License Version 2](CPYTHON-LICENSE.txt), also referenced in
[THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

| Upstream source | SHA-256 of the original file |
|---|---|
| `Lib/test/test_long.py` | `66eeb959a2a1e573f16067fc02d75f22d5344a223bed08033b01612f52d9a11a` |
| `Lib/test/test_int.py` | `2d947888f306e945ebc12c6817691330528c0bc7a13330b942c9af97fe3075d8` |

| Fixture | Preserved cases | Adaptation |
|---|---|---|
| [mpz_cpython_long.py](../programs/numbers/mpz_cpython_long.py) | `LongTest.check_division` and all twelve fixed `test_division` corner cases; `check_bitop_identities_1/2`; `test_karatsuba` multiplication identity; `test_bit_length` power boundaries; `test_hash` | Explicit `mpz`, decimal strings for oversized literals, standalone assertions, `//` and `%` instead of `divmod`, `.abs()` and `.pow()`. Four sign combinations for the division cases. Deterministic bounded values replace random/exhaustive loops. Multiplication tests do not claim a Karatsuba implementation. |
| [mpz_cpython_int.py](../programs/numbers/mpz_cpython_int.py) | `IntTestCases.test_basic` base-2..36 representations of `2**32+1`, whitespace/sign and prefix checks; `test_invalid_signs`; `test_unicode`; explicit string cases from `test_underscores`; `test_int_base_limits` | Explicit `mpz`, expected decimal strings, assertions/caught exception classes. Additional prefix/underscore boundaries. |

These are selected adapted assertions, not unchanged upstream modules or a run
of the whole CPython suite. Excluded areas include true division and floats,
implicit conversion/index protocols, builtin subclass behavior, bytes and buffers,
format specifications, configurable decimal limits, CPython object identity/cache
or C-API/refcount internals, and exhaustive/random huge-memory fixtures.

## Original regression and integration cases

- [mpz_arithmetic.py](../programs/numbers/mpz_arithmetic.py) contains 24 independent
  CPython-generated operand pairs with 192 exact expected decimal arithmetic,
  division and bitwise results, plus mixed right-hand `int` and unary checks.
  Boundaries span 30-bit limbs and 63/64/65/127/128/255/256/1023-bit magnitudes.
- [mpz_storage.py](../programs/numbers/mpz_storage.py) retains values through typed
  fields, returns, list items, dictionary keys and set membership, while creating
  further allocations. Aliases and copies keep their values after arithmetic and
  repeated initialization; dictionary hashes remain stable.
- [mpz_limits.py](../programs/numbers/mpz_limits.py) checks signed-64-bit conversion,
  zero divisors, negative shift counts/exponents, zero and sign-extending huge
  shifts, and the fixed 4300-digit decimal conversion boundary.
- [mpz_applications.py](../programs/numbers/mpz_applications.py) computes 100!,
  Fibonacci(200), modular exponentiation, 64-square bitboard shifts and masked
  FNV-1a arithmetic. A bounded ordinary-int control remains independent of mpz.
- [mpz_dynamic.py](../programs/numbers/mpz_dynamic.py) checks existing Dynamic Any
  arithmetic, truth, hashing, equality, typed-to-dynamic storage and bigint
  dictionary keys after further allocations.
- [mpz_shadow.py](../programs/imports/mpz_shadow.py) checks a user-defined module
  named `mpz` retains ordinary mutable field and initialization semantics.
  The `tests/errors/library/mpz_*` cases enforce private-handle/intrinsic,
  subclass, native-int-left arithmetic and unbound-initializer boundaries.

## Reproduce

```sh
PYTHON=python3.13 tests/record.sh mpz_arithmetic mpz_cpython_long mpz_cpython_int mpz_storage mpz_limits mpz_applications mpz_dynamic mpz_shadow
PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/numbers/mpz_*.py tests/programs/imports/mpz_shadow.py tests/errors/library/mpz_*.py
PYSTACHY_GC_STRESS_PROGRAM=1 PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/numbers/mpz_*.py tests/programs/imports/mpz_shadow.py tests/errors/library/mpz_*.py
```
