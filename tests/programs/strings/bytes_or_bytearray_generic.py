# A generic class's __init__ may take bytes | bytearray: each call types the class, as its
# type variable's argument does.
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, item: T, data: bytes | bytearray) -> None:
        self.item = item
        self.n = len(data)
        self.first: int = data[0] if len(data) > 0 else -1


a = Box(1, b"abc")
b = Box("x", bytearray(b"\x09\x08"))
print(a.item, a.n, a.first, b.item, b.n, b.first)
