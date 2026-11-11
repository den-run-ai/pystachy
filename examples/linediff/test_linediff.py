"""Exact small diff reports, including final-newline and input-alias behavior."""
import linediff
import pytest


@pytest.mark.parametrize("start,stop,expected", [(0, 0, "0,0"), (0, 1, "1"), (2, 5, "3,3")])
def test_hunk_span(start: int, stop: int, expected: str):
    assert linediff.span(start, stop) == expected


def test_replacement_and_missing_final_newline():
    old = ["same\n", "old"]
    new = ["same\n", "new\n"]
    assert linediff.unified(old, new, 1, "before", "after") == [
        "--- before", "+++ after", "@@ -1,2 +1,2 @@", " same", "-old",
        "\\ No newline at end of file", "+new",
    ]
    assert old == ["same\n", "old"]
    assert new == ["same\n", "new\n"]


def test_equal_inputs_and_word_counts():
    assert linediff.unified(["same\n"], ["same\n"], 3, "a", "b") == []
    assert linediff.worddiff(["one old\n"], ["one new\n"]) == (["one [-old-] {+new+}"], 1, 1)
