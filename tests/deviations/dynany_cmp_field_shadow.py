# pystachy: dynamic-any
# Base-typed reflection of a comparison-created field needs a concrete layout.
from typing import Any


class Base:
    pass


class Child(Base):
    def __init__(self) -> None:
        self.items = ["child"]


class Writer:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Writer") -> bool:
        other.items = self.items
        return True


def read(base: Base) -> None:
    print(base.items)


original = Base()
base: Any = original
writer: Any = Writer()
print(writer == base)
read(original)
try:
    read(Child())
except TypeError as error:
    print(error)
