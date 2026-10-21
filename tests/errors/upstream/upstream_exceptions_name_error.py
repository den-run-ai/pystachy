# error: upstream_exceptions_name_error.py:10: error: name 'bluch' is not defined
# CPython 3.13.16 Lib/test/test_exceptions.py, NameErrorTests.test_name_error_has_name,
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this NameError when the read runs, which the try statement catches (the
# test checks its name attribute, which Pystachy does not support); Pystachy rejects a
# read of a name that nothing binds at compile time, with CPython's message.
def test_name_error_has_name() -> None:
    try:
        bluch
    except NameError as exc:
        print("bluch", exc)


test_name_error_has_name()
