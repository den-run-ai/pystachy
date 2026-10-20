# pylev's distance functions on strings: the cases of its own test suite (tests.py in the
# pylev repository, run under unittest there) as a program, then edge cases on every variant
# and alias: empty strings, swapped lengths, transpositions, control characters
import pylev
from pylev import damerau_levenshtein

print(pylev.__all__)
print(pylev.__version__, pylev.__author__, pylev.__license__)

# tests.py's test_data, each pair in both orders, for the three functions it tests
# (it leaves classic_levenshtein out as too slow; it runs on short pairs below)
TEST_DATA = [
    ("classic", "kitten", "sitting", 3),
    ("same", "kitten", "kitten", 0),
    ("empty", "", "", 0),
    ("a", "meilenstein", "levenshtein", 4),
    ("b", "levenshtein", "frankenstein", 6),
    ("c", "confide", "deceit", 6),
    ("d", "CUNsperrICY", "conspiracy", 8),
]
for name, a, b, expected in TEST_DATA:
    got = [
        pylev.recursive_levenshtein(a, b),
        pylev.recursive_levenshtein(b, a),
        pylev.wf_levenshtein(a, b),
        pylev.wf_levenshtein(b, a),
        pylev.wfi_levenshtein(a, b),
        pylev.wfi_levenshtein(b, a),
    ]
    print(name, expected, got, got == [expected] * 6)

# test_damerau_levenshtein
print(damerau_levenshtein("ba", "abc"), damerau_levenshtein("foobar", "foobra"),
      damerau_levenshtein("fee", "deed"))

# every variant and alias, damerau_levenshtein in both orders; classic_levenshtein, which
# takes exponential time, only on the short pairs
PAIRS = [
    ("", "abc"), ("abc", ""), ("a", "b"), ("flaw", "lawn"), ("gumbo", "gambol"),
    ("saturday", "sunday"), ("ab", "ba"), ("ca", "abc"), ("abcdef", "badcfe"),
    ("aaa", "aaaaaa"), ("aab", "aba"), ("a\x00b", "\x00ab"), ("\t\n", "\n\t"),
    ("Levenshtein", "Lenvinsten"), ("The quick brown fox", "The quack brown fax!"),
    ("x" * 20, "y" * 19), ("abcdefghij" * 3, "abdcefhgij" * 3),
]
for a, b in PAIRS:
    print(repr(a), repr(b), pylev.levenshtein(a, b), pylev.levenschtein(a, b),
          pylev.wf_levenshtein(a, b), pylev.wfi_levenshtein(a, b),
          pylev.recursive_levenshtein(a, b), damerau_levenshtein(a, b),
          damerau_levenshtein(b, a))
    if len(a) + len(b) <= 10:
        print("  classic", pylev.classic_levenshtein(a, b), pylev.classic_levenschtein(b, a))

# Pystachy's str holds UTF-8 bytes, and pylev counts edits of what len() and indexing count:
# the distances agree with CPython's where the edits touch only ASCII characters (naive /
# naif keep the i with diaeresis) or replace one character with another that differs from it
# in one byte (e acute / e grave), and not in general (PORT.md)
for a, b in [("naïve", "naïf"), ("é", "è")]:
    print(repr(a), repr(b), pylev.levenshtein(a, b), pylev.wf_levenshtein(a, b),
          damerau_levenshtein(a, b))
