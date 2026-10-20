# error: upstream_format_percent_z.py:8: error: unsupported format character 'z' (0x7a) at index 1
# CPython 3.13.16 Lib/test/test_format.py, FormatTest.test_specifier_z_error
# (assertRaisesRegex(ValueError, "unsupported format character 'z'"): "%z.1f" % 0),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this ValueError where the formatting runs; Pystachy checks a constant format
# string at compile time, with CPython's message.
"%z.1f" % 0
