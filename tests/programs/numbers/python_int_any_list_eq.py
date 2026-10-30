# pystachy: dynamic-any
# Equality reads each stored integer without applying this caller's fixed-width read boundary.
from typing import Any
from any_wide_values import make

wide = make(70)
negative = -wide
smallest = -make(63)
native: list[int] = [wide, negative, smallest]
boxed: list[Any] = [wide, negative, smallest]
print(native == boxed, boxed == native)
print(native != boxed, boxed != native)
boxed[1] = negative - 1
print(native == boxed, boxed == native)
boxed[1] = negative


class Equal:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __eq__(self, other: Any) -> bool:
        print("compare", other, self.value is other)
        return self.value == other


callbacks: list[Any] = [Equal(wide), Equal(negative), Equal(smallest)]
print(native == callbacks, callbacks == native)
