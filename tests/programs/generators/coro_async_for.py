# async for (PEP 492): __aiter__ once, then each item __anext__ gives, awaited, until it raises
# StopAsyncIteration; continue, break and the loop's else block; a StopAsyncIteration that the
# body raises is no end of the loop
import types


@types.coroutine
def tick(tag: str):
    yield tag


class Counter:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __aiter__(self):
        print("aiter")
        return self

    async def __anext__(self) -> int:
        await tick("next")
        if self.i >= self.n:
            raise StopAsyncIteration
        self.i += 1
        return self.i


class Pairs:
    def __init__(self) -> None:
        self.k = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> tuple[int, str]:
        self.k += 1
        if self.k > 3:
            raise StopAsyncIteration
        return self.k, "v" + str(self.k)


async def main() -> int:
    total = 0
    async for i in Counter(3):
        total += i
        if i == 2:
            continue
        print("item", i)
    else:
        print("loop else", total)
    async for i in Counter(5):
        if i == 2:
            break
    else:
        print("not reached")
    async for a, b in Pairs():
        print("pair", a, b)
    try:
        async for a, b in Pairs():
            raise StopAsyncIteration
    except StopAsyncIteration:
        print("the body's StopAsyncIteration propagates")
    async for i in Counter(0):
        print("not reached")
    else:
        print("empty")
    return total


c = main()
try:
    while True:
        print("yielded", c.send(None))
except StopIteration:
    print("done")
