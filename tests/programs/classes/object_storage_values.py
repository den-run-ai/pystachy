# object as a stored type: a variable, a field, a list's, dict's or tuple's items and a function's
# result hold a value of any type (numbers, a str, bytes, containers, objects of the program's
# classes, class objects, None), which str(), repr(), format(), f-strings, truth, ==, != (with
# either operand first, numbers by their values) and hash() take as CPython does
class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return False
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))


class Plain:
    pass


class Holder:
    def __init__(self, label: str) -> None:
        self.label = label
        self.value: object = None


def pick(i: int) -> object:
    if i == 0:
        return 42
    if i == 1:
        return "text"
    if i == 2:
        return Point(1, 2)
    if i == 3:
        return [1, 2]
    return None


def main() -> None:
    xs: list[object] = [1, 2.5, True, "s", b"b", [1, "a"], {"k": 2}, (1, "t"), {3}, Point(0, 0), None, int, Point, 10 ** 15]
    for x in xs:
        print(str(x), repr(x), f"{x}", format(x), bool(x), x == 1, 1 == x, x != "s", "s" != x, x is None)
    print([x == y for x in xs[:4] for y in [1, 1.0, True, "s"]])
    print(hash(xs[0]) == hash(1.0), hash(xs[2]) == hash(1), hash(xs[3]) == hash("s"), hash(xs[9]) == hash(Point(0, 0)))
    d: dict[str, object] = {"a": 1, "b": "two", "c": None}
    for k in d:
        print(k, d[k], d[k] == "two")
    t: tuple[object, object, object] = (1, "x", None)
    print(t, t[0], t[1] == "x", len(t), hash(t) == hash((1, "x", None)))
    vt: tuple[object, ...] = (1, "a", 2.5)
    print(vt, len(vt), "%s-%s-%s" % vt, "%r|%r|%r" % vt)
    for i in range(5):
        v = pick(i)
        print(i, v, v == 42, v is None, repr(v))
    h = Holder("h")
    print(h.label, h.value)
    h.value = 3
    print(h.value, h.value == 3)
    h.value = "now a str"
    print(h.value)
    h.value = Plain()
    print(h.value is h.value, h.value == h.value, h.value is None)
    o: object = Point(3, 4)
    print(o == Point(3, 4), Point(3, 4) == o, o != Point(3, 5), o == "Point(3, 4)")
    print(f"{xs[1]:.2f}", f"{xs[0]:>4}", format(xs[3], "^5"), "{!r} and {}".format(xs[3], xs[0]))
    print(xs[5] == [1, "a"], xs[6] == {"k": 2}, xs[7] == (1, "t"), xs[8] == {3}, [1, "a"] == xs[5])
    print(xs[11] == int, xs[11] is int, xs[12] == Point, xs[0] == xs[2], xs[2] == xs[0], xs[13] == 10 ** 15)
    print(xs[0] == xs[1], xs[1] == 2.5, xs[4] == b"b", xs[4] == "b", xs[10] == None, None == xs[10])
    print(type(xs[0]).__name__, type(xs[9]).__name__, type(xs[10]).__name__, type(xs[11]).__name__, type(xs[9]).__qualname__)
    print(callable(xs[0]), callable(xs[11]), callable(xs[12]), callable(xs[10]))


main()
