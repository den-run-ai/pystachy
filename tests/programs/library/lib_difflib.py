# lib/difflib.py: CPython 3.13's difflib with its marked edits (lib/README.md), against CPython's
# own: SequenceMatcher over strs and lists of lines, and get_close_matches. Cases after CPython's
# Lib/test/test_difflib.py and the module's doctests.
import difflib
from difflib import SequenceMatcher, get_close_matches


def show(s):
    print(round(s.ratio(), 6), round(s.quick_ratio(), 6), round(s.real_quick_ratio(), 6))
    print(s.get_matching_blocks())
    print(s.get_opcodes())


show(SequenceMatcher(None, "abcd", "bcde"))
show(SequenceMatcher(None, "b" * 100, "a" + "b" * 100))
show(SequenceMatcher(None, "b" * 100, "b" * 50 + "a" + "b" * 50))
show(SequenceMatcher(None, "a" * 40 + "c" + "b" * 40, "a" * 40 + "b" * 40))
show(SequenceMatcher(None, "qabxcd", "abycdf"))
show(SequenceMatcher(None, "", ""))
show(SequenceMatcher(None, "abc", ""))
show(SequenceMatcher(None, "", "abc"))
show(SequenceMatcher(None, "same text", "same text"))

# junk: a function of an element, and the popular elements of a long b (autojunk)
s = SequenceMatcher(lambda x: x == " ", "private Thread currentThread;", "private volatile Thread currentThread;")
print(round(s.ratio(), 3), s.get_matching_blocks(), sorted(s.bjunk))
s = SequenceMatcher(None, " abcd", "abcd abcd")
print(s.find_longest_match(0, 5, 0, 9), s.find_longest_match())
s = SequenceMatcher(lambda x: x == " ", " abcd", "abcd abcd")
print(s.find_longest_match(0, 5, 0, 9), s.find_longest_match(1), s.find_longest_match(0, 3, 4))
s = SequenceMatcher(isjunk=lambda x: x in [" ", "b"], a="a" * 40 + "b" * 40, b="a" * 44 + "b" * 40 + " " * 20)
print(sorted(s.bjunk), round(s.ratio(), 6), s.get_opcodes())
seq1 = "b" * 200
seq2 = "a" + "b" * 200
s = SequenceMatcher(None, seq1, seq2)
print(round(s.ratio(), 6), sorted(s.bpopular), s.get_opcodes())
s = SequenceMatcher(None, seq1, seq2, autojunk=False)
print(round(s.ratio(), 6), sorted(s.bpopular), s.get_opcodes())


def blank(line: str) -> bool:
    return line.strip() == ""


# lists of lines, as diff tools compare them
a = ["one\n", "two\n", "three\n", "\n", "four\n", "five\n", "six\n"]
b = ["zero\n", "one\n", "tree\n", "four\n", "\n", "five\n", "six\n", "seven\n"]
show(SequenceMatcher(None, a, b))
ls = SequenceMatcher(blank, a, b)
print(ls.get_opcodes(), sorted(ls.bjunk))
for tag, i1, i2, j1, j2 in ls.get_opcodes():
    print(f"{tag:7} a[{i1}:{i2}] {a[i1:i2]!r} b[{j1}:{j2}] {b[j1:j2]!r}")
empty: list[str] = []
show(SequenceMatcher(None, empty, empty))
show(SequenceMatcher(None, a, empty))

# set_seq1/set_seq2/set_seqs reuse what they can, and the caches of a pair
s = SequenceMatcher(None, "abxcd", "abcd")
first = s.get_matching_blocks()
print(first is s.get_matching_blocks(), s.get_opcodes() is s.get_opcodes(), [m.size for m in first])
s.set_seq1("bcde")
print(round(s.ratio(), 6), s.get_opcodes())
s.set_seq2("abcd")
print(round(s.ratio(), 6), s.get_opcodes())
s.set_seqs("kitten", "sitting")
show(s)
m = s.get_matching_blocks()[0]
print(m.a, m.b, m.size, m[2], m == (m.a, m.b, m.size), len(m))
i, j, k = m
print(i, j, k)

# get_close_matches: the best n with a ratio of at least cutoff, best first
words = ["ape", "apple", "peach", "puppy", "apply", "appeal", "maple", "pale", "apples"]
print(get_close_matches("appel", ["ape", "apple", "peach", "puppy"]))
print(get_close_matches("appel", words), get_close_matches("appel", words, n=5))
print(get_close_matches("appel", words, n=2, cutoff=0.8), get_close_matches("zzz", words), get_close_matches("pech", words, 1, 0.5))
print(get_close_matches("wheel", ["while", "with", "where", "wheel", "yield", "else"]), get_close_matches("", words))
for n, cutoff in [(0, 0.6), (-1, 0.6), (3, 1.5), (3, -0.1)]:
    try:
        get_close_matches("appel", words, n, cutoff)
    except ValueError as e:
        print("ValueError:", e)
print(difflib.IS_CHARACTER_JUNK(" "), difflib.IS_CHARACTER_JUNK("\t"), difflib.IS_CHARACTER_JUNK("\n"), difflib.IS_CHARACTER_JUNK("x"))
print(difflib.IS_LINE_JUNK("\n"), difflib.IS_LINE_JUNK("  #   \n"), difflib.IS_LINE_JUNK("hello\n"), difflib.IS_LINE_JUNK("#"))

# difflib's own junk functions, and an unannotated function, as isjunk
s2 = SequenceMatcher(difflib.IS_CHARACTER_JUNK, "a b\tc", "a  b c")
print(s2.get_opcodes(), sorted(s2.bjunk))


def hash_junk(x):
    return x == "#"


print(SequenceMatcher(hash_junk, "a#b", "ab#").get_opcodes())
lj = SequenceMatcher(difflib.IS_LINE_JUNK, ["a\n", "\n", "b\n"], ["a\n", "b\n", "#\n", "  \n"])
print(lj.get_opcodes(), sorted(lj.bjunk))

# get_opcodes() and get_matching_blocks() return lists (never None), cached or not
def tags(codes: list[tuple[str, int, int, int, int]]) -> str:
    return " ".join([c[0] for c in codes])


s3 = SequenceMatcher(None, "abcdef", "abXdeZf")
print(tags(s3.get_opcodes()), tags(s3.get_opcodes()))
blocks: list[difflib.Match] = s3.get_matching_blocks()
print(blocks == s3.get_matching_blocks(), sum([m.size for m in blocks]))
