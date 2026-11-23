"""Numeric operations on explicit, finite unions, using native typed lowering."""
from __future__ import annotations
from src.pystachy_compiler.dynamic import comparison_builtin, comparison_invalid
from src.pystachy_compiler.ir import Ins, Val
from src.pystachy_compiler.specs import BIG, COMPLEXC, DUNDER, NONEARG, UCALLS
from src.pystachy_compiler.syntax import made_var, mk
from src.pystachy_compiler.utils import is_dict, is_list, is_opt, is_union, targs, tname, typestr, umembers, unopt

def unarith(op: str, t: str) -> bool:
    # does gen_unumeric compile no binary op of an operand of type t, a closed union or one or
    # None: an operator it has not, or a member that is no number (its two errors, below)
    cx = is_union(unopt(t)) and COMPLEXC in umembers(unopt(t))
    if op not in ["+", "-", "*", "/", "//", "%"] + (["**"] if cx else []):
        return True
    return len([m for m in umembers(unopt(t)) if m not in ["int", "float", "bool", "None", COMPLEXC]]) > 0


def bool_int(t: str) -> bool:
    # is t a bool | int (Gen.bool_int reads it as the int it is)
    return is_union(t) and sorted(umembers(t)) == ["bool", "int"]


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


def declines_none(self, c: str, m: str) -> bool:
    # is method m of class c one of int's or str's operations that lib/enum.py gives the members
    # of an IntEnum, IntFlag or StrEnum class (enum_builtin), which decline None, as CPython's do:
    # an operation of None and such a member raises the TypeError it raises for a number
    return m in self.classes[c].methods and self.enum_builtin(c) != "" and self.classes[c].methods[m].mod == "enum"


def gen_unumeric(self, op: str, a: Val, b: Val, shown: str, unary: bool) -> Val:
    # (a complex number, as an operand or a member, takes part as complex_arith computes it: each
    # member's case is arith's of its value, and ** too, where one is complex)
    cx = any([unopt(v.t) == COMPLEXC or (is_union(unopt(v.t)) and COMPLEXC in umembers(unopt(v.t))) for v in ([a] if unary else [a, b])])
    # A union that holds objects beside numbers (object_union: int | Decimal, what sum() of
    # objects is) selects each member's operation too: an object's method, the reflected one for
    # a number on its left (gen_dunder), which every operator may be. Its operations' results
    # are their union, where there is one. A str member has no arithmetic: narrow it first.
    objects = False
    for v in [a] if unary else [a, b]:
        members = umembers(unopt(v.t)) if is_union(unopt(v.t)) else [unopt(v.t)]
        if self.object_union(v.t) and len([m for m in members if m == "str" or m == "file"]) == 0:
            objects = True
    ab = [bool_int(a.t), not unary and bool_int(b.t)]
    if not unary and (ab[0] or ab[1]) and (ab[0] or a.t in ["int", "bool", BIG]) and (ab[1] or b.t in ["int", "bool", BIG]) and (op in ["**", "<<", ">>"] or (op in ["&", "|", "^"] and not (ab[0] and ab[1]) and (a.t if ab[1] else b.t) in ["int", BIG])):
        # (a bool | int, as isinstance(x, int) narrows a value of object to, where the result is an
        # int whatever it holds, as a bool is an int there: x ** n, x << n, x & 7, ... of its int)
        return self.arith(op, self.bool_int(a), self.bool_int(b), shown)
    if not objects and op not in (["+", "-"] if unary else ["+", "-", "*", "/", "//", "%"] + (["**"] if cx else [])):
        self.err("closed numeric union arithmetic supports +, -, *, /, //, % and unary + or -; narrow other operations first")
    # A closed value union's (numbers beside a str, a list or a dict, as json.JSONValue is):
    # each member's own operation by its tag, and CPython's TypeError for a pair of types
    # that has none (unumeric_case's leaf). The other operand is one too, or of a builtin type.
    values = all([self.value_union(v.t) if is_union(unopt(v.t)) else comparison_builtin(unopt(v.t)) != "" for v in ([a] if unary else [a, b])])
    nominal: list[str] = []
    relaxed = False
    for v in [a] if unary else [a, b]:
        for m in umembers(unopt(v.t)) if is_union(unopt(v.t)) else [unopt(v.t)]:
            if m not in ["int", "float", "bool", "None", COMPLEXC] and not objects:
                if not values:
                    self.err("closed union arithmetic requires narrowing with isinstance() first" + self.unarrowed(a if is_union(unopt(a.t)) else b))
                relaxed = True
            elif m != "None":
                nominal.append(COMPLEXC if cx else "float" if m == "float" or op == "/" else "int")
    dead = self.term
    result = self.unumeric_case(op, a, b, shown, unary)
    if relaxed and self.term and not dead and self.drying == 0 and not self.curfn.cmpops:
        # (no pair of their types has the operation: an error, as it is of two builtin types)
        self.err(f"unsupported operand type(s) for {shown if shown != '' else op}: {typestr(a.t)}" + ("" if unary else f" and {typestr(b.t)}") + " (no member of the closed union supports it)")
    # An explicitly None operand can make every path raise. Keep a numeric
    # placeholder for the surrounding expression's type checking, never None.
    return Val("undef", self.union_type(nominal) if len(nominal) > 0 else "int") if self.term and not objects else result

def gen_unumeric_case(self, op: str, a: Val, b: Val, shown: str, unary: bool) -> Val:
    # Expression evaluation has already happened, left to right and exactly once.
    # Expand only explicit union/optional types; leaf operations keep their native
    # representation, overflow/division checks and exception edges.
    left = is_union(unopt(a.t)) or is_opt(a.t)
    v = a if left or unary else b
    if not is_union(unopt(v.t)) and not is_opt(v.t):
        if (a.t == "None" or (not unary and b.t == "None")) and not (not unary and op == "%" and a.t == "str"):
            if not unary and op in DUNDER:
                # (None beside an object: the method CPython calls, a.__iop__(None) for x op= y,
                # else a.__op__(None), or b.__rop__(None), where it takes None, since None's own
                # methods decline; one that cannot take None keeps the TypeError below)
                if b.t == "None" and a.t in self.classes and a.t != COMPLEXC:
                    for m in (["__i" + DUNDER[op][2:]] if shown == op + "=" else []) + [DUNDER[op]]:
                        if m in self.classes[a.t].methods:
                            if self.cmp_method(a.t, m, "None") != "" and not declines_none(self, a.t, m):
                                return self.call_fn(self.classes[a.t].methods[m], [a, b], [])
                            break
                elif a.t == "None" and b.t in self.classes and b.t != COMPLEXC:
                    rm = "__r" + DUNDER[op][2:]
                    if self.cmp_method(b.t, rm, "None") != "" and not declines_none(self, b.t, rm):
                        return self.call_fn(self.classes[b.t].methods[rm], [b, a], [])
            message = f"bad operand type for unary {op}: 'NoneType'" if unary else f"unsupported operand type(s) for {shown if shown != '' else op}: '{tname(a.t)}' and '{tname(b.t)}'"
            if not unary and len([t for t in [a.t, b.t] if t == "str" or is_list(t) or is_dict(t)]) > 0:
                message = comparison_invalid(op, a.t, b.t, shown)  # (a sequence beside None: CPython's own wording)
                if message == "":
                    message = "'NoneType' object is not iterable"  # (a list's +=, which takes an iterable)
            self.raise_("TypeError", self.sconst(message))
            return Val("null", "None")
        if not unary and shown == op + "=" and b.t in self.classes and b.t != COMPLEXC and (a.t == "int" or a.t == "float" or a.t == "bool"):
            # (a number that the union's variable holds, and an object: the object's reflected
            # method, whose result the variable takes, as CPython's x += o rebinds x: gen_dunder
            # keeps that for a variable of the number's type, which could not hold it. A complex
            # number's arithmetic is complex_arith's, as arith gives it, not the class's methods)
            rm = "__r" + DUNDER[op][2:] if op in DUNDER else ""
            if rm in self.classes[b.t].methods:
                self.notnone(b, f"TypeError: unsupported operand type(s) for {shown}: '{tname(a.t)}' and 'NoneType'")
                return self.call_fn(self.classes[b.t].methods[rm], [b, a], [])
        if not unary and shown == op + "=" and a.t in self.classes and a.t != COMPLEXC and op in DUNDER:
            # (an object that the union's variable holds, on the left of x op= y: its class's
            # in-place method where it defines one, as gen_inplace calls it for a variable of the
            # class's type, since CPython's x += y tries x.__iadd__(y) before x.__add__(y))
            im = "__i" + DUNDER[op][2:]
            if im in self.classes[a.t].methods:
                return self.call_fn(self.classes[a.t].methods[im], [a, b], [])
            r = self.inplace_subclasses(op, a, b)  # (one its subclass defines: statements.py)
            if r is not None:
                return r
        if not unary and shown == op + "=" and is_list(a.t) and (op == "+" or op == "*"):
            # A union's list on the left of += or *= changes in place, as a list variable's
            # does (gen_inplace), and stays the variable's value: another reference to it sees
            # the change. += takes any iterable in CPython: a list's items here, a str's
            # characters and a dict's keys where the list holds such values
            if op == "*":
                if b.t != "int" and b.t != "bool":
                    self.raise_("TypeError", self.sconst(f"can't multiply sequence by non-int of type '{tname(b.t)}'"))
                    return Val("null", "None")
                return self.inplace(op, a, self.vnode(b))
            if b.t in ["None", "int", "float", "bool"]:
                self.raise_("TypeError", self.sconst(f"'{tname(b.t)}' object is not iterable"))
                return Val("null", "None")
            more = b
            if b.t != a.t:
                # (a str's characters, a dict's keys or another list's items, as the list holds them)
                item = made_var("__item", self.line)
                more = self.expr(mk("listcomp", "", self.line, [item, item, self.vnode(b)]), a.t)
            return self.inplace(op, a, self.vnode(more))
        # (builtin types that have no such operation, which a closed value union's members
        # reach: CPython's TypeError for the two objects)
        error = comparison_invalid("unary" + op if unary else op, a.t, "" if unary else b.t, shown)
        if error != "":
            self.raise_("TypeError", self.sconst(error))
            return Val("null", "None")
        if not unary and op == "%" and a.t == "str":
            # A union's str member as a format, of a number: one that has no conversion raises
            # CPython's error, since the number then has no place in it. Formatting with a
            # format computed at run time is not compiled, so one that has a conversion raises
            # too (docs/language/compatibility.md)
            if b.t not in ["int", "float", "bool", "None", BIG]:
                self.err(f"% of a closed union's value that may be a str and {typestr(b.t)} is formatting with a format string computed at run time, which is not supported: narrow the value with isinstance() first")
            spec = self.label()
            plain = self.label()
            self.cbr(self.cmp2("in", Val(self.sconst("%"), "str"), a).v, spec, plain)
            self.place(spec)
            self.raise_("TypeError", self.sconst("% formatting with a format string computed at run time is not supported"))
            self.place(plain)
            self.raise_("TypeError", self.sconst("not all arguments converted during string formatting"))
            return Val("null", "None")
        return self.unary(mk("unary", op, 0, [self.vnode(a)])) if unary else self.arith(op, a, b, shown)
    members = umembers(unopt(v.t)) if is_union(unopt(v.t)) else [unopt(v.t)]
    if is_opt(v.t) or (self.object_union(v.t) and v.v not in self.nn):
        members = ["None"] + members  # (a union that holds objects may be None, as they may)
    end = self.label()
    results: list[Val] = []
    edges: list[str] = []
    # (a member whose payload is a pointer is read under a test of its own tag, the last too:
    # union_proof.py)
    proved = len([m for m in members if m == "str" or is_list(m) or is_dict(m)]) > 0
    for i in range(len(members)):
        member = members[i]
        hit = self.label()
        miss = self.label() if i + 1 < len(members) or proved else ""
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
    if proved:
        self.unreachable()
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return Val("null", "None")
    # A fixed operator has a finite result set: int, float, or int | float.
    # Do not widen int to float, which would lose its runtime type and precision.
    result_type = self.union_type([r.t for r in results])
    if result_type.startswith("!") and (self.object_union(a.t) or (not unary and self.object_union(b.t)) or len([r for r in results if r.t in self.classes and r.t != COMPLEXC]) > 0):
        # (a union with objects says which results have no union; one of numbers alone, complex
        # numbers too, keeps the conversion's own diagnostic below, which the promoting-int
        # baseline records: tools/python_int_optin_exceptions.json)
        promoting = " (a promoting int joins no other result: docs/python-int.md)" if len([r for r in results if r.t == BIG]) > 0 else ""
        self.err(f"unsupported operand types for {shown if shown != '' else op}: the results of {typestr(v.t)}'s members ({', '.join([typestr(r.t) for r in results])}) have no union{promoting}; narrow it with isinstance() first")
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
    members = umembers(unopt(u.t))
    if (self.object_union(u.t) and u.v not in self.nn) or is_opt(u.t):
        members = ["None"] + members  # (a union that holds objects may be None, as they may)
    if is_opt(u.t):
        u = Val(u.v, unopt(u.t)).identity(u)
    end = self.label()
    results: list[Val] = []
    edges: list[str] = []
    proved = len([m for m in members if is_list(m) or is_dict(m)]) > 0  # (as unumeric_case's)
    for j in range(len(members)):
        hit = self.label()
        miss = self.label() if j + 1 < len(members) or proved else ""
        if miss == "":
            self.br(hit)
        elif members[j] == "None":
            self.cbr(self.ptr_cmp('==', vals[i], Val('null', 'None')).v, hit, miss)
        else:
            self.cbr(self.utest(u, [members[j]], False), hit, miss)
        self.place(hit)
        args = [self.vnode(v) for v in vals]
        mine = Val("null", "None") if members[j] == "None" else self.uget(u, members[j])
        args[i] = self.vnode(self.as_int(mine) if name == "chr" and members[j] == "bool" else mine)  # (chr() of a bool: of its int)
        r = Val("null", "None")
        if members[j] == "None" and none_call_error(name, [v.t for v in vals], i) != "":
            self.raise_("TypeError", self.sconst(none_call_error(name, [v.t for v in vals], i)))  # (CPython's, for None)
        elif i == 0 and name in UCALLS and members[j] not in UCALLS[name] and (members[j] == "str" or is_list(members[j]) or is_dict(members[j]) or members[j] in ["int", "float", "bool"]):
            # (a member this builtin takes no value of: CPython's error for that object)
            self.raise_("TypeError", self.sconst(NONEARG[name].replace("NoneType", tname(members[j]))))
        else:
            r = self.builtin(name, args, want)
        if not self.term:
            results.append(r)
            edges.append(self.cur)
            self.br(end)
        if miss != "":
            self.place(miss)
    if proved:
        self.unreachable()
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return Val("null", "None")
    result_type = self.union_type([r.t for r in results])
    if result_type.startswith("!"):
        self.err(f"unsupported call {name}() of {typestr(u.t)}: its members' results ({', '.join([typestr(r.t) for r in results])}) have no union")
    if result_type == "None":
        return Val("null", "None")  # (each member's call gave None, as time.sleep()'s: nothing to join, and LLVM has no void phi)
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

def gen_uidentity(self, a: str, b: str) -> bool:
    # can a value of type a be compared by identity (is, is not) with one of type b, one of them a
    # union that holds numbers or strs beside objects, lists or dicts (Socket | int): where no
    # number or str of one may meet a number or str of the other, whose identity Pystachy does
    # not model ("'is' is only supported for objects and None"). An object, list or dict is the
    # other's by its pointer, and never a number or str (ucmp)
    ma = umembers(unopt(a)) if is_union(unopt(a)) else [unopt(a)]
    mb = umembers(unopt(b)) if is_union(unopt(b)) else [unopt(b)]
    for m in ma + mb:
        if m not in ["int", "float", "bool", "str"] and not is_list(m) and not is_dict(m) and (m not in self.classes or self.classes[m].exc != "" or m == COMPLEXC):
            return False
    return len([x for x in ma if x in ["int", "float", "bool", "str"]]) == 0 or len([y for y in mb if y in ["int", "float", "bool", "str"]]) == 0

def gen_uvalue_orders(self, a: str, b: str) -> bool:
    # can a op b, an ordering, select each member's by its tag (uorder): one of them is a closed
    # value union's (which may be None) and the other is one too, or of a builtin type
    oka = self.value_union(a) if is_union(unopt(a)) else comparison_builtin(unopt(a)) != ""
    okb = self.value_union(b) if is_union(unopt(b)) else comparison_builtin(unopt(b)) != ""
    cx = len([t for t in [a, b] if COMPLEXC in (umembers(unopt(t)) if is_union(unopt(t)) else [unopt(t)])]) > 0
    return (self.value_union(a) or self.value_union(b)) and oka and okb and not cx  # (a complex number's has no member's ordering to select)

def gen_uorder(self, op: str, a: Val, b: Val, top: bool = True) -> Val:
    # a op b, an ordering (<, <=, >, >=) of closed value unions' values (uvalue_orders): the
    # comparison of the two members that their tags name, natively; a pair of types that has no
    # ordering (None, a number with a str, a dict) raises CPython's TypeError. Both operands
    # are evaluated already
    left = is_union(unopt(a.t)) or is_opt(a.t)
    v = a if left else b
    if not is_union(unopt(v.t)) and not is_opt(v.t):
        error = comparison_invalid(op, a.t, b.t)
        if error != "":
            self.raise_("TypeError", self.sconst(error))
            return Val("false", "bool")
        return self.cmp2(op, a, b)
    t = unopt(v.t)
    members = (["None"] if is_opt(v.t) else []) + (umembers(t) if is_union(t) else [t])
    end = self.label()
    ph = Ins("phi", "bool", "")
    reached = 0
    dead = self.term
    proved = len([m for m in members if m == "str" or is_list(m) or is_dict(m)]) > 0  # (as unumeric_case's)
    for j in range(len(members)):
        hit = self.label()
        miss = self.label() if j + 1 < len(members) or proved else ""
        if miss == "":
            self.br(hit)
        elif members[j] == "None":
            self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, hit, miss)
        else:
            self.cbr(self.utest(Val(v.v, t), [members[j]], False), hit, miss)
        self.place(hit)
        x = Val("null", "None") if members[j] == "None" else self.uget(Val(v.v, t), members[j]) if is_union(t) else Val(v.v, t)
        r = self.uorder(op, x if left else a, b if left else x, False)
        if not self.term:
            self.incoming(ph, r.v, self.cur)
            reached += 1
            self.br(end)
        if miss != "":
            self.place(miss)
    if proved:
        self.unreachable()
    self.place(end)
    if reached == 0:
        if top and not dead and self.drying == 0 and not self.curfn.cmpops:
            self.err(f"'{op}' not supported between instances of {typestr(a.t)} and {typestr(b.t)} (no member of the closed union has that ordering)")
        self.unreachable()  # (every pair of members raises)
        return Val("false", "bool")
    return Val(self.phi(ph), "bool")

def gen_ucontains(self, op: str, a: Val, b: Val) -> Val:
    # a in b (not in), where b is a closed value union's value: the test of the list, the dict
    # or the str that its tag names; None and a number raise CPython's TypeError, as a str does
    # for an a that is no str. A dict whose keys have another builtin type than a holds no such
    # key. a, where it is a union's value too, is tested member by member
    at = unopt(a.t)
    if is_union(at) or is_opt(a.t):
        # (a's members first: each is then of one type, which the container's test takes)
        members = (["None"] if is_opt(a.t) else []) + (umembers(at) if is_union(at) else [at])
        end = self.label()
        ph = Ins("phi", "bool", "")
        reached = 0
        proved = len([m for m in members if m == "str" or is_list(m) or is_dict(m)]) > 0  # (as unumeric_case's)
        for j in range(len(members)):
            hit = self.label()
            miss = self.label() if j + 1 < len(members) or proved else ""
            if miss == "":
                self.br(hit)
            elif members[j] == "None":
                self.cbr(self.ptr_cmp('==', a, Val('null', 'None')).v, hit, miss)
            else:
                self.cbr(self.utest(Val(a.v, at), [members[j]], False), hit, miss)
            self.place(hit)
            x = Val("null", "None") if members[j] == "None" else self.uget(Val(a.v, at), members[j]) if is_union(at) else Val(a.v, at)
            r = self.ucontains(op, x, b)
            if not self.term:
                self.incoming(ph, r.v, self.cur)
                reached += 1
                self.br(end)
            if miss != "":
                self.place(miss)
        if proved:
            self.unreachable()
        self.place(end)
        if reached == 0:
            self.unreachable()
            return Val("false", "bool")
        return Val(self.phi(ph), "bool")
    t = unopt(b.t)
    b = self.unone(b, "argument of type 'NoneType' is not iterable")
    tag = self.mload('int', b.v)
    end = self.label()
    ph = Ins("phi", "bool", "")
    reached = 0
    absent = "false" if op == "in" else "true"
    for m in umembers(t):
        arm = self.label()
        nxt = self.label()
        self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(m)), "int")).v, arm, nxt)
        self.place(arm)
        r = Val(absent, "bool")
        if is_list(m):
            r = self.cmp2(op, a, self.uget(b, m))
        elif is_dict(m):
            kt = targs(m)[0]
            if is_list(a.t) or is_dict(a.t):
                self.raise_("TypeError", self.sconst(f"unhashable type: '{tname(a.t)}'"))
            elif not ((kt == "str") != (a.t == "str") and comparison_builtin(a.t) != "" and comparison_builtin(kt) != ""):
                r = self.cmp2(op, a, self.uget(b, m))  # (else a str key and a number, or None: no such key)
        elif m == "str":
            if a.t == "str":
                r = self.cmp2(op, a, self.uget(b, m))
            else:
                self.raise_("TypeError", self.sconst(f"'in <string>' requires string as left operand, not {tname(a.t)}"))
        else:
            self.raise_("TypeError", self.sconst(f"argument of type '{tname(m)}' is not iterable"))
        if not self.term:
            self.incoming(ph, r.v, self.cur)
            reached += 1
            self.br(end)
        self.place(nxt)
    self.unreachable()
    self.place(end)
    if reached == 0:
        self.unreachable()
        return Val("false", "bool")
    return Val(self.phi(ph), "bool")

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
        elif (op == "==" or op == "!=") and la.t == "None" and lb.t == "None":
            r = Val("true" if op == "==" else "false", "bool")  # (the union holds None, as the other operand is)
        elif (op == "==" or op == "!=") and (la.t == "None" or lb.t == "None") and la.t not in self.classes and lb.t not in self.classes:
            pass  # (a number or str is never None)
        elif (op == "==" or op == "!=") and (self.unequal_types(la.t, lb.t) or self.unequal_types(lb.t, la.t)):
            pass  # (a number or str and an object whose class has no __eq__: never equal)
        elif (op == "is" or op == "is not") and (la.t in ["int", "float", "bool", "str"]) != (lb.t in ["int", "float", "bool", "str"]) and not is_union(unopt(la.t)) and not is_union(unopt(lb.t)):
            r = Val("false" if op == "is" else "true", "bool")  # (a number or str is no object, list, dict or None: uidentity)
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
