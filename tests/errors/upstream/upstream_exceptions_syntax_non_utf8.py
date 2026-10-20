# error: upstream_exceptions_syntax_non_utf8.py:8: error: Non-UTF-8 code starting with '\x89' in file
# CPython 3.13.16 Lib/test/test_exceptions.py, SyntaxErrorTests.test_non_utf8
# (its run_script() of the source below), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython's SyntaxError is a compile-time error here too, at its line (the first upstream,
# after these seven lines) and with its message, which goes on with the file's path:
# upstream checks the part before it.
‰