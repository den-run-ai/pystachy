"""Interface values: Protocol classes as stored interfaces (#488).

A class whose base is typing.Protocol is an interface. A value of it is a pointer to an
immutable 16-byte box {table, object}: the object is an implementation's own pointer, never
copied, and the table a constant of adapter code pointers, one table for each implementation
type converted to the interface (null where the value is None). The interface's methods call
their table entry with the object, as a Callable's call calls its code with its env
(Gen.icall). Each entry is compiled once the program is complete, for the operations that
calls through the interface use (iface_finish): an implementation needs only what is called.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import where
from src.pystachy_compiler.ir import ClassInfo, Data, FnInfo, Ins, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import SPECSHOW
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import clone, gelem, is_gen, is_opt, lt, typestr

# the intrinsic that an interface method's body calls: its table entry (iface_call)
IFACE_CALL = "__pystachy_iface__"

# the operations that every interface has, which str(), repr() and truth tests call: appended to
# the Protocol's own methods where its body does not declare them
IMPLICIT = ["__repr__", "__str__", "__bool__"]

PROTOCOLS = ["typing.Protocol", "typing_extensions.Protocol"]

# the templates of the stored interfaces Iterator[T], which joins of distinct iterators give
# (iter_join): __next__ gives T and __iter__ an Iterator[T]; and Iterable[T], whose __iter__ gives
# an Iterator[T]. In a Protocol's methods, Iterator[X] and Iterable[X] annotate these (iface_ann)
ITERATOR = "typing$Iterator"
ITERABLE = "typing$Iterable"

# operations whose adapter uses the builtin form that CPython's own operation is, so that a
# builtin type (a list, a generator, a file) can implement them: next(o), iter(o), len(o), ...
BUILTIN_FORMS = {"__next__": "next", "__iter__": "iter", "__len__": "len", "__repr__": "repr", "__str__": "str", "__bool__": "bool", "__hash__": "hash", "__abs__": "abs"}

# and the operators that a builtin type implements: o + a, o == a, a in o, o[a] (operator_form)
BINOPS = {"__add__": "+", "__sub__": "-", "__mul__": "*", "__truediv__": "/", "__floordiv__": "//", "__mod__": "%", "__pow__": "**", "__matmul__": "@", "__and__": "&", "__or__": "|", "__xor__": "^", "__lshift__": "<<", "__rshift__": ">>"}
CMPOPS = {"__eq__": "==", "__ne__": "!=", "__lt__": "<", "__le__": "<=", "__gt__": ">", "__ge__": ">="}


class Iface:
    # an interface class (a Protocol class): its operations, in the order of its table
    def __init__(self, name: str):
        self.name = name
        self.ops: list[str] = []
        self.props: dict[str, bool] = {}  # the operations that read a property
        self.implicit: dict[str, bool] = {}  # the IMPLICIT operations its body does not declare
        self.used: dict[int, bool] = {}  # the slots that compiled code calls through
        self.origin = ""  # an interface of type arguments: its template (iface_of)


class ITab:
    # the table of one implementation type's adapters for one interface
    def __init__(self, impl: str, iface: str, name: str, data: Data):
        self.impl = impl
        self.iface = iface
        self.name = name
        self.data = data
        self.codes: dict[int, str] = {}  # slot -> its adapter's symbol, once a call uses the slot
        self.mod = ""  # (the module and identity policy of the code that converted to it)
        self.home = "-"
        self.line = 0


def gen_protocol_base(self, n: Node) -> bool:
    # does a class's base n name typing.Protocol (or typing_extensions')
    return self.imported_ref(n) in PROTOCOLS


def gen_protocol_params(self, n: Node) -> list[str]:
    # the type variables of a class's base n when it is Protocol[T, U] (TypeVars, each once): a
    # generic interface (protocol_template); ["!"] for another subscript of Protocol; else []
    if n.kind != "index" or not self.protocol_base(n.kids[0]):
        return []
    out: list[str] = []
    for x in n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]:
        if x.kind != "name" or x.s not in self.typevars or x.s in self.tvtuples or x.s in out:
            return ["!"]
        out.append(x.s)
    return out


def gen_protocol_problem(self, name: str, c: Node, tvs: list[str]) -> str:
    # why class statement c of Protocol class name (generic with type variables tvs) is no
    # interface Pystachy compiles, or "": its methods take annotated parameters and give an
    # annotated result, which a table's entries take and give for every implementation; its body
    # holds methods (properties among them), a docstring, pass and ...
    if "!" in tvs:
        return "Protocol[...] takes TypeVars, each once (a TypeVarTuple is not supported)"
    for d in c.kids[1:]:
        if self.imported(d.s) not in ["typing.runtime_checkable", "typing_extensions.runtime_checkable"]:
            return f"Protocol {short(name)}: unsupported decorator @{short(d.s)}"
    seen: list[str] = []
    for d in c.kids[0].kids:
        if d.kind == "pass" or (d.kind == "expr" and (d.kids[0].kind == "str" or d.kids[0].kind == "ellipsis")):
            continue
        if d.kind != "def":
            return f"Protocol {short(name)}: a stored interface's members are its methods and properties (an attribute declaration is not supported yet: declare a property)"
        for x in d.kids[3:]:
            if not (x.s == "property" and len(x.kids) == 0) and self.imported(x.s) != "abc.abstractmethod":
                return f"Protocol {short(name)}: unsupported decorator @{short(x.s)} on {d.s}"
        if d.s in seen:
            return f"Protocol {short(name)}: {d.s} is defined twice"
        if d.s == "__init__" or d.s == "__new__":
            return f"Protocol {short(name)}: {d.s} is not supported in a stored interface (a Protocol has no objects of its own)"
        seen.append(d.s)
        ps = d.kids[0].kids
        if len(ps) == 0 or ps[0].kind != "param":
            return f"method '{d.s}' of Protocol {short(name)} must take self as its first parameter"
        for p in ps[1:]:
            if p.kind != "param":
                return f"Protocol {short(name)}.{d.s}: *args and **kwargs are not supported in a stored interface's methods"
            if p.kids[0].kind == "noann":
                return f"Protocol {short(name)}.{d.s}: parameter '{p.s}' needs an annotation (a stored interface's methods take fixed types)"
        if d.kids[1].kind == "noann":
            return f"Protocol {short(name)}.{d.s}: the method needs a return annotation (a stored interface's methods give a fixed type)"
        if len([x for x in d.kids[3:] if x.s == "property"]) > 0 and len(ps) != 1:
            return f"Protocol {short(name)}.{d.s}: a property takes only self"
    return ""


def gen_protocol_class(self, name: str, c: Node, tvs: list[str], mod: str) -> None:
    # class statement c of Protocol class name, which protocol_problem accepts, as an interface
    # (see Iface): each method's body becomes the call of its table entry, and the implicit
    # operations are added. A generic one (type variables tvs) is a template whose P[X] names an
    # interface of its own (iface_spec): its statement then makes no class
    c.kids = c.kids[:1]
    kept: list[Node] = []
    ops: list[str] = []
    for d in c.kids[0].kids:
        if d.kind != "def":
            kept.append(d)
            continue
        d.kids = d.kids[:3] + [x for x in d.kids[3:] if x.s == "property"]
        for p in d.kids[0].kids[1:]:
            p.kids[0] = self.iface_ann(p.kids[0])
        d.kids[1] = self.iface_ann(d.kids[1])
        ops.append(d.s)
        kept.append(stub_def(d))
    for m in IMPLICIT:
        if m not in ops:
            kept.append(implicit_def(m, c.line))
    c.kids[0].kids = kept
    if len(tvs) > 0:
        self.ifgeneric[name] = tvs
        self.ifnodes[name] = c
        self.ifmods[name] = mod
        return
    self.ifaces[name] = iface_info(name, c)


def gen_iface_ann(self, a: Node) -> Node:
    # annotation a of a Protocol's method, where Iterator[X] and Iterable[X] (typing's or
    # collections.abc's, also inside other types) annotate the stored interfaces of X: a value of
    # any iterator, or of any iterable, of X items (ITERATOR, ITERABLE)
    if a.kind == "str":
        return self.iface_ann(self.parse_expr(a.s))
    if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr") and self.ann_base(a.kids[0]) in ["iterator", "iterable"]:
        return mk("ifacetype", ITERATOR if self.ann_base(a.kids[0]) == "iterator" else ITERABLE, a.line, [self.iface_ann(a.kids[1])])
    return mk(a.kind, a.s, a.line, [self.iface_ann(x) for x in a.kids])


def iface_info(name: str, c: Node) -> Iface:
    # the operations of interface class name, whose class statement (stubbed) is c
    face = Iface(name)
    for d in c.kids[0].kids:
        if d.kind == "def":
            face.ops.append(d.s)
            if len(d.kids) > 3:
                face.props[d.s] = True
            if d.line == c.line and d.s in IMPLICIT:
                face.implicit[d.s] = True
    return face


def implicit_def(m: str, line: int) -> Node:
    # def m(self) -> str (bool for __bool__) of an interface that does not declare IMPLICIT m
    ret = mk("name", "bool" if m == "__bool__" else "str", line, [])
    params = mk("params", "0,-1", line, [mk("param", "self", line, [mk("noann", "", line, []), mk("noann", "", line, [])])])
    return stub_def(mk("def", m, line, [params, ret, mk("block", "", line, [])]))


def gen_iface_spec(self, c: str, a: Node) -> str:
    # P[X, Y] of generic Protocol c, annotation a's subscript: the interface whose methods take
    # and give the types its type variables are bound to (iface_make); or "!" and why not
    tvs = self.ifgeneric[c]
    xs = a.kids if a.kind == "tuple" else [a]
    if len(xs) != len(tvs):
        return f"!{short(c)}[...] takes {len(tvs)} type{'s' if len(tvs) != 1 else ''} ({', '.join([short(x) for x in tvs])}), not {len(xs)}"
    ts: list[str] = []
    for x in xs:
        t = self.ann(x)
        if t.startswith("!"):
            return t
        ts.append(t)
    return self.iface_of(c, ts)


def gen_iface_of(self, c: str, ts: list[str]) -> str:
    # the interface of template c (a generic Protocol, or ITERATOR) for types ts: one class for
    # each binding, named once for the whole compilation (Gen.ifspecs: the passes after the one
    # that made it make it again before their code, iface_respec, as a join hint may name it)
    key = c + "[" + ",".join(ts) + "]"
    if key in self.ifmade:
        return self.ifmade[key]
    if key not in self.ifspecs:
        self.ifspecs[key] = [f"{c}-i{len(self.ifspecs) + 1}", c] + ts
    name = self.ifspecs[key][0]
    self.ifmade[key] = name
    line = self.line
    if c == ITERATOR:
        # Iterator[T]: __next__ gives T, __iter__ an Iterator[T] (of the same object, usually)
        node = mk("class", name, line, [mk("block", "", line, [op_def("__next__", [], ts[0], line), op_def("__iter__", [], name, line)])])
    elif c == ITERABLE:
        # Iterable[T]: __iter__ gives an Iterator[T], made of each object's own iterator
        node = mk("class", name, line, [mk("block", "", line, [op_def("__iter__", [], self.iface_of(ITERATOR, ts), line)])])
    else:
        node = clone(self.ifnodes[c])
        node.s = name
        line = node.line
        bindings: dict[str, str] = {}
        for i in range(len(ts)):
            bindings[self.ifgeneric[c][i]] = ts[i]
        for d in node.kids[0].kids:
            if d.kind == "def":
                for p in d.kids[0].kids[1:]:
                    p.kids[0] = self.bound_annotation(p.kids[0], bindings, name)
                if d.kids[1].kind != "noann":
                    d.kids[1] = self.bound_annotation(d.kids[1], bindings, name)
    for m in IMPLICIT:
        if len([d for d in node.kids[0].kids if d.kind == "def" and d.s == m]) == 0:
            node.kids[0].kids.append(implicit_def(m, node.line))
    SPECSHOW[name] = f"{short(c)}[{', '.join([typestr(t) for t in ts])}]"
    self.iface_make(name, c, node)
    self.line = line
    return name


def op_def(m: str, ps: list[str], ret: str, line: int) -> Node:
    # def m(self, _a0: A, ...) -> ret of a stored interface ITERATOR's, its types bound
    params = mk("params", "0,-1", line, [mk("param", "self", line, [mk("noann", "", line, []), mk("noann", "", line, [])])])
    for j in range(len(ps)):
        params.kids.append(mk("param", f"_a{j}", line, [mk("boundtype", ps[j], line, []), mk("noann", "", line, [])]))
    return stub_def(mk("def", m, line, [params, mk("boundtype", ret, line, []), mk("block", "", line, [])]))


def gen_iface_make(self, name: str, origin: str, node: Node) -> None:
    # interface class name, of class statement node (stubbed, its annotations bound), made while
    # declarations are made or code compiled: its methods are declared, and compiled now where
    # code is being compiled (a call compiles them otherwise: Gen.lazy)
    ci = ClassInfo(name, node)
    ci.mod = self.ifmods.get(origin, "")
    self.classes[name] = ci
    self.ifaces[name] = iface_info(name, node)
    self.ifaces[name].origin = origin
    sel = self.selfcls
    lib = self.lib
    line = self.line
    try:
        for d in node.kids[0].kids:
            if d.kind == "def":
                self.line = d.line
                self.lib = ci.mod != ""
                self.selfcls = name
                g = self.declare_fn(d, name)
                g.mod = ci.mod
                ci.methods[g.name] = g
        self.declare_fields(ci)  # (none, but the __init__ every class has: class_fields)
        self.selfcls = sel
        for f in ci.methods.values() if self.compiling else []:
            if f.ll not in self.compiled:
                fr = self.save()
                self.modlevel = False
                self.lenient = False
                try:
                    self.function(f, f.node.kids[2].kids)
                finally:
                    self.restore(fr)
    finally:
        self.selfcls = sel
        self.lib = lib
        self.line = line


def gen_iface_respec(self) -> None:
    # the interfaces of type arguments that earlier passes made (iface_of), made again in their
    # order before any code is compiled: a join hint of this pass may name one
    for key in [k for k in self.ifspecs]:
        spec = self.ifspecs[key]
        if spec[1] == ITERATOR or spec[1] == ITERABLE or spec[1] in self.ifgeneric:
            self.iface_of(spec[1], spec[2:])


def gen_iface_use(self, f: FnInfo) -> None:
    # a call of method f of an interface: its table slot is used (iface_finish compiles it)
    face = self.ifaces[f.cls]
    if f.name in face.ops:
        face.used[face.ops.index(f.name)] = True


def gen_iface_item(self, t: str) -> str:
    # the type of the items of an iterator of type t (a class with __next__, an interface among
    # them, a generator, a file), or "" where t is no iterator
    if is_gen(t):
        return gelem(t)
    if t == "file":
        return "str"
    if self.is_iterator(t):
        return self.next_type(t)
    return ""


def gen_iter_join(self, a: str, b: str) -> str:
    # the type of a value that is an iterator of type a or one of type b, distinct types of which
    # no other join is: the stored interface Iterator[T] (iface_of), where both give items of type
    # T; "" otherwise. Its values hold either object, which calls of next(), iter() and loops
    # advance as their own. A module that compiles Any dynamically keeps its own joins (Any values)
    if a == b or self.rtmode or self.dyn_policy(self.line):
        return ""
    ta = self.iface_item(a)
    tb = self.iface_item(b)
    if ta == "" or tb == "" or ta != tb or "?" in ta:
        return ""
    if self.iface_impl(a) != "" or self.iface_impl(b) != "":
        return ""
    if self.is_iface(a) and self.ifaces[a].origin == ITERATOR:
        return a if not self.is_iface(b) else ""
    if self.is_iface(b) and self.ifaces[b].origin == ITERATOR:
        return b if not self.is_iface(a) else ""
    if self.is_iface(a) or self.is_iface(b):
        return ""
    return self.iface_of(ITERATOR, [ta])


def stub_def(d: Node) -> Node:
    # def d with the body of an interface's method: return __pystachy_iface__(self, a, b), each
    # parameter passed on as the table entry's argument
    args = [mk("name", p.s, d.line, []) for p in d.kids[0].kids]
    call = mk("call", "", d.line, [mk("name", IFACE_CALL, d.line, [])] + args)
    d.kids[2] = mk("block", "", d.line, [mk("return", "", d.line, [call])])
    return d


def gen_is_iface(self, t: str) -> bool:
    # is t an interface class (a value of it: a box of a table and an object, or None)
    return t in self.ifaces


def gen_iface_reflect(self, t: str, what: str) -> None:
    # an error where what (type(), isinstance(), hash(), ...) needs the class of a value of
    # static type t that an interface is: only the run time knows its object's class (#487)
    if self.is_iface(t):
        self.err(f"{what} of a value of {typestr(t)} is not supported: its object's class is known only when the program runs (#487)")


def gen_iface_call(self, args: list[Node]) -> Val:
    # __pystachy_iface__(self, a, b) in a method of an interface (protocol_class): the call of the
    # entry of its operation in self's table, with self's object and the arguments, which have
    # the method's types (self is not None: its caller checked)
    f = self.curfn
    if f.cls not in self.ifaces:
        self.err(f"name '{IFACE_CALL}' is not defined")
    k = self.ifaces[f.cls].ops.index(f.name)
    o = self.expr(args[0], "")
    vals = [self.expr(a, "") for a in args[1:]]
    tab = self.mload('%ptr', o.v)
    obj = self.mload('%ptr', self.maddr('%ptr', o.v, '1', True))
    code = self.mload('%ptr', self.maddr('%ptr', tab, str(k), True))
    return self.icall(code, obj, vals, f.ret)


def gen_iface_obj(self, v: Val) -> Val:
    # the object that a value of an interface holds (null for None), as identity sees it
    if not self.is_iface(v.t):
        return v
    if v.v in self.nn:
        return Val(self.mload('%ptr', self.maddr('%ptr', v.v, '1', True)), "env")
    start = self.cur
    some = self.label()
    end = self.label()
    ph = Ins("phi", "env", "")
    self.incoming(ph, "null", start)
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, some)
    self.place(some)
    o = self.mload('%ptr', self.maddr('%ptr', v.v, '1', True))
    self.incoming(ph, o, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "env")


def gen_iface_impl(self, t: str) -> str:
    # why a value of type t cannot be held by an interface, or "": it must be a reference, whose
    # pointer the box holds
    if t == "None" or t == "dyn" or is_opt(t) or lt(t) != "ptr" or t.startswith("fn[") or t == "exc" or t == "exctype":
        return f"an interface value cannot hold a value of type {typestr(t)} (it holds objects, containers, generators and files)"
    return ""


def gen_to_iface(self, v: Val, t: str) -> Val:
    # v as a value of interface t: a new box of the table of v's type for t and v itself; a
    # value of a class that is None stays None (null)
    why = self.iface_impl(v.t)
    if why != "":
        self.err(f"expected {typestr(t)}, got {typestr(v.t)}: {why}")
    if self.is_iface(v.t):
        # (its table would call the other interface's, and its box hold the other's box, whose
        # object identity must see through: not supported yet)
        self.err(f"a value of {typestr(v.t)} as a value of {typestr(t)} is not supported: convert the object itself")
    tab = self.iface_table(v.t, t)
    if v.t not in self.classes or v.v in self.nn:
        return self.iface_box(tab, v.v, t)
    start = self.cur
    some = self.label()
    end = self.label()
    ph = Ins("phi", t, "")
    self.incoming(ph, "null", start)
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, some)
    self.place(some)
    b = self.iface_box(tab, v.v, t)
    self.incoming(ph, b.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), t)


def gen_iface_box(self, tab: str, obj: str, t: str) -> Val:
    # a new box of table tab and object obj, a value of interface t (the collector scans it: it
    # keeps the object alive)
    b = self.rt("pys_alloc", "ptr", ["i64 16"])
    self.mstore('%ptr', tab, b)
    self.mstore('%ptr', obj, self.maddr('%ptr', b, '1', True))
    self.nn[b] = True
    return Val(b, t)


def gen_iface_table(self, impl: str, t: str) -> str:
    # the symbol of the table of implementation type impl for interface t: a constant whose
    # entries iface_finish compiles, those that the program calls
    key = impl + " " + t
    if key in self.itabs:
        return self.itabs[key].name
    if self.drying > 0:
        return "null"  # (dry's code is dropped: a conversion it types needs no table)
    name = f"@it.{len(self.itabs)}"
    d = Data("itab", name)
    self.consts.append(d)
    tab = ITab(impl, t, name, d)
    tab.mod = self.curfn.mod
    tab.home = self.fn_home(self.curfn)
    tab.line = self.line
    self.itabs[key] = tab
    return name


def gen_iface_finish(self) -> bool:
    # compile the entries the tables still lack, of the slots that calls through their interfaces
    # use (which compiling them can add to); whether it compiled one
    did = False
    for key in [k for k in self.itabs]:
        tab = self.itabs[key]
        face = self.ifaces[tab.iface]
        for k in range(len(face.ops)):
            if k in face.used and k not in tab.codes:
                tab.codes[k] = self.iface_adapter(tab, k)
                did = True
    return did


def gen_iface_tables(self) -> None:
    # each table's entries, once the program is complete (null for an operation nothing calls)
    for tab in self.itabs.values():
        face = self.ifaces[tab.iface]
        tab.data.refs = [tab.codes[k] if k in tab.codes else "null" for k in range(len(face.ops))]


def gen_iface_adapter(self, tab: ITab, k: int) -> str:
    # the code of entry k of table tab: a function R(ptr object, A a0, B a1) of the interface's
    # operation's types, whose body is the operation on the object, of the implementation's type:
    # o.name(a0, a1), o.name for a property, or the builtin form of an operation that has one
    # (next(o), len(o), ...). Its result is converted to R, as a return statement converts it
    face = self.ifaces[tab.iface]
    op = face.ops[k]
    m = self.classes[tab.iface].methods[op]
    ps = m.ptypes[1:]
    line = tab.line
    ll = f"@cv.{self.ncv}"
    self.ncv += 1
    f = FnInfo("<interface>", ll, mk("def", "<interface>", line, []), "")
    f.params = ["_o"] + [f"_a{j}" for j in range(len(ps))]
    f.ptypes = [tab.impl] + ps
    for _ in f.params:
        f.defaults.append(mk("noann", "", line, []))
        f.dglob.append("")
        f.dtypes.append("")
    f.ret = m.ret
    f.mod = tab.mod
    f.home = tab.home
    o = mk("name", "_o", line, [])
    a: list[Node] = []
    for j in range(len(ps)):
        x = mk("name", f"_a{j}", line, [])
        a.append(x if m.npos < 0 or j + 1 < m.npos else mk("kw", m.params[j + 1], line, [x]))
    if op in face.props:
        e = mk("attr", op, line, [o])
    elif op in BUILTIN_FORMS and len(ps) == 0 and (op in face.implicit or tab.impl not in self.classes or op == "__next__" or op == "__iter__"):
        e = mk("call", "", line, [mk("name", BUILTIN_FORMS[op], line, []), o])
    elif tab.impl not in self.classes and operator_form(op, len(a)) != "":
        e = operator_expr(op, o, a, line)  # (a builtin type's operator: o[a0], a0 in o, o + a0, ...)
    else:
        e = mk("call", "", line, [mk("attr", op, line, [o])] + a)
    body = [mk("return", "", line, [e])]
    if e.kind == "assign" or e.kind == "del":
        body = [e]  # (o[a0] = a1, del o[a0]: statements, whose operation returns None)
    if op in face.implicit and (op == "__repr__" or op == "__str__") and (is_gen(tab.impl) or tab.impl == "file"):
        # (Pystachy prints neither: a list of the interface's values has a repr that may never
        # print one, which CPython prints by its address, <generator object f at 0x...>)
        what = "a generator" if is_gen(tab.impl) else "a file"
        msg = mk("str", f"{op[2:-2]}() of {what} held by a value of {typestr(tab.iface)} is not supported", line, [])
        body = [mk("raise", "", line, [mk("call", "", line, [mk("name", "NotImplementedError", line, []), msg])])]
    f.node.kids = [mk("params", "-1,-1", line, []), mk("noann", "", line, []), mk("block", "", line, body)]
    self.making.append(f"making the table of {typestr(tab.impl)} as {typestr(tab.iface)} (for {op}), converted at {where(line)}")
    fr = self.save()
    self.modlevel = False
    self.lenient = False
    self.line = line
    self.function(f, body)
    self.restore(fr)
    self.making.pop()
    return ll


def operator_form(op: str, n: int) -> str:
    # the kind of syntax that operation op, with n arguments, is for a builtin type: "index",
    # "contains", "setitem", "delitem", "binop", "cmp", "call", or "" for a method call
    if op == "__getitem__" and n == 1:
        return "index"
    if op == "__contains__" and n == 1:
        return "contains"
    if op == "__setitem__" and n == 2:
        return "setitem"
    if op == "__delitem__" and n == 1:
        return "delitem"
    if op in BINOPS and n == 1:
        return "binop"
    if op in CMPOPS and n == 1:
        return "cmp"
    if op == "__call__":
        return "call"
    return ""


def operator_expr(op: str, o: Node, a: list[Node], line: int) -> Node:
    # operation op of object o with arguments a in its syntax (operator_form)
    k = operator_form(op, len(a))
    if k == "index":
        return mk("index", "", line, [o, a[0]])
    if k == "contains":
        return mk("cmp", "in", line, [a[0], o])
    if k == "setitem":
        return mk("assign", "", line, [mk("index", "", line, [o, a[0]]), a[1]])
    if k == "delitem":
        return mk("del", "", line, [mk("index", "", line, [o, a[0]])])
    if k == "binop":
        return mk("binop", BINOPS[op], line, [o, a[0]])
    if k == "cmp":
        return mk("cmp", CMPOPS[op], line, [o, a[0]])
    return mk("call", "", line, [o] + a)


def gen_iface_cmp(self, op: str, a: Val, b: Val) -> Val:
    # a comparison of which an operand is a value of an interface: is and is not compare the
    # objects the boxes hold (None's null), as their identity is the objects'; the others call
    # the objects' methods, which their classes alone know: not supported yet
    if op == "is" or op == "is not":
        if not self.isref(a.t) or not self.isref(b.t):
            return Val("false" if op == "is" else "true", "bool")
        return self.ptr_cmp('==' if op == 'is' else '!=', self.iface_obj(a), self.iface_obj(b))
    if (op == "==" or op == "!=") and (a.t == "None" or b.t == "None"):
        # (None equals only None: an object's __eq__ with None is not called here)
        self.err(f"comparing a value of {typestr(a.t if self.is_iface(a.t) else b.t)} with None by {op} calls its object's __eq__: compare with 'is None' or 'is not None'")
    t = a.t if self.is_iface(a.t) else b.t
    self.err(f"comparing values of {typestr(t)} with {op} is not supported: their objects' classes are known only when the program runs (compare with 'is')")
    return Val("false", "bool")
