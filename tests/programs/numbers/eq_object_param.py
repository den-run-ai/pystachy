# a parameter annotated object, as __eq__(self, other: object) takes one: any argument, which each
# call types (the function is a template), and which isinstance() narrows; objects of an imported
# class whose __eq__ takes object compare and sort with it, and are keys where it defines __hash__
from mods.hashed import Key, Pair, same
import mods.hashed


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return False
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"


class Point3(Point):
    def __init__(self, x: int, y: int, z: int) -> None:
        super().__init__(x, y)
        self.z = z


def describe(v: object) -> str:
    if isinstance(v, Point):
        return f"point {v.x},{v.y}"
    if isinstance(v, str):
        return "str " + v
    return "other " + repr(v)


print(Point(1, 2) == Point(1, 2), Point(1, 2) == 3, Point(1, 2) != "a", Point(1, 2) == Point(2, 1))
print(Point(1, 2) == Point3(1, 2, 3), Point3(0, 0, 1) == Point(0, 0), Point(1, 2) in [Point(0, 0), Point(1, 2)])
seen = {Point(1, 2), Point(1, 2), Point(3, 4), Point3(3, 4, 5)}
print(len(seen), Point(3, 4) in seen, seen)
print(describe(Point(5, 6)), describe(3), describe("s"), describe([1]), describe(Point3(1, 1, 1)))
grid: dict[Point, str] = {Point(0, 0): "origin"}
print(grid[Point(0, 0)], grid.get(Point(1, 1), "?"), hash(Point(1, 2)) == hash((1, 2)))
print([Pair(1)] == [Pair(1)], [Pair(1)] == [Pair(2)], (Pair(1), 2) == (Pair(1), 2), Pair(1) == 1)
xs = [(Pair(1), 2), (Pair(1), 1)]
xs.sort()
print([t[1] for t in xs], [mods.hashed.Pair(3)] != [mods.hashed.Pair(3)])
keys = {Key(1): "one", Key(2): "two"}
print(keys[Key(1)], Key(3) in keys, {Key(1), Key(1)}, Key(2) == Pair(2))
try:
    print({Pair(1)})
except TypeError as e:
    print("TypeError:", e)
k = Key(9)
print(same(k, k), same(k, Key(9)), same(k, None))
