"""Classes that derive from a builtin container: component of the self-hosting Pystachy compiler.

An object of class C(list) or C(dict) begins with the container's header as runtime.c lays it
out (a List's four fields, a Dict's twelve), followed by C's own fields. Its pointer is therefore
the container's pointer, and an operation that C does not define is the builtin's own, compiled
for that pointer exactly as for a list or a dict (Gen.bview). Which code an operation runs is
decided from the static type alone: no list or dict holds a class word or a flag, and no builtin
path tests for a subclass.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import where
from src.pystachy_compiler.frames import IterArg
from src.pystachy_compiler.ir import FnInfo, Ins, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import CONTAINER_HEADERS
from src.pystachy_compiler.syntax import Node, made_var, mentions, mk
from src.pystachy_compiler.utils import elem, is_dict, is_gen, is_list, is_opt, is_tuple, is_union, targs, typestr, umembers, unopt

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
BARITH: list[str] = ["__add__", "__radd__", "__mul__", "__rmul__", "__or__", "__ror__"]
# for each comparison, the special method that decides it for its left operand and the one for
# its right operand, which CPython asks first where the right operand's class derives from the
# left one's (gen_bcompared): the builtin container's own, inherited one per operator, unless
# the class defines it (a class that defines __eq__ alone still compares != as list does)
BCMP: dict[str, list[str]] = {"==": ["__eq__", "__eq__"], "!=": ["__ne__", "__ne__"], "<": ["__lt__", "__gt__"],
                              "<=": ["__le__", "__ge__"], ">": ["__gt__", "__lt__"], ">=": ["__ge__", "__le__"]}
# the builtin functions that iterate their first argument
BITERATE: list[str] = ["list", "tuple", "set", "frozenset", "dict", "sorted", "sum", "min", "max", "any", "all", "enumerate", "zip", "reversed",
                       "math.fsum", "math.prod"]


def builtin_base(n: Node) -> str:
    # "list" where a class statement's base n is that builtin type, bare or subscripted, else ""
    x = n.kids[0] if n.kind == "index" else n
    return x.s if x.kind == "name" and x.s in CONTAINER_HEADERS else ""


def has_def(c: Node, name: str) -> bool:
    # does class statement c define method name in its own body
    for d in c.kids[0].kids:
        if d.kind == "def" and d.s == name:
            return True
    return False


def bnamed(kind: str) -> str:
    # how a class's base names the types of what builtin container kind holds, for messages
    return "list[T]" if kind == "list" else "dict[K, V]"


def bopen(kind: str, sized: bool) -> str:
    # the type of builtin container kind whose items no fill has typed yet, or (sized) the type
    # of one whose items no code reads, for its header alone (len() and truth)
    if kind == "list":
        return "list[int]" if sized else "list[?]"
    return "dict[int,int]" if sized else "dict[?,?]"


def may_fill(n: Node) -> bool:
    # may code n store a container's first item: a call of one of the methods that do, of
    # the container's __init__, or an assignment to an item or a slice
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].s in ["append", "extend", "insert", "__init__", "update", "setdefault"]:
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
        kind = builtin_base(n)
        b = self.hints.get("base:" + c, bopen(kind, False))
        if n.kind == "index":
            line = self.line
            self.line = n.line
            b = self.ann(n)
            if b.startswith("!"):
                self.err(b[1:])
            if "dyn" in b or "?" in b:
                self.err(f"a class deriving from {typestr(b)} is not supported: name the types of its items (class {short(c)}({bnamed(kind)}))")
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
            self.err(f"cannot infer what '{short(v.t)}' objects hold before an item is stored in one: name it in the base (class {short(v.t)}({bnamed(self.bkind(v.t))}))")
    if "?" in b:
        b = bopen(self.bkind(v.t), True)
    return Val(v.v, b if v.v in self.nn else self.optional(b))


def gen_bdecay(self, v: Val, own: list[str], sized: bool = False) -> Val:
    # v as the builtin container its class derives from, where the class defines none of own
    if self.bdecays(v.t, own):
        return self.bview(v, sized)
    # Borrowing a shared container for these operations leaves its stored class untouched.
    # Comparisons and arithmetic dispatch on the original member, including reflected calls.
    if len(own) > 0 and all(m in ["__iter__", "__reversed__", "__getitem__", "__setitem__", "__delitem__", "__len__", "__bool__", "__contains__"] for m in own):
        return bborrow(self, v, own)
    return v


def bparameter_type(self, t: str, expected: str) -> int:
    # Whether a parameter's annotation describes t, including containers that retain a
    # subclass item in its own representation: -1 for incompatible types, 0 for unchanged
    # types, 1 where the body needs the actual subclass or tagged item type. In particular,
    # list[Stack | list[int]] is never read as a list of untagged list pointers.
    if t == expected:
        return 0
    u = unopt(t)
    w = unopt(expected)
    if w != "" and ((self.bkind(u) != "" and self.bbase(u) == w) or bfamily(self, u) == w):
        return 1
    family = bfamily(self, w)
    if family != "" and family in umembers(w) and (u == family or (self.bkind(u) != "" and self.bbase(u) == family) or bfamily(self, u) == family):
        # The plain builtin member already admits its subclasses. Keep their
        # actual storage when another caller added a tagged family member to
        # this parameter; unions of named subclasses alone keep their bounds.
        return 1
    if not ((is_list(u) and is_list(w)) or (is_dict(u) and is_dict(w)) or (is_tuple(u) and is_tuple(w))):
        return -1
    actual = targs(u)
    declared = targs(w)
    if len(actual) != len(declared) or (is_dict(u) and actual[0] != declared[0]):
        return -1
    changed = 0
    for i in range(len(actual)):
        match = bparameter_type(self, actual[i], declared[i])
        if match < 0:
            return -1
        changed = max(changed, match)
    return changed


def bparameter(self, f: FnInfo, j: int, t: str) -> bool:
    # A list/dict annotation accepts its subclass, also inside another annotated container.
    # Compile the body for the actual representation. Native/exported interfaces
    # keep their declared representation.
    if j >= len(f.ptypes):
        return False
    declared = f.ptypes[j]
    # A union's class member can receive None in its comparison method even when the
    # container annotation omits it. Compile that arm with a nullable container parameter;
    # operations on None then raise only if the method actually executes them.
    nullable = j == 1 and f.cls != "" and f.name in ["__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"] and (is_list(declared) or is_dict(declared)) and (t == "None" or (is_opt(t) and unopt(t) == declared))
    if not nullable and bparameter_type(self, t, declared) != 1:
        return False
    if f.gen or f.extern or f.export or f.pyexport or f.prop or f.acc != "" or f.deco != "" or len(f.node.kids) < 3:
        return False
    return j != f.vararg and j != f.kwarg


def bfamily(self, t: str) -> str:
    # A closed union of objects sharing one list/dict payload, including its plain builtin
    # form. Its boxes keep each object's class; no original container or alias is changed.
    if not is_union(unopt(t)):
        return ""
    base = ""
    subclass = False
    for m in umembers(unopt(t)):
        b = m
        if self.bkind(m) != "":
            b = self.bbase(m)
            subclass = True
        if (not is_list(b) and not is_dict(b)) or "?" in b or (base != "" and base != b):
            return ""
        base = b
    return base if subclass else ""


def bstorage_join(self, a: str, b: str) -> str:
    # One physical item layout for aliases of the same list/dict. Only a closed
    # family of a builtin container and its subclasses can request this rewrite.
    if not ((is_list(a) and is_list(b)) or (is_dict(a) and is_dict(b))):
        return ""
    if is_dict(a) and targs(a)[0] != targs(b)[0]:
        return ""
    x = targs(a)[0] if is_list(a) else targs(a)[1]
    y = targs(b)[0] if is_list(b) else targs(b)[1]
    members = (umembers(x) if is_union(x) else [x]) + (umembers(y) if is_union(y) else [y])
    bases = [self.bbase(t) if t in self.classes else t for t in members]
    if not any(t in self.classes for t in members) or len(bases) == 0 or not (is_list(bases[0]) or is_dict(bases[0])) or any(t != bases[0] for t in bases):
        return ""
    return self.join_type(a, b)


def bborrow(self, v: Val, own: list[str]) -> Val:
    # A default operation on every member of a shared container family borrows the selected
    # member's payload. The union box remains in its original storage, keeping class and
    # identity for later observations. None stays None so the operation evaluates its other
    # operands before raising. An override, including dict.__missing__, needs member dispatch.
    base = bfamily(self, v.t)
    if base == "":
        return v
    methods = own + (["__missing__"] if "__getitem__" in own else [])
    members = umembers(unopt(v.t))
    for m in members:
        if self.bkind(m) != "" and any(name in self.classes[m].methods for name in methods):
            return v
    t = base if v.v in self.nn else self.optional(base)
    ph = Ins("phi", t, "")
    end = self.label()
    if v.v not in self.nn:
        nonnull = self.label()
        self.incoming(ph, "null", self.cur)
        self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, nonnull)
        self.place(nonnull)
    tag = self.mload('int', v.v)
    for i in range(len(members)):
        m = members[i]
        nxt = self.label() if i + 1 < len(members) else ""
        if nxt != "":
            arm = self.label()
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(m)), "int")).v, arm, nxt)
            self.place(arm)
        item = self.uget(Val(v.v, unopt(v.t)), m)
        self.incoming(ph, item.v, self.cur)
        self.br(end)
        if nxt != "":
            self.place(nxt)
    self.place(end)
    return Val(self.phi(ph), t)


def gen_bcompared(self, op: str, a: Val, b: Val) -> list[Val]:
    # the operands of a op b (a comparison of BCMP) where one is an object of a class deriving
    # from a builtin container: both as the containers where the container's comparison decides
    # it, else both as they are (the class's method decides). CPython's do_richcompare asks the
    # right operand first where its class derives from the left one's type (a builtin container,
    # or anything but such an object), else the left operand
    if op not in BCMP or (self.bkind(a.t) == "" and self.bkind(b.t) == ""):
        return [a, b]
    if op != "==" and op != "!=" and (self.bkind(a.t) == "dict" or self.bkind(b.t) == "dict"):
        return [a, b]  # (dicts have no order: an object's class raises CPython's TypeError, naming it)
    if self.bkind(a.t) != "" and BCMP[op][0] in self.classes[a.t].methods:
        return [a, b]
    if self.bkind(a.t) == "" and BCMP[op][1] in self.classes[b.t].methods:
        return [a, b]
    return [self.bdecay(a, []), self.bdecay(b, [])]


def gen_bkeeps(self, op: str, a: Val, b: Val) -> bool:
    # whether a op b is compiled with both operands as they are, where bcompared would compare
    # them as containers although CPython calls a method of the program with the object of a
    # class deriving from a builtin container: the left operand's method, or the right one's
    # reflected method where the left operand's container declines a right operand that is no
    # such container (one of the container's kind, an object of another class deriving from it
    # too, is compared by the container, which does not decline it). False where bcompared
    # decides as CPython does. A user's method must always receive the original object:
    # restarting with its builtin view can silently change both the method and stored aliases.
    if op not in BCMP or (self.bkind(a.t) == "" and self.bkind(b.t) == ""):
        return False
    if op != "==" and op != "!=" and (self.bkind(a.t) == "dict" or self.bkind(b.t) == "dict"):
        return False
    if self.bkind(a.t) != "" and BCMP[op][0] in self.classes[a.t].methods:
        return False
    if self.bkind(a.t) == "" and BCMP[op][1] in self.classes[b.t].methods:
        return False
    ka = self.bkind(a.t)
    kb = self.bkind(b.t)
    if ka == "":
        return self.bcalled(op, a.t, 0)
    if kb != ka and not (is_list(b.t) if ka == "list" else is_dict(b.t)):
        return self.bcalled(op, b.t, 1)
    return False


def gen_bkept(self, op: str, a: Val, b: Val) -> Val:
    # a op b with both operands as they are: the program's method takes the object itself, whose
    # class isinstance() and type() tell there. Its type is the class's where the container's
    # was, in the method and in whatever the method stores it in, returns it to or passes it on
    # to. A storage or call boundary that cannot preserve it reports its ordinary diagnostic;
    # it must not retry the whole program with class-erasing container views (#1739).
    return self.cmp3(op, a, b)


def gen_bcalled(self, op: str, t: str, side: int) -> bool:
    # does comparison op (of BCMP) call a method that the program defines for an operand of
    # type t, its left one (side 0) or its right one (side 1, the reflected method): the method
    # of an object's class, written in the program (not a dataclass's generated one, which
    # declines an object of another class unread). A class deriving from a builtin container
    # keeps the container's method for each operator it does not define; any other class's
    # != inverts its __eq__ where it defines no __ne__
    if t not in self.classes:
        return False
    ms = self.classes[t].methods
    m = BCMP[op][side]
    if m in ms and not ms[m].synthetic:
        return True
    return op == "!=" and self.bkind(t) == "" and "__eq__" in ms and not ms["__eq__"].synthetic


def gen_bsearched(self, item: Val, a: Val) -> list[Val]:
    # item == a, as a tuple search compares an item with what it looks for (titem_eq), where one
    # is an object of a class deriving from a builtin container that defines no __eq__ and the
    # other's class has an __eq__ of the program that takes not that object but its container:
    # CPython calls the method with the object, and the method can take it here only as the
    # container, as == hands it over where no method takes the object itself (bcompared, #1763).
    # Beside a list or dict, or another such object, that defines no __eq__ either, both as the
    # containers, whose == CPython's is then. Else both as they are
    r = [item, a]
    kinds = [self.bkind(item.t), self.bkind(a.t)]
    for i in range(2):
        x = r[i]
        y = r[1 - i]
        if kinds[i] == "" or not self.bdecays(x.t, ["__eq__"]):
            continue
        u = unopt(y.t)
        if (is_list(u) if kinds[i] == "list" else is_dict(u)) or (kinds[1 - i] == kinds[i] and self.bdecays(y.t, ["__eq__"])):
            r[i] = self.bview(x)
            continue
        if y.t not in self.classes or kinds[1 - i] != "":
            continue
        ms = self.classes[y.t].methods
        if "__eq__" not in ms or ms["__eq__"].synthetic or self.cmp_method(y.t, "__eq__", x.t) != "":
            continue
        v = self.bview(x)
        if self.cmp_method(y.t, "__eq__", v.t) != "":
            r[i] = v
    return r


def gen_bfound(self, t: str, b: str) -> None:
    # the objects of class t, whose bare base names no item type, hold what builtin type b
    # does, which a first fill showed: so for the rest of this pass, whose code so far made
    # them without that type, and the next pass compiles the program with it from the start
    # (as a join's hint, see Rejoin: a newhints entry ends the pass, at an error or at its end)
    c = self.classes[t].origin if self.classes[t].origin != "" else t
    kind = self.bkind(t)
    if "?" in b or "None" in targs(b):
        self.err(f"cannot infer what '{short(c)}' objects hold from {typestr(b)}: name it in the base (class {short(c)}({bnamed(kind)}))")
    if self.final or self.rtmode:
        self.err(f"cannot infer what '{short(c)}' objects hold: name it in the base (class {short(c)}({bnamed(kind)}))")
    self.bsub[c] = b
    self.newhints["base:" + c] = b


def gen_bfill(self, t: str, m: str, args: list[Node]) -> None:
    # o.append(v), o.insert(i, v) or o.extend(xs) on an object of class t whose bare base no
    # fill has typed yet: the item's type decides it (as a list variable's first fill does)
    if "?" not in self.bbase(t) or len([a for a in args if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) > 0:
        return
    if self.bkind(t) == "dict":
        # (d.update(m) of a dict m, d.setdefault(k, v): the first item's key and value)
        if m == "update" and len(args) == 1 and is_dict(unopt(self.dry(args[0]))):
            self.bfound(t, unopt(self.dry(args[0])))
        elif m == "setdefault" and len(args) == 2:
            self.bfound(t, self.ctype("dict", [self.dry(args[0]), self.dry(args[1])]))
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
    # new empty container of its type, made as the display [] of that type is, whose fields o
    # takes (its item array is its own allocation, or the display's inline items, which o's
    # pointer to them keeps: runtime.c tests l->a against the header's own inline items, never
    # o's fields, so o's items never go there)
    b = self.bbase(o.t)
    kind = self.bkind(o.t)
    if self.classes[o.t].tag > 0:
        # (a hierarchy's class tag is an object's first word, which here is the header's)
        self.err(f"internal error: class {short(o.t)}, which derives from {kind}, has a class tag")
    if "?" in b:
        b = bopen(kind, True)
    made = self.expr(mk(kind, "", self.line, []), b)
    for k, t in enumerate(CONTAINER_HEADERS[kind]):
        src = self.maddr(kind + ".header", made.v, str(k))
        self.mem_store(Val(self.fgep(o, k), "&" + t), Val(self.mload(t, src), t))


def gen_bmake(self, c: str, args: list[Node]) -> Val:
    # C(args) of class C deriving from a builtin container, which defines no __init__: a new
    # object, then list.__init__(o, args), which takes at most an iterable of its items and
    # extends the list as list's own extend() does, also where C defines an extend(); or
    # dict.__init__(o, args), which updates the dict as dict's own update() does
    kind = self.bkind(c)
    pos = [a for a in args if a.kind != "kw"]
    if len(pos) > 1 or len([a for a in args if a.kind == "starred" or a.kind == "dstar" or (a.kind == "kw" and kind == "list")]) > 0:
        self.err(f"{short(c)}() takes at most one argument, an iterable of its items (as list() does)" if kind == "list" else
                 f"{short(c)}() takes at most one positional argument, a mapping or an iterable of pairs, and keyword arguments (as dict() does)")
    o = self.new_obj(c)
    if len(args) > 0:
        self.bfill(c, "extend" if kind == "list" else "update", args)
        self.method(self.bview(o), "extend" if kind == "list" else "update", args)
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
    # the value's type decides it (a dict's, with the key's)
    if "?" in self.bbase(t):
        self.bfound(t, self.ctype("dict", [self.dry(key), vt]) if self.bkind(t) == "dict" else self.ctype("list", [vt]))


def gen_bmissing(self, me: Val, key: Node) -> Val:
    # me[key] of an object me of a class deriving from dict that defines __missing__ (and no
    # __getitem__): dict's lookup, and me.__missing__(key) where the key is not there, as
    # CPython's dict_subscript calls it (get(), in, setdefault() and pop() never do). me's
    # None raises once the key is evaluated, as for a dict. A bare base that no fill has typed
    # yet holds keys of the key's type and values of what __missing__ returns for it, unless
    # the __missing__ that this compiles (as a template's call does) stores a first item itself
    if "?" in self.bbase(me.t):
        kt = self.dry(key)
        rt = self.dry(mk("call", "", key.line, [mk("attr", "__missing__", key.line, [self.vnode(me)]), key]))
        if "?" in self.bbase(me.t):
            self.bfound(me.t, self.ctype("dict", [kt, rt]))
    d = self.bview(me)
    kv = targs(unopt(d.t))
    k = self.expr(key, kv[0])
    if k.t == "dyn" or kv[0] == "dyn" or not self.bmissable(k.t, kv[0]):
        self.err(f"{short(me.t)}[k] of a {typestr(k.t)} key, with __missing__, is not supported: the keys' type {typestr(kv[0])} must take it as it is")
    kx = self.dkey(k, kv[0])
    d = self.unwrap(d, "TypeError: 'NoneType' object is not subscriptable")
    e = self.nonekey(kx, "-1", "pys_dict_find", [f"ptr {d.v}", f"i64 {self.to_slot(kx)}"], self.key_fx(kv[0]), kv[0])
    hit = self.label()
    miss = self.label()
    end = self.label()
    self.cbr(self.num_cmp("<", Val(e, "int"), Val("0", "int")).v, miss, hit)
    self.place(hit)
    v1 = self.dict_value(d, e)
    l1 = self.cur
    self.br(end)
    self.place(miss)
    v2 = self.coerce(self.method(Val(d.v, me.t), "__missing__", [self.vnode(k)]), v1.t, f"the value {short(me.t)}.__missing__() returns ({typestr(v1.t)}, as the dict's)")
    l2 = self.cur
    self.br(end)
    self.place(end)
    ph = Ins("phi", v1.t, "")
    self.incoming(ph, v1.v, l1)
    self.incoming(ph, v2.v, l2)
    return Val(self.phi(ph), v1.t)


def gen_bmissable(self, kt: str, dkt: str) -> bool:
    # is a key of type kt looked up among a dict's keys of type dkt as it is (a str among strs,
    # an int among ints, ...), which bmissing supports, not converted (a bool among ints, an
    # int past 64 bits, an int among floats)
    return kt == dkt or kt == "None" or unopt(kt) == unopt(dkt)


def gen_bsuper(self, me: Val, m: str, args: list[Node]) -> Val:
    # super().m(args) in a method of a class deriving from a builtin container, or list.m(me,
    # args): the container's own method m on object me, whatever the class defines. Its
    # __init__ takes at most an iterable of the items, which replace those it holds; its
    # __getitem__, __setitem__, __delitem__ and __contains__ are those of o[k], o[k] = v, del
    # o[k] and k in o on the container
    kind = self.bkind(me.t)
    if len([a for a in args if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) > 0:
        self.err(f"keyword and star arguments of {kind}.{m}() are not supported here; pass them by position")
    if m == "__init__" and kind == "dict":
        # (dict.__init__(o, m): the items of m, a mapping or an iterable of pairs, update o's,
        # which it keeps, as CPython's dict_init does)
        if len(args) > 1:
            self.err(f"dict.__init__() takes at most one positional argument, a mapping or an iterable of pairs ({len(args)} given)")
        if len(args) == 1:
            self.bfill(me.t, "update", args)
            self.method(self.bview(me), "update", args)
        return Val("null", "None")
    if m == "__init__":
        if len(args) > 1:
            self.err(f"{kind}.__init__() takes at most one argument, an iterable of its items ({len(args)} given)")
        if len(args) == 1:
            self.bfill(me.t, "extend", args)
            source = self.mapgen(args[0]) if self.is_mapcall(args[0]) else args[0]
            if self.iterator_call(source):
                item = made_var("__item", source.line)
                source = mk("listcomp", "gen", source.line, [item, item, source])
            if source.kind == "listcomp" and source.s == "gen":
                # Capture the outer iterator before clearing, then append as each item arrives.
                # A generator can observe the destination or raise after a partial fill.
                target = self.bview(me)
                clear = mk("attr", "clear", source.line, [self.vnode(target)])
                self.listcomp(source, unopt(target.t), "", target.v, IterArg(mk("call", "", source.line, [clear])))
            else:
                value = self.consume(source, "")
                given = self.vnode(value)
                self.method(self.bview(me), "clear", [])
                if is_gen(value.t):
                    item = made_var("__item", source.line)
                    given = mk("listcomp", "gen", source.line, [item, item, given])
                self.method(self.bview(me), "extend", [given])
        else:
            self.method(self.bview(me, True), "clear", [])
        return Val("null", "None")
    if (m == "__repr__" or m == "__str__") and len(args) == 0:
        # (object's __str__ is repr() of the object, its class's __repr__ if it defines one)
        return self.repr(self.bview(me)) if m == "__repr__" else self.repr(me)
    if m == "__len__" and len(args) == 0:
        return self.builtin("len", [self.vnode(self.bview(me, True))], "")
    line = self.line
    if m == "__getitem__" and len(args) == 1:
        # (dict.__getitem__ calls a class's __missing__ where the key is not there, as d[k] does)
        if kind == "dict" and "__missing__" in self.classes[me.t].methods:
            return self.bmissing(me, args[0])
        v = self.bview(me)
        return self.subscript(mk("index", "", line, [self.vnode(v), args[0]]), v)
    if m == "__setitem__" and len(args) == 2:
        # (its key, then its value, evaluated before the store, as the call's arguments are)
        b = self.bbase(me.t)
        k = self.vnode(self.expr(args[0], "" if "?" in b else targs(b)[0] if kind == "dict" else "int"))
        x = self.expr(args[1], "" if "?" in b else targs(b)[1] if kind == "dict" else elem(b))
        self.bstored(me.t, k, x.t)
        self.assign(mk("index", "", line, [self.vnode(self.bview(me)), k]), x)
        return Val("null", "None")
    if m == "__delitem__" and len(args) == 1:
        self.stmt(mk("del", "", line, [mk("index", "", line, [self.vnode(self.bview(me)), args[0]])]))
        return Val("null", "None")
    if m == "__contains__" and len(args) == 1:
        return self.expr(mk("cmp", "in", line, [args[0], self.vnode(self.bview(me))]), "")
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
