# Asynchronous comprehensions (PEP 530) in an async def: list, set and dict comprehensions with an
# async for clause, first or later, mixed with for and if clauses, an await in the element, in a
# condition and in a later iterable; the async for clause takes items from an async generator, or
# from an object of a class with __aiter__ and __anext__, until StopAsyncIteration. The items of an
# await that suspends reach the code that runs the coroutine.
import types


@types.coroutine
def tick(tag: str):
    yield tag


async def count(n: int):
    for i in range(n):
        yield i


async def double(x: int) -> int:
    await tick("double " + str(x))
    return 2 * x


class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __aiter__(self):
        return self

    async def __anext__(self) -> int:
        if self.n == 0:
            raise StopAsyncIteration
        self.n -= 1
        return self.n


async def main() -> None:
    print([x async for x in count(4)])
    print([x async for x in count(5) if x % 2 == 0])
    print([(x, y) for x in range(2) async for y in count(2)])
    print([(x, y) async for x in count(2) for y in "ab"])
    print([(x, y) async for x in count(2) async for y in count(x + 1)])
    print([await double(x) async for x in count(2)])
    print([x async for x in count(4) if await double(x) > 2])
    print([y for x in range(2) for y in await make(x)])
    print({x % 3 async for x in count(7)})
    print({x: x * x async for x in count(3)})
    print([x async for x in Countdown(3)])
    print([[y async for y in count(x)] for x in range(3)])
    print(sum([x async for x in count(5)]))


async def make(n: int) -> list[int]:
    await tick("make")
    return list(range(n))


c = main()
try:
    while True:
        print("driver got", c.send(None))
except StopIteration:
    print("done")
