# typing.AbstractSet[T]: a set or a frozenset read through its own operators and methods, whose
# results are AbstractSets too; and frozenset() that nothing types, empty for any element type
from typing import AbstractSet


def count(s: AbstractSet[str]) -> int:
    return len(s)


def pick(flag: bool) -> AbstractSet[int]:
    return {1, 2} if flag else frozenset({3})


print(count({"a"}), count(frozenset({"b", "c"})), count(frozenset()), count(set()))
print(sorted(pick(True)), sorted(pick(False)), pick(True) == {2, 1}, pick(False) == frozenset([3]), pick(True) | {9} == {1, 2, 9}, len(pick(False) | {9}), sorted(pick(False) - {3}), sorted(pick(True) & {2, 5}), sorted(pick(True) ^ pick(False)))
a = pick(True)
b = pick(False)
c = a | b
print(sorted(c), sorted(a.union(b, {7})), a.isdisjoint(b), a.issubset(c), c.issuperset(b), sorted(a.intersection({1})), sorted(a.difference({1})), sorted(a.symmetric_difference({1, 8})), sorted(a.copy()), len(set(a)), len(frozenset(b)))
e = frozenset()
print(e, bool(e), e == frozenset(), 3 in e, isinstance(e, frozenset), isinstance(e, set), (e, e), [1 for _ in range(2) if not e])
x: AbstractSet[str] = frozenset()
y: frozenset[str] = frozenset()
z: AbstractSet[str] = e
print(len(x), len(y), len(z), x == y, {"k"} | e == {"k"}, {"k"} - e == {"k"}, {"k"} & e == set(), e <= {"k"})
