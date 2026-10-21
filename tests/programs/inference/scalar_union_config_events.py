"""Explicit scalar unions: typed configuration and event values."""
from typing import Union

def config(flag: int) -> int | str | None:
    if flag < 0:
        return None
    if flag == 0:
        return "auto"
    return flag

def describe(value: int | str | None) -> str:
    if value is None:
        return "missing"
    if isinstance(value, str):
        return "mode:" + value.upper()
    return "count:" + str(value + 1)

def branch(flag: bool) -> int:
    value: int | str = "start"
    if flag:
        value = 12
    else:
        value = "word"
    if isinstance(value, int):
        return value + 1
    return len(value)

def conditional(flag: bool) -> str:
    value: int | str = 42 if flag else "fast"
    if isinstance(value, str):
        return value
    return str(value)

def mutate(value: int | str) -> str:
    if isinstance(value, int):
        value = "changed"
    else:
        value = "same"
    return value.upper()

def wider(value: Union[int, str]) -> int | str | bool:
    return value

def scalar(value: int | float | bool | str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value + 10)
    if isinstance(value, float):
        return str(value + 0.5)
    return value.upper()

def optional_scalar(value: int | None) -> int | str | None:
    return value

for i in range(-1, 2):
    print(describe(config(i)))
print(branch(True), branch(False))
print(conditional(True), conditional(False))
print(mutate(1), mutate("word"))
print(describe(optional_scalar(None)), describe(optional_scalar(2)))
print(scalar(True), scalar(1), scalar(1.5), scalar("hello"))
print(scalar(wider(3)), scalar(wider("safe")))

# Mixed configuration values retain one explicit, finite element type.
def config_table() -> int:
    values: dict[str, int | str | None] = {"workers": 4, "mode": "auto", "unset": None}
    result = 0
    for key in values:
        value = values[key]
        if isinstance(value, int):
            result += value
        elif isinstance(value, str):
            result += len(value)
    values["workers"] = "disabled"
    print(describe(values["workers"]), describe(values["unset"]))
    return result

def events() -> str:
    values: list[int | str | None] = [1, "created", None]
    values.append(7)
    values[0] = "updated"
    result = ""
    for value in values:
        result += describe(value) + ";"
    return result

print(config_table(), events())
