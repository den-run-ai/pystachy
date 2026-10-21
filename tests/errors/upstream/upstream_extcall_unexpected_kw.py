# error: upstream_extcall_unexpected_kw.py:11: error: e() got an unexpected keyword argument 'c'
# CPython 3.13.16 Lib/test/test_extcall.py, doctest "Verify clearing of SF bug #733667",
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; a call whose arguments do not fit
# is a compile-time error here, with CPython's message.
def e(a,b):
    print(a, b)


e(c=4)
