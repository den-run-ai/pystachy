# AbstractSet[T] values hold a set or a frozenset: read through len(), in, loops and comparisons,
# and as the other operand of a set's operators and methods (mypyc's dataflow analysis returns
# its gen and kill sets so, an empty pair of frozensets where an operation has none)
from collections.abc import Set as AbstractSet
from typing import Any, TypeVar

T = TypeVar("T")
GenAndKill = tuple[AbstractSet[T], AbstractSet[T]]
_EMPTY: tuple[frozenset[Any], frozenset[Any]] = (frozenset(), frozenset())


def size(s: AbstractSet[str]) -> int:
    return len(s)


def has(s: AbstractSet[str], k: str) -> bool:
    return k in s


def names(s: AbstractSet[str]) -> list[str]:
    return sorted([x for x in s])


def clean() -> GenAndKill[str]:
    return _EMPTY


def gen(name: str) -> GenAndKill[str]:
    return {name}, set()


def kill(name: str) -> GenAndKill[str]:
    return set(), frozenset({name})


def both(a: str, b: str) -> GenAndKill[str]:
    return frozenset({a}), {b}


def step(kind: int, name: str) -> GenAndKill[str]:
    if kind == 0:
        return clean()
    if kind == 1:
        return gen(name)
    if kind == 2:
        return kill(name)
    return both(name, name + "'")


def ints(flag: bool) -> AbstractSet[int]:
    if flag:
        return {3, 1, 2}
    return frozenset({20, 10})


print(size({"a", "b"}), size(frozenset({"c"})), size(set()), size(frozenset()))
print(has({"a"}, "a"), has(frozenset({"a"}), "b"), names(frozenset({"z", "y"})), names({"q"}))
live: set[str] = set()
dead: set[str] = set()
for kind, name in [(1, "x"), (0, "-"), (1, "y"), (2, "x"), (3, "z"), (0, "-"), (2, "y'"), (2, "z'")]:
    opgen, opkill = step(kind, name)
    if opkill:
        live -= opkill
    if opgen:
        live |= opgen
        dead -= opgen
    if opkill:
        dead |= opkill
    print(kind, name, len(opgen), len(opkill), bool(opgen), bool(opkill), sorted(live), sorted(dead))
g, k = clean()
print(len(g), len(k), bool(g), "x" in g, g == k, g == set(), k == frozenset(), sorted(live | g), sorted(live - k), sorted(live & g), live.isdisjoint(g), live.issuperset(k), g <= live)
for flag in [True, False]:
    s = ints(flag)
    print(len(s), 1 in s, 10 in s, sorted(s), sum([x for x in s]), sorted({x * 2 for x in s}), s == {1, 2, 3}, s == frozenset({10, 20}), {10} <= s, s >= {1, 2})
    copy = set(s)
    copy.add(99)
    frozen = frozenset(s)
    print(sorted(copy), sorted(frozen), len(s), copy, frozen == s, copy > s)
table: dict[str, AbstractSet[str]] = {"m": {"a"}, "f": frozenset({"b", "c"})}
print(sorted(table), [len(table[key]) for key in sorted(table)], "b" in table["f"], "b" in table["m"])
pairs: list[GenAndKill[str]] = [clean(), gen("p"), kill("q")]
print([(len(a), len(b)) for a, b in pairs])
