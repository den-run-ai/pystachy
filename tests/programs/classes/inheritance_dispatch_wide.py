# A call through a base of more than eight concrete classes selects its override in a
# function shared by every call with the same argument types (Gen.dispatch_call), not with
# an arm for each class at each call site. Overrides keep their own defaults, keywords bind
# as they would, results join to their common type, recursion and exceptions pass through,
# and a None receiver raises before the override runs, after the receiver and arguments.
from typing import Callable

events: list[str] = []


class Node:
    def __init__(self, n: int) -> None:
        self.n = n

    def value(self, extra: int = 1) -> int:
        return self.n + extra

    def scale(self, k: float) -> float:
        return self.n * k

    def child(self) -> "Node":
        return self

    def note(self, tag: str = "node") -> None:
        events.append(f"{tag}:{self.n}")

    def accept(self, v: "Visitor") -> int:
        return v.visit_node(self)

    def explode(self, depth: int) -> int:
        return depth

    def show(self, x) -> str:
        return f"{type(self).__name__}={x}"


class A(Node):
    def value(self, extra: int = 2) -> int:
        return self.n * 10 + extra


class B(Node):
    def value(self, extra: int = 3) -> int:
        return self.n * 100 + extra

    def note(self, tag: str = "b") -> None:
        events.append(f"B {tag}:{self.n}")


class C(Node):
    def child(self) -> "Leaf":
        return Leaf(self.n + 1)


class D(Node):
    def explode(self, depth: int) -> int:
        if depth >= 2:
            raise ValueError(f"too deep at {depth}")
        return D(self.n).explode(depth + 1) + 1


class E(Node):
    def scale(self, k: float) -> float:
        return k - self.n

    def show(self, x) -> str:
        return f"E{x}{x}"


class F(Node):
    def accept(self, v: "Visitor") -> int:
        return v.visit_f(self)


class G(F):
    pass


class H(F):
    def value(self, extra: int = 8) -> int:
        self.n += 1
        return self.n + extra


class Pair(Node):
    def __init__(self, left: Node, right: Node) -> None:
        super().__init__(0)
        self.left = left
        self.right = right

    def accept(self, v: "Visitor") -> int:
        return v.visit_pair(self)


class Leaf(Node):
    def value(self, extra: int = 9) -> int:
        return -self.n - extra


class Visitor:
    def visit_node(self, o: Node) -> int:
        return o.n

    def visit_f(self, o: F) -> int:
        return 1000 + o.n

    def visit_pair(self, o: Pair) -> int:
        return o.left.accept(self) * 2 + o.right.accept(self)


def make() -> list[Node]:
    return [Node(1), A(2), B(3), C(4), D(5), E(6), F(7), G(8), H(9), Pair(Leaf(1), Pair(F(2), A(3))), Leaf(10)]


def arg(x: int) -> int:
    events.append(f"arg {x}")
    return x


def receiver(o: Node | None) -> Node | None:
    events.append("receiver")
    return o


nodes = make()
print([x.value() for x in nodes])
print([x.value(5) for x in nodes])
print([x.value(extra=6) for x in nodes])
print([x.scale(2.0) for x in nodes])
print([x.scale(0.5) for x in nodes])
print([type(x.child()).__name__ for x in nodes])
print([x.show(1) for x in nodes])
print([x.show("s") for x in nodes])
print([x.child().value() for x in nodes])
for x in nodes:
    x.note()
    x.note("t")
print(events)
events.clear()
vis = Visitor()
print([x.accept(vis) for x in nodes])
for x in nodes:
    try:
        print(type(x).__name__, x.explode(0))
    except ValueError as e:
        print(type(x).__name__, "ValueError", e)
values: list[Callable[[int], int]] = [x.value for x in nodes]
print([f(4) for f in values])
f_nodes: list[F] = [F(1), G(2), H(3)]
print([x.value() for x in f_nodes], [x.value() for x in f_nodes])
maybe: Node | None = None
try:
    print(receiver(maybe).value(arg(1)))
except AttributeError as e:
    print("AttributeError", e, events)
events.clear()
print(receiver(nodes[2]).value(arg(2)), events)
