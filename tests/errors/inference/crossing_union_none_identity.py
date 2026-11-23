# error: 'is' is only supported for objects and None
# crossing matrix (tools/crossing_matrix.py), column union, row none: without `is`


def pick(v: int | None) -> int | None:
    return v


def main() -> None:
    x: int | None = pick(None)
    print(x is x, x is not x)


main()
