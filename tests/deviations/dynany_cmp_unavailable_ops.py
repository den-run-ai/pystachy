# pystachy: dynamic-any
# Unsupported bodies raise explicitly, rather than returning identity's answer.
# CPython runs each body and returns True. Keep both operand orders and every
# rich comparison: an unavailable reflected method must raise as well.
from typing import Any


class Left:
    def __init__(self) -> None:
        self.items = [1]

    def __eq__(self, other: "Left") -> bool:
        print("eq body")
        box = [other]
        return len(box[0].items) == len(self.items)

    def __ne__(self, other: "Left") -> bool:
        print("ne body")
        box = [other]
        return len(box[0].items) == len(self.items)

    def __lt__(self, other: "Left") -> bool:
        print("lt body")
        box = [other]
        return len(box[0].items) == len(self.items)

    def __le__(self, other: "Left") -> bool:
        print("le body")
        box = [other]
        return len(box[0].items) == len(self.items)

    def __gt__(self, other: "Left") -> bool:
        print("gt body")
        box = [other]
        return len(box[0].items) == len(self.items)

    def __ge__(self, other: "Left") -> bool:
        print("ge body")
        box = [other]
        return len(box[0].items) == len(self.items)


class Right:
    def __init__(self) -> None:
        self.items = ["x"]


def compare(a: Any, b: Any, op: int) -> bool:
    if op == 0:
        return a == b
    if op == 1:
        return a != b
    if op == 2:
        return a < b
    if op == 3:
        return a <= b
    if op == 4:
        return a > b
    return a >= b


left: Any = Left()
right: Any = Right()
for reverse in [False, True]:
    for op in range(6):
        try:
            if reverse:
                print(compare(right, left, op))
            else:
                print(compare(left, right, op))
        except TypeError as error:
            assert "could not be compiled" in str(error)
            print("unavailable", reverse, op)
        finally:
            print("cleanup", reverse, op)
