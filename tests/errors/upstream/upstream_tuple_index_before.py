# error: upstream_tuple_index_before.py:10: error: tuple index out of range
# CPython 3.13.16 Lib/test/seq_tests.py, CommonTest.test_getitem, which TupleTest runs
# (assertRaises(IndexError, u.__getitem__, -len(u)-1), u of 5 items),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this IndexError where the subscript runs; Pystachy checks a constant tuple
# index at compile time, and its message, which goes on with the index and the tuple's
# length, starts with CPython's.
u = (0, 1, 2, 3, 4)
u[-6]
