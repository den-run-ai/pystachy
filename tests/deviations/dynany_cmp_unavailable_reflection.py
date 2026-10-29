# pystachy: dynamic-any
# An unavailable left method is not NotImplemented: do not try the right method
# after rejecting it. CPython instead runs the left method, including its print.
from typing import Any


class Left:
    def __init__(self) -> None:
        self.items = [1]

    def __eq__(self, other: "Left") -> bool:
        print("left body")
        box = [other]
        return len(box[0].items) == len(self.items)


class Right:
    def __init__(self) -> None:
        self.items = ["x"]

    def __eq__(self, other: Any) -> bool:
        print("right body")
        return True


left: Any = Left()
right: Any = Right()
try:
    print(left == right)
except TypeError as error:
    assert "could not be compiled" in str(error)
    print("unavailable eq")
finally:
    print("cleanup eq")
# An absent __ne__ inverts __eq__; the unavailable status must not be inverted.
try:
    print(left != right)
except TypeError as error:
    assert "could not be compiled" in str(error)
    print("unavailable ne")
finally:
    print("cleanup ne")
