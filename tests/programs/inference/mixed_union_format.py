"""Formatting uses the selected member and evaluates value/spec exactly once."""
events: list[str] = []


def make(kind: int) -> int | float | bool | str | list[int] | dict[str, int] | None:
    events.append("value" + str(kind))
    if kind == 0:
        return 7
    if kind == 1:
        return 1.25
    if kind == 2:
        return True
    if kind == 3:
        return "word"
    if kind == 4:
        return [1, 2]
    if kind == 5:
        return {"a": 3}
    return None


def spec(text: str) -> str:
    events.append("spec:" + text)
    return text


def literal(value: int | float | bool | str | list[int] | dict[str, int] | None) -> None:
    try:
        print(format(value, ">8"))
    except TypeError as error:
        print(str(error))


print(bool(make(0)), bool(make(4)), str(make(3)), repr(make(4)), f"{make(5)}")
print(make(0) and make(3), make(4) or make(6), make(6) and make(0))
print(events)
events.clear()


for kind in range(7):
    print(format(make(kind), spec("")))
    print(f"{make(kind):{spec('')}}")
    try:
        print(format(make(kind), spec(">8")))
    except TypeError as error:
        print(str(error))
    literal(make(kind))
    print(events)
    events.clear()


def raising_spec() -> str:
    events.append("raising spec")
    raise ValueError("spec failed")


try:
    print(format(make(4), raising_spec()))
except ValueError as error:
    print(str(error), events)
