"""Shared CPython/native checks of the column application's public helpers."""
import io

import column
import pytest


@pytest.fixture
def rows() -> list[list[str]]:
    return [["a", "bb"], ["long", "c"], ["z"]]


def test_widths_and_input_ownership(rows: list[list[str]]):
    assert column.widths(rows) == [4, 2]
    assert column.widths([]) == []
    assert rows == [["a", "bb"], ["long", "c"], ["z"]]


@pytest.mark.parametrize("right,expected", [
    (False, "a   |bb\nlong|c\nz\n"),
    (True, "   a|bb\nlong|c\n   z\n"),
])
def test_alignment(rows: list[list[str]], right: bool, expected: str):
    output = io.StringIO()
    columns: set[int] = {1} if right else set()
    column.align(rows, "|", columns, output)
    assert output.getvalue() == expected
    assert output.tell() == len(expected)
    output.close()


def test_column_numbers_are_unique():
    assert column.parse_columns("1,3,3") == {1, 3}


@pytest.mark.parametrize("text", ["0", "a", "1,,2", ""])
def test_invalid_column_numbers(text: str):
    with pytest.raises(ValueError, match="invalid column number"):
        column.parse_columns(text)
