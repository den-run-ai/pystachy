"""Conversions component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import shown
from src.pystachy_compiler.ir import Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import DUNDER, NONEVAR, REFL
from src.pystachy_compiler.utils import (
    elem,
    is_callable,
    is_dict,
    is_fn,
    is_fset,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_sopt,
    is_tuple,
    lt,
    selem,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_to_slot(self, v: Val) -> str:
    if v.t == "int":
        return v.v
    if v.t == "float":
        return self.ins(f"bitcast double {v.v} to i64")
    if v.t == "bool":
        return self.ins(f"zext i1 {v.v} to i64")
    return self.ins(f"ptrtoint ptr {v.v} to i64")

def gen_from_slot(self, s: str, t: str) -> Val:
    if t == "int":
        return Val(s, t)
    if t == "float":
        return Val(self.ins(f"bitcast i64 {s} to double"), t)
    if t == "bool":
        return Val(self.ins(f"trunc i64 {s} to i1"), t)
    return Val(self.ins(f"inttoptr i64 {s} to ptr"), t)

def gen_rarg(self, v: Val) -> str:
    if v.t == "bool":
        return "i64 " + self.ins(f"zext i1 {v.v} to i64")
    return f"{lt(v.t)} {v.v}"

def gen_rres(self, r: str, t: str) -> Val:
    if t == "None":
        return Val("null", "None")
    if t == "bool":
        return Val(self.ins(f"icmp ne i64 {r}, 0"), "bool")
    return Val(r, t)

def gen_as_int(self, v: Val) -> Val:
    if v.t == "bool":
        return Val(self.ins(f"zext i1 {v.v} to i64"), "int")
    return v

def gen_as_float(self, v: Val) -> Val:
    if v.t == "int":
        return Val(self.ins(f"sitofp i64 {v.v} to double"), "float")
    if v.t == "bool":
        return Val(self.ins(f"uitofp i1 {v.v} to double"), "float")
    return v

def gen_floats(self, v: Val) -> Val:
    # a number, or a list of numbers, as float(s)
    if v.t == "list[int]" or v.t == "list[bool]":
        return Val(self.rt("pys_m_floats", "ptr", [f"ptr {v.v}"]), "list[float]")
    return self.as_float(v)

def gen_is_dc(self, t: str) -> bool:
    return t in self.classes and (len(self.classes[t].node.kids) > 1 or t in self.nts)

def gen_isnum(self, t: str) -> bool:
    return t == "int" or t == "float" or t == "bool"

def gen_isref(self, t: str) -> bool:
    return t == "None" or lt(t) == "ptr"

def gen_coerce(self, v: Val, t: str, what: str = "") -> Val:
    # v as a value of type t; what names v for the error when v may be None and t may not
    if v.t == t:
        return v
    if v.t == "None" and t in self.classes:
        return Val("null", t)
    if v.t in self.classes and t in self.classes and self.classes[v.t].exc != "" and self.derives(v.t, t):
        return Val(v.v, t)  # (an exception object is an object of its base classes too)
    if v.t in self.classes and t == "exc" and self.classes[v.t].exc != "":
        self.err(f"expected a builtin exception, got an object of {short(v.t)} (annotate it with {short(v.t)} or a base class of the program)")
    if v.t == "exc" and t in self.classes and self.classes[t].exc != "":
        self.err(f"expected an object of {short(t)}, got a builtin exception, which is not converted to a class of the program (catch it as one: except {short(t)} as e)")
    if self.widens(v.t, t):
        return Val(v.v, t)
    if is_fn(v.t) and is_callable(unopt(t)):
        return Val(self.to_callable(v, unopt(t)).v, t)  # (a function where a Callable is expected)
    if is_sopt(t) and v.t == unopt(t):
        return Val(self.rt("pys_box", "ptr", ["i64 " + self.to_slot(v)]), t)  # (a new box)
    if self.reboxes(v.t, t):
        # a tuple with an int where t holds an int | None (also deeper): a new tuple, of boxes
        return self.tuple_([self.coerce(self.tget(v, i), targs(t)[i], what) for i in range(len(targs(t)))])
    if is_opt(v.t) and self.widens(unopt(v.t), t):
        # (CPython would pass the None on: there is nothing here that could hold it)
        if what == "":
            what = "a value used as " + typestr(t)
        if self.curfn.ll + v.v in self.wide:
            self.err(f"{what} may be None ({typestr(v.t)}), and a test does not narrow a global or a field (a call may change it): copy it to a local variable, and test that")
        self.err(f"{what} may be None ({typestr(v.t)}); test it with 'is not None' first")
    hint = " (write a float literal like 1.0, or use float())" if t == "float" and v.t == "int" else ""
    if is_fn(t) and is_fn(v.t):
        hint = " (each function is a type of its own: a variable, a list's items or a dict's values hold one function)"
    if hint == "" and self.curfn.ll in self.guessed:
        hint = f" (perhaps because {self.guessed[self.curfn.ll]})"
    self.err(f"expected {typestr(t)}, got {typestr(v.t)}{hint}")
    return v

def gen_desc(self, t: str, use: str) -> str:
    # type descriptor for the runtime's generic repr (use "repr"), equality ("==") or ordering
    # ("<", ">", ...; a list or tuple compares its items with == first)
    if t == "int":
        return "i"
    if t == "float":
        return "f"
    if t == "bool":
        return "b"
    if t == "str":
        return "s"
    if is_opt(t) and t != NONEVAR:
        return "?" + self.desc(unopt(t), use)  # None or the value
    if t == "None":
        return "?s"  # (always None: a tuple's item)
    sub = use if use == "repr" or use == "==" else "== " + use
    if is_list(t):
        return "L" + self.desc(elem(t), sub)
    if is_dict(t):
        a = targs(t)
        return "D" + self.desc(a[0], use) + self.desc(a[1], use if use == "repr" else "==")
    if is_set(t):
        # (S<e> a set, F<e> a frozenset: equal, or ordered as subsets, by their elements)
        return ("F" if is_fset(t) else "S") + self.desc(selem(t), "repr" if use == "repr" else "==")
    if is_tuple(t):
        a = targs(t)
        if len(a) > 9:
            self.err("tuples are limited to 9 elements")
        return "T" + str(len(a)) + "".join([self.desc(x, sub) for x in a])
    if t == "exc":
        return "E"  # (repr: pys_exc_repr; equality: identity)
    if t in self.classes:
        # O<id>: the runtime calls back into pys_obj_eq/cmp/repr, which dispatch on the id, and
        # so the methods of use (a < b: __lt__, else the reflected __gt__) with objects of
        # class t (see obj_helpers): one that cannot take them is an error here. The id has
        # three digits or more, which runtime.c reads up to the next descriptor's letter
        ms = self.classes[t].methods
        for op in use.split():
            m = "__repr__" if op == "repr" else DUNDER[op]
            m = DUNDER[REFL[op]] if m not in ms and op in REFL else m
            f = ms[m] if m in ms else None
            if f is not None and (f.bad != "" or (op != "repr" and f.ptypes[1] != t and f.ptypes[1] != "")):
                self.err(f.bad if f.bad != "" else f"comparing {shown(t)} objects (in a list, tuple, in, count, index, sort, min or max) calls {m}() with a {shown(t)}, but it takes a {typestr(f.ptypes[1])}")
        if t not in self.ocls:
            self.ocls[t] = len(self.ocls)
        return f"O{self.ocls[t]:03d}"
    if is_fn(t) or is_callable(t):
        self.err(f"printing a function, or comparing containers of functions, is not supported: {typestr(t)}")
    if is_kw(t):
        self.err(f"printing or comparing **kwargs inside a container is not supported: make it a dict first, dict(kwargs) ({typestr(t)})")
    self.err(f"{tname(t)} values cannot be compared or printed")
    return ""

# ---- types and declarations
