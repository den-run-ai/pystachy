"""Explicit closed scalar, container and native reference unions."""
from __future__ import annotations
from src.pystachy_compiler.analysis import ann_target
from src.pystachy_compiler.ir import ClassInfo, FnInfo, Ins, Val
from src.pystachy_compiler.names import owner
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.specs import NONEVAR, OPTTYPES
from src.pystachy_compiler.utils import elem, is_dict, is_list, is_opt, is_sopt, is_tuple, is_union, is_vtuple, targs, typestr, umembers, unopt

def gen_uboxes(self, a: str, b: str) -> bool:
    # is a value of type a one of union type b (or b | None) once boxed: a member's (one that
    # may be None, where b may be: see to_union)
    a = self.rec_type(a)
    b = self.rec_type(b)
    if not is_union(unopt(b)) or a == "None":
        return False
    src = unopt(a)
    return src in umembers(unopt(b)) or (src in self.classes and len([m for m in umembers(unopt(b)) if m in self.classes and self.derives(src, m)]) == 1)

def gen_reference_union(self, t: str) -> bool:
    return is_union(unopt(t)) and all([m == "file" or m in self.classes for m in umembers(unopt(t))])

def gen_scalar_union(self, t: str) -> bool:
    return is_union(unopt(t)) and all([m in ["int", "float", "bool", "str"] for m in umembers(unopt(t))])

def gen_num_union(self, t: str) -> bool:
    # a union of numbers (int, float, bool), not None: sum() adds its values and orderings compare
    # them, an int with a float exactly (runtime.c's opv)
    return is_union(t) and all([m == "int" or m == "float" or m == "bool" for m in umembers(t)])

def gen_value_union(self, t: str) -> bool:
    return is_union(unopt(t)) and all([m in ["int", "float", "bool", "str"] or is_list(m) or is_dict(m) for m in umembers(unopt(t))])

def gen_ueq_type(self, t: str) -> bool:
    # Finite builtin value trees: paired runtime descriptors handle their layouts,
    # but no class callbacks, file handles, functions or sets cross this boundary.
    t = unopt(t)
    if t.startswith("rec[") and t[4:-1] in self.recursive:
        return True  # each registered graph has only builtin scalar/list/dict leaves
    if t in ["None", "int", "float", "bool", "str"]:
        return True
    if is_union(t):
        return all([self.ueq_type(m) for m in umembers(t)])
    if is_list(t) or is_dict(t) or is_tuple(t) or is_vtuple(t):
        return all([self.ueq_type(m) for m in targs(t)])
    return False

def gen_uop(self, v: Val, op: str) -> Val:
    # Truth and str select the existing native member operation. Evaluate v once,
    # handle None before loading the tag, and join only the operation's result.
    if not self.value_union(v.t) and op == "str" and self.reference_union(v.t):
        return self.refl_union_str(v, "__str__")  # (each class's: reflection.py)
    if not self.value_union(v.t):
        self.err("closed reference union operations require narrowing with isinstance() first")
    t = "bool" if op == "truth" else "str"
    end = self.label()
    ph = Ins("phi", t, "")
    if is_opt(v.t):
        arm = self.label()
        self.incoming(ph, "false" if op == "truth" else self.sconst("None"), self.cur)
        self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, end, arm)
        self.place(arm)
    tag = self.mload('int', v.v)
    members = umembers(unopt(v.t))
    for i in range(len(members)):
        nxt = self.label() if i + 1 < len(members) else ""
        if nxt != "":
            arm = self.label()
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(members[i])), "int")).v, arm, nxt)
            self.place(arm)
        item = self.uget(Val(v.v, unopt(v.t)), members[i])
        result = Val(self.truth(item), "bool") if op == "truth" else self.to_str(item)
        self.incoming(ph, result.v, self.cur)
        self.br(end)
        if nxt != "":
            self.place(nxt)
    self.place(end)
    return Val(self.phi(ph), t)

def gen_uequal(self, op: str, a: Val, b: Val) -> Val:
    # Both operands are already evaluated. Boxes of a narrower union keep their
    # pointers and tags; a concrete scalar is boxed only at this dynamic boundary.
    t = self.union_type([a.t, b.t])
    if t.startswith("!") or not self.ueq_type(t):
        self.err("closed union equality requires builtin scalar, list, dict or tuple values")
    a = self.coerce(a, t)
    b = self.coerce(b, t)
    r = self.rt("pys_eq", "i64", ["i64 " + self.to_slot(a), "i64 " + self.to_slot(b), f"ptr {self.sconst(self.desc(t, '=='))}"])
    return self.num_cmp('!=' if op == '==' else '==', Val(r, "int"), Val('0', "int"))

def gen_umember_problem(self, t: str) -> str:
    # why a value of type t cannot be one of a union's (A | B), or ""
    if t == "int" or t == "float" or t == "bool" or t == "str":
        return ""
    if t == "file" or (t in self.classes and self.classes[t].exc == ""):
        return ""
    if is_list(t) or is_dict(t):
        return ""
    return f"{typestr(t)} in a closed union is not supported (use scalar, list/dict or native class/file types)"

def gen_union_type(self, ts: list[str]) -> str:
    # the type of a value of one of types ts (None among them: T | None): the type, for one, else
    # union[...] of them, nested unions and optionals flattened, in sorted order; "!" and why not
    ms: list[str] = []
    none = False
    for t in ts:
        t = self.rec_type(t)
        if t == "None" or t == NONEVAR:
            none = True
            continue
        if is_opt(t):
            none = True
            t = unopt(t)
        for m in umembers(t) if is_union(t) else [t]:
            if m not in ms:
                ms.append(m)
    if len(ms) == 0:
        return "None"
    if len(ms) == 1:
        r = self.optional(ms[0]) if none else ms[0]
        return r if r != "" else f"!None/Optional is only supported for {OPTTYPES}, not {typestr(ms[0])}"
    for m in ms:
        if self.umember_problem(m) != "":
            return "!" + self.umember_problem(m)
    refs = [m for m in ms if m == "file" or m in self.classes]
    if len(refs) > 0:
        if len(refs) != len(ms):
            return "!reference unions cannot mix native references with scalar or container members"
        if len(ms) > 4:
            return "!reference unions support at most four members"
        for a in refs:
            for b in refs:
                if a != b and a in self.classes and b in self.classes and self.derives(a, b):
                    return "!reference unions cannot contain overlapping class families"
    ms.sort()
    u = self.ctype("union", ms)
    return self.optional(u) if none else u

def gen_utag(self, t: str) -> int:
    # the tag of type t in a union's box: one number per type, for the whole program, so that
    # a union's box is also one of a union of more types
    if t not in self.utags:
        self.utags[t] = len(self.utags) + 1
    return self.utags[t]

def gen_ubox(self, v: Val, m: str) -> str:
    # v, of member type m, as a union's box (a class's object that may be None: null)
    b = self.rt("pys_ubox", "ptr", [f"i64 {self.utag(m)}", "i64 " + self.to_slot(Val(v.v, m))])
    if m not in self.classes or v.v in self.nn:
        return b
    return self.select(self.ptr_cmp('==', v, Val('null', 'None')).v, Val('null', '%ptr'), Val(b, '%ptr'))

def gen_uget(self, u: Val, m: str) -> Val:
    # the value a union's box u holds, known to be of member type m
    i = Ins("union.payload", "%slot", m)
    i.a = [u]
    self.put(i, 2)
    return self.from_slot(f"%t{i.r[1]}", m)

def gen_utest(self, u: Val, ms: list[str], may_none: bool) -> str:
    # i1: does the union's box u (null where it is None, if may_none) hold a value of one of types ms
    if len(ms) == 0:
        return "false"
    l0 = self.cur
    lload = self.label() if may_none else ""
    lend = self.label() if may_none else ""
    if may_none:
        self.cbr(self.ptr_cmp('==', u, Val('null', 'None')).v, lend, lload)
        self.place(lload)
    i = Ins("union.tag", "int", "")
    i.a = [Val(u.v, unopt(u.t))]  # (the existing guard, or narrowing, excludes None)
    self.put(i, 1)
    tag = f"%t{i.r[0]}"
    r = ""
    for m in ms:
        x = self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(m)), "int")).v
        r = x if r == "" else self.scalar('or', [Val(r, 'bool'), Val(x, 'bool')])
    if not may_none:
        return r
    l1 = self.cur
    self.br(lend)
    self.place(lend)
    ph = Ins("phi", "bool", "")
    self.incoming(ph, "false", l0)
    self.incoming(ph, r, l1)
    return self.phi(ph)

def gen_to_union(self, v: Val, t: str, what: str) -> Val:
    # v as a value of union type t (or t | None): a box of its tag and slot, the same pointer for
    # a union of fewer types, null for None; an error where v is of no member type, or may be
    # None and t may not
    u = unopt(t)
    ms = umembers(u)
    none_ok = self.optional(u) == t
    src = unopt(v.t)
    if is_union(src) and len([m for m in umembers(src) if m not in ms]) == 0:
        if is_opt(v.t) and not none_ok:
            if self.join_hint(t, v.t):
                return Val("undef", t)  # (see join_hint)
            self.err(f"{what if what != '' else 'a value used as ' + typestr(t)} may be None ({typestr(v.t)}); test it with 'is not None' first")
        return Val(v.v, t)
    if src not in ms:
        bases = [m for m in ms if src in self.classes and m in self.classes and self.derives(src, m)]
        if len(bases) != 1:
            if self.join_hint(t, v.t):
                return Val("undef", t)  # (see join_hint)
            hint = f" (perhaps because {self.guessed[self.curfn.ll]})" if self.curfn.ll in self.guessed else ""
            self.err(f"expected {typestr(t)}, got {typestr(v.t)}{hint}")
        src = bases[0]
        v = self.coerce(v, src)
    if not is_opt(v.t):
        return Val(self.ubox(v, src), t)
    if not none_ok:
        if self.join_hint(t, v.t):
            return Val("undef", t)  # (see join_hint)
        self.err(f"{what if what != '' else 'a value used as ' + typestr(t)} may be None ({typestr(v.t)}); test it with 'is not None' first")
    # an optional value: None stays null, any other value is boxed (with no branch, so that
    # convert_in can make it at the end of a block); an int | None's value is in its box
    return Val(self.rt("pys_ubox_opt", "ptr", [f"i64 {self.utag(src)}", f"ptr {v.v}", f"i64 {1 if is_sopt(v.t) else 0}"]), t)

def gen_narrow_val(self, v: Val, nt: str) -> Val:
    # v, a local's value of its own type, as of the type nt a test or an assignment narrowed it
    # to (see narrows): an optional's value, a union's member, a union of fewer members,
    # or an ordinary class pointer whose runtime class test proved a derived layout
    if nt == v.t:
        return v
    if v.t in self.classes and nt in self.classes and self.derives(nt, v.t):
        return Val(v.v, nt)
    if not is_union(unopt(v.t)):
        return self.deref(v)  # (an optional known not to be None)
    if nt == "None":
        return Val("null", "None")
    if is_union(unopt(nt)):
        return Val(v.v, nt)  # (the same box)
    m = unopt(nt)
    if m not in self.classes and not is_opt(nt):
        return self.uget(Val(v.v, unopt(v.t)), m)
    # a class's object, or a value that may be None: null stays None
    l0 = self.cur
    lget = self.label()
    lend = self.label()
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, lend, lget)
    self.place(lget)
    x = self.coerce(self.uget(Val(v.v, unopt(v.t)), m), nt)
    l1 = self.cur
    self.br(lend)
    self.place(lend)
    ph = Ins("phi", nt, "")
    self.incoming(ph, "null", l0)
    self.incoming(ph, x.v, l1)
    return Val(self.phi(ph), nt)

def gen_unarrowed(self, v: Val) -> str:
    # the hint for an error about value v that only some of its types support, where it is a
    # union's (or a union | None's): narrow it first; else ""
    if not is_union(unopt(v.t)):
        return ""
    if self.curfn.ll + v.v in self.wide:
        return ": copy it to a local variable, and narrow that to one of its types with isinstance() (a test does not narrow a global or a field, which a call may change)"
    return ": narrow it to one of its types first, with isinstance()"

def gen_uisinst(self, v: Val, c: Node) -> str:
    # i1: isinstance(v, c) for a union value v (or one that may be None): its tag is that of a
    # member type c names, or it is None and c names NoneType
    ms: list[str] = []
    dynamic: list[str] = []
    for m in umembers(unopt(v.t)):
        k = self.isinst(m, c)
        if k == -1 and m in self.classes and self.classes[m].tag > 0 and self.puretype(c, False):
            # puretype permits literal tuple entries whose eventual isinstance
            # check may raise. Dynamic class tests cannot silently ignore those.
            pending = [c]
            while len(pending) > 0:
                item = pending.pop()
                if item.kind == "tuple":
                    pending.extend(item.kids)
                elif item.kind == "binop" and item.s == "|":
                    pending.extend([part for part in item.kids if part.kind != "None"])
                elif self.isinst("None", item) < 0:
                    self.err("runtime reference union isinstance() requires valid type operands")
            dynamic.append(m)
            continue
        if k == -1:
            self.err("isinstance() is only supported with the builtin types and classes as its second argument")
        if k == 1 or k == -2:
            ms.append(m)
    may_none = (is_opt(v.t) or self.optional(unopt(v.t)) == unopt(v.t)) and v.v not in self.nn
    r = self.utest(v, ms, may_none)
    if may_none and self.isinst("None", c) == 1:
        r = self.scalar('or', [Val(r, 'bool'), Val(self.ptr_cmp('==', v, Val('null', 'None')).v, 'bool')])
    for m in dynamic:
        hit = self.label()
        end = self.label()
        test = self.utest(v, [m], may_none)
        before = self.cur
        self.cbr(test, hit, end)
        self.place(hit)
        match = self.obj_isinst(self.uget(Val(v.v, unopt(v.t)), m), c)
        result = self.scalar('or', [Val(r, 'bool'), Val(match.v, 'bool')])
        after = self.cur
        self.br(end)
        self.place(end)
        ph = Ins("phi", "bool", "")
        self.incoming(ph, r, before)
        self.incoming(ph, result, after)
        r = self.phi(ph)
    return r

def gen_umethod(self, o: Val, m: str, args: list[Node]) -> Val:
    # Resolve the receiver before evaluating arguments. Each expression is then
    # evaluated once; only the selected native member performs its call/defaults.
    if not self.reference_union(o.t):
        self.err("closed union method calls require narrowing with isinstance() first")
    members = umembers(unopt(o.t))
    for member in members:
        if member in self.classes and m not in self.classes[member].methods:
            self.err(f"reference union member {typestr(member)} must declare method {m}() (callable fields are not supported)")
    self.guard(self.ptr_cmp('==', o, Val('null', 'None')).v, f"AttributeError: 'NoneType' object has no attribute '{m}'")
    bound: list[Node] = []
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            self.err("reference union methods do not support unpacked arguments")
        if a.kind == "kw":
            bound.append(mk("kw", a.s, a.line, [self.vnode(self.expr(a.kids[0], ""))]))
        else:
            bound.append(self.vnode(self.expr(a, "")))
    tag = self.mload('int', o.v)
    end = self.label()
    results: list[Val] = []
    edges: list[str] = []
    narrow = dict(self.narrowed)
    for i in range(len(members)):
        hit = self.label()
        miss = self.label() if i + 1 < len(members) else ""
        if miss != "":
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(members[i])), "int")).v, hit, miss)
        else:
            self.br(hit)
        self.place(hit)
        self.narrowed = dict(narrow)
        result = self.method(self.uget(Val(o.v, unopt(o.t)), members[i]), m, bound)
        if len(results) > 0 and result.t != results[0].t:
            self.err("reference union methods must have identical return types")
        if not self.term:
            results.append(result)
            edges.append(self.cur)
            self.br(end)
        if miss != "":
            self.place(miss)
    self.narrowed = narrow
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return Val("null", "None")
    if results[0].t == "None":
        return Val("null", "None")
    ph = Ins("phi", results[0].t, "")
    for i in range(len(results)):
        self.incoming(ph, results[i].v, edges[i])
    return Val(self.phi(ph), results[0].t)

def gen_now_type(self, name: str) -> str:
    # the type local name has here: as a test or an assignment narrowed it, else its own
    return self.narrowed[name] if name in self.narrowed else self.ltype[name]

def gen_isinst_narrow(self, t: str, c: Node, truth: bool) -> str:
    # the type of a value of union type t (or t | None) where isinstance(x, c) is truth: the
    # members that are (or are not) instances of c, with None where it is not; "" where c
    # decides nothing that way
    none = is_opt(t) or self.optional(unopt(t)) == unopt(t)
    keep: list[str] = []
    for m in umembers(unopt(t)):
        r = self.isinst(m, c)
        if r == -1 or r == -3:
            return ""
        if (r == 1 or r == -2) == truth:
            keep.append(m)
    if none and (self.isinst("None", c) == 1) == truth:
        keep.append("None")
    if len(keep) == 0:
        return ""
    nt = self.union_type(keep)
    return nt if not nt.startswith("!") and nt != t else ""

def gen_holds(self, t: str, vt: str) -> str:
    # what a local of type t holds once a value of type vt is assigned to it: a T where t is
    # T | None (and vt is not None or optional), a member or fewer members where t is a union
    # (or a union | None); "" where that is t itself, nothing narrower
    if is_union(unopt(t)):
        if vt == "None" or vt == t:
            return ""
        if vt in umembers(unopt(t)) or (is_union(unopt(vt)) and len([m for m in umembers(unopt(vt)) if m not in umembers(unopt(t))]) == 0):
            return vt if not (is_opt(vt) and not is_opt(t)) else ""
        return ""
    if is_opt(t) and not is_opt(vt) and vt != "None":
        return unopt(t)
    return ""


def gen_stable(self, s: str) -> str:
    # type (or key of types) s for joins' keys, the same in every pass: a class template's
    # specialization in it is named by the types of the call that made it, not by the order
    # that numbered it (Box-2), as each specialization or instance has joins of its own
    out = ""
    w = ""
    for ch in s + " ":
        if ch in "[](),| ;=~>*?":
            out += self.stable(self.classes[w].speckey) if w in self.classes and self.classes[w].speckey != "" else w
            out += ch
            w = ""
        else:
            w += ch
    return out[: len(out) - 1]


def gen_fnkey(self, f: FnInfo) -> str:
    # function f's key for joins: its module, its def's line, its class and name and, for a
    # template's instance, its argument types (see stable)
    k = f"{f.mod}:{f.node.line}:{self.stable(f.cls)}.{f.name}"
    return k + "(" + self.stable(f.ikey) + ")" if f.inst else k


def gen_field_key(self, ci: ClassInfo, name: str) -> str:
    # the key for joins of field name of class ci: of the class that declares it (see stable)
    return f"field:{self.stable(self.field_root(ci, name).name)}.{name}"


def gen_local_hint(self, name: str) -> str:
    # the type a join of an earlier pass gave local name of the function being compiled, or ""
    return self.hints.get(f"{self.fnkey(self.curfn)}|{name}", "") if len(self.hints) > 0 else ""


def gen_join_at(self, kind: str, name: str, t: str) -> list[str]:
    # the location a value of type t is being stored to (joinkind, joinname, jointype: see
    # join_hint), set from here, as it was before (to restore after the store)
    was = [self.joinkind, self.joinname, self.jointype]
    self.joinkind = kind
    self.joinname = name
    self.jointype = t
    return was


def gen_join_hint(self, t: str, vt: str) -> bool:
    # a value of type vt that the location being stored to, whose type t was inferred (as
    # join_at set it), does not take: unless this is the last pass, a join gives the location
    # the union of both types, as if annotated (Gen.newhints, which the next pass compiles it
    # with: see Rejoin), and the store is dropped; False where the location is annotated or
    # another kind's, or the union is no type a join gives
    if self.final or self.joinkind == "" or t != self.jointype or self.drying > 0 or self.rtmode:
        return False
    key = ""
    if self.joinkind == "local":
        body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
        if self.joinname in self.curfn.params or self.joinname in self.compvars or ann_target(body, self.joinname):
            return False
        key = f"{self.fnkey(self.curfn)}|{self.joinname}"
    elif self.joinkind == "global":
        if self.joinname in self.constflags or owner(self.joinname) not in self.inits or ann_target(self.inits[owner(self.joinname)].node.kids, self.joinname):
            return False
        key = f"global:{self.joinname}"
    elif self.joinkind == "field" or self.joinkind == "return":
        key = self.joinname
    j = self.join_type(self.newhints.get(key, t), vt)
    if key != "" and (j == "" or j == t or j == self.hints.get(key, "")) and (is_list(t) or is_dict(t)) and self.join_type(t, vt) == t:
        # a list or dict of another item type, which the location's cannot be as it is: where a
        # call of a function or method without a return annotation made it, the function returns
        # the location's type, as if annotated, and makes a fresh result of it (see retval)
        e = self.joinsrc
        fs: list[FnInfo] = []  # (the function called: by its name, or a method of the class of the variable it is called on)
        if e.kind == "call" and e.kids[0].kind == "name" and e.kids[0].s in self.funcs:
            fs.append(self.funcs[e.kids[0].s])
        elif e.kind == "call" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name" and self.typed_now(e.kids[0].kids[0]):
            c = self.dry(e.kids[0].kids[0])
            if c in self.classes and e.kids[0].s in self.classes[c].methods and len([x for x in self.classes.values() if x.name != c and self.derives(x.name, c)]) == 0:
                # (no class derives from c: the call is no dispatch to methods of other classes,
                # whose returns would each need the type)
                fs.append(self.classes[c].methods[e.kids[0].s])
        if len(fs) == 1 and fs[0].node.kind == "def" and fs[0].node.kids[1].kind == "noann":
            tf = fs[0]
            rk = f"{self.fnkey(tf.insts[tf.lastikey] if tf.lastikey in tf.insts else tf)}|return"  # (the call's instance)
            if self.hints.get(rk, "") != t and self.newhints.get(rk, "") != t:
                self.newhints[rk] = t
                return True
    if key == "" or j == "" or j == t or j == self.hints.get(key, ""):
        return False
    self.newhints[key] = j
    return True


def gen_join_type(self, a: str, b: str) -> str:
    # the type of a location that holds values of types a and b, as a join gives it (join_hint):
    # their union (see joinable); for lists, dicts of one key type and tuples of one length, the
    # one of their items' joins (a display assigned to it is made of that); "" if there is none
    if is_list(a) and is_list(b) and "?" not in a and "?" not in b:
        e = self.join_type(elem(a), elem(b))
        return self.ctype("list", [e]) if e != "" else ""
    if is_dict(a) and is_dict(b) and targs(a)[0] == targs(b)[0] and "?" not in a and "?" not in b:
        e = self.join_type(targs(a)[1], targs(b)[1])
        return self.ctype("dict", [targs(a)[0], e]) if e != "" else ""
    if is_tuple(a) and is_tuple(b) and len(targs(a)) == len(targs(b)):
        ts: list[str] = []
        for i in range(len(targs(a))):
            x = targs(a)[i] if targs(a)[i] == targs(b)[i] else self.join_type(targs(a)[i], targs(b)[i])
            if x == "":
                return ""
            ts.append(x)
        return self.ctype("tuple", ts)
    if a == b:
        return a
    j = self.union_type([a, b])
    return j if not j.startswith("!") and self.joinable(j) else ""


def gen_joinable(self, t: str) -> bool:
    # can a join give a location type t: T | None, or a union of int, float, bool and str (that
    # may be None), whose operations select the member's by the tag (see unumeric)
    u = unopt(t)
    if not is_union(u):
        return is_opt(t)
    return all([m in ["int", "float", "bool", "str"] for m in umembers(u)])
