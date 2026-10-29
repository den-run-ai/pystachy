# pystachy: dynamic-any
from typing import Any


def check(a, b) -> bool:
    print("helper")
    print(len(b.items))
    try:
        if a.fail:
            raise ValueError("first")
        return a.items[4] == b.items[0]
    finally:
        print("cleanup")


class Left:
    def __init__(self, fail: bool) -> None:
        self.items = [1]
        self.fail = fail

    def __eq__(self, other: "Left") -> bool:
        print("comparison")
        return check(self, other)


class Right:
    def __init__(self) -> None:
        self.items = ["x"]


for fail in [True, False]:
    left: Any = Left(fail)
    right: Any = Right()
    try:
        print(left == right)
    except ValueError as error:
        print("ValueError", str(error))
    except IndexError:
        print("IndexError")
