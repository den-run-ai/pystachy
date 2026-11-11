"""Builtin dynamic-payload guard proofs over the real typed-IR CFG.

Dynamic boxes have immutable tags. Only nonescaping private slots carry memory
facts; a copied SSA box keeps its tag when the original binding is overwritten.
The open tag domain always retains an unknown member, which stands for every
DynType outside the tracked builtins (a wide int's among them). An int read
accepts an int's or a bool's box, whose payload is its int value. This is
deliberately not a proof for class inheritance or container layouts.
"""
from __future__ import annotations

from src.pystachy_compiler.ir import IFn, Ins, slot_register
from src.pystachy_compiler.union_state import UnionState, union_join


# The builtin DynTypes this proof tells apart (runtime.c's pys_dyntype_<tag>).
TRACKED: list[str] = ["bool", "float", "int", "none", "str"]


def payload_tags(t: str) -> list[str]:
    # the tags of the boxes whose payload a dyn.payload of static type t may read
    if t == "int":
        return ["bool", "int"]
    if t == "float" or t == "str" or t == "bool":
        return [t]
    return []


def exact_dynamic_payload(t: str) -> bool:
    return len(payload_tags(t)) > 0


class DynamicProof:
    def __init__(self, fn: IFn):
        self.fn = fn
        self.full: list[str] = ["?"] + TRACKED
        self.base: dict[str, list[str]] = {}
        self.blocks: dict[str, int] = {}
        self.private: dict[str, str] = {}
        self.bad: list[str] = []
        self.badblocks: list[str] = []
        self.visits = 0
        self.payloads = 0
        for i in fn.slots:
            if i.t == "dyn" or i.t == "dyntype" or i.t == "bool":
                # (a local's "is assigned" flag shares its number: named by number alone, it
                # would retype the local's own slot)
                self.private[slot_register(i)] = i.t
        for bn in range(len(fn.blocks)):
            b = fn.blocks[bn]
            self.blocks[b.label] = bn
            for i in b.code:
                if i.op == "dyn.payload" and exact_dynamic_payload(i.s):
                    self.payloads += 1
                # An address is private only if EVERY use is a direct load/store.
                # Passing it to a callee, aliasing it or using machine addressing
                # disables memory facts for the whole function, including earlier
                # guards. We never assume a callback leaves escaped storage alone.
                for j in range(len(i.a)):
                    v = i.a[j].v
                    if v in self.private and (j != 0 or (i.op != "mem.load" and i.op != "mem.store")):
                        del self.private[v]
        self.livevalues: dict[str, dict[str, bool]] = {}
        uses: dict[str, dict[str, bool]] = {}
        definitions: dict[str, dict[str, bool]] = {}
        for b in fn.blocks:
            uses[b.label] = {}
            definitions[b.label] = {}
            self.livevalues[b.label] = {}
            for i in b.code:
                if i.op == "phi":
                    continue
                for a in i.a:
                    if a.v.startswith("%") and a.v not in definitions[b.label]:
                        uses[b.label][a.v] = True
                for n in i.r:
                    definitions[b.label]["%t" + str(n)] = True
        changed = True
        while changed:
            changed = False
            for bn in range(len(fn.blocks) - 1, -1, -1):
                b = fn.blocks[bn]
                live = dict(uses[b.label])
                targets = [v for v in b.code[-1].b]
                if b.handler != "":
                    targets.append(b.handler)
                last = b.code[-1]
                if last.op == "check":
                    key = last.x if last.x != "" else last.s
                    if key in fn.cold:
                        targets.append(fn.cold[key])
                for target in targets:
                    if target not in self.blocks:
                        continue
                    incoming = dict(self.livevalues[target])
                    for i in fn.blocks[self.blocks[target]].code:
                        if i.op != "phi":
                            break
                        r = "%t" + str(i.r[0])
                        if r in incoming:
                            del incoming[r]
                            if b.label in i.b:
                                v = i.a[i.b.index(b.label)].v
                                if v.startswith("%"):
                                    incoming[v] = True
                    for v in incoming:
                        if v not in definitions[b.label]:
                            live[v] = True
                if live != self.livevalues[b.label]:
                    self.livevalues[b.label] = live
                    changed = True

    def key(self, s: UnionState, v: str, tag: bool = False) -> str:
        k = ("T:" if tag else "D:") + v
        if tag and v.startswith("@pys_dyntype_") and v[13:] in TRACKED:
            s.set(k, [v[13:]])
        elif not tag and (v == "@pys_dyn_true_box" or v == "@pys_dyn_false_box"):
            s.set(k, ["bool"])
        elif not tag and v == "@pys_dyn_none_box":
            s.set(k, ["none"])
        return k

    def forget_bool(self, s: UnionState, v: str) -> None:
        if v in s.truth:
            del s.truth[v]
        if v in s.bt:
            del s.bt[v]
        if v in s.bf:
            del s.bf[v]

    def compare(self, s: UnionState, result: str, value: str, member: str, equal: bool) -> None:
        yes = s.clone()
        no = s.clone()
        yes.narrow(value, [member])
        no.narrow(value, [t for t in self.full if t != member])
        s.boolean(result, yes if equal else no, no if equal else yes)

    def transfer(self, s: UnionState, i: Ins, block: str, checking: bool) -> None:
        r = "%t" + str(i.r[0]) if len(i.r) > 0 else ""
        for n in i.r:
            v = "%t" + str(n)
            s.forget("D:" + v)
            s.forget("T:" + v)
            self.forget_bool(s, v)
        if i.op == "dyn.type":
            s.copy("T:" + r, self.key(s, i.a[0].v))
        elif i.op == "dyn.payload" and exact_dynamic_payload(i.s):
            accepted = payload_tags(i.s)
            if checking and s.live and len([t for t in s.dom(self.key(s, i.a[0].v)) if t not in accepted]) > 0:
                self.bad.append("dyn.payload needs tag " + "/".join(accepted) + " for " + i.a[0].v)
                self.badblocks.append(block)
        elif i.op == "mem.load" and i.a[0].v in self.private:
            addr = i.a[0].v
            typ = self.private[addr]
            # A forged operand/result annotation cannot change a slot's contract.
            if i.t != typ or i.a[0].t != "*" + typ:
                if checking:
                    self.bad.append("dynamic guard proof needs matching private load types")
                    self.badblocks.append(block)
            elif typ == "bool":
                s.boolcopy(r, addr)
            else:
                s.copy(("T:" if typ == "dyntype" else "D:") + r, "M:" + addr)
        elif i.op == "mem.store" and i.a[0].v in self.private:
            addr = i.a[0].v
            typ = self.private[addr]
            s.forget("M:" + addr)
            self.forget_bool(s, addr)
            if i.a[0].t != "*" + typ or i.a[1].t != typ:
                if checking:
                    self.bad.append("dynamic guard proof needs matching private store types")
                    self.badblocks.append(block)
            elif typ == "bool":
                s.boolcopy(addr, i.a[1].v)
            else:
                s.copy("M:" + addr, self.key(s, i.a[1].v, typ == "dyntype"))
        elif i.op == "ptr.cmp" and (i.s == "==" or i.s == "!="):
            for j in range(2):
                operand = i.a[j]
                literal = i.a[1 - j]
                if operand.t == "dyntype" and literal.t == "dyntype" and literal.v.startswith("@pys_dyntype_") and literal.v[13:] in TRACKED:
                    self.compare(s, r, self.key(s, operand.v, True), literal.v[13:], i.s == "==")
                    break
        elif i.op == "scalar.bin" and i.t == "bool":
            x = i.a[0].v
            y = i.a[1].v
            if i.s == "xor" and (x == "true" or y == "true"):
                value = x if y == "true" else y
                s.boolean(r, s.conditional(value, False), s.conditional(value, True))
            elif i.s == "or" or i.s == "and":
                xt = s.conditional(x, True)
                xf = s.conditional(x, False)
                yt = s.conditional(y, True)
                yf = s.conditional(y, False)
                if i.s == "or":
                    xf.cond(y, False)
                    s.boolean(r, union_join(xt, yt), xf)
                else:
                    xt.cond(y, True)
                    s.boolean(r, xt, union_join(xf, yf))
        elif i.op == "select" and (i.t == "dyn" or i.t == "dyntype" or i.t == "bool"):
            yes = s.conditional(i.a[0].v, True)
            no = s.conditional(i.a[0].v, False)
            if i.t == "bool":
                yes.boolcopy(r, i.a[1].v)
                no.boolcopy(r, i.a[2].v)
            else:
                key = ("T:" if i.t == "dyntype" else "D:") + r
                yes.copy(key, self.key(yes, i.a[1].v, i.t == "dyntype"))
                no.copy(key, self.key(no, i.a[2].v, i.t == "dyntype"))
            merged = union_join(yes, no)
            s.d = merged.d
            s.eq = merged.eq
            s.bt = merged.bt
            s.bf = merged.bf
            s.truth = merged.truth
            s.live = merged.live
        # Other instructions produce unknown values. Calls cannot change an
        # existing immutable box's tag or a nonescaping private binding. Loads
        # from globals, fields, containers or escaped slots receive no facts.

    def edge(self, state: UnionState, source: str, target: str) -> UnionState:
        s = state.clone()
        dests: list[str] = []
        sources: list[str] = []
        bools: list[str] = []
        bsources: list[str] = []
        for i in self.fn.blocks[self.blocks[target]].code:
            if i.op != "phi":
                break
            r = "%t" + str(i.r[0])
            if source not in i.b:
                # The shape verifier checks named edges. Missing incoming values
                # cannot establish a proof if malformed IR reaches this solver.
                s.forget("D:" + r)
                s.forget("T:" + r)
                self.forget_bool(s, r)
                continue
            a = i.a[i.b.index(source)]
            if i.t == "dyn" or i.t == "dyntype":
                dests.append(("T:" if i.t == "dyntype" else "D:") + r)
                sources.append(self.key(s, a.v, i.t == "dyntype"))
            elif i.t == "bool":
                bools.append(r)
                bsources.append(a.v)
        # Phi assignments are simultaneous, including swapping loop-carried
        # values. Keep old sources until every temporary has been captured.
        for j in range(len(dests)):
            s.copy("phi:" + dests[j], sources[j])
        bs: list[UnionState] = []
        for j in range(len(bools)):
            q = s.clone()
            q.boolcopy(bools[j], bsources[j])
            # A saved condition refers to the PREVIOUS phi values. Rebinding
            # those names must not resurrect their old implications. Facts on
            # the captured source temporaries can instead describe the new
            # destinations (and preserve a paired value/condition phi).
            for facts in [q.bt[bools[j]], q.bf[bools[j]]]:
                for k in dests:
                    if k in facts:
                        del facts[k]
                    if "phi:" + k in facts:
                        facts[k] = facts["phi:" + k]
                        del facts["phi:" + k]
            bs.append(q)
        for k in dests:
            s.copy(k, "phi:" + k)
        for k in dests:
            s.forget("phi:" + k)
        for j in range(len(bools)):
            k = bools[j]
            s.truth[k] = bs[j].truth[k]
            s.bt[k] = bs[j].bt[k]
            s.bf[k] = bs[j].bf[k]
        s.retain(self.livevalues[target])
        return s

    def run(self) -> None:
        starts: dict[str, UnionState] = {"entry": UnionState(self.base, self.full)}
        pending = ["entry"]
        queued = {"entry": True}
        head = 0
        while head < len(pending):
            label = pending[head]
            head += 1
            queued[label] = False
            s = starts[label].clone()
            b = self.fn.blocks[self.blocks[label]]
            self.visits += 1
            targets: list[str] = []
            edges: list[UnionState] = []
            for i in b.code:
                if i.op == "phi":
                    continue
                # Before EH lowering, callbacks and runtime operations can leave
                # through a handler at this point, not at the block's final state.
                throwing = i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume" or i.op == "raise" or i.op == "throw" or i.op == "check"
                if b.handler != "" and throwing:
                    targets.append(b.handler)
                    edges.append(s.conditional(i.a[0].v, True) if i.op == "check" else s.clone())
                self.transfer(s, i, label, False)
            last = b.code[-1]
            if last.op == "cbr":
                targets.extend(last.b)
                edges.append(s.conditional(last.a[0].v, True))
                edges.append(s.conditional(last.a[0].v, False))
            elif last.op == "check":
                targets.append(last.b[0])
                edges.append(s.conditional(last.a[0].v, False))
                key = last.x if last.x != "" else last.s
                if key in self.fn.cold:
                    targets.append(self.fn.cold[key])
                    edges.append(s.conditional(last.a[0].v, True))
            else:
                for target in last.b:
                    targets.append(target)
                    edges.append(s.clone())
            for j in range(len(targets)):
                target = targets[j]
                if not edges[j].live or target not in self.blocks:
                    continue
                state = self.edge(edges[j], label, target)
                merged = union_join(starts[target], state) if target in starts else state
                if target not in starts or not merged.same(starts[target]):
                    starts[target] = merged
                    if target not in queued or not queued[target]:
                        pending.append(target)
                        queued[target] = True
        # Check only after the finite worklist reaches a fixed point. Checking
        # the first visit would miss a later unsafe join or loop backedge.
        for label in starts:
            s = starts[label].clone()
            for i in self.fn.blocks[self.blocks[label]].code:
                if i.op != "phi":
                    self.transfer(s, i, label, True)
