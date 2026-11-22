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
from src.pystachy_compiler.ir import Data, Ins, Val
from src.pystachy_compiler.names import OBJECT, short
from src.pystachy_compiler.symbols import ClassInfo, FnInfo
from src.pystachy_compiler.specs import BIG, BIGOPT, COMPLEXC, EMPTYFS, OBJECTC, SPECSHOW
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import clone, elem, gelem, is_callable, is_clsval, is_dict, is_gen, is_list, is_opt, is_set, is_sopt, is_tuple, is_union, is_vtuple, lt, targs, typestr, umembers, unopt

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

# OBJECT (names.py) is the stored interface that `object` annotates where no template takes it (a
# parameter's object annotation still makes a template): a variable's, a field's, a container's
# items, a function's result. Every type implements it, and it declares no operation but those of
# every interface: a number, held as the box of its T | None (its own pointer for a reference), is
# printed, compared, hashed and tested by its type's own operations, which isinstance() narrows it
# to (object_iface); any other operation is an error that says so (object_note)

# the builtin types whose names isinstance() takes beside the program's classes for a value of
# an interface (iface_classes), and those a test narrows such a value to, as the type it is then
# (iface_narrow: an int may be a bool, which keeps its own repr and truth)
BUILTIN_TESTS = ["int", "float", "bool", "str", "bytes", "list", "dict", "tuple", "set", "frozenset", "type"]

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
        # the operations that the program's code asks of a value's object whatever its class,
        # which no method of the protocol declares (iface_op): format(), hash(), isinstance(),
        # == and != with a value of another type. By the operation's key (which no method's
        # name is): the types of its arguments after the object, its result's, the expression
        # that each implementation's entry returns, of its object _o and arguments _a0, ..., and
        # what errors name it by
        self.dargs: dict[str, list[str]] = {}
        self.dret: dict[str, str] = {}
        self.dexpr: dict[str, Node] = {}
        self.dshow: dict[str, str] = {}


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
        self.ifspecs[key] = [c if c == OBJECT else f"{c}-i{len(self.ifspecs) + 1}", c] + ts
    name = self.ifspecs[key][0]
    self.ifmade[key] = name
    line = self.line
    if c == OBJECT:
        # object: no operation of its own (OBJECT)
        node = mk("class", name, line, [mk("block", "", line, [])])
    elif c == ITERATOR:
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
    SPECSHOW[name] = "object" if c == OBJECT else f"{short(c)}[{', '.join([typestr(t) for t in ts])}]"
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
        if spec[1] == ITERATOR or spec[1] == ITERABLE or spec[1] == OBJECT or spec[1] in self.ifgeneric:
            self.iface_of(spec[1], spec[2:])


def gen_object_iface(self) -> str:
    # the interface that an object annotation names in a variable, a field, a container's items
    # or a result (OBJECT), made by the first that names it
    return self.iface_of(OBJECT, [])


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


def gen_iface_widens(self, body: list[Node], name: str, t: str, vt: str) -> bool:
    # may a store of a value of type vt widen variable name of type t, which code body annotates
    # (join_hint): where its annotation types nothing (Iterator[T] and Iterable[T] annotations, also
    # inside a list's or dict's, tmpl_ann) and the join is the Iterator[T] interface of distinct
    # iterators (iter_join), as the variable's value, a list's items or a dict's values
    a = ann_node(body, name)
    if a is None or not self.tmpl_ann(a):
        return False
    j = self.join_type(t, vt)
    return self.is_iface(j) or (is_list(j) and self.is_iface(elem(j))) or (is_dict(j) and self.is_iface(targs(j)[1]))


def ann_node(body: list[Node], name: str) -> Node | None:
    # the annotation of variable name in code body (into blocks, as ann_target looks), or None
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        if st.kind == "annassign" and st.kids[0].kind == "name" and st.kids[0].s == name:
            return st.kids[1]
        for kid in st.kids:
            found: Node | None = None
            if kid.kind == "block":
                found = ann_node(kid.kids, name)
            elif kid.kind == "except":
                found = ann_node(kid.kids[1].kids, name)
            if found is not None:
                return found
    return None


def gen_iter_join(self, a: str, b: str) -> str:
    # the type of a value that is an iterator of type a or one of type b, distinct types of which
    # no other join is (a class and its base class join as the base: join): the stored interface
    # Iterator[T] (iface_of), where both give items of type T, or one gives ints and the other
    # promoting ints (T is the promoting int, which the other's ints become, bigints.py); ""
    # otherwise. Its values hold either object, which calls of next(), iter() and loops advance as
    # their own. (A display in a module that compiles Any dynamically keeps its Any items: expr)
    if a == b or self.rtmode or self.join(a, b) != "":
        return ""
    ta = self.iface_item(a)
    tb = self.iface_item(b)
    t = ta if ta == tb else (BIG if (ta == BIG and tb == "int") or (ta == "int" and tb == BIG) else "")
    if t == "" or "?" in t:
        return ""
    if self.iface_impl(a) != "" or self.iface_impl(b) != "":
        return ""
    if self.is_iface(a) and self.ifaces[a].origin == ITERATOR:
        return a if not self.is_iface(b) and ta == t else ""
    if self.is_iface(b) and self.ifaces[b].origin == ITERATOR:
        return b if not self.is_iface(a) and tb == t else ""
    if self.is_iface(a) or self.is_iface(b):
        return ""
    return self.iface_of(ITERATOR, [t])


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


def gen_is_object(self, t: str) -> bool:
    # is t the type of a value that an object annotation stores (OBJECT)
    return t == OBJECT


def gen_object_note(self, ts: list[str]) -> str:
    # what an error of an operation that its operands' types ts do not take adds where one is
    # object's (OBJECT), whose value takes only the operations of every value: "" otherwise
    for t in ts:
        if t == OBJECT and self.int_policy(self.line):
            # (iface_narrow: an int there is a promoting int, which a bool that passes the test is not)
            return " (narrow a value of object with isinstance() to float, bool, str, bytes, type or a class of the program first, not to int in a module that opts in to promoting ints: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)"
        if t == OBJECT:
            return " (narrow a value of object with isinstance() to int, float, bool, str, bytes, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)"
    return ""


def gen_iface_reflect(self, t: str, what: str) -> None:
    # an error where what (type(), isinstance(), hash(), ...) needs the class of a value of
    # static type t that an interface is: only the run time knows its object's class (#487)
    if self.is_iface(t):
        self.err(f"{what} of a value of {typestr(t)} is not supported: its object's class is known only when the program runs (#487)" + self.object_note([t]))


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
    obj = self.mload('env', self.maddr('%ptr', o.v, '1', True))  # (its object: a closure's env's word, as icall takes it)
    code = self.mload('%ptr', self.maddr('%ptr', tab, str(k), True))
    return self.icall(code, obj, vals, f.ret)


def gen_iface_obj(self, v: Val) -> Val:
    # the object that a value of an interface holds (null for None), as identity sees it
    if not self.is_iface(v.t):
        return v
    if v.v in self.nn:
        return Val(self.mload('env', self.maddr('%ptr', v.v, '1', True)), "env")
    start = self.cur
    some = self.label()
    end = self.label()
    ph = Ins("phi", "env", "")
    self.incoming(ph, "null", start)
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, some)
    self.place(some)
    o = self.mload('env', self.maddr('%ptr', v.v, '1', True))
    self.incoming(ph, o, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "env")


def gen_iface_impl(self, t: str) -> str:
    # why a value of type t cannot be held by an interface, or "": it must be a reference, whose
    # pointer the box holds
    if t == "None" or t == "dyn" or is_opt(t) or lt(t) != "ptr" or t.startswith("fn[") or t == "exc" or t == "exctype":
        return f"an interface value cannot hold a value of type {typestr(t)} (it holds objects, containers, generators and files)"
    if is_union(unopt(t)):
        # (its box would stand for the object, which is and id() must see: convert each member)
        return f"a union's value converts once narrowed to one class (isinstance() first), not as {typestr(t)}"
    if is_callable(unopt(t)):
        return f"a {typestr(t)} is not an implementation: annotate a callback with Callable[[A], R] rather than a protocol with __call__"
    return ""


def gen_object_impl(self, t: str) -> str:
    # why a value of type t cannot be a value of object (OBJECT), or "": any value, but a
    # function or Callable value, an exception and a value of another interface (whose box is not
    # its object), each as to_object holds it
    u = unopt(t)
    if t == "dyn":
        return ""  # (an Any value: dyn_object)
    if self.refl_builtin_class(t) != "":
        return ""  # (a builtin class named, as its class object: to_object)
    if t.startswith("fn[") or is_callable(u):
        return f"a function or Callable value as a value of object is not supported yet: call it, or store a {typestr(t)} where one is expected"
    if t == "exc" or t == "exctype" or u == "exc" or u == "exctype" or (u in self.classes and self.classes[u].exc != ""):
        return "an exception (or its class) as a value of object is not supported yet"
    if self.is_iface(u):
        return f"a value of {typestr(u)} as a value of object is not supported: convert the object itself"
    if is_union(u):
        for m in umembers(u):
            why = self.object_impl(m)
            if why != "":
                return why
        return ""
    if u == "int" or u == "float" or u == "bool" or u == BIG or lt(u) == "ptr":
        return ""
    return f"a value of {typestr(t)} as a value of object is not supported"


def gen_to_object(self, v: Val) -> Val:
    # v as a value of object (OBJECT): None as None (null), a number as a box of the table of
    # its T | None and that T | None's own box, an optional value as None or what it holds, a
    # union's as the member its tag selects, a builtin class named as its class object, any
    # other value as a box of the table of its type and the value itself
    why = self.object_impl(v.t)
    if why != "":
        self.err(f"expected object, got {typestr(v.t)}: {why}")
    t = v.t
    if t == "None":
        return Val("null", OBJECT)
    if t == "dyn":
        return self.dyn_object(v)
    if self.refl_builtin_class(t) != "":
        return self.to_object(self.class_value_builtin(v))
    if t == "int" or t == "float" or t == "bool":
        b = self.coerce(v, self.ctype("opt", [t]))  # (its T | None's box, which never changes)
        return self.object_box(b.t, b.v)
    if t == BIG:
        b = self.coerce(v, BIGOPT)  # (a promoting int's box: bigints.py)
        return self.object_box(BIGOPT, b.v)
    u = unopt(t)
    if v.v in self.nn or (not is_opt(t) and u not in self.classes and not is_union(u)):
        if is_union(u):
            return self.union_object(Val(v.v, u))
        held = t if is_sopt(t) else u  # (a number's box is its own value: is_sopt)
        return self.object_box(held, v.v)
    # (None, which a value of a class, an optional value or a union with a class may be, as None)
    start = self.cur
    some = self.label()
    end = self.label()
    ph = Ins("phi", OBJECT, "")
    self.incoming(ph, "null", start)
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, some)
    self.place(some)
    if is_union(u):
        b = self.union_object(Val(v.v, u))
    else:
        held = t if is_sopt(t) else u
        b = self.object_box(held, v.v)
    self.incoming(ph, b.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), OBJECT)


def gen_dyn_object(self, v: Val) -> Val:
    # v, an Any value, as a value of object: None (its box) as None, any other value as a box of
    # the table of Any and v's own box, whose entries compile the operations of Any values
    # (dynamic.py), which know its type when the program runs
    start = self.cur
    some = self.label()
    end = self.label()
    ph = Ins("phi", OBJECT, "")
    self.incoming(ph, "null", start)
    self.cbr(self.ptr_cmp('==', v, Val(self.rtdata("pys_dyn_none_box"), "dyn")).v, end, some)
    self.place(some)
    b = self.object_box("dyn", v.v)
    self.incoming(ph, b.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), OBJECT)


def gen_object_dyn(self, v: Val) -> Val:
    # v, a value of object, as an Any value: None's box for None, else its object as an Any
    # value, which its table's entry makes of it as its type's value is made one (dynamic.py)
    e = mk("name", "_o", self.line, [])
    return self.iface_apply(v, "dyn()", [], "dyn", e, "Any", [], "dyn", v, v)


def gen_object_type_attr(self, v: Val, what: str) -> Val:
    # type(v).__name__ (what: __name__, __qualname__ or __module__) of a value of object: its
    # object's type's, by its table's entry; NoneType's (builtins) for None
    line = self.line
    e = mk("attr", what, line, [mk("call", "", line, [mk("name", "type", line, []), mk("name", "_o", line, [])])])
    return self.iface_apply(v, "type()." + what, [], "str", e, f"type().{what}", [], "type()." + what, v, v)


def gen_union_object(self, v: Val) -> Val:
    # v, a value of a union known not to be None, as a value of object: the member its tag
    # selects, converted as to_object converts it (the union's box is not that member's value)
    ms = umembers(v.t)
    end = self.label()
    ph = Ins("phi", OBJECT, "")
    for j in range(len(ms)):
        nxt = self.label() if j + 1 < len(ms) else ""
        if nxt != "":
            arm = self.label()
            self.cbr(self.utest(v, [ms[j]], False), arm, nxt)
            self.place(arm)
        x = self.to_object(self.uget(v, ms[j]))
        self.incoming(ph, x.v, self.cur)
        self.br(end)
        if nxt != "":
            self.place(nxt)
    self.place(end)
    return Val(self.phi(ph), OBJECT)


def gen_to_iface(self, v: Val, t: str) -> Val:
    # v as a value of interface t: a new box of the table of v's type for t and v itself; a
    # value of a class that is None stays None (null)
    if t == OBJECT:
        return self.to_object(v)  # (any value: its own rules)
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


def gen_object_box(self, held: str, obj: str) -> Val:
    # a new box of object's table of type held and obj, a value of that type (OBJECT), stored as
    # one: a number's T | None box made of a union's payload is a T | None by that store, as the
    # Lean checks of payload bits read a box's type from its uses (GUARDS.md)
    b = self.rt("pys_alloc", "ptr", ["i64 16"])
    self.mstore('%ptr', self.iface_table(held, OBJECT), b)
    self.mstore(held, obj, self.maddr('%ptr', b, '1', True))
    self.nn[b] = True
    return Val(b, OBJECT)


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
    line = tab.line
    derived = op in face.dargs
    m = self.classes[tab.iface].methods[op] if not derived else None
    ps = face.dargs[op] if derived else m.ptypes[1:] if m is not None else []
    ll = f"@cv.{self.ncv}"
    self.ncv += 1
    f = FnInfo("<interface>", ll, mk("def", "<interface>", line, []), "")
    f.params = ["_o"] + [f"_a{j}" for j in range(len(ps))]
    f.ptypes = [tab.impl] + ps
    for _ in f.params:
        f.defaults.append(mk("noann", "", line, []))
        f.dglob.append("")
        f.dtypes.append("")
    f.ret = face.dret[op] if derived else m.ret if m is not None else "None"
    f.mod = tab.mod
    f.home = tab.home
    o = mk("name", "_o", line, [])
    a: list[Node] = []
    for j in range(len(ps)):
        x = mk("name", f"_a{j}", line, [])
        a.append(x if m is None or m.npos < 0 or j + 1 < m.npos else mk("kw", m.params[j + 1], line, [x]))
    parts = op.split("|", 2) if derived else []
    bad = ""
    body: list[Node] = []
    if derived and parts[0] == "as":
        # (a narrowing, iface_narrowed: the object as the type the test proved, of an
        # implementation of that type; another's is never reached, as the test failed for it)
        nt = op[3:]
        held = unopt(tab.impl) if is_sopt(tab.impl) else tab.impl
        if held == BIG and nt == "int":
            # (as|bool and the others never reach a promoting int: their tests fail for it)
            bad = f"narrowing a value of {typestr(tab.iface)} to {typestr(self.union_type(['int', 'bool']))} by isinstance() is not supported where it may hold a promoting int (a module that opts in to promoting ints stored one), which {typestr(self.union_type(['int', 'bool']))} holds only within 64 bits"
        ok = held == nt or held == "dyn" or (is_union(nt) and held in umembers(nt)) or (nt == "type[object]" and held.startswith("type["))
        ok = ok or (held in self.classes and nt in self.classes and not self.is_iface(nt) and self.derives(held, nt))
        unreached = mk("raise", "", line, [mk("call", "", line, [mk("name", "SystemError", line, []), mk("str", f"a value of {typestr(tab.iface)} narrowed by isinstance() to {typestr(nt)} holds a {typestr(held)}", line, [])])])
        body = [unreached]
        e = mk("name", "_o", line, [])
        if ok and is_sopt(tab.impl):
            test = mk("cmp", "is", line, [mk("name", "_o", line, []), mk("None", "", line, [])])
            body = [mk("if", "", line, [test, mk("block", "", line, [clone(unreached)]), mk("block", "", line, [])]), mk("return", "", line, [e])]
        elif ok:
            body = [mk("return", "", line, [e])]
    elif derived and parts[0] == "is" and parts[1] != OBJECT:
        e = o
        body = object_is_body(tab.impl, parts[1], line)  # (x is a number: object_is_num)
    elif derived and (parts[0] == "==" or parts[0] == "!=") and (self.unequal_types(parts[2], tab.impl) or (tab.iface == OBJECT and never_equal(self, parts[2], tab.impl))):
        # (a number or str and an object of a class that defines no __eq__ or __ne__: CPython
        # compares them by identity, never the same, as unions' members are compared; and, held
        # by a value of object, values of builtin types of different kinds, a number and a str,
        # a list and a tuple, ...)
        e = mk("False" if parts[0] == "==" else "True", "", line, [])
    elif derived:
        e = with_line(clone(face.dexpr[op]), line)  # (an operation the protocol does not declare: iface_op)
        if tab.iface == OBJECT and (parts[0] == "==" or parts[0] == "!=") and e.kind == "cmp":
            ts = [tab.impl if x.s == "_o" else parts[2] for x in e.kids]
            if (eq_kind(self, ts[0]) == "type" or ts[0] == OBJECTC) and ts[1] in self.classes and ts[1] != OBJECTC and not self.is_iface(ts[1]):
                # (a class object, or object()'s object, and an object of a class: CPython asks the
                # class's __eq__ or __ne__, reflected, as the object on the left asks it first)
                e.kids = [e.kids[1], e.kids[0]]
    elif op in face.props:
        e = mk("attr", op, line, [o])
    elif op in BUILTIN_FORMS and len(ps) == 0 and (op in IMPLICIT or tab.impl not in self.classes or op == "__next__" or op == "__iter__"):
        e = mk("call", "", line, [mk("name", BUILTIN_FORMS[op], line, []), o])
    elif tab.impl not in self.classes and operator_form(op, len(a)) != "":
        e = operator_expr(op, o, a, line)  # (a builtin type's operator: o[a0], a0 in o, o + a0, ...)
    else:
        e = mk("call", "", line, [mk("attr", op, line, [o])] + a)
    if len(body) == 0:
        body = [mk("return", "", line, [e])]
    if e.kind == "assign" or e.kind == "del":
        body = [e]  # (o[a0] = a1, del o[a0]: statements, whose operation returns None)
    if ((op in face.implicit and (op == "__repr__" or op == "__str__")) or op == "format()") and (is_gen(tab.impl) or tab.impl == "file"):
        # (Pystachy prints neither: a list of the interface's values has a repr that may never
        # print one, which CPython prints by its address, <generator object f at 0x...>; and
        # format() of one is its str())
        what = "a generator" if is_gen(tab.impl) else "a file"
        msg = mk("str", f"{'format' if op == 'format()' else op[2:-2]}() of {what} held by a value of {typestr(tab.iface)} is not supported", line, [])
        body = [mk("raise", "", line, [mk("call", "", line, [mk("name", "NotImplementedError", line, []), msg])])]
    f.node.kids = [mk("params", "-1,-1", line, []), mk("noann", "", line, []), mk("block", "", line, body)]
    self.making.append(f"making the table of {typestr(tab.impl)} as {typestr(tab.iface)} (for {face.dshow[op] if derived else op}), converted at {where(line)}")
    if bad != "":
        self.err(bad)
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


def with_line(n: Node, line: int) -> Node:
    # n (a copy of a node made where code asked for an interface's operation: iface_op), its
    # nodes placed at line, where an implementation's table is made
    n.line = line
    for k in n.kids:
        with_line(k, line)
    return n


def gen_iface_cmp(self, op: str, a: Val, b: Val) -> Val:
    # a comparison of which an operand is a value of an interface: is and is not compare the
    # objects the boxes hold (None's null), as their identity is the objects'; == and != compare
    # the objects as Python does (iface_eq); an ordering is not supported yet
    if (op == "is" or op == "is not") and (self.is_object(a.t) or self.is_object(b.t)):
        r = self.object_is(a, b) if self.is_object(a.t) else self.object_is(b, a)
        return r if op == "is" else Val(self.scalar('xor', [Val(r.v, 'bool'), Val('true', 'bool')]), "bool")
    if op == "is" or op == "is not":
        u = b.t if self.is_iface(a.t) else a.t
        if is_union(unopt(u)):
            # (a union's box is not its object, which only its member's tag tells)
            self.err(f"comparing a value of {typestr(a.t if self.is_iface(a.t) else b.t)} with a value of {typestr(u)} by '{op}' is not supported: narrow the union to one class first")
        if not self.isref(a.t) or not self.isref(b.t):
            return Val("false" if op == "is" else "true", "bool")
        return self.ptr_cmp('==' if op == 'is' else '!=', self.iface_obj(a), self.iface_obj(b))
    if op == "==" or op == "!=":
        return self.iface_eq(op, a, b)
    t = a.t if self.is_iface(a.t) else b.t
    self.err(f"comparing values of {typestr(t)} with {op} is not supported: their objects' classes are known only when the program runs (compare with ==, != or is)" + self.object_note([a.t, b.t]))
    return Val("false", "bool")


def gen_object_is(self, x: Val, y: Val) -> Val:
    # x is y, x a value of object (OBJECT): None is only None; an object of a class, a str, a
    # container or a class object is itself (the box's second word); a number is, as PyPy has it,
    # any equal number of its type (an int and a promoting int both being ints, a float by its
    # bits), which CPython's small ints, bools and constants are, and other equal numbers may or
    # may not be (docs/language/compatibility.md); another value of object by its own value
    t = y.t
    if self.refl_builtin_class(t) != "":
        y = self.class_value_builtin(y)  # (a builtin class named: its class object)
        t = y.t
    if t == "None":
        return self.ptr_cmp('==', x, y)
    if self.is_object(t):
        return self.object_is_object(x, y)
    if t == "int" or t == "float" or t == "bool" or t == BIG:
        return self.object_is_num(x, y)
    if is_sopt(t):
        # (None, or the number it holds)
        if y.v in self.nn:
            return self.object_is_num(x, self.deref(y))
        end = self.label()
        some = self.label()
        ph = Ins("phi", "bool", "")
        self.incoming(ph, self.ptr_cmp('==', x, Val('null', 'None')).v, self.cur)
        self.cbr(self.ptr_cmp('==', y, Val('null', 'None')).v, end, some)
        self.place(some)
        r = self.object_is_num(x, self.deref(y))
        self.incoming(ph, r.v, self.cur)
        self.br(end)
        self.place(end)
        return Val(self.phi(ph), "bool")
    if is_union(unopt(t)) or t == "dyn":
        # (None, or the member its tag selects, or the value an Any value is, as a value of object:
        # a number in a new box, which object_is_object's entry compares by its value)
        return self.object_is_object(x, self.to_object(y))
    if self.is_iface(t):
        return self.ptr_cmp('==', self.iface_obj(x), self.iface_obj(y))
    if self.isref(t):
        return self.ptr_cmp('==', self.iface_obj(x), y)  # (not held by a value of object, it is never x)
    self.err(f"comparing a value of object with a value of {typestr(t)} by 'is' is not supported")
    return Val("false", "bool")


def gen_object_is_object(self, x: Val, y: Val) -> Val:
    # x is y of two values of object: the same object (or both None), else, where neither is
    # None, by x's table's entry, which asks whether y is the object of x's type that it holds
    # (object_is: a number by its value)
    same = self.ptr_cmp('==', self.iface_obj(x), self.iface_obj(y))
    line = self.line
    end = self.label()
    more = self.label()
    ph = Ins("phi", "bool", "")
    self.incoming(ph, "true", self.cur)
    self.cbr(same.v, end, more)
    self.place(more)
    for v in [x, y]:
        if v.v not in self.nn:
            some = self.label()
            self.incoming(ph, "false", self.cur)
            self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, some)
            self.place(some)
    e = mk("cmp", "is", line, [mk("name", "_a0", line, []), mk("name", "_o", line, [])])
    r = self.iface_op(Val(x.v, OBJECT), "is|" + OBJECT, [OBJECT], "bool", e, "its object is object", [Val(y.v, OBJECT)])
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "bool")


def gen_object_is_num(self, x: Val, y: Val) -> Val:
    # x is y, x a value of object and y an int, a float or a bool: whether x holds a number of
    # y's type equal to it (object_is), by x's table's entry (an entry of another type: False)
    line = self.line
    e = mk("cmp", "is", line, [mk("name", "_o", line, []), mk("name", "_a0", line, [])])
    if x.v in self.nn:
        return self.iface_op(x, "is|" + y.t, [y.t], "bool", e, f"its object is {typestr(y.t)}", [y])
    end = self.label()
    some = self.label()
    ph = Ins("phi", "bool", "")
    self.incoming(ph, "false", self.cur)
    self.cbr(self.ptr_cmp('==', x, Val('null', 'None')).v, end, some)
    self.place(some)
    r = self.iface_op(x, "is|" + y.t, [y.t], "bool", e, f"its object is {typestr(y.t)}", [y])
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "bool")


def eq_kind(self, t: str) -> str:
    # the kind of builtin value that a value of type t is, as CPython's == finds values of two
    # kinds unequal (each kind's __eq__ declines the other's): "num" (a number, also a complex
    # one), "str", "bytes", "list", "tuple", "dict", "set" (a set or a frozenset), "None", "type"
    # (a class object, equal only to itself); "" for a type whose values' classes decide (an
    # object of a class of the program, a value of an interface) or another (a file, ...)
    u = unopt(t)
    if u == "int" or u == "float" or u == "bool" or u == BIG or u == COMPLEXC:
        return "num"
    if u in self.classes or self.is_iface(u):
        return ""
    if u == "str" or u == "bytes" or u == "None":
        return u
    if is_list(u) or is_dict(u):
        return "list" if is_list(u) else "dict"
    if is_tuple(u) or is_vtuple(u):
        return "tuple"
    if is_set(u) or u == EMPTYFS:
        return "set"
    return "type" if is_clsval(u) or u == "exctype" else ""


def never_equal(self, a: str, b: str) -> bool:
    # are a value of type a (an optional one not None) and one of type b, which an implementation
    # of object compares (iface_eq), never equal, as values of builtin types of two kinds are
    return eq_kind(self, a) != "" and eq_kind(self, b) != "" and eq_kind(self, a) != eq_kind(self, b)


def num_kind(t: str) -> str:
    # the Python type of a number of type t, as identity tells numbers apart (object_is): "int"
    # for an int and a promoting int, "float", "bool"; "" for any other type
    if t == "int" or t == BIG:
        return "int"
    return t if t == "float" or t == "bool" else ""


def object_is_body(impl: str, h: str, line: int) -> list[Node]:
    # the body of the entry of implementation impl for x is h, h a number of type h (object_is_num):
    # a number of its kind is h where it equals it (a float by its bits: NaN is a NaN, 0.0 is not
    # -0.0), any other value never
    held = unopt(impl) if is_sopt(impl) else impl
    no = mk("return", "", line, [mk("False", "", line, [])])
    o = mk("name", "_o", line, [])
    a = mk("name", "_a0", line, [])
    if impl == "dyn":
        return [mk("return", "", line, [mk("cmp", "is", line, [o, a])])]  # (an Any value's identity: dynamic.py)
    if num_kind(held) == "" or num_kind(held) != num_kind(h):
        return [no]
    same = mk("cmp", "==", line, [o, a])
    if held == "float":
        zero = mk("cmp", "!=", line, [clone(o), mk("float", "0.0", line, [])])
        sign = mk("cmp", "==", line, [mk("call", "", line, [mk("name", "str", line, []), clone(o)]), mk("call", "", line, [mk("name", "str", line, []), clone(a)])])
        nans = mk("boolop", "and", line, [mk("cmp", "!=", line, [clone(o), clone(o)]), mk("cmp", "!=", line, [clone(a), clone(a)])])
        same = mk("boolop", "or", line, [mk("boolop", "and", line, [same, mk("boolop", "or", line, [zero, sign])]), nans])
    body = [mk("return", "", line, [same])]
    if is_sopt(impl):
        # (a number's box, which is never None here: object_impl)
        test = mk("cmp", "is", line, [clone(o), mk("None", "", line, [])])
        body = [mk("if", "", line, [test, mk("block", "", line, [no]), mk("block", "", line, [])])] + body
    return body


def gen_iface_op(self, v: Val, key: str, args: list[str], ret: str, e: Node, show: str, vals: list[Val]) -> Val:
    # the call of operation key of v's interface, which no method of the protocol declares (Iface's
    # dargs), with v's object and vals: each implementation's entry returns expression e of its
    # object (_o) and arguments (_a0, ...) of types args, as a value of type ret (iface_adapter;
    # show names the operation in its errors). v is known not to be None. Code that dry() types is
    # dropped, and asks for no operation
    if self.drying > 0:
        return Val("undef", ret)
    face = self.ifaces[v.t]
    if key not in face.dargs:
        face.ops.append(key)
        face.dargs[key] = args
        face.dret[key] = ret
        face.dexpr[key] = e
        face.dshow[key] = show
    k = face.ops.index(key)
    face.used[k] = True
    tab = self.mload('%ptr', v.v)
    obj = self.mload('env', self.maddr('%ptr', v.v, '1', True))
    code = self.mload('%ptr', self.maddr('%ptr', tab, str(k), True))
    return self.icall(code, obj, vals, ret)


def gen_iface_apply(self, v: Val, key: str, args: list[str], ret: str, e: Node, show: str, vals: list[Val], none: str, a: Val, b: Val) -> Val:
    # operation key (iface_op) of interface value v's object where it is one, and the operation
    # none on None itself where v is None, as CPython runs it there (iface_none), as a value of
    # type ret
    if v.v in self.nn:
        return self.iface_op(v, key, args, ret, e, show, vals)
    yes = self.label()
    no = self.label()
    end = self.label()
    ph = Ins("phi", ret, "")
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, no, yes)
    self.place(no)
    r = self.iface_none(none, a, b)
    if not self.term:
        self.incoming(ph, r.v, self.cur)
        self.br(end)
    self.place(yes)
    r = self.iface_op(v, key, args, ret, e, show, vals)
    if not self.term:
        self.incoming(ph, r.v, self.cur)
        self.br(end)
    self.place(end)
    if len(ph.a) == 0:
        self.unreachable()
        return Val("undef", ret)
    return Val(self.phi(ph), ret)


def gen_iface_none(self, none: str, a: Val, b: Val) -> Val:
    # the value of operation none (iface_apply) where the interface value is None: a == b or
    # a != b of None with the other operand ("==" or "!=", with a or b the null), hash(None),
    # format(None, spec) of spec's value a ("format"), isinstance() of None and a class ("false")
    if none == "==" or none == "!=":
        return self.cmp2(none, a, b)
    if none == "hash":
        return self.hash_value(Val("null", "None"))
    if none == "format":
        self.guard(self.num_cmp('!=', Val(self.mload('int', a.v), "int"), Val('0', "int")).v, "TypeError: unsupported format string passed to NoneType.__format__")
        return Val(self.sconst("None"), "str")
    if none == "dyn":
        return Val(self.rtdata("pys_dyn_none_box"), "dyn")  # (None as an Any value: object_dyn)
    if none.startswith("type()."):
        return Val(self.sconst("builtins" if none == "type().__module__" else "NoneType"), "str")  # (object_type_attr)
    return Val("false", "bool")


def gen_iface_eq(self, op: str, a: Val, b: Val) -> Val:
    # a == b or a != b (op) where an operand is a value of an interface: its object compared with
    # the other operand as Python compares them, by the entry of each implementation's table that
    # compiles that comparison for the object's class (a value of an interface for the other
    # operand is its object, compared by its own table's entry in turn: the innermost comparison
    # is of two classes, with their __eq__ or __ne__, reflected methods and identity), and None's
    # where the value is None
    left = self.is_iface(a.t)
    x = a if left else b
    other = b if left else a
    if self.is_object(x.t) and is_union(unopt(other.t)) and self.object_impl(other.t) == "":
        # (a union's value as a value of object, its member as itself: compared by both tables'
        # entries, as no implementation's own comparison takes a closed union)
        other = self.to_object(other)
    if "?" in other.t:
        self.err(f"comparing a value of {typestr(x.t)} with a {typestr(other.t)} by {op} is not supported: annotate the empty container")
    none = other.t == "None"
    line = self.line
    o = mk("name", "_o", line, [])
    y = mk("None", "", line, []) if none else mk("name", "_a0", line, [])
    e = mk("cmp", op, line, [o, y] if left else [y, o])
    key = f"{op}|{'l' if left else 'r'}|{other.t}"
    show = f"its object {op} {typestr(other.t)}" if left else f"{typestr(other.t)} {op} its object"
    nul = Val("null", "None")
    return self.iface_apply(x, key, [] if none else [other.t], "bool", e, show, [] if none else [other], op, nul if left else other, other if left else nul)


def gen_iface_hash(self, v: Val) -> Val:
    # hash(v) of a value of an interface: its object's, by its class's __hash__ (TypeError for an
    # unhashable class, as CPython's) or identity; None's where it is None
    e = mk("call", "", self.line, [mk("name", "hash", self.line, []), mk("name", "_o", self.line, [])])
    return self.iface_apply(v, "hash()", [], "int", e, "hash()", [], "hash", v, v)


def gen_iface_format(self, v: Val, sv: Val) -> Val:
    # format(v, spec), spec's value sv, of a value of an interface: its object's, by its class's
    # __format__, or str() where spec is empty; None's where it is None (an empty spec only)
    line = self.line
    e = mk("call", "", line, [mk("name", "format", line, []), mk("name", "_o", line, []), mk("name", "_a0", line, [])])
    return self.iface_apply(v, "format()", ["str"], "str", e, "format()", [sv], "format", sv, sv)


def gen_iface_held(self, t: str) -> bool:
    # does tuple type t hold a value of an interface, also in a tuple it holds: its hash is then
    # its items' hashes mixed item by item, which runtime.c's walks of a descriptor cannot compute
    for x in targs(t):
        if self.is_iface(unopt(x)) or (is_tuple(unopt(x)) and self.iface_held(unopt(x))):
            return True
    return False


def gen_iface_classes(self, c: Node) -> list[str]:
    # the classes that c, isinstance()'s second argument for a value of an interface, names: a
    # class of the program (not a protocol), object, a builtin type of BUILTIN_TESTS that the
    # module does not bind, or a tuple or union of these; ["!"] for another type, which an
    # implementation's entry might not see as the caller's code does
    if c.kind == "tuple" or (c.kind == "binop" and c.s == "|"):
        out: list[str] = []
        for x in c.kids:
            xs = self.iface_classes(x)
            if "!" in xs:
                return xs
            out.extend([y for y in xs if y not in out])
        return out
    if c.kind == "name" and c.s in self.classes and not self.is_iface(c.s) and c.s not in self.ifgeneric:
        return [c.s]
    if c.kind == "name" and c.s == "object" and not self.bound("object"):
        return ["object"]
    if c.kind == "name" and c.s in BUILTIN_TESTS and not self.bound(c.s):
        return [c.s]
    return ["!"]


def gen_iface_isinst(self, v: Val, c: Node) -> Val:
    # isinstance(v, c) of a value of an interface: of its object, by the entry of each
    # implementation's table that tests its class (a test of the class tag where it has
    # subclasses); False for None, but isinstance(None, object)
    cs = self.iface_classes(c)
    if "!" in cs:
        self.err(f"isinstance() of a value of {typestr(v.t)} is only supported with the program's classes and the builtin types {', '.join(BUILTIN_TESTS)} as its second argument (or a tuple of them): the object's class is known only when the program runs")
    if "object" in cs:
        return Val("true", "bool")
    line = self.line
    e = mk("call", "", line, [mk("name", "isinstance", line, []), mk("name", "_o", line, []), clone(c)])
    key = "isinstance()|" + ",".join(cs)
    pcall = self.pcall
    r = self.iface_apply(v, key, [], "bool", e, "isinstance()", [], "isinstance", v, v)
    # (its entries test the object's class and run no code of the program, so an attribute that
    # the test read keeps its fact, which narrows it: unions.py's narrows_path)
    self.pcall = pcall
    return r


def gen_iface_narrow(self, c: Node) -> str:
    # the type that a value of an interface holds where isinstance(x, c) is true, which its reads
    # take (iface_narrowed): c's, where it names one class that has one layout (not a class
    # template's, whose objects' types its specializations are), bool, float, str or bytes; int
    # | bool for int, whose test a bool passes (keeping its own repr and truth), but in a module
    # that opts in to promoting ints, whose union would hold 64-bit ints; any class's class
    # object for type; "" otherwise (a container's item types are not known)
    cs = self.iface_classes(c)
    if len(cs) != 1 or cs[0] == "!" or cs[0] == "object" or cs[0] in self.tmpl:
        return ""
    k = cs[0]
    if k in self.classes:
        return k
    if k == "int":
        return "" if self.int_policy(self.line) else self.union_type(["int", "bool"])
    if k == "bool" or k == "float" or k == "str" or k == "bytes":
        return k
    return "type[object]" if k == "type" else ""


def gen_iface_narrowed(self, v: Val, nt: str) -> Val:
    # v, a value of an interface that isinstance() proved holds a value of type nt (not None):
    # an object of a class of the program is held as itself; a number, a str or a class object
    # by its own table's entry, which knows how its type holds it (a number in its T | None's box)
    if nt in self.classes and not self.is_iface(nt) and not self.is_object(v.t):
        return Val(self.mload(nt, self.maddr('%ptr', v.v, '1', True)), nt)
    # (a value of object's object, by its entry, which returns it at its own class or a base of
    # it: what the call declares, as a proof of the read sees it)
    e = mk("name", "_o", self.line, [])
    if is_union(nt):
        # (int | bool, of isinstance(x, int): a bool test, then the bool or the int that the
        # entry of that type returns, made the union's member here, where the union's tag is the
        # one this code gives it; an entry returns no union, whose tag only its own code knows)
        line = self.line
        isb = self.iface_isinst(v, mk("name", "bool", line, []))
        yes = self.label()
        no = self.label()
        end = self.label()
        ph = Ins("phi", nt, "")
        self.cbr(isb.v, yes, no)
        for m in ["bool", "int"]:
            self.place(yes if m == "bool" else no)
            r = self.coerce(self.iface_op(v, "as|" + m, [], m, clone(e), f"narrowing by isinstance() to {m}", []), nt)
            self.incoming(ph, r.v, self.cur)
            self.br(end)
        self.place(end)
        return Val(self.phi(ph), nt)
    return self.iface_op(v, "as|" + nt, [], nt, e, f"narrowing by isinstance() to {typestr(nt)}", [])
