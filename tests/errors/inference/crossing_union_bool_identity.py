# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row bool: without `is`


def pick(v: bool | str) -> bool | str:
    return v


def main() -> None:
    x: bool | str = pick(True)
    print(x is x, x is not x)


main()
