# error: upstream_int_base_non_str.py:7: error: int() can't convert non-string with explicit base
# CPython 3.13.16 Lib/test/test_int.py, IntTestCases.test_basic (assertRaises(TypeError, int, 1,
# 12)), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile
# time, with CPython's message.
int(1, 12)
