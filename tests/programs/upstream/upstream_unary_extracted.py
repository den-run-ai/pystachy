# CPython 3.13.16 Lib/test/test_unary.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 867adb0ac3eddbe957c0137a84f2dbac75bfd09c0a8b51e3e75a7af9eaa3f8eb),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: UnaryOpTestCase.test_invert, UnaryOpTestCase.test_negation_of_exponentiation.
"""Test compiler changes for unary ops (+, -, ~) introduced in Python 2.2"""

class UnaryOpTestCase:

    def test_invert(self):
        assert ~2 == -(2 + 1)
        assert ~0 == -1
        assert ~~2 == 2

    def test_negation_of_exponentiation(self):
        assert -2 ** 3 == -8
        assert (-2) ** 3 == -8
        assert -2 ** 4 == -16
        assert (-2) ** 4 == 16


def _UnaryOpTestCase__test_invert():
    t = UnaryOpTestCase()
    t.test_invert()
    print('ok UnaryOpTestCase.test_invert')


def _UnaryOpTestCase__test_negation_of_exponentiation():
    t = UnaryOpTestCase()
    t.test_negation_of_exponentiation()
    print('ok UnaryOpTestCase.test_negation_of_exponentiation')


_UnaryOpTestCase__test_invert()
_UnaryOpTestCase__test_negation_of_exponentiation()
