# Generic visitor results, annotated template fields and class attributes compose across a
# hierarchy wide enough to share virtual dispatch. Defaults read preceding class constants;
# the visitor's non-hierarchy state keeps its annotated defaultdict without becoming a template.
from collections import defaultdict
from typing import ClassVar, Final, Generic, TypeVar

T = TypeVar("T")


class Notes:
    totals: defaultdict[str, int]

    def __init__(self) -> None:
        self.totals = defaultdict(int)


class Visitor(Generic[T]):
    def visit(self, node: "Node") -> T:
        raise NotImplementedError


class Node:
    KIND: Final = 1
    flags: Final = ["node"]
    labels: ClassVar[dict[int, str]] = {KIND: "v"}
    seen: defaultdict[str, int]

    def __init__(self, notes: Notes, value: int) -> None:
        self.notes = notes
        self.value = value
        self.seen = defaultdict(int)

    def show(self, extra: int = KIND) -> str:
        self.seen["show"] += 1
        return Node.labels[extra] + str(self.value)

    def accept(self, visitor: Visitor[T]) -> T:
        return visitor.visit(self)


class A(Node):
    def show(self, extra: int = 1) -> str:
        return "A" + super().show(extra)


class B(Node):
    pass


class C(Node):
    pass


class D(Node):
    pass


class E(Node):
    pass


class F(Node):
    pass


class G(Node):
    pass


class H(Node):
    def show(self, extra: int = 1) -> str:
        return "H" + super().show(extra)


class TextVisitor(Visitor[str]):
    calls: ClassVar[int] = 0

    def __init__(self, notes: Notes) -> None:
        self.notes = notes

    def visit(self, node: Node) -> str:
        TextVisitor.calls += 1
        self.notes.totals["visit"] += 1
        return node.show()


class EvenVisitor(Visitor[bool]):
    def visit(self, node: Node) -> bool:
        return node.value % 2 == 0


notes = Notes()
nodes: list[Node] = [Node(notes, 0), A(notes, 1), B(notes, 2), C(notes, 3), D(notes, 4), E(notes, 5), F(notes, 6), G(notes, 7), H(notes, 8)]
text = TextVisitor(notes)
print([node.accept(text) for node in nodes])
print([node.accept(EvenVisitor()) for node in nodes])
print([node.show() for node in nodes])
Node.labels[Node.KIND] = "x"
print([node.accept(text) for node in nodes])
print(TextVisitor.calls, notes.totals["visit"], [node.seen["show"] for node in nodes], Node.flags)
