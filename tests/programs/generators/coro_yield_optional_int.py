# As coro_yield_optional.py with int yields, whose int | None is a box: the next compile pass
# gives the coroutine that type from the start, and its awaits box what they pass on
import types


@types.coroutine
def tick():
    yield 7


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
