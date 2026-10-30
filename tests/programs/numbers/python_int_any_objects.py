# pystachy: dynamic-any
# Wide numbers must reach comparison callbacks as ints, in both operand orders.
from typing import Any
from any_wide_values import make


class Number:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __eq__(self, other: Any) -> bool:
        print("eq", type(other).__name__)
        return isinstance(other, int) and self.value == other

    def __lt__(self, other: Any) -> bool:
        print("lt", type(other).__name__)
        return self.value < other

    def __gt__(self, other: Any) -> bool:
        print("gt", type(other).__name__)
        return self.value > other

    def __hash__(self) -> int:
        return hash(self.value)


value: Any = make(70)
number: Any = Number(value)
print(number == value, value == number)
print(number < value + 1, value - 1 < number)
print(number > value - 1, value + 1 > number)
entries: dict[Any, Any] = {value: "wide"}
print(entries[number])
entries[number] = "updated"
print(len(entries), entries[value])


def narrowed(value: Any) -> Any:
    if isinstance(value, int):
        return value + 3
    return "other"


print(narrowed(value), narrowed(-value), narrowed(True), narrowed(1.5))
