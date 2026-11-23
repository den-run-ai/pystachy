# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union, row frozenset: not stored


def pick(v: frozenset[int] | int) -> frozenset[int] | int:
    return v


def main() -> None:
    v = frozenset([3])
    x: frozenset[int] | int = pick(v)


main()
