# Promoting int compatibility cases

[python_int_cpython_int.py](../programs/numbers/python_int_cpython_int.py) opts in to
[promoting ints](../../docs/python-int.md) with a leading `# pystachy: python-int` comment and
checks the builtin `int()` with assertions selected from CPython 3.13.16's
`Lib/test/test_int.py`, at commit
[`cbc944f4bc59639a444dd971c737788ba2283a91`](https://github.com/python/cpython/tree/cbc944f4bc59639a444dd971c737788ba2283a91)
(SHA-256 of the original file:
`2d947888f306e945ebc12c6817691330528c0bc7a13330b942c9af97fe3075d8`, the file
[mpz.md](mpz.md) records). Its license is [the PSF License Version 2](CPYTHON-LICENSE.txt),
also referenced in [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES). The pinned interpreter
ignores the comment and records the expected output with its own `int`.

| Preserved cases | Adaptation |
|---|---|
| `IntTestCases.test_basic`'s base-2..36 spellings of `2**32+1`, whitespace, sign and prefix checks; `test_invalid_signs`; `test_unicode`; `test_underscores`'s explicit string cases; `test_int_base_limits` | Builtin `int()`, assertions and caught exception classes instead of `unittest`, expected values as decimal strings. Bool inputs are an original addition. |

These are selected adapted assertions, not the unchanged upstream module or a run of CPython's
suite: floats, bytes and buffers, subclasses, C-API behavior, indexable bases and giant base
values are excluded. The case and
[python_int_reflection.py](../programs/numbers/python_int_reflection.py) (original `type()` and
`__class__` reflection) come from the source-rewriting prototype of #901, recorded again with
the pinned interpreter.

[python_int_cpython_long.py](../programs/numbers/python_int_cpython_long.py) and
[python_int_import.py](../programs/numbers/python_int_import.py) come from #901's head
`9c81341a` too, unchanged, with the recordings it made with the pinned interpreter. The first
checks assertions selected from `Lib/test/test_long.py` at the same CPython commit (SHA-256
`66eeb959a2a1e573f16067fc02d75f22d5344a223bed08033b01612f52d9a11a`, which [mpz.md](mpz.md)
records), under the same license:

| Preserved cases | Adaptation |
|---|---|
| Twelve long-division cases, each in four sign combinations; bitwise identities over eight values; 64 multiplication identities; twelve `bit_length()` boundaries; integer hashes | Ordinary `int` operators and `pow()` with standalone assertions instead of `unittest`; deterministic bounded loops instead of random and exhaustive ones. Floats, bytes, subclasses, C-API and huge-memory cases are excluded. |

The second is original: a module without the comment calls a function of one that opts in
(`tests/python_int_modules/promoting_module.py`) and computes with, prints and lists the int
past 64 bits that it returns. Both needed a list of ints that holds one.
