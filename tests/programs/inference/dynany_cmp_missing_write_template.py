# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self, value):
        self.value = value


class SharedLayout:
    def __init__(self, value):
        self.value = str(value)


class Writer:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Writer") -> bool:
        print("body")
        other.items = self.items
        return other.items is self.items


writer = Writer()
integer = Peer(7)
text = Peer("seven")
shared_integer = SharedLayout(8)
shared_text = SharedLayout("eight")
x: Any = writer
a: Any = integer
b: Any = text
c: Any = shared_integer
d: Any = shared_text
print(vars(integer), vars(text))
print(vars(shared_integer), vars(shared_text))
print(hasattr(integer, "items"), hasattr(text, "items"))
print(x == a, x == b, x == c, x == d)
print(integer.value, text.value, shared_integer.value, shared_text.value)
print(integer.items is text.items, shared_integer.items is shared_text.items)
integer.items.append(4)
print(writer.items, text.items, shared_integer.items, shared_text.items)
