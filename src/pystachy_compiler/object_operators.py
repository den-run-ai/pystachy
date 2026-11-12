"""Concrete reflected operator dispatch and bounded NotImplemented results."""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, Data, Ins, Val
from src.pystachy_compiler.diagnostics import shown as type_shown
from src.pystachy_compiler.specs import DUNDER, REFL
from src.pystachy_compiler.utils import is_opt, is_union, lib_source, tname, typestr, umembers, unopt


def gen_notimplemented(self) -> Val:
    # An address-significant immortal singleton. Shared module state, like string
    # constants, survives dry runs; a restarted compilation gets a fresh pool.
    if "NotImplemented" not in self.bconsts:
        value = Val("@pys.notimplemented", "notimpl")
        self.bconsts["NotImplemented"] = value
        self.consts.append(Data("singleton", value.v))
    return self.bconsts["NotImplemented"]


def gen_object_op_needed(self, op: str, a: str, b: str) -> bool:
    # Fixed typed methods that cannot decline keep the existing direct path.
    # A possible reflected method or inferred/declining result needs full dispatch.
    if a == "dyn" or b == "dyn" or is_union(unopt(a)) or is_union(unopt(b)):
        # These operands need their existing dynamic dispatch or union admission
        # checks. A concrete peer does not reveal their runtime class or method.
        return False
    if op == "%" and a == "str":
        return False  # String formatting never asks the value's __rmod__.
    cmp = op in REFL or op in ["==", "!="]
    m = "__pow__" if op == "**" else "__divmod__" if op == "divmod" else DUNDER.get(op, "")
    r = DUNDER[REFL[op]] if op in REFL else m if cmp else "__r" + m[2:]
    if m == "":
        return False
    if op in ["**", "divmod"] and (a in self.classes or b in self.classes):
        return True
    for side in [a, b]:
        if side not in self.classes:
            continue
        kinds = self.cmp_kinds(side)
        for c in kinds:
            ms = self.classes[c].methods
            if not cmp and r in ms:
                return True
            for name in [m, r, "__eq__" if op == "!=" else m]:
                if name in ms:
                    f = ms[name]
                    if f.ret == "" or f.infer or "notimpl" in f.ret:
                        return True
    return False


def operator_switch(self, value: Val, alts: list[Val], labels: list[str]) -> None:
    if len(alts) == 1:
        self.br(labels[0])
        return
    if is_opt(value.t):
        self.cbr(self.ptr_cmp("==", value, Val("null", "None")).v, labels[0], labels[1])
        return
    if alts[0].t == "None":
        nonnull = self.label()
        self.cbr(self.ptr_cmp("==", value, Val("null", "None")).v, labels[0], nonnull)
        self.place(nonnull)
    self.cmp_tags(value, alts, labels)


def operator_result(self, result: Val, end: str, results: list[Val], blocks: list[Blk], invert: bool = False) -> bool:
    # False means the method always accepted; True continues to the next method.
    if self.term:
        return False  # A statically non-returning specialization has no join edge.
    if result.t == "notimpl":
        return True
    rest = ""
    if result.t == "opt[notimpl]":
        rest = self.label()
        accept = self.label()
        self.cbr(self.ptr_cmp("==", result, Val("null", "None")).v, accept, rest)
        self.place(accept)
        result = Val("null", "None")
    elif is_union(unopt(result.t)) and "notimpl" in umembers(unopt(result.t)):
        rest = self.label()
        accept = self.label()
        may_none = is_opt(result.t) or self.optional(result.t) == result.t
        self.cbr(self.utest(result, ["notimpl"], may_none), rest, accept)
        self.place(accept)
        members = [t for t in umembers(unopt(result.t)) if t != "notimpl"]
        target = self.union_type(members + (["None"] if may_none else []))
        result = self.narrow_val(result, target)
    if invert:
        result = Val(self.scalar("xor", [Val(self.truth(result), "bool"), Val("true", "bool")]), "bool")
    results.append(result)
    blocks.append(self.blk)
    self.br(end)
    if rest != "":
        self.place(rest)
    return rest != ""


def operator_pair(self, op: str, a: Val, b: Val, shown: str, inplace: bool, end: str, results: list[Val], blocks: list[Blk], modulus: Val | None, at: str, bt: str) -> None:
    cmp = op in REFL or op in ["==", "!="]
    m = "__pow__" if op == "**" else "__divmod__" if op == "divmod" else DUNDER.get(op, "")
    rm = DUNDER[REFL[op]] if op in REFL else m if cmp else "__r" + m[2:]
    am = self.classes[a.t].methods if a.t in self.classes else {}
    bm = self.classes[b.t].methods if b.t in self.classes else {}
    same = a.t == b.t or (self.tmpl_of(a.t) != "" and self.tmpl_of(a.t) == self.tmpl_of(b.t))
    first = a.t in self.classes and b.t in self.classes and not same and self.derives(b.t, a.t)
    if not cmp:
        first = first and rm in bm and (rm not in am or bm[rm] is not am[rm])
    sides: list[int] = []
    names: list[str] = []
    if inplace and ("__i" + m[2:]) in am:
        sides.append(0)
        names.append("__i" + m[2:])
    if first:
        sides.append(1)
        names.append(rm)
    sides.append(0)
    names.append(m)
    if not first and (cmp or not same) and not (op == "%" and a.t == "str"):
        sides.append(1)
        names.append(rm)
    if modulus is not None:
        # CPython 3.13 only tries the base's __pow__ for ternary power.
        sides = [0]
        names = [m]
    for j in range(len(sides)):
        lhs = a if sides[j] == 0 else b
        rhs = b if sides[j] == 0 else a
        methods = am if sides[j] == 0 else bm
        name = names[j]
        invert = cmp and op == "!=" and name not in methods and "__eq__" in methods
        name = "__eq__" if invert else name
        if name not in methods:
            continue
        f = methods[name]
        if cmp and f.synthetic and self.is_dc(f.cls) and lhs.t != rhs.t:
            continue
        if cmp and lib_source(f.node.line, self.libdir, "enum.py") and (rhs.t == "None" or (rhs.t in self.classes and not self.derives(rhs.t, f.cls) and not (self.enum_intlike(f.cls) and self.enum_intlike(rhs.t)))):
            continue
        if cmp and self.cmp_method(lhs.t, name, rhs.t) == "":
            why = f"{name}() of {type_shown(lhs.t)} cannot compare an operand of type {typestr(rhs.t)}"
            if not self.lenient or not self.curfn.ll.startswith("@o."):
                self.err(why)
            self.raise_("TypeError", self.sconst(why))
            return
        # Methods bind after both operands have been evaluated. Calls may mutate
        # either object: every fallback invokes the next method on the same values.
        arg = rhs
        static = bt if sides[j] == 0 else at
        if rhs.t == "None" and (static in self.classes or is_opt(static)) and len(f.ptypes) > 1 and f.ptypes[1] == "":
            # Native class and optional parameters already admit None. Preserve that nullable
            # type at a template's call boundary, rather than requiring a new
            # None-only specialization of an ordinary field-reading method.
            # Selection still uses the concrete pair; an explicit None operand
            # has static type None and keeps its ordinary specialization.
            arg = Val(rhs.v, static)
        args = [self.vnode(arg)]
        if modulus is not None:
            args.append(self.vnode(modulus))
        result = self.call_fn(f, [lhs], args, direct=True)
        if not operator_result(self, result, end, results, blocks, invert):
            return
    if op in ["==", "!="]:
        value = self.ptr_cmp("==" if op == "==" else "!=", a, b) if self.isref(a.t) and self.isref(b.t) else Val("false" if op == "==" else "true", "bool")
        operator_result(self, value, end, results, blocks)
        return
    if modulus is not None:
        error = f"unsupported operand type(s) for ** or pow(): '{tname(a.t)}', '{tname(b.t)}', '{tname(modulus.t)}'"
    elif cmp:
        error = f"'{op}' not supported between instances of '{tname(a.t)}' and '{tname(b.t)}'"
    else:
        symbol = shown if shown != "" else "** or pow()" if op == "**" else "divmod()" if op == "divmod" else op
        error = f"unsupported operand type(s) for {symbol}: '{tname(a.t)}' and '{tname(b.t)}'"
    self.raise_("TypeError", self.sconst(error))


def gen_object_operator(self, op: str, a: Val, b: Val, shown: str = "", inplace: bool = False, modulus: Val | None = None) -> Val:
    # Dispatch only where the actual class can change method selection. Every
    # operand was already evaluated once; no payload is read before its class guard.
    xs = [Val("null", "None"), Val(a.v, unopt(a.t))] if is_opt(a.t) else self.cmp_alts(a)
    ys = [Val("null", "None"), Val(b.v, unopt(b.t))] if is_opt(b.t) else self.cmp_alts(b)
    end = self.label()
    results: list[Val] = []
    blocks: list[Blk] = []
    starts = [self.label() for x in xs]
    operator_switch(self, a, xs, starts)
    narrow = dict(self.narrowed)
    nonnull = dict(self.nn)
    for i in range(len(xs)):
        self.place(starts[i])
        arms = [self.label() for y in ys]
        operator_switch(self, b, ys, arms)
        for j in range(len(ys)):
            self.place(arms[j])
            self.narrowed = dict(narrow)
            self.nn = dict(nonnull)
            left = self.deref(a) if is_opt(a.t) and i > 0 else xs[i]
            right = self.deref(b) if is_opt(b.t) and j > 0 else ys[j]
            for value in [left, right]:
                if value.t in self.classes:
                    self.nn[value.v] = True
            operator_pair(self, op, left, right, shown, inplace, end, results, blocks, modulus, a.t, b.t)
    self.narrowed = narrow
    self.nn = nonnull
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return Val("undef", "int")
    t = results[0].t
    for result in results:
        if result.t != t:
            joined = self.join(t, result.t)
            if joined == "" or (not is_opt(joined) and joined not in self.classes):
                self.err("operator dispatch methods must return one concrete type (optionally None)")
            t = joined
    if t == "None":
        return Val("null", "None")
    phi = Ins("phi", t, "")
    for i in range(len(results)):
        value = self.convert_in(results[i], t, blocks[i]) if results[i].t != t else results[i]
        self.incoming(phi, value.v, self.convedge if results[i].t != t else blocks[i].label)
    return Val(self.phi(phi), t)
