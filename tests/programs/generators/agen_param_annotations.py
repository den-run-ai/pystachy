# A function's parameter annotated AsyncIterator[T], AsyncIterable[T] or AsyncGenerator[T, S]
# takes an async generator whose awaits yield values to the code that runs it (which no annotation
# names), and an object of a class with __aiter__ and __anext__.
import types
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator


@types.coroutine
def tick(tag: str):
    yield tag


async def ticking(n: int):
    for i in range(n):
        await tick("tick " + str(i))
        yield i


async def quiet(n: int):
    for i in range(n):
        yield i * 10


class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __aiter__(self) -> "Countdown":
        return self

    async def __anext__(self) -> int:
        if self.n == 0:
            raise StopAsyncIteration
        self.n -= 1
        return self.n


async def total(xs: AsyncIterable[int]) -> int:
    t = 0
    async for x in xs:
        t += x
    return t


async def first(xs: AsyncIterator[int]) -> int:
    return await anext(xs, -1)


async def step(g: "AsyncGenerator[int, None]") -> int:
    return await g.__anext__()


async def main() -> None:
    print(await total(ticking(3)))
    print(await total(quiet(3)))
    print(await total(Countdown(4)))
    print(await first(ticking(2)), await first(quiet(0)), await first(Countdown(1)))
    print(await step(quiet(1)))


def drive(c) -> None:
    try:
        while True:
            print("driver got", c.send(None))
    except StopIteration:
        print("done")


drive(main())
