# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row str: without `is`


def pick(v: str | int) -> str | int:
    return v


def main() -> None:
    x: str | int = pick('text')
    print(x is x, x is not x)


main()
