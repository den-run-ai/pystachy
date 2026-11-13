# A generator yields the int member of a union it tested: the yielded word is that member's
# payload, which the IR check (PYSTACHY_IRCHECK=1, on in tests/run.sh) reads as the
# generator's element type, not as a raw slot word.
from typing import Iterator


def steps(n: int) -> Iterator[int]:
    s: int | str = n if n > 0 else "none"
    if isinstance(s, int):
        yield s
        yield s + 1


def ints(xs: list[int | str]) -> Iterator[int]:
    for x in xs:
        if isinstance(x, int):
            yield x


def labels(xs: list[int | str]) -> Iterator[str]:
    for x in xs:
        if isinstance(x, str):
            yield x


print(list(steps(2)), list(steps(0)))
print(list(ints([1, "a", 3, "b"])), list(labels([1, "a", 3, "b"])))
