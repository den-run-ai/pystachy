# A subclass can add a protocol absent from the base. Static base-type fallbacks must not hide
# its truth, equality or string methods, all of which plain ordinary objects support too.
from typing import Iterator


class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class Child(Base):
    def __str__(self) -> str:
        return "child:" + str(self.n)

    def __repr__(self) -> str:
        return "Child(" + str(self.n) + ")"

    def __bool__(self) -> bool:
        return self.n == 0

    def __eq__(self, other: Base) -> bool:
        return self.n == other.n


def report(obj: Base) -> None:
    print(bool(obj), obj == Base(2), obj == obj)


report(Base(2))
report(Child(2))
report(Child(0))
child: Base = Child(2)
print(str(child) == "child:2", repr(child) == "Child(2)")


class IterBase:
    def __iter__(self) -> Iterator[int]:
        print("iterate")
        return iter([1])


class ContainsChild(IterBase):
    def __contains__(self, value: int) -> bool:
        print("contains", value)
        return False


class ContainsGrandchild(ContainsChild):
    pass


def membership(obj: IterBase) -> None:
    print(1 in obj, 1 not in obj)


membership(IterBase())
membership(ContainsChild())
membership(ContainsGrandchild())


class Empty:
    pass


class AddedContains(Empty):
    def __contains__(self, value: int) -> bool:
        return value == 2


def added_membership(obj: Empty) -> None:
    print(2 in obj, 2 not in obj)


added_membership(AddedContains())
try:
    added_membership(Empty())
except TypeError as exc:
    print(exc)
try:
    added_membership(None)
except TypeError as exc:
    print(exc)
