# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row list: without `is`


def pick(v: list[int] | int) -> list[int] | int:
    return v


def main() -> None:
    v: list[int] = [1, 2]
    x: list[int] | int = pick(v)
    print(x is x, x is not x)


main()
