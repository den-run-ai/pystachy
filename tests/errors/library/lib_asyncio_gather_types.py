# error: expected Task[int], got Task[str]
# gather() makes a list of its awaitables' results, which must have one type here: of an int
# and a str, CPython's is [1, 'a'] (lib/compatibility.md#asyncio).
import asyncio


async def num() -> int:
    return 1


async def text() -> str:
    return "a"


async def main() -> None:
    print(await asyncio.gather(num(), text()))


asyncio.run(main())
