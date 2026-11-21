# issubclass() with collections.abc's classes: a builtin class answers as its objects do, a class
# by its methods or the ABC it derives from; an object of a base class answers by its own class,
# and so do the members of a union
from collections.abc import Hashable, Iterable, Mapping, MutableMapping, Sequence, Sized
import typing


class Base:
    def name(self) -> str:
        return "base"


class WithLen(Base):
    def __len__(self) -> int:
        return 2


class WithIter(Base):
    def __iter__(self):
        return iter([1, 2])


class Pal(Sequence):
    def __getitem__(self, i: int) -> str:
        return "abcba"[i]

    def __len__(self) -> int:
        return 5


def kinds(x: Base) -> str:
    return f"{isinstance(x, Sized)} {isinstance(x, Iterable)} {isinstance(x, Hashable)}"


def num_or_list(x: int | list[int]) -> bool:
    return isinstance(x, Iterable)


def klass(k: type[Base]) -> bool:
    return issubclass(k, Sized)


print(kinds(Base()), kinds(WithLen()), kinds(WithIter()))
print(num_or_list(3), num_or_list([3]))
print(issubclass(dict, Mapping), issubclass(list, MutableMapping), issubclass(str, Sequence), issubclass(int, Hashable), issubclass(list, Hashable))
print(issubclass(Pal, Sequence), issubclass(Pal, typing.Sequence), issubclass(Pal, Hashable), issubclass(Base, Iterable), issubclass(WithLen, Sized))
print(klass(Base), klass(WithLen), klass(WithIter))
