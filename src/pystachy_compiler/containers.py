"""Containers component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import shown
from src.pystachy_compiler.ir import Ins, IterArg, SetArg, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import OPTTYPES
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import (
    bool_for_int,
    elem,
    elem_problem,
    folds,
    has_method,
    is_dict,
    is_fset,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_sopt,
    is_tuple,
    key_problem,
    literal,
    lookable,
    selem,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_set_display(self, n: Node, want: str, folded: bool) -> Val:
    # {a, b, ...}: the items, evaluated in order, inserted into a new set (BUILD_SET). One of
    # more than two constants is CPython's frozenset constant of them merged into a new set
    # (SET_UPDATE), which can leave it a smaller table; folded: the iterable of a for loop or
    # a comprehension, of constants, which CPython's AST optimizer makes that frozenset. The
    # constant is the frozenset of the items inserted in order, made again of its elements
    # in the order it has them (the compiler's merge_consts_recursive does that). One of literals
    # is made where the display first runs and kept in a global, which the collector scans: each
    # run after that copies it into a new set, or (folded) is it, as CPython's code object keeps
    # it (an operator's result is made on each run, as CPython leaves one beyond its limits)
    const = (folded or (len(n.kids) > 2 and folds(mk("tuple", "", n.line, n.kids)))) and literal(mk("tuple", "", n.line, n.kids)) and not self.rtmode
    g = f"@fs.{len(self.globs)}"
    old = ""
    l0 = ""
    ldone = ""
    if const:
        self.global_var(g, "ptr")
        old = self.ins(f"load ptr, ptr {g}")
        l0 = self.cur
        lmake = self.label()
        ldone = self.label()
        self.cbr(self.ins(f"icmp eq ptr {old}, null"), lmake, ldone)
        self.place(lmake)
    et = selem(want) if is_set(want) and "?" not in want else ""
    given = et != ""
    items: list[Val] = []
    jt = ""
    for e in n.kids:
        if e.kind == "starred":
            self.err("unpacking in a set display ({*xs}) is not supported: use set(xs) or s.update(xs)")
        v = self.expr(e, et)
        if et == "" and v.t != "None":
            et = v.t
        jt = v.t if jt == "" else self.join(jt, v.t) or "-"  # (the items' types together)
        items.append(v)
    if not given and is_tuple(jt):
        et = self.none_items(jt)  # (None among the strs of a tuple's item: str | None)
    if et == "":
        self.err("cannot infer the type of a set of None")
    if elem_problem(et) != "":
        self.err(elem_problem(et))
    items = [self.store_elem(v, et) for v in items]
    r = self.rt("pys_set_new", "ptr", [f"i64 {self.key_kind(et)}"])
    for v in items:
        self.rt("pys_set_add", "void", [f"ptr {r}", "i64 " + self.to_slot(v)])
    if folded or (len(items) > 2 and folds(mk("tuple", "", n.line, n.kids))):
        c = self.rt("pys_set_new", "ptr", [f"i64 {self.key_kind(et)}"])
        self.rt("pys_set_update_list", "void", [f"ptr {c}", f"ptr {self.rt('pys_set_list', 'ptr', [f'ptr {r}'])}"])
        r = c
        if const:
            self.emit(f"store ptr {r}, ptr {g}")
            l1 = self.cur
            self.br(ldone)
            self.place(ldone)
            ph = Ins("phi", self.ctype("frozenset", [et]), "")
            self.incoming(ph, old, l0)
            self.incoming(ph, r, l1)
            r = self.phi(ph)
        if not folded:
            m = self.rt("pys_set_new", "ptr", [f"i64 {self.key_kind(et)}"])
            self.rt("pys_set_update", "void", [f"ptr {m}", f"ptr {r}"])
            r = m
    return Val(r, self.ctype("frozenset" if folded else "set", [et]))

def gen_iter_elem(self, t: str) -> str:
    # the type of the items a loop over a value of type t gets, or ""
    if is_list(t):
        return elem(t)
    if is_set(t):
        return selem(t)
    if is_dict(t):
        return targs(t)[0]
    if t == "str" or is_kw(t):
        return "str"
    if is_tuple(t) and len(targs(t)) > 0 and all(x == targs(t)[0] for x in targs(t)):
        return targs(t)[0]
    return ""

def gen_siter(self, n: Node, et: str, what: str) -> Val:
    # an iterable that a set takes the elements of (set(it), s.update(it), s.union(it), ...),
    # for elements of type et ("": any): a set or frozenset, a dict (CPython takes its keys
    # with their hashes), or else the list of its items, in the order CPython's iterator
    # gives them (a list's, a tuple's, a str's characters, what a generator yields, ...)
    return self.sitems(self.consume(n, self.ctype("list", [et]) if et != "" else ""), et, what)

def gen_sitems(self, v: Val, et: str, what: str) -> Val:
    # siter's iterable, from its value v: where the set method takes its items (the iterator
    # CPython makes then runs __iter__, and None raises)
    v = self.unwrap(v, "TypeError: 'NoneType' object is not iterable")
    if v.t == "str":
        v = Val(self.rt("pys_str_list", "ptr", [f"ptr {v.v}"]), "list[str]")
    elif v.t == "tuple[]" and et != "":
        v = Val(self.as_list(v, "set").v, self.ctype("list", [et]))  # (() has no item to type: the elements wanted)
    elif not is_set(v.t) and not is_dict(v.t):
        v = self.as_list(v, "set")
    if not is_set(v.t) and not is_dict(v.t) and not is_list(v.t):
        self.err(f"'{tname(v.t)}' object is not iterable")
    it = self.iter_elem(v.t)
    if "?" in v.t:
        self.err(f"cannot infer the type of an empty {tname(v.t)}; add a type annotation")
    if et != "" and it != et and self.wider(it, et) != et:
        self.err(f"{what} of {typestr(v.t)} for a set of {typestr(et)} is not supported: a set holds elements of one type")
    if et == "" and elem_problem(it) != "":
        self.err(elem_problem(it))
    return v

def gen_supdate(self, s: str, v: Val) -> None:
    # set s takes the elements of v, a set, a dict or a list (siter), as CPython's update does
    if is_set(v.t):
        self.rt("pys_set_update", "void", [f"ptr {s}", f"ptr {v.v}"])
    elif is_dict(v.t):
        self.rt("pys_set_update_dict", "void", [f"ptr {s}", f"ptr {v.v}"])
    else:
        self.rt("pys_set_update_list", "void", [f"ptr {s}", f"ptr {v.v}"])

def gen_sdiscard(self, ov: str, v: Val, et: str) -> None:
    # set ov (of elements of type et) discards v, which it holds or not; None is no element
    if v.t == "None":
        return
    if is_opt(v.t) and unopt(v.t) == et:
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.isnull(v), l2, l1)
        self.place(l1)
        self.rt("pys_set_discard", "void", [ov, "i64 " + self.to_slot(self.dkey(self.deref(v), et))])
        self.br(l2)
        self.place(l2)
        return
    self.rt("pys_set_discard", "void", [ov, "i64 " + self.to_slot(self.dkey(v, et))])

def gen_sargs(self, o: Val, m: str, args: list[Node]) -> list[SetArg]:
    # the arguments of set o's method m (update(), union(), ...), evaluated in order before it
    # takes the items of any (stake). With several (or for union() and difference(), which copy
    # o first), a generator expression (or map(), filter(), range(), zip(), enumerate(),
    # reversed()) makes its iterator now, where its outermost iterable is evaluated (and range()
    # checks its step, and __iter__ runs), and runs at its turn (a range's items are never all
    # made at once); any other iterable is evaluated now, and its __iter__ runs at its turn
    et = selem(o.t)
    split = len(args) > 1 or m == "union" or m == "difference"
    out: list[SetArg] = []
    for a in args:
        g = self.mapgen(a) if self.is_mapcall(a) else a
        if len(args) > 1 and self.iterator_call(g):
            item = mk("name", "__item", g.line, [])
            g = mk("listcomp", "gen", g.line, [item, item, g])
        if g.kind != "listcomp" or g.s != "gen":
            out.append(SetArg(self.consume(g, self.ctype("list", [et]) if et != "" else ""), g))
            continue
        x = SetArg(Val("", ""), g)
        if split:
            x.arg.split = self.label()
            x.v = self.sgen(o, m, g, x.arg)
            x.back = self.label()
            self.br(x.back)
            self.place(x.arg.split)
        out.append(x)
    return out

def gen_stake(self, o: Val, m: str, x: SetArg) -> Val:
    # the items of argument x of set o's method m (sargs), at its turn: a set, a dict or a list,
    # or none (type "") where a generator added (or discarded) each item as it came
    what = f"{'frozenset' if is_fset(o.t) else 'set'}.{m}()"
    if x.gen.kind != "listcomp" or x.gen.s != "gen":
        return self.sitems(x.v, selem(o.t), what)
    if x.arg.split == "":
        v = self.sgen(o, m, x.gen, None)
    else:
        self.br(x.arg.trav)
        self.place(x.back)
        v = x.v
    return v if v.t == "" else self.sitems(v, selem(o.t), what)

def gen_sgen(self, o: Val, m: str, g: Node, arg: IterArg | None) -> Val:
    # generator expression g, an argument of set o's method m: update() adds each item to o as
    # it is yielded, and difference_update() discards it (none: a Val of type ""), as CPython's
    # set_update_internal and set_difference_update_internal do; the others take a list of them
    if m == "update" or m == "difference_update":
        self.listcomp(g, o.t, "", o.v, arg, "set" if m == "update" else "discard")
        return Val("", "")
    et = selem(o.t)
    return self.listcomp(g, self.ctype("list", [et]) if et != "" else "", "", "", arg)

def gen_keys_list(self, v: Val) -> Val:
    # a dict's keys (or v as it is), where CPython iterates over a dict as over any iterable
    return Val(self.rt("pys_dict_keys", "ptr", [f"ptr {v.v}"]), self.ctype("list", [targs(v.t)[0]])) if is_dict(v.t) else v

def gen_set_new(self, name: str, args: list[Node], want: str) -> Val:
    # set(), set(it), frozenset(), frozenset(it): a new set (frozenset) of the elements of it,
    # made as CPython's make_new_set makes it (set_update_internal: a set's table is merged, a
    # dict's keys are added after one resize for them all, any other iterable's items are added
    # in order); frozenset(f) of a frozenset is f itself
    fz = name == "frozenset"
    for a in args:
        if a.kind == "kw":
            self.err(f"{name}() takes no keyword arguments")
    if len(args) > 1:
        self.err(f"{name} expected at most 1 argument, got {len(args)}")
    w = want if is_set(want) and is_fset(want) == fz and "?" not in want else ""
    if len(args) == 0:
        if w == "":
            self.err(f"cannot infer the type of an empty {name}; add a type annotation ({'s: set[T] = set()' if not fz else 'f: frozenset[T] = frozenset()'})")
        return Val(self.rt("pys_set_new", "ptr", [f"i64 {self.key_kind(selem(w))}"]), w)
    v = self.siter(args[0], selem(w) if w != "" else "", f"{name}()")
    t = self.ctype(name, [selem(w) if w != "" else self.none_items(self.iter_elem(v.t))])
    if fz and is_fset(v.t):
        return Val(v.v, t)
    if is_set(v.t):
        return Val(self.rt("pys_set_copy", "ptr", [f"ptr {v.v}"]), t)
    r = self.rt("pys_set_new", "ptr", [f"i64 {self.key_kind(selem(t))}"])
    self.supdate(r, v)
    return Val(r, t)

def gen_setop(self, op: str, a: Val, b: Val) -> Val:
    # a | b, a & b, a - b and a ^ b of sets or frozensets: a new one of a's kind, made as
    # CPython's set_or, set_intersection, set_difference and set_symmetric_difference make it
    w = self.wider(selem(a.t), selem(b.t))
    if w == "":
        self.err(f"unsupported operand types for {op}: {typestr(a.t)} and {typestr(b.t)} (a set holds elements of one type)")
    fn = "pys_set_or" if op == "|" else "pys_set_and" if op == "&" else "pys_set_sub" if op == "-" else "pys_set_xor"
    return Val(self.rt(fn, "ptr", [f"ptr {a.v}", f"ptr {b.v}"]), self.ctype("frozenset" if is_fset(a.t) else "set", [w]))

def gen_smethod(self, o: Val, m: str, args: list[Node]) -> Val:
    # a method of a set or frozenset o, run as CPython's setobject.c runs it; the iterables the
    # methods take are those siter takes, each evaluated before the method runs (its *args)
    fz = is_fset(o.t)
    tn = "frozenset" if fz else "set"
    et = selem(o.t)
    if not has_method(tn, m):
        self.err(f"'{tn}' object has no attribute '{m}'")
    for a in args:
        if a.kind == "kw":
            self.err(f"{tn}.{m}() takes no keyword arguments")
    n = len(args)
    if (m == "pop" or m == "clear" or m == "copy") and n > 0:
        self.err(f"{tn}.{m}() takes no arguments ({n} given)")
    if m in "add discard remove symmetric_difference symmetric_difference_update isdisjoint issubset issuperset".split() and n != 1:
        self.err(f"{tn}.{m}() takes exactly one argument ({n} given)")
    ov = f"ptr {o.v}"
    none = Val("null", "None")
    if m == "add":
        v = self.store_elem(self.expr(args[0], et), et)
        self.rt("pys_set_add", "void", [ov, "i64 " + self.to_slot(v)])
        return none
    if m == "discard" or m == "remove":
        v = self.expr(args[0], et)
        if v.t == "None" or (is_opt(v.t) and unopt(v.t) == et):
            # None is no element: discard() does nothing, remove() raises KeyError: None
            if m == "remove":
                self.guard(self.isnull(v) if v.t != "None" else "true", "KeyError: None")
                if v.t == "None":
                    return none
                v = self.deref(v)
            else:
                self.sdiscard(ov, v, et)
                return none
        k = self.dkey(v, et)
        if m == "remove" and bool_for_int(v.t, et):
            # a bool where the elements are ints removes the int it equals, and CPython's
            # KeyError names it as the bool it is (KeyError: True), where the runtime's would
            # name the int
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.ins(f"icmp eq i64 {self.rt('pys_set_has', 'i64', [ov, 'i64 ' + self.to_slot(k)])}, 0"), l1, l2)
            self.place(l1)
            self.raise_("KeyError", self.repr(v).v)
            self.place(l2)
            m = "discard"
        self.rt("pys_set_discard" if m == "discard" else "pys_set_remove", "void", [ov, "i64 " + self.to_slot(k)])
        return none
    if m == "pop":
        return self.from_slot(self.rt("pys_set_pop", "i64", [ov]), et)
    if m == "clear":
        self.rt("pys_set_clear", "void", [ov])
        return none
    if m == "copy":
        return o if fz else Val(self.rt("pys_set_copy", "ptr", [ov]), o.t)  # (frozenset.copy() is the frozenset)
    if m == "update" or m == "union" or m == "intersection" or m == "intersection_update" or m == "difference" or m == "difference_update":
        # CPython evaluates every argument first, in order, then the method takes the items of
        # each in turn (sargs, stake): update() adds a generator's (or map()'s, filter()'s) as
        # it yields them, which may see the set change, and difference_update() discards them so
        sa = self.sargs(o, m, args)
        if m == "update" or m == "difference_update":
            for x in sa:
                v = self.stake(o, m, x)
                if v.t == "":
                    pass  # (a generator: each item went as it came)
                elif m == "update":
                    self.supdate(o.v, v)
                else:
                    self.rt("pys_set_isub" if is_set(v.t) else "pys_set_isub_list", "void", [ov, f"ptr {self.keys_list(v).v}"])
            return none
        if m == "union":
            r = Val(self.rt("pys_set_copy", "ptr", [ov]), o.t)
            for x in sa:
                v = self.stake(o, m, x)
                if is_set(v.t):
                    self.rt("pys_set_union_more", "void", [f"ptr {r.v}", ov, f"ptr {v.v}"])  # (but o itself)
                else:
                    self.supdate(r.v, v)
            return r
        if m == "intersection" or m == "intersection_update":
            r = o if n > 0 else Val(self.rt("pys_set_copy", "ptr", [ov]), o.t)
            for x in sa:
                v = self.stake(o, m, x)
                r = Val(self.rt("pys_set_and" if is_set(v.t) else "pys_set_and_list", "ptr", [f"ptr {r.v}", f"ptr {self.keys_list(v).v}"]), o.t)
            if m == "intersection":
                return r
            self.rt("pys_set_assign", "void", [ov, f"ptr {r.v}"])  # (o takes the intersection's table)
            return none
        if n == 0:
            return Val(self.rt("pys_set_copy", "ptr", [ov]), o.t)
        x = sa[0]
        if (x.gen.kind == "listcomp" and x.gen.s == "gen") or unopt(x.v.t) in self.classes:
            # code runs as its items are taken (a generator's, __iter__): CPython's
            # set_copy_and_difference has copied o before
            r = Val(self.rt("pys_set_copy", "ptr", [ov]), o.t)
            self.rt("pys_set_isub_list", "void", [f"ptr {r.v}", f"ptr {self.stake(o, m, x).v}"])
        else:
            v = self.stake(o, m, x)
            r = Val(self.rt("pys_set_sub" if is_set(v.t) else "pys_set_sub_dict" if is_dict(v.t) else "pys_set_sub_list", "ptr", [ov, f"ptr {v.v}"]), o.t)
        for x in sa[1:]:
            v = self.stake(o, m, x)
            self.rt("pys_set_isub" if is_set(v.t) else "pys_set_isub_list", "void", [f"ptr {r.v}", f"ptr {self.keys_list(v).v}"])
        return r
    if (m == "issuperset" or m == "isdisjoint") and ((args[0].kind == "listcomp" and args[0].s == "gen") or self.is_mapcall(args[0])):
        # CPython takes a generator's items until one decides: one o lacks (issuperset), or one
        # it holds (isdisjoint), and the generator runs no further
        g = self.mapgen(args[0]) if self.is_mapcall(args[0]) else args[0]
        e = mk("cmp", "in" if m == "issuperset" else "not in", g.line, [g.kids[0], self.vnode(o)])
        return self.listcomp(mk("listcomp", "gen", g.line, [e] + g.kids[1:]), "", "all")
    vs = [self.siter(a, et, f"{tn}.{m}()") for a in args]
    v = vs[0]
    if m == "symmetric_difference":
        return Val(self.rt("pys_set_xor" if is_set(v.t) else "pys_set_xor_dict" if is_dict(v.t) else "pys_set_xor_list", "ptr", [ov, f"ptr {v.v}"]), o.t)
    if m == "symmetric_difference_update":
        self.rt("pys_set_ixor" if is_set(v.t) else "pys_set_ixor_dict" if is_dict(v.t) else "pys_set_ixor_list", "void", [ov, f"ptr {v.v}"])
        return none
    if m == "isdisjoint":
        hit = self.rt("pys_set_isdisjoint" if is_set(v.t) else "pys_set_isdisjoint_list", "i64", [ov, f"ptr {self.keys_list(v).v}"])
    elif is_set(v.t):
        hit = self.rt("pys_set_cmp", "i64", [ov, f"ptr {v.v}", "i64 1" if m == "issubset" else "i64 3"])
    else:
        hit = self.rt("pys_set_le_list" if m == "issubset" else "pys_set_ge_list", "i64", [ov, f"ptr {self.keys_list(v).v}"])
    return Val(self.ins(f"icmp ne i64 {hit}, 0"), "bool")

def gen_fromkeys(self, args: list[Node], want: str) -> Val:
    # dict.fromkeys(xs, v=None): a dict of xs's items, each mapped to v. Both are evaluated
    # first; a dict's keys go into a table sized for them, any other iterable's one by one
    for a in args:
        if a.kind == "kw":
            self.err("dict.fromkeys() takes no keyword arguments")
    if len(args) == 0 or len(args) > 2:
        self.err(f"fromkeys expected {'at least 1 argument' if len(args) == 0 else 'at most 2 arguments'}, got {len(args)}")
    kv = targs(want) if is_dict(want) and "?" not in want else ["", ""]
    w = self.ctype("list", [kv[0]]) if kv[0] != "" and (args[0].kind == "list" or args[0].kind == "listcomp") else ""
    if kv[0] != "" and args[0].kind == "dict" and len(args[0].kids) == 0:
        w = want  # ({} has no key to type: the keys wanted)
    xs = self.consume(args[0], w) if self.iterator_call(args[0]) and args[0].kids[0].s == "range" else self.expr(args[0], w)
    V = kv[1]
    v = self.expr(args[1], V) if len(args) == 2 else Val("null", "None")
    if is_opt(xs.t):
        xs = self.unwrap(xs, "TypeError: 'NoneType' object is not iterable")
    if xs.t == "str":
        xs = Val(self.rt("pys_str_list", "ptr", [f"ptr {xs.v}"]), "list[str]")
    elif xs.t == "tuple[]" and kv[0] != "":
        xs = Val(self.as_list(xs, "fromkeys").v, self.ctype("list", [kv[0]]))  # (() has no item to type: the keys wanted)
    elif not is_dict(xs.t):
        xs = self.as_list(xs, "fromkeys")
    if not is_list(xs.t) and not is_dict(xs.t):
        self.err(f"'{tname(xs.t)}' object is not iterable")
    K = targs(xs.t)[0] if is_dict(xs.t) else elem(xs.t)
    if key_problem(K) != "":
        self.err(key_problem(K))
    if v.t == "None" and V == "":
        self.err(f"dict.fromkeys(keys{', None' if len(args) == 2 else ''}) needs the type of the dict it makes, whose values are None: annotate it (d: dict[K, V | None] = ...)")
    if v.t == "None" and self.optional(V) != V:
        self.err(f"dict.fromkeys(keys{', None' if len(args) == 2 else ''}) needs values that can be None ({OPTTYPES}), not {typestr(V)}: give a value")
    V = v.t if V == "" else V
    v = self.coerce(v, V)
    t = self.ctype("dict", [K, V])
    if is_dict(xs.t):
        return Val(self.rt("pys_dict_fromkeys_dict", "ptr", [f"ptr {xs.v}", "i64 " + self.to_slot(v)]), t)
    return Val(self.rt("pys_dict_fromkeys", "ptr", [f"i64 {self.key_kind(K)}", f"ptr {xs.v}", "i64 " + self.to_slot(v)]), t)

def gen_affix_any(self, tup: Val, m: str, av: list[str]) -> Val:
    # s.startswith((a, b, ...), start, end) (or endswith), as CPython's loop over the tuple: each
    # item in order, stopping at the first that matches (False for an empty tuple); an item that
    # is None raises when it is reached. av: the call's arguments, the item's place left empty
    lend = self.label()
    ph = Ins("phi", "bool", "")
    for i in range(len(targs(tup.t))):
        item = self.tget(tup, i)
        if is_opt(item.t):
            self.guard(self.ins(f"icmp eq ptr {item.v}, null"), f"TypeError: tuple for {m} must only contain str, not NoneType")
        c = self.rres(self.rt(f"pys_str_{m}", "i64", [av[0], f"ptr {item.v}"] + av[2:]), "bool")
        nx = self.label()
        self.incoming(ph, "true", self.cur)
        self.cbr(c.v, lend, nx)
        self.place(nx)
    self.incoming(ph, "false", self.cur)
    self.br(lend)
    self.place(lend)
    return Val(self.phi(ph), "bool")

def gen_optdefault(self, d: Val, t: str) -> str:
    # the type of d.get(k, d) and d.pop(k, d) for values of type t: t | None for a default
    # that may be None
    if (d.t == "None" or (is_opt(d.t) and unopt(d.t) == t)) and t not in self.classes and self.optional(t) != "":
        return self.optional(t)
    return t

def gen_key_kind(self, kt: str) -> str:
    # the key kind of a new dict whose keys have type kt (runtime.c's Dict.kind): 0 int, 1 str,
    # or a tuple key's type descriptor
    if kt == "int" or kt == "str":
        return "1" if kt == "str" else "0"
    return f"ptrtoint (ptr {self.sconst(self.desc(kt, '=='))} to i64)"

def gen_dkey(self, k: Val, kt: str) -> Val:
    # a key to look up in a dict whose keys have type kt: one that may be None stays optional
    # (see nonekey), and a bool or a tuple with what CPython finds as such a key (lookable) is one
    if is_opt(k.t) and unopt(k.t) == kt:
        return k
    if k.t == "bool" and kt == "int":
        return self.as_int(k)  # (True is the key 1)
    if is_tuple(k.t) and k.t != kt and lookable(k.t, kt):
        return Val(k.v, kt)  # (a None where the keys hold a str finds none: runtime.c's hval)
    if is_sopt(k.t) and bool_for_int(unopt(k.t), kt):
        self.err(f"a {typestr(k.t)} key of a dict with {typestr(kt)} keys is supported by get() and in only, as CPython's KeyError would name it as the bool it is: test it with 'is not None' first")
    return self.coerce(k, kt)

def gen_bool_find(self, d: str, k: Val, key: str) -> str:
    # the entry of key k in dict d (key: k's slot as a key of d's type), where k holds a bool
    # and d's keys an int (bool_for_int): one that d does not hold raises CPython's KeyError
    # here, naming k as it is (KeyError: True), where the runtime's lookup would name the key
    # as the int it equals (KeyError: 1)
    e = self.rt("pys_dict_find", "i64", [f"ptr {d}", f"i64 {key}"])
    l1 = self.label()
    l2 = self.label()
    self.cbr(self.ins(f"icmp slt i64 {e}, 0"), l1, l2)
    self.place(l1)
    self.raise_("KeyError", self.repr(k).v)
    self.place(l2)
    return e

def gen_store_key(self, k: Val, kt: str) -> Val:
    # k as a key stored into a dict whose keys have type kt (d[k] = v, d[k] op= v, a display,
    # setdefault): a bool is rejected where the keys hold an int, as it is where an int is
    # stored, since CPython keeps a key it adds as it is, which prints as True, not 1 (it
    # looks up, pops and deletes the int key it equals: dkey)
    if bool_for_int(k.t, kt):
        self.err(f"a {typestr(k.t)} key is stored into a dict with {typestr(kt)} keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()")
    return self.coerce(k, kt)

def gen_store_elem(self, k: Val, et: str) -> Val:
    # k as an element added to a set whose elements have type et (s.add(k), a display, a
    # comprehension): as store_key, a bool is rejected where the elements are ints
    if bool_for_int(k.t, et):
        self.err(f"a {typestr(k.t)} element is added to a set of {typestr(et)} elements, where CPython keeps an element it adds as the bool it is (True, not 1): convert the bool with int()")
    return self.coerce(k, et)

def gen_nonekey(self, k: Val, none: str, fn: str, av: list[str]) -> str:
    # the slot fn(av) returns, a dict lookup of key k; a key that is None is in no dict: the
    # result is then the slot none, or with none "" KeyError: None
    if not is_opt(k.t):
        return self.rt(fn, "i64", av)
    if none == "":
        self.guard(self.ins(f"icmp eq ptr {k.v}, null"), "KeyError: None")
        return self.rt(fn, "i64", self.keyed(k, av))
    l1 = self.label()
    l2 = self.label()
    l3 = self.label()
    self.cbr(self.ins(f"icmp eq ptr {k.v}, null"), l1, l2)
    self.place(l2)
    r = self.rt(fn, "i64", self.keyed(k, av))
    e2 = self.cur
    self.br(l3)
    self.place(l1)
    self.br(l3)
    self.place(l3)
    ph = Ins("phi", "%slot", "")
    self.incoming(ph, none, l1)
    self.incoming(ph, r, e2)
    return self.phi(ph)

def gen_keyed(self, k: Val, av: list[str]) -> list[str]:
    # the arguments av of a dict lookup by key k (av[1]), which is not None here: an int key
    # that may be None is the int its box holds
    if not is_sopt(k.t):
        return av
    return [av[0], "i64 " + self.to_slot(self.deref(k))] + av[2:]

def gen_none_arg(self, m: str, k: int) -> str:
    # what str method m (or file.write) raises for None as its argument k
    if m == "startswith" or m == "endswith":
        return f"TypeError: {m} first arg must be str or a tuple of str, not NoneType"
    if m == "partition" or m == "rpartition":
        return "TypeError: must be str, not NoneType"
    if m == "removeprefix" or m == "removesuffix" or m == "write":
        return f"TypeError: {m}() argument must be str, not None"
    return f"TypeError: {m}() argument {k} must be str, not None"

def gen_to_str(self, v: Val) -> Val:
    t = v.t
    if t == "str":
        return v
    if is_kw(t):
        return self.kw_repr(v)
    if t == "int":
        return Val(self.rt("pys_str_int", "ptr", [f"i64 {v.v}"]), "str")
    if t == "float":
        return Val(self.rt("pys_str_float", "ptr", [f"double {v.v}"]), "str")
    if t == "bool":
        return Val(self.select(v.v, Val(self.sconst("True"), "str"), Val(self.sconst("False"), "str")), "str")
    if t == "None":
        return Val(self.sconst("None"), "str")
    if t in self.classes:
        return self.obj_str(v, "__str__")
    if t == "opt[str]":
        return Val(self.select(self.ins(f"icmp eq ptr {v.v}, null"), Val(self.sconst("None"), "str"), Val(v.v, "str")), "str")
    if t == "exc":
        return Val(self.rt("pys_exc_str", "ptr", [f"ptr {v.v}"]), "str")
    return self.repr(v)

def gen_obj_str(self, v: Val, m: str) -> Val:
    # str()/repr() of an object through __str__/__repr__; None prints as "None". An exception
    # object's are those of its class (its ExcClass's: exc_helpers)
    if self.classes[v.t].tag > 0:
        # Select the concrete class before selecting __str__/__repr__ or object.__repr__:
        # a subclass may introduce the protocol where its static base has no method.
        cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, v.t)]
        end = self.label()
        nonnull = self.label()
        start = self.cur
        ph = Ins("phi", "str", "")
        self.incoming(ph, self.sconst("None"), start)
        self.cbr(self.ins(f"icmp eq ptr {v.v}, null"), end, nonnull)
        self.place(nonnull)
        tag = self.ins(f"load i64, ptr {v.v}")
        narrow = dict(self.narrowed)
        for i in range(len(cs)):
            c = cs[i]
            nxt = self.label() if i + 1 < len(cs) else ""
            if nxt != "":
                arm = self.label()
                self.cbr(self.ins(f"icmp eq i64 {tag}, {c.tag}"), arm, nxt)
                self.place(arm)
            self.narrowed = dict(narrow)
            method = m if m in c.methods else "__repr__"
            if method in c.methods and c.methods[method].bad != "" and self.lenient:
                method = ""
            if method in c.methods:
                r = self.call_fn(c.methods[method], [Val(v.v, c.name)], [], direct=True)
            else:
                qn = shown(c.name) if "$" in c.name and not c.name.startswith("__main__$") else "__main__." + short(c.name)
                r = Val(self.rt("pys_default_repr", "ptr", [f"ptr {self.sconst(qn)}", f"ptr {v.v}"]), "str")
            if not self.term:
                self.incoming(ph, r.v, self.cur)
                self.br(end)
            if nxt != "":
                self.place(nxt)
        self.narrowed = narrow
        self.place(end)
        return Val(self.phi(ph), "str")
    ms = self.classes[v.t].methods
    exc = self.classes[v.t].exc != ""
    if m not in ms and not exc:
        m = "__repr__"
    if m in ms and ms[m].bad != "" and self.lenient:
        m = ""  # (see desc)
    if v.v in self.nn and exc:
        return Val(self.rt("pys_exc_ostr" if m == "__str__" else "pys_exc_orepr", "ptr", [f"ptr {v.v}"]), "str")
    if v.v in self.nn and m in ms:
        return self.call_fn(ms[m], [v], [])
    l1 = self.label()
    l2 = self.label()
    l3 = self.label()
    self.cbr(self.ins(f"icmp eq ptr {v.v}, null"), l1, l2)
    self.place(l1)
    self.br(l3)
    self.place(l2)
    if exc:
        r = Val(self.rt("pys_exc_ostr" if m == "__str__" else "pys_exc_orepr", "ptr", [f"ptr {v.v}"]), "str")
    elif m in ms:
        r = self.call_fn(ms[m], [v], [])
    else:
        # object.__repr__: <__main__.Name object at 0x...>, <module.Name object at 0x...>
        qn = shown(v.t) if "$" in v.t and not v.t.startswith("__main__$") else "__main__." + short(v.t)
        r = Val(self.rt("pys_default_repr", "ptr", [f"ptr {self.sconst(qn)}", f"ptr {v.v}"]), "str")
    e2 = self.cur
    self.br(l3)
    self.place(l3)
    ph = Ins("phi", "str", "")
    self.incoming(ph, self.sconst("None"), l1)
    self.incoming(ph, r.v, e2)
    return Val(self.phi(ph), "str")

def gen_repr(self, v: Val) -> Val:
    if is_kw(v.t):
        return self.kw_repr(v)
    if v.t in self.classes:
        return self.obj_str(v, "__repr__")
    if v.t == "None":
        return Val(self.sconst("None"), "str")
    if v.t == "file":
        self.err(f"cannot convert {v.t} to str")
    if v.t == "exc":
        return Val(self.rt("pys_exc_repr", "ptr", [f"ptr {v.v}"]), "str")
    return Val(self.rt("pys_repr", "ptr", ["i64 " + self.to_slot(v), f"ptr {self.sconst(self.desc(v.t, 'repr'))}"]), "str")
