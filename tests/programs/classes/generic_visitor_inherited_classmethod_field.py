# A field that an inherited class method that uses cls initializes: its TypeVar return binds
# from the visitor's generic base, as the defining class's does.
from typing import Generic, TypeVar

T = TypeVar("T")


class G(Generic[T]):
    def get(self) -> T:
        raise NotImplementedError


class V(G[int]):
    def get(self) -> int:
        return 7


class Base:
    @classmethod
    def depth(cls, visitor: G[T], n: int) -> T:
        if n > 0:
            return cls.depth(visitor, n - 1)
        return visitor.get()


class Kid(Base):
    def __init__(self) -> None:
        self.value = self.depth(V(), 1)


print(Kid().value + 1)
