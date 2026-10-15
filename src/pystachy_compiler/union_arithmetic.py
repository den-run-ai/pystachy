"""Numeric operations on explicit, finite unions, using native typed lowering."""
from __future__ import annotations
from src.pystachy_compiler.ir import Ins, Val
from src.pystachy_compiler.syntax import mk
from src.pystachy_compiler.utils import is_opt, is_union, tname, umembers, unopt

def gen_unumeric(self, op: str, a: Val, b: Val, shown: str, unary: bool) -> Val:
    if op not in (["+", "-"] if unary else ["+", "-", "*", "/", "//", "%"]):
        self.err("closed numeric union arithmetic supports +, -, *, /, //, % and unary + or -; narrow other operations first")
    nominal: list[str] = []
    for v in [a] if unary else [a, b]:
        for m in umembers(unopt(v.t)) if is_union(unopt(v.t)) else [unopt(v.t)]:
            if m not in ["int", "float", "bool", "None"]:
                self.err("closed union arithmetic requires narrowing with isinstance() first" + self.unarrowed(a if is_union(unopt(a.t)) else b))
            if m != "None":
                nominal.append("float" if m == "float" or op == "/" else "int")
    result = self.unumeric_case(op, a, b, shown, unary)
    # An explicitly None operand can make every path raise. Keep a numeric
    # placeholder for the surrounding expression's type checking, never None.
    return Val("undef", self.union_type(nominal)) if self.term else result

def gen_unumeric_case(self, op: str, a: Val, b: Val, shown: str, unary: bool) -> Val:
    # Expression evaluation has already happened, left to right and exactly once.
    # Expand only explicit union/optional types; leaf operations keep their native
    # representation, overflow/division checks and exception edges.
    left = is_union(unopt(a.t)) or is_opt(a.t)
    v = a if left or unary else b
    if not is_union(unopt(v.t)) and not is_opt(v.t):
        if a.t == "None" or (not unary and b.t == "None"):
            message = f"bad operand type for unary {op}: 'NoneType'" if unary else f"unsupported operand type(s) for {shown if shown != '' else op}: '{tname(a.t)}' and '{tname(b.t)}'"
            self.raise_("TypeError", self.sconst(message))
            return Val("null", "None")
        return self.unary(mk("unary", op, 0, [self.vnode(a)])) if unary else self.arith(op, a, b, shown)
    members = umembers(unopt(v.t)) if is_union(unopt(v.t)) else [unopt(v.t)]
    if is_opt(v.t):
        members = ["None"] + members
    end = self.label()
    results: list[Val] = []
    edges: list[str] = []
    for i in range(len(members)):
        member = members[i]
        hit = self.label()
        miss = self.label() if i + 1 < len(members) else ""
        if miss == "":
            self.br(hit)
        elif member == "None":
            self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, hit, miss)
        else:
            self.cbr(self.utest(v, [member], False), hit, miss)
        self.place(hit)
        value = Val("null", "None") if member == "None" else self.uget(Val(v.v, unopt(v.t)), member) if is_union(unopt(v.t)) else self.deref(v)
        result = self.unumeric_case(op, value if left or unary else a, b if left or unary else value, shown, unary)
        if not self.term:
            results.append(result)
            edges.append(self.cur)
            self.br(end)
        if miss != "":
            self.place(miss)
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return Val("null", "None")
    # A fixed operator has a finite result set: int, float, or int | float.
    # Do not widen int to float, which would lose its runtime type and precision.
    result_type = self.union_type([r.t for r in results])
    ph = Ins("phi", result_type, "")
    for i in range(len(results)):
        self.incoming(ph, self.convert_at(results[i], result_type, edges[i]).v, edges[i])
    return Val(self.phi(ph), result_type)
