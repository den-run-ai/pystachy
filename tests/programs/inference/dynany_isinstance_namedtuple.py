# pystachy: dynamic-any
# isinstance(x, tuple) of an Any value that holds a NamedTuple's object is true, as it is for the
# class itself and for namedtuple()'s (#1581). Such an object passes the test with its own layout,
# so the local stays an Any value after it: its class, its fields and its identity are the
# object's, not those of a tuple of its fields, and a tuple's own operations still read a tuple
from collections import namedtuple
from typing import Any, NamedTuple


class P(NamedTuple):
    x: int
    y: int


R = namedtuple("R", ["a", "b"])


class Plain:
    def __init__(self) -> None:
        self.v = 1


kept: list[Any] = []


def kinds(tag: str, v: Any) -> None:
    print(tag, isinstance(v, tuple), isinstance(v, (list, tuple)), isinstance(v, (int, tuple)), isinstance(v, P), isinstance(v, tuple | None))


def described(v: Any) -> str:
    # (the test narrows v to a tuple where no NamedTuple is boxed: here one is)
    if isinstance(v, tuple):
        kept.append(v)
        return f"{type(v).__name__}: equals (1, 2): {v == (1, 2)}, hashes as it: {hash(v) == hash((1, 2))}, {v!r}"
    return "no tuple"


def summed(v: Any) -> Any:
    # a tuple's own operations, on the values that are tuples
    if not isinstance(v, tuple):
        return None
    total = 0
    for item in v:
        if isinstance(item, int):
            total += item
    first, *rest = v
    return [len(v), v[0], v[-1], total, first, len(rest), 2 in v, v + (9,), v[0:1]]


values: list[Any] = [P(1, 2), R(1, "b"), (1, 2), (3,), Plain(), None, [1, 2], "ab", 7]
tags = ["P", "R", "tuple", "single", "plain", "none", "list", "str", "int"]
for i in range(len(values)):
    kinds(tags[i], values[i])
    print(described(values[i]), summed(values[i]) if tags[i] not in ["P", "R"] else "-")
print(kept)
print([isinstance(k, P) for k in kept], kept[0] is values[0], kept[0].x, kept[1].b)
