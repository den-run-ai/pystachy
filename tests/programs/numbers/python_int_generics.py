# pystachy: python-int
# Promoting ints (docs/python-int.md) as the ints that a generic class's type variable binds: an
# annotation Box[int], a call Box(1) or Box(2 ** 70), and a class of a module that does not opt in
# (fixed_generics) make objects of one class, whose fields, parameters, results and containers of T
# hold promoting ints, past 64 bits and -2**63 too, in every module of the program.
from typing import Generic, TypeVar
from fixed_generics import Stack, made, pushed

T = TypeVar("T")
K = TypeVar("K")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v

    def get(self) -> T:
        return self.v

    def put(self, v: T) -> None:
        self.v = v


class Table(Generic[K, T]):
    def __init__(self, k: K, v: T) -> None:
        self.rows: dict[K, T] = {k: v}
        self.pairs: list[tuple[K, T]] = [(k, v)]

    def add(self, k: K, v: T) -> None:
        self.rows[k] = v
        self.pairs.append((k, v))

    def get(self, k: K) -> T:
        return self.rows[k]


def doubled(b: Box[int]) -> int:
    return b.get() * 2


big = 2 ** 70
low = -(2 ** 63)
b: Box[int] = Box(1)
b.put(big)
c = Box(1)
c.put(low)
print(b.get(), c.get(), doubled(b), doubled(Box(3)), doubled(c))
boxes = [Box(1), Box(big), b, c]
print([x.get() for x in boxes], [type(x).__name__ for x in boxes][0])
t = Table("a", big)
t.add("b", low)
t.add("c", 5)
print(t.get("a"), t.get("b"), t.get("c") + big, t.rows, t.pairs)
u: Table[int, int] = Table(big, 1)
u.add(-big, big)
print(u.get(big), u.get(-big), sorted(u.rows), u.pairs)
# a class of a module that does not opt in
s = Stack(1)
s.push(big)
s.push(low)
print(s.peek(), s.total(), s.pop(), s.pop(), s.peek())
m = made(7)
pushed(m, big)
m.push(-big)
print(m.items, m.total(), m.pop(), m.pop(), m.pop())
n: Stack[int] = Stack(big)
pushed(n, 1)
print(n.items, n.peek(), n.total())
