# The annotations of async generators: AsyncGenerator[T, S], AsyncGenerator[T], AsyncIterator[T]
# and AsyncIterable[T], typing's and collections.abc's, as the return annotation of an async
# generator function or method (quoted too), and of a variable, a parameter and a field that hold
# async generators. -> AsyncIterator[Any] leaves the items' type to the first yield.
import collections.abc
import typing
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any, AsyncGenerator


async def ints() -> AsyncIterator[int]:
    yield 1
    yield 2


async def strs() -> typing.AsyncIterable[str]:
    yield "x"


async def floats() -> collections.abc.AsyncGenerator[float, None]:
    yield 1.5


async def pairs() -> AsyncGenerator[tuple[int, str]]:
    yield 1, "one"


async def quoted() -> "AsyncIterator[bool]":
    yield True


async def anything() -> AsyncIterator[Any]:
    yield [1, 2]


class Range:
    def __init__(self, n: int) -> None:
        self.n = n

    async def __aiter__(self) -> AsyncIterator[int]:
        for i in range(self.n):
            yield i


class Holder:
    def __init__(self, g: AsyncIterator[int]) -> None:
        self.g: AsyncIterator[int] = g


async def total(xs: AsyncIterable[int]) -> int:
    t = 0
    async for x in xs:
        t += x
    return t


async def main() -> None:
    g: AsyncIterator[int] = ints()
    print(await total(g))
    print(await total(Holder(ints()).g))
    async for s in strs():
        print(s)
    async for f in floats():
        print(f)
    async for n, w in pairs():
        print(n, w)
    async for b in quoted():
        print(b)
    async for xs in anything():
        print(xs, sum(xs))
    async for i in Range(3):
        print("range", i)


c = main()
try:
    c.send(None)
except StopIteration:
    print("done")
