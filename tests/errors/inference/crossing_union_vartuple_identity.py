# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row vartuple: without `is`


def pick(v: tuple[int, ...] | int) -> tuple[int, ...] | int:
    return v


def main() -> None:
    v: tuple[int, ...] = (1, 2, 3)
    x: tuple[int, ...] | int = pick(v)
    print(x is x, x is not x)


main()
