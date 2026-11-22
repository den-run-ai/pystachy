# error: expected int, got bool | int (a bool passes isinstance(x, int): int(x) is its int, and `not isinstance(x, bool)` narrows x to int)
# an int parameter would hold a bool that passed isinstance(x, int) as it is, which prints as True
def twice(n: int) -> int:
    return n * 2


def main() -> None:
    x: object = True
    if isinstance(x, int):
        print(twice(x))


main()
