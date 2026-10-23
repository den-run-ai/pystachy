# pystachy: dynamic-any
from typing import Any


class Numbers:
    def __init__(self, filled: bool) -> None:
        self.items: set[int] = {0} if filled else set()
        self.marker = 1

    def __eq__(self, other: "Numbers") -> bool:
        print("numbers comparison ran")
        return self.items == other.items and self.marker == other.marker


class Words:
    def __init__(self, filled: bool) -> None:
        self.items: set[str] = {""} if filled else set()
        self.marker = 1

    def __eq__(self, other: "Words") -> bool:
        print("words comparison ran")
        return self.items == other.items


class Data:
    def __init__(self, filled: bool) -> None:
        self.items: set[bytes] = {b""} if filled else set()
        self.marker = 1


class FrozenWords:
    def __init__(self, filled: bool) -> None:
        self.items: frozenset[str] = frozenset({""}) if filled else frozenset()
        self.marker = 1


for filled in [False, True]:
    x: Any = Numbers(filled)
    y: Any = Words(filled)
    z: Any = Data(filled)
    f: Any = FrozenWords(filled)
    print("int/str", filled, x == y, y == x, x != y, y != x)
    print("int/bytes", filled, x == z, z == x, x != z, z != x)
    print("str/bytes", filled, y == z, z == y, y != z, z != y)
    print("frozen", filled, x == f, f == x, x != f, f != x)
    print("same layout", x == Numbers(filled), Numbers(filled) == x)


class MissingMarker:
    def __init__(self) -> None:
        self.items: set[str] = set()


# Equal empty sets reach the missing read; nonempty sets short-circuit it.
for filled in [False, True]:
    x = Numbers(filled)
    y = MissingMarker()
    try:
        print("missing marker", filled, x == y)
    except AttributeError as exc:
        print(str(exc))
