"""Original unittest-style and computed-table examples for the maintained roman port.

Add the repository's ports directory to PYTHONPATH/PYSTACHY_PATH when running.
"""

import unittest

import pytest
import roman

pytestmark = pytest.mark.ports

KNOWN = {1: "I", 4: "IV", 9: "IX", 14: "XIV", 40: "XL", 90: "XC", 400: "CD", 1994: "MCMXCIV", 2026: "MMXXVI"}


class KnownValues(unittest.TestCase):
    def setUp(self):
        self.numbers: list[int] = sorted(KNOWN)

    def test_to_roman(self):
        for number in self.numbers:
            with self.subTest(number=number):
                self.assertEqual(roman.toRoman(number), KNOWN[number])

    def test_from_roman(self):
        for number in self.numbers:
            self.assertEqual(roman.fromRoman(KNOWN[number]), number)


class RoundTrip(KnownValues):
    """Its two inherited tests run again on this class, as unittest collects them."""

    def test_round_trip(self):
        for number in range(1, 200):
            self.assertEqual(roman.fromRoman(roman.toRoman(number)), number)
        self.assertIn(1994, self.numbers)


class Errors(unittest.TestCase):
    def test_out_of_range(self):
        with self.assertRaises(roman.OutOfRangeError):
            roman.toRoman(5000)
        self.assertRaises(roman.OutOfRangeError, roman.toRoman, -1)

    def test_invalid_numeral(self):
        with self.assertRaisesRegex(roman.InvalidRomanNumeralError, "Invalid"):
            roman.fromRoman("IIII")

    @unittest.skip("lower-case numerals are not accepted")
    def test_lower_case(self):
        self.assertEqual(roman.fromRoman("xiv"), 14)


@pytest.mark.parametrize("number", range(1, 4))
def test_repeated_units(number):
    assert roman.toRoman(number) == "I" * number


@pytest.mark.parametrize("number, numeral", sorted(KNOWN.items()))
def test_known_pairs(number, numeral):
    assert roman.toRoman(number) == numeral


# (A value that a call makes has no ID the collector can read from the source: name it.)
@pytest.mark.parametrize("numeral", [roman.toRoman(n) for n in (5, 50, 500)], ids=["five", "fifty", "five-hundred"])
def test_computed_numerals(numeral):
    assert roman.fromRoman(numeral) in (5, 50, 500)
