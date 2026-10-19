"""Experimental, typed expression-node subset of CPython's _ast module.

Only construction and field access are provided. This module does not parse
source, validate arbitrary trees or compile AST objects. See docs/prototypes/ast.md.
As in CPython 3.13, a list field left out is a new empty list, an optional field
None and a context the one Load object that every node shares.
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


# (a list field's default: each node made without it gets an empty list of its own)
_exprs: list[expr] = []
_keys: list[expr | None] = []


class expr_context(AST):
    pass


class Load(expr_context):
    pass


class Store(expr_context):
    pass


class Del(expr_context):
    pass


_load = Load()  # (CPython's one Load, the context of every node made without one)


class boolop(AST):
    pass


class And(boolop):
    pass


class Or(boolop):
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


class cmpop(AST):
    pass


class Eq(cmpop):
    pass


class NotEq(cmpop):
    pass


class Lt(cmpop):
    pass


class LtE(cmpop):
    pass


class Gt(cmpop):
    pass


class GtE(cmpop):
    pass


class Is(cmpop):
    pass


class IsNot(cmpop):
    pass


class In(cmpop):
    pass


class NotIn(cmpop):
    pass


_cmpops: list[cmpop] = []


class keyword(AST):
    _fields: tuple[str, ...] = ("arg", "value")
    _attributes: tuple[str, ...] = ("lineno", "col_offset", "end_lineno", "end_col_offset")
    __match_args__: tuple[str, ...] = ("arg", "value")

    # (arg is None for **kwargs; CPython's default None precedes the required value, which the
    # typed constructor cannot express, so both are given)
    def __init__(self, arg: str | None, value: expr):
        self.arg = arg
        self.value = value


_keywords: list[keyword] = []


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
    def __init__(self, id: str, ctx: expr_context | None = _load):
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


class BoolOp(expr):
    _fields: tuple[str, ...] = ("op", "values")
    __match_args__: tuple[str, ...] = ("op", "values")

    def __init__(self, op: boolop, values: list[expr] = _exprs):
        self.op = op
        self.values: list[expr] = [] if values is _exprs else values


class NamedExpr(expr):
    _fields: tuple[str, ...] = ("target", "value")
    __match_args__: tuple[str, ...] = ("target", "value")

    def __init__(self, target: expr, value: expr):
        self.target = target
        self.value = value


class IfExp(expr):
    _fields: tuple[str, ...] = ("test", "body", "orelse")
    __match_args__: tuple[str, ...] = ("test", "body", "orelse")

    def __init__(self, test: expr, body: expr, orelse: expr):
        self.test = test
        self.body = body
        self.orelse = orelse


class Dict(expr):
    _fields: tuple[str, ...] = ("keys", "values")
    __match_args__: tuple[str, ...] = ("keys", "values")

    # (a key is None where the display unpacks a mapping, {**d})
    def __init__(self, keys: list[expr | None] = _keys, values: list[expr] = _exprs):
        self.keys: list[expr | None] = [] if keys is _keys else keys
        self.values: list[expr] = [] if values is _exprs else values


class Set(expr):
    _fields: tuple[str, ...] = ("elts",)
    __match_args__: tuple[str, ...] = ("elts",)

    def __init__(self, elts: list[expr] = _exprs):
        self.elts: list[expr] = [] if elts is _exprs else elts


class Await(expr):
    _fields: tuple[str, ...] = ("value",)
    __match_args__: tuple[str, ...] = ("value",)

    def __init__(self, value: expr):
        self.value = value


class Yield(expr):
    _fields: tuple[str, ...] = ("value",)
    __match_args__: tuple[str, ...] = ("value",)

    def __init__(self, value: expr | None = None):
        self.value = value


class YieldFrom(expr):
    _fields: tuple[str, ...] = ("value",)
    __match_args__: tuple[str, ...] = ("value",)

    def __init__(self, value: expr):
        self.value = value


class Compare(expr):
    _fields: tuple[str, ...] = ("left", "ops", "comparators")
    __match_args__: tuple[str, ...] = ("left", "ops", "comparators")

    def __init__(self, left: expr, ops: list[cmpop] = _cmpops, comparators: list[expr] = _exprs):
        self.left = left
        self.ops: list[cmpop] = [] if ops is _cmpops else ops
        self.comparators: list[expr] = [] if comparators is _exprs else comparators


class Call(expr):
    _fields: tuple[str, ...] = ("func", "args", "keywords")
    __match_args__: tuple[str, ...] = ("func", "args", "keywords")

    def __init__(self, func: expr, args: list[expr] = _exprs, keywords: list[keyword] = _keywords):
        self.func = func
        self.args: list[expr] = [] if args is _exprs else args
        self.keywords: list[keyword] = [] if keywords is _keywords else keywords


class Attribute(expr):
    _fields: tuple[str, ...] = ("value", "attr", "ctx")
    __match_args__: tuple[str, ...] = ("value", "attr", "ctx")

    def __init__(self, value: expr, attr: str, ctx: expr_context | None = _load):
        self.value = value
        self.attr = attr
        self.ctx = ctx


class Subscript(expr):
    _fields: tuple[str, ...] = ("value", "slice", "ctx")
    __match_args__: tuple[str, ...] = ("value", "slice", "ctx")

    def __init__(self, value: expr, slice: expr, ctx: expr_context | None = _load):
        self.value = value
        self.slice = slice
        self.ctx = ctx


class Starred(expr):
    _fields: tuple[str, ...] = ("value", "ctx")
    __match_args__: tuple[str, ...] = ("value", "ctx")

    def __init__(self, value: expr, ctx: expr_context | None = _load):
        self.value = value
        self.ctx = ctx


class List(expr):
    _fields: tuple[str, ...] = ("elts", "ctx")
    __match_args__: tuple[str, ...] = ("elts", "ctx")

    def __init__(self, elts: list[expr] = _exprs, ctx: expr_context | None = _load):
        self.elts: list[expr] = [] if elts is _exprs else elts
        self.ctx = ctx


class Tuple(expr):
    _fields: tuple[str, ...] = ("elts", "ctx")
    __match_args__: tuple[str, ...] = ("elts", "ctx")

    def __init__(self, elts: list[expr] = _exprs, ctx: expr_context | None = _load):
        self.elts: list[expr] = [] if elts is _exprs else elts
        self.ctx = ctx


class Slice(expr):
    _fields: tuple[str, ...] = ("lower", "upper", "step")
    __match_args__: tuple[str, ...] = ("lower", "upper", "step")

    def __init__(self, lower: expr | None = None, upper: expr | None = None, step: expr | None = None):
        self.lower = lower
        self.upper = upper
        self.step = step
