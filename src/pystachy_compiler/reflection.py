"""Reflection component of the self-hosting Pystachy compiler.

Reflection over values whose possible classes the compiler knows (docs/internals.md#reflection):
type(x)'s names and identity, getattr/setattr/hasattr with names that are literals or come from a
constant set (#486), and with names known only at run time for consumers that need no value of
the attribute (#489's first version). Where a run-time choice is needed, the code dispatches on
the value's exact class (union tag, then class tag) and reads the class's reflection record: an
internal constant global (Data "classrec", lowered in lower_module.py) emitted only for classes
that reach such a site, which LLVM's globaldce and llvm-link --only-needed drop otherwise.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import shown
from src.pystachy_compiler.analysis import clean_doc, local_names
from src.pystachy_compiler.ir import Data, FnInfo, Ins, Loop, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import HASATTR, ITERS, RANGEC
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import (
    targs,
    is_dict,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_tuple,
    is_union,
    is_vtuple,
    typestr,
    umembers,
    unopt,
)

# the record's flags (word 3): the class's objects have an instance __dict__, it is a dataclass, a
# frozen one, it is in an inheritance hierarchy (class tag), it is a builtin type
RF_DICT = 1
RF_DATACLASS = 2
RF_FROZEN = 4
RF_TAGGED = 8
RF_BUILTIN = 16

# the builtin types type(x) names for a statically typed value, by the start of its type
BUILTIN_TYPES: list[str] = ["int", "float", "bool", "str", "bytes", "None"]


class RLeaf:
    # one concrete case of a dispatch on a value's exact type (refl_split): its type ("None" for
    # None), the block where it starts and the value narrowed to it there
    def __init__(self, c: str, label: str, v: Val):
        self.c = c
        self.label = label
        self.v = v


def gen_refl_typeof(self, n: Node) -> Node | None:
    # the operand x of type(x) (the builtin, one positional argument) or of x.__class__ (an
    # object's: not a class or module name), or None
    if n.kind == "call" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s == "type" and not self.bound("type") and n.kids[1].kind != "kw" and n.kids[1].kind != "starred":
        return n.kids[1]
    if n.kind == "attr" and n.s == "__class__" and self.dotted(n) == "":
        x = n.kids[0]
        if x.kind == "name" and x.s in self.classes and x.s not in self.ltype:
            return None  # (C.__class__: the class's metaclass, type)
        return x
    return None


def gen_refl_concrete(self, t: str) -> list[str]:
    # the exact types a value of static type t may have, but None: its class and the classes
    # derived from it in a hierarchy, each member of a union (expanded alike), or t itself
    t = unopt(t)
    if is_union(t):
        out: list[str] = []
        for m in umembers(t):
            for c in self.refl_concrete(m):
                if c not in out:
                    out.append(c)
        return out
    if t in self.classes and self.classes[t].tag > 0:
        return [c.name for c in self.classes.values() if c.tag > 0 and self.derives(c.name, t) and c.name not in self.tmpl]
    return [t]


def gen_refl_may_none(self, v: Val) -> bool:
    # may value v be None at run time (an optional value, an object or a union that may be null)
    if v.t == "None":
        return True
    if v.v in self.nn:
        return False
    return is_opt(v.t) or v.t in self.classes or (is_union(v.t) and self.optional(v.t) == v.t)


def gen_refl_split(self, v: Val, nonnull: bool = False) -> list[RLeaf]:
    # dispatch on the exact type of v: None (where it may be, unless nonnull), then the union's
    # member tag and an object's class tag. Each leaf's block is left open for the caller to
    # place and fill; the blocks that test end here
    leaves: list[RLeaf] = []
    if v.t == "None":
        l0 = self.label()
        self.br(l0)
        return [RLeaf("None", l0, Val("null", "None"))]
    if self.refl_may_none(v) and not nonnull:
        ln = self.label()
        nn = self.label()
        self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, ln, nn)
        leaves.append(RLeaf("None", ln, Val("null", "None")))
        self.place(nn)
    t = unopt(v.t)
    if is_opt(v.t):
        v = self.deref(v)  # (an int's, float's or bool's box read: the value it holds)
    if is_union(t):
        tag = Ins("union.tag", "int", "")
        tag.a = [Val(v.v, t)]
        self.put(tag, 1)
        ms = umembers(t)
        for i in range(len(ms)):
            hit = self.label()
            miss = self.label() if i + 1 < len(ms) else ""
            if miss != "":
                self.cbr(self.num_cmp('==', Val(f"%t{tag.r[0]}", "int"), Val(str(self.utag(ms[i])), "int")).v, hit, miss)
            else:
                self.br(hit)
            self.place(hit)
            x = self.uget(Val(v.v, t), ms[i])
            leaves.extend(self.refl_split_class(x))
            if miss != "":
                self.place(miss)
        return leaves
    leaves.extend(self.refl_split_class(v))
    return leaves


def gen_refl_split_class(self, v: Val) -> list[RLeaf]:
    # the leaves of a value known not to be None: by its class tag in a hierarchy, else its type
    cs = self.refl_concrete(v.t)
    out: list[RLeaf] = []
    if len(cs) == 1:
        l1 = self.label()
        self.br(l1)
        return [RLeaf(cs[0], l1, Val(v.v, cs[0]))]
    tag = self.mload('int', v.v)
    for i in range(len(cs)):
        hit = self.label()
        miss = self.label() if i + 1 < len(cs) else ""
        if miss != "":
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.classes[cs[i]].tag), "int")).v, hit, miss)
        else:
            self.br(hit)
        out.append(RLeaf(cs[i], hit, Val(v.v, cs[i])))
        if miss != "":
            self.place(miss)
    return out


def gen_refl_type_name(self, c: str, what: str) -> str:
    # what type(x).<what> is (__name__, __qualname__ or __module__) for a value of exact type c,
    # or "" where Pystachy does not know it
    if c == "None" or c in BUILTIN_TYPES or is_list(c) or is_dict(c) or is_tuple(c) or is_vtuple(c) or is_set(c) or is_kw(c):
        b = "NoneType" if c == "None" else "list" if is_list(c) else "dict" if is_dict(c) or is_kw(c) else "tuple" if is_tuple(c) or is_vtuple(c) else c[: c.find("[")] if is_set(c) else c
        return "builtins" if what == "__module__" else b
    if c in self.classes and self.classes[c].exc == "":
        ci = self.classes[c]
        q = shown(ci.origin if ci.origin != "" else c)
        if c.startswith("_pystachy_iterators$") or c == RANGEC:
            return "builtins" if what == "__module__" else short(c)
        mod = q[: q.rfind(".")] if "." in q else "__main__"
        o = ci.origin if ci.origin != "" else c
        if o in self.cnts and self.cnts[o].kids[2].kind == "str":
            mod = self.cnts[o].kids[2].s  # (namedtuple(..., module=...)'s)
        return mod if what == "__module__" else short(c)
    return ""


def gen_refl_record(self, c: str) -> str:
    # the reflection record of exact type c (a class's specialization: its template's, which is
    # the class CPython has): an internal constant made once, the first time a site needs it.
    # Words: name, qualified name, module (strs), flags, the number of names and the sorted
    # name table (#489's run-time names, null until a site needs them), the number of fields and
    # the field table (names in __dict__ order, descriptors, offsets: null until needed)
    if c in self.classes and self.classes[c].origin != "":
        c = self.classes[c].origin
    key = ("c." + c) if c in self.classes else ("b." + self.refl_type_name(c, "__name__"))
    name = "@pys.refl." + key
    if name in self.reflrecs:
        return name
    d = Data("classrec", name)
    d.refs = [self.sconst(self.refl_type_name(c, "__name__")), self.sconst(self.refl_type_name(c, "__qualname__")), self.sconst(self.refl_type_name(c, "__module__")), "null", "null"]
    flags = RF_BUILTIN if c not in self.classes else 0
    if c in self.classes:
        ci = self.classes[c]
        flags += 0 if ci.slotlimit else RF_DICT
        flags += RF_DATACLASS if self.is_dc(c) and c not in self.nts else 0
        flags += RF_FROZEN if "frozen" in ci.dcopts else 0
        flags += RF_TAGGED if ci.tag > 0 else 0
    d.items = [Val(str(flags), "int"), Val("0", "int"), Val("0", "int")]
    self.consts.append(d)
    self.reflrecs[name] = d
    return name


def gen_refl_type_of(self, v: Val, what: str, nonnull: bool = False) -> list[RLeaf]:
    # the exact types v may have (None too, unless nonnull), each checked to have a name type(x)
    # gives (else an error)
    cs = self.refl_concrete(v.t)
    if self.refl_may_none(v) and not nonnull and "None" not in cs:
        cs = ["None"] + cs
    for c in cs:
        if self.refl_type_name(c, what) == "":
            self.err(f"type(x).{what} of {typestr(c)} is not supported (#486: user classes and the builtin types int, float, bool, str, bytes, list, dict, tuple, set and frozenset)")
    return [RLeaf(c, "", Val("", c)) for c in cs]


def gen_refl_class_of(self, v: Val, nonnull: bool = False) -> Val:
    # the reflection record of v's exact type (CPython's type(v)), as a machine pointer: one
    # record where its static type decides, else a phi over the dispatch's leaves (LLVM makes a
    # switch, or a lookup table, of the chain)
    cs = self.refl_type_of(v, "__name__", nonnull)
    if len(cs) == 1:
        return Val(self.refl_record(cs[0].c), "%ptr")
    leaves = self.refl_split(v, nonnull)
    end = self.label()
    ph = Ins("phi", "%ptr", "")
    for lf in leaves:
        self.place(lf.label)
        self.incoming(ph, self.refl_record(lf.c), self.cur)
        self.br(end)
    self.place(end)
    return Val(self.phi(ph), "%ptr")


def gen_refl_type_attr(self, x: Node, what: str) -> Val:
    # type(x).__name__ (__qualname__, __module__) and x.__class__.__name__: a constant where x's
    # type decides it, else the name in the record of its exact class (refl_class_of)
    v = self.expr(x, "")
    known = self.knownobj(x)
    if v.t == "exc" or (v.t in self.classes and self.classes[v.t].exc != ""):
        if what != "__name__" and what != "__qualname__":
            self.err(f"type(e).{what} of an exception is not supported; type(e).__name__ is")
        if v.t == "exc":
            return Val(self.rt("pys_exc_name", "ptr", [f"ptr {v.v}"]), "str")
        return Val(self.rt("pys_exc_cls", "ptr", [f"ptr {v.v}"]), "str")
    if v.t == "opt[exc]":
        # (an exception or None, as __exit__ and __cause__ give it: NoneType for None)
        if what != "__name__" and what != "__qualname__":
            self.err(f"type(e).{what} of an exception is not supported; type(e).__name__ is")
        e0 = self.cur
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, l2, l1)
        self.place(l1)
        nv = self.rt("pys_exc_name", "ptr", [f"ptr {v.v}"])
        e1 = self.cur
        self.br(l2)
        self.place(l2)
        ph = Ins("phi", "str", "")
        self.incoming(ph, self.sconst("NoneType"), e0)
        self.incoming(ph, nv, e1)
        return Val(self.phi(ph), "str")
    cs = self.refl_type_of(v, what, known)
    names = [self.refl_type_name(c.c, what) for c in cs]
    if len([s for s in names if s != names[0]]) == 0:
        return Val(self.sconst(names[0]), "str")
    rec = self.refl_class_of(v, known)
    word = 0 if what == "__name__" else 1 if what == "__qualname__" else 2
    a = self.maddr('%ptr', rec.v, str(word)) if word > 0 else rec.v
    return Val(self.mload('str', a), "str")


def gen_refl_type_operand(self, n: Node) -> str:
    # what an operand of a type comparison names statically, as refl_record takes it: a class
    # or a builtin type named by its name (C, int, list, ...); "" for type(x) and x.__class__
    if self.refl_typeof(n) is not None:
        return ""
    if n.kind == "name" and n.s in self.classes and n.s not in self.ltype and self.classes[n.s].exc == "":
        self.class_ready(n)
        return n.s
    if n.kind == "name" and n.s == "range" and RANGEC in self.classes and not self.bound(n.s):
        return RANGEC  # (lib/_pystachy_range.py's class)
    if n.kind == "name" and n.s in ["int", "float", "bool", "str", "bytes", "list", "dict", "tuple", "set", "frozenset"] and not self.bound(n.s):
        # (a container type's record is its name's: any element types)
        return "list[int]" if n.s == "list" else "dict[int,int]" if n.s == "dict" else "tuple[int]" if n.s == "tuple" else "set[int]" if n.s == "set" else "frozenset[int]" if n.s == "frozenset" else n.s
    if n.kind == "call" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s == "type" and n.kids[1].kind == "None" and not self.bound("type"):
        return "None"
    self.err("a comparison of type(x) is supported with type(y), y.__class__, a class or a builtin type's name (#486); class objects as values are not (#7)")
    return ""


def gen_refl_type_cmp(self, n: Node) -> Val | None:
    # type(a) is C, type(a) == type(b) and their negations (is not, !=), with type(x) or
    # x.__class__ on either side: a comparison of the records of the two exact types, which LLVM
    # folds where the static types decide it; None where n is no such comparison
    if n.kind != "cmp" or len(n.kids) != 2 or n.s not in ["is", "is not", "==", "!="]:
        return None
    if self.refl_typeof(n.kids[0]) is None and self.refl_typeof(n.kids[1]) is None:
        return None
    sides: list[Val] = []
    for k in n.kids:
        x = self.refl_typeof(k)
        if x is not None:
            v = self.expr(x, "")
            if v.t == "exc" or (v.t in self.classes and self.classes[v.t].exc != ""):
                self.err(f"unsupported call type({v.t}): type(e) of an exception is supported as type(e).__name__ (and isinstance(e, C) tests its class)")
            sides.append(self.refl_class_of(v, self.knownobj(x)))
        else:
            c = self.refl_type_operand(k)
            sides.append(Val(self.refl_record(c), "%ptr"))
    neg = n.s == "is not" or n.s == "!="
    if sides[0].v.startswith("@") and sides[1].v.startswith("@"):
        same = sides[0].v == sides[1].v
        return Val("true" if same != neg else "false", "bool")
    return Val(self.scalar_cmp('ne' if neg else 'eq', sides[0], sides[1]), "bool")


# ---- getattr, setattr and hasattr with a name the compiler knows (#486)
def gen_refl_name(self, n: Node) -> str:
    # the attribute name argument n gives at compile time: a str literal (or, in a class that
    # specializes on literals, a constant); "" where only the run time knows it
    if n.kind == "kw" or n.kind == "starred" or n.kind == "dstar":
        return ""
    if n.kind == "attr" and n.s == "name" and n.kids[0].kind == "dcfield":
        return n.kids[0].s  # (f.name of a dataclasses.Field: refl_unroll_fields)
    c = self.const_of(n, {}, True) if self.lit_context() else n if n.kind == "str" else None
    return c.s if c is not None and c.kind == "str" else ""


def gen_refl_args(self, name: str, args: list[Node], lo: int, hi: int) -> None:
    # getattr(), setattr(), hasattr() take positional arguments only, lo to hi of them
    for a in args:
        if a.kind == "kw":
            self.err(f"{name}() takes no keyword arguments")
        if a.kind == "starred" or a.kind == "dstar":
            self.err(f"star arguments of {name}() are not supported")
    if len(args) < lo or len(args) > hi:
        n = str(lo) if lo == hi else str(lo) + " or " + str(hi)
        self.err(f"{name} expected {n} arguments, got {len(args)}")


def gen_refl_has(self, c: str, a: str) -> str:
    # what hasattr(x, a) is for a value of exact type c: "y" true, "n" false, "f" its "is
    # assigned" flag says (a field __init__ may leave unassigned), "p" a property's getter says
    # (by raising AttributeError or not)
    if c in self.classes and self.classes[c].exc == "" and c not in self.nts:
        ci = self.classes[c]
        if a in ci.methods and ci.methods[a].prop:
            return "p"
        if a in ci.fflag and c + "." + a not in self.cvars:
            return "f"
    h = self.has(c, a)
    return "y" if h != 0 else "n"


def gen_refl_join(self, vals: list[Val], what: str) -> str:
    # the type of a value that is one of vals (an arm each): their join, or a union of them
    t = ""
    for v in vals:
        if t == "":
            t = v.t
        elif v.t != t:
            j = self.join(t, v.t)
            if j == "":
                j = self.union_type([t, v.t])
                if j.startswith("!"):
                    self.err(f"{what}: {typestr(t)} and {typestr(v.t)} have no common type ({j[1:]})")
            t = j
    return t


def gen_refl_phi(self, vals: list[Val], blocks: list[str], end: str, what: str) -> Val:
    # the value of the arms that reached end (each from its block), as one type (refl_join)
    self.place(end)
    if len(vals) == 0:
        self.unreachable()
        return Val("null", "None")
    t = self.refl_join(vals, what)
    if t == "None":
        return Val("null", "None")
    ph = Ins("phi", t, "")
    for j in range(len(vals)):
        self.incoming(ph, self.convert_at(vals[j], t, blocks[j]).v, blocks[j])
    return Val(self.phi(ph), t)


def gen_refl_catch_attr(self, x: Val, a: str, d: Val, vals: list[Val], blocks: list[str], end: str, truth: bool = False) -> None:
    # x.a, a property read, where an AttributeError its getter raises gives d instead (getattr's
    # default, or hasattr's False): the getter in a try block of its own, as CPython catches it;
    # with truth, True where the getter returns (hasattr)
    c = self.stop_catch()
    outer = self.handler
    self.handler = c.landing
    l = self.label()
    c.tr.body = l
    self.place(l)
    v = self.expr(mk("attr", a, self.line, [self.vnode(x)]), "")
    self.handler = outer
    if truth:
        v = Val("true", "bool")  # (hasattr: the getter returned)
    vals.append(v)
    blocks.append(self.cur)
    self.br(end)
    e = self.landing(c.landing, c.slot, c.mark)
    yes = self.label()
    no = self.label()
    self.cbr(self.exc_match(e, self.catch_set(mk("name", "AttributeError", self.line, []))), yes, no)
    self.place(no)
    self.throw(e)
    self.place(yes)
    self.rt("pys_exc_restore", "void", [f"ptr {c.old}"])
    c.tr.exit = end
    vals.append(d)
    blocks.append(self.cur)
    self.br(end)


def gen_refl_getattr(self, args: list[Node], want: str) -> Val:
    # getattr(o, name, default) with a name the compiler knows: per exact class of o, the
    # attribute where it has it, else the default (a property's getter that raises
    # AttributeError: the default too, as CPython catches it). o and default are evaluated first
    self.refl_args("getattr", args, 2, 3)
    a = self.refl_name(args[1])
    if a == "":
        self.err("getattr() of a name only the run time knows is supported where its text is used (print(), str(), repr(), an f-string field without a format spec): elsewhere its value would need a type of its own (#487, #489); use a str literal or a constant set of names (#486)")
    if len(args) == 2 and not self.refl_derived_only(args[0], a):
        return self.expr(mk("attr", a, args[0].line, [args[0]]), want)
    o = self.expr(args[0], "")
    known = self.knownobj(args[0])  # (a template's parameter whose argument is no None)
    d = self.expr(args[2], "") if len(args) == 3 else Val("", "")  # (none: CPython's AttributeError)
    if o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != ""):
        self.err("getattr() of an exception object is not supported (its fields are read as e.name, after except C as e)")
    vals: list[Val] = []
    blocks: list[str] = []
    end = self.label()
    narrow = dict(self.narrowed)
    for lf in self.refl_split(o, known):
        self.place(lf.label)
        self.narrowed = dict(narrow)
        h = self.refl_has(lf.c, a)
        if lf.c not in self.classes and h != "n":
            self.err(f"getattr() of '{a}' of {typestr(lf.c)}, a method or attribute of a builtin type, is not supported (#247)")
        if d.t == "" and (h == "n" or lf.c == "None"):
            cn = "NoneType" if lf.c == "None" else short(lf.c)
            self.raise_("AttributeError", self.sconst(f"'{cn}' object has no attribute '{a}'"))
            continue
        if d.t == "" and (h == "p" or h == "f"):
            h = "y"  # (the read raises CPython's AttributeError itself)
        if h == "p":
            self.refl_catch_attr(lf.v, a, d, vals, blocks, end)
            continue
        if h == "f":
            yes = self.label()
            no = self.label()
            self.cbr(self.mem_load(Val(self.fgep(lf.v, self.classes[lf.c].fflag[a]), "*bool")).v, yes, no)
            self.place(no)
            vals.append(d)
            blocks.append(self.cur)
            self.br(end)
            self.place(yes)
        v = d if h == "n" else self.expr(mk("attr", a, self.line, [self.vnode(lf.v)]), "")
        if not self.term:
            vals.append(v)
            blocks.append(self.cur)
            self.br(end)
    self.narrowed = narrow
    return self.refl_phi(vals, blocks, end, f"getattr(o, '{a}', default)")


def gen_refl_setattr(self, args: list[Node]) -> Val:
    # setattr(o, name, value): o.name = value, with o and value evaluated first (CPython's order)
    self.refl_args("setattr", args, 3, 3)
    a = self.refl_name(args[1])
    if a == "":
        return self.refl_setattr_runtime(args)
    o = self.expr(args[0], "")
    want = ""
    if o.t in self.classes and a in self.classes[o.t].ftypes:
        want = self.classes[o.t].ftypes[a]
    v = self.expr(args[2], want)
    if o.t in self.classes and a not in self.classes[o.t].ftypes and not self.is_prop(o.t, a) and self.classes[o.t].tag > 0:
        self.err(f"setattr() of '{a}' on a {short(o.t)}, which does not have it, would add an attribute to the object, which is not supported (#489)")
    self.assign(mk("attr", a, self.line, [self.vnode(o)]), v)
    return Val("null", "None")


# ---- which programs need exceptions on (Gen.program): a property's getter that a reflective
# lookup calls may raise AttributeError, which getattr() with a default and hasattr() catch
def refl_props(n: Node, out: dict[str, bool]) -> None:
    # the names of the properties the classes in n define (a def decorated @property)
    if n.kind == "def":
        for k in n.kids:
            if k.kind == "deco" and (k.s == "property" or k.s.endswith("$property") or k.s.endswith(".property")):
                out[n.s] = True
    for k in n.kids:
        refl_props(k, out)


def refl_needs_eh(n: Node, props: dict[str, bool]) -> bool:
    # does n hold getattr(o, name, default) or hasattr(o, name) whose name may be a property's:
    # one of props, or a name the run time decides (only where the program has properties)
    if len(props) > 0 and n.kind == "call" and n.kids[0].kind == "name" and ((n.kids[0].s == "getattr" and len(n.kids) == 4) or (n.kids[0].s == "hasattr" and len(n.kids) == 3)):
        a = n.kids[2]
        if a.kind != "str" or a.s in props:
            return True
    for k in n.kids:
        if refl_needs_eh(k, props):
            return True
    return False


# ---- loops over constant sets of attribute names, unrolled (#486)
REFL_BUDGET = 256  # the most copies of a loop body that unrolling compiles (nested loops: their product)


def refl_lits(n: Node) -> list[str] | None:
    # the names a tuple or list display of str literals holds, else None
    if (n.kind != "tuple" and n.kind != "list") or len(n.kids) == 0:
        return None
    out: list[str] = []
    for k in n.kids:
        if k.kind != "str":
            return None
        out.append(k.s)
    return out


def refl_reflective(n: Node, name: str) -> bool:
    # does code n use name as an attribute name: getattr(o, name...), setattr(o, name, v),
    # hasattr(o, name), operator's attrgetter(name) or methodcaller(name, ...) (not in the defs,
    # lambdas and classes in it)
    if n.kind == "def" or n.kind == "lambda" or n.kind == "class" or n.kind == "subclass":
        return False
    if n.kind == "call" and len(n.kids) >= 3 and n.kids[0].kind == "name" and n.kids[0].s in ["getattr", "setattr", "hasattr", "delattr"] and n.kids[2].kind == "name" and n.kids[2].s == name:
        return True
    if n.kind == "call" and len(n.kids) >= 2 and n.kids[1].kind == "name" and n.kids[1].s == name and refl_formatter(n.kids[0]) and len([a for a in n.kids[2:] if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) == 0:
        return True  # (string.Formatter().format(name, ...): a constant template, see refl_formatter)
    if n.kind == "call" and len(n.kids) >= 2 and n.kids[1].kind == "name" and n.kids[1].s == name and (n.kids[0].kind == "name" or n.kids[0].kind == "attr"):
        f = n.kids[0].s[n.kids[0].s.rfind("$") + 1 :]  # (operator$attrgetter: the loader's name for an import)
        if f == "attrgetter" or f == "methodcaller":
            return True
    for k in n.kids:
        if refl_reflective(k, name):
            return True
    return False


def refl_scoped(n: Node) -> bool:
    # does code n define a function, lambda or class (whose code a copy of it would compile again)
    if n.kind == "def" or n.kind == "lambda" or n.kind == "class" or n.kind == "subclass":
        return True
    for k in n.kids:
        if refl_scoped(k):
            return True
    return False


def refl_binds_in(n: Node, name: str) -> bool:
    # does comprehension n bind name as a variable of its own
    if n.kind == "name":
        return n.s == name
    if n.kind == "listcomp" or n.kind == "setcomp" or n.kind == "dictcomp" or n.kind == "nestedcomp":
        for k in n.kids[1:]:
            if k.kind != "listcomp" and k.kind != "nestedcomp" and refl_binds_in(k, name):
                return True
    for k in n.kids:
        if (k.kind == "listcomp" or k.kind == "nestedcomp") and refl_binds_in(k, name):
            return True
    return False


def refl_subst(n: Node, name: str, lit: Node) -> Node:
    # a copy of code n whose reads of name are lit (but in a comprehension that binds name)
    if n.kind == "name" and n.s == name:
        c = Node(lit.kind, lit.s, n.line)
        c.kids = lit.kids
        return c
    c = Node(n.kind, n.s, n.line)
    c.chk = n.chk
    c.mchk = n.mchk
    c.depth = n.depth
    keep = (n.kind == "listcomp" or n.kind == "setcomp" or n.kind == "dictcomp") and refl_binds_in(n, name)
    for k in n.kids:
        c.kids.append(clone_node(k) if keep else refl_subst(k, name, lit))
    return c


def clone_node(n: Node) -> Node:
    c = Node(n.kind, n.s, n.line)
    c.kids = [clone_node(k) for k in n.kids]
    c.chk = n.chk
    c.mchk = n.mchk
    c.depth = n.depth
    return c


def refl_uses(n: Node, name: str, out: list[int]) -> None:
    # count in out the name nodes of name in n: [all of them, those that are a for statement's
    # or a comprehension's iterable, the assignments that bind it to a display of str literals]
    if n.kind == "name" and n.s == name:
        out[0] += 1
    if n.kind == "for" and len(n.kids) > 1 and n.kids[1].kind == "name" and n.kids[1].s == name:
        out[1] += 1
    if (n.kind == "listcomp" or n.kind == "setcomp" or n.kind == "dictcomp") and len(n.kids) == 3 and n.kids[2].kind == "name" and n.kids[2].s == name:
        out[1] += 1
    if (n.kind == "assign" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s == name and refl_lits(n.kids[1]) is not None) or (n.kind == "annassign" and len(n.kids) == 3 and n.kids[0].kind == "name" and n.kids[0].s == name and refl_lits(n.kids[2]) is not None):
        out[2] += 1
    for k in n.kids:
        refl_uses(k, name, out)


def gen_refl_bound_once(self, name: str) -> list[str] | None:
    # the names held by variable name where one statement of its scope's own code binds it to a
    # tuple or list display of str literals and its every other use is as a for loop's (or a
    # comprehension's) iterable: a local of the function, or a variable of the main program's
    # module; else None
    local = not self.modlevel and (name in self.ltype or name in self.assigned) and name not in self.gdecl
    if "$" in name or (not local and (self.curfn.mod != "" or "" not in self.inits)):
        return None
    if local and (self.curfn.node.kind != "def" or name in self.curfn.params or len([p for p in self.curfn.node.kids[0].kids if p.s == name]) > 0):
        return None  # (a parameter, which a loop may iterate before the statement binds it again)
    scope = self.curfn.node.kids[2] if local else self.inits[""].node
    body = scope.kids
    lits: list[str] | None = None
    for st in body:
        if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s == name:
            lits = refl_lits(st.kids[1])
        if st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name" and st.kids[0].s == name:
            lits = refl_lits(st.kids[2])
    if lits is None:
        return None
    out = [0, 0, 0]
    refl_uses(scope, name, out)
    return lits if out[2] == 1 and out[0] == out[1] + 1 else None


def gen_refl_const_names(self, it: Node) -> list[str] | None:
    # the attribute names a loop's iterable it gives, where they are constants: a tuple or list
    # display of str literals, or a variable bound once to one and only iterated (see bound_once)
    lits = refl_lits(it)
    if lits is not None:
        return lits
    if it.kind == "name" and not it.chk:
        return self.refl_bound_once(it.s)
    if self.refl_dir_of(it) is not None:
        return []  # (dir(x)'s, once x is evaluated: refl_unroll_for)
    return None


def gen_refl_unroll_for(self, n: Node) -> bool:
    # for name in <constant names>: body, where body uses name as an attribute name: the body
    # once per name, each with name read as that literal (name is still assigned it, for the code
    # after the loop): continue goes on to the next copy, break past the loop (and its else
    # block). Over dir(x), one such run per exact class x may have (refl_split)
    tgt = n.kids[0]
    it = n.kids[1]
    body = n.kids[2].kids
    if n.kind != "for":
        return False
    m = ""
    x = self.refl_dict_of(it)
    if x is None and it.kind == "call" and len(it.kids) == 1 and it.kids[0].kind == "attr" and it.kids[0].s in ["items", "keys", "values"]:
        x = self.refl_dict_of(it.kids[0].kids[0])
        m = it.kids[0].s if x is not None else ""
        if x is not None:
            it = it.kids[0].kids[0]
    if x is not None:
        self.refl_unroll_dict(n, it, x, "keys" if m == "" else m)
        return True
    fns = self.refl_dc_names(it)
    if fns is not None:
        self.refl_unroll_fields(n, fns)
        return True
    if tgt.kind != "name":
        return False
    names = self.refl_const_names(it)
    if names is None or not refl_reflective(n.kids[2], tgt.s):
        return False
    asg: dict[str, bool] = {}
    local_names(body, asg)
    if tgt.s in asg or refl_scoped(n.kids[2]):
        return False  # (the run-time name it then is: see refl_getattr)
    groups: list[list[str]] = [names]
    labels: list[str] = [""]
    narrow: list[str] = [""]  # (each group's class, which a variable x of dir(x) is narrowed to)
    objs: list[Val] = [Val("", "")]  # (and its object, whose fields' flags decide the names listed)
    if it.kind == "name":
        self.expr(it, "")  # (its read checks that it is assigned, as the loop's would)
    dx = self.refl_dir_of(it)
    if dx is not None:
        o = self.expr(dx, "")
        groups = []
        labels = []
        narrow = []
        objs = []
        xt = self.ltype.get(dx.s, "") if dx.kind == "name" and dx.s not in asg and self.narrowable(dx.s) else ""
        for lf in self.refl_split(o, self.knownobj(dx)):
            labels.append(lf.label)
            narrow.append(lf.c if xt in self.classes and self.classes[xt].tag > 0 and lf.c in self.classes and lf.c != xt and self.derives(lf.c, xt) else "")
            objs.append(lf.v)
            g: list[str] = []
            for nk in self.refl_dir_names(lf.c):
                g.append(nk[0] if lf.c not in self.classes or self.refl_listed(lf.c, nk) else " " + nk[0])  # (" ": where its flag is set)
            groups.append(g)
    total = 0
    for g in groups:
        total += len(g)
    if total * self.reflcopies > REFL_BUDGET:
        self.err(f"unrolling this loop over {total} attribute names would compile its body {total * self.reflcopies} times, more than the budget of {REFL_BUDGET} copies (#486): use fewer names, or a literal name in each call")
    brk = self.elsebrk if n.kids[2].kids is self.elsekids else self.label()
    after = self.forget(body, tgt)
    outer = self.reflcopies
    self.reflcopies = outer * max(total, 2)
    brks: list[dict[str, str]] = []
    join = self.label()
    for gi in range(len(groups)):
        if labels[gi] != "":
            self.place(labels[gi])
        # (dir() lists a field __init__ may leave unassigned where its flag is set as the loop
        # starts: the list it makes then is what the loop goes through)
        snap: dict[str, str] = {}
        for nm in groups[gi]:
            if nm.startswith(" "):
                snap[nm] = self.mem_load(Val(self.fgep(objs[gi], self.classes[objs[gi].t].fflag[nm[1:]]), "*bool")).v
        for entry in groups[gi]:
            nxt = self.label()
            nm = entry[1:] if entry.startswith(" ") else entry
            if entry.startswith(" "):
                go = self.label()
                self.cbr(snap[entry], go, nxt)
                self.place(go)
            self.narrowed = dict(after)
            if narrow[gi] != "":
                self.narrowed[dx.s if dx is not None else ""] = narrow[gi]  # (its object's exact class here)
            self.assign(tgt, Val(self.sconst(nm), "str"))
            lp = Loop("while", self.cur, self.cur, nxt, brk)
            self.loops.append(lp)
            self.wdepth.append(len(self.exits))
            self.brks.append([])
            self.branch += 1
            self.stmts([refl_subst(st, tgt.s, mk("str", nm, st.line, [])) for st in body])
            self.branch -= 1
            self.wdepth.pop()
            self.loops.pop()
            brks.extend(self.brks.pop())
            self.br(nxt)
            self.place(nxt)
        self.br(join)
    self.place(join)
    self.reflcopies = outer
    self.narrowed = after
    if n.kids[2].kids is self.elsekids:
        self.elsebrks = brks
    else:
        self.br(brk)
        self.place(brk)
    return True


# ---- the names an object answers to (dir(), run-time names) and its __dict__ (vars())
def refl_body(cn: Node) -> list[Node]:
    # the statements of class statement cn's body
    for k in cn.kids:
        if k.kind == "block":
            return k.kids
    return []


def refl_annotated(body: list[Node]) -> bool:
    # does a class body annotate a name (x: int): its class has __annotations__
    for st in body:
        if st.kind == "annassign" and st.kids[0].kind == "name" and st.kids[1].kind != "noann":
            return True  # (not a class attribute's x = v, which the class statement makes an annassign)
    return False


def gen_refl_supported(self, c: str, what: str) -> None:
    # the classes whose names reflection knows: the program's ordinary classes and dataclasses
    if c not in self.classes:
        return
    ci = self.classes[c]
    why = ""
    if ci.exc != "":
        why = "an exception class"
    elif c in self.nts:
        why = "a NamedTuple"
    elif c.startswith(ITERS + "$"):
        why = "an iterator of a builtin container"
    elif c == RANGEC:
        why = "a range"
    elif ci.bad != "":
        why = ci.bad
    if why != "":
        self.err(f"{what} of a {short(c)} object is not supported: {why} (#486)")


def gen_refl_defines(self, c: str, m: str) -> bool:
    # does a class statement (c's, or a base's whose method c inherits) define method m, or
    # @dataclass write it: a function of the class, which CPython binds (not object's slot wrapper)
    ci = self.classes[c]
    if m not in ci.methods:
        return False
    f = ci.methods[m]
    if f.synthetic or (m == "__init__" and self.is_dc(f.cls) and "no-init" not in self.classes[f.cls].dcopts if f.cls in self.classes else False):
        return True
    owner = f.cls if f.cls in self.classes else c
    for st in refl_body(self.classes[owner].node):
        if st.kind == "def" and st.s == m:
            return True
    return False


def gen_refl_names(self, c: str) -> list[list[str]]:
    # every name an object of class c answers to, as dir(o) lists them (sorted by their bytes),
    # with its kind: "f" a field (an instance attribute), "g" one __init__ may leave unassigned
    # (its flag says), "c" a class attribute, "p" a property, "m" a method, "s" a static and "k" a
    # class method, "o" one object, its type or @dataclass gives (see refl_otext), "u" a slot that
    # no code assigns (an attribute an object never has)
    self.refl_supported(c, "reflection")
    ci = self.classes[c]
    out: dict[str, str] = {}
    for n in HASATTR["any"].split():
        out[n] = "o"
    for n in ["__module__", "__firstlineno__", "__static_attributes__"]:
        out[n] = "o"
    if not ci.slotlimit:
        out["__dict__"] = "o"
        out["__weakref__"] = "o"
    k = c
    while k in self.classes:
        if refl_annotated(refl_body(self.classes[k].node)):
            out["__annotations__"] = "o"  # (a dataclass without fields has none)
        o = self.classes[k].origin if self.classes[k].origin != "" else k
        if o in self.tparams:
            # a generic class's (Generic[T], class C[T]), which its subclasses inherit or get
            for n in ["__class_getitem__", "__orig_bases__", "__parameters__"] + (["__type_params__"] if o in self.pep695 else []):
                out[n] = "o"
        k = self.classes[k].base
    if self.abc_class(c):
        for n in ["__abstractmethods__", "_abc_impl"]:
            out[n] = "o"  # (ABCMeta's, which it sets on each class it makes)
    if self.is_dc(c):
        for n in ["__dataclass_fields__", "__dataclass_params__", "__replace__"]:
            out[n] = "o"
        if self.has(c, "__match_args__") != 0:
            out["__match_args__"] = "o"
    for m in ci.methods:
        f = ci.methods[m]
        if "." in m:
            continue  # (a property's setter or deleter: x.setter)
        if f.prop:
            out[m] = "p"
        elif f.deco == "staticmethod":
            out[m] = "s"
        elif f.deco == "classmethod":
            out[m] = "k"
        elif self.refl_defines(c, m):
            out[m] = "m"
    for fl in ci.ftypes:
        if fl.startswith(" "):
            continue  # (the class tag)
        if fl in ci.fdefault and (fl not in ci.fopts or c in self.nts):
            out[fl] = "c"
        elif fl in ci.fflag and c + "." + fl not in self.cvars:
            out[fl] = "g"
        else:
            out[fl] = "f"
    for fl in ci.slots:
        if fl not in out:
            out[fl] = "u"  # (a slot no code assigns: listed, but never set)
    for n in out:
        self.refl_public(c, n)
    return [[n, out[n]] for n in sorted(out.keys())]


def gen_refl_public(self, c: str, n: str) -> None:
    # attribute n of class c, whose name reflection shows, must not be private (__x): CPython's
    # compiler mangles such a name in a class body (to _C__x), which Pystachy does not
    if n.startswith("__") and not n.endswith("__") and "." not in n:
        self.err(f"reflection over a {short(c)} object is not supported: CPython mangles the name of its private attribute {n} (to _ClassName{n}), which Pystachy does not (#486)")


def gen_refl_listed(self, c: str, nk: list[str]) -> bool:
    # does dir() of an object of class c list name nk (refl_names) whatever the object: all but a
    # field __init__ may leave unassigned, which is listed where its flag is set (a slot always is:
    # its descriptor is the class's)
    return nk[1] != "g" or nk[0] in self.classes[c].slots


def refl_self_stores(n: Node, me: str, out: list[str]) -> None:
    # the attributes code n assigns through me (me.x = ..., me.x: T = ..., (me.a, me.b) = ...,
    # me.x += ...), in order (not in the defs, lambdas and classes in it)
    if n.kind == "def" or n.kind == "lambda" or n.kind == "class" or n.kind == "subclass":
        return
    if n.kind == "attr" and n.kids[0].kind == "name" and n.kids[0].s == me:
        return
    if n.kind == "assign" or (n.kind == "annassign" and len(n.kids) == 3) or n.kind == "augassign":
        # (an annotation without a value, me.x: int, assigns nothing)
        ts = n.kids[:-1] if n.kind == "assign" else n.kids[:1]
        for t in ts:
            refl_target_stores(t, me, out)
    for k in n.kids:
        refl_self_stores(k, me, out)


def refl_target_stores(t: Node, me: str, out: list[str]) -> None:
    if t.kind == "attr" and t.kids[0].kind == "name" and t.kids[0].s == me:
        if t.s not in out:
            out.append(t.s)
    elif t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
        for k in t.kids:
            refl_target_stores(k, me, out)


def gen_refl_init_order(self, c: str, f: FnInfo, out: list[str], maybe: dict[str, bool]) -> bool:
    # append to out the attributes __init__ f assigns to its object (of class c), in the order a
    # run assigns them first: its body's own statements one by one, a super().__init__(...) or
    # Base.__init__(self, ...) statement in the base's. A branch or loop may assign one new
    # attribute (where it runs: the field's flag says), which no later statement assigns after
    # another new one. False where that order is not known (more new attributes in one branch or
    # loop, an assignment through a property's setter). maybe gets the attributes a branch or
    # loop assigns first, which an object may lack after its __init__
    if len(f.params) == 0 or f.node.kind != "def":
        return False
    me = f.params[0]
    cond: dict[str, int] = {}  # (an attribute a branch or loop assigns first: len(out) then)
    for st in f.node.kids[2].kids:
        if st.kind == "expr" and st.kids[0].kind == "call" and st.kids[0].kids[0].kind == "attr" and st.kids[0].kids[0].s == "__init__":
            r = st.kids[0].kids[0].kids[0]
            base = self.classes[f.cls].base if f.cls in self.classes else ""
            if base not in self.classes or self.classes[base].exc != "":
                return False
            if (r.kind == "call" and r.kids[0].kind == "name" and r.kids[0].s == "super") or (r.kind == "name" and r.s == base):
                if "__init__" in self.classes[base].methods and not self.refl_init_order(c, self.classes[base].methods["__init__"], out, maybe):
                    return False
                continue
        stores: list[str] = []
        refl_self_stores(st, me, stores)
        for x in stores:
            if self.is_prop(c, x):
                return False
            if x in cond and len(out) > cond[x]:
                return False
        if st.kind == "assign" or st.kind == "annassign" or st.kind == "augassign":
            for x in stores:
                if x not in out:
                    out.append(x)
                if x in maybe:
                    del maybe[x]  # (assigned whatever the branch did)
            continue
        new = [x for x in stores if x not in out]
        if len(new) > 1:
            return False
        if len(new) == 1:
            out.append(new[0])
            cond[new[0]] = len(out)
            maybe[new[0]] = True
    return True


def gen_refl_dict_order(self, c: str) -> list[str]:
    # the names in the __dict__ of an object of class c, in the order CPython inserts them: the
    # fields __init__ assigns (a dataclass's: its fields), each where it is first assigned;
    # an error where Pystachy does not know that order
    self.refl_supported(c, "vars() or __dict__")
    ci = self.classes[c]
    if ci.slotlimit:
        self.err(f"'{short(c)}' object has no attribute '__dict__' (its class defines __slots__): vars() argument must have __dict__ attribute")
    out: list[str] = []
    maybe: dict[str, bool] = {}  # (those an object may lack after its __init__)
    if self.is_dc(c) and c not in self.nts and "no-init" not in ci.dcopts:
        for fl in self.dc_fields(ci):
            if "no-init" in ci.fopts[fl] and fl not in ci.fdefault and fl not in ci.factory:
                self.err(f"vars() of {short(c)}, whose field {fl} its __init__ leaves unassigned, is not supported (#486)")
            out.append(fl)
        if "__post_init__" in ci.methods:
            pi = ci.methods["__post_init__"]
            if not self.refl_init_order(c, pi, out, maybe):
                self.err(f"vars() of {short(c)} is not supported: the order its __post_init__ assigns attributes in is not known at compile time (#486)")
    elif "__init__" in ci.methods and not self.refl_init_order(c, ci.methods["__init__"], out, maybe):
        self.err(f"vars() of {short(c)} is not supported: the order its __init__ assigns attributes in is not known at compile time (an assignment in a branch, a loop or a property's setter) (#486)")
    for fl in out:
        if fl not in ci.ftypes:
            self.err(f"vars() of {short(c)} is not supported: it assigns attribute {fl}, which is no field of its class (#486)")
        self.refl_public(c, fl)
    # (a field __init__ may leave unassigned that other code may assign: inserted last then)
    late = [fl for fl in out if fl in maybe and self.refl_late(fl)]
    if len(late) > 1 or (len(late) == 1 and late[0] != out[-1]):
        self.err(f"vars() of {short(c)} is not supported: its attribute {late[0]}, which its __init__ may leave unassigned, may be assigned later, which inserts it last in the __dict__ (#486)")
    for fl in ci.ftypes:
        if fl.startswith(" ") or fl in out:
            continue
        if fl in ci.fdefault and (fl not in ci.fopts or c in self.nts):
            if self.refl_stored(fl):
                self.err(f"vars() of {short(c)} is not supported: its class attribute {fl} may be assigned through an object, which then holds it in its __dict__ (#486)")
            continue  # (a class attribute: not in the object's __dict__)
        self.err(f"vars() of {short(c)} is not supported: its attribute {fl} is assigned outside __init__, where the order of the __dict__ is not known at compile time (#486)")
    return out


def refl_attr_stores(n: Node, out: dict[str, bool]) -> None:
    # the attribute names that assignments in n assign (o.x = ..., o.x += ..., for o.x in ...)
    if n.kind == "assign" or n.kind == "annassign" or n.kind == "augassign" or n.kind == "for":
        ts = n.kids[:-1] if n.kind == "assign" else n.kids[:1]
        for t in ts:
            refl_attr_targets(t, out)
    for k in n.kids:
        refl_attr_stores(k, out)


def refl_attr_targets(t: Node, out: dict[str, bool]) -> None:
    if t.kind == "attr":
        out[t.s] = True
    elif t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
        for k in t.kids:
            refl_attr_targets(k, out)


def gen_refl_stored(self, name: str) -> bool:
    # does any assignment of the program assign an attribute called name (or setattr() any
    # attribute): a class attribute of that name may be in an object's __dict__
    if len(self.reflstores) == 0:
        self.reflstores[" "] = True
        for m in self.inits:
            refl_attr_stores(self.inits[m].node, self.reflstores)
            if refl_calls(self.inits[m].node, "setattr"):
                self.reflstores["  setattr"] = True
    return name in self.reflstores or "  setattr" in self.reflstores


def gen_refl_late(self, name: str) -> bool:
    # may code other than an __init__'s (or __post_init__'s) own statements assign an attribute
    # called name: a field __init__ leaves unassigned is then inserted last in the object's
    # __dict__ (setattr() with a name that is no literal may assign any)
    if len(self.refllate) == 0:
        self.refllate[" "] = True
        for m in self.inits:
            refl_late_stores(self.inits[m].node, self.refllate, "")
    return name in self.refllate or "  any" in self.refllate


def refl_late_stores(n: Node, out: dict[str, bool], me: str) -> None:
    # the attribute names that code n assigns (see refl_late), but those assigned through me, the
    # first parameter of the __init__ or __post_init__ whose own statements n is in
    if n.kind == "def":
        me = n.kids[0].kids[0].s if (n.s == "__init__" or n.s == "__post_init__") and len(n.kids[0].kids) > 0 else ""
    elif n.kind == "lambda" or n.kind == "class" or n.kind == "subclass":
        me = ""
    ts: list[Node] = []
    if n.kind == "assign":
        ts = n.kids[:-1]
    elif n.kind == "annassign" and len(n.kids) == 3:
        ts = n.kids[:1]
    elif n.kind == "augassign" or n.kind == "for" or n.kind == "compfor":
        ts = n.kids[:1]
    elif (n.kind == "listcomp" or n.kind == "asynccomp") and len(n.kids) > 1:
        ts = n.kids[1:2]
    elif n.kind == "withitem" and len(n.kids) == 2:
        ts = n.kids[1:]
    for t in ts:
        refl_late_targets(t, out, me)
    if n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s == "setattr":
        if len(n.kids) >= 3 and n.kids[2].kind == "str":
            out[n.kids[2].s] = True
        else:
            out["  any"] = True
    for k in n.kids:
        refl_late_stores(k, out, me)


def refl_late_targets(t: Node, out: dict[str, bool], me: str) -> None:
    if t.kind == "attr" and not (me != "" and t.kids[0].kind == "name" and t.kids[0].s == me):
        out[t.s] = True
    elif t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
        for k in t.kids:
            refl_late_targets(k, out, me)


def refl_calls(n: Node, f: str) -> bool:
    if n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s == f:
        return True
    for k in n.kids:
        if refl_calls(k, f):
            return True
    return False


def gen_refl_fields_table(self, c: str) -> str:
    # the record of class c (its exact class: a template's specialization has its own layout)
    # with its field table, which pys_refl_vars walks: c's __dict__ order, descriptors, offsets
    order = self.refl_dict_order(c)
    ci = self.classes[c]
    rec = self.refl_layout_record(c)
    d = self.reflrecs[rec]
    if d.refs[4] == "null":
        t = Data("classfields", rec + ".fields")
        t.text = "%C." + c
        for fl in order:
            ft = ci.ftypes[fl]
            if is_union(unopt(ft)) and not self.value_union(ft):
                self.err(f"vars() of {short(c)}, whose field {fl} is a {typestr(ft)}, is not supported (a union of classes: #487)")
            t.refs.append(self.sconst(fl))
            t.refs.append(self.sconst(self.desc(ft, "repr")))
            t.items.append(Val(str(ci.fpos[fl]), "int"))
            flag = ci.fflag[fl] if fl in ci.fflag and c + "." + fl not in self.cvars else -1
            t.items.append(Val(str(flag), "int"))
        self.consts.append(t)
        d.refs[4] = t.name
        d.items[2] = Val(str(len(order)), "int")
    return rec


def gen_refl_layout_record(self, c: str) -> str:
    # the record of exact class c itself (refl_record names a specialization by its template's,
    # the class CPython has; a field table belongs to the specialization's own layout)
    if c in self.classes and self.classes[c].origin != "":
        name = "@pys.refl.c." + c
        if name not in self.reflrecs:
            self.refl_record(self.classes[c].origin)
            base = self.reflrecs["@pys.refl.c." + self.classes[c].origin]
            d = Data("classrec", name)
            d.refs = [base.refs[0], base.refs[1], base.refs[2], "null", "null"]
            d.items = [base.items[0], Val("0", "int"), Val("0", "int")]
            self.consts.append(d)
            self.reflrecs[name] = d
        return name
    return self.refl_record(c)


def gen_refl_dict_of(self, n: Node) -> Node | None:
    # the operand x of vars(x) or x.__dict__ (an object's: not a module's or class's), or None
    if n.kind == "call" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s == "vars" and not self.bound("vars") and n.kids[1].kind != "kw" and n.kids[1].kind != "starred":
        return n.kids[1]
    if n.kind == "attr" and n.s == "__dict__" and self.dotted(n) == "":
        x = n.kids[0]
        if x.kind == "name" and x.s in self.classes and x.s not in self.ltype:
            return None
        return x
    return None


def gen_refl_vars_text(self, o: Val, known: bool) -> Val:
    # repr(vars(o)): the runtime's walk of the field table of o's exact class
    leaves = self.refl_type_of(o, "__name__", known)
    for lf in leaves:
        if lf.c == "None" or lf.c not in self.classes:
            self.err(f"vars() argument must have __dict__ attribute: of a {typestr(lf.c)}, it is not supported (#486)")
        self.refl_fields_table(lf.c)
    if len(leaves) == 1:
        rec = Val(self.refl_layout_record(leaves[0].c), "%ptr")
    else:
        sp = self.refl_split(o, known)
        end = self.label()
        ph = Ins("phi", "%ptr", "")
        po = Ins("phi", "%ptr", "")  # (the object itself: a union's member, not its box)
        for lf in sp:
            self.place(lf.label)
            self.incoming(ph, self.refl_layout_record(lf.c), self.cur)
            self.incoming(po, lf.v.v, self.cur)
            self.br(end)
        self.place(end)
        rec = Val(self.phi(ph), "%ptr")
        o = Val(self.phi(po), "%ptr")
    return Val(self.rt("pys_refl_vars", "ptr", [f"ptr {rec.v}", f"ptr {o.v}"]), "str")


# ---- text of what a reflective lookup finds, for consumers that need no value of it
class RText:
    # a deferred text (refl_defer): what vars(o) or getattr(o, name[, default]) looked up as its
    # argument was evaluated, made a str when its consumer converts it (print() converts its
    # arguments once all are evaluated; str(), repr() and f-strings at once)
    def __init__(self, kind: str, o: Val, known: bool):
        self.kind = kind  # "vars" or "getattr"
        self.o = o
        self.known = known  # (o is a template's parameter whose argument is no None)
        self.sel = ""  # getattr: the slot of the arm taken (refl_lookup)
        self.arms: list[RArm] = []


class RArm:
    # one name a run-time getattr may find (refl_lookup): its index, the exact class of its object,
    # the kind of the name (refl_names; "d" the default, "x" the miss), the name, and the slot of
    # the value it found (a value's) or of its object (a method's, an object's own attribute)
    def __init__(self, k: int, c: str, kind: str, name: str):
        self.k = k
        self.c = c
        self.kind = kind
        self.name = name
        self.slot = ""
        self.t = ""


def gen_refl_textual(self, n: Node) -> bool:
    # is n vars(x), x.__dict__ or getattr(x, name[, default]) with a run-time name: what only a
    # consumer of its text supports
    if self.refl_dict_of(n) is not None:
        return True
    return n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s == "getattr" and not self.bound("getattr") and (len(n.kids) == 3 or len(n.kids) == 4) and self.refl_name(n.kids[2]) == "" and n.kids[2].kind not in ["kw", "starred", "dstar"]


def gen_refl_defer(self, n: Node) -> Val:
    # evaluate n (see refl_textual) as its consumer's argument: a "%refl" value, the index of its
    # RText, which refl_finish makes the text of
    x = self.refl_dict_of(n)
    if x is not None:
        o = self.refl_dict_operand(n, x)
        r = RText("vars", o, True)
    else:
        r = self.refl_lookup(n)
    self.refltexts.append(r)
    return Val(str(len(self.refltexts) - 1), "%refl")


def gen_refl_finish(self, v: Val, conv: str) -> Val:
    # the text of deferred value v (refl_defer): str() of it (conv "str"), or repr() ("repr")
    r = self.refltexts[int(v.v)]
    if r.kind == "vars":
        return self.refl_vars_text(r.o, r.known)
    return self.refl_lookup_text(r, conv)


def gen_refl_dict_operand(self, n: Node, x: Node) -> Val:
    # the object of vars(x) or x.__dict__ (n), evaluated: None raises CPython's error there, and
    # each class it may have must have a __dict__ whose order is known (refl_dict_order)
    o = self.expr(x, "")
    known = self.knownobj(x)
    if o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != ""):
        self.err("vars() and __dict__ of an exception object are not supported (#486)")
    for lf in self.refl_type_of(o, "__name__", known):
        if lf.c == "None":
            msg = "TypeError: vars() argument must have __dict__ attribute" if n.kind == "call" else "AttributeError: 'NoneType' object has no attribute '__dict__'"
            self.guard(self.ptr_cmp('==', o, Val('null', 'None')).v, msg)
        elif lf.c not in self.classes:
            self.err(f"vars() argument must have __dict__ attribute: of a {typestr(lf.c)}, it is not supported (#486)" if n.kind == "call" else f"type {typestr(lf.c)} has no attribute '__dict__'")
        else:
            self.refl_dict_order(lf.c)
    return o


def gen_refl_unroll_dict(self, n: Node, d: Node, x: Node, m: str) -> None:
    # for k, v in vars(x).items() (x.__dict__, .keys(), .values(), or the dict itself): the body
    # once per name in its __dict__ (refl_dict_order), each reading the attribute as that copy
    # starts, as CPython's iterator over the live __dict__ does (a field __init__ may leave
    # unassigned: only where its flag is set); k is that name, v the value as the join of the
    # fields' types. One run of copies per exact class x may have (refl_split)
    tgt = n.kids[0]
    body = n.kids[2].kids
    o = self.refl_dict_operand(d, x)
    if refl_scoped(n.kids[2]):
        self.err("a loop over vars() or __dict__ whose body defines a function, lambda or class is not supported (#486)")
    leaves = self.refl_split(o, True)
    orders: list[list[str]] = []
    types: list[Val] = []
    total = 0
    for lf in leaves:
        order = self.refl_dict_order(lf.c)
        orders.append(order)
        total += len(order)
        for fl in order:
            types.append(Val("", self.classes[lf.c].ftypes[fl]))
    if total * self.reflcopies > REFL_BUDGET:
        self.err(f"unrolling this loop over the attributes of {typestr(o.t)} would compile its body {total * self.reflcopies} times, more than the budget of {REFL_BUDGET} copies (#486)")
    # (the values' join only where the loop binds them: a loop over the names alone takes fields
    # of types that join in none)
    vt = self.refl_join(types, f"the values of vars() of {typestr(o.t)}") if len(types) > 0 and m in ["items", "values"] else "int"
    kt = ""  # (the key's name, read as the literal in each copy where the body does not assign it)
    vn: Node | None = None
    if m == "items" and tgt.kind == "tuple" and len(tgt.kids) == 2 and tgt.kids[0].kind == "name":
        kt = tgt.kids[0].s
        vn = tgt.kids[1]
    elif m == "items":
        vn = tgt  # (k, v as one tuple)
    elif m == "keys" and tgt.kind == "name":
        kt = tgt.s
    elif m == "values":
        vn = tgt
    asg: dict[str, bool] = {}
    local_names(body, asg)
    # (a variable x of vars(x) is narrowed to the exact class of each run of copies)
    xt = self.ltype.get(x.s, "") if x.kind == "name" and x.s not in asg and self.narrowable(x.s) else ""
    brk = self.elsebrk if n.kids[2].kids is self.elsekids else self.label()
    after = self.forget(body, tgt)
    outer = self.reflcopies
    self.reflcopies = outer * max(total, 2)
    brks: list[dict[str, str]] = []
    join = self.label()
    for li in range(len(leaves)):
        lf = leaves[li]
        self.place(lf.label)
        ci = self.classes[lf.c]
        ov = Val(lf.v.v, lf.c)
        # (the fields __init__ may leave unassigned, as the loop starts: where its body assigns
        # one, CPython's next step raises, see refl_size_check)
        flagged = [fl for fl in orders[li] if fl in ci.fflag and lf.c + "." + fl not in self.cvars]
        snap = [self.mem_load(Val(self.fgep(ov, ci.fflag[fl]), "*bool")).v for fl in flagged]
        for j in range(len(orders[li])):
            fl = orders[li][j]
            if j > 0:
                self.refl_size_check(ov, flagged, snap)
            nxt = self.label()
            self.narrowed = dict(after)
            if xt in self.classes and self.classes[xt].tag > 0 and lf.c != xt and self.derives(lf.c, xt):
                self.narrowed[x.s] = lf.c
            if fl in ci.fflag and lf.c + "." + fl not in self.cvars:
                go = self.label()
                self.cbr(self.mem_load(Val(self.fgep(ov, ci.fflag[fl]), "*bool")).v, go, nxt)
                self.place(go)
            key = Val(self.sconst(fl), "str")
            if m == "items" and vn is tgt:
                val = self.coerce(self.getfield(ov, self.field(ov, fl), fl), vt)
                self.assign(tgt, self.tuple_([key, val]))
            else:
                if vn is not None:
                    self.assign(vn, self.coerce(self.getfield(ov, self.field(ov, fl), fl), vt))
                if kt != "":
                    self.assign(mk("name", kt, n.line, []), key)
                elif m == "keys":
                    self.assign(tgt, key)
            lp = Loop("while", self.cur, self.cur, nxt, brk)
            self.loops.append(lp)
            self.wdepth.append(len(self.exits))
            self.brks.append([])
            self.branch += 1
            sub = kt != "" and kt not in asg
            self.stmts([refl_subst(st, kt, mk("str", fl, st.line, [])) if sub else st for st in body])
            self.branch -= 1
            self.wdepth.pop()
            self.loops.pop()
            brks.extend(self.brks.pop())
            self.br(nxt)
            self.place(nxt)
        if len(orders[li]) > 0:
            self.refl_size_check(ov, flagged, snap)  # (the step that ends the loop)
        self.br(join)
    self.place(join)
    self.reflcopies = outer
    self.narrowed = after
    if n.kids[2].kids is self.elsekids:
        self.elsebrks = brks
    else:
        self.br(brk)
        self.place(brk)


def gen_refl_size_check(self, ov: Val, flagged: list[str], snap: list[str]) -> None:
    # a step of an iterator over the __dict__ of ov: CPython raises where its size changed since
    # the loop began, which here means a field __init__ left unassigned then (one of flagged,
    # whose flags were snap) has been assigned since (no attribute is deleted)
    if len(flagged) == 0:
        return
    ci = self.classes[ov.t]
    bad = ""
    for i in range(len(flagged)):
        now = self.mem_load(Val(self.fgep(ov, ci.fflag[flagged[i]]), "*bool")).v
        d = self.scalar('xor', [Val(now, 'bool'), Val(snap[i], 'bool')])
        bad = d if bad == "" else self.scalar('or', [Val(bad, 'bool'), Val(d, 'bool')])
    self.guard(bad, "RuntimeError: dictionary changed size during iteration")


# ---- dir(), copies of __dict__, and formatting with it
VARS_USES = ("vars(x) and x.__dict__ are supported where they are printed (print(), str(), repr(), an f-string field), "
             "iterated (for k, v in vars(x).items(), .keys(), .values()), formatted (a % format or str.format_map() of a constant "
             "format) or copied (dict(vars(x)), vars(x).copy()): a live __dict__ that code may change is not (#489)")
def gen_refl_dir_names(self, c: str) -> list[list[str]]:
    # dir() of a value of exact type c: [name, kind] sorted (kind "g": present where its flag says)
    if c == "None":
        return [[n, "o"] for n in sorted(HASATTR["any"].split() + ["__bool__"])]
    if c not in self.classes:
        b = "list" if is_list(c) else "dict" if is_dict(c) or is_kw(c) else "tuple" if is_tuple(c) or is_vtuple(c) else "int" if c == "bool" else c[: c.find("[")] if is_set(c) else c
        if b not in HASATTR:
            self.err(f"dir() of a {typestr(c)} is not supported (#486)")
        return [[n, "o"] for n in sorted(HASATTR["any"].split() + HASATTR[b].split())]
    return self.refl_names(c)


def gen_refl_dir(self, x: Node) -> Val:
    # dir(x): a new sorted list of the names x's exact class answers to (refl_names), for each
    # class it may have; a field __init__ may leave unassigned is listed where its flag is set
    o = self.expr(x, "")
    known = self.knownobj(x)
    if o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != "") or o.t == "file" or o.t.startswith("fn[") or o.t.startswith("callable["):
        self.err(f"dir() of a {typestr(o.t)} is not supported (#486)")
    vals: list[Val] = []
    blocks: list[str] = []
    end = self.label()
    for lf in self.refl_split(o, known):
        self.place(lf.label)
        names = self.refl_dir_names(lf.c)
        r = self.rt("pys_list_new", "ptr", [f"i64 {len(names)}"])
        for nk in names:
            if lf.c in self.classes and not self.refl_listed(lf.c, nk):
                yes = self.label()
                no = self.label()
                self.cbr(self.mem_load(Val(self.fgep(lf.v, self.classes[lf.c].fflag[nk[0]]), "*bool")).v, yes, no)
                self.place(yes)
                self.rt("pys_list_append", "void", [f"ptr {r}", "i64 " + self.to_slot(Val(self.sconst(nk[0]), "str"))])
                self.br(no)
                self.place(no)
            else:
                self.rt("pys_list_append", "void", [f"ptr {r}", "i64 " + self.to_slot(Val(self.sconst(nk[0]), "str"))])
        vals.append(Val(r, "list[str]"))
        blocks.append(self.cur)
        self.br(end)
    return self.refl_phi(vals, blocks, end, "dir()")


def gen_refl_dir_of(self, it: Node) -> Node | None:
    # the operand x of dir(x) or sorted(dir(x)) (a loop's iterable), or None
    if it.kind == "call" and len(it.kids) == 2 and it.kids[0].kind == "name" and it.kids[0].s == "sorted" and not self.bound("sorted"):
        it = it.kids[1]
    if it.kind == "call" and len(it.kids) == 2 and it.kids[0].kind == "name" and it.kids[0].s == "dir" and not self.bound("dir") and it.kids[1].kind != "kw" and it.kids[1].kind != "starred":
        return it.kids[1]
    return None


def gen_refl_dict_copy(self, d: Node) -> Val:
    # dict(vars(x)), vars(x).copy() (x.__dict__ too): a new dict of x's attributes now, from
    # their names to their values as the join of their types, for each class x may have
    x = self.refl_dict_of(d)
    if x is None:
        self.err("internal error: refl_dict_copy of no __dict__")
        return Val("", "")
    o = self.refl_dict_operand(d, x)
    leaves = self.refl_split(o, True)
    types: list[Val] = []
    for lf in leaves:
        ci = self.classes[lf.c]
        for fl in self.refl_dict_order(lf.c):
            types.append(Val("", ci.ftypes[fl]))
    vt = self.refl_join(types, f"the values of vars() of {typestr(o.t)}") if len(types) > 0 else "int"
    dt = self.ctype("dict", ["str", vt])
    vals: list[Val] = []
    blocks: list[str] = []
    end = self.label()
    for lf in leaves:
        self.place(lf.label)
        ci = self.classes[lf.c]
        ov = Val(lf.v.v, lf.c)
        r = self.expr(mk("dict", "", self.line, []), dt)
        for fl in self.refl_dict_order(lf.c):
            nxt = ""
            if fl in ci.fflag and lf.c + "." + fl not in self.cvars:
                # (a field __init__ may leave unassigned: where its flag is set)
                go = self.label()
                nxt = self.label()
                self.cbr(self.mem_load(Val(self.fgep(ov, ci.fflag[fl]), "*bool")).v, go, nxt)
                self.place(go)
            v = self.coerce(self.getfield(ov, self.field(ov, fl), fl), vt)
            self.rt("pys_dict_set", "void", [f"ptr {r.v}", "i64 " + self.to_slot(Val(self.sconst(fl), "str")), "i64 " + self.to_slot(v)], self.key_fx("str"))
            if nxt != "":
                self.br(nxt)
                self.place(nxt)
        vals.append(r)
        blocks.append(self.cur)
        self.br(end)
    return self.refl_phi(vals, blocks, end, "vars()")


def gen_refl_dict_format(self, d: Node, keys: list[str], fmt: str, what: str) -> Val:
    # fmt formatted with the attributes keys of x (vars(x) or x.__dict__: d) by position, as a %
    # format (what "%") or str.format() of them: x is evaluated, then for each class it may have,
    # each attribute read in order (each key must be one it always has)
    x = self.refl_dict_of(d)
    if x is None:
        return Val("", "")
    o = self.refl_dict_operand(d, x)
    vals: list[Val] = []
    blocks: list[str] = []
    end = self.label()
    for lf in self.refl_split(o, True):
        self.place(lf.label)
        ci = self.classes[lf.c]
        order = self.refl_dict_order(lf.c)
        ov = Val(lf.v.v, lf.c)
        args: list[Node] = []
        for k in keys:
            if k not in order:
                self.err(f"KeyError: '{k}': a {what} format reads a key that vars() of {short(lf.c)} does not have (#486)")
            if k in ci.fflag and lf.c + "." + k not in self.cvars:
                # (a field __init__ may leave unassigned: KeyError where it is, as CPython's dict raises)
                unset = self.scalar('xor', [Val(self.mem_load(Val(self.fgep(ov, ci.fflag[k]), "*bool")).v, 'bool'), Val('true', 'bool')])
                self.guard(unset, f"KeyError: '{k}'")
            args.append(self.vnode(self.getfield(ov, self.field(ov, k), k)))
        r = self.percent(fmt, mk("tuple", "", self.line, args)) if what == "%" else self.str_format(fmt, "format", args)
        vals.append(r)
        blocks.append(self.cur)
        self.br(end)
    return self.refl_phi(vals, blocks, end, what)


def gen_refl_percent(self, fmt: str, d: Node) -> Val:
    # fmt % vars(x) (or x.__dict__), fmt a constant: each %(key)... reads attribute key, in the
    # order the format names them, and fmt % (those values) formats them as CPython does
    out = ""
    keys: list[str] = []
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch != "%":
            out += ch
            i += 1
            continue
        if i + 1 < len(fmt) and fmt[i + 1] == "%":
            out += "%%"
            i += 2
            continue
        if i + 1 >= len(fmt) or fmt[i + 1] != "(":
            self.err("a % format of vars() is supported where each of its fields names a key, %(key)s (#486)")
        j = i + 2
        depth = 1
        while j < len(fmt) and depth > 0:
            if fmt[j] == "(":
                depth += 1
            elif fmt[j] == ")":
                depth -= 1
            j += 1
        if depth > 0:
            self.err("ValueError: incomplete format key")
        keys.append(fmt[i + 2 : j - 1])
        out += "%"
        i = j
    return self.refl_dict_format(d, keys, out, "%")


def gen_refl_format_map(self, fmt: str, d: Node) -> Val:
    # fmt.format_map(vars(x)), fmt a constant: fmt's fields name x's attributes, each read once in
    # the order of their first use, and formatted as fmt.format() of them by position does
    out = ""
    keys: list[str] = []
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if (ch == "{" or ch == "}") and i + 1 < len(fmt) and fmt[i + 1] == ch:
            out += ch + ch
            i += 2
            continue
        if ch != "{":
            out += ch
            i += 1
            continue
        j = i + 1
        while j < len(fmt) and fmt[j] not in ".[!:}{":
            j += 1
        k = fmt[i + 1 : j]
        if k == "" or k.isdigit():
            self.err("ValueError: Format string contains positional fields: format_map() with vars() needs a name in each field (#486)")
        if k not in keys:
            keys.append(k)
        out += "{" + str(keys.index(k))
        i = j
    return self.refl_dict_format(d, keys, out, "str.format_map()")


def refl_lit_strs(n: Node) -> list[str] | None:
    # the strs of a str literal or a tuple of them, else None
    if n.kind == "str":
        return [n.s]
    if n.kind != "tuple":
        return None
    out: list[str] = []
    for k in n.kids:
        if k.kind != "str":
            return None
        out.append(k.s)
    return out


def refl_fold(n: Node) -> int:
    # in an unrolled copy, a test of str literals only: "x".startswith("t"), "x" == "y", "x" in
    # ("a", "b"), not of one: 1 or 0, else -1
    if n.kind == "unary" and n.s == "not":
        r = refl_fold(n.kids[0])
        return 1 - r if r >= 0 else -1
    if n.kind == "call" and len(n.kids) == 2 and n.kids[0].kind == "attr" and (n.kids[0].s == "startswith" or n.kids[0].s == "endswith") and n.kids[0].kids[0].kind == "str":
        s = n.kids[0].kids[0].s
        ps = refl_lit_strs(n.kids[1])
        if ps is None:
            return -1
        for p in ps:
            if (n.kids[0].s == "startswith" and s.startswith(p)) or (n.kids[0].s == "endswith" and s.endswith(p)):
                return 1
        return 0
    if n.kind == "cmp" and len(n.kids) == 2 and n.kids[0].kind == "str":
        if n.s == "==" or n.s == "!=":
            if n.kids[1].kind != "str":
                return -1
            return 1 if (n.kids[0].s == n.kids[1].s) == (n.s == "==") else 0
        if n.s == "in" or n.s == "not in":
            if n.kids[1].kind == "str":
                return 1 if (n.kids[0].s in n.kids[1].s) == (n.s == "in") else 0
            ps = refl_lit_strs(n.kids[1])
            if ps is None or n.kids[1].kind != "tuple":
                return -1
            return 1 if (n.kids[0].s in ps) == (n.s == "in") else 0
    return -1


# ---- dataclasses.fields(), asdict() and astuple(), made per class (#486)
def gen_refl_dc_class(self, x: Node, what: str) -> str:
    # the dataclass that fields()/asdict()/astuple()'s argument x is (a class's name), or of
    # whose object it is: one class (a hierarchy's base must be narrowed first); "" for an object
    # x, whose evaluation is the caller's
    if x.kind == "name" and x.s in self.classes and x.s not in self.ltype:
        self.class_ready(x)
        c = x.s
        if not self.is_dc(c) or c in self.nts:
            self.err(f"TypeError: must be called with a dataclass type or instance: {what}() of class {short(c)}")
        return c
    return ""


def gen_refl_dc_check(self, t: str, what: str) -> str:
    # the dataclass of an object of static type t, for what(): one class
    cs = self.refl_concrete(t)
    if len(cs) > 1 and what != "fields" and unopt(t) in self.classes and len([c for c in cs if not self.is_dc(c)]) == 0:
        return unopt(t)  # (a dataclass hierarchy's base: its copies dispatch, see refl_dc_copy)
    if len(cs) != 1 or cs[0] not in self.classes or not self.is_dc(cs[0]) or cs[0] in self.nts:
        if len(cs) > 1:
            self.err(f"{what}() of a {typestr(t)}, whose objects may be of several classes, is not supported (#486): narrow it with isinstance() first")
        self.err(f"TypeError: {what}() should be called on dataclass instances" if what != "fields" else f"TypeError: must be called with a dataclass type or instance, not {typestr(t)}")
    return cs[0]


def gen_refl_dc_names(self, it: Node) -> list[str] | None:
    # the field names of dataclasses.fields(X) (a class, or a variable whose object's class is
    # one dataclass), a loop's iterable; else None
    if it.kind != "call" or len(it.kids) != 2 or it.kids[1].kind == "kw" or it.kids[1].kind == "starred":
        return None
    f = it.kids[0]
    nm = self.aliases[f.s] if f.kind == "name" and f.s in self.aliases and f.s not in self.ltype and f.s not in self.gtypes else self.dotted(f) if f.kind == "attr" else ""
    if nm != "dataclasses.fields":
        return None
    c = self.refl_dc_class(it.kids[1], "fields")
    if c == "":
        c = self.refl_dc_check(self.expr(it.kids[1], "").t, "fields")
    ci = self.classes[c]
    for fl in self.dc_fields(ci):
        self.refl_public(c, fl)
    return [fl for fl in self.dc_fields(ci) if not fl.startswith(" ")]


def refl_subst_field(n: Node, name: str, fl: str) -> Node:
    # a copy of code n where name is a dataclasses.Field of field fl: name.name is the literal
    # fl, any other read of name a "dcfield" node (an error where it is compiled)
    if n.kind == "attr" and n.s == "name" and n.kids[0].kind == "name" and n.kids[0].s == name:
        return mk("str", fl, n.line, [])
    if n.kind == "name" and n.s == name:
        return mk("dcfield", fl, n.line, [])
    c = Node(n.kind, n.s, n.line)
    c.chk = n.chk
    c.mchk = n.mchk
    c.depth = n.depth
    keep = (n.kind == "listcomp" or n.kind == "setcomp" or n.kind == "dictcomp") and refl_binds_in(n, name)
    for k in n.kids:
        c.kids.append(clone_node(k) if keep else refl_subst_field(k, name, fl))
    return c


def gen_refl_unroll_fields(self, n: Node, names: list[str]) -> None:
    # for f in dataclasses.fields(X): body: the body once per field, f.name read as its literal
    tgt = n.kids[0]
    body = n.kids[2].kids
    if tgt.kind != "name":
        self.err("a loop over dataclasses.fields() needs a name as its target (#486)")
    asg: dict[str, bool] = {}
    local_names(body, asg)
    if tgt.s in asg or refl_scoped(n.kids[2]):
        self.err("a loop over dataclasses.fields() whose body assigns its variable, or defines a function, lambda or class, is not supported (#486)")
    if len(names) * self.reflcopies > REFL_BUDGET:
        self.err(f"unrolling this loop over {len(names)} fields would compile its body {len(names) * self.reflcopies} times, more than the budget of {REFL_BUDGET} copies (#486)")
    brk = self.elsebrk if n.kids[2].kids is self.elsekids else self.label()
    after = self.forget(body, tgt)
    outer = self.reflcopies
    self.reflcopies = outer * max(len(names), 2)
    brks: list[dict[str, str]] = []
    for fl in names:
        nxt = self.label()
        self.narrowed = dict(after)
        lp = Loop("while", self.cur, self.cur, nxt, brk)
        self.loops.append(lp)
        self.wdepth.append(len(self.exits))
        self.brks.append([])
        self.branch += 1
        self.stmts([refl_subst_field(st, tgt.s, fl) for st in body])
        self.branch -= 1
        self.wdepth.pop()
        self.loops.pop()
        brks.extend(self.brks.pop())
        self.br(nxt)
        self.place(nxt)
    self.reflcopies = outer
    self.narrowed = after
    if n.kids[2].kids is self.elsekids:
        self.elsebrks = brks
    else:
        self.br(brk)
        self.place(brk)


def gen_refl_dc_type(self, t: str, what: str, seen: list[str]) -> str:
    # the type of asdict()'s (what "asdict") or astuple()'s copy of a value of type t: a
    # dataclass's object a dict (a tuple), recursively into lists, tuples and dicts; scalars and
    # bytes as they are (CPython's _asdict_inner deep-copies them, and deepcopy returns an
    # immutable object itself; other objects it deep-copies, which is not supported)
    if t in ["int", "float", "bool", "str", "bytes", "None"] or self.scalar_union(t):
        return t
    if is_opt(t):
        x = self.refl_dc_type(unopt(t), what, seen)
        return self.optional(x) if self.optional(x) != "" else self.union_type([x, "None"])
    if is_list(t):
        return self.ctype("list", [self.refl_dc_type(targs(t)[0], what, seen)])
    if is_dict(t):
        return self.ctype("dict", [self.refl_dc_type(targs(t)[0], what, seen), self.refl_dc_type(targs(t)[1], what, seen)])
    if is_tuple(t):
        return self.ctype("tuple", [self.refl_dc_type(x, what, seen) for x in targs(t)])
    if is_vtuple(t):
        return self.ctype("vtuple", [self.refl_dc_type(targs(t)[0], what, seen)])
    if t in self.classes and self.is_dc(t) and t not in self.nts:
        if t in seen:
            self.err(f"{what}() of dataclass {short(t)}, which holds objects of its own class, is not supported (#486)")
        rs: list[Val] = []
        for c in self.refl_concrete(t):
            # (each class a hierarchy's object may have: their copies' join)
            ci = self.classes[c]
            if not self.is_dc(c):
                self.err(f"{what}() of a {short(t)}, whose subclass {short(c)} is no dataclass, is not supported (#486)")
            fs = [fl for fl in self.dc_fields(ci) if not fl.startswith(" ")]
            for fl in fs:
                if what == "asdict":
                    self.refl_public(c, fl)
            ts = [self.refl_dc_type(ci.ftypes[fl], what, seen + [t]) for fl in fs]
            if what == "astuple":
                rs.append(Val("", self.ctype("tuple", ts)))
            else:
                vt = self.refl_join([Val("", x) for x in ts], f"asdict() of {short(c)}") if len(ts) > 0 else "int"
                rs.append(Val("", self.ctype("dict", ["str", vt])))
        r = self.refl_join(rs, f"{what}() of a {short(t)}, whose classes' copies")
        return self.optional(r)  # (an object of the class may be None, which _asdict_inner keeps)
    self.err(f"{what}() of a dataclass holding a {typestr(t)} is not supported (CPython deep-copies it: #486)")
    return ""


def gen_refl_dc_copy(self, v: Val, what: str, seen: list[str], nonnull: bool = False) -> Val:
    # asdict()'s (astuple()'s) copy of value v (refl_dc_type): new containers throughout, as
    # CPython's _asdict_inner (_astuple_inner) makes them
    t = v.t
    if t in ["int", "float", "bool", "str", "bytes", "None"] or self.scalar_union(t):
        return v
    rt = self.refl_dc_type(t, what, seen)
    if is_opt(t) or (t in self.classes and v.v not in self.nn and not nonnull):
        # None stays None; else the copy of the value it holds
        yes = self.label()
        no = self.label()
        end = self.label()
        start = self.cur
        self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, yes)
        self.place(yes)
        inner = self.refl_dc_copy(self.deref(v) if is_opt(t) else Val(v.v, t), what, seen, True)
        inner = self.coerce(inner, rt)
        e1 = self.cur
        self.br(end)
        self.place(no)
        self.unreachable()
        self.place(end)
        ph = Ins("phi", rt, "")
        self.incoming(ph, "null", start)
        self.incoming(ph, inner.v, e1)
        return Val(self.phi(ph), rt)
    if t in self.classes:
        rvals: list[Val] = []
        rblocks: list[str] = []
        rend = self.label()
        for lf in self.refl_split(v, True):
            self.place(lf.label)
            c = lf.c
            ci = self.classes[c]
            ov = Val(v.v, c)
            fs = [fl for fl in self.dc_fields(ci) if not fl.startswith(" ")]
            vals: list[Val] = []
            for fl in fs:
                vals.append(self.refl_dc_copy(self.getfield(ov, self.field(ov, fl), fl), what, seen + [t]))
            if what == "astuple":
                r = self.coerce(self.tuple_(vals), unopt(rt))
            else:
                vt = unopt(rt)
                kids: list[Node] = []
                for j in range(len(fs)):
                    kids.append(mk("str", fs[j], self.line, []))
                    kids.append(self.vnode(self.coerce(vals[j], targs(vt)[1])))
                r = self.expr(mk("dict", "", self.line, kids), vt)
            rvals.append(r)
            rblocks.append(self.cur)
            self.br(rend)
        return self.refl_phi(rvals, rblocks, rend, what + "()")
    if is_tuple(t):
        return self.tuple_([self.refl_dc_copy(self.tget(v, j), what, seen) for j in range(len(targs(t)))])
    # a list, dict or runtime-length tuple: a new one of the copies of its items
    x = mk("name", "__pys_dc", self.line, [])
    if is_dict(t):
        k = mk("name", "__pys_dck", self.line, [])
        e = mk("tuple", "", self.line, [mk("call", "", self.line, [mk("name", "__pys_" + what, self.line, []), k]), mk("call", "", self.line, [mk("name", "__pys_" + what, self.line, []), x])])
        comp = mk("dictcomp", "", self.line, [mk("listcomp", "", self.line, [e, mk("tuple", "", self.line, [k, x]), mk("call", "", self.line, [mk("attr", "items", self.line, [self.vnode(v)])])])])
        return self.coerce(self.expr(comp, rt), rt)
    comp = mk("listcomp", "", self.line, [mk("call", "", self.line, [mk("name", "__pys_" + what, self.line, []), x]), x, self.vnode(v)])
    r = self.coerce(self.expr(comp, self.ctype("list", [targs(rt)[0]])), self.ctype("list", [targs(rt)[0]]))
    if is_vtuple(t):
        return self.coerce(r, rt)
    return r


def gen_refl_dataclasses(self, name: str, args: list[Node]) -> Val:
    # dataclasses.asdict(obj), astuple(obj), is_dataclass(x), and the compiler's recursive
    # __pys_asdict / __pys_astuple of a copy's items
    what = name[name.rfind(".") + 1 :].replace("__pys_", "")
    if len(args) != 1 or args[0].kind == "kw" or args[0].kind == "starred":
        self.err(f"{what}() takes one positional argument here (dict_factory/tuple_factory are not supported: #486)")
    if what == "is_dataclass":
        if args[0].kind == "name" and args[0].s in self.classes and args[0].s not in self.ltype:
            self.class_ready(args[0])
            return Val("true" if self.is_dc(args[0].s) and args[0].s not in self.nts else "false", "bool")
        v = self.expr(args[0], "")
        cs = self.refl_concrete(v.t)
        yes = [c for c in cs if c in self.classes and self.is_dc(c) and c not in self.nts]
        if len(yes) == 0:
            return Val("false", "bool")
        if len(yes) != len(cs):
            self.err(f"is_dataclass() of a {typestr(v.t)}, whose objects may be of several classes, is not supported (#486)")
        return Val("true", "bool") if v.v in self.nn or self.knownobj(args[0]) else self.ptr_cmp('!=', v, Val('null', 'None'))
    v = self.expr(args[0], "")
    if name.startswith("__pys_"):
        return self.refl_dc_copy(v, what, [])
    if args[0].kind == "name" and args[0].s in self.classes and args[0].s not in self.ltype:
        self.err(f"TypeError: {what}() should be called on dataclass instances")
    c = self.refl_dc_check(v.t, what)
    self.notnone(Val(v.v, c), f"TypeError: {what}() should be called on dataclass instances")
    return self.refl_dc_copy(Val(v.v, c), what, [], True)


def gen_refl_union_str(self, v: Val, m: str) -> Val:
    # str() (m "__str__") or repr() ("__repr__") of a reference union of classes: that of the
    # object's exact class, each the way an object of its class is printed (obj_str)
    for c in umembers(unopt(v.t)):
        if c not in self.classes:
            self.err(f"str() or repr() of a {typestr(v.t)} is not supported: narrow it with isinstance() first")
    vals: list[Val] = []
    blocks: list[str] = []
    end = self.label()
    narrow = dict(self.narrowed)
    for lf in self.refl_split(v):
        self.place(lf.label)
        self.narrowed = dict(narrow)
        r = Val(self.sconst("None"), "str") if lf.c == "None" else self.obj_str(lf.v, m)
        if not self.term:
            vals.append(r)
            blocks.append(self.cur)
            self.br(end)
    self.narrowed = narrow
    return self.refl_phi(vals, blocks, end, "str()")


# ---- names only the run time knows (#489's first version): hasattr(), the text of getattr()
# and setattr() of a class whose names __slots__ closes. Each exact class the receiver may have
# finds the name in its record's sorted name table (pys_refl_find); the site then switches on
# that index, which LLVM makes a jump table or a lookup table of
KINDS = "fgcpmskou"  # a name table's kinds (refl_names), stored as their positions + 1
SLOT_WRAPPERS = "__delattr__ __eq__ __ge__ __getattribute__ __gt__ __hash__ __init__ __le__ __lt__ __ne__ __repr__ __setattr__ __str__ __bool__".split()
OBJ_BUILTINS = "__dir__ __format__ __getstate__ __reduce__ __reduce_ex__ __sizeof__".split()
TYPE_BUILTINS = "__init_subclass__ __new__ __subclasshook__".split()


def gen_refl_name_list(self, c: str) -> list[list[str]]:
    # the names a value of exact type c answers to, with their kinds: a class's (refl_names),
    # None's (which have kind "o")
    if c == "None" or c not in self.classes:
        return self.refl_dir_names(c)
    return self.refl_names(c)


def gen_refl_names_table(self, c: str) -> str:
    # the record of exact type c with its name table (refl_name_list), made once
    rec = self.refl_layout_record(c) if c in self.classes else self.refl_record(c)
    d = self.reflrecs[rec]
    if d.refs[3] == "null":
        names = self.refl_name_list(c)
        t = Data("classnames", rec + ".names")
        for nk in names:
            t.refs.append(self.sconst(nk[0]))
            t.items.append(Val(str(KINDS.find(nk[1]) + 1), "int"))
        self.consts.append(t)
        d.refs[3] = t.name
        d.items[1] = Val(str(len(names)), "int")
    return rec


def gen_refl_runtime_name(self, a: Node, what: str) -> Val:
    # a run-time attribute name, which must be a str (CPython raises TypeError for another type)
    v = self.expr(a, "str")
    if v.t != "str":
        self.err(f"{what}(): attribute name must be string, not '{typestr(v.t)}'")
    return v


def gen_refl_find(self, c: str, name: Val) -> str:
    # the index of name in the name table of exact type c's record, or -1
    rec = self.refl_names_table(c)
    return self.rt("pys_refl_find", "i64", [f"ptr {rec}", f"ptr {name.v}"])


def gen_refl_hasattr(self, args: list[Node]) -> Val:
    # hasattr(o, name) with a run-time name: per exact class of o, whether its name table holds
    # name, but where name is a field __init__ may leave unassigned (its flag) or a property (its
    # getter, whose AttributeError means False)
    self.refl_args("hasattr", args, 2, 2)
    o = self.expr(args[0], "")
    known = self.knownobj(args[0])
    nv = self.refl_runtime_name(args[1], "hasattr")
    if o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != ""):
        self.err("hasattr() of an exception object is not supported (#489)")
    vals: list[Val] = []
    blocks: list[str] = []
    end = self.label()
    narrow = dict(self.narrowed)
    for lf in self.refl_split(o, known):
        self.place(lf.label)
        self.narrowed = dict(narrow)
        names = self.refl_name_list(lf.c)
        idx = self.refl_find(lf.c, nv)
        for j in range(len(names)):
            kind = names[j][1]
            if kind != "g" and kind != "p" and kind != "u":
                continue
            yes = self.label()
            no = self.label()
            self.cbr(self.num_cmp('==', Val(idx, "int"), Val(str(j), "int")).v, yes, no)
            self.place(yes)
            if kind == "u":
                vals.append(Val("false", "bool"))
                blocks.append(self.cur)
                self.br(end)
            elif kind == "g":
                vals.append(Val(self.mem_load(Val(self.fgep(lf.v, self.classes[lf.c].fflag[names[j][0]]), "*bool")).v, "bool"))
                blocks.append(self.cur)
                self.br(end)
            else:
                self.refl_catch_attr(lf.v, names[j][0], Val("false", "bool"), vals, blocks, end, True)
            self.place(no)
        vals.append(self.num_cmp('>=', Val(idx, "int"), Val("0", "int")))
        blocks.append(self.cur)
        self.br(end)
    self.narrowed = narrow
    return self.refl_phi(vals, blocks, end, "hasattr()")


def gen_refl_otext(self, c: str, name: str) -> str:
    # how str() of attribute name (kind "o") of an object of exact type c is made: "=<text>" a
    # constant, "w" a method-wrapper and "b" a builtin method of the object, "t" a builtin
    # method of its type, "v" its __dict__, "" where Pystachy does not know it
    if c == "None":
        cn = "NoneType"
        if name == "__class__":
            return "=<class 'NoneType'>"
        if name == "__doc__":
            return "=The type of the None singleton."
    else:
        ci = self.classes[c]
        cn = short(c)
        mod = self.refl_type_name(c, "__module__")
        if name == "__class__":
            return f"=<class '{mod}.{cn}'>"
        if name == "__module__":
            return "=" + mod
        if name == "__weakref__":
            return "=None"
        if name == "__dict__":
            return "v"
        if name == "__doc__":
            # (as CPython 3.13's compiler keeps a docstring: clean_doc)
            body = refl_body(ci.node)
            return "=" + clean_doc(body[0].kids[0].s) if len(body) > 0 and body[0].kind == "expr" and body[0].kids[0].kind == "str" and not self.is_dc(c) else "=None" if not self.is_dc(c) else ""
        if name == "__firstlineno__":
            line = ci.node.line
            for k in ci.node.kids:
                if k.kind == "deco" and k.line < line:
                    line = k.line
            return "=" + str(line)
        if name == "__static_attributes__":
            out: list[str] = []
            for st in refl_body(ci.node):
                if st.kind == "def":
                    refl_static_attrs(st, out)
            names = sorted(out)
            return "=(" + ", ".join(["'" + x + "'" for x in names]) + ("," if len(names) == 1 else "") + ")"
        if name == "__hash__" and "__eq__" in ci.methods and self.refl_defines(c, "__eq__") and "__hash__" not in ci.methods:
            return "=None"
    if name in SLOT_WRAPPERS:
        return "w"
    if name in OBJ_BUILTINS:
        return "b"
    if name in TYPE_BUILTINS:
        return "t"
    return ""


def refl_static_attrs(n: Node, out: list[str]) -> None:
    # the attributes CPython 3.13 lists in a class's __static_attributes__ that code n (in the class
    # body, not a class nested in it) stores as self.x, the name self as its compiler checks it: by
    # an assignment, an annotated one with a value, a for loop's, a comprehension's or a with
    # statement's target, also in nested functions and lambdas; not by += or del
    if n.kind == "class" or n.kind == "subclass":
        return
    ts: list[Node] = []
    if n.kind == "assign":
        ts = n.kids[:-1]
    elif n.kind == "annassign" and len(n.kids) == 3:
        ts = n.kids[:1]
    elif n.kind == "for" or n.kind == "compfor":
        ts = n.kids[:1]
    elif (n.kind == "listcomp" or n.kind == "asynccomp") and len(n.kids) > 1:
        ts = n.kids[1:2]
    elif n.kind == "withitem" and len(n.kids) == 2:
        ts = n.kids[1:]
    for t in ts:
        refl_target_stores(t, "self", out)
    for k in n.kids:
        refl_static_attrs(k, out)


def gen_refl_lookup(self, n: Node) -> RText:
    # getattr(o, name[, default]) with a run-time name, as a consumer of its text evaluates it:
    # per exact class of o, the name's index in its name table selects what CPython's lookup
    # does now: a field's or property's value (kept in a slot of its own), else what its text
    # needs later (refl_lookup_text); a name it does not have is the default, else CPython's
    # AttributeError. The arm taken is kept in the RText's slot sel
    args = n.kids[1:]
    self.refl_args("getattr", args, 2, 3)
    o = self.expr(args[0], "")
    known = self.knownobj(args[0])
    nv = self.refl_runtime_name(args[1], "getattr")
    d = self.expr(args[2], "") if len(args) == 3 else Val("", "")
    if o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != ""):
        self.err("getattr() of an exception object is not supported (#489)")
    r = RText("getattr", o, known)
    r.sel = self.alloca("int", "")
    if d.t != "":
        r.arms.append(RArm(0, "", "d", ""))
        r.arms[0].t = d.t
        r.arms[0].slot = d.v  # (the default's value: evaluated before the lookup, as CPython does)
    end = self.label()
    narrow = dict(self.narrowed)
    members: dict[str, str] = {}
    if is_union(unopt(o.t)):
        for m in umembers(unopt(o.t)):
            for c in self.refl_concrete(m):
                members[c] = m
    for lf in self.refl_split(o, known):
        self.place(lf.label)
        self.narrowed = dict(narrow)
        if lf.c != "None" and lf.c not in self.classes:
            self.err(f"the text of getattr(o, name) for a run-time name is not supported where o may be a {typestr(lf.c)}, whose methods are no values (#247, #489)")
        names = self.refl_name_list(lf.c)
        for nk in names:
            if nk[1] == "o" and self.refl_otext(lf.c, nk[0]) == "":
                self.err(f"the text of getattr(o, name) for a run-time name is not supported where o may be a {short(lf.c) if lf.c != 'None' else 'None'}, whose attribute {nk[0]} Pystachy cannot print (#489)")
            if nk[1] == "o" and self.refl_otext(lf.c, nk[0]) == "v":
                self.refl_fields_table(lf.c)
        idx = self.refl_find(lf.c, nv)
        for j in range(len(names)):
            nm = names[j][0]
            kind = names[j][1]
            if kind == "u":
                continue  # (a slot never set: the miss below)
            arm = RArm(len(r.arms), lf.c, kind, nm)
            arm.t = members.get(lf.c, "")  # (the union member to read the object from, later)
            r.arms.append(arm)
            yes = self.label()
            no = self.label()
            self.cbr(self.num_cmp('==', Val(idx, "int"), Val(str(j), "int")).v, yes, no)
            self.place(yes)
            if kind in ["f", "g", "c", "p"]:
                if d.t != "" and kind == "g":
                    there = self.label()
                    miss = self.label()
                    self.cbr(self.mem_load(Val(self.fgep(lf.v, self.classes[lf.c].fflag[nm]), "*bool")).v, there, miss)
                    self.place(miss)
                    self.mstore('int', '0', r.sel)
                    self.br(end)
                    self.place(there)
                cc = self.stop_catch() if d.t != "" and kind == "p" else None
                outer = self.handler
                if cc is not None:
                    # (a getter's AttributeError gives the default, as CPython catches it)
                    self.handler = cc.landing
                    body = self.label()
                    cc.tr.body = body
                    self.place(body)
                v = self.expr(mk("attr", nm, self.line, [self.vnode(lf.v)]), "")
                self.handler = outer
                arm.slot = self.alloca(v.t, "")
                self.mstore(v.t, v.v, arm.slot)
                arm.c = lf.c + "\x01" + v.t
                if cc is not None:
                    self.mstore('int', str(arm.k), r.sel)
                    self.br(end)
                    e = self.landing(cc.landing, cc.slot, cc.mark)
                    caught = self.label()
                    other = self.label()
                    self.cbr(self.exc_match(e, self.catch_set(mk("name", "AttributeError", self.line, []))), caught, other)
                    self.place(other)
                    self.throw(e)
                    self.place(caught)
                    self.rt("pys_exc_restore", "void", [f"ptr {cc.old}"])
                    cc.tr.exit = end
                    self.mstore('int', '0', r.sel)
                    self.br(end)
                    self.place(no)
                    continue
            self.mstore('int', str(arm.k), r.sel)
            self.br(end)
            self.place(no)
        if d.t != "":
            self.mstore('int', '0', r.sel)
        else:
            cn = "NoneType" if lf.c == "None" else short(lf.c)
            m = self.rt("pys_str_add", "ptr", [f"ptr {self.sconst(chr(39) + cn + chr(39) + ' object has no attribute ' + chr(39))}", f"ptr {nv.v}"])
            m = self.rt("pys_str_add", "ptr", [f"ptr {m}", f"ptr {self.sconst(chr(39))}"])
            self.raise_("AttributeError", m)
        self.br(end)
    self.narrowed = narrow
    self.place(end)
    return r


def gen_refl_lookup_text(self, r: RText, conv: str) -> Val:
    # the text of what refl_lookup found (str(), or repr() for conv "repr"): the arm in r.sel
    sel = self.mload('int', r.sel)
    vals: list[Val] = []
    blocks: list[str] = []
    end = self.label()
    for i in range(len(r.arms)):
        arm = r.arms[i]
        nxt = self.label() if i + 1 < len(r.arms) else ""
        if nxt != "":
            yes = self.label()
            self.cbr(self.num_cmp('==', Val(sel, "int"), Val(str(arm.k), "int")).v, yes, nxt)
            self.place(yes)
        vals.append(self.refl_arm_text(r, arm, conv))
        blocks.append(self.cur)
        self.br(end)
        if nxt != "":
            self.place(nxt)
    return self.refl_phi(vals, blocks, end, "getattr()")


def gen_refl_arm_text(self, r: RText, arm: RArm, conv: str) -> Val:
    # the text of one arm of a run-time getattr (see refl_lookup)
    if arm.kind == "d":
        v = Val(arm.slot, arm.t)
        return self.repr(v) if conv == "repr" else self.to_str(v)
    c = arm.c[: arm.c.find("\x01")] if "\x01" in arm.c else arm.c
    if arm.kind in ["f", "g", "c", "p"]:
        t = arm.c[arm.c.find("\x01") + 1 :]
        v = Val(self.mload(t, arm.slot), t)
        return self.repr(v) if conv == "repr" else self.to_str(v)
    # the object, again: the receiver's register, or its union box's payload (a pure read)
    if c == "None":
        obj = Val(self.refl_record("None"), "%ptr")
    elif arm.t != "":
        obj = Val(self.uget(Val(r.o.v, unopt(r.o.t)), arm.t).v, c)
    else:
        obj = Val(r.o.v, c)
    if arm.kind == "m":
        f = self.classes[c].methods[arm.name]
        q = short(f.cls if f.cls in self.classes else c) + "." + arm.name
        rp = self.obj_str(Val(obj.v, c), "__repr__")
        s = self.rt("pys_str_add", "ptr", [f"ptr {self.sconst('<bound method ' + q + ' of ')}", f"ptr {rp.v}"])
        return Val(self.rt("pys_str_add", "ptr", [f"ptr {s}", f"ptr {self.sconst('>')}"]), "str")
    if arm.kind == "s":
        f = self.classes[c].methods[arm.name]
        q = short(f.cls if f.cls in self.classes else c) + "." + arm.name
        addr = Val(self.scalar_cast('ptrtoint', Val(self.refl_record(c), '%ptr'), 'int'), "int")
        hx = self.builtin("hex", [self.vnode(addr)], "")
        s = self.rt("pys_str_add", "ptr", [f"ptr {self.sconst('<function ' + q + ' at ')}", f"ptr {hx.v}"])
        return Val(self.rt("pys_str_add", "ptr", [f"ptr {s}", f"ptr {self.sconst('>')}"]), "str")
    if arm.kind == "k":
        f = self.classes[c].methods[arm.name]
        q = short(f.cls if f.cls in self.classes else c)
        return Val(self.sconst(f"<bound method {q}.{arm.name} of <class '{self.refl_type_name(c, '__module__')}.{short(c)}'>>"), "str")
    how = self.refl_otext(c, arm.name)
    cn = "NoneType" if c == "None" else short(c)
    if how.startswith("="):
        text = how[1:]
        if conv == "repr" and (arm.name == "__module__" or arm.name == "__doc__") and text != "None":
            return self.repr(Val(self.sconst(text), "str"))
        return Val(self.sconst(text), "str")
    if how == "v":
        return Val(self.rt("pys_refl_vars", "ptr", [f"ptr {self.refl_layout_record(c)}", f"ptr {obj.v}"]), "str")
    if how == "w":
        return Val(self.rt("pys_default_repr", "ptr", [f"ptr {self.sconst('method-wrapper ' + chr(39) + arm.name + chr(39) + ' of ' + cn)}", f"ptr {obj.v}"]), "str")
    if how == "b":
        return Val(self.rt("pys_default_repr", "ptr", [f"ptr {self.sconst('built-in method ' + arm.name + ' of ' + cn)}", f"ptr {obj.v}"]), "str")
    return Val(self.rt("pys_default_repr", "ptr", [f"ptr {self.sconst('built-in method ' + arm.name + ' of type')}", f"ptr {self.refl_record(c)}"]), "str")


def gen_refl_setattr_runtime(self, args: list[Node]) -> Val:
    # setattr(o, name, value) with a run-time name, where o's classes close their names with
    # __slots__: per exact class, a slot field stores the value (which must fit every slot field,
    # as any may be the one named), a property calls its setter, and every other name raises
    # CPython's error: AttributeError (read-only, or no __dict__ for a new name), TypeError for
    # __class__
    o = self.expr(args[0], "")
    known = self.knownobj(args[0])
    nv = self.refl_runtime_name(args[1], "setattr")
    v = self.expr(args[2], "")
    if o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != ""):
        self.err("setattr() of an exception object is not supported (#489)")
    end = self.label()
    narrow = dict(self.narrowed)
    for lf in self.refl_split(o, known):
        self.place(lf.label)
        self.narrowed = dict(narrow)
        if lf.c == "None":
            m = self.rt("pys_str_add", "ptr", [f"ptr {self.sconst(chr(39) + 'NoneType' + chr(39) + ' object has no attribute ' + chr(39))}", f"ptr {nv.v}"])
            m = self.rt("pys_str_add", "ptr", [f"ptr {m}", f"ptr {self.sconst(chr(39) + ' and no __dict__ for setting new attributes')}"])
            self.raise_("AttributeError", m)
            continue
        ci = self.classes[lf.c] if lf.c in self.classes else None
        if ci is None or not ci.slotlimit:
            self.err(f"setattr() of a name only the run time knows is supported for objects whose class closes its names with __slots__; an object of {typestr(lf.c)} may get a new attribute, which needs per-object storage (#489)")
            continue
        if "frozen" in ci.dcopts:
            self.err("setattr() of a run-time name on a frozen dataclass is not supported (#489)")
        names = self.refl_names(lf.c)
        idx = self.refl_find(lf.c, nv)
        cn = short(lf.c)
        for j in range(len(names)):
            nm = names[j][0]
            kind = names[j][1]
            yes = self.label()
            no = self.label()
            self.cbr(self.num_cmp('==', Val(idx, "int"), Val(str(j), "int")).v, yes, no)
            self.place(yes)
            if kind == "u":
                self.err(f"setattr() of a run-time name is not supported where it may name slot {nm} of {cn}, which no code assigns (#489)")
            if kind == "f" or kind == "g":
                ft = ci.ftypes[nm]
                if not (v.t == ft or self.widens(v.t, ft) or self.converts(v.t, ft)):
                    self.err(f"setattr() of a run-time name with a {typestr(v.t)} is not supported: the name may be {cn}'s field {nm}, a {typestr(ft)} (#489)")
                self.assign(mk("attr", nm, self.line, [self.vnode(lf.v)]), v)
            elif kind == "p":
                self.assign(mk("attr", nm, self.line, [self.vnode(lf.v)]), v)
            elif nm == "__class__":
                self.raise_("TypeError", self.sconst(f"__class__ must be set to a class, not '{self.refl_type_name(v.t, '__name__') if self.refl_type_name(v.t, '__name__') != '' else typestr(v.t)}' object"))
            else:
                self.raise_("AttributeError", self.sconst(f"'{cn}' object attribute '{nm}' is read-only"))
            self.br(end)
            self.place(no)
        m = self.rt("pys_str_add", "ptr", [f"ptr {self.sconst(chr(39) + cn + chr(39) + ' object has no attribute ' + chr(39))}", f"ptr {nv.v}"])
        m = self.rt("pys_str_add", "ptr", [f"ptr {m}", f"ptr {self.sconst(chr(39) + ' and no __dict__ for setting new attributes')}"])
        self.raise_("AttributeError", m)
    self.narrowed = narrow
    self.place(end)
    return Val("null", "None")


def gen_refl_replace_changes(self, obj: Node, d: Val) -> None:
    # dataclasses.replace(obj, **changes) with changes a dict[str, T]: a key may name any init
    # field, so T must fit each; even then, which field a key names is known only at run time
    # (#489's named rejection)
    o = self.expr(obj, "")
    vt = targs(d.t)[1]
    if o.t in self.classes and self.is_dc(o.t):
        ci = self.classes[o.t]
        for fl in self.dc_fields(ci):
            ft = ci.ftypes[fl]
            if "no-init" not in ci.fopts[fl] and not (vt == ft or self.widens(vt, ft) or self.converts(vt, ft)):
                self.err(f"replace(obj, **changes) with a {typestr(d.t)} is not supported: a key may name field {fl} of {short(o.t)} ({typestr(ft)}), which a value of type {typestr(vt)} does not fit (#489)")
    self.err(f"replace(obj, **changes) with a {typestr(d.t)} is not supported: which field each key names is known only at run time (#489)")


def gen_refl_hasattr_lit(self, o: Val, a: str, known: bool) -> Val:
    # hasattr(o, "a") where a class o may have makes a a property: its getter decides, by
    # raising AttributeError or not, per exact class (refl_has)
    vals: list[Val] = []
    blocks: list[str] = []
    end = self.label()
    narrow = dict(self.narrowed)
    for lf in self.refl_split(o, known):
        self.place(lf.label)
        self.narrowed = dict(narrow)
        h = self.refl_has(lf.c, a)
        if h == "p":
            self.refl_catch_attr(lf.v, a, Val("false", "bool"), vals, blocks, end, True)
            continue
        if h == "f":
            vals.append(Val(self.mem_load(Val(self.fgep(lf.v, self.classes[lf.c].fflag[a]), "*bool")).v, "bool"))
        else:
            vals.append(Val("true" if h == "y" else "false", "bool"))
        blocks.append(self.cur)
        self.br(end)
    self.narrowed = narrow
    return self.refl_phi(vals, blocks, end, "hasattr()")


def gen_refl_prop_in(self, t: str, a: str) -> bool:
    # may a value of static type t be an object whose class makes a a property
    for c in self.refl_concrete(t):
        if c in self.classes and a in self.classes[c].methods and self.classes[c].methods[a].prop:
            return True
    return False


def gen_refl_derived_only(self, x: Node, a: str) -> bool:
    # is x a variable of a hierarchy's class that lacks attribute a, which a class derived from it
    # has: getattr(x, "a") then reads it where x's object has it (refl_getattr)
    if x.kind != "name" or self.whole != 0:
        return False  # (static_type: a variable's, outside the search for a fill)
    t = self.static_type(x)
    if t not in self.classes or self.classes[t].tag == 0 or a in self.classes[t].ftypes or a in self.classes[t].methods:
        return False
    for c in self.refl_concrete(t):
        if a in self.classes[c].ftypes or a in self.classes[c].methods:
            return True
    return False


def refl_formatter(f: Node) -> bool:
    # is callee f string.Formatter().format, of the base Formatter itself (lib/string.py's, whose
    # get_field, get_value, format_field and convert_field are str.format()'s)
    return f.kind == "attr" and f.s == "format" and f.kids[0].kind == "call" and len(f.kids[0].kids) == 1 and f.kids[0].kids[0].kind == "name" and f.kids[0].kids[0].s == "string$Formatter"


def refl_attr_fields(fmt: str) -> bool:
    # does format string fmt have a replacement field that reads an attribute ({0.x})
    i = 0
    while i < len(fmt):
        if fmt[i] == "{" and i + 1 < len(fmt) and fmt[i + 1] == "{":
            i += 2
            continue
        if fmt[i] == "{":
            j = i + 1
            while j < len(fmt) and fmt[j] not in "!:}{":
                if fmt[j] == ".":
                    return True
                j += 1
            i = j
            continue
        i += 1
    return False
