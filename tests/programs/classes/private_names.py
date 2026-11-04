# Private attributes and methods use the class where they were written, including inherited
# method bodies. Explicit mangled access works; strings and dunders keep their spelling.
class Base:
    __constant = 7

    def __init__(self) -> None:
        self.__value = 11

    def __helper(self) -> int:
        return self.__value

    def read(self) -> int:
        return self.__helper()

    def names(self) -> None:
        print(self.__helper.__name__, self.__helper.__qualname__)


class Child(Base):
    def __init__(self) -> None:
        super().__init__()
        self.__value = 23

    def __helper(self) -> int:
        return self.__value + 100

    def own(self) -> int:
        return self.__helper()


class __Leading:
    def __init__(self) -> None:
        self.__value = 3
        self.__tail_ = 4
        self.__dunder__ = 5


class ___:
    def __init__(self) -> None:
        self.__value = 6


b = Base()
c = Child()
print(b.read(), c.read(), c.own())
print(b._Base__value, c._Base__value, c._Child__value, Base._Base__constant)
print(hasattr(c, "__value"), hasattr(c, "_Base__value"), getattr(c, "_Child__value"))
print(getattr(c, "__value", -1), "__value")
b.names()
c.names()
x = __Leading()
print(x._Leading__value, x._Leading__tail_, x.__dunder__, ___().__value)
