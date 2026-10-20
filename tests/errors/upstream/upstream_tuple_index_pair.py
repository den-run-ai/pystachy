# error: upstream_tuple_index_pair.py:10: error: tuple index out of range
# CPython 3.13.16 Lib/test/seq_tests.py, CommonTest.test_getitem, which TupleTest runs
# (assertRaises(IndexError, a.__getitem__, 3), a = self.type2test([10, 11])),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this IndexError where the subscript runs; Pystachy checks a constant tuple
# index at compile time, and its message, which goes on with the index and the tuple's
# length, starts with CPython's.
a = (10, 11)
a[3]
