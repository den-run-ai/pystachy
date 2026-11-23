# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row tuple: without `is`


def pick(v: tuple[int, str] | int) -> tuple[int, str] | int:
    return v


def main() -> None:
    v = (1, 's')
    x: tuple[int, str] | int = pick(v)
    print(x is x, x is not x)


main()
