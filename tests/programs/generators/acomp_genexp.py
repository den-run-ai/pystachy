# Asynchronous generator expressions (PEP 530): a generator expression with an async for clause
# or an await (outside its first iterable) is an async generator, also in a function that is not
# async; its first iterable, and that iterable's __aiter__(), are evaluated where it is written.
# async for, anext() and a comprehension take its items; an await in it suspends the coroutine that
# runs whatever iterates it.
import types


@types.coroutine
def tick(tag: str):
    yield tag


async def count(n: int):
    print("count", n, "starts")
    for i in range(n):
        yield i


async def double(x: int) -> int:
    await tick("double " + str(x))
    return 2 * x


class Source:
    def __aiter__(self):
        print("__aiter__ called")
        return Ticker()


class Ticker:
    def __init__(self) -> None:
        self.i = 0

    async def __anext__(self) -> str:
        self.i += 1
        if self.i > 2:
            raise StopAsyncIteration
        return "t" + str(self.i)


def squares(n: int):
    return (x * x async for x in count(n))


def tagged(s: Source):
    return (t + "!" async for t in s)


async def main() -> None:
    g = (x + 1 async for x in count(3))
    print("made")
    async for v in g:
        print("got", v)
    h = (await double(x) for x in range(2))
    print(await anext(h), await anext(h), await anext(h, -1))
    print([v async for v in squares(4)])
    t = tagged(Source())
    print("tagged made")
    print([v async for v in t])
    nested = (y async for x in count(2) async for y in count(x + 2) if y != x)
    print([v async for v in nested])


c = main()
try:
    while True:
        print("driver got", c.send(None))
except StopIteration:
    print("done")
