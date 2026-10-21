# Dict comprehensions: the key is evaluated before the value; a repeated key keeps its first
# position and takes the last value; the types come from the key and value, or from the dict
# type expected (an annotation, a parameter, a return type); the variables are the
# comprehension's own; errors propagate from the key, the value and the iteration
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")


def note(tag: str, v: int) -> int:
    print(tag, v)
    return v


def order() -> None:
    print({note("key", i) % 2: note("value", i) for i in range(4)})
    print({i % 3: i for i in range(10)})
    print({w[0]: w for w in ["apple", "avocado", "banana", "blueberry", "cherry"]})


def typed() -> None:
    words = ["héllo", "wörld", "", "abc"]
    d: dict[str, int | None] = {w: None for w in words if w}
    d["x"] = 5
    print(d)
    groups: dict[str, list[int]] = {w: [] for w in ["a", "b"]}
    groups["a"].append(1)
    print(groups)
    ratios: dict[int, float] = {i: i / 2 for i in range(3)}
    print(ratios)
    maybe: dict[str, int] | None = {w: len(w) for w in ["ab", "c"]}
    print(maybe)
    keyed = {(w, i): i * i for i, w in enumerate(["x", "y"])}
    print(keyed, keyed[("y", 1)])
    nested = {w: {c: i for i, c in enumerate(w)} for w in ["ab", "ba"]}
    print(nested)
    empty = {w: 0 for w in ["only"] if w != "only"}
    print(empty, len(empty))
    print({k: v for k, v in zip("abc", [1, 2, 3]) if v != 2})
    print({k: v * 10 for k, v in {"a": 1, "b": 2}.items()})
    print({x: x * x for x in {9, 3, 5}})
    print(sorted({k: 0 for k in [3, 1, 2]}), len({k: 0 for k in "aab"}), "a" in {k: 1 for k in "ab"})
    print(f"{ {k: 1 for k in 'ab'} }")


def pick(n: int) -> int | dict[str, int | None]:
    if n:
        return n
    return {k: None for k in "ab"}


def unions() -> None:
    v: dict[str, float] | list[int] = {k: 1.5 for k in "ab"}
    print(pick(0), pick(2), v)
    print({k: 1 for k in "ab"} == {"a": 1, "b": 1}, {k: [k] for k in "ab"} != {"a": ["a"]})


def scope() -> None:
    k = "outer k"
    v = -1
    xs = [1, 2]
    print({k: v for k, v in [("a", 1)]}, k, v)
    print({xs: len(xs) for xs in ["a", "bb"] if xs in ["a", "bb"]}, xs)


def errors() -> None:
    d = {"a": 1, "b": 2}
    try:
        print({k: d.pop(k) for k in d})
    except RuntimeError as e:
        print("RuntimeError", e)
    print(d)
    try:
        print({k: 10 // (k - 2) for k in range(4)})
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)
    try:
        print({{"a": 0}[w]: w for w in ["a", "b"]})
    except KeyError as e:
        print("KeyError", e)


def invert(d: dict[K, V]) -> dict[V, K]:
    return {v: k for k, v in d.items()}


def lengths(words: list[str]):
    return {w: len(w) for w in words}


def table(n: int) -> dict[int, list[int]]:
    return {i: [j for j in range(i)] for i in range(n)}


def total(d: dict[str, float]) -> float:
    return sum(d.values())


class Index(Generic[T]):
    def __init__(self, items: list[T]) -> None:
        self.items = items

    def positions(self) -> dict[T, int]:
        return {x: i for i, x in enumerate(self.items)}

    def counts(self) -> dict[T, int]:
        return {x: self.items.count(x) for x in self.items}


class Squares:
    table: dict[int, int] = {i: i * i for i in range(4)}

    def __init__(self, n: int) -> None:
        self.n = n
        self.cubes: dict[int, int] = {i: i * self.table[i] for i in range(n)}


def defaults(t: dict[str, int] = {k: 1 for k in "ab"}) -> dict[str, int]:
    return t


order()
typed()
unions()
scope()
errors()
print(invert({"a": 1, "b": 2}), invert({1: "x"}))
print(lengths(["ab", "world"]), table(3))
print(total({w: len(w) * 1.5 for w in ["ab", "c"]}))
ix = Index(["b", "a", "b"])
print(ix.positions(), ix.counts())
print(Index([3, 1]).positions())
print(Squares.table, Squares(3).cubes)
print(defaults(), defaults({"z": 0}))
module = {name: n for n, name in enumerate(["zero", "one", "two"])}
print(module, {v: k for k, v in module.items() if v})
