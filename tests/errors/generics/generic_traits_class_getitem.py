# error: generic_traits_class_getitem.py:23: error: G[...] with a custom __class_getitem__ is not supported
# A generic class's own type variable passed on to a generic base (G[T]) still subscripts that base:
# CPython calls its custom __class_getitem__ (which may run code, or name another class, here Other).
from typing import Generic, TypeVar

T = TypeVar("T")


class Other:
    def value(self) -> int:
        return 42


class G(Generic[T]):
    def __class_getitem__(cls, item):
        print("subscript")
        return Other

    def value(self) -> int:
        return 7


class N(Generic[T], G[T]):
    pass


print(N().value())
