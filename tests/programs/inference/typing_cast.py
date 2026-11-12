# typing.cast(T, v) returns v unchanged, whatever T says; T types a display or a call it is.
import typing
from typing import cast

Row = list[float]


def first(xs: list[int]) -> int:
    return cast(int, xs[0])


def main() -> None:
    x = cast(int, 5)
    y = cast("str", "a")
    z = cast(list[float], [])
    z.append(1.5)
    w = typing.cast(Row, [])
    w.append(2.5)
    lie = cast(str, 7)
    f = cast(float, 1)
    d = cast("dict[str, list[int]]", {})
    d["k"] = [1]
    opt = cast("int | None", None)
    keys = cast("dict[str, int | None]", dict.fromkeys(["a", "b"]))
    print(x, y, z, w, lie + 1, f, type(f).__name__, d, opt, keys, first([4, 5]))


main()
