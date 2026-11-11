"""Compare heap and sorting selection through the original application API."""
import pytest
import topk


@pytest.mark.parametrize("limit", [-1, 0, 1, 3, 20])
def test_heap_selection_matches_sort_with_ties(limit: int):
    words: dict[str, int] = {}
    pairs: dict[tuple[str, str], int] = {}
    total = topk.count(["Red blue red!", "blue green."], words, pairs)
    assert total == 5
    assert words == {"red": 2, "blue": 2, "green": 1}
    assert pairs == {("red", "blue"): 1, ("blue", "red"): 1, ("blue", "green"): 1}
    assert topk.pick(limit, words, pairs, False) == topk.pick(limit, words, pairs, True)


def test_punctuation_and_empty_lines_do_not_create_words():
    words: dict[str, int] = {}
    pairs: dict[tuple[str, str], int] = {}
    assert topk.count(["", "... !!!", "A\tB"], words, pairs) == 2
    assert words == {"a": 1, "b": 1}
    assert pairs == {("a", "b"): 1}
