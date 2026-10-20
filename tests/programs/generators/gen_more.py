# More generator forms (#490): closures that yield, defaults, *args, keyword arguments,
# generator methods overridden in a subclass, exceptions raised in a generator reaching the
# consumer (and its generator finished after), and a generator resuming itself.
from collections.abc import Iterator


def make(step: int):
    def gen(n: int) -> Iterator[int]:
        for i in range(0, n, step):
            yield i * step
    return gen


def rng(stop: int, start: int = 0, *extra: int) -> Iterator[int]:
    for i in range(start, stop):
        yield i
    for e in extra:
        yield e


class Base:
    def items(self) -> Iterator[str]:
        yield "base"


class Child(Base):
    def items(self) -> Iterator[str]:
        yield "child"
        yield "more"


def failing() -> Iterator[int]:
    yield 1
    raise KeyError("inside")


def counter() -> Iterator[int]:
    total = 0
    for i in range(3):
        total += i
        yield total


g2 = make(2)
print(list(g2(7)), list(make(3)(10)))
print(list(rng(3)), list(rng(5, 3)), list(rng(1, 0, 7, 8)), list(rng(start=2, stop=4)))
objs: list[Base] = [Base(), Child()]
for o in objs:
    print([s for s in o.items()])
f = failing()
try:
    for v in f:
        print("got", v)
except KeyError as e:
    print("caught", repr(e))
print("after", list(f), next(f, -1))
c = counter()
print(next(c), sum(c))
