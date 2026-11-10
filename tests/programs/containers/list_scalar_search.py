# in, index(), count() and remove() of lists of ints, bools and strs, which the runtime searches
# by their slots or bytes (pys_list_find's scalar paths): the range arguments' boundaries, strs
# equal to an item but other objects than it, the extreme ints, and removal until none is left.
# Lists of other items (str | None, lists) keep the general search
import sys

n = len(sys.argv) + 5  # (8, not a constant)
ints = [i * i % 11 for i in range(40)]
print(4 in ints, 6 in ints, 6 not in ints, ints.index(4), ints.index(4, 3), ints.index(4, -n), ints.index(9, 3, 20), ints.count(4), ints.count(6), ints.count(0))
for st, en in [(0, 0), (5, 2), (-1000, 1000), (39, 40), (40, 41), (-1, 40), (2, -2), (-3, -1)]:
    try:
        print(st, en, ints.index(5, st, en))
    except ValueError as e:
        print(st, en, "ValueError", e)
lim = [sys.maxsize, -sys.maxsize - 1, 0, -1, sys.maxsize]
print(sys.maxsize in lim, -sys.maxsize - 1 in lim, lim.index(-sys.maxsize - 1), lim.count(sys.maxsize), lim.index(sys.maxsize, 1), 1 in lim)
bools = [i % 3 == 0 for i in range(n)]
print(True in bools, False in bools, bools.index(False), bools.count(True), bools.index(True, 1), [False].count(True), True in [False] * n)
words = [("ab" * i)[: i % 5] for i in range(20)] + ["é", "é", "", "abab"]
key = "ab" + "ab"[: n - 6]  # ("abab", made at run time: another object than the items equal to it)
print(key in words, "aba" in words, "ba" in words, words.index(key), words.index(key, 5), words.index("", 1), words.count(key), words.count(""))
print(words.count("é"), words.index("é"), "e" in words, "é"[:0] in words)
empty_strs: list[str] = []
empty_ints: list[int] = []
print("" in empty_strs, 0 in empty_ints, empty_ints.count(1), "x" in ["x" * n], "x" * n in ["x" * n], "x\0y" in ["x\0z", "x\0y"], ["a", "b"].index("b"))
try:
    words.index("zz")
except ValueError as e:
    print("ValueError", e)
try:
    words.index(key, 20, 23)
except ValueError as e:
    print("ValueError", e)
while 4 in ints:
    ints.remove(4)
words.remove(key)
words.remove("")
print(ints.count(4), len(ints), words.count(key), words.index(""), len(words))
try:
    for _ in range(n):
        bools.remove(True)
except ValueError as e:
    print("ValueError", e, bools)
opt: list[str | None] = ["a", None, "b", None]
print(None in opt, "b" in opt, "c" in opt, opt.index(None), opt.count(None), opt.index("b"))
nested = [[1, 2], [3]]
print([3] in nested, [1] in nested, nested.index([3]), nested.count([1, 2]))
