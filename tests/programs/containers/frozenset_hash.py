# hash() of a frozenset is CPython's (frozenset_hash): it depends only on its elements' hashes,
# whatever order they were added in, so a frozenset of ints hashes alike in every run. Its
# elements may be objects hashed by their class's __hash__, and frozensets themselves; a tuple
# holding a frozenset hashes it as its item (mypyc's RUnion: hash(("union", items))).
class Key:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Key) and other.v == self.v

    def __hash__(self) -> int:
        return self.v * 7


ints = frozenset([1, 2, 3])
empty: frozenset[int] = frozenset()
print(hash(ints), hash(frozenset([3, 2, 1, 2])) == hash(ints), hash(empty))
print(hash(frozenset([-1])), hash(frozenset([0])), hash(frozenset(range(100))))
print(hash(frozenset(["a", "b"])) == hash(frozenset(["b", "a"])))
keys = frozenset([Key(1), Key(2), Key(1)])
print(len(keys), hash(keys), hash(keys) == hash(frozenset([Key(2), Key(1)])))
nested = frozenset([frozenset([1]), frozenset([2, 3])])
print(hash(nested), hash(nested) == hash(frozenset([frozenset([3, 2]), frozenset([1])])))
print(hash((1, ints)), hash((1, ints)) == hash((1, frozenset([3, 1, 2]))), hash((7, keys)))
print(hash(("union", keys)) == hash(("union", frozenset([Key(2), Key(1)]))))
