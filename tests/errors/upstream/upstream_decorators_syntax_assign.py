# error: upstream_decorators_syntax_assign.py:9: error: invalid syntax
# CPython 3.13.16 Lib/test/test_decorators.py, TestDecorators.test_errors (the SyntaxError of
# the statement "x = y" as a decorator), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython's message goes on: "Maybe you meant '==' or ':=' instead of '='?" (a hint of its
# parser that Pystachy leaves out, as docs/language.md's "Syntax errors" allows).
x = 1
y = 2
@x = y
def f(): pass
