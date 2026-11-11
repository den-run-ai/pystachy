"""Bounded closed-union guard examples without unproved mutation effects."""


def scalar(value: int | str) -> int:
    if isinstance(value, int):
        return value + 1
    return len(value)


def optional(value: int | str | None) -> int:
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return len(value)
    return 0


print(scalar(3), scalar("abc"), optional(None), optional(7), optional("guard"))
