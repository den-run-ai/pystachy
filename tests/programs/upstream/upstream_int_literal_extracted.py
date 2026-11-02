# CPython 3.13.16 Lib/test/test_int_literal.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 2dd1dd8ca1e049abef5e5548179aba2532952f9f5362bc7c6d09bd73f80c5974),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: TestHexOctBin.test_bin_baseline, TestHexOctBin.test_hex_baseline,
#   TestHexOctBin.test_oct_baseline.
"""Test correct treatment of hex/oct constants.

This is complex because of changes due to PEP 237.
"""

class TestHexOctBin:

    def test_hex_baseline(self):
        assert 0 == 0
        assert 1 == 1
        assert 81985529216486895 == 81985529216486895
        assert 0 == 0
        assert 16 == 16
        assert 2147483647 == 2147483647
        assert 9223372036854775807 == 9223372036854775807
        assert -0 == 0
        assert -16 == -16
        assert -2147483647 == -2147483647
        assert -9223372036854775807 == -9223372036854775807
        assert -0 == 0
        assert -16 == -16
        assert -2147483647 == -2147483647
        assert -9223372036854775807 == -9223372036854775807

    def test_oct_baseline(self):
        assert 0 == 0
        assert 1 == 1
        assert 342391 == 342391
        assert 0 == 0
        assert 16 == 16
        assert 2147483647 == 2147483647
        assert 9223372036854775807 == 9223372036854775807
        assert -0 == 0
        assert -16 == -16
        assert -2147483647 == -2147483647
        assert -9223372036854775807 == -9223372036854775807
        assert -0 == 0
        assert -16 == -16
        assert -2147483647 == -2147483647
        assert -9223372036854775807 == -9223372036854775807

    def test_bin_baseline(self):
        assert 0 == 0
        assert 1 == 1
        assert 1365 == 1365
        assert 0 == 0
        assert 16 == 16
        assert 2147483647 == 2147483647
        assert 9223372036854775807 == 9223372036854775807
        assert -0 == 0
        assert -16 == -16
        assert -2147483647 == -2147483647
        assert -9223372036854775807 == -9223372036854775807
        assert -0 == 0
        assert -16 == -16
        assert -2147483647 == -2147483647
        assert -9223372036854775807 == -9223372036854775807


def _TestHexOctBin__test_bin_baseline():
    t = TestHexOctBin()
    t.test_bin_baseline()
    print('ok TestHexOctBin.test_bin_baseline')


def _TestHexOctBin__test_hex_baseline():
    t = TestHexOctBin()
    t.test_hex_baseline()
    print('ok TestHexOctBin.test_hex_baseline')


def _TestHexOctBin__test_oct_baseline():
    t = TestHexOctBin()
    t.test_oct_baseline()
    print('ok TestHexOctBin.test_oct_baseline')


_TestHexOctBin__test_bin_baseline()
_TestHexOctBin__test_hex_baseline()
_TestHexOctBin__test_oct_baseline()
