# The annotations suggested for mixed literal items preserve their CPython values.
def fail(value: int | float) -> None:
    xs = [1, value + None]
    print(xs)

def main() -> None:
    numbers: list[float | int] = [1, 2.5]
    scalars: list[float | int | str | None] = [1, "x", 2.5, None]
    rows: list[tuple[str, float | int]] = [("a", 1), ("b", 2.5)]
    nested: list[tuple[str, tuple[float | int, int | str]]] = [("a", (1, "x")), ("b", (2.5, 2))]
    print(numbers, scalars, rows, nested)
    print(isinstance(numbers[0], int), isinstance(numbers[1], float))
    try:
        fail(1)
    except TypeError:
        print("caught TypeError")

main()
