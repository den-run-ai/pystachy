# pystachy: dynamic-any
from typing import Any


def size(value) -> int:
    print("helper")
    try:
        return len(value.items)
    finally:
        print("helper cleanup")


def forward(value) -> int:
    return size(value)


class Left:
    def __init__(self, fail: bool) -> None:
        self.items = [1]
        self.fail = fail

    def __eq__(self, other: "Left") -> bool:
        print("comparison")
        try:
            if self.fail:
                raise ValueError("first")
            print(forward(other))
        except AttributeError:
            print("missing")
        finally:
            print("comparison cleanup")
        return True


class Missing:
    pass


for fail in [False, True]:
    left: Any = Left(fail)
    right: Any = Missing()
    try:
        print(left == right)
    except ValueError as error:
        print(str(error))
print(size(Left(False)))
