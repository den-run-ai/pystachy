# Promoting integer compatibility cases

These programs use a leading `# pystachy: python-int` comment and ordinary Python
integer expressions. The pinned CPython **3.13.16** interpreter ignores the
comment and records expectations using its builtin `int`. There is no bigint
oracle wrapper, import fallback or embedded CPython in native execution.

The selected upstream assertions retain the source and PSF license recorded in
[mpz.md](mpz.md): CPython commit
[`cbc944f4bc59639a444dd971c737788ba2283a91`](https://github.com/python/cpython/tree/cbc944f4bc59639a444dd971c737788ba2283a91),
`Lib/test/test_int.py` SHA-256
`2d947888f306e945ebc12c6817691330528c0bc7a13330b942c9af97fe3075d8`,
and `Lib/test/test_long.py` SHA-256
`66eeb959a2a1e573f16067fc02d75f22d5344a223bed08033b01612f52d9a11a`.
The [PSF license](CPYTHON-LICENSE.txt) and repository notices apply.

| Fixture | Evidence and adaptation |
|---|---|
| [python_int_cpython_int.py](../programs/numbers/python_int_cpython_int.py) | Previously selected `test_basic`, invalid signs, Unicode, underscore and base-limit assertions, restored to builtin `int` syntax. All bases 2–36, 29 invalid cases and bool inputs. Standalone assertions replace unittest. |
| [python_int_cpython_long.py](../programs/numbers/python_int_cpython_long.py) | Twelve fixed long-division cases in four sign combinations; eight-value bitwise identities; 64 multiplication identities; twelve bit-length boundaries; integer hashes. Ordinary `int`/`pow`; deterministic bounded loops replace random/exhaustive tests. |
| [python_int_arithmetic.py](../programs/numbers/python_int_arithmetic.py) | Original 64-bit promotion/demotion boundaries, large decimal/radix/f-string literals, 10×10 signed arithmetic pairs, shifts, power/modular inverses, error classes, radix output and decimal limits. Expected text comes directly from CPython. |
| [python_int_storage.py](../programs/numbers/python_int_storage.py) | Original typed calls/defaults/returns, quoted annotations, closures, fields, list aliases, dict keys, set membership, allocation pressure, indexing/slicing, large-start ranges, factorial and Fibonacci. |
| [python_int_import.py](../programs/numbers/python_int_import.py) | A default-mode consumer calls an opted-in module; the promoted return value survives the boundary and both operand orders. The helper lives outside the corpus and uses a `.path` sidecar. |
| [python_int_recursion.py](../programs/numbers/python_int_recursion.py) | Original recursive, mutually recursive and memoized functions and a recursive method, with direct and quoted annotations. |
| [python_int_forward_ref.py](../programs/numbers/python_int_forward_ref.py) | Original quoted forward references to a later class and quoted container annotations. |
| [python_int_reflection.py](../programs/numbers/python_int_reflection.py) | Original `type()` / `__class__` names and type comparisons of promoting, native and other values. |
| [python_int_identity.py](../programs/numbers/python_int_identity.py) | Original `is` / `is not` cases CPython's values decide: one object, None, bools, unequal values and its small-int cache. The undecided case is [a deviation](../deviations/python_int_identity_ambiguous.py). |
| [python_int_errors.py](../programs/numbers/python_int_errors.py) | Original operand, `range` and `bin` errors; CPython's exception classes and text. |
| [python_int_base_errors.py](../programs/numbers/python_int_base_errors.py) | Original `int(value, base)` errors: the base is checked before the value, as in CPython. |

The four `tests/errors/library/python_int_*.py` cases enforce explicit rejection
of builtin aliases/rebinding, the Dynamic Any combination, and private field
writes. `tools/test_integer_mode.py` additionally checks pragma placement,
unchanged default ASTs, exact radix and decimal tokens, quoted, `Literal` and
`Annotated` annotations, binding scopes, helper shadowing, docstrings and
successive hosted-compilation isolation. These guards run in
`make check-fast` and therefore in Lint CI.

This is **selected adapted coverage**, not unchanged upstream `test_int` /
`test_long` modules or a complete `regrtest` run. No float/true-division, bytes,
subclass, arbitrary protocol, full range/format, C-API/refcount or huge-memory
coverage is claimed. The [prototype contract](../../docs/python-int.md) lists
additional boundary restrictions and reproduction commands. New differential
programs and error fixtures use the existing corpus machinery, including its
native/hosted, JIT/AOT, GC, optimizer-disabled and sanitizer CI configurations;
registration does not mean a particular draft head has passed every configuration.
