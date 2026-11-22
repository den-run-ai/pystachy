# isinstance() of an object of a class deriving from list or dict against collections.abc's
# classes answers as the builtin's objects do: builtin_bases.py's classes meet cabc_isinst
from collections.abc import Collection, Container, Hashable, Iterable, Mapping, MutableMapping, MutableSequence, Reversible, Sequence, Sized


class Stack(list[int]):
    def top(self) -> int:
        return self[-1]


class Registry(dict[str, int]):
    def total(self) -> int:
        return sum(self.values())


def main() -> None:
    s = Stack([1, 2, 3])
    r = Registry(a=1)
    print(isinstance(s, Sequence), isinstance(s, MutableSequence), isinstance(s, Hashable), isinstance(s, Mapping))
    print(isinstance(s, Sized), isinstance(s, Iterable), isinstance(s, Reversible), isinstance(s, Container), isinstance(s, Collection))
    print(isinstance(r, Mapping), isinstance(r, MutableMapping), isinstance(r, Sequence), isinstance(r, Hashable), isinstance(r, Sized))
    print(s.top(), r.total())


main()
