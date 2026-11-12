# error: an async generator function's return annotation must be AsyncIterator[T], AsyncIterable[T] or AsyncGenerator[T, S]
# as a generator function's must be Iterator[T], Iterable[T] or Generator[Y, S, R]
async def ticks() -> int:
    yield 1


async def main() -> None:
    async for t in ticks():
        print(t)


main().send(None)
