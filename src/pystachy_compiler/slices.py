"""Bounded native slice values and forwarding to existing slicing operations."""
from __future__ import annotations
from src.pystachy_compiler.ir import Val
from src.pystachy_compiler.specs import SLICEC, SLICES
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import is_list, tname, unopt


def gen_slice_object(self, bounds: list[Node]) -> Val:
    # Evaluate every raw bound, preserving None and bool, before allocating the key.
    # User methods see these raw values; builtin consumers normalize them later.
    values: list[Val] = []
    for n in bounds:
        v = Val("null", "None") if n.kind == "omit" else self.expr(n, "")
        if v.t not in ["None", "int", "bool", "opt[int]", "opt[bool]", "union[bool,int]", "opt[union[bool,int]]"]:
            self.err("slice values support int, bool or None bounds")
        values.append(v)
    while len(values) < 3:
        values.append(Val("null", "None"))
    o = self.new_obj(SLICEC)
    self.call_fn(self.classes[SLICEC].methods["__init__"], [o], [self.vnode(v) for v in values], direct=True)
    return o


def gen_slice_node(self, obj: Val, key: Val) -> Node:
    # An existing slice's raw bounds become int/None for builtin slicing. This
    # never reevaluates the receiver or key expression, including augmented stores.
    name = "list" if is_list(unopt(obj.t)) else "byte" if obj.t == "bytes" else tname(unopt(obj.t))
    error = "string indices must be integers, not 'NoneType'" if obj.t == "str" else f"{name} indices must be integers or slices, not NoneType"
    self.notnone(key, "TypeError: " + error)
    bounds: list[Node] = []
    ci = self.classes[SLICEC]
    for name in ["start", "stop", "step"]:
        value = self.getfield(key, Val(self.fgep(key, ci.fpos[name]), ci.ftypes[name]), name)
        bound = self.call_fn(self.funcs[SLICES + "$_index"], [value], [])
        bounds.append(self.vnode(bound))
    return mk("slice", "", self.line, [self.vnode(obj)] + bounds)
