# pystachy: dynamic-any
# Omitted defaults keep definition-time objects, including closure environment slots.
from typing import Any

NUMBER = int("1000")


def choose(value: int = NUMBER, *, flag: bool = True) -> Any:
    return (value, flag)


def collect(values: list[Any] = []) -> Any:
    values.append(len(values) + 1)
    return values


def make(prefix: str) -> Any:
    captured = int("2000")
    values: list[Any] = [prefix]

    def inner(value: int = captured, *, items: list[Any] = values) -> Any:
        items.append(value)
        boxed: Any = value
        original: Any = captured
        return (boxed is original, items is values, items)

    return inner


empty: Any = []
keywords: Any = {}
function: Any = choose
first = function(*empty, **keywords)
second = function(*empty, **keywords)
print(first[0] is NUMBER, second[0] is NUMBER, first[0] is second[0], first[1])
provided = int("1000")
args: Any = [provided]
third = function(*args, **{"flag": False})
print(third[0] is provided, third[0] is NUMBER, third[1])

collector: Any = collect
left = collector(*empty)
right = collector(*empty)
print(left is right, left)
explicit: list[Any] = []
result = collector(*empty, **{"values": explicit})
print(result is explicit, result is left, result)

closure: Any = make("kept")
a = closure(*empty)
b = closure(*empty, **keywords)
print(a[0], a[1], a[2] is b[2], a[2])
replacement: list[Any] = ["replacement"]
c = closure(*[int("2000")], **{"items": replacement})
print(c[0], c[1], c[2] is replacement, c[2])
