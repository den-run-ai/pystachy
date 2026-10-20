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
from src.pystachy_compiler.ir import Data, FnInfo, Ins, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import METHODS, NONEVAR, RTDATA
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import elem, is_callable, is_dict, is_fn, is_list, is_opt, is_set, is_sopt, is_tuple, is_union, is_vtuple, targs, typestr, umembers, unopt

DYN = "dyn"
# runtime.c's DynType kinds (DK_*) and the flags of a class's (DF_*)
DK_OBJ = 8
DK_FUNC = 9
DF_EQ = 1
DF_CMP = 2
DF_HASH = 4
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
    # object of the program's classes, a container of boxes, a tuple (made one of boxes), and dyn
    if t == DYN or t in BUILTIN or t == NONEVAR:
        return ""
    if t in self.classes and t not in self.tmpl:
        return "" if self.classes[t].exc == "" else f"an exception object ({typestr(t)}) as Any is not supported yet"
    if is_opt(t):
        return self.dyn_boxable(unopt(t))
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
    if "__eq__" in ms:
        flags |= DF_EQ
    if "__lt__" in ms or "__le__" in ms or "__gt__" in ms or "__ge__" in ms:
        flags |= DF_CMP
    if flags != 0:
        self.ocmp[c] = True  # (@o.eq and @o.cmp, compiled leniently: what the class cannot compare raises when it runs)
    if self.hash_kind(c) != "id" or len([x for x in self.classes.values() if x.tag > 0 and self.derives(x.name, c) and self.hash_kind(x.name) != "id"]) > 0:
        if c not in self.hcls:
            self.hcls[c] = True
        flags |= DF_HASH
    dt = Data("dyntype", name)
    dt.refs = [self.sconst(d), self.sconst(short(c)), base]
    dt.items = [Val(str(DK_OBJ), "int"), Val(str(self.ocls[c]), "int"), Val(str(flags), "int")]
    self.consts.append(dt)
    self.dynclasses.append(c)
    return name


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
    why = self.dyn_boxable(t)
    if why != "":
        self.err(why)
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
        ms = umembers(unopt(t))
        self.dyn_check(v, ms + (["None"] if is_opt(t) or self.optional(unopt(t)) == unopt(t) else []), typestr(t))
        return self.dyn_select(v, ms + ["None"], t)
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
    # payload's), else "" (it stays dyn)
    if not truth:
        return ""
    ts = self.dyn_isinst_types(c)
    if len(ts) == 2 and ts[0] == "int" and ts[1] == "bool":
        return ""  # (an int or a bool: both stay boxed)
    if len(ts) != 1 or ts[0] == "" or ts[0] == "*":
        return ""
    return ts[0]


# ---- operations

def gen_dyn_arith(self, op: str, a: Val, b: Val, inplace: bool = False) -> Val:
    # a op b where either is dyn: both boxed, through the class dunders of the boxed classes that
    # define them (dyn_dispatchers), then pys_dyn_binop's builtin arithmetic
    if op not in BINOPS:
        self.err(f"the operator {op} on Any values is not supported")
    x = self.dyn_box(a)
    y = self.dyn_box(b)
    f = self.dyn_dispatcher(("i" if inplace else "") + "op" + str(BINOPS[op]), [DYN, DYN], DYN, BINDUNDERS[op])
    return self.dyn_call(f, [x, y])


def gen_dyn_unary(self, op: str, v: Val) -> Val:
    f = self.dyn_dispatcher("un" + str(UNOPS[op]), [DYN], DYN, {"-": "__neg__", "+": "__pos__", "~": "__invert__"}[op])
    return self.dyn_call(f, [v])


def gen_dyn_compare(self, op: str, a: Val, b: Val) -> Val:
    # a op b where either is dyn: ==, !=, <, <=, >, >= (is, in: dyn_identity, dyn_contains)
    x = self.dyn_box(a)
    y = self.dyn_box(b)
    if op == "==" or op == "!=":
        r = Val(self.rt("pys_dyn_eq", "i64", [f"ptr {x.v}", f"ptr {y.v}"]), "int")
        return self.num_cmp("!=" if op == "==" else "==", r, Val("0", "int"))
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
    # payload but for floats (a float's box is its identity, as a float object's is CPython's)
    x = self.dyn_box(a)
    y = self.dyn_box(b)
    ta = Val(self.dyn_typeof(x), "dyntype")
    same = self.ptr_cmp("==", x, y).v
    st = self.ptr_cmp("==", ta, Val(self.dyn_typeof(y), "dyntype")).v
    sp = self.num_cmp("==", Val(self.to_slot(self.dyn_payload(x, "int")), "int"), Val(self.to_slot(self.dyn_payload(y, "int")), "int")).v
    nf = self.ptr_cmp("!=", ta, Val(self.rtdata("pys_dyntype_float"), "dyntype")).v
    alike = self.scalar("and", [Val(st, "bool"), Val(self.scalar("and", [Val(sp, "bool"), Val(nf, "bool")]), "bool")])
    r = self.scalar("or", [Val(same, "bool"), Val(alike, "bool")])
    return Val(r if op == "is" else self.scalar("xor", [Val(r, "bool"), Val("true", "bool")]), "bool")


def gen_dyn_truth(self, v: Val) -> str:
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


def gen_dyn_type_name(self, v: Val) -> Val:
    # type(v).__name__: its DynType's name
    t = self.dyn_typeof(v)
    return Val(self.mload("%ptr", self.maddr("ptr", t, "2")), "str")


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
    for c in [x for x in self.dynclasses]:
        if not self.dyn_supports(c, key, dunder, len(ps) - 1):
            continue
        hit = self.label()
        nxt = self.label()
        self.cbr(self.ptr_cmp("==", t, Val(self.dyntypes[c], "dyntype")).v, hit, nxt)
        self.place(hit)
        self.dyn_arm(f, key, dunder, self.dyn_payload(o, c), ps[1:])
        self.place(nxt)
    if key.startswith("op") and dunder != "":
        # the reflected operation of the right operand's class (b.__radd__(a)), where a's has none
        r = "__r" + dunder[2:]
        b = ps[1]
        tb = Val(self.dyn_typeof(b), "dyntype")
        for c in [x for x in self.dynclasses]:
            if r not in self.classes[c].methods:
                continue
            hit = self.label()
            nxt = self.label()
            self.cbr(self.ptr_cmp("==", tb, Val(self.dyntypes[c], "dyntype")).v, hit, nxt)
            self.place(hit)
            x = self.dyn_payload(b, c)
            self.dyn_return(f, self.expr(mk("call", "", line, [mk("attr", r, line, [self.vnode(x)]), self.vnode(o)]), ""))
            self.place(nxt)
    if key.startswith("call.") or key.startswith("has."):
        self.dyn_builtin_methods(f, key, o, ps[1:])
    if key.startswith("callv."):
        self.dyn_fn_arms(f, key, o, ps[1:])
    self.dyn_fallback(f, key, ps)


def gen_dyn_fn_arms(self, f: FnInfo, key: str, o: Val, args: list[Val]) -> None:
    # the cases of dispatcher callv.<n> for the function values boxed: each called as its own
    # type calls it (defaults, a closure's env, a bound method's object), or the TypeError of a
    # call with the wrong number of arguments
    t = Val(self.dyn_typeof(o), "dyntype")
    line = self.line
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
    # does class c have a case in dispatcher key: it defines the dunder (or the attribute, the
    # method that takes nargs positional arguments) the operation runs
    ci = self.classes[c]
    if key.startswith("get."):
        a = key[4:]
        return a in ci.ftypes or (a in ci.methods and ci.methods[a].prop)
    if key.startswith("set."):
        return key[4:] in ci.ftypes
    if key.startswith("call.") or key.startswith("has."):
        m = key[key.find(".") + 1 : key.rfind(".")]
        if m not in ci.methods or ci.methods[m].prop:
            return False
        return self.dyn_takes(ci.methods[m], 0 if ci.methods[m].deco != "" else 1, nargs)
    if key.startswith("callv."):
        return "__call__" in ci.methods and self.dyn_takes(ci.methods["__call__"], 1, nargs)
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
    elif key.startswith("has."):
        r = Val("null", "None")  # (it has the method: the call that follows calls it)
    elif key.startswith("call."):
        r = self.expr(mk("call", "", line, [mk("attr", key[5 : key.rfind(".")], line, [xn])] + an), "")
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
    # boxes, and str's and tuple's, whose arguments unbox (dyn_unbox) and whose fresh results box
    m = key[key.find(".") + 1 : key.rfind(".")]
    n = int(key[key.rfind(".") + 1 :])
    t = Val(self.dyn_typeof(o), "dyntype")
    line = self.line
    for bt in ["list[dyn]", "dict[dyn,dyn]", "str", "vtuple[dyn]"]:
        if not self.dyn_builtin_takes(bt, m, n):
            continue
        hit = self.label()
        nxt = self.label()
        self.cbr(self.ptr_cmp("==", t, Val(self.dyn_type(bt), "dyntype")).v, hit, nxt)
        self.place(hit)
        if key.startswith("has."):
            self.ret_(Val("null", "None"))
        else:
            x = self.dyn_payload(o, bt)
            r = self.expr(mk("call", "", line, [mk("attr", m, line, [self.vnode(x)])] + [self.vnode(a) for a in args]), "")
            self.dyn_return(f, self.dyn_fresh(r))
        self.place(nxt)


def gen_dyn_builtin_takes(self, bt: str, m: str, n: int) -> bool:
    # does builtin type bt (one a box holds) have method m, called with n positional arguments
    base = "list" if is_list(bt) else "dict" if is_dict(bt) else "vtuple" if is_vtuple(bt) else bt
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
    # compile the dispatchers (again) for the classes boxed so far, if any or a new dispatcher
    # appeared since the last time: True if so. Compiling them may box more classes, and need
    # more dispatchers, so that program calls this until it is False
    sig = f"{len(self.dynclasses)} {len(self.dynfns)}"
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
    if len([a for a in args if a.kind not in ["int", "float", "str", "True", "False", "None", "name"]]) > 0:
        self.dyn_call(self.dyn_dispatcher(f"has.{m}.{len(args)}", [DYN], "None", m), [o])
    vals = [self.dyn_box(self.expr(a, DYN)) for a in args]
    return self.dyn_call(self.dyn_dispatcher(f"call.{m}.{len(args)}", [DYN] * (len(args) + 1), DYN, m), [o] + vals)


def gen_dyn_mixed(self, es: list[Node]) -> bool:
    # do the items es of a display (in a module that compiles Any so) have no one type, so that
    # it is a container of dynamic values, and the displays among the items are made so too: the
    # types of those that are not empty displays, which a dry run gives
    ts: list[str] = []
    for e in es:
        if (e.kind == "list" or e.kind == "dict" or e.kind == "set") and len(e.kids) == 0:
            continue
        if e.kind == "starred" or e.kind == "dstar":
            return False
        ts.append(self.dry(e, ""))
    if len(ts) < 2:
        return DYN in ts
    j = ts[0]
    for t in ts[1:]:
        j = self.join(j, t) if j != "" else ""
    return j == "" or j == DYN



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
    dt.items = [Val(str(DK_FUNC), "int"), Val("-1", "int"), Val("0", "int")]
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
    have = len(f.params) - own
    return f"TypeError: {short(f.name) if not k.startswith('c:') else k[k.find(':', 2) + 1 : k.find('@')]}() takes {have} positional argument{'s' if have != 1 else ''} but {n} {'were' if n != 1 else 'was'} given"
