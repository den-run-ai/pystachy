# @contextmanager methods whose names for the object, or whose classes, are what the method the
# loader writes reads: a subclass's receiver named as its class, receivers named args and kwds,
# and classes named args and kwds, with super() in an override
from contextlib import contextmanager
from typing import Iterator


class C:
    @contextmanager
    def scope(C, n: int = 1) -> Iterator[int]:
        yield 42 + n


class D(C):
    @contextmanager
    def scope(D, n: int = 1) -> Iterator[int]:
        with super().scope(n) as v:
            yield v * 10


class K:
    @contextmanager
    def scope(args, n: int = 1) -> Iterator[int]:
        yield n

    @contextmanager
    def other(kwds) -> Iterator[str]:
        yield "o"


class args:
    @contextmanager
    def scope(self, n: int = 1) -> Iterator[int]:
        yield n


class kwds(args):
    @contextmanager
    def scope(self, n: int = 1) -> Iterator[int]:
        with super().scope(n + 1) as v:
            yield v * 10


with D().scope(2) as w:
    print(w)
with K().scope(5) as v, K().other() as o:
    print(v, o)
with args().scope(5) as x, kwds().scope() as y:
    print(x, y)
