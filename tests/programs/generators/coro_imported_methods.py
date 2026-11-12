# async methods, plain and special (__aenter__, __aexit__, __anext__), of a class that an
# imported module defines, and that module's async def
from coro_box import Box, twice


async def main() -> int:
    total = await Box(4).get() + await twice(3)
    async with Box(1) as v:
        total += v
    async for i in Box(3):
        total += i
    print("total", total)
    return total


c = main()
try:
    c.send(None)
except StopIteration:
    print("done")
