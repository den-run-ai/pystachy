# pprint orders the keys of objects of two classes whose __lt__ declines the other class by the
# names of the classes, as CPython's _safe_key does where < raises TypeError, and those of one
# class by their own __lt__.
import pprint


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other: "Base") -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return self.n < other.n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Base) and type(self) is type(other) and self.n == other.n

    def __hash__(self) -> int:
        return self.n

    def __repr__(self) -> str:
        return "%s(%d)" % (type(self).__name__, self.n)


class A(Base):
    pass


class B(Base):
    pass


d: dict[Base, int] = {B(1): 1, A(2): 2, B(0): 3, A(1): 4}
print(pprint.pformat(d))
print(pprint.pformat(d, width=10))
print(pprint.saferepr(d))
