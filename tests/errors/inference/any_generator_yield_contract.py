# error: expected int, got str
from typing import Any, Generator


def values() -> Generator[int, None, Any]:
    yield "wrong"
    return 1


print(list(values()))
