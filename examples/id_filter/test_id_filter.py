"""Independent set and document-scan oracles for the reusable ID-filter API."""
from idset import IdSet, from_ids
from search import SearchIndex, sample_documents
import pytest


@pytest.mark.parametrize("capacity", [0, 1, 62, 63, 64, 126, 127])
def test_word_boundaries_against_sets(capacity: int):
    left_values = list(range(0, capacity, 2))
    right_values = list(range(0, capacity, 3))
    left = from_ids(capacity, left_values)
    right = from_ids(capacity, right_values)
    a = set(left_values)
    b = set(right_values)
    assert left.intersection(right).ids() == sorted(a & b)
    assert left.union(right).ids() == sorted(a | b)
    assert left.difference(right).ids() == sorted(a - b)
    assert left.intersection_count(right) == len(a & b)
    assert left.storage_words() == (capacity + 62) // 63


def test_duplicates_and_returned_storage_are_independent():
    original = from_ids(64, [0, 62, 63, 63])
    copied = original.union(original)
    exported = original.ids()
    copied.discard(63)
    exported.append(1)
    assert original.ids() == [0, 62, 63]
    assert copied.ids() == [0, 62]


@pytest.mark.parametrize("value", [-1, 64])
def test_invalid_ids_do_not_mutate_mask(value: int):
    mask = IdSet(64)
    with pytest.raises(ValueError):
        mask.add(value)
    with pytest.raises(ValueError):
        mask.discard(value)
    with pytest.raises(ValueError):
        mask.contains(value)
    assert mask.count() == 0


def test_different_universes_reject_even_with_same_word_count():
    with pytest.raises(ValueError):
        IdSet(62).intersection(IdSet(63))


@pytest.mark.parametrize("language", ["en", "fr", "missing"])
def test_search_matches_independent_document_scan(language: str):
    documents = sample_documents()
    index = SearchIndex(documents)
    for tag in ["python", "compiler", "missing"]:
        expected: list[str] = []
        for title, lang, tags, blocked in documents:
            if lang == language and tag in tags.split() and not blocked:
                expected.append(title)
        assert index.matches(tag, language) == expected
        assert index.count(tag, language) == len(expected)
