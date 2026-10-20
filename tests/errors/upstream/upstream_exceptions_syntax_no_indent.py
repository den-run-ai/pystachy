# error: upstream_exceptions_syntax_no_indent.py:9: error: expected an indented block
# CPython 3.13.16 Lib/test/test_exceptions.py, ExceptionTests.testSyntaxErrorMissingParens
# (its ckmsg() of the source below), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython's SyntaxError is a compile-time error here too, at its line (upstream's, after
# these seven lines) and with its message but for what it goes on with, its parser's hint
# (as docs/language.md allows); the column offsets that upstream checks are not reported.
if True:
print "No indent"