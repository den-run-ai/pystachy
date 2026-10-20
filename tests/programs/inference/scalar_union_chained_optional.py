"""Chained isinstance guards refine the current optional member type."""


def after_bool(value: bool | str | None) -> str:
    if isinstance(value, bool):
        return "bool:" + str(value)
    if isinstance(value, str):
        return value
    return "none"


def after_int(value: int | str | None) -> str:
    if isinstance(value, int):
        return str(value + 1)
    if isinstance(value, str):
        assert isinstance(value, str)
        return value
    return "none"


def after_str(value: int | str | None) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, int):
        assert isinstance(value, int)
        return value
    return -1


print(after_bool(True), after_bool(False), after_bool("word"), after_bool(None))
print(after_int(3), after_int("word"), after_int(None))
print(after_str(3), after_str("word"), after_str(None))
