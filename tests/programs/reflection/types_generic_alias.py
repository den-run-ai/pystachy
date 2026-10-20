# Pystachy's types module has GenericAlias for CPython's idiom for a generic class,
# __class_getitem__ = classmethod(GenericAlias) in a class body, which defines nothing in
# Pystachy: the classes work as they do without it, whichever way the module names GenericAlias,
# also in a block and in a subclass. Its other names import as in CPython (unused here), also in an
# optional import, whose except clause runs in neither; types.TracebackType is the class of what a
# with statement passes to __exit__ (an object, where an exception reaches it, else None)
import sys
import types
import types as _types
from types import FunctionType, GenericAlias

try:
    from types import MappingProxyType
except ImportError:
    print("no MappingProxyType")


class Queue:
    __class_getitem__ = classmethod(GenericAlias)

    def __init__(self) -> None:
        self.items: list[int] = []

    def put(self, x: int) -> None:
        self.items.append(x)


class Stack(Queue):
    __class_getitem__ = classmethod(types.GenericAlias)

    def top(self) -> int:
        return self.items[-1]


if sys.platform != "win32":
    class Pair:
        """A pair of ints."""
        __class_getitem__ = classmethod(_types.GenericAlias)
        first: int = 1
        second: int = 2


class Managed:
    def __enter__(self) -> "Managed":
        return self

    def __exit__(self, typ: type[BaseException] | None, value: BaseException | None, tb: types.TracebackType | None) -> bool:
        print("exit", value is None, tb is None, isinstance(tb, types.TracebackType))
        return True


with Managed():
    pass
with Managed():
    raise ValueError("suppressed")
q = Queue()
q.put(3)
s = Stack()
s.put(4)
s.put(5)
p = Pair()
print(q.items, s.items, s.top(), p.first + p.second, isinstance(s, Queue))
