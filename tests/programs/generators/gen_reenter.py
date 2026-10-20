# A generator that resumes itself raises ValueError: generator already executing (#490).
from collections.abc import Generator, Iterator

holder: list[Generator[int, None, None]] = []


def selfish() -> Iterator[int]:
    yield 1
    for v in holder[0]:
        yield v


g = selfish()
holder.append(g)
print(next(g))
print(next(g))
