# A module-level generator variable declared with Any and assigned later is typed by its value,
# as an initialized one is (once rejected).
from typing import Any, Generator


def values() -> Generator[int, None, None]:
    yield 1


g: Generator[Any, None, None]
g = values()
print(next(g), list(g))
