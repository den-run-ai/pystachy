# isinstance(x, int) narrows a value of object to int | bool, as a bool passes it: a further
# 'not isinstance(x, bool)' leaves an int, which every int operation and parameter takes, and int(x)
# converts the bool to its int
def use(x: object) -> None:
    if isinstance(x, int) and not isinstance(x, bool):
        xs = [10, 20, 30, 40]
        n: int = x
        print(list(range(x)), xs[x], [0] * x, n + 1, max(x, 1), hex(x), x.bit_length())
    if isinstance(x, int):
        print(list(range(int(x))), int(x) + 1, x + 1, x * 2, x == 1, str(x))


def main() -> None:
    for o in [3, True, 2]:
        v: object = o
        use(v)


main()
