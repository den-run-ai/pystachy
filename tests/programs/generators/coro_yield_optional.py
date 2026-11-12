# A coroutine that yields str awaits one that yields str | None (it also awaits a coroutine that
# never yields): its yield type becomes str | None, as an await that yields None makes it
import types


@types.coroutine
def tick():
    yield "t"


class Q:
    async def quiet(self) -> int:
        return 1


async def mixed() -> int:
    await tick()
    return await Q().quiet()


async def outer() -> int:
    await tick()
    return await mixed()


c = outer()
try:
    while True:
        print("yielded", c.send(None))
except StopIteration:
    print("done")
