# pystachy: dynamic-any
# Class objects held as Any values give their class attributes and call their static and class
# methods, as the classes named in the source do; a name a class lacks is CPython's
# AttributeError, found before the arguments are evaluated (#1393).
from typing import Any


class Base:
    tag = "base"
    count = 3
    names: list[Any] = ["x", "y"]
    limit: int = 10

    def __init__(self, n: int) -> None:
        self.n = n

    @staticmethod
    def kind() -> str:
        return "base-kind"

    @staticmethod
    def add(a: int, b: int = 5) -> int:
        return a + b

    @classmethod
    def label(cls) -> str:
        return "label of " + cls.__name__

    @classmethod
    def make(cls, n: int) -> "Base":
        return cls(n)

    def show(self) -> str:
        return f"<{self.n}>"


class Derived(Base):
    tag = "derived"


class Plain:
    @staticmethod
    def kind() -> str:
        return "plain-kind"

    @classmethod
    def who(cls) -> str:
        return cls.__name__


class Special(Plain):
    @staticmethod
    def kind() -> str:
        return "special-kind"

    @classmethod
    def who(cls) -> str:
        return "special " + cls.__name__


class Other:
    tag = 7

    @staticmethod
    def loose(x, y=2):
        return [x, y]


def side(log: list[str], v: int) -> int:
    log.append("side")
    return v


held: list[Any] = [Base(1), Derived(2), Other()]
ks: list[Any] = [Base, Derived, Other]
for k in ks:
    print(k.__name__, k.tag, getattr(k, "tag", "none"), getattr(k, "absent", "none"))
for k in ks[:2]:
    print(k.kind(), k.count, k.names, k.limit, k.add(1), k.add(1, 2), k.add(b=4, a=3), k.label())
    o = k.make(9)
    print(type(o).__name__, o.n, o.show())
k: Any = Other
print(k.loose(1), k.loose("a", y=None))
log: list[str] = []
for k in ks:
    try:
        print(k.absent)
    except AttributeError as e:
        print("AttributeError:", e)
    try:
        print(k.absent(side(log, 1)))
    except AttributeError as e:
        print("AttributeError:", e, log)
k = Base
try:
    print(k.add())
except TypeError as e:
    print("TypeError:", e)
try:
    print(k.add(1, 2, 3))
except TypeError as e:
    print("TypeError:", e)
try:
    print(k.add(1, c=3))
except TypeError as e:
    print("TypeError:", e)
try:
    print(k.kind(side(log, 2)))
except TypeError as e:
    print("TypeError:", e, log)
try:
    print(k.count())
except TypeError as e:
    print("TypeError:", e)
reg: dict[str, Any] = {"b": Base, "d": Derived, "p": Plain, "s": Special}
print([reg[n].kind() for n in sorted(reg)])
print([reg[n].who() for n in ["p", "s"]])
x: Any = Base(4)
print(x.tag, x.kind(), x.count)
