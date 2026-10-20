# error: upstream_extcall_unexpected_dd.py:11: error: h() got an unexpected keyword argument 'e'
# CPython 3.13.16 Lib/test/test_extcall.py, doctest "What about willful misconduct?",
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; a call whose arguments do not fit
# is a compile-time error here, with CPython's message.
def h(j=1, a=2, h=3):
    print(j, a, h)


h(**{'e': 2})
