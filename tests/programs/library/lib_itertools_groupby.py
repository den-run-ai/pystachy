# itertools.groupby() (lib/_pystachy_itertools.py): keys and groups of consecutive items, the
# groups sharing the groupby's iterator as the C type's do: advancing the groupby ends the group
# before it, and the key function runs once for each item read, in CPython's order.
from itertools import groupby
from collections.abc import Iterator


def letters(word: str) -> Iterator[str]:
    for c in word:
        print("  read", c)
        yield c


class Key:
    # a key whose comparisons print, compared as CPython compares keys (the target key first)
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: "Key") -> bool:  # type: ignore[override]
        print("  eq", self.name, other.name)
        return self.name[0] == other.name[0]


print([k for k, g in groupby("AAAABBBCCDAABBB")], [list(g) for k, g in groupby("AAAABBBCCD")])
print([(k, list(g)) for k, g in groupby([1, 2, 3, 4, 5, 6, 7], lambda x: x // 3)])
print([(k, list(g)) for k, g in groupby(["a", "bb", "cc", "d"], len)], [(k, len(list(g))) for k, g in groupby(sorted("mississippi"))])
print([(k, list(g)) for k, g in groupby([(1, "a"), (1, "b"), (2, "c")], key=lambda p: p[0])])
empty: list[int] = []
print(len(list(groupby(empty))), [(k, list(g)) for k, g in groupby([5])], [k for k, g in groupby([1.0, 1.0, 2.0])])

# a group ends when the groupby moves on, read or not
groups = list(groupby("aabbbc"))
print([(k, list(g)) for k, g in groups])
gb = groupby([1, 1, 2, 2, 2, 3])
k1, g1 = next(gb)
print(k1, next(g1))
k2, g2 = next(gb)
print(k2, list(g1), next(g2), list(g2), list(g2))
k3, g3 = next(gb)
print(k3, list(g3), next(gb, None) is None)
gb2 = groupby(letters("aabc"))
print("made")
for k, g in gb2:
    print("key", k)
gb3 = groupby(letters("xxyz"))
k, g = next(gb3)
print(k, next(g))
print(next(g), next(g, "end"))

# the key function runs once for each item read
calls: list[int] = []


def key(x: int) -> int:
    calls.append(x)
    return x % 2


print([(k, list(g)) for k, g in groupby([1, 3, 2, 4, 5], key)], calls)
calls.clear()
print([k for k, g in groupby([1, 3, 2, 4, 5], key)], calls)

# keys compare with ==, the target key on the left; an object is equal to itself, as in CPython
a = Key("a1")
keys = [a, a, Key("a2"), Key("b1")]
print([(k.name, len(list(g))) for k, g in groupby(keys)])
print([k.name for k, g in groupby(keys)])

# a key that is not equal to itself (a NaN that a key function makes anew) still makes a group of
# its item, as in CPython, where the key compares as the very object it is
print([len(list(g)) for k, g in groupby([float("nan"), float("nan"), 1.0, 1.0])])
print([len(list(g)) for k, g in groupby([1, 2, 3], key=lambda v: float("nan"))])


def score(v: int) -> float:
    return float("nan") if v % 3 == 0 else float(v // 2)


print([(k, list(g)) for k, g in groupby(range(10), key=score)][1:4])
nans = groupby([float("nan"), float("nan")])
nan_key1, nan_group1 = next(nans)
nan_key2, nan_group2 = next(nans)
print(list(nan_group1), list(nan_group2), len(list(nans)))
