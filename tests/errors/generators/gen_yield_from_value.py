# error: the value of yield from is supported assigned to a variable (r = yield from g()); a yield from elsewhere in an expression is not
from collections.abc import Generator, Iterator


def sub() -> Generator[int, None, int]:
    yield 1
    return 2


def outer() -> Iterator[int]:
    print((yield from sub()))


print(list(outer()))
