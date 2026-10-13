# Generic classes named with their types: C[X] as an annotation names the specialization whose
# type variables are bound to X (a variable, a field, a parameter, a return, an item type), whose
# objects a call makes where its context expects one (q: Box[int] = Box()) or C[X](...) makes; and
# Iterable[T] binds T to the items' type of the argument
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class Box(Generic[T]):
    def __init__(self, items: Iterable[T] = ()) -> None:
        self.items: list[T] = list(items)

    def push(self, x: T) -> None:
        self.items.append(x)

    def pop(self) -> T:
        return self.items.pop()

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return f"Box({self.items!r})"


class Pair(Generic[K, V]):
    def __init__(self, key: K, value: V) -> None:
        self.key = key
        self.value = value

    def swap(self) -> "Pair[V, K]":
        return Pair(self.value, self.key)


def fill(b: Box[int], n: int) -> Box[int]:
    for i in range(n):
        b.push(i * i)
    return b


def fresh() -> Box[str]:
    return Box()


class Holder:
    def __init__(self) -> None:
        self.names: Box[str] = Box()
        self.boxes: list[Box[int]] = []
        self.maybe: Box[float] | None = None


b: Box[int] = Box()
b.push(1)
print(b, len(fill(b, 3)), fill(Box(), 2), fresh(), fresh().items == [])
print(Box([1, 2]), Box("ab"), Box({"k": 1, "j": 2}), Box((4, 5)), Box({7}), Box([[1], []]))
c = Box[str]()
c.push("x")
e = Box[int]([])
e.push(3)
f: Box[list[str]] = Box([])
f.push(["y"])
print(c, e, f, Box[bool]([True]).pop())
h = Holder()
h.names.push("a")
h.boxes.append(Box([7]))
h.boxes.append(Box())
h.boxes[1].push(8)
h.maybe = Box([1.5])
print(h.names, h.boxes, h.maybe, h.maybe.pop() if h.maybe is not None else None)
o: Box[int] | None = Box()
if o is not None:
    o.push(9)
print(o)
p = Pair("k", 1)
q: Pair[int, str] = p.swap()
print(p.key, p.value, q.key, q.value, Pair[str, float]("pi", 3.14).value)


class Stack(Generic[T]):
    # a generic class whose __init__ takes no T: what its objects are bound to comes from where
    # they go, or the call
    def __init__(self) -> None:
        self.items: list[T] = []

    def push(self, x: T) -> "Stack[T]":
        self.items.append(x)
        return self


st: Stack[str] = Stack()
print(st.push("a").push("b").items, Stack[int]().push(1).items, len(Holder().boxes))
