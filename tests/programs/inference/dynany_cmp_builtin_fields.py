# pystachy: dynamic-any
# Concrete comparison adapters retain each closed builtin field's own storage.
from typing import Any


class Words:
    def __init__(self, empty: bool) -> None:
        self.items: list[str] = [] if empty else ["three"]
        self.count = 0


class Reals:
    def __init__(self) -> None:
        self.items = [3.0]
        self.count = 0


class Missing:
    def __init__(self) -> None:
        self.count = 0


class Numbers:
    def __init__(self, empty: bool, fail: bool = False) -> None:
        self.items: list[int] = [] if empty else [3]
        self.count = 0
        self.fail = fail

    def __eq__(self, other: "Numbers") -> bool:
        print("comparison ran", len(self.items))
        other.count += 1
        if self.fail:
            raise ValueError("first error")
        return self.items == other.items


for empty in [False, True]:
    numbers = Numbers(empty)
    words = Words(empty)
    x: Any = numbers
    y: Any = words
    print(x == y, y == x, x != y, y in [x])
    print(words.count)
    # The ordinary typed specialization is independent of the adapter.
    print(numbers == Numbers(empty))
    # Containers retain their storage and aliases after comparison.
    numbers.items.append(4)
    words.items.append("four")
    print(numbers.items, words.items)

x = Numbers(False)
y = Reals()
print(x == y, y == x, x != y)
print(y.count)

# A different builtin field plus an absent field must preserve the first error.
x = Numbers(False, True)
y = Words(False)
try:
    print(x == y)
except ValueError as exc:
    print(str(exc))
print(y.count)
y = Missing()
x = Numbers(False)
try:
    print(x == y)
except AttributeError as exc:
    print(str(exc))
print(y.count)


class Inherited(Numbers):
    pass


x = Inherited(True)
y = Words(True)
print(y == x)
print(y.count)
