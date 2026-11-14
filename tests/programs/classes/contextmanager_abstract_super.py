# A subclass that declares an abstract @contextmanager method again: super().NAME() runs the
# base class's body, in the same module and in another, and the object's own class's elsewhere.
from abc import abstractmethod
from contextlib import contextmanager
from typing import Iterator

from mods.cm_abstract_base import Remote


class Base:
    @abstractmethod
    @contextmanager
    def scope(self) -> Iterator[None]:
        raise NotImplementedError("base")


class Child(Base):
    @abstractmethod
    @contextmanager
    def scope(self) -> Iterator[None]:
        raise NotImplementedError("child")

    def through_super(self) -> str:
        try:
            super().scope()
            return "made"
        except NotImplementedError as e:
            return str(e)


class Local(Remote):
    @abstractmethod
    @contextmanager
    def scope(self, tag: str = "t") -> Iterator[None]:
        raise NotImplementedError("local " + tag)

    def through_super(self) -> str:
        try:
            super().scope("s")
            return "made"
        except NotImplementedError as e:
            return str(e)


def direct(b: Base) -> str:
    try:
        b.scope()
        return "made"
    except NotImplementedError as e:
        return str(e)


def own(x: Local) -> str:
    try:
        x.scope(tag="k")
        return "made"
    except NotImplementedError as e:
        return str(e)


c = Child()
print(c.through_super(), direct(c), direct(Base()))
print(Local().through_super(), own(Local()))
