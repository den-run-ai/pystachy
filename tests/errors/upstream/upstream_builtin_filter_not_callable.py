# error: upstream_builtin_filter_not_callable.py:7: error: 'int' object is not callable
# CPython 3.13.16 Lib/test/test_builtin.py, BuiltinTest.test_filter,
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile
# time, with CPython's message.
print(list(filter(42, (1, 2))))
