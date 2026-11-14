# Async generators (PEP 525): an async def that yields makes an async generator object when it is
# called, running none of its body; async for takes its items until it finishes (break, continue
# and the loop's else block), as does await of __anext__() and anext(), which raise
# StopAsyncIteration once it has finished. Its items' type comes from its first yield, or from its
# return annotation; an __aiter__ that is an async generator method makes a class async iterable.
from collections.abc import AsyncIterator


async def count(n: int):
    print("count starts")
    for i in range(n):
        yield i * 10
    print("count ends")


async def words() -> AsyncIterator[str]:
    yield "a"
    yield "b"


async def nothing() -> AsyncIterator[int]:
    if False:
        yield 0


class Pair:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b

    async def __aiter__(self) -> AsyncIterator[int]:
        yield self.a
        yield self.b


async def main() -> int:
    g = count(3)
    print("made")
    total = 0
    async for x in g:
        print("item", x)
        total += x
    async for x in count(5):
        if x == 10:
            continue
        if x == 30:
            break
        print("loop", x)
    else:
        print("not reached")
    async for w in words():
        async for x in count(2):
            print(w, x)
    else:
        print("nested done")
    async for x in nothing():
        print("not reached", x)
    else:
        print("empty")
    async for x in Pair(7, 8):
        print("pair", x)
    h = words()
    print(await h.__anext__(), await anext(h))
    try:
        await anext(h)
    except StopAsyncIteration:
        print("exhausted")
    try:
        await h.__anext__()
    except StopAsyncIteration:
        print("still exhausted")
    print(await anext(h, "default"))
    print(aiter(h) is h, h.__aiter__() is h)
    k = count(2)
    a = k.__anext__()
    print(type(k).__name__, type(a).__name__)
    print(await a)
    z = k.aclose()
    print(type(z).__name__)
    await z
    return total


c = main()
try:
    c.send(None)
except StopIteration:
    print("done")
