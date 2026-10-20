# error: generator values cannot be compared or printed
from collections.abc import Iterator


def nums() -> Iterator[int]:
    yield 1


print(nums())
