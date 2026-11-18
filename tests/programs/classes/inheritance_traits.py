# Traits as mypyc compiles them (mypy's nodes: Statement, Expression and SymbolNode): a secondary
# base that derives from a class of the primary base's chain (Node) and adds no fields (an empty
# __slots__, no __init__, no stores to the instance). Objects of the classes deriving from both
# begin with that class's fields, so a value of a trait's type reads them (line), calls the
# methods of the object's class (accept) and its properties (name), and isinstance() sees every
# class deriving from the trait. Methods resolve in CPython's order: the class's own, then the
# primary chain's own (FuncBase.fullname), then a trait's (Statement.accept for Decorator, over
# Node.accept). super() in the primary chain finds what no trait defines (__init__).
from abc import abstractmethod


class Context:
    __slots__ = ("line", "column")

    def __init__(self, line: int = -1, column: int = -1) -> None:
        self.line = line
        self.column = column


class Node(Context):
    __slots__ = ()

    def accept(self, v: "Visitor") -> str:
        return "node"

    def where(self) -> str:
        return "at " + str(self.line)


class Statement(Node):
    __slots__ = ()

    def accept(self, v: "Visitor") -> str:
        return "statement " + self.where()


class Expression(Node):
    __slots__ = ()


class SymbolNode(Node):
    __slots__ = ()

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def fullname(self) -> str:
        return "m." + self.name

    def describe(self) -> str:
        return self.fullname + " line " + str(self.line)


class FuncBase(Node):
    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        super().__init__(10)
        self._name = name

    @property
    def fullname(self) -> str:
        return "func " + self._name


class FuncItem(FuncBase):
    __slots__ = ("body",)

    def __init__(self, name: str, body: list[Statement]) -> None:
        super().__init__(name)
        self.body = body


class FuncDef(FuncItem, SymbolNode, Statement):
    __slots__ = ()

    @property
    def name(self) -> str:
        return self._name

    def accept(self, v: "Visitor") -> str:
        return v.visit_func(self)


class LambdaExpr(FuncItem, Expression):
    __slots__ = ()

    def accept(self, v: "Visitor") -> str:
        return "lambda " + str(len(self.body))


class Decorator(SymbolNode, Statement):
    __slots__ = ("func",)

    def __init__(self, func: FuncDef) -> None:
        super().__init__(func.line + 1)
        self.func = func

    @property
    def name(self) -> str:
        return "@" + self.func.name


class PassStmt(Statement):
    __slots__ = ()


class Var(SymbolNode):
    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        super().__init__(5)
        self._name = name

    @property
    def name(self) -> str:
        return self._name


class Visitor:
    def visit_func(self, f: FuncDef) -> str:
        return "def " + f.name + " " + str(len(f.body))


f = FuncDef("f", [PassStmt()])
d = Decorator(f)
v = Visitor()
stmts: list[Statement] = [f, PassStmt(), d]
syms: list[SymbolNode] = [Var("x"), f, d]
nodes: list[Node] = [f, LambdaExpr("g", []), d, Var("y")]
print([s.accept(v) for s in stmts], [s.line for s in stmts])
print([s.name for s in syms], [s.fullname for s in syms], [s.describe() for s in syms])
print([n.accept(v) for n in nodes], [n.where() for n in nodes])
print([isinstance(n, Statement) for n in nodes], [isinstance(n, SymbolNode) for n in nodes], [isinstance(n, Expression) for n in nodes])
print([isinstance(s, FuncBase) for s in syms], isinstance(d, Node), f.column, d.func.body[0].accept(v))
