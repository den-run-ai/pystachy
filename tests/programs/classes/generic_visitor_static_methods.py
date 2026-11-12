# A static or class method -> T whose parameter is annotated with a generic class's G[T] is bound
# by its argument's class, as a method's is: a class method's cls and a static method's missing
# self do not count among its parameters, here by direct calls, a recursive call through cls and
# self.m(...) calls that type the fields value and label.
from typing import Generic, TypeVar

T = TypeVar("T")


class G(Generic[T]):
    def visit(self) -> T:
        raise NotImplementedError()


class A(G[int]):
    def visit(self) -> int:
        return 1


class B(G[str]):
    def visit(self) -> str:
        return "b"


class Host:
    def __init__(self) -> None:
        self.value = self.pick(A(), B())
        self.label = self.fixed(B(), 3)

    @classmethod
    def pick(cls, visitor: G[T], other: B) -> T:
        return visitor.visit()

    @staticmethod
    def fixed(visitor: G[T], n: int) -> T:
        return visitor.visit()

    @classmethod
    def depth(cls, visitor: G[T], n: int) -> T:
        if n == 0:
            return visitor.visit()
        return cls.depth(visitor, n - 1)


h = Host()
print(Host.pick(A(), B()) + 1, h.value + 1, h.label.upper())
print(Host.depth(A(), 3) + 1, Host.depth(B(), 2).upper(), Host.fixed(A(), 0) + 1)
