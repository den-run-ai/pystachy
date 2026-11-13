"""Optimizations component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import os
from src.pystachy_compiler.diagnostics import dynamic_program, fail, int_lists, int_program
from src.pystachy_compiler.ir import Blk, IFn, Ins, Lookup, Loop, Val, Values, tmpname, one_num
from src.pystachy_compiler.ircheck import EffectSummaries
from src.pystachy_compiler.specs import CANON_DEPTH, FXALL, FXBIT, LOOKUPS, NONEVAR, RAWW, REACH
from src.pystachy_compiler.utils import is_list, is_opt, is_tuple, is_union, umembers


# Every non-read summary effect: exceptions, allocation/GC, callbacks, runtime
# state and writes must remain bounded for later optimizations and EH lowering.
# Representation rewrites can introduce reads of immutable boxes, classified more
# broadly by IROPS than the original local-slot reads. Read-sensitive consumers
# must rerun effects() after those rewrites instead of using the old read bounds.
PASS_SAFETY_EFFECTS = FXALL & ~(FXBIT["rL"] | FXBIT["rD"] | FXBIT["rO"] | FXBIT["rG"] | FXBIT["rF"])


class PassContract:
    # Contracts for the existing pre-EH function passes. Analyses are owned by one
    # invocation of a pass: Values, predecessor maps and proofs never survive it.
    # "invalidates" describes snapshots a future consumer must rebuild, not a cache
    # that exists today. Non-read effect bounds remain sound even when a pass
    # invalidates read bounds or exact effect summaries.
    def __init__(self, name: str, analyses: list[str], preserves: list[str], invalidates: list[str]):
        self.name = name
        self.requires = ["typed-ir", "pre-eh", "effect-safety-bounds"]
        self.analyses = analyses
        self.preserves = ["typed-ir", "pre-eh", "effect-safety-bounds"] + preserves
        self.invalidates = invalidates
        self.rerun = ["typed-ir", "pre-eh", "effect-safety-bounds"]


# Dispatch order is part of the contract: every local analysis sees the previous
# pass's rewritten IR, and nullcheck can change the CFG after the other passes.
PASS_CONTRACTS: list[PassContract] = [
    PassContract("charslots", ["uses", "predecessors", "reaching-stores"],
                 ["cfg", "loop-shape"],
                 ["values", "range-proofs", "alias-proofs", "slot-layout", "exact-effects"]),
    PassContract("listget", ["predecessors", "loop-ranges", "values", "invariant-slots"],
                 ["cfg", "loop-shape", "slot-layout"],
                 ["values", "range-proofs", "alias-proofs", "exact-effects"]),
    PassContract("listguard", ["predecessors", "loop-ranges", "values", "invariant-slots"],
                 ["slot-layout"],
                 ["values", "range-proofs", "alias-proofs", "cfg", "loop-shape", "exact-effects"]),
    PassContract("dictfuse", ["predecessors", "values", "lookup-proofs"],
                 ["cfg", "loop-shape", "slot-layout"],
                 ["values", "range-proofs", "alias-proofs", "exact-effects"]),
    PassContract("unionslots", ["values", "uses", "alias-proofs", "reaching-stores"],
                 ["cfg", "loop-shape"],
                 ["values", "range-proofs", "alias-proofs", "slot-layout", "read-effect-bounds", "exact-effects"]),
    PassContract("nullcheck", ["predecessors", "dominators", "values", "reaching-stores"],
                 ["loop-shape", "slot-layout"],
                 ["values", "range-proofs", "alias-proofs", "cfg", "dominators", "exact-effects"]),
]


def gen_pass_check(self, fn: IFn, contract: PassContract, after: bool) -> None:
    # Debug-only enforcement. program() verifies the initial typed IR; a changed
    # pass reruns it before another pass can consume the result. No analysis of the
    # function or effect recomputation is added to the normal compilation path.
    checks = contract.rerun if after else contract.requires
    if after and "typed-ir" in checks:
        self.verify(fn, False)
    if "pre-eh" in checks and fn.pads:
        fail(f"internal error: {contract.name} requires pre-EH IR in {fn.f.ll}", 0)
    actual = 0
    for b in fn.blocks:
        for i in b.code:
            if "pre-eh" in checks and len(i.b) == 2 and (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume"):
                fail(f"internal error: {contract.name} requires pre-EH IR in {fn.f.ll}", 0)
            # Like effects(): an entry snapshot itself adds no observable effect.
            # recursionscope gives counted entries their real R/I effects instead.
            snapshot = b is fn.blocks[0] and i is b.code[0] and i.op == "rt" and i.s == "recursion.depth" and len(i.r) == 1 and tmpname(i.r[0]) == fn.rdepth
            if "effect-safety-bounds" in checks and not snapshot:
                actual |= self.opfx(i, fn.fa) & PASS_SAFETY_EFFECTS
    if "effect-safety-bounds" in checks and actual & ~fn.fx != 0:
        fail(f"internal error: {contract.name} requires conservative effect safety bounds in {fn.f.ll}", 0)


def recursion_cycles(calls: list[list[int]], comp: list[int]) -> list[bool]:
    # Whether each function lies on a cycle of the program's direct calls (the callees of its
    # call and init ops, EffectSummaries.calls, through uncounted adapters too), including a
    # call of itself: Tarjan's strongly connected components, with explicit stacks (no
    # recursion; each edge is followed once). comp gets each function's component: the
    # functions of one cycle share it.
    nf = len(calls)
    index = [-1] * nf
    low = [0] * nf
    onstack = [False] * nf
    cyclic = [False] * nf
    stack: list[int] = []
    count = 0
    for root in range(nf):
        if index[root] >= 0:
            continue
        index[root] = count
        low[root] = count
        count += 1
        stack.append(root)
        onstack[root] = True
        work = [root]
        edges = [0]
        while len(work) > 0:
            v = work[len(work) - 1]
            e = edges[len(edges) - 1]
            if e < len(calls[v]):
                edges[len(edges) - 1] = e + 1
                w = calls[v][e]
                if w == v:
                    cyclic[v] = True
                elif index[w] < 0:
                    index[w] = count
                    low[w] = count
                    count += 1
                    stack.append(w)
                    onstack[w] = True
                    work.append(w)
                    edges.append(0)
                elif onstack[w] and index[w] < low[v]:
                    low[v] = index[w]
                continue
            work.pop()
            edges.pop()
            if len(work) > 0 and low[v] < low[work[len(work) - 1]]:
                low[work[len(work) - 1]] = low[v]
            if low[v] == index[v]:
                members: list[int] = []
                while True:
                    w = stack.pop()
                    onstack[w] = False
                    members.append(w)
                    comp[w] = v
                    if w == v:
                        break
                if len(members) > 1:
                    for w in members:
                        cyclic[w] = True
    return cyclic


def recursion_snapshot(fn: IFn) -> int:
    # the position, in fn's entry block, of the op that gen_enter made fn.rdepth
    code = fn.blocks[0].code
    for at in range(len(code)):
        i = code[at]
        if i.op == "rt" and i.s == "recursion.depth" and len(i.r) == 1 and tmpname(i.r[0]) == fn.rdepth:
            return at
    fail(f"internal error: {fn.f.ll} has no entry depth for its recursion accounting", 0)
    return -1


def recursion_unsnapshot(fn: IFn) -> None:
    # fn's entry depth, which no handler restores, is not needed
    fn.blocks[0].code.pop(recursion_snapshot(fn))
    fn.rdepth = ""


def recursion_resume_site(code: list[Ins], at: int) -> list[int]:
    # the positions of the accounting gen_resume_enter put around the resume at code[at] (its entry,
    # recursion.resume; the depth it entered from; and that depth's restoration after the resume),
    # or [] if not found
    enter = at - 1
    while enter >= 0 and not (code[enter].op == "rt" and code[enter].s == "recursion.resume"):
        enter -= 1
    if enter < 0 or enter + 1 >= at or len(code[enter].r) != 1:
        return []
    sub = code[enter + 1]
    if (sub.op != "scalar.bin" or sub.s != "sub" or len(sub.r) != 1 or len(sub.a) != 2
            or sub.a[0].v != tmpname(code[enter].r[0]) or sub.a[1].v != "1"):
        return []
    for after in range(at + 1, len(code)):
        i = code[after]
        if i.op == "rt" and i.s == "recursion.restore" and len(i.a) == 1 and i.a[0].v == tmpname(sub.r[0]):
            return [enter, enter + 1, after]
    return []


def gen_recursionscope(self) -> int:
    # The native depth counts the activations that recursion can repeat
    # (docs/internals.md#native-recursion-depth), once the whole program is built and
    # Gen.effects has summarized it. The graph is the summaries' direct calls, and from each
    # resume or drop of a generator handle gen[Y] an edge to every generator body that makes
    # such handles (they share the type). A function can be entered again while it is active
    # only if it lies on a cycle of that graph or reaches code that the graph does not show
    # (U, apart from generator resumes, which are edges, and a body's own yields, which
    # suspend it): an icall, a runtime callback such as an __eq__ or __repr__. Any other
    # function is at most once on any native stack, so its frame can change at which call a
    # bounded recursion fails, never whether an unbounded one is caught: every cycle passes
    # through a counted function or a counted resume. Such a source function neither checks
    # nor counts; its handlers still restore the depth it was entered at (callees that raised
    # may have left it higher). A counted one's entry op checks and counts
    # (pys.recursion.enter), its handlers restore that active depth, and each normal return
    # the caller's. A resume counts the generator body it runs unless no body of the
    # handle's type can be entered again, and so does closing one (pys.gen.drop.counted). The summaries gain
    # exactly the entries' and returns' effects (R I) without another walk of every op, or
    # are computed again where resumes lose their accounting. Returns how many functions count.
    nf = len(self.fns)
    calls = self.summaries.calls
    unknown = FXBIT["U"]
    bodies: dict[str, list[int]] = {}
    for j in range(nf):
        if self.fns[j].f.gen:
            t = self.fns[j].f.ret
            if t not in bodies:
                bodies[t] = []
            bodies[t].append(j)
    edges: list[list[int]] = []
    local: list[int] = []
    for j in range(nf):
        fn = self.fns[j]
        es = [c for c in calls[j]]
        u = self.summaries.direct[j] & unknown
        if u != 0 and (fn.resumes or fn.f.gen):
            # (its own U may be only its yields and resumes: look at each op)
            u = 0
            for b in fn.blocks:
                for i in b.code:
                    if i.op == "gen.resume" or i.op == "gen.drop":
                        if len(i.a) == 1 and i.a[0].t in bodies:
                            es.extend(bodies[i.a[0].t])
                        else:
                            u = unknown
                    elif i.op == "rt" and i.s == "gen.unraisable":
                        # (reporting what closing raised renders the exception: user code only
                        # for an exception class of the program's, as ircheck's E descriptors;
                        # an exception renders its arguments as it is made)
                        if len(self.xcls) > 0:
                            u = unknown
                    elif i.op != "gen.yield":
                        c = i.s if i.op == "call" else "@init." + i.s if i.op == "init" else ""
                        if c not in self.fll:
                            u = u | (self.opfx(i, fn.fa) & unknown)
        edges.append(es)
        local.append(u)
    comp = [-1] * nf
    cyclic = recursion_cycles(edges, comp)
    reach = EffectSummaries()
    reach.update(local, edges)
    again = [cyclic[j] or reach.fx[j] & unknown != 0 for j in range(nf)]
    repeat: dict[str, bool] = {}
    for t in bodies:
        repeat[t] = any(again[j] for j in bodies[t])
        if not repeat[t]:
            self.genplain[t] = True  # (closing one need not count either: lowering's gen.drop)
    # Closed recursion: the source functions of a cycle that reaches no U, no function outside it
    # that can be entered again (a counted function, a body of a generator type that can recur)
    # and no sys.setrecursionlimit find the depth word as the cycle's outermost call found it,
    # until that call returns: nothing else they run changes it or counts from it. Lowering
    # passes their depth as an argument instead (rdpass): each checks the limit and counts in a
    # register, and its own symbol loads the word for the body. Each frame counts at the same call.
    marks = [unknown if again[j] or self.fns[j].setslimit else 0 for j in range(nf)]
    outer = EffectSummaries()
    outer.update(marks, edges)
    cycles: dict[int, list[int]] = {}
    for j in range(nf):
        if cyclic[j]:
            if comp[j] not in cycles:
                cycles[comp[j]] = []
            cycles[comp[j]].append(j)
    for cy in cycles:
        closed = True
        for j in cycles[cy]:
            fn = self.fns[j]
            if not fn.counted or fn.f.gen or fn.setslimit or reach.fx[j] & unknown != 0 or is_tuple(fn.f.ret):
                closed = False  # (a fixed tuple's function may return its slots instead: tupleret)
            for w in edges[j]:
                if comp[w] != cy and outer.fx[w] != 0:
                    closed = False
        for j in cycles[cy] if closed else []:
            self.rdpass[self.fns[j].f.ll] = True
    rescan = False
    for j in range(nf):
        fn = self.fns[j]
        if not fn.resumes:
            continue
        for b in fn.blocks:
            at = 0
            while at < len(b.code):
                i = b.code[at]
                if i.op == "gen.resume" and len(i.a) == 1 and i.a[0].t in bodies and not repeat[i.a[0].t]:
                    site = recursion_resume_site(b.code, at)
                    if len(site) == 3:
                        b.code = [b.code[k] for k in range(len(b.code)) if k not in site]
                        at -= 2
                        rescan = True
                at += 1
    direct = [m for m in self.summaries.direct]
    entered = FXBIT["R"] | FXBIT["I"]
    n = 0
    for j in range(nf):
        fn = self.fns[j]
        if not fn.counted:
            continue
        if not again[j]:
            fn.counted = False
            if not fn.landed:
                recursion_unsnapshot(fn)
            continue
        # Before any local handler or body code: a failed entry belongs to the caller.
        # The checked entry guarantees depth >= 1, so the caller's depth (the entry's
        # result minus one) cannot overflow. Restoring it after a recursive call also keeps
        # tail-call elimination from discarding the activation.
        at = recursion_snapshot(fn)
        fn.blocks[0].code[at].s = "recursion.enter"
        if fn.f.ll in self.rdpass:
            # (closed recursion: lowering checks the depth its caller passed and leaves the word alone)
            direct[j] = direct[j] | entered
            n += 1
            continue
        base = Ins("scalar.bin", "int", "sub")
        base.a = [Val(fn.rdepth, "int"), Val("1", "int")]
        fn.n += 1
        base.r = one_num(fn.n)
        fn.blocks[0].code.insert(at + 1, base)
        for b in fn.blocks:
            code: list[Ins] = []
            for i in b.code:
                if i.op == "ret" or i.op == "ret.none":
                    restore = Ins("rt", "None", "recursion.restore")
                    restore.a = [Val(tmpname(base.r[0]), "int")]
                    code.append(restore)
                code.append(i)
            b.code = code
        direct[j] = direct[j] | entered
        n += 1
    if n > 0:
        self.runtime("pys_recursion_enter")
        self.runtime("pys_recursion_restore")
    if rescan:
        self.effects()
    elif n > 0:
        self.summaries.update(direct, calls)
        for j in range(nf):
            self.fns[j].fx = self.summaries.fx[j]
    return n


def gen_optimize(self, fn: IFn, on: dict[str, bool]) -> int:
    # Run the registered passes in contract order; how many ops they rewrote.
    chk = os.getenv("PYSTACHY_IRCHECK", "") == "1"
    checked = False
    n = 0
    for contract in PASS_CONTRACTS:
        if contract.name not in on:
            continue
        # These passes share their entry requirements. Check them once, and only
        # check again after a rewrite, while the previous checks still hold.
        if chk and not checked:
            gen_pass_check(self, fn, contract, False)
            checked = True
        changed = 0
        if contract.name == "charslots":
            changed = self.charslots(fn)
        elif contract.name == "listget":
            changed = self.listget(fn)
        elif contract.name == "listguard":
            changed = self.listguard(fn)
        elif contract.name == "dictfuse":
            changed = self.dictfuse(fn)
        elif contract.name == "unionslots":
            changed = self.unionslots(fn)
        elif contract.name == "nullcheck":
            changed = self.nullcheck(fn)
        else:
            fail(f"internal error: no implementation of IR pass {contract.name}", 0)
        n += changed
        if chk and changed > 0:
            gen_pass_check(self, fn, contract, True)
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

def ascii_char_test(code: list[Ins], x: int, counts: dict[str, int], literals: list[str]) -> int:
    # The typed lowering of local == ASCII literal, returning the literal or -1.
    # Every temporary that goes away must have exactly its one use here.
    if x + 4 >= len(code):
        return -1
    load, pack, literal, eq, truth = code[x], code[x + 1], code[x + 2], code[x + 3], code[x + 4]
    if pack.op != "slot.pack" or literal.op != "slot.pack" or eq.op != "rt" or eq.s != "eq" or eq.x != "s":
        return -1
    if pack.a[0].v != tmpname(load.r[0]) or eq.a[0].v != tmpname(pack.r[0]) or eq.a[1].v != tmpname(literal.r[0]):
        return -1
    if literal.a[0].t != "str" or not literal.a[0].v.startswith("@s."):
        return -1
    # sconst assigns these symbols in literal-table order. Non-ASCII raw bytes
    # can have the same ordinal as a different UTF-8 encoding of the character.
    raw = literals[int(literal.a[0].v[3:])]
    if len(raw) != 1 or ord(raw) >= 128:
        return -1
    if truth.op != "num.cmp" or truth.s != "!=" or truth.a[0].t != "int" or truth.a[0].v != tmpname(eq.r[0]) or truth.a[1].v != "0":
        return -1
    for intermediate in [load, pack, literal, eq]:
        if counts[tmpname(intermediate.r[0])] != 1:
            return -1
    return ord(raw)

def gen_charslots(self, fn: IFn) -> int:
    # Try one private slot whose sole store immediately follows text.get. Bound
    # the work per function and skip suspendable frames and exception regions.
    if self.rtmode or fn.coro or fn.f.cmpops or fn.tries or fn.n > 512 or len(fn.blocks) > 128:
        return 0
    slots = {f"%{s.s or 'h'}.{s.r[0]}": s for s in fn.slots if s.k == 0 and s.t == "str"}
    if not slots:
        return 0
    size = 0
    for block in fn.blocks:
        size += len(block.code)
        if size > 1024:
            return 0
    addr = ""
    storeblock = 0
    storepos = 0
    for j in range(len(fn.blocks)):
        code = fn.blocks[j].code
        for x in range(1, len(code)):
            i = code[x]
            if i.op == "mem.store" and i.a[0].v in slots:
                index = code[x - 1]
                if index.op == "rt" and index.s == "text.get" and i.a[1].v == tmpname(index.r[0]):
                    storeblock, storepos, addr = j, x, i.a[0].v
                    break
        if addr != "":
            break
    if addr == "":
        return 0

    # All uses, including address-taking, boxing, phi operands and reads that
    # escape. Accept only the exact equality lowering, with private temporaries.
    counts: dict[str, int] = {}
    reads: list[list[int]] = []
    operands = 0
    for j in range(len(fn.blocks)):
        for x in range(len(fn.blocks[j].code)):
            i = fn.blocks[j].code[x]
            operands += len(i.a)
            if operands > 4096:
                return 0
            for k in range(len(i.a)):
                v = i.a[k].v
                counts[v] = counts.get(v, 0) + 1
                if v == addr:
                    if k == 0 and i.op == "mem.load" and i.t == "str":
                        reads.append([j, x])
                    elif k != 0 or j != storeblock or x != storepos:
                        return 0
    index = fn.blocks[storeblock].code[storepos - 1]
    point = tmpname(index.r[0])
    if counts[point] != 1 or not reads:
        return 0

    for read in reads:
        ch = ascii_char_test(fn.blocks[read[0]].code, read[1], counts, self.strvals)
        if ch < 0:
            return 0
        read.append(ch)

    # A path reaching any read without passing the store would observe an
    # uninitialized local. Stop the backwards search at the defining block.
    preds = self.preds(fn)
    seen: dict[int, bool] = {}
    pending: list[int] = []
    for read in reads:
        if read[0] == storeblock and read[1] <= storepos:
            return 0
        pending.append(read[0])
    while pending:
        j = pending.pop()
        if j != storeblock and j not in seen:
            if j == 0:
                return 0
            seen[j] = True
            for pred in preds[fn.blocks[j].label]:
                pending.append(pred)

    # The original potentially raising read executes once, in place. Keep its
    # SSA name and the final predicate's name; all other replaced values are private.
    index.t = "int"
    index.s = self.runtime("pys_text_ord_at")
    for read in reversed(reads):
        code = fn.blocks[read[0]].code
        x = read[1]
        truth = code[x + 4]
        truth.s = "=="
        truth.a = [Val(point, "int"), Val(str(read[2]), "int")]
        for _ in range(4):
            code.pop(x)
    del fn.blocks[storeblock].code[storepos]
    fn.slots = [s for s in fn.slots if s is not slots[addr]]
    return 1

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
    bad = FXBIT["wL"] | FXBIT["U"]
    ranges = False
    some = False
    for lp in fn.loops:
        ranges = ranges or (lp.kind == "range" and lp.nonnegative)
        for s in lp.seqs:
            some = some or is_list(s.t)
    ranges = ranges and not fn.coro and fn.fx & bad == 0
    if not some and not ranges:
        return 0
    at: dict[str, int] = {}
    for j in range(len(fn.blocks)):
        at[fn.blocks[j].label] = j
    pl = self.preds(fn)
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
    if not ranges:
        return n
    # range(k, len(xs), step) tests a captured length. Its positive constant step
    # and nonnegative start keep the induction value nonnegative (overflow exits
    # the loop), and no list write or unknown call anywhere in this function can
    # invalidate the length, including before the loop or across its back edge.
    # A suspended generator can let its caller mutate the list, so is excluded.
    # Entry-only local bindings let the same list be recognized across that edge;
    # every other value uses canon's existing, bounded forward-path proof.
    vs = Values(fn, pl)
    slots: dict[str, int] = {}
    for slot in fn.slots:
        if slot.k == 0 and is_list(slot.t):
            slots[f"%{slot.s or 'h'}.{slot.r[0]}"] = 0
    for b in range(len(fn.blocks)):
        code = fn.blocks[b].code
        for x in range(len(code)):
            i = code[x]
            for k in range(len(i.a)):
                a = i.a[k].v
                if a in slots and slots[a] >= 0 and (k != 0 or i.op != "mem.load"):
                    slots[a] = x + 1 if k == 0 and i.op == "mem.store" and b == 0 else -1
    for b in range(len(fn.blocks)):
        code = fn.blocks[b].code
        for x in range(len(code)):
            i = code[x]
            if i.op == "mem.load" and i.a[0].v in slots:
                a = i.a[0].v
                if slots[a] >= 0 and (b > 0 or x >= slots[a]):
                    vs.cn[tmpname(i.r[0])] = "slot " + a
    for lp in fn.loops:
        if lp.kind != "range" or not lp.nonnegative or len(lp.idx) != 1 or len(pl[lp.body]) != 1:
            continue
        stop = self.canon(vs, lp.stop.v)
        w = vs.at[int(stop[2:])] if stop.startswith("%t") and stop[2:].isdigit() else -1
        if w < 0:
            continue
        length = fn.blocks[w // vs.stride].code[w % vs.stride]
        if length.op != "list.len":
            continue
        # The semantic length records its list owner without reconstructing
        # layout from a generic machine load.
        seq = self.canon(vs, length.a[0].v)
        idx = self.canon(vs, lp.idx[0])
        l = lp.body
        steps = 0
        while l != "" and steps < len(fn.blocks):
            steps += 1
            b = at[l]
            code = fn.blocks[b].code
            l = ""
            for j in range(len(code)):
                i = code[j]
                if i.op == "rt" and i.s == "list.get" and self.canon(vs, i.a[0].v) == seq and self.canon(vs, i.a[1].v) == idx:
                    i.op = "list.load"
                    i.s = ""
                    i.r = [i.r[0], fn.n + 1, fn.n + 2, fn.n + 3]
                    fn.n += 3
                    n += 1
                    break
                if self.opfx(i, fn.fa) & bad != 0:
                    break
                if j == len(code) - 1 and (i.op == "br" or i.op == "cbr" or i.op == "check") and len(pl[i.b[0]]) == 1 and at[i.b[0]] > b:
                    l = i.b[0]
    return n

# the most ops that listguard copies for one loop, and the largest constant it adds to an index
GUARD_OPS = 400
GUARD_OFFSET = 1 << 20
NO_OFFSET = -(1 << 62)  # (guard_offset: no offset)


def guard_literal(v: str) -> bool:
    # is v a small int literal
    d = v[1:] if v.startswith("-") else v
    return 0 < len(d) <= 7 and d.isdigit()


def guard_index(self, vs: Values, v: str, idx: str, index: dict[str, bool]) -> bool:
    # is value v a range loop's index: idx, its canonical value, or a load in the loop of the
    # loop variable's slot, which only the loop's first op stores (index: those loads)
    return v in index or self.canon(vs, v) == idx


def guard_offset(self, vs: Values, v: str, idx: str, sums: dict[str, Ins], index: dict[str, bool]) -> int:
    # c where value v is a range loop's index (guard_index) plus the constant c: the index, or a
    # checked or nsw sum or difference of it and an int literal (sums: each such op of the function,
    # by the value it computes); NO_OFFSET where it is none of these
    if guard_index(self, vs, v, idx, index):
        return 0
    c = self.canon(vs, v)
    if c not in sums:
        return NO_OFFSET
    i = sums[c]
    add = i.s == "+" or i.s == "add"
    x = i.a[0].v
    y = i.a[1].v
    if guard_literal(y) and guard_index(self, vs, x, idx, index) and -GUARD_OFFSET <= int(y) <= GUARD_OFFSET:
        return int(y) if add else -int(y)
    if add and guard_literal(x) and guard_index(self, vs, y, idx, index) and -GUARD_OFFSET <= int(x) <= GUARD_OFFSET:
        return int(x)
    return NO_OFFSET


def guard_base(a: Val, defined: dict[str, bool], loads: dict[str, Ins]) -> str:
    # the key of operand a where it is an int that a range loop's copy may add to its index as a base
    # (guard_base_offset), which no iteration changes: a register that the loop does not define (the
    # register), or the loop's load of a local slot that it never stores ("slot S"); "" otherwise
    v = a.v
    if a.t != "int":
        return ""
    if v in loads:
        return "slot " + loads[v].a[0].v
    if (v.startswith("%t") or v.startswith("%a")) and v not in defined:
        return v
    return ""


def guard_base_sum(self, vs: Values, i: Ins, idx: str, sums: dict[str, Ins], index: dict[str, bool], defined: dict[str, bool], loads: dict[str, Ins], found: list[Ins]) -> tuple[str, int]:
    # (b, c) where the checked or nsw sum i adds a base b (guard_base: its key) to a range loop's
    # index plus the constant c (guard_offset), in either order, and i is put in found;
    # ("", NO_OFFSET) where it does not
    if i.s != "+" and i.s != "add":
        return ("", NO_OFFSET)
    for k in range(2):
        b = guard_base(i.a[k], defined, loads)
        c = guard_offset(self, vs, i.a[1 - k].v, idx, sums, index)
        if b != "" and c != NO_OFFSET:
            found.append(i)
            return (b, c)
    return ("", NO_OFFSET)


def guard_base_offset(self, vs: Values, v: str, idx: str, sums: dict[str, Ins], index: dict[str, bool], defined: dict[str, bool], loads: dict[str, Ins], found: list[Ins]) -> tuple[str, int]:
    # (b, c) where value v is a range loop's index plus a base b plus the constant c: a sum that
    # guard_base_sum takes (and puts in found), or one plus or minus an int literal. ("", c) where
    # v is the index plus c alone (guard_offset), and ("", NO_OFFSET) where it is none of these
    c = guard_offset(self, vs, v, idx, sums, index)
    if c != NO_OFFSET:
        return ("", c)
    w = self.canon(vs, v)
    if w not in sums:
        return ("", NO_OFFSET)
    i = sums[w]
    b, c = guard_base_sum(self, vs, i, idx, sums, index, defined, loads, found)
    if b != "":
        return (b, c)
    add = i.s == "+" or i.s == "add"
    x = i.a[0].v
    y = i.a[1].v
    inner = ""
    k = 0
    if guard_literal(y) and -GUARD_OFFSET <= int(y) <= GUARD_OFFSET:
        inner = self.canon(vs, x)
        k = int(y) if add else -int(y)
    elif add and guard_literal(x) and -GUARD_OFFSET <= int(x) <= GUARD_OFFSET:
        inner = self.canon(vs, y)
        k = int(x)
    if inner in sums:
        b, c = guard_base_sum(self, vs, sums[inner], idx, sums, index, defined, loads, found)
        if b != "" and -GUARD_OFFSET <= c + k <= GUARD_OFFSET:
            return (b, c + k)
    return ("", NO_OFFSET)


def call_counts(fns: list[IFn]) -> dict[str, int]:
    # how many times fns' IR names each function (by symbol), as a call's callee or as a value,
    # an operand that a Callable or a store takes (Gen.callsites)
    n: dict[str, int] = {}
    for fn in fns:
        for b in fn.blocks:
            for i in b.code:
                if i.op == "call":
                    n[i.s] = n.get(i.s, 0) + 1
                for v in i.a:
                    if v.v.startswith("@"):
                        n[v.v] = n.get(v.v, 0) + 1
    return n


class GuardPlan:
    # what listguard does to one loop: its blocks (by label), the block before it, the lists the
    # test before it reads (the value, or "slot S" for a slot it loads in the loop and never stores)
    # with the largest constant added to an index of each, the ops the copy leaves unchecked, and
    # the calls whose copies it marks to be inlined
    def __init__(self, lp: Loop, pre: Blk):
        self.lp = lp
        self.pre = pre
        self.region: dict[str, bool] = {}
        self.lists: list[str] = []
        self.most: dict[str, int] = {}
        self.slot_load: dict[str, Ins] = {}  # (a load of each such slot, whose operand the test reuses)
        self.list_type: dict[str, str] = {}
        self.reads: list[Ins] = []
        self.stores: list[Ins] = []
        self.folds: list[Ins] = []
        self.inline: list[Ins] = []
        self.start = 0  # (the range's first value)
        # the bases that indexes add (guard_base's keys: "slot S" or a register), the smallest constant
        # added with each, a load of each slot base, and each list with each base it is indexed by
        # ("<list key>\t<base key>") with the largest constant added with that pair
        self.bases: list[str] = []
        self.least: dict[str, int] = {}
        self.base_load: dict[str, Ins] = {}
        self.pairs: list[str] = []
        self.pmost: dict[str, int] = {}
        self.basesums: list[Ins] = []  # (the checked sums b + i of accepted indexes: the copy's add none)


def guard_plan(self, fn: IFn, lp: Loop, vs: Values, pl: dict[str, list[int]], at: dict[str, int], sums: dict[str, Ins]) -> GuardPlan | None:
    # the plan for range loop lp (gen_listguard), or None where it gets no copy
    if lp.kind != "range" or not lp.nonnegative or len(lp.idx) != 1 or lp.head not in at or lp.body not in at:
        return None
    region: dict[str, bool] = {lp.head: True}
    pending = [lp.body]
    ops = len(fn.blocks[at[lp.head]].code)
    while len(pending) > 0:
        l = pending.pop()
        if l in region or l == lp.exit:
            continue
        if l not in at:
            return None
        region[l] = True
        b = fn.blocks[at[l]]
        ops += len(b.code)
        if ops > GUARD_OPS or b.handler != "":
            return None
        for s in b.code[len(b.code) - 1].b:
            pending.append(s)
    if fn.blocks[at[lp.head]].handler != "" or len([i for i in fn.blocks[at[lp.head]].code if i.op == "phi"]) > 0:
        return None
    for other in fn.loops:
        if other is not lp and other.head in region:
            return None  # (a loop in this one: only innermost loops get copies)
    outside = [j for j in pl[lp.head] if fn.blocks[j].label not in region]
    if len(outside) != 1:
        return None
    pre = fn.blocks[outside[0]]
    if pre.code[len(pre.code) - 1].op != "br":
        return None
    start = ""
    for i in pre.code:
        if (i.op == "mem.store" or i.op == "mach.store") and i.a[0].v == lp.ctr:
            start = i.a[1].v  # (the counter's first value, a nonnegative constant: Loop.nonnegative)
    if not guard_literal(start):
        return None
    plan = GuardPlan(lp, pre)
    plan.region = region
    plan.start = int(start)
    # a call of a function that the program names nowhere else (Gen.callsites), which LLVM inlines
    # as an internal function's last call: once the copy calls it too, LLVM would inline neither
    # call, and the copy would run slower than the loop did (#1300). The copy's call is inlined
    # (lowering: alwaysinline), the loop's then being the last, and the callee's ops count toward
    # the copy's. Not a coroutine's, nor an exported function's, which C or CPython may call too
    for l in region:
        for i in fn.blocks[at[l]].code:
            if i.op == "call" and i.s != fn.f.ll and i.s in self.fll and self.callsites.get(i.s, 0) == 1:
                callee = self.fns[self.fll[i.s]]
                if callee.coro or callee.f.export or callee.f.pyexport:
                    continue
                for cb in callee.blocks:
                    ops += len(cb.code)
                if ops > GUARD_OPS:
                    return None
                plan.inline.append(i)
    idx = self.canon(vs, lp.idx[0])
    bad = FXBIT["wL"] | FXBIT["U"]
    defined: dict[str, bool] = {}
    stored: dict[str, bool] = {}
    for l in region:
        for i in fn.blocks[at[l]].code:
            for r in i.r:
                defined[tmpname(r)] = True
            if i.op == "mem.store" or i.op == "mach.store":
                stored[i.a[0].v] = True
    # the loop variable's slot, where the loop's first op stores the index and no other op of it
    # stores: every load of it in the loop reads that iteration's index
    first = fn.blocks[at[lp.body]].code[0]
    var = ""
    if first.op == "mem.store" and first.a[1].v == lp.idx[0] and first.a[0].v.startswith("%") and "." in first.a[0].v:
        var = first.a[0].v
        for l in region:
            for i in fn.blocks[at[l]].code:
                if (i.op == "mem.store" or i.op == "mach.store") and i.a[0].v == var and i is not first:
                    var = ""
    index: dict[str, bool] = {}
    loads: dict[str, Ins] = {}  # (a value the loop loads from a local slot that it never stores)
    for l in region:
        for i in fn.blocks[at[l]].code:
            a = i.a[0].v if len(i.a) > 0 else ""
            if i.op == "mem.load" and a.startswith("%") and "." in a and a not in stored and a not in fn.fa:
                loads[tmpname(i.r[0])] = i
            if i.op == "mem.load" and var != "" and a == var:
                index[tmpname(i.r[0])] = True
    keys: dict[str, bool] = {}  # (each guarded access's list and offset, for listfast's checks)
    for l in region:
        for i in fn.blocks[at[l]].code:
            if i.op == "rt" and (i.s == "list.get" or i.s == "list.set"):
                o = i.a[0]
                if not is_list(o.t) or i.x != "" or len(i.r) > 1:
                    continue  # (an access the copy keeps checked; it changes no list's length)
                if i.s == "list.set" and (int_lists() or dynamic_program()):
                    continue  # (an item assignment stays checked where a list may hold numeric identities)
                found: list[Ins] = []
                base, c = guard_base_offset(self, vs, i.a[1].v, idx, sums, index, defined, loads, found)
                key = o.v if o.v not in defined else "slot " + loads[o.v].a[0].v if o.v in loads else ""
                if c == NO_OFFSET or key == "" or (base == "" and int(start) + c < 0):
                    continue
                for summed in found:
                    if summed.op == "ovf" and len([x for x in plan.basesums if x is summed]) == 0:
                        plan.basesums.append(summed)
                if key not in plan.list_type:
                    plan.lists.append(key)
                    plan.list_type[key] = o.t
                    if key.startswith("slot "):
                        plan.slot_load[key] = loads[o.v]
                if base == "" and key not in plan.most:
                    plan.most[key] = c
                elif base == "" and c > plan.most[key]:
                    plan.most[key] = c
                elif base != "":
                    # (a base's test before the loop checks start + c >= 0 for its smallest c)
                    if base not in plan.least:
                        plan.bases.append(base)
                        plan.least[base] = c
                        for v in loads:
                            if base == "slot " + loads[v].a[0].v:
                                plan.base_load[base] = loads[v]
                    elif c < plan.least[base]:
                        plan.least[base] = c
                    pair = key + "\t" + base
                    if pair not in plan.pmost:
                        plan.pairs.append(pair)
                        plan.pmost[pair] = c
                    elif c > plan.pmost[pair]:
                        plan.pmost[pair] = c
                keys[f"{key} {base} {c}"] = True
                if i.s == "list.get":
                    plan.reads.append(i)
                else:
                    plan.stores.append(i)
            elif self.opfx(i, fn.fa) & bad != 0:
                return None  # (an op that may change a list's length, or run user code)
    if len(plan.lists) == 0:
        return None
    # listfast's check of an index before its inline read: the copy goes to the read
    for l in region:
        code = fn.blocks[at[l]].code
        last = code[len(code) - 1]
        if last.op != "cbr":
            continue
        w = vs.at[int(last.a[0].v[2:])] if last.a[0].v.startswith("%t") and last.a[0].v[2:].isdigit() else -1
        if w < 0:
            continue
        test = vs.fn.blocks[w // vs.stride].code[w % vs.stride]
        if test.op != "int.ucmp" or test.s != "<":
            continue
        u = vs.at[int(test.a[1].v[2:])] if test.a[1].v.startswith("%t") and test.a[1].v[2:].isdigit() else -1
        if u < 0:
            continue
        length = vs.fn.blocks[u // vs.stride].code[u % vs.stride]
        if length.op != "list.len":
            continue
        owner = length.a[0].v
        key = owner if owner not in defined else "slot " + loads[owner].a[0].v if owner in loads else ""
        base, c = guard_base_offset(self, vs, test.a[0].v, idx, sums, index, defined, loads, [])
        if key != "" and c != NO_OFFSET and f"{key} {base} {c}" in keys:
            plan.folds.append(last)
    return plan


def gen_listguard(self, fn: IFn) -> int:
    # Unchecked list accesses in range loops, behind tests before each loop. An innermost loop over
    # range(start, stop) or range(start, stop, step), with constants start >= 0 and step > 0, whose
    # ops change no list's length (no op with wL but its item assignments, which change none, and no
    # user code, U), gets a copy. Each read or assignment of an item of a list the loop does not
    # rebind (a value it does not define, or a local slot it does not store), at the loop's index i
    # plus a constant c (xs[i], ys[i + 1], zs[i - 1] = v) with start + c >= 0, is unchecked in the
    # copy: a list.load, or a list.store, which stores the item as list.set does where no list holds
    # numeric identities (a program none of whose modules opts in to promoting ints or dynamic Any;
    # elsewhere assignments keep their checks); and listfast's inline read is. The tests run the
    # copy where each such list, as the loop starts, has stop <= len(xs) - c for its largest c: then
    # 0 <= i + c < len(xs) for every i the loop takes, as no length changes while it runs. Otherwise
    # the loop runs as compiled, raising IndexError where CPython raises it, after the same
    # iterations. An index may also add a base b that no iteration changes (guard_base: data[bi + d]);
    # then the tests check start + c + b >= 0 for b's smallest c, compute stop + b, checked, and need
    # stop + b <= len(xs) - c for each list's largest c with b; the copy reads b once, from the
    # tests, and adds it without an overflow check (guard_loop). The copy keeps every other check.
    # A coroutine is left as it is (a caller may
    # change a list while it is suspended), as is a loop that a try statement covers or that holds
    # another loop or more than GUARD_OPS ops. How many accesses the copies leave unchecked
    if fn.coro or len(fn.loops) == 0:
        return 0
    some = False
    for lp in fn.loops:
        some = some or (lp.kind == "range" and lp.nonnegative)
    if not some:
        return 0
    at: dict[str, int] = {}
    for j in range(len(fn.blocks)):
        at[fn.blocks[j].label] = j
    pl = self.preds(fn)
    vs = Values(fn, pl)
    sums: dict[str, Ins] = {}  # (the int sums and differences, by their values: guard_offset)
    for b in fn.blocks:
        for i in b.code:
            if i.op == "ovf" and len(i.r) == 3 and (i.s == "+" or i.s == "-"):
                sums[tmpname(i.r[1])] = i
            elif i.op == "scalar.bin" and i.t == "int" and (i.s == "add" or i.s == "sub") and len(i.r) == 1:
                sums[tmpname(i.r[0])] = i
    plans: list[GuardPlan] = []
    for lp in fn.loops:
        plan = guard_plan(self, fn, lp, vs, pl, at, sums)
        if plan is not None:
            plans.append(plan)
    n = 0
    for p in plans:
        n += guard_loop(self, fn, p)
    return n


def clone_instruction(i: Ins, numbers: dict[int, int], labels: dict[str, str]) -> Ins:
    # A fresh instruction with the caller's SSA and block renaming. Keep this
    # boundary explicit so hosted inspection can follow exact clone provenance.
    d = Ins(i.op, i.t, i.s)
    d.line = i.line
    d.k = i.k
    d.x = i.x
    d.r = [numbers[r] for r in i.r]
    d.b = [labels[l] if l in labels else l for l in i.b]
    d.a = []
    for v in i.a:
        w = Val(tmpname(numbers[int(v.v[2:])]) if v.v.startswith("%t") and v.v[2:].isdigit() and int(v.v[2:]) in numbers else v.v, v.t).identity(v)
        w.lit = v.lit
        w.infer_from = v.infer_from
        d.a.append(w)
    return d


def guard_loop(self, fn: IFn, plan: GuardPlan) -> int:
    # the copy of plan's loop and the test before it (gen_listguard); how many accesses it unchecks
    lp = plan.lp
    region = plan.region
    labels: dict[str, str] = {}
    numbers: dict[int, int] = {}
    for b in fn.blocks:
        if b.label in region:
            fn.n += 1
            labels[b.label] = f"L{fn.n}"
            for i in b.code:
                for r in i.r:
                    fn.n += 1
                    numbers[r] = fn.n
                    if tmpname(r) in fn.fa:
                        fn.fa[tmpname(fn.n)] = True
    fn.n += 1
    test = Blk(f"L{fn.n}")
    # each base's register: a slot base's is the test's load of the slot, which the copy reads in
    # place of the loop's loads of it (the loop never stores the slot), so that the tests and the
    # copy's indexes name one value
    based: dict[str, str] = {}
    dropped: dict[int, bool] = {}  # (by result: the loop's loads of a slot base, which the copy leaves out)
    for base in plan.bases:
        if not base.startswith("slot "):
            based[base] = base
            continue
        fn.n += 1
        based[base] = tmpname(fn.n)
        for b in fn.blocks:
            if b.label in region:
                for i in b.code:
                    if i.op == "mem.load" and "slot " + i.a[0].v == base:
                        numbers[i.r[0]] = fn.n
                        dropped[i.r[0]] = True
    reads: dict[int, bool] = {}
    for i in plan.reads:
        reads[i.r[0]] = True
    stores: list[Ins] = plan.stores
    folds: list[Ins] = plan.folds
    slow: dict[str, bool] = {}  # (listfast's fallback reads, which the copy never reaches: kept as they are)
    for i in folds:
        slow[i.b[1]] = True
    copies: list[Blk] = []
    fitted: dict[str, bool] = {}  # (the copy's overflow flags of b + i sums, which it no longer computes)
    last = 0
    n = 0
    for j in range(len(fn.blocks)):
        b = fn.blocks[j]
        if b.label not in region:
            continue
        last = j
        c = Blk(labels[b.label])
        for i in b.code:
            if len(i.r) == 1 and i.r[0] in dropped:
                continue
            d = clone_instruction(i, numbers, labels)
            if i.op == "rt" and i.s == "list.get" and len(i.r) == 1 and i.r[0] in reads and b.label not in slow:
                d.op = "list.load"  # (as listget makes it: the slot pys_list_get would have returned)
                d.s = ""
                d.r = [d.r[0], fn.n + 1, fn.n + 2, fn.n + 3]
                fn.n += 3
                n += 1
            elif i.op == "rt" and i.s == "list.set" and len([x for x in stores if x is i]) > 0:
                d.op = "list.store"  # (as pys_list_set stores an item where the list has no identity companion)
                d.t = ""
                d.s = ""
                d.r = [fn.n + 1, fn.n + 2, fn.n + 3]
                fn.n += 3
                n += 1
            elif i.op == "cbr" and len([x for x in folds if x is i]) > 0:
                d.a = [Val("true", "bool")]  # (listfast's check, which the test before the loop makes)
                n += 1
            elif i.op == "ovf" and len([x for x in plan.basesums if x is i]) > 0:
                # b + i, an index's base and the loop's index: start + b >= -c and stop + b fit, which
                # the tests before the loop check, so b + i does, for every i the loop takes
                fitted[tmpname(d.r[2])] = True
                d.op = "scalar.bin"
                d.s = "add"
                d.x = "nsw"
                d.r = [d.r[1]]
            elif i.op == "check" and len(d.a) == 1 and d.a[0].v in fitted:
                d.op = "br"  # (the overflow check of such a sum: it never fails)
                d.s = ""
                d.x = ""
                d.a = []
            elif i.op == "call" and len([x for x in plan.inline if x is i]) > 0:
                d.x = "inline"  # (its callee's only call but the loop's: guard_plan)
            c.code.append(d)
        copies.append(c)
    # the tests, each list's in turn: stop <= len(xs) - c, for its largest c. A list the loop loads
    # from a local slot is loaded here too, and where that is null (a local not yet assigned, whose
    # read in the loop raises), the loop runs as compiled
    tests: list[Blk] = [test]
    cur = test
    lists: dict[str, str] = {}
    for key in plan.lists:
        if not key.startswith("slot "):
            lists[key] = key
            continue
        src = plan.slot_load[key]
        load = Ins("mem.load", src.t, "")
        load.a = [src.a[0]]
        fn.n += 1
        load.r = [fn.n]
        cur.code.append(load)
        lists[key] = tmpname(fn.n)
        null = Ins("ptr.cmp", "bool", "==")
        null.a = [Val(lists[key], plan.list_type[key]), Val("null", plan.list_type[key])]
        fn.n += 1
        null.r = [fn.n]
        cur.code.append(null)
        fn.n += 1
        nxt = Blk(f"L{fn.n}")
        skip = Ins("cbr", "", "")
        skip.a = [Val(tmpname(null.r[0]), "bool")]
        skip.b = [lp.head, nxt.label]
        cur.code.append(skip)
        tests.append(nxt)
        cur = nxt
    # each base b's tests: start + c + b >= 0 for its smallest c, then s = stop + b, checked; where
    # either fails, the loop runs as compiled
    ends: dict[str, str] = {}  # (each base's s)
    for base in plan.bases:
        if base.startswith("slot "):
            src = plan.base_load[base]
            load = Ins("mem.load", src.t, "")
            load.a = [src.a[0]]
            load.r = [int(based[base][2:])]
            cur.code.append(load)
        low = Ins("scalar.cmp", "bool", "sle")
        low.a = [Val(str(-(plan.start + plan.least[base])), "int"), Val(based[base], "int")]
        fn.n += 1
        low.r = [fn.n]
        cur.code.append(low)
        fn.n += 1
        nxt = Blk(f"L{fn.n}")
        branch = Ins("cbr", "", "")
        branch.a = [Val(tmpname(low.r[0]), "bool")]
        branch.b = [nxt.label, lp.head]
        cur.code.append(branch)
        tests.append(nxt)
        cur = nxt
        self.runtime("llvm.sadd.with.overflow.i64")
        add = Ins("ovf", "int", "+")
        add.a = [Val(lp.stop.v, "int"), Val(based[base], "int")]
        add.r = [fn.n + 1, fn.n + 2, fn.n + 3]
        fn.n += 3
        cur.code.append(add)
        ends[base] = tmpname(add.r[1])
        fn.n += 1
        nxt = Blk(f"L{fn.n}")
        branch = Ins("cbr", "", "")
        branch.a = [Val(tmpname(add.r[2]), "bool")]
        branch.b = [lp.head, nxt.label]
        cur.code.append(branch)
        tests.append(nxt)
        cur = nxt
    plain = [key for key in plan.lists if key in plan.most]
    for k in range(len(plain)):
        key = plain[k]
        length = Ins("list.len", "int", "")
        length.a = [Val(lists[key], plan.list_type[key])]
        fn.n += 1
        length.r = [fn.n]
        cur.code.append(length)
        limit = tmpname(fn.n)
        if plan.most[key] != 0:
            less = Ins("scalar.bin", "int", "sub")
            less.a = [Val(limit, "int"), Val(str(plan.most[key]), "int")]
            fn.n += 1
            less.r = [fn.n]
            cur.code.append(less)
            limit = tmpname(fn.n)
        fits = Ins("scalar.cmp", "bool", "sle")
        fits.a = [Val(lp.stop.v, "int"), Val(limit, "int")]
        fn.n += 1
        fits.r = [fn.n]
        cur.code.append(fits)
        target = labels[lp.head]  # (each list's test in turn, then the copy)
        nxt = cur
        if k < len(plain) - 1 or len(plan.pairs) > 0:
            fn.n += 1
            nxt = Blk(f"L{fn.n}")
            tests.append(nxt)
            target = nxt.label
        branch = Ins("cbr", "", "")
        branch.a = [Val(tmpname(fits.r[0]), "bool")]
        branch.b = [target, lp.head]
        cur.code.append(branch)
        cur = nxt
    # each list and base b that an index adds: stop + b <= len(xs) - c for the pair's largest c,
    # which keeps b + i + c < len(xs) for every i the loop takes
    for k in range(len(plan.pairs)):
        pair = plan.pairs[k]
        key = pair[: pair.find("\t")]
        base = pair[pair.find("\t") + 1 :]
        length = Ins("list.len", "int", "")
        length.a = [Val(lists[key], plan.list_type[key])]
        fn.n += 1
        length.r = [fn.n]
        cur.code.append(length)
        limit = tmpname(fn.n)
        if plan.pmost[pair] != 0:
            less = Ins("scalar.bin", "int", "sub")
            less.a = [Val(limit, "int"), Val(str(plan.pmost[pair]), "int")]
            fn.n += 1
            less.r = [fn.n]
            cur.code.append(less)
            limit = tmpname(fn.n)
        fits = Ins("scalar.cmp", "bool", "sle")
        fits.a = [Val(ends[base], "int"), Val(limit, "int")]
        fn.n += 1
        fits.r = [fn.n]
        cur.code.append(fits)
        target = labels[lp.head]
        nxt = cur
        if k < len(plan.pairs) - 1:
            fn.n += 1
            nxt = Blk(f"L{fn.n}")
            tests.append(nxt)
            target = nxt.label
        branch = Ins("cbr", "", "")
        branch.a = [Val(tmpname(fits.r[0]), "bool")]
        branch.b = [target, lp.head]
        cur.code.append(branch)
        cur = nxt
    # the block before the loop goes to the test, and the loop's test (and its copy's) comes from it
    end = plan.pre.code[len(plan.pre.code) - 1]
    end.b = [test.label if l == lp.head else l for l in end.b]
    # a block after the loop that a block of it goes to takes the copy's value from the copy
    for b in fn.blocks:
        if b.label in region:
            continue
        for i in b.code:
            if i.op != "phi":
                continue
            for k in range(len(i.b)):
                if i.b[k] in region:
                    v = i.a[k]
                    w = Val(tmpname(numbers[int(v.v[2:])]) if v.v.startswith("%t") and v.v[2:].isdigit() and int(v.v[2:]) in numbers else v.v, v.t).identity(v)
                    i.a.append(w)
                    i.b.append(labels[i.b[k]])
    head = 0
    for j in range(len(fn.blocks)):
        if fn.blocks[j].label == lp.head:
            head = j
    fn.blocks = fn.blocks[:head] + tests + fn.blocks[head:last + 1] + copies + fn.blocks[last + 1:]
    copy = Loop(lp.kind, labels[lp.head], labels[lp.body], labels[lp.step] if lp.step in labels else lp.step, lp.exit)
    copy.mode = lp.mode
    copy.ctr = lp.ctr
    copy.nonnegative = lp.nonnegative
    copy.stop = Val(lp.stop.v, lp.stop.t)
    copy.idx = [tmpname(numbers[int(lp.idx[0][2:])])]
    fn.loops.append(copy)
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
            if i.op == "rt" and (i.s == "dict.has" or i.s == "dict.getitem" or i.s == "dict.set") and self.opfx(i, vs.fn.fa) & FXBIT["U"] == 0:
                # (but not a lookup that may run user code, U: CPython runs a key's __hash__ and
                # __eq__ at each lookup of keys hashed by their class or held as dynamic values,
                # and that code can change any dict. Such an op ends what the others found)
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
                    ev = Val(tmpname(looks[m].e), "int")
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
                        has[tmpname(i.r[0])] = len(looks)
                    looks.append(Lookup(i, j, x, d, k))
            elif i.op == "num.cmp" and i.a[0].t == "int" and i.a[1].v == "0" and (i.s == "==" or i.s == "!="):
                # A typed membership truth test carries the same has-result fact as
                # a membership result; not/branch handling below stays shared.
                r = i.a[0].v
                if r in has:
                    cond[tmpname(i.r[0])] = has[r]
                    pos[tmpname(i.r[0])] = i.s == "!="
            elif i.op == "scalar.bin" and i.s == "xor" and i.t == "bool" and i.a[1].v == "true":
                r = i.a[0].v
                if r in cond:
                    cond[tmpname(i.r[0])] = cond[r]
                    pos[tmpname(i.r[0])] = not pos[r]
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
            fi.line = i.line
            fi.a = [i.a[0], i.a[1]]
            fi.x = i.x
            fi.r = one_num(f.e)
            code[x] = fi
            ad = Ins("scalar.bin", "int", "add")
            ad.line = i.line
            ad.a = [Val(tmpname(f.e), "int"), Val("1", "int")]
            ad.r = one_num(i.r[0])
            code.insert(x + 1, ad)
        else:
            self.runtime("pys_dict_entry")
            en = Ins("rt", "int", "dict.entry")
            en.line = i.line
            en.a = [i.a[0], i.a[1]]
            en.x = i.x
            en.r = one_num(f.e)
            code.insert(x, en)
            self.runtime("pys_dict_val")
            i.s = "dict.val"
            i.a = [i.a[0], Val(tmpname(f.e), "int")]
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
    # allocates nothing. Private optional scalars also use two slots: presence and payload,
    # only for None, scalar boxes or their phis, with no use beyond null tests and payload reads.
    # Inferred None-first locals can retain NONEVAR on their slots: the same producer/use
    # checks prove scalar storage without depending on that provisional annotation.
    # Plain scalar dict.get producers with one private store also split: one lookup and
    # one safe value read replace the optional allocation. Other unknown producers and
    # escaping optionals stay boxed; no nullable pointer is dereferenced
    # to take it apart. A generator's locals stay (its frame keeps them). How many slots it split
    if fn.coro:
        return 0
    cands = [s for s in fn.slots if s.k == 0 and ((is_union(s.t) and len([m for m in umembers(s.t) if m != "int" and m != "float" and m != "bool"]) == 0) or s.t in ["opt[int]", "opt[float]", "opt[bool]", NONEVAR])]
    if len(cands) == 0:
        return 0  # (no scalar union or optional local: defs and uses would go unread)
    defs: dict[str, list[int]] = {}  # a value -> the block and position of the op that makes it
    uses: dict[str, list[list[int]]] = {}  # a value -> the block, position and operand of each use
    for j in range(len(fn.blocks)):
        code = fn.blocks[j].code
        for x in range(len(code)):
            i = code[x]
            for r in i.r:
                defs[tmpname(r)] = [j, x]
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
            if u[2] != 0 or (i.op != "mem.load" and i.op != "mem.store") or (i.op == "mem.store" and not self.usplits(fn, defs, uses, i.a[1].v, {}, is_opt(s.t))):
                ok = False
            elif i.op == "mem.load":
                if is_opt(s.t) and self.uleaves(fn, uses, i, {}):
                    ok = False  # (optional copies and identity-sensitive uses also stay boxed)
                for w in uses.get(tmpname(i.r[0]), []):
                    o = fn.blocks[w[0]].code[w[1]]
                    if (o.op == "union.payload" or o.op == "union.raw") and tmpname(o.r[0]) in uses:
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
            h.r = one_num(fn.n)
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
            v = tmpname(i.r[0])
            ops: list[Ins] = []
            for half in halves[addr]:
                fn.n += 1
                ld = Ins("mem.load", "int", "")
                ld.line = i.line
                ld.a = [Val(half, "*int")]
                ld.r = one_num(fn.n)
                ops.append(ld)
            parts[v] = [tmpname(ops[0].r[0]), tmpname(ops[1].r[0])]
            for w in uses.get(v, []):
                o = fn.blocks[w[0]].code[w[1]]
                if is_opt(split[addr].t) and o.op == "ptr.cmp":
                    test = Ins("num.cmp", "bool", o.s)
                    test.a = [Val(parts[v][0], "int"), Val("0", "int")]
                    test.r = o.r
                    repl[f"{w[0]}:{w[1]}"] = [test]
                elif o.op == "union.tag" or self.tag_read(o):
                    ren[tmpname(o.r[0])] = parts[v][1 if is_opt(split[addr].t) else 0]
                    repl[f"{w[0]}:{w[1]}"] = []
                elif o.op == "union.payload" or o.op == "union.raw":
                    p = Ins("slot.pack", "%slot", "")
                    p.line = o.line
                    p.a = [Val(parts[v][1], "int")]
                    p.r = one_num(o.r[1])
                    repl[f"{w[0]}:{w[1]}"] = [p]
            if self.uleaves(fn, uses, i, split):  # (a copy to a slot that splits stores the parts)
                # (the box that leaves, as the value it replaces)
                box = Ins("rt", "%ptr", "ubox")
                box.line = i.line
                box.a = [Val(parts[v][0], "int"), Val(parts[v][1], "*T")]
                box.r = one_num(i.r[0])
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
                st.line = i.line
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
                pure = (i.op == "rt" and (i.s == "ubox" or i.s == "box")) or i.op == "slot.pack" or (i.op == "slot.unpack" and is_opt(i.t)) or i.op == "union.tag" or i.op == "union.payload" or i.op == "union.raw" or (i.op == "phi" and (is_union(i.t) or is_opt(i.t) or i.t == "int"))
                if pure and len([r for r in i.r if tmpname(r) in used]) == 0:
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

def optional_dict_source(fn: IFn, defs: dict[str, list[int]], uses: dict[str, list[list[int]]], v: str) -> Ins | None:
    # A plain scalar get(k), with None as its default, whose box goes immediately
    # into one private local. The caller proves that the local has only presence
    # tests and numeric reads. Keep opt-in storage, copies, phis and identity uses
    # on the existing path. A single getbox and unpack use makes replacement local:
    # no other operation can observe the box or repeat the key's hash/equality.
    if dynamic_program() or int_program() or v not in defs or len(uses.get(v, [])) != 1:
        return None
    use = uses[v][0]
    store = fn.blocks[use[0]].code[use[1]]
    if store.op != "mem.store" or use[2] != 1:
        return None
    d = defs[v]
    unpack = fn.blocks[d[0]].code[d[1]]
    if unpack.op != "slot.unpack" or unpack.t not in ["opt[int]", "opt[float]", "opt[bool]"] or len(unpack.a) != 1:
        return None
    raw = unpack.a[0].v
    if raw not in defs or len(uses.get(raw, [])) != 1:
        return None
    d = defs[raw]
    call = fn.blocks[d[0]].code[d[1]]
    if call.op != "rt" or call.s != "dict.getbox" or len(call.a) != 3 or call.a[2].v != "0":
        return None
    return call


def gen_usplits(self, fn: IFn, defs: dict[str, list[int]], uses: dict[str, list[list[int]]], v: str, seen: dict[str, bool], optional: bool = False) -> bool:
    # can unionslots take apart union value v: an op's (a phi's where its incoming values'
    # are) or a parameter's. An optional admits only known scalar boxes, None and their phis.
    if optional and v == "null":
        return True
    if v in seen or (not optional and v.startswith("%a") and v[2:].isdigit()):
        return True
    if v not in defs:
        return False
    seen[v] = True
    i = fn.blocks[defs[v][0]].code[defs[v][1]]
    if i.op == "phi":
        for a in i.a:
            if not self.usplits(fn, defs, uses, a.v, seen, optional):
                return False
    elif optional:
        return (i.op == "rt" and i.s == "box") or optional_dict_source(fn, defs, uses, v) is not None
    return True

def gen_uparts(self, fn: IFn, defs: dict[str, list[int]], v: str, t: str, parts: dict[str, list[str]], before: dict[str, list[Ins]], after: dict[str, list[Ins]], heads: dict[int, list[Ins]]) -> list[str]:
    # the tag and the payload's bits of value v of union t (unionslots): a ubox's operands; a
    # phi's as two phis, put after the phis of its block, of its incoming values' parts; else
    # what union.tag and union.raw read of the box, put where v is made (a parameter: as the
    # function begins), so that they are there wherever v is
    if v in parts:
        return parts[v]
    if is_opt(t) and v == "null":
        return ["0", "0"]
    d = defs[v] if v in defs else [0, -1]
    i = fn.blocks[d[0]].code[d[1]] if d[1] >= 0 else Ins("", "", "")
    if is_opt(t) and i.op == "slot.unpack":
        # usplits proved this getbox has no other observer. Read the payload at
        # the original lookup, before subsequent callbacks can mutate the dict.
        # val_or_zero never reads the miss index and performs no allocation.
        raw = i.a[0].v
        rd = defs[raw]
        get = fn.blocks[rd[0]].code[rd[1]]
        self.runtime("pys_dict_find")
        self.runtime("pys_dict_val_or_zero")
        get.s = "dict.find"
        get.t = "int"
        get.a = get.a[:2]
        ops: list[Ins] = []
        fn.n += 1
        found = Ins("num.cmp", "bool", ">=")
        found.line = get.line
        found.a = [Val(raw, "int"), Val("0", "int")]
        found.r = one_num(fn.n)
        ops.append(found)
        fn.n += 1
        tag = Ins("num.cast", "int", "")
        tag.line = get.line
        tag.a = [Val(tmpname(found.r[0]), "bool")]
        tag.r = one_num(fn.n)
        ops.append(tag)
        fn.n += 1
        payload = Ins("rt", "*V", "dict.val_or_zero")
        payload.line = get.line
        payload.a = [get.a[0], Val(raw, "int")]
        payload.r = one_num(fn.n)
        ops.append(payload)
        parts[v] = [tmpname(tag.r[0]), tmpname(payload.r[0])]
        key = f"{rd[0]}:{rd[1]}"
        if key not in after:
            after[key] = []
        after[key].extend(ops)
        return parts[v]
    if is_opt(t) and i.op == "rt" and i.s == "box":
        parts[v] = ["1", i.a[0].v]
        return parts[v]
    if i.op == "rt" and i.s == "ubox":
        parts[v] = [i.a[0].v, i.a[1].v]
        return parts[v]
    if i.op == "phi":
        ph: list[Ins] = []
        for k in range(2):
            fn.n += 1
            p = Ins("phi", "int", "")
            p.line = i.line
            p.r = one_num(fn.n)
            p.a = []
            p.b = []
            ph.append(p)
        parts[v] = [tmpname(ph[0].r[0]), tmpname(ph[1].r[0])]  # (first: a loop's phi meets itself)
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
    tg.line = i.line
    tg.a = [Val(v, t)]
    tg.r = one_num(fn.n)
    pl = Ins("union.raw", "%slot", "")
    pl.line = i.line
    pl.a = [Val(v, t)]
    pl.r = [fn.n + 1, fn.n + 2]
    fn.n += 2
    parts[v] = [tmpname(tg.r[0]), tmpname(pl.r[1])]
    key = f"{d[0]}:{d[1]}" if d[1] >= 0 else "0:0"
    at = after if d[1] >= 0 else before
    if key not in at:
        at[key] = []
    at[key].extend([tg, pl])
    return parts[v]

def gen_uleaves(self, fn: IFn, uses: dict[str, list[list[int]]], i: Ins, split: dict[str, Ins]) -> bool:
    # does the value of load i of a slot that unionslots splits leave the local: go to an op other
    # than its union.tag, its union.payload/raw, a tag read and a store to a slot that splits too
    for w in uses.get(tmpname(i.r[0]), []):
        o = fn.blocks[w[0]].code[w[1]]
        if is_opt(i.t):
            if self.tag_read(o) or (o.op == "ptr.cmp" and len(o.a) == 2 and (o.a[0].v == "null" or o.a[1].v == "null")):
                continue
            return True
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
        elif i.op == "union.payload" or i.op == "union.raw" or i.op == "dyn.payload" or i.op == "dyn.raw":
            # A union box's tag and payload are immutable. Retain the equivalence of
            # repeated narrowed reads expose to dictionary lookup fusion.
            r = self.same(vs, v, f"{i.op} {i.s} {self.canon(vs, i.a[0].v)}")
        elif i.op == "dyn.type":
            r = self.same(vs, v, f"dyn.type {self.canon(vs, i.a[0].v)}")
        elif i.op == "tuple.load" or i.op == "tuple.store":
            if v == tmpname(i.r[0]):
                # Fixed and traversed tuple slots share one semantic address key.
                r = self.same(vs, v, f"address int 0 {self.canon(vs, i.a[0].v)} {i.k}")
            else:
                x = self.reaching(vs, self.addr(vs, tmpname(i.r[0])), w // vs.stride, w % vs.stride)
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
                    return i.a[1].v if i.op == "mem.store" or i.op == "mach.store" else tmpname(i.r[0])
                if (i.op == "mem.store" or i.op == "mach.store") and heap and not p.startswith("@") and "." not in p and not self.disjoint(vs, a, q):
                    return ""
                continue
            if i.op == "tuple.load" or i.op == "tuple.store":
                p = tmpname(i.r[0])
                q = self.addr(vs, p)
                if q == a:
                    return i.a[1].v if i.op == "tuple.store" else tmpname(i.r[1])
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
                v = tmpname(i.r[0])
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
        br.line = t.line
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
