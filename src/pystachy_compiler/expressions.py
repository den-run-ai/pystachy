"""Expressions component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.utils import is_union, umembers
from src.pystachy_compiler.analysis import collect, comp_shared, comp_unbound, deleted, only_none, stack_aliases, stack_kept, walrus_names
from src.pystachy_compiler.diagnostics import shown
from src.pystachy_compiler.ir import ClassInfo, FmtArgs, FnInfo, Ins, IterArg, Loop, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.reflection import VARS_USES, refl_annotated, refl_body, refl_fold, refl_reflective
from src.pystachy_compiler.specs import (
    CHECKED,
    DUNDER,
    FOPS,
    FRT,
    GALIASSUB,
    HASATTR,
    ICMP,
    IOPS,
    IRT,
    MODATTRS,
    NONEVAR,
    ORDOP,
    PYBUILTINS,
    RANGEC,
    RANGES,
    REFL,
    STUB,
    TYPE_SIZE,
    TYPING,
    UNARY,
    UNSUPPORTED,
)
from src.pystachy_compiler.syntax import Node, comp_names, made_var, mk, names_in
from src.pystachy_compiler.utils import (
    atomic_dict,
    atomic_list,
    bool_for_int,
    clone,
    elem,
    fbits,
    fmt_index,
    folds,
    int_fits,
    is_callable,
    is_const,
    is_dict,
    is_fn,
    is_gen,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_sopt,
    is_super,
    is_tuple,
    is_vtuple,
    kw_names,
    kw_types,
    lt,
    nones,
    nonetest,
    plain_args,
    runtime_format,
    same_kind,
    selem,
    slice_items,
    takes_self,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_narrows(self, n: Node, truth: bool, out: dict[str, str]) -> None:
    # the locals that test n narrows when its value is truth, as mypy narrows them, and the type
    # each then holds: an optional one is not None (x, x is not None, x != None, isinstance(x,
    # T)), a union holds a value of the types isinstance(x, T) names, or of the others; an
    # ordinary class local is a tested subclass; and not/and/or of those
    if not self.anyopt:
        return
    k = n.kind
    if k == "unary" and n.s == "not":
        self.narrows(n.kids[0], not truth, out)
    elif k == "boolop" and (n.s == "and") == truth:
        self.narrows(n.kids[0], truth, out)
        w: dict[str, bool] = {}
        walrus_names(n.kids[1], w)
        for nm in w:
            out.pop(nm, "")  # (the right operand binds it again)
        self.narrows(n.kids[1], truth, out)
    elif (k == "name" or k == "walrus") and truth and self.narrowable(n.s):
        out[n.s] = unopt(out[n.s] if n.s in out else self.now_type(n.s))  # (x, or (x := v): what x holds now)
    elif k == "cmp" and n.kids[1].kind == "None" and (n.kids[0].kind == "name" or n.kids[0].kind == "walrus") and (n.s == "is not" or n.s == "!=" or n.s == "is" or n.s == "==") and self.narrowable(n.kids[0].s):
        if (n.s == "is not" or n.s == "!=") == truth:
            nm = n.kids[0].s
            out[nm] = unopt(out[nm] if nm in out else self.now_type(nm))
    elif k == "call" and len(n.kids) == 3 and n.kids[0].kind == "name" and n.kids[0].s == "isinstance" and (n.kids[1].kind == "name" or n.kids[1].kind == "walrus") and self.narrowable(n.kids[1].s):
        nm = n.kids[1].s
        t = out[nm] if nm in out else self.now_type(nm)
        if self.bound("isinstance"):
            return
        if is_union(unopt(t)):
            nt = self.isinst_narrow(t, n.kids[2], truth)
            if nt != "":
                out[nm] = nt
        elif truth and t in self.classes and self.classes[t].tag > 0 and n.kids[2].kind == "name" and n.kids[2].s in self.classes and self.derives(n.kids[2].s, t):
            # The runtime class check proved this pointer has the derived layout. Keep
            # the declared storage type, and refine only reads on this control-flow path.
            out[nm] = n.kids[2].s
        elif self.isinst(t, n.kids[2]) == (-2 if truth else -3):
            out[nm] = unopt(t)

def gen_forget_walrus(self, pre: dict[str, str], es: list[Node]) -> dict[str, str]:
    # narrowed as it was before expressions es that may not run, or run in a loop, and whose
    # narrowing is not kept (pre), less the names a := in them may have bound since
    w: dict[str, bool] = {}
    for e in es:
        walrus_names(e, w)
    if len(w) == 0:
        return pre
    out: dict[str, str] = {}
    for nm in pre:
        if nm not in w:
            out[nm] = pre[nm]
    return out

def gen_narrowable(self, name: str) -> bool:
    # a local (or parameter) of an optional type, union, or ordinary class: a global or field
    # may change in a call, and so may a variable that a closure assigns (nonlocal)
    t = self.ltype.get(name, "")
    return (is_opt(t) or is_union(t) or (t in self.classes and self.classes[t].tag > 0)) and not self.is_global(name) and name not in self.nlw

def gen_narrow_by(self, test: Node, truth: bool) -> dict[str, str]:
    # narrowed becomes a copy narrowed by test being truth; the state before is returned
    pre = self.narrowed
    self.narrowed = dict(pre)
    found: dict[str, str] = {}
    self.narrows(test, truth, found)
    for nm in found:
        self.narrowed[nm] = found[nm]
    return pre

def gen_forget(self, body: list[Node], tgt: Node) -> dict[str, str]:
    # a loop: what it binds (in body, and its target tgt) may be None on its later passes, and
    # after it; a copy of the state after it is returned
    if len(self.narrowed) > 0:
        names: dict[str, bool] = {}
        collect(body, names)
        deleted(body, names)
        tn: list[str] = []
        names_in(tgt, tn)
        for nm in tn:
            names[nm] = True
        self.narrowed = dict(self.narrowed)
        for nm in names:
            if nm in self.narrowed:
                del self.narrowed[nm]
    return dict(self.narrowed)

# ---- tests the static types decide
def gen_static(self, n: Node) -> int:
    # 1 or 0 if n is a test whose result the static types decide and that has nothing else to
    # evaluate: isinstance(x, T), x is None and x is not None for a variable x (that is surely
    # assigned), and not/and/or of those; -1 otherwise. A template's function, compiled for
    # its argument types, can so dispatch on them as unannotated code does, also with None is
    # x, x == None and x != None for its parameter x (not where x's class defines __eq__ or
    # __ne__). Elsewhere == runs: the branch it would remove may give a list its item type.
    if self.reflcopies > 1 and refl_fold(n) >= 0:
        return refl_fold(n)  # (a test of the literals an unrolled copy reads: reflection.py)
    k = n.kind
    c = self.const_of(n, {}, True) if self.lit_context() and k != "name" else None
    if c is not None:
        # (a test of the constants of a class that specializes on literals)
        held = c.kind == "True" or (c.kind == "tuple" and len(c.kids) > 0) or (c.kind == "str" and c.s != "") or (c.kind == "int" and c.s != "0") or c.kind == "unary"
        return 1 if held else 0
    x = nonetest(n)
    if x >= 0 and (x == 1 or n.s == "==" or n.s == "!=") and not (self.curfn.inst and n.kids[x].kind == "name" and n.kids[x].s in self.curfn.params and n.kids[x].s not in self.compvars):
        x = -1
    if k == "name" and self.static_type(n) == "None":
        return 0  # a parameter whose argument is None is false
    if k == "name" and is_tuple(self.static_type(n)):
        return 0 if self.static_type(n) == "tuple[]" else 1  # (*args: the extra arguments)
    if k == "name" and is_kw(self.static_type(n)):
        return 0 if self.static_type(n) == "kw[]" else 1  # (**kwargs: the extra keyword arguments)
    if k == "cmp" and n.s in "== != < <= > >=".split() and (self.static_len(n.kids[0]) >= 0 or self.static_len(n.kids[1]) >= 0):
        # len(args) == 2 for a tuple (*args) or a **kwargs record, whose length its type fixes,
        # against an int constant (one that fits in 64 bits: else the test compiles, to its error)
        a = self.static_len(n.kids[0]) if n.kids[0].kind != "int" else int(n.kids[0].s) if int_fits(n.kids[0].s) else -1
        b = self.static_len(n.kids[1]) if n.kids[1].kind != "int" else int(n.kids[1].s) if int_fits(n.kids[1].s) else -1
        if a >= 0 and b >= 0:
            ok = a == b if n.s == "==" else a != b if n.s == "!=" else a < b if n.s == "<" else a <= b if n.s == "<=" else a > b if n.s == ">" else a >= b
            return 1 if ok else 0
    if k == "cmp" and (n.s == "in" or n.s == "not in") and len(n.kids) == 2 and n.kids[0].kind == "str" and n.kids[1].kind == "name" and is_kw(self.static_type(n.kids[1])):
        r = 1 if n.kids[0].s in kw_names(self.static_type(n.kids[1])) else 0  # ("name" in kwargs)
        return r if n.s == "in" else 1 - r
    if k == "unary" and n.s == "not":
        r = self.static(n.kids[0])
        return 1 - r if r >= 0 else -1
    if k == "boolop":
        a = self.static(n.kids[0])
        if a < 0 or (a == 1) == (n.s == "or"):
            return a
        return self.static(n.kids[1])
    if x >= 0:
        t = self.static_type(n.kids[x])
        r = -1 if t == "" or (t in self.classes and not self.knownobj(n.kids[x])) or is_opt(t) or (is_union(t) and self.optional(t) == t) else 1 if t == "None" else 0
        if (n.s == "==" or n.s == "!=") and (t == "exc" or (t in self.classes and ("__eq__" in self.classes[t].methods or "__ne__" in self.classes[t].methods))):
            r = -1  # (CPython calls x.__eq__ or __ne__; an exception's class may define one)
        return r if r < 0 or n.s == "is" or n.s == "==" else 1 - r
    if k == "call" and n.kids[0].kind == "name" and n.kids[0].s == "hasattr" and not self.bound("hasattr") and len(n.kids) == 3 and n.kids[2].kind == "str":
        t = self.static_type(n.kids[1], True)
        if t in self.classes and self.classes[t].tag > 0:
            return -1  # the concrete class may add attributes beyond the static type
        if t != "" and (self.refl_prop_in(t, n.kids[2].s) or self.reference_union(t)):
            return -1  # (a property's getter, or the union's member, decides: reflection.py)
        h = self.has(t, n.kids[2].s) if t != "" else -1
        return 1 if h == -1 and self.knownobj(n.kids[1]) else max(h, -1)
    if k == "call" and n.kids[0].kind == "name" and n.kids[0].s == "isinstance" and not self.bound("isinstance") and len(n.kids) == 3:
        t = self.static_type(n.kids[1], True)
        r = self.isinst(t, n.kids[2]) if t != "" else -1
        return r if r >= 0 else (1 if r == -2 else 0) if r < -1 and self.knownobj(n.kids[1]) else -1
    if k == "call" and n.kids[0].kind == "name" and n.kids[0].s == "callable" and not self.bound("callable") and len(n.kids) == 2:
        t = self.static_type(n.kids[1], True)
        r = self.callable_type(t) if t != "" else -1
        return r if r >= 0 else 1 if r == -2 and self.knownobj(n.kids[1]) else -1
    return -1

def gen_static_len(self, n: Node) -> int:
    # the length of len(x), for a variable x whose type fixes it (a tuple, **kwargs's record),
    # or -1
    if n.kind != "call" or len(n.kids) != 2 or n.kids[0].kind != "name" or n.kids[0].s != "len" or self.bound("len") or n.kids[1].kind != "name":
        return -1
    t = self.static_type(n.kids[1])
    return len(targs(t)) if is_tuple(t) and t != "tuple[]" else 0 if t == "tuple[]" or t == "kw[]" else len(kw_names(t)) if is_kw(t) else -1

def gen_static_reads(self, n: Node) -> None:
    # test n, which static() decides, still reads the classes of its isinstance() tests where it
    # runs, up to where and/or stops (see isinst_reads)
    if n.kind == "unary" and n.s == "not":
        self.static_reads(n.kids[0])
    elif n.kind == "boolop":
        self.static_reads(n.kids[0])
        if (self.static(n.kids[0]) == 1) != (n.s == "or"):
            self.static_reads(n.kids[1])
    elif n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s == "isinstance" and len(n.kids) == 3:
        self.isinst_reads(n.kids[2])

def gen_knownobj(self, n: Node) -> bool:
    # is n a template's parameter whose argument is an object known not to be None (see nnp)
    return n.kind == "name" and n.s in self.curfn.nnp and self.static_type(n) in self.classes

def gen_has(self, t: str, a: str) -> int:
    # hasattr(x, a) for x of static type t: 1 or 0; for an object's own attribute -1 (true
    # unless it is None), or -2 for a field __init__ may leave unassigned (its flag says).
    # The builtin types have CPython 3.13's attributes.
    if a in HASATTR["any"].split():
        return 1
    if t == "None":
        return 1 if a == "__bool__" else 0
    if is_opt(t):
        r = self.has(unopt(t), a)
        if r != 1 and a == "__bool__":
            self.err(f"hasattr() of '{a}' on a {typestr(t)} is not supported")
        return -1 if r == 1 else 0  # (unless it is None)
    if t in self.classes:
        ci = self.classes[t]
        if "." in a:
            return 0  # (no attribute name: a key of a property's setter, x.setter, or a default_factory's)
        if a in ci.methods and ci.methods[a].prop:
            self.err(f"hasattr() of property '{a}' is not supported: read it in a try/except AttributeError block")
        if a in ci.fflag and t + "." + a not in self.cvars:
            return -2
        if a in ci.methods or a in ci.ftypes:
            return -1
        if t in self.nts:
            self.err(f"hasattr() of '{a}' on a NamedTuple is not supported")
        if (a == "__dict__" or a == "__weakref__") and ci.slotlimit:
            return 0  # (__slots__ without them: CPython's objects have neither)
        if a in HASATTR["obj"].split():
            return -1
        if a == "__annotations__" or (a == "__replace__" and self.is_dc(t)):
            # (a dataclass's __replace__, and the annotations of a class body, its or a base's: a
            # dataclass without fields has none)
            c = t
            while c in self.classes and a == "__annotations__":
                if refl_annotated(refl_body(self.classes[c].node)):
                    return -1
                c = self.classes[c].base
            return -1 if a == "__replace__" else 0
        if a == "__abstractmethods__" or a == "_abc_impl":
            return -1 if self.abc_class(t) else 0  # (ABCMeta's, on each class it makes)
        if a in ["__class_getitem__", "__orig_bases__", "__parameters__", "__type_params__"]:
            # (a generic class's, Generic[T] or class C[T], and its subclasses')
            c = t
            while c in self.classes:
                o = self.classes[c].origin if self.classes[c].origin != "" else c
                if o in self.tparams and (a != "__type_params__" or o in self.pep695):
                    return -1
                c = self.classes[c].base
            return 0
        if self.is_dc(t) and a == "__match_args__":
            # (but for match_args=False, which leaves the one a base dataclass writes, if any)
            c = t
            while c in self.classes and "no-match_args" in self.classes[c].dcopts:
                c = self.classes[c].base
            return -1 if c in self.classes else 0
        return -1 if self.is_dc(t) and a in "__dataclass_fields__ __dataclass_params__".split() else 0
    b = "list" if is_list(t) else "dict" if is_dict(t) else "tuple" if is_tuple(t) or is_vtuple(t) else "int" if t == "bool" else "generator" if is_gen(t) else t
    b = t[: t.find("[")] if is_set(t) else b
    if b in HASATTR:
        return 1 if a in HASATTR[b].split() else 0
    self.err(f"hasattr() of '{a}' on a {tname(t)} is not supported")
    return 0

def gen_static_type(self, n: Node, typed: bool = False) -> str:
    # the type of a variable read that cannot fail, or "" (typed: in isinstance or hasattr)
    if n.kind != "name" or n.chk:
        return ""
    if self.whole != 0 and n.s in self.nonevars:
        # for fills, the parameter at the line of the if: None up to the line that binds it,
        # and then of a type known only once that line is compiled
        if self.whole > 0 and self.whole <= self.nonevars[n.s]:
            return "None"
        self.unsure = self.unsure or n.s not in self.ltype
        return self.ltype.get(n.s, "") if self.whole > 0 else ""
    if self.whole > 0 and typed and self.unbound_local(n.s) and n.s not in self.compvars:
        self.unsure = True  # (a local bound further on, whose type decides isinstance and hasattr)
    if (n.s in self.nonevars or n.s in self.noneglobals) and n.s not in self.ltype:
        return "None"
    if n.s in self.ltype:
        t = self.ltype[n.s]
        if typed and t == NONEVAR:
            # (a local that only None has been assigned so far may hold another value on a
            # loop's later passes, unless None is all that its function assigns it)
            body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
            return "None" if only_none(body, n.s) else ""
        return self.narrowed[n.s] if n.s in self.narrowed and (is_opt(t) or is_union(t) or t in self.classes) and t != NONEVAR else t
    if self.is_global(n.s) and n.s in self.gtypes and n.s not in self.gflag:
        return self.gtypes[n.s]
    return ""

def gen_isinst(self, t: str, c: Node) -> int:
    # isinstance(x, c) for x of static type t: 1, 0, -2 for "x is not None" and -3 for "x is
    # None" (an optional value, or an object), or -1 when x's value decides otherwise or c is
    # not a type Pystachy knows
    if c.kind == "binop" and c.s == "|":
        # (a union, where None is NoneType; None | None raises, and so does a tuple in it)
        if not self.puretype(c, False):
            return -1
        return self.isinst(t, mk("tuple", "|", c.line, c.kids))
    if is_union(t):
        # (decided where every member decides it alike, and None, where a class's object may be it)
        rs = [self.isinst(m, c) for m in umembers(t)] + ([self.isinst("None", c)] if self.optional(t) == t else [])
        return rs[0] if len([r for r in rs if r != rs[0]]) == 0 and (rs[0] == 1 or rs[0] == 0) else -1
    if is_opt(t):
        # by whether it is None
        r = self.isinst(unopt(t), c)
        n = self.isinst("None", c)
        return r if r == n else -2 if r == 1 and n == 0 else -3 if r == 0 and n == 1 else -1
    if c.kind == "tuple":
        # one of them, tested in order: CPython stops at a match, and raises at an item that is
        # not a type (anywhere in a union, which checks them all when it is built); it has built
        # every item before, also those past the match (see puretype)
        if c.s == "" and not self.puretype(c, False):
            return -1
        r = 0
        for x in c.kids:
            y = self.isnone(t) if x.kind == "None" and c.s == "|" else self.isinst(t, x)
            if y == -1 or (y == 1 and c.s == ""):
                return y
            r = y if r == 0 else r if y == 0 or y == r else 1  # (None or not None: true)
        return r
    if c.kind == "call" and len(c.kids) == 2 and c.kids[0].kind == "name" and c.kids[0].s == "type" and c.kids[1].kind == "None" and not self.bound("type"):
        return self.isnone(t)
    abc = self.typing_ref(c) if c.kind == "attr" or (c.kind == "name" and c.s not in self.classes and self.imported(c.s) != "") else ""
    if abc == "Sequence" or abc == "MutableSequence" or abc == "Mapping" or abc == "MutableMapping":
        # (collections.abc's: str, bytes and tuple, also a NamedTuple, are Sequences, list is a mutable one)
        if abc.endswith("Mapping"):
            return 1 if is_dict(t) else 0
        if is_list(t) or (abc == "Sequence" and (t == "str" or t == "bytes" or is_tuple(t) or is_vtuple(t))):
            return 1
        return -2 if abc == "Sequence" and (t in self.nts or t == RANGEC) else 0  # (a range is a Sequence too)
    if c.kind != "name":
        return -1
    while c.s in self.taliases and self.alias_kept(c.s):
        c = self.alias_value(c.s)  # (Pos = int: the class int, which nothing else binds to Pos)
    if c.s in self.classes:
        if t in self.classes and self.classes[t].tag > 0:
            return -2 if self.derives(t, c.s) else -1 if self.derives(c.s, t) else 0
        # (an exception of class t, or of a builtin one, may be an object of a class deriving from t)
        xc = self.classes[c.s].exc != "" and (t == "exc" or (t in self.classes and (self.derives(t, c.s) or self.derives(c.s, t))))
        return -2 if t == c.s or (t in self.classes and self.classes[t].origin == c.s) else -1 if xc else 0
    if self.bound(c.s):
        return -1
    if c.s == "object":
        return 1
    if c.s == "int":
        return 1 if t == "int" or t == "bool" else 0
    if c.s == "bool" or c.s == "float" or c.s == "str" or c.s == "bytes":
        return 1 if t == c.s else 0
    if c.s == "tuple" and t in self.nts:
        return -2  # (a tuple, unless it is None)
    if c.s == "tuple" and is_vtuple(t):
        return 1
    if c.s == "list" or c.s == "dict" or c.s == "tuple" or c.s == "set" or c.s == "frozenset":
        return 1 if t.startswith(c.s + "[") else 0
    if c.s == "type" and t.startswith("fn[b:"):
        # a builtin's value: one of CPython's builtin classes (int, list, ...) is a type
        return 1 if t[5:-1] in "bool bytearray bytes classmethod complex dict enumerate filter float frozenset int list map memoryview object property range reversed set slice staticmethod str super tuple type zip".split() else 0
    if c.s == "range" and RANGEC in self.classes:
        return -2 if t == RANGEC else 0  # (an object of lib/_pystachy_range.py's class, unless it is None)
    if c.s in "bytearray memoryview complex range slice type".split():
        return 0
    return -1

def gen_isnone(self, t: str) -> int:
    # isinstance(x, type(None)) for x of static type t, not an optional one (see isinst)
    return 1 if t == "None" else -3 if t in self.classes else 0

def gen_class_matches(self, c: str, t: Node) -> bool:
    # isinstance's type expression, for an exact ordinary class rather than a static upper bound.
    if t.kind == "tuple" or (t.kind == "binop" and t.s == "|"):
        return any([self.class_matches(c, x) for x in t.kids])
    if t.kind == "name" and t.s in self.classes:
        return self.derives(c, t.s)
    return self.isinst(c, t) in [1, -2]

def gen_obj_isinst(self, v: Val, t: Node) -> Val:
    if not self.puretype(t, False):
        self.err("isinstance() is only supported with the builtin types and classes as its second argument")
    end = self.label()
    nonnull = self.label()
    start = self.cur
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, nonnull)
    self.place(nonnull)
    tag = self.mload('int', v.v)
    r = "false"
    for c in self.classes.values():
        if c.tag > 0 and self.derives(c.name, v.t) and self.class_matches(c.name, t):
            hit = self.num_cmp('==', Val(tag, "int"), Val(str(c.tag), "int")).v
            r = hit if r == "false" else self.scalar('or', [Val(r, 'bool'), Val(hit, 'bool')])
    done = self.cur
    self.br(end)
    self.place(end)
    ph = Ins("phi", "bool", "")
    self.incoming(ph, "true" if self.isinst("None", t) == 1 else "false", start)
    self.incoming(ph, r, done)
    return Val(self.phi(ph), "bool")

def gen_isinst_reads(self, c: Node) -> None:
    # c, isinstance's second argument, is built before the test, all of a tuple's or union's
    # items too: a class it names whose class statement may not have run yet raises there,
    # and so does one read through a module whose import raised (modchk)
    if c.kind == "tuple" or (c.kind == "binop" and c.s == "|"):
        for x in c.kids:
            self.isinst_reads(x)
    elif c.kind == "name" and c.s in self.taliases:
        self.expr(c, "")  # (a type alias's variable, Pos = int, unbound before its assignment)
    elif c.kind == "name":
        self.class_ahead(c.s)
        self.modchk(c)
        if (c.chk or self.foreign(c.s)) and c.s in self.gflag and c.s in self.classes:
            self.guard(self.scalar('xor', [Val(self.mload('bool', f'@g.{c.s}.def'), 'bool'), Val('true', 'bool')]), self.unbound(c.s))

def gen_puretype(self, c: Node, u: bool) -> bool:
    # can c, isinstance's second argument, be built without running code or raising, as
    # Pystachy compiles none of it: the types Pystachy knows (it decides isinstance(None, c))
    # and None can, in a tuple the other constants too, a builtin's name (an exception class,
    # tested past a match) and typing's names; in a union (u), None | None, a tuple and what
    # is not a type raise
    if c.kind == "binop" and c.s == "|":
        return (c.kids[0].kind != "None" or c.kids[1].kind != "None") and self.puretype(c.kids[0], True) and self.puretype(c.kids[1], True)
    if c.kind == "tuple":
        for x in c.kids:
            if not self.puretype(x, False):
                return False
        return not u
    if not u and c.kind == "name" and c.s in PYBUILTINS and not self.bound(c.s) and self.imported(c.s) == "":
        return True
    return c.kind == "None" or (not u and (is_const(c) or self.typing_ref(c) in TYPING)) or self.isinst("None", c) >= 0

# ---- expressions
def gen_cond(self, n: Node) -> str:
    if n.kind == "name" and "?" in self.rtype(n.s):
        self.allowq = True
        v = self.read(n)
        self.allowq = False
        return self.truth(v)
    if n.kind == "boolop":
        return self.boolop(n, True, "").v
    if n.kind == "unary" and n.s == "not":
        return self.scalar('xor', [Val(self.cond(n.kids[0]), 'bool'), Val('true', 'bool')])
    return self.truth(self.expr(n, ""))

def gen_truth(self, v: Val) -> str:
    if is_union(unopt(v.t)):
        return self.uop(v, "truth").v
    t = v.t
    if t == "bool":
        return v.v
    if is_fn(t):
        return "true"  # (a function is true)
    if is_kw(t):
        return "true" if len(kw_names(t)) > 0 else "false"  # (**kwargs: true where a keyword argument was given)
    if t == "int":
        return self.num_cmp("!=", v, Val("0", "int")).v
    if t == "float":
        return self.num_cmp("!=", v, Val("0.0", "float")).v
    if t == "str" or t == "bytes" or is_list(t) or is_dict(t) or is_set(t) or is_vtuple(t):
        return self.num_cmp('!=', Val(self.mload('int', v.v), "int"), Val('0', "int")).v
    if t == "None":
        return "false"
    if is_tuple(t):
        return "false" if t == "tuple[]" else "true"
    if is_opt(t):
        # not None, and then the value's own truth
        nn = self.ptr_cmp('!=', v, Val('null', 'None')).v
        e0 = self.cur
        l1 = self.label()
        l2 = self.label()
        self.cbr(nn, l1, l2)
        self.place(l1)
        r = self.truth(self.deref(v))
        e1 = self.cur
        self.br(l2)
        self.place(l2)
        ph = Ins("phi", "bool", "")
        self.incoming(ph, "false", e0)
        self.incoming(ph, r, e1)
        return self.phi(ph)
    nz = self.ptr_cmp('!=', v, Val('null', 'None')).v
    if t in self.classes and self.classes[t].tag > 0:
        cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, t)]
        if any(["__bool__" in c.methods or "__len__" in c.methods for c in cs]):
            # Truth has its own fallback: a subclass can add __bool__ or __len__ even
            # when the static base has neither. Select the concrete protocol before
            # falling back to object.__bool__, and never inspect a None receiver's tag.
            end = self.label()
            nonnull = self.label()
            start = self.cur
            ph = Ins("phi", "bool", "")
            self.incoming(ph, "false", start)
            self.cbr(nz, nonnull, end)
            self.place(nonnull)
            tag = self.mload('int', v.v)
            narrow = dict(self.narrowed)
            for i in range(len(cs)):
                c = cs[i]
                nxt = self.label() if i + 1 < len(cs) else ""
                if nxt != "":
                    arm = self.label()
                    self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(c.tag), "int")).v, arm, nxt)
                    self.place(arm)
                self.narrowed = dict(narrow)
                r = "true"
                if "__bool__" in c.methods:
                    r = self.coerce(self.call_fn(c.methods["__bool__"], [Val(v.v, c.name)], [], direct=True), "bool").v
                elif "__len__" in c.methods:
                    size = self.coerce(self.call_fn(c.methods["__len__"], [Val(v.v, c.name)], [], direct=True), "int")
                    self.guard(self.num_cmp('<', Val(size.v, "int"), Val('0', "int")).v, "ValueError: __len__() should return >= 0")
                    r = self.num_cmp('!=', Val(size.v, "int"), Val('0', "int")).v
                if not self.term:
                    self.incoming(ph, r, self.cur)
                    self.br(end)
                if nxt != "":
                    self.place(nxt)
            self.narrowed = narrow
            self.place(end)
            return self.phi(ph)
    if t in self.classes and ("__bool__" in self.classes[t].methods or "__len__" in self.classes[t].methods):
        # None is false; otherwise __bool__, else __len__() != 0
        l1 = self.label()
        l2 = self.label()
        e1 = self.cur
        self.cbr(nz, l1, l2)
        self.place(l1)
        ms = self.classes[t].methods
        if "__bool__" in ms:
            r = self.coerce(self.call_fn(ms["__bool__"], [Val(v.v, t)], []), "bool").v
        else:
            r = self.num_cmp('!=', Val(self.objlen(Val(v.v, t)).v, "int"), Val('0', "int")).v
        e2 = self.cur
        self.br(l2)
        self.place(l2)
        ph = Ins("phi", "bool", "")
        self.incoming(ph, "false", e1)
        self.incoming(ph, r, e2)
        return self.phi(ph)
    return nz

def gen_list_hint_type(self, a: str, b: str) -> str:
    # A supported annotation for mixed scalar rows. This is diagnostic advice only;
    # successful programs keep their existing inference and representation.
    if is_tuple(a) and is_tuple(b) and len(targs(a)) == len(targs(b)):
        ts = [self.list_hint_type(targs(a)[i], targs(b)[i]) for i in range(len(targs(a)))]
        return self.ctype("tuple", ts) if "" not in ts else ""
    ms = (umembers(unopt(a)) if is_union(unopt(a)) else [unopt(a)]) + (umembers(unopt(b)) if is_union(unopt(b)) else [unopt(b)])
    if any(t not in ["None", "int", "float", "bool", "str"] for t in ms):
        return ""
    t = self.union_type([a, b])
    return "" if t.startswith("!") else t

def gen_expr(self, n: Node, want: str, returnctx: bool = False, resultsoft: bool = False) -> Val:
    self.line = n.line
    k = n.kind
    resultsoft = resultsoft or n is self.soft
    if returnctx and k in ["binop", "boolop", "ifexp"]:
        # Contextual return inference follows fresh literal trees and calls.
        # Other operations keep the hints their operands already needed.
        want = self.generic_hint(n, want)
    if k == "val":
        return self.vnodes[int(n.s)]  # (a value computed already: see vnode)
    if k == "excinfo":
        # (with_cm's except clause: the exception it handles, and its class as an exctype)
        return Val(self.excs[-1].v, "exctype" if n.s == "type" else "exc")
    if k == "int":
        if not int_fits(n.s):
            self.err("integer literal does not fit in 64 bits")
        return Val(n.s, "int")
    if k == "float":
        return Val(fbits(n.s), "float")
    if k == "str":
        self.modchk(n)
        return Val(self.sconst(n.s), "str")
    if k == "bytes":
        self.modchk(n)
        return Val(self.bconst(n.s), "bytes")
    if k == "True" or k == "False":
        return Val(k.lower(), "bool")
    if k == "None":
        return Val("null", "None")
    if k == "name" and (is_opt(want) or want in self.classes) and want != NONEVAR and self.ltype.get(n.s, "") == NONEVAR:
        # a local only None has been assigned so far, where a T | None is expected
        t0 = self.none_type(n.s)
        self.ltype[n.s] = t0 if t0 != "" else want
    if is_opt(want) and k != "ifexp" and k != "boolop":
        want = unopt(want)  # (what types an empty display is the type a value would hold)
    if is_union(want) and (k == "list" or k == "listcomp" or k == "dict" or k == "dictcomp"):
        # A fresh display can use its one declared container member's element
        # storage. Existing mutable containers are never widened or copied.
        candidates = [m for m in umembers(want) if is_dict(m)] if k == "dict" or k == "dictcomp" else [m for m in umembers(want) if is_list(m)]
        if len(candidates) == 1:
            want = candidates[0]
    if k == "name":
        if "?" not in want and same_kind(want, self.ltype.get(n.s, "")) and self.unfilled(n.s):
            self.refine(n.s, want)  # an empty container that nothing fills takes the type expected here
        self.modchk(n)
        return self.read(n)
    if k == "badattr":
        self.err(n.s)  # a module attribute that does not exist, or a module used as a value
    if k == "dcfield":
        self.err("a dataclasses.Field object as a value is not supported; its .name is (#486)")
    if k == "lambda":
        return self.closure(n)
    if k == "set":
        return self.set_display(n, want, False, returnctx, resultsoft)
    if k == "setcomp" or k == "dictcomp":
        if n.kids[0].kind != "listcomp":
            self.err(UNSUPPORTED[n.kids[0].kind])
        return self.listcomp(n.kids[0], want, "", "", None, k[:-4], resultsoft)
    if k == "dictstar":
        return self.dict_merge(n, want)
    if k == "yield":
        return self.yield_value(n)  # (what send() sends the generator)
    if k in UNSUPPORTED:
        self.err(UNSUPPORTED[k])
    if k == "walrus":
        v = self.walrus(n, want)
        self.gencall = ""  # (its target holds a generator the call made: no loop owns it, owned_gen)
        return v
    if k == "binop" and n.s == "%" and self.refl_dict_of(n.kids[1]) is not None and (n.kids[0].kind == "str" or (n.kids[0].kind == "name" and self.const_str(n.kids[0]).kind == "str")):
        return self.refl_percent(n.kids[0].s if n.kids[0].kind == "str" else self.strglobals[n.kids[0].s], n.kids[1])  # (fmt % vars(x): reflection.py)
    if k == "binop" and n.s == "%" and n.kids[0].kind == "str":
        return self.percent(n.kids[0].s, n.kids[1])
    if k == "binop" and n.s == "%" and n.kids[0].kind == "name" and self.const_str(n.kids[0]).kind == "str":
        return self.percent(self.strglobals[n.kids[0].s], n.kids[1])  # (FMT % args of a module's FMT = "...")
    if k == "binop" and n.s == "|" and n.kids[0].kind == "dict" and len(n.kids[0].kids) == 0 and not is_dict(unopt(want)):
        # {} | d: the empty display takes d's type (it has nothing to evaluate first)
        b = self.expr(n.kids[1], "", resultsoft=resultsoft)
        return self.arith(n.s, self.expr(n.kids[0], unopt(b.t) if is_dict(unopt(b.t)) else ""), b)
    if k == "binop":
        a = self.expr(n.kids[0], want, resultsoft=resultsoft)
        return self.arith(n.s, a, self.expr(n.kids[1], a.t, resultsoft=resultsoft))
    if k == "unary":
        return self.unary(n)
    if k == "boolop":
        return self.boolop(n, False, want, resultsoft)
    if k == "cmp":
        return self.compare(n)
    if k == "ifexp":
        return self.ifexp(n, want, resultsoft)
    if k == "call":
        return self.call(n, want, resultsoft)
    if k == "attr":
        path = self.dotted(n)
        if path != "" and path[: path.rfind(".")] not in MODATTRS:
            self.modchk(n)
            return self.modattr(path)
        tc = n.kids[0]
        if is_super(tc) and not self.bound("super"):
            return self.super_call(tc, n.s, [], read=True)
        if n.s == "__dict__" and self.refl_dict_of(n) is not None:
            self.err(VARS_USES)
        if tc.kind == "dcfield":
            if n.s != "name":
                self.err(f"the attribute {n.s} of a dataclasses.Field is not supported; its name is (#486)")
            return Val(self.sconst(tc.s), "str")
        if (n.s == "__name__" or n.s == "__qualname__" or n.s == "__module__") and self.refl_typeof(tc) is not None:
            # type(x).__name__ and x.__class__.__name__: its class's name (an exception's, its
            # ExcClass's), see refl_type_attr
            x = self.refl_typeof(tc)
            if x is not None:
                return self.refl_type_attr(x, n.s)
        c = n.kids[0].s if n.kids[0].kind == "name" and n.kids[0].s not in self.ltype else ""
        if c in self.classes and ((c in self.nts and (n.s == "_fields" or n.s == "_field_defaults")) or (c not in self.nts and n.s in self.classes[c].fdefault)):
            return self.class_attr(n.kids[0], n.s)
        if c in self.classes and n.s == "__name__":
            self.class_ready(n.kids[0])
            return Val(self.sconst(short(c)), "str")  # (C.__name__, and cls.__name__ in a class method)
        if c in self.classes:
            self.no_class_attr(c, n.s)
        o = self.expr(n.kids[0], "")
        if is_fn(o.t) and (n.s == "__name__" or n.s == "__qualname__"):
            # (a function of a module's top level, or a builtin: its own name; a closure's
            # qualified name is outer.<locals>.name, a bound method's C.name)
            fk = o.t[5:-1]
            if o.t.startswith("fn[u:"):
                return Val(self.sconst(fk[fk.find(".") + 1 :] if n.s == "__name__" else fk), "str")
            if o.t.startswith("fn[m:"):
                mn = fk[fk.rfind(".") + 1 :]
                if n.s == "__name__":
                    return Val(self.sconst(mn), "str")
                cn = fk[: fk.rfind(".")]
                ci = self.classes[cn]
                qn = self.sconst(short(ci.methods[mn].cls) + "." + mn)
                if ci.tag > 0:
                    tag = self.mload('int', o.v)
                    for cc in self.classes.values():
                        if cc.tag > 0 and cc.name != cn and self.derives(cc.name, cn):
                            matches = self.num_cmp('==', Val(tag, "int"), Val(str(cc.tag), "int")).v
                            subname = self.sconst(short(cc.methods[mn].cls) + "." + mn)
                            qn = self.select(matches, Val(subname, '%ptr'), Val(qn, '%ptr'))
                return Val(qn, "str")
            if o.t.startswith("fn[d:"):
                mn = fk[: fk.find(":")]
                return Val(self.sconst(mn if n.s == "__name__" else tname(fk[fk.find(":") + 1 :]) + "." + mn), "str")
            if o.t.startswith("fn[c:"):
                clo = self.closures[int(fk[: fk.find(":")])]
                if clo.wunknown != "":
                    self.err(clo.wunknown)
                if clo.wname != "":
                    return Val(self.sconst(clo.wname if n.s == "__name__" else clo.wqual), "str")  # (functools.wraps())
                return Val(self.sconst(clo.name if n.s == "__name__" else clo.qual), "str")
            return Val(self.sconst(short(fk) if o.t.startswith("fn[f:") else fk[fk.rfind(".") + 1 :]), "str")
        if o.t in self.nts and (n.s == "_fields" or n.s == "_field_defaults"):
            self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{n.s}'")
            if n.s == "_field_defaults":
                return self.nt_defaults(self.classes[o.t].origin if self.classes[o.t].origin != "" else o.t)
            return self.tuple_([Val(self.sconst(x), "str") for x in self.classes[o.t].fields])
        if o.t == "exc" and n.s == "__cause__" and self.causeread:
            # (raise ... from c's c, or the StopIteration of PEP 479's RuntimeError; else None)
            return Val(self.rt("pys_exc_cause", "ptr", [f"ptr {o.v}"]), "opt[exc]")
        if unopt(o.t) == "exctype" and n.s == "__name__":
            # (the class of an exception, as __exit__ takes it: the exception itself)
            o = self.unwrap(o, "AttributeError: 'NoneType' object has no attribute '__name__'")
            return Val(self.rt("pys_exc_name", "ptr", [f"ptr {o.v}"]), "str")
        if o.t == "file" and (n.s == "closed" or n.s == "name" or n.s == "mode"):
            r = self.rt(f"pys_file_{n.s}", "i64" if n.s == "closed" else "ptr", [f"ptr {o.v}"])
            return self.num_cmp('!=', Val(r, "int"), Val('0', "int")) if n.s == "closed" else Val(r, "str")
        bm = self.method_value(o, n.s)
        if bm.t != "":
            return bm
        if o.t in self.classes:
            self.fn_attr_read(o, n.s)
        return self.getfield(o, self.field(o, n.s), n.s)
    if k == "index":
        return self.index(n, want)
    if k == "slice":
        o = self.expr(n.kids[0], "")
        if o.t == RANGEC:
            # a range object's slice: the range of those items (lib/_pystachy_range.py's _slice,
            # of the bounds given, a bool as an int, else None)
            bs: list[Node] = [self.vnode(o)]
            for bx in n.kids[1:] + [mk("omit", "", n.line, [])] * (4 - len(n.kids)):
                bv = self.expr(bx, "int") if bx.kind != "omit" else Val("null", "None")
                bs.append(self.vnode(self.as_int(bv) if bv.t == "bool" else bv))
            return self.call_fn(self.funcs[RANGES + "$_slice"], [], bs)
        fold = is_tuple(unopt(o.t)) or o.t in self.nts  # (constant bounds: the items' types)
        bnd = [self.slice_bound(n.kids[1], fold), self.slice_bound(n.kids[2], fold)]
        step = self.slice_step(n.kids[3], fold) if len(n.kids) == 4 else "1"
        o = self.unwrap(o, "TypeError: 'NoneType' object is not subscriptable")
        if o.t in self.classes and o.t not in self.nts and "__getitem__" not in self.classes[o.t].methods:
            self.err(f"'{tname(o.t)}' object is not subscriptable")
        if o.t in self.classes and o.t not in self.nts:
            self.err(f"slicing an object is not supported: {short(o.t)}.__getitem__ would take a slice object, which Pystachy does not have")
        if is_tuple(o.t) or o.t in self.nts:
            return self.slice_tuple(o, bnd, step)
        if is_vtuple(o.t):
            return Val(self.rt("pys_vtuple_slice", "ptr", [f"ptr {o.v}", f"i64 {bnd[0]}", f"i64 {bnd[1]}", f"i64 {step}"]), o.t)
        if o.t != "str" and o.t != "bytes" and not is_list(o.t):
            self.err(f"'{o.t}' cannot be sliced")
        if step == "1":
            fn = "pys_str_slice" if o.t == "str" else "pys_bytes_slice" if o.t == "bytes" else "pys_list_slice"
            return Val(self.rt(fn, "ptr", [f"ptr {o.v}", f"i64 {bnd[0]}", f"i64 {bnd[1]}"]), o.t)
        fn = "pys_str_slice_step" if o.t == "str" else "pys_bytes_slice_step" if o.t == "bytes" else "pys_list_slice_step"
        return Val(self.rt(fn, "ptr", [f"ptr {o.v}", f"i64 {bnd[0]}", f"i64 {bnd[1]}", f"i64 {step}"]), o.t)
    if (k == "list" or k == "tuple") and len([x for x in n.kids if x.kind == "starred"]) > 0:
        return self.star_display(n, want)  # ([a, *xs], (a, *xs))
    if k == "list":
        et = elem(want) if is_list(want) and "?" not in want else ""
        soft = n is self.soft  # (an operand of ==: as its items are, see compare)
        items: list[Val] = []
        given = et != ""
        jt = ""
        for e in n.kids:
            v = self.expr(e, et, returnctx, resultsoft)
            if et == "" and v.t != "None":
                et = v.t
            jt = v.t if jt == "" else self.join(jt, v.t) or "-"  # (the items' types together)
            items.append(v)
        if (returnctx or resultsoft) and given and len([v for v in items if not self.widens(v.t, et) and not self.boxes(v.t, et) and not (is_fn(v.t) and is_callable(unopt(et)))]) > 0:
            # A comparison's expected type is only a hint. Keep the display's
            # own inference if an item cannot enter that representation.
            given = False
            et = ""
            for v in items:
                if et == "" and v.t != "None":
                    et = v.t
        if not given and (is_opt(jt) or is_tuple(jt)):
            et = jt  # None among strings (or T | None among T): T | None (also as tuple items)
        if given and soft:
            for v in items:
                et = self.wider(et, v.t) or et
        if et == "" or et == "None":
            self.err(f"cannot infer the type of {'an empty list' if len(items) == 0 else 'a list of None'}; add a type annotation (xs: list[T] = [], or -> list[T] on a function returning the list)")
        for v in items if not is_list(want) and et in self.classes else items[:0]:
            e0 = et
            while et in self.classes and self.classes[et].exc != "" and v.t in self.classes and not self.derives(v.t, et):
                et = self.classes[et].base  # (exception objects of several classes: a base of them all)
            if e0 in self.classes and et not in self.classes:
                self.err(f"objects of the exception classes {short(e0)} and {short(v.t)} in one list are not supported: no class of the program is a base of both (give them one: class Base(Exception), class {short(e0)}(Base), ...)")
        if not given and jt == "-":
            hint = items[0].t
            for v in items[1:]:
                hint = self.list_hint_type(hint, v.t) if hint != "" else ""
            for v in items if hint != "" else items[:0]:
                if not (self.term and v.v == "undef") and not self.widens(v.t, et) and not self.converts(v.t, et):
                    self.line = n.line
                    advice = typestr(hint).replace("float | int", "int | float")
                    numeric = "; for numeric promotion instead, write float literals or use float() on the integer items" if all(x.t in ["int", "float"] for x in items) else ""
                    self.err(f"expected {typestr(et)}, got {typestr(v.t)}; this list literal needs list[{advice}] to preserve its mixed item types (include enclosing containers in the annotation){numeric}")
        items = [self.coerce(v, et) for v in items]
        lty = self.ctype("list", [et])
        r = self.rt("pys_list_new_atomic" if atomic_list(lty) else "pys_list_new", "ptr", [f"i64 {len(items)}"])
        for v in items:
            self.rt("pys_list_append", "void", [f"ptr {r}", "i64 " + self.to_slot(v)])
        return Val(r, lty)
    if k == "dict":
        kv = targs(want) if is_dict(want) and "?" not in want else ["", ""]
        soft = n is self.soft
        ks: list[Val] = []
        vs: list[Val] = []
        given = kv[1] != ""
        kgiven = kv[0] != ""
        jt = ""
        kj = ""
        for i in range(0, len(n.kids), 2):
            a = self.expr(n.kids[i], kv[0], returnctx, resultsoft)
            if kv[0] == "":
                kv[0] = a.t
            b = self.expr(n.kids[i + 1], kv[1], returnctx, resultsoft)
            if kv[1] == "" and b.t != "None":
                kv[1] = b.t
            jt = b.t if jt == "" else self.join(jt, b.t) or "-"
            kj = a.t if kj == "" else self.join(kj, a.t) or "-"
            ks.append(a)
            vs.append(b)
        if (returnctx or resultsoft) and kgiven and len([v for v in ks if not self.widens(v.t, kv[0]) and not self.boxes(v.t, kv[0])]) > 0:
            kgiven = False
            kv[0] = ks[0].t
        if (returnctx or resultsoft) and given and len([v for v in vs if not self.widens(v.t, kv[1]) and not self.boxes(v.t, kv[1]) and not (is_fn(v.t) and is_callable(unopt(kv[1])))]) > 0:
            given = False
            kv[1] = ""
            for v in vs:
                if kv[1] == "" and v.t != "None":
                    kv[1] = v.t
        if not given and (is_opt(jt) or is_tuple(jt)):
            kv[1] = jt  # None among strings (or T | None among T): T | None (also as tuple items)
        if not kgiven and is_tuple(kj):
            kv[0] = self.none_items(kj)
        ks = [self.store_key(x, kv[0]) for x in ks]
        if given and soft:
            for b in vs:
                kv[1] = self.wider(kv[1], b.t) or kv[1]
        if kv[0] == "" or kv[1] == "":
            self.err(f"cannot infer the type of {'an empty dict' if len(ks) == 0 else 'a dict of None values'}; add a type annotation (d: dict[K, V] = {{}}, or -> dict[K, V] on a function returning the dict)")
        vs = [self.coerce(x, kv[1]) for x in vs]
        if self.key_problem(kv[0]) != "":
            self.err(self.key_problem(kv[0]))
        r = self.rt("pys_dict_new_atomic" if atomic_dict(self.ctype("dict", kv)) else "pys_dict_new", "ptr", [f"i64 {self.key_kind(kv[0])}", f"i64 {len(ks)}"])
        for i in range(len(ks)):
            self.rt("pys_dict_set", "void", [f"ptr {r}", "i64 " + self.to_slot(ks[i]), "i64 " + self.to_slot(vs[i])], self.key_fx(kv[0]))
        return Val(r, self.ctype("dict", kv))
    if k == "tuple":
        ws = targs(want) if is_tuple(want) else []
        vals: list[Val] = []
        for i in range(len(n.kids)):
            v = self.expr(n.kids[i], ws[i] if i < len(ws) else "", returnctx, resultsoft)
            if i < len(ws) and v.t != ws[i] and self.widens(v.t, ws[i]):
                v = Val(v.v, ws[i])  # (None as an object, T as T | None)
            elif i < len(ws) and self.converts(v.t, ws[i]) and not is_sopt(v.t):
                v = self.coerce(v, ws[i])  # (an int as an int | None: its box)
            elif i < len(ws) and is_fn(v.t) and is_callable(unopt(ws[i])):
                v = self.coerce(v, ws[i])  # (a function where a Callable is expected: made one)
            vals.append(v)
        return self.stack_tuple(vals) if n is self.stkkey else self.tuple_(vals)
    if k == "listcomp":
        if n.s == "gen":
            return self.genexp_value(n)  # (where no consumer takes its items at once: a generator)
        unrolled = self.unroll(n)
        if unrolled is not None:
            return self.expr(mk("list", "", n.line, unrolled), want, resultsoft=resultsoft)
        return self.listcomp(n, want, resultsoft=resultsoft)
    if k == "fstr":
        parts: list[Val] = []
        for part in n.kids:
            if part.kind == "fmt" and self.refl_textual(part.kids[0]) and part.kids[1].kind == "str" and part.kids[1].s == "":
                parts.append(self.refl_finish(self.refl_defer(part.kids[0]), "str"))  # (f"{vars(o)}": reflection.py)
            elif part.kind == "fmt":
                parts.append(self.format_(self.expr(part.kids[0], ""), part.kids[1]))
            elif part.kind == "str":
                parts.append(Val(self.sconst(part.s), "str"))
            else:
                parts.append(self.to_str(self.expr(part, "")))  # compiler-written parts (dataclass __repr__)
        return self.concat(parts)
    self.err(f"unsupported expression '{k}'")
    return Val("", "")

def gen_class_attr(self, cn: Node, a: str) -> Val:
    # C.a through the class: a NamedTuple's _fields, or the value a class-body default binds
    # (instances read it until they assign the field; C.a = v is not supported)
    ci = self.class_ready(cn)
    if a == "_fields":
        return self.tuple_([Val(self.sconst(x), "str") for x in self.nt_fields(ci.name)])
    if a == "_field_defaults":
        return self.nt_defaults(ci.name)
    t = ci.ftypes[a]
    if is_const(ci.fdefault[a]) and cn.s + "." + a not in self.cvars:
        return self.coerce(self.expr(ci.fdefault[a], t), t)
    self.class_default(ci, a)
    return Val(self.mload(t, ci.fglob[a]), t)

def gen_cvar_stores(self, ns: list[Node]) -> None:
    # the class attributes the program assigns through their class (C.x = v, C.x += v; a class
    # method's cls.x is C.x): those of a plain class become class variables (self.cvars), read
    # from their global by C.x and by the objects that have not assigned x themselves
    for n in ns:
        ts: list[Node] = n.kids[:-1] if n.kind == "assign" else [n.kids[0]] if (n.kind == "augassign" or n.kind == "annassign") and len(n.kids) > 0 else []
        while len(ts) > 0:
            t = ts.pop()
            if t.kind == "tuple" or t.kind == "starred":
                ts.extend(t.kids)
            elif t.kind == "attr" and t.kids[0].kind == "name" and t.kids[0].s in self.classes:
                c = t.kids[0].s
                if not self.is_dc(c) and t.s in self.classes[c].fdefault:
                    self.cvars[c + "." + t.s] = True
                    # (and of the exception classes that share it, see cvar)
                    h = self.default_home(self.classes[c], t.s)
                    for x in self.classes.values():
                        related = self.classes[c].tag > 0 and x.tag > 0 and (self.derives(c, x.name) or self.derives(x.name, c))
                        if t.s in x.ftypes and (related or (t.s in x.fdefault and self.default_home(x, t.s) is h)):
                            self.cvars[x.name + "." + t.s] = True
        self.cvar_stores(n.kids)

def gen_cvar(self, cn: Node, a: str) -> ClassInfo:
    # the class that C.a = ... assigns a class variable of (see cvar_stores), checked
    c = cn.s
    if self.is_dc(c):
        self.err(f"assigning to a class attribute of {'NamedTuple' if c in self.nts else 'dataclass'} {short(c)} ({short(c)}.{a} = ...) is not supported")
    if c + "." + a not in self.cvars:
        self.err(f"type object '{short(c)}' has no attribute '{a}': adding a class attribute by assigning it is not supported (declare it in the class body, {a}: T = ...)")
    # an exception class shares the class variables it inherits with its base (default_home):
    # one global each, which the objects of both read
    ci = self.classes[c]
    h = self.default_home(ci, a)
    if h is not ci:
        how = f" (cls in class method {self.curfn.name}(), which {short(c)} inherits)" if self.curfn.deco == "classmethod" and self.curfn.cls == c and self.curfn.name not in self.body_names(ci.node) else ""
        self.err(f"assigning class attribute '{a}' through {short(c)}{how}, which inherits it from {short(h.name)}, is not supported (CPython would give {short(c)} an attribute of its own; {short(h.name)}.{a} = ... changes the one they share)")
    for x in self.classes.values():
        if ci.tag == 0 and a in x.fdefault and x is not ci and (self.derives(x.name, c) or self.derives(c, x.name)) and self.default_home(x, a) is not h:
            self.err(f"assigning class attribute {short(c)}.{a} is not supported where {short(x.name)} binds '{a}' in its class body too: an object's class attribute is read through the class of its static type (no dispatch on the object's class)")
    return self.class_ready(cn)

def gen_class_store(self, ci: ClassInfo, a: str, v: Val) -> None:
    # C.a = v through the class: its class variable's global
    self.class_default(ci, a)
    self.mstore(ci.ftypes[a], self.coerce(v, ci.ftypes[a]).v, ci.fglob[a])

def gen_no_class_attr(self, c: str, a: str) -> None:
    # C.a where class C binds no class attribute a: CPython's AttributeError, or why it is not supported
    ci = self.classes[c]
    if ci.bad != "":
        self.err(ci.bad)
    if c in self.nts and a in self.nt_fields(c):
        self.err(f"reading a NamedTuple's field through its class ({short(c)}.{a}, a descriptor in CPython) is not supported")
    if c in self.nts and a == "__doc__":
        self.err(f"reading the __doc__ of NamedTuple {short(c)} is not supported (Pystachy keeps no docstrings of classes)")
    if a in ci.methods:
        if ci.methods[a].prop:
            self.err(f"{short(c)}.{a} is a property: read it on an instance")
        self.err(f"method '{short(c)}.{a}' cannot be used as a value (call it)")
    if a in ci.fields:
        self.err(f"type object '{short(c)}' has no attribute '{a}' (its objects have the field '{a}')")
    self.err(f"type object '{short(c)}' has no attribute '{a}'")

def gen_class_ready(self, cn: Node) -> ClassInfo:
    # the class that name cn reads (C.a, C.m(...)), checked where its class statement may not
    # have run yet, or where the import that binds it (or its module) may have raised
    c = cn.s
    self.class_ahead(c)  # (not where cn is a local of the function, assigned further on)
    ci = self.classes[c]
    if ci.bad != "":
        self.err(ci.bad)
    self.modchk(cn)
    if (cn.chk or self.foreign(c)) and c in self.gflag:
        self.guard(self.scalar('xor', [Val(self.mload('bool', f'@g.{c}.def'), 'bool'), Val('true', 'bool')]), self.unbound(c))
    return ci

def gen_class_call(self, cn: Node, m: str, args: list[Node], want: str, resultsoft: bool = False) -> Val:
    # C.m(...): a static or class method called through its class (cls.m(...) in a class method)
    ci = self.class_ready(cn)
    if m not in ci.methods and m in ci.fdefault and cn.s not in self.nts:
        return self.obj_call(self.class_attr(cn, m), args, want, resultsoft)  # (C.k(args) of a class attribute k)
    if m not in ci.methods and m == "register" and self.abc_class(cn.s):
        self.err(f"{short(cn.s)}.register() is not supported: isinstance() and issubclass() of an ABC are decided by the class statements, so no class can become a virtual subclass")
    if m not in ci.methods:
        self.err(f"type object '{short(cn.s)}' has no attribute '{m}'")
    f = ci.methods[m]
    if f.prop:
        self.err(f"{short(cn.s)}.{m} is a property: read it on an instance")
    if f.bad == STUB.replace("NAME", m):
        self.err(f.bad)  # (an imported module's: CPython's stub raises NotImplementedError, however it is called)
    if f.deco == "":
        if ci.tag > 0:
            if len(args) == 0 or args[0].kind in ["kw", "starred", "dstar"]:
                self.err(f"{short(cn.s)}.{m}() needs an instance as its first argument")
            o = self.expr(args[0], cn.s)
            if o.t not in self.classes or not self.derives(o.t, cn.s):
                self.err(f"{short(cn.s)}.{m}() needs an instance of {short(cn.s)}")
            self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
            return self.call_fn(f, [o], args[1:], want, direct=True, resultsoft=resultsoft)
        self.err(f"{short(cn.s)}.{m}() is a method of its objects: calling it through the class is not supported; call it on an object, o.{m}(...)")
    self.cls_bound(f, cn.s, False)
    return self.call_fn(f, [], args, want, resultsoft=resultsoft)

def gen_cls_bound(self, f: FnInfo, c: str, obj: bool) -> None:
    # a class method that uses cls, called through class c (obj: through an object of c, which
    # may be of a class deriving from c): it is compiled for each class that has it, whose
    # name its cls reads (see inherit), so the call's class must be f's. A static or class
    # method that a class deriving from c overrides is called through c alone, as calls are
    # not dispatched on an object's class.
    if f.deco != "" and obj:
        for x in self.classes.values():
            if x.name != c and not x.excluded and self.derives(x.name, c) and f.name in x.methods and x.methods[f.name].orig is not f.orig:
                self.err(f"calling {'static' if f.deco == 'staticmethod' else 'class'} method {f.name}() on an object of {short(c)}, which may be one of {short(x.name)}, is not supported: {short(x.name)} overrides it (calls are not dispatched on the object's class; call {short(c)}.{f.name}() or {short(x.name)}.{f.name}())")
    if f.deco != "classmethod" or not f.clsuse:
        return
    subs = [x.name for x in self.classes.values() if obj and x.name != c and self.derives(x.name, c)]
    if f.cls != c:
        self.err(f"calling class method {short(c)}.{f.name}() is not supported: it uses cls, and is compiled only for {short(f.cls)}, which defines it (a class that inherits it has its own only where no default value of it is evaluated when its def runs, and in the same module)")
    if len(subs) > 0:
        self.err(f"calling class method {f.name}() on an object of {short(c)}, which may be one of {short(subs[0])}, is not supported: it uses cls, which would be {short(c)} (calls are not dispatched on the object's class; call {short(c)}.{f.name}() or {short(subs[0])}.{f.name}())")

def gen_percent(self, fmt: str, rhs: Node) -> Val:
    # "format" % args with a constant format: each conversion becomes what format() or
    # str()/repr() of its argument gives, as CPython's printf-style formatting does
    items: list[Val] = []
    if rhs.kind == "tuple":
        for x in rhs.kids:
            items.append(self.expr(x, ""))
    else:
        v = self.ntup(self.expr(rhs, ""))  # (a NamedTuple is a tuple: its fields are the arguments)
        if is_tuple(unopt(v.t)) and is_opt(v.t):
            return self.percent_opt(fmt, v)
        if is_tuple(v.t):
            for i in range(len(targs(v.t))):
                items.append(self.tget(v, i))
        elif is_dict(unopt(v.t)) and "%(" in fmt:
            self.err("% formatting with a mapping (%(name)s) is not supported")
        else:
            items.append(v)
    return self.pformat(fmt, items, False)

def gen_percent_opt(self, fmt: str, v: Val) -> Val:
    # "format" % t, t a tuple or None: the tuple's items are the arguments, None is one argument
    l1 = self.label()
    l2 = self.label()
    l3 = self.label()
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, l1, l2)
    self.place(l1)
    a = self.pformat(fmt, [Val("null", "None")], True)
    ph = Ins("phi", "str", "")
    if not self.term:
        self.incoming(ph, a.v, self.cur)
    self.br(l3)
    self.place(l2)
    tv = Val(v.v, unopt(v.t))
    items: list[Val] = []
    for i in range(len(targs(tv.t))):
        items.append(self.tget(tv, i))
    b = self.pformat(fmt, items, False)
    if not self.term:
        self.incoming(ph, b.v, self.cur)
    self.br(l3)
    self.place(l3)
    if len(ph.a) == 0:
        self.unreachable()
        return Val(self.sconst(""), "str")
    return Val(self.phi(ph), "str")

def gen_pformat(self, fmt: str, items: list[Val], rtnone: bool) -> Val:
    # fmt % items; rtnone: a None among them that a conversion cannot take raises when it runs
    # (it is a tuple's place, see percent_opt), as CPython's error
    parts: list[Val] = []
    lit: list[str] = []
    used = 0
    i = 0
    while i < len(fmt):
        c = fmt[i]
        i += 1
        if c != "%":
            lit.append(c)
            continue
        if i < len(fmt) and fmt[i] == "%":
            lit.append("%")
            i += 1
            continue
        flags = ""
        while i < len(fmt) and fmt[i] in "-+ #0":
            flags += fmt[i]
            i += 1
        width = ""
        while i < len(fmt) and (fmt[i].isdigit() or fmt[i] == "*"):
            width += fmt[i]
            i += 1
        prec = ""
        if i < len(fmt) and fmt[i] == ".":
            i += 1
            prec = "."
            while i < len(fmt) and (fmt[i].isdigit() or fmt[i] == "*"):
                prec += fmt[i]
                i += 1
        while i < len(fmt) and fmt[i] in "hlL":
            i += 1
        if i >= len(fmt):
            self.err("ValueError: incomplete format")
        t = fmt[i]
        i += 1
        if "*" in width or "*" in prec:
            self.err("% formatting with a * width or precision is not supported")
        if t not in "sradiuxXoeEfFgGc":
            self.err(f"unsupported format character '{t}' ({ord(t):#x}) at index {i - 1}")
        if used >= len(items):
            return self.fmt_error("not enough arguments for format string")
        v = items[used]
        used += 1
        if len(lit) > 0:
            parts.append(Val(self.sconst("".join(lit)), "str"))
            lit = []
        if rtnone and v.t == "None" and t not in "sra":
            return self.fmt_error(self.nonefmt(t))
        if is_sopt(v.t) and t not in "sra":
            v = self.unwrap(v, "TypeError: " + self.nonefmt(t))
        parts.append(self.conversion(v, flags, width, prec, t))
    if used < len(items):
        return self.fmt_error("not all arguments converted during string formatting")
    if len(lit) > 0:
        parts.append(Val(self.sconst("".join(lit)), "str"))
    return self.concat(parts)

def gen_nonefmt(self, t: str) -> str:
    # what %-conversion t (not s, r or a) raises for None
    if t == "c":
        return "%c requires int or char"
    if t in "diuxXo":
        return f"%{t} format: {'a real number' if t in 'diu' else 'an integer'} is required, not NoneType"
    return "must be real number, not NoneType"

def gen_fmt_error(self, msg: str) -> Val:
    self.raise_("TypeError", self.sconst(msg))
    return Val(self.sconst(""), "str")

def gen_str_format(self, fmt: str, m: str, args: list[Node]) -> Val:
    # "...".format(args) or "...".format_map(mapping) of a literal format: the arguments are
    # evaluated as a call evaluates them, then the format is read as CPython's str.format reads
    # it (Objects/stringlib/unicode_format.h), each field formatted in turn as it comes; an error
    # in the format, a missing argument or a bad conversion raises then, as CPython's does
    fa = FmtArgs(f"str.{m}()")
    if m == "format_map":
        if len([a for a in args if a.kind == "kw" or a.kind == "dstar"]) > 0:
            self.err("str.format_map() takes no keyword arguments")
        if len([a for a in args if a.kind == "starred"]) > 0:
            self.err("unpacking arguments into str.format_map() is not supported")
        if len(args) != 1:
            self.err(f"str.format_map() takes exactly one argument ({len(args)} given)")
        fa.kd = self.expr(args[0], "")
        fa.mapping = True
    elif not self.format_args(fa, args):
        return Val(self.sconst(""), "str")
    r = self.str_fields(fmt, 2, fa)
    return r if r.t != "" else Val(self.sconst(""), "str")

def gen_format_of(self, f: Node) -> Node:
    # FMT.format (or format_map) of a module's FMT = "..." as the literal's method (const_str);
    # any other f as it is
    if f.kind != "attr" or (f.s != "format" and f.s != "format_map"):
        return f
    o = self.const_str(f.kids[0])
    return f if o is f.kids[0] else mk("attr", f.s, f.line, [o])

def gen_const_str(self, o: Node) -> Node:
    # the literal that name o reads where it is a module's FMT = "..." (module_strs), once it is
    # read (with its checks), as a format is read before its arguments; any other o as it is
    if o.kind != "name" or o.s not in self.strglobals or not self.globread(o.s) or self.gtype(o.s) != "str":
        return o
    self.expr(o, "")
    return mk("str", self.strglobals[o.s], o.line, [])

def gen_format_args(self, fa: FmtArgs, args: list[Node]) -> bool:
    # str.format()'s arguments, evaluated into fa: the positional ones in order (* of a tuple
    # gives its items; of a list, as the last, a copy of it), then the keywords (** of a function's
    # **kwargs, of a dict display with str keys, or a copy of a dict[str, T]); False where a
    # keyword given twice raises
    line = self.line
    for a in args:
        if a.kind == "kw" or a.kind == "dstar":
            continue
        if fa.rest.t != "":
            self.err(f"unpacking a list into the arguments of {fa.who} is supported only after the other positional arguments")
        if a.kind != "starred":
            fa.pos.append(self.expr(a, ""))
            continue
        v = self.ntup(self.expr(a.kids[0], ""))
        self.line = a.line
        v = self.unwrap(v, f"TypeError: {fa.who} argument after * must be an iterable, not NoneType")
        if is_tuple(v.t):
            for i in range(len(targs(v.t))):
                fa.pos.append(self.tget(v, i))
        elif is_list(v.t):
            fa.rest = self.bmethod(v, "copy", [])
        elif is_vtuple(v.t):
            fa.rest = self.as_list(v, "format")
        elif v.t == RANGEC:
            self.notnone(v, f"TypeError: {fa.who} argument after * must be an iterable, not NoneType")
            fa.rest = self.as_list(v, "format")  # (a new list of its numbers)
        else:
            self.err(f"unpacking a {typestr(v.t)} into the arguments of {fa.who} is not supported (a tuple's or a list's items are)")
    at = 0
    while at < len(args):
        a = args[at]
        at += 1
        if a.kind == "kw":
            # (the keywords up to the next ** are all evaluated, then each name checked in turn,
            # as CPython builds a dict of them and merges it)
            run = [a]
            while at < len(args) and args[at].kind != "dstar":
                if args[at].kind == "kw":
                    run.append(args[at])
                at += 1
            vals = [self.expr(k.kids[0], "") for k in run]
            for j in range(len(run)):
                if not self.format_kw(fa, run[j].s, vals[j]):
                    return False
        elif a.kind == "dstar" and a.kids[0].kind == "dict" and len([i for i in range(0, len(a.kids[0].kids), 2) if a.kids[0].kids[i].kind != "str"]) == 0:
            # (**{"k": v}: its items, a later key's value replacing an earlier one's, as in the dict)
            d = a.kids[0]
            names: list[str] = []
            vals: list[Val] = []
            for i in range(0, len(d.kids), 2):
                v = self.expr(d.kids[i + 1], "")
                if d.kids[i].s in names:
                    vals[names.index(d.kids[i].s)] = v
                else:
                    names.append(d.kids[i].s)
                    vals.append(v)
            for j in range(len(names)):
                if not self.format_kw(fa, names[j], vals[j]):
                    return False
        elif a.kind == "dstar":
            v = self.expr(a.kids[0], "")
            if is_kw(v.t):
                names = kw_names(v.t)
                for i in range(len(names)):
                    if not self.format_kw(fa, names[i], self.tget(self.kw_tuple(v), i)):
                        return False
                continue
            self.line = a.line
            v = self.unwrap(v, f"TypeError: {fa.who} argument after ** must be a mapping, not NoneType")
            if not is_dict(v.t) or targs(v.t)[0] != "str":
                self.err(f"** of a {typestr(v.t)} into the arguments of {fa.who} is not supported (of a dict[str, T], a function's **kwargs or a dict display with str keys, it is)")
            if fa.kd.t != "":
                self.err(f"** of more than one dict into the arguments of {fa.who} is not supported")
            fa.kd = self.bmethod(v, "copy", [])
            self.format_merge(fa)
    self.line = line
    return True

def gen_format_kw(self, fa: FmtArgs, name: str, v: Val) -> bool:
    # keyword argument name=v of str.format(): CPython's TypeError (False) where an earlier one
    # has the name, and once it runs where the dict of a ** has it
    if name in fa.kwn:
        self.raise_("TypeError", self.sconst(f"{fa.who} got multiple values for keyword argument '{name}'"))
        return False
    if fa.kd.t != "":
        self.format_dup(fa, name)
    fa.kwn.append(name)
    fa.kwv.append(v)
    return True

def gen_format_dup(self, fa: FmtArgs, name: str) -> None:
    line = self.line
    has = self.expr(mk("cmp", "in", line, [mk("str", name, line, []), self.vnode(fa.kd)]), "bool")
    self.guard(has.v, f"TypeError: {fa.who} got multiple values for keyword argument '{name}'")

def gen_format_merge(self, fa: FmtArgs) -> None:
    # the keywords before a ** of a dict (fa.kd, its copy): CPython's TypeError, once it runs,
    # for the first of the dict's keys, in its order, that one of them has
    if len(fa.kwn) < 2:
        for nm in fa.kwn:
            self.format_dup(fa, nm)
        return
    line = self.line
    k = made_var("__pys_item", line)
    names = mk("tuple", "", line, [mk("str", nm, line, []) for nm in fa.kwn])
    dups = self.expr(mk("listcomp", "", line, [k, k, self.vnode(fa.kd), mk("cmp", "in", line, [k, names])]), "")
    l1 = self.label()
    l2 = self.label()
    self.cbr(self.num_cmp('!=', Val(self.mload('int', dups.v), "int"), Val("0", "int")).v, l1, l2)
    self.place(l1)
    key = self.expr(mk("index", "", line, [self.vnode(dups), mk("int", "0", line, [])]), "")
    msg = self.concat([Val(self.sconst(f"{fa.who} got multiple values for keyword argument '"), "str"), key, Val(self.sconst("'"), "str")])
    self.raise_("TypeError", msg.v)
    self.place(l2)

def gen_fmt_raise(self, kind: str, msg: str) -> Val:
    # raise kind(msg) (a KeyError's msg is the key, shown by its repr): Val("", "")
    self.raise_(kind, self.repr(Val(self.sconst(msg), "str")).v if kind == "KeyError" else self.sconst(msg))
    return Val("", "")

def gen_str_fields(self, s: str, depth: int, fa: FmtArgs) -> Val:
    # CPython's build_string: s formatted with fa's arguments, at nesting depth (2, then 1 in a
    # field's spec), its text and each field in turn (str_field); Val("", "") where it raises
    if depth <= 0:
        return self.fmt_raise("ValueError", "Max string recursion exceeded")
    parts: list[Val] = []
    n = len(s)
    i = 0
    while i < n:
        # the text up to a '{' or '}', which the same brace after it escapes (MarkupIterator_next)
        start = i
        c = ""
        while i < n and c != "{" and c != "}":
            c = s[i]
            i += 1
        brace = c == "{" or c == "}"
        ln = i - start
        if c == "}" and (i >= n or s[i] != "}"):
            return self.fmt_raise("ValueError", "Single '}' encountered in format string")
        if c == "{" and i >= n:
            return self.fmt_raise("ValueError", "Single '{' encountered in format string")
        if brace and s[i] == c:
            i += 1
            brace = False
        elif brace:
            ln -= 1
        if ln > 0:
            parts.append(Val(self.sconst(s[start : start + ln]), "str"))
        if not brace:
            continue
        # the field's name, up to a '}', ':' or '!' (not within [...]), then its conversion and
        # spec, whose braces nest (parse_field)
        j = i
        c = ""
        while i < n and c != "}" and c != ":" and c != "!":
            c = s[i]
            i += 1
            if c == "{":
                return self.fmt_raise("ValueError", "unexpected '{' in field name")
            if c == "[":
                while i < n and s[i] != "]":
                    i += 1
        name = s[j : i - 1]
        conv = ""
        spec = ""
        expand = False
        if c == "!" or c == ":":
            done = False
            if c == "!":
                if i >= n:
                    return self.fmt_raise("ValueError", "end of string while looking for conversion specifier")
                # (one character: str holds UTF-8 bytes)
                k = i + 1
                end = i + (1 if ord(s[i]) < 0xC0 else 2 if ord(s[i]) < 0xE0 else 3 if ord(s[i]) < 0xF0 else 4)
                while k < n and k < end and ord(s[k]) >= 0x80 and ord(s[k]) < 0xC0:
                    k += 1
                conv = s[i:k]
                i = k
                if i < n:
                    c = s[i]
                    i += 1
                    done = c == "}"
                    if c != "}" and c != ":":
                        return self.fmt_raise("ValueError", "expected ':' after conversion specifier")
            if not done:
                j = i
                count = 1
                while i < n and count > 0:
                    c = s[i]
                    i += 1
                    if c == "{":
                        expand = True
                        count += 1
                    elif c == "}":
                        count -= 1
                if count > 0:
                    return self.fmt_raise("ValueError", "unmatched '{' in format spec")
                spec = s[j : i - 1]
        elif c != "}":
            return self.fmt_raise("ValueError", "expected '}' before end of string")
        r = self.str_field(name, conv, spec, expand, depth, fa)
        if r.t == "":
            return r
        parts.append(r)
    return self.concat(parts)

def gen_str_field(self, name: str, conv: str, spec: str, expand: bool, depth: int, fa: FmtArgs) -> Val:
    # CPython's output_markup: the object field name gives (its argument, then each .attr and
    # [key] of it in turn), converted by conv, formatted by spec once the fields in spec are;
    # Val("", "") where it raises
    line = self.line
    j = 0
    while j < len(name) and name[j] != "." and name[j] != "[":
        j += 1
    first = name[:j]
    idx = fmt_index(first)
    if idx == -2:
        return self.fmt_raise("ValueError", "Too many decimal digits in format string")
    if first == "" or idx >= 0:
        # ({} numbers the fields automatically, {0} manually, and a format cannot do both)
        if fa.auto[0] == 0:
            fa.auto[0] = 1 if first == "" else 2
        if fa.auto[0] == 2 and first == "":
            return self.fmt_raise("ValueError", "cannot switch from manual field specification to automatic field numbering")
        if fa.auto[0] == 1 and first != "":
            return self.fmt_raise("ValueError", "cannot switch from automatic field numbering to manual field specification")
        if first == "":
            idx = fa.auto[1]
            fa.auto[1] += 1
    v = self.format_arg(first, idx, fa)
    k = j
    while k < len(name) and v.t != "":
        c = name[k]
        k += 1
        a = k
        if c == ".":
            while k < len(name) and name[k] != "." and name[k] != "[":
                k += 1
        elif c == "[":
            while k < len(name) and name[k] != "]":
                k += 1
            if k >= len(name):
                return self.fmt_raise("ValueError", "Missing ']' in format string")
            k += 1
        else:
            return self.fmt_raise("ValueError", "Only '.' or '[' may follow ']' in format field specifier")
        key = name[a:k] if c == "." else name[a : k - 1]
        ki = fmt_index(key) if c == "[" else -1
        if ki == -2:
            return self.fmt_raise("ValueError", "Too many decimal digits in format string")
        if key == "":
            return self.fmt_raise("ValueError", "Empty attribute in format string")
        # (an item's key is an int where it is digits, else a str)
        x = mk("int", str(ki), line, []) if ki >= 0 else mk("str", key, line, [])
        v = self.expr(mk("attr", key, line, [self.vnode(v)]) if c == "." else mk("index", "", line, [self.vnode(v), x]), "")
    if v.t == "":
        return v
    if conv != "" and conv != "\x00":  # (CPython's NUL, as no conversion)
        if conv != "r" and conv != "s" and conv != "a":
            cp = ord(conv[0]) if len(conv) == 1 else ord(conv[0]) & (0x3F >> (len(conv) - 1))
            for b in conv[1:]:
                cp = cp * 64 + (ord(b) & 0x3F)
            return self.fmt_raise("ValueError", f"Unknown conversion specifier {conv}" if cp > 32 and cp < 127 else f"Unknown conversion specifier \\x{cp:x}")
        fn = "__pys_repr" if conv == "r" else "__pys_str" if conv == "s" else "__pys_ascii"
        v = self.expr(mk("call", "", line, [mk("name", fn, line, []), self.vnode(v)]), "")
    sp = mk("str", spec, line, [])
    if expand:
        sv = self.str_fields(spec, depth - 1, fa)
        if sv.t == "":
            return sv
        sp = self.vnode(sv)
    return self.format_(v, sp)

def gen_format_arg(self, first: str, idx: int, fa: FmtArgs) -> Val:
    # the argument a field names: positional argument idx, else keyword first; Val("", "") where
    # there is none (CPython's IndexError or KeyError) or format_map() has no positional ones
    line = self.line
    if idx < 0:
        if first in fa.kwn:
            return fa.kwv[fa.kwn.index(first)]
        if fa.kd.t != "":
            return self.expr(mk("index", "", line, [self.vnode(fa.kd), mk("str", first, line, [])]), "")
        return self.fmt_raise("KeyError", first)
    if fa.mapping:
        return self.fmt_raise("ValueError", "Format string contains positional fields")
    if idx < len(fa.pos):
        return fa.pos[idx]
    msg = f"Replacement index {idx} out of range for positional args tuple"
    if fa.rest.t == "":
        return self.fmt_raise("IndexError", msg)
    j = idx - len(fa.pos)
    self.guard(self.num_cmp('<=', Val(self.mload('int', fa.rest.v), "int"), Val(str(j), "int")).v, "IndexError: " + msg)
    return self.expr(mk("index", "", line, [self.vnode(fa.rest), mk("int", str(j), line, [])]), "")

def gen_cat(self, a: Val, b: Val) -> Val:
    if a.v == self.sconst(""):
        return b
    return Val(self.rt("pys_str_add", "ptr", [f"ptr {a.v}", f"ptr {b.v}"]), "str")

def gen_concat(self, parts: list[Val]) -> Val:
    # the strs parts as one str (an f-string's pieces, a % format's, all made already, in
    # order), literals next to each other as one: two pieces are a str.add, three to eight a
    # str.cat, which copies each piece once, and more are joined eight at a time, then those
    # joins (each piece is copied once per level: three times up to 512 pieces). Adding them
    # one at a time would copy every prefix again, quadratic in the pieces (a dataclass's
    # __repr__ has two per field)
    ps: list[Val] = []
    run: list[str] = []  # (the literals since the last other piece; the "" at the end ends a run)
    for v in parts + [Val("", "str")]:
        if v.v.startswith("@s."):
            run.append(self.strvals[int(v.v[3:])])
            continue
        s = "".join(run)
        if s != "":
            ps.append(Val(self.sconst(s), "str"))
        run = []
        if v.v != "":
            ps.append(v)
    if len(ps) == 0:
        return Val(self.sconst(""), "str")
    while len(ps) > 1:
        out: list[Val] = []
        for j in range(0, len(ps), 8):
            g = ps[j : j + 8]
            if len(g) == 1:
                out.append(g[0])
            elif len(g) == 2:
                out.append(Val(self.rt("pys_str_add", "ptr", [f"ptr {g[0].v}", f"ptr {g[1].v}"]), "str"))
            else:
                args = [f"i64 {len(g)}"] + [f"ptr {x.v}" for x in g] + ["ptr null"] * (8 - len(g))
                out.append(Val(self.rt("pys_str_cat", "ptr", args), "str"))
        ps = out
    return ps[0]

def gen_conversion(self, v: Val, flags: str, width: str, prec: str, t: str) -> Val:
    # one %-conversion of v, as a format() spec: '-' left-aligns, '0' pads numbers with
    # zeros after the sign, '+' and ' ' are the sign options, '#' the alternate form
    if t == "s" or t == "r" or t == "a":
        sv = self.to_str(v) if t == "s" else self.repr(v) if t == "r" else Val(self.rt("pys_ascii", "ptr", [f"ptr {self.repr(v).v}"]), "str")
        if width == "" and prec == "":
            return sv
        return self.format_(sv, mk("str", ("<" if "-" in flags else ">") + width + prec, self.line, []))
    if t == "c":
        # one character, of a str or a code point (a precision, flags but '-' change nothing)
        if unopt(v.t) == "str":
            v = self.unwrap(v, "TypeError: %c requires int or char")
        v = v if v.t == "str" else self.as_int(v)
        if v.t != "str" and v.t != "int":
            self.err("%c requires int or char")
        cv = Val(self.rt("pys_pct_char" if v.t == "str" else "pys_pct_chr", "ptr", [f"{lt(v.t)} {v.v}"]), "str")
        return cv if width == "" else self.format_(cv, mk("str", ("<" if "-" in flags else ">") + width, self.line, []))
    spec = "<" if "-" in flags else ""
    spec += "+" if "+" in flags else " " if " " in flags else ""
    spec += "#" if "#" in flags else ""
    spec += "0" if "0" in flags and "-" not in flags else ""
    spec += width
    if t == "d" or t == "i" or t == "u" or t == "x" or t == "X" or t == "o":
        if prec != "":
            self.err(f"%{t} with a precision is not supported")
        if v.t == "float" and (t == "d" or t == "i" or t == "u"):
            v = Val(self.rt("pys_f2i", "i64", [f"double {v.v}"]), "int")  # %d truncates a float, as int() does
        v = self.as_int(v)
        if v.t != "int":
            self.err(f"%{t} format: {'a real number' if t in 'diu' else 'an integer'} is required, not {tname(v.t)}")
        return self.format_(v, mk("str", spec + ("d" if t == "i" or t == "u" else t), self.line, []))
    v = self.as_float(self.as_int(v))
    if v.t != "float":
        self.err(f"must be real number, not {tname(v.t)}")
    return self.format_(v, mk("str", spec + (prec if prec != "" else ".6") + t, self.line, []))

def gen_format_(self, v: Val, spec: Node) -> Val:
    # format(v, spec), as an f-string field computes it; spec is a str or an f-string node, or
    # format()'s argument
    empty = spec.kind == "str" and spec.s == ""
    if v.t in self.classes and self.classes[v.t].tag > 0:
        cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, v.t)]
        if any(["__format__" in c.methods for c in cs]):
            # A subclass's __format__ takes precedence over the object's str fallback,
            # even with an empty spec. Evaluate a computed spec once before dispatch.
            sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
            nonempty = self.num_cmp('!=', Val(self.mload('int', sv.v), "int"), Val('0', "int")).v
            absent = self.label()
            present = self.label()
            done = self.label()
            ph = Ins("phi", "str", "")
            self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, absent, present)
            self.place(absent)
            self.guard(nonempty, "TypeError: unsupported format string passed to NoneType.__format__")
            self.incoming(ph, self.sconst("None"), self.cur)
            self.br(done)
            self.place(present)
            tag = self.mload('int', v.v)
            for i in range(len(cs)):
                ci = cs[i]
                nxt = self.label() if i + 1 < len(cs) else ""
                if nxt != "":
                    arm = self.label()
                    self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(ci.tag), "int")).v, arm, nxt)
                    self.place(arm)
                obj = Val(v.v, ci.name)
                if "__format__" in ci.methods:
                    text = self.coerce(self.call_fn(ci.methods["__format__"], [obj, sv], [], direct=True), "str", "__format__()'s result")
                else:
                    self.guard(nonempty, f"TypeError: unsupported format string passed to {tname(ci.name)}.__format__")
                    text = self.to_str(obj)
                if not self.term:
                    self.incoming(ph, text.v, self.cur)
                    self.br(done)
                if nxt != "":
                    self.place(nxt)
            self.place(done)
            return Val(self.phi(ph), "str")
    if v.t in self.classes and "__format__" in self.classes[v.t].methods:
        sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
        if v.v not in self.nn:
            # None's own __format__ accepts only an empty spec
            self.guard(self.ptr_cmp('==', v, Val('null', 'None')).v, "TypeError: unsupported format string passed to NoneType.__format__")
        return self.call_fn(self.classes[v.t].methods["__format__"], [v, sv], [])
    if empty:
        return self.to_str(v)
    if is_union(unopt(v.t)):
        # Both value and spec run once, before the selected native member formats
        # or raises. A nonempty spec is legal for some members and not for others.
        sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
        return Val(self.rt("pys_format", "ptr", ["i64 " + self.to_slot(v), f"ptr {self.sconst(self.desc(v.t, 'repr'))}", f"ptr {sv.v}"]), "str")
    if v.t == "None":
        if spec.kind == "str":
            self.err("unsupported format string passed to NoneType.__format__")
        # a computed spec runs, as for any value: str(None) when it turns out empty, else TypeError
        sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
        self.guard(self.num_cmp('!=', Val(self.mload('int', sv.v), "int"), Val('0', "int")).v, "TypeError: unsupported format string passed to NoneType.__format__")
        return self.to_str(v)
    if is_opt(v.t):
        # None's __format__ accepts only an empty spec, the value's its own (the runtime checks)
        if spec.kind == "str" and unopt(v.t) != "str" and not is_sopt(v.t):
            self.err(f"unsupported format string passed to {tname(unopt(v.t))}.__format__")
        sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
        return Val(self.rt("pys_format", "ptr", ["i64 " + self.to_slot(v), f"ptr {self.sconst(self.desc(v.t, 'repr'))}", f"ptr {sv.v}"]), "str")
    if v.t in self.classes or v.t == "file" or v.t == "exc":
        if spec.kind == "str":
            self.err(f"unsupported format string passed to {tname(v.t)}.__format__")
        # a computed spec: str(v) when it turns out empty, TypeError otherwise
        sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
        self.guard(self.num_cmp('!=', Val(self.mload('int', sv.v), "int"), Val('0', "int")).v, f"TypeError: unsupported format string passed to {tname(v.t)}.__format__")
        return self.to_str(v)
    if spec.kind == "str" and not self.isnum(v.t) and v.t != "str":
        self.err(f"unsupported format string passed to {tname(v.t)}.__format__")
    sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
    d = self.sconst(self.desc(v.t, "repr"))
    return Val(self.rt("pys_format", "ptr", ["i64 " + self.to_slot(v), f"ptr {d}", f"ptr {sv.v}"]), "str")

def gen_slice_bound(self, x: Node, fold: bool = False) -> str:
    # a slice's start or stop: an int, or the runtime's marker of an omitted bound (-2**63), which
    # an explicit None is too; with fold, True and False are the constants 1 and 0
    if x.kind == "omit":
        return "-9223372036854775808"
    bv = self.expr(x, "int")
    if bv.t == "None":
        return "-9223372036854775808"
    if fold and bv.t == "bool" and (bv.v == "true" or bv.v == "false"):
        return "1" if bv.v == "true" else "0"
    if is_sopt(bv.t):
        return self.optbound(bv)  # (None: omitted)
    # a given bound of -2**63 clamps exactly like -2**63 + 1, which is not the marker
    bd = self.coerce(self.as_int(bv), "int").v  # (as ival)
    if bd.startswith("%"):
        bd = self.select(self.num_cmp('==', Val(bd, "int"), Val('-9223372036854775808', "int")).v, Val("-9223372036854775807", "int"), Val(bd, "int"))
    elif bd == "-9223372036854775808":
        bd = "-9223372036854775807"
    return bd

def gen_slice_step(self, x: Node, fold: bool = False) -> str:
    # a slice's step: an int, 1 where it is omitted or None (the runtime raises CPython's
    # ValueError for 0, and takes -2**63 as -(2**63 - 1)); fold as for slice_bound
    if x.kind == "omit":
        return "1"
    bv = self.expr(x, "int")
    if bv.t == "None":
        return "1"
    if fold and bv.t == "bool" and (bv.v == "true" or bv.v == "false"):
        return "1" if bv.v == "true" else "0"
    if is_sopt(bv.t):
        return self.optint(bv, "1")
    return self.coerce(self.as_int(bv), "int").v

def gen_slice_tuple(self, o: Val, bnd: list[str], step: str) -> Val:
    # o[lo:hi:st] of a fixed-shape tuple or a NamedTuple (a plain tuple of its fields, as in
    # CPython), where o is not None: with constant bounds, the tuple of the items they select,
    # whose types are known; otherwise the empty tuple is empty, and one of a single item type that
    # a runtime-length tuple can hold gives a tuple[T, ...]
    if o.t in self.nts:
        self.notnone(o, "TypeError: 'NoneType' object is not subscriptable")
        o = self.ntup(o, True)
    ts = targs(o.t)
    if all(not x.startswith("%") for x in bnd + [step]):
        if int(step) == 0:
            self.guard("true", "ValueError: slice step cannot be zero")
            return self.tuple_([])
        ix = slice_items(int(bnd[0]), int(bnd[1]), int(step), len(ts))
        if ix == list(range(len(ts))):
            return o  # (all of a tuple is the tuple itself, as in CPython)
        return self.tuple_([self.tget(o, i) for i in ix])
    if len(ts) == 0:
        self.slice_check(step)  # (*args of a call without extra arguments)
        return o
    if any(x != ts[0] for x in ts) or unopt(ts[0]) not in ["int", "float", "bool", "str"]:
        self.err(f"slicing a {typestr(o.t)} by bounds or a step other than integer literals is not supported: the types of the items it selects would not be known (use literals, or a tuple[T, ...] of int, float, bool or str items)")
    vt = self.coerce(o, self.ctype("vtuple", [ts[0]]))
    return Val(self.rt("pys_vtuple_slice", "ptr", [f"ptr {vt.v}", f"i64 {bnd[0]}", f"i64 {bnd[1]}", f"i64 {step}"]), vt.t)

def gen_optbound(self, v: Val) -> str:
    # a slice bound that is an int | None: None is an omitted bound (the runtime's marker -2**63,
    # which a given bound of -2**63 is not: it clamps exactly like -2**63 + 1)
    e0 = self.cur
    l1 = self.label()
    l2 = self.label()
    self.cbr(self.ptr_cmp('!=', v, Val('null', 'None')).v, l1, l2)
    self.place(l1)
    bd = self.as_int(self.deref(v)).v
    bd = self.select(self.num_cmp('==', Val(bd, "int"), Val('-9223372036854775808', "int")).v, Val("-9223372036854775807", "int"), Val(bd, "int"))
    e1 = self.cur
    self.br(l2)
    self.place(l2)
    ph = Ins("phi", "int", "")
    self.incoming(ph, "-9223372036854775808", e0)
    self.incoming(ph, bd, e1)
    return self.phi(ph)

def gen_optint(self, v: Val, none: str) -> str:
    # an int | None or bool | None as an int, None giving the int constant none
    e0 = self.cur
    l1 = self.label()
    l2 = self.label()
    self.cbr(self.ptr_cmp('!=', v, Val('null', 'None')).v, l1, l2)
    self.place(l1)
    n = self.as_int(self.deref(v)).v
    e1 = self.cur
    self.br(l2)
    self.place(l2)
    ph = Ins("phi", "int", "")
    self.incoming(ph, none, e0)
    self.incoming(ph, n, e1)
    return self.phi(ph)

def gen_numkey(self, v: Val, t: str) -> list[str]:
    # number v (an int, float or bool) as the item of a list[t] (t another of them) that equals it,
    # for in, count(), index() and remove(): [its value, whether there is one ("true": always)].
    # No int equals 2.5 or nan, no float 2**53 + 1, no bool 2
    if v.t == "bool":
        return [self.as_float(v).v if t == "float" else self.as_int(v).v, "true"]
    if t == "float":
        fv = self.as_float(v).v
        if not v.v.startswith("%") and -9007199254740992 <= int(v.v) <= 9007199254740992:
            return [fv, "true"]
        inr = self.scalar_cmp('olt', Val(fv, 'float'), Val('0x43E0000000000000', 'float'))  # (2**63, where an int's float may round to)
        back = self.select(inr, Val(self.scalar_cast('fptosi', Val(fv, 'float'), 'int'), "int"), Val("0", "int"))
        exact = self.num_cmp("==", Val(back, "int"), Val(v.v, "int")).v
        return [fv, self.scalar('and', [Val(inr, 'bool'), Val(exact, 'bool')])]
    iv = v.v
    ok = "true"
    if v.t == "float":
        lo = self.scalar_cmp('oge', Val(v.v, 'float'), Val('0xC3E0000000000000', 'float'))
        inr = self.scalar('and', [Val(lo, 'bool'), Val(self.scalar_cmp('olt', Val(v.v, 'float'), Val('0x43E0000000000000', 'float')), 'bool')])
        iv = self.select(inr, Val(self.scalar_cast('fptosi', Val(v.v, 'float'), 'int'), "int"), Val("0", "int"))
        back = self.scalar_cast('sitofp', Val(iv, 'int'), 'float')
        ok = self.scalar('and', [Val(inr, 'bool'), Val(self.scalar_cmp('oeq', Val(back, 'float'), Val(v.v, 'float')), 'bool')])
    if t == "bool":
        b01 = self.int_ucmp('<', Val(iv, "int"), Val('2', "int")).v
        ok = b01 if ok == "true" else self.scalar('and', [Val(ok, 'bool'), Val(b01, 'bool')])
        iv = self.scalar_cast('trunc', Val(iv, 'int'), 'bool')
    return [iv, ok]

def bind_names(n: Node, env: dict[str, Node]) -> Node | None:
    # a copy of expression n whose reads of env's names are env's nodes (a copy of each); None
    # where n has its own scopes or bindings (a lambda, comprehension or := in it)
    if n.kind in ["lambda", "listcomp", "setcomp", "dictcomp", "nestedcomp", "asynccomp", "walrus"]:
        return None
    if n.kind == "name" and n.s in env:
        return clone(env[n.s]) if env[n.s].kind != "val" else env[n.s]
    c = Node(n.kind, n.s, n.line)
    c.chk = n.chk
    c.mchk = n.mchk
    c.depth = n.depth
    for k in n.kids:
        x = bind_names(k, env)
        if x is None:
            return None
        c.kids.append(x)
    return c

def gen_iter_static(self, n: Node) -> str:
    # the type of a variable or of a field of the method's own object (self.k), which reading
    # it cannot change, or ""
    f = self.curfn
    if n.kind == "attr" and n.kids[0].kind == "name" and takes_self(f) and n.kids[0].s == f.params[0] and n.kids[0].s in self.ltype and f.cls in self.classes:
        return self.classes[f.cls].ftypes.get(n.s, "")
    return self.static_type(n) if n.kind == "name" else ""

def gen_unroll(self, g: Node, every: bool = False) -> list[Node] | None:
    # [e for t in xs], or the generator expression, whose items a fixed tuple xs of items of
    # different types (or, in a class that specializes on literals, of constants), or a
    # **kwargs record's items() or values() of different types, supply: an expression e for
    # each item, with t bound to it (xs evaluated once, first); else None
    if g.kind != "listcomp" or len(g.kids) != 3:
        return None
    it = g.kids[2]
    c = self.const_of(it, {}, True) if self.lit_context() else None
    items: list[Node] = []
    fns = self.refl_dc_names(it)
    cns = self.refl_const_names(it) if fns is None and g.kids[1].kind == "name" and refl_reflective(g.kids[0], g.kids[1].s) and self.refl_dir_of(it) is None else None
    if fns is not None:
        items = [mk("dcfield", x, it.line, []) for x in fns]  # (dataclasses.fields(X): reflection.py)
    elif cns is not None and len(cns) > 0:
        if it.kind == "name":
            self.expr(it, "")  # (its read checks it is assigned)
        items = [mk("str", x, it.line, []) for x in cns]  # (constant attribute names: reflection.py)
    elif c is not None and c.kind == "tuple":
        items = c.kids
    elif it.kind == "call" and len(it.kids) == 1 and it.kids[0].kind == "attr" and (it.kids[0].s == "items" or it.kids[0].s == "values") and is_kw(self.iter_static(it.kids[0].kids[0])):
        t = self.iter_static(it.kids[0].kids[0])
        if not every and len([x for x in kw_types(t) if x != kw_types(t)[0]]) == 0:
            return None  # (of one type: the loop's)
        v = self.kw_tuple(self.expr(it.kids[0].kids[0], ""))
        for j in range(len(kw_names(t))):
            x = self.vnode(self.tget(v, j))
            items.append(mk("tuple", "", it.line, [mk("str", kw_names(t)[j], it.line, []), x]) if it.kids[0].s == "items" else x)
    else:
        t = self.iter_static(it)
        if (not every or t != "") and (not is_tuple(t) or (not every and len([x for x in targs(t) if x != targs(t)[0]]) == 0)):
            return None  # (of one type: the loop's, but for tuple(), whose result is fixed)
        v = self.expr(it, "")
        if not is_tuple(v.t):
            return None
        items = [self.vnode(self.tget(v, j)) for j in range(len(targs(v.t)))]
    out: list[Node] = []
    tgt = g.kids[1]
    for x in items:
        env: dict[str, Node] = {}
        if tgt.kind == "name":
            env[tgt.s] = x
        elif tgt.kind == "tuple" and x.kind == "tuple" and len(tgt.kids) == len(x.kids) and len([y for y in tgt.kids if y.kind != "name"]) == 0:
            for j in range(len(tgt.kids)):
                env[tgt.kids[j].s] = x.kids[j]
        else:
            self.err("a comprehension over a tuple of items of different types needs a name, or names for each pair of items(), as its target")
        e = bind_names(g.kids[0], env)
        if e is None:
            self.err("a comprehension over a tuple of items of different types cannot hold a lambda, comprehension or := expression")
        out.append(e)
    return out

def gen_dict_merge(self, n: Node, want: str) -> Val:
    # {**a, "k": v, **b}, in CPython's order: of **kwargs records and str keys, the record of
    # the merged keyword arguments, each name where it first appears with the last value given;
    # of dicts of one type, a new dict that each ** updates once its operand is evaluated
    names: list[str] = []
    vals: list[Val] = []
    pairs: list[Val] = []  # (the keys and values before the first **, and their nodes)
    keys: list[Node] = []
    r = Val("", "")  # (the dict, once a ** of a dict decides it)
    kw = False
    i = 0
    while i < len(n.kids):
        x = n.kids[i]
        if x.kind != "dstar":
            if r.t != "":
                kv = targs(r.t)
                key = self.store_key(self.expr(x, kv[0]), kv[0])
                self.rt("pys_dict_set", "void", [f"ptr {r.v}", "i64 " + self.to_slot(key), "i64 " + self.to_slot(self.coerce(self.expr(n.kids[i + 1], kv[1]), kv[1]))], self.key_fx(kv[0]))
            elif kw and x.kind != "str":
                self.err("a key of a dict display with ** of a **kwargs record must be a str literal")
            elif kw:
                names.append(x.s)
                vals.append(self.expr(n.kids[i + 1], ""))
            else:
                keys.append(x)
                pairs.append(self.expr(x, ""))
                pairs.append(self.expr(n.kids[i + 1], ""))
            i += 2
            continue
        v = self.expr(x.kids[0], want if is_dict(want) and r.t == "" else r.t)
        self.line = x.line
        if is_kw(v.t) and r.t == "" and len([k for k in keys if k.kind != "str"]) == 0:
            if not kw:
                kw = True
                for j in range(len(keys)):
                    names.append(keys[j].s)
                    vals.append(pairs[2 * j + 1])
            for j in range(len(kw_names(v.t))):
                names.append(kw_names(v.t)[j])
                vals.append(self.tget(self.kw_tuple(v), j))
        elif not kw and is_dict(unopt(v.t)) and (r.t == "" or unopt(v.t) == r.t):
            v = self.unwrap(v, "TypeError: 'NoneType' object is not a mapping")
            if r.t == "":
                kv = targs(v.t)
                r = Val(self.rt("pys_dict_new_atomic" if atomic_dict(v.t) else "pys_dict_new", "ptr", [f"i64 {self.key_kind(kv[0])}", "i64 0"]), v.t)
                for j in range(0, len(pairs), 2):
                    self.rt("pys_dict_set", "void", [f"ptr {r.v}", "i64 " + self.to_slot(self.store_key(pairs[j], kv[0])), "i64 " + self.to_slot(self.coerce(pairs[j + 1], kv[1]))], self.key_fx(kv[0]))
            self.rt("pys_dict_update", "void", [f"ptr {r.v}", f"ptr {v.v}"], self.key_fx(targs(r.t)[0]))
        else:
            self.err(f"** of a {typestr(v.t)} in a dict display is not supported: of a function's **kwargs (with str keys), or of dicts of one type, it is")
        i += 1
    if r.t != "":
        return r
    # a name given again keeps its first place and takes its last value, as in a dict
    out: list[str] = []
    outv: list[Val] = []
    for j in range(len(names)):
        if names[j] in out:
            outv[out.index(names[j])] = vals[j]
        else:
            out.append(names[j])
            outv.append(vals[j])
    return self.kw_record(out, outv)

def gen_tuple_(self, vals: list[Val]) -> Val:
    t = self.ctype("tuple", [v.t for v in vals])
    p = self.alloc_fixed(t).v
    for i in range(len(vals)):
        s = self.to_slot(vals[i])
        self.tstore(Val(p, t), i, s)
    return Val(p, t)

def gen_stack_tuple(self, vals: list[Val]) -> Val:
    # tuple_, in this function's frame (a slot of its items, lowered to an array): the *args of
    # a call of a function that copies them to the heap before it could keep them (stack_ok)
    t = self.ctype("tuple", [v.t for v in vals])
    self.n += 1
    i = Ins("slot", t, "")
    i.k = 2
    i.r = [self.n]
    self.fn.slots.append(i)
    p = f"%stk.{self.n}"
    for j in range(len(vals)):
        s = self.to_slot(vals[j])
        self.tstore(Val(p, t), j, s)
    return Val(p, t)

def gen_stack_ok(self, f: FnInfo) -> bool:
    # whether a call of f may make f's *args tuple in its own frame (stack_tuple), where it is
    # gone once f returns: f copies the tuple to the heap before any statement that could
    # keep it (keep_stack), and it keeps it nowhere else (stack_kept). A dict probe with the
    # key, the most a cache's hit does with its arguments (lib/functools), then allocates
    # nothing
    if f.stk < 0:
        f.stk = 0
        if f.vararg >= 0 and f.node.kind == "def" and not f.export and not f.pyexport:
            names: dict[str, bool] = {f.params[f.vararg]: True}
            body = f.node.kids[2].kids
            added = True
            while added:
                added = False
                for st in body:
                    if stack_aliases(st, names):
                        added = True
            ns = list(names)
            if len([st for st in body if stack_kept(st, ns)]) == 0:
                f.stk = 1
                f.stknames = names
    return f.stk == 1

def gen_keep_stack(self, n: Node) -> None:
    # before statement n of a function whose *args tuple may be in its caller's frame
    # (stack_ok): each local that may hold the tuple and that n uses other than to look it up
    # or read its items (stack_uses) holds its heap copy from here on, which the first such
    # statement of a call makes. A tuple that is not in a frame (runtime.c's pys_on_stack), as
    # a call through a Callable passes it, is kept as it is
    ns = self.curfn.stknames
    k = n.kind
    if k == "assign" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[1].kind == "name" and n.kids[1].s in ns:
        return  # (y = args: y may hold the tuple too, see stack_aliases)
    out: dict[str, bool] = {}
    if (k == "if" or k == "assert") and n.kids[0].kind == "name" and n.kids[0].s in ns:
        for c in n.kids[1:] if k == "assert" else []:
            self.stack_uses(c, out)  # (if args: whether it has items)
    elif k == "if":
        self.stack_uses(n.kids[0], out)
    elif k == "match":
        for c in n.kids:
            if c.kind != "block":
                self.stack_uses(c, out)  # (its subject, and its cases' guards)
    elif k == "for":
        self.stack_target(n.kids[0], out)
        if n.kids[1].kind != "name" or n.kids[1].s not in ns:
            self.stack_uses(n.kids[1], out)  # (for x in args reads its items)
    elif k == "with":
        for w in n.kids[:-1]:
            self.stack_uses(w.kids[0], out)
            if len(w.kids) > 1:
                self.stack_target(w.kids[1], out)
    elif k == "assign" or k == "annassign" or k == "augassign":
        ts = n.kids[:-1] if k == "assign" else [n.kids[0]]
        for x in ts:
            self.stack_target(x, out)
        if k != "annassign" or len(n.kids) == 3:
            self.stack_uses(n.kids[-1], out)
    elif k == "expr" or k == "return" or k == "raise" or k == "assert" or k == "del":
        for c in n.kids:
            self.stack_uses(c, out)
    for nm in out:
        t = unopt(self.ltype.get(nm, ""))
        if nm not in self.lreg or nm in self.compvars or not is_tuple(t):
            continue  # (not assigned yet here: it holds nothing; or a comprehension's own)
        if ".stk" not in self.lreg:
            self.alloca(t, ".stk")  # (the heap copy, once made)
        hs = self.lreg[".stk"]
        v = self.mload('%ptr', self.lreg[nm])
        h = self.mload('%ptr', hs)
        lchk = self.label()
        lcopy = self.label()
        lnew = self.label()
        lold = self.label()
        ldone = self.label()
        self.cbr(self.scalar_cmp('eq', Val(v, '%ptr'), Val(h, '%ptr')), ldone, lchk)  # (it holds the copy: a statement before kept it)
        self.place(lchk)
        self.cbr(self.num_cmp('!=', Val(self.rt('pys_on_stack', 'i64', [f'ptr {v}']), "int"), Val('0', "int")).v, lcopy, ldone)
        self.place(lcopy)
        self.cbr(self.scalar_cmp('eq', Val(h, '%ptr'), Val('null', '%ptr')), lnew, lold)
        self.place(lold)
        self.mstore('%ptr', h, self.lreg[nm])  # (the copy another local's statement made)
        self.br(ldone)
        self.place(lnew)
        cp = self.alloc_fixed(t).v
        for j in range(len(targs(t))):
            wd = self.mload('int', self.maddr('int', f'{v}', f'{j}'))
            self.mstore('int', wd, self.maddr('int', f'{cp}', f'{j}'))
        self.mstore('%ptr', cp, hs)
        self.mstore('%ptr', cp, self.lreg[nm])
        self.br(ldone)
        self.place(ldone)

def gen_stack_target(self, t: Node, out: dict[str, bool]) -> None:
    # stack_uses of an assignment's target: d[x] = v stores the key x
    if t.kind == "index" and len(t.kids) == 2 and t.kids[1].kind == "name" and t.kids[1].s in self.curfn.stknames:
        out[t.kids[1].s] = True
        self.stack_uses(t.kids[0], out)
    elif t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
        for c in t.kids:
            self.stack_target(c, out)
    elif t.kind == "attr":
        self.stack_uses(t.kids[0], out)
    elif t.kind != "name":
        self.stack_uses(t, out)

def gen_stack_uses(self, n: Node, out: dict[str, bool]) -> None:
    # the names of curfn.stknames that expression n uses other than as a key it looks up (x in
    # d, x in xs, d[x], d.get(x)) or as a tuple whose items it reads (f(*x), len(x), x[i]): the
    # uses that could keep what the name holds
    ns = self.curfn.stknames
    k = n.kind
    if k == "name":
        if n.s in ns:
            out[n.s] = True
        return
    if len(n.kids) > 0:
        a = n.kids[0]
        if k == "cmp" and len(n.kids) == 2 and (n.s == "in" or n.s == "not in") and a.kind == "name" and a.s in ns:
            t = unopt(self.probe_type(n.kids[1]))
            if is_dict(t) or is_set(t) or is_list(t) or is_tuple(t):
                self.stack_uses(n.kids[1], out)
                return
        if k == "cmp" and len(n.kids) == 2 and (n.s == "in" or n.s == "not in") and n.kids[1].kind == "name" and n.kids[1].s in ns:
            self.stack_uses(a, out)  # (x in args: its items)
            return
        if k == "unary" and n.s == "not" and a.kind == "name" and a.s in ns:
            return
        if k == "index" and len(n.kids) == 2 and n.kids[1].kind == "name" and n.kids[1].s in ns and is_dict(unopt(self.probe_type(a))):
            self.stack_uses(a, out)
            return
        if k == "index" and len(n.kids) == 2 and a.kind == "name" and a.s in ns:
            self.stack_uses(n.kids[1], out)
            return
        if k == "call" and len(n.kids) >= 2 and a.kind == "attr" and a.s == "get" and n.kids[1].kind == "name" and n.kids[1].s in ns and is_dict(unopt(self.probe_type(a.kids[0]))):
            self.stack_uses(a.kids[0], out)
            for c in n.kids[2:]:
                self.stack_uses(c, out)
            return
        if k == "call" and len(n.kids) == 2 and a.kind == "name" and a.s == "len" and not self.bound("len") and n.kids[1].kind == "name" and n.kids[1].s in ns:
            return
        if k == "starred" and a.kind == "name" and a.s in ns:
            return
    for c in n.kids:
        self.stack_uses(c, out)

def gen_lookup_key(self, n: Node) -> bool:
    # whether n is a tuple display that a lookup takes as its key, which it keeps nowhere: it
    # can be made in the frame (stack_tuple) instead of on the heap
    return n.kind == "tuple" and len(n.kids) > 0 and len([x for x in n.kids if x.kind == "starred"]) == 0

def gen_probe_type(self, n: Node) -> str:
    # the static type of n where it is a variable (static_type, or a global that may not be
    # assigned yet, whose read then raises first) or a field of one (self.d), or ""
    if n.kind == "attr" and len(n.kids) == 1:
        o = unopt(self.probe_type(n.kids[0]))
        return self.classes[o].ftypes.get(n.s, "") if o in self.classes else ""
    t = self.static_type(n)
    if t == "" and n.kind == "name" and n.s not in self.ltype and n.s not in self.compvars and not self.unbound_local(n.s):
        return self.gtypes.get(n.s, "")
    return t

def gen_tget(self, v: Val, i: int) -> Val:
    item = Ins("tuple.load", "%slot", targs(v.t)[i])
    item.k = i
    item.a = [v]
    self.put(item, 2)
    return self.from_slot(f"%t{item.r[1]}", item.s)

def gen_tstore(self, v: Val, index: int, slot: str) -> None:
    item = Ins("tuple.store", "", targs(v.t)[index])
    item.k = index
    item.a = [v, Val(slot, "%slot")]
    self.put(item, 1)

def gen_index(self, n: Node, want: str = "") -> Val:
    c = n.kids[0]
    if c.kind == "name" and c.s in self.galias and c.s not in self.ltype:
        self.err(GALIASSUB.replace("NAME", short(c.s)))
    f = c.kids[0] if c.kind == "call" else c
    if c.kind == "call" and n.kids[1].kind == "int" and n.kids[1].s == "0" and f.kind == "attr" and f.s == "split" and len(c.kids) <= 3 and plain_args(c.kids[1:]) and self.dotted(f) == "" and (f.kids[0].kind != "name" or self.static_type(f.kids[0]) == "str") and not is_super(f.kids[0]):
        # s.split()[0], s.split(sep)[0], s.split(sep, n)[0]: the first part alone, made without
        # the list or the other parts (pys_str_split_first). The receiver is evaluated as call()
        # evaluates it, and what is not a str's split is indexed as it was
        self.line = c.line
        o = self.expr(f.kids[0], self.default_want(f.kids[0], f.s, c.kids[1:], ""))
        if o.t == "str":
            return self.bmethod(o, f.s, c.kids[1:], True)
        r = self.method(o, f.s, c.kids[1:])
        self.close_temp(f.kids[0], o)
        return self.subscript(n, r)
    return self.subscript(n, self.expr(c, ""), want)

def gen_subscript(self, n: Node, o: Val, want: str = "") -> Val:
    # o[i], where o is the value of n.kids[0] and n.kids[1] the index
    t = unopt(o.t)
    sub = "TypeError: 'NoneType' object is not subscriptable"  # (once the index is evaluated)
    if t in ["fn[b:list]", "fn[b:dict]", "fn[b:tuple]", "fn[b:set]", "fn[b:frozenset]"]:
        self.err(f"{t[5:-1]}[...] as a value is not supported (only annotations may name a type: a type alias is a module-level name = {t[5:-1]}[...] that nothing else binds)")
    if is_kw(t) and n.kids[1].kind == "str":
        # kwargs["name"]: the keyword argument name, or CPython's KeyError where the call passed none
        names = kw_names(t)
        if n.kids[1].s in names:
            return self.tget(self.kw_tuple(o), names.index(n.kids[1].s))
        self.raise_("KeyError", self.repr(Val(self.sconst(n.kids[1].s), "str")).v, self.sconst("KeyError"))
        self.place(self.label())  # (not reached)
        return Val("null", "None")
    if is_kw(t) and (len(kw_types(t)) == 0 or len([x for x in kw_types(t) if x != kw_types(t)[0]]) > 0):
        # kwargs[k] of values of different types (or none): the value of the name k is, of
        # their union, or CPython's KeyError
        k = self.expr(n.kids[1], "str")
        o = self.unwrap(o, sub)
        if k.t != "str":
            self.err(f"a {typestr(k.t)} key of a {typestr(t)} is not supported: its keys are str")
        return self.pick(self.kw_tuple(o), [self.cmp2("==", k, Val(self.sconst(x), "str")) for x in kw_names(t)], "KeyError", self.repr(k).v, f"indexing a {typestr(t)} with a variable key", want)
    if is_kw(t):
        o = self.kw_dict(o)  # (another key: looked up in the dict CPython makes)
        t = o.t
    if is_vtuple(t):
        i = self.ival(n.kids[1], "TypeError: tuple indices must be integers or slices, not NoneType")
        o = self.unwrap(o, sub)
        return self.from_slot(self.rt("pys_vtuple_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), targs(t)[0])
    if t == "bytes":
        i = self.ival(n.kids[1], "TypeError: byte indices must be integers or slices, not NoneType")
        o = self.unwrap(o, sub)
        return Val(self.rt("pys_bytes_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), "int")
    if is_list(t) or t == "str":
        i = self.ival(n.kids[1], "TypeError: list indices must be integers or slices, not NoneType" if is_list(t) else "TypeError: string indices must be integers, not 'NoneType'")
        o = self.unwrap(o, sub)
        if t == "str":
            return Val(self.rt("pys_str_get", "ptr", [f"ptr {o.v}", f"i64 {i.v}"]), "str")
        return self.list_read(o, i)
    if is_dict(t):
        kv = targs(t)
        if self.lookup_key(n.kids[1]):
            self.stkkey = n.kids[1]  # (memo[(i, j)])
        kval = self.expr(n.kids[1], kv[0])
        self.stkkey = self.nokey
        kx = self.dkey(kval, kv[0])
        o = self.unwrap(o, sub)
        if bool_for_int(kval.t, kv[0]):
            key = self.to_slot(kx)
            return self.from_slot(self.rt("pys_dict_val", "i64", [f"ptr {o.v}", f"i64 {self.bool_find(o.v, kval, key)}"]), kv[1])
        return self.from_slot(self.nonekey(kx, "", "pys_dict_getitem", [f"ptr {o.v}", f"i64 {self.to_slot(kx)}"], self.key_fx(kv[0])), kv[1])
    if is_tuple(t) or t in self.nts:
        ts = targs(t) if is_tuple(t) else self.classes[t].fields  # (a NamedTuple's fields)
        c = self.const_of(n.kids[1], {}, True) if self.lit_context() else None
        i = self.expr(c if c is not None and c.kind in ["int", "unary", "True", "False"] else n.kids[1], "int")
        if i.t == "bool" and (i.v == "true" or i.v == "false"):
            i = Val("1" if i.v == "true" else "0", "int")
        if is_tuple(t) and (i.t == "int" or i.t == "bool") and i.v.startswith("%"):
            # t[i] of a variable i: the item there, of the items' type or their union, or
            # CPython's IndexError past either end
            o = self.unwrap(o, sub)
            at = self.as_int(i)
            at = Val(self.select(self.num_cmp('<', at, Val('0', "int")).v, Val(self.scalar('add', [at, Val(str(len(ts)), "int")]), "int"), at), "int")
            msg = Val(self.sconst("tuple index out of range"), "str").v
            return self.pick(o, [self.num_cmp('==', at, Val(str(x), "int")) for x in range(len(ts))], "IndexError", msg, f"indexing a {typestr(t)} with a variable index", want)
        if i.t != "int" or i.v.startswith("%"):
            self.err("tuple index must be an integer constant")
        j = int(i.v)
        if j < 0:
            j += len(ts)
        if j < 0 or j >= len(ts):
            # (rather than CPython's IndexError where it runs: the item would have no type)
            self.err(f"tuple index out of range: {i.v} for a tuple of {len(ts)} item{'s' if len(ts) != 1 else ''} (a constant index is checked at compile time)")
        if t in self.nts:
            self.notnone(o, sub)
            return self.getfield(o, self.field(o, ts[j]), ts[j])
        return self.tget(self.unwrap(o, sub), j)
    if t in self.classes:
        # o[k]: o.__getitem__(k), once k is evaluated
        ik = self.expr(n.kids[1], self.argtype(t, "__getitem__", 1, f"'{tname(t)}' object is not subscriptable"))
        self.notnone(o, sub)
        return self.protocol(o, "__getitem__", [ik])
    self.err(f"'{tname(t) if is_gen(t) else t}' object is not subscriptable")
    return o

def gen_pick(self, o: Val, tests: list[Val], exc: str, msg: str, what: str, want: str, dflt: Val | None = None) -> Val:
    # item k of tuple o where tests[k] (computed already) holds, the first that does, as the
    # type of o's items (and dflt) or their union; where none does, dflt, or else raise
    # exc(msg). Of no items, the raise, and a value of the type the context expects (which no
    # return statement then sees)
    ts = targs(o.t) + ([dflt.t] if dflt is not None else [])
    if len(ts) == 0:
        self.raise_(exc, msg)
        self.place(self.label())  # (not reached)
        t = want if want != "" and "?" not in want else "None"
        return Val("0" if t == "int" else fbits("0.0") if t == "float" else "false" if t == "bool" else "null", t)
    rt = ts[0] if len([x for x in ts if x != ts[0]]) == 0 else self.union_type(ts)
    if rt.startswith("!"):
        self.err(f"{what} is not supported: {rt[1:]}")
    ph = Ins("phi", rt, "")
    end = self.label()
    for k in range(len(tests)):
        arm = self.label()
        nxt = self.label()
        self.cbr(tests[k].v, arm, nxt)
        self.place(arm)
        v = self.coerce(self.tget(o, k), rt)
        self.incoming(ph, v.v, self.cur)
        self.br(end)
        self.place(nxt)
    if dflt is not None:
        v = self.coerce(dflt, rt)
        self.incoming(ph, v.v, self.cur)
        self.br(end)
    else:
        self.raise_(exc, msg)
    self.place(end)
    return Val(self.phi(ph), rt)

def gen_list_read(self, o: Val, i: Val) -> Val:
    # Both operands have run, and o is not None. Check the current length: unsigned
    # comparison also sends every negative index to the runtime's normalization and errors.
    # No call or allocation separates this check from the existing inline list.load.
    if o.t != "list[int]" or "listfast" not in self.opts:
        return self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), elem(o.t))
    fast = self.label()
    slow = self.label()
    done = self.label()
    length = Ins("list.len", "int", "")
    length.a = [o]
    self.put(length, 1)
    self.cbr(self.int_ucmp('<', Val(i.v, "int"), Val(f'%t{length.r[0]}', "int")).v, fast, slow)
    ph = Ins("phi", "int", "")
    self.place(fast)
    read = Ins("list.load", "int", "")
    read.a = [o, i]
    self.put(read, 4)
    self.incoming(ph, f"%t{read.r[0]}", self.cur)
    self.br(done)
    self.place(slow)
    v = self.rt("pys_list_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"])
    self.incoming(ph, v, self.cur)
    self.br(done)
    self.place(done)
    return Val(self.phi(ph), "int")

def gen_argtype(self, t: str, m: str, j: int, missing: str) -> str:
    # the type of parameter j of the special method m of class t, which an operator calls (its
    # argument is evaluated for that type); missing: the error where t does not define m
    ms = self.classes[t].methods
    if m not in ms:
        self.err(missing)
    if ms[m].bad != "":
        self.err(ms[m].bad)  # (an imported module's method that cannot be compiled)
    return ms[m].ptypes[j] if j < len(ms[m].ptypes) else ""

def gen_protocol(self, o: Val, m: str, args: list[Val]) -> Val:
    # the call of the special method m of o's class that an operator makes (o[k] calls
    # __getitem__), with the arguments it has evaluated; o is known not to be None
    f = self.classes[o.t].methods[m]
    if f.npos < len(args) + 1:
        self.err(f"{m} must take {len(args)} argument{'s' if len(args) != 1 else ''} besides self")
    return self.call_fn(f, [o] + args, [])

def gen_obj_iter(self, v: Val, none: str, missing: str, name: str = "__iter__") -> Val:
    # what iterating over object v gives at once (list(), sorted(), str.join(), ...): the list
    # its __iter__ (or __reversed__) returns the iterator of (see iter_ret), or a new list of the
    # items its iterator object's __next__ gives (obj_iterator)
    it = self.obj_iterator(v, none, missing, name)
    return it if is_list(it.t) or is_gen(it.t) else self.drain(it)

def gen_obj_iterator(self, v: Val, none: str, missing: str, name: str = "__iter__") -> Val:
    # iter(v) of object v: the list its __iter__ returns the iterator of (see iter_ret), or the
    # iterator object __iter__ returns, an object of a class with __next__ (is_iterator). With
    # name "__reversed__", reversed(v): only the list its __reversed__ returns the iterator of. v
    # None raises none ("Kind: text"); missing is the error where v's class does not define
    # __iter__ (CPython iterates by __getitem__ then, which is not supported)
    ms = self.classes[v.t].methods
    if name not in ms and "__getitem__" in ms:
        self.err(f"iterating over {short(v.t)} by its __getitem__ is not supported (CPython calls __getitem__(0), __getitem__(1), ... until IndexError): define __iter__")
    if name not in ms:
        self.err(missing)
    f = ms[name]
    if f.bad != "":
        self.err(f.bad)  # (an imported module's generator __iter__: its own error, not its type's)
    if f.gen:
        # (an __iter__ that yields: the generator its call makes)
        self.notnone(v, none)
        return self.protocol(v, name, [])
    if not f.iters and name == "__reversed__":
        # (CPython iterates over what it returns, which need not be an iterator)
        self.err(f"{short(v.t)}.__reversed__ returning {typestr(f.ret)} is not supported: return iter(xs) of a list xs of the items (-> Iterator[T])")
    self.notnone(v, none)
    it = self.protocol(v, name, [])
    if f.iters:
        return it
    if not self.is_iterator(it.t):
        self.err(f"iter() returned non-iterator of type '{tname(it.t)}': {short(v.t)}.__iter__ must return an iterator, an object whose class defines __next__, or iter(xs) of a list xs (-> Iterator[T])")
    self.notnone(it, "TypeError: iter() returned non-iterator of type 'NoneType'")
    self.nn[it.v] = True
    return it

def gen_is_iterator(self, t: str) -> bool:
    # is t an iterator: a class (not a NamedTuple) whose __next__ gives the items
    return t in self.classes and t not in self.nts and "__next__" in self.classes[t].methods

def gen_next_type(self, t: str) -> str:
    # the type of the items of an object of class t: what its __next__ returns, or else its
    # __iter__'s iterator's (the list's items, see iter_ret); "" where that is not known
    seen: list[str] = []
    while t not in seen:
        seen.append(t)
        ms = self.classes[t].methods if t in self.classes and t not in self.nts else {}
        m = "__next__" if "__next__" in ms else "__iter__"
        if m not in ms or ms[m].bad != "":
            return ""
        r = self.instance(ms[m], [t], []).ret if ms[m].generic and ms[m].ret == "" else ms[m].ret
        if m == "__next__" or r == "":
            return r
        if ms[m].iters:
            return elem(r)
        t = r
    return ""  # a cycle of non-iterator __iter__ returns cannot supply an item type

def gen_iter_ret(self, e: Node) -> Val:
    # return iter(x) in an __iter__ that returns an Iterator[T]: the list[T] that iterator steps
    # through, as a for loop over x would: x for a list, a new list of the items of a tuple or
    # str, the list of an object's own __iter__; reversed(x), as iter(list(reversed(x))): a new
    # list of its items; an iterator other than these is not supported
    if e.kind == "call" and e.kids[0].kind == "name" and e.kids[0].s == "reversed" and not self.bound("reversed") and not self.bound("list") and len(e.kids) == 2 and e.kids[1].kind != "kw":
        e = mk("call", "", e.line, [mk("name", "iter", e.line, []), mk("call", "", e.line, [mk("name", "list", e.line, []), e])])
    if e.kind != "call" or e.kids[0].kind != "name" or e.kids[0].s != "iter" or self.bound("iter") or len(e.kids) != 2 or e.kids[1].kind == "kw":
        self.err(f"{short(self.curfn.cls)}.{self.curfn.name} must return iter(xs) or reversed(xs) here, where xs is a list, a tuple, a str or an object with __iter__")
    v = self.iterable(self.consume(e.kids[1], self.ret))
    if self.is_iterator(v.t):
        # (the iterator object of another object's __iter__, whose items its __next__ gives as
        # the loop asks for them: not a list of them)
        self.err(f"iter() of an object whose __iter__ returns a {short(v.t)} in {short(self.curfn.cls)}.__iter__ -> Iterator[T] is not supported: leave out the return annotation, or annotate -> {short(v.t)}")
    if (is_tuple(v.t) and v.t != "tuple[]") or v.t == RANGEC:
        v = self.as_list(v, "iter")  # (of the items, which share one type; a range's numbers)
    last = self.blk.code[-1] if len(self.blk.code) > 0 else Ins("", "", "")
    if last.op == "rt" and (last.s == "dict.keys" or last.s == "dict.values" or last.s == "dict.items") and v.v == f"%t{last.r[0]}":
        # (keys() is a list here; CPython's view iterator raises if the dict changes size)
        self.err(f"iter() of a dict's {last.s[5:]}() in {self.curfn.name} is not supported: its iterator raises if the dict changes size; return iter(list(...)) of a copy")
    if v.t == "str":
        v = Val(self.rt("pys_str_list", "ptr", [f"ptr {v.v}"]), "list[str]")
    if v.t == "bytes":
        v = Val(self.rt("pys_bytes_list", "ptr", [f"ptr {v.v}"]), "list[int]")
    if not is_list(v.t):
        self.err(f"iter() of {typestr(v.t)} in {self.curfn.name} is not supported: return iter(xs) of a list xs of the items")
    return v

def gen_listcomp(self, n: Node, want: str, mode: str = "", into: str = "", arg: IterArg | None = None, kind: str = "list", resultsoft: bool = False) -> Val:
    # [e for t in it if c] runs as a loop appending to a fresh list (or to list into, of type
    # want, as xs.extend(e for ...) does item by item); t is scoped to it. mode any/all:
    # any(e for ...) / all(...) instead, stopping at the deciding element. kind "set": {e for
    # t in it if c}, adding to a fresh set (or to set into, as s.update(e for ...) does); kind
    # "discard": discarding each from set into, as s.difference_update(e for ...) does; kind
    # "dict": {k: v for ...} (e is the tuple of k and v), setting d[k] = v in a fresh dict.
    # Later for and if clauses are loops and tests nested in the first loop, in their order
    h = Ins("", "", "")
    if mode == "any" or mode == "all":
        res = self.alloca("bool", "")
        self.mstore('bool', 'false' if mode == 'any' else 'true', res)
    elif mode != "":
        res = ""  # (a reduction: mode is # and the key of its Reduce, which holds what it keeps)
    elif into != "":
        res = into
    else:
        h = self.hole(kind)
        res = f"%t{h.r[0]}"
    names: list[str] = []
    comp_names(n, names)
    if comp_unbound(n, names) != "":
        self.err(comp_unbound(n, names))
    saved: list[str] = []
    held: list[int] = []
    for nm in names:
        saved.append(self.ltype.get(nm, "") + " " + self.lreg.get(nm, ""))
        held.append(self.compvars.get(nm, 0))
    app = mk("lcappend" if mode == "" else "reduce" if mode.startswith("#") else "anyall", mode[1:] if mode.startswith("#") else mode if mode != "" or kind == "list" else kind, n.line, [n.kids[0]])
    body = [app]
    for j in range(len(n.kids) - 1, 2, -1):
        # (a later for clause hides its own targets' names, but those it binds into an earlier
        # clause's variable; one that any() or all() decided in leaves the loop around it too:
        # see "compfor")
        c = n.kids[j]
        inner = mk("block", "", n.line, body)
        if c.kind == "compfor":
            shared: list[str] = []
            comp_shared(n, j, shared)
            body = [mk("compfor", mode if mode == "any" or mode == "all" else "", n.line, [c.kids[0], c.kids[1], inner, mk("names", " ".join(shared), n.line, [])])]
        else:
            body = [mk("if", "", n.line, [c.kids[0] if c.kind == "compif" else c, inner, mk("block", "", n.line, [])])]
    self.lcs.append(res)
    self.lct.append(elem(want) if is_list(want) and kind == "list" and "?" not in want else want if is_dict(want) and kind == "dict" and "?" not in want else selem(want) if is_set(want) and kind != "list" and kind != "dict" and "?" not in want else "")
    self.lcsoft.append(resultsoft)
    pre = self.narrowed  # (its variables are its own: the loop binds no outer local, but by :=)
    share = self.compshare
    self.compshare = {}
    own: list[str] = []
    names_in(n.kids[1], own)
    # (a comprehension the program writes, not one the compiler makes of a call (made_var),
    # iterates iter() of its iterable's iterator, as CPython 3.13's does: see for_)
    written = not n.kids[1].made
    self.for_(mk("for", "comp" if written else "", n.line, [n.kids[1], n.kids[2], mk("block", "", n.line, body)]), own, arg)
    self.narrowed = self.forget_walrus(pre, [n])
    self.compshare = share
    et = self.lct.pop()
    self.lcs.pop()
    self.lcsoft.pop()
    for i in range(len(names)):
        nm = names[i]
        sp = saved[i].find(" ")
        if sp == 0:
            if nm in self.ltype:
                del self.ltype[nm]
        else:
            self.ltype[nm] = saved[i][:sp]
            self.lreg[nm] = saved[i][sp + 1 :]
        if held[i] > 0:
            self.compvars[nm] = held[i]
        elif nm in self.compvars:
            del self.compvars[nm]
    if mode == "any" or mode == "all":
        return Val(self.mload('bool', res), "bool")
    if mode != "":
        return Val("", "")
    if et == "":
        self.err("cannot infer the element type of this comprehension")
    t = et if kind == "dict" else self.ctype("list" if kind == "list" else "set", [et])
    if into == "":
        self.holes[h.k] = t
        if kind != "list":
            self.key_kind(targs(et)[0] if kind == "dict" else et)  # (a tuple key's descriptor, a string constant, which lowering prints)
    return Val(res, t)

def gen_ifexp(self, n: Node, want: str, resultsoft: bool = False) -> Val:
    st = self.static(n.kids[0])
    if st >= 0:
        self.static_reads(n.kids[0])
        return self.expr(n.kids[1] if st == 1 else n.kids[2], want, resultsoft=resultsoft)
    c = self.cond(n.kids[0])
    l1 = self.label()
    l2 = self.label()
    l3 = self.label()
    self.cbr(c, l1, l2)
    self.place(l1)
    pre = self.narrow_by(n.kids[0], True)
    self.branch += 1  # (neither arm surely rebinds a template parameter whose argument is None)
    a = self.expr(n.kids[1], want, resultsoft=resultsoft)
    if is_vtuple(unopt(want)):
        a = self.coerce(a, want)  # (construct the requested representation in its arm)
    if (is_fn(a.t) and is_callable(unopt(want))) or is_union(unopt(want)):
        a = self.coerce(a, want)  # (a function where a Callable is expected: made one in its arm)
    # an arm that ends the program (sys.exit()) has no edge to the join, and no value
    e1 = "" if self.term else self.cur
    self.br(l3)
    self.place(l2)
    self.narrowed = pre
    self.narrow_by(n.kids[0], False)
    wb = want if want != "" else a.t
    if want == "" and n.kids[2].kind == "ifexp" and self.optional(a.t) != "":
        wb = self.optional(a.t)  # (x if c else y if d else None: T | None)
    b = self.expr(n.kids[2], wb, resultsoft=resultsoft)
    self.branch -= 1
    if is_vtuple(unopt(want)):
        b = self.coerce(b, want)
    if (is_fn(b.t) and is_callable(unopt(want))) or is_union(unopt(want)):
        b = self.coerce(b, want)
    self.narrowed = self.forget_walrus(pre, n.kids[1:])
    e2 = "" if self.term else self.cur
    t = b.t if e1 == "" or (a.t == "None" and e2 != "") else a.t
    if e1 != "" and e2 != "" and a.t != b.t and (want == "" or is_opt(want)) and is_opt(self.join(a.t, b.t)):
        t = self.join(a.t, b.t)  # x if c else None: T | None
    ph = Ins("phi", t, "")
    if e1 != "":
        self.incoming(ph, self.convert_at(a, t, e1).v, e1)  # (an int as an int | None: its box, made there)
    if e2 != "":
        self.incoming(ph, self.coerce(b, t).v, e2)
    self.br(l3)
    self.place(l3)
    if t == "None":
        return Val("null", "None")  # (None either way)
    return Val(self.phi(ph), t)

def gen_boolop(self, n: Node, ascond: bool, want: str, resultsoft: bool = False) -> Val:
    # Python semantics: `a or b` yields a if a is truthy, else b (same static type)
    c0 = n.kids[0]
    c1 = n.kids[1]
    if n.s == "or" and c0.kind == "cmp" and c0.s == "is" and c1.kind == "cmp" and c1.s == "==" and c0.kids[0].kind == "name" and c0.kids[1].kind == "name" and c1.kids[0].kind == "name" and c1.kids[1].kind == "name" and c0.kids[0].s == c1.kids[0].s and c0.kids[1].s == c1.kids[1].s and self.isnum(self.static_type(c0.kids[0])) and self.isnum(self.static_type(c0.kids[1])):
        # x is y or x == y, the identity-or-equality test, on numbers: x == y (numbers have no
        # identity here; see the deviation about NaN)
        return Val(self.cond(c1), "bool") if ascond else self.expr(c1, want, resultsoft=resultsoft)
    st = self.static(n.kids[0])
    if st >= 0:
        # a static test on the left: it is the value if it decides, else the right operand
        # (where the test is not compiled, static_reads() reads its classes)
        if (st == 1) == (n.s == "or") and not ascond:
            return self.expr(n.kids[0], want, resultsoft=resultsoft)
        self.static_reads(n.kids[0])
        if (st == 1) == (n.s == "or"):
            return Val("true" if st == 1 else "false", "bool")
        return Val(self.cond(n.kids[1]), "bool") if ascond else self.expr(n.kids[1], want, resultsoft=resultsoft)
    a = Val(self.cond(n.kids[0]), "bool") if ascond else self.expr(n.kids[0], want, resultsoft=resultsoft)
    if a.t == "None":
        # None is false: `None and b` is None without evaluating b, `None or b` is b
        if n.s == "or":
            return self.expr(n.kids[1], want, resultsoft=resultsoft)
        return Val("null", "None")
    c = self.truth(a)
    if self.term:
        self.place(self.label())
    e1 = self.cur
    l2 = self.label()
    l3 = self.label()
    if n.s == "and":
        self.cbr(c, l2, l3)
    elif is_sopt(a.t) and not ascond:
        # x or y with x an int | None: a true x is unboxed where it goes to the join (e1)
        e1 = self.label()
        self.cbr(c, e1, l2)
        self.place(e1)
        self.br(l3)
    else:
        self.cbr(c, l3, l2)
    self.place(l2)
    pre = self.narrow_by(n.kids[0], n.s == "and")
    self.branch += 1
    b = Val(self.cond(n.kids[1]), "bool") if ascond else self.expr(n.kids[1], a.t, resultsoft=resultsoft)
    self.branch -= 1
    self.narrowed = self.forget_walrus(pre, n.kids[1:])
    # a right operand that ends the program (sys.exit()) has no edge to the join, and no value
    rt = a.t
    if not ascond and (is_opt(a.t) or is_opt(b.t) or b.t == "None"):
        # x or y with x T | None: a true x is a T; x or None, x and y: T | None
        rt = unopt(a.t) if n.s == "or" else a.t
        if not self.term and self.join(rt, b.t) != "":
            rt = self.join(rt, b.t)
    ph = Ins("phi", rt, "")
    self.incoming(ph, self.convert_at(a, rt, e1).v if not ascond and self.converts(a.t, rt) else a.v, e1)
    if not self.term:
        self.incoming(ph, self.coerce(b, rt).v, self.cur)
    self.br(l3)
    self.place(l3)
    return Val(self.phi(ph), rt)

def gen_unary(self, n: Node) -> Val:
    op = n.s
    e = n.kids[0]
    if op == "not":
        return Val(self.scalar('xor', [Val(self.cond(e), 'bool'), Val('true', 'bool')]), "bool")
    if op == "-" and (e.kind == "int" or e.kind == "float"):
        return self.expr(mk(e.kind, "-" + e.s, e.line, []), "")
    v = self.expr(e, "")
    if is_union(unopt(v.t)):
        return self.unumeric(op, v, Val("", ""), "", True)
    if is_sopt(v.t):
        v = self.unwrap(v, f"TypeError: bad operand type for unary {op}: 'NoneType'")
    v = self.as_int(v)
    if v.t == "int" and op == "-":
        return Val(self.iop("-", "0", v.v), "int")
    if v.t == "int" and op == "~":
        return Val(self.scalar('xor', [Val(v.v, 'int'), Val('-1', 'int')]), "int")
    if v.t == "float" and op == "-":
        return Val(self.scalar('fneg', [Val(v.v, 'float')]), "float")
    if (v.t == "int" or v.t == "float") and op == "+":
        return v
    m = UNARY[op]
    if v.t in self.classes and m in self.classes[v.t].methods:
        self.notnone(v, f"TypeError: bad operand type for unary {op}: 'NoneType'")
        return self.call_fn(self.classes[v.t].methods[m], [v], [])
    self.err(f"bad operand type for unary {op}: '{tname(v.t)}'")
    return v

def gen_dunder(self, op: str, a: Val, b: Val, shown: str = "") -> Val:
    # operator overloading: guard unsupported reflected dispatch before selecting __add__ & co
    m = DUNDER.get(op, "")
    if m != "" and (a.t in self.nts or b.t in self.nts):
        r = self.ntop(op, a, b, shown)
        if r.t != "":
            return r
    if op in REFL and (a.t in self.classes or b.t in self.classes):
        return self.richcmp(op, a, b)
    if (op == "==" or op == "!=") and a.t == "None" and b.t in self.classes:
        # None == x: None's own __eq__ declines, so CPython asks x
        bm = self.classes[b.t].methods
        if m in bm and self.cmp_method(b.t, m, "None") != "":
            return self.eqcall(bm[m], op == "==", b, a)
        if op == "!=" and self.cmp_method(b.t, "__eq__", "None") != "":
            return Val(self.scalar('xor', [Val(self.eqcall(bm['__eq__'], True, b, a).v, 'bool'), Val('true', 'bool')]), "bool")
        return Val("", "")
    # (two specializations of one class template are one class to CPython)
    same = a.t == b.t or (self.tmpl_of(a.t) != "" and self.tmpl_of(a.t) == self.tmpl_of(b.t))
    sh = shown if shown != "" else op
    if op == "**":
        # A builtin numeric exponent cannot supply a user reflected method or subclass
        # priority. Keep object/object and reflected power outside this bounded dispatch.
        if a.t in self.classes and self.isnum(b.t) and "__pow__" in self.classes[a.t].methods:
            self.none_operand(shown if shown != "" else "** or pow()", a, b)
            return self.call_fn(self.classes[a.t].methods["__pow__"], [a], [self.vnode(b)])
        # CPython calls a.__ipow__(b) (**=), a.__pow__(b), else b.__rpow__(a) (b of another class)
        pw = ""
        for x, n in [(a, "__ipow__" if shown == "**=" else ""), (a, "__pow__"), (b, "__rpow__" if not same else "")]:
            if pw == "" and x.t in self.classes and n in self.classes[x.t].methods:
                pw = f"{tname(x.t)}.{n}"
        if pw != "":
            self.err(f"** and pow() of objects are not supported ({tname(unopt(a.t))} {sh} {tname(b.t)} calls {pw})")
    rm = "__r" + m[2:]
    if m != "" and op != "==" and op != "!=" and b.t in self.classes and not (op == "%" and a.t == "str"):
        # A base-typed value may hold a subclass on either side. Python gives a strict
        # subclass's distinct reflected method priority over the left forward method,
        # including when it overrides a reflected method already present on the base.
        # Reject any such possible pair until reflected arithmetic is implemented.
        left = [a.t]
        right = [b.t]
        if a.t in self.classes and self.classes[a.t].tag > 0:
            left = [c.name for c in self.classes.values() if c.tag > 0 and self.derives(c.name, a.t)]
        if self.classes[b.t].tag > 0:
            right = [c.name for c in self.classes.values() if c.tag > 0 and self.derives(c.name, b.t)]
        for at in left:
            for bt in right:
                pair_same = at == bt or (self.tmpl_of(at) != "" and self.tmpl_of(at) == self.tmpl_of(bt))
                if pair_same or rm not in self.classes[bt].methods:
                    continue
                reflected = at not in self.classes or m not in self.classes[at].methods
                if at in self.classes and self.derives(bt, at):
                    reflected = reflected or rm not in self.classes[at].methods or self.classes[bt].methods[rm] is not self.classes[at].methods[rm]
                if reflected:
                    self.err(f"reflected operator methods are not supported ({tname(unopt(at))} {sh} {tname(bt)} calls {tname(bt)}.{rm})")
    if a.t not in self.classes:
        return Val("", "")
    ms = self.classes[a.t].methods
    if m in ms and (op == "==" or op == "!=") and self.lenient and self.cmp_method(a.t, m, b.t) == "":
        return Val("", "")
    if m in ms and (op == "==" or op == "!="):
        return self.eqcall(ms[m], op == "==", a, b)
    if m in ms:
        self.none_operand(shown if shown != "" else op, a, b)
        return self.call_fn(ms[m], [a, b], [])
    if op == "!=" and "__eq__" in ms:
        return Val(self.scalar('xor', [Val(self.dunder('==', a, b).v, 'bool'), Val('true', 'bool')]), "bool")
    return Val("", "")

def gen_ntop(self, op: str, a: Val, b: Val, shown: str) -> Val:
    # a op b with a NamedTuple operand: tuple's methods, which compare it (with tuples and
    # other NamedTuples), concatenate and repeat it as the tuple of its fields, unless its class
    # defines the operator; Val("", "") where the class's own method or no method applies
    m = DUNDER[op]
    rm = DUNDER[REFL[op]] if op in REFL else m if op == "==" or op == "!=" else "__r" + m[2:]
    tl = (a.t in self.nts or is_tuple(a.t)) and (b.t in self.nts or is_tuple(b.t))
    if a.t in self.nts and m in self.classes[a.t].methods:
        return Val("", "")  # (CPython calls it first, also with a tuple or another NamedTuple)
    cmp = op in REFL or op == "==" or op == "!="
    if b.t in self.nts and rm in self.classes[b.t].methods and (is_tuple(a.t) if cmp else a.t != b.t):
        # (CPython asks a tuple's subclass first, and b's __radd__ & co where a has no __add__)
        self.err(f"{short(b.t)}.{rm} with a {typestr(a.t)} operand is not supported")
    if tl and (op == "==" or op == "!="):
        return self.cmp2(op, self.ntup(a), self.ntup(b))
    if tl and cmp:
        return self.richcmp(op, a, b)
    if (op == "+" and tl) or (op == "*" and (a.t == "int" or b.t == "int")):
        sh = shown if shown != "" else op
        self.none_operand(sh, a, b)  # (None on the left)
        self.notnone(b, 'TypeError: can only concatenate tuple (not "NoneType") to tuple' if op == "+" else f"TypeError: unsupported operand type(s) for {sh}: 'int' and 'NoneType'")
        return self.arith(op, self.ntup(a, True), self.ntup(b, True), shown)
    return Val("", "")

def gen_ntup(self, v: Val, known: bool = False) -> Val:
    # a NamedTuple as tuple's methods see it: the tuple of its fields (a tuple | None if it
    # may be None and is not known not to be here); any other value as it is
    if v.t not in self.nts:
        return v
    ci = self.classes[v.t]
    maybe = v.v not in self.nn and not known
    l0 = self.cur
    lread = self.label() if maybe else ""
    lend = self.label() if maybe else ""
    if maybe:
        self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, lend, lread)
        self.place(lread)
    t = self.tuple_([self.getfield(v, Val(self.fgep(v, ci.fpos[x]), ci.ftypes[x]), x) for x in ci.fields])
    if not maybe:
        return t
    l1 = self.cur
    self.br(lend)
    self.place(lend)
    ph = Ins("phi", self.optional(t.t), "")
    self.incoming(ph, "null", l0)
    self.incoming(ph, t.v, l1)
    return Val(self.phi(ph), ph.t)

def gen_cmp_method(self, t: str, m: str, other: str) -> str:
    # m, if class t defines it as a binary method that accepts an operand of type other
    if t not in self.classes or m not in self.classes[t].methods:
        return ""
    f = self.classes[t].methods[m]
    if (f.bad != "" and not self.lenient) or (f.bad == "" and len(f.params) == 2 and (self.widens(other, f.ptypes[1]) or f.ptypes[1] == "")):
        return m  # (a method that cannot be compiled: the call reports why; see desc. A template takes any operand)
    return ""

def gen_exc_kinds(self, t: str) -> list[str]:
    # the exception classes an object of exception class t may be of, where one has a
    # comparison method, which inherit_cmp tells apart by their ExcClass as it does ordinary
    # classes by their tag (a subclass's method, or its reflected one first); else []
    if t not in self.classes or self.classes[t].exc == "":
        return []
    cs = [c.name for c in self.classes.values() if c.exc != "" and self.derives(c.name, t)]
    for c in cs:
        if any([DUNDER[o] in self.classes[c].methods for o in ICMP]):
            return cs
    return []

def gen_cmp_kinds(self, t: str) -> list[str]:
    # the classes an object of class t may be of, which inherit_cmp compares it as: by the tag
    # of an ordinary class, by the ExcClass of an exception class (exc_kinds)
    if self.classes[t].tag != 0:
        return [c.name for c in self.classes.values() if c.tag != 0 and self.derives(c.name, t)]
    ks = self.exc_kinds(t)
    return ks if len(ks) > 0 else [t]

def gen_cmp_pick(self, op: str, at: str, bt: str) -> list[str]:
    # the method concrete_cmp calls for op between objects of the concrete classes at and bt, as
    # [the operand it is called on ("a" or "b"), the method, "!" if its result is inverted
    # (a != b by __eq__)]; [] where neither class has one
    right = at in self.classes and bt in self.classes and at != bt and self.derives(bt, at)
    sides = ["b", "a"] if right else ["a", "b"]
    methods = [DUNDER[REFL[op]] if op in REFL else DUNDER[op], DUNDER[op]] if right else [DUNDER[op], DUNDER[REFL[op]] if op in REFL else DUNDER[op]]
    for i in range(2):
        lt = bt if sides[i] == "b" else at
        rt = at if sides[i] == "b" else bt
        m = methods[i]
        inv = ""
        if lt in self.classes:
            ms = self.classes[lt].methods
            if op == "!=" and m not in ms and "__eq__" in ms:
                m = "__eq__"
                inv = "!"
            if m in ms and ms[m].synthetic and self.is_dc(ms[m].cls) and lt != rt:
                continue  # (what @dataclass writes returns NotImplemented for an object of another class)
            if m in ms:
                return [sides[i], m, inv]
    return []

def gen_inherit_cmp(self, op: str, a: Val, b: Val, phase: int = 0) -> Val:
    # Compare concrete runtime types, including None. Both operands matter: Python gives
    # the right operand's reflected comparison priority when its class is a strict subtype.
    if phase == 2:
        return self.concrete_cmp(op, a, b)
    v = a if phase == 0 else b
    if v.t not in self.classes:
        return self.inherit_cmp(op, a, b, phase + 1)
    cs = self.cmp_kinds(v.t)
    if len(cs) == 1 and v.v in self.nn:
        return self.inherit_cmp(op, a, b, phase + 1)
    end = self.label()
    ph = Ins("phi", "bool", "")
    if v.v not in self.nn:
        null = self.label()
        some = self.label()
        self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, null, some)
        self.place(null)
        r = self.inherit_cmp(op, Val("null", "None") if phase == 0 else a, b if phase == 0 else Val("null", "None"), phase + 1)
        if not self.term:
            self.incoming(ph, r.v, self.cur)
            self.br(end)
        self.place(some)
    xc = self.classes[v.t].exc != ""
    tag = self.mload('%ptr' if xc else 'int', v.v) if len(cs) > 1 else ""
    for i in range(len(cs)):
        nxt = self.label() if i + 1 < len(cs) else ""
        if nxt != "":
            arm = self.label()
            if xc:
                # (an exception object's first field is its class's ExcClass, made for the test)
                self.xcls[cs[i]] = True
                hit = self.scalar_cmp('eq', Val(tag, '%ptr'), Val(f"@x.{cs[i]}", '%ptr'))
            else:
                hit = self.num_cmp('==', Val(tag, "int"), Val(str(self.classes[cs[i]].tag), "int")).v
            self.cbr(hit, arm, nxt)
            self.place(arm)
        r = self.inherit_cmp(op, Val(v.v, cs[i]) if phase == 0 else a, b if phase == 0 else Val(v.v, cs[i]), phase + 1)
        if not self.term:
            self.incoming(ph, r.v, self.cur)
            self.br(end)
        if nxt != "":
            self.place(nxt)
    self.place(end)
    if len(ph.a) == 0:
        self.unreachable()
        return Val("false", "bool")
    return Val(self.phi(ph), "bool")

def gen_concrete_cmp(self, op: str, a: Val, b: Val) -> Val:
    # Both objects now have known, non-null concrete classes. NotImplemented is outside
    # the subset; a supported comparison method returns bool, so the first one completes.
    p = self.cmp_pick(op, a.t, b.t)
    if len(p) > 0:
        lhs = a if p[0] == "a" else b
        rhs = b if p[0] == "a" else a
        m = p[1]
        if self.cmp_method(lhs.t, m, rhs.t) == "":
            why = f"{m}() of {shown(lhs.t)} cannot compare an operand of type {typestr(rhs.t)}"
            if not self.lenient or not self.curfn.ll.startswith("@o."):
                self.err(why)
            # (in obj_helpers' bodies, which compile every ordering of a class that a descriptor
            # compares, it raises where it runs; desc rejects the operations that run it)
            self.raise_("TypeError", self.sconst(why))
            return Val("false", "bool")
        r = self.coerce(self.call_fn(self.classes[lhs.t].methods[m], [lhs, rhs], [], direct=True), "bool")
        return Val(self.scalar('xor', [Val(r.v, 'bool'), Val('true', 'bool')]), "bool") if p[2] == "!" else r
    if op == "==" or op == "!=":
        # object.__eq__ declines, then Python falls back to object identity.
        if (a.t in self.classes or a.t == "None") and (b.t in self.classes or b.t == "None"):
            return self.ptr_cmp('==' if op == '==' else '!=', a, b)
        return Val("false" if op == "==" else "true", "bool")
    self.raise_("TypeError", self.sconst(f"'{op}' not supported between instances of '{tname(a.t)}' and '{tname(b.t)}'"))
    return Val("false", "bool")

def gen_member_item(self, item: Val, a: Val, found: str, ph: Ins) -> None:
    # CPython's test of one item in x in s: item is x or item == x, going to found (ph true)
    # if so, else on in the block placed next, as a tuple's item is tested (titem_eq)
    self.titem_eq(item, a, found, ph, "true")

def gen_iter_in(self, op: str, a: Val, it: Val) -> Val:
    # x in o of an object whose __iter__ returns iterator object it: its items, from __next__,
    # each tested as a tuple's are (member_item), until the first that matches; the rest stay
    # in the iterator
    found = self.label()
    ph = Ins("phi", "bool", "")
    c = self.stop_catch()
    lc = self.label()
    none = self.label()
    self.fn.loops.append(Loop("while", lc, lc, lc, none))
    self.place(lc)
    item = self.next_in(it, c)
    self.place(self.label())
    self.member_item(item, a, found, ph)
    self.br(lc)
    self.stop_landing(c, none)
    self.place(none)
    self.incoming(ph, "false", self.cur)
    self.br(found)
    self.place(found)
    r = self.phi(ph)
    return Val(r if op == "in" else self.scalar('xor', [Val(r, 'bool'), Val('true', 'bool')]), "bool")

def gen_inherit_contains(self, op: str, a: Val, b: Val) -> Val:
    # Membership chooses __contains__ before the iterator fallback on the concrete class.
    # A subclass can add __contains__ even when its base already supplies __iter__.
    self.notnone(b, "TypeError: argument of type 'NoneType' is not iterable")
    cs = [c for c in self.classes.values() if c.tag != 0 and self.derives(c.name, b.t)]
    tag = self.mload('int', b.v) if len(cs) > 1 else ""
    end = self.label()
    ph = Ins("phi", "bool", "")
    for i in range(len(cs)):
        ci = cs[i]
        nxt = self.label() if i + 1 < len(cs) else ""
        if nxt != "":
            arm = self.label()
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(ci.tag), "int")).v, arm, nxt)
            self.place(arm)
        obj = Val(b.v, ci.name)
        result = Val("false", "bool")
        if "__contains__" in ci.methods:
            hit = self.truth(self.call_fn(ci.methods["__contains__"], [obj, a], [], direct=True))
            result = Val(hit if op == "in" else self.scalar('xor', [Val(hit, 'bool'), Val('true', 'bool')]), "bool")
        elif "__iter__" in ci.methods or "__getitem__" in ci.methods:
            items = self.obj_iterator(obj, "TypeError: argument of type 'NoneType' is not iterable", f"argument of type '{short(ci.name)}' is not iterable")
            if is_gen(items.t):
                hit = self.gen_contains(a, items).v  # (an __iter__ that yields)
                result = Val(hit if op == "in" else self.scalar('xor', [Val(hit, 'bool'), Val('true', 'bool')]), "bool")
            else:
                result = self.cmp2(op, a, items) if is_list(items.t) else self.iter_in(op, a, items)
        else:
            self.raise_("TypeError", self.sconst(f"argument of type '{short(ci.name)}' is not iterable"))
        if not self.term:
            self.incoming(ph, result.v, self.cur)
            self.br(end)
        if nxt != "":
            self.place(nxt)
    self.place(end)
    if len(ph.a) == 0:
        self.unreachable()
        return Val("false", "bool")
    return Val(self.phi(ph), "bool")

def gen_isnull(self, v: Val) -> str:
    # i1: is v None at run time
    if v.t == "None":
        return "true"
    if (v.t in self.classes and v.v not in self.nn) or is_opt(v.t) or (is_union(v.t) and self.optional(v.t) == v.t and v.v not in self.nn):
        return self.ptr_cmp('==', v, Val('null', 'None')).v
    return "false"

def gen_richcmp(self, op: str, a: Val, b: Val) -> Val:
    # a < b for objects, as CPython does it: a.__lt__(b) if a defines it, else the reflected
    # b.__gt__(a), else TypeError naming both run-time types (None defines neither)
    fw = self.cmp_method(a.t, DUNDER[op], b.t)
    rf = self.cmp_method(b.t, DUNDER[REFL[op]], a.t)
    if fw == "" and rf == "" and not self.lenient and a.t in self.classes and DUNDER[op] in self.classes[a.t].methods:
        self.err(f"{DUNDER[op]}() of {shown(a.t)} takes a {typestr(self.classes[a.t].methods[DUNDER[op]].ptypes[1])}, not a {typestr(b.t)}")
    # a NamedTuple without the method compares as the tuple of its fields (see ntop): b's
    # reflected method runs only where a is None
    nt = fw == "" and (a.t in self.nts or b.t in self.nts) and (a.t in self.nts or is_tuple(a.t)) and (b.t in self.nts or is_tuple(b.t))
    if fw == "" and rf == "" and not self.lenient and not nt:
        self.err(f"'{op}' not supported between instances of '{tname(a.t)}' and '{tname(b.t)}'")
    if fw != "" and a.v in self.nn:
        return self.call_fn(self.classes[a.t].methods[fw], [a, b], [])
    lend = self.label()
    ph = Ins("phi", "bool", "")
    if nt:
        lcall = self.label()
        lnone = self.label()
        self.cbr(self.scalar('or', [Val(self.isnull(a), 'bool'), Val(self.isnull(b), 'bool')]), lnone, lcall)
        self.place(lcall)
        r = self.cmp2(op, self.ntup(a, True), self.ntup(b, True))
        self.incoming(ph, r.v, self.cur)
        self.br(lend)
        self.place(lnone)
    if fw != "":
        lcall = self.label()
        lnone = self.label()
        self.cbr(self.isnull(a), lnone, lcall)
        self.place(lcall)
        r = self.call_fn(self.classes[a.t].methods[fw], [a, b], [])
        self.incoming(ph, r.v, self.cur)
        self.br(lend)
        self.place(lnone)
    if rf != "" and not (self.classes[b.t].methods[rf].synthetic and self.is_dc(self.classes[b.t].methods[rf].cls)):
        # (what @dataclass writes returns NotImplemented for None, here a, as for an object of
        # another class)
        lcall = self.label()
        lerr = self.label()
        self.cbr(self.isnull(b), lerr, lcall)
        self.place(lcall)
        r = self.call_fn(self.classes[b.t].methods[rf], [b, a], [])
        self.incoming(ph, r.v, self.cur)
        self.br(lend)
        self.place(lerr)
    an = self.isnull(a)
    bn = self.isnull(b)
    ms: list[str] = []
    for x in ["NoneType", tname(unopt(a.t))]:
        for y in ["NoneType", tname(unopt(b.t))]:
            ms.append(self.sconst(f"'{op}' not supported between instances of '{x}' and '{y}'"))
    mn = self.select(bn, Val(ms[0], "str"), Val(ms[1], "str"))
    mf = self.select(bn, Val(ms[2], "str"), Val(ms[3], "str"))
    self.raise_("TypeError", self.select(an, Val(mn, "str"), Val(mf, "str")))
    self.place(lend)
    if len(ph.a) == 0:
        return Val("false", "bool")
    return Val(self.phi(ph), "bool")

def gen_eqcall(self, f: FnInfo, iseq: bool, a: Val, b: Val) -> Val:
    # a == b via __eq__ (or != via __ne__). With None on the left CPython falls back to
    # b's reflected method, or to identity when both are None.
    if a.v in self.nn:
        return self.call_fn(f, [a, b], [])
    same = "true" if iseq else "false"
    lnull = self.label()
    lcall = self.label()
    lend = self.label()
    ph = Ins("phi", "bool", "")
    self.cbr(self.ptr_cmp('==', a, Val('null', 'None')).v, lnull, lcall)
    self.place(lnull)
    if b.t == a.t:
        lboth = self.label()
        lrefl = self.label()
        self.cbr(self.ptr_cmp('==', b, Val('null', 'None')).v, lboth, lrefl)
        self.place(lboth)
        self.incoming(ph, same, lboth)
        self.br(lend)
        self.place(lrefl)
        r = self.call_fn(f, [b, a], [])
        self.incoming(ph, r.v, self.cur)
    else:
        # None == None is True; None == <anything else> is False
        self.incoming(ph, same if b.t == "None" else ("false" if iseq else "true"), lnull)
    self.br(lend)
    self.place(lcall)
    r = self.call_fn(f, [a, b], [])
    self.incoming(ph, r.v, self.cur)
    self.br(lend)
    self.place(lend)
    return Val(self.phi(ph), "bool")

def gen_arith(self, op: str, a: Val, b: Val, shown: str = "") -> Val:
    if is_union(unopt(a.t)) or is_union(unopt(b.t)):
        return self.unumeric(op, a, b, shown, False)
    du = self.dunder(op, a, b, shown)
    if du.t != "":
        return du
    if is_opt(a.t) or is_opt(b.t):
        self.none_operands(op, a, b, shown)
        return self.arith(op, self.deref(a) if is_opt(a.t) else a, self.deref(b) if is_opt(b.t) else b, shown)
    if a.t == "bool" and b.t == "bool" and (op == "&" or op == "|" or op == "^"):
        return Val(self.scalar(IOPS[op], [Val(a.v, 'bool'), Val(b.v, 'bool')]), "bool")
    if is_set(a.t) and is_set(b.t) and (op == "|" or op == "&" or op == "-" or op == "^"):
        return self.setop(op, a, b)
    a = self.as_int(a)
    b = self.as_int(b)
    if a.t == "int" and b.t == "int" and op == "/":
        return Val(self.rt("pys_idiv", "double", [f"i64 {a.v}", f"i64 {b.v}"]), "float")
    if a.t == "int" and b.t == "int" and op != "/":
        if op in CHECKED:
            return Val(self.iop(op, a.v, b.v), "int")
        if op in IOPS:
            return Val(self.scalar(IOPS[op], [Val(a.v, 'int'), Val(b.v, 'int')]), "int")
        if op in IRT:
            return Val(self.rt(IRT[op], "i64", [f"i64 {a.v}", f"i64 {b.v}"]), "int")
    if (a.t == "int" or a.t == "float") and (b.t == "int" or b.t == "float"):
        x = self.as_float(a)
        y = self.as_float(b)
        if op in FOPS:
            return Val(self.scalar(FOPS[op], [Val(x.v, 'float'), Val(y.v, 'float')]), "float")
        if op in FRT:
            return Val(self.rt(FRT[op], "double", [f"double {x.v}", f"double {y.v}"]), "float")
    seq = a.t == "str" or a.t == "bytes" or is_list(a.t)
    if op == "+" and seq and a.t == b.t:
        return Val(self.rt("pys_str_add" if a.t == "str" else "pys_bytes_add" if a.t == "bytes" else "pys_list_add", "ptr", [f"ptr {a.v}", f"ptr {b.v}"]), a.t)
    lw = self.wider(a.t, b.t) if op == "+" and is_list(a.t) and is_list(b.t) else ""
    if lw != "" and self.widens_items(a.t, lw) and self.widens_items(b.t, lw):
        return Val(self.rt("pys_list_add", "ptr", [f"ptr {a.v}", f"ptr {b.v}"]), lw)  # (a new list of the items of both)
    if op == "*" and seq and b.t == "int":
        return Val(self.rt("pys_str_mul" if a.t == "str" else "pys_bytes_mul" if a.t == "bytes" else "pys_list_mul", "ptr", [f"ptr {a.v}", f"i64 {b.v}"]), a.t)
    if op == "+" and is_tuple(a.t) and is_tuple(b.t):
        return self.tuple_([self.tget(a, i) for i in range(len(targs(a.t)))] + [self.tget(b, i) for i in range(len(targs(b.t)))])
    if op == "*" and is_tuple(a.t) and b.t == "int":
        if b.v.startswith("%"):
            self.err(f"{typestr(a.t)} * n needs a constant n (its length is part of its type)")
        ts = targs(a.t)
        count = max(0, int(b.v))
        # For a nonempty tuple, size = 6 + count * (len(a.t) - 6); divide first so
        # even sys.maxsize cannot overflow in the self-hosted compiler. () stays ().
        if len(ts) > 0 and count > (TYPE_SIZE - 6) // (len(a.t) - 6):
            self.err(f"type representation exceeds {TYPE_SIZE} bytes; simplify the type or annotate template parameters")
        return self.tuple_([self.tget(a, i % len(ts)) for i in range(len(ts) * count)])
    if op == "*" and a.t == "int" and (b.t == "str" or b.t == "bytes" or is_list(b.t) or is_tuple(b.t)):
        return self.arith(op, b, a)
    if op == "+" and is_list(a.t) and is_list(b.t):
        self.err(f"unsupported operand types for +: {typestr(a.t)} and {typestr(b.t)} (a list holds items of one type)")
    if op == "|" and is_dict(a.t) and is_dict(b.t):
        # a | b: a copy of a, updated with b (dict_or: PyDict_Copy, then dict_update_arg)
        if b.t != a.t:
            self.err(f"unsupported operand types for {shown if shown != '' else op}: {typestr(a.t)} and {typestr(b.t)} (a dict holds keys and values of one type each)")
        r = self.rt("pys_dict_copy", "ptr", [f"ptr {a.v}"], self.key_fx(targs(a.t)[0]))
        self.rt("pys_dict_update", "void", [f"ptr {r}", f"ptr {b.v}"], self.key_fx(targs(a.t)[0]))
        return Val(r, a.t)
    if op == "%" and a.t == "str":
        # CPython formats with any str on the left; only a literal format is compiled (percent)
        self.err(runtime_format("%"))
    # CPython's TypeError, at compile time
    an = tname(a.t)
    bn = tname(b.t)
    if op == "+" and (a.t == "str" or is_list(a.t) or is_tuple(a.t)):
        self.err(f'can only concatenate {an} (not "{bn}") to {an}')
    if op == "+" and a.t == "bytes":
        self.err(f"can't concat {bn} to bytes")
    sq = a.t == "str" or a.t == "bytes" or is_list(a.t) or is_tuple(a.t)
    if op == "*" and (sq or b.t == "str" or b.t == "bytes" or is_list(b.t) or is_tuple(b.t)):
        self.err(f"can't multiply sequence by non-int of type '{bn if sq else an}'")
    self.err(f"unsupported operand type(s) for {shown if shown != '' else '** or pow()' if op == '**' else op}: '{an}' and '{bn}'")
    return a

def gen_compare(self, n: Node) -> Val:
    tc = self.refl_type_cmp(n)  # (type(a) is C, type(a) == type(b): reflection.py)
    if tc is not None:
        return tc
    ops = n.s.split(",")
    if len(ops) == 1 and (n.kids[0].kind == "list" or n.kids[0].kind == "dict") and (len(n.kids[0].kids) == 0 or nones(n.kids[0])):
        # [] == xs, {} in ds, [None] == xs: an empty display, or one of None, takes its type
        # from the other side (it has nothing to evaluate first)
        b = self.expr(n.kids[1], "")
        w = b.t
        if ops[0] == "in" or ops[0] == "not in":
            w = elem(b.t) if is_list(b.t) else targs(b.t)[0] if is_dict(b.t) else ""
        if (ops[0] == "in" or ops[0] == "not in") and b.t in self.classes and b.t not in self.nts:
            # x in o: the type of __contains__'s parameter, or of the items __iter__ steps through
            ms = self.classes[b.t].methods
            if "__contains__" in ms:
                w = self.argtype(b.t, "__contains__", 1, "")
            elif "__iter__" in ms and is_list(ms["__iter__"].ret):
                w = elem(ms["__iter__"].ret)
        if len(n.kids[0].kids) > 0:
            self.soft = n.kids[0]
        return self.cmp2(ops[0], self.expr(n.kids[0], w, resultsoft=True), b)
    # (x is None reads a local that only None was assigned to so far, see none_type)
    self.nonecmp = len(ops) == 1 and n.kids[1].kind == "None" and n.kids[0].kind == "name" and (ops[0] == "is" or ops[0] == "is not" or ops[0] == "==" or ops[0] == "!=")
    if len(ops) == 1 and (ops[0] == "in" or ops[0] == "not in") and self.lookup_key(n.kids[0]):
        t = unopt(self.probe_type(n.kids[1]))
        if is_dict(t) or is_set(t):
            self.stkkey = n.kids[0]  # ((i, j) in memo)
    a = self.expr(n.kids[0], "")
    self.stkkey = self.nokey
    self.nonecmp = False
    if len(ops) == 1 and (ops[0] == "in" or ops[0] == "not in") and self.iterator_call(n.kids[1]) and n.kids[1].kids[0].s == "range":
        # x in range(...): arithmetic, as CPython's range.__contains__ does for ints; an int |
        # None that is None equals no item
        nn = ""
        if is_sopt(a.t) and unopt(a.t) != "float":
            nn = self.ptr_cmp('!=', a, Val('null', 'None')).v
            a = Val(self.optint(a, "0"), "int")
        if a.t != "int" and a.t != "bool":
            self.err(f"'in range(...)' needs an int, not {typestr(a.t)}")
        vs = self.range_args(n.kids[1].kids[1:])
        hit = self.rt("pys_range_has", "i64", [f"i64 {self.as_int(a).v}", f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"])
        if nn != "":
            hit = self.select(nn, Val(hit, "int"), Val("0", "int"))
        return self.num_cmp('!=' if ops[0] == 'in' else '==', Val(hit, "int"), Val('0', "int"))
    if len(ops) == 1:
        w = a.t
        if (ops[0] == "in" or ops[0] == "not in") and n.kids[1].kind == "list" and (is_list(a.t) or is_dict(a.t)):
            w = self.ctype("list", [a.t])  # (xs in [[1], [2]]: a list of such)
        if (ops[0] == "in" or ops[0] == "not in") and n.kids[1].kind == "set" and folds(mk("tuple", "", n.line, n.kids[1].kids)):
            # x in {1, 2, 3}: CPython's AST optimizer makes a display of constants there a
            # frozenset constant (see set_display)
            return self.cmp2(ops[0], a, self.set_display(n.kids[1], "", True))
        self.soft = n.kids[1]  # (a display there may hold what may be None where a holds none)
        return self.cmp2(ops[0], a, self.expr(n.kids[1], w, resultsoft=True))
    l3 = self.label()
    ph = Ins("phi", "bool", "")
    r = a
    for i in range(len(ops)):
        self.branch += 1 if i > 0 else 0
        b = self.expr(n.kids[i + 1], a.t, resultsoft=True)
        self.branch -= 1 if i > 0 else 0
        r = self.cmp2(ops[i], a, b)
        if i < len(ops) - 1:
            nx = self.label()
            self.incoming(ph, "false", self.cur)
            self.cbr(r.v, nx, l3)
            self.place(nx)
        a = b
    self.incoming(ph, r.v, self.cur)
    self.br(l3)
    self.place(l3)
    self.narrowed = self.forget_walrus(self.narrowed, n.kids[2:])  # (operands that may not run)
    return Val(self.phi(ph), "bool")

def gen_exc_id(self, v: Val) -> Val:
    # what an exception is, for is and ==: the object of an exception class it raises, if it
    # raises one (each raise of it makes an exception of its own), else itself
    return Val(self.rt("pys_exc_id", "ptr", [f"ptr {v.v}"]), "exc") if v.t == "exc" else v

def gen_exc_eq(self, t: str, what: str = "") -> None:
    # == compares exceptions (of type t, or inside t) by identity: not where an exception
    # class defines __eq__ or __ne__, which CPython calls for one that an exception may be
    if not self.ueq_type(t) and "E" in self.desc(t, "repr"):
        for c in self.classes.values():
            if c.exc != "" and ("__eq__" in c.methods or "__ne__" in c.methods):
                m = "__eq__" if "__eq__" in c.methods else "__ne__"
                what = what if what != "" else "between exceptions" if t == "exc" else f"between values of type {typestr(t)}"
                self.err(f"== {what} is not supported where an exception class defines {m} ({short(c.name)} does): compare objects of the class itself, or use 'is'")

def gen_titem_eq(self, item: Val, a: Val, hit: str, ph: Ins | None, value: str) -> bool:
    # whether tuple item is x, or item == x, as CPython's PyObject_RichCompareBool(item, x, Py_EQ)
    # tests it for in, index() and count(): a branch to hit (where phi ph, if any, takes value)
    # where it is, and on in a new block where it is not; False if no branch can reach hit
    u = unopt(item.t)
    identity = (item.t in self.classes or is_list(u) or is_dict(u) or is_set(u) or is_tuple(u) or is_vtuple(u)) and self.isref(a.t)
    if identity:
        # (an object, list, dict, set or tuple, also one that may be None, is found
        # by identity first, as the runtime's eqitem finds a list's item: xs in (xs,)
        # with xs = [nan]; a number has no identity here, see the deviation about NaN,
        # and a str's is its value)
        nx = self.label()
        if ph is not None:
            self.incoming(ph, value, self.cur)
        self.cbr(self.ptr_cmp('==', item, a).v, hit, nx)
        self.place(nx)
    # Named tuples and homogeneous runtime tuples compare as tuples, including
    # numeric and optional element layouts accepted by ordinary equality.
    if item.t in self.nts and "__eq__" not in self.classes[item.t].methods:
        item = self.ntup(item)
    if a.t in self.nts and "__eq__" not in self.classes[a.t].methods:
        a = self.ntup(a)
    paired = item.t != a.t and self.ueq_type(item.t) and self.ueq_type(a.t) and not (self.isnum(item.t) and self.isnum(a.t))
    setpair = is_set(item.t) and is_set(a.t) and self.wider(selem(item.t), selem(a.t)) != ""
    if not paired and not setpair and not self.comparable(item.t, a.t) and self.boxwider(item.t, a.t) == "":
        # item == x of types whose values are never equal: CPython still calls the
        # item's __eq__(x), or where the item's class has none (a builtin type's
        # declines) x's __eq__(item); with neither, they are not equal
        c = self.foreign_eq(item, a)
        if c.t != "":
            nx = self.label()
            if ph is not None:
                self.incoming(ph, value, self.cur)
            self.cbr(c.v, hit, nx)
            self.place(nx)
        return identity or c.t != ""
    if paired:
        r = self.rt("pys_eq_pair", "i64", ["i64 " + self.to_slot(item), "i64 " + self.to_slot(a), f"ptr {self.sconst(self.desc(item.t, '=='))}", f"ptr {self.sconst(self.desc(a.t, '=='))}"])
        c = self.num_cmp('!=', Val(r, "int"), Val('0', "int"))
    else:
        c = self.cmp2("==", item, a)
    nx = self.label()
    if ph is not None:
        self.incoming(ph, value, self.cur)
    self.cbr(c.v, hit, nx)
    self.place(nx)
    return True

def gen_cmp2(self, op: str, a: Val, b: Val) -> Val:
    if (op == "==" or op == "!=") and (a.t == RANGEC) != (b.t == RANGEC):
        # a range and a value of a builtin type, which is never equal to a range (CPython compares
        # them by identity); None, or a value that may be None, may be the same as a range that is
        o = b.t if a.t == RANGEC else a.t
        if o in self.classes or o == "None" or is_opt(o) or is_union(o):
            if o not in self.classes and o != "None":
                self.err(f"comparing a range with {typestr(o)} is not supported")
        else:
            return Val("false" if op == "==" else "true", "bool")
    if (op == "in" or op == "not in") and b.t == RANGEC:
        # x in a range object: arithmetic, as x in range(...) (an int | None that is None equals
        # no item)
        self.notnone(b, "TypeError: argument of type 'NoneType' is not iterable")
        nn = ""
        if is_sopt(a.t) and unopt(a.t) != "float":
            nn = self.ptr_cmp('!=', a, Val('null', 'None')).v
            a = Val(self.optint(a, "0"), "int")
        if a.t != "int" and a.t != "bool":
            self.err(f"'in' of a range needs an int, not {typestr(a.t)}")
        rf = self.range_fields(b)
        hit = self.rt("pys_range_has", "i64", [f"i64 {self.as_int(a).v}", f"i64 {rf[0]}", f"i64 {rf[1]}", f"i64 {rf[2]}"])
        if nn != "":
            hit = self.select(nn, Val(hit, "int"), Val("0", "int"))
        return self.num_cmp('!=' if op == 'in' else '==', Val(hit, "int"), Val('0', "int"))
    if op in ["==", "!=", "<", "<=", ">", ">="]:
        if is_vtuple(unopt(a.t)) and is_tuple(b.t):
            b = self.coerce(b, unopt(a.t))
        elif is_tuple(a.t) and is_vtuple(unopt(b.t)):
            a = self.coerce(a, unopt(b.t))
    if (op == "==" or op == "!=" or op in REFL) and ((a.t in self.classes and self.classes[a.t].tag != 0) or (b.t in self.classes and self.classes[b.t].tag != 0)):
        return self.inherit_cmp(op, a, b)
    ka = self.exc_kinds(a.t) if op == "==" or op == "!=" or op in REFL else []
    kb = self.exc_kinds(b.t) if op == "==" or op == "!=" or op in REFL else []
    if (len(ka) > 1 or len(kb) > 1 or (a.t != b.t and len(ka) + len(kb) > 0)) and a.t != "exc" and b.t != "exc":
        # (objects of one exception class that has no subclass call its method as before; an
        # exception, of a builtin class, stays rejected: exc_eq)
        return self.inherit_cmp(op, a, b)
    if (op == "in" or op == "not in") and b.t in self.classes and self.classes[b.t].tag != 0:
        return self.inherit_contains(op, a, b)
    if (is_union(unopt(a.t)) or is_union(unopt(b.t))) and a.t != "None" and b.t != "None":
        if (op == "==" or op == "!=") and self.ueq_type(a.t) and self.ueq_type(b.t):
            return self.uequal(op, a, b)
        if not ((op == "in" or op == "not in") and (is_tuple(b.t) or (is_list(b.t) and is_union(unopt(elem(b.t))) and self.ueq_type(elem(b.t))))):
            self.err("comparing closed union values requires narrowing with isinstance() first")
    if (op == "in" or op == "not in") and is_kw(b.t):
        b = self.kw_list(b)  # (x in kwargs: among the names)
    if (op == "==" or op == "!=" or op == "is" or op == "is not") and is_callable(unopt(a.t)) and is_fn(b.t):
        b = self.coerce(b, unopt(a.t))  # (a function and a Callable: as Callables of one type)
    elif (op == "==" or op == "!=" or op == "is" or op == "is not") and is_fn(a.t) and is_callable(unopt(b.t)):
        a = self.coerce(a, unopt(b.t))
    if (op == "==" or op == "!=" or op == "is" or op == "is not") and is_callable(unopt(a.t)) and unopt(a.t) == unopt(b.t) and (is_opt(a.t) or is_opt(b.t)):
        # Callables that may be None: both are, or both hold one function (below)
        nula = self.ptr_cmp('==', a, Val('null', 'None')).v
        nulb = self.ptr_cmp('==', b, Val('null', 'None')).v
        lsome = self.label()
        ldone = self.label()
        cph = Ins("phi", "bool", "")
        self.incoming(cph, self.scalar('and', [Val(nula, 'bool'), Val(nulb, 'bool')]), self.cur)
        self.cbr(self.scalar('or', [Val(nula, 'bool'), Val(nulb, 'bool')]), ldone, lsome)
        self.place(lsome)
        rv = self.cmp2("==", Val(a.v, unopt(a.t)), Val(b.v, unopt(b.t)))
        self.incoming(cph, rv.v, self.cur)
        self.br(ldone)
        self.place(ldone)
        eqv = self.phi(cph)
        return Val(eqv if op == "==" or op == "is" else self.scalar('xor', [Val(eqv, 'bool'), Val('true', 'bool')]), "bool")
    if is_callable(a.t) and a.t == b.t and (op == "==" or op == "!=" or op == "is" or op == "is not"):
        # one function, as Callables of one type: the same code and the same env (a closure's)
        ca = self.mload('%ptr', a.v)
        cb = self.mload('%ptr', b.v)
        ea = self.mload('%ptr', self.maddr('%ptr', f'{a.v}', '1', True))
        eb = self.mload('%ptr', self.maddr('%ptr', f'{b.v}', '1', True))
        both = self.scalar('and', [Val(self.scalar_cmp('eq', Val(ca, '%ptr'), Val(cb, '%ptr')), 'bool'), Val(self.scalar_cmp('eq', Val(ea, '%ptr'), Val(eb, '%ptr')), 'bool')])
        return Val(both if op == "==" or op == "is" else self.scalar('xor', [Val(both, 'bool'), Val('true', 'bool')]), "bool")
    if (is_fn(a.t) or is_fn(b.t)) and (op == "==" or op == "!=" or op == "is" or op == "is not"):
        # a function value is the function its type names: never None, and the same function as
        # another value of its type only (a closure, as the same def or lambda run once: its env)
        if a.t.startswith("fn[m:") and b.t.startswith("fn[m:"):
            ac = a.t[5 : a.t.rfind(".")]
            bc = b.t[5 : b.t.rfind(".")]
            am = a.t[a.t.rfind(".") + 1 : -1]
            bm = b.t[b.t.rfind(".") + 1 : -1]
            if ac in self.classes and bc in self.classes and self.classes[ac].tag != 0 and self.classes[bc].tag != 0 and (self.derives(ac, bc) or self.derives(bc, ac)):
                if op == "is" or op == "is not":
                    self.err(f"'{op}' between bound methods is not supported: CPython makes a new method object each time one is read (compare them with ==)")
                if am == bm:
                    return self.ptr_cmp('==' if op == '==' else '!=', a, b)
        if a.t == b.t and (a.t.startswith("fn[m:") or a.t.startswith("fn[d:")) and (op == "is" or op == "is not"):
            self.err(f"'{op}' between bound methods is not supported: CPython makes a new method object each time one is read (compare them with ==)")
        if a.t == b.t and (a.t.startswith("fn[c:") or a.t.startswith("fn[m:") or a.t.startswith("fn[d:")):
            # (bound methods of one method are equal where they are bound to one object)
            return self.ptr_cmp('==' if op == '==' or op == 'is' else '!=', a, b)
        same = a.t == b.t
        return Val("true" if same == (op == "==" or op == "is") else "false", "bool")
    if (op == "==" or op == "!=") and a.t == b.t and a.t == "file":
        # files compare by identity, as CPython's do
        return self.ptr_cmp('==' if op == '==' else '!=', a, b)
    xa = a.t == "exc" or (a.t in self.classes and self.classes[a.t].exc != "")
    xb = b.t == "exc" or (b.t in self.classes and self.classes[b.t].exc != "")
    if xa and xb and a.t != b.t and a.t in self.classes and b.t in self.classes and (op == "==" or op == "!="):
        # objects of exception classes with a base class in common: as objects of that base,
        # by identity (where a class they may be of has __eq__, see exc_kinds)
        cb = a.t
        while cb in self.classes and not self.derives(b.t, cb):
            cb = self.classes[cb].base
        if cb in self.classes:
            a = self.coerce(a, cb)
            b = self.coerce(b, cb)
    if xa and xb and (a.t != b.t or a.t == "exc") and (op == "==" or op == "!=" or op == "is" or op == "is not"):
        # exceptions, builtin or objects of exception classes of different classes: by identity
        # (an exception class's object is an exception of its own that each raise of it makes)
        if op == "==" or op == "!=":
            x = "an exception" if a.t == "exc" else f"an object of {short(a.t)}"
            y = "an exception" if b.t == "exc" else f"an object of {short(b.t)}"
            self.exc_eq("exc", "between exceptions" if a.t == b.t else f"between {x} and {y}")
        return self.ptr_cmp('==' if op == '==' or op == 'is' else '!=', self.exc_id(a), self.exc_id(b))
    if op == "is" or op == "is not":
        if (a.t == "None") != (b.t == "None") and (not self.isref(a.t) or not self.isref(b.t)):
            # a number or bool is never None
            return Val("false" if op == "is" else "true", "bool")
        if a.t == "bool" and b.t == "bool":
            # (x is True: a bool is one of CPython's two objects True and False)
            return Val(self.scalar_cmp('eq' if op == 'is' else 'ne', Val(a.v, 'bool'), Val(b.v, 'bool')), "bool")
        if not self.isref(a.t) or not self.isref(b.t) or (is_sopt(a.t) and b.t != "None") or (is_sopt(b.t) and a.t != "None"):
            self.err("'is' is only supported for objects and None")
        return self.ptr_cmp('==' if op == 'is' else '!=', a, b)
    du = self.dunder(op, a, b)
    if du.t != "":
        return du
    if (op == "in" or op == "not in") and is_opt(b.t):
        b = self.unwrap(b, "TypeError: argument of type 'NoneType' is not iterable")
    if (op == "in" or op == "not in") and b.t in self.nts and "__contains__" not in self.classes[b.t].methods:
        self.notnone(b, "TypeError: argument of type 'NoneType' is not iterable")
        b = self.ntup(b, True)  # (tuple's __contains__)
    if (op == "in" or op == "not in") and b.t in self.classes:
        # x in o: o.__contains__(x), true as its result is; else x is among what o's __iter__
        # steps through
        if "__contains__" not in self.classes[b.t].methods:
            b = self.obj_iterator(b, "TypeError: argument of type 'NoneType' is not iterable", f"argument of type '{tname(b.t)}' is not iterable")
            if not is_list(b.t) and not is_gen(b.t):
                return self.iter_in(op, a, b)
        else:
            self.notnone(b, "TypeError: argument of type 'NoneType' is not iterable")
            r = self.truth(self.protocol(b, "__contains__", [a]))
            return Val(r if op == "in" else self.scalar('xor', [Val(r, 'bool'), Val('true', 'bool')]), "bool")
    if (op == "in" or op == "not in") and is_gen(b.t):
        r = self.gen_contains(a, b).v  # (x in g: it runs until an item equals x)
        return Val(r if op == "in" else self.scalar('xor', [Val(r, 'bool'), Val('true', 'bool')]), "bool")
    if (op == "in" or op == "not in") and b.t == "str":
        a = self.unwrap(a, "TypeError: 'in <string>' requires string as left operand, not NoneType")
    if (op == "in" or op == "not in") and a.t == "None" and ((is_dict(b.t) and targs(b.t)[0] not in self.classes) or (is_set(b.t) and selem(b.t) not in self.classes) or (is_list(b.t) and (self.optional(elem(b.t)) == "" or self.isnum(elem(b.t))) and elem(b.t) not in self.classes)):
        return Val("false" if op == "in" else "true", "bool")  # None is no key of a dict (no element of a set) but an object's, and no number
    kt = targs(b.t)[0] if is_dict(b.t) else selem(b.t) if is_set(b.t) else ""
    if (op == "in" or op == "not in") and is_opt(a.t) and ((kt != "" and (unopt(a.t) == kt or (is_sopt(a.t) and bool_for_int(unopt(a.t), kt)))) or (is_sopt(a.t) and is_list(b.t) and (unopt(a.t) == elem(b.t) or self.isnum(elem(b.t))))):
        # None is no key of the dict (and no int of a list[int])
        nn = self.ptr_cmp('!=', a, Val('null', 'None')).v
        e0 = self.cur
        l1 = self.label()
        l2 = self.label()
        self.cbr(nn, l1, l2)
        self.place(l1)
        hv = self.cmp2("in", self.deref(a), b)
        e1 = self.cur
        self.br(l2)
        self.place(l2)
        ph = Ins("phi", "bool", "")
        self.incoming(ph, "false", e0)
        self.incoming(ph, hv.v, e1)
        hv = Val(self.phi(ph), "bool")
        return hv if op == "in" else Val(self.scalar('xor', [Val(hv.v, 'bool'), Val('true', 'bool')]), "bool")
    if (op == "in" or op == "not in") and is_tuple(b.t):
        # CPython: for each item in order, item is x or item == x; stop at the first match
        lend = self.label()
        ph = Ins("phi", "bool", "")
        for i in range(len(targs(b.t))):
            self.titem_eq(self.tget(b, i), a, lend, ph, "true")
        self.incoming(ph, "false", self.cur)
        self.br(lend)
        self.place(lend)
        r = self.phi(ph)
        return Val(r if op == "in" else self.scalar('xor', [Val(r, 'bool'), Val('true', 'bool')]), "bool")
    if op == "in" or op == "not in":
        r = ""
        if b.t == "str":
            r = self.rt("pys_str_contains", "i64", [f"ptr {b.v}", f"ptr {self.coerce(a, 'str').v}"])
        elif b.t == "bytes" and (a.t == "int" or a.t == "bool"):
            r = self.rt("pys_bytes_has", "i64", [f"ptr {b.v}", f"i64 {self.as_int(a).v}"])  # (a byte's value)
        elif b.t == "bytes" and a.t == "bytes":
            r = self.rt("pys_bytes_contains", "i64", [f"ptr {b.v}", f"ptr {a.v}"])
        elif b.t == "bytes":
            self.err(f"a bytes-like object is required, not '{tname(a.t)}'")
        elif is_list(b.t):
            if a.t != elem(b.t) and (is_list(a.t) or is_dict(a.t) or is_tuple(a.t)) and self.numeric_comparable(a.t, elem(b.t)):
                # A read-only search can compare the two item layouts directly;
                # coercing the needle would wrongly widen mutable containers.
                r = self.rt("pys_list_find_pair", "i64", [f"ptr {b.v}", "i64 " + self.to_slot(a), f"ptr {self.sconst(self.desc(elem(b.t), '=='))}", f"ptr {self.sconst(self.desc(a.t, '=='))}"])
                return self.num_cmp(">=" if op == "in" else "<", Val(r, "int"), Val("0", "int"))
            ok = "true"
            if self.isnum(a.t) and self.isnum(unopt(elem(b.t))) and a.t != unopt(elem(b.t)):
                nk = self.numkey(a, unopt(elem(b.t)))  # (1 in [1.0]: the item that equals it)
                a = Val(nk[0], unopt(elem(b.t)))
                ok = nk[1]
            et = a.t if is_opt(a.t) and unopt(a.t) == elem(b.t) else elem(b.t)  # (None is in no list[T])
            if is_union(unopt(elem(b.t))) and self.ueq_type(elem(b.t)):
                et = self.union_type([elem(b.t), a.t])
            if a.t == "None" and elem(b.t) not in self.classes and self.optional(elem(b.t)) != "" and not self.isnum(elem(b.t)):
                et = self.optional(elem(b.t))
            s = self.to_slot(self.coerce(a, et))
            self.exc_eq(et)
            r = self.rt("pys_list_find", "i64", [f"ptr {b.v}", f"i64 {s}", f"ptr {self.sconst(self.desc(et, '=='))}"])
            r = self.scalar('add', [Val(r, 'int'), Val('1', 'int')])
            if ok != "true":
                r = self.select(ok, Val(r, "int"), Val("0", "int"))
        elif is_dict(b.t):
            s = self.to_slot(self.dkey(a, targs(b.t)[0]))
            r = self.rt("pys_dict_has", "i64", [f"ptr {b.v}", f"i64 {s}"], self.key_fx(targs(b.t)[0]))
        elif is_set(b.t):
            s = self.to_slot(self.dkey(a, selem(b.t)))
            r = self.rt("pys_set_has", "i64", [f"ptr {b.v}", f"i64 {s}"], self.key_fx(selem(b.t)))
        else:
            self.err(f"'in' is not supported for {b.t}")
        return self.num_cmp('!=' if op == 'in' else '==', Val(r, "int"), Val('0', "int"))
    if (is_sopt(a.t) or is_sopt(b.t)) and self.isnum(unopt(a.t)) and self.isnum(unopt(b.t)):
        return self.optcmp(op, a, b)
    if self.isnum(a.t) and self.isnum(b.t):
        if a.t != "float" and b.t != "float":
            return self.num_cmp(op, self.as_int(a), self.as_int(b))
        if a.t == "float" and b.t == "float":
            return self.num_cmp(op, a, b)
        # int against float: exact, as CPython compares them (double rounding would not be)
        iv = self.as_int(b if a.t == "float" else a)
        if not iv.v.startswith("%") and -9007199254740992 <= int(iv.v) <= 9007199254740992:
            return self.num_cmp(op, self.as_float(a), self.as_float(b))
        fv = a if a.t == "float" else b
        r = self.rt("pys_cmp_if", "i64", [f"i64 {iv.v}", f"double {fv.v}"])
        if a.t == "float":
            r = self.select(self.num_cmp('==', Val(r, "int"), Val('2', "int")).v, Val("2", "int"), Val(self.scalar('sub', [Val('0', 'int'), Val(r, 'int')]), "int"))
        # cmp_if returns -1, 0, 1, or 2 for unordered (NaN). Unsigned <= 1
        # excludes both -1 and 2 for >=; signed <= 0 keeps -1 and 0 for <=.
        if op == ">=":
            return self.int_ucmp("<=", Val(r, "int"), Val("1", "int"))
        if op == "<" or op == ">":
            return self.num_cmp("==", Val(r, "int"), Val("-1" if op == "<" else "1", "int"))
        return self.num_cmp(op, Val(r, "int"), Val("0", "int"))
    if is_set(a.t) and is_set(b.t) and op in ICMP:
        # subsets and equality (a set equals a frozenset of its elements)
        if self.wider(selem(a.t), selem(b.t)) == "":
            self.err(f"cannot compare {typestr(a.t)} {op} {typestr(b.t)}")
        r = self.rt("pys_set_cmp", "i64", [f"ptr {a.v}", f"ptr {b.v}", f"i64 {ORDOP[op] if op in ORDOP else 4 if op == '==' else 5}"], self.key_fx(selem(a.t)) + self.key_fx(selem(b.t)))
        return self.num_cmp('!=', Val(r, "int"), Val('0', "int"))
    eq = op == "==" or op == "!="
    if eq and (a.t == "None") != (b.t == "None") and self.isnum(a.t if b.t == "None" else b.t):
        return Val("false" if op == "==" else "true", "bool")  # a number or bool never equals None
    if eq and (a.t == "None" or b.t == "None" or (a.t == b.t and a.t in self.classes)) and self.isref(a.t) and self.isref(b.t):
        if a.t == "exc" or b.t == "exc":
            self.exc_eq("exc", "between an exception and None")
        return self.ptr_cmp(op, a, b)
    if op in ORDOP and is_tuple(a.t) and is_tuple(b.t) and len(targs(a.t)) != len(targs(b.t)):
        return self.tuple_order(op, a, b)  # (of different lengths, which no one tuple type holds)
    # T and T | None (also as items): None == None, None == x is False, and None < x raises
    ct = self.wider(a.t, b.t)
    if eq and ct == "" and self.numeric_comparable(a.t, b.t):
        # Equality reads each operand using its own descriptor, preserving exact
        # numeric comparison without changing either container's stored type.
        r = self.rt("pys_eq_pair", "i64", ["i64 " + self.to_slot(a), "i64 " + self.to_slot(b), f"ptr {self.sconst(self.desc(a.t, '=='))}", f"ptr {self.sconst(self.desc(b.t, '=='))}"])
        return self.num_cmp("!=" if op == "==" else "==", Val(r, "int"), Val("0", "int"))
    if ct == "" and self.boxwider(a.t, b.t) != "":
        # a tuple with an int where the other's item may be None: compared as a new tuple of boxes
        ct = self.boxwider(a.t, b.t)
        a = self.boxto(a, ct)
        b = self.boxto(b, ct)
    u = unopt(ct)
    if ct != "" and (u == "str" or u == "bytes" or is_list(u) or is_tuple(u) or is_vtuple(u) or (eq and is_dict(u)) or is_set(u) or u == "exc"):
        self.exc_eq(ct)
        d = f"ptr {self.sconst(self.desc(ct, '==' if eq else op))}"
        sa = self.to_slot(a)
        sb = self.to_slot(b)
        if eq:
            r = self.rt("pys_eq", "i64", [f"i64 {sa}", f"i64 {sb}", d])
            return self.num_cmp('!=' if op == '==' else '==', Val(r, "int"), Val('0', "int"))
        r = self.rt("pys_cmpop", "i64", [f"i64 {sa}", f"i64 {sb}", d, f"i64 {ORDOP[op]}"])
        return self.num_cmp('!=', Val(r, "int"), Val('0', "int"))
    x = "an exception" if a.t == "exc" else a.t
    y = "an exception" if b.t == "exc" else b.t
    self.err(f"cannot compare {x} {op} {y}")
    return a

def gen_tuple_order(self, op: str, a: Val, b: Val) -> Val:
    # a < b (or <=, >, >=) of tuples of different lengths, as CPython orders them: by the
    # first items that are not equal (an object, list, dict, set or tuple is equal to itself,
    # as CPython finds by identity first), else by their lengths
    la = len(targs(a.t))
    lb = len(targs(b.t))
    lend = self.label()
    ph = Ins("phi", "bool", "")
    for i in range(min(la, lb)):
        x = self.tget(a, i)
        y = self.tget(b, i)
        ldiff = self.label()
        lnext = self.label()
        u = unopt(x.t)
        if is_tuple(x.t) and is_tuple(y.t) and len(targs(x.t)) != len(targs(y.t)):
            self.br(ldiff)  # (tuples of different lengths, never equal)
        else:
            if (x.t in self.classes or is_list(u) or is_dict(u) or is_set(u) or is_tuple(u)) and self.isref(y.t):
                lcmp = self.label()
                self.cbr(self.ptr_cmp('==', x, y).v, lnext, lcmp)
                self.place(lcmp)
            self.cbr(self.cmp2("==", x, y).v, lnext, ldiff)
        self.place(ldiff)
        # (items without the ordering, dicts or objects without __lt__ & co, raise CPython's
        # TypeError only where they are reached, as the runtime's comparison of tuples of one
        # length raises it: equal ones go on to the lengths)
        if is_dict(x.t) and is_dict(y.t):
            self.raise_("TypeError", self.sconst(f"'{op}' not supported between instances of 'dict' and 'dict'"))
        else:
            lenient = self.lenient
            self.lenient = True  # (see richcmp)
            r = self.cmp2(op, x, y)
            self.lenient = lenient
            self.incoming(ph, r.v, self.cur)
            self.br(lend)
        self.place(lnext)
    shorter = {"<": la < lb, "<=": la <= lb, ">": la > lb, ">=": la >= lb}[op]
    self.incoming(ph, "true" if shorter else "false", self.cur)
    self.br(lend)
    self.place(lend)
    return Val(self.phi(ph), "bool")

def gen_optcmp(self, op: str, a: Val, b: Val) -> Val:
    # a op b for numbers of which one or both may be None: == and != compare None as CPython
    # does (None equals only None), and an ordering raises its TypeError for None
    an = self.isnull(a)
    bn = self.isnull(b)
    anyn = an if bn == "false" else bn if an == "false" else self.scalar('or', [Val(an, 'bool'), Val(bn, 'bool')])
    lnone = self.label()
    lval = self.label()
    lend = self.label()
    self.cbr(anyn, lnone, lval)
    self.place(lnone)
    ph = Ins("phi", "bool", "")
    if op == "==" or op == "!=":
        both = "false" if an == "false" or bn == "false" else self.scalar('and', [Val(an, 'bool'), Val(bn, 'bool')])
        self.incoming(ph, both if op == "==" else self.scalar('xor', [Val(both, 'bool'), Val('true', 'bool')]), self.cur)
        self.br(lend)
    else:
        ms: list[str] = []
        for x in ["NoneType", tname(unopt(a.t))]:
            for y in ["NoneType", tname(unopt(b.t))]:
                ms.append(self.sconst(f"'{op}' not supported between instances of '{x}' and '{y}'"))
        mn = self.select(bn, Val(ms[0], "str"), Val(ms[1], "str"))
        mf = self.select(bn, Val(ms[2], "str"), Val(ms[3], "str"))
        self.raise_("TypeError", self.select(an, Val(mn, "str"), Val(mf, "str")))
    self.place(lval)
    r = self.cmp2(op, self.deref(a) if is_opt(a.t) else a, self.deref(b) if is_opt(b.t) else b)
    self.incoming(ph, r.v, self.cur)
    self.br(lend)
    self.place(lend)
    return Val(self.phi(ph), "bool")

def gen_numeric_comparable(self, t: str, u: str) -> bool:
    # Matching builtin container trees may differ at numeric leaves. Keep
    # optional/union widening and user comparison callbacks out of this path.
    if t == u:
        return self.ueq_type(t)
    if self.isnum(t) and self.isnum(u):
        return True
    if (is_list(t) and is_list(u)) or (is_dict(t) and is_dict(u)) or (is_tuple(t) and is_tuple(u)):
        a = targs(t)
        b = targs(u)
        return len(a) == len(b) and all([self.numeric_comparable(a[i], b[i]) for i in range(len(a))])
    return False

def gen_comparable(self, t: str, u: str) -> bool:
    # can t == u be true at all? (otherwise CPython just answers False)
    if is_union(unopt(t)) or is_union(unopt(u)):
        return self.ueq_type(self.union_type([t, u]))
    if t == u or (self.isnum(unopt(t)) and self.isnum(unopt(u))) or self.wider(t, u) != "" or self.numeric_comparable(t, u):
        return True
    return (t == "None" and (u in self.classes or is_opt(u))) or (u == "None" and (t in self.classes or is_opt(t)))

def gen_foreign_eq(self, a: Val, b: Val) -> Val:
    # a == b of types whose values comparable() finds never equal: the __eq__ of a's class
    # where it takes a b, else, where a's class has none or a dataclass's (a builtin type's
    # declines, as object's and a dataclass's do for an object of another class), the __eq__
    # of b's class where it takes an a (CPython's reflected call); Val("", "") where neither
    # applies, and CPython finds them not equal
    if a.t in self.classes and "__eq__" in self.classes[a.t].methods:
        if self.cmp_method(a.t, "__eq__", b.t) != "":
            return self.eqcall(self.classes[a.t].methods["__eq__"], True, a, b)
        if not self.classes[a.t].methods["__eq__"].synthetic:
            return Val("", "")
    if self.cmp_method(b.t, "__eq__", a.t) != "":
        return self.eqcall(self.classes[b.t].methods["__eq__"], True, b, a)
    return Val("", "")

# ---- calls
