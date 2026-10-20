# error: upstream_unpack_ex_non_iterable.py:9: error: cannot unpack non-iterable int object
# CPython 3.13.16 Lib/test/test_unpack_ex.py, its doctest "Unpacking non-sequence"
# (`a, *b = 7`: TypeError: cannot unpack non-iterable int object),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError where the assignment runs; Pystachy rejects the assignment at
# compile time, with CPython's message.
a = 0
a, *b = 7
