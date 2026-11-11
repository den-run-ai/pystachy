"""Shared field/character selection checks; CLI process tests remain separate."""
import cut
import pytest


def test_overlapping_ranges_merge():
    assert cut.parse_list("4-5,1-2,2-4,8") == [(1, 5), (8, 8)]
    assert cut.parse_list("-2,4-") == [(1, 2), (4, cut.END)]


@pytest.mark.parametrize("text", ["", "-", "0", "3-2", "1,,2", "a"])
def test_invalid_ranges(text: str):
    with pytest.raises(ValueError):
        cut.parse_list(text)


@pytest.mark.parametrize("complement,expected", [(False, "b|d"), (True, "a|c")])
def test_field_order_and_complement(complement: bool, expected: str):
    assert cut.cut_line("a,b,c,d", cut.parse_list("4,2"), True, ",", "|", False, complement) == expected


def test_undelimited_lines_and_unicode():
    ranges = cut.parse_list("2")
    assert cut.cut_line("plain", ranges, True, ",", "|", True, False) is None
    assert cut.cut_line("plain", ranges, True, ",", "|", False, False) == "plain"
    assert cut.cut_line("é界x", ranges, False, ",", "|", False, False) == "界"
