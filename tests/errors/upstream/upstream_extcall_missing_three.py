# error: upstream_extcall_missing_three.py:8: error: f() missing 3 required positional arguments: 'a', 'b', and 'c'
# CPython 3.13.16 Lib/test/test_extcall.py, doctest "Too few and missing arguments",
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; a call whose arguments do not fit
# is a compile-time error here, with CPython's message.
def f(a, b, c): pass
f()
