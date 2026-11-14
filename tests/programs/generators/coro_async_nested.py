# async with and async for in an async def and in a coroutine closure it defines, whose hidden
# locals have the same names; the closure's yields join the outer coroutine's (str | None)
import types


@types.coroutine
def tick():
    yield "t"


class CM:
    def __init__(self, n: str) -> None:
        self.n = n

    async def __aenter__(self):
        await tick()
        return self.n

    async def __aexit__(self, *a):
        print("exit", self.n)


class Two:
    def __init__(self) -> None:
        self.k = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> int:
        self.k += 1
        if self.k > 2:
            raise StopAsyncIteration
        await tick()
        return self.k


async def outer(tag: str) -> str:
    async def inner(x: int) -> str:
        async with CM(tag + "-inner" + str(x)) as v:
            async for k in Two():
                print("inner", v, k)
        return v

    out = ""
    async with CM(tag) as w:
        async for i in Two():
            out += await inner(i)
    return w + ":" + out


c = outer("o")
n = 0
try:
    while True:
        c.send(None)
        n += 1
except StopIteration:
    pass
print("suspensions", n)


async def show() -> None:
    print(await outer("p"))

d = show()
try:
    while True:
        d.send(None)
except StopIteration:
    pass
