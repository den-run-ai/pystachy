# pystachy: dynamic-any
from typing import Any


def compare(left: Any, right: Any) -> None:
    print(type(left).__name__, type(right).__name__, type(left) is type(right))
    print(iter(left) is left, iter(right) is right)
    print(next(left), next(right))


def positive(x: int) -> bool:
    return x > 0


compare(zip([1], [2]), zip(["a"], ["b"]))
compare(enumerate([3]), enumerate(["c"]))
compare(map(str, [4]), map(str, ["d"]))
compare(filter(None, [0, 5]), filter(positive, [0, 6]))
compare(reversed([7]), reversed([8]))
compare(reversed("é"), reversed((9,)))
compare(iter(range(1)), reversed(range(1)))
