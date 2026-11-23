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
from src.pystachy_compiler.diagnostics import ClassBoxes, NeedHandlers, NeedHierarchy, NeedSliceEH, Rejoin, TupleBoxes, dynamic_program, where
from src.pystachy_compiler.frames import Frame
from src.pystachy_compiler.ir import Data, Ins, Val, tmpname
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.names import MAPVIEW, OBJECT, SEQVIEW, SETVIEW, VIEWSHOW, short
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.symbols import ClassInfo, FnInfo
from src.pystachy_compiler.specs import BIG, BIGOPT, COMPLEXC, EMPTYFS, OBJECTC, RANGEC, SPECSHOW, is_excname
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import clone, elem, gelem, identity_abi, is_callable, is_clsval, is_dict, is_fset, is_gen, is_list, is_opt, is_set, is_sopt, is_tuple, is_union, is_vtuple, lib_file, lt, numeric_identity, selem, targs, tname, typestr, umembers, unopt

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
BUILTIN_TESTS = ["int", "float", "bool", "str", "bytes", "list", "dict", "tuple", "set", "frozenset", "type", "complex", "range"]

# the builtin types of BUILTIN_TESTS whose objects are those of a class of lib/ (builtin_backed),
# which a test narrows such a value to (iface_narrow)
BUILTIN_LIB = {"complex": COMPLEXC, "range": RANGEC}

# the read-only view (names.py's VIEWSHOW) that a test of each builtin container type narrows a
# value of object to (iface_narrow): its items are values of object, read through the view's
# table, whose entries read the container the value holds, of whatever type (view_defs)
VIEW_OF = {"list": SEQVIEW, "tuple": SEQVIEW, "set": SETVIEW, "frozenset": SETVIEW, "dict": MAPVIEW}

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
        self.ifspecs[key] = [c if c == OBJECT or c in VIEWSHOW else f"{c}-i{len(self.ifspecs) + 1}", c] + ts
    name = self.ifspecs[key][0]
    self.ifmade[key] = name
    line = self.line
    if c == OBJECT:
        # object: no operation of its own (OBJECT)
        node = mk("class", name, line, [mk("block", "", line, [])])
    elif c in VIEWSHOW:
        # a view of a container that a value of object holds: the operations that read it
        node = mk("class", name, line, [mk("block", "", line, view_defs(self, c, line))])
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
    SPECSHOW[name] = "object" if c == OBJECT else VIEWSHOW[c] if c in VIEWSHOW else f"{short(c)}[{', '.join([typestr(t) for t in ts])}]"
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
        if spec[1] == ITERATOR or spec[1] == ITERABLE or spec[1] == OBJECT or spec[1] in VIEWSHOW or spec[1] in self.ifgeneric:
            self.iface_of(spec[1], spec[2:])


def gen_object_iface(self) -> str:
    # the interface that an object annotation names in a variable, a field, a container's items
    # or a result (OBJECT), made by the first that names it
    return self.iface_of(OBJECT, [])


def gen_iface_use(self, f: FnInfo) -> None:
    # a call of method f of an interface: its table slot is used (iface_finish compiles it); a
    # view's, object's (view_slot)
    if self.is_view(f.cls):
        self.ifaces[OBJECT].used[view_slot(self, f)] = True
        return
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
        if self.is_view(t):
            ops = "x[i], index(), count()" if t == SEQVIEW else "x[key], get(), keys(), values(), items()" if t == MAPVIEW else ""
            return f" ({typestr(t)} is a read-only view of {view_kind(t)} that a value of object holds, which isinstance() narrowed it to: it takes len(), iteration, in, {ops + ', ' if ops != '' else ''}str(), repr(), ==, != and is, which give its items as values of object, and changes nothing; change the container through a variable of its own type)"
        if t == OBJECT and self.int_policy(self.line):
            # (iface_narrow: an int there is a promoting int, which a bool that passes the test is not)
            return " (narrow a value of object with isinstance() to float, bool, str, bytes, list, tuple, dict, set, frozenset, type or a class of the program first, not to int in a module that opts in to promoting ints: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise)"
        if t == OBJECT:
            return " (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type or a class of the program first: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise)"
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
    # (a view's box is a value of object's, whose table has the view's operations: view_slot)
    k = view_slot(self, f) if self.is_view(f.cls) else self.ifaces[f.cls].ops.index(f.name)
    o = self.expr(args[0], "")
    vals = [self.expr(a, "") for a in args[1:]]
    if (f.cls == MAPVIEW or f.cls == SETVIEW) and (f.name == "__getitem__" or f.name == "get" or f.name == "__contains__"):
        view_hash(self, vals[0])
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
    # function or Callable value (whose value is made anew where it is converted, and has no
    # repr() or hash() of its own here), each as to_object holds it: an exception class as its
    # class object (exctype), a value of another interface as its object (protocol_object)
    u = unopt(t)
    if t == "dyn":
        return ""  # (an Any value: dyn_object)
    if self.refl_builtin_class(t) != "":
        return ""  # (a builtin class named, as its class object: to_object)
    if t.startswith("fn[") or is_callable(u):
        return f"a function, bound method or lambda (a Callable value) as a value of object is not supported yet: call it, or store a {typestr(t)} where one is expected"
    if self.is_view(u) or self.is_iface(u):
        return ""  # (a view of a value of object's container: that value, view_slot; a protocol's value: its object, protocol_object)
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
    # other value as a box of the table of its type and the value itself (a value of object, or a
    # view of one's container, as itself: a cast of its box, view_slot)
    if self.is_object(v.t):
        return v
    if self.is_view(v.t):
        return self.cast(v, OBJECT, "view")
    if self.is_iface(unopt(v.t)):
        return protocol_object(self, Val(v.v, unopt(v.t)))
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


def protocol_object(self, v: Val) -> Val:
    # v, a value of a protocol, as a value of object: None as None, else its object, by the entry
    # of its implementation's table, which makes a value of object of it as to_object makes one of
    # a value of its type (the protocol's box is not the object's: its table is the protocol's)
    self.object_iface()  # (object's, which a program that stores no value as object has not made)
    e = mk("name", "_o", self.line, [])
    return self.iface_apply(v, "object()", [], OBJECT, e, "object", [], "object", v, v)


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
    if self.is_view(t):
        return to_view(self, v, t)
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
    f.ikey = f"{tab.iface}|{tab.impl}|{op}"  # (its joins' own key, as the other entries made at its line have theirs: Gen.fnkey)
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
    tried = ""  # (the attempt of a comparison that may not compile: eq_how)
    note = ""  # (what an error of the entry's comparison says to do: eq_note)
    body: list[Node] = []
    if derived and parts[0] == "as":
        # (a narrowing, iface_narrowed: the object as the type the test proved, of an
        # implementation of that type; another's is never reached, as the test failed for it)
        nt = op[3:]
        held = unopt(tab.impl) if is_sopt(tab.impl) else tab.impl
        if held == BIG and nt == "int":
            # (as|bool and the others never reach a promoting int: their tests fail for it)
            bad = f"narrowing a value of {typestr(tab.iface)} to {typestr(self.union_type(['int', 'bool']))} by isinstance() is not supported where it may hold a promoting int (a module that opts in to promoting ints stored one), which {typestr(self.union_type(['int', 'bool']))} holds only within 64 bits"
        if held == "exctype" and nt == "type[object]":
            # (an exception class, whose test of type passes: its class object is exceptions.py's,
            # which no type[object], a class's reflection record, is)
            bad = f"narrowing a value of {typestr(tab.iface)} to type by isinstance() is not supported where it may hold an exception class (a {typestr(held)}): test it with isinstance() of the classes it may be, or compare it with 'is'"
        ok = held == nt or held == "dyn" or (is_union(nt) and held in umembers(nt)) or (nt == "type[object]" and held.startswith("type["))
        ok = ok or (held in self.classes and nt in self.classes and not self.is_iface(nt) and self.derives(held, nt))
        # (an exception object of a class of the program as the exception that raises it, as a
        # builtin exception class's test narrows it, BaseException; a caught exception, of type
        # BaseException, as the object of a class of the program that the test proved it raises)
        wrap = nt == "exc" and held in self.classes and self.classes[held].exc != ""
        unwrap = held == "exc" and nt in self.classes and self.classes[nt].exc != ""
        unreached = mk("raise", "", line, [mk("call", "", line, [mk("name", "SystemError", line, []), mk("str", f"a value of {typestr(tab.iface)} narrowed by isinstance() to {typestr(nt)} holds a {typestr(held)}", line, [])])])
        body = [unreached]
        e = mk("name", "_o", line, [])
        if ok and is_sopt(tab.impl):
            test = mk("cmp", "is", line, [mk("name", "_o", line, []), mk("None", "", line, [])])
            body = [mk("if", "", line, [test, mk("block", "", line, [clone(unreached)]), mk("block", "", line, [])]), mk("return", "", line, [e])]
        elif ok:
            body = [mk("return", "", line, [e])]
        elif wrap or unwrap:
            body = [mk("return", "", line, [mk("call", "", line, [mk("name", "__pys_exc_user" if wrap else "__pys_exc_obj", line, []), clone(e)])])]
    elif derived and parts[0] == "is" and parts[1] != OBJECT:
        e = o
        body = object_is_body(tab.impl, op[3:], line, self.dyn_boxable(op[3:]) == "")  # (x is a number, object_is_num, or a reference: object_is_held)
    elif derived and parts[0] == "view":
        e = o
        body = view_body(self, parts[1], parts[2], tab.impl, line)  # (a view's operation on the container: view_slot)
    elif derived and op == "hash?()":
        e = o
        body = [with_line(s, line) for s in Parser(Lexer("def _hash():\n" + hashed_source(self, tab.impl), 1).file()).module().kids[0].kids[2].kids]
    elif derived and parts[0] == "conv":
        e = o
        body = [with_line(s, line) for s in Parser(Lexer("def _conv():\n" + conversion_source(self, parts[1], tab.impl), 1).file()).module().kids[0].kids[2].kids]
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
        how = eq_how(self, tab, op, e)
        if how != "":
            tried = "objeq:" + self.stable(f"{tab.iface}|{tab.impl}|{op}")
        if tried != "" and tried in self.xnot:
            # (a comparison of two types that no comparison of the compiler takes, a pass found:
            # CPython's default answer, or the other operand's method that CPython calls reflected)
            e = eq_default_expr(how, e, line)
        note = eq_note(self, tab, op, e)
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
    if note != "":
        self.making.append(note)  # (said after the table's making, as an error says the innermost first: err)
    self.making.append(f"making the table of {typestr(tab.impl)} as {typestr(tab.iface)} (for {face.dshow[op] if derived else op}), converted at {where(line)}")
    if bad != "":
        self.err(bad)
    fr = self.save()
    self.modlevel = False
    self.lenient = False
    self.line = line
    if tried != "" and tried not in self.xnot:
        eq_try(self, f, body, tried, fr)
    else:
        self.function(f, body)
    self.restore(fr)
    if note != "":
        self.making.pop()
    self.making.pop()
    return ll


def eq_try(self, f: FnInfo, body: list[Node], tried: str, fr: Frame) -> None:
    # compile entry f, a comparison that eq_default could answer, as an attempt (Gen.xtry) named
    # tried: where it does not compile, this pass goes on, to find the other comparisons that do
    # not (an error after it starts the next pass instead: gen_err), and ends, and the next pass
    # compiles CPython's default answer from the start (iface_adapter); the partial compilation
    # of the entry is dropped with this pass
    previous = self.xtry
    making = len(self.making)
    sel = self.selfcls
    self.xtry = tried
    try:
        self.function(f, body)
    except Rejoin as retry:
        if isinstance(retry, NeedHandlers) or isinstance(retry, NeedHierarchy) or isinstance(retry, ClassBoxes) or isinstance(retry, NeedSliceEH) or isinstance(retry, TupleBoxes) or tried not in self.newx:
            raise
        self.restore(fr)
        while len(self.making) > making:
            self.making.pop()
        self.selfcls = sel
    self.xtry = previous


def eq_family(self, t: str, op: str) -> str:
    # the family of a value of type t for op (== or !=) with a value of another family, which
    # CPython's comparisons of the two kinds both decline (NotImplemented), so that it compares
    # them by identity: "num" (a number), "str", "bytes", "None", "list" and "dict" (an object of a
    # class that derives from one too), "tuple" (a NamedTuple's object too), "set" (a frozenset
    # too), "range", "dc:C" (an object of dataclass C, whose generated __eq__ declines another
    # class's), "id:T" (a value equal only to itself: a generator, a class object, an exception,
    # an enum member, object()'s object, an object of a class without a method for op); "" where
    # the method that CPython calls for op is the program's (user_cmp), which alone answers, or
    # for another type, whose comparison is the compiler's own
    u = unopt(t) if is_sopt(t) else t
    if u == "int" or u == "float" or u == "bool" or u == BIG or u == COMPLEXC:
        return "num"
    if u == "str" or u == "bytes" or u == "None":
        return u
    if u == RANGEC:
        return "range"
    if is_list(u):
        return "list"
    if is_dict(u):
        return "dict"
    if is_set(u) or u == EMPTYFS:
        return "set"
    if is_tuple(u) or is_vtuple(u):
        return "tuple"
    if is_gen(u) or is_clsval(u) or u == "exctype" or u == "exc":
        return "id:" + u
    if u not in self.classes or user_cmp(self, u, op):
        return ""
    if self.bkind(u) != "":
        return self.bkind(u)  # ("list" or "dict": the builtin's own comparison, which its class keeps)
    if u in self.nts:
        return "tuple"
    if self.is_dc(u) and "no-eq" not in self.classes[u].dcopts:
        return "dc:" + u
    return "id:" + u


def user_method(self, c: str, m: str) -> bool:
    # does class c, or a class it derives from (its template's, for a specialization), define
    # method m (not one the compiler writes for a dataclass, nor one of lib/ that declines what
    # it does not take: lib_declines)
    seen: dict[str, bool] = {}
    todo = [c]
    while len(todo) > 0:
        x = todo.pop()
        if x in seen or x not in self.classes:
            continue
        seen[x] = True
        ci = self.classes[x]
        if m in ci.methods and not ci.methods[m].synthetic:
            return not lib_declines(self, ci.methods[m])
        todo.extend([ci.base, ci.origin] + ci.roles)
    return False


def lib_declines(self, f: FnInfo) -> bool:
    # is f a comparison method of a class of lib/ annotated to take one type (range's, a deque's,
    # a date's, a timedelta's, a weak reference's): it stands for a method of CPython's type, which
    # returns NotImplemented for a value of another type, so that the other operand's method, else
    # identity, answers (as cmp_pick skips it)
    t = f.ptypes[1] if len(f.ptypes) == 2 else ""
    return lib_file(f.node.line, self.libdir) and t != "" and t != "dyn" and not self.is_object(t)


def user_cmp(self, c: str, op: str) -> bool:
    # is the method that CPython calls for an object of class c op a value (== or !=) one of the
    # program: an __eq__ that c defines or inherits for ==; for !=, an __ne__ so defined, or c's
    # __eq__, which object's __ne__ inverts, but not for a class that derives from list or dict,
    # or a NamedTuple, whose __ne__ is the builtin's (it declines another kind, and identity then
    # answers: eq_family). (An IntEnum's, IntFlag's or StrEnum's are lib/enum.py's, which take
    # any value)
    if user_method(self, c, "__ne__" if op == "!=" else "__eq__"):
        return True
    return op == "!=" and self.bkind(c) == "" and c not in self.nts and user_method(self, c, "__eq__")


def eq_default(self, a: str, b: str, op: str) -> str:
    # CPython's answer to a op b (op == or !=), a of type a and b of type b, where the comparison
    # of a declines b (eq_family): "swap" where the method that CPython calls for b is the
    # program's (user_cmp), reflected, as b op a calls it first; where the comparison of b
    # declines a too, "is" where one object may have both types (one class, or a class and a
    # class it derives from), "false" where none may; "" where a comparison decides (of numbers,
    # of strs, of containers item by item, a dataclass's, a's method of the program)
    fa = eq_family(self, a, op)
    fb = eq_family(self, b, op)
    if fa != "" and fb == "" and b in self.classes and user_cmp(self, b, op):
        return "swap"
    if fa == "" or fb == "":
        return ""
    if fa == fb:
        return "is" if fa.startswith("id:") else ""
    ua = fa[3:]
    ub = fb[3:]
    if (fa.startswith("id:") or fa.startswith("dc:")) and (fb.startswith("id:") or fb.startswith("dc:")) and ua in self.classes and ub in self.classes and (self.derives(ua, ub) or self.derives(ub, ua)):
        return "is"
    return "false"


def eq_how(self, tab: ITab, op: str, e: Node) -> str:
    # how CPython answers comparison e of entry op ("==|l|T", "!=|r|T", ...) of implementation
    # tab.impl with a value of type T, where the compiler's own comparison of the two types does
    # not compile (eq_default: the entry tries it, eq_try); "" where that comparison decides
    parts = op.split("|", 2)
    if len(parts) != 3 or (parts[0] != "==" and parts[0] != "!=") or parts[2] == "None":
        return ""
    if self.is_iface(unopt(parts[2])) or self.is_iface(tab.impl) or e.kind != "cmp" or len(e.kids) != 2 or e.kids[0].kind != "name" or e.kids[1].kind != "name":
        return ""
    ts = [tab.impl if x.s == "_o" else parts[2] for x in e.kids]
    return eq_default(self, ts[0], ts[1], e.s)


def eq_note(self, tab: ITab, op: str, e: Node) -> str:
    # what an error of comparison e of entry op of implementation tab.impl says to do, where its
    # left operand's class defines the method CPython calls (__eq__, or __ne__ for !=) annotated
    # to take a type that the right operand's is not: "" for another entry
    parts = op.split("|", 2)
    if len(parts) != 3 or (parts[0] != "==" and parts[0] != "!=") or e.kind != "cmp" or len(e.kids) != 2 or e.kids[0].kind != "name" or e.kids[1].kind != "name":
        return ""
    ts = [tab.impl if x.s == "_o" else parts[2] for x in e.kids]
    c = ts[0]
    seen: dict[str, bool] = {}
    while c in self.classes and c not in seen:
        # (the class and its bases, nearest first)
        seen[c] = True
        ci = self.classes[c]
        for m in (["__ne__", "__eq__"] if parts[0] == "!=" else ["__eq__"]):
            if m in ci.methods and not ci.methods[m].synthetic:
                f = ci.methods[m]
                t = f.ptypes[1] if len(f.ptypes) == 2 else ""
                if t == "" or self.is_object(t) or t == "dyn" or t == ts[1] or lib_file(f.node.line, self.libdir):
                    return ""  # (and a method of lib/, which the program cannot annotate)
                return f"{short(c)}.{m}() takes only {typestr(t)}, where CPython calls it with any value that a value of {typestr(tab.iface)} holds: annotate its parameter object and narrow it with isinstance()"
        c = ci.base
    return ""


def eq_default_expr(how: str, e: Node, line: int) -> Node:
    # comparison e, _o op _a0 or _a0 op _o (op "==" or "!="), as how (eq_default) answers it: its
    # operands' identity ("is"), False for == and True for != ("false"), or the operands swapped
    # ("swap": the right operand's method, which CPython calls reflected)
    if how == "swap":
        return mk("cmp", e.s, line, [clone(e.kids[1]), clone(e.kids[0])])
    if how == "is":
        return mk("cmp", "is" if e.s == "==" else "is not", line, [clone(e.kids[0]), clone(e.kids[1])])
    return mk("False" if e.s == "==" else "True", "", line, [])


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
    # the objects as Python does (iface_eq); an ordering is not supported yet. A view is compared
    # as the value of object it is (view_slot)
    a = self.to_object(a) if self.is_view(a.t) else a
    b = self.to_object(b) if self.is_view(b.t) else b
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
        same = self.ptr_cmp('==', self.iface_obj(x), y)  # (the object that x holds as itself)
        return object_is_held(self, x, y, same) if dynamic_program() else same
    self.err(f"comparing a value of object with a value of {typestr(t)} by 'is' is not supported")
    return Val("false", "bool")


def object_is_held(self, x: Val, y: Val, same: Val) -> Val:
    # x is y of a value of object x and an object y of a reference type (object_is) in a program
    # with Any values: the object that x holds as itself (same), else, where x is not None, by
    # x's table's entry, as an Any value that x holds may be y but its box is not
    # (object_is_body); a value of another type is not y
    line = self.line
    end = self.label()
    more = self.label()
    ph = Ins("phi", "bool", "")
    self.incoming(ph, "true", self.cur)
    self.cbr(same.v, end, more)
    self.place(more)
    if x.v not in self.nn:
        some = self.label()
        self.incoming(ph, "false", self.cur)
        self.cbr(self.ptr_cmp('==', x, Val('null', 'None')).v, end, some)
        self.place(some)
    e = mk("cmp", "is", line, [mk("name", "_o", line, []), mk("name", "_a0", line, [])])
    r = self.iface_op(Val(x.v, OBJECT), "is|" + y.t, [y.t], "bool", e, f"its object is {typestr(y.t)}", [y])
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "bool")


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
    if u in self.classes and self.classes[u].exc != "" and "__eq__" not in self.classes[u].methods and "__ne__" not in self.classes[u].methods:
        return "uexc"  # (an exception object of a class of the program that defines no __eq__: equal only to itself)
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
    if u == "exc":
        return "exc"  # (an exception, equal only to itself: no builtin exception class defines __eq__)
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


def object_is_body(impl: str, h: str, line: int, boxable: bool) -> list[Node]:
    # the body of the entry of implementation impl for x is h, h a number of type h (object_is_num)
    # or an object of a reference type h that x does not hold as itself (object_is_held): an Any
    # value is h where it holds it, and never where no Any value can hold a value of type h (not
    # boxable: a list or a dict of typed items, ...); a number of its kind is h where it equals it
    # (a float by its bits: NaN is a NaN, 0.0 is not -0.0); any other value never
    held = unopt(impl) if is_sopt(impl) else impl
    no = mk("return", "", line, [mk("False", "", line, [])])
    o = mk("name", "_o", line, [])
    a = mk("name", "_a0", line, [])
    if impl == "dyn":
        return [mk("return", "", line, [mk("cmp", "is", line, [o, a])])] if boxable else [no]  # (an Any value's identity: dynamic.py)
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
    if self.is_view(v.t):
        v = self.to_object(v)  # (a view's box is its value of object's: view_slot)
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
    if none == "object":
        return Val("null", OBJECT)  # (None as a value of object: protocol_object)
    if none.startswith("type()."):
        return Val(self.sconst("builtins" if none == "type().__module__" else "NoneType"), "str")  # (object_type_attr)
    if none.startswith("raise:"):
        self.raise_("TypeError", self.sconst(none[6:]))  # (object_convert: None has no such conversion)
        return Val("undef", "int")
    return Val("false", "bool")


def gen_iface_eq(self, op: str, a: Val, b: Val) -> Val:
    # a == b or a != b (op) where an operand is a value of an interface: its object compared with
    # the other operand as Python compares them, by the entry of each implementation's table that
    # compiles that comparison for the object's class (a value of an interface for the other
    # operand is its object, compared by its own table's entry in turn: the innermost comparison
    # is of two classes, with their __eq__ or __ne__, reflected methods and identity), and None's
    # where the value is None. A view is compared as the value of object it is (view_slot)
    a = self.to_object(a) if self.is_view(a.t) else a
    b = self.to_object(b) if self.is_view(b.t) else b
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


def gen_object_convert(self, v: Val, kind: str) -> Val:
    # conversion kind of v, a value of object (or a view): len(), int(), float(), or a numeric
    # conversion of % formatting ("%d", "%x", "%f", "%c", ...), whose result has one type whatever
    # v holds: an int (a promoting int's for int(), %d and %x in a module that opts in), a float, or
    # %c's str of one character. The entry of the type it holds converts it as CPython does, or
    # raises CPython's TypeError where that type has no such conversion, as for None
    # (conversion_source)
    v = self.to_object(v)
    c = kind[1:] if kind.startswith("%") else ""
    big = (kind == "int" or (c != "" and c in "diuxXo")) and self.int_policy(self.line)
    ret = BIG if big else "int" if kind == "len" or kind == "int" or (c != "" and c in "diuxXo") else "str" if c == "c" else "float"
    none = "object of type 'NoneType' has no len()" if kind == "len" else NONEARG_OBJECT[kind] if kind in NONEARG_OBJECT else self.nonefmt(c)
    show = f"{kind}()" if c == "" else f"{kind} formatting"
    e = mk("name", "_o", self.line, [])
    return self.iface_apply(v, f"conv|{kind}|{ret}", [], ret, e, show, [], "raise:" + none, v, v)


# the TypeError of int() and float() of None (as of another type that has no such conversion)
NONEARG_OBJECT = {"int": "int() argument must be a string, a bytes-like object or a real number, not 'NoneType'", "float": "float() argument must be a string or a real number, not 'NoneType'"}


def type_text(held: str, before: str, name: str, after: str) -> str:
    # a message that names a value's type between before and after, as Python source: the name of
    # type held where its values have one, an exception's own class's (type(_o).__name__ of
    # BaseException, which any builtin exception class's object is) where they do not
    if held == "exc":
        return repr(before) + " + type(_o).__name__ + " + repr(after)
    return repr(before + name + after)


def conversion_source(self, kind: str, impl: str) -> str:
    # the body of the entry of implementation impl of object for conversion kind (object_convert),
    # as Python source: the conversion of a value of impl's type, as CPython's (bytes by its ASCII
    # text, where it is one), or the TypeError CPython raises for a value of that type, which
    # names it as None's names NoneType
    held = unopt(impl) if is_sopt(impl) else impl
    pre = "    if _o is None:\n        raise SystemError('a value of object holds no None')\n" if is_sopt(impl) else ""
    name = "int" if held == BIG else "_io.TextIOWrapper" if held == "file" else tname(held)
    methods = self.classes[held].methods if held in self.classes else {}
    real = held == "int" or held == "bool" or held == "float" or held == BIG
    c = kind[1:] if kind.startswith("%") else ""
    if kind == "len":
        if held == EMPTYFS:
            return "    return 0\n"
        if held == "str" or held == "bytes" or held == "dyn" or is_list(held) or is_dict(held) or is_set(held) or is_tuple(held) or is_vtuple(held) or "__len__" in methods or held in self.nts or self.bkind(held) != "":
            return "    return len(_o)\n"
        return f"    raise TypeError({type_text(held, "object of type '", name, "' has no len()")})\n"
    if kind == "int" or kind == "float":
        if real or held == "str" or held == "dyn" or "__index__" in methods or ("__int__" in methods if kind == "int" else "__float__" in methods):
            return pre + f"    return {kind}(_o)\n"
        what = "invalid literal for int() with base 10: " if kind == "int" else "could not convert string to float: "
        if held == "bytes":
            bad = f"        raise ValueError('{what}' + repr(_o))\n"
            return "    try:\n        _s = _o.decode('ascii')\n    except UnicodeDecodeError:\n" + bad + f"    try:\n        return {kind}(_s)\n    except ValueError:\n" + bad
        return f"    raise TypeError({type_text(held, NONEARG_OBJECT[kind][:-9], name, NONEARG_OBJECT[kind][-1:])})\n"
    if c in "diu":
        if real:
            return pre + "    return int(_o)\n"  # (a float truncated, as int() does)
        if "__int__" in methods or "__index__" in methods:
            return f"    return _o.{'__int__' if '__int__' in methods else '__index__'}()\n"
        if held == "dyn":
            return f"    if isinstance(_o, (int, float)):\n        return int(_o)\n    raise TypeError('%{c} format: a real number is required, not ' + type(_o).__name__)\n"
        return f"    raise TypeError({type_text(held, f'%{c} format: a real number is required, not ', name, '')})\n"
    if c in "xXo":
        if real and held != "float":
            return pre + "    return int(_o)\n"
        if "__index__" in methods:
            return "    return _o.__index__()\n"
        if held == "dyn":
            return f"    if isinstance(_o, int):\n        return int(_o)\n    raise TypeError('%{c} format: an integer is required, not ' + type(_o).__name__)\n"
        return f"    raise TypeError({type_text(held, f'%{c} format: an integer is required, not ', name, '')})\n"
    if c == "c":
        if (real and held != "float") or held == "str" or "__index__" in methods:
            return pre + "    return '%c' % _o\n"
        if held == "dyn":
            return "    if isinstance(_o, str):\n        _t: str = _o\n        return '%c' % _t\n    if isinstance(_o, int):\n        _n: int = _o\n        return '%c' % _n\n    raise TypeError('%c requires int or char')\n"
        return "    raise TypeError('%c requires int or char')\n"
    if real:
        return pre + "    return float(_o)\n"
    if "__float__" in methods or "__index__" in methods:
        return "    return _o.__float__()\n" if "__float__" in methods else "    return float(_o.__index__())\n"
    if held == "dyn":
        return "    if isinstance(_o, (int, float)):\n        return float(_o)\n    raise TypeError('must be real number, not ' + type(_o).__name__)\n"
    return f"    raise TypeError({type_text(held, 'must be real number, not ', name, '')})\n"


def gen_holds_object(self, t: str) -> bool:
    # does a value of type t hold a value of object (or a view of one's container) in its items,
    # at any depth, or is it one: the runtime's comparisons and searches, which read the items by
    # their descriptors, cannot compare it (container_eq, container_find). (A protocol's values
    # in a container keep their compilation error: tests/errors/classes/protocol_search.py)
    u = unopt(t)
    if self.is_object(u) or self.is_view(u):
        return True
    if is_list(u) or is_vtuple(u) or is_tuple(u) or is_dict(u):
        return len([x for x in targs(u) if self.holds_object(x)]) > 0
    return False


def same_test(self, x: str, y: str, a: str, b: str) -> str:
    # CPython's test that items a and b, of types x and y, are the same, which a comparison or a
    # search of containers makes of each pair: a is b or a == b, the identity test where Pystachy
    # tells it (values of an interface, references), else a == b (numbers by their values, as
    # typed containers compare them: compatibility.md's NaN)
    if self.is_iface(unopt(x)) or self.is_iface(unopt(y)) or (self.isref(x) and self.isref(y)):
        return f"{a} is {b} or {a} == {b}"
    return f"{a} == {b}"


def container_kind(t: str) -> str:
    # what container_eq compares a value of type t as: "list", "tuple" (fixed or runtime-length),
    # "dict", or ""
    return "list" if is_list(t) else "tuple" if is_tuple(t) or is_vtuple(t) else "dict" if is_dict(t) else ""


def gen_container_eq(self, op: str, a: Val, b: Val) -> Val:
    # a == b (op "==", or "!=" its negation) of two containers, one of which holds values of
    # object (holds_object), which the runtime's comparisons cannot reach: a function compiled
    # for the pair of types, which compares them as CPython's list, tuple and dict do, each pair of
    # items by identity, then equality (same_test), which calls the items' own entries; containers
    # of two kinds, or tuples of two lengths, are unequal. Val("", "") where it does not compare
    # them (dicts of two key types), which the caller compiles as it did
    ka = container_kind(a.t)
    kb = container_kind(b.t)
    if ka == "" or kb == "" or (ka == "dict" and kb == "dict" and targs(a.t)[0] != targs(b.t)[0]):
        return Val("", "")
    if ka != kb or (is_tuple(a.t) and is_tuple(b.t) and len(targs(a.t)) != len(targs(b.t))):
        return Val("false" if op == "==" else "true", "bool")
    r = self.compare_helper("==|" + a.t + "|" + b.t, container_eq_source(self, a.t, b.t), [a, b], "bool")
    return r if op == "==" else Val(self.scalar('xor', [r, Val('true', 'bool')]), "bool")


def container_eq_source(self, x: str, y: str) -> str:
    # the body of the function of container_eq for types x and y (its arguments _a and _b), as
    # Python source: the lengths, then the items in order (a dict's values by key), as CPython's
    # rich comparisons of lists, tuples and dicts go, reading the lengths again at each step
    if is_tuple(x) or is_tuple(y):
        n = len(targs(x if is_tuple(x) else y))
        out = "" if is_tuple(x) and is_tuple(y) else f"    if len({'_b' if is_tuple(x) else '_a'}) != {n}:\n        return False\n"
        for j in range(n):
            tx = targs(x)[j] if is_tuple(x) else targs(x)[0]
            ty = targs(y)[j] if is_tuple(y) else targs(y)[0]
            out += f"    if not ({same_test(self, tx, ty, f'_a[{j}]', f'_b[{j}]')}):\n        return False\n"
        return out + "    return True\n"
    if is_dict(x):
        same = same_test(self, targs(x)[1], targs(y)[1], "_x", "_y")
        return "    if len(_a) != len(_b):\n        return False\n    for _k in _a:\n        if _k not in _b:\n            return False\n        _x = _a[_k]\n        _y = _b[_k]\n" + f"        if not ({same}):\n            return False\n    return True\n"
    same = same_test(self, targs(x)[0], targs(y)[0], "_x", "_y")
    return "    if len(_a) != len(_b):\n        return False\n    _i = 0\n    while _i < len(_a) and _i < len(_b):\n        _x = _a[_i]\n        _y = _b[_i]\n" + f"        if not ({same}):\n            return False\n        _i += 1\n    return len(_a) == len(_b)\n"


def gen_container_find(self, what: str, x: Val, xs: Val) -> Val:
    # the index of the first item of xs (a list or a runtime-length tuple) that is x or equal to
    # it, -1 for none (what "find"), or how many there are ("count"), where either holds values
    # of object (holds_object): a function compiled for their types, as CPython's in,
    # index() and count() search, each item compared with x as item == x (same_test)
    same = same_test(self, targs(xs.t)[0], x.t, "_y", "_a")
    if what == "find":
        src = "    _i = 0\n    while _i < len(_b):\n        _y = _b[_i]\n" + f"        if {same}:\n            return _i\n        _i += 1\n    return -1\n"
    else:
        src = "    _n = 0\n    _i = 0\n    while _i < len(_b):\n        _y = _b[_i]\n" + f"        if {same}:\n            _n += 1\n        _i += 1\n    return _n\n"
    return self.compare_helper(f"{what}|{x.t}|{xs.t}", src, [x, xs], "int")


def gen_compare_helper(self, key: str, src: str, args: list[Val], ret: str) -> Val:
    # the call of the function of body src (Python source of its arguments _a and _b, of the
    # types of args) that container_eq or container_find asks for by key, compiled once for the
    # program as a virtual call's dispatcher is (Gen.dispatchers, which holds it by key)
    key = "compare:" + key
    if key not in self.dispatchers:
        line = self.line
        g = FnInfo("<compare>", f"@ce.{len(self.dispatchers)}", mk("def", "<compare>", line, []), "")
        g.ikey = key  # (its joins' own key: Gen.fnkey)
        g.params = ["_a", "_b"]
        g.ptypes = [v.t for v in args]
        for _ in g.params:
            g.defaults.append(mk("noann", "", line, []))
            g.dglob.append("")
            g.dtypes.append("")
        g.ret = ret
        g.mod = self.curfn.mod
        g.home = self.fn_home(self.curfn)
        body = [with_line(s, line) for s in Parser(Lexer("def _compare():\n" + src, 1).file()).module().kids[0].kids[2].kids]
        g.node.kids = [mk("params", "-1,-1", line, []), mk("noann", "", line, []), mk("block", "", line, body)]
        self.dispatchers[key] = g
        fr = self.save()
        self.modlevel = False
        self.lenient = False
        self.function(g, body)
        self.restore(fr)
        self.line = line
    g = self.dispatchers[key]
    c = Ins("call", ret, g.ll)
    c.a = [v for v in args if v.t != "None"]  # (an argument that is None is not passed, as dispatch_call's)
    if identity_abi(g):
        # (in a program with dynamic values, a number's identity box after the arguments, as call
        # passes them: none, as no comparison reads it, and the slot of the result's, unread)
        c.a = c.a + [Val("null", "dyn") for v in c.a if numeric_identity(v.t)]
        if numeric_identity(ret):
            idresult = self.alloca("dyn", "")
            self.mem_store(Val(idresult, "&dyn"), Val("null", "dyn"))
            c.a.append(Val(idresult, "&dyn"))
    self.put(c, 1)
    return Val(tmpname(c.r[0]), ret)


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
    if c.kind == "name" and (c.s in BUILTIN_TESTS or is_excname(c.s)) and not self.bound(c.s):
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


def gen_iface_narrow(self, c: Node, t: str) -> str:
    # the type that a value of interface t holds where isinstance(x, c) is true, which its reads
    # take (iface_narrowed): c's, where it names one class that has one layout (not a class
    # template's, whose objects' types its specializations are), bool, float, str or bytes, lib/'s
    # class for complex and range (BUILTIN_LIB); int
    # | bool for int, whose test a bool passes (keeping its own repr and truth), but in a module
    # that opts in to promoting ints, whose union would hold 64-bit ints; any class's class
    # object for type; for a value of object, the read-only view of the list or tuple, the set or
    # frozenset, or the dict that c names (VIEW_OF: of one of them); "" otherwise
    cs = self.iface_classes(c)
    if self.is_object(t) and len(cs) > 0 and cs[0] in VIEW_OF and len([k for k in cs if k in VIEW_OF and VIEW_OF[k] == VIEW_OF[cs[0]]]) == len(cs):
        return self.iface_of(VIEW_OF[cs[0]], [])
    if len(cs) != 1 or cs[0] == "!" or cs[0] == "object" or cs[0] in self.tmpl:
        return ""
    k = cs[0]
    if k in self.classes:
        return k
    if k in BUILTIN_LIB and BUILTIN_LIB[k] in self.classes:
        return BUILTIN_LIB[k]  # (a complex number, a range: lib/'s object)
    if k == "int":
        return "" if self.int_policy(self.line) else self.union_type(["int", "bool"])
    if k == "bool" or k == "float" or k == "str" or k == "bytes":
        return k
    if is_excname(k):
        return "exc"  # (an exception object of that builtin class, or of a class deriving from it)
    return "type[object]" if k == "type" else ""


def gen_is_view(self, t: str) -> bool:
    # is t a view of a container that a value of object holds (VIEW_OF), whose box is that value's
    return t in VIEWSHOW


def view_defs(self, c: str, line: int) -> list[Node]:
    # the operations of view c, which read the container that a value of object holds, its items
    # values of object: len(), iteration and in; for a list or a tuple its items by index, index()
    # and count(); for a dict its values by key, get(), keys(), values() and items()
    obj = self.object_iface()
    defs = [op_def("__len__", [], "int", line), op_def("__iter__", [], self.iface_of(ITERATOR, [obj]), line), op_def("__contains__", [obj], "bool", line)]
    if c == SEQVIEW:
        defs = defs + [op_def("__getitem__", ["int"], obj, line), op_def("index", [obj], "int", line), op_def("count", [obj], "int", line)]
    if c == MAPVIEW:
        get = op_def("get", [obj, obj], obj, line)
        get.kids[0].kids[2].kids[1] = mk("None", "", line, [])  # (get(key) is get(key, None))
        items = self.ctype("list", [self.ctype("tuple", [obj, obj])])
        defs = defs + [op_def("__getitem__", [obj], obj, line), get, op_def("keys", [], self.ctype("list", [obj]), line), op_def("values", [], self.ctype("list", [obj]), line), op_def("items", [], items, line)]
    return defs


def view_slot(self, f: FnInfo) -> int:
    # the slot of object's table whose entry runs operation f of a view (a method of view_defs, or
    # an IMPLICIT one): an IMPLICIT one's own slot of object's, any other a derived operation of
    # object's, which each implementation's entry runs on the container it holds (view_body). A
    # view's box is the value of object's own (iface_narrowed), so that its object is one, and
    # the view becomes a value of object again as it is (to_object)
    face = self.ifaces[OBJECT]
    if f.name in IMPLICIT:
        return face.ops.index(f.name)
    key = f"view|{f.cls}|{f.name}"
    if key not in face.dargs:
        face.ops.append(key)
        face.dargs[key] = f.ptypes[1:]
        face.dret[key] = f.ret
        face.dexpr[key] = mk("name", "_o", f.node.line, [])
        face.dshow[key] = f"{VIEWSHOW[f.cls]}.{f.name}()"
    return face.ops.index(key)


def gen_view_join(self, a: str, b: str) -> str:
    # the type of a value that is an a or a b where either is a view (an arm of x if c else y, an
    # operand of or): a value of object, which holds both, where they are not one view (or it and
    # None) and both can be one; "" otherwise
    if (not self.is_view(a) and not self.is_view(b)) or a == b or a == "None" or b == "None":
        return ""
    return OBJECT if self.object_impl(a) == "" and self.object_impl(b) == "" else ""


def view_takes(self, t: str, view: str) -> bool:
    # is a value of type t a container that view reads, one that the type test of view's
    # container types passes (isinst): a list or a tuple (a NamedTuple's object too, and one of a
    # class that derives from list), a set or a frozenset, a dict (also one of a class that
    # derives from it, and of lib/collections' mappings)
    if view == SEQVIEW:
        return is_list(t) or is_tuple(t) or is_vtuple(t) or t in self.nts or self.bkind(t) == "list"
    if view == SETVIEW:
        return is_set(t) or t == EMPTYFS
    return is_dict(t) or self.bkind(t) == "dict" or self.dict_class(t)


def view_kind(view: str) -> str:
    # what view reads, as an error names it
    return "a list or a tuple" if view == SEQVIEW else "a set or a frozenset" if view == SETVIEW else "a dict"


def to_view(self, v: Val, t: str) -> Val:
    # v as a value of view t: a container that t reads, as the value of object that holds it,
    # whose box the view's is (view_slot); None as None
    if v.t == "None":
        return Val("null", t)
    if not view_takes(self, unopt(v.t), t) and self.join_hint(t, v.t):
        return Val("undef", t)  # (a store a join drops: the next pass compiles it, a value of object's)
    if not view_takes(self, unopt(v.t), t):
        self.err(f"expected {typestr(t)}, got {typestr(v.t)}: a value of {typestr(t)} is {view_kind(t)} that a value of object holds, narrowed by isinstance()")
    return self.cast(self.to_object(v), t, "view")


def view_source(self, view: str, op: str, impl: str) -> str:
    # the body of operation op of view on a container of type impl (its object _o, arguments _a0
    # and _a1), as Python source, whose __OBJ annotates object and __DYN Any (view_body): CPython's
    # operations, which find an item that is the value or equal to it (a key equal to the given
    # one whatever its type: 1.0 finds 1, as CPython's hash and equality do; the caller hashed it,
    # view_hash); a str in a container of strs directly; keys(), values() and items() a new
    # list, as a dict's are (compatibility.md's snapshots)
    if impl == EMPTYFS:
        # (frozenset() that nothing typed, which is empty)
        return "    return 0\n" if op == "__len__" else "    _r: list[__OBJ] = []\n    return iter(_r)\n" if op == "__iter__" else "    return False\n"
    if op == "__len__":
        return "    return len(_o)\n"
    if impl == "dyn":
        return dyn_view_source(view, op)
    if is_tuple(impl) or impl in self.nts:
        return tuple_view_source(op, len(self.classes[impl].fields) if impl in self.nts else len(targs(impl)))
    k = "" if impl in self.classes else selem(impl) if is_set(impl) else targs(impl)[0]
    fast = f"    if isinstance(_a0, str):\n        return {'_a0 in _o' if op == '__contains__' else '_o[_a0]'}\n" if k == "str" else ""
    scan = "    for _i in _o:\n        if _i is _a0 or _i == _a0:\n"
    if op == "__iter__":
        return "    return iter(_o)\n"
    if op == "__contains__":
        return fast + scan + "            return True\n    return False\n"
    if op == "__getitem__" and view == SEQVIEW:
        return "    return _o[_a0]\n"
    if op == "__getitem__":
        return fast + scan + "            return _o[_i]\n    raise KeyError(_a0)\n"
    if op == "get":
        fast = "    if isinstance(_a0, str):\n        if _a0 in _o:\n            return _o[_a0]\n        return _a1\n" if k == "str" else ""
        return fast + scan + "            return _o[_i]\n    return _a1\n"
    if op == "index":
        missing = "repr(_a0) + ' is not in list'" if is_list(impl) or self.bkind(impl) == "list" else "'tuple.index(x): x not in tuple'"
        return "    _n = 0\n" + scan + "            return _n\n        _n += 1\n    raise ValueError(" + missing + ")\n"
    if op == "count":
        return "    _n = 0\n" + scan + "            _n += 1\n    return _n\n"
    if op == "keys":
        return "    _r: list[__OBJ] = []\n    for _i in _o:\n        _r.append(_i)\n    return _r\n"
    if op == "values":
        return "    _r: list[__OBJ] = []\n    for _i in _o:\n        _r.append(_o[_i])\n    return _r\n"
    return "    _r: list[tuple[__OBJ, __OBJ]] = []\n    for _i in _o:\n        _t: tuple[__OBJ, __OBJ] = (_i, _o[_i])\n        _r.append(_t)\n    return _r\n"


def tuple_view_source(op: str, n: int) -> str:
    # view_source's body of a Sequence[object]'s operation op on a tuple of n items of their own
    # types, read one by one by constant indexes
    if op == "__iter__":
        return "    _r: list[__OBJ] = [" + ", ".join([f"_o[{j}]" for j in range(n)]) + "]\n    return iter(_r)\n"
    if op == "__getitem__":
        out = f"    _i = _a0\n    if _i < 0:\n        _i += {n}\n"
        for j in range(n):
            out += f"    if _i == {j}:\n        return _o[{j}]\n"
        return out + "    raise IndexError('tuple index out of range')\n"
    found = {"__contains__": "return True", "index": "return _j", "count": "_n += 1"}[op]
    out = "    _n = 0\n"
    for j in range(n):
        out += f"    if _o[{j}] is _a0 or _o[{j}] == _a0:\n        {found.replace('_j', str(j))}\n"
    if op == "__contains__":
        return out + "    return False\n"
    return out + ("    return _n\n" if op == "count" else "    raise ValueError('tuple.index(x): x not in tuple')\n")


def dyn_view_source(view: str, op: str) -> str:
    # view_source's body of view's operation op on an Any value (a list, a tuple or a dict, which
    # an Any value's own operations read: dynamic.py), its iteration by the Any container's own
    if op == "__iter__":
        if view == MAPVIEW:
            return "    _d: dict[__DYN, __DYN] = _o\n    return iter(_d)\n"
        return "    if isinstance(_o, tuple):\n        _t: tuple[__DYN, ...] = _o\n        return iter(_t)\n    _l: list[__DYN] = _o\n    return iter(_l)\n"
    if op == "__contains__":
        return "    return _a0 in _o\n"
    if op == "__getitem__":
        return "    return _o[_a0]\n"
    if op == "get":
        return "    if _a0 in _o:\n        return _o[_a0]\n    return _a1\n"
    scan = "    for _i in _o:\n        if _i is _a0 or _i == _a0:\n"
    if op == "index":
        return "    _n = 0\n" + scan + "            return _n\n        _n += 1\n    if isinstance(_o, tuple):\n        raise ValueError('tuple.index(x): x not in tuple')\n    raise ValueError(repr(_a0) + ' is not in list')\n"
    if op == "count":
        return "    _n = 0\n" + scan + "            _n += 1\n    return _n\n"
    if op == "keys":
        return "    _r: list[__OBJ] = []\n    for _i in _o:\n        _r.append(_i)\n    return _r\n"
    if op == "values":
        return "    _r: list[__OBJ] = []\n    for _i in _o:\n        _r.append(_o[_i])\n    return _r\n"
    return "    _r: list[tuple[__OBJ, __OBJ]] = []\n    for _i in _o:\n        _t: tuple[__OBJ, __OBJ] = (_i, _o[_i])\n        _r.append(_t)\n    return _r\n"


def view_body(self, view: str, op: str, impl: str, line: int) -> list[Node]:
    # the body of the entry of implementation impl of object for operation op of view (view_slot):
    # view_source's, at line; never reached where impl is no container that view reads, as the
    # test that narrowed the value to view failed for it
    if impl != "dyn" and not view_takes(self, impl, view):
        msg = mk("str", f"a value of object narrowed by isinstance() to {VIEWSHOW[view]} holds a {typestr(impl)}", line, [])
        return [mk("raise", "", line, [mk("call", "", line, [mk("name", "SystemError", line, []), msg])])]
    body = Parser(Lexer("def _view():\n" + view_source(self, view, op, impl), 1).file()).module().kids[0].kids[2].kids
    return [with_line(bound_names(bound_names(s, "__OBJ", OBJECT), "__DYN", "dyn"), line) for s in body]


def view_hash(self, v: Val) -> None:
    # hash value v of object, a key that a view of a dict or a set looks for, as CPython hashes it
    # first: TypeError for an unhashable one, by the entry of its implementation (hashed_source);
    # None is hashable
    e = mk("name", "_o", self.line, [])
    self.iface_apply(v, "hash?()", [], "bool", e, "hash()", [], "hash?", v, v)


def hashed_source(self, impl: str) -> str:
    # the body of the entry of implementation impl of object that hashes its object as a key
    # (view_hash): hash() of it, which raises CPython's TypeError for a list, a dict, a set or an
    # object of an unhashable class; for a tuple that hash() does not take, CPython's TypeError for
    # an item that is a list, a dict or a set; nothing for a value that Pystachy's hash() does not
    # take but CPython's does (a function, a generator, a frozenset of objects, ...), which a
    # view's look-up finds only by identity or equality
    if impl == "dyn" or self.hashable(impl) or is_list(impl) or is_dict(impl) or (is_set(impl) and not is_fset(impl)) or impl in self.nts or (is_tuple(impl) and self.iface_held(impl)):
        return "    hash(_o)\n    return True\n"
    if is_tuple(impl) or is_vtuple(impl):
        for x in targs(impl):
            u = unopt(x)
            if is_list(u) or is_dict(u) or (is_set(u) and not is_fset(u)):
                raise_ = f"raise TypeError(\"unhashable type: '{tname(u)}'\")"
                return f"    if len(_o) > 0:\n        {raise_}\n    return True\n" if is_vtuple(impl) else f"    {raise_}\n"
    return "    return True\n"


def bound_names(n: Node, name: str, t: str) -> Node:
    # n with each name name the bound type t, which an annotation reads as t (gen_ann's boundtype)
    if n.kind == "name" and n.s == name:
        return mk("boundtype", t, n.line, [])
    n.kids = [bound_names(k, name, t) for k in n.kids]
    return n


def gen_iface_narrowed(self, v: Val, nt: str) -> Val:
    # v, a value of an interface that isinstance() proved holds a value of type nt (not None):
    # an object of a class of the program is held as itself; a number, a str or a class object
    # by its own table's entry, which knows how its type holds it (a number in its T | None's box);
    # a container, as the view of it that nt is, by the value of object's own box (view_slot)
    if self.is_view(nt):
        return self.cast(v, nt, "view")
    if nt in self.classes and not self.is_iface(nt) and not self.is_object(v.t) and not self.is_view(v.t):
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
