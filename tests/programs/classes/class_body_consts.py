# In an ordinary class, a class-body value or method default reads a constant that the body bound
# once before it, as CPython reads it from the class namespace: mypyc's operator tables
# (op_str: Final = {ADD: "+", ...}), a comprehension's first iterable, and names that a module
# global or a builtin also has.
from typing import Final

ADD = 99
len = 7


class IntOp:
    ADD: Final = 0
    SUB: Final = 1
    MUL: Final = 2
    EQ: Final = 100
    NEQ: Final = 101
    NEG: Final = -3
    op_str: Final = {ADD: "+", SUB: "-", MUL: "*"}
    signed_ops: Final = {"==": EQ, "!=": NEQ}
    order = [MUL, ADD, NEG]
    pairs: list[tuple[int, int]] = [(op, op + 1) for op in (ADD, SUB)]
    len = 3
    size = len * 2
    late = ADD

    def __init__(self, op: int = SUB) -> None:
        self.op = op

    def show(self, sep: str = "") -> str:
        return self.op_str[self.op] + sep


x = 10


class A:
    before: int = x
    x: int = 1
    y: int = x + 1


i = IntOp()
print(i.show(), IntOp(IntOp.MUL).show("|"), IntOp.signed_ops, IntOp.order, IntOp.pairs)
print(IntOp.size, IntOp.late, A.before, A().y, ADD, len)
