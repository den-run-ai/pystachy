from collections.abc import Generator, Iterator


def ascending(start: int, limit: int) -> Generator[int, None, int]:
    print("start", start)
    while start < limit:
        yield start
        start += 1
    return 42


def failing(start: int) -> Iterator[int]:
    yield -start
    raise ValueError("after yield")


def advance(it: Iterator[int]) -> int:
    return next(it, -1)


a = ascending(2, 4)
b = ascending(8, 10)
c = failing(5)
print("created")
print(advance(a), advance(b), advance(c))
print(advance(a), advance(a), advance(a))
try:
    print(advance(c))
except ValueError as error:
    print(str(error), advance(c))
b.close()
print(advance(b), advance(b))
