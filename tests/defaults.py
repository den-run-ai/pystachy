# Default values are evaluated once, when the def or class statement runs (as in CPython).
from dataclasses import dataclass

LOG: list[str] = []


def note(s: str) -> int:
    LOG.append(s)
    return len(LOG)


def add(x: int, acc: list[int] = []) -> list[int]:
    acc.append(x)
    return acc


def counted(tag: str, n: int = note("counted default")) -> str:
    return f"{tag}:{n}"


LIMIT = 3


def limit(n: int = LIMIT) -> int:
    return n


LIMIT = 30


def table(key: str, d: dict[str, int] = {}) -> int:
    d[key] = d.get(key, 0) + 1
    return d[key]


class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"


ORIGIN = Point(0, 0)


def shift(dx: int, p: Point = ORIGIN) -> Point:
    p.x += dx
    return p


class Bag:
    def __init__(self, name: str, items: list[str] = []):
        self.name = name
        self.items = items

    def put(self, s: str, sep: str = "-", seen: list[str] = []) -> str:
        seen.append(s)
        self.items.append(s)
        return sep.join(seen)


class Registry:
    names: list[str] = []
    count: int = 0

    def __init__(self, n: str):
        self.names.append(n)
        self.count += 1


@dataclass
class Cfg:
    name: str
    size: int = 4
    dims: tuple[int, int] = (2, 3)
    owner: Point = ORIGIN


print(add(1), add(2), add(3, []), add(4))
print(LOG, counted("a"), counted("b", 7), counted("c"), LOG)
print(limit(), limit(5))
print(table("x"), table("y"), table("x"), table("x", {}), table("x"))
print(shift(1), shift(2), shift(5, Point(10, 10)), ORIGIN)
b1 = Bag("one")
b2 = Bag("two")
print(b1.put("p"), b2.put("q", "+"), b1.items, b2.items is b1.items)
r1 = Registry("r1")
r2 = Registry("r2")
print(r1.names, r2.names, r1.count, r2.count)
c1 = Cfg("c1")
c2 = Cfg("c2", size=9)
c1.owner.y = 42
print(c1, c2, c1.dims is c2.dims, c2.owner.y)
