# An annotation's union of a class and a class derived from it is that class also where the union
# nests or names another union: Union[Union[Base, Other], Child], an alias of Base | Other with
# Child, Optional[...] of one, quoted or written typing.Union, as for the flat Base | Other | Child
import typing
from typing import Optional, TypeAlias, Union


class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class Child(Base):
    pass


class Other:
    def __init__(self, s: str) -> None:
        self.s = s


BaseOrOther: TypeAlias = Union[Base, Other]
Either = Base | Other


def nested(k: int) -> Union[Union[Base, Other], Child]:
    return Child(k) if k > 0 else Other("o")


def aliased(k: int) -> BaseOrOther | Child:
    return Child(k) if k > 0 else Base(k)


def optional(k: int) -> Optional[Union[Child, Either]]:
    return None if k == 0 else Child(k)


def quoted(k: int) -> "typing.Union[Child, typing.Union[Other, Base]]":
    return Child(k) if k > 0 else Base(k)


def show(k: int) -> None:
    a = nested(k)
    b = aliased(k)
    c = optional(k)
    d = quoted(k)
    print(type(a).__name__, type(b).__name__, "None" if c is None else type(c).__name__, type(d).__name__)
    if isinstance(a, Base):
        print("n", a.n, isinstance(a, Child))


for k in range(2):
    show(k)
