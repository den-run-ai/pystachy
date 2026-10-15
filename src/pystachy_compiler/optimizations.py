"""Optimizations component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.ir import IFn, Ins, Lookup, Val, Values
from src.pystachy_compiler.specs import CANON_DEPTH, FXBIT, LOOKUPS, RAWW, REACH
from src.pystachy_compiler.utils import is_list


def gen_optimize(self, fn: IFn, on: dict[str, bool]) -> int:
    # run the passes on fn that on turns on; how many ops they rewrote
    n = 0
    if "listget" in on:
        n += self.listget(fn)
    if "dictfuse" in on:
        n += self.dictfuse(fn)
    return n

def gen_preds(self, fn: IFn) -> dict[str, list[int]]:
    # the blocks that branch to each block of fn, by label, as positions in fn.blocks, once
    # each, and the unwind edges: a block that a try statement covers (Blk.handler, which
    # eh_ir has not made invokes yet) goes to its landing block, where an op of it that
    # raises goes. A check's raising edge is left out: its cold block raises, ending the
    # program or, covered itself, going to a landing block (an unwind edge of its own)
    pl: dict[str, list[int]] = {}
    for b in fn.blocks:
        pl[b.label] = []
    for j in range(len(fn.blocks)):
        code = fn.blocks[j].code
        for l in code[len(code) - 1].b:
            if j not in pl[l]:
                pl[l].append(j)
        h = fn.blocks[j].handler
        if h != "" and h in pl and j not in pl[h]:
            pl[h].append(j)
    return pl

def gen_listget(self, fn: IFn) -> int:
    # Unchecked list reads in sequence loops. The test a seq loop makes of a list leads to a
    # block (Loop.tests) where the loop's index (Loop.idx) is within the list's length. A
    # list.get of that list at that index, on the one path from there with no op between
    # that may shorten a list (wL, or U: user code), needs no bounds check: it becomes a
    # list.load, which lowers to an inline load. The path goes only to blocks that one
    # branch leads to, so that no other path reaches the read: not a handler's either,
    # whose code (after a landing block, which only unwind edges reach, see preds) joins
    # this path only after its try statement or at a loop's test, where paths meet. How
    # many reads it rewrote
    some = False
    for lp in fn.loops:
        for s in lp.seqs:
            some = some or is_list(s.t)
    if not some:
        return 0
    at: dict[str, int] = {}
    for j in range(len(fn.blocks)):
        at[fn.blocks[j].label] = j
    pl = self.preds(fn)
    bad = FXBIT["wL"] | FXBIT["U"]
    n = 0
    for lp in fn.loops:
        for k in range(len(lp.tests) if lp.kind == "seq" else 0):
            s = lp.seqs[k]
            l = lp.tests[k] if is_list(s.t) else ""
            steps = 0
            while l != "" and steps < len(fn.blocks):
                steps += 1
                code = fn.blocks[at[l]].code
                l = ""
                for j in range(len(code)):
                    i = code[j]
                    if i.op == "rt" and i.s == "list.get" and i.a[0].v == s.v and i.a[1].v == lp.idx[k]:
                        i.op = "list.load"
                        i.s = ""
                        i.r = [i.r[0], fn.n + 1, fn.n + 2, fn.n + 3]  # (the inline load's address arithmetic)
                        fn.n += 3
                        n += 1
                        break
                    if self.opfx(i, fn.fa) & bad != 0:
                        break
                    if j == len(code) - 1 and (i.op == "br" or i.op == "cbr" or i.op == "check") and len(pl[i.b[0]]) == 1:
                        l = i.b[0]  # (a cbr's: the next sequence's test, in a zip)
    return n

def gen_dictfuse(self, fn: IFn) -> int:
    # Dict lookup fusion. A dict.has or a dict.getitem of key k in dict d finds k's entry; a
    # dict.getitem or a dict.set of the same d and k after it, where k is known to be in d,
    # can reuse that entry while no dict changes: the has or getitem becomes a dict.find
    # (the entry, or -1) or a dict.entry (the entry, or a KeyError), the getitem after it a
    # dict.val (the entry's value) and the set a dict.entry_set (which moves no entry). k is
    # in d after a getitem, and where the test of a has's result is true. A forward pass over
    # the blocks in order keeps the lookups that hold at the end of each block (Lookup, by
    # position in looks: True where k is known to be in d), from the blocks that branch to a
    # block, and none from a later one (a loop's back edge) nor in a landing block, which
    # unwind edges reach (preds): what holds where an op raises is not what holds at the end
    # of its block (a getitem that raised KeyError ends its block knowing k in d), so a
    # handler's code knows only its own lookups, and so does the code after its try
    # statement, where the handler's end joins. An op with wD or U, and a set that reuses no
    # entry, ends them all. d and k must be the same values (canon). At most
    # LOOKUPS hold at once (the oldest gives way), and a block's state is dropped once the
    # last block it branches to has read it, so that the work and the memory grow linearly
    # with the function. How many ops it rewrote
    some = False
    for b in fn.blocks:
        for i in b.code:
            some = some or (i.op == "rt" and (i.s == "dict.has" or i.s == "dict.getitem"))
    if not some:
        return 0
    pl = self.preds(fn)
    vs = Values(fn, pl)
    looks: list[Lookup] = []
    has: dict[str, int] = {}  # a has's result -> its lookup
    cond: dict[str, int] = {}  # a test of it (icmp ne/eq 0, and xor true of one) -> the lookup
    pos: dict[str, bool] = {}  # and whether it is true where k is in d
    # (a block shares the state it starts with, and copies it before it changes it: own)
    none: dict[int, bool] = {}
    outs: list[dict[int, bool]] = []
    last = [-1] * len(fn.blocks)  # the last block after it that each block branches to
    for j in range(len(fn.blocks)):
        for p in pl[fn.blocks[j].label]:
            if p < j:
                last[p] = j
    bad = FXBIT["wD"] | FXBIT["U"]
    n = 0
    for j in range(len(fn.blocks)):
        b = fn.blocks[j]
        st = none
        own = False
        ps = pl[b.label]
        back = len(b.code) > 0 and b.code[0].op == "landing"  # (only unwind edges reach it: none holds)
        for p in ps:
            back = back or p >= j  # (a loop's back edge: none holds)
        for x in range(len(ps) if not back else 0):
            if x > 0 and len(st) == 0:
                break
            # what holds on the branch from block ps[x]: a cbr on a has's test tells whether k is in d
            e = outs[ps[x]]
            t = fn.blocks[ps[x]].code[len(fn.blocks[ps[x]].code) - 1]
            if t.op == "cbr" and t.b[0] != t.b[1] and t.a[0].v in cond and cond[t.a[0].v] in e:
                c = cond[t.a[0].v]
                e = e.copy()
                if (b.label == t.b[0]) == pos[t.a[0].v]:
                    e[c] = True
                else:
                    e.pop(c)
            if x == 0:
                st = e
            else:
                if not own:
                    st = st.copy()
                    own = True
                for c in [c for c in st]:
                    if c not in e:
                        st.pop(c)
                    elif not e[c]:
                        st[c] = False
        for x in range(len(b.code)):
            i = b.code[x]
            if i.op == "rt" and (i.s == "dict.has" or i.s == "dict.getitem" or i.s == "dict.set"):
                d = self.canon(vs, i.a[0].v)
                k = self.canon(vs, i.a[1].v)
                m = -1
                for c in st:
                    if st[c] and looks[c].d == d and looks[c].k == k:
                        m = c
                if m >= 0 and i.s != "dict.has":
                    # reuse the entry lookup m found
                    if looks[m].e == 0:
                        fn.n += 1
                        looks[m].e = fn.n
                    ev = Val(f"%t{looks[m].e}", "int")
                    if i.s == "dict.getitem":
                        self.runtime("pys_dict_val")
                        i.s = "dict.val"
                        i.a = [i.a[0], ev]
                    else:
                        self.runtime("pys_dict_entry_set")
                        i.s = "dict.entry_set"
                        i.a = [i.a[0], ev, i.a[2]]
                    n += 1
                elif i.s == "dict.set":
                    st = none
                    own = False
                else:
                    if not own:
                        st = st.copy()
                        own = True
                    if len(st) >= LOOKUPS:
                        o = len(looks)
                        for c in st:
                            o = c if c < o else o
                        st.pop(o)
                    st[len(looks)] = i.s == "dict.getitem"
                    if i.s == "dict.has":
                        has[f"%t{i.r[0]}"] = len(looks)
                    looks.append(Lookup(i, j, x, d, k))
            elif i.op == "num.cmp" and i.a[0].t == "int" and i.a[1].v == "0" and (i.s == "==" or i.s == "!="):
                # A typed membership truth test carries the same has-result fact as
                # a membership result; not/branch handling below stays shared.
                r = i.a[0].v
                if r in has:
                    cond[f"%t{i.r[0]}"] = has[r]
                    pos[f"%t{i.r[0]}"] = i.s == "!="
            elif i.op == "scalar.bin" and i.s == "xor" and i.t == "bool" and i.a[1].v == "true":
                r = i.a[0].v
                if r in cond:
                    cond[f"%t{i.r[0]}"] = cond[r]
                    pos[f"%t{i.r[0]}"] = not pos[r]
            elif len(st) > 0 and self.opfx(i, vs.fn.fa) & bad != 0:
                st = none
                own = False
        outs.append(st if last[j] > j else none)
        for p in ps:
            if p < j and last[p] == j:
                outs[p] = none
    # the lookups whose entry an op reuses: a has becomes a find (and k in d is its entry + 1,
    # which is not 0), a getitem an entry and a val; each adds one op to its block, before
    # the next lookup of the block (shift: how many it has added)
    blk = -1
    shift = 0
    for f in looks:
        if f.e == 0:
            continue
        if f.blk != blk:
            blk = f.blk
            shift = 0
        code = fn.blocks[f.blk].code
        x = f.x + shift
        shift += 1
        i = f.op
        if code[x] is not i:
            self.bad_ir(fn, fn.blocks[f.blk], f"dictfuse lost the lookup of %t{f.e}")
        if i.s == "dict.has":
            self.runtime("pys_dict_find")
            fi = Ins("rt", "int", "dict.find")
            fi.a = [i.a[0], i.a[1]]
            fi.r = [f.e]
            code[x] = fi
            ad = Ins("scalar.bin", "int", "add")
            ad.a = [Val(f"%t{f.e}", "int"), Val("1", "int")]
            ad.r = [i.r[0]]
            code.insert(x + 1, ad)
        else:
            self.runtime("pys_dict_entry")
            en = Ins("rt", "int", "dict.entry")
            en.a = [i.a[0], i.a[1]]
            en.r = [f.e]
            code.insert(x, en)
            self.runtime("pys_dict_val")
            i.s = "dict.val"
            i.a = [i.a[0], Val(f"%t{f.e}", "int")]
        n += 1
    return n

def gen_canon(self, vs: Values, v: str) -> str:
    # the canonical value of value v (Values): ops with the same canonical value compute
    # equal values (as long as no back edge comes between them). Loads follow reaching
    # typed stores/loads; pure operations use their operator, types, flags and canonical
    # operands. Every other value is its own. It recurses
    # once for each link of the chain of values it follows, so a value it reaches below
    # CANON_DEPTH calls is its own (a long chain, of k = k ^ 1 in straight-line code, would
    # overflow the native compiler's stack)
    if v in vs.cn:
        return vs.cn[v]
    if vs.depth >= CANON_DEPTH:
        vs.cn[v] = v
        return v
    vs.depth += 1
    r = v
    w = vs.at[int(v[2:])] if v.startswith("%t") and v[2:].isdigit() else -1
    if w >= 0:
        i = vs.fn.blocks[w // vs.stride].code[w % vs.stride]
        if i.op == "rt":
            if self.rtfns[i.s].fx & ~FXBIT["R"] == 0 and not self.rtfns[i.s].q:
                r = self.same(vs, v, f"rt {i.s} {', '.join([self.canon(vs, a.v) for a in i.a])}")
        elif i.op == "slot.pack" or i.op == "slot.unpack":
            r = self.same(vs, v, f"{i.op} {i.t} {i.a[0].t} {self.canon(vs, i.a[0].v)}")
        elif i.op == "scalar.bin" or i.op == "scalar.cast" or i.op == "scalar.cmp" or i.op == "select" or i.op == "num.cast" or i.op == "num.cmp" or i.op == "int.ucmp" or i.op == "ptr.cmp":
            r = self.same(vs, v, f"{i.op} {i.t} {i.s} {i.x} {', '.join([a.t + ' ' + self.canon(vs, a.v) for a in i.a])}")
        elif i.op == "mem.load" or (i.op == "mach.load" and i.s == ""):
            x = self.reaching(vs, self.addr(vs, i.a[0].v), w // vs.stride, w % vs.stride)
            if x != "":
                r = self.canon(vs, x)
        elif i.op == "mach.addr":
            r = self.same(vs, v, f"address {i.s} {i.k} {self.canon(vs, i.a[0].v)} {self.canon(vs, i.a[1].v)}")
        elif i.op == "field.addr":
            r = self.same(vs, v, f"field {i.a[0].t} {i.k} {self.canon(vs, i.a[0].v)}")
            vs.fieldtype[r] = i.a[0].t
            vs.fieldindex[r] = i.k
        elif i.op == "union.payload":
            # A union box's tag and payload are immutable. Retain the equivalence of
            # repeated narrowed reads expose to dictionary lookup fusion.
            r = self.same(vs, v, f"union.payload {i.s} {self.canon(vs, i.a[0].v)}")
        elif i.op == "tuple.load" or i.op == "tuple.store":
            if v == f"%t{i.r[0]}":
                # Fixed and traversed tuple slots share one semantic address key.
                r = self.same(vs, v, f"address int 0 {self.canon(vs, i.a[0].v)} {i.k}")
            else:
                x = self.reaching(vs, self.addr(vs, f"%t{i.r[0]}"), w // vs.stride, w % vs.stride)
                if x != "":
                    r = self.canon(vs, x)
    vs.depth -= 1
    vs.cn[v] = r
    return r

def gen_same(self, vs: Values, v: str, t: str) -> str:
    # the first value of the computation t (Values.same): v, if it is the first
    if t in vs.same:
        return vs.same[t]
    vs.same[t] = v
    vs.text[v] = t
    return v

def gen_addr(self, vs: Values, a: str) -> str:
    # the canonical address of address a: a slot (%name.N) and a global (@name) are their own
    return self.canon(vs, a) if a.startswith("%t") and a[2:].isdigit() else a

def gen_reaching(self, vs: Values, a: str, j: int, x: int) -> str:
    # the value that the load at position x of block j reads from canonical address a: the
    # value stored or read by the last store or load of a before it, on the one path back
    # through blocks that a single branch leads to (not to a landing block's predecessor, which
    # an unwind edge leaves at an op that raised, before the ops after it, as a store to a
    # that the walk would find from its end: preds), or "" if an op between may write a's
    # memory (a slot's: only a store to it; a global's: a store to it, or an op with wG;
    # another's: a store that may alias it, or an op with wL wD wO), or no such op is found
    # within REACH ops (each load would otherwise walk back over the whole function: a
    # value that is not found is only its own canonical value)
    slot = a.startswith("%") and "." in a
    glob = a.startswith("@")
    heap = not slot and not glob
    stop = FXBIT["wG"] if glob else RAWW
    steps = 0
    while True:
        code = vs.fn.blocks[j].code
        for y in range(x - 1, -1, -1):
            steps += 1
            if steps > REACH:
                return ""
            i = code[y]
            if i.op == "mem.load" or i.op == "mem.store" or i.op == "mach.load" or i.op == "mach.store":
                if i.op == "mach.load" and i.s != "":
                    continue
                p = i.a[0].v
                q = self.addr(vs, p)
                if q == a:
                    return i.a[1].v if i.op == "mem.store" or i.op == "mach.store" else f"%t{i.r[0]}"
                if (i.op == "mem.store" or i.op == "mach.store") and heap and not p.startswith("@") and "." not in p and not self.disjoint(vs, a, q):
                    return ""
                continue
            if i.op == "tuple.load" or i.op == "tuple.store":
                p = f"%t{i.r[0]}"
                q = self.addr(vs, p)
                if q == a:
                    return i.a[1].v if i.op == "tuple.store" else f"%t{i.r[1]}"
                if i.op == "tuple.store" and heap and not self.disjoint(vs, a, q):
                    return ""
                continue
            if not slot and self.opfx(i, vs.fn.fa) & stop != 0:
                return ""
        ps = vs.pl[vs.fn.blocks[j].label]
        if len(ps) != 1 or ps[0] >= j or (len(code) > 0 and code[0].op == "landing"):
            return ""  # (a landing block's predecessors reach it where an op raised, not from their end)
        j = ps[0]
        x = len(vs.fn.blocks[j].code)

def gen_disjoint(self, vs: Values, a: str, b: str) -> bool:
    # whether canonical addresses a and b are fields at different indices of the same class
    # or of unrelated classes: never the same memory. A base and a derived exception class
    # may view one object through different struct types, so their fields may alias.
    if a not in vs.fieldtype or b not in vs.fieldtype:
        return False
    ca = vs.fieldtype[a]
    cb = vs.fieldtype[b]
    if ca == cb:
        return vs.fieldindex[a] != vs.fieldindex[b]
    return not self.derives(ca, cb) and not self.derives(cb, ca)
