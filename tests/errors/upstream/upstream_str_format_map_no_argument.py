# error: upstream_str_format_map_no_argument.py:8: error: str.format_map() takes exactly one argument (0 given)
# CPython 3.13.16 Lib/test/test_str.py, StrTest.test_format_map
# (self.assertRaises(TypeError, ''.format_map)),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError where the call runs; Pystachy rejects the call at compile time,
# with CPython's message.
''.format_map()
