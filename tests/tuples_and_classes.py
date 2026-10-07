from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


def divmod2(a: int, b: int) -> tuple[int, int]:
    return a // b, a % b


q, r = divmod2(17, 5)
print(q, r, divmod2(-17, 5))
a, b = 1, 2
a, b = b, a
print(a, b)
t = (1, "two", 3.0, True)
print(t, t[0], t[1], t[-1], len(t), (5,), (1, 2) == (1, 2), (1, 2) < (1, 3), (2, "a") > (1, "z"))
pts = [(3, "c"), (1, "a"), (2, "b"), (1, "Z")]
pts.sort()
print(pts, sorted(pts)[0], (2, "b") in pts)
for n, s in pts:
    print(n, s, end=", ")
print()


class Vec:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def add(self, o: Vec) -> Vec:
        return Vec(self.x + o.x, self.y + o.y)

    def scale(self, k: float = 2.0) -> Vec:
        return Vec(self.x * k, self.y * k)

    def __str__(self) -> str:
        return f"Vec({self.x}, {self.y})"


v = Vec(1.0, 2.0).add(Vec(0.5, 0.5))
print(v, v.scale(), v.scale(k=-1.0), str(v.scale(0.5)), v.x)


class Node:
    def __init__(self, val: int, next: Optional[Node] = None):
        self.val = val
        self.next = next


class LinkedList:
    count: int = 0

    def __init__(self):
        self.head: Node | None = None

    def push(self, v: int) -> None:
        self.head = Node(v, self.head)
        self.count += 1

    def total(self) -> int:
        s = 0
        n = self.head
        while n is not None:
            s += n.val
            n = n.next
        return s

    def items(self) -> list[int]:
        out: list[int] = []
        n = self.head
        while n:
            out.append(n.val)
            n = n.next
        return out


ll = LinkedList()
for i in range(1, 6):
    ll.push(i * i)
print(ll.count, ll.total(), ll.items(), ll.head is not None, ll.head.next.val)
empty = LinkedList()
print(empty.head is None, empty.total(), empty.items(), empty.count)


@dataclass
class Item:
    name: str
    price: float
    qty: int = 1

    def cost(self) -> float:
        return self.price * self.qty


cart = [Item("pen", 1.5, 4), Item("book", 12.25), Item(qty=3, name="mug", price=4.0)]
print([it.name for it in cart], sum([it.cost() for it in cart]), cart[2].qty)
by_name: dict[str, Item] = {}
for it in cart:
    by_name[it.name] = it
by_name["pen"].qty += 1
print(by_name["pen"].qty, cart[0].qty, by_name["book"] is cart[1], cart[0] == cart[1], cart[0] == by_name["pen"])


class Counter:
    def __init__(self, start: int = 0, step: int = 1):
        self.n = start
        self.step = step
        self.history: list[int] = []

    def tick(self) -> int:
        self.history.append(self.n)
        self.n += self.step
        return self.n


c = Counter(step=3)
while c.tick() < 10:
    pass
print(c.n, c.history, Counter(5).tick())
print(cart[0], Item("a", 1.0) == Item("a", 1.0), Item("a", 1.0) != Item("a", 2.0), [Item("z", 0.5)][0])
