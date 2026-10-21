"""Subset widening, tuple item boxing and optional payloads retain their types."""
from typing import Union

def describe(value: int | float | bool | str | None) -> str:
    if isinstance(value, bool):
        return "bool:" + str(value)
    if isinstance(value, int):
        return "int:" + str(value)
    if isinstance(value, float):
        return "float:" + str(value)
    if isinstance(value, str):
        return "str:" + value
    return "none"

def tuple_values(flag: bool) -> tuple[int | str, float | str | None]:
    if flag:
        return (7, 1.5)
    return ("event", None)

def widen(value: int | str | None) -> int | str | float | None:
    return value

def optional_member(value: int | str | None) -> str:
    if not isinstance(value, str):
        # The remaining int | None uses the existing scalar-optional box layout.
        if value is None:
            return "none"
        return str(value + 1)
    return value.upper()

def duplicate(value: Union[int, str, int]) -> str:
    if isinstance(value, str):
        return value
    return str(value)

def snapshot() -> str:
    values: list[int | str] = ["kept"]
    old = values[0]
    values[0] = 9
    if isinstance(old, str):
        # The retained string must remain live through mutations and collections.
        for i in range(100):
            values.append(str(i) * 30)
        return old + ":" + describe(values[0])
    return "bad"

for flag in [True, False]:
    pair = tuple_values(flag)
    print(describe(pair[0]), describe(pair[1]))
print(describe(widen(3)), describe(widen("x")), describe(widen(None)))
print(optional_member(4), optional_member(None), optional_member("word"))
print(duplicate(4), duplicate("value"), snapshot())
