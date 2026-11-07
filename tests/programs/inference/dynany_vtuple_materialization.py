# pystachy: dynamic-any
# Native references and existing numeric identities survive direct construction.
from typing import Any


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


def numbers(x: float, y: int) -> tuple[Any, ...]:
    return (x, x, y, y)


def references(box: Box, items: list[Any], x: float | None) -> tuple[Any, ...]:
    return (box, items, (x, None), x)


def fresh(i: int) -> tuple[Any, ...]:
    return (Box(i), ["owned-" + str(i)], "leaf-" + str(i))


def convert(values: tuple[Any, Any]) -> tuple[Any, ...]:
    return values


x = float("1.25")
y = int("1234567")
values = numbers(x, y)
print(values, values[0] is x, values[0] is values[1], values[2] is y, values[2] is values[3])
box = Box(3)
items: list[Any] = ["item"]
kept = references(box, items, x)
kept[0].value = 9
kept[1].append("changed")
print(kept[0] is box, kept[1] is items, box.value, items)
source: tuple[Any, Any] = (box, items)
saved = convert(source)
print(saved[0] is box, saved[1] is items, source[0] is box)
owned = fresh(7)
for i in range(100):
    garbage: Any = ["temporary-" + str(i), Box(i), (float(i), None)]
# Nested numeric fixed-tuple storage has a separate existing identity limitation.
# Check its value, and the dynamic identity retained by the direct outer display.
print(kept[0].value, kept[1], kept[2], kept[3], kept[2][0] == x, kept[3] is x)
print(references(box, items, None)[2])
print(owned[0].value, owned[1], owned[2])
