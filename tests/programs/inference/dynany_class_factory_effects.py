# pystachy: dynamic-any
# Class capture and argument effects precede binding and initializer effects.
from typing import Any


events: list[str] = []


class Checked:
    def __init__(self, value: int, *, label: str = "default") -> None:
        events.append("init:" + label)
        if value < 0:
            raise ValueError("negative")
        self.value = value


def choose() -> Any:
    events.append("callee")
    return Checked


def argument(value: int) -> int:
    events.append("argument:" + str(value))
    return value


first = choose()(argument(7), label="supplied")
print(first.value, events)
events.clear()
try:
    choose()(argument(1), argument(2))
except TypeError as exc:
    print(str(exc))
print(events)
events.clear()
try:
    choose()(argument(-1))
except ValueError as exc:
    print(str(exc))
print(events)
