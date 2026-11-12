"""Objects under construction: each field a class's code reads without an "is assigned" flag test
is assigned before that code can see the object (fl_fields)."""
from dataclasses import dataclass, field


class Point:
    scale = 2  # (a class attribute's default, stored where the object is made)

    def __init__(self, x: int, y: int, label: str) -> None:
        self.x = x * self.scale
        self.y = y
        if label:
            self.label = label  # (assigned on one path only: flagged)
        self.name = "p" + str(self.x)

    def show(self) -> str:
        return self.name + " " + str(self.x + self.y)


class Node:
    def __init__(self, value: int, after: "Node | None") -> None:
        self.value = value
        self.after = after


def chain(n: int) -> int:
    # (each allocation in the loop is complete before the next one runs)
    head: Node | None = None
    for i in range(n):
        head = Node(i, head)
    total = 0
    while head is not None:
        total += head.value
        head = head.after
    return total


def either(flag: bool) -> str:
    p = Point(1, 2, "a") if flag else Point(3, 4, "")
    return p.show()


class Shape:
    def __init__(self, sides: int) -> None:
        self.sides = sides

    def area(self) -> int:
        return 0


class Square(Shape):
    def __init__(self, side: int) -> None:
        super().__init__(4)
        self.side = side

    def area(self) -> int:
        return self.side * self.side


def areas(shapes: list[Shape]) -> int:
    # (each call dispatches on its object's class tag)
    return sum([s.area() for s in shapes])


class AppError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.msg = msg

    def fmt(self, code: int) -> str:
        return "code " + str(code)


class CodeError(AppError):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(super().fmt(code))  # (fmt reads none of the fields not yet assigned)


class Labeled(AppError):
    msg = "class message"  # (a class variable shadowing AppError's field)

    def __init__(self) -> None:
        pass


def message(e: AppError) -> str:
    return e.msg  # (a Labeled object's class variable, through AppError's view)


class Memo:
    def __init__(self, seed: int) -> None:
        # (only hasattr tests table's flag: no read finds it unassigned)
        if not hasattr(self, "table"):
            self.table: dict[int, int] = {}
        self.table[seed] = seed * seed

    def get(self, key: int) -> int:
        return self.table.get(key, -1)


@dataclass
class Bag:
    name: str
    items: list[int] = field(default_factory=list)


def bagged(n: int) -> int:
    b = Bag("b")
    for i in range(n):
        b.items.append(i)
    return len(b.items)


Labeled.msg = "rebound"
print(Point(1, 2, "q").show(), chain(4), either(True), either(False))
print(Square(3).area(), areas([Square(2), Shape(5)]), bagged(3), Memo(4).get(4), Memo(2).get(3))
try:
    raise CodeError(7)
except AppError as e:
    print(e, e.msg)
print(Labeled().msg, message(Labeled()), repr(str(Labeled())))
