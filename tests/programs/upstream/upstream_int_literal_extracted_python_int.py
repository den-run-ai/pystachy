# pystachy: python-int
# CPython 3.13.16 Lib/test/test_int_literal.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 2dd1dd8ca1e049abef5e5548179aba2532952f9f5362bc7c6d09bd73f80c5974),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# These tests need CPython's int, so the program opts in to promoting ints.
# Tests: TestHexOctBin.test_bin_unsigned, TestHexOctBin.test_hex_unsigned,
#   TestHexOctBin.test_oct_unsigned.
"""Test correct treatment of hex/oct constants.

This is complex because of changes due to PEP 237.
"""

class TestHexOctBin:

    def test_hex_unsigned(self):
        assert 2147483648 == 2147483648
        assert 4294967295 == 4294967295
        assert -2147483648 == -2147483648
        assert -4294967295 == -4294967295
        assert -2147483648 == -2147483648
        assert -4294967295 == -4294967295
        assert 9223372036854775808 == 9223372036854775808
        assert 18446744073709551615 == 18446744073709551615
        assert -9223372036854775808 == -9223372036854775808
        assert -18446744073709551615 == -18446744073709551615
        assert -9223372036854775808 == -9223372036854775808
        assert -18446744073709551615 == -18446744073709551615

    def test_oct_unsigned(self):
        assert 2147483648 == 2147483648
        assert 4294967295 == 4294967295
        assert -2147483648 == -2147483648
        assert -4294967295 == -4294967295
        assert -2147483648 == -2147483648
        assert -4294967295 == -4294967295
        assert 9223372036854775808 == 9223372036854775808
        assert 18446744073709551615 == 18446744073709551615
        assert -9223372036854775808 == -9223372036854775808
        assert -18446744073709551615 == -18446744073709551615
        assert -9223372036854775808 == -9223372036854775808
        assert -18446744073709551615 == -18446744073709551615

    def test_bin_unsigned(self):
        assert 2147483648 == 2147483648
        assert 4294967295 == 4294967295
        assert -2147483648 == -2147483648
        assert -4294967295 == -4294967295
        assert -2147483648 == -2147483648
        assert -4294967295 == -4294967295
        assert 9223372036854775808 == 9223372036854775808
        assert 18446744073709551615 == 18446744073709551615
        assert -9223372036854775808 == -9223372036854775808
        assert -18446744073709551615 == -18446744073709551615
        assert -9223372036854775808 == -9223372036854775808
        assert -18446744073709551615 == -18446744073709551615


def _TestHexOctBin__test_bin_unsigned():
    t = TestHexOctBin()
    t.test_bin_unsigned()
    print('ok TestHexOctBin.test_bin_unsigned')


def _TestHexOctBin__test_hex_unsigned():
    t = TestHexOctBin()
    t.test_hex_unsigned()
    print('ok TestHexOctBin.test_hex_unsigned')


def _TestHexOctBin__test_oct_unsigned():
    t = TestHexOctBin()
    t.test_oct_unsigned()
    print('ok TestHexOctBin.test_oct_unsigned')


_TestHexOctBin__test_bin_unsigned()
_TestHexOctBin__test_hex_unsigned()
_TestHexOctBin__test_oct_unsigned()
