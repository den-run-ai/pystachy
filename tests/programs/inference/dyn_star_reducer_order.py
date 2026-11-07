# pystachy: dynamic-any
# Capture the callee first and match CPython's two star-expansion timing rules.
from typing import Any

EVENTS: list[str] = []


def original(a: int, b: int = 0, *, c: int = 0) -> int:
    EVENTS.append("original")
    return a * 100 + b * 10 + c


def replacement(a: int, b: int = 0, *, c: int = 0) -> int:
    EVENTS.append("replacement")
    return -(a * 100 + b * 10 + c)


class Holder:
    def __init__(self) -> None:
        self.function: Any = original


holder: Any = Holder()
FUNCTION: Any = original


def change_field() -> Any:
    holder.function = replacement
    EVENTS.append("field")
    return [1, 2]


def change_global() -> Any:
    global FUNCTION
    FUNCTION = replacement
    EVENTS.append("global")
    return [3, 4]


def keyword() -> int:
    EVENTS.append("keyword")
    return 5


print(holder.function(*change_field(), c=keyword()))
print(holder.function(*[1, 2]))
print(FUNCTION(*change_global(), c=keyword()))
print(FUNCTION(*[3, 4]))
print(EVENTS)
EVENTS.clear()

items: Any = [6]
function: Any = original


def mutate_keyword() -> int:
    EVENTS.append("mutate")
    items.append(7)
    return 8


# A sole star keeps its iterable until keywords finish evaluating.
print(function(*items, c=mutate_keyword()))
print(items, EVENTS)
EVENTS.clear()
items = [6]


def next_pack() -> Any:
    EVENTS.append("next")
    items.append(9)
    return [7]


# Several positional groups consume the first star before evaluating the next.
print(function(*items, *next_pack(), c=keyword()))
print(items, EVENTS)
EVENTS.clear()


def named_pack(label: str, value: Any) -> Any:
    EVENTS.append(label)
    return value


# Even a star written after a keyword is evaluated with positional arguments first.
print(function(c=keyword(), *named_pack("star", [1, 2])))
print(EVENTS)
EVENTS.clear()

try:
    holder.missing(*named_pack("unreached star", [1]), c=keyword())
except AttributeError:
    print("missing first", EVENTS)
