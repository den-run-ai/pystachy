# A function that returns iterators of different kinds returns an Iterator[T].
from typing import Iterator


def letters(n: int) -> Iterator[str]:
    for i in range(n):
        yield "abc"[i]


def source(kind: int):
    if kind == 0:
        return iter(["x", "y"])
    if kind == 1:
        return letters(2)
    return iter(("p", "q", "r"))


print([list(source(k)) for k in range(3)])
it = source(1)
print(next(it), next(it), next(it, "done"))
