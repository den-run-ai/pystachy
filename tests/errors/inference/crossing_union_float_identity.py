# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row float: without `is`


def pick(v: float | str) -> float | str:
    return v


def main() -> None:
    x: float | str = pick(2.5)
    print(x is x, x is not x)


main()
