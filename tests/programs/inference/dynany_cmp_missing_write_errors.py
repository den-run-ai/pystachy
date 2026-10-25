# pystachy: dynamic-any
from dataclasses import dataclass
from typing import Any


class Slotted:
    __slots__ = ()


@dataclass(frozen=True)
class Frozen:
    value: int = 0


def evaluated(values: list[int]) -> list[int]:
    print("RHS")
    return values


class Writer:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Writer") -> bool:
        print("body")
        try:
            other.items = evaluated(self.items)
        except AttributeError:
            print("readonly")
            return True
        finally:
            print("cleanup")
        return False


writer: Any = Writer()
slotted: Any = Slotted()
frozen: Any = Frozen()
print(writer == slotted)
print(writer == frozen)
