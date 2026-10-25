# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self, empty: bool) -> None:
        self.items: list[str] = [] if empty else ["one"]


class Strict:
    def __init__(self, empty: bool, fail: bool = False) -> None:
        self.items: list[int] = [] if empty else [1]
        self.marker = 7
        self.fail = fail

    def __eq__(self, other: "Strict") -> bool:
        alias = other
        captured = alias
        print("comparison")
        if self.fail:
            raise ValueError("first error")

        def value() -> int:
            print("captured read")
            try:
                return captured.marker
            finally:
                print("inner cleanup")

        try:
            return self.items == alias.items and self.marker == value()
        finally:
            print("outer cleanup")


class DirectAlias:
    def __init__(self) -> None:
        self.items: list[int] = []
        self.marker = 7

    def __eq__(self, other: "DirectAlias") -> bool:
        alias = other
        print("alias comparison")
        try:
            return self.items == alias.items and self.marker == alias.marker
        except AttributeError as exc:
            print(str(exc))
            return True


for empty in [False, True]:
    strict = Strict(empty)
    x: Any = strict
    y: Any = Peer(empty)
    for reflected in [False, True]:
        try:
            print(y == x if reflected else x == y)
        except AttributeError as exc:
            print(str(exc))
    # A concrete call after the dynamic adapter keeps its ordinary field reads.
    print(strict == Strict(empty))

x = Strict(True, True)
y = Peer(True)
try:
    print(x == y)
except ValueError as exc:
    print(str(exc))
x = DirectAlias()
print(x == y, y in [x])
