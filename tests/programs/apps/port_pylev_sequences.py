# pylev on sequences other than str (its docs speak of strings, and its code indexes and
# compares any sequence), and recursive_levenshtein's optional arguments: the lengths and
# offsets that select a slice of each sequence, and a memo shared between calls
import pylev

# lists of words: an edit is a whole word
wa = "the quick brown fox jumps over the lazy dog".split()
wb = "the quick red fox jumped over a lazy dog today".split()
print(pylev.levenshtein(wa, wb), pylev.wf_levenshtein(wa, wb), pylev.wfi_levenshtein(wb, wa),
      pylev.recursive_levenshtein(wa, wb), pylev.damerau_levenshtein(wa, wb),
      pylev.classic_levenshtein(wa[:4], wb[:4]))
empty: list[str] = []
print(pylev.levenshtein(wa, wa), pylev.damerau_levenshtein(["a", "b"], ["b", "a"]),
      pylev.levenshtein(empty, ["x"]), pylev.damerau_levenshtein(["x", "y"], empty))

# lists of ints, with the extremes of a 64-bit int as items
ia = [1, 2, 3, 4, 5, 6, 7, 8, 9223372036854775807]
ib = [2, 1, 3, 4, 6, 5, 7, 9, -9223372036854775807]
print(pylev.levenshtein(ia, ib), pylev.wf_levenshtein(ia, ib), pylev.damerau_levenshtein(ia, ib),
      pylev.damerau_levenshtein(ib, ia[:5]), pylev.recursive_levenshtein(ia, ib))

# recursive_levenshtein(string_1, string_2, len_1, len_2, offset_1, offset_2): the distance
# between string_1[offset_1:offset_1 + len_1] and string_2[offset_2:offset_2 + len_2]
print(pylev.recursive_levenshtein("kitten", "sitting", 3, 3))
print(pylev.recursive_levenshtein("xxkitten", "ysitting", 6, 7, 2, 1))
print(pylev.recursive_levenshtein("abc", "abd", 0, 2))
print(pylev.recursive_levenshtein("abc", "abd", len_2=1))
print(pylev.recursive_levenshtein("abcdef", "zzcdez", offset_1=2, offset_2=2, len_1=3, len_2=3))

# a memo passed in is filled with one entry per (offset_1, len_1, offset_2, len_2) visited;
# its keys do not name the strings, so a second call with other strings reads the first's
# results (upstream behaviour, kept)
memo: dict[str, int] = {}
print(pylev.recursive_levenshtein("flaw", "lawn", memo=memo), len(memo), memo["0,4,0,4"],
      memo["3,1,3,1"])
print(pylev.recursive_levenshtein("flaw", "lawn", memo=memo), len(memo))
print(pylev.recursive_levenshtein("abcd", "abcd", memo=memo), pylev.recursive_levenshtein("abcd", "abcd"))
