"""Scalar, reference and runtime-tag union boxes survive storage and collection."""


def int_member(value: int) -> int | str:
    return value


def float_member(value: float) -> float | str:
    return value


def bool_member(value: bool) -> bool | str:
    return value


def str_member(value: str) -> int | str:
    return value


def list_member(value: list[str]) -> int | list[str]:
    return value


def dict_member(value: dict[str, str]) -> int | dict[str, str]:
    return value


def optional_member(value: int | None) -> int | str | None:
    return value


def runtime_member(values: list[float]) -> int | float:
    total: int | float = 0
    for value in values:
        total += value
    return total


class Left:
    def __init__(self, name: str) -> None:
        self.name = name


class Right:
    def __init__(self, name: str) -> None:
        self.name = name


def reference_member(value: Left) -> Left | Right:
    return value


def retained() -> None:
    strings: list[int | str] = [str_member("string-" + str(i)) for i in range(8)]
    lists: list[int | list[str]] = [list_member(["list-" + str(i)]) for i in range(8)]
    dicts: list[int | dict[str, str]] = [dict_member({"key": "dict-" + str(i)}) for i in range(8)]
    objects: list[Left | Right] = [reference_member(Left("object-" + str(i))) for i in range(8)]
    alias = lists[3]
    lists[3] = 103
    for i in range(80):
        garbage = ["temporary-" + str(i), str(i) * 12]
        assert len(garbage) == 2
    if isinstance(alias, list):
        alias.append("retained alias")
        print(alias)
    print(strings, lists, dicts)
    print([item.name for item in objects])
    # Replacing a scalar box by a reference allocates a new box; the old scalar
    # box's kind cannot be reused for a pointer-bearing payload.
    mixed: list[int | str] = [int_member(1000)]
    old = mixed[0]
    mixed[0] = str_member("replacement-" + str(1000))
    print(old, mixed)


print(int_member(-9223372036854775808), int_member(9223372036854775807))
print(float_member(-0.0), float_member(1.25), bool_member(True), bool_member(False))
print(optional_member(None), optional_member(1234))
print(runtime_member([]), runtime_member([0.25, 1.5]))
retained()
