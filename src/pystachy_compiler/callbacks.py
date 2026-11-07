"""Bounded AOT versions of loops whose erased callback has known targets.

Run after ordinary compilation, before effects and recursion accounting. Only
already-emitted immutable function objects are candidates. No source is inferred
again, and no code or profiling state is created while the program runs.
"""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Ins, Loop, Val
from src.pystachy_compiler.utils import identity_abi, is_callable


def callback_codes(fn: IFn, param: int) -> dict[str, bool]:
    # Follow the incoming value through its private, write-once parameter slot.
    # A captured/rebound/escaped slot cannot establish a target for the whole loop.
    arg = f"%a{param}"
    slot = ""
    for i in fn.blocks[0].code:
        if i.op == "mem.store" and i.a[1].v == arg:
            slot = i.a[0].v
    if slot == "" or not any(f"%{i.s}.{i.r[0]}" == slot for i in fn.slots):
        return {}
    stores = 0
    values = {arg: True}
    for b in fn.blocks:
        for i in b.code:
            for j in range(len(i.a)):
                if i.a[j].v != slot:
                    continue
                if i.op == "mem.store" and j == 0 and i.a[1].v == arg and b is fn.blocks[0]:
                    stores += 1
                elif i.op == "mem.load" and j == 0:
                    values[f"%t{i.r[0]}"] = True
                else:
                    return {}
    if stores != 1:
        return {}
    codes: dict[str, bool] = {}
    blocks = {b.label: b for b in fn.blocks}
    for b in fn.blocks:
        for i in b.code:
            if i.op == "mach.load" and i.t == "%ptr" and i.a[0].v in values:
                codes[f"%t{i.r[0]}"] = True
    # A direct use inside a loop pays for one guard per function activation.
    predecessors: dict[str, list[str]] = {}
    for b in fn.blocks:
        predecessors[b.label] = []
    for b in fn.blocks:
        for label in b.code[-1].b:
            predecessors[label].append(b.label)
    for loop in fn.loops:
        # Only the cyclic region: an else clause after the loop is not hot work.
        repeated: dict[str, bool] = {}
        pending = [loop.head]
        while len(pending) > 0:
            label = pending.pop()
            if label == loop.exit or label in repeated:
                continue
            repeated[label] = True
            pending.extend(predecessors[label])
        pending = [loop.head]
        seen = {loop.exit: True}
        while len(pending) > 0:
            label = pending.pop()
            if label in seen or label not in repeated:
                continue
            seen[label] = True
            b = blocks[label]
            for i in b.code:
                if i.op == "icall" and i.a[0].v in codes:
                    return codes
            pending.extend(b.code[-1].b)
    return {}


def callback_ins(i: Ins, arg: str, target: str, code: str, ft: str, codes: dict[str, bool]) -> Ins:
    c = Ins(i.op, i.t, i.s)
    c.k, c.x = i.k, i.x
    c.r, c.b = [r for r in i.r], [b for b in i.b]
    c.a = []
    for v in i.a:
        value = Val(target if v.v == arg else v.v, v.t).identity(v)
        value.lit, value.infer_from = v.lit, v.infer_from
        c.a.append(value)
    if i.op == "icall" and i.a[0].v in codes:
        # The exact immutable object proves both code and null environment.
        # Keep the ordinary adapter's argument/result conversions and ABI.
        c.op, c.s = "call", code
        c.a = [Val("null", ft)] + c.a[2:]
    return c


def callback_clone(fn: IFn, param: int, target: str, code: str, ft: str, codes: dict[str, bool], ordinal: int) -> IFn:
    f = fn.f
    g = FnInfo(f.name, f"{f.ll}.callback{ordinal}", f.node, "")
    g.params, g.ptypes = [p for p in f.params], [t for t in f.ptypes]
    g.ret, g.mod, g.home = f.ret, f.mod, f.home
    g.synthetic, g.noret = True, f.noret
    g.cmpops = f.cmpops
    out = IFn(g)
    out.ps, out.n = [p for p in fn.ps], fn.n
    out.numeric_only = fn.numeric_only
    out.fa, out.cold, out.coldh = dict(fn.fa), dict(fn.cold), dict(fn.coldh)
    out.rdepth, out.resumes, out.setslimit = fn.rdepth, fn.resumes, fn.setslimit
    # The original entry owns the source frame; a version is an uncounted helper.
    arg = f"%a{param}"
    out.slots = [callback_ins(i, arg, target, code, ft, codes) for i in fn.slots]
    out.blocks = []
    for b in fn.blocks:
        block = Blk(b.label)
        block.handler = b.handler
        block.code = [callback_ins(i, arg, target, code, ft, codes) for i in b.code]
        out.blocks.append(block)
    for loop in fn.loops:
        item = Loop(loop.kind, loop.head, loop.body, loop.step, loop.exit)
        item.mode, item.ctr = loop.mode, loop.ctr
        item.stop = Val(loop.stop.v, loop.stop.t)
        item.seqs = [Val(v.v, v.t) for v in loop.seqs]
        item.tests, item.idx = [s for s in loop.tests], [s for s in loop.idx]
        out.loops.append(item)
    return out


def callback_guards(fn: IFn, param: int, targets: list[str], variants: list[IFn]) -> None:
    # Retain the entry's depth snapshot ahead of the dispatcher. Every branch
    # executes the body once, after the caller has evaluated all arguments.
    entry = fn.blocks[0]
    fn.n += 1
    fallback = Blk(f"L{fn.n}")
    fallback.code = entry.code[1:]
    entry.code = entry.code[:1]
    for b in [fallback] + fn.blocks:
        for i in b.code:
            i.b = [fallback.label if label == "entry" else label for label in i.b]
    current = entry
    added: list[Blk] = []
    for j in range(len(variants)):
        fn.n += 1
        hit = Blk(f"L{fn.n}")
        fn.n += 1
        miss = Blk(f"L{fn.n}") if j + 1 < len(variants) else fallback
        compare = Ins("ptr.cmp", "bool", "==")
        compare.a = [Val(f"%a{param}", fn.f.ptypes[param]), Val(targets[j], fn.f.ptypes[param])]
        fn.n += 1
        compare.r = [fn.n]
        branch = Ins("cbr", "", "")
        branch.a, branch.b = [Val(f"%t{fn.n}", "bool")], [hit.label, miss.label]
        current.code.extend([compare, branch])
        call = Ins("call", fn.f.ret, variants[j].f.ll)
        call.a = [Val(f"%a{p}", fn.f.ptypes[p]) for p in fn.ps]
        ret = Ins("ret", "", "")
        if fn.f.ret != "None":
            fn.n += 1
            call.r = [fn.n]
            ret.a = [Val(f"%t{fn.n}", fn.f.ret)]
        hit.code = [call, ret]
        added.append(hit)
        if miss is not fallback:
            added.append(miss)
        current = miss
    fn.blocks = [entry] + added + [fallback] + fn.blocks[1:]


def specialize_callbacks(fns: list[IFn], adapters: dict[str, str], objects: dict[str, bool]) -> int:
    # Two targets per kernel, at most 256 existing instructions per body and
    # 4096 additional instructions per module. Candidate order is deterministic;
    # frequencies are not inferred from static use counts.
    candidates: dict[str, list[str]] = {}
    for key in adapters:
        ft, ct = key.split(" ")
        target = "@cvo." + adapters[key][4:]
        if ft.startswith("fn[f:") and target in objects:
            if ct not in candidates:
                candidates[ct] = []
            if len(candidates[ct]) < 2:
                candidates[ct].append(key)
    extra = 0
    for fn in fns[:]:
        f = fn.f
        if f.cls != "" or f.clo >= 0 or f.gen or f.export or f.pyexport or identity_abi(f) or len(fn.tries) > 0 or fn.landed or fn.coro or fn.pads or len(fn.loops) == 0:
            continue
        if not fn.counted or fn.rdepth == "":
            continue
        params = [p for p in fn.ps if is_callable(f.ptypes[p])]
        size = len(fn.slots) + sum(len(b.code) for b in fn.blocks)
        if len(params) != 1 or size > 256 or (size + 4) * 2 + extra > 4096:
            continue
        param = params[0]
        codes = callback_codes(fn, param)
        if len(codes) == 0:
            continue
        targets: list[str] = []
        variants: list[IFn] = []
        for key in candidates.get(f.ptypes[param], []):
            ft = key.split(" ")[0]
            code = adapters[key]
            target = "@cvo." + code[4:]
            variants.append(callback_clone(fn, param, target, code, ft, codes, len(variants) + 1))
            targets.append(target)
        if len(variants) > 0:
            callback_guards(fn, param, targets, variants)
            fns.extend(variants)
            extra += (size + 4) * len(variants)
    return extra
