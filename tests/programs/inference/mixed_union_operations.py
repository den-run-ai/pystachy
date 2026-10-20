"""Generic scalar operations compose with explicitly bounded container values."""

def render(value: int | str | None | list[int | str | None] | dict[str, int | str | None]) -> str:
    if isinstance(value, list):
        return repr(value) + ":" + str(0 in value) + ":" + str(value.count(False))
    if isinstance(value, dict):
        return repr(value) + ":" + str(value.get("n", None) == 0)
    return str(value) + ":" + repr(value) + ":" + str(bool(value))

print(render(0))
print(render("event"))
print(render(None))
print(render([0, "event", None]))
print(render({"n": 0, "name": "event", "optional": None}))

def increment(value: int | float | list[int | float]) -> int | float:
    if isinstance(value, list):
        return value[0] + 1
    return value + 1

print(increment(2), increment(2.5), increment([3.5]))
