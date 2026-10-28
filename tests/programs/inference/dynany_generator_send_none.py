# pystachy: dynamic-any
# This program deliberately has no send()/throw(): the no-protocol lowering
# must still provide a real None box to an Any send channel.
from typing import Any, Generator


def values() -> Generator[int, Any, None]:
    first = yield 1
    print("first", first is None, first)
    second = yield 2
    print("second", second is None, second)


print(list(values()))
it = values()
print(next(it), next(it))
try:
    next(it)
except StopIteration:
    print("done")
