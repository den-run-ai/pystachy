# pystachy: dynamic-any
# Typed parser bookkeeping must not narrow the open parse_float/payload boundary.
import tomllib
from typing import Any


class Token:
    def __init__(self, label: str) -> None:
        self.label = label


shared = Token("before")
events: list[str] = []


def reuse(text: str) -> Any:
    events.append(text)
    return shared


document = tomllib.loads("a.x = 1.25\na.y = [2.5, 3.75]\n[a.other]\nz = 4.5", parse_float=reuse)
print(events)
print(document["a"]["x"] is shared, document["a"]["y"][0] is shared)
shared.label = "after"
print(document["a"]["x"].label, document["a"]["other"]["z"].label)
document["a"]["new"] = shared
print(document["a"]["new"] is document["a"]["x"])

number = float("nan")


def same_number(text: str) -> Any:
    return number


numbers = tomllib.loads("a = 1.5\nb = [2.5, 3.5]", parse_float=same_number)
print(numbers["a"] is number, numbers["a"] is numbers["b"][0])
print(numbers["a"] in numbers["b"], numbers["b"] == [number, number])


def fail(text: str) -> Any:
    events.append(text)
    raise ValueError("callback stopped")


events.clear()
try:
    tomllib.loads("a = 1.25\na = 2.5", parse_float=fail)
except ValueError as error:
    print(type(error).__name__, str(error), events)

# A callback runs before a duplicate-key rejection, including its side effects.
events.clear()
try:
    tomllib.loads("a = 1.25\na = 2.5", parse_float=reuse)
except tomllib.TOMLDecodeError as error:
    print(type(error).__name__, str(error), events)
