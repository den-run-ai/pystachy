"""Optimizations component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Ins, Lookup, Val, Values
from src.pystachy_compiler.ircheck import EffectSummaries
from src.pystachy_compiler.specs import CANON_DEPTH, FXBIT, LOOKUPS, RAWW, REACH
from src.pystachy_compiler.utils import identity_abi, is_list, is_tuple, is_union, numeric_identity, umembers


def recursion_blocked(self) -> bool:
    # Scalar code changes can change conservative roots in callers. Keep the
    # original program when finalization or termination callbacks can expose it.
    return (("open" in self.rtfns and not recursion_scoped_files(self))
            or any(k.startswith("weakref.") for k in self.rtfns)
            or self.ext != "" or len(self.cdirect) > 0
            or any(g.v == "@g.atexit$_hook" for g in self.globs))


def recursion_scoped_files(self) -> bool:
    # A native File protected immediately by with's unwind action is an explicit
    # collector root until deterministic close, including exception exits. Its
    # closure cannot depend on stale conservative stack/register roots. Require
    # this for every open, with no intervening instruction that could raise or
    # expose the new file. Suspended generators may retain their actions beyond
    # a normal native activation, so leave those and all other opens excluded.
    found = False
    for fn in self.fns:
        for b in fn.blocks:
            for at in range(len(b.code)):
                i = b.code[at]
                if i.op != "rt" or i.s != "open":
                    continue
                if fn.f.gen or fn.coro or len(i.r) != 1 or at + 1 == len(b.code):
                    return False
                protect = b.code[at + 1]
                if protect.op != "rt" or protect.s != "unwind_file" or len(protect.a) != 1 or protect.a[0].v != f"%t{i.r[0]}":
                    return False
                found = True
    return found  # an unaccounted runtime registration is not a proof


def recursion_copy(i: Ins) -> Ins:
    out = Ins(i.op, i.t, i.s)
    out.k = i.k
    out.x = i.x
    out.r = [r for r in i.r]
    out.a = [Val(a.v, a.t) for a in i.a]
    out.b = [b for b in i.b]
    return out


def recursion_fast(fn: IFn, skip: int, base: str, names: dict[str, str], entry: bool) -> IFn:
    # This runs after ordinary typed optimizations. Copy only their final IR and
    # the signature/lowering metadata it uses; never mutate the source FnInfo.
    old = fn.f
    f = FnInfo(old.name + ("$recursionentry" if entry else "$recursionfast"), names[old.ll], old.node, old.cls)
    f.params = [p for p in old.params]
    f.ptypes = [t for t in old.ptypes]
    f.ret = old.ret
    f.deco = old.deco
    f.mod = old.mod
    f.home = old.home
    f.noret = old.noret
    out = IFn(f)
    out.ps = [p for p in fn.ps]
    out.slots = [recursion_copy(i) for i in fn.slots]
    out.n = fn.n
    out.fa = {v: True for v in fn.fa}
    out.cold = {k: v for k, v in fn.cold.items()}
    out.blocks = []
    for b in fn.blocks:
        block = Blk(b.label)
        for at in range(len(b.code)):
            i = b.code[at]
            if b is fn.blocks[0] and at < skip:
                continue
            if base != "" and i.op == "rt" and i.s == "recursion.restore" and len(i.a) == 1 and i.a[0].v == base:
                continue
            op = recursion_copy(i)
            if op.op == "call":
                op.s = names[op.s]
            elif op.op == "init":
                op.op = "call"
                op.t = "None"
                op.s = names["@init." + op.s]
            block.code.append(op)
        out.blocks.append(block)
    return out


def recursion_repeated(self, fn: IFn, bounds: list[int]) -> bool:
    # A loop elsewhere in the function does not amortize a one-off source call.
    # Find calls in the strongly connected region of a recorded loop head by
    # intersecting forward/backward reachability. Implicit failure exits cannot
    # lead back to a head in these handler-free functions.
    at: dict[str, int] = {}
    back: list[list[int]] = [[] for _ in fn.blocks]
    forward: list[list[int]] = []
    counted: list[bool] = []
    for j in range(len(fn.blocks)):
        at[fn.blocks[j].label] = j
    for j in range(len(fn.blocks)):
        b = fn.blocks[j]
        edges = [at[l] for l in b.code[-1].b]
        forward.append(edges)
        for target in edges:
            back[target].append(j)
        counted.append(any(i.op == "call" and i.s in self.fll and bounds[self.fll[i.s]] > 0 for i in b.code))
    for loop in fn.loops:
        if loop.head not in at:
            continue
        head = at[loop.head]
        ancestors: dict[int, bool] = {head: True}
        work = [head]
        pos = 0
        while pos < len(work):
            j = work[pos]
            pos += 1
            for previous in back[j]:
                if previous not in ancestors:
                    ancestors[previous] = True
                    work.append(previous)
        reached: dict[int, bool] = {head: True}
        work = [head]
        pos = 0
        while pos < len(work):
            j = work[pos]
            pos += 1
            if counted[j]:
                return True
            for target in forward[j]:
                if target in ancestors and target not in reached:
                    reached[target] = True
                    work.append(target)
    return False


def recursion_bounded(self) -> int:
    # Version a bounded whole function, not a speculative early failure. The
    # selector tests the maximum *simultaneous* source-call depth, including all
    # branches. If the budget is unavailable the original body still runs: a
    # zero-trip loop may succeed, and effects before a failing call must happen.
    # Fast clones have no depth observers or mutations, including on failure
    # paths. Only direct calls in that proven subgraph use their unchecked ABI;
    # pointers, callbacks and every original entry retain their guarded symbols.
    if recursion_blocked(self):
        return 0
    nf = len(self.fns)
    calls: list[list[int]] = []
    back: list[list[int]] = [[] for _ in range(nf)]
    pending: list[int] = []
    valid: list[bool] = []
    bounds = [-1] * nf
    skips: list[int] = []
    bases: list[str] = []
    sizes: list[int] = []
    ready: list[int] = []
    for j in range(nf):
        fn = self.fns[j]
        ok = not (fn.coro or fn.f.gen or fn.f.export or fn.f.pyexport or fn.f.extern
                  or len(fn.tries) > 0 or fn.gdepth != "" or fn.pads)
        skip = 0
        base = ""
        if fn.counted:
            code = fn.blocks[0].code
            if len(code) > 0 and code[0].op == "rt" and code[0].s == "recursion.check" and fn.rdepth == "":
                skip = 1
            elif len(code) >= 2:
                enter = code[0]
                sub = code[1]
                if (enter.op == "rt" and enter.s == "recursion.enter" and len(enter.r) == 1
                        and fn.rdepth == f"%t{enter.r[0]}" and sub.op == "scalar.bin"
                        and sub.s == "sub" and sub.t == "int" and len(sub.r) == 1
                        and len(sub.a) == 2 and sub.a[0].v == fn.rdepth and sub.a[1].v == "1"):
                    skip = 2
                    base = f"%t{sub.r[0]}"
            ok = ok and skip > 0
        elif fn.rdepth != "":
            ok = False
        seen: dict[int, bool] = {}
        size = len(fn.slots)
        for b in fn.blocks:
            ok = ok and b.handler == ""
            size += len(b.code)
            for at in range(len(b.code)):
                i = b.code[at]
                if b is fn.blocks[0] and at < skip:
                    continue
                if base != "" and i.op == "rt" and i.s == "recursion.restore" and len(i.a) == 1 and i.a[0].v == base:
                    continue
                if any(a.v == fn.rdepth or (base != "" and a.v == base) for a in i.a):
                    ok = False
                callee_name = i.s if i.op == "call" else "@init." + i.s if i.op == "init" else ""
                if callee_name in self.fll:
                    seen[self.fll[callee_name]] = True
                elif (i.op == "throw" or i.op == "landing" or i.op.startswith("gen.")
                      or (i.op == "rt" and i.s in ["throw", "reraise"])
                      or self.opfx(i, fn.fa) & (FXBIT["U"] | FXBIT["I"]) != 0):
                    ok = False
        cs = [c for c in seen]
        calls.append(cs)
        pending.append(len(cs))
        valid.append(ok)
        skips.append(skip)
        bases.append(base)
        sizes.append(size)
        for c in cs:
            back[c].append(j)
        if len(cs) == 0:
            ready.append(j)
    # Bottom-up worklist: cycles (including uncounted-adapter cycles) never
    # become ready. Invalid callees propagate failure, not a guessed bound.
    pos = 0
    while pos < len(ready):
        j = ready[pos]
        pos += 1
        depth = 0
        ok = valid[j]
        for c in calls[j]:
            ok = ok and bounds[c] >= 0
            depth = max(depth, bounds[c])
        if ok:
            bounds[j] = depth + (1 if self.fns[j].counted else 0)
        for p in back[j]:
            pending[p] -= 1
            if pending[p] == 0:
                ready.append(p)
    roots: list[int] = []
    needed: dict[int, bool] = {}
    total = 0
    for j in range(nf):
        # Pure leaves already have one check. Version only functions with child
        # activations; cap both depth and emitted IR so large programs cannot
        # acquire an unbounded specialization/compilation cost.
        if not self.fns[j].counted or bounds[j] < 2 or bounds[j] > 64 or len(self.fns[j].loops) == 0:
            continue
        # A new forwarding return would hide the fresh tuple from tupleret and
        # reintroduce a heap allocation in callers which unpack it. Descendant
        # clones remain eligible; their bodies retain the fresh return proof.
        if "tupleret" in self.opts and is_tuple(self.fns[j].f.ret):
            continue
        if sizes[j] > 2048 or not recursion_repeated(self, self.fns[j], bounds):
            continue
        closure: dict[int, bool] = {j: True}
        work = [j]
        pos = 0
        cost = 0
        extra = 0
        while pos < len(work):
            c = work[pos]
            pos += 1
            cost += sizes[c]
            if c not in needed:
                extra += sizes[c]
            if cost > 2048 or total + extra > 8192:
                break
            for child in calls[c]:
                if child not in closure:
                    closure[child] = True
                    work.append(child)
        if cost > 2048 or total + extra > 8192:
            continue
        roots.append(j)
        for c in closure:
            needed[c] = True
        total += extra
    if len(roots) == 0:
        return 0
    # Only maximal regions need an entry wrapper. A nested root remains an
    # unchecked descendant of its selected ancestor; retaining its original
    # guarded entry avoids another wrapper and keeps the private descendant
    # inlineable. The complete needed DAG includes uncounted/intermediate
    # adapters, so an incoming edge catches transitive nesting too.
    roots = [j for j in roots if not any(parent in needed for parent in back[j])]
    entries = {j: True for j in roots}
    names: dict[str, str] = {}
    for j in needed:
        name = self.fns[j].f.ll
        names[name] = "@rf." + name[1:]
    # Clone before changing any original entry. Shared descendants get one
    # private clone regardless of how many bounded roots call them.
    for j in needed:
        fast = recursion_fast(self.fns[j], skips[j], bases[j], names, j in entries)
        self.fll[fast.f.ll] = len(self.fns)
        self.fns.append(fast)
    self.runtime("pys_recursion_room")
    for j in roots:
        fn = self.fns[j]
        fn.n += 1
        slow = f"L{fn.n}"
        fn.blocks[0].label = slow
        for b in fn.blocks:
            for i in b.code:
                i.b = [slow if l == "entry" else l for l in i.b]
        entry = Blk("entry")
        room = Ins("rt", "int", "recursion.room")
        room.a = [Val(str(bounds[j]), "int")]
        fn.n += 1
        room.r = [fn.n]
        cmp = Ins("scalar.cmp", "bool", "ne")
        cmp.a = [Val(f"%t{room.r[0]}", "int"), Val("0", "int")]
        fn.n += 1
        cmp.r = [fn.n]
        fn.n += 1
        fastblock = Blk(f"L{fn.n}")
        br = Ins("cbr", "", "")
        br.a = [Val(f"%t{cmp.r[0]}", "bool")]
        br.b = [fastblock.label, slow]
        entry.code = [room, cmp, br]
        call = Ins("call", fn.f.ret, names[fn.f.ll])
        call.a = [Val(f"%a{p}", fn.f.ptypes[p]) for p in fn.ps]
        if identity_abi(fn.f):
            call.a.extend([Val(f"%aid{p}", "dyn") for p in fn.ps if numeric_identity(fn.f.ptypes[p])])
            if numeric_identity(fn.f.ret):
                call.a.append(Val("%idret", "*dyn"))
        ret = Ins("ret", "", "")
        if fn.f.ret != "None":
            fn.n += 1
            call.r = [fn.n]
            ret.a = [Val(f"%t{fn.n}", fn.f.ret)]
        fastblock.code = [call, ret]
        fn.blocks = [entry, fastblock] + fn.blocks
    return len(roots)


def recursion_successors(fn: IFn) -> list[list[int]]:
    at: dict[str, int] = {b.label: j for j, b in enumerate(fn.blocks)}
    succ: list[list[int]] = []
    for block in fn.blocks:
        term = block.code[len(block.code) - 1]
        labels = [label for label in term.b]
        if term.op == "check":
            labels.append(fn.cold[term.x if term.x != "" else term.s])
        succ.append([at[label] for label in labels])
    return succ


def recursion_returning(fn: IFn, succ: list[list[int]]) -> list[bool]:
    back: list[list[int]] = [[] for _ in fn.blocks]
    returns: list[bool] = []
    work: list[int] = []
    for at in range(len(fn.blocks)):
        term = fn.blocks[at].code[len(fn.blocks[at].code) - 1]
        returns.append(term.op in ["ret", "ret.none"])
        if returns[at]:
            work.append(at)
        for child in succ[at]:
            back[child].append(at)
    pos = 0
    while pos < len(work):
        at = work[pos]
        pos += 1
        for parent in back[at]:
            if not returns[parent]:
                returns[parent] = True
                work.append(parent)
    return returns


def recursion_partial_child(self, fn: IFn) -> bool:
    # The existing leaf proof permits observers only beyond a publication bridge
    # into a suffix that cannot return. Recheck that boundary before reusing the
    # body with its entry already guaranteed by its immediate caller's budget.
    if (not fn.counted or fn.rdepth != "" or fn.coro or fn.f.gen or len(fn.tries) > 0
            or fn.gdepth != "" or fn.pads or len(fn.blocks[0].code) == 0):
        return False
    entry = fn.blocks[0].code[0]
    if entry.op != "rt" or entry.s != "recursion.check":
        return False
    succ = recursion_successors(fn)
    returns = recursion_returning(fn, succ)
    if not returns[0]:
        return False
    for at in range(len(fn.blocks)):
        block = fn.blocks[at]
        if block.handler != "":
            return False
        for pos in range(len(block.code)):
            op = block.code[pos]
            if at == 0 and pos == 0:
                continue
            if op.op == "landing" or op.op.startswith("gen."):
                return False
            observed = (op.op in ["call", "init", "icall", "throw"]
                        or self.opfx(op, fn.fa) & (FXBIT["U"] | FXBIT["I"]) != 0)
            if returns[at] and observed:
                return False
    # Verify the bridge invariant, rather than inferring it from a symbol or
    # the absence of rdepth. Bit 1 is unpublished, bit 2 already published.
    # Every observer must see exactly one bridge, and no bridge can be crossed
    # twice even through a cycle or an exceptional `check` successor.
    states = [0] * len(fn.blocks)
    states[0] = 1
    work = [0]
    pos = 0
    while pos < len(work):
        at = work[pos]
        pos += 1
        state = states[at]
        block = fn.blocks[at]
        for index in range(len(block.code)):
            op = block.code[index]
            if at == 0 and index == 0:
                continue
            if op.op == "rt" and op.s == "recursion.enter":
                if state != 1 or len(op.r) != 1:
                    return False
                state = 2
            elif op.op == "rt" and op.s.startswith("recursion."):
                return False
            elif (op.op in ["call", "init", "icall", "throw"]
                    or self.opfx(op, fn.fa) & (FXBIT["U"] | FXBIT["I"]) != 0):
                if state != 2:
                    return False
            if op.op in ["ret", "ret.none"] and state != 1:
                return False
        for target in succ[at]:
            combined = states[target] | state
            if combined != states[target]:
                states[target] = combined
                work.append(target)
    return True


def recursion_partial_header(fn: IFn, symbol: str) -> IFn:
    old = fn.f
    info = FnInfo(old.name + "$recursionpartial", symbol, old.node, old.cls)
    info.params = [p for p in old.params]
    info.ptypes = [t for t in old.ptypes]
    info.ret = old.ret
    info.deco = old.deco
    info.mod = old.mod
    info.home = old.home
    info.noret = old.noret
    out = IFn(info)
    out.ps = [p for p in fn.ps]
    out.slots = [recursion_copy(op) for op in fn.slots]
    out.n = fn.n
    out.fa = {value: True for value in fn.fa}
    out.cold = {key: label for key, label in fn.cold.items()}
    out.blocks = []
    return out


def recursion_partial_leaf(fn: IFn, symbol: str) -> IFn:
    out = recursion_partial_header(fn, symbol)
    for block in fn.blocks:
        copied = Blk(block.label)
        for pos in range(len(block.code)):
            op = block.code[pos]
            if block is fn.blocks[0] and pos == 0:
                continue
            if op.op == "rt" and op.s == "recursion.enter":
                # The unpublished chain is exactly root -> this child. The
                # original bridge is crossed once; its whole suffix is guarded.
                depth = Ins("rt", "int", "recursion.depth")
                out.n += 1
                depth.r = [out.n]
                active = Ins("scalar.bin", "int", "add")
                active.a = [Val(f"%t{out.n}", "int"), Val("2", "int")]
                active.r = [number for number in op.r]
                publish = Ins("rt", "None", "recursion.restore")
                publish.a = [Val(f"%t{op.r[0]}", "int")]
                copied.code.extend([depth, active, publish])
            else:
                copied.code.append(recursion_copy(op))
        out.blocks.append(copied)
    return out


def recursion_same_tail(left: Blk, right: Blk) -> bool:
    renamed: dict[str, str] = {}
    for at in range(3):
        a = left.code[at]
        b = right.code[at]
        if (a.op != b.op or a.t != b.t or a.s != b.s or a.k != b.k or a.x != b.x
                or len(a.r) != len(b.r) or len(a.a) != len(b.a) or a.b != b.b):
            return False
        for pos in range(len(a.a)):
            if a.a[pos].t != b.a[pos].t or renamed.get(a.a[pos].v, a.a[pos].v) != b.a[pos].v:
                return False
        for pos in range(len(a.r)):
            renamed[f"%t{a.r[pos]}"] = f"%t{b.r[pos]}"
    return True


def recursion_merge_tails(fn: IFn) -> int:
    # Always-inlining a partial child into duplicate return blocks duplicates
    # its entire body. Share only a local-slot load, that child call, and return;
    # prefixes stay on their original paths, including every depth publication.
    # The proof/budget already selected this private root. Do not rewrite the
    # guarded fallback or use this sharing to admit larger regions.
    if not fn.f.ll.startswith("@rp.") or fn.coro or fn.f.gen or fn.pads or len(fn.tries) > 0:
        return 0
    slots: dict[str, str] = {}
    uses: dict[str, str] = {}
    blocked: dict[str, bool] = {"entry": True, "": True}
    if len(fn.blocks) > 0:
        blocked[fn.blocks[0].label] = True
    for op in fn.slots:
        if op.op == "slot" and op.k == 0 and len(op.r) == 1:
            slots[f"%{op.s or 'h'}.{op.r[0]}"] = op.t
        for arg in op.a:
            uses[arg.v] = ""
    for value in fn.fa:
        uses[value] = ""
    uses[fn.rdepth] = ""
    uses[fn.gdepth] = ""
    for label in fn.cold.values():
        blocked[label] = True
    for label in fn.coldh.values():
        blocked[label] = True
    for block in fn.blocks:
        blocked[block.handler] = True
        for op in block.code:
            if op.op not in ["br", "cbr"]:
                for label in op.b:
                    blocked[label] = True  # phi, check and other hidden edges
            for arg in op.a:
                if arg.v not in uses:
                    uses[arg.v] = block.label
                elif uses[arg.v] != block.label:
                    uses[arg.v] = ""
    candidates: list[Blk] = []
    redirects: dict[str, str] = {}
    for block in fn.blocks:
        if block.label in blocked or block.handler != "" or len(block.code) != 3:
            continue
        load = block.code[0]
        call = block.code[1]
        ret = block.code[2]
        if (load.op != "mem.load" or len(load.r) != 1 or len(load.a) != 1 or len(load.b) != 0
                or load.a[0].v not in slots or slots[load.a[0].v] != load.t
                or call.op != "call" or not call.s.startswith("@rp2.") or len(call.r) != 1 or len(call.b) != 0
                or ret.op != "ret" or len(ret.r) != 0 or len(ret.a) != 1 or len(ret.b) != 0):
            continue
        loaded = f"%t{load.r[0]}"
        result = f"%t{call.r[0]}"
        if (loaded == result or ret.a[0].v != result or ret.a[0].t != call.t
                or not any(arg.v == loaded and arg.t == load.t for arg in call.a)
                or uses.get(loaded, "") != block.label or uses.get(result, "") != block.label):
            continue
        for previous in candidates:
            if recursion_same_tail(previous, block):
                redirects[block.label] = previous.label
                break
        if block.label not in redirects:
            candidates.append(block)
    if len(redirects) == 0:
        return 0
    for block in fn.blocks:
        for op in block.code:
            if op.op in ["br", "cbr"]:
                op.b = [redirects.get(label, label) for label in op.b]
    fn.blocks = [block for block in fn.blocks if block.label not in redirects]
    return len(redirects)


def recursion_partial_wrap(self, fn: IFn, symbol: str) -> None:
    fn.n += 1
    slow = f"L{fn.n}"
    fn.blocks[0].label = slow
    for block in fn.blocks:
        for op in block.code:
            op.b = [slow if label == "entry" else label for label in op.b]
    entry = Blk("entry")
    room = Ins("rt", "int", "recursion.room")
    room.a = [Val("2", "int")]
    fn.n += 1
    room.r = [fn.n]
    enough = Ins("scalar.cmp", "bool", "ne")
    enough.a = [Val(f"%t{fn.n}", "int"), Val("0", "int")]
    fn.n += 1
    enough.r = [fn.n]
    fn.n += 1
    fast = Blk(f"L{fn.n}")
    branch = Ins("cbr", "", "")
    branch.a = [Val(f"%t{enough.r[0]}", "bool")]
    branch.b = [fast.label, slow]
    entry.code = [room, enough, branch]
    call = Ins("call", fn.f.ret, symbol)
    call.a = [Val(f"%a{param}", fn.f.ptypes[param]) for param in fn.ps]
    if identity_abi(fn.f):
        call.a.extend([Val(f"%aid{param}", "dyn") for param in fn.ps if numeric_identity(fn.f.ptypes[param])])
        if numeric_identity(fn.f.ret):
            call.a.append(Val("%idret", "*dyn"))
    ret = Ins("ret", "", "")
    if fn.f.ret != "None":
        fn.n += 1
        call.r = [fn.n]
        ret.a = [Val(f"%t{fn.n}", fn.f.ret)]
    fast.code = [call, ret]
    fn.blocks = [entry, fast] + fn.blocks


def recursion_partial(self) -> int:
    if recursion_blocked(self):
        return 0
    nf = len(self.fns)
    children = [recursion_partial_child(self, fn) for fn in self.fns]
    weights = [len(fn.slots) + sum(len(block.code) for block in fn.blocks) for fn in self.fns]
    names: dict[str, str] = {}
    count = 0
    total = 0
    for root in range(nf):
        fn = self.fns[root]
        if (not fn.counted or fn.coro or fn.f.gen or fn.f.export or fn.f.pyexport or fn.f.extern
                or len(fn.tries) > 0 or fn.gdepth != "" or fn.pads or len(fn.blocks[0].code) < 2):
            continue
        if "tupleret" in self.opts and is_tuple(fn.f.ret):
            continue  # the forwarding wrapper would lose a fresh aggregate return
        enter = fn.blocks[0].code[0]
        sub = fn.blocks[0].code[1]
        if (enter.op != "rt" or enter.s != "recursion.enter" or len(enter.r) != 1
                or fn.rdepth != f"%t{enter.r[0]}" or sub.op != "scalar.bin" or sub.s != "sub"
                or sub.t != "int" or len(sub.r) != 1 or len(sub.a) != 2
                or sub.a[0].v != fn.rdepth or sub.a[1].v != "1"):
            continue
        base = f"%t{sub.r[0]}"
        succ = recursion_successors(fn)
        returns = recursion_returning(fn, succ)
        published = [False] * len(fn.blocks)
        work: list[int] = []
        valid = returns[0]
        size = weights[root]
        for at in range(len(fn.blocks)):
            block = fn.blocks[at]
            valid = valid and block.handler == ""
            for pos in range(len(block.code)):
                op = block.code[pos]
                if at == 0 and pos < 2:
                    continue
                if op.op == "rt" and op.s == "recursion.restore" and len(op.a) == 1 and op.a[0].v == base:
                    continue
                if any(arg.v in [fn.rdepth, base] for arg in op.a):
                    valid = False
                callee_name = op.s if op.op == "call" else "@init." + op.s if op.op == "init" else ""
                child = self.fll.get(callee_name, -1)
                observer = False
                if child >= 0 and child < nf:
                    observer = not children[child]
                    if observer and returns[at]:
                        # Only an ordinary direct tail call may return after
                        # changing the limit; there are no unchecked calls left.
                        valid = valid and op.op == "call" and block.code[len(block.code) - 1].op in ["ret", "ret.none"]
                        for after in block.code[pos + 1:]:
                            if after.op == "rt" and after.s == "recursion.restore" and len(after.a) == 1 and after.a[0].v == base:
                                continue
                            if after.op in ["call", "init", "icall", "throw"] or self.opfx(after, fn.fa) & (FXBIT["U"] | FXBIT["I"]) != 0:
                                valid = False
                elif op.op == "throw" or (op.op == "rt" and op.s in ["throw", "reraise"]):
                    observer = True
                    valid = valid and not returns[at]
                elif op.op == "landing" or op.op.startswith("gen.") or self.opfx(op, fn.fa) & (FXBIT["U"] | FXBIT["I"]) != 0:
                    valid = False
                if observer and not published[at]:
                    published[at] = True
                    work.append(at)
        pos = 0
        while pos < len(work):
            at = work[pos]
            pos += 1
            for target in succ[at]:
                if not published[target]:
                    published[target] = True
                    work.append(target)
        wanted: dict[int, bool] = {}
        normal_child = False
        for at in range(len(fn.blocks)):
            if published[at]:
                continue
            for op in fn.blocks[at].code:
                if op.op == "call" and op.s in self.fll:
                    child = self.fll[op.s]
                    if child < nf and children[child]:
                        wanted[child] = True
                        normal_child = normal_child or fn.blocks[at].code[len(fn.blocks[at].code) - 1].op in ["ret", "ret.none"]
        # Restrict this pass to a mixed body with useful normal child calls and
        # guarded suffixes. An unchecked child must directly feed a return: a
        # prefix scan before dispatch may still publish on its common path and
        # pay more for the selector than it saves. Keep all other prefix children
        # in the closed clone set once this stronger profitability test passes.
        if not valid or published[0] or len(work) == 0 or not normal_child or size > 768:
            continue
        cost = size
        # Both private layers must inline to expose the removed checks to LLVM.
        # Charge each rewritten callsite, not each shared child definition: one
        # child called repeatedly expands repeatedly. Child suffix calls retain
        # original guarded symbols, so mandatory inlining cannot recurse.
        for at in range(len(fn.blocks)):
            if published[at]:
                continue
            for op in fn.blocks[at].code:
                if op.op == "call" and op.s in self.fll:
                    child = self.fll[op.s]
                    if child in wanted:
                        cost += weights[child]
        if cost > 2048 or total + cost > 8192:
            continue
        total += cost
        for child in wanted:
            callee = self.fns[child]
            if callee.f.ll not in names:
                name = "@rp2." + callee.f.ll[1:]
                names[callee.f.ll] = name
                copied = recursion_partial_leaf(callee, name)
                self.fll[name] = len(self.fns)
                self.fns.append(copied)
        symbol = "@rp." + fn.f.ll[1:]
        fast = recursion_partial_header(fn, symbol)
        depth = Ins("rt", "int", "recursion.depth")
        depth.r = [number for number in sub.r]
        active = Ins("scalar.bin", "int", "add")
        active.a = [Val(base, "int"), Val("1", "int")]
        active.r = [number for number in enter.r]
        for at in range(len(fn.blocks)):
            block = fn.blocks[at]
            copied_block = Blk(block.label)
            if at == 0:
                copied_block.code = [depth, active]
            inserted = False
            for pos in range(len(block.code)):
                op = block.code[pos]
                if at == 0 and pos < 2:
                    continue
                if published[at] and not inserted and op.op != "phi":
                    publish = Ins("rt", "None", "recursion.restore")
                    publish.a = [Val(fn.rdepth, "int")]
                    copied_block.code.append(publish)
                    inserted = True
                if (not published[at] and op.op == "rt" and op.s == "recursion.restore"
                        and len(op.a) == 1 and op.a[0].v == base):
                    continue
                copied_op = recursion_copy(op)
                if not published[at] and op.op == "call" and op.s in names:
                    copied_op.s = names[op.s]
                copied_block.code.append(copied_op)
            fast.blocks.append(copied_block)
        recursion_merge_tails(fast)
        self.fll[symbol] = len(self.fns)
        self.fns.append(fast)
        self.runtime("pys_recursion_room")
        self.runtime("pys_recursion_depth")
        self.runtime("pys_recursion_restore")
        recursion_partial_wrap(self, fn, symbol)
        count += 1
    return count


def gen_recursionregion(self) -> int:
    return recursion_bounded(self) + recursion_partial(self)


def gen_recursionleaf(self) -> int:
    # Depth observation is separate from ordinary effects: the source entry still
    # raises and reads runtime state after this pass. Scan every block, including
    # exceptional/cleanup paths, before changing any function. A counted callee
    # observes its caller's depth even when its own bookkeeping will be elided.
    # Uncounted compiler adapters can be transparent only through a complete
    # transitive proof. Unknown/indirect calls, generators, and U/I operations are
    # boundaries (including limit changes, descriptor callbacks and foreign code).
    # A/R alone are not depth observers: native collection runs no user code, and
    # generator cleanup is an explicit gen.drop operation. But removing even
    # scalar bookkeeping can change register allocation and stale conservative
    # roots. Unmanaged files and weakrefs expose that changed retention, so
    # programs using them keep their original IR, including unrelated leaves.
    # Immediately registered with-files stay rooted until deterministic close.
    # Runtime registrations are complete here, before lowering; open creates a
    # collectable File, while std, print and input do not.
    if recursion_blocked(self):
        return 0
    # Uncaught errors and allocation failure can nevertheless run termination
    # callbacks. Keep full bookkeeping when atexit or CPython hooks may exist.
    # A throw of a user exception can also render __str__ before terminating; it
    # is a boundary below even though ordinary effect summaries label it only R.
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
                    m = m | observed
                c = i.s if i.op == "call" else "@init." + i.s if i.op == "init" else ""
                if c in self.fll:
                    ix = self.fll[c]
                    callee = self.fns[ix]
                    if callee.counted or callee.f.gen or callee.coro:
                        m = m | observed
                    elif ix not in seen:
                        seen[ix] = True
                        cs.append(ix)
                elif i.op == "throw" or i.op.startswith("gen.") or (i.op == "rt" and i.s in ["throw", "reraise"]) or self.opfx(i, fn.fa) & (FXBIT["U"] | FXBIT["I"]) != 0:
                    m = m | observed
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
