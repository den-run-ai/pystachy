# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row complex: without `is`


def pick(v: complex | str) -> complex | str:
    return v


def main() -> None:
    x: complex | str = pick((1 + 2j))
    print(x is x, x is not x)


main()
