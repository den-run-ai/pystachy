# typing's forms that only a type checker reads: collections.abc's names (Mapping[K, V] is a
# dict, Sequence[T] a list), Final (bare, the type of its value, or Final[T]) and @overload
# stubs, which the def after them replaces; in the program and in an imported module.
from collections.abc import MutableSequence, Iterable, Callable
import collections.abc as cabc
from typing import Final, Mapping, MutableMapping, Sequence, overload
import typing as t
from mods.typed import LIMIT, NAMES, Named, get, keys, total

GREETING: Final = "hello"
COUNTS: Final[dict[str, int]] = {"a": 1}
SIZES: Final = [1, 2, 3]


def grow(xs: MutableSequence[str], m: Mapping[str, Sequence[int]]) -> int:
    xs.append(GREETING)
    return len(xs) + sum([len(v) for v in m.values()])


def merge(a: cabc.Mapping[str, int], b: MutableMapping[str, int]) -> MutableMapping[str, int]:
    for k, v in a.items():
        b[k] = b.get(k, 0) + v
    return b


@overload
def pick(x: int) -> int: ...
@t.overload
def pick(x: str) -> str: ...
def pick(x: str) -> str:
    return x.upper()


class Box:
    label: Final[str]
    items: Sequence[int]

    def __init__(self, label: str, items: list[int]) -> None:
        self.label = label
        self.items = items

    @overload
    def get(self, i: int) -> int: ...
    @overload
    def get(self, i: str) -> int: ...
    def get(self, i: int) -> int:
        return self.items[i]


def local_final(n: int) -> int:
    k: Final = 7
    m: Final[int] = n * k
    return m


xs = ["x"]
print(grow(xs, {"p": [1, 2], "q": []}), xs)
print(merge({"a": 2, "b": 1}, COUNTS), COUNTS, SIZES)
print(pick("abc"), Box("b", [4, 5]).get(1), Box("c", []).label, local_final(3))
print(LIMIT, NAMES, get(4), total([1, 2]), keys({"b": 1, "a": 2}, {"z": []}, {3: 3}))
n = Named("n")
print(n.name, n.twice(21), GREETING)
