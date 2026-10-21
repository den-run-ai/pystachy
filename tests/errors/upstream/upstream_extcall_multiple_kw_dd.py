# error: upstream_extcall_multiple_kw_dd.py:12: error: __main__.f() got multiple values for keyword argument 'a'
# CPython 3.13.16 Lib/test/test_extcall.py, doctest "Here we add keyword arguments",
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; a call whose arguments do not fit
# is a compile-time error here, with CPython's message. (The doctest's helper prints
# its **kwargs with test.support.sortdict(); it never runs here, and prints them as is.)
def f(*a, **k):
    print(a, k)


f(1, 2, **{'a': -1, 'b': 5}, **{'a': 4, 'c': 6})
