# Promoting integer prototype

A leading `# pystachy: python-int` comment opts one module into an experimental
integer frontend. CPython ignores the comment and runs the same source using its
builtin integers. Pystachy lowers integer literals, `int()` and `int` annotations
to a private value that promotes checked arithmetic overflow to the
[mpz backend](mpz.md). This is a draft integration experiment, not complete
CPython `int` compatibility or a change to the default language contract.

```python
# pystachy: python-int
x: int = 9223372036854775807
values: list[int] = [x, x + 1, 2 ** 128]
print(values)
print(pow(3, -1, 11))  # 4
print(list(range(2 ** 100, 2 ** 100 + 3)))
```

The pragma must precede the first statement. Each imported module chooses its
own contract. The compiler, subset runtime and existing libraries continue to
use their checked int64 arithmetic; bigint limb calculations cannot recursively
promote themselves. Combining this pragma with `dynamic-any` is rejected.

## Verified surface

- Integer literals, including exact oversized hexadecimal, octal and binary
  values; integer/string construction, selected Unicode/base/underscore inputs.
- Integer `+ - * // % & | ^`, unary operations, shifts, nonnegative integer power,
  `divmod`, `abs`, `sum`, comparisons, hashing, decimal text, `bin`, `oct`, `hex`,
  `bit_length` and `bit_count`. Small-result demotion is automatic.
- Three-argument `pow`, including negative exponents using a modular inverse.
- Annotated parameters/defaults/returns, quoted `int` annotations, class fields,
  closures, and homogeneous typed lists/dicts/sets of promoting integers. `int`
  names one concrete class, so annotated recursive and mutually recursive
  functions and methods compile. A quoted annotation stays a forward reference;
  `Literal` values and `Annotated` metadata are not rewritten.
- List reads/writes and slices: huge scalar indices raise `IndexError`; huge
  slice bounds/steps clamp. Sequence repetition uses a checked native size.
- Iteration of `range` with arbitrary-precision start/stop/step, including a few
  values around enormous starts. This is an iterator-oriented range stand-in;
  full range indexing, slicing, membership and length APIs are not implemented.
- Direct `isinstance(value, int)` includes native integers/bools. `int(x)` keeps
  the identity of an already-promoted value. `type(x).__name__`, `__qualname__`,
  `__module__`, `x.__class__.__name__` and `type(a) == type(b)` report CPython's
  `int`, also against a native int. `is` and `is not` give CPython's answer
  where it is decided: one value (`int(x) is x`), None, a bool, unequal values, or
  equal values in CPython's small-int cache (-5 to 256). Equal values outside it
  raise `NotImplementedError` unless they are one wrapper: CPython's answer then
  depends on how it made each object
  ([deviation](../tests/deviations/python_int_identity_ambiguous.py)).
- A right operand that int has no operation with raises CPython's `TypeError`
  text; a float arithmetic or comparison operand raises `NotImplementedError`
  rather than an error CPython does not raise. `int(value, base)` checks the
  base before the value, as CPython does.

## Representation and compiler boundary

`lib/_pystachy_int.py` stores a full signed int64 field and a separate nullable
`mpz` reference in a GC-scanned wrapper. Small arithmetic uses checked native
operations, catches only `OverflowError`, and retries with immutable mpz values.
Big results that fit int64 return to small storage. Aliases retain their previous
value when another variable is rebound by arithmetic. Private fields cannot be
read or modified by consumer code.

This is **not a one-word tagged representation**. Every value still has a heap
wrapper, and some operations allocate temporary wrappers/payloads. Native int64
containers are never reinterpreted as pointer-bearing containers. Opted-in
`list[int]` uses the existing scanned class-reference storage. No GMP dependency,
CPython embedding, or new runtime C entry point is introduced by this prototype.

`integer_mode.py` rewrites the opted-in module before import qualification. The
lexer retains exact oversized radix tokens instead of using its default int64
rejection sentinel. Compiler hooks for native-left numeric operations, typed
coercion, powers and indexing are restricted to the shipped private class's
source, including its generated specializations. Default-mode modules are not
rewritten. The new compiler source participates in runtime-cache identity and
normal source/package resource discovery.

## Remaining compatibility limits

| Area | Current boundary |
|---|---|
| Float arithmetic/comparison/conversion and true division | Not implemented; unsupported forms reject or raise explicit errors. Negative non-modular powers raise `NotImplementedError`. |
| Bytes/buffers, `to_bytes` / `from_bytes`, format specs | Not implemented. Radix functions and decimal string conversion are covered. |
| Identity, `type`, subclasses, builtin aliases | `id()` is rejected and undecided identity raises (above); type names and type comparisons report `int`, but `hasattr`, `dir` and other reflection see the private class. Runtime use of the `int` type object outside supported direct forms is rejected. |
| Constructor/index protocols | Only native integer/bool/string inputs and the private integer value; arbitrary `__int__` / `__index__` objects and every builtin call-binding detail are not supported. |
| Containers and native libraries | Homogeneous promoting storage is covered. Native `list[int]` aliases, mixed bool/float keys and all builtin method/FFI boundaries are not integrated. |
| Imported native results | A typed promoting parameter/return or explicit `int(result)` converts scalar values. Two unconverted native results can still take checked int64 arithmetic. |
| JSON, struct, C extensions and C-API | Keep existing contracts; no transparent bigint JSON path or CPython object ABI. |
| Dynamic Any and reflection | Combined opt-in rejected; the opt-in corpus replay records each fixture's rejection in `tools/dynany_optin_exceptions.json`. Callbacks, type metadata and dynamic dispatch still need integration. |
| String limits | Inherits the fixed 4,300-digit backend limit; no configurable `sys.set_int_max_str_digits`. |
| Name resolution | Rebinding rewritten builtins, star imports, builtin import aliases and match patterns are rejected in opted-in modules. |
| Performance | No speed or memory improvement claim. [Measured](../bench/integers/README.md) against CPython and PyPy: int64-only loops run 15–72× slower than default int64 (every value is a wrapper; overflow is detected by a caught `OverflowError`), and promoted values up to 2.3× slower than explicit mpz. |

The [test provenance](../tests/upstream/python-int.md) distinguishes selected
adapted CPython assertions from a complete upstream test run. Passing this suite
is evidence for the tested surface only.

## Reproduce

Use the repository's pinned Python interpreter and LLVM toolchain, then:

```sh
make
python3.13 -m unittest discover -s tools -p test_integer_mode.py
PYTHON=python3.13 tests/record.sh python_int_arithmetic python_int_storage python_int_cpython_int python_int_cpython_long
PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/numbers/python_int_*.py
PYSTACHY_GC_STRESS_PROGRAM=1 PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/numbers/python_int_*.py
```

The ordinary `mpz_*` corpus remains a separate backend regression control.
