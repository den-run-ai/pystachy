# error: a function, bound method or lambda
# crossing matrix (tools/crossing_matrix.py), column object, row function: not stored


def helper(n: int) -> int:
    return n + 1


def main() -> None:
    x: object = helper


main()
