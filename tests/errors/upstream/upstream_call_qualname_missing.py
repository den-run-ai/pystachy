# error: upstream_call_qualname_missing.py:20: error: A.method_two_args() missing 1 required positional argument: 'y'
# CPython 3.13.16 Lib/test/test_call.py, TestErrorMessagesUseQualifiedName.test_missing_arguments,
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; a call whose arguments do not fit
# is a compile-time error here, with CPython's message and its qualified name.
class A:
    def method_two_args(self, x, y):
        pass

    @staticmethod
    def static_no_args():
        pass

    @staticmethod
    def positional_only(arg, /):
        pass


A().method_two_args("x")
