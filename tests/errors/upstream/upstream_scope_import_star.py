# error: upstream_scope_import_star.py:9: error: import * only allowed at module level
# CPython 3.13.16 Lib/test/test_scope.py, ScopeTests.testUnoptimizedNamespaces (its first
# check_syntax_error source), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython's SyntaxError is a compile-time error here too, at the inner function's import.
if 1:
    def unoptimized_clash1(strip):
        def f(s):
            from sys import *
            return getrefcount(s) # ambiguity: free or local
        return f
