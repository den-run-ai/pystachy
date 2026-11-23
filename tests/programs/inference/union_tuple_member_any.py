# pystachy: dynamic-any
# A union's tuple member crosses into Any as the tuple it holds.
from typing import Any


def pick(k: int) -> int | tuple[int, str]:
    if k == 0:
        return 7
    return (7, "seven")


def main() -> None:
    v = pick(1)
    a: Any = v
    print(a, v, a == v, isinstance(a, tuple), len(a))
    xs: list[Any] = [pick(0), pick(1)]
    print(xs, xs[1][1])
    b: Any = pick(0)
    print(b + 1, isinstance(b, tuple))


main()
