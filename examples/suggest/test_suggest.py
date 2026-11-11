"""Exercise spelling reports and their real difflib error boundaries."""
import pytest
import suggest


def test_word_locations_include_punctuation_and_extra_spaces():
    assert suggest.words('  "Hello," world!') == [(4, "hello"), (12, "world")]


def test_unknown_words_report_but_numbers_do_not():
    assert suggest.check(["hello wrld 123"], ["hello", "world"], 3, 0.75) == ["1:7: wrld: world"]
    assert suggest.check(["hello world"], ["hello", "world"], 3, 0.75) == []


@pytest.mark.parametrize("count,cutoff", [(0, 0.75), (1, -0.1), (1, 1.1)])
def test_invalid_match_options(count: int, cutoff: float):
    with pytest.raises(ValueError):
        suggest.check(["unknown"], ["word"], count, cutoff)
