# A module that does not opt in: its dicts of tuple keys and sets of tuples hold checked 64-bit ints.
def put(d: dict[tuple[int, int], str], n: int) -> None:
    d[(n, n)] = "fixed"
    d[(-9223372036854775807 - 1, n)] = "edge"


def get(d: dict[tuple[int, int], str], k: tuple[int, int]) -> str:
    return d.get(k, "missing")


def add(s: set[tuple[int, int]], n: int) -> None:
    s.add((n, n))
    s.add((-9223372036854775807 - 1, n))


def has(s: set[tuple[int, int]], t: tuple[int, int]) -> bool:
    return t in s


def total(s: set[tuple[int, int]]) -> int:
    t = 0
    for a, b in s:
        t += a + b
    return t


def first_key(d: dict[tuple[int, int], str]) -> tuple[int, int]:
    for k in d:
        return k
    return (0, 0)


def made() -> set[tuple[int, int]]:
    return {(-9223372036854775807 - 1, 1), (2, -9223372036854775807 - 1)}


def edge() -> tuple[int, int]:
    return (-9223372036854775807 - 1, 5)
