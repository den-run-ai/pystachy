# A module that does not opt in: its tuples hold checked 64-bit ints, also those its lists hold.
def total(xs: list[tuple[int, int]]) -> int:
    s = 0
    for a, b in xs:
        s += a + b
    return s


def push(xs: list[tuple[int, int]], a: int, b: int) -> None:
    xs.append((a, b))


def first(xs: list[tuple[int, int]]) -> tuple[int, int]:
    return xs[0]


def made() -> list[tuple[int, int]]:
    return [(1, -9223372036854775807 - 1), (-9223372036854775807 - 1, 5)]
