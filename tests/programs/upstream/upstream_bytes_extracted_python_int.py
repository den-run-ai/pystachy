# pystachy: python-int
# CPython 3.13.16 Lib/test/test_bytes.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 aae9cf5348faa9b39bdccb13489e14facb6cdf51bfa5310a75518608645f6e06),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# These tests need CPython's int, so the program opts in to promoting ints.
# Tests: BytesTest.test_constructor_value_errors.
"""Unit tests for the bytes and bytearray types.

XXX This is a mess.  Common tests should be unified with string_tests.py (and
the latter should be modernized).
"""
import sys

class BaseBytesTest:

    def assertTypedEqual(self, actual, expected):
        assert type(actual) is type(expected)
        assert actual == expected

    def test_constructor_value_errors(self):
        try:
            self.type2test([-1])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([-sys.maxsize])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([-sys.maxsize - 1])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([-sys.maxsize - 2])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([-10 ** 100])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([256])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([257])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([sys.maxsize])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([sys.maxsize + 1])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            self.type2test([10 ** 100])
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')

class BytesTest(BaseBytesTest):
    type2test = bytes


def _BytesTest__test_constructor_value_errors():
    t = BytesTest()
    t.test_constructor_value_errors()
    print('ok BytesTest.test_constructor_value_errors')


_BytesTest__test_constructor_value_errors()
