# A module that does not opt in: its dicts, their items and the pairs it gives dict() hold checked
# 64-bit ints.
def pairs_of(d: dict[int, int]) -> list[tuple[int, int]]:
    return list(d.items())


def build(xs: list[tuple[int, int]]) -> dict[int, int]:
    return dict(xs)


def extend(d: dict[int, int], xs: list[tuple[int, int]]) -> None:
    d.update(xs)


def first(d: dict[int, int]) -> tuple[int, int]:
    return list(d.items())[0]


def edges() -> dict[int, int]:
    return dict([(1, -9223372036854775807 - 1), (-9223372036854775807 - 1, 2)])
