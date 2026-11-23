# == and != of Protocol values compare their objects as CPython does: the left object's
# __eq__ (or __ne__), then the right one's reflected method, then identity where neither class
# decides; a value of another type, None or a value of the protocol on either side.
from typing import Protocol


class Keyed(Protocol):
    def key(self) -> str: ...


class Plain:
    def key(self) -> str:
        return "plain"


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def key(self) -> str:
        return f"p{self.x},{self.y}"

    def __eq__(self, other: object) -> bool:
        print("Point.__eq__", type(other).__name__)
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y


class Tagged:
    def __init__(self, n: int) -> None:
        self.n = n

    def key(self) -> str:
        return f"t{self.n}"

    def __eq__(self, other: object) -> bool:
        print("Tagged.__eq__")
        if not isinstance(other, Tagged):
            return NotImplemented
        return other.n == self.n

    def __ne__(self, other: object) -> bool:
        print("Tagged.__ne__")
        if not isinstance(other, Tagged):
            return NotImplemented
        return other.n != self.n


def same(a: Keyed, b: Keyed) -> bool:
    return a == b


def differ(a: Keyed, b: Keyed) -> bool:
    return a != b


plain = Plain()
p1 = Point(1, 2)
items: list[Keyed] = [plain, p1, Point(1, 2), Point(3, 4), Tagged(1), Tagged(1), Plain()]
for i in range(len(items)):
    row = []
    for j in range(len(items)):
        row.append("1" if same(items[i], items[j]) else "0")
    print(items[i].key(), "".join(row))
print(differ(items[4], items[5]), differ(items[4], items[0]), differ(items[0], items[1]), differ(items[0], items[0]))
k: Keyed = p1
print(k == p1, p1 == k, k == Point(1, 2), Point(9, 9) == k, k != plain, plain != k)
print(k == 3, 3 == k, k != "s", k == None, None == k, k != None)
q: Keyed = plain
print(q == 3, 3 != q, q == "s", q == None, None != q, q == plain, plain == q)
nothing: Keyed | None = None
print(nothing == None, nothing == k, k == nothing, nothing != k, nothing == nothing, nothing is None)
print(sum(1 for x in items if x == p1), [x == plain for x in items].count(True))
