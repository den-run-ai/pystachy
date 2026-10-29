# pystachy: dynamic-any
from typing import Any


class Guard:
    def __enter__(self) -> "Guard":
        print("enter")
        return self

    def __exit__(self, kind, error, traceback) -> bool:
        print("exit", kind is None)
        return False


class Peer:
    def __init__(self, empty: bool) -> None:
        self.items: list[int] = [] if empty else [3]


class Missing:
    pass


class Numbers:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Numbers") -> bool:
        print("cleanup comparison")
        with Guard():
            try:
                for value in self.items:
                    assert value == 3
                attempts = 0
                while attempts < 1:
                    attempts += 1
                return self.items[0] == other.items[0]
            except IndexError:
                print("caught index")
                return False
            except AttributeError:
                print("caught missing")
                return True
            finally:
                print("finally")


x: Any = Numbers()
for empty in [False, True]:
    y: Any = Peer(empty)
    print(x == y, y == x, x != y)
y = Missing()
print(x == y, y == x, x != y)
print(Numbers() == Numbers())
