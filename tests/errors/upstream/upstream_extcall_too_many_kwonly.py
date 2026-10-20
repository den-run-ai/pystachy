# error: upstream_extcall_too_many_kwonly.py:8: error: f() takes 0 positional arguments but 1 positional argument (and 1 keyword-only argument) were given
# CPython 3.13.16 Lib/test/test_extcall.py, doctest "Too many arguments",
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; a call whose arguments do not fit
# is a compile-time error here, with CPython's message.
def f(*, kw): pass
f(1, kw=3)
