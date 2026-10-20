# error: is annotated to return no value (Iterator[T], Iterable[T] or Generator[Y, None, None])
from typing import Any, Iterator


def values() -> Iterator[Any]:
    yield 1
    return 2


print(list(values()))
