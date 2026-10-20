# error: a generator's send type cannot contain Any: annotate Generator[Y, S, R] with a concrete send type S that may be None
from typing import Any, Generator


def receive() -> Generator[int, Any, None]:
    value = yield 1
    print(value)


print(next(receive()))
