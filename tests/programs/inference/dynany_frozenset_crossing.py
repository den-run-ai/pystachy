# pystachy: dynamic-any
# A frozenset of Any values where a frozenset[T] or an AbstractSet[T] is expected: nothing changes
# a frozenset, so it crosses as a tuple does, its elements checked as T's (docs/dynamic-any.md).
# The typed set holds them as the frozenset did: it is iterated in the same order, and no
# __hash__ or __eq__ runs for it. mypyc's dataflow analysis returns its shared empty pair so.
from collections.abc import Set as AbstractSet
from typing import Any, TypeVar

T = TypeVar("T")
GenAndKill = tuple[AbstractSet[T], AbstractSet[T]]
_EMPTY: tuple[frozenset[Any], frozenset[Any]] = (frozenset(), frozenset())
calls = [0, 0]


class Reg:
    def __init__(self, name: str) -> None:
        self.name = name


class Key:
    def __init__(self, n: int) -> None:
        self.n = n

    def __hash__(self) -> int:
        calls[0] += 1
        return self.n % 4

    def __eq__(self, other: object) -> bool:
        calls[1] += 1
        return isinstance(other, Key) and other.n == self.n


def clean() -> GenAndKill[str]:
    return _EMPTY


def strs(s: frozenset[Any]) -> AbstractSet[str]:
    return s


def ints(s: frozenset[Any]) -> frozenset[int]:
    return s


def regs(s: frozenset[Any]) -> AbstractSet[Reg]:
    return s


def keys(s: frozenset[Any]) -> frozenset[Key]:
    return s


def maybe(s: frozenset[Any], some: bool) -> frozenset[str] | None:
    if some:
        return s
    return None


def pair(a: frozenset[Any], b: frozenset[Any]) -> tuple[AbstractSet[int], frozenset[str]]:
    return a, b


def size(s: AbstractSet[str]) -> int:
    return len(s)


gen, kill = clean()
print(len(gen), len(kill), gen == kill, size(gen))
live: set[str] = {"x"}
live |= gen
live -= kill
print(live)

words: frozenset[Any] = frozenset(["pear", "fig", "apple", "kiwi", "plum", "date", "lime"])
ws = strs(words)
print(len(ws), "fig" in ws, "nut" in ws, sorted(ws), [w for w in ws] == [w for w in words])
live |= ws
print(len(live), ws <= live, ws == frozenset(["pear", "fig", "apple", "kiwi", "plum", "date", "lime"]))

small: frozenset[Any] = frozenset([16, 0, 8, -1, 24, 3])
many: frozenset[Any] = frozenset([i * 37 % 101 - 50 for i in range(60)])
for src in [small, many]:
    ns = ints(src)
    print(len(ns), [n for n in ns] == [n for n in src], -1 in ns, 8 in ns, 1000 in ns, sum(ns))
print([n for n in ints(small)], sorted(ints(small) | {100}))

a = Reg("a")
b = Reg("b")
rs = regs(frozenset([a, b, a]))
print(len(rs), a in rs, b in rs, Reg("a") in rs, sorted([r.name for r in rs]))

made: frozenset[Any] = frozenset([Key(1), Key(5), Key(9), Key(2), Key(1)])
before = [calls[0], calls[1]]
ks = keys(made)
print(len(ks), calls[0] - before[0], calls[1] - before[1], [k.n for k in ks] == [k.n for k in made])
print(Key(5) in ks, Key(6) in ks, sorted([k.n for k in ks]))

print(maybe(words, False), maybe(frozenset(["z"]), True))
pi, ps = pair(small, frozenset(["s", "t"]))
print(sorted(pi), sorted(ps))
