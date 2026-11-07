# Complete state and byte-level checks for the pyperformance byte-BPE port.
# Expected ranks/IDs were derived from the pristine pinned upstream implementation
# under CPython 3.13.16. Keep this small: native execution also runs under GC stress.
from bpe_tokeniser import SimpleBytePairEncoding, bpe_encode, bpe_train


PATTERN = r"'s|'t|'re|'ve|'m|'ll|'d| ?[a-zA-Z]+| ?\d+| ?[^\sa-zA-Z\d]+|\s+(?!\S)|\s+"


def check_state(enc: SimpleBytePairEncoding, learned: list[bytes]) -> None:
    # Check every entry and its insertion order; a checksum cannot establish this.
    items = list(enc.mergeable_ranks.items())
    assert len(items) == 256 + len(learned)
    for i in range(256):
        assert items[i] == (bytes([i]), i)
    for i in range(len(learned)):
        assert items[256 + i] == (learned[i], 256 + i)


def check_text(enc: SimpleBytePairEncoding, text: str, expected: list[int]) -> None:
    tokens = enc.encode(text)
    assert tokens == expected
    assert enc.decode_bytes(tokens) == text.encode("utf-8")
    assert enc.decode(tokens) == text
    print(repr(text), tokens)


# A byte-complete vocabulary needs no corpus and encodes every possible byte,
# including bytes which cannot independently represent valid UTF-8 text.
base = SimpleBytePairEncoding.train("", 256, PATTERN)
check_state(base, [])
for i in range(256):
    value = bytes([i])
    assert bpe_encode(base.mergeable_ranks, value) == [i]
    assert base.decode_bytes([i]) == value
all_bytes = bytes([i for i in range(256)])
all_ids = [i for i in range(256)]
assert bpe_encode(base.mergeable_ranks, all_bytes) == all_ids
assert base.decode_bytes(all_ids) == all_bytes
assert bpe_encode(base.mergeable_ranks, b"") == []
assert base.decode_bytes([]) == b""
assert base.decode([]) == ""
print("all 256 bytes and empty input")

# Equal-frequency pairs choose their first occurrence in the corpus. The pattern
# retains whitespace, while splitting it into its own pretokenization boundary.
for corpus, learned in [("ab cd", [b"ab", b"cd"]), ("cd ab", [b"cd", b"ab"])]:
    tie = SimpleBytePairEncoding.train(corpus, 258, r"\S+|\s+")
    check_state(tie, learned)
    check_text(tie, corpus, [256, 32, 257])

# The trainer and encoder both merge overlapping equal-ranked pairs from the left.
overlap = SimpleBytePairEncoding.train("aaaaa", 259, PATTERN)
check_state(overlap, [b"aa", b"aaaa", b"aaaaa"])
overlap_cases: list[tuple[str, list[int]]] = [
    ("", []), ("a", [97]), ("aa", [256]), ("aaa", [256, 97]),
    ("aaaa", [257]), ("aaaaa", [258]), ("aaaaaa", [257, 256]),
    ("aaaaaaa", [257, 256, 97]),
]
for text, expected in overlap_cases:
    check_text(overlap, text, expected)
    assert bpe_encode(overlap.mergeable_ranks, text.encode("utf-8")) == expected

# Exact ordered training state, corpus IDs, and unseen input after training.
corpus = "banana bandana banana\nbanana\tbandana\n"
enc = SimpleBytePairEncoding.train(corpus, 264, PATTERN)
check_state(enc, [b"an", b"ban", b"ana", b"banana", b"band", b"bandana",
                  b" bandana", b" banana"])
assert bpe_train(corpus, 264, PATTERN) == enc.mergeable_ranks
check_text(enc, corpus, [259, 262, 263, 10, 259, 9, 261, 10])
check_text(enc, "bananas bandanas", [259, 115, 262, 115])
check_text(enc, "日本語 😀 ÆÉ Ġ e\u0301",
           [230, 151, 165, 230, 156, 172, 232, 170, 158, 32, 240, 159, 152, 128,
            32, 195, 134, 195, 137, 32, 196, 160, 32, 101, 204, 129])
check_text(enc, "a\u00a0b\u2003c", [97, 194, 160, 98, 226, 128, 131, 99])
check_text(enc, "x\v\fy", [120, 11, 12, 121])
check_text(enc, "don't won't I'll 123",
           [100, 111, 110, 39, 116, 32, 119, 111, 110, 39, 116, 32, 73, 39,
            108, 108, 32, 49, 50, 51])
check_text(enc, "  a\tb\r\nc \n\n", [32, 32, 97, 9, 98, 13, 10, 99, 32, 10, 10])
check_text(enc, "\x00\x01\x7f", [0, 1, 127])

# Training merges bytes, including partial UTF-8 sequences. Decoding must join all
# token bytes before decoding, so characters may span several tokens.
unicode_corpus = "日本語 😀 日本語 😀\nÆÉ Ġ e\u0301"
unicode_enc = SimpleBytePairEncoding.train(unicode_corpus, 268, PATTERN)
check_state(unicode_enc,
            [b"\xe6\x97", b"\xe6\x97\xa5", b"\xe6\x97\xa5\xe6",
             b"\xe6\x97\xa5\xe6\x9c", b"\xe6\x97\xa5\xe6\x9c\xac",
             b"\xe6\x97\xa5\xe6\x9c\xac\xe8", b"\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa",
             b"\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e", b" \xf0", b" \xf0\x9f",
             b" \xf0\x9f\x98", b" \xf0\x9f\x98\x80"])
check_text(unicode_enc, unicode_corpus,
           [263, 267, 32, 263, 267, 10, 195, 134, 195, 137, 32, 196, 160, 32, 101, 204, 129])
assert unicode_enc.decode_bytes([256, 165]) == "日".encode("utf-8")
assert unicode_enc.decode([256, 165]) == "日"

# Replacement happens per invalid UTF-8 subsequence, preserving valid neighbours.
decode_cases: list[tuple[list[int], str]] = [
    ([], ""), ([255], "�"), ([192, 128], "��"), ([226, 130], "�"),
    ([237, 160, 128], "���"), ([65, 128, 66], "A�B"),
    ([240, 159, 152, 128], "😀"), ([195, 134, 195, 137], "ÆÉ"),
]
for tokens, expected_text in decode_cases:
    assert enc.decode_bytes(tokens) == bytes(tokens)
    assert enc.decode(tokens) == expected_text
    print("decode", tokens, repr(expected_text))

# Preserve upstream rejection boundaries: a too-small vocabulary, a corpus with
# too few available merges, and token IDs absent from the decoder.
for size in [-1, 255]:
    rejected = False
    try:
        bpe_train("ab", size, PATTERN)
    except ValueError as exc:
        rejected = True
        assert str(exc) == "vocab_size must be at least 256, so we can encode all bytes"
        print("vocab", size, str(exc))
    assert rejected
for text, size in [("", 257), ("a", 257), ("ab", 258)]:
    rejected = False
    try:
        bpe_train(text, size, PATTERN)
    except ValueError as exc:
        rejected = True
        assert str(exc) == "max() iterable argument is empty"
        print("exhausted", repr(text), size, str(exc))
    assert rejected
for token in [-1, 264, 999999]:
    rejected = False
    try:
        enc.decode([token])
    except KeyError as exc:
        rejected = True
        assert str(exc) == str(token)
        print("token", token, str(exc))
    assert rejected
print("byte BPE checks complete")
