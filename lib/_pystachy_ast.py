"""Experimental, typed expression-node subset of CPython's _ast module.

Only construction and field access are provided. This module does not parse
source, validate arbitrary trees or compile AST objects. See docs/prototypes/ast.md.
"""
from __future__ import annotations


PyCF_ONLY_AST = 1024
PyCF_TYPE_COMMENTS = 4096
PyCF_ALLOW_TOP_LEVEL_AWAIT = 8192
PyCF_OPTIMIZED_AST = 33792  # PyCF_ONLY_AST | the optimized-AST bit


class AST:
    _fields: tuple[str, ...] = ()
    _attributes: tuple[str, ...] = ()
    __match_args__: tuple[str, ...] = ()


class mod(AST):
    pass


class expr(AST):
    # Metadata follows CPython. Location fields are not implemented by this slice.
    _attributes: tuple[str, ...] = ("lineno", "col_offset", "end_lineno", "end_col_offset")


class expr_context(AST):
    pass


class Load(expr_context):
    pass


class Store(expr_context):
    pass


class Del(expr_context):
    pass


class operator(AST):
    pass


class Add(operator):
    pass


class Sub(operator):
    pass


class Mult(operator):
    pass


class MatMult(operator):
    pass


class Div(operator):
    pass


class Mod(operator):
    pass


class Pow(operator):
    pass


class LShift(operator):
    pass


class RShift(operator):
    pass


class BitOr(operator):
    pass


class BitXor(operator):
    pass


class BitAnd(operator):
    pass


class FloorDiv(operator):
    pass


class unaryop(AST):
    pass


class Invert(unaryop):
    pass


class Not(unaryop):
    pass


class UAdd(unaryop):
    pass


class USub(unaryop):
    pass


class Expression(mod):
    _fields: tuple[str, ...] = ("body",)
    __match_args__: tuple[str, ...] = ("body",)

    def __init__(self, body: expr):
        self.body = body


class Constant(expr):
    _fields: tuple[str, ...] = ("value", "kind")
    __match_args__: tuple[str, ...] = ("value", "kind")

    def __init__(self, value: int | float | str | bool | None, kind: str | None = None):
        self.value = value
        self.kind = kind


class Name(expr):
    _fields: tuple[str, ...] = ("id", "ctx")
    __match_args__: tuple[str, ...] = ("id", "ctx")

    # CPython shares the default Load singleton; explicit None remains None.
    def __init__(self, id: str, ctx: expr_context | None = Load()):
        self.id = id
        self.ctx = ctx


class BinOp(expr):
    _fields: tuple[str, ...] = ("left", "op", "right")
    __match_args__: tuple[str, ...] = ("left", "op", "right")

    def __init__(self, left: expr, op: operator, right: expr):
        self.left = left
        self.op = op
        self.right = right


class UnaryOp(expr):
    _fields: tuple[str, ...] = ("op", "operand")
    __match_args__: tuple[str, ...] = ("op", "operand")

    def __init__(self, op: unaryop, operand: expr):
        self.op = op
        self.operand = operand
