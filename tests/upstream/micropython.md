# MicroPython's integer tests

`tests/programs/upstream/upstream_micropython_*.py` are 36 of MicroPython's
[`tests/basics/`](https://github.com/micropython/micropython/tree/a39e77f08d1daf13658ccae99b763003a8218bdf/tests/basics)
integer tests at commit
[`a39e77f08d1daf13658ccae99b763003a8218bdf`](https://github.com/micropython/micropython/commit/a39e77f08d1daf13658ccae99b763003a8218bdf)
(2026-10-26). Each is unchanged after a four-line header, whose first line opts it in to
[promoting ints](../../docs/python-int.md) (`# pystachy: python-int`). The pinned interpreter
ignores the header and records the expected output, as for every differential case: MicroPython's
own `.exp` files are not used. They are under the MIT License, Copyright (c) 2013-2026 Damien P.
George, reproduced in [MICROPYTHON-LICENSE.txt](MICROPYTHON-LICENSE.txt) and referenced in
[THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES). [`mpz/`](../../mpz/README.md) adapts the same
project's arbitrary-precision core.

| Upstream file | SHA-256 |
|---|---|
| [`builtin_abs_intbig.py`](../programs/upstream/upstream_micropython_builtin_abs_intbig.py) | `dc1cf43847f35ec603274991d1e869eacb351be957842dde2a6d0a54b46f7ba2` |
| [`builtin_bin_intbig.py`](../programs/upstream/upstream_micropython_builtin_bin_intbig.py) | `a629784a05c37598ee998efcc274b88bbc712f6fbb6a452a453cfa490eb31a27` |
| [`builtin_divmod_intbig.py`](../programs/upstream/upstream_micropython_builtin_divmod_intbig.py) | `fd92bab3feafeaf5c34f047a2d0786a3f8c603f422113107d4e60a65d075e223` |
| [`builtin_hash_intbig.py`](../programs/upstream/upstream_micropython_builtin_hash_intbig.py) | `c8e26d21f137cc261de3622d2856827d5e8c27ba5358b0f5836816f8a407d900` |
| [`builtin_hex_intbig.py`](../programs/upstream/upstream_micropython_builtin_hex_intbig.py) | `77e667cdda555584927cc3048679f00d12fade81d6b5f4157ad3808433d4f600` |
| [`builtin_oct_intbig.py`](../programs/upstream/upstream_micropython_builtin_oct_intbig.py) | `d90146a0ed050bc8029d2ce9f39f53b7e0d81f6b2c043e0377b2402ba9443515` |
| [`builtin_pow3_intbig.py`](../programs/upstream/upstream_micropython_builtin_pow3_intbig.py) | `18849671d6b6172b313af89c253195e6e89f6e6d5e171f6e48e1fd68ecf73555` |
| [`floordivide_intbig.py`](../programs/upstream/upstream_micropython_floordivide_intbig.py) | `8b6f3eda6403ac7fb3712634c29f9717e47b3d5f1d413fac5cbabfe039b7851d` |
| [`int2.py`](../programs/upstream/upstream_micropython_int2.py) | `28d2eb71dc252947d5c4a9957588019365a3daeb842a8c95eb92e900c6f5af22` |
| [`int_big1.py`](../programs/upstream/upstream_micropython_int_big1.py) | `4202ffd2bc9995972cd994c044e8f83e961e1e78a7ca73af74f3488dbe652f79` |
| [`int_big_add.py`](../programs/upstream/upstream_micropython_int_big_add.py) | `6565da2b76584af11eeea8584d3ce6aa79c176b6be893f4fde02faae20a2afad` |
| [`int_big_and.py`](../programs/upstream/upstream_micropython_int_big_and.py) | `191f63f1f42847e4cc4b36a65648081981915f4a483023b2f9bfd35dd7b3cac7` |
| [`int_big_and2.py`](../programs/upstream/upstream_micropython_int_big_and2.py) | `7270dcd4b679718b5e1e1a0e3c143657fbe3949568d1427df186fa583191e32e` |
| [`int_big_and3.py`](../programs/upstream/upstream_micropython_int_big_and3.py) | `48064ce1d3b07bb21612e5c8d51979fb1630855eda434b2ce2582f35336613fd` |
| [`int_big_cmp.py`](../programs/upstream/upstream_micropython_int_big_cmp.py) | `7bfd94b919ecd37ab4998e21600e25a724b2f323aa5402fcd4a6766e7c531135` |
| [`int_big_div.py`](../programs/upstream/upstream_micropython_int_big_div.py) | `40926c444abcc27222f4237d5efa5d17ec13acae38da781815ad96a36fe8a915` |
| [`int_big_lshift.py`](../programs/upstream/upstream_micropython_int_big_lshift.py) | `572f5ed76f688dddd708db3f86a7ec3c844fbbb6fdb681c56d0eb3de444425f0` |
| [`int_big_mod.py`](../programs/upstream/upstream_micropython_int_big_mod.py) | `ad57542f91bb44af5fd551809436dba32f013a537b2b894ed2d1742413aa745e` |
| [`int_big_mul.py`](../programs/upstream/upstream_micropython_int_big_mul.py) | `d005a6c5d8a19241211afae36d2942ce57e9173b78217d1b76ec982a6ade8935` |
| [`int_big_or.py`](../programs/upstream/upstream_micropython_int_big_or.py) | `77a010df9c7080907427c5b279cfcedfda24898937e872dbfbb15bbac43fc1a4` |
| [`int_big_or2.py`](../programs/upstream/upstream_micropython_int_big_or2.py) | `0731f9301de2c1992a605ad177abf24cffd28dd10a23a41f83b0f56bd478635b` |
| [`int_big_or3.py`](../programs/upstream/upstream_micropython_int_big_or3.py) | `56e9aa64398fb99df1ffd2170006fd7be7373cef5765eeb899d1da6ffead6af2` |
| [`int_big_pow.py`](../programs/upstream/upstream_micropython_int_big_pow.py) | `48cdb853548d3db543f5b2a5c5ad506d4bffc3f86da9af8e1e0feb00d09645d6` |
| [`int_big_rshift.py`](../programs/upstream/upstream_micropython_int_big_rshift.py) | `89600990e42e927e9456dd74c6f6c846a08f1eac2fb7bc15ccb4bb10e8ddd220` |
| [`int_big_unary.py`](../programs/upstream/upstream_micropython_int_big_unary.py) | `53a7fed38db434089958cc06f38953a04cbf5ecaacf9d80761dfc98d49016602` |
| [`int_big_xor.py`](../programs/upstream/upstream_micropython_int_big_xor.py) | `6afd9f1c664b2b75d27e8771d23a8941568682d5d6b938bb00c28c38d7c1c863` |
| [`int_big_xor2.py`](../programs/upstream/upstream_micropython_int_big_xor2.py) | `d6ff8a08bdc84ee126a420826595db8fbfb84752fff34b4f84e4bee26493628d` |
| [`int_big_xor3.py`](../programs/upstream/upstream_micropython_int_big_xor3.py) | `4400652f30c555b34a18aa527d905f68a978536739fa41c4c05c7fd21e34caa5` |
| [`int_constfolding.py`](../programs/upstream/upstream_micropython_int_constfolding.py) | `b6770393f3a9aa235403947e4a9ac8a913608939bccc28dfaaff87734fdc2285` |
| [`int_constfolding_intbig.py`](../programs/upstream/upstream_micropython_int_constfolding_intbig.py) | `bf35e602f30bf6c031602c0da2f92f18dc8dd5b103bec5e85747bc6ee0bcc6a0` |
| [`int_divmod.py`](../programs/upstream/upstream_micropython_int_divmod.py) | `c1a8785cf29431fa2c3d1d52da0fc578788cc67f20150aba4895a157b1c76fed` |
| [`int_divmod_intbig.py`](../programs/upstream/upstream_micropython_int_divmod_intbig.py) | `c8fd42fab62ee416518bcf888145db49e77f2235eedb03031941682cfbca84b6` |
| [`int_divzero.py`](../programs/upstream/upstream_micropython_int_divzero.py) | `5c847f4b1726d8fcbcd85d794d9eeeadedd791c4040211d4ac7edcebce30572a` |
| [`int_intbig.py`](../programs/upstream/upstream_micropython_int_intbig.py) | `3a0e964c4b124e0d2be7da931adf8e9f17815a3ff1ce178908182daabb81c6f1` |
| [`int_small.py`](../programs/upstream/upstream_micropython_int_small.py) | `95bb160610b830e20a8c1dae749037fde2ce205da6a8484e02b25368584cfe17` |
| [`slice_intbig.py`](../programs/upstream/upstream_micropython_slice_intbig.py) | `6e0b06873f446c426d587dd04f8e067fe18ebf3f442383f0ba4a3ca74152fd67` |

## Selection

51 integer tests of `tests/basics/` were run with the comment prepended, JIT, against CPython
3.13: the `int*.py` files but `int_big_to_small_int29.py` and `int_bytes_optional_args_cp311.py`
(MicroPython configurations, with `.exp` files of their own), the `*_intbig.py` files but those of
`array`, `bytearray`, `bytes`, `memoryview` and `struct`, `builtin_round_int.py` and
`string_format_modulo_int.py`. The 36 above print what CPython prints: 35 also with the compiler of
main before #907's list storage, and `builtin_hash_intbig.py` since dict keys hold promoting ints.
The other 15 stay out; the first problem of each:

| Upstream file | First problem |
|---|---|
| `builtin_round_int.py` | A list of tuples whose items are a `bool` or an int (`expected int, got bool \| int`). |
| `builtin_round_intbig.py` | Tuples in a list hold 64-bit ints ([boundaries](../../docs/python-int.md#64-bit-boundaries)): `OverflowError`. |
| `int1.py` | `int(x, base)` where `x` is not a `str` is rejected during compilation (CPython raises `TypeError`). |
| `int_64_basics.py` | `hasattr()` of a module (`unsupported module attribute`). |
| `int_big_error.py` | `@` between ints is rejected during compilation (CPython raises `TypeError`). |
| `int_big_to_small.py` | Prints `SKIP` under CPython: it needs MicroPython's `micropython` module. |
| `int_big_zeroone.py` | A module variable bound to a list and later to a tuple. |
| `int_bytes.py`, `int_bytes_int64.py`, `int_bytes_intbig.py` | `int.to_bytes()` and `int.from_bytes()` are not supported. |
| `int_parse.py` | `int()` of a `bytes`. |
| `op_error_intbig.py` | `in` with an int as the container is rejected during compilation (CPython raises `TypeError`). |
| `special_methods_intbig.py` | `int()` of an object whose class defines `__int__`. |
| `string_format_intbig.py` | `str.format()` of a format string computed at run time. |
| `string_format_modulo_int.py` | `%` formatting with a `*` width or precision. |

Only `builtin_round_intbig.py` meets a limit of promoting ints; the others meet limits of the
subset that modules without the comment share ([language](../../docs/language.md)).
