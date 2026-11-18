"""Classes that derive from a builtin container: component of the self-hosting Pystachy compiler.

An object of class C(list) begins with the container's header as runtime.c lays it out (a List's
four words), followed by C's own fields. Its pointer is therefore the container's pointer, and an
operation that C does not define is the builtin's own, compiled for that pointer exactly as for a
list (Gen.bview). Which code an operation runs is decided from the static type alone: no list
holds a class word or a flag, and no builtin path tests for a subclass.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import where
from src.pystachy_compiler.ir import FnInfo, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.syntax import Node, made_var, mentions, mk
from src.pystachy_compiler.utils import elem, is_list, targs, typestr

# the builtin containers a class may derive from, each with the 8-byte words of its header
# (runtime.c's List), which the object's struct starts with as hidden fields
BWORDS: dict[str, int] = {"list": 4}
# the special methods whose operations a class deriving from a container takes from it where it
# defines none of them (Gen.bdecays): the others are an ordinary class's
BITER: list[str] = ["__iter__"]
BREV: list[str] = ["__reversed__"]
BITEM: list[str] = ["__getitem__"]
BSTORE: list[str] = ["__setitem__"]
BDEL: list[str] = ["__delitem__"]
BLEN: list[str] = ["__len__"]
BTRUTH: list[str] = ["__bool__", "__len__"]
BIN: list[str] = ["__contains__"]
BSHOW: list[str] = ["__repr__", "__str__"]
BREPR: list[str] = ["__repr__"]
BARITH: list[str] = ["__add__", "__radd__", "__mul__", "__rmul__"]
# for each comparison, the special method that decides it for its left operand and the one for
# its right operand, which CPython asks first where the right operand's class derives from the
# left one's (gen_bcompared): the builtin container's own, inherited one per operator, unless
# the class defines it (a class that defines __eq__ alone still compares != as list does)
BCMP: dict[str, list[str]] = {"==": ["__eq__", "__eq__"], "!=": ["__ne__", "__ne__"], "<": ["__lt__", "__gt__"],
                              "<=": ["__le__", "__ge__"], ">": ["__gt__", "__lt__"], ">=": ["__ge__", "__le__"]}
# the builtin functions that iterate their first argument
BITERATE: list[str] = ["list", "tuple", "set", "frozenset", "sorted", "sum", "min", "max", "any", "all", "enumerate", "zip", "reversed",
                       "math.fsum", "math.prod"]


def builtin_base(n: Node) -> str:
    # "list" where a class statement's base n is that builtin type, bare or subscripted, else ""
    x = n.kids[0] if n.kind == "index" else n
    return x.s if x.kind == "name" and x.s in BWORDS else ""


def has_def(c: Node, name: str) -> bool:
    # does class statement c define method name in its own body
    for d in c.kids[0].kids:
        if d.kind == "def" and d.s == name:
            return True
    return False


def may_fill(n: Node) -> bool:
    # may code n store a container's first item: a call of one of the methods that do, of
    # the container's __init__, or an assignment to an item or a slice
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].s in ["append", "extend", "insert", "__init__"]:
        return True
    if (n.kind == "assign" or n.kind == "augassign") and n.kids[0].kind in ["index", "slice", "name", "attr"]:
        return n.kind == "augassign" or n.kids[0].kind in ["index", "slice"]
    for k in n.kids:
        if may_fill(k):
            return True
    return False


def gen_bkind(self, t: str) -> str:
    # "list" where t is a class that derives from that builtin (or a specialization of one), else ""
    if len(self.bsubn) == 0 or t not in self.classes:
        return ""
    c = self.classes[t].origin if self.classes[t].origin != "" else t
    return builtin_base(self.bsubn[c]) if c in self.bsubn else ""


def gen_bbase(self, t: str) -> str:
    # the builtin type that the objects of class t begin as, list[T], or "": what its base
    # names (class C(list[int])); for a bare base, what the first fill of one of its objects
    # showed, on this pass or an earlier one (bfound), and list[?] until then
    if self.bkind(t) == "":
        return ""
    c = self.classes[t].origin if self.classes[t].origin != "" else t
    if c not in self.bsub:
        n = self.bsubn[c]
        b = self.hints.get("base:" + c, "list[?]")
        if n.kind == "index":
            line = self.line
            self.line = n.line
            b = self.ann(n)
            if b.startswith("!"):
                self.err(b[1:])
            if "dyn" in b or "?" in b:
                self.err(f"a class deriving from {typestr(b)} is not supported: name the type of its items (class {short(c)}(list[T]))")
            self.line = line
        self.bsub[c] = b
    return self.bsub[c]


def gen_bdecays(self, t: str, own: list[str]) -> bool:
    # is t a class deriving from a builtin container that defines none of the special methods
    # own: the operation they would make is then the container's
    if self.bkind(t) == "":
        return False
    for m in own:
        if m in self.classes[t].methods:
            return False
    return True


def gen_bview(self, v: Val, sized: bool = False) -> Val:
    # v, an object of a class deriving from a builtin container, as that container: the same
    # pointer, which may be None unless the object is known not to be (as an optional list is,
    # so that the builtin's code raises CPython's error for None). sized: for len() and truth
    # alone, which read no item, so that a base no fill has typed yet will do
    b = self.bbase(v.t)
    if "?" in b and not sized:
        self.bearly(v.t)
        b = self.bbase(v.t)
        if "?" in b:
            self.err(f"cannot infer what '{short(v.t)}' objects hold before an item is stored in one: name it in the base (class {short(v.t)}(list[T]))")
    if "?" in b:
        b = "list[int]"
    return Val(v.v, b if v.v in self.nn else self.optional(b))


def gen_bdecay(self, v: Val, own: list[str], sized: bool = False) -> Val:
    # v as the builtin container its class derives from, where the class defines none of own
    return self.bview(v, sized) if self.bdecays(v.t, own) else v


def gen_bcompared(self, op: str, a: Val, b: Val) -> list[Val]:
    # the operands of a op b (a comparison of BCMP) where one is an object of a class deriving
    # from a builtin container: both as the containers where the container's comparison decides
    # it, else both as they are (the class's method decides). CPython's do_richcompare asks the
    # right operand first where its class derives from the left one's type (a builtin container,
    # or anything but such an object), else the left operand
    if op not in BCMP or (self.bkind(a.t) == "" and self.bkind(b.t) == ""):
        return [a, b]
    if self.bkind(a.t) != "" and BCMP[op][0] in self.classes[a.t].methods:
        return [a, b]
    if self.bkind(a.t) == "" and BCMP[op][1] in self.classes[b.t].methods:
        return [a, b]
    return [self.bdecay(a, []), self.bdecay(b, [])]


def gen_bfound(self, t: str, b: str) -> None:
    # the objects of class t, whose bare base names no item type, hold what builtin type b
    # does, which a first fill showed: so for the rest of this pass, whose code so far made
    # them without that type, and the next pass compiles the program with it from the start
    # (as a join's hint, see Rejoin; program() ends this pass even if a retry dropped newhints)
    c = self.classes[t].origin if self.classes[t].origin != "" else t
    if "?" in b or "None" in targs(b):
        self.err(f"cannot infer what '{short(c)}' objects hold from {typestr(b)}: name it in the base (class {short(c)}(list[T]))")
    if self.final or self.rtmode:
        self.err(f"cannot infer what '{short(c)}' objects hold: name it in the base (class {short(c)}(list[T]))")
    self.bsub[c] = b
    self.bnew["base:" + c] = b
    self.newhints["base:" + c] = b


def gen_bfill(self, t: str, m: str, args: list[Node]) -> None:
    # o.append(v), o.insert(i, v) or o.extend(xs) on an object of class t whose bare base no
    # fill has typed yet: the item's type decides it (as a list variable's first fill does)
    if "?" not in self.bbase(t) or len([a for a in args if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) > 0:
        return
    if (m == "append" and len(args) == 1) or (m == "insert" and len(args) == 2):
        self.bfound(t, self.ctype("list", [self.dry(args[-1])]))
    elif m == "extend" and len(args) == 1:
        self.bfound(t, self.ctype("list", [self.bitems(args[0])]))


def gen_bitems(self, a: Node) -> str:
    # the type of the items that iterating expression a gives, for a first fill: those of
    # the list of them (as list(a) makes it)
    item = made_var("__item", a.line)
    it = self.dry(mk("listcomp", "", a.line, [item, item, a]))
    return elem(it) if is_list(it) else "?"


def gen_binit(self, o: Val) -> None:
    # the header of o, a new object of a class deriving from a builtin container: that of a
    # new empty container of its type, made as the display [] of that type is, whose words o
    # takes (its item array is its own allocation, or the display's inline items, which o's
    # pointer to them keeps: runtime.c tests l->a against the header's own inline items, never
    # o's fields, so o's items never go there)
    b = self.bbase(o.t)
    kind = self.bkind(o.t)
    if self.classes[o.t].tag > 0:
        # (a hierarchy's class tag is an object's first word, which here is the header's)
        self.err(f"internal error: class {short(o.t)}, which derives from {kind}, has a class tag")
    if "?" in b:
        b = "list[int]"
    made = self.expr(mk("list", "", self.line, []), b)
    for k in range(BWORDS[kind]):
        self.mstore("int", self.mload("int", self.maddr("int", made.v, str(k))), self.maddr("int", o.v, str(k)))


def gen_bmake(self, c: str, args: list[Node]) -> Val:
    # C(args) of class C deriving from a builtin container, which defines no __init__: a new
    # object, then list.__init__(o, args), which takes at most an iterable of its items and
    # extends the list as list's own extend() does, also where C defines an extend()
    if len(args) > 1 or len([a for a in args if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) > 0:
        self.err(f"{short(c)}() takes at most one argument, an iterable of its items (as list() does)")
    o = self.new_obj(c)
    if len(args) == 1:
        self.bfill(c, "extend", args)
        self.method(self.bview(o), "extend", args)
    return o


def gen_bbuiltin(self, name: str, v: Val, n: int) -> Val:
    # the first v of the n positional arguments of builtin function name, as the builtin
    # container that its class derives from where the function reads it through a special
    # method the class leaves to the container: its length, its truth, or its items, which
    # None has not (CPython's TypeError, raised where the function would iterate it). min() and
    # max() of two or more arguments compare them (cmp2), and return one of them
    if self.bkind(v.t) == "":
        return v
    if name == "len":
        return self.bdecay(v, BLEN, True)
    if name == "bool":
        return self.bdecay(v, BTRUTH, True)
    if name in BITERATE and not ((name == "min" or name == "max") and n > 1) and self.bdecays(v.t, BREV if name == "reversed" else BITER):
        return self.unwrap(self.bview(v), "TypeError: 'NoneType' object is not reversible" if name == "reversed" else "TypeError: 'NoneType' object is not iterable")
    return v


def gen_bstored(self, t: str, key: Node, vt: str) -> None:
    # o[key] = v, v of type vt, on an object of class t whose bare base no fill has typed yet:
    # the value's type decides it
    if "?" in self.bbase(t):
        self.bfound(t, self.ctype("list", [vt]))


def gen_bsuper(self, me: Val, m: str, args: list[Node]) -> Val:
    # super().m(args) in a method of a class deriving from a builtin container, or list.m(me,
    # args): the container's own method m on object me, whatever the class defines. Its
    # __init__ takes at most an iterable of the items, which replace those it holds
    kind = self.bkind(me.t)
    if len([a for a in args if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) > 0:
        self.err(f"keyword and star arguments of {kind}.{m}() are not supported here; pass them by position")
    if m == "__init__":
        if len(args) > 1:
            self.err(f"{kind}.__init__() takes at most one argument, an iterable of its items ({len(args)} given)")
        if len(args) == 1:
            self.bfill(me.t, "extend", args)
            given = self.vnode(self.consume(args[0], ""))
            self.method(self.bview(me), "clear", [])
            self.method(self.bview(me), "extend", [given])
        else:
            self.method(self.bview(me, True), "clear", [])
        return Val("null", "None")
    if (m == "__repr__" or m == "__str__") and len(args) == 0:
        # (object's __str__ is repr() of the object, its class's __repr__ if it defines one)
        return self.repr(self.bview(me)) if m == "__repr__" else self.repr(me)
    if m == "__len__" and len(args) == 0:
        return self.builtin("len", [self.vnode(self.bview(me, True))], "")
    if m.startswith("__") and m.endswith("__"):
        self.err(f"{kind}.{m}() of a class that derives from {kind} is not supported: use the operation on {kind}(self) or a method of {kind}")
    self.bfill(me.t, m, args)
    return self.method(self.bview(me), m, args)


def gen_bearly(self, t: str) -> None:
    # what the objects of class t hold, which its bare base does not say, is needed before the
    # code that shows it is compiled: the functions not compiled yet that may store an object's
    # first item (the class's own methods, and those that name the class) are compiled now, as
    # early() compiles those that fill a global container. Only on a pass that ends once the
    # type is found (bfound): the next one has it from the start, and compiles nothing early
    c = self.classes[t].origin if self.classes[t].origin != "" else t
    fs: list[FnInfo] = [f for f in self.funcs.values()]
    for ci in self.classes.values():
        if ci.bad == "" and ci.name not in self.tmpl:
            fs.extend(ci.methods.values())
    for f in fs:
        if "?" not in self.bbase(t):
            break
        if f.generic or f.bad != "" or f.ll in self.compiled or f.node.kind != "def" or len(f.node.kids) < 3 or f.extern or f.export:
            continue
        own = f.cls in self.classes and (f.cls == c or self.classes[f.cls].origin == c)
        named = c in f.ptypes or mentions(f.node.kids[2], [c])  # (a parameter of the class, or code that names it)
        if not (own or named) or not may_fill(f.node.kids[2]) or self.unready(f.node.kids[2], f.mod, {}):
            continue
        self.making.append(f"compiling {f.name if f.cls == '' else f.cls + '.' + f.name}() for what '{short(c)}' objects hold at {where(self.line)}")
        fr = self.save()
        self.modlevel = False
        self.lenient = False
        self.function(f, f.node.kids[2].kids)
        self.restore(fr)
        self.making.pop()
