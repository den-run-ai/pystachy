# pystachy: dynamic-any
# An object whose __iter__ returns iter() of its list iterates through an Any value as CPython's
# list iterator does (#773): an item appended to the list during the loop is reached, whether
# __iter__ is annotated Iterator[T] or not.
from typing import Any, Iterator


class Annotated:
    def __init__(self) -> None:
        self.items: list[int] = [1, 2]

    def __iter__(self) -> Iterator[int]:
        return iter(self.items)


class Plain:
    def __init__(self) -> None:
        self.items: list[str] = ["a", "b"]

    def __iter__(self):
        return iter(self.items)


a = Annotated()
x: Any = a
for v in x:
    if v == 1:
        a.items.append(3)
    print(v)
p = Plain()
y: Any = p
for s in y:
    if s == "b":
        p.items.append("c")
    print(s)
print(list(x), sorted(y, reverse=True))
