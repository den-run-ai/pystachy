# error: nums() is annotated to return no value (Iterator[T], Iterable[T] or Generator[Y, None, None]): annotate it Generator[Y, None, R] to return one
from collections.abc import Iterator


def nums() -> Iterator[int]:
    yield 1
    return 5


for v in nums():
    print(v)
