# An await in an async generator passes what its awaitable yields on to the code that runs the
# coroutine that iterates it, as CPython's asend awaitable does, and resumes it with what that
# code sends; the items go to the async for. Async generators that iterate async generators, async
# with in one, an await of a coroutine that suspends, and send() of None, throw() and close() of
# the driven coroutine, which reach the async generator through the step that runs it.
import types


@types.coroutine
def tick(tag: str):
    yield tag


async def pause(tag: str) -> int:
    await tick(tag)
    return len(tag)


class Lock:
    async def __aenter__(self) -> str:
        await tick("enter")
        return "locked"

    async def __aexit__(self, t, v, tb) -> None:
        await tick("exit")


async def source(n: int):
    for i in range(n):
        await tick("before " + str(i))
        yield i
        k = await pause("after")
        print("source resumed", k)


async def doubled(n: int):
    async for x in source(n):
        yield x * 2
    async with Lock() as l:
        yield len(l)


async def main() -> None:
    async for x in doubled(2):
        print("main got", x)


def drive(c) -> None:
    try:
        while True:
            print("driver got", c.send(None))
    except StopIteration:
        print("finished")


drive(main())


async def guarded():
    try:
        await tick("waiting")
        yield 1
    except KeyError as e:
        print("guarded caught", repr(e))
        await tick("handled")
        yield 2
    finally:
        print("guarded finally")


async def consumer() -> None:
    async for x in guarded():
        print("consumer got", x)


c = consumer()
print(c.send(None))
print(c.throw(KeyError("k")))
try:
    c.send(None)
except StopIteration:
    print("consumer finished")
c = consumer()
print(c.send(None))
c.close()
print("closed")
