# error: upstream_builtin_all_two_args.py:7: error: all() takes exactly one argument (2 given)
# CPython 3.13.16 Lib/test/test_builtin.py, BuiltinTest.test_all,
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile
# time, with CPython's message.
all([2, 4, 6], [])    # Too many args
