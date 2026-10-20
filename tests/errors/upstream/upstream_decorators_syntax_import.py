# error: upstream_decorators_syntax_import.py:5: error: invalid syntax
# CPython 3.13.16 Lib/test/test_decorators.py, TestDecorators.test_errors (the SyntaxError of
# the statement "import sys" as a decorator), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
@import sys
def f(): pass
