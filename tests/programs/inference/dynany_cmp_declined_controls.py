# pystachy: dynamic-any
# Unavailable lower-priority methods must not preempt a supported subclass
# method. None still reaches an optional operand annotation in either order.
from typing import Any


class Nullable:
    def __eq__(self, other: "Nullable | None") -> bool:
        print("nullable eq", other is None)
        return other is None


class Base:
    def __eq__(self, other: int) -> bool:
        print("base eq")
        return False

    def __lt__(self, other: int) -> bool:
        print("base lt")
        return False


class Child(Base):
    def __eq__(self, other: Base) -> bool:
        print("child eq")
        return True

    def __gt__(self, other: Base) -> bool:
        print("child gt")
        return True


nullable: Any = Nullable()
other: Any = Nullable()
none: Any = None
print(nullable == none, none == nullable)
print(nullable != none, none != nullable)
print(nullable == other, nullable != other, none == none)
print([nullable] == [none], [none] == [nullable])
base: Any = Base()
child: Any = Child()
print(base == child, child == base, child == child)
print(base != child, child != base, child != child)
print(base < child, child > base)
print(base == 1, base < 1)
