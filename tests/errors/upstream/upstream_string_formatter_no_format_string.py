# error: upstream_string_formatter_no_format_string.py:10: error: Formatter.format() missing 1 required positional argument: 'format_string'
# CPython 3.13.16 Lib/test/test_string.py, ModuleTest.test_basic_formatter
# (self.assertRaises(TypeError, fmt.format), fmt = string.Formatter()),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError where the call runs; Pystachy rejects the call at compile time,
# with CPython's message.
import string
fmt = string.Formatter()
fmt.format()
