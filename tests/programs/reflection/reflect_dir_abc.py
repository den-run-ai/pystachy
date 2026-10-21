# dir() and hasattr() of objects of classes ABCMeta makes (a class deriving from abc.ABC, or whose
# statement passes metaclass=ABCMeta): they also have __abstractmethods__ and _abc_impl, and
# ABC's __slots__; their __dict__ is their own fields'
from abc import ABC, ABCMeta, abstractmethod


class Plain:
    pass


class Shape(ABC):
    def __init__(self, n: int) -> None:
        self.n = n

    @abstractmethod
    def area(self) -> int: ...


class Square(Shape):
    def area(self) -> int:
        return self.n * self.n


class Meta(metaclass=ABCMeta):
    pass


base = set(dir(Plain()))
print(sorted(set(dir(Square(2))) - base))
print(sorted(set(dir(Meta())) - base))
print(hasattr(Square(2), "_abc_impl"), hasattr(Meta(), "__abstractmethods__"), hasattr(Plain(), "_abc_impl"))
names = ["n", "area", "_abc_impl", "__abstractmethods__", "__slots__", "zz"]
print([x for x in names if hasattr(Square(3), x + "")])
print(vars(Square(4)), type(Square(4)).__name__)
