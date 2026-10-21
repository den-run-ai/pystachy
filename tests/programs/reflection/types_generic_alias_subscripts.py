# A class whose body binds __class_getitem__ = classmethod(GenericAlias), CPython's idiom for a
# generic class, may be subscripted in annotations, evaluated or quoted: C[int] annotates an object
# of C, whose fields keep their one type each, as CPython does not check the subscript; so does a
# module's type alias of one
from types import GenericAlias
import types


class Queue:
    __class_getitem__ = classmethod(GenericAlias)

    def __init__(self) -> None:
        self.items: list[int] = []

    def put(self, x: int) -> None:
        self.items.append(x)


class Pair:
    __class_getitem__ = classmethod(types.GenericAlias)

    def __init__(self, a: str, b: str) -> None:
        self.a = a
        self.b = b


def fill(q: Queue[int], n: int) -> Queue[int]:
    for i in range(n):
        q.put(i)
    return q


def swap(p: "Pair[str, str]") -> Pair[str, str]:
    return Pair(p.b, p.a)


q: Queue[float] = fill(Queue(), 3)
print(q.items, isinstance(q, Queue))
p = swap(Pair("x", "y"))
print(p.a, p.b)
pairs: list[Pair[str, str]] = [p, swap(p)]
print([x.a + x.b for x in pairs])
nothing: Queue[int] | None = None
print(nothing is None)
# (a module's alias of a subscript is a type alias, which annotations name)
IntQueue = Queue[int]


def total(q: IntQueue) -> int:
    return sum(q.items)


print(total(fill(Queue(), 4)))
