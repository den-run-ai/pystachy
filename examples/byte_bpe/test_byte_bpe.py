"""Byte-level tokenizer assertions shared by CPython pytest and native tests.

The existing recorded corpus and upstream benchmark replay retain the complete
ordered model/token comparisons; these cases provide individual test outcomes.
"""
from bpe_tokeniser import BPE_PATTERN, SimpleBytePairEncoding, bpe_encode, bpe_train
import pytest


@pytest.fixture
def byte_vocabulary() -> SimpleBytePairEncoding:
    return SimpleBytePairEncoding.train("", 256, BPE_PATTERN)


def test_every_byte_and_empty_input(byte_vocabulary: SimpleBytePairEncoding):
    tokenizer = byte_vocabulary
    assert len(tokenizer.mergeable_ranks) == 256
    for value in range(256):
        assert tokenizer.mergeable_ranks[bytes([value])] == value
        assert bpe_encode(tokenizer.mergeable_ranks, bytes([value])) == [value]
        assert tokenizer.decode_bytes([value]) == bytes([value])
    assert tokenizer.encode("") == []
    assert tokenizer.decode([]) == ""


@pytest.mark.parametrize("corpus,first,second", [
    ("ab cd", b"ab", b"cd"), ("cd ab", b"cd", b"ab"),
])
def test_training_ties_use_first_occurrence(corpus: str, first: bytes, second: bytes):
    tokenizer = SimpleBytePairEncoding.train(corpus, 258, r"\S+|\s+")
    assert list(tokenizer.mergeable_ranks.items())[256:] == [(first, 256), (second, 257)]
    assert tokenizer.encode(corpus) == [256, 32, 257]


@pytest.mark.parametrize("text,expected", [
    ("", []), ("a", [97]), ("aaa", [256, 97]),
    ("aaaaa", [258]), ("aaaaaaa", [257, 256, 97]),
])
def test_overlapping_merges_are_leftmost(text: str, expected: list[int]):
    tokenizer = SimpleBytePairEncoding.train("aaaaa", 259, BPE_PATTERN)
    assert tokenizer.encode(text) == expected
    assert tokenizer.decode(expected) == text


@pytest.mark.parametrize("text", ["日本語 😀 ÆÉ e\u0301", "a\u00a0b\u2003c", "\x00\x01\x7f"])
def test_unseen_unicode_roundtrip(byte_vocabulary: SimpleBytePairEncoding, text: str):
    tokens = byte_vocabulary.encode(text)
    assert tokens == list(text.encode("utf-8"))
    assert byte_vocabulary.decode_bytes(tokens) == text.encode("utf-8")
    assert byte_vocabulary.decode(tokens) == text


@pytest.mark.parametrize("tokens,expected", [
    ([255], "�"), ([226, 130], "�"), ([65, 128, 66], "A�B"),
    ([240, 159, 152, 128], "😀"),
])
def test_decode_replacement(byte_vocabulary: SimpleBytePairEncoding, tokens: list[int], expected: str):
    assert byte_vocabulary.decode_bytes(tokens) == bytes(tokens)
    assert byte_vocabulary.decode(tokens) == expected


@pytest.mark.parametrize("size", [-1, 255])
def test_too_small_vocabulary(size: int):
    with pytest.raises(ValueError, match="vocab_size must be at least 256"):
        bpe_train("ab", size, BPE_PATTERN)


def test_exhausted_training_pairs():
    with pytest.raises(ValueError):
        bpe_train("", 257, BPE_PATTERN)


@pytest.mark.parametrize("token", [-1, 256, 999999])
def test_unknown_token(byte_vocabulary: SimpleBytePairEncoding, token: int):
    with pytest.raises(KeyError):
        byte_vocabulary.decode([token])
