# isinstance() of a protocol's value with a builtin type tests its object's type (a str, a list, a
# tuple or a dict implements a protocol of __len__), and narrows it to str as to a class; a
# container's test narrows nothing; callable() is its object's class's answer
from typing import Protocol


class Sized(Protocol):
    def __len__(self) -> int: ...


class Bag:
    def __len__(self) -> int:
        return 3


class Caller:
    def __len__(self) -> int:
        return 0

    def __call__(self) -> str:
        return "called"


def show(s: Sized) -> str:
    if isinstance(s, str):
        return "str " + s.upper()
    if isinstance(s, list):
        return "list " + str(len(s))
    return "other " + str(len(s))


def main() -> None:
    items: list[Sized] = ["ab", [1, 2], Bag(), (1,), {"k": 1}, Caller()]
    for s in items:
        print(show(s), isinstance(s, (tuple, dict)), isinstance(s, int), callable(s))


main()
