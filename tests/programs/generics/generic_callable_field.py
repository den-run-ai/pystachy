# A lambda, a builtin class or an unannotated def given for a generic class's Callable[[], T]
# parameter, whose type variables the context or the other arguments bind: the Callable it
# becomes, also in a field that __init__ stores it in unannotated; and C(...) that a lambda
# returns, which the Callable's result type binds.
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")


class Box(Generic[T]):
    def __init__(self, f: Callable[[], T]) -> None:
        self.f = f

    def get(self) -> T:
        return self.f()


class Maker(Generic[K, T]):
    def __init__(self, key: K, f: Callable[[], T] | None = None) -> None:
        self.key = key
        self.f = f

    def make(self) -> T | None:
        f = self.f
        return f() if f is not None else None


class Stack(Generic[T]):
    def __init__(self) -> None:
        self.items: list[T] = []

    def push(self, x: T) -> None:
        self.items.append(x)


def zero():
    return 0


b: Box[list[int]] = Box(list)
x = b.get()
x.append(3)
print(x, b.get(), b.f())
c = Box[float](float)
print(c.get())
d: Box[float] = Box(lambda: 1.5)
print(d.get())
e: Box[int] = Box(zero)
print(e.get(), e.f())
boxes: list[Box[str]] = [Box(str), Box(lambda: "é")]
print([bx.get() for bx in boxes])
m: Maker[str, dict[str, int]] = Maker("k", dict)
print(m.key, m.make())
n: Maker[str, int] = Maker("n")
print(n.make())
n.f = int
print(n.make())


def holder() -> Box[set[str]]:
    return Box(set)


def stack() -> Stack[int]:
    return Stack()


print(holder().get())
stacks: Box[Stack[str]] = Box(lambda: Stack())
s1 = stacks.get()
s1.push("one")
s2 = stack()
s2.push(2)
boxes2: Box[Box[list[int]]] = Box(lambda: Box(list))
inner = boxes2.get().get()
inner.append(5)
print(s1.items, stacks.get().items, s2.items, inner)


class Shelf:
    def __init__(self) -> None:
        self.box: Box[tuple[int, str]] = Box(lambda: (1, "a"))

    def take(self) -> tuple[int, str]:
        return self.box.get()


print(Shelf().take())
