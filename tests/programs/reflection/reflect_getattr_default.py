# getattr(o, "name", default) (#486): the attribute where the exact class has it, the default where
# it has not; a field __init__ may leave unassigned reads its flag, a property's AttributeError
# gives the default; o and the default are evaluated first, as CPython evaluates arguments
class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        if x > 5:
            self.z = x * 10

    @property
    def scaled(self) -> int:
        if self.x > 3:
            raise AttributeError("too big")
        return self.x * 100

    def norm(self) -> int:
        return self.x * self.x + self.y * self.y


class A:
    def __init__(self, v: int) -> None:
        self.v = v

    def __deepcopy__(self, memo: dict[int, int]) -> "A":
        return A(self.v + 100)


class B:
    def __init__(self, v: int) -> None:
        self.v = v


class Shape:
    def area(self) -> float:
        return 0.0


class Square(Shape):
    def __init__(self, s: float) -> None:
        self.s = s


def has_hook(x) -> bool:
    return getattr(x, "__deepcopy__", None) is not None


def side(sh: Shape) -> float:
    return getattr(sh, "s", -1.0)


def dflt(tag: str) -> int:
    print("default evaluated:", tag)
    return -1


p = Point(1, 2)
print(getattr(p, "x", -1), getattr(p, "w", -1), getattr(p, "z", -1), getattr(Point(7, 1), "z", -1))
print(getattr(p, "scaled", -1), getattr(Point(4, 1), "scaled", -1))
print(getattr(p, "x", dflt("x")), getattr(p, "nope", dflt("nope")))
print(getattr(p, "x", None), getattr(p, "w", "absent"))
print(has_hook(A(1)), has_hook(B(1)))
print(side(Shape()), side(Square(2.5)))
q: Point | None = None
print(getattr(q, "x", "none"))
q = Point(5, 6)
print(getattr(q, "x", "none"))
