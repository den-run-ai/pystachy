# error: upstream_extcall_multiple_values.py:12: error: g() got multiple values for argument 'x'
# CPython 3.13.16 Lib/test/test_extcall.py, doctest "What about willful misconduct?",
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; a call whose arguments do not fit
# is a compile-time error here, with CPython's message. (The doctest's helper prints
# its **kwargs with test.support.sortdict(); it never runs here, and prints them as is.)
def g(x, *y, **z):
    print(x, y, z)


g(1, 2, 3, **{'x': 4, 'y': 5})
