# error: upstream_decorators_undef.py:7: error: name 'undef' is not defined
# CPython 3.13.16 Lib/test/test_decorators.py, TestDecorators.test_errors ("undef", NameError),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises NameError when the def statement runs; a name that nothing binds is a
# compile-time error here, with CPython's message.
@undef
def f(): pass
assert f() is None
