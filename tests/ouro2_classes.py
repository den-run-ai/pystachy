from __future__ import annotations


class Point:
    x: int
    y: int

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def add(self, o: Point) -> Point:
        return Point(self.x + o.x, self.y + o.y)

    def norm1(self) -> int:
        return abs(self.x) + abs(self.y)

    def show(self) -> str:
        return "(" + str(self.x) + ", " + str(self.y) + ")"


class Node:
    val: int
    next: Node

    def __init__(self, val: int, next: Node) -> None:
        self.val = val
        self.next = next


class Stack:
    top: Node
    size: int
    log: list[str]

    def __init__(self) -> None:
        self.top = None
        self.size = 0
        self.log = []

    def push(self, v: int) -> None:
        self.top = Node(v, self.top)
        self.size += 1
        self.log.append("push " + str(v))

    def pop(self) -> int:
        n = self.top
        self.top = n.next
        self.size -= 1
        return n.val

    def empty(self) -> bool:
        return self.top is None


class Counter:
    n: int

    def __init__(self) -> None:
        self.n = 0

    def bump(self) -> int:
        self.n += 1
        return self.n


class Tree:
    left: Tree
    right: Tree
    key: int

    def __init__(self, key: int) -> None:
        self.key = key
        self.left = None
        self.right = None

    def insert(self, key: int) -> None:
        if key < self.key:
            if self.left is None:
                self.left = Tree(key)
            else:
                self.left.insert(key)
        elif self.right is None:
            self.right = Tree(key)
        else:
            self.right.insert(key)

    def walk(self, out: list[int]) -> None:
        if self.left is not None:
            self.left.walk(out)
        out.append(self.key)
        if self.right is not None:
            self.right.walk(out)


p = Point(1, 2).add(Point(10, -20))
print(p.show(), p.norm1(), p.x, p.y)
p.x = 99
p.y += 1
print(p.show())
s = Stack()
for i in range(5):
    s.push(i * i)
print(s.size, s.pop(), s.pop(), s.size, s.empty(), len(s.log), s.log[4])
while not s.empty():
    s.pop()
print(s.empty(), s.top is None)
c = Counter()
c.bump()
print(c.bump(), c.n)
t = Tree(50)
for k in [30, 70, 20, 40, 60, 80, 35, 65]:
    t.insert(k)
keys: list[int] = []
t.walk(keys)
line = ""
for k in keys:
    line = line + str(k) + " "
print(line)
pts = [Point(1, 1), Point(2, 2)]
pts.append(Point(3, 3))
sx = 0
for q in pts:
    sx += q.x
print(sx, pts[0] is pts[0], pts[0] is pts[1], pts[0] == pts[0], pts[1] != pts[2])
none: Point = None
print(none is None, p is not None)
