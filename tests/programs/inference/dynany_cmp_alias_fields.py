# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self, empty: bool) -> None:
        self.items: list[str] = [] if empty else ["three"]


class Numbers:
    def __init__(self, empty: bool) -> None:
        self.items: list[int] = [] if empty else [3]

    def __eq__(self, other: "Numbers") -> bool:
        alias = other
        captured = alias
        print("alias comparison")

        def matches() -> bool:
            print("nested ran")
            return self.items == captured.items

        return matches()


for empty in [False, True]:
    numbers = Numbers(empty)
    peer = Peer(empty)
    x: Any = numbers
    y: Any = peer
    print(x == y, y == x, x != y, y in [x])
    numbers.items.append(4)
    peer.items.append("four")
    print(numbers.items, peer.items, x == y)
    print(numbers == Numbers(empty))
