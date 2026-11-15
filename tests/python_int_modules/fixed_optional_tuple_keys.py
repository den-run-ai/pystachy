# This module deliberately retains fixed-width integer reads and annotations.
def add_fixed(values: set[tuple[int, str] | None]) -> None:
    values.add((-9223372036854775807 - 1, "fixed"))
    values.add(None)


def contains_fixed(values: set[tuple[int, str] | None]) -> bool:
    return (-9223372036854775807 - 1, "fixed") in values and None in values


def read_fixed(values: list[tuple[int, str] | None], index: int) -> tuple[int, str] | None:
    return values[index]


def read_nested(values: list[tuple[tuple[int, int] | None, str] | None], index: int) -> tuple[tuple[int, int] | None, str] | None:
    return values[index]
