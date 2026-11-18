from typing import Iterator
from observe import observe, nested, pair
from producer import values, integers


def outer() -> Iterator[Iterator[float | None]]:
    yield values()


observe(values())
observe(integers())
nested(outer())
g = values()
first = next(g)
print("middle", next(g) is None)
pair(first, next(g))
