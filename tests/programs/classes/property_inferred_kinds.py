# Inferred getters of generic classes (typed for each specialization), named tuples,
# dataclasses, enums, classes with __slots__ and exception classes.
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Generic, NamedTuple, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v

    @property
    def value(self):
        return self.v

    @property
    def pair(self):
        return (self.v, self.v)


class Stack[U]:
    def __init__(self) -> None:
        self.items: list[U] = []

    def push(self, u: U) -> None:
        self.items.append(u)

    @property
    def top(self):
        return self.items[-1]

    @property
    def size(self):
        return len(self.items)


print(Box(3).value + 1, Box("s").value.upper(), Box(2.5).pair)
st: Stack[str] = Stack()
st.push("a")
st.push("b")
print(st.top + "!", st.size)


class P(NamedTuple):
    x: int
    y: int

    @property
    def total(self):
        return self.x + self.y

    @property
    def flipped(self):
        return P(self.y, self.x)


print(P(1, 2).total, P(1, 2).flipped, P(1, 5).flipped.x)


@dataclass
class D:
    x: int
    y: int

    @property
    def norm1(self):
        return abs(self.x) + abs(self.y)

    @property
    def swapped(self):
        return D(self.y, self.x)


print(D(3, -4).norm1, D(3, -4).swapped, D(3, -4).swapped.swapped.x)


class Status(IntEnum):
    OK = 200
    MISSING = 404

    @property
    def is_success(self):
        return 200 <= self <= 299

    @property
    def text(self):
        return self.name.lower()


class Color(Enum):
    RED = 1
    BLUE = 2

    @property
    def warm(self):
        return self is Color.RED


for s in Status:
    print(s, s.is_success, s.text)
for c in Color:
    print(c, c.warm)


class V:
    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    @property
    def length2(self):
        return self.x * self.x + self.y * self.y

    @property
    def neg(self):
        return V(-self.x, -self.y)


print(V(3.0, 4.0).length2, V(3.0, 4.0).neg.x, V(1.0, 2.0).neg.neg.length2)


class AppError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code

    @property
    def fatal(self):
        return self.code >= 500

    @property
    def summary(self):
        return f"{self.code}: {self}"


for e in [AppError(500, "boom"), AppError(404, "page")]:
    try:
        raise e
    except AppError as x:
        print(x.fatal, x.summary)
