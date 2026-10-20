# sqids's blocklist: the cases of its own tests/test_blocklist.py (sqids 0.5.2), run as a
# program instead of under pytest, with lists where they pass sets; ids the default blocklist
# blocks, by both of Sqids's ways of filtering it; and the property of tests/test_round_trip.py
# on fixed inputs instead of hypothesis's
import sys

from sqids import Sqids
from sqids.constants import DEFAULT_ALPHABET, DEFAULT_BLOCKLIST

# test_default_blocklist, test_empty_blocklist, test_custom_blocklist
for blocklist in [DEFAULT_BLOCKLIST, [], ["ArUO"]]:
    s = Sqids(blocklist=blocklist)
    print(s.decode("aho1e"), s.encode([4572721]), s.decode("ArUO"), s.encode([100000]))
    print(s.decode("QyG4"))

# test_blocklist: blocked whole ids, a word inside one, a word with a digit at either end
s = Sqids(blocklist=["JSwXFaosAN", "OCjV9JK64o", "rBHf", "79SM", "7tE6"])
print(s.encode([1000000, 2000000]), s.decode("1aYeB7bRUt"))
print(Sqids(blocklist=[]).encode([1000000, 2000000]))

# test_decoding_blocklist_words, test_match_against_short_blocklist_word
words = ["86Rf07", "se8ojk", "ARsz1p", "Q8AI49", "5sQRZO"]
s = Sqids(blocklist=words)
print([s.decode(w) for w in words], s.encode([1, 2, 3]))
s = Sqids(blocklist=["pnd"])
print(s.encode([1000]), s.decode(s.encode([1000])), Sqids(blocklist=[]).encode([1000]))

# test_blocklist_filtering_in_constructor: a lowercase word, an uppercase alphabet
upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
s = Sqids(alphabet=upper, blocklist=["sxnzkl"])
print(s.encode([1, 2, 3]), s.decode("IBSHOZ"), Sqids(alphabet=upper).encode([1, 2, 3]))

# test_alphabet_is_not_superset_of_blocklist_word_characters: such a word is dropped, and the
# ids are those of an empty blocklist (upstream reads the private fields by their mangled
# names); "BBC" (lowered, three letters) and "abab" are kept, and each blocks an id
plain = [Sqids(alphabet="abc", blocklist=[]).encode([n]) for n in range(12)]
for word in ["ab!", "abc!", "xyz", "BBC", "abab"]:
    s = Sqids(alphabet="abc", blocklist=[word])
    ids = [s.encode([n]) for n in range(12)]
    print(word, ids == plain, [n for n in range(12) if ids[n] != plain[n]])

# words the filter lowers, keeps as 3-letter words, puts at the ends (with a digit), or drops
# (too short, or with characters outside the alphabet)
print(Sqids().encode([63]), Sqids().encode([1]))
s = Sqids(blocklist=["UKK", "Uk1", "1uk", "ñañ", "éé1", "ab", "XYZ1", "zz9z"])
print(s.encode([63]), s.encode([1]), s.decode(s.encode([63])))

# a word given twice or in other cases, which upstream's sets hold once and the port's lists
# as often as given, and words of spaces or of nothing: the same ids
plain62 = [Sqids(blocklist=[]).encode([n]) for n in range(70)]
for bl in [["UKP", "ukp", "Ukp", "ukp"], ["bnn", "BNN", "gXZ", "gxz", "gxz"], ["", "   ", "a b"]]:
    s = Sqids(blocklist=bl)
    ids = [s.encode([n]) for n in range(70)]
    print(bl, [(n, ids[n]) for n in range(70) if ids[n] != plain62[n]],
          all(s.decode(ids[n]) == [n] for n in range(70)))

# test_max_encoding_attempts, test_small_words_are_ignored
s = Sqids("abc", 3, ["cab", "abc", "bca"])
try:
    print(s.encode([0]))
except ValueError as e:
    print("ValueError:", e)
print(Sqids().encode([0]), Sqids(blocklist=["bM"]).encode([0]))

# ids the default blocklist blocks: a word at the start or the end (with a digit), a word
# anywhere, two numbers; the same with the blocklist filtered by the constructor (a copy of
# the default blocklist, or the default alphabet as another str equal to it), and with a
# minimum length
blocked = [[21606], [152540], [15583], [125256], [3465, 42]]
alphabet_copy = "".join(list(DEFAULT_ALPHABET))
for min_length in [0, 8]:
    a = Sqids(min_length=min_length)
    b = Sqids(min_length=min_length, blocklist=list(DEFAULT_BLOCKLIST))
    c = Sqids(min_length=min_length, blocklist=[])
    d = Sqids(alphabet_copy, min_length)
    for numbers in blocked:
        x = a.encode(numbers)
        same = x == b.encode(numbers) and x == d.encode(numbers)
        print(min_length, numbers, c.encode(numbers), x, same, a.decode(x))

# test_round_trip.py's property: an id decodes to its numbers, and blocking it gives another
# id that does too
for alphabet in ["abc", "0123456789", "zyxwvutsrqponmlkjihgfedcba", "\x00\x7f ~!\n",
                 DEFAULT_ALPHABET]:
    for min_length in [0, 7]:
        for numbers in [[0], [1, 2, 3], [999, 0, 12345678], [sys.maxsize]]:
            s = Sqids(min_length=min_length, alphabet=alphabet, blocklist=[])
            id1 = s.encode(numbers)
            ok = s.decode(id1) == numbers
            line = f"{alphabet[:3]!r}/{len(alphabet)} {min_length} {numbers} {ok} {id1[:12]!r}"
            if len(id1) >= 3:
                s = Sqids(min_length=min_length, alphabet=alphabet, blocklist=[id1])
                id2 = s.encode(numbers)
                line += f" {id1 != id2} {s.decode(id2) == numbers} {id2[:12]!r}"
            print(line)
