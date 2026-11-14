# Coroutines in a program without try or with statements: what they yield reaches the code that
# runs them, and awaits of coroutines that never suspend run them directly.
import types


@types.coroutine
def tick(n: int):
    yield n


async def double(x: int) -> int:
    return 2 * x


async def a() -> int:
    await tick(1)
    await tick(2)
    return await double(5)


async def b() -> int:
    v = await a() + 1
    print("b got", v)
    return v


c = b()
print(c.send(None))
print(c.send(None))
print(type(c).__name__)
