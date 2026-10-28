# pystachy: dynamic-any
from typing import Any


class Index:
    def __init__(self, label: str, value: int) -> None:
        self.label = label
        self.value = value

    def __index__(self) -> int:
        print("index", self.label)
        return self.value


class BadIndex:
    def __index__(self) -> Any:
        print("bad index")
        return 1.5


class Raising:
    def __index__(self) -> int:
        raise ValueError("index failed")


class Lookup:
    def __getitem__(self, key: Any) -> str:
        print("lookup", type(key).__name__)
        return "original key"


class MutatingIndex:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def __index__(self) -> int:
        self.values.pop()
        self.values[0] = "replaced" + str(len(self.values))
        return -1


def read(value: Any, key: Any) -> None:
    try:
        print("read", value[key])
    except TypeError as error:
        print("TypeError:", error)
    except ValueError as error:
        print("ValueError:", error)


def slices(value: Any, start: Any, stop: Any, step: Any) -> None:
    try:
        print("slice", value[start:stop:step])
    except TypeError as error:
        print("TypeError:", error)
    except ValueError as error:
        print("ValueError:", error)


items: Any = [10, 20, 30, 40]
one: Any = Index("one", 1)
read(items, one)
read((10, 20), one)
read("ab", one)
read(items, BadIndex())
read(items, Raising())
read(items, 1.5)
read(123, one)
read(Lookup(), one)
mapping: Any = {one: "key"}
read(mapping, one)
items[one] = 25
print(items)
del items[one]
print(items)
slices(items, Index("start", 0), Index("stop", 3), Index("step", 2))
slices(items, Index("unused start", 0), Index("unused stop", 3), Index("zero step", 0))
slices(items, BadIndex(), Index("unused stop", 3), None)
slices(123, Index("unused start", 0), Index("unused stop", 3), Index("unused step", 1))
bound: Any = Index("typed bound", 1)
print([5, 6, 7][bound:])
live: list[Any] = ["first", "last"]
read(live, MutatingIndex(live))
print(live)
immutable: Any = (1, 2)
try:
    immutable[one] = 3
except TypeError as error:
    print("immutable:", error)
try:
    del immutable[one]
except TypeError as error:
    print("immutable:", error)
