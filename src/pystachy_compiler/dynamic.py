"""Dynamic values: typing.Any as a runtime-typed box, in the modules that opt in.

A module whose first lines, before any code, hold the comment "# pystachy: dynamic-any" compiles
its Any annotations as the type dyn (docs/dynamic-any.md), elsewhere concrete inference's. A dyn
value is a pointer to an immutable box {DynType *, payload} (runtime.c's dynamic values): the
DynType tells its Python type and the payload's layout, and the payload is a number's bits or a
reference's own pointer. Values are boxed where they flow into dyn storage (a variable, field,
parameter, return value or item of that type) and keep their concrete types and layouts
everywhere else. A box never holds a container whose items are typed: list[Any], dict[Any, Any]
and tuples of boxes are the containers it may hold, and a display that flows into dyn storage is
made so from the start, so that no alias of a container reads its slots with another layout.
Narrowing (isinstance) reads the payload back; a concrete annotation that takes a dyn value checks
its type where it unboxes it. Operations on dyn values call runtime.c's generic helpers, or, for
the program's classes, functions the compiler writes once every class that is boxed is known
(dyn_dispatchers): each tests the box's DynType for those classes and calls the class's own code.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import LINES, dynamic_file
from src.pystachy_compiler.ir import ClassInfo, Data, FnInfo, Ins, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import JSONANY, METHODS, NONEVAR, RTDATA
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import elem, holds_dyn, is_callable, is_dict, is_fn, is_list, is_opt, is_set, is_tuple, is_union, is_vtuple, takes_self, targs, tname, typestr, umembers, unopt

DYN = "dyn"
# what isinstance(x, int) narrows a dyn local to: still the box (a bool passes the test too),
# which arithmetic reads as an int (dyn_proven_int); everything else reads it as dyn
DYNINT = "dyn[int]"
# runtime.c's DynType kinds (DK_*) and the flags of a class's (DF_*)
DK_OBJ = 8
DK_FUNC = 9
DF_EQ = 1
DF_CMP = 2
DF_HASH = 4
DF_BOXID = 8
DF_NE = 16
DF_X = 32
# the comparisons the program's @o.x.<class> runs with any value, by their op codes (+ 1: dyn_xhelper)
XCMP: list[str] = ["__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"]
XOPS: list[str] = ["==", "!=", "<", "<=", ">", ">="]
# the operator codes of pys_dyn_binop and pys_dyn_unary
BINOPS: dict[str, int] = {"+": 0, "-": 1, "*": 2, "/": 3, "//": 4, "%": 5, "**": 6, "<<": 7, ">>": 8, "&": 9, "|": 10, "^": 11}
UNOPS: dict[str, int] = {"-": 0, "+": 1, "~": 2}
CMPOPS: dict[str, int] = {"<": 0, "<=": 1, ">": 2, ">=": 3}
BINDUNDERS: dict[str, str] = {"+": "__add__", "-": "__sub__", "*": "__mul__", "/": "__truediv__", "//": "__floordiv__", "%": "__mod__",
                              "**": "__pow__", "<<": "__lshift__", ">>": "__rshift__", "&": "__and__", "|": "__or__", "^": "__xor__"}
# the builtin types' DynTypes (RTDATA), by the static type of the payload
BUILTIN: dict[str, str] = {"None": "pys_dyntype_none", "bool": "pys_dyntype_bool", "int": "pys_dyntype_int", "float": "pys_dyntype_float",
                           "str": "pys_dyntype_str", "list[dyn]": "pys_dyntype_list", "dict[dyn,dyn]": "pys_dyntype_dict",
                           "vtuple[dyn]": "pys_dyntype_tuple"}


def gen_dyn_policy(self, line: int) -> bool:
    # does the module of source line line compile Any as dyn
    return dynamic_file(line // LINES)


def gen_rtdata(self, sym: str) -> str:
    # the operand of runtime data sym (RTDATA), which the module then declares
    if sym not in RTDATA:
        self.err(f"internal error: no runtime data {sym}")
    self.rtdatas[sym] = True
    return "@" + sym


def gen_dyn_boxable(self, t: str) -> str:
    # why a value of static type t cannot become a dyn value, or "": a scalar, None, a str, an
    # object of the program's classes, a container of boxes, a tuple (made one of boxes), a union
    # of these, and dyn
    if t == DYN or t in BUILTIN or t == NONEVAR:
        return ""
    if t in self.classes and t not in self.tmpl:
        return "" if self.classes[t].exc == "" else f"an exception object ({typestr(t)}) as Any is not supported yet"
    if is_opt(t):
        return self.dyn_boxable(unopt(t))
    if is_union(t):
        for m in umembers(t):
            if self.dyn_boxable(m) != "":
                return self.dyn_boxable(m)
        return ""
    if is_tuple(t):
        for x in targs(t):
            if self.dyn_boxable(x) != "":
                return self.dyn_boxable(x)
        return ""
    if is_vtuple(t):
        return self.dyn_boxable(targs(t)[0])
    if is_list(t) or is_dict(t) or is_set(t):
        # (an alias of a typed container would read its slots with another layout, or store a
        # box where its typed code reads a number: copying it would break its identity)
        which = "list[Any]" if is_list(t) else "dict[Any, Any]" if is_dict(t) else "set[Any]"
        return f"a {typestr(t)} cannot become an Any value: its items are typed, and Any's containers hold Any items (make it a {which} from the start, or copy it)"
    if t.startswith("fn[b:") or t.startswith("fn[d:") or t.startswith("fn[u:"):
        return f"a builtin function or method as an Any value is not supported yet ({typestr(t)})"
    if is_fn(t) or is_callable(t):
        return ""
    return f"a {typestr(t)} value cannot become an Any value"


def gen_dyn_type(self, t: str) -> str:
    # the DynType operand of payloads of static type t (a class's: its own, dyn_class_type)
    if t in BUILTIN:
        return self.rtdata(BUILTIN[t])
    return self.dyn_class_type(t)


def gen_dyn_class_type(self, c: str) -> str:
    # @dt.<class>: the DynType of class c's objects, made once (and its bases'): DK_OBJ, its
    # descriptor O<id> (which pys_obj_repr dispatches on), its name, its O<id>, its base's DynType,
    # and its flags: DF_EQ and DF_CMP where the class defines == or an ordering, which the program's
    # pys_obj_eq and pys_obj_cmp run then (ocmp), DF_HASH where it hashes through its __hash__ (or
    # is unhashable: hcls). Each class that gets one is a case of the dispatchers (dyn_dispatchers)
    if c in self.dyntypes:
        return self.dyntypes[c]
    ci = self.classes[c]
    name = f"@dt.{c}"
    self.dyntypes[c] = name
    base = self.dyn_class_type(ci.base) if ci.base in self.classes and self.classes[ci.base].exc == "" else "null"
    d = self.desc(c, "repr")  # (O<id>: its repr helper)
    flags = 0
    ms = ci.methods
    if "__eq__" in ms or len([x for x in self.classes.values() if x.tag > 0 and self.derives(x.name, c) and "__eq__" in x.methods]) > 0:
        flags |= DF_EQ  # (also where a subclass defines it, whose == the class's helper dispatches to)
    if "__ne__" in ms or len([x for x in self.classes.values() if x.tag > 0 and self.derives(x.name, c) and "__ne__" in x.methods]) > 0:
        flags |= DF_NE  # (its != runs the program's @o.ne helper, as == does @o.eq: pys_dyn_ne)
        self.one[c] = True
    cmps = ["__lt__", "__le__", "__gt__", "__ge__"]
    if len([k for k in cmps if k in ms]) > 0 or len([x for x in self.classes.values() if x.tag > 0 and self.derives(x.name, c) and len([k for k in cmps if k in x.methods]) > 0]) > 0:
        flags |= DF_CMP  # (also where a subclass defines one, whose reflected method the class's helper runs first)
    if flags != 0:
        self.ocmp[c] = True  # (@o.eq and @o.cmp, compiled leniently: what the class cannot compare raises when it runs)
    if c in self.nts:
        flags |= DF_EQ | DF_CMP | DF_NE  # (a NamedTuple's objects compare as tuples of their fields: ntop)
        self.ocmp[c] = True
        self.one[c] = True  # (its != is tuple's, also where its class defines __eq__ but no __ne__)
    if len([m for m in XCMP if self.dyn_xmethod(c, m)]) > 0 or c in self.nts:
        flags |= DF_X  # (its comparisons with values of other types run its methods: @o.x.<class>, pys_dyn_eq)
        self.xobj[c] = True
    if self.hash_kind(c) != "id" or len([x for x in self.classes.values() if x.tag > 0 and self.derives(x.name, c) and self.hash_kind(x.name) != "id"]) > 0 or c in self.nts:
        # (a NamedTuple's: tuple's hash of its fields or its own __hash__, as hash_value gives it)
        if c not in self.hcls:
            self.hcls[c] = True
        flags |= DF_HASH
    dt = Data("dyntype", name)
    dt.refs = [self.sconst(d), self.sconst(short(c)), base]
    dt.items = [Val(str(DK_OBJ), "int"), Val(str(self.ocls[c]), "int"), Val(str(flags), "int")]
    self.consts.append(dt)
    self.dynclasses.append(c)
    return name


def gen_dyn_xmethod(self, c: str, m: str) -> bool:
    # does class c have comparison method m (its own or a base's) for a value of another type: not
    # one that @dataclass wrote, which declines an object of another class, nor one whose
    # declaration failed, which the lenient helpers leave out (see desc)
    ms = self.classes[c].methods
    return m in ms and ms[m].bad == "" and not (ms[m].synthetic and self.is_dc(ms[m].cls))


def gen_dyn_xhelper(self, c: str) -> None:
    # @o.x.<class>(op, a, b): comparison op (1 ==, 2 !=, 3 <, 4 <=, 5 >, 6 >=, XCMP) of the object a
    # of class c with b, an Any value that is no object of c's hierarchy (pys_dyn_eq, through
    # pys_obj_cmp(-1 - id, op, a, b): gen_dispatch): 0 or 1, its result, 2 where c has no method
    # for op, as object's own methods decline, or 3 where its method does not take b (dyn_xbody)
    f = FnInfo("x", f"@o.x.{c}", self.classes[c].node, "")
    f.params = ["op", "a", "b"]
    f.ptypes = ["int", c, DYN]
    f.ret = "int"
    self.lenient = True
    self.function(f, [mk("dynx", c, self.classes[c].node.line, [])])
    self.lenient = False


def gen_dyn_xbody(self, c: str) -> None:
    # the body of @o.x.<class> (dyn_xhelper): c's own method, which takes b as its parameter's type
    # takes an Any value; != is not == where c has no __ne__, as object.__ne__ inverts __eq__. A
    # method annotated with a type that b's value does not have (dyn_isa), or that no Any value has
    # (list[int]), cannot run with it: 3, and the comparison is identity's, or TypeError for an
    # ordering, without b's reflected method, as a method that returns no NotImplemented (#499)
    # decides in CPython. A NamedTuple without the method (!= also where it defines __eq__:
    # tuple's __ne__) compares its fields with a tuple, as tuple's methods do, which decline any
    # other value
    line = self.line
    op = self.read(mk("name", "op", line, []))
    a = self.read(mk("name", "a", line, []))
    b = self.read(mk("name", "b", line, []))
    nt = c in self.nts
    for k in range(len(XCMP)):
        m = XCMP[k]
        inv = False
        if not self.dyn_xmethod(c, m) and k == 1 and self.dyn_xmethod(c, "__eq__") and not nt:
            m = "__eq__"
            inv = True
        if not self.dyn_xmethod(c, m) and not nt:
            continue
        hit = self.label()
        nxt = self.label()
        self.cbr(self.num_cmp("==", op, Val(str(k + 1), "int")).v, hit, nxt)
        self.place(hit)
        ps = self.classes[c].methods[m].ptypes if self.dyn_xmethod(c, m) else []
        takes = self.dyn_isa(b, ps[1]) if len(ps) >= 2 else ""
        if takes == "false" or f"{c}.{m}" in self.xnot:
            self.ret_(Val("3", "int"))
            self.place(nxt)
            continue
        if takes != "":
            run = self.label()
            decline = self.label()
            self.cbr(takes, run, decline)
            self.place(decline)
            self.ret_(Val("3", "int"))
            self.place(run)
        if self.dyn_xmethod(c, m):
            self.xtry = f"{c}.{m}"
            r = self.truth(self.expr(mk("call", "", line, [mk("attr", m, line, [self.vnode(a)]), self.vnode(b)]), ""))
            self.xtry = ""
            if inv:
                r = self.scalar("xor", [Val(r, "bool"), Val("true", "bool")])
            if not self.term:
                self.ret_(Val(self.select(r, Val("1", "int"), Val("0", "int")), "int"))
        else:
            tup = self.label()
            other = self.label()
            self.cbr(self.dyn_test(b, ["vtuple[dyn]"]), tup, other)
            self.place(tup)
            same = self.cmp2(XOPS[k], self.ntup(a, True), b)
            self.ret_(Val(self.select(same.v, Val("1", "int"), Val("0", "int")), "int"))
            self.place(other)
            self.ret_(Val("2", "int"))
        self.place(nxt)
    self.ret_(Val("2", "int"))


def gen_dyn_box(self, v: Val) -> Val:
    # v as a dyn value (dyn_boxable says which values can be)
    t = self.rec_type(v.t)
    if t == DYN:
        return v
    if t == "None" or t == NONEVAR:
        return Val(self.rtdata("pys_dyn_none_box"), DYN)
    if t == "bool":
        return Val(self.select(v.v, Val(self.rtdata("pys_dyn_true_box"), DYN), Val(self.rtdata("pys_dyn_false_box"), DYN)), DYN)
    if t == "int":
        return Val(self.rt("pys_dyn_int", "ptr", [f"i64 {v.v}"]), DYN)
    if t == "float":
        return Val(self.rt("pys_dyn_float", "ptr", [f"double {v.v}"]), DYN)
    if t == "str" and v.v.startswith("@s."):
        # a str constant's box is a constant too, one per constant, as a str is its payload's
        # object: so a literal key of a dict[str, Any], whose keys are boxes (#777), allocates
        # nothing, and is the very box that a display or a store of that literal put there
        g = "@dbs." + v.v[3:]
        if g not in self.dynboxes:
            self.dynboxes[g] = True
            d = Data("dynbox", g)
            d.refs = [self.dyn_type("str"), v.v]
            self.consts.append(d)
        return Val(g, DYN)
    why = self.dyn_boxable(t)
    if why != "":
        self.err(why)
    if is_union(unopt(t)):
        return self.dyn_union_box(Val(v.v, t))
    if is_opt(t):
        # None or the value's box
        end = self.label()
        some = self.label()
        start = self.cur
        self.cbr(self.ptr_cmp("==", v, Val("null", "None")).v, end, some)
        self.place(some)
        b = self.dyn_box(self.deref(v))
        got = self.cur
        self.br(end)
        self.place(end)
        ph = Ins("phi", DYN, "")
        self.incoming(ph, self.rtdata("pys_dyn_none_box"), start)
        self.incoming(ph, b.v, got)
        return Val(self.phi(ph), DYN)
    if is_tuple(t):
        # a tuple of boxes, made of its items (a tuple cannot change: only its identity differs)
        items = [self.dyn_box(self.tget(v, i)) for i in range(len(targs(t)))]
        raw = self.tuple_(items) if len(items) > 0 else Val("null", "None")
        tv = self.rt("pys_vtuple_from", "ptr", [f"ptr {raw.v}", f"i64 {len(items)}"])
        return self.dyn_box(Val(tv, "vtuple[dyn]"))
    if is_vtuple(t) and t != "vtuple[dyn]":
        self.err(f"a {typestr(t)} as an Any value is not supported yet")
    if t in self.classes and self.classes[t].tag > 0:
        return Val(self.rt("pys_dyn_ref", "ptr", [f"ptr {self.dyn_tagged_type(v)}", f"ptr {v.v}"]), DYN)
    if is_fn(t) or is_callable(t):
        return self.dyn_fn_box(v)
    return Val(self.rt("pys_dyn_ref", "ptr", [f"ptr {self.dyn_type(t)}", f"ptr {v.v}"]), DYN)


def gen_dyn_union_box(self, v: Val) -> Val:
    # union value v (a union's box, null where it is None: to_union) as a dyn value: the box of
    # the member's value its tag selects, as usplit selects a member's operation
    u = Val(v.v, unopt(v.t))
    ms = umembers(u.t)
    end = self.label()
    ph = Ins("phi", DYN, "")
    if is_opt(v.t) or len([m for m in ms if m in self.classes]) > 0:
        some = self.label()
        self.incoming(ph, self.rtdata("pys_dyn_none_box"), self.cur)
        self.cbr(self.ptr_cmp("==", v, Val("null", "None")).v, end, some)
        self.place(some)
    for j in range(len(ms)):
        hit = self.label()
        miss = self.label() if j + 1 < len(ms) else ""
        if miss == "":
            self.br(hit)
        else:
            self.cbr(self.utest(u, [ms[j]], False), hit, miss)
        self.place(hit)
        b = self.dyn_box(self.uget(u, ms[j]))
        self.incoming(ph, b.v, self.cur)
        self.br(end)
        if miss != "":
            self.place(miss)
    self.place(end)
    return Val(self.phi(ph), DYN)


def gen_dyn_value_type(self, v: Val) -> str:
    # the DynType of typed value v's exact type, as type(v) compares with an Any value's
    # (refl_dyn_type_cmp): its box's; else a list's, a dict's or a tuple's for one whose items no
    # box holds, null where no box holds a value of its type (bytes, a set), and for an optional
    # or a union whose value may be one of these, the one of the value it holds: None's for None,
    # a member's by its tag, as dyn_union_box selects the member's box
    t = self.rec_type(v.t)
    if self.dyn_boxable(t) == "":
        return self.dyn_typeof(self.dyn_box(v))
    if is_list(t) or is_dict(t) or is_tuple(t) or is_vtuple(t):
        return self.dyn_type("list[dyn]" if is_list(t) else "dict[dyn,dyn]" if is_dict(t) else "vtuple[dyn]")
    if not is_union(unopt(t)) and not (is_opt(t) and t != NONEVAR):
        return "null"
    u = Val(v.v, unopt(t))
    ms = umembers(u.t) if is_union(u.t) else [u.t]
    end = self.label()
    ph = Ins("phi", "dyntype", "")
    if is_opt(t) or len([m for m in ms if m in self.classes]) > 0:
        some = self.label()
        self.incoming(ph, self.dyn_type("None"), self.cur)
        self.cbr(self.ptr_cmp("==", v, Val("null", "None")).v, end, some)
        self.place(some)
    for j in range(len(ms)):
        hit = self.label()
        miss = self.label() if j + 1 < len(ms) else ""
        if miss == "":
            self.br(hit)
        else:
            self.cbr(self.utest(u, [ms[j]], False), hit, miss)
        self.place(hit)
        r = self.dyn_value_type(self.uget(u, ms[j]) if is_union(u.t) else u)
        self.incoming(ph, r, self.cur)
        self.br(end)
        if miss != "":
            self.place(miss)
    self.place(end)
    return self.phi(ph)


def gen_dyn_tagged_type(self, v: Val) -> str:
    # the DynType of the object v of a class of a hierarchy: its concrete class's, by its tag
    # (None, null, has no tag: pys_dyn_ref boxes it as None whatever DynType it is given)
    cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, v.t) and not c.excluded and c.name not in self.tmpl]
    if len(cs) == 1:
        return self.dyn_class_type(cs[0].name)
    end = self.label()
    start = self.cur
    ph = Ins("phi", "dyntype", "")
    some = self.label()
    self.incoming(ph, "null", start)
    self.cbr(self.ptr_cmp("==", v, Val("null", "None")).v, end, some)
    self.place(some)
    tag = self.mload("int", v.v)
    r = self.dyn_class_type(cs[-1].name)
    for c in cs[:-1]:
        hit = self.num_cmp("==", Val(tag, "int"), Val(str(c.tag), "int")).v
        r = self.select(hit, Val(self.dyn_class_type(c.name), "dyntype"), Val(r, "dyntype"))
    self.incoming(ph, r, self.cur)
    self.br(end)
    self.place(end)
    return self.phi(ph)


def gen_dyn_typeof(self, v: Val) -> str:
    # the DynType pointer of box v (an immutable box: no memory effect)
    i = Ins("dyn.type", "dyntype", "")
    i.a = [Val(v.v, DYN)]
    self.put(i, 1)
    return f"%t{i.r[0]}"


def gen_dyn_payload(self, v: Val, t: str) -> Val:
    # the payload of box v, which a test proved to be of static type t
    if t == "None" or t == NONEVAR:
        return Val("null", "None")
    i = Ins("dyn.payload", "%slot", t)
    i.a = [Val(v.v, DYN)]
    self.put(i, 2)
    return self.from_slot(f"%t{i.r[1]}", t)


def gen_dyn_unbox(self, v: Val, t: str, what: str = "") -> Val:
    # dyn value v as a value of static type t, which a typed variable, parameter, field or
    # return takes: its payload where v's type is t (an object's class t's or a subclass's),
    # else TypeError (docs/dynamic-any.md: CPython does not check annotations); an optional t
    # takes None too, and a union one of its members' values
    if t == DYN:
        return v
    if t == "None":
        self.dyn_check(v, ["None"], "None")
        return Val("null", "None")
    if is_opt(t) and t != NONEVAR:
        # None stays None, a value is unboxed as the optional's value type
        end = self.label()
        some = self.label()
        start = self.cur
        isnone = self.ptr_cmp("==", Val(self.dyn_typeof(v), "dyntype"), Val(self.rtdata("pys_dyntype_none"), "dyntype")).v
        self.cbr(isnone, end, some)
        self.place(some)
        x = self.coerce(self.dyn_unbox(v, unopt(t), what), t)
        got = self.cur
        self.br(end)
        self.place(end)
        ph = Ins("phi", t, "")
        self.incoming(ph, "null", start)
        self.incoming(ph, x.v, got)
        return Val(self.phi(ph), t)
    if t in BUILTIN:
        r = self.rt("pys_dyn_unbox", "i64", [f"ptr {v.v}", f"ptr {self.dyn_type(t)}"])
        return self.from_slot(self.to_slot(Val(r, "int")), t) if t != "int" else Val(r, "int")
    if t in self.classes and t not in self.tmpl and self.classes[t].exc == "":
        r = self.rt("pys_dyn_unbox", "i64", [f"ptr {v.v}", f"ptr {self.dyn_class_type(t)}"])
        return self.from_slot(self.to_slot(Val(r, "int")), t)
    if is_union(unopt(t)):
        ms = umembers(unopt(t)) + (["None"] if is_opt(t) or self.optional(unopt(t)) == unopt(t) else [])
        self.dyn_check(v, ms, typestr(t))
        return self.dyn_select(v, ms, t)
    if is_tuple(t):
        # a tuple of the length and item types t gives, from a tuple of boxes
        tv = self.dyn_unbox(v, "vtuple[dyn]", what)
        n = len(targs(t))
        size = self.mload("int", tv.v)
        self.rt("pys_unpack_check", "void", [f"i64 {size}", f"i64 {n}"])
        items: list[Val] = []
        for j in range(n):
            slot = self.rt("pys_vtuple_get", "i64", [f"ptr {tv.v}", f"i64 {j}"])
            items.append(self.dyn_unbox(self.from_slot(slot, DYN), targs(t)[j], what))
        return self.tuple_(items)
    self.err(f"{what if what != '' else 'an Any value'} cannot be used as {typestr(t)} (narrow it with isinstance() first)")
    return v


def gen_dyn_check(self, v: Val, ts: list[str], shown: str) -> None:
    # TypeError unless box v holds a value of one of static types ts
    self.guard(self.scalar("xor", [Val(self.dyn_test(v, ts), "bool"), Val("true", "bool")]), f"TypeError: expected {shown}")


def gen_dyn_unboxable(self, t: str) -> bool:
    # can an Any value have static type t: does dyn_unbox compile for it (not for a list[int],
    # whose items an Any list does not type, nor for a function)
    if t == DYN or t == "None" or t in BUILTIN:
        return True
    if is_opt(t) and t != NONEVAR:
        return self.dyn_unboxable(unopt(t))
    if t in self.classes:
        return t not in self.tmpl and self.classes[t].exc == ""
    if is_union(unopt(t)):
        return True
    return is_tuple(t) and len([x for x in targs(t) if not self.dyn_unboxable(x)]) == 0


def gen_dyn_isa(self, v: Val, t: str) -> str:
    # i1: does dyn_unbox take box v as a value of static type t without an error: "" where it
    # takes any value (t is dyn, or a template's ""), "false" where no Any value has t
    # (dyn_unboxable: dyn_xbody's comparison method annotated t never runs)
    if t == "" or t == DYN:
        return ""
    if not self.dyn_unboxable(t):
        return "false"
    if t == "None":
        return self.dyn_test(v, ["None"])
    if is_opt(t) and t != NONEVAR:
        r = self.dyn_isa(v, unopt(t))
        return "" if r == "" else self.scalar("or", [Val(self.dyn_test(v, ["None"]), "bool"), Val(r, "bool")])
    if t in BUILTIN:
        return self.dyn_test(v, [t])
    if t in self.classes and t not in self.tmpl and self.classes[t].exc == "":
        # (an object of t or a subclass, or None, as pys_dyn_unbox walks the box's bases: also of
        # a subclass that the program boxes after this test is compiled)
        r = self.rt("pys_dyn_isa", "i64", [f"ptr {v.v}", f"ptr {self.dyn_class_type(t)}"])
        return self.num_cmp("!=", Val(r, "int"), Val("0", "int")).v
    if is_union(unopt(t)):
        return self.dyn_test(v, umembers(unopt(t)) + (["None"] if is_opt(t) or self.optional(unopt(t)) == unopt(t) else []))
    # a tuple of t's length whose items each have t's item type (dyn_unbox checks them in turn)
    end = self.label()
    ph = Ins("phi", "bool", "")
    tup = self.label()
    self.incoming(ph, "false", self.cur)
    self.cbr(self.dyn_test(v, ["vtuple[dyn]"]), tup, end)
    self.place(tup)
    tv = self.dyn_payload(v, "vtuple[dyn]")
    sized = self.label()
    self.incoming(ph, "false", self.cur)
    self.cbr(self.num_cmp("==", Val(self.mload("int", tv.v), "int"), Val(str(len(targs(t))), "int")).v, sized, end)
    self.place(sized)
    for j in range(len(targs(t))):
        r = self.dyn_isa(self.from_slot(self.rt("pys_vtuple_get", "i64", [f"ptr {tv.v}", f"i64 {j}"]), DYN), targs(t)[j])
        if r != "":
            nx = self.label()
            self.incoming(ph, "false", self.cur)
            self.cbr(r, nx, end)
            self.place(nx)
    self.incoming(ph, "true", self.cur)
    self.br(end)
    self.place(end)
    return self.phi(ph)


def gen_dyn_select(self, v: Val, ts: list[str], t: str) -> Val:
    # box v, which holds a value of one of types ts, as a value of type t (a union of them)
    end = self.label()
    ph = Ins("phi", t, "")
    for m in ts:
        hit = self.label()
        nxt = self.label()
        self.cbr(self.dyn_test(v, [m]), hit, nxt)
        self.place(hit)
        x = self.coerce(self.dyn_payload(v, m), t)
        self.incoming(ph, x.v, self.cur)
        self.br(end)
        self.place(nxt)
    self.unreachable()
    self.place(end)
    return Val(self.phi(ph), t)


def gen_dyn_test(self, v: Val, ts: list[str]) -> str:
    # i1: does box v hold a value of one of static types ts (a class's object: of it or a subclass)
    if len(ts) == 0:
        return "false"
    t = Val(self.dyn_typeof(v), "dyntype")
    r = ""
    for m in ts:
        for d in self.dyn_types_of(m):
            x = self.ptr_cmp("==", t, Val(d, "dyntype")).v
            r = x if r == "" else self.scalar("or", [Val(r, "bool"), Val(x, "bool")])
    return r if r != "" else "false"


def gen_dyn_types_of(self, t: str) -> list[str]:
    # the DynTypes of the boxes that hold values of static type t: a class's and its subclasses'
    # of those boxed (a subclass boxed later is a case the program tests too: see dyn_dispatchers)
    if t in BUILTIN:
        return [self.dyn_type(t)]
    if t in self.classes:
        return [self.dyntypes[c] for c in self.dynclasses if self.derives(c, t)]
    return []


def gen_dyn_isinst_types(self, c: Node) -> list[str]:
    # the static types whose boxes isinstance(x, c) accepts, for a dyn x: the builtin types it
    # names, a class (whose subclasses' boxes dyn_test accepts too), a tuple of these; [""] where
    # c is no type this decides
    if c.kind == "tuple" or (c.kind == "binop" and c.s == "|"):
        out: list[str] = []
        for x in c.kids:
            ts = ["None"] if x.kind == "None" else self.dyn_isinst_types(x)
            if "" in ts:
                return [""]
            out.extend(ts)
        return out
    if c.kind == "call" and len(c.kids) == 2 and c.kids[0].kind == "name" and c.kids[0].s == "type" and c.kids[1].kind == "None":
        return ["None"]
    if c.kind != "name":
        return [""]
    if c.s in self.classes and self.classes[c.s].exc == "" and c.s not in self.tmpl:
        self.dyn_class_type(c.s)  # (so that dyn_test has its DynType, even if no object of it is boxed yet)
        return [c.s]
    if self.bound(c.s):
        return [""]
    m = {"int": ["int", "bool"], "bool": ["bool"], "float": ["float"], "str": ["str"], "list": ["list[dyn]"], "dict": ["dict[dyn,dyn]"],
         "tuple": ["vtuple[dyn]"], "object": ["*"]}
    if c.s in m:
        return m[c.s]
    if c.s in "set frozenset bytes bytearray complex range type memoryview slice".split():
        return []  # (no box holds one yet)
    return [""]


def gen_dyn_isinst(self, v: Val, c: Node) -> Val:
    # isinstance(v, c) for a dyn v
    ts = self.dyn_isinst_types(c)
    if "" in ts:
        self.err("isinstance() of an Any value is only supported with builtin types, classes, None and tuples of them")
    if "*" in ts:
        return Val("true", "bool")
    return Val(self.dyn_test(v, ts), "bool")


def gen_dyn_narrow_type(self, c: Node, truth: bool) -> str:
    # the static type a dyn local has where isinstance(x, c) is truth: the one type c names (the
    # payload's), else "" (it stays dyn); DYNINT where c is int, which a bool passes too
    if not truth:
        return ""
    ts = self.dyn_isinst_types(c)
    if len(ts) == 2 and ts[0] == "int" and ts[1] == "bool":
        return DYNINT
    if len(ts) != 1 or ts[0] == "" or ts[0] == "*":
        return ""
    return ts[0]


def gen_dyn_narrowed(self, v: Val, nt: str) -> Val:
    # box v of a local that a test narrowed to nt: its payload as a value of type nt, or where nt is
    # DYNINT the box itself, which arithmetic and comparisons then read as an int (dyn_proven_int)
    if nt == DYNINT:
        self.dynints[v.v] = True
        return v
    return self.dyn_payload(v, nt)


def gen_dyn_proven_int(self, v: Val) -> Val:
    # v as an int, for an operation whose result is the same for a bool as for the int it equals:
    # a static int or bool, or a box that a test proved holds one (its payload: 0 or 1 for a bool);
    # Val("", "") for any other value
    if v.t == "int" or v.t == "bool":
        return self.as_int(v)
    if v.t == DYN and v.v in self.dynints:
        return self.dyn_payload(v, "int")
    return Val("", "")


# ---- widening: storage that its first value typed, which an Any value reaches later

def ann_binds(ns: list[Node], name: str) -> bool:
    # does an annotated assignment among ns, outside the defs, lambdas and classes in them, declare
    # name
    for n in ns:
        if n.kind == "annassign" and n.kids[0].kind == "name" and n.kids[0].s == name:
            return True
        if n.kind != "def" and n.kind != "lambda" and n.kind != "class" and n.kind != "subclass" and ann_binds(n.kids, name):
            return True
    return False


def gen_dyn_widen(self, name: str, t: str) -> bool:
    # an Any value stored into local name (or returned, name ""), which its earlier stores (the
    # function's earlier returns) gave static type t, in a module that compiles Any as dyn: the
    # function is compiled again with that storage dynamic from the start (gen_function), as
    # CPython's variable holds whatever was assigned last. Not where something besides the code of
    # this compilation holds t: an annotation, a closure's cell, a generator's frame, a value of t
    # that cannot be boxed as it is. True where it will be (this compilation's store unboxes)
    f = self.curfn
    if self.drying > 0 or self.modlevel or f.gen or not self.dyn_policy(f.node.line) or self.dyn_boxable(t) != "":
        return False
    if name == "":
        if not f.infer:
            return False
        if f.ll not in self.dynrets:
            self.dynrets[f.ll] = f"{short(f.name)}() returns both {typestr(t)} and Any (each function has one return type)"
            self.dynrline[f.ll] = self.line
        return True
    if name in self.cells or name in self.compvars or name in self.nlw or (f.clo >= 0 and name in self.closures[f.clo].caps):
        return False
    if len(f.params) > 0 and name == f.params[0] and takes_self(f):
        return False
    for p in f.node.kids[0].kids if f.node.kind == "def" else []:
        if p.s == name and p.kids[0].kind != "noann":
            return False
    if f.node.kind != "def" or ann_binds(f.node.kids[2].kids, name):
        return False
    if f.ll not in self.dynwide:
        self.dynwide[f.ll] = {}
    self.dynwide[f.ll][name] = True
    return True


def gen_dyn_fields(self, ci: ClassInfo) -> None:
    # in a module that compiles Any as dyn: the fields of class ci that __init__ gave a type
    # (scan_fields), and a method of the class assigns an Any value later, made dynamic from the
    # start. A field's type is decided before any code that reads it is compiled, so it is what the
    # declarations show: the methods' Any parameters, fields and returns (dyn_guessed)
    if not self.dyn_policy(ci.node.line) or ci.name in self.tmpl or ci.exc != "" or ci.origin != "":
        return
    for m in ci.methods:
        f = ci.methods[m]
        if f.cls == ci.name and f.node.kind == "def" and takes_self(f) and not f.pending:
            self.dyn_field_stores(ci, f, f.node.kids[2].kids)


def gen_dyn_field_stores(self, ci: ClassInfo, f: FnInfo, ns: list[Node]) -> None:
    for st in ns:
        if st.kind == "def" or st.kind == "lambda" or st.kind == "class" or st.kind == "subclass":
            continue
        if st.kind == "assign" or st.kind == "augassign":
            for x in st.kids[:-1]:
                if x.kind == "attr" and x.kids[0].kind == "name" and x.kids[0].s == f.params[0] and x.s in ci.ftypes and ci.ftypes[x.s] != DYN:
                    if x.s not in ci.fdefault and self.dyn_boxable(ci.ftypes[x.s]) == "" and not field_ann(ci, x.s) and self.dyn_guessed(st.kids[-1], f):
                        ci.ftypes[x.s] = DYN
        self.dyn_field_stores(ci, f, st.kids)


def field_ann(ci: ClassInfo, name: str) -> bool:
    # is field name of class ci declared with an annotation: in the class body (name: T) or in a
    # method (self.name: T = v)
    for st in ci.node.kids[0].kids:
        if st.kind == "annassign" and st.kids[0].kind == "name" and st.kids[0].s == name:
            return True
    for m in ci.methods:
        f = ci.methods[m]
        if f.cls == ci.name and f.node.kind == "def" and len(f.params) > 0 and self_ann(f.node.kids[2].kids, f.params[0], name):
            return True
    return False


def self_ann(ns: list[Node], me: str, name: str) -> bool:
    for n in ns:
        if n.kind == "annassign" and n.kids[0].kind == "attr" and n.kids[0].s == name and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == me:
            return True
        if n.kind != "def" and n.kind != "lambda" and n.kind != "class" and n.kind != "subclass" and self_ann(n.kids, me, name):
            return True
    return False


def gen_dyn_guessed(self, e: Node, f: FnInfo) -> bool:
    # is e, an expression of method f, an Any value as the declarations show (guess): a parameter,
    # field or return annotated Any, an item of a container of Any items, arithmetic on one, or a
    # conditional expression with one
    if e.kind == "binop" and e.s in BINOPS:
        return self.dyn_guessed(e.kids[0], f) or self.dyn_guessed(e.kids[1], f)
    if e.kind == "unary" and e.s != "not":
        return self.dyn_guessed(e.kids[0], f)
    if e.kind == "ifexp":
        return self.dyn_guessed(e.kids[1], f) or self.dyn_guessed(e.kids[2], f)
    if e.kind == "index" and len(e.kids) == 2:
        t = self.guess(e.kids[0], f)
        return t == DYN or t == "list[dyn]" or t == "vtuple[dyn]" or (is_dict(t) and targs(t)[1] == DYN)
    return self.guess(e, f) == DYN


def gen_dyn_global_ahead(self, name: str, t: str) -> bool:
    # module code's first store of module variable name, a value of static type t, in a module that
    # compiles Any as dyn: does module code assign it an Any value later, as far as can be told
    # before it runs (dyn_ahead)? Then it is dynamic from the start: a module variable's type is
    # decided where it is first stored, since the functions compiled meanwhile read it
    if not self.modlevel or self.drying > 0 or self.curfn.node.kind == "def" or not self.dyn_policy(self.line) or self.dyn_boxable(t) != "":
        return False
    return self.dyn_stores_ahead(self.curfn.node.kids, name, {})


def gen_dyn_stores_ahead(self, ns: list[Node], name: str, env: dict[str, bool]) -> bool:
    # does a statement among ns assign name a value dyn_ahead finds dynamic; env: the loop
    # targets around them, whether each takes Any items
    for st in ns:
        if st.kind == "def" or st.kind == "lambda" or st.kind == "class" or st.kind == "subclass":
            continue
        if st.kind == "assign" or st.kind == "augassign":
            for x in st.kids[:-1]:
                if x.kind == "name" and x.s == name and self.dyn_ahead(st.kids[-1], env):
                    return True
        if st.kind == "for" and len(st.kids) >= 3:
            inner = dict(env)
            et = self.dyn_items_ahead(st.kids[1], env)
            if st.kids[0].kind == "name":
                inner[st.kids[0].s] = et == DYN
            elif st.kids[0].kind == "tuple" or st.kids[0].kind == "list":
                ts = targs(et) if is_tuple(et) and len(targs(et)) == len(st.kids[0].kids) else []
                for j in range(len(st.kids[0].kids)):
                    if st.kids[0].kids[j].kind == "name":
                        inner[st.kids[0].kids[j].s] = et == DYN or (len(ts) > 0 and ts[j] == DYN)
            if self.dyn_stores_ahead(st.kids[2].kids, name, inner):
                return True
            if self.dyn_stores_ahead(st.kids[3:], name, env):
                return True  # (its else block)
            continue
        if self.dyn_stores_ahead(st.kids, name, env):
            return True
    return False


def gen_dyn_ahead(self, e: Node, env: dict[str, bool]) -> bool:
    # is e an Any value, as module code read before it runs tells (dyn_global_ahead), from the
    # types its variables have now, without compiling it: a variable of type Any or a loop target
    # that takes Any items (env), arithmetic on an Any value, an item, attribute or method result
    # of one, an item of a container of Any items, or a call of a function declared to return Any
    k = e.kind
    if k == "name":
        return env[e.s] if e.s in env else self.gtypes.get(e.s, "") == DYN
    if k == "binop" and e.s in BINOPS:
        return self.dyn_ahead(e.kids[0], env) or self.dyn_ahead(e.kids[1], env)
    if k == "unary" and e.s != "not":
        return self.dyn_ahead(e.kids[0], env)
    if k == "ifexp":
        return self.dyn_ahead(e.kids[1], env) or self.dyn_ahead(e.kids[2], env)
    if (k == "index" or k == "attr") and self.dyn_ahead(e.kids[0], env):
        return True
    if k == "index" and e.kids[0].kind == "name" and e.kids[0].s not in env:
        t = self.gtypes.get(e.kids[0].s, "")
        return t == "list[dyn]" or t == "vtuple[dyn]" or (is_dict(t) and targs(t)[1] == DYN)
    if k == "call" and e.kids[0].kind == "attr" and self.dyn_ahead(e.kids[0].kids[0], env):
        return True
    if k == "call" and e.kids[0].kind == "name" and e.kids[0].s in self.funcs and e.kids[0].s not in env and self.funcs[e.kids[0].s].ret == DYN:
        return True
    return False


def gen_dyn_items_ahead(self, it: Node, env: dict[str, bool]) -> str:
    # the type of the items of a loop over it in module code, as far as dyn_ahead can tell (DYN
    # for a loop over an Any value), or ""
    if self.dyn_ahead(it, env):
        return DYN
    if it.kind == "name" and it.s not in env:
        return self.iter_elem(self.gtypes.get(it.s, ""))
    if it.kind == "call" and len(it.kids) == 1 and it.kids[0].kind == "attr" and it.kids[0].kids[0].kind == "name" and it.kids[0].kids[0].s not in env:
        # d.items(), d.keys() and d.values() of a dict variable
        t = self.gtypes.get(it.kids[0].kids[0].s, "")
        if is_dict(t):
            m = it.kids[0].s
            return self.ctype("tuple", targs(t)) if m == "items" else targs(t)[0] if m == "keys" else targs(t)[1] if m == "values" else ""
    return ""


def gen_dyn_widened(self, name: str) -> bool:
    # is local name of the function being compiled dynamic from its first store (dyn_widen)
    return self.curfn.ll in self.dynwide and name in self.dynwide[self.curfn.ll]


def gen_dyn_none_first(self, name: str) -> None:
    # variable name, which holds None so far as T | None does (NONEVAR: a null pointer), is given
    # an Any value, or a read types it by one that its code assigns it later (none_type): the null
    # would be read as the box of None. A local is dynamic from its first store in the function's
    # next compilation (dyn_widen; also from speculative typing, as the type a read gives the
    # local stays); a module variable, or a local that cannot be, is an error
    if self.ltype.get(name, "") == NONEVAR:
        d = self.drying
        self.drying = 0
        ok = self.dyn_widen(name, NONEVAR)
        self.drying = d
        if not ok:
            self.err(f"'{short(name)}' is assigned None and then an Any value, which it cannot hold here; annotate it ({short(name)}: Any = None)")
    elif name not in self.ltype and self.gtypes.get(name, "") == NONEVAR:
        self.err(f"'{short(name)}' holds None until it is given an Any value here; annotate it{self.where_def(name)} ({short(name)}: Any = None)")


def gen_dyn_asked(self, f: FnInfo) -> int:
    # how many widenings of f's storage dyn_widen has been asked for
    return (len(self.dynwide[f.ll]) if f.ll in self.dynwide else 0) + (1 if f.ll in self.dynrets else 0)


def gen_dyn_again(self, f: FnInfo, asked: int) -> bool:
    # after a compilation of f, which started with asked widenings: compile it again, with the
    # ones asked for since? Not where another function's call took what f returns while f was
    # compiled (functions that call each other): that compilation stands, whose stores unbox their
    # Any values, and a return of one is the error it was
    if self.dyn_asked(f) == asked:
        return False
    if f.ll in self.dynseen:
        if f.ll in self.dynrets:
            self.line = self.dynrline[f.ll]
            self.err(self.dynrets[f.ll])
        return False
    # (what this compilation inferred of the values it returns, which the next one infers again)
    if f.ll in self.guessed:
        del self.guessed[f.ll]
    if f.ll in self.qused:
        del self.qused[f.ll]
    if f.ll in self.retseen:
        del self.retseen[f.ll]
    if f.ll in self.qret:
        del self.qret[f.ll]
    if f.ll in self.qholes:
        del self.qholes[f.ll]
    if f.ll in self.qforward:
        del self.qforward[f.ll]
    # (nor the joins it found for the storage that is dynamic now, which the next pass would give
    # that storage first, see join_hint: only f's own compilation joins its locals, and its result
    # where no other function took it)
    k = self.fnkey(f) + "|"
    if f.ll in self.dynwide:
        for name in self.dynwide[f.ll]:
            self.newhints.pop(k + name, "")
    if f.ll in self.dynrets:
        self.newhints.pop(k + "return", "")
    return True


# ---- operations

def gen_dyn_arith(self, op: str, a: Val, b: Val, inplace: bool = False) -> Val:
    # a op b where either is dyn: both boxed, through the class dunders of the boxed classes that
    # define them (dyn_dispatchers), then pys_dyn_binop's builtin arithmetic
    if op not in BINOPS:
        self.err(f"the operator {op} on Any values is not supported")
    pa = self.dyn_proven_int(a)
    pb = self.dyn_proven_int(b)
    if pa.t != "" and pb.t != "" and op != "**" and ((op != "&" and op != "|" and op != "^") or a.t == "int" or b.t == "int"):
        # (ints, or a bool and an int: the typed arithmetic, of an int result but for /'s float;
        # ** may give a float, and & | ^ of two bools a bool)
        return self.arith(op, pa, pb)
    x = self.dyn_box(a)
    y = self.dyn_box(b)
    f = self.dyn_dispatcher(("i" if inplace else "") + "op" + str(BINOPS[op]), [DYN, DYN], DYN, BINDUNDERS[op])
    return self.dyn_call(f, [x, y])


def gen_dyn_unary(self, op: str, v: Val) -> Val:
    p = self.dyn_proven_int(v)
    if p.t != "":
        # (an int or a bool: -x, +x and ~x are ints)
        return p if op == "+" else self.arith("-", Val("0", "int"), p) if op == "-" else self.arith("^", p, Val("-1", "int"))
    f = self.dyn_dispatcher("un" + str(UNOPS[op]), [DYN], DYN, {"-": "__neg__", "+": "__pos__", "~": "__invert__"}[op])
    return self.dyn_call(f, [v])


def gen_dyn_compare(self, op: str, a: Val, b: Val) -> Val:
    # a op b where either is dyn: ==, !=, <, <=, >, >= (is, in: dyn_identity, dyn_contains)
    pa = self.dyn_proven_int(a)
    pb = self.dyn_proven_int(b)
    if pa.t != "" and pb.t != "":
        return self.num_cmp(op, pa, pb)  # (ints, or a bool and an int: compared as ints)
    x = self.dyn_box(a)
    y = self.dyn_box(b)
    if op == "==" or op == "!=":
        r = Val(self.rt("pys_dyn_eq" if op == "==" else "pys_dyn_ne", "i64", [f"ptr {x.v}", f"ptr {y.v}"]), "int")
        return self.num_cmp("!=", r, Val("0", "int"))
    r = Val(self.rt("pys_dyn_cmp", "i64", [f"ptr {x.v}", f"ptr {y.v}", f"i64 {CMPOPS[op]}"]), "int")
    return self.num_cmp("!=", r, Val("0", "int"))


def gen_dyn_cmp2(self, op: str, a: Val, b: Val) -> Val:
    # a op b, where a or b is dyn; Val("", "") where the typed comparison does it (an item in a
    # typed container: the container's own search, which unboxes the item)
    if (op == "is" or op == "is not") and (a.t == "None" or b.t == "None"):
        x = b if a.t == "None" else a
        return self.ptr_cmp("==" if op == "is" else "!=", self.dyn_box(x), Val(self.rtdata("pys_dyn_none_box"), DYN))
    if op == "is" or op == "is not":
        return self.dyn_identity(op, a, b)
    if op == "in" or op == "not in":
        if b.t != DYN:
            return Val("", "")
        r = self.dyn_contains(b, a)
        return r if op == "in" else Val(self.scalar("xor", [r, Val("true", "bool")]), "bool")
    return self.dyn_compare(op, a, b)


def gen_dyn_identity(self, op: str, a: Val, b: Val) -> Val:
    # a is b (op "is") or a is not b, where either is dyn: the same box, or the same type and
    # payload but for floats and bound methods (whose box is their identity, as a float object's
    # and a method object's is CPython's: DF_BOXID)
    x = self.dyn_box(a)
    y = self.dyn_box(b)
    ta = Val(self.dyn_typeof(x), "dyntype")
    same = self.ptr_cmp("==", x, y).v
    st = self.ptr_cmp("==", ta, Val(self.dyn_typeof(y), "dyntype")).v
    sp = self.num_cmp("==", Val(self.to_slot(self.dyn_payload(x, "int")), "int"), Val(self.to_slot(self.dyn_payload(y, "int")), "int")).v
    nf = self.ptr_cmp("!=", ta, Val(self.rtdata("pys_dyntype_float"), "dyntype")).v
    fl = self.mload("int", self.maddr("int", ta.v, "5"))  # (its DynType's flags)
    nb = self.num_cmp("==", Val(self.scalar("and", [Val(fl, "int"), Val(str(DF_BOXID), "int")]), "int"), Val("0", "int")).v
    nf = self.scalar("and", [Val(nf, "bool"), Val(nb, "bool")])
    alike = self.scalar("and", [Val(st, "bool"), Val(self.scalar("and", [Val(sp, "bool"), Val(nf, "bool")]), "bool")])
    r = self.scalar("or", [Val(same, "bool"), Val(alike, "bool")])
    return Val(r if op == "is" else self.scalar("xor", [Val(r, "bool"), Val("true", "bool")]), "bool")


def gen_dyn_truth(self, v: Val) -> str:
    p = self.dyn_proven_int(v)
    if p.t != "":
        return self.num_cmp("!=", p, Val("0", "int")).v
    f = self.dyn_dispatcher("truth", [DYN], "bool", "__bool__")
    return self.dyn_call(f, [v]).v


def gen_dyn_str(self, v: Val) -> Val:
    f = self.dyn_dispatcher("str", [DYN], "str", "__str__")
    return self.dyn_call(f, [v])


def gen_dyn_repr(self, v: Val) -> Val:
    return Val(self.rt("pys_dyn_repr", "ptr", [f"ptr {v.v}"]), "str")


def gen_dyn_len(self, v: Val) -> Val:
    f = self.dyn_dispatcher("len", [DYN], "int", "__len__")
    return self.dyn_call(f, [v])


def gen_dyn_format(self, v: Val, spec: Val) -> Val:
    # format(v, spec) for a dyn v: its class's __format__, else what CPython's object.__format__ and
    # the builtin types' do (dyn_fallback)
    f = self.dyn_dispatcher("format", [DYN, "str"], "str", "__format__")
    return self.dyn_call(f, [v, spec])


def gen_dyn_hash(self, v: Val) -> Val:
    return Val(self.rt("pys_dyn_hash", "i64", [f"ptr {v.v}"]), "int")


def gen_dyn_getitem(self, o: Val, k: Val) -> Val:
    f = self.dyn_dispatcher("getitem", [DYN, DYN], DYN, "__getitem__")
    return self.dyn_call(f, [self.dyn_box(o), self.dyn_box(k)])


def gen_dyn_setitem(self, o: Val, k: Val, v: Val) -> None:
    f = self.dyn_dispatcher("setitem", [DYN, DYN, DYN], "None", "__setitem__")
    self.dyn_call(f, [self.dyn_box(o), self.dyn_box(k), self.dyn_box(v)])


def gen_dyn_delitem(self, o: Val, k: Val) -> None:
    f = self.dyn_dispatcher("delitem", [DYN, DYN], "None", "__delitem__")
    self.dyn_call(f, [self.dyn_box(o), self.dyn_box(k)])


def gen_dyn_contains(self, o: Val, k: Val) -> Val:
    # k in o, for a dyn o
    f = self.dyn_dispatcher("contains", [DYN, DYN], "bool", "__contains__")
    return self.dyn_call(f, [self.dyn_box(o), self.dyn_box(k)])


def gen_dyn_int(self, v: Val) -> Val:
    return Val(self.rt("pys_dyn_int_of", "i64", [f"ptr {v.v}"]), "int")


def gen_dyn_float(self, v: Val) -> Val:
    return Val(self.rt("pys_dyn_float_of", "double", [f"ptr {v.v}"]), "float")


def gen_dyn_type_module(self, v: Val) -> Val:
    # type(v).__module__: its class's module (module), "builtins" for the builtin types'
    return self.dyn_call(self.dyn_dispatcher("module", [DYN], "str", "__module__"), [v])


def gen_dyn_bound(self, v: Val, bound: bool) -> str:
    # a typed sequence's slice's bound (or, not bound, its step) that is an Any value (slice_dyn):
    # an int's or a bool's value, None as an omitted one, else CPython's TypeError; a given bound of
    # -2**63 is -2**63 + 1, as slice_bound clamps it (runtime.c's dbound for an Any value's slice)
    none = self.dyn_test(v, ["None"])
    ok = self.scalar("or", [Val(none, "bool"), Val(self.dyn_test(v, ["int", "bool"]), "bool")])
    self.guard(self.scalar("xor", [Val(ok, "bool"), Val("true", "bool")]), "TypeError: slice indices must be integers or None or have an __index__ method")
    x = Val(self.to_slot(self.dyn_payload(v, "int")), "int")
    if bound:
        x = Val(self.select(self.num_cmp("==", x, Val("-9223372036854775808", "int")).v, Val("-9223372036854775807", "int"), x), "int")
    return self.select(none, Val("-9223372036854775808" if bound else "1", "int"), x)


def gen_dyn_slice(self, o: Val, bs: list[Node]) -> Val:
    # o[lo:hi:st] for a dyn o, bs its bounds and step (omit nodes where omitted, no step where no
    # second colon): their values, evaluated in turn, as Any values (None where omitted), which
    # runtime.c's pys_dyn_slice converts once it has tested o, as CPython's sequences do (an
    # object's __getitem__ would take a slice object, which Pystachy does not have)
    vs = [o]
    for i in range(3):
        vs.append(self.expr(bs[i], "") if i < len(bs) and bs[i].kind != "omit" else Val("null", "None"))
    f = self.dyn_dispatcher("slice", [DYN, DYN, DYN, DYN], DYN, "__getitem__")
    return self.dyn_call(f, vs)


def gen_dyn_type_name(self, v: Val) -> Val:
    # type(v).__name__: its DynType's name
    t = self.dyn_typeof(v)
    return Val(self.mload("%ptr", self.maddr("%ptr", t, "2", True)), "str")


# ---- the dispatchers: functions of the program that the compiler writes once every class that
# is boxed is known (program's last passes compile them again while more classes get boxed)

def gen_dyn_dispatcher(self, key: str, ptypes: list[str], ret: str, dunder: str) -> FnInfo:
    # @dyn.<key>: a function of parameters ptypes (the receiver first) and result ret, whose body
    # dyn_body writes: for each boxed class whose objects have dunder (or the attribute it names),
    # a test of the receiver's DynType and the class's own operation, then the builtin types'
    if key in self.dynfns:
        return self.dynfns[key]
    f = FnInfo("dyn." + key, "@dyn." + key, mk("block", "", self.line, []), "")
    f.params = ["o"] + [f"a{j}" for j in range(1, len(ptypes))]
    f.ptypes = ptypes
    f.ret = ret
    f.synthetic = True
    self.dynfns[key] = f
    self.dynkeys[key] = dunder
    self.dynlines[key] = self.line
    return f


def gen_dyn_call(self, f: FnInfo, args: list[Val]) -> Val:
    # a call of dispatcher f, which program compiles at the end: no argument coercion but boxing
    self.called[f.ll] = True
    c = Ins("call", f.ret, f.ll)
    c.a = [self.dyn_box(args[j]) if f.ptypes[j] == DYN else args[j] for j in range(len(args))]
    if f.ret == "None":
        self.add(c)
        return Val("null", "None")
    self.put(c, 1)
    return Val(f"%t{c.r[0]}", f.ret)


def gen_dyn_body(self, key: str) -> None:
    # the body of dispatcher @dyn.<key> (see dyn_dispatcher), whose parameters are o, a1, ...:
    # the cases of the boxed classes that support the operation, those of the builtin types where
    # the program's code does the work (a method call), and then runtime.c's helper
    f = self.dynfns[key]
    line = self.line
    ps = [self.read(mk("name", p, line, [])) for p in f.params]
    o = ps[0]
    dunder = self.dynkeys[key]
    t = Val(self.dyn_typeof(o), "dyntype")
    arith = (key.startswith("op") or key.startswith("iop")) and dunder != ""
    r = "__r" + dunder[2:] if arith else ""
    # the case of the receiver's class, by one switch on its DynType's class id (word 3: a class's
    # dense O<id>, which its DynType holds, or -1 for a builtin or function DynType, which takes
    # the rest), which LLVM can make a jump table, rather than a comparison with each class's
    # DynType in turn (#799). A subclass has a DynType of its own, so its case is exact too
    arms = [x for x in self.dynclasses if self.dyn_supports(x, key, dunder, len(ps) - 1)]
    labels = [self.label() for x in arms]
    rest = self.label()
    if len(arms) > 0:
        cid = Val(self.mload("int", self.maddr("int", t.v, "3")), "int")
        self.switch(cid, [str(self.ocls[x]) for x in arms], labels, rest)
    for j in range(len(arms)):
        c = arms[j]
        hit = labels[j]
        self.place(hit)
        if arith and not (key.startswith("iop") and ("__i" + dunder[2:]) in self.classes[c].methods):
            # (CPython's binary_op1 runs first the reflected method of a right operand of a strict
            # subclass, where it is that subclass's own and not c's)
            cm = self.classes[c].methods
            for s in [x for x in self.dynclasses if x != c and self.derives(x, c) and r in self.classes[x].methods and (r not in cm or self.classes[x].methods[r] is not cm[r])]:
                self.dyn_reflected(f, s, r, o, ps[1], "true")
        self.dyn_arm(f, key, dunder, self.dyn_payload(o, c), ps[1:])
        if not self.term:
            self.br(rest)
    self.place(rest)
    if arith:
        # the reflected operation of the right operand's class (b.__radd__(a)), where a's has
        # none and is of another type (not of the same class, nor str for %, which formats b)
        for c in [x for x in self.dynclasses]:
            if r not in self.classes[c].methods:
                continue
            ok = "true"
            for s in [x for x in self.dynclasses if x == c or (self.tmpl_of(c) != "" and self.tmpl_of(x) == self.tmpl_of(c))]:
                ok = self.scalar("and", [Val(ok, "bool"), self.ptr_cmp("!=", t, Val(self.dyntypes[s], "dyntype"))])
            if dunder == "__mod__":
                ok = self.scalar("and", [Val(ok, "bool"), self.ptr_cmp("!=", t, Val(self.dyn_type("str"), "dyntype"))])
            self.dyn_reflected(f, c, r, o, ps[1], ok)
    if key.startswith("call.") or key.startswith("has."):
        self.dyn_builtin_methods(f, key, o, ps[1:])
    if key.startswith("callv."):
        self.dyn_fn_arms(f, key, o, ps[1:])
    self.dyn_fallback(f, key, ps)


def gen_dyn_reflected(self, f: FnInfo, c: str, r: str, a: Val, b: Val, ok: str) -> None:
    # dispatcher f's case for a right operand b of class c, where ok holds too: b.r(a), the
    # reflected method r of b's class
    hit = self.label()
    nxt = self.label()
    tb = self.ptr_cmp("==", Val(self.dyn_typeof(b), "dyntype"), Val(self.dyntypes[c], "dyntype"))
    self.cbr(tb.v if ok == "true" else self.scalar("and", [tb, Val(ok, "bool")]), hit, nxt)
    self.place(hit)
    x = self.dyn_payload(b, c)
    self.dyn_return(f, self.expr(mk("call", "", self.line, [mk("attr", r, self.line, [self.vnode(x)]), self.vnode(a)]), ""))
    self.place(nxt)


def gen_dyn_fn_arms(self, f: FnInfo, key: str, o: Val, args: list[Val]) -> None:
    # the cases of dispatcher callv.<n> for the function values boxed: each called as its own
    # type calls it (defaults, a closure's env, a bound method's object), or the TypeError of a
    # call with the wrong number of arguments
    t = Val(self.dyn_typeof(o), "dyntype")
    for ft in [x for x in self.dynfuncs]:
        hit = self.label()
        nxt = self.label()
        self.cbr(self.ptr_cmp("==", t, Val(self.dynfnt[ft], "dyntype")).v, hit, nxt)
        self.place(hit)
        bad = self.dyn_fn_takes(ft, len(args))
        if bad != "":
            i = bad.find(": ")
            self.raise_(bad[:i], self.sconst(bad[i + 2 :]))
        else:
            x = Val("null", ft) if ft.startswith("fn[f:") else self.dyn_payload(o, ft)
            self.dyn_return(f, self.obj_call(x, [self.vnode(a) for a in args], ""))
        self.place(nxt)


def gen_dyn_supports(self, c: str, key: str, dunder: str, nargs: int) -> bool:
    # does class c have a case in dispatcher key: it defines the dunder (or the attribute, or the
    # method, whatever the arguments: a call that does not fit raises its TypeError) the
    # operation runs
    ci = self.classes[c]
    if key.startswith("get."):
        a = key[4:]
        return a in ci.ftypes or (a in ci.methods and (ci.methods[a].prop or (ci.methods[a].deco == "" and ci.methods[a].bad == "")))  # (a method's: the bound method)
    if key.startswith("set."):
        a = key[4:]
        return a in ci.ftypes or (a in ci.methods and ci.methods[a].prop)  # (a property's setter, or CPython's error without one)
    if key.startswith("call.") or key.startswith("has."):
        m = key[key.find(".") + 1 : key.rfind(".")]
        if m in ci.ftypes and m not in ci.methods:
            return True  # (a field, whose value the call calls as a function value: dyn_arm)
        if m not in ci.methods or ci.methods[m].prop:
            return False
        return ci.methods[m].bad == "" and len(ci.methods[m].defaults) >= len(ci.methods[m].params)  # (has.: CPython's lookup finds it)
    if key.startswith("callv."):
        return "__call__" in ci.methods and ci.methods["__call__"].bad == ""
    if key == "module":
        return True
    if key == "truth":
        return "__bool__" in ci.methods or "__len__" in ci.methods
    if key == "str":
        return "__str__" in ci.methods or "__repr__" in ci.methods
    if key.startswith("iop"):
        return ("__i" + dunder[2:]) in ci.methods or dunder in ci.methods
    return dunder in ci.methods


def gen_dyn_takes(self, fm: FnInfo, own: int, nargs: int) -> bool:
    # can function fm be called with own values (its object) and nargs positional arguments, as
    # arity finds them: no case calls a method with arguments it would reject when compiled
    if fm.bad != "" or len(fm.defaults) < len(fm.params):
        return False
    np = len(fm.params)
    last = fm.vararg if fm.vararg >= 0 else fm.npos if fm.npos >= 0 else np
    last = min(last, fm.kwarg) if fm.kwarg >= 0 else last
    required = len([j for j in range(last) if fm.defaults[j].kind == "noann"])
    kwreq = [j for j in range(last, np) if j != fm.vararg and j != fm.kwarg and fm.defaults[j].kind == "noann"]
    given = own + nargs
    return len(kwreq) == 0 and given >= required and (fm.vararg >= 0 or given <= last)


def gen_dyn_arity(self, fm: FnInfo, own: int, nargs: int) -> str:
    # CPython's TypeError message for a call of fm with own values (its object) and nargs
    # positional arguments that dyn_takes rejects, as arity words it for a typed call: too many
    # positional arguments, else the missing positional, then keyword-only, parameters
    np = len(fm.params)
    last = fm.vararg if fm.vararg >= 0 else fm.npos if fm.npos >= 0 else np
    last = min(last, fm.kwarg) if fm.kwarg >= 0 else last
    given = own + nargs
    off = 1 if fm.deco == "classmethod" else 0  # (cls, which CPython counts and fm.params leaves out)
    if fm.vararg < 0 and given > last:
        dflt = len([j for j in range(last) if fm.defaults[j].kind != "noann"])
        takes = f"from {last + off - dflt} to {last + off}" if dflt > 0 else str(last + off)
        plural = "s" if dflt > 0 or last + off != 1 else ""
        return f"{self.fname(fm)}() takes {takes} positional argument{plural} but {given + off} {'was' if given + off == 1 else 'were'} given"
    for kind in ["positional", "keyword-only"]:
        miss = [fm.params[j] for j in range(np) if ((given <= j and j < last) if kind == "positional" else j >= last) and j != fm.vararg and j != fm.kwarg and fm.defaults[j].kind == "noann"]
        if len(miss) > 0:
            names = "'" + "', '".join(miss) + "'"
            if len(miss) == 2:
                names = f"'{miss[0]}' and '{miss[1]}'"
            elif len(miss) > 2:
                names = "'" + "', '".join(miss[:-1]) + f"', and '{miss[-1]}'"
            return f"{self.fname(fm)}() missing {len(miss)} required {kind} argument{'s' if len(miss) != 1 else ''}: {names}"
    return f"{self.fname(fm)}() cannot take {nargs} positional argument{'s' if nargs != 1 else ''}"


def gen_dyn_arm(self, f: FnInfo, key: str, dunder: str, x: Val, args: list[Val]) -> None:
    # class x.t's case of dispatcher key: its own operation on the object x, then return
    line = self.line
    xn = self.vnode(x)
    an = [self.vnode(a) for a in args]
    if key.startswith("get."):
        r = self.expr(mk("attr", key[4:], line, [xn]), "")
    elif key.startswith("set."):
        self.assign(mk("attr", key[4:], line, [xn]), args[0])
        r = Val("null", "None")
    elif key.startswith("has.") and key[4 : key.rfind(".")] not in self.classes[x.t].methods and self.dyn_boxable(self.rec_type(self.classes[x.t].ftypes[key[4 : key.rfind(".")]])) == "":
        r = self.dyn_box(self.expr(mk("attr", key[4 : key.rfind(".")], line, [xn]), ""))  # (a field's value, which the call calls)
    elif key.startswith("has."):
        r = Val("null", DYN)  # (a method, which call.<m>.<n> calls, or a field no box holds, whose call raises there)
    elif key.startswith("call.") and key[5 : key.rfind(".")] not in self.classes[x.t].methods:
        # a field's value, called as a function value is (callv.<n>), or CPython's TypeError for
        # one that no box holds, which is not callable either
        v = self.expr(mk("attr", key[5 : key.rfind(".")], line, [xn]), "")
        if self.dyn_boxable(self.rec_type(v.t)) != "":
            self.raise_("TypeError", self.sconst(f"'{tname(self.rec_type(v.t))}' object is not callable"))
            return
        r = self.dyn_call(self.dyn_dispatcher(f"callv.{len(args)}", [DYN] * (len(args) + 1), DYN, "__call__"), [v] + args)
    elif key.startswith("call."):
        fm = self.classes[x.t].methods[key[5 : key.rfind(".")]]
        own = 0 if fm.deco != "" else 1
        if not self.dyn_takes(fm, own, len(args)):
            # (arguments that do not fit its parameters: CPython's TypeError, once they are evaluated)
            self.raise_("TypeError", self.sconst(self.dyn_arity(fm, own, len(args))))
            return
        r = self.expr(mk("call", "", line, [mk("attr", key[5 : key.rfind(".")], line, [xn])] + an), "")
    elif key == "module":
        r = Val(self.sconst(self.refl_type_name(x.t, "__module__")), "str")
    elif key == "slice":
        self.raise_("TypeError", self.sconst(f"slicing an object is not supported: {short(x.t)}.__getitem__ would take a slice object, which Pystachy does not have"))
        return
    elif key.startswith("callv.") and not self.dyn_takes(self.classes[x.t].methods["__call__"], 1, len(args)):
        # (arguments that do not fit __call__'s parameters: CPython's TypeError)
        self.raise_("TypeError", self.sconst(self.dyn_arity(self.classes[x.t].methods["__call__"], 1, len(args))))
        return
    elif key == "truth":
        r = Val(self.truth(x), "bool")
    elif key == "str":
        r = self.to_str(x)
    elif key == "len":
        r = self.objlen(x)
    elif key.startswith("iop") and ("__i" + dunder[2:]) in self.classes[x.t].methods:
        r = self.expr(mk("call", "", line, [mk("attr", "__i" + dunder[2:], line, [xn])] + an), "")
    elif key == "contains":
        r = self.coerce(self.expr(mk("call", "", line, [mk("attr", dunder, line, [xn])] + an), ""), "bool")
    else:
        r = self.expr(mk("call", "", line, [mk("attr", dunder, line, [xn])] + an), "")
    self.dyn_return(f, r)


def gen_dyn_return(self, f: FnInfo, r: Val) -> None:
    # return r from dispatcher f: boxed where it returns dyn (a fresh typed container a builtin
    # method makes is made one of boxes)
    if self.term:
        return
    if f.ret == "None":
        self.ret_(Val("null", "None"))
        return
    if f.ret == DYN and self.dyn_boxable(self.rec_type(r.t)) != "":
        self.err(self.dyn_boxable(r.t))
    self.ret_(self.dyn_box(r) if f.ret == DYN else self.coerce(r, f.ret))


def gen_dyn_builtin_methods(self, f: FnInfo, key: str, o: Val, args: list[Val]) -> None:
    # the cases of a method call's dispatcher (call.<m>.<n>, and has.<m>.<n>, which only finds it)
    # for the builtin types that box: list[Any] and dict[Any, Any]'s methods, which keep their
    # boxes, and str's, tuple's and the numbers', whose arguments unbox (dyn_unbox) and whose fresh
    # results box (a bool's are int's, of its payload, 0 or 1)
    m = key[key.find(".") + 1 : key.rfind(".")]
    n = int(key[key.rfind(".") + 1 :])
    t = Val(self.dyn_typeof(o), "dyntype")
    line = self.line
    for bt in ["list[dyn]", "dict[dyn,dyn]", "str", "vtuple[dyn]", "int", "bool", "float"]:
        if not self.dyn_builtin_takes(bt, m, n):
            continue
        hit = self.label()
        nxt = self.label()
        self.cbr(self.ptr_cmp("==", t, Val(self.dyn_type(bt), "dyntype")).v, hit, nxt)
        self.place(hit)
        if key.startswith("has."):
            self.ret_(Val("null", DYN))  # (a method, which call.<m>.<n> calls)
        else:
            x = self.dyn_payload(o, "int" if bt == "bool" else bt)
            r = self.expr(mk("call", "", line, [mk("attr", m, line, [self.vnode(x)])] + [self.vnode(a) for a in args]), "")
            self.dyn_return(f, self.dyn_fresh(r))
        self.place(nxt)


def gen_dyn_builtin_takes(self, bt: str, m: str, n: int) -> bool:
    # does builtin type bt (one a box holds) have method m, called with n positional arguments
    base = "list" if is_list(bt) else "dict" if is_dict(bt) else "vtuple" if is_vtuple(bt) else "int" if bt == "bool" else bt
    special = {"list.sort": "0 0", "dict.update": "1 1", "dict.pop": "1 2", "dict.setdefault": "2 2", "str.join": "1 1"}
    k = base + "." + m
    if k in special:
        lo = int(special[k].split(" ")[0])
        return lo <= n and n <= int(special[k].split(" ")[1])
    if k not in METHODS:
        return False
    e = METHODS[k]
    ps = [p for p in e[e.find(":") + 1 :].split(",") if p != "" and p != "#"]
    return len([p for p in ps if "=" not in p]) <= n and n <= len(ps)


def gen_dyn_fresh(self, v: Val) -> Val:
    # v, which a builtin method made just now, as a value a box can hold: a list of typed items a
    # list of their boxes (nothing else refers to it yet: pys_dyn_list_of), anything else as it is
    t = self.rec_type(v.t)
    if not is_list(t) or elem(t) == DYN:
        return v
    d = self.desc(elem(t), "repr")
    return Val(self.rt("pys_dyn_list_of", "ptr", [f"ptr {v.v}", f"ptr {self.sconst(d)}"]), "list[dyn]")


def gen_dyn_fallback(self, f: FnInfo, key: str, ps: list[Val]) -> None:
    # what dispatcher key does for the builtin types: runtime.c's helper, or an AttributeError
    if self.term:
        return
    o = ps[0]
    if key.startswith("op") or key.startswith("iop"):
        n = key[2:] if key.startswith("op") else key[3:]
        fn = "pys_dyn_binop" if key.startswith("op") else "pys_dyn_inplace"
        self.ret_(Val(self.rt(fn, "ptr", [f"ptr {o.v}", f"ptr {ps[1].v}", f"i64 {n}"]), DYN))
    elif key.startswith("un"):
        self.ret_(Val(self.rt("pys_dyn_unary", "ptr", [f"ptr {o.v}", f"i64 {key[2:]}"]), DYN))
    elif key == "truth":
        self.ret_(self.num_cmp("!=", Val(self.rt("pys_dyn_truth", "i64", [f"ptr {o.v}"]), "int"), Val("0", "int")))
    elif key == "str":
        self.ret_(Val(self.rt("pys_dyn_str", "ptr", [f"ptr {o.v}"]), "str"))
    elif key == "len":
        self.ret_(Val(self.rt("pys_dyn_len", "i64", [f"ptr {o.v}"]), "int"))
    elif key == "module":
        self.ret_(Val(self.sconst("builtins"), "str"))
    elif key == "slice":
        self.ret_(Val(self.rt("pys_dyn_slice", "ptr", [f"ptr {o.v}", f"ptr {ps[1].v}", f"ptr {ps[2].v}", f"ptr {ps[3].v}"]), DYN))
    elif key == "format":
        # str() for an empty spec, as object.__format__ and the builtin types' give; else a number's
        # or a str's own formatting, or the TypeError that names the value's type
        empty = self.label()
        some = self.label()
        self.cbr(self.num_cmp("==", Val(self.mload("int", ps[1].v), "int"), Val("0", "int")).v, empty, some)
        self.place(empty)
        self.ret_(self.dyn_str(o))
        self.place(some)
        self.ret_(Val(self.rt("pys_format", "ptr", ["i64 " + self.to_slot(o), f"ptr {self.sconst('A')}", f"ptr {ps[1].v}"]), "str"))
    elif key == "getitem":
        self.ret_(Val(self.rt("pys_dyn_getitem", "ptr", [f"ptr {o.v}", f"ptr {ps[1].v}"]), DYN))
    elif key == "setitem":
        self.rt("pys_dyn_setitem", "void", [f"ptr {o.v}", f"ptr {ps[1].v}", f"ptr {ps[2].v}"])
        self.ret_(Val("null", "None"))
    elif key == "delitem":
        self.rt("pys_dyn_delitem", "void", [f"ptr {o.v}", f"ptr {ps[1].v}"])
        self.ret_(Val("null", "None"))
    elif key == "contains":
        self.ret_(self.num_cmp("!=", Val(self.rt("pys_dyn_contains", "i64", [f"ptr {o.v}", f"ptr {ps[1].v}"]), "int"), Val("0", "int")))
    elif key.startswith("callv."):
        msg = self.concat([Val(self.sconst("'"), "str"), self.dyn_type_name(o), Val(self.sconst("' object is not callable"), "str")])
        self.raise_("TypeError", msg.v)
    else:
        # an attribute or method no boxed value of this type has: AttributeError, naming its type
        a = key[4:] if key.startswith("get.") or key.startswith("set.") else key[key.find(".") + 1 : key.rfind(".")]
        msg = self.concat([Val(self.sconst("'"), "str"), self.dyn_type_name(o), Val(self.sconst(f"' object has no attribute '{a}'"), "str")])
        self.raise_("AttributeError", msg.v)


def gen_dyn_dispatchers(self) -> bool:
    # compile the dispatchers (again) for the classes and function values boxed so far, if any
    # or a new dispatcher appeared since the last time: True if so. Compiling them may box more
    # classes and function values (get.<a> a bound method), and need more dispatchers, so that
    # program calls this until it is False
    sig = f"{len(self.dynclasses)} {len(self.dynfns)} {len(self.dynfuncs)}"
    if sig == self.dynsig:
        return False
    self.dynsig = sig
    for key in [k for k in self.dynfns]:
        f = self.dynfns[key]
        if f.ll in self.compiled:
            self.fns = [fn for fn in self.fns if fn.f.ll != f.ll]
            del self.compiled[f.ll]
        self.function(f, [mk("dynbody", key, self.dynlines[key], [])])
    return True


def gen_dyn_builtin(self, name: str, v: Val) -> Val:
    # builtin name (len, str, repr, int, float, bool) of the dyn value v
    if name == "len":
        return self.dyn_len(v)
    if name == "str":
        return self.dyn_str(v)
    if name == "repr":
        return self.dyn_repr(v)
    if name == "int":
        return self.dyn_int(v)
    if name == "float":
        return self.dyn_float(v)
    if name == "id":
        return Val(self.rt("pys_dyn_id", "i64", [f"ptr {v.v}"]), "int")
    return Val(self.dyn_truth(v), "bool")


def gen_dyn_getattr(self, o: Val, a: str) -> Val:
    # o.a for a dyn o: its class's attribute, boxed
    return self.dyn_call(self.dyn_dispatcher("get." + a, [DYN], DYN, a), [o])


def gen_dyn_setattr(self, o: Val, a: str, v: Val) -> None:
    # o.a = v for a dyn o: a field of its class, which takes v as its type does
    self.dyn_call(self.dyn_dispatcher("set." + a, [DYN, DYN], "None", a), [o, self.dyn_box(v)])


def gen_dyn_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # o.m(args) for a dyn o: the method of its class (or of its builtin type) that m names, found
    # before the arguments are evaluated, as CPython's LOAD_ATTR finds it, then called with them
    # boxed (positional arguments only)
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            self.err(f"a method call of an Any value takes positional arguments only (o.{m}(...))")
    # (no lookup first where no argument can run code or raise: literals, and locals that flow
    # analysis found assigned, whose reads have no check)
    call = self.dyn_dispatcher(f"call.{m}.{len(args)}", [DYN] * (len(args) + 1), DYN, m)
    if len([a for a in args if a.kind not in ["int", "float", "str", "True", "False", "None"] and not (a.kind == "name" and a.s in self.ltype and not a.chk)]) == 0:
        vals = [self.dyn_box(self.expr(a, DYN)) for a in args]
        return self.dyn_call(call, [o] + vals)
    # the lookup gives null for a method, which call.<m>.<n> then calls, or a field's value, read
    # now as LOAD_ATTR reads it, which callv.<n> calls although an argument assigns the field anew
    h = self.dyn_call(self.dyn_dispatcher(f"has.{m}.{len(args)}", [DYN], DYN, m), [o])
    vals = [self.dyn_box(self.expr(a, DYN)) for a in args]
    fld = self.label()
    meth = self.label()
    end = self.label()
    ph = Ins("phi", DYN, "")
    self.cbr(self.ptr_cmp("==", h, Val("null", "None")).v, meth, fld)
    self.place(fld)
    r = self.dyn_call(self.dyn_dispatcher(f"callv.{len(args)}", [DYN] * (len(args) + 1), DYN, "__call__"), [h] + vals)
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(meth)
    r = self.dyn_call(call, [o] + vals)
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), DYN)


def gen_dyn_mixed(self, es: list[Node]) -> bool:
    # do the items es of a display (in a module that compiles Any so) have no one type, so that
    # it is a container of dynamic values, and the displays among the items are made so too: the
    # types of those that are not empty displays, which a dry run gives
    ts: list[str] = []
    for e in es:
        if self.dyn_untyped_empty(e):
            continue  # (its type comes of the items before it, #782; a dry run alone would reject it)
        if e.kind == "starred" or e.kind == "dstar":
            return False
        ts.append(self.dyn_dry(e))
    if len(ts) < 2:
        return DYN in ts
    if self.dyn_callables(ts):
        return False
    j = ts[0]
    for t in ts[1:]:
        j = self.join(j, t) if j != "" else ""
    return j == "" or j == DYN


def gen_dyn_callables(self, ts: list[str]) -> bool:
    # are ts, the types of a display's items, a Callable's and functions' after it: Callables of
    # its type, as the display compiles them in modules that do not opt in, rather than Any
    # values, which no builtin function is yet (#782)
    return len(ts) > 0 and is_callable(unopt(ts[0])) and len([t for t in ts[1:] if t != ts[0] and not is_fn(t)]) == 0


def gen_dyn_untyped_empty(self, e: Node) -> bool:
    # does e hold an empty list or dict display that nothing in e types, which only the display
    # around e can (a dry run of e alone would reject it): one on its own or in a tuple display,
    # whose items each have their own type, or one in a display that no item before it types
    # (dyn_untyped_items); list(), dict() and set() are such displays too. An item that holds one
    # that its own items type, ([1], []), decides with the others whether a display's items have
    # one type (#782)
    if e.kind == "tuple":
        return len([k for k in e.kids if self.dyn_untyped_empty(k)]) > 0
    if e.kind == "call":
        return len(e.kids) == 1 and self.empty_ctor(e) != ""
    if e.kind != "list" and e.kind != "dict" and e.kind != "set":
        return False
    if len(e.kids) == 0:
        return True
    if e.kind == "dict":
        return self.dyn_untyped_items([e.kids[i] for i in range(0, len(e.kids), 2)]) or self.dyn_untyped_items([e.kids[i] for i in range(1, len(e.kids), 2)])
    return self.dyn_untyped_items(e.kids)


def gen_empty_ctor(self, e: Node) -> str:
    # "list", "dict" or "set" where call e is list(), dict() or set() of the builtin, else ""
    f = e.kids[0]
    return f.s if len(e.kids) == 1 and f.kind == "name" and f.s in ["list", "dict", "set"] and not self.bound(f.s) else ""


def gen_dyn_untyped_items(self, ks: list[Node]) -> bool:
    # do the items ks of a display (a dict's keys, or its values) hold an empty display that no
    # item before it types: typed code types an empty item by the items before it, so where one of
    # them is a container of the same kind that holds none ([[1], []], [list([1]), []], not
    # [1.5, []]): a display by its kind, another expression by the type a dry run gives it (dyn_dry
    # remembers it, and compiling the display compiles the item anyway)
    typed: dict[str, bool] = {}  # (the kinds of the containers before the item that hold none)
    for k in ks:
        if self.dyn_untyped_empty(k):
            if (self.empty_ctor(k) if k.kind == "call" else k.kind) not in typed:
                return True
        elif k.kind == "list" or k.kind == "dict" or k.kind == "set" or k.kind == "tuple":
            typed[k.kind] = True
        elif k.kind != "starred" and k.kind != "dstar":
            t = unopt(self.dyn_dry(k))
            typed["list" if is_list(t) else "dict" if is_dict(t) else "set" if is_set(t) else "tuple" if is_tuple(t) or is_vtuple(t) else ""] = True
    return False


def gen_dyn_dry(self, e: Node) -> str:
    # dry(e) of an item of a display that dyn_mixed decides, remembered for the statement being
    # compiled (gen_stmt forgets them): compiling the display compiles its items again, and each
    # item that holds a display decides it again, so that without this the work doubled with each
    # level of nesting (#781). A literal or a name costs no more to compile again
    if e.kind in ["int", "float", "str", "bytes", "True", "False", "None", "name"]:
        return self.dry(e, "")
    j = e.memo - 1
    if j >= 0 and j < len(self.dmemo) and self.dmemo[j] is e:
        return self.dmemot[j]
    t = self.dry(e, "")
    e.memo = len(self.dmemo) + 1
    self.dmemo.append(e)
    self.dmemot.append(t)
    return t



def gen_dyn_fn_type(self, ft: str) -> str:
    # @dtf.<n>: the DynType of the boxes of function values of type ft (a def's, a closure's, a
    # bound method's, a Callable's), made once: DK_FUNC, descriptor Z (runtime.c prints such a
    # value as <function>, and compares and hashes it by identity), the name of its type. Each is
    # a case of the dispatchers that call boxes (callv.<n>)
    if ft in self.dynfnt:
        return self.dynfnt[ft]
    name = f"@dtf.{len(self.dynfnt)}"
    self.dynfnt[ft] = name
    self.dynfuncs.append(ft)
    dt = Data("dyntype", name)
    tn = "method" if ft.startswith("fn[m:") else "function"
    dt.refs = [self.sconst("Z"), self.sconst(tn), "null"]
    # (a bound method's box is its identity, as each evaluation of o.m makes a new method object)
    dt.items = [Val(str(DK_FUNC), "int"), Val("-1", "int"), Val(str(DF_BOXID) if ft.startswith("fn[m:") else "0", "int")]
    self.consts.append(dt)
    return name


def gen_dyn_fn_box(self, v: Val) -> Val:
    # function value v boxed: a def of a module's top level has no value (null), so that its box
    # is a constant of its own, whose payload, the address of its DynType, tells it apart from
    # other functions; a closure's box holds its env, a bound method's its object, a Callable's
    # its {code, env} object
    t = self.dyn_fn_type(v.t)
    if v.t.startswith("fn[f:"):
        g = "@dbx." + t[5:]
        if g not in self.dynboxes:
            self.dynboxes[g] = True
            d = Data("dynbox", g)
            d.refs = [t]
            self.consts.append(d)
        return Val(g, DYN)
    return Val(self.rt("pys_dyn_ref", "ptr", [f"ptr {t}", f"ptr {v.v}"]), DYN)


def gen_dyn_call_value(self, o: Val, args: list[Node]) -> Val:
    # o(args) for a dyn o: the function its box holds, called with the arguments boxed (positional
    # only), once they are evaluated, as CPython calls the value (callv.<n>)
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            self.err("a call of an Any value takes positional arguments only")
    vals = [self.dyn_box(self.expr(a, DYN)) for a in args]
    return self.dyn_call(self.dyn_dispatcher(f"callv.{len(args)}", [DYN] * (len(args) + 1), DYN, "__call__"), [o] + vals)


def gen_dyn_fn_takes(self, ft: str, n: int) -> str:
    # "" if a function value of type ft takes n positional arguments, else CPython's TypeError
    if is_callable(ft):
        k = len(targs(ft)) - 1
        return "" if k == n else f"TypeError: the function takes {k} positional argument{'s' if k != 1 else ''} but {n} {'were' if n != 1 else 'was'} given"
    k = ft[3:-1]
    f: FnInfo | None = None
    own = 0
    if k.startswith("f:"):
        f = self.funcs[k[2:]] if k[2:] in self.funcs else None
    elif k.startswith("c:"):
        f = self.closures[int(k[2 : k.find(":", 2)])].f
        own = 1  # (its env, which a call passes first)
    elif k.startswith("m:"):
        c = k[2 : k.rfind(".")]
        f = self.classes[c].methods[k[k.rfind(".") + 1 :]] if c in self.classes and k[k.rfind(".") + 1 :] in self.classes[c].methods else None
        own = 1 if f is not None and f.deco == "" else 0
    if f is None:
        return "TypeError: the function cannot be called with positional arguments only"
    if self.dyn_takes(f, own, n):
        return ""
    if f.bad == "" and not k.startswith("c:"):
        return "TypeError: " + self.dyn_arity(f, own, n)  # (by its qualified name, as a method call's)
    have = len(f.params) - own
    return f"TypeError: {short(f.name) if not k.startswith('c:') else k[k.find(':', 2) + 1 : k.find('@')]}() takes {have} positional argument{'s' if have != 1 else ''} but {n} {'were' if n != 1 else 'was'} given"



def gen_dyn_sum(self, xs: Val, start: Val) -> Val:
    # sum(xs, start) of a list (of a dynamic value's items, or of dynamic values): start + each
    # item in turn, as dynamic additions (dyn_arith), the list's length read at every step as
    # CPython's iterator reads it
    if xs.t != "list[dyn]" and not is_list(xs.t):
        self.err(f"sum() of {typestr(xs.t)} is not supported")
    acc = self.alloca(DYN, "")
    ctr = self.alloca("int", "")
    self.mem_store(Val(acc, "*dyn"), self.dyn_box(start))
    self.mstore("int", "0", ctr)
    head = self.label()
    body = self.label()
    end = self.label()
    self.br(head)
    self.place(head)
    i = self.mload("int", ctr)
    self.cbr(self.num_cmp("<", Val(i, "int"), Val(self.mload("int", xs.v), "int")).v, body, end)
    self.place(body)
    item = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {xs.v}", f"i64 {i}"]), elem(xs.t))
    total = self.dyn_arith("+", self.mem_load(Val(acc, "*dyn")), item)
    self.mem_store(Val(acc, "*dyn"), total)
    self.mstore("int", self.scalar("add", [Val(i, "int"), Val("1", "int")]), ctr)
    self.br(head)
    self.place(end)
    return self.mem_load(Val(acc, "*dyn"))


def gen_json_any(self, name: str, args: list[Node], want: str, resultsoft: bool) -> Val | None:
    # json.loads() or json.dumps() (name: json$loads, json$dumps) in a module that compiles Any as
    # dyn: lib's function of Any values (JSONANY, which the loader adds to a program that has such
    # a module and json) where the document is Any values, so that loads() decodes it into Any's
    # containers and dumps() encodes those as the objects they are, with no copy (#779); else
    # None, json's own function of JSONValue. loads() where its result becomes Any storage (want
    # holds Any values); dumps() where its argument does, or is a list, dict or tuple display or a
    # list or dict comprehension, which is then Any's
    q = JSONANY + "$" + name[name.find("$") + 1 :]
    if q not in self.funcs:
        return None
    if name == "json$loads":
        if not holds_dyn(want):
            return None
        self.add(Ins("init", "", JSONANY))  # (its module's code, as an import runs it: nothing imports it)
        return self.call_fn(self.funcs[q], [], args, want, resultsoft=resultsoft)
    objkw = [x for x in args if x.kind == "kw" and x.s == "obj"]
    if len(args) == 0 or args[0].kind == "starred" or args[0].kind == "dstar" or (args[0].kind == "kw" and len(objkw) != 1):
        return None
    a = args[0] if args[0].kind != "kw" else objkw[0].kids[0]
    if a.kind == "list" or a.kind == "dict" or a.kind == "tuple" or a.kind == "dictcomp" or (a.kind == "listcomp" and a.s != "gen"):
        self.add(Ins("init", "", JSONANY))
        return self.call_fn(self.funcs[q], [], args, want, resultsoft=resultsoft)
    if args[0].kind == "kw":
        # (dumps(obj=...): the function its value's type chooses, which dry() finds without
        # evaluating it before the arguments ahead of it, called with the arguments as they are)
        if not holds_dyn(self.dry(a)):
            return None
        self.add(Ins("init", "", JSONANY))
        return self.call_fn(self.funcs[q], [], args, want, resultsoft=resultsoft)
    v = self.expr(a, "")
    if not holds_dyn(v.t):
        return self.call_fn(self.funcs[name], [], [self.vnode(v)] + args[1:], want, resultsoft=resultsoft)
    self.add(Ins("init", "", JSONANY))
    return self.call_fn(self.funcs[q], [], [self.vnode(v)] + args[1:], want, resultsoft=resultsoft)
