"""Optimizations component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, IFn, Ins, Lookup, Val, Values
from src.pystachy_compiler.ircheck import EffectSummaries
from src.pystachy_compiler.specs import CANON_DEPTH, FXBIT, LOOKUPS, RAWW, REACH
from src.pystachy_compiler.utils import is_list, is_union, umembers


def gen_recursionleaf(self) -> int:
    # Depth observation is separate from ordinary effects: the source entry still
    # raises and reads runtime state after this pass. Scan every block, including
    # exceptional/cleanup paths, before changing any function. A counted callee
    # observes its caller's depth even when its own bookkeeping will be elided.
    # Uncounted compiler adapters can be transparent only through a complete
    # transitive proof. Unknown/indirect calls, generators, and U/I operations are
    # boundaries (including limit changes, descriptor callbacks and foreign code).
    # A/R alone are not boundaries: native collection runs no user code. Weakref
    # callbacks are queued for explicit invocation, and generator cleanup is an
    # explicit gen.drop operation; file finalization cannot observe source depth.
    # Uncaught errors and allocation failure can nevertheless run termination
    # callbacks. Keep full bookkeeping when atexit or CPython hooks may exist.
    # A throw of a user exception can also render __str__ before terminating; it
    # is a boundary below even though ordinary effect summaries label it only R.
    if self.ext != "" or len(self.cdirect) > 0 or any(g.v == "@g.atexit$_hook" for g in self.globs):
        return 0
    direct: list[int] = []
    calls: list[list[int]] = []
    bases: list[str] = []
    eligible: list[bool] = []
    observed = FXBIT["I"]
    for fn in self.fns:
        own = fn.counted and not fn.coro and not fn.f.gen and len(fn.blocks[0].code) >= 2
        base = ""
        if own:
            enter = fn.blocks[0].code[0]
            sub = fn.blocks[0].code[1]
            own = enter.op == "rt" and enter.s == "recursion.enter" and len(enter.r) == 1 and fn.rdepth == f"%t{enter.r[0]}"
            own = own and sub.op == "scalar.bin" and sub.s == "sub" and sub.t == "int" and len(sub.a) == 2 and len(sub.r) == 1
            own = own and sub.a[0].v == fn.rdepth and sub.a[1].v == "1"
            if own:
                base = f"%t{sub.r[0]}"
        bases.append(base)
        eligible.append(own)
        m = observed if fn.f.gen or fn.coro else 0
        cs: list[int] = []
        seen: dict[int, bool] = {}
        for b in fn.blocks:
            for at in range(len(b.code)):
                i = b.code[at]
                if own and b is fn.blocks[0] and at < 2:
                    continue  # the validated entry and its caller-depth subtraction
                if own and i.op == "rt" and i.s == "recursion.restore" and len(i.a) == 1 and i.a[0].v in [fn.rdepth, base]:
                    continue
                # These tokens belong only to the bookkeeping above. A future
                # consumer of either token must invalidate this proof explicitly.
                if own and any(a.v == fn.rdepth or a.v == base for a in i.a):
                    m |= observed
                c = i.s if i.op == "call" else "@init." + i.s if i.op == "init" else ""
                if c in self.fll:
                    ix = self.fll[c]
                    callee = self.fns[ix]
                    if callee.counted or callee.f.gen or callee.coro:
                        m |= observed
                    elif ix not in seen:
                        seen[ix] = True
                        cs.append(ix)
                elif i.op == "throw" or i.op.startswith("gen.") or (i.op == "rt" and i.s in ["throw", "reraise"]) or self.opfx(i, fn.fa) & (FXBIT["U"] | FXBIT["I"]) != 0:
                    m |= observed
        direct.append(m)
        calls.append(cs)
    depth = EffectSummaries()
    depth.update(direct, calls)
    n = 0
    for j in range(len(self.fns)):
        if not eligible[j]:
            continue
        fn = self.fns[j]
        base = bases[j]
        if depth.fx[j] != 0 and not recursion_cold(self, fn, base, depth.fx):
            continue
        enter = fn.blocks[0].code[0]
        self.runtime("pys_recursion_check")
        enter.s = "recursion.check"
        enter.t = "None"
        enter.r = []
        fn.blocks[0].code.pop(1)
        for b in fn.blocks:
            b.code = [i for i in b.code if not (i.op == "rt" and i.s == "recursion.restore" and len(i.a) == 1 and i.a[0].v in [fn.rdepth, base])]
        fn.rdepth = ""
        n += 1
    return n


def recursion_cold(self, fn: IFn, base: str, depth: list[int]) -> bool:
    # A function such as JSON number() calls source helpers only on error paths.
    # Its entry check must still run before its body, but publication can wait
    # until an edge into a region that cannot return. All observers must lie in
    # that region; its complement neither reads nor changes depth/limit. Thus an
    # enter at the boundary cannot fail after the entry check passed, and every
    # subsequent callback observes the original active depth. No edge returns to
    # the normal region, so publication occurs at most once on an execution.
    # This does not move a failing *callee* entry check: side effects before its
    # call stay before it. Local handlers/generators require a different proof.
    if len(fn.tries) > 0 or fn.coro or fn.f.gen or fn.gdepth != "":
        return False
    nb = len(fn.blocks)
    at: dict[str, int] = {}
    back: list[list[int]] = []
    returns = [False] * nb
    observes = [False] * nb
    work: list[int] = []
    for j in range(nb):
        at[fn.blocks[j].label] = j
        back.append([])
    for j in range(nb):
        b = fn.blocks[j]
        if b.handler != "":
            return False
        for k in range(len(b.code)):
            i = b.code[k]
            if i.op == "landing" or i.op.startswith("gen."):
                return False
            if j == 0 and k < 2:
                continue
            if i.op == "rt" and i.s == "recursion.restore" and len(i.a) == 1 and i.a[0].v in [fn.rdepth, base]:
                continue
            if any(a.v == fn.rdepth or a.v == base for a in i.a):
                return False
            c = i.s if i.op == "call" else "@init." + i.s if i.op == "init" else ""
            if c in self.fll:
                ix = self.fll[c]
                callee = self.fns[ix]
                observes[j] = observes[j] or callee.counted or callee.f.gen or callee.coro or depth[ix] != 0
            elif i.op == "throw" or (i.op == "rt" and i.s in ["throw", "reraise"]) or self.opfx(i, fn.fa) & (FXBIT["U"] | FXBIT["I"]) != 0:
                observes[j] = True
        t = b.code[len(b.code) - 1]
        if observes[j] and (j == 0 or t.op == "ret" or t.op == "ret.none"):
            return False  # neither the entry nor a returning block can be terminal
        if t.op == "ret" or t.op == "ret.none":
            returns[j] = True
            work.append(j)
        succ: dict[str, bool] = {l: True for l in t.b}
        if t.op == "check":
            succ[fn.cold[t.x if t.x != "" else t.s]] = True
        for l in succ:
            back[at[l]].append(j)
    # Backward reachability is iterative and visits each edge at most once.
    pos = 0
    while pos < len(work):
        j = work[pos]
        pos += 1
        for p in back[j]:
            if not returns[p]:
                returns[p] = True
                work.append(p)
    if not returns[0] or any(returns[j] and observes[j] for j in range(nb)):
        return False
    # Observer-free failure sinks need no publication. In particular the hidden
    # failure edges of `check` must stay in that class: changing fn.cold's shape
    # would invalidate nullcheck's later pruning of unused built-in raise blocks.
    needed = [v for v in observes]
    work = [j for j in range(nb) if observes[j]]
    pos = 0
    while pos < len(work):
        j = work[pos]
        pos += 1
        for p in back[j]:
            if not returns[p] and not needed[p]:
                needed[p] = True
                work.append(p)
    for j in range(nb):
        t = fn.blocks[j].code[len(fn.blocks[j].code) - 1]
        if returns[j] and t.op == "check" and needed[at[fn.cold[t.x if t.x != "" else t.s]]]:
            return False
    bridges: list[Blk] = []
    repairs: dict[str, str] = {}
    for j in range(nb):
        if not returns[j]:
            continue
        b = fn.blocks[j]
        t = b.code[len(b.code) - 1]
        targets: dict[str, bool] = {}
        for l in t.b:
            if not returns[at[l]] and needed[at[l]]:
                targets[l] = True
        redirects: dict[str, str] = {}
        for l in targets:
            fn.n += 1
            bridge = Blk(f"L{fn.n}")
            publish = Ins("rt", "int", "recursion.enter")
            fn.n += 1
            publish.r = [fn.n]
            br = Ins("br", "", "")
            br.b = [l]
            bridge.code = [publish, br]
            bridges.append(bridge)
            redirects[l] = bridge.label
            repairs[l + " " + b.label] = bridge.label
        if len(redirects) > 0:
            t.b = [redirects.get(l, l) for l in t.b]
    # Repair each phi once, not once per incoming edge of a large shared join.
    for b in fn.blocks:
        for phi in b.code:
            if phi.op != "phi":
                break
            phi.b = [repairs.get(b.label + " " + p, p) for p in phi.b]
    fn.blocks.extend(bridges)
    return len(bridges) > 0


def gen_optimize(self, fn: IFn, on: dict[str, bool]) -> int:
    # run the passes on fn that on turns on; how many ops they rewrote
    n = 0
    if "listget" in on:
        n += self.listget(fn)
    if "dictfuse" in on:
        n += self.dictfuse(fn)
    if "unionslots" in on:
        n += self.unionslots(fn)
    if "nullcheck" in on:
        n += self.nullcheck(fn)
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
            if i.op == "rt" and (i.s == "dict.has" or i.s == "dict.getitem" or i.s == "dict.set") and "H" not in i.x:
                # (but a lookup of keys hashed by their class: CPython runs __hash__ and __eq__
                # at each, which its effects, U, show)
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
                        i.x = ""
                    else:
                        self.runtime("pys_dict_entry_set")
                        i.s = "dict.entry_set"
                        i.a = [i.a[0], ev, i.a[2]]
                        i.x = ""
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
            fi.x = i.x
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
            en.x = i.x
            en.r = [f.e]
            code.insert(x, en)
            self.runtime("pys_dict_val")
            i.s = "dict.val"
            i.a = [i.a[0], Val(f"%t{f.e}", "int")]
            i.x = ""
        n += 1
    return n

def gen_unionslots(self, fn: IFn) -> int:
    # Locals of a union of numbers out of the heap. Such a local's slot holds a box (each value
    # a ubox's); where its address goes nowhere but to its loads and stores, it becomes two int
    # slots, its value's tag and its payload's bits. A store keeps the parts of what it stores
    # (uparts: a ubox's operands, a union phi's as phis of its incoming values' parts, else what
    # union.tag and union.raw read of the box where it is made); a load reads them, and the
    # union.tag and union.payload/raw of what it loaded become them. A load whose value goes
    # elsewhere too (a call, a return, a phi: it leaves the local) makes the box there, so a
    # slot is split only where each such load follows a store of a box that goes (upaid): no
    # more boxes than before, also where a store's box was made elsewhere (a call's, a
    # parameter's), which a load that leaves would box again. A ubox, slot.pack, union read or
    # union phi that nothing uses any more goes: a loop that adds floats to an int | float local
    # allocates nothing. A generator's locals stay (its frame keeps them). How many slots it split
    if fn.coro:
        return 0
    cands = [s for s in fn.slots if s.k == 0 and is_union(s.t) and len([m for m in umembers(s.t) if m != "int" and m != "float" and m != "bool"]) == 0]
    if len(cands) == 0:
        return 0  # (no local of a union of numbers: defs and uses would go unread)
    defs: dict[str, list[int]] = {}  # a value -> the block and position of the op that makes it
    uses: dict[str, list[list[int]]] = {}  # a value -> the block, position and operand of each use
    for j in range(len(fn.blocks)):
        code = fn.blocks[j].code
        for x in range(len(code)):
            i = code[x]
            for r in i.r:
                defs[f"%t{r}"] = [j, x]
            for k in range(len(i.a)):
                if i.a[k].v not in uses:
                    uses[i.a[k].v] = []
                uses[i.a[k].v].append([j, x, k])
    split: dict[str, Ins] = {}  # a slot that splits: its address -> its slot
    for s in cands:
        addr = f"%{s.s or 'h'}.{s.r[0]}"
        ok = addr in uses
        for u in uses.get(addr, []):
            i = fn.blocks[u[0]].code[u[1]]
            if u[2] != 0 or (i.op != "mem.load" and i.op != "mem.store") or (i.op == "mem.store" and not self.usplits(fn, defs, i.a[1].v, {})):
                ok = False
            elif i.op == "mem.load":
                for w in uses.get(f"%t{i.r[0]}", []):
                    o = fn.blocks[w[0]].code[w[1]]
                    if (o.op == "union.payload" or o.op == "union.raw") and f"%t{o.r[0]}" in uses:
                        ok = False  # (its address taken: nothing does)
        if ok:
            split[addr] = s
    gone = 1
    while gone > 0:
        # (a copy to a slot that splits does not leave, until that slot does not split)
        gone = 0
        for addr in [a for a in split]:
            if not self.upaid(fn, defs, uses, addr, split):
                del split[addr]
                gone += 1
    if len(split) == 0:
        return 0
    halves: dict[str, list[str]] = {}  # a split slot's address -> its tag's and payload's slots
    for addr in split:
        s = split[addr]
        halves[addr] = []
        for half in ["tag", "pay"]:
            fn.n += 1
            h = Ins("slot", "int", f"{s.s or 'h'}.{half}")
            h.r = [fn.n]
            fn.slots.append(h)
            halves[addr].append(f"%{h.s}.{fn.n}")
    parts: dict[str, list[str]] = {}  # a union value -> its tag and its payload's bits (uparts)
    before: dict[str, list[Ins]] = {}  # "j:x" -> ops to put before op x of block j
    after: dict[str, list[Ins]] = {}  # "j:x" -> ops to put after it
    repl: dict[str, list[Ins]] = {}  # "j:x" -> the ops that replace it
    heads: dict[int, list[Ins]] = {}  # block j -> phis to put after its phis
    ren: dict[str, str] = {}  # a value -> the value that replaces it
    for addr in split:
        for u in uses[addr]:
            i = fn.blocks[u[0]].code[u[1]]
            if i.op != "mem.load":
                continue
            v = f"%t{i.r[0]}"
            ops: list[Ins] = []
            for half in halves[addr]:
                fn.n += 1
                ld = Ins("mem.load", "int", "")
                ld.a = [Val(half, "*int")]
                ld.r = [fn.n]
                ops.append(ld)
            parts[v] = [f"%t{ops[0].r[0]}", f"%t{ops[1].r[0]}"]
            for w in uses.get(v, []):
                o = fn.blocks[w[0]].code[w[1]]
                if o.op == "union.tag" or self.tag_read(o):
                    ren[f"%t{o.r[0]}"] = parts[v][0]
                    repl[f"{w[0]}:{w[1]}"] = []
                elif o.op == "union.payload" or o.op == "union.raw":
                    p = Ins("slot.pack", "%slot", "")
                    p.a = [Val(parts[v][1], "int")]
                    p.r = [o.r[1]]
                    repl[f"{w[0]}:{w[1]}"] = [p]
            if self.uleaves(fn, uses, i, split):  # (a copy to a slot that splits stores the parts)
                # (the box that leaves, as the value it replaces)
                box = Ins("rt", "%ptr", "ubox")
                box.a = [Val(parts[v][0], "int"), Val(parts[v][1], "*T")]
                box.r = [i.r[0]]
                ops.append(box)
            repl[f"{u[0]}:{u[1]}"] = ops
    for addr in split:
        for u in uses[addr]:
            i = fn.blocks[u[0]].code[u[1]]
            if i.op != "mem.store":
                continue
            q = self.uparts(fn, defs, i.a[1].v, split[addr].t, parts, before, after, heads)
            ops = []
            for k in range(2):
                st = Ins("mem.store", "", "")
                st.a = [Val(halves[addr][k], "*int"), Val(q[k], "int")]
                ops.append(st)
            repl[f"{u[0]}:{u[1]}"] = ops
    for j in range(len(fn.blocks)):
        b = fn.blocks[j]
        code = []
        put = j not in heads
        for x in range(len(b.code)):
            key = f"{j}:{x}"
            if not put and b.code[x].op != "phi":
                code.extend(heads[j])
                put = True
            code.extend(before.get(key, []))
            if key in repl:
                code.extend(repl[key])
            else:
                code.append(b.code[x])
            code.extend(after.get(key, []))
        b.code = code
    for b in fn.blocks:
        for i in b.code:
            for a in i.a:
                if a.v in ren:
                    a.v = ren[a.v]
    fn.slots = [s for s in fn.slots if s.k != 0 or f"%{s.s or 'h'}.{s.r[0]}" not in split]  # (its flag stays)
    gone = 1
    while gone > 0:
        # (what nothing uses any more, of what these ops make)
        used: dict[str, bool] = {}
        for b in fn.blocks:
            for i in b.code:
                for a in i.a:
                    used[a.v] = True
        gone = 0
        for b in fn.blocks:
            code = []
            for i in b.code:
                pure = (i.op == "rt" and i.s == "ubox") or i.op == "slot.pack" or i.op == "union.tag" or i.op == "union.payload" or i.op == "union.raw" or (i.op == "phi" and (is_union(i.t) or i.t == "int"))
                if pure and len([r for r in i.r if f"%t{r}" in used]) == 0:
                    gone += 1
                else:
                    code.append(i)
            b.code = code
    return len(split)

def gen_tag_read(self, i: Ins) -> bool:
    # does op i, which a union box's value is an operand of (unionslots), read the box's tag as
    # union.tag does: an int load of its first word, as the dispatch of str(), truth tests,
    # equality and methods reads it (Gen.mload of the box)
    return i.op == "mach.load" and i.t == "int" and i.s == ""

def gen_usplits(self, fn: IFn, defs: dict[str, list[int]], v: str, seen: dict[str, bool]) -> bool:
    # can unionslots take apart union value v: an op's (a phi's where its incoming values'
    # are) or a parameter's
    if v in seen or (v.startswith("%a") and v[2:].isdigit()):
        return True
    if v not in defs:
        return False
    seen[v] = True
    i = fn.blocks[defs[v][0]].code[defs[v][1]]
    if i.op == "phi":
        for a in i.a:
            if not self.usplits(fn, defs, a.v, seen):
                return False
    return True

def gen_uparts(self, fn: IFn, defs: dict[str, list[int]], v: str, t: str, parts: dict[str, list[str]], before: dict[str, list[Ins]], after: dict[str, list[Ins]], heads: dict[int, list[Ins]]) -> list[str]:
    # the tag and the payload's bits of value v of union t (unionslots): a ubox's operands; a
    # phi's as two phis, put after the phis of its block, of its incoming values' parts; else
    # what union.tag and union.raw read of the box, put where v is made (a parameter: as the
    # function begins), so that they are there wherever v is
    if v in parts:
        return parts[v]
    d = defs[v] if v in defs else [0, -1]
    i = fn.blocks[d[0]].code[d[1]] if d[1] >= 0 else Ins("", "", "")
    if i.op == "rt" and i.s == "ubox":
        parts[v] = [i.a[0].v, i.a[1].v]
        return parts[v]
    if i.op == "phi":
        ph: list[Ins] = []
        for k in range(2):
            fn.n += 1
            p = Ins("phi", "int", "")
            p.r = [fn.n]
            p.a = []
            p.b = []
            ph.append(p)
        parts[v] = [f"%t{ph[0].r[0]}", f"%t{ph[1].r[0]}"]  # (first: a loop's phi meets itself)
        for k in range(len(i.a)):
            q = self.uparts(fn, defs, i.a[k].v, t, parts, before, after, heads)
            for h in range(2):
                ph[h].a.append(Val(q[h], "int"))
                ph[h].b.append(i.b[k])
        if d[0] not in heads:
            heads[d[0]] = []
        heads[d[0]].extend(ph)
        return parts[v]
    fn.n += 1
    tg = Ins("union.tag", "int", "")
    tg.a = [Val(v, t)]
    tg.r = [fn.n]
    pl = Ins("union.raw", "%slot", "")
    pl.a = [Val(v, t)]
    pl.r = [fn.n + 1, fn.n + 2]
    fn.n += 2
    parts[v] = [f"%t{tg.r[0]}", f"%t{pl.r[1]}"]
    key = f"{d[0]}:{d[1]}" if d[1] >= 0 else "0:0"
    at = after if d[1] >= 0 else before
    if key not in at:
        at[key] = []
    at[key].extend([tg, pl])
    return parts[v]

def gen_uleaves(self, fn: IFn, uses: dict[str, list[list[int]]], i: Ins, split: dict[str, Ins]) -> bool:
    # does the value of load i of a slot that unionslots splits leave the local: go to an op other
    # than its union.tag, its union.payload/raw, a tag read and a store to a slot that splits too
    for w in uses.get(f"%t{i.r[0]}", []):
        o = fn.blocks[w[0]].code[w[1]]
        if not (o.op == "union.tag" or o.op == "union.payload" or o.op == "union.raw" or self.tag_read(o) or (o.op == "mem.store" and w[2] == 1 and o.a[0].v in split)):
            return True
    return False

def gen_ufresh(self, fn: IFn, defs: dict[str, list[int]], uses: dict[str, list[list[int]]], v: str, seen: dict[str, bool]) -> bool:
    # is union value v a box made for its one use alone (unionslots): a ubox's, or a phi's of such
    # boxes, which goes once the store that uses it is split
    if v in seen or v not in defs or len(uses.get(v, [])) != 1:
        return False
    seen[v] = True
    i = fn.blocks[defs[v][0]].code[defs[v][1]]
    if i.op == "phi":
        for a in i.a:
            if not self.ufresh(fn, defs, uses, a.v, seen):
                return False
        return True
    return i.op == "rt" and i.s == "ubox"

def gen_upaid(self, fn: IFn, defs: dict[str, list[int]], uses: dict[str, list[list[int]]], addr: str, split: dict[str, Ins]) -> bool:
    # may unionslots split the slot at addr: does each of its loads that leave, which makes a
    # box, follow on every path a store of a box that goes (ufresh), with no other such load
    # between them, so that it makes no more boxes than before. A loop's load that leaves needs
    # such a store in the loop; a store of a call's or a parameter's box pays for none
    at: dict[str, int] = {}
    for k in range(len(fn.blocks)):
        at[fn.blocks[k].label] = k
    ops: dict[str, int] = {}  # "j:x" -> 1 for a store of a box that goes, 2 for a load that leaves
    for u in uses[addr]:
        i = fn.blocks[u[0]].code[u[1]]
        if i.op == "mem.store" and self.ufresh(fn, defs, uses, i.a[1].v, {}):
            ops[f"{u[0]}:{u[1]}"] = 1
        elif i.op == "mem.load" and self.uleaves(fn, uses, i, split):
            ops[f"{u[0]}:{u[1]}"] = 2
    paid: list[bool] = []  # block j -> is a box paid for as it begins (none at the entry; else
    for j in range(len(fn.blocks)):  # until a path into it shows otherwise)
        paid.append(j != 0)
    more = True
    while more:
        more = False
        for j in range(len(fn.blocks)):
            b = fn.blocks[j]
            now = paid[j]
            low = now  # (what a raise in the block finds at its handler)
            for x in range(len(b.code)):
                k = ops.get(f"{j}:{x}", 0)
                if k == 2 and not now:
                    return False
                now = k == 1 or (now and k == 0)
                low = low and now
            for l in b.code[len(b.code) - 1].b:
                if l in at and paid[at[l]] and not now:
                    paid[at[l]] = False
                    more = True
            if b.handler in at and paid[at[b.handler]] and not low:
                paid[at[b.handler]] = False
                more = True
    return True

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
        elif i.op == "union.payload" or i.op == "union.raw" or i.op == "dyn.payload":
            # A union box's tag and payload are immutable. Retain the equivalence of
            # repeated narrowed reads expose to dictionary lookup fusion.
            r = self.same(vs, v, f"{i.op} {i.s} {self.canon(vs, i.a[0].v)}")
        elif i.op == "dyn.type":
            r = self.same(vs, v, f"dyn.type {self.canon(vs, i.a[0].v)}")
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

def gen_nullcheck(self, fn: IFn) -> int:
    # Null checks that another test makes redundant (#787). A check that a value is not None
    # (Gen.notnone's, before a read through it) cannot fail where the same value has passed
    # such a test on every path to it: where a block that only a passed test leads to (the
    # block after a check of it, or the branch of a cbr on a ptr.cmp of it with null where it
    # is not None, when that block has no other predecessor) dominates the check's block. The
    # same value is the value itself, one equal to it (canon), or a load of a slot that only
    # the entry block stores and only loads and stores use (a parameter the function never
    # assigns: every load of it after those stores reads what was passed, on any path, back
    # edges and unwind edges included). Such a check becomes a br, its ptr.cmp goes once
    # nothing reads it, the block after it joins its block where nothing else goes there, and
    # a cold block that no check goes to any more goes too. A walk down the dominator tree
    # (Cooper, Harvey and Kennedy's) keeps what is known on the way, so that the work grows
    # linearly with the function. It runs on every function, and what it allocates makes the
    # collector run sooner, so it keeps no map of every value and no list for each block: it
    # leaves a function without checks, or with fewer than two tests that terminators make, at
    # once, and makes Values only where two tests need canon. How many checks it removed
    nb = len(fn.blocks)
    stride = 1
    some = False
    for b in fn.blocks:
        if len(b.code) >= stride:
            stride = len(b.code) + 1
        some = some or b.code[len(b.code) - 1].op == "check"
    if not some:
        return 0
    # one walk over the ops: the null tests (a ptr.cmp of a value with null) and their blocks;
    # where each load is (its block * stride + its position); and the slots that only the entry
    # block stores and only loads and stores use, as the position in the entry block after the
    # last store there (-1 for another slot)
    tests: dict[str, Ins] = {}
    tblk: dict[str, int] = {}
    lds = [-1] * (fn.n + 1)
    slots: dict[str, int] = {}
    for s in fn.slots:
        if s.k == 0:
            slots[f"%{s.s or 'h'}.{s.r[0]}"] = 0
    for j in range(nb):
        code = fn.blocks[j].code
        for x in range(len(code)):
            i = code[x]
            if i.op == "mem.load":
                if len(i.r) == 1 and i.r[0] < len(lds):
                    lds[i.r[0]] = j * stride + x
            elif i.op == "ptr.cmp" and (i.s == "==" or i.s == "!=") and (i.a[0].v == "null") != (i.a[1].v == "null"):
                v = f"%t{i.r[0]}"
                tests[v] = i
                tblk[v] = j
            for k in range(len(i.a)):
                a = i.a[k].v
                if a in slots and slots[a] >= 0 and (k != 0 or i.op != "mem.load"):
                    slots[a] = x + 1 if k == 0 and i.op == "mem.store" and j == 0 else -1
    # the tests that terminators make: a check's of v == null, which may go, or a cbr's; one goes
    # only where another comes before it. Each one's key: its slot's (nullslot), else its
    # canonical value
    keys: dict[str, str] = {}
    rest: list[str] = []  # the tests whose key is their canonical value
    some = False
    nterm = 0
    for b in fn.blocks:
        t = b.code[len(b.code) - 1]
        if (t.op == "check" or t.op == "cbr") and len(t.a) > 0 and t.a[0].v in tests:
            some = some or (t.op == "check" and tests[t.a[0].v].s == "==")
            nterm += 1
            if t.a[0].v not in keys:
                keys[t.a[0].v] = self.nullslot(fn, lds, stride, slots, tests[t.a[0].v])
                if keys[t.a[0].v] == "":
                    rest.append(t.a[0].v)
    if not some or nterm < 2:
        return 0
    # the blocks each block goes to, sx[so[j]:so[j + 1]] for block j: its terminator's, then its
    # landing block (an unwind edge, along which only what holds where the block starts holds),
    # each once; how many blocks go to each block, and the last whose terminator goes there
    # (flat lists, not a list for each block, as are the predecessors and the dominator tree's
    # children below)
    at: dict[str, int] = {}
    for j in range(nb):
        if fn.blocks[j].label != "":
            at[fn.blocks[j].label] = j
    so = [0] * (nb + 1)
    sx: list[int] = []
    npred = [0] * nb
    pred1 = [-1] * nb
    for j in range(nb):
        b = fn.blocks[j]
        ls = b.code[len(b.code) - 1].b
        for e in range(len(ls) + 1):
            l = ls[e] if e < len(ls) else b.handler
            if l in at:
                c = at[l]
                new = True
                for u in range(so[j], len(sx)):
                    new = new and sx[u] != c
                if new:
                    sx.append(c)
                    npred[c] += 1
                    if e < len(ls):
                        pred1[c] = j
        so[j + 1] = len(sx)
    # the blocks that the entry block reaches, in postorder (the entry block last), and their
    # dominators
    seen = [False] * nb
    seen[0] = True
    post: list[int] = []
    stack = [0]
    nxt = [0]  # the next successor to visit, of each block on the stack
    while len(stack) > 0:
        j = stack[len(stack) - 1]
        k = nxt[len(nxt) - 1]
        if so[j] + k < so[j + 1]:
            nxt[len(nxt) - 1] = k + 1
            c = sx[so[j] + k]
            if not seen[c]:
                seen[c] = True
                stack.append(c)
                nxt.append(0)
        else:
            post.append(j)
            stack.pop()
            nxt.pop()
    num = [0] * nb  # a reached block's position in reverse postorder
    for k in range(len(post)):
        num[post[k]] = len(post) - 1 - k
    po = [0] * (nb + 1)  # each block's predecessors: px[po[j]:po[j + 1]]
    for e in range(len(sx)):
        po[sx[e] + 1] += 1
    for j in range(nb):
        po[j + 1] += po[j]
    px = [0] * len(sx)
    fill = [0] * nb
    for j in range(nb):
        for e in range(so[j], so[j + 1]):
            px[po[sx[e]] + fill[sx[e]]] = j
            fill[sx[e]] += 1
    idom = [-1] * nb
    idom[0] = 0
    changed = True
    while changed:
        changed = False
        for k in range(len(post) - 2, -1, -1):
            j = post[k]
            d = -1
            for e in range(po[j], po[j + 1]):
                p = px[e]
                if idom[p] < 0:
                    continue
                if d < 0:
                    d = p
                    continue
                x = p
                while x != d:
                    while num[x] > num[d]:
                        x = idom[x]
                    while num[d] > num[x]:
                        d = idom[d]
            if d != idom[j]:
                idom[j] = d
                changed = True
    ko = [0] * (nb + 1)  # each block's children in the dominator tree: kx[ko[j]:ko[j + 1]]
    for k in range(len(post) - 1):
        ko[idom[post[k]] + 1] += 1
    for j in range(nb):
        ko[j + 1] += ko[j]
        fill[j] = 0
    kx = [0] * (len(post) - 1)
    for k in range(len(post) - 2, -1, -1):
        d = idom[post[k]]
        kx[ko[d] + fill[d]] = post[k]
        fill[d] += 1
    # (a test whose key is its canonical value is the same value as no other where it is the only one)
    if len(rest) > 1:
        vs = Values(fn, self.preds(fn))
        for v in rest:
            q = tests[v]
            keys[v] = self.canon(vs, q.a[0].v if q.a[1].v == "null" else q.a[1].v)
    else:
        for v in rest:
            keys[v] = v
    # down the dominator tree: what a block's one predecessor's test tells, while in it
    known: dict[str, bool] = {}
    gone: list[int] = []  # the blocks whose check goes
    stack = [0]
    nxt = [0]
    adds = [""]  # what each block on the stack made known
    while len(stack) > 0:
        j = stack[len(stack) - 1]
        k = nxt[len(nxt) - 1]
        if k == 0 and len(known) > 0:
            t = fn.blocks[j].code[len(fn.blocks[j].code) - 1]
            if t.op == "check" and t.a[0].v in keys and tests[t.a[0].v].s == "==" and keys[t.a[0].v] in known:
                gone.append(j)
        if k < ko[j + 1] - ko[j]:
            nxt[len(nxt) - 1] = k + 1
            c = kx[ko[j] + k]
            key = ""
            p = pred1[c] if npred[c] == 1 else -1
            if p >= 0:
                t = fn.blocks[p].code[len(fn.blocks[p].code) - 1]
                if len(t.a) > 0 and t.a[0].v in keys:
                    q = tests[t.a[0].v]
                    if (t.op == "check" and q.s == "==") or (t.op == "cbr" and t.b[0] != t.b[1] and (q.s == "==") == (fn.blocks[c].label == t.b[1])):
                        key = keys[t.a[0].v]
            if key != "" and key not in known:
                known[key] = True
            else:
                key = ""
            stack.append(c)
            nxt.append(0)
            adds.append(key)
        else:
            if adds[len(adds) - 1] != "":
                del known[adds[len(adds) - 1]]
            stack.pop()
            nxt.pop()
            adds.pop()
    if len(gone) == 0:
        return 0
    # each check that goes becomes a br, and its test goes where nothing else reads it
    reads: dict[str, int] = {}  # the tests of the checks that go -> how many ops read them then
    brs = [False] * nb  # the blocks that end with such a br
    for j in gone:
        code = fn.blocks[j].code
        t = code[len(code) - 1]
        br = Ins("br", "", "")
        br.b = [t.b[0]]
        code[len(code) - 1] = br
        brs[j] = True
        reads[t.a[0].v] = 0
    for b in fn.blocks:
        for i in b.code:
            for o in i.a:
                if o.v in reads:
                    reads[o.v] = reads[o.v] + 1
    for v in reads:
        if reads[v] == 0:
            q = tests[v]
            fn.blocks[tblk[v]].code = [i for i in fn.blocks[tblk[v]].code if i is not q]
    # a cold block that no check goes to any more goes, and the block without a label that goes
    # to the first cold block, after a ret (gen_function), if it goes there
    cold: dict[str, bool] = {}  # the cold blocks some check still goes to
    for b in fn.blocks:
        t = b.code[len(b.code) - 1]
        if t.op == "check":
            cold[fn.cold[t.x if t.x != "" else t.s]] = True
    dead: dict[str, bool] = {}  # the others
    for key in [key for key in fn.cold]:
        if fn.cold[key] not in cold:
            dead[fn.cold[key]] = True
            del fn.cold[key]
            if key in fn.coldh:
                del fn.coldh[key]
    drop = [False] * nb  # the blocks that go
    if len(dead) > 0:
        for j in range(nb):
            b = fn.blocks[j]
            t = b.code[len(b.code) - 1]
            drop[j] = b.label in dead or (b.label == "" and t.op == "br" and t.b[0] in dead)
    # a block that only such a br goes to joins it, but for a block that a loop's or a try
    # statement's shape names, or that starts with a phi or a landing op
    pin: dict[str, bool] = {"entry": True}
    for lp in fn.loops:
        for l in [lp.head, lp.body, lp.step, lp.exit] + lp.tests:
            pin[l] = True
    for tr in fn.tries:
        for l in [tr.body, tr.landing, tr.final, tr.orelse, tr.exit]:
            pin[l] = True
    pin[fn.gpad] = True
    for j in range(nb):
        if not brs[j] or drop[j]:
            continue
        b = fn.blocks[j]
        while True:
            t = b.code[len(b.code) - 1]
            l = t.b[0] if t.op == "br" else ""
            if l not in at or l in pin:
                break
            c = at[l]
            cb = fn.blocks[c]
            if c == j or npred[c] != 1 or drop[c] or cb.handler != b.handler or cb.code[0].op == "phi" or cb.code[0].op == "landing":
                break
            b.code.pop()
            b.code.extend(cb.code)
            drop[c] = True
            # (a phi after it names this block now)
            for sl in cb.code[len(cb.code) - 1].b:
                if sl in at:
                    for i in fn.blocks[at[sl]].code:
                        if i.op != "phi":
                            break
                        i.b = [b.label if y == l else y for y in i.b]
            if not brs[c]:
                break
    fn.blocks = [fn.blocks[j] for j in range(nb) if not drop[j]]
    return len(gone)

def gen_nullslot(self, fn: IFn, lds: list[int], stride: int, slots: dict[str, int], q: Ins) -> str:
    # nullcheck's key of the value that ptr.cmp q compares with null where it is a load of a slot
    # that only the entry block stores, after its stores there: "slot " and the slot; else ""
    v = q.a[0].v if q.a[1].v == "null" else q.a[1].v
    w = -1
    if v.startswith("%t") and v[2:].isdigit() and int(v[2:]) < len(lds):
        w = lds[int(v[2:])]
    if w >= 0:
        a = fn.blocks[w // stride].code[w % stride].a[0].v
        if slots.get(a, -1) >= 0 and (w >= stride or w % stride >= slots[a]):
            return "slot " + a
    return ""
