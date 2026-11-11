"""Typed CSV aggregation cases usable by original pytest and native execution."""
import csv

import csvstat
import pytest


@pytest.mark.parametrize("values,kind", [
    (["", ""], "empty"), (["1", "2", "1"], "int"),
    (["1", "2.5", ""], "float"), (["1", "word"], "text"),
])
def test_column_type_transitions(values: list[str], kind: str):
    column = csvstat.Column("value")
    for value in values:
        column.add(value)
    assert column.kind() == kind
    assert sum(column.counts.values()) + column.empty == len(values)


def test_ragged_csv_preserves_empty_fields_and_counts_extra_rows():
    columns, count, longer = csvstat.collect(csv.reader(["a,b", "1,x", "2", "3,y,extra", ""]))
    assert count == 4
    assert longer == 1
    assert columns[0].kind() == "int"
    assert columns[0].empty == 1
    assert columns[1].counts == {"x": 1, "y": 1}
    assert columns[1].empty == 2


def test_integer_endpoints_remain_exact_past_float_precision():
    column = csvstat.Column("id")
    column.add("9007199254740992")
    column.add("9007199254740993")
    result = csvstat.statistics(column)
    assert result[:6] == ["int", "2", "0", "2", "9007199254740992", "9007199254740993"]
    assert result[-2:] == ["9007199254740992", "1"]


def test_sample_moments():
    assert csvstat.moments([1.0, 2.0, 3.0]) == (2.0, 2.0, 1.0)
