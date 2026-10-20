# error: typing.Any is only supported in the parameter and return annotations of a function
from typing import Any, Generator


def values() -> Generator[int, None, None]:
    yield 1


g: Generator[Any, None, None]
g = values()
