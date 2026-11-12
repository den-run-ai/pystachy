# Frozensets are dict keys and set elements, hashed as hash() hashes them and compared as sets
# are: an equal frozenset finds the key whatever order its elements were added in. Their
# elements may be objects with __hash__ and __eq__, and frozensets.
class Key:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Key) and other.v == self.v

    def __hash__(self) -> int:
        return self.v * 7

    def __repr__(self) -> str:
        return f"Key({self.v})"


a = frozenset([1, 2, 3])
d = {a: "x", frozenset([4]): "y"}
print(d[frozenset([3, 2, 1])], d.get(frozenset([5]), "none"), frozenset([4]) in d, len(d))
d[frozenset([1, 2, 3])] = "z"
print(len(d), d[a], sorted(d.values()))
del d[frozenset([4])]
print(d)
try:
    print(d[frozenset([9])])
except KeyError as e:
    print("KeyError", e)
s = {frozenset(["a"]), frozenset(["a"]), frozenset(["b"])}
print(len(s), frozenset(["b"]) in s, frozenset(["c"]) in s)
s.add(frozenset(["c", "a"]))
s.discard(frozenset(["a"]))
print(sorted([sorted(x) for x in s]))
objects = {frozenset([Key(1), Key(2)]): 1}
print(objects[frozenset([Key(2), Key(1)])], frozenset([Key(3)]) in objects, objects)
nested = frozenset([frozenset([1]), frozenset([2, 3])])
print(len(nested), frozenset([3, 2]) in nested, frozenset([4]) in nested)
counts: dict[frozenset[str], int] = {}
for word in ["ab", "ba", "abc", "cab", "x"]:
    k = frozenset(word)
    counts[k] = counts.get(k, 0) + 1
print(sorted([("".join(sorted(k)), n) for k, n in counts.items()]))
