# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row int: without `is`


def pick(v: int | str) -> int | str:
    return v


def main() -> None:
    x: int | str = pick(41)
    print(x is x, x is not x)


main()
