# error: upstream_builtin_max_not_iterable.py:7: error: 'int' object is not iterable
# CPython 3.13.16 Lib/test/test_builtin.py, BuiltinTest.test_max,
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile
# time, with CPython's message.
max(42)
