"""The pidigits kernel, whose promoting-int opt-in stays out of the typed workloads' programs."""
import pidigits


def test_pidigits():
    assert pidigits.calc_ndigits(20) == [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3, 2, 3, 8, 4]
