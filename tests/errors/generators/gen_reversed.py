# error: 'generator' object is not reversible
from collections.abc import Iterator


def nums() -> Iterator[int]:
    yield 1


for v in reversed(nums()):
    print(v)
