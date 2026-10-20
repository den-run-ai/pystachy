# error: upstream_exceptions_syntax_unterminated.py:8: error: unterminated string literal (detected at line 8)
# CPython 3.13.16 Lib/test/test_exceptions.py, ExceptionTests.testSyntaxErrorOffset
# (its check() at line 1 of the source below), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython's SyntaxError is a compile-time error here too, reported at its line (upstream's
# line, after these seven lines) and with its message; the column offsets that upstream
# checks are not reported.
x = "a