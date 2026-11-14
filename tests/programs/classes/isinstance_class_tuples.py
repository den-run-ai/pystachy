# isinstance(x, (A, B)) of classes derived from x's narrows x to A | B, as mypy reads it (#1325):
# a field or method that each of them declares, and a return or store as A | B, as mypyc's
# RVec.unwrap_item_type returns item_type after isinstance(item_type, (RPrimitive, RInstance)).
# One class derived from another is that one. Where the union does not do what x's class does
# (x == y, a call taking x's class), x keeps its class there, as it did before.
class Op:
    def __init__(self, line: int) -> None:
        self.line = line


class Assign(Op):
    def __init__(self, dest: str, line: int) -> None:
        super().__init__(line)
        self.dest = dest

    def label(self) -> str:
        return "assign " + self.dest


class AssignSub(Assign):
    pass


class AssignMulti(Op):
    def __init__(self, dest: str, n: int, line: int) -> None:
        super().__init__(line)
        self.dest = dest
        self.n = n

    def label(self) -> str:
        return "multi " + self.dest


class Branch(Op):
    pass


class Wrap(Op):
    def __init__(self, inner: Op) -> None:
        super().__init__(inner.line)
        self.inner = inner


def dests(ops: list[Op]) -> list[str]:
    values: list[str] = []
    for op in ops:
        if isinstance(op, (Assign, AssignMulti)):
            values.append(op.dest)
    return values


def assigned(op: Op) -> Assign | AssignMulti | None:
    if isinstance(op, (Assign, AssignMulti)):
        return op
    return None


def unwrap(t: Op) -> Assign | AssignMulti:
    item = t
    while True:
        if isinstance(item, Wrap):
            item = item.inner
        elif isinstance(item, (Assign, AssignMulti)):
            return item
        else:
            raise ValueError("no assignment")


def relabel(op: Op, tag: str) -> str:
    if isinstance(op, (Assign, AssignMulti)):
        op.dest = op.dest + tag
        return op.label()
    return "-"


def first(op: Op) -> str:
    if isinstance(op, (Assign, AssignSub)):
        return op.dest
    return "-"


def count(op: Op) -> int:
    return op.line


def lines(op: Op, others: list[Op]) -> int:
    if isinstance(op, (Assign, AssignMulti)):
        return count(op) + len([o for o in others if o == op])
    return 0


ops: list[Op] = [Assign("a", 1), Branch(2), AssignMulti("b", 3, 3), AssignSub("c", 4)]
print(dests(ops), relabel(ops[0], "!"), relabel(ops[1], "?"), first(ops[3]), first(ops[1]))
a = assigned(ops[2])
print(a.label() if a is not None else "none", assigned(ops[1]) is None)
print(unwrap(Wrap(Wrap(ops[2]))).label(), unwrap(ops[0]).label(), lines(ops[2], ops), lines(ops[1], ops))
try:
    unwrap(Wrap(Branch(5)))
except ValueError as e:
    print("ValueError", e)
