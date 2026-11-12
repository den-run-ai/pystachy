# An override of a secondary base's method may return a class that derives from the one the
# base's returns, as an override of a primary base's may: mypy's FuncDef(FuncBase, SymbolNode)
# has a class method deserialize that returns a FuncDef, where its trait SymbolNode's returns a
# SymbolNode. Also through a reference typed as the secondary base, its bound methods and
# Callables, and with optional returns.
from typing import Callable


class Node:
    def __init__(self, line: int) -> None:
        self.line = line


class SymbolNode(Node):
    __slots__ = ()

    def name(self) -> str:
        raise NotImplementedError()

    def copy(self) -> "SymbolNode":
        raise NotImplementedError()

    def peer(self) -> "SymbolNode | None":
        return None

    @classmethod
    def deserialize(cls, data: dict[str, int]) -> "SymbolNode":
        raise NotImplementedError()


class FuncBase(Node):
    pass


class FuncDef(FuncBase, SymbolNode):
    def name(self) -> str:
        return "f" + str(self.line)

    def copy(self) -> "FuncDef":
        return FuncDef(self.line + 1)

    def peer(self) -> "FuncDef | None":
        return self if self.line > 1 else None

    @classmethod
    def deserialize(cls, data: dict[str, int]) -> "FuncDef":
        return FuncDef(data["line"])


class Tool:
    def run(self) -> "Tool":
        return Tool()

    def label(self) -> str:
        return "tool"


class Hammer(Node, Tool):
    def run(self) -> "Hammer":
        return Hammer(self.line * 2)

    def label(self) -> str:
        return "hammer" + str(self.line)


def via(s: SymbolNode) -> str:
    p = s.peer()
    return s.copy().name() + " " + ("-" if p is None else p.name())


def use(t: Tool) -> str:
    return t.run().label()


def bound(s: SymbolNode) -> str:
    m = s.copy
    return m().name()


def call(make: Callable[[], SymbolNode]) -> str:
    return make().copy().name()


f = FuncDef.deserialize({"line": 2})
print(f.name(), via(f), via(FuncDef(1)), f.copy().line)
print(use(Hammer(3)), use(Tool()), Hammer(5).run().line)
g: SymbolNode = f.copy()
print(bound(f), call(f.copy), g.name(), isinstance(g, FuncBase))
