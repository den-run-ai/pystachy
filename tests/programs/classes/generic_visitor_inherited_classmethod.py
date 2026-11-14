# A class method that uses cls, inherited, binds its TypeVar return from a visitor's generic
# base as the defining class's does: before a recursive call through cls, through a subclass
# of a subclass, and past another parameter (generic_visitor_inherited_classmethod_field.py:
# a field that self.depth(...) initializes).
from typing import Generic, TypeVar

T = TypeVar("T")


class G(Generic[T]):
    def get(self) -> T:
        raise NotImplementedError


class V(G[int]):
    def get(self) -> int:
        return 7


class W(G[str]):
    def get(self) -> str:
        return "w"


class Base:
    @classmethod
    def depth(cls, visitor: G[T], n: int) -> T:
        if n > 0:
            return cls.depth(visitor, n - 1)
        return visitor.get()

    @classmethod
    def pick(cls, label: str, visitor: G[T]) -> T:
        if label == "":
            return cls.pick("again", visitor)
        return visitor.get()


class Child(Base):
    pass


class Grandchild(Child):
    pass


print(Base.depth(V(), 2))
print(Child.depth(V(), 2))
print(Child.depth(W(), 3))
print(Grandchild.depth(V(), 1))
print(Child.pick("", V()))
print(Grandchild.pick("", W()))
