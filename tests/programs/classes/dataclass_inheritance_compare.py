# Comparisons in a hierarchy of dataclasses: a base's own __eq__ is used where a subclass's
# generated one declines an object of another class, and with None; an init=False field
# without a default is unassigned until a method sets it.
from dataclasses import dataclass, field


@dataclass(order=True)
class Base:
    x: int
    cache: dict[str, int] = field(init=False, repr=False, compare=False)

    def fill(self) -> None:
        self.cache = {"x": self.x}

    def __eq__(self, other: "Base") -> bool:
        print("Base.__eq__")
        return self.x == other.x


@dataclass(order=True)
class Derived(Base):
    y: int = 0


b: Base = Base(1)
d: Base = Derived(1, 2)
try:
    print(d.cache)
except AttributeError as e:
    print("AttributeError", e)
d.fill()
print(d.cache, d)
print(b == d, d == b, d == Derived(1, 2), b == Base(1))
n: Base | None = None
print(d == n, n == d, d != n)
try:
    print(d < n)
except TypeError as e:
    print("TypeError", e)
try:
    print(b < d)
except TypeError as e:
    print("TypeError", e)
print(d > Derived(1, 1), b >= Base(0))


def pick(xs: list[Base], k: int) -> Base:
    def key(v: Base) -> int:
        return v.x * k

    return max(xs, key=key)


print(pick([b, d, Derived(5)], -1))
