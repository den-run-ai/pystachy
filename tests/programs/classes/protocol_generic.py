# Protocol[T] names one interface for each binding of T.
from typing import Protocol, TypeVar

T = TypeVar("T")


class Cell(Protocol[T]):
    def get(self) -> T: ...

    def put(self, value: T) -> None: ...


class IntBox:
    def __init__(self) -> None:
        self.v = 0

    def get(self) -> int:
        return self.v

    def put(self, value: int) -> None:
        self.v = value


class Doubling:
    def __init__(self, v: int) -> None:
        self.v = v

    def get(self) -> int:
        return self.v * 2

    def put(self, value: int) -> None:
        self.v = value


class TextBox:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def get(self) -> str:
        return "".join(self.parts)

    def put(self, value: str) -> None:
        self.parts.append(value)


def bump(cell: Cell[int]) -> int:
    cell.put(cell.get() + 1)
    return cell.get()


ints: list[Cell[int]] = [IntBox(), Doubling(5)]
print([bump(c) for c in ints], [c.get() for c in ints])
texts: list[Cell[str]] = [TextBox()]
texts[0].put("ab")
texts[0].put("c")
print(texts[0].get())
pairs: list[tuple[str, Cell[int]]] = [("x", IntBox()), ("y", Doubling(1))]
for key, cell in pairs:
    cell.put(4)
    print(key, cell.get())
