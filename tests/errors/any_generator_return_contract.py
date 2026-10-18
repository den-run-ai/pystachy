# error: expected int, got str
from typing import Any, Generator


def values() -> Generator[Any, None, int]:
    yield 1
    return "wrong"


print(list(values()))
