# Functions, classes and methods Pystachy cannot compile: errors only where a program uses them.
class Base:
    def __init__(self, v: int) -> None:
        self.v = v


class Derived(Base):
    pass


class Registry:
    def __init__(self, name: str) -> None:
        self.entries = {}


class Node:
    def __init__(self, v: int) -> None:
        self.v = v
        self.kids: list["Node"] = []


def to_bytes(x: bytes) -> bytes:
    return x


def options(**kwargs: int) -> int:
    return len(kwargs)


def uses(d: Derived) -> int:
    return d.v


def first[T](xs: list[T]) -> T:
    return xs[0]


async def collect(it):
    return [x async for x in it]


def ok() -> str:
    return "ok"


class Blob:
    data: bytes = b""


import typing as t


def head(n: t.Optional[Node]) -> int:
    return n.v if n is not None else -1


def names(xs: t.List[str]) -> t.Dict[str, int]:
    return {x: len(x) for x in xs} if False else {"n": len(xs)}


def setup() -> None:
    pass


class Hooks:
    def __init__(self) -> None:
        self.ready = setup()


from typing import Iterable


def total(xs: Iterable[int]) -> int:
    return sum(xs)


def maybe(x: int | None) -> int:
    return 0 if x is None else x


def by_weight(d: dict[float, Node]) -> int:
    return len(d)


class Weights:
    keys: dict[float, int]


class Cell:
    def __init__(self) -> None:
        self.held: int | None = None


class Bag:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self):
        return self.n


class Pair:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pair) and other.x == self.x


def mk() -> list[int]:
    return [1]


def defaults(xs: Iterable[int] = [1, 2], d: dict[float, str] = {}) -> int:
    return 0


def template(x, ys: Iterable[int], y: int | None = None) -> int:
    return x


class Probe:
    def helper(self) -> int | None:
        return 3

    def __init__(self) -> None:
        self.x = self.helper()

    def scan(self, xs: Iterable[int] = mk()) -> int:
        return 0
