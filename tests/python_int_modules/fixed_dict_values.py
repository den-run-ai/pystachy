# A module that does not opt in: its dicts of tuples of ints hold checked 64-bit ints.
def first_value(d: dict[str, tuple[int, int]]) -> tuple[int, int]:
    return d["a"]


def put(d: dict[str, tuple[int, int]], k: str, a: int, b: int) -> None:
    d[k] = (a, b)


def total(d: dict[str, tuple[int, int]]) -> int:
    s = 0
    for a, b in d.values():
        s += a + b
    return s


def made() -> dict[str, tuple[int, int]]:
    return {"m": (-9223372036854775807 - 1, 1), "n": (2, -9223372036854775807 - 1)}


def edge() -> tuple[int, int]:
    return (-9223372036854775807 - 1, 5)
