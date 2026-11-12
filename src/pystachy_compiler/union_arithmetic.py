"""Numeric operations on explicit, finite unions, using native typed lowering."""
from __future__ import annotations
from src.pystachy_compiler.ir import Ins, Val
from src.pystachy_compiler.specs import DUNDER, NONEARG
from src.pystachy_compiler.syntax import mk
from src.pystachy_compiler.utils import is_opt, is_union, tname, typestr, umembers, unopt

def unarith(op: str, t: str) -> bool:
    # does gen_unumeric compile no binary op of an operand of type t, a closed union or one or
    # None: an operator it has not, or a member that is no number (its two errors, below)
    if op not in ["+", "-", "*", "/", "//", "%"]:
        return True
    return len([m for m in umembers(unopt(t)) if m not in ["int", "float", "bool", "None"]]) > 0


def none_call_error(name: str, ts: list[str], i: int) -> str:
    # CPython's TypeError message for builtin name called with None as argument i (the others
    # of types ts), where usplit knows it; "" where the call is compiled for None as it is
    if name in NONEARG:
        return NONEARG[name]
    if name == "math.floor" or name == "math.ceil":
        return "must be real number, not NoneType"
    if name == "math.trunc":
        return "type NoneType doesn't define __trunc__ method"
    if (name == "divmod" or name == "pow") and len(ts) == 2:
        names = [tname(ts[k]) if k != i else "NoneType" for k in range(2)]
        return f"unsupported operand type(s) for {'divmod()' if name == 'divmod' else '** or pow()'}: '{names[0]}' and '{names[1]}'"
    return ""


def gen_unumeric(self, op: str, a: Val, b: Val, shown: str, unary: bool) -> Val:
    # A union that holds objects beside numbers (object_union: int | Decimal, what sum() of
    # objects is) selects each member's operation too: an object's method, the reflected one for
    # a number on its left (gen_dunder), which every operator may be. Its operations' results
    # are their union, where there is one. A str member has no arithmetic: narrow it first.
    objects = False
    for v in [a] if unary else [a, b]:
        members = umembers(unopt(v.t)) if is_union(unopt(v.t)) else [unopt(v.t)]
        if self.object_union(v.t) and len([m for m in members if m == "str" or m == "file"]) == 0:
            objects = True
    if not objects and op not in (["+", "-"] if unary else ["+", "-", "*", "/", "//", "%"]):
        self.err("closed numeric union arithmetic supports +, -, *, /, //, % and unary + or -; narrow other operations first")
    nominal: list[str] = []
    for v in [a] if unary else [a, b]:
        for m in umembers(unopt(v.t)) if is_union(unopt(v.t)) else [unopt(v.t)]:
            if m not in ["int", "float", "bool", "None"] and not objects:
                self.err("closed union arithmetic requires narrowing with isinstance() first" + self.unarrowed(a if is_union(unopt(a.t)) else b))
            if m != "None":
                nominal.append("float" if m == "float" or op == "/" else "int")
    result = self.unumeric_case(op, a, b, shown, unary)
    # An explicitly None operand can make every path raise. Keep a numeric
    # placeholder for the surrounding expression's type checking, never None.
    return Val("undef", self.union_type(nominal)) if self.term and not objects else result

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
        if not unary and shown == op + "=" and b.t in self.classes and (a.t == "int" or a.t == "float" or a.t == "bool"):
            # (a number that the union's variable holds, and an object: the object's reflected
            # method, whose result the variable takes, as CPython's x += o rebinds x: gen_dunder
            # keeps that for a variable of the number's type, which could not hold it)
            rm = "__r" + DUNDER[op][2:] if op in DUNDER else ""
            if rm in self.classes[b.t].methods:
                self.notnone(b, f"TypeError: unsupported operand type(s) for {shown}: '{tname(a.t)}' and 'NoneType'")
                return self.call_fn(self.classes[b.t].methods[rm], [b, a], [])
        return self.unary(mk("unary", op, 0, [self.vnode(a)])) if unary else self.arith(op, a, b, shown)
    members = umembers(unopt(v.t)) if is_union(unopt(v.t)) else [unopt(v.t)]
    if is_opt(v.t) or (self.object_union(v.t) and v.v not in self.nn):
        members = ["None"] + members  # (a union that holds objects may be None, as they may)
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
    if result_type.startswith("!"):
        self.err(f"unsupported operand types for {shown if shown != '' else op}: the results of {typestr(v.t)}'s members ({', '.join([typestr(r.t) for r in results])}) have no union; narrow it with isinstance() first")
    ph = Ins("phi", result_type, "")
    for i in range(len(results)):
        r = self.convert_at(results[i], result_type, edges[i])
        self.incoming(ph, r.v, self.convedge)
    return Val(self.phi(ph), result_type)

def gen_usplit(self, name: str, vals: list[Val], i: int, want: str) -> Val:
    # name(..., u, ...) of builtin name, which takes no value of union u (vals[i]): name of each
    # member's value, chosen by its tag (union splitting), compiled as the native call it is,
    # and the union of their results (int | float: abs(), math's results are floats)
    u = vals[i]
    members = umembers(u.t)
    if self.object_union(u.t) and u.v not in self.nn:
        members = ["None"] + members  # (a union that holds objects may be None, as they may)
    end = self.label()
    results: list[Val] = []
    edges: list[str] = []
    for j in range(len(members)):
        hit = self.label()
        miss = self.label() if j + 1 < len(members) else ""
        if miss == "":
            self.br(hit)
        elif members[j] == "None":
            self.cbr(self.ptr_cmp('==', u, Val('null', 'None')).v, hit, miss)
        else:
            self.cbr(self.utest(u, [members[j]], False), hit, miss)
        self.place(hit)
        args = [self.vnode(v) for v in vals]
        args[i] = self.vnode(Val("null", "None") if members[j] == "None" else self.uget(u, members[j]))
        r = Val("null", "None")
        if members[j] == "None" and none_call_error(name, [v.t for v in vals], i) != "":
            self.raise_("TypeError", self.sconst(none_call_error(name, [v.t for v in vals], i)))  # (CPython's, for None)
        else:
            r = self.builtin(name, args, want)
        if not self.term:
            results.append(r)
            edges.append(self.cur)
            self.br(end)
        if miss != "":
            self.place(miss)
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return Val("null", "None")
    result_type = self.union_type([r.t for r in results])
    if result_type.startswith("!"):
        self.err(f"unsupported call {name}() of {typestr(u.t)}: its members' results ({', '.join([typestr(r.t) for r in results])}) have no union")
    ph = Ins("phi", result_type, "")
    for j in range(len(results)):
        r = self.convert_at(results[j], result_type, edges[j])
        self.incoming(ph, r.v, self.convedge)
    return Val(self.phi(ph), result_type)

def gen_unequal_types(self, a: str, b: str) -> bool:
    # is a number or str (a) never equal to an object of class b: no class b's object may be of
    # defines __eq__ (or __ne__), so CPython compares the two by identity
    if a not in ["int", "float", "bool", "str"] or b not in self.classes or self.classes[b].exc != "" or b in self.nts:
        return False
    for c in self.classes.values():
        if (c.name == b or self.derives(c.name, b)) and ("__eq__" in c.methods or "__ne__" in c.methods or self.is_dc(c.name)):
            return False
    return True

def gen_uorders(self, a: str, b: str) -> bool:
    # can a value of type a be ordered (<, <=, >, >=) with one of type b, one of them a union, by
    # each member's native ordering (ucmp): numbers with numbers, strs with strs
    ms = (umembers(a) if is_union(a) else [a]) + (umembers(b) if is_union(b) else [b])
    return all([m in ["int", "float", "bool"] for m in ms]) or all([m == "str" for m in ms])

def gen_ucmp(self, op: str, a: Val, b: Val, nonnull: bool = False) -> Val:
    # a op b, an ordering where a or b is of a union (uorders): each member's ordering, chosen by
    # its tag (union splitting), compiled as the native comparison it is; nonnull: identity's
    # operands are known not to be None
    if op in ["is", "is not"] and not nonnull and (is_opt(a.t) or is_opt(b.t) or self.reference_union(a.t) or self.reference_union(b.t)):
        # Native reference identity may include None, an optional union's or a class
        # union's (whose None is a null box pointer, as a class type's None is null).
        # Do not read a union tag until both pointers are nonnull; the remaining arms
        # use original refs.
        nula = self.ptr_cmp("==", a, Val("null", "None")).v
        nulb = self.ptr_cmp("==", b, Val("null", "None")).v
        both = self.scalar("and", [Val(nula, "bool"), Val(nulb, "bool")])
        null_result = both if op == "is" else self.scalar("xor", [Val(both, "bool"), Val("true", "bool")])
        some = self.label()
        done = self.label()
        result = Ins("phi", "bool", "")
        self.incoming(result, null_result, self.cur)
        self.cbr(self.scalar("or", [Val(nula, "bool"), Val(nulb, "bool")]), done, some)
        self.place(some)
        value = self.ucmp(op, Val(a.v, unopt(a.t)), Val(b.v, unopt(b.t)), True)
        self.incoming(result, value.v, self.cur)
        self.br(done)
        self.place(done)
        return Val(self.phi(result), "bool")
    left = is_union(a.t)
    v = a if left else b
    members = umembers(v.t)
    if self.object_union(v.t) and v.v not in self.nn and not nonnull:
        members = ["None"] + members  # (a union that holds objects may be None, as they may)
    end = self.label()
    ph = Ins("phi", "bool", "")
    reached = 0
    for j in range(len(members)):
        hit = self.label()
        miss = self.label() if j + 1 < len(members) else ""
        if miss == "":
            self.br(hit)
        elif members[j] == "None":
            self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, hit, miss)
        else:
            self.cbr(self.utest(v, [members[j]], False), hit, miss)
        self.place(hit)
        x = Val("null", "None") if members[j] == "None" else self.uget(v, members[j])
        la = x if left else a
        lb = b if left else x
        ordering = op in ["<", "<=", ">", ">="]
        r = Val("false" if op == "==" else "true", "bool")
        if (la.t == "None" or lb.t == "None") and (is_union(la.t) or is_union(lb.t)):
            # None with the other operand's union: its members, in turn (an object's __eq__ is
            # asked about None too, and None equals a union that holds None)
            r = self.ucmp(op, la, lb)
        elif ordering and (la.t == "None" or lb.t == "None") and la.t not in self.classes and lb.t not in self.classes:
            # None has no ordering with a number, a str or None: CPython's TypeError, which names
            # both operands' types. (An object's method is asked about None, as it is below.)
            self.raise_("TypeError", self.sconst(f"'{op}' not supported between instances of '{tname(la.t)}' and '{tname(lb.t)}'"))
        elif (op == "==" or op == "!=") and (self.unequal_types(la.t, lb.t) or self.unequal_types(lb.t, la.t)):
            pass  # (a number or str and an object whose class has no __eq__: never equal)
        else:
            r = self.cmp2(op, la, lb)  # (the other operand's union, in turn)
        if not self.term:
            self.incoming(ph, r.v, self.cur)
            reached += 1
            self.br(end)
        if miss != "":
            self.place(miss)
    self.place(end)
    if reached == 0:
        self.unreachable()  # (every member's comparison raises)
        return Val("false", "bool")
    return Val(self.phi(ph), "bool")
