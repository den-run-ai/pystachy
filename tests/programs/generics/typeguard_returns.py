# A function annotated to return TypeGuard[T] or TypeIs[T] (typing's) returns a bool, as in
# mypyc's rtypes.py, whose is_tagged(rtype) returns TypeGuard[RPrimitive] and whose
# RVoid.__eq__(other) returns TypeGuard[RVoid]. A static checker narrows the argument by such a
# predicate; Pystachy narrows by the code's own tests (isinstance(), is None, ...).
from typing import TypeGuard, TypeIs


class RType:
    pass


class RPrimitive(RType):
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> TypeGuard["RPrimitive"]:
        return isinstance(other, RPrimitive) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)


def is_primitive(t: RType) -> TypeGuard[RPrimitive]:
    return isinstance(t, RPrimitive)


def is_int(x: object) -> TypeIs[int]:
    return isinstance(x, int) and not isinstance(x, bool)


a = RPrimitive("int")
print(a == RPrimitive("int"), a == RPrimitive("str"), a != RPrimitive("str"), is_primitive(a), is_primitive(RType()))
print(is_int(3), is_int(True), is_int("3"))
items: list[RType] = [a, RType()]
flags = [is_primitive(t) for t in items]
print(flags, is_int(1) is True, len({a, RPrimitive("int")}))
