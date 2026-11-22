"""Explicit closed scalar, container and native reference unions."""
from __future__ import annotations
from src.pystachy_compiler.analysis import ann_target
from src.pystachy_compiler.diagnostics import dynamic_program, int_lists, where
from src.pystachy_compiler.ir import Ins, Val, tmpname
from src.pystachy_compiler.symbols import ClassInfo, FnInfo
from src.pystachy_compiler.names import owner
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.specs import BIG, BIGOPT, COMPLEXC, FXBIT, NONEVAR, OPTTYPES, PYMETHODS
from src.pystachy_compiler.utils import elem, has_method, is_callable, is_clsval, is_dict, is_fn, is_list, is_opt, is_sopt, is_tuple, is_union, is_vtuple, targs, tname, typestr, umembers, unopt

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

def gen_object_union(self, t: str) -> bool:
    # a union (or one | None) of a class's objects or files and of scalars (int | Decimal,
    # str | TextIO): one box, null for None as a class's value is, whose arithmetic, comparisons,
    # truth, str() and builtin calls select the member's by the tag, as a scalar union's do;
    # a method call or an attribute needs the member, as a reference union's. A complex number
    # is not one of its objects: beside scalars it is a scalar member (cx_union), and beside
    # objects and files alone a reference member (complex | C), as optional() and union_type say
    ms = umembers(unopt(t)) if is_union(unopt(t)) else []
    refs = [m for m in ms if m == "file" or (m in self.classes and m != COMPLEXC)]
    return 0 < len(refs) < len(ms) and all([m in refs or m in ["int", "float", "bool", "str"] for m in ms])

def gen_scalar_union(self, t: str) -> bool:
    return is_union(unopt(t)) and all([m in ["int", "float", "bool", "str"] for m in umembers(unopt(t))])

def gen_cx_union(self, t: str) -> bool:
    # a closed union of scalars that holds complex numbers too (int | complex, ...): its builtin
    # calls split by member (usplit), whose complex numbers the class's methods and complex_arith
    # compute, as its operators (unumeric) and equality (complex_ueq) do
    return is_union(unopt(t)) and COMPLEXC in umembers(unopt(t)) and all([m in ["int", "float", "bool", "str", COMPLEXC] for m in umembers(unopt(t))])

def gen_num_union(self, t: str) -> bool:
    # a union of numbers (int, float, bool), not None: sum() adds its values and orderings compare
    # them, an int with a float exactly (runtime.c's opv)
    return is_union(t) and all([m == "int" or m == "float" or m == "bool" for m in umembers(t)])

def gen_value_union(self, t: str) -> bool:
    return is_union(unopt(t)) and all([m in ["int", "float", "bool", "str", COMPLEXC] or is_list(m) or is_dict(m) for m in umembers(unopt(t))])

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
    calls = op == "truth" and is_union(unopt(v.t)) and all([m in ["int", "float", "bool", "str"] or is_list(m) or is_dict(m) or is_callable(m) for m in umembers(unopt(v.t))])
    objects = self.object_union(v.t) and op != "len"  # (each member's own, an object's by its methods; repr() too)
    if not self.value_union(v.t) and not calls and not objects:
        if len([m for m in umembers(unopt(v.t)) if is_callable(m)]) > 0:
            self.err("a union that holds a Callable requires narrowing with isinstance() or callable() first")
        self.err("closed reference union operations require narrowing with isinstance() first")
    t = "bool" if op == "truth" else "int" if op == "len" else "str"
    if op == "len":
        self.notnone(v, "TypeError: object of type 'NoneType' has no len()")
    end = self.label()
    ph = Ins("phi", t, "")
    if (is_opt(v.t) or (objects and v.v not in self.nn)) and op != "len":
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
        if is_callable(members[i]):
            self.incoming(ph, "true", self.cur)  # (a function is true)
            self.br(end)
            if nxt != "":
                self.place(nxt)
            continue
        if op == "len" and not (members[i] == "str" or is_list(members[i]) or is_dict(members[i])):
            # (a number: CPython's error for that object, as len() of it alone is rejected)
            self.raise_("TypeError", self.sconst(f"object of type '{tname(members[i])}' has no len()"))
            if nxt != "":
                self.place(nxt)
            continue
        if op == "repr" and members[i] not in self.classes:
            result = self.repr(self.scalar_view(v))  # (the runtime reads the box's own tag)
        else:
            item = self.uget(Val(v.v, unopt(v.t)), members[i])
            result = Val(self.truth(item), "bool") if op == "truth" else self.builtin("len", [self.vnode(item)], "") if op == "len" else self.repr(item) if op == "repr" else self.to_str(item)
        self.incoming(ph, result.v, self.cur)
        self.br(end)
        if nxt != "":
            self.place(nxt)
    self.place(end)
    return Val(self.phi(ph), t)

# ---- a closed value union's own operations (None | bool | int | float | str | list | dict, as
# json.JSONValue is): the member that the box's tag names performs them, natively, and a member
# that cannot raises the error CPython raises for that object. Each tag is tested by a branch of
# its own, so that the payload's read follows the test of the tag it belongs to (union_proof.py).

def gen_ureject(self, o: Val, keep: list[str], kind: str, text: str, none: str = "") -> Val:
    # o, a closed union's value that may be None, where only a value of one of types keep goes
    # on: None and the other members raise kind (an exception class) with text, in which {} is
    # the type's name (none: the whole text for None, where the caller has one). The value, as
    # the union it holds
    t = unopt(o.t)
    o = self.unone(o, none if none != "" else text.replace("{}", "NoneType"), kind)
    bad = [m for m in umembers(t) if m not in keep]
    if len(bad) == 0:
        return o
    tag = self.mload('int', o.v)
    for m in bad:
        arm = self.label()
        nxt = self.label()
        self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(m)), "int")).v, arm, nxt)
        self.place(arm)
        self.raise_(kind, self.sconst(text.replace("{}", tname(m))))
        self.place(nxt)
    return o

def gen_uonly(self, o: Val, m: str, kind: str, text: str) -> Val:
    # the value of member type m that closed union value o holds: None and the other members
    # raise, as ureject's do
    t = unopt(o.t)
    o = self.unone(o, text.replace("{}", "NoneType"), kind)
    tag = self.mload('int', o.v)
    ok = self.label()
    bad = self.label()
    self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(m)), "int")).v, ok, bad)
    self.place(bad)
    others = [x for x in umembers(t) if x != m]
    for i in range(len(others)):
        if i + 1 < len(others):
            arm = self.label()
            nxt = self.label()
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(others[i])), "int")).v, arm, nxt)
            self.place(arm)
            self.raise_(kind, self.sconst(text.replace("{}", tname(others[i]))))
            self.place(nxt)
        else:
            self.raise_(kind, self.sconst(text.replace("{}", tname(others[i]))))
    self.place(ok)
    return self.uget(Val(o.v, t), m)

def gen_uiter_items(self, t: str) -> list[str]:
    # the types of the items a loop takes from a value of closed union t: a list member's items,
    # a dict member's keys, a str member's characters
    items: list[str] = []
    for m in umembers(t):
        if is_list(m):
            items.append(elem(m))
        elif is_dict(m):
            items.append(targs(m)[0])
        elif m == "str":
            items.append("str")
    return items

def gen_uiterable(self, v: Val, msg: str) -> Val:
    # what a for loop steps through where v is a closed value union's (Gen.iterable): the value
    # itself, known to hold a list, a dict or a str. None raises msg and a number CPython's
    # TypeError here, where the loop's iterator is made, before another sequence of a zip() is
    # asked for an item. for_seq then takes each item by the tag (useq_used, useq_next)
    t = unopt(v.t)
    items = self.uiter_items(t)
    if len(items) == 0 or self.rtmode:
        self.err(f"cannot iterate over {typestr(v.t)}")
    it = self.union_type(items)
    if it.startswith("!"):
        self.err(f"iterating over a closed union value ({typestr(v.t)}) is not supported ({it[1:]}): narrow it with isinstance() first")
    keep = [m for m in umembers(t) if is_list(m) or is_dict(m) or m == "str"]
    return self.ureject(v, keep, "TypeError", "'{}' object is not iterable", msg[11:] if msg.startswith("TypeError: ") else msg)

def gen_useq_used(self, s: Val) -> str:
    # what the iterator over closed union value s (uiterable) records when it is made, as
    # seq_start does for each type: a dict's size and a str's length, 0 for a list
    members = [m for m in umembers(s.t) if is_list(m) or is_dict(m) or m == "str"]
    tag = self.mload('int', s.v)
    end = self.label()
    ph = Ins("phi", "int", "")
    for m in members:
        arm = self.label()
        nxt = self.label()
        self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(m)), "int")).v, arm, nxt)
        self.place(arm)
        self.incoming(ph, "0" if is_list(m) else self.mload('int', self.uget(s, m).v), self.cur)
        self.br(end)
        self.place(nxt)
    self.unreachable()  # (another member raised: uiterable)
    self.place(end)
    return self.phi(ph)

def gen_useq_next(self, s: Val, pos: str, used: str, i: str, le: str) -> Val:
    # the next item of closed union value s in a for loop (for_seq), which goes to le at its
    # end: the list's, by index against its current length, the dict's, by entry, failing if it
    # changed size, or the str's, by its byte cursor, each as that type's own loop takes it
    # (pos: the entry or cursor; used: useq_used's; i: the loop's count), as a value of the
    # union of their item types (uiter_items)
    it = self.union_type(self.uiter_items(s.t))
    members = [m for m in umembers(s.t) if is_list(m) or is_dict(m) or m == "str"]
    tag = self.mload('int', s.v)
    end = self.label()
    ph = Ins("phi", it, "")
    for m in members:
        arm = self.label()
        nxt = self.label()
        self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(m)), "int")).v, arm, nxt)
        self.place(arm)
        x = self.uget(s, m)
        go = self.label()
        j = i
        if is_list(m):
            self.cbr(self.num_cmp('<', Val(i, "int"), Val(self.list_len(x), "int")).v, go, le)
            self.place(go)
        elif is_dict(m):
            j = self.rt("pys_dict_next", "i64", [f"ptr {x.v}", f"i64 {self.mload('int', pos)}", f"i64 {used}", f"i64 {i}"])
            self.cbr(self.num_cmp('>=', Val(j, "int"), Val('0', "int")).v, go, le)
            self.place(go)
            self.mstore('int', self.scalar('add', [Val(j, 'int'), Val('1', 'int')]), pos)
        else:
            j = self.mload('int', pos)
            self.cbr(self.int_ucmp('<', Val(j, "int"), Val(used, "int")).v, go, le)
            self.place(go)
            self.mstore('int', self.rt("pys_text_next", "i64", [f"ptr {x.v}", f"i64 {j}"]), pos)
        item = self.coerce(self.seq_item(x, j, "")[0], it)
        self.incoming(ph, item.v, self.cur)
        self.br(end)
        self.place(nxt)
    self.unreachable()  # (another member raised: uiterable)
    self.place(end)
    return Val(self.phi(ph), it)

def umethod_mismatch(m: str, member: str, ts: list[str]) -> str:
    # what o.m(args) does where a closed union's value o is of type member and its positional
    # arguments are of builtin types ts, for the methods that a list shares with a dict or a
    # str but that take other arguments (pop, index, count): "" for the member's own call;
    # "TypeError: ..." for CPython's error; "KeyError" where a dict has no key of that type;
    # "default" where its pop() then gives the default
    plain = all([t in ["None", "bool", "int", "float", "str"] or is_list(t) or is_dict(t) for t in ts])
    if not plain:
        return ""
    if is_list(member) and m == "pop":
        if len(ts) > 1:
            return f"TypeError: pop expected at most 1 argument, got {len(ts)}"
        if len(ts) == 1 and ts[0] != "int" and ts[0] != "bool":
            return f"TypeError: '{tname(ts[0])}' object cannot be interpreted as an integer"
    if is_dict(member) and m == "pop":
        if len(ts) == 0:
            return "TypeError: pop expected at least 1 argument, got 0"
        if len(ts) > 2:
            return f"TypeError: pop expected at most 2 arguments, got {len(ts)}"
        if is_list(ts[0]) or is_dict(ts[0]):
            return f"TypeError: unhashable type: '{tname(ts[0])}'"
        if (targs(member)[0] == "str") != (ts[0] == "str"):
            return "KeyError" if len(ts) == 1 else "default"
    if is_list(member) and m == "count" and len(ts) != 1:
        return f"TypeError: list.count() takes exactly one argument ({len(ts)} given)"
    if member == "str" and (m == "count" or m == "index") and len(ts) > 0 and ts[0] != "str":
        return f"TypeError: must be str, not {tname(ts[0])}"
    return ""

def gen_uvalue_method(self, o: Val, m: str, args: list[Node], want: str, resultsoft: bool) -> Val:
    # o.m(args) of a closed value union's value: the method of the member that its tag names. A
    # member whose type has no such method in CPython (and None) raises AttributeError, before
    # the arguments are evaluated, as CPython looks the attribute up first. Where one member has
    # it, the call is its own; where several do (pop, copy, index), each argument is evaluated
    # once and the results are their union
    t = unopt(o.t)
    if len([x for x in umembers(t) if is_list(x)]) > 1 or len([x for x in umembers(t) if is_dict(x)]) > 1:
        # (lists, or dicts, of several item types: no one call's arguments suit them all)
        self.err("closed union method calls require narrowing with isinstance() first")
    havers: list[str] = []
    for x in umembers(t):
        base = "list" if is_list(x) else "dict" if is_dict(x) else x
        if base in PYMETHODS and m in PYMETHODS[base]:
            if base == "bool" and has_method("int", m):
                base = "int"  # (a bool's are an int's: the call is of its int, below)
            if not (has_method(base, m) or (base == "str" and (m == "format" or m == "format_map"))):
                self.err(f"{base}.{m}() is not supported, and a closed union's value ({typestr(o.t)}) may be a {base}: narrow it with isinstance() first")
            havers.append(x)
    if len(havers) == 0:
        self.err(f"no member of {typestr(o.t)} has a method {m}(): closed union method calls select a str, list, dict or number member's method")
    missing = f"'{{}}' object has no attribute '{m}'"
    if len(havers) == 1:
        only = self.uonly(o, havers[0], "AttributeError", missing)
        return self.method(self.as_int(only) if only.t == "bool" else only, m, args, want, resultsoft)
    o = self.ureject(o, havers, "AttributeError", missing)
    bound: list[Node] = []
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            self.err("closed union methods do not support unpacked arguments: narrow the value with isinstance() first")
        if a.kind == "kw":
            bound.append(mk("kw", a.s, a.line, [self.vnode(self.expr(a.kids[0], ""))]))
        else:
            bound.append(self.vnode(self.expr(a, "")))
    tag = self.mload('int', o.v)
    end = self.label()
    results: list[Val] = []
    edges: list[str] = []
    narrow = dict(self.narrowed)
    for x in havers:
        arm = self.label()
        nxt = self.label()
        self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(self.utag(x)), "int")).v, arm, nxt)
        self.place(arm)
        self.narrowed = dict(narrow)
        result = Val("null", "None")
        problem = umethod_mismatch(m, x, [self.expr(b, "").t for b in bound if b.kind != "kw"])
        if problem.startswith("TypeError: "):
            self.raise_("TypeError", self.sconst(problem[11:]))
        elif problem == "KeyError":
            self.raise_("KeyError", self.repr(self.expr(bound[0], "")).v, self.sconst("KeyError"))
        elif problem == "default":
            result = self.expr(bound[1], "")
        else:
            result = self.method(self.as_int(self.uget(o, x)) if x == "bool" else self.uget(o, x), m, bound)
        if not self.term:
            results.append(result)
            edges.append(self.cur)
            self.br(end)
        self.place(nxt)
    self.unreachable()  # (another member raised: ureject)
    self.narrowed = narrow
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return Val("null", "None")
    if all([r.t == "None" for r in results]):
        return Val("null", "None")
    rt = self.union_type([r.t for r in results])
    if rt.startswith("!"):
        self.err(f"unsupported call of {m}() on {typestr(o.t)}: its members' results ({', '.join([typestr(r.t) for r in results])}) have no union; narrow it with isinstance() first")
    ph = Ins("phi", rt, "")
    for i in range(len(results)):
        r = self.convert_at(results[i], rt, edges[i])
        self.incoming(ph, r.v, self.convedge)
    return Val(self.phi(ph), rt)

def gen_scalar_view(self, v: Val) -> Val:
    # The box of a union of objects and scalars, where its tag is one of the scalars', as a
    # union of scalars alone: the same pointer, since a union's box is also one of a union of
    # more types (utag). The runtime then formats it by its tag, as it does a scalar union's:
    # no payload is read here, so none goes untyped to a descriptor's slot (docs/typed-ir.md).
    scalars = [m for m in umembers(unopt(v.t)) if m == "int" or m == "float" or m == "bool" or m == "str"]
    if len(scalars) == 1:
        scalars.append("int" if scalars[0] == "str" else "str")  # (a tag the box never has)
    return Val(v.v, self.union_type(scalars))

def gen_uequal(self, op: str, a: Val, b: Val) -> Val:
    # Both operands are already evaluated. Boxes of a narrower union keep their
    # pointers and tags; a concrete scalar is boxed only at this dynamic boundary.
    # A tuple of promoting ints compares as its 64-bit ints, as a union holds them (bigints.py).
    a = self.big_tuple_narrow(a) if is_tuple(a.t) and BIG in a.t else a
    b = self.big_tuple_narrow(b) if is_tuple(b.t) and BIG in b.t else b
    t = self.union_type([a.t, b.t])
    if t.startswith("!") and self.ueq_type(a.t) and self.ueq_type(b.t):
        # A tuple need not become a union member just to compare with a union.
        # Each descriptor keeps its own layout, including optional/union boxes.
        r = self.rt("pys_eq_pair", "i64", ["i64 " + self.to_slot(a), "i64 " + self.to_slot(b), f"ptr {self.sconst(self.desc(a.t, '=='))}", f"ptr {self.sconst(self.desc(b.t, '=='))}"])
        return self.num_cmp('!=' if op == '==' else '==', Val(r, "int"), Val('0', "int"))
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
    if is_callable(t):
        return ""  # (a function value, as a Callable variable holds it: a pointer to its code and environment)
    return f"{typestr(t)} in a closed union is not supported (use scalar, list/dict or native class/file types)"

def gen_union_type(self, ts: list[str]) -> str:
    # the type of a value of one of types ts (None among them: T | None): the type, for one, else
    # union[...] of them, nested unions and optionals flattened, in sorted order; "!" and why not
    ms: list[str] = []
    none = False
    if "dyn" in ts:
        return "dyn"  # (Any | T: a dynamic value holds any of them)
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
    if BIG in ms and "int" in ms:
        ms.remove("int")  # (a promoting int holds a 64-bit one: bigints.py)
    if len(ms) > 1 and BIG in ms and BIGOPT in ts and BIG not in ts:
        # (an int | None of a module that opts in, with other types: their union, which holds a 64-bit
        # int, as the 64-bit int | None it holds makes one: bigints.py)
        ms[ms.index(BIG)] = "int"
    if len(ms) == 0:
        return "None"
    if len(ms) == 1:
        r = self.optional(ms[0]) if none else ms[0]
        return r if r != "" else f"!None/Optional is only supported for {OPTTYPES}, not {typestr(ms[0])}"
    for m in ms:
        if self.umember_problem(m) != "":
            return "!" + self.umember_problem(m)
    if len([m for m in ms if is_callable(m)]) > 1:
        return "!a closed union holds one Callable type: callable() cannot tell two apart"
    refs = [m for m in ms if m == "file" or m in self.classes]
    if COMPLEXC in refs and len(refs) != len(ms):
        # (a complex number is a scalar member beside scalars or containers, and a reference
        # member beside only objects and files: complex | C)
        refs.remove(COMPLEXC)
    if len(refs) > 0:
        # (scalars may be members beside them, each under its own tag: object_union; but not a
        # complex number as well, which is a scalar member beside scalars, see above)
        others = [m for m in ms if m not in refs and m not in ["int", "float", "bool", "str"]]
        if len([m for m in others if m != COMPLEXC]) > 0:
            return "!reference unions cannot mix native references with container members"
        if len(others) > 0:
            return "!reference unions cannot mix native references with complex and scalar members"
        if len(refs) > 4:
            return "!reference unions support at most four members"
        for a in refs:
            for b in refs:
                if a != b and a in self.classes and b in self.classes and (self.derives(a, b) or b in self.classes[a].overlaps):
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

def gen_ubox(self, v: Val, m: str, u: str) -> str:
    # v, of member type m, as a box of union u (a class's object that may be None: null)
    b = self.rt("pys_ubox", "ptr", [f"i64 {self.utag(m)}", "i64 " + self.to_slot(Val(v.v, m), False, True)], t=u)
    if m not in self.classes or v.v in self.nn:
        return b
    return self.select(self.ptr_cmp('==', v, Val('null', 'None')).v, Val('null', u), Val(b, u))

def gen_uget(self, u: Val, m: str) -> Val:
    # the value a union's box u holds, known to be of member type m
    i = Ins("union.payload", "*" + m, m)
    i.a = [u]
    self.put(i, 2)
    return self.from_slot(tmpname(i.r[1]), m).identity(u)

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
    tag = tmpname(i.r[0])
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
        return Val(v.v, t).identity(v)
    calls = [m for m in ms if is_callable(m)]
    if src not in ms and len(calls) == 1 and (is_fn(src) or is_callable(src)):
        # a function where the union's Callable member is expected: the value a Callable variable
        # holds (to_callable, with its errors), in the union's box
        v = self.coerce(v, calls[0], what)
        src = calls[0]
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
        if src == COMPLEXC and not none_ok and v.v not in self.nn:
            # (a complex number's object may be None, a complex | None's, which a union without
            # None holds no box for: Pystachy's TypeError, where CPython stores the None)
            self.notnone(v, f"TypeError: a value used as {typestr(t)} is None; annotate it {typestr(t)} | None")
            self.nn[v.v] = True
        return Val(self.ubox(v, src, t), t).identity(v)
    if not none_ok:
        if self.join_hint(t, v.t):
            return Val("undef", t)  # (see join_hint)
        self.err(f"{what if what != '' else 'a value used as ' + typestr(t)} may be None ({typestr(v.t)}); test it with 'is not None' first")
    # an optional value: None stays null, any other value is boxed (with no branch, so that
    # convert_in can make it at the end of a block); an int | None's value is in its box
    return Val(self.rt("pys_ubox_opt", "ptr", [f"i64 {self.utag(src)}", f"ptr {v.v}", f"i64 {1 if is_sopt(v.t) else 0}"]), t).identity(v)

def gen_narrow_val(self, v: Val, nt: str) -> Val:
    # v, a local's value of its own type, as of the type nt a test or an assignment narrowed it
    # to (see narrows): an optional's value, a union's member, a union of fewer members,
    # or an ordinary class pointer whose runtime class test proved a derived layout
    if nt == v.t:
        return v
    if v.t == "dyn":
        return self.dyn_narrowed(v, nt)  # (a dynamic value's box, which a test proved holds an nt)
    if self.is_iface(v.t) and nt in self.classes and not self.is_iface(nt):
        return self.iface_narrowed(v, nt)  # (an interface's box, whose object a test proved an nt)
    if v.t in self.classes and nt in self.classes and (self.derives(nt, v.t) or nt in self.classes[v.t].overlaps):
        return Val(v.v, nt)
    if v.t in self.classes and is_union(nt) and len([m for m in umembers(nt) if m not in self.classes]) == 0:
        return self.class_union(v, nt)  # (isinstance(x, (A, B)) proved it an A or a B: narrows)
    if not is_union(unopt(v.t)):
        return self.deref(v)  # (an optional known not to be None)
    if nt == "None":
        return Val("null", "None")
    if is_union(unopt(nt)):
        return Val(v.v, nt).identity(v)  # (the same box)
    m = unopt(nt)
    if m not in self.classes and not is_opt(nt):
        return self.uget(Val(v.v, unopt(v.t)).identity(v), m)
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
    return Val(self.phi(ph), nt).identity(v)

def gen_class_union(self, v: Val, nt: str) -> Val:
    # v, an object of a class (not None), as a value of union nt of classes derived from v's,
    # which a test proved it is one of: boxed as the member its class derives from, as found
    # by its class tag (the last member's where no other's is: the test excluded the rest)
    ms = umembers(nt)
    tag = self.mload('int', v.v)
    end = self.label()
    ph = Ins("phi", nt, "")
    for i in range(len(ms)):
        m = ms[i]
        if i + 1 < len(ms):
            hit = "false"
            for c in self.classes.values():
                if c.tag > 0 and self.derives(c.name, m):
                    x = self.num_cmp('==', Val(tag, "int"), Val(str(c.tag), "int")).v
                    hit = x if hit == "false" else self.scalar('or', [Val(hit, 'bool'), Val(x, 'bool')])
            yes = self.label()
            no = self.label()
            self.cbr(hit, yes, no)
            self.place(yes)
            self.incoming(ph, self.ubox(Val(v.v, m), m, nt), self.cur)
            self.br(end)
            self.place(no)
        else:
            self.incoming(ph, self.ubox(Val(v.v, m), m, nt), self.cur)
            self.br(end)
    self.place(end)
    return Val(self.phi(ph), nt).identity(v)

def gen_unarrowed(self, v: Val) -> str:
    # the hint for an error about value v that only some of its types support, where it is a
    # union's (or a union | None's): narrow it first; else ""
    if not is_union(unopt(v.t)):
        return ""
    if self.curfn.ll + v.v in self.wide:
        return ": copy it to a local variable, and narrow that to one of its types with isinstance() (a test does not narrow a global, nor a field past a call or a store that may change it)"
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

# ---- attribute paths that a test narrows (x.a, self.a.b)
# A test of an attribute read narrows the reads of that attribute that follow it, as a test of a
# local narrows the local: isinstance(e.node, T) and then e.node.name. CPython reads the
# attribute again each time, so that holds only while nothing can have stored the attribute. A
# fact is an entry of Gen.narrowed whose key is the path, and so follows the branches and joins
# as a local's does; its value names the narrowed type, the value the test read (a narrowed read
# is that very value where its block is on every way here, path_dominates, and else the field's
# load again, which then holds it: path_again), the attribute's own type, and when it was made
# (path_fact). What may have changed the attribute since voids the fact (path_live):
# - an operation that may run code of the program or write objects' fields (Gen.pcall): a call,
#   a generator's resume or yield, a runtime function with U, U? or wO, a store to a global
#   (which a class attribute is) and any store this file cannot name;
# - a store to an attribute of that name on any object (Gen.pstamps, by setfield);
# - a store to the path's local;
# - a loop, whose body runs again after what follows a read in it (path_void in forget).
# Only fields are paths: a property's read is a call. An if statement's branches, a conditional
# expression's arms and a failing assertion's message do not follow one another, so what one
# does is taken back for the other (path_undo) and holds after them where it may have run. A
# branch that ends in a raise, break or return is followed by other code of the function all the
# same: an except clause or a finally block, which start with no fact (unnarrowed), and the code
# after a loop, where every fact is void (loop).


def gen_path_key(self, n: Node) -> str:
    # "x.a.b" for a chain of attribute reads on local x, which only this function's own stores
    # rebind (no global, nor a local a closure assigns); else ""
    if n.kind != "attr" or len(n.kids) != 1:
        return ""
    b = n.kids[0]
    if b.kind == "name":
        if b.s not in self.ltype or b.s in self.nlw or self.is_global(b.s):
            return ""
        return b.s + "." + n.s
    k = self.path_key(b)
    return k + "." + n.s if k != "" else ""

def gen_path_void(self) -> None:
    # code of the program may run here, or run again: every fact made before is void
    self.pseq += 1
    self.pcall = self.pseq

def gen_path_stamp(self, key: str) -> None:
    # a store to an attribute ("a" and its name) or to a local's slot ("l" and its register)
    self.pseq += 1
    old = self.pstamps.get(key, 0)
    self.plogk.append(key)
    self.plogv.append(old)
    self.pstamps[key] = self.pseq

def gen_path_event(self, i: Ins, kind: int) -> None:
    # instruction i, as it is added, may change what a path's read gives (PATH_OPS: kind)
    if kind == 1:
        self.path_void()
    elif kind == 2:
        f = self.rtfns[i.s]
        if f.q or (f.fx & (FXBIT["U"] | FXBIT["wO"])) != 0:
            self.path_void()
    else:
        a = i.a[0].v
        if a.startswith("%") and "." in a:
            self.path_stamp("l" + a)  # (a local's slot, or its flag: slot_register)
        elif self.pfield != "" and not a.startswith("@"):
            self.path_stamp("a" + self.pfield)
        else:
            self.path_void()  # (also a global's: a class attribute, which an object without its own reads)

def gen_path_live(self, key: str, born: int, session: int) -> bool:
    # has nothing that may change path key's value happened since born, in code that is kept
    # (session: the dry() that made the fact, if one did, is still typing)
    if self.pcall > born or session not in self.psess:
        return False
    parts = key.split(".")
    if self.pstamps.get("l" + self.lreg.get(parts[0], ""), 0) > born or self.pstamps.get("l" + self.lflag.get(parts[0], ""), 0) > born:
        return False
    for a in parts[1:]:
        if self.pstamps.get("a" + a, 0) > born:
            return False
    return True

def gen_path_mark(self) -> int:
    return len(self.plogk)

def gen_path_undo(self, mark: int, keys: list[str], vals: list[int]) -> None:
    # takes back the stamps made since mark (path_mark), which are those of code that the code
    # compiled next does not follow (an if statement's other branch); keys and vals receive
    # them, for path_redo
    while len(self.plogk) > mark:
        k = self.plogk.pop()
        old = self.plogv.pop()
        if k not in keys:
            keys.append(k)
            vals.append(self.pstamps[k])
        self.pstamps[k] = old

def gen_path_redo(self, keys: list[str], vals: list[int]) -> None:
    # the stamps path_undo took back hold again, where the code they are of may have run
    for j in range(len(keys)):
        if self.pstamps.get(keys[j], 0) < vals[j]:
            self.plogk.append(keys[j])
            self.plogv.append(self.pstamps.get(keys[j], 0))
            self.pstamps[keys[j]] = vals[j]

def gen_path_read(self, n: Node, v: Val, born: int, block: str) -> None:
    # attribute path n was read, as a field's load (v, of the field's type) in block, or as a
    # fact's value
    self.preadn.append(n)
    self.preadv.append(v)
    self.preads.append(born)
    self.preadb.append(block)

def gen_path_dominates(self, block: str) -> bool:
    # does every way from the function's entry to the block being compiled pass block (where a
    # fact's value was read: its uses there are then valid)? Of the blocks and branches made so
    # far, which decide it: what is made later branches forward, or back to a loop's start,
    # which the loop's code is reached through. A test that and/or compile to one value read
    # its later operands in blocks that do not (path_value then reads the field again)
    if block == self.cur:
        return True
    if self.drying > 0:
        return True  # (its blocks are dropped)
    key = block + ">" + self.cur
    if key in self.pdoms:
        return self.pdoms[key]
    succs: dict[str, list[str]] = {}
    for b in self.fn.blocks:
        out: list[str] = [b.handler] if b.handler != "" else []
        if len(b.code) > 0:
            out.extend(b.code[len(b.code) - 1].b)
        succs[b.label] = out
    entry = self.fn.blocks[0].label
    r = False
    if entry == block:
        r = True
    else:
        # reached at all, and not without block
        for avoid in ["", block]:
            seen: dict[str, bool] = {entry: True}
            todo = [entry]
            hit = False
            while len(todo) > 0:
                l = todo.pop()
                if l == self.cur:
                    hit = True
                    break
                for x in succs.get(l, []):
                    if x != avoid and x not in seen:
                        seen[x] = True
                        todo.append(x)
            if avoid == "" and not hit:
                break  # (no way here yet: not known)
            r = avoid != "" and not hit
    self.pdoms[key] = r
    return r

def gen_path_seen(self, n: Node) -> int:
    # where the statement being compiled read attribute path n and each attribute before it
    # (so that each is a field: a property's read is a call, and is not recorded), or -1
    at = -1
    for j in range(len(self.preadn) - 1, -1, -1):
        if self.preadn[j] is n:
            at = j
            break
    b = n.kids[0]
    if at < 0 or (b.kind == "attr" and self.path_seen(b) < 0):
        return -1
    return at

def path_fact(nt: str, v: Val, born: int, session: int, block: str) -> str:
    # (its last part: "1" for a number that has an identity for Any values, which is read with
    # its box each time: path_again, dynamic.py)
    return nt + "\t" + v.v + "\t" + v.t + "\t" + str(born) + "\t" + str(session) + "\t" + block + "\t" + ("1" if v.idslot != "" or v.idfrom != "" else "0")

def gen_path_type(self, key: str, out: dict[str, str], t: str) -> str:
    # the type path key has here: as out or a live fact narrowed it, else its field's type t
    f = out[key] if key in out else self.narrowed.get(key, "")
    if f == "":
        return t
    ps = f.split("\t")
    return ps[0] if key in out or self.path_live(key, int(ps[3]), int(ps[4])) else t

def gen_path_value(self, n: Node, key: str) -> Val:
    # the read of attribute path n where narrowed has a fact for it: the value the test read, as
    # of the type it narrowed to; Val("", "") where the fact is void, or where that value is not
    # at hand here (path_dominates: the field is read again, path_again)
    ps = self.narrowed[key].split("\t")
    born = int(ps[3])
    if not self.path_live(key, born, int(ps[4])) or ps[6] == "1" or not self.path_dominates(ps[5]):
        return Val("", "")
    v = Val(ps[1], ps[2])
    self.path_read(n, v, born, ps[5])
    return self.narrow_val(v, ps[0])

def gen_path_again(self, n: Node, key: str, v: Val) -> Val:
    # v, attribute path n's field read again where a fact, live before that read, has a value that
    # is not at hand (path_value): nothing has stored the attribute since the test, so it holds the value the
    # test read, of the type it narrowed to, which the IR is told by a test of it (a payload's
    # read needs its tag's test: union_proof.py)
    ps = self.narrowed[key].split("\t")
    born = int(ps[3])
    nt = ps[0]
    if v.t != ps[2]:
        return v
    self.path_read(n, v, born, self.cur)
    if v.idfrom != "" and v.t != BIGOPT and (is_opt(v.t) or is_union(v.t)):
        return self.dyn_unbox(Val(v.idfrom, "dyn"), nt).identity(v)  # (as a local's narrowed read: Gen.read)
    if v.t in self.classes:
        return self.narrow_val(v, nt)  # (the same pointer, of the class its test proved)
    if is_union(unopt(v.t)) and nt != "None" and not is_opt(nt) and not is_union(nt):
        ok = self.utest(v, [nt], is_opt(v.t) or self.reference_union(v.t) or self.object_union(v.t))
    elif is_opt(v.t) and not is_union(unopt(v.t)) and nt == unopt(v.t):
        ok = self.ptr_cmp('!=', v, Val('null', 'None')).v
    else:
        return v  # (a narrower union, or None: as the field's type here)
    # (no code reaches the failing branch while path_live is right; it is an error, not an
    # unreachable, so that a mistake there cannot read one type's payload as another's)
    self.guard(self.scalar('xor', [Val(ok, 'bool'), Val('true', 'bool')]), "SystemError: an attribute that a test narrowed changed before this read")
    return self.narrow_val(v, nt)

def gen_narrows_path(self, n: Node, test: str, c: Node, truth: bool, out: dict[str, str]) -> None:
    # narrows, for a test of attribute path n that the statement has just read: test "" (its
    # truth), "none" (n is not None), "isinstance" (of c) or "callable"
    key = self.path_key(n)
    at = self.path_seen(n) if key != "" else -1
    if at < 0:
        return
    v = self.preadv[at]
    born = self.preads[at]
    block = self.preadb[at]
    session = self.psess[len(self.psess) - 1]
    if not self.path_live(key, born, session):
        return
    t = self.path_type(key, out, v.t)
    nt = ""
    if test == "" or test == "none":
        nt = unopt(t) if truth and is_opt(t) else ""
    elif test == "callable":
        nt = self.callable_narrow(t, truth) if is_union(unopt(t)) else ""
    elif is_union(unopt(t)):
        nt = self.isinst_narrow(t, c, truth)
    elif truth and t in self.classes and self.classes[t].tag > 0 and c.kind == "name" and c.s in self.classes and (self.derives(c.s, t) or c.s in self.classes[t].overlaps):
        nt = c.s  # (the class its runtime class test proved: narrows)
    elif self.isinst(t, c) == (-2 if truth else -3):
        nt = unopt(t)
    if nt != "" and nt != t:
        out[key] = path_fact(nt, v, born, session, block)

def gen_narrows_paths(self, n: Node, truth: bool, out: dict[str, str]) -> None:
    # narrows, of the attribute paths alone (an if statement's else branch, whose facts are made
    # where the test has just been read)
    k = n.kind
    if k == "unary" and n.s == "not":
        self.narrows_paths(n.kids[0], not truth, out)
    elif k == "boolop" and (n.s == "and") == truth:
        self.narrows_paths(n.kids[0], truth, out)
        self.narrows_paths(n.kids[1], truth, out)
    else:
        self.narrows_leaf(n, truth, out)

def gen_narrows_leaf(self, n: Node, truth: bool, out: dict[str, str]) -> None:
    # narrows, for a test that is no not/and/or: of an attribute path, if it is of one
    k = n.kind
    if k == "attr":
        self.narrows_path(n, "", n, truth, out)
    elif k == "cmp" and len(n.kids) == 2 and n.kids[1].kind == "None" and n.kids[0].kind == "attr" and (n.s == "is not" or n.s == "!=" or n.s == "is" or n.s == "=="):
        self.narrows_path(n.kids[0], "none", n, (n.s == "is not" or n.s == "!=") == truth, out)
    elif k == "call" and len(n.kids) == 3 and n.kids[0].kind == "name" and n.kids[0].s == "isinstance" and n.kids[1].kind == "attr" and not self.bound("isinstance"):
        self.narrows_path(n.kids[1], "isinstance", n.kids[2], truth, out)
    elif k == "call" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s == "callable" and n.kids[1].kind == "attr" and not self.bound("callable"):
        self.narrows_path(n.kids[1], "callable", n, truth, out)


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


def field_home(self, ci: ClassInfo, name: str) -> ClassInfo:
    # the class that declares field name of class ci (field_root): of a class template's
    # specialization, the template, where its body annotates the field float, int or str (its
    # specializations share that annotation, and so the join of a value given to it: ann_takes)
    root = self.field_root(ci, name)
    return self.classes[root.origin] if root.origin != "" and name in self.classes[root.origin].fann else root


def gen_field_key(self, ci: ClassInfo, name: str) -> str:
    # the key for joins of field name of class ci: of the class that declares it (see stable)
    return f"field:{self.stable(field_home(self, ci, name).name)}.{name}"


FLOATAT = "float:at"  # (no location's key: where the program first gave an int to one annotated float)
MEMBERAT = "member:at"  # (and where it first gave an enum member to one annotated int or str, its types)
ANNTYPES = ["float", "int", "str"]  # (the annotations whose locations join: ann_takes)


def float_takes(vt: str) -> bool:
    # is vt the type of a number that a location annotated float holds too, as it is: an int (a
    # promoting one as well) or a bool, which PEP 484 accepts where a float is expected and
    # CPython stores unconverted, or a union of numbers, as such a location has once it joined.
    # Only a store that was an error joins one (join_hint), which then is an int | float (or a
    # bool | float, ...), as if annotated so; what holds only floats keeps its type
    return vt == "int" or vt == "bool" or vt == BIG or (is_union(vt) and all([m == "int" or m == "float" or m == "bool" for m in umembers(vt)]))


def member_takes(self, t: str, vt: str) -> bool:
    # is vt the type of a member of an enum class whose objects are also CPython's ints (IntEnum,
    # IntFlag) or strs (StrEnum), where t is that type (int or str: enum_builtin), or a union of
    # such members and t: a location annotated t holds one as it is, as CPython stores it, and its
    # class, repr(), type() and isinstance() stay the member's. Only a store that was an error
    # joins one (join_hint): the location then holds a union of both, an int | C, as if annotated
    # so; what holds only ints or strs keeps its type
    if is_union(vt):
        return len([m for m in umembers(vt) if m != t and not member_takes(self, t, m)]) == 0
    return (t == "int" or t == "str") and vt in self.classes and self.enum_builtin(vt) == t


def ann_takes(self, t: str, vt: str) -> bool:
    # does a location annotated t (float, int or str, ANNTYPES), or of the union an earlier join
    # gave it, hold a value of type vt too, as it is (float_takes, member_takes)
    if is_union(t):
        return len([m for m in umembers(t) if m in ANNTYPES and ann_takes(self, m, vt)]) > 0
    return (t == "float" and float_takes(vt)) or member_takes(self, t, vt)


def ann_open(self) -> bool:
    # may a location annotated float, int or str join now: not in an attempt that an error
    # declines (xtry: a comparison's or an adapter's of a program with Any values), whose int for
    # a float declines it, as before, so that no declined code widens storage; a narrowing's
    # attempt drops its joins where it is declined (err)
    return self.xtry == "" or self.xtry.startswith("narrow:")


def ann_site(t: str) -> bool:
    # can a location of type t be one annotated float, int or str, before or after its join
    # (ann_takes)
    return t in ANNTYPES or (is_union(t) and len([m for m in umembers(t) if m in ANNTYPES]) > 0)


def field_value(self, ci: ClassInfo, name: str, v: Val) -> Val:
    # v as a value of field name of class ci, where no store of the object's field takes it: the
    # default its class body gives it, or the argument of the __init__ @dataclass writes. An int
    # for a field annotated float joins the field, as a store does (setfield, join_hint), and so
    # does an enum member for one annotated int or str
    t = ci.ftypes[name]
    if not ann_site(t) or not ann_takes(self, t, v.t) or name not in field_home(self, ci, name).fann:
        return self.coerce(v, t)
    was = self.join_at("ann:field", self.field_key(ci, name), t)
    cv = self.coerce(v, t)
    self.join_at(was[0], was[1], was[2])
    return cv


def ann_returns(f: FnInfo) -> bool:
    # may the return of f, annotated -> float, -> int or -> str, join with what it returns
    # (ann_takes; join_hint, whose key is its def's, "return:" and the line: its instances and its
    # class's specializations share the join): a function's or a method's whose def has the
    # annotation, but a special method's, whose result the operation that calls it checks, and a
    # function that C or CPython calls. Of the functions the compiler writes (a Callable's
    # adapter, a dispatcher, ...), only a dataclass field's default_factory, whose join is the
    # field's
    if f.synthetic:
        return f.name.endswith(".factory")
    if f.node.kind != "def" or len(f.node.kids) < 3 or f.node.kids[1].kind == "noann" or f.gen or f.extern or f.export or f.pyexport or f.iters:
        return False
    return f.cls == "" or not (f.name.startswith("__") and f.name.endswith("__"))


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
    # another kind's, or the union is no type a join gives. A location annotated float, int or
    # str (a variable, a field: "ann:field", or a function's return: "ann:return") joins too, but
    # only with the values it also holds (ann_takes: the numbers a float does, the enum members an
    # int or a str does), from its annotation's type or from the join an earlier pass gave it
    if self.final or self.joinkind == "" or t != self.jointype or self.drying > 0 or self.rtmode:
        return False
    key = ""
    ann = self.joinkind == "ann:field" or self.joinkind == "ann:return"
    if self.joinkind == "local":
        body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
        if self.joinname in self.curfn.params or self.joinname in self.compvars:
            return False
        # (an annotation that types nothing, Iterator[T]'s, joins distinct iterators as if there
        # were none: interfaces.py)
        ann = ann_target(body, self.joinname) and not self.iface_widens(body, self.joinname, t, vt)
        key = f"{self.fnkey(self.curfn)}|{self.joinname}"
    elif self.joinkind == "global":
        if self.joinname in self.constflags or owner(self.joinname) not in self.inits:
            return False
        ann = ann_target(self.inits[owner(self.joinname)].node.kids, self.joinname) and not self.iface_widens(self.inits[owner(self.joinname)].node.kids, self.joinname, t, vt)
        key = f"global:{self.joinname}"
    elif self.joinkind == "field" or self.joinkind == "return" or ann:
        key = self.joinname
    if ann and not (ann_takes(self, t, vt) and (t in ANNTYPES or (ann_site(t) and self.hints.get(key, "") == t)) and ann_open(self)):
        return False
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
    at = FLOATAT if float_takes(vt) else MEMBERAT
    if ann and self.joinkind != "local" and at not in self.hints and at not in self.newhints:
        # (the first such store, which an error names: err; a member's with the annotation and its
        # class)
        base = [m for m in umembers(t) if m in ANNTYPES and ann_takes(self, m, vt)][0] if is_union(t) else t
        self.newhints[at] = where(self.line) if at == FLOATAT else f"{where(self.line)}|{base}|{vt}"
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
    if (is_tuple(a) or is_vtuple(a)) and (is_tuple(b) or is_vtuple(b)) and "?" not in a and "?" not in b:
        # tuples of other lengths (or one of a runtime length): a runtime-length tuple of their
        # items' join, where one can hold them (tuple[()] and tuple[int, int]: tuple[int, ...])
        xs = targs(a) + targs(b)
        e = xs[0] if len(xs) > 0 else ""
        for x in xs[1:]:
            e = (e if e == x else self.join_type(e, x)) if e != "" else ""
        return self.ctype("vtuple", [e]) if e != "" and unopt(e) != BIG and self.vtuple_holds(e) else ""
    if a == b:
        return a
    if is_clsval(unopt(a)) or is_clsval(unopt(b)):
        # class objects: those of a class that both classes derive from; with another value, where
        # the module opts in to dynamic Any, an Any value (the class's box, which such a module's
        # locations held before class objects were typed: class_values.py)
        j = self.join(a, b)
        if j != "" or not self.dyn_policy(self.line):
            return j
        return "dyn" if self.dyn_boxable(a) == "" and self.dyn_boxable(b) == "" else ""
    if (a == BIG and b == "int") or (b == BIG and a == "int"):
        return BIG  # (a promoting int holds both: bigints.py)
    if (a == BIG and b in ["bool", "float", "str"]) or (b == BIG and a in ["bool", "float", "str"]):
        # (with a bool, a float or a str, their union, which holds 64-bit ints, as in other modules)
        a, b = "int" if a == BIG else a, "int" if b == BIG else b
    it = self.iter_join(a, b)
    if it != "":
        return it  # (distinct iterators of one item type: the interface Iterator[T], interfaces.py)
    j = self.union_type([a, b])
    return j if not j.startswith("!") and self.joinable(j) else ""


def gen_joinable(self, t: str) -> bool:
    # can a join give a location type t: T | None, or a union of int, float, bool and str (that
    # may be None), whose operations select the member's by the tag (see unumeric), with the
    # members of enum classes whose objects are also CPython's ints or strs (member_takes) where
    # it has that type: an int | C, whose member keeps its class
    u = unopt(t)
    if not is_union(u):
        return is_opt(t)
    ms = umembers(u)
    return all([m in ["int", "float", "bool", "str"] or (m in self.classes and self.enum_builtin(m) in ms) for m in ms])


def gen_replay_state(self) -> list[int]:
    # what a function body that local_again discards must not leave behind: the functions,
    # classes, closures, specializations, globals and roots compiled so far (an unused
    # specialization still counts toward the compiler's bounded inference budgets)
    return [len(self.fns), len(self.classes), len(self.closures), self.template_instances, self.template_retained,
            len(self.globs), len(self.gcroots)]


def gen_local_again(self, f: FnInfo, before: list[int]) -> bool:
    # A bounded alternative to Rejoin: where every join that compiling f found (join_hint) widens
    # one of f's own unannotated locals (a total that 0 starts and floats are added to; an int
    # local that a promoting int reaches, bigints.py), f alone is compiled again with those joins,
    # as the program's next pass would compile it. Joins of parameters, globals, fields and
    # returns (f's own is the key ...|return, which names no local), a generator or closure, a
    # function with captured cells and a body that compiled a new dependency (replay_state) keep
    # the whole-program pass, as does dynamic Any's own retry. No new Gen/Frame state: the
    # driver's hints survive a fallback, and dry() cannot request joins.
    if dynamic_program() or self.modlevel or self.rtmode or f.gen or f.clo >= 0 or f.node.kind != "def":
        return False
    if len(self.cells) > 0 or f.ll in self.retseen or f.ll in self.dynseen or self.replay_state() != before:
        return False
    prefix = self.fnkey(f) + "|"
    names: list[str] = []
    for key in self.newhints:
        name = key[len(prefix):] if key.startswith(prefix) else ""
        if name == "" or name in f.params or name in self.compvars or name not in self.ltype:
            return False  # another pending join already needs the whole-program fallback
        if self.newhints[key] == BIG and (not int_lists() or self.ltype[name] != "int"):
            return False  # (a promoting int replaces only an int local, where a module opts in)
        names.append(name)
    if len(names) == 0:
        return False
    for name in names:
        self.hints[prefix + name] = self.newhints[prefix + name]
    # Keep newhints until the retry succeeds: gen_err then falls back through Rejoin if
    # a changed type exposes a diagnostic or a specialization limit during this attempt.
    # Its result is inferred afresh, just as in dyn_again; no recursive consumer took it.
    self.guessed.pop(f.ll, "")
    self.qused.pop(f.ll, "")
    self.qret.pop(f.ll, "")
    self.qholes.pop(f.ll, [])
    self.qforward.pop(f.ll, False)
    return True
