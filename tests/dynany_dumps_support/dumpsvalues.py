# pystachy: dynamic-any
# A module that opts in and gives Any values to programs that do not
# (tests/programs/inference/dynany_dumps_caller*.py): json.dumps() of them is the dynamic
# encoder's there too (docs/dynamic-any.md#json-values).
from typing import Any


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


def table(n: int) -> Any:
    rows: list[Any] = [n, "two", 3.5, None, True, [n, {"k": (1, 2)}]]
    return {"rows": rows, "n": n, "t": (n, "é"), "big": 2**62}


def scalar(kind: str) -> Any:
    if kind == "int":
        return 10**3
    if kind == "float":
        return 0.1
    if kind == "str":
        return 'a"b'
    if kind == "bool":
        return False
    return None


def ring() -> Any:
    xs: list[Any] = [1]
    xs.append(xs)
    return xs


def nan_row() -> Any:
    return [1.5, float("nan"), float("inf")]


def point() -> Any:
    return Point(1, 2)


def with_point() -> Any:
    return {"p": Point(3, 4), "n": [Point(5, 6)]}


def encode(o: Any) -> Any:
    if isinstance(o, Point):
        return [o.x, o.y]
    raise TypeError("not a point")
