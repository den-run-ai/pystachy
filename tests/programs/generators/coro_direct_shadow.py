# A name that an async def's own code binds, as a comprehension's target or by :=, is not the
# module's async def of that name: an await of a call of it runs what the name holds, so the
# function that awaits it stays a coroutine (no synchronous twin), and CPython's result follows.
async def g(x: int) -> int:
    return x + 1


async def h(x: int) -> int:
    return x * 10


async def in_comprehension() -> list[int]:
    return [await g(2) for g in [h, h]]


async def by_walrus() -> int:
    total = 0
    if (g := h) is not None:
        total = await g(3)
    return total


async def main() -> None:
    print(await in_comprehension())
    print(await by_walrus())
    print(await g(1))


try:
    main().send(None)
except StopIteration:
    print("done")
