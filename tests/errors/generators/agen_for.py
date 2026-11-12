# error: 'async_generator' object is not iterable: iterate it with async for
# a for loop over an async generator: CPython raises TypeError as it runs
async def ticks():
    yield 1


def main() -> None:
    for t in ticks():
        print(t)


main()
