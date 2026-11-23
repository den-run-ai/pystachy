# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row dict: without `is`


def pick(v: dict[str, int] | int) -> dict[str, int] | int:
    return v


def main() -> None:
    v: dict[str, int] = {'a': 1}
    x: dict[str, int] | int = pick(v)
    print(x is x, x is not x)


main()
