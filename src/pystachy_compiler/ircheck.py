"""Ircheck component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import Blk, IFn, Ins
from src.pystachy_compiler.specs import FX, FXALL, FXBIT, ICMP, IROPS, NONEVAR, RAWR, RAWW, RUNTIME
from src.pystachy_compiler.utils import is_dict, is_gen, is_opt, is_set, is_tuple, is_union, lt, same_kind, targs, umembers


class EffectSummaries:
    # One compilation's completed function contexts. FnInfo retains each context's parameter
    # and return types; these summaries retain its effects and direct call dependencies. A
    # missing/indirect callee contributes FXALL, never the empty mask used by a proven pure
    # function. Indices are stable while the program's optimization passes run.
    def __init__(self):
        self.direct: list[int] = []
        self.calls: list[list[int]] = []
        self.fx: list[int] = []
        self.reused = 0
        self.invalidated = 0
        self.edge_visits = 0
        self.edge_bound = 0

    def update(self, direct: list[int], calls: list[list[int]]) -> None:
        # Rebuild the reverse graph, then invalidate changed contexts and their callers.
        # Resetting that closure to local effects also handles REMOVED effects and cycles:
        # simply OR-ing new effects into an old summary would retain obsolete facts forever.
        n = len(direct)
        callers: list[list[int]] = []
        for j in range(n):
            callers.append([])
        for j in range(n):
            for c in calls[j]:
                callers[c].append(j)
        fresh = len(self.fx) != n
        if fresh:
            self.fx = [0] * n
        dirty: list[bool] = [False] * n
        affected: list[int] = []
        for j in range(n):
            if fresh or direct[j] != self.direct[j] or calls[j] != self.calls[j]:
                dirty[j] = True
                affected.append(j)
        head = 0
        while head < len(affected):
            c = affected[head]
            head += 1
            for j in callers[c]:
                if not dirty[j]:
                    dirty[j] = True
                    affected.append(j)
        self.invalidated = len(affected)
        self.reused = n - self.invalidated
        self.edge_visits = 0
        self.edge_bound = 0
        for j in affected:
            self.fx[j] = direct[j] & FXALL
            self.edge_bound += (len(FX) - 1) * len(callers[j])
        # Unchanged callees already have complete summaries. Dirty callees propagate below.
        pending: list[int] = []
        queued: list[bool] = [False] * n
        for j in affected:
            for c in calls[j]:
                if not dirty[c]:
                    self.fx[j] |= self.fx[c]
            if self.fx[j] != 0:
                pending.append(j)
                queued[j] = True
        head = 0
        while head < len(pending):
            c = pending[head]
            head += 1
            queued[c] = False
            for j in callers[c]:
                self.edge_visits += 1
                m = self.fx[j] | self.fx[c]
                if m != self.fx[j]:
                    self.fx[j] = m
                    if not queued[j]:
                        pending.append(j)
                        queued[j] = True
        # There are only len(FX)-1 summary bits, each added at most once to a dirty
        # function: at most that many visits per reverse edge. Propagation uses neither
        # recursion nor an iteration cutoff.
        self.direct = [m for m in direct]
        self.calls = [[c for c in cs] for cs in calls]


def gen_verify(self, fn: IFn, eh: bool) -> None:
    # PYSTACHY_IRCHECK=1: fn is well formed. Every op is in IROPS, an rt op's key in RUNTIME;
    # call and init ops call compiled
    # functions (or, in runtime mode, runtime.c's functions that runtime.py declares); every block ends with its one terminator; branches go to blocks of fn; a phi
    # starts its block, and its predecessors branch there; each op holds exactly the numbers
    # its lowering prints (Ins.r), and no number or label is above IFn.n. Exceptions (once the
    # passes of eh_ir have run, eh): a landing op is alone in its block, which only the unwind
    # edges of invokes reach, and every invoke's unwind edge goes to one; in a block that a
    # try statement covers, no call that may raise is left a call, nor a raise or throw
    at: dict[str, int] = {}
    lands: dict[str, bool] = {}
    for b in fn.blocks:
        if len(b.code) > 0 and b.code[0].op == "landing":
            lands[b.label] = True
    for i in fn.slots:
        if i.op != "slot" or len(i.r) != 1:
            self.bad_ir(fn, fn.blocks[0], f"a {i.op} op among the slots, with {len(i.r)} numbers")
        if i.r[0] > fn.n:
            self.bad_ir(fn, fn.blocks[0], f"the slot of {i.s} numbered {i.r[0]}, above IFn.n ({fn.n})")
    for j in range(len(fn.blocks)):
        l = fn.blocks[j].label
        if l in at:
            self.bad_ir(fn, fn.blocks[j], "a second block of that name")
        if l.startswith("L") and int(l[1:]) > fn.n:
            self.bad_ir(fn, fn.blocks[j], f"a label above IFn.n ({fn.n})")
        at[l] = j
    succ: list[list[str]] = []
    for b in fn.blocks:
        out: list[str] = []
        for j in range(len(b.code)):
            i = b.code[j]
            if i.op not in IROPS:
                self.bad_ir(fn, b, f"unknown op {i.op}")
            inv = len(i.b) == 2 and (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume")
            if ("T" in IROPS[i.op] or inv) != (j == len(b.code) - 1):
                self.bad_ir(fn, b, f"a terminator in the middle, at {i.op}" if j < len(b.code) - 1 else f"no terminator, last {i.op}")
            if i.op == "landing" and j > 0:
                self.bad_ir(fn, b, "a landing op after other ops")
            if inv and i.b[1] not in lands:
                self.bad_ir(fn, b, f"an invoke whose unwind edge goes to {i.b[1]}, which is no landing block")
            for l in i.b[:1] if inv else i.b if i.op != "phi" else i.b[:0]:
                if l in lands:
                    self.bad_ir(fn, b, f"a branch to the landing block {l}, which only unwind edges may reach")
            if eh and b.handler != "" and (i.op == "raise" or i.op == "throw" or (not inv and (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume") and self.opfx(i, fn.fa) & FXBIT["R"] != 0)):
                self.bad_ir(fn, b, f"{i.op} {i.s} may raise, in a block {b.handler} covers, but goes to no landing block")
            if i.op == "phi" and j > 0 and b.code[j - 1].op != "phi":
                self.bad_ir(fn, b, "a phi after other ops")
            if i.op == "rt" and i.s not in self.rtfns:
                self.bad_ir(fn, b, f"no RUNTIME entry for {i.s}" if i.s not in RUNTIME else f"{i.s}, which runtime() did not declare")
            if i.op == "empty.kind":
                if len(i.a) != 1 or i.t != "" or i.s != "" or i.x != "" or len(i.b) != 0 or i.k < 0 or i.k >= len(self.holes):
                    self.bad_ir(fn, b, "empty.kind needs one empty dict/set and a valid type hole")
                t = i.a[0].t
                if not (is_dict(t) or is_set(t)) or (i.k == 0 and "?" in t):
                    self.bad_ir(fn, b, "empty.kind needs a dict/set key type or a deferred hole")
                h = self.holes[i.k] if i.k > 0 else t
                if h != "" and (not same_kind(t, h) or "?" in h):
                    self.bad_ir(fn, b, "empty.kind needs a concrete hole of the same dict/set kind")
            if i.op == "scalar.bin" or i.op == "scalar.cast" or i.op == "scalar.cmp":
                self.verify_scalar(fn, b, i)
            if i.op == "select":
                if len(i.a) != 3 or i.s != "" or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, "select needs three operands and no extra metadata")
                t = i.t
                if i.a[0].t != "bool" or i.a[1].t != t or i.a[2].t != t:
                    self.bad_ir(fn, b, "select needs a bool condition and matching value and result types")
                if t == "" or t == "None" or t.startswith("*") or t == "#" or (t.startswith("%") and t not in ["%ptr", "%byte", "%i32", "%slot"]) or (t in ["T", "K", "V", "S"] and t not in self.classes):
                    self.bad_ir(fn, b, "select needs a native or machine scalar value type")

            if i.op == "mach.load" or i.op == "mach.store":
                load = i.op == "mach.load"
                if len(i.a) != (1 if load else 2) or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, f"{i.op} has invalid operands or extra metadata")
                if i.a[0].t != "%ptr":
                    self.bad_ir(fn, b, f"{i.op} needs a machine pointer address")
                t = i.t if load else i.a[1].t
                if t == "" or t == "None" or (t.startswith("%") and t not in ["%ptr", "%byte", "%i32"]) or t.startswith("*") or t == "#" or (t in ["T", "K", "V", "S"] and t not in self.classes):
                    self.bad_ir(fn, b, f"{i.op} needs a machine storage value type")
                if (not load and i.t != "") or i.s not in ["", "length", "length.range", "bytes"] or (i.s == "length.range" and not load) or (i.s.startswith("length") and t != "int") or (i.s == "bytes" and t != "%byte"):
                    self.bad_ir(fn, b, f"{i.op} has invalid value or memory metadata")
            if i.op == "mach.addr":
                if len(i.a) != 2 or i.t != "%ptr" or i.s not in ["int", "%ptr", "%byte"] or i.x != "" or i.k not in [0, 1] or len(i.b) != 0:
                    self.bad_ir(fn, b, "mach.addr needs a machine element type and inbounds flag")
                if i.a[0].t != "%ptr" or i.a[1].t != "int":
                    self.bad_ir(fn, b, "mach.addr needs a machine pointer and int index")
            if i.op == "mem.load" or i.op == "mem.store":
                if len(i.a) != (1 if i.op == "mem.load" else 2) or i.s != "" or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, f"{i.op} has invalid operands or extra metadata")
                t = i.a[0].t[1:] if i.a[0].t.startswith("*") else ""
                if t == "" or t.startswith("%") or t.startswith("*") or t == "#" or (t in ["T", "K", "V", "S"] and t not in self.classes):
                    self.bad_ir(fn, b, f"{i.op} needs a typed address of a native value")
                if (i.op == "mem.load" and i.t != t) or (i.op == "mem.store" and (i.t != "" or i.a[1].t != t)):
                    self.bad_ir(fn, b, f"{i.op} needs matching address and native value types")
            if i.op == "alloc.fixed":
                if len(i.a) != 0 or i.s != "" or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, "alloc.fixed needs no operands or extra metadata")
                if i.t not in self.classes and not (is_tuple(i.t) and i.t.endswith("]") and i.t.count("[") == i.t.count("]") and "" not in targs(i.t) and "..." not in targs(i.t)):
                    self.bad_ir(fn, b, "alloc.fixed needs a declared class or fixed tuple type")
                if "alloc" not in self.rtfns:
                    self.bad_ir(fn, b, "alloc.fixed needs the alloc runtime declaration")
            if i.op == "field.addr":
                if len(i.a) != 1 or i.s != "" or i.x != "" or len(i.b) != 0:
                    self.bad_ir(fn, b, "field.addr needs one object and no extra metadata")
                if i.a[0].t not in self.classes:
                    self.bad_ir(fn, b, "field.addr needs a declared class layout")
                ci = self.classes[i.a[0].t]
                if i.k < 0 or (i.k >= len(ci.fields) and i.k not in ci.fflag.values()):
                    self.bad_ir(fn, b, "field.addr needs a declared field or assignment flag index")
                t = ci.ftypes[ci.fields[i.k]] if i.k < len(ci.fields) else "bool"
                if i.t != "*" + t and not (i.t == "*" + NONEVAR and lt(t) == "ptr"):
                    # (but a field compiled while only None had been given to it: Gen.none_field)
                    self.bad_ir(fn, b, "field.addr result must address the declared member type")
            if i.op == "tuple.load" or i.op == "tuple.store":
                if len(i.a) != (1 if i.op == "tuple.load" else 2) or i.x != "" or len(i.b) != 0:
                    self.bad_ir(fn, b, f"{i.op} has invalid operands or extra metadata")
                t = i.a[0].t
                ts = targs(t) if is_tuple(t) and t.endswith("]") and t.count("[") == t.count("]") else []
                if "" in ts or "..." in ts or i.k < 0 or i.k >= len(ts):
                    self.bad_ir(fn, b, f"{i.op} needs a fixed tuple and an in-range item index")
                if i.s != ts[i.k] or i.s.startswith("%") or i.s.startswith("*") or i.s == "#" or (i.s in ["T", "K", "V", "S"] and i.s not in self.classes):
                    self.bad_ir(fn, b, f"{i.op} needs the declared native item type")
                if (i.op == "tuple.load" and i.t != "%slot") or (i.op == "tuple.store" and (i.t != "" or i.a[1].t != "%slot")):
                    self.bad_ir(fn, b, f"{i.op} needs an opaque item slot")
            if i.op == "num.cast" or i.op == "num.cmp":
                if len(i.a) != (1 if i.op == "num.cast" else 2) or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, f"{i.op} has invalid operands or extra metadata")
                t = i.a[0].t
                if i.op == "num.cast":
                    if i.s != "" or not ((t == "bool" and (i.t == "int" or i.t == "float")) or (t == "int" and i.t == "float")):
                        self.bad_ir(fn, b, "num.cast needs bool to int/float or int to float")
                elif i.t != "bool" or i.s not in ICMP or (t != "int" and t != "float") or i.a[1].t != t:
                    self.bad_ir(fn, b, "num.cmp needs a comparison of two ints or two floats, returning bool")
            if i.op == "int.ucmp":
                if len(i.a) != 2 or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, "int.ucmp needs two operands and no extra metadata")
                if i.t != "bool" or i.s not in ["<", "<=", ">", ">="] or i.a[0].t != "int" or i.a[1].t != "int":
                    self.bad_ir(fn, b, "int.ucmp needs an unsigned order comparison of two ints, returning bool")
            if i.op == "ptr.cmp":
                if len(i.a) != 2 or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, "ptr.cmp needs two operands and no extra metadata")
                if i.t != "bool" or (i.s != "==" and i.s != "!="):
                    self.bad_ir(fn, b, "ptr.cmp needs == or !=, returning bool")
                for a in i.a:
                    t = a.t
                    if t == "" or t.startswith("%") or t.startswith("*") or t == "#" or (t in ["T", "K", "V", "S"] and t not in self.classes) or (t != "None" and lt(t) != "ptr"):
                        self.bad_ir(fn, b, "ptr.cmp needs native references or None")
            if i.op == "slot.pack" or i.op == "slot.unpack":
                if len(i.a) != 1 or i.s != "" or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, f"{i.op} needs one operand and no immediates or labels")
                t = i.a[0].t if i.op == "slot.pack" else i.t
                slot = i.t if i.op == "slot.pack" else i.a[0].t
                if slot != "%slot" or t == "" or t.startswith("%") or t.startswith("*") or t == "#" or (t in ["T", "K", "V", "S"] and t not in self.classes):
                    self.bad_ir(fn, b, f"{i.op} needs a native value type and a %slot")
            if i.op == "union.tag" or i.op == "union.payload":
                if len(i.a) != 1 or i.x != "" or i.k != 0 or len(i.b) != 0:
                    self.bad_ir(fn, b, f"{i.op} needs one union operand and no extra metadata")
                u = i.a[0].t
                ms = umembers(u) if is_union(u) and u.endswith("]") else []
                if len(ms) < 2:
                    self.bad_ir(fn, b, f"{i.op} needs a nonoptional closed union")
                for j in range(len(ms)):
                    m = ms[j]
                    if m == "" or m == "None" or is_opt(m) or is_union(m) or m.count("[") != m.count("]") or m in ms[:j] or m.startswith("%") or m.startswith("*") or m == "#" or (m in ["T", "K", "V", "S"] and m not in self.classes):
                        self.bad_ir(fn, b, f"{i.op} needs distinct nonoptional union members")
                if (i.op == "union.tag" and (i.t != "int" or i.s != "")) or (i.op == "union.payload" and (i.t != "%slot" or i.s not in ms)):
                    self.bad_ir(fn, b, f"{i.op} has an invalid result type or member")
            if i.op.startswith("gen."):
                self.verify_gen(fn, b, i, j)
            n = self.nums(i)
            if len(i.r) != n:
                self.bad_ir(fn, b, f"{i.op} {i.s} with {len(i.r)} numbers, where its lowering prints {n}")
            for x in i.r:
                if x > fn.n:
                    self.bad_ir(fn, b, f"{i.op} {i.s} numbered {x}, above IFn.n ({fn.n})")
            if (i.op == "call" and i.s not in self.fll and i.s not in self.externs) or (i.op == "init" and "@init." + i.s not in self.fll):
                self.bad_ir(fn, b, f"a call of {i.s}, which is not compiled")
            if i.op != "phi":
                out.extend(i.b)
            if i.op == "check":
                ck = i.x if i.x != "" else i.s
                out.append(fn.cold[ck] if ck in fn.cold else f"(none for {ck})")
        if len(b.code) == 0:
            self.bad_ir(fn, b, "no terminator")
        for l in out:
            if l not in at or l == "entry":
                self.bad_ir(fn, b, f"a branch to {l}, which is no block of it")
        succ.append(out)
    for b in fn.blocks:
        for i in b.code:
            if i.op == "phi":
                for l in i.b:
                    if l not in at or b.label not in succ[at[l]]:
                        self.bad_ir(fn, b, f"a phi from {l}, which does not branch there")

def gen_verify_gen(self, fn: IFn, b: Blk, i: Ins, j: int) -> None:
    # a generator op (docs/internals.md#generators): gen.start ends the entry block of a
    # generator function (IFn.coro) and names it (a str); gen.yield (a %slot, k 0 or 1) and
    # gen.ret (none, or a %slot) suspend one, gen.promise without an operand is its own promise;
    # gen.promise, gen.resume and gen.drop of a handle take a generator
    own = i.op == "gen.start" or i.op == "gen.yield" or i.op == "gen.ret" or (i.op == "gen.promise" and len(i.a) == 0)
    if own and not fn.coro:
        self.bad_ir(fn, b, f"{i.op} outside a generator function")
    if i.s != "" or i.x != "" or (i.k != 0 and i.op != "gen.yield") or i.k < 0 or i.k > 1:
        self.bad_ir(fn, b, f"{i.op} with extra metadata")
    if i.op == "gen.start" and (b is not fn.blocks[0] or len(i.a) != 1 or i.a[0].t != "str" or len(i.b) != 1 or i.t != ""):
        self.bad_ir(fn, b, "gen.start must end the entry block, with the generator's name and its first block")
    if i.op == "gen.yield" and (len(i.a) != 1 or i.a[0].t != "%slot" or len(i.b) != 1 or i.t != ""):
        self.bad_ir(fn, b, "gen.yield needs the value's slot and the block where it resumes")
    if i.op == "gen.ret" and (len(i.a) > 1 or (len(i.a) == 1 and i.a[0].t != "%slot") or len(i.b) != 0 or i.t != ""):
        self.bad_ir(fn, b, "gen.ret needs the slot of its value, if any")
    if i.op == "gen.promise" and (i.t != "%ptr" or len(i.a) > 1 or (len(i.a) == 1 and not is_gen(i.a[0].t)) or len(i.b) != 0):
        self.bad_ir(fn, b, "gen.promise needs a generator or none (its own)")
    if (i.op == "gen.resume" or i.op == "gen.drop") and (len(i.a) != 1 or not is_gen(i.a[0].t) or i.t != "" or (len(i.b) != 0 and (i.op == "gen.drop" or len(i.b) != 2))):
        self.bad_ir(fn, b, f"{i.op} needs a generator")
    if i.op == "gen.start" and j != len(b.code) - 1:
        self.bad_ir(fn, b, "gen.start before other ops")

def gen_nums(self, i: Ins) -> int:
    if i.op == "scalar.bin" or i.op == "scalar.cast" or i.op == "scalar.cmp":
        return 1
    # how many numbers op i defines (%tN): what its lowering prints
    if i.op == "field.addr" or i.op == "mach.load" or i.op == "mach.addr":
        return 1
    if i.op == "ovf":
        return 3
    if i.op == "list.load":
        return 4
    if i.op == "landing" or i.op == "exc.match" or i.op == "union.payload" or i.op == "tuple.load":
        return 2
    if i.op == "phi" or i.op == "select" or i.op == "list.len" or i.op == "slot.pack" or i.op == "slot.unpack" or i.op == "union.tag" or i.op == "num.cast" or i.op == "num.cmp" or i.op == "alloc.fixed" or i.op == "tuple.store" or i.op == "mem.load" or i.op == "int.ucmp" or i.op == "ptr.cmp" or i.op == "empty.kind":
        return 1
    if i.op == "gen.yield":
        return 2
    if i.op == "gen.ret":
        return 2
    if i.op == "gen.promise":
        return 1
    if i.op == "rt":
        return 0 if self.rtfns[i.s].sig[0] == "None" else 1
    if i.op == "call" or i.op == "icall":
        return 0 if i.t == "None" else 1
    return 0

def gen_bad_ir(self, fn: IFn, b: Blk, what: str) -> None:
    fail(f"internal error: bad IR in {fn.f.ll}, block {b.label or '(unnamed)'}: {what}", 0)

def gen_effects(self) -> None:
    # A context is analyzed once regardless of how many call sites use it. Scan local ops
    # and deduplicate dependencies, then reuse/propagate summaries through reverse edges.
    direct: list[int] = []
    calls: list[list[int]] = []
    for fn in self.fns:
        m = 0
        cs: list[int] = []
        seen: dict[int, bool] = {}
        for b in fn.blocks:
            for i in b.code:
                c = i.s if i.op == "call" else "@init." + i.s if i.op == "init" else ""
                if c in self.fll:
                    ix = self.fll[c]
                    if ix not in seen:
                        seen[ix] = True
                        cs.append(ix)
                else:
                    m |= self.opfx(i, fn.fa)
        direct.append(m & ~FXBIT["N"])
        calls.append(cs)
    self.summaries.update(direct, calls)
    for j in range(len(self.fns)):
        self.fns[j].fx = self.summaries.fx[j]

def gen_opfx(self, i: Ins, fa: dict[str, bool]) -> int:
    # the effects of op i (FX bits) of a function whose field addresses are fa (IFn.fa): a
    # call's and an init's are its callee's summary (IFn.fx: every letter until effects has
    # computed it, and if the callee is not compiled). Memory effects use typed addresses.
    if i.op == "call" or i.op == "init":
        c = i.s if i.op == "call" else "@init." + i.s
        return self.fns[self.fll[c]].fx if c in self.fll else FXALL
    if i.op == "icall":
        return FXALL  # (a Callable's code: any function of its type)
    if i.op == "rt":
        # (an exception, E, may be an object of an exception class, whose __str__ and __repr__ run;
        # a key hashed by its class, H, runs __hash__ and __eq__, and one hashed by identity, P,
        # its __repr__ where a KeyError names it; a recursive alias's edge, R, lets a value nest
        # past the depth guard of the runtime's descriptor walks)
        f = self.rtfns[i.s]
        fx = f.fx | (FXBIT["R"] if f.rq and "R" in i.x else 0)
        u = "O" in i.x or "H" in i.x or ("P" in i.x and fx & FXBIT["R"] != 0) or ("E" in i.x and len(self.xcls) > 0)
        return FXALL if f.q and u else fx
    if i.op == "mem.load" or i.op == "mem.store" or i.op == "mach.load" or i.op == "mach.store":
        st = i.op == "mem.store" or i.op == "mach.store"
        a = i.a[0].v
        if a.startswith("@"):
            return FXBIT["wG"] if st else FXBIT["rG"]
        if a.startswith("%") and "." in a:
            return 0  # a local slot: no address escapes
        if a in fa:
            return FXBIT["wO"] if st else FXBIT["rO"]
        return RAWW if st else RAWR
    return self.opfxs[i.op]

# ---- optimizations (OPTS): passes over an IFn, once the program is built and its effect
# summaries computed, that rewrite ops into cheaper ones (docs/typed-ir.md 7.1)
