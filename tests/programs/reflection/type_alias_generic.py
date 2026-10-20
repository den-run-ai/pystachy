# Generic type aliases: a type statement's type parameters (type Pair[T] = tuple[T, T]), or the
# TypeVars an assigned alias's value names (Pair = tuple[T, T]), are replaced by a
# subscript's type arguments, as in typing; nested and in templates, generic classes and
# methods. An assigned generic alias named without arguments is its value, TypeVars and all:
# a function annotated with it is a template, as with the TypeVars written out. A type
# statement's type parameter hides a module-level name (type Twice[Name]: not the alias Name).
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

Pair = tuple[T, T]
Mapping2 = dict[K, list[V]]
Maybe = Optional[T]
Fn = Callable[[T], T]
type Grid[C] = list[list[C]]
type Swap[A, B] = tuple[B, A]
type Rows[R] = list[Pair[R]]  # (a generic alias in another)
type Points = Rows[float]
Name = str
type Twice[Name] = tuple[Name, Name]


def swap(p: Pair[str]) -> Pair[str]:
    return (p[1], p[0])


def first(p: Pair[T]) -> T:
    return p[0]


def corner(g: Grid[float]) -> float:
    return g[0][0]


def flip(s: Swap[int, str]) -> Swap[str, int]:
    return (s[1], s[0])


def group(m: Mapping2[str, int], k: str) -> int:
    return sum(m.get(k, []))


def or_zero(x: Maybe[int]) -> int:
    return x if x is not None else 0


def twice(f: Fn[int], x: int) -> int:
    return f(f(x))


def spread(ps: Points) -> float:
    return max(p[1] for p in ps) - min(p[0] for p in ps)


def add(t: Twice[int], label: Name) -> str:
    return f"{label}={t[0] + t[1]}"


def ends(p: Pair) -> T:
    # (Pair without arguments: tuple[T, T], so this is a template)
    return p[1]


class Box(Generic[T]):
    def __init__(self, items: Grid[T]) -> None:
        self.items = items

    def at(self, p: Pair[int]) -> T:
        return self.items[p[0]][p[1]]

    def rows(self) -> Rows[int]:
        return [(len(r), len(r)) for r in self.items]


print(swap(("a", "b")), first((1, 2)), first(("x", "y")))
print(corner([[1.5, 2.0], [3.0]]), flip(("a", 1)))
print(group({"a": [1, 2], "b": [3]}, "a"), group({}, "z"))
print(or_zero(None), or_zero(5), twice(lambda n: n * 3, 2))
print(spread([(1.0, 4.5), (0.5, 2.0)]))
print(ends((1, 2)), ends(("é", "ü")), add((1, 2), "sum"))
b = Box([["a", "b"], ["c"]])
print(b.at((0, 1)), b.rows())
g: Grid[int] = []
g.append([1])
print(g)
