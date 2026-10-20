# error: upstream_baseexception_raise_string.py:10: error: exceptions must derive from BaseException
# CPython 3.13.16 Lib/test/test_baseexception.py, UsageTests.test_raise_string
# (its raise_fails("spam")),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the raise runs, which raise_fails catches; Pystachy
# rejects the raise at compile time, and its message, which goes on with what a raise
# needs, starts with CPython's.
try:
    raise "spam"
except TypeError:
    pass  # What is expected.
