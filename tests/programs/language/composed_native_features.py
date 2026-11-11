from dataclasses import dataclass
from typing import Any, Callable, final


@final
class Window:
    def __init__(self, values: list[int]) -> None:
        self._values = values

    @property
    def values(self) -> Any:
        return self._values

    def __getitem__(self, key: slice) -> list[int]:
        return self.values[key]


@final
@dataclass
class Row:
    index: int
    value: int


def invoke(callback: Callable[[], int]) -> int:
    return callback()


def row(pair: tuple[int, int]) -> Row:
    return Row(pair[0], pair[1])


def describe(value: Row) -> str:
    match value:
        case Row(1, number) if number > 0:
            return "first:" + str(number)
        case Row(index=i, value=number):
            return str(i) + ":" + str(number)
    return "missing"


window = Window([1, 2, 3, 4, 5, 6])
callbacks: list[Callable[[], int]] = [lambda: value for value in window[1:6:2]]
rows = map(row, enumerate(map(invoke, callbacks), start=1))
print([describe(item) for item in rows])

callbacks2: list[Callable[[], int]] = [lambda: value for value in window[slice(None, None, -2)]]
rows2 = map(row, enumerate(map(invoke, callbacks2), start=1))
selected = min(rows2, key=lambda item: item.index + item.value, default=Row(9, 9))
print(describe(selected), window.values)

# Each comprehension evaluation owns its capture cells, even when its closures
# are retained by an iterator constructed during a later evaluation.
print(list(map(invoke, callbacks)), list(map(invoke, callbacks2)))
