# error: upstream_bool_convert_self.py:11: error: __bool__ should return bool, returned Foo
# CPython 3.13.16 Lib/test/test_bool.py, BoolTest.test_convert_to_bool (its class Foo),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError where bool() calls __bool__; Pystachy rejects the method at
# compile time, with CPython's message. The return annotation is added: without it, the method
# is typed to return None, and the message says "returned NoneType".


class Foo(object):
    def __bool__(self) -> "Foo":
        return self


bool(Foo())
