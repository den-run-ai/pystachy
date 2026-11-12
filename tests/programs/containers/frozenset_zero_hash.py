# A frozenset whose CPython hash is 0 (of one K, whose __hash__ gives this value) keeps that hash
# in a dict or set of such keys, which keep CPython's hashes: set(d), frozenset(d), differences,
# intersections and an enclosing frozenset find it
class K:
    def __init__(self, n: int) -> None:
        self.n = n

    def __hash__(self) -> int:
        return 5969340177766309242

    def __eq__(self, other: object) -> bool:
        return isinstance(other, K)


k = frozenset([K(1)])
print(hash(k))
d = {k: 1}
s = set(d)
print(k in s, k in d, frozenset([K(2)]) in s, frozenset(d) == frozenset([k]))
print(len(s - {k}), len({k} - s), len(s ^ {k}), len(s & {k}))
n = frozenset([k])
print(hash(n) == hash(frozenset([frozenset([K(3)])])), n in set({n: 3}), set({n: 4}) == {n})
