# pystachy: dynamic-any
from typing import Any


def operand(value):
    print("operand")
    alias = value
    return alias


def contents(value):
    print("contents")
    if value.fail:
        raise ValueError("helper first")
    saved = value.view
    return saved


class Left:
    def __init__(self) -> None:
        self.items = [1]
        self.fail = False

    @property
    def view(self) -> list[int]:
        print("left getter")
        return self.items

    def __eq__(self, other: "Left") -> bool:
        print("comparison")
        peer = operand(other)
        left = contents(self)
        try:
            print(left is self.items, contents(peer) is peer.items)
            print(operand(self).items == operand(other).items)
            return contents(self) == contents(other)
        except ValueError as error:
            print(str(error))
            return True
        finally:
            print("cleanup")


class Right:
    def __init__(self, fail: bool) -> None:
        self.items = ["one"]
        self.fail = fail

    @property
    def view(self) -> list[str]:
        print("right getter")
        return self.items


a: Any = Left()
b: Any = Right(False)
print(a == b)
c: Any = Right(True)
print(a == c)
