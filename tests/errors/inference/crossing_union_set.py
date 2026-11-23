# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union, row set: not stored


def pick(v: set[int] | int) -> set[int] | int:
    return v


def main() -> None:
    v: set[int] = {3}
    x: set[int] | int = pick(v)


main()
