# error: upstream_int_missing_string_base0.py:7: error: int() missing string argument
# CPython 3.13.16 Lib/test/test_int.py, IntTestCases.test_keyword_args (assertRaises(TypeError,
# int, base=0)), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile
# time, with CPython's message.
int(base=0)
