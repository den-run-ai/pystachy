"""Conversions component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.utils import is_union, umembers
from src.pystachy_compiler.diagnostics import dynamic_program, shown
from src.pystachy_compiler.ir import Ins, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import BIG, BIGOPT, DUNDER, NONEVAR, ORDOP, REFL
from src.pystachy_compiler.bigints import big_viewable, held
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
    is_vtuple,
    lt,
    selem,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_to_slot(self, v: Val, keep: bool = False) -> str:
    # v in an 8-byte slot. A slot holds a 64-bit int, so a promoting int is narrowed, and so is a
    # tuple of them, into the tuple of their 64-bit ints, which is the same tuple (bigints.py), as
    # the runtime reads it; but kept (keep) as an item of a tuple of its type
    if v.t == BIG:
        v = self.big_narrow(v)  # (an 8-byte slot holds a 64-bit int: bigints.py)
    if v.t == BIGOPT:
        v = self.big_opt_narrow(v)  # (and an int | None the box of one: bigints.py)
    if is_tuple(v.t) and BIG in v.t and not keep:
        v = self.big_tuple_narrow(v)
    if v.t == "int":
        return v.v
    i = Ins("slot.pack", "%slot", "")
    i.a = [v]
    self.put(i, 1)
    return f"%t{i.r[0]}"

def gen_from_slot(self, s: str, t: str) -> Val:
    # Recursive container slots hold the existing union-box pointer. Expose one
    # layer of its finite named type graph when reading the value.
    t = self.rec_type(t)
    if t == "int":
        return Val(s, t)
    i = Ins("slot.unpack", t, "")
    i.a = [Val(s, "%slot")]
    self.put(i, 1)
    return Val(f"%t{i.r[0]}", t)

def gen_rarg(self, v: Val) -> str:
    if v.t == "bool":
        return "i64 " + self.as_int(v).v
    return f"{lt(v.t)} {v.v}"

def gen_rres(self, r: str, t: str) -> Val:
    if t == "None":
        return Val("null", "None")
    if t == "bool":
        return self.num_cmp('!=', Val(r, "int"), Val('0', "int"))
    return Val(r, t)

def gen_as_int(self, v: Val) -> Val:
    if v.t == "bool":
        return self.num_cast(v, "int")
    if v.t == BIG:
        return self.big_narrow(v)  # (a promoting int, where a 64-bit int is needed: bigints.py)
    return v

def gen_as_float(self, v: Val) -> Val:
    if v.t == "int" or v.t == "bool":
        return self.num_cast(v, "float")
    if v.t == BIG:
        return self.big_float(v)  # (rounded once, as CPython converts an int operand of a float operation)
    return v

def gen_num_cast(self, v: Val, t: str) -> Val:
    # Numeric promotion, unlike slot.pack's bit-preserving representation conversion.
    i = Ins("num.cast", t, "")
    i.a = [v]
    self.put(i, 1)
    return Val(f"%t{i.r[0]}", t)

def gen_num_cmp(self, op: str, a: Val, b: Val) -> Val:
    # The frontend normalizes bools and handles exact mixed int/float comparisons first.
    i = Ins("num.cmp", "bool", op)
    i.a = [a, b]
    self.put(i, 1)
    return Val(f"%t{i.r[0]}", "bool")

def gen_int_ucmp(self, op: str, a: Val, b: Val) -> Val:
    # Bounds checks interpret native int bits as unsigned, also rejecting negatives.
    # Keep that distinction explicit rather than changing num.cmp's signed semantics.
    i = Ins("int.ucmp", "bool", op)
    i.a = [a, b]
    self.put(i, 1)
    return Val(f"%t{i.r[0]}", "bool")

def gen_ptr_cmp(self, op: str, a: Val, b: Val) -> Val:
    # Native reference identity/null tests, including boxed optional scalars.
    i = Ins("ptr.cmp", "bool", op)
    i.a = [a, b]
    self.put(i, 1)
    return Val(f"%t{i.r[0]}", "bool")

def gen_floats(self, v: Val) -> Val:
    # a number, or a list of numbers, as float(s)
    if v.t == "list[int]" or v.t == "list[bool]":
        return Val(self.rt("pys_m_floats", "ptr", [f"ptr {v.v}"]), "list[float]")
    return self.as_float(v)

def gen_ufloats(self, v: Val) -> Val:
    # a list of a union's numbers as floats, as math.fsum() and math.dist() make them (each item's
    # own number: an int's float, by its tag)
    d = self.sconst(self.desc(elem(v.t), "=="))
    return Val(self.rt("pys_m_ufloats", "ptr", [f"ptr {v.v}", f"ptr {d}"]), "list[float]")

def gen_is_dc(self, t: str) -> bool:
    return t in self.classes and (len(self.classes[t].node.kids) > 1 or t in self.nts)

def gen_isnum(self, t: str) -> bool:
    return t == "int" or t == "float" or t == "bool"

def gen_isref(self, t: str) -> bool:
    return t == "None" or lt(t) == "ptr"

def gen_coerce(self, v: Val, t: str, what: str = "") -> Val:
    # v as a value of type t; what names v for the error when v may be None and t may not
    if t.startswith("rec["):
        x = self.coerce(Val(v.v, self.rec_type(v.t)), self.rec_type(t), what)
        return Val(x.v, t)
    if v.t.startswith("rec["):
        v = Val(v.v, self.rec_type(v.t))
    if self.term and v.v == "undef":
        # Numeric union dispatch can prove that every tag raises. Its placeholder
        # never reaches the annotated return or assignment, so needs no conversion.
        return Val("undef", t)
    if v.t == t:
        return v
    if t == BIG and v.t == "int":
        return self.to_big(v)  # (a promoting int: bigints.py; a bool is rejected, as in a module that does not opt in)
    if t == BIGOPT and (v.t == BIG or v.t == "int"):
        return self.big_box(self.to_big(v))  # (an int | None of a module that opts in: bigints.py)
    if v.t == BIGOPT and t != "":
        if t == "opt[int]" and self.join_hint(t, v.t):
            return Val("undef", t)  # (as an inferred int location becomes a promoting int: see join_hint)
        v = self.big_opt_narrow(v)  # (into 64-bit storage: the same box, where the value fits)
        if v.t == t:
            return v
    if v.t == BIG:
        if (t == "int" or t == "bool") and self.join_hint(t, v.t):
            return Val("undef", t)  # (an inferred int location becomes a promoting int: the next pass, see join_hint)
        v = self.big_narrow(v)  # (into 64-bit storage, or as an int: bigints.py)
        if v.t == t:
            return v
    if is_tuple(v.t) and BIG in v.t and t != "" and BIG not in t:
        if is_tuple(t) and self.join_hint(t, v.t):
            return Val("undef", t)  # (as an int location becomes a promoting int)
        v = self.big_tuple_narrow(v)  # (a tuple of promoting ints into 64-bit storage: the same tuple, bigints.py)
        if v.t == t:
            return v
    if big_viewable(v.t, t):
        return self.big_tuple_view(v, t)  # (items that promote where t's do not, or the other way: the same tuple, bigints.py)
    if dynamic_program() and v.lit and (v.t == "float" or (v.t == "int" and (int(v.v) < -5 or int(v.v) > 256))) and ((is_sopt(t) and unopt(t) == v.t) or (is_union(unopt(t)) and v.t in umembers(unopt(t)))):
        captured = Val(v.v, v.t).identity(v)
        captured.idfrom = self.dyn_id_box(v).v
        v = captured
    if t == "dyn":
        return self.dyn_box(v)  # (into dynamic storage: dynamic.py)
    if v.t == "dyn":
        return self.dyn_unbox(v, t, what)  # (out of it, where a concrete type is expected)
    if is_vtuple(unopt(t)) and is_tuple(v.t):
        et = targs(unopt(t))[0]
        vals = [self.coerce(self.tget(v, i), et) for i in range(len(targs(v.t)))]
        raw = self.tuple_(vals)
        return Val(self.rt("pys_vtuple_from", "ptr", [f"ptr {raw.v}", f"i64 {len(vals)}"]), t)
    if is_vtuple(unopt(t)) and is_vtuple(v.t):
        et = targs(unopt(t))[0]
        if is_sopt(et) and targs(v.t)[0] == unopt(et):
            # A fresh immutable tuple of boxes; an existing list or tuple's
            # numeric storage must never be reinterpreted as pointer slots.
            return Val(self.rt("pys_vtuple_box", "ptr", [f"ptr {v.v}"]), t)
    if v.t == "None" and t in self.classes:
        return Val("null", t)
    if v.t in self.classes and t in self.classes and self.derives(v.t, t):
        return Val(v.v, t)  # an object is an object of its base classes too
    if v.t in self.classes and t == "exc" and self.classes[v.t].exc != "":
        self.err(f"expected a builtin exception, got an object of {short(v.t)} (annotate it with {short(v.t)} or a base class of the program)")
    if v.t == "exc" and t in self.classes and self.classes[t].exc != "":
        self.err(f"expected an object of {short(t)}, got a builtin exception, which is not converted to a class of the program (catch it as one: except {short(t)} as e)")
    if self.widens(v.t, t):
        return Val(v.v, t).identity(v)
    if is_union(unopt(t)) and v.t != "None":
        return self.to_union(v, t, what)
    if is_fn(v.t) and is_callable(unopt(t)):
        return Val(self.to_callable(v, unopt(t)).v, t)  # (a function where a Callable is expected)
    if is_sopt(t) and v.t == unopt(t):
        return Val(self.rt("pys_box", "ptr", ["i64 " + self.to_slot(v)]), t).identity(v)  # representation-only boxing
    if self.reboxes(v.t, t):
        # a tuple with an int where t holds an int | None (also deeper): a new tuple, of boxes
        return self.tuple_([self.coerce(self.tget(v, i), targs(t)[i], what) for i in range(len(targs(t)))])
    if self.join_hint(t, v.t):
        return Val("undef", t)  # (a store a join drops: the next pass compiles it, see join_hint)
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
    if "rec[" in t:
        return gen_rec_desc(self, t, use, {}, 0)
    return gen_plain_desc(self, t, use)


def gen_plain_desc(self, t: str, use: str) -> str:
    # (t's own constructor is no recursive alias's, though its parts may hold one: see gen_rec_desc)
    if is_union(unopt(t)):
        # (a union of numbers also orders, as runtime.c's opv compares its members' values)
        if not ((use == "repr" and self.value_union(t)) or (use == "==" and self.ueq_type(t)) or (self.num_union(unopt(t)) and all([op in ORDOP or op == "==" for op in use.split()]))):
            self.err("closed union operations require narrowing with isinstance() first")
        members = umembers(unopt(t))
        d = "U" + str(len(members)) + ":"
        for m in members:
            d += str(self.utag(m)) + ":" + self.desc(m, use)
        return ("?" if is_opt(t) else "") + d
    # type descriptor for the runtime's generic repr (use "repr"), equality ("==") or ordering
    # ("<", ">", ...; a list or tuple compares its items with == first)
    if t == "dyn":
        return "A"  # (a dynamic value's box, walked by its own DynType's descriptor)
    if t == "int" or t == BIG:
        return "i"  # (a promoting int as a container holds it: 64-bit, bigints.py)
    if t == BIGOPT:
        return "?J"  # (an int | None of a module that opts in: a box of a promoting int's two words, runtime.c's jbig)
    if t == "float":
        return "f"
    if t == "bool":
        return "b"
    if t == "str":
        return "s"
    if t == "bytes":
        return "y" if use == "repr" else "s"  # (a bytes compares, orders and hashes as a str of its bytes)
    if is_opt(t) and t != NONEVAR:
        return "?" + self.desc(unopt(t), use)  # None or the value
    if t == "None":
        return "?s"  # (always None: a tuple's item)
    sub = use if use == "repr" or use == "==" else "== " + use
    if is_list(t):
        return "L" + self.desc(held(elem(t)), sub)  # (a tuple of ints as a list holds it: bigints.held)
    if is_vtuple(t):
        return "V" + self.desc(targs(t)[0], sub)
    if is_dict(t):
        a = targs(t)
        return "D" + self.desc(held(a[0]), use) + self.desc(held(a[1]), use if use == "repr" else "==")  # (a tuple of ints as the dict holds it: bigints.held)
    if is_set(t):
        # (S<e> a set, F<e> a frozenset: equal, or ordered as subsets, by their elements)
        return ("F" if is_fset(t) else "S") + self.desc(held(selem(t)), "repr" if use == "repr" else "==")  # (a tuple of ints as the set holds it: bigints.held)
    if is_tuple(t):
        a = targs(t)
        if len(a) > 9:
            self.err("tuples are limited to 9 elements")
        # (J: a promoting int item, its slot and its Mpz word past the items, utils.tslots)
        return "T" + str(len(a)) + "".join(["J" if x == BIG else self.desc(x, sub) for x in a])
    if t == "exc":
        return "E"  # (repr: pys_exc_repr; equality: identity)
    if t == "exctype":
        return "C"  # (an exception class's class object: repr pys_exc_type; equality and hash: identity)
    if t in self.classes:
        # O<id>: the runtime calls back into pys_obj_eq/cmp/repr, which dispatch on the id, and
        # so the methods of use (a < b: __lt__, else the reflected __gt__) with objects of
        # class t (see obj_helpers): one that cannot take them (an object of t, or of a base
        # of t) is an error here. The id has three digits or more, which runtime.c reads up to
        # the next descriptor's letter
        ms = self.classes[t].methods
        for op in use.split():
            m = "__repr__" if op == "repr" else DUNDER[op]
            m = DUNDER[REFL[op]] if m not in ms and op in REFL else m
            f = ms[m] if m in ms else None
            takes = f is None or op == "repr" or f.ptypes[1] == t or f.ptypes[1] == "" or (f.ptypes[1] in self.classes and self.derives(t, f.ptypes[1]))
            takes = takes or (f is not None and f.ptypes[1] == "dyn" and self.dyn_boxable(t) == "")  # (an Any parameter: the object boxed)
            if f is not None and (f.bad != "" or not takes):
                self.err(f.bad if f.bad != "" else f"comparing {shown(t)} objects (in a list, tuple, in, count, index, sort, min or max) calls {m}() with a {shown(t)}, but it takes a {typestr(f.ptypes[1])}")
            # (and between the subclasses' objects a t-typed value may hold, compared by their
            # classes, as inherit_cmp does: the helpers raise where it runs, see concrete_cmp)
            ks = self.cmp_kinds(t) if op != "repr" else []
            for x in ks:
                for y in ks:
                    p = self.cmp_pick(op, x, y) if x != t or y != t else []
                    if len(p) > 0:
                        lt = x if p[0] == "a" else y
                        rt = y if p[0] == "a" else x
                        g = self.classes[lt].methods[p[1]]
                        if self.cmp_method(lt, p[1], rt) == "":
                            self.err(g.bad if g.bad != "" else f"comparing {shown(t)} objects (in a list, tuple, in, count, index, sort, min or max) calls {p[1]}() of {shown(lt)} with a {shown(rt)}, but it takes a {typestr(g.ptypes[1])}")
            # (a NamedTuple, or a dataclass by the method @dataclass writes, compares its fields:
            # those of a class are checked here as well, so that the error is the operation's
            # rather than its helper's, which compiles their comparison; what the check adds to
            # ocls and ocmp is not kept)
            if op != "repr" and t not in self.fchk and ((f is None and t in self.nts) or (f is not None and f.synthetic and self.is_dc(t))):
                ci = self.classes[t]
                oc = dict(self.ocls)
                om = dict(self.ocmp)
                self.fchk[t] = True
                for x in [x for x in self.dc_fields(ci) if x not in ci.fopts or "no-compare" not in ci.fopts[x]]:
                    if unopt(ci.ftypes[x]) in self.classes:
                        self.desc(unopt(ci.ftypes[x]), "==" if op == "==" else "== " + op)
                del self.fchk[t]
                self.ocls = oc
                self.ocmp = om
        if t not in self.ocls:
            self.ocls[t] = len(self.ocls)
        if use != "repr":
            self.ocmp[t] = True
        return f"O{self.ocls[t]:03d}"
    if is_fn(t) or is_callable(t):
        self.err(f"printing a function, or comparing containers of functions, is not supported: {typestr(t)}")
    if is_kw(t):
        self.err(f"printing or comparing **kwargs inside a container is not supported: make it a dict first, dict(kwargs) ({typestr(t)})")
    self.err(f"{tname(t)} values cannot be compared or printed")
    return ""


def gen_rec_desc(self, t: str, use: str, active: dict[str, int], offset: int) -> str:
    # A finite descriptor graph encoded inside one immutable string. R<n>:
    # refers n bytes backwards from the R to an enclosing alias's descriptor.
    # References are leaves for skip(), and followed only while reading a value.
    # Thus neither descriptor construction nor skipping expands a recursive type.
    name = self.rec_fold(t)
    if name.startswith("rec["):
        if name in active:
            return "R" + str(offset - active[name]) + ":"
        active[name] = offset
        out = gen_rec_desc_body(self, self.rec_type(name), use, active, offset)
        del active[name]
        return out
    return gen_rec_desc_body(self, t, use, active, offset)


def gen_rec_desc_body(self, t: str, use: str, active: dict[str, int], offset: int) -> str:
    if is_opt(t):
        return "?" + gen_rec_desc_body(self, unopt(t), use, active, offset + 1)
    if is_union(t):
        if use != "repr" and use != "==":
            self.err("recursive value ordering requires narrowing with isinstance() first")
        # (as gen_desc's unions: the runtime compares and prints only these members by descriptor)
        if not ((use == "repr" and self.value_union(t)) or (use == "==" and self.ueq_type(t))):
            self.err("closed union operations require narrowing with isinstance() first")
        ms = umembers(t)
        out = "U" + str(len(ms)) + ":"
        for m in ms:
            out += str(self.utag(m)) + ":"
            out += gen_rec_desc(self, m, use, active, offset + len(out))
        return out
    if is_list(t):
        return "L" + gen_rec_desc(self, held(elem(t)), use, active, offset + 1)
    if is_dict(t):
        ts = targs(t)
        out = "D" + gen_rec_desc(self, held(ts[0]), use, active, offset + 1)
        return out + gen_rec_desc(self, held(ts[1]), use, active, offset + len(out))
    if is_tuple(t):
        ts = targs(t)
        if len(ts) > 9:
            self.err("tuples are limited to 9 elements")
        out = "T" + str(len(ts))
        for m in ts:
            out += "J" if m == BIG else gen_rec_desc(self, m, use, active, offset + len(out))
        return out
    return gen_plain_desc(self, t, use)  # (not self.desc, which would hand t back here)

# ---- types and declarations
