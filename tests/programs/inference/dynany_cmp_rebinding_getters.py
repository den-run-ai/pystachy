# pystachy: dynamic-any
from typing import Any


class Left:
    def __init__(self) -> None:
        self.values = [1]

    @property
    def items(self) -> list[int]:
        print("left getter")
        return self.values

    def __eq__(self, other: "Left") -> bool:
        print("comparison")
        try:
            if len(other.items) > 1:
                other = self
            return self.items == other.items
        except AttributeError:
            print("missing")
            return True
        except ValueError as error:
            print(str(error))
            return True
        finally:
            print("cleanup")


class Right:
    def __init__(self, fail: bool) -> None:
        self.values = ["x", "y"]
        self.fail = fail

    @property
    def items(self) -> list[str]:
        print("right getter")
        if self.fail:
            raise ValueError("getter first")
        return self.values


class Missing:
    pass


a: Any = Left()
b: Any = Right(False)
print(a == b)
c: Any = Right(True)
print(a == c)
d: Any = Missing()
print(a == d)
