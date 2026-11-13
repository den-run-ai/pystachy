# error: iterator_base_call_subscript.py:11: error: unsupported base class
# CPython prints base evaluated 1 first: it evaluates the base's subscript, a call, where the class statement runs
from typing import Iterable, Iterator


def pick(n: int) -> str:
    print("base evaluated", n)
    return "int"


class Once(Iterable[pick(1)]):
    def __iter__(self) -> Iterator[int]:
        return iter([1])


print(list(Once()))
