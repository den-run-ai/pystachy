# isinstance() with each class of collections.abc, as CPython's ABCs answer: the builtin types they
# register, lib's mappings, deque, range and iterators, and classes by the methods they define (__eq__
# without __hash__, a dataclass's eq) or by the ABC they derive from (its views too)
from collections import OrderedDict, defaultdict, deque, Counter
from collections.abc import (Callable, Collection, Container, Generator, Hashable, ItemsView, Iterable, Iterator, KeysView,
                             Mapping, MappingView, MutableMapping, MutableSequence, MutableSet, Reversible, Sequence, Set, Sized,
                             ValuesView)
from dataclasses import dataclass
from typing import NamedTuple


class Plain:
    pass


class Sizey:
    def __len__(self) -> int:
        return 1

    def __iter__(self):
        return iter([1])

    def __contains__(self, x: int) -> bool:
        return True


class Eq:
    def __eq__(self, other: object) -> bool:
        return True


class EqHash(Eq):
    def __hash__(self) -> int:
        return 1


class Calls:
    def __call__(self) -> int:
        return 1


@dataclass
class D:
    x: int


@dataclass(frozen=True)
class F:
    x: int


class P(NamedTuple):
    x: int


class Lower(MutableMapping):
    def __init__(self) -> None:
        self.d: dict[str, int] = {}

    def __getitem__(self, k: str) -> int:
        return self.d[k.lower()]

    def __setitem__(self, k: str, v: int) -> None:
        self.d[k.lower()] = v

    def __delitem__(self, k: str) -> None:
        del self.d[k.lower()]

    def __iter__(self):
        return iter(self.d)

    def __len__(self) -> int:
        return len(self.d)


def gen():
    yield 1


def f() -> int:
    return 1


m = Lower()
m["a"] = 1
abcs = ["Hashable", "Iterable", "Iterator", "Reversible", "Sized", "Container", "Collection", "Callable", "Generator",
        "Sequence", "MutableSequence", "Set", "MutableSet", "Mapping", "MutableMapping", "MappingView", "KeysView", "ItemsView",
        "ValuesView"]


def row(name: str, bits: list[bool]) -> None:
    print(name.ljust(10), "".join(["1" if b else "." for b in bits]))


def check(x) -> list[bool]:
    return [isinstance(x, Hashable), isinstance(x, Iterable), isinstance(x, Iterator), isinstance(x, Reversible),
            isinstance(x, Sized), isinstance(x, Container), isinstance(x, Collection), isinstance(x, Callable),
            isinstance(x, Generator), isinstance(x, Sequence), isinstance(x, MutableSequence), isinstance(x, Set),
            isinstance(x, MutableSet), isinstance(x, Mapping), isinstance(x, MutableMapping), isinstance(x, MappingView),
            isinstance(x, KeysView), isinstance(x, ItemsView), isinstance(x, ValuesView)]


row("int", check(1))
row("float", check(1.5))
row("bool", check(True))
row("None", check(None))
row("str", check("s"))
row("bytes", check(b"s"))
row("list", check([1]))
row("tuple", check((1, 2)))
row("dict", check({"a": 1}))
row("set", check({1}))
row("frozenset", check(frozenset([1])))
row("gen", check(gen()))
row("func", check(f))
row("class", check(Plain))
row("Plain", check(Plain()))
row("Sizey", check(Sizey()))
row("Eq", check(Eq()))
row("EqHash", check(EqHash()))
row("Calls", check(Calls()))
row("D", check(D(1)))
row("F", check(F(1)))
row("P", check(P(1)))
row("range", check(range(3)))
row("deque", check(deque([1])))
row("odict", check(OrderedDict([("a", 1)])))
dd: defaultdict[str, int] = defaultdict(int)
row("ddict", check(dd))
row("Counter", check(Counter("ab")))
row("iter", check(iter([1])))
row("Lower", check(m))
row("keys", check(m.keys()))
row("items", check(m.items()))
row("values", check(m.values()))
