# pystachy: dynamic-any
from typing import Any


class Peer:
    pass


class Ordered:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other) -> bool:
        print("eq")
        return self.items == other.items

    def __ne__(self, other) -> bool:
        print("ne")
        return self.items != other.items

    def __lt__(self, other) -> bool:
        print("lt")
        return self.items < other.items

    def __le__(self, other) -> bool:
        print("le")
        return self.items <= other.items

    def __gt__(self, other) -> bool:
        print("gt")
        return self.items > other.items

    def __ge__(self, other) -> bool:
        print("ge")
        return self.items >= other.items


x: Any = Ordered()
y: Any = Peer()
for reverse in [False, True]:
    a = y if reverse else x
    b = x if reverse else y
    for op in range(6):
        try:
            if op == 0:
                print(a == b)
            elif op == 1:
                print(a != b)
            elif op == 2:
                print(a < b)
            elif op == 3:
                print(a <= b)
            elif op == 4:
                print(a > b)
            else:
                print(a >= b)
        except AttributeError as exc:
            print(str(exc))
