# Functions and classes Pystachy cannot compile: errors only where a program uses them.
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
