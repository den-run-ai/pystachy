# error: upstream_exceptions_undefined_variable.py:10: error: name 'undefined_variable' is not defined
# CPython 3.13.16 Lib/test/test_exceptions.py, ExceptionTests.testRaising (its NameError of
# `x = undefined_variable`),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this NameError when the read runs, which the try statement catches;
# Pystachy rejects a read of a name that nothing binds at compile time, also in a try
# statement whose clause catches it, with CPython's message.
def testRaising() -> None:
    try: x = undefined_variable
    except NameError: pass


testRaising()
