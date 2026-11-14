# None binds a generic class's type variable where no other argument binds it: Box(None) is a
# Box[None], as a type checker infers it, and so is an annotation or a call naming Box[None]
# (asyncio's Future[None] and Task[None]). Fields that the variable types, T and T | None,
# hold None, also where a method stores them again; list[T] is a list[None], which prints,
# compares and iterates as CPython's does. Box(1) keeps its own specialization. (Pair(None, [1])
# stays an error: tests/errors/generics/generic_none_conflict.py.)
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v
        self.items: list[T] = [v]

    def get(self) -> T:
        return self.v

    def put(self, v: T) -> None:
        self.v = v
        self.items.append(v)

    def __repr__(self) -> str:
        return f"Box({self.v!r}, {self.items!r})"


b = Box(None)
print(b.v, b.get(), b)
b.put(None)
print(b.items, len(b.items), b.items == [None, None], b.items[1], None in b.items)
for x in b.items:
    print("item", x)
c: Box[None] = Box(None)
print(c.get() is None, c)
d = Box[None](None)
print(d.items)
i = Box(3)
print(i.get() + 1, i)


class Fut[R]:
    def __init__(self) -> None:
        self._result: R | None = None
        self._done = False

    def set_result(self, r: R) -> None:
        self._result = r
        self._done = True

    def result(self) -> R | None:
        return self._result


f: Fut[None] = Fut()
print(f.result(), f._done)
f.set_result(None)
print(f.result(), f._done)
g: Fut[int] = Fut()
g.set_result(5)
print(g.result())
NoneFut = Fut[None]
h: NoneFut = Fut()
print(h.result())
k: "Fut[None]" = Fut()
print(k.result())


class Opt(Generic[T]):
    def __init__(self, v: Optional[T]) -> None:
        self.v = v


print(Opt[None](None).v)


def collect(n: int, v: T) -> list[T]:
    return [v for i in range(n)]


print(collect(2, 1), collect(3, None))
