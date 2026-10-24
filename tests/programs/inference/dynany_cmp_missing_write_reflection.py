# pystachy: dynamic-any
from typing import Any


class Untouched:
    def __init__(self) -> None:
        self.value = 1


class Peer:
    def __init__(self) -> None:
        self.items = [9]


class Writer:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Writer") -> bool:
        print("body")
        other.items = self.items
        return other.items is self.items


untouched = Untouched()
boxed: Any = untouched
writer: Any = Writer()
peer: Any = Peer()
print(vars(untouched))
print(dict(vars(untouched)))
for name, value in vars(untouched).items():
    print(name, value)
print(writer == peer)
print(vars(untouched))
print(vars(untouched).copy())
for name in untouched.__dict__:
    print(name)
print(hasattr(untouched, "items"))


class Root:
    pass


class Child(Root):
    def __init__(self) -> None:
        self.items = [9]


root: Any = Root()
child = Child()
print(vars(child))
