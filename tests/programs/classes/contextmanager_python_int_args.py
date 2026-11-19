# pystachy: python-int
from contextlib import contextmanager
from typing import Iterator
class Scope:
    @contextmanager
    def opened(self, x: int, *, extra: int = 0) -> Iterator[int]:
        print(x, extra)
        yield 1

def absent() -> Scope | None:
    return None

for value in [3, 2**80]:
    with Scope.opened(absent(), value, extra=value) as result:
        print(result)

@Scope.opened(absent(), 2**80, extra=2**81)
def inner() -> int:
    return 7

print(inner(), inner())
