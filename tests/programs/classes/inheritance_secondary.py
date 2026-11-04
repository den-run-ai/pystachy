# pystachy: dynamic-any
from typing import Any, Callable


class Storage:
    def __init__(self, value: int) -> None:
        self.value = value


class Reader:
    def read(self, offset: int, /) -> int:
        return offset


class Both(Storage, Reader):
    def read(self, offset: int) -> int:
        self.value += offset
        return self.value


class Twice(Both):
    def read(self, offset: int) -> int:
        self.value += 2 * offset
        return self.value


class Other:
    pass


class Independent(Other, Reader):
    pass


def guarded(value: Storage) -> int:
    if isinstance(value, Reader):
        return value.read(1)
    return -1


def exercise(obj: Both, role: Reader, boxed: Any) -> None:
    print(obj is role, boxed is role, type(role).__name__)
    print(isinstance(boxed, Storage), isinstance(boxed, Reader), isinstance(boxed, Other))
    print(isinstance(role, Storage), guarded(obj), boxed.read(3), obj.value)
    method: Callable[[int], int] = role.read
    concrete: Callable[[int], int] = obj.read
    print(method == concrete, method(2), obj.value)
    if isinstance(boxed, Reader):
        print(boxed.read(1), obj.value)
    print(hasattr(obj, "__dict__"), hasattr(obj, "__weakref__"))


for item in [Both(10), Twice(20)]:
    exercise(item, item, item)
    print(item.read(offset=0))
print(guarded(Storage(5)), Independent().read(6), Reader().read(7))
