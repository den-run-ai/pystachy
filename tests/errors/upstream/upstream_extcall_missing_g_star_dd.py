# error: upstream_extcall_missing_g_star_dd.py:12: error: g() missing 1 required positional argument: 'x'
# CPython 3.13.16 Lib/test/test_extcall.py, doctest "Verify clearing of SF bug #733667",
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; a call whose arguments do not fit
# is a compile-time error here, with CPython's message. (The doctest's helper prints
# its **kwargs with test.support.sortdict(); it never runs here, and prints them as is.)
def g(x, *y, **z):
    print(x, y, z)


g(*(), **{})
