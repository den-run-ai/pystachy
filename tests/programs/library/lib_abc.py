# abc (lib/_pystachy_abc.py, which Pystachy loads for import abc): abstract methods of a class
# deriving from ABC or passing metaclass=ABCMeta, also under @property, @classmethod and
# @staticmethod and through the deprecated decorators, implemented down a hierarchy and called
# through super(); making an object of a class that leaves one abstract raises CPython's TypeError
# once the arguments are evaluated; a class with no ABC base is not abstract
import abc
from abc import ABC, ABCMeta, abstractmethod


class Base(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def value(self) -> int:
        print("Base.value runs", self.name)
        return 1

    @property
    @abstractmethod
    def size(self) -> int:
        ...

    @classmethod
    @abstractmethod
    def make(cls) -> str:
        ...

    @staticmethod
    @abstractmethod
    def helper() -> str:
        ...

    def total(self) -> int:
        return self.value() + self.size


class Partial(Base):
    @property
    def size(self) -> int:
        return 10

    @classmethod
    def make(cls) -> str:
        return "made"


class Full(Partial):
    def value(self) -> int:
        return super().value() + 1

    @staticmethod
    def helper() -> str:
        return "help"


class Meta(metaclass=ABCMeta):
    @abc.abstractmethod
    def run(self) -> None:
        ...


class MetaImpl(Meta):
    def run(self) -> None:
        print("MetaImpl.run")


class NotABC:
    @abstractmethod
    def f(self) -> int:
        return 5


class Attr(ABC):
    @abstractmethod
    def limit(self) -> int:
        ...


def arg(n: int) -> int:
    print("arg", n)
    return n


def build(k: int) -> None:
    try:
        if k == 0:
            Base(str(arg(1)))
        elif k == 1:
            Partial(name=str(arg(2)))
        elif k == 2:
            Meta()
        elif k == 3:
            Attr()
    except TypeError as e:
        print("TypeError:", e)


f = Full("full")
print(f.total(), f.size, Full.make(), Full.helper(), f.helper())
print(isinstance(f, Base), isinstance(f, ABC), isinstance(f, Partial))
for k in range(4):
    build(k)
MetaImpl().run()
print(NotABC().f(), abc.get_cache_token() == abc.get_cache_token())


def score(b: Base) -> int:
    return b.value()


print(score(f), score(Full("other")))


class Old(ABC):
    @abc.abstractproperty
    def p(self) -> int:
        ...

    @abc.abstractclassmethod
    def c(cls) -> int:
        ...

    @abc.abstractstaticmethod
    def s() -> int:
        ...


class OldImpl(Old):
    @property
    def p(self) -> int:
        return 1

    @classmethod
    def c(cls) -> int:
        return 2

    @staticmethod
    def s() -> int:
        return 3


class ModMeta(metaclass=abc.ABCMeta):
    @abstractmethod
    def go(self) -> int:
        ...


o = OldImpl()
print(o.p, OldImpl.c(), OldImpl.s())
for k in range(2):
    try:
        if k == 0:
            Old()
        else:
            ModMeta()
    except TypeError as e:
        print("TypeError:", e)
