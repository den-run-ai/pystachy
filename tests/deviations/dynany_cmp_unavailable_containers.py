# pystachy: dynamic-any
# Container equality and searches must propagate an unavailable comparison,
# including a hash collision in an Any-keyed dictionary. CPython runs the body.
from typing import Any


class Left:
    def __init__(self) -> None:
        self.items = [1]

    def __eq__(self, other: "Left") -> bool:
        print("comparison body")
        box = [other]
        return len(box[0].items) == len(self.items)

    def __hash__(self) -> int:
        return 1


class Right:
    def __init__(self) -> None:
        self.items = ["x"]

    def __hash__(self) -> int:
        return 1


left: Any = Left()
right: Any = Right()
values: list[Any] = [left]
table: dict[Any, int] = {left: 7}
for operation in range(7):
    try:
        if operation == 0:
            print([values] == [[right]])
        elif operation == 1:
            print((left,) == (right,))
        elif operation == 2:
            print(right in values)
        elif operation == 3:
            print(values.count(right))
        elif operation == 4:
            print(values.index(right))
        elif operation == 5:
            print(right in table)
        else:
            print(table[right])
    except TypeError as error:
        assert "could not be compiled" in str(error)
        print("unavailable", operation)
print("unchanged", len(values), len(table))
