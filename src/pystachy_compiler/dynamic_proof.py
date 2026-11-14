"""Builtin dynamic-payload guard proofs over the real typed-IR CFG.

A dynamic box's tag is immutable: the address of its DynType, one of runtime.c's
(BUILTIN_KINDS) or one the program emits (DynTypes). Only nonescaping private slots carry
memory facts; a copied SSA box keeps its tag when the original binding is overwritten. A
function's tag domain holds the DynTypes its tests and payload reads name, and an unknown
member, which stands for every other DynType (a runtime iterator's, say). Tests compare a
box's DynType with a DynType, call pys_dyn_isa or pys_dyn_role_isa (runtime.c), switch on
the class number of its DynType, or combine these. A payload read of static type t needs
every tag that reaches it to be one whose boxes have t's payload layout: an int's or a
bool's for an int (a bool's payload is its int value), for a class that of the class, of
a subclass or of a class that takes it as its role, and the DynType of t's boxes
otherwise. The table of DynTypes is the compiler's own: this checks the IR against it,
not the table.
"""
from __future__ import annotations

from src.pystachy_compiler.dataflow import forward_fixpoint, live_values
from src.pystachy_compiler.ir import Blk, Data, IFn, Ins, slot_register
from src.pystachy_compiler.union_proof import proof_number
from src.pystachy_compiler.union_state import UnionState, union_join


# runtime.c's DynType kinds (DK_*, as dynamic.py names them) and its role flag
DK_NONE = 0
DK_INT = 2
DK_OBJ = 8
DF_ROLE = 256
# the i64 word of a DynType that holds its class number, which class dispatchers switch on
CLASS_WORD = "3"
# runtime.c's builtin DynTypes and their kinds: their class number is -1, and they have no base
BUILTIN_KINDS: dict[str, int] = {
    "@pys_dyntype_none": 0, "@pys_dyntype_bool": 1, "@pys_dyntype_int": 2, "@pys_dyntype_bigint": 2,
    "@pys_dyntype_float": 3, "@pys_dyntype_str": 4, "@pys_dyntype_list": 5, "@pys_dyntype_intlist": 5,
    "@pys_dyntype_biglist": 5, "@pys_dyntype_dict": 6, "@pys_dyntype_tuple": 7, "@pys_dyntype_type": 12}
# Builtin payload types and the DynTypes whose boxes have that payload layout, sorted: a
# bool's payload is its int value, and checked and promoting int lists share one layout.
BUILTIN_PAYLOADS: dict[str, list[str]] = {
    "bool": ["@pys_dyntype_bool"], "int": ["@pys_dyntype_bool", "@pys_dyntype_int"],
    "float": ["@pys_dyntype_float"], "str": ["@pys_dyntype_str"],
    "dict[dyn,dyn]": ["@pys_dyntype_dict"], "vtuple[dyn]": ["@pys_dyntype_tuple"],
    "list[dyn]": ["@pys_dyntype_list"], "list[int]": ["@pys_dyntype_biglist", "@pys_dyntype_intlist"]}
# runtime.c's constant boxes and their DynTypes
BOX_TAGS: dict[str, str] = {"@pys_dyn_true_box": "@pys_dyntype_bool", "@pys_dyn_false_box": "@pys_dyntype_bool",
                            "@pys_dyn_none_box": "@pys_dyntype_none"}


class DynTypes:
    """The DynTypes of a program's boxes: runtime.c's and the program's own (its constants,
    as dynamic.py's dyn_class_type, dyn_fn_type and generator types make them), and the
    DynType of the boxes of each static type the program boxes (dyntypes and dynfnt)."""

    def __init__(self, consts: list[Data], dyntypes: dict[str, str], dynfnt: dict[str, str]) -> None:
        self.kind: dict[str, int] = {}
        self.cls: dict[str, int] = {}
        self.base: dict[str, str] = {}
        self.role: dict[str, str] = {}
        self.held: dict[str, str] = {}
        for k in BUILTIN_KINDS:
            self.kind[k] = BUILTIN_KINDS[k]
            self.cls[k] = -1
            self.base[k] = ""
            self.role[k] = ""
        for d in consts:
            if d.kind == "dyntype" and len(d.items) == 3 and len(d.refs) >= 3:
                # words kind, class number and flags; references descriptor, name, base,
                # three hooks and, with DF_ROLE, its role's DynType
                flags = int(d.items[2].v)
                self.kind[d.name] = int(d.items[0].v)
                self.cls[d.name] = int(d.items[1].v)
                self.base[d.name] = d.refs[2] if d.refs[2] != "null" else ""
                self.role[d.name] = d.refs[6] if (flags & DF_ROLE) != 0 and len(d.refs) == 7 else ""
        for t in dyntypes:
            self.held[t] = dyntypes[t]
        for t in dynfnt:
            self.held[t] = dynfnt[t]

    def derives(self, x: str, t: str) -> bool:
        # does DynType x's chain of bases, which pys_dyn_isa follows, reach DynType t
        seen: dict[str, bool] = {}
        while x != "" and x in self.kind and x not in seen:
            if x == t:
                return True
            seen[x] = True
            x = self.base[x]
        return False

    def tests(self, t: str, role: bool) -> list[str]:
        # the DynTypes of the boxes x for which pys_dyn_isa(x, t), or pys_dyn_role_isa, holds
        k = self.kind[t]
        return sorted([x for x in self.kind if x == t or (k == DK_INT and self.kind[x] == DK_INT) or (k == DK_OBJ and (self.kind[x] == DK_NONE or self.derives(x, t))) or (role and self.role[x] == t)])

    def payloads(self, t: str) -> list[str]:
        # the DynTypes of the boxes whose payload a read of static type t may take, sorted:
        # none for a type no DynType holds
        if t in BUILTIN_PAYLOADS:
            return BUILTIN_PAYLOADS[t]
        if t not in self.held:
            return []
        h = self.held[t]
        if h not in self.kind or self.kind[h] != DK_OBJ:
            return [h]
        # (a subclass's objects share its class's layout, and a role is a fieldless base)
        return sorted([x for x in self.kind if self.derives(x, h) or self.role[x] == h])

    def numbered(self, n: str) -> list[str]:
        # the DynTypes of the classes whose class number is literal n, sorted
        number = proof_number(n, 0, 2147483647)
        return sorted([x for x in self.kind if number >= 0 and self.kind[x] == DK_OBJ and self.cls[x] == number])


class DynamicProof:
    def __init__(self, fn: IFn, types: DynTypes):
        self.fn = fn
        self.types = types
        self.base: dict[str, list[str]] = {}
        self.blocks: dict[str, int] = {}
        self.private: dict[str, str] = {}
        self.bad: list[str] = []
        self.badblocks: list[str] = []
        self.visits = 0
        self.payloads = 0
        # the tags each payload type accepts, the tags for which each runtime test (its op and
        # DynType) holds, the class number word addresses and class numbers of the tags that
        # dyn.type reads, and the tags of each class number a switch tests
        self.accepts: dict[str, dict[str, bool]] = {}
        self.tests: dict[str, list[str]] = {}
        self.others: dict[str, list[str]] = {}
        self.addresses: dict[str, bool] = {}
        self.numbers: dict[str, bool] = {}
        self.cases: dict[str, list[str]] = {}
        # The domain names each tag these mention or a test compares with; "?" stands for
        # every other DynType.
        self.named: dict[str, bool] = {}
        tags: dict[str, bool] = {}
        for b in fn.blocks:
            for i in b.code:
                if i.op == "dyn.type" and len(i.r) == 1:
                    tags["%t" + str(i.r[0])] = True
        # (each in a pass of its own: a block can be listed before one that runs first)
        for b in fn.blocks:
            for i in b.code:
                if i.op == "mach.addr" and i.s == "int" and len(i.r) == 1 and len(i.a) == 2 and i.a[0].v in tags and i.a[1].v == CLASS_WORD:
                    self.addresses["%t" + str(i.r[0])] = True
        for b in fn.blocks:
            for i in b.code:
                if i.op == "mach.load" and i.t == "int" and len(i.r) == 1 and len(i.a) == 1 and i.a[0].v in self.addresses:
                    self.numbers["%t" + str(i.r[0])] = True
        for b in fn.blocks:
            for i in b.code:
                found: list[str] = []
                if i.op == "dyn.payload":
                    self.payloads += 1
                    if i.s not in self.accepts:
                        found = types.payloads(i.s)
                        self.accepts[i.s] = {t: True for t in found}
                elif i.op == "rt" and (i.s == "dyn.isa" or i.s == "dyn.role_isa") and len(i.a) == 2 and i.a[1].v in types.kind:
                    test = i.s + "|" + i.a[1].v
                    if test not in self.tests:
                        found = types.tests(i.a[1].v, i.s == "dyn.role_isa")
                        self.tests[test] = found
                elif i.op == "ptr.cmp":
                    found = [a.v for a in i.a if a.t == "dyntype" and a.v in types.kind]
                elif i.op == "switch" and len(i.a) > 0 and i.a[0].v in self.numbers:
                    for j in range(1, len(i.a)):
                        if i.a[j].v not in self.cases:
                            self.cases[i.a[j].v] = types.numbered(i.a[j].v)
                            found.extend(self.cases[i.a[j].v])
                for t in found:
                    self.named[t] = True
        self.full: list[str] = ["?"] + sorted([t for t in self.named])
        for test in self.tests:
            passing = {t: True for t in self.tests[test]}
            self.others[test] = [t for t in self.full if t not in passing]
        for i in fn.slots:
            if i.t == "dyn" or i.t == "dyntype" or i.t == "bool":
                # (a local's "is assigned" flag shares its number: named by number alone, it
                # would retype the local's own slot)
                self.private[slot_register(i)] = i.t
        for bn in range(len(fn.blocks)):
            b = fn.blocks[bn]
            self.blocks[b.label] = bn
            for i in b.code:
                # An address is private only if EVERY use is a direct load/store.
                # Passing it to a callee, aliasing it or using machine addressing
                # disables memory facts for the whole function, including earlier
                # guards. We never assume a callback leaves escaped storage alone.
                for j in range(len(i.a)):
                    v = i.a[j].v
                    if v in self.private and (j != 0 or (i.op != "mem.load" and i.op != "mem.store")):
                        del self.private[v]
        self.livevalues: dict[str, dict[str, bool]] = live_values(fn, self.blocks)

    def key(self, s: UnionState, v: str, tag: bool = False) -> str:
        # the state's key of value v, a box or (tag) a DynType; a constant's key gets its tag
        k = ("T:" if tag else "D:") + v
        t = v if tag and v in self.types.kind else "" if tag else BOX_TAGS.get(v, "")
        if t != "":
            s.set(k, [t] if t in self.named else ["?"])
        return k

    def accepted(self, payload: str) -> str:
        # the tags a payload read accepts, for its message
        tags = [t for t in self.accepts[payload]]
        return "/".join(tags[:4]) + ("/..." if len(tags) > 4 else "") if len(tags) > 0 else "none (no DynType holds it)"

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
            if v in self.addresses:
                s.forget("A:" + v)
            if v in self.numbers:
                s.forget("C:" + v)
        if i.op == "dyn.type":
            s.copy("T:" + r, self.key(s, i.a[0].v))
        elif i.op == "dyn.payload":
            accepted = self.accepts[i.s]
            if checking and s.live and (len(accepted) == 0 or len([t for t in s.dom(self.key(s, i.a[0].v)) if t not in accepted]) > 0):
                self.bad.append("dyn.payload of " + i.s + " needs tag " + self.accepted(i.s) + " for " + i.a[0].v)
                self.badblocks.append(block)
        elif i.op == "rt" and r != "" and len(i.a) == 2 and i.s + "|" + i.a[1].v in self.tests:
            # pys_dyn_isa or pys_dyn_role_isa of a box and a DynType: nonzero for its tests' tags
            test = i.s + "|" + i.a[1].v
            box = self.key(s, i.a[0].v)
            yes = s.clone()
            no = s.clone()
            yes.narrow(box, self.tests[test])
            no.narrow(box, self.others[test])
            s.boolean(r, yes, no)
        elif i.op == "num.cmp" and (i.s == "==" or i.s == "!=") and r != "" and len(i.a) == 2:
            # a test's integer result compared with zero
            for j in range(2):
                v = i.a[j].v
                if i.a[1 - j].v == "0" and v in s.truth:
                    s.boolean(r, s.conditional(v, i.s == "!="), s.conditional(v, i.s == "=="))
                    break
        elif i.op == "mach.addr" and r in self.addresses:
            # the class number word of a tag, then the class number it holds
            s.copy("A:" + r, self.key(s, i.a[0].v, True))
        elif i.op == "mach.load" and r in self.numbers:
            s.copy("C:" + r, "A:" + i.a[0].v)
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
                if operand.t == "dyntype" and literal.t == "dyntype" and literal.v in self.named:
                    self.compare(s, r, self.key(s, operand.v, True), literal.v, i.s == "==")
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

    def flow(self, b: Blk, s: UnionState, targets: list[str], edges: list[UnionState]) -> None:
        # one block for the worklist (dataflow.forward_fixpoint): s becomes its facts at its
        # end, and each edge that leaves it joins targets and edges
        label = b.label
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
        elif last.op == "switch" and len(last.a) > 0 and last.a[0].v in self.numbers and len(last.a) == len(last.b):
            # A class dispatcher: each case takes the tags of its class number, and the
            # default the rest. (A case whose number no DynType of the table holds learns
            # nothing.)
            number = "C:" + last.a[0].v
            taken: dict[str, bool] = {}
            for j in range(1, len(last.a)):
                arm = s.clone()
                if len(self.cases[last.a[j].v]) > 0:
                    arm.narrow(number, self.cases[last.a[j].v])
                for t in self.cases[last.a[j].v]:
                    taken[t] = True
                targets.append(last.b[j])
                edges.append(arm)
            rest = s.clone()
            rest.narrow(number, [t for t in self.full if t not in taken])
            targets.append(last.b[0])
            edges.append(rest)
        else:
            for target in last.b:
                targets.append(target)
                edges.append(s.clone())

    def run(self) -> None:
        forward_fixpoint(self)
