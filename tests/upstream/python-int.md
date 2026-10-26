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
