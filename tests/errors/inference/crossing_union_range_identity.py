# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row range: without `is`


def pick(v: range | int) -> range | int:
    return v


def main() -> None:
    x: range | int = pick(range(3))
    print(x is x, x is not x)


main()
