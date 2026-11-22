"""Proofs of reads of objects at narrower classes over the real typed-IR CFG.

An operand may read an object at a class its value's definition does not derive from: a
derived class (a downcast), or a class that may share an object with it, and a member cast
reads an object cast's value as one of its union's classes. The frontend makes such reads
where a test of the object's class leads, as a method dispatcher, isinstance or a match
does. With PYSTACHY_IRCHECK=1 the verifier asks this proof to show, at each such read, that
every class the object may have derives from the class it is read at.

Facts are domains of classes (UnionState): an object's domain starts as the classes that may
have objects and derive from its static class (Gen.derives; the verifier gives them, members)
and None, as a reference may be None, and a test against None and its class word narrow it. A
read of None at any class reads no object, so a domain of None alone needs no other proof. A tagged class's objects begin with their class's tag, an int
(ClassInfo.tag), and an exception class's with its descriptor, @x.<class>; a mach.load of the
object's first word or a mem.load of that field reads the word. A test of the word against a
tag or a descriptor, a switch on it, and the class word an allocation stores narrow the domain;
"?" stands for an object of no class the proof knows, which no test removes. Nonescaping
private slots carry memory facts, and so does an object's field of a class, keyed by the slot
the object was loaded from while it still holds it (UnionState.loaded), else by the object's
SSA value, so that a test of x.f proves a later read of x.f. An object's class never changes
once its word is stored, so calls leave the facts of SSA values and private slots alone; a
call may store any field, and a store to a field may store that field of any object, so they
forget the field facts they may change. Loads from globals and escaped slots receive the
static class's domain.
"""
from __future__ import annotations

from src.pystachy_compiler.dataflow import forward_fixpoint, live_values
from src.pystachy_compiler.ir import Blk, IFn, Ins, slot_register
from src.pystachy_compiler.symbols import ClassInfo
from src.pystachy_compiler.union_state import UnionState, union_join
from src.pystachy_compiler.utils import is_opt, is_union, umembers


class ClassProof:
    def __init__(self, fn: IFn, classes: dict[str, ClassInfo], members: dict[str, list[str]], types: dict[str, str], reads: dict[str, dict[str, bool]]):
        # fn's reads (ircheck.class_reads): each value an operand reads at a narrower class, with
        # those classes; types: each value's type where it is defined (ir.value_definitions);
        # members: for each class named here, the classes that may have objects and derive
        # from it, sorted
        self.fn = fn
        self.classes = classes
        self.members = members
        self.types = types
        self.reads = reads
        self.base: dict[str, list[str]] = {}
        self.blocks: dict[str, int] = {}
        self.private: dict[str, str] = {}
        self.bad: list[str] = []
        self.badblocks: list[str] = []
        self.visits = 0
        named: dict[str, bool] = {}
        for c in members:
            for m in members[c]:
                named[m] = True
        self.full: list[str] = sorted(["?", "None"] + [m for m in named])
        # (the values that are an object's class word, and the field addresses of one, by
        # the object they belong to)
        self.words: dict[str, str] = {}
        self.wordfields: dict[str, str] = {}
        for b in fn.blocks:
            for i in b.code:
                if i.op == "field.addr" and len(i.r) == 1 and len(i.a) == 1 and self.word_index(i.a[0].t) == i.k:
                    self.wordfields["%t" + str(i.r[0])] = i.a[0].v
        for b in fn.blocks:
            for i in b.code:
                if len(i.r) != 1 or len(i.a) != 1:
                    continue
                r = "%t" + str(i.r[0])
                if i.op == "mach.load" and i.a[0].t == "%ptr" and (i.t == "int" or i.t == "%ptr") and self.word_index(self.types.get(i.a[0].v, "")) == 0:
                    self.words[r] = i.a[0].v
                elif i.op == "mem.load" and i.a[0].v in self.wordfields:
                    self.words[r] = self.wordfields[i.a[0].v]
        for v in types:
            domain = self.domain(types[v])
            if len(domain) > 0:
                self.base["D:" + v] = domain
        # (the fields of a class that field.addr addresses, by result: the key's index and the
        # field's type, and each key that may name the field, with that type's domain)
        self.fields: dict[str, int] = {}
        self.fieldobjs: dict[str, str] = {}
        loads: dict[str, str] = {}
        for b in fn.blocks:
            for i in b.code:
                if i.op == "mem.load" and len(i.r) == 1 and len(i.a) == 1:
                    loads["%t" + str(i.r[0])] = i.a[0].v
        for b in fn.blocks:
            for i in b.code:
                if i.op == "field.addr" and len(i.r) == 1 and len(i.a) == 1 and i.t.startswith("&") and len(self.domain(i.t[1:])) > 0 and i.a[0].v.startswith("%"):
                    r = "%t" + str(i.r[0])
                    self.fields[r] = i.k
                    obj = i.a[0].v
                    self.fieldobjs[r] = obj
                    for owner in [obj, loads.get(obj, "")]:
                        if owner.startswith("%"):
                            self.base[self.field_key(owner, i.k)] = self.domain(i.t[1:])
        # (None, which an object's operand may read: no object, so of no class)
        self.base["D:null"] = ["None"]
        for i in fn.slots:
            if i.k != 2 and len(self.domain(i.t)) > 0:
                self.private[slot_register(i)] = i.t
                self.base["M:" + slot_register(i)] = self.domain(i.t)
        for bn in range(len(fn.blocks)):
            b = fn.blocks[bn]
            self.blocks[b.label] = bn
            for i in b.code:
                # (a slot is private while every use of its address is a direct load or store)
                for j in range(len(i.a)):
                    v = i.a[j].v
                    if v in self.private and (j != 0 or (i.op != "mem.load" and i.op != "mem.store")):
                        del self.private[v]
        self.livevalues: dict[str, dict[str, bool]] = live_values(fn, self.blocks)

    def field_key(self, owner: str, index: int) -> str:
        # the key of field index of the object that owner, a slot or an SSA value, names (without
        # its %, so that liveness keeps it: UnionState.needed)
        return "F:" + owner[1:] + "#" + str(index)

    def forget_fields(self, s: UnionState, index: int, owner: str) -> None:
        # forget the facts of field index of every object (-1: of every field), or of owner's
        # fields alone (owner != "")
        prefix = "F:" + owner[1:] + "#" if owner != "" else "F:"
        suffix = "#" + str(index)
        for k in [k for k in s.d if k.startswith(prefix) and (index < 0 or k.endswith(suffix))]:
            s.forget(k)

    def word_index(self, t: str) -> int:
        # the index of the field that holds the class word of an object of type t (its tag's,
        # or its exception descriptor's), or -1 where it has none; of a closed union of classes,
        # where all its classes' objects hold it at one index
        c = t[4:-1] if is_opt(t) else t
        if is_union(c):
            ms = umembers(c)
            indexes = [self.word_index(m) for m in ms]
            return indexes[0] if len(ms) > 0 and indexes[0] >= 0 and all(x == indexes[0] for x in indexes) else -1
        if c not in self.classes:
            return -1
        info = self.classes[c]
        if info.tag > 0:
            # (a tagged class's struct begins with its tag: flow.gen_fl_fields)
            return info.fpos[" class"] if " class" in info.fpos else 0
        if info.exc != "" and " cls" in info.fpos:
            return info.fpos[" cls"]
        return -1

    def domain(self, t: str) -> list[str]:
        # the classes an object of static type t may have: a class's members, a closed union of
        # classes' members together, and "?" for an object; [] for a type of no object
        c = t[4:-1] if is_opt(t) else t
        if c in self.members:
            return sorted(self.members[c] + ["None"])
        if c == "object":
            return ["?", "None"]
        if is_union(c):
            ms = umembers(c)
            if len(ms) > 0 and all(m in self.members for m in ms):
                found: dict[str, bool] = {"None": True}
                for m in ms:
                    for x in self.members[m]:
                        found[x] = True
                return sorted([x for x in found])
        return []

    def allowed(self, t: str) -> list[str]:
        c = t[4:-1] if is_opt(t) else t
        return self.members[c] if c in self.members else []

    def read_class(self, v: str, t: str) -> str:
        # the class that an operand of type t reads value v at, where it needs a proof, else "":
        # a member cast's value is read at its class wherever it is read
        if v not in self.reads:
            return ""
        if t in self.reads[v]:
            return t
        d = self.types.get(v, "")
        return d if d in self.reads[v] else ""

    def check(self, s: UnionState, v: str, t: str, block: str, where: str) -> None:
        # a read of object v at class t: every class v's object may have derives from t
        if not s.live:
            return
        accepted = self.allowed(t)
        domain = s.dom("D:" + v)
        if len(accepted) == 0 or len([m for m in domain if m not in accepted and m != "None"]) > 0:
            self.bad.append(where + " reads " + v + " as " + t + " without a proof that its class derives from " + t)
            self.badblocks.append(block)

    def forget_bool(self, s: UnionState, v: str) -> None:
        if v in s.truth:
            del s.truth[v]
        if v in s.bt:
            del s.bt[v]
        if v in s.bf:
            del s.bf[v]

    def tagged(self, literal: str) -> list[str]:
        # the classes whose objects' class word a tag or descriptor literal is
        return [m for m in self.full if m != "?" and m in self.classes and ((self.classes[m].tag > 0 and str(self.classes[m].tag) == literal) or (self.classes[m].exc != "" and "@x." + m == literal))]

    def assign(self, s: UnionState, key: str, domain: list[str]) -> None:
        # the object of key (and of each key equal to it: the same object) has a class of domain
        # alone now, whatever its facts were
        rep = s.eq.get(key, key)
        for x in s.eq:
            if s.eq[x] == rep:
                s.d[x] = domain
        s.d[key] = domain

    def compare(self, s: UnionState, result: str, key: str, matched: list[str], equal: bool) -> None:
        # a test of a class word: its value is one of matched's words where it holds; "?"
        # stays on both sides
        yes = s.clone()
        no = s.clone()
        yes.narrow(key, sorted(["?"] + matched))
        no.narrow(key, [m for m in self.full if m not in matched])
        s.boolean(result, yes if equal else no, no if equal else yes)

    def transfer(self, s: UnionState, i: Ins, block: str, checking: bool) -> None:
        r = "%t" + str(i.r[0]) if len(i.r) > 0 else ""
        if checking and s.live and i.op != "ptr.cmp":
            # (a ptr.cmp compares identities, or tests for None, which no class changes)
            for j in range(len(i.a)):
                a = i.a[j]
                t = self.read_class(a.v, a.t)
                if t != "":
                    if i.op == "select" and j > 0:
                        self.check(s.conditional(i.a[0].v, j == 1), a.v, t, block, "select operand " + str(j))
                    else:
                        self.check(s, a.v, t, block, i.op + " operand " + str(j))
        for n in i.r:
            v = "%t" + str(n)
            s.forget("D:" + v)
            self.forget_bool(s, v)
            if v in s.loaded:
                del s.loaded[v]
            self.forget_fields(s, -1, v)  # (a loop may redefine the SSA value)
        if i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume":
            self.forget_fields(s, -1, "")
        if r in self.words:
            s.copy("D:" + r, "D:" + self.words[r])
        elif (i.op == "mem.load" or i.op == "mach.load") and len(i.a) == 1 and i.a[0].v in self.private and r != "":
            s.copy("D:" + r, "M:" + i.a[0].v)
            s.loaded[r] = i.a[0].v
        elif i.op == "mem.load" and len(i.a) == 1 and i.a[0].v in self.fields and r != "" and "D:" + r in self.base:
            key = self.field_key(s.loaded.get(self.fieldobjs[i.a[0].v], self.fieldobjs[i.a[0].v]), self.fields[i.a[0].v])
            if key in self.base:
                s.copy("D:" + r, key)
        elif (i.op == "mem.store" or i.op == "mach.store") and len(i.a) == 2:
            addr = i.a[0].v
            v = i.a[1].v
            if addr in self.private:
                s.forget("M:" + addr)
                s.copy("M:" + addr, "D:" + v)
                for obj in [o for o in s.loaded if s.loaded[o] == addr]:
                    del s.loaded[obj]
                self.forget_fields(s, -1, addr)
            elif addr in self.fields:
                # (any object's field of that index may be the one stored)
                self.forget_fields(s, self.fields[addr], "")
                key = self.field_key(s.loaded.get(self.fieldobjs[addr], self.fieldobjs[addr]), self.fields[addr])
                if key in self.base:
                    s.copy(key, "D:" + v)
            # (an allocation's class word, which its constructor stores before any read)
            owner = self.wordfields[addr] if addr in self.wordfields else addr if i.op == "mach.store" and self.word_index(self.types.get(addr, "")) == 0 else ""
            if owner != "":
                matched = self.tagged(v)
                self.assign(s, "D:" + owner, matched if len(matched) > 0 else ["?"])
        elif (i.op == "num.cmp" or i.op == "ptr.cmp" or i.op == "scalar.cmp") and (i.s == "==" or i.s == "!=" or i.s == "eq" or i.s == "ne") and len(i.a) == 2 and r != "":
            for j in range(2):
                v = i.a[j].v
                other = i.a[1 - j].v
                if v in self.words and not other.startswith("%"):
                    self.compare(s, r, "D:" + v, self.tagged(other), i.s == "==" or i.s == "eq")
                    break
                if other == "null" and v.startswith("%") and (i.op == "ptr.cmp" or i.a[j].t == "%ptr") and len(s.dom("D:" + v)) > 0 and "D:" + v in self.base:
                    # (a test of an object against None, also of its pointer as a machine word)
                    yes = s.clone()
                    no = s.clone()
                    yes.narrow("D:" + v, ["None"])
                    no.narrow("D:" + v, [m for m in self.full if m != "None"])
                    s.boolean(r, yes if i.s == "==" or i.s == "eq" else no, no if i.s == "==" or i.s == "eq" else yes)
                    break
        elif i.op == "scalar.bin" and i.t == "bool" and len(i.a) == 2:
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
        elif i.op == "select" and len(i.a) == 3:
            yes = s.conditional(i.a[0].v, True)
            no = s.conditional(i.a[0].v, False)
            if i.t == "bool":
                yes.boolcopy(r, i.a[1].v)
                no.boolcopy(r, i.a[2].v)
            elif "D:" + r in self.base:
                yes.copy("D:" + r, "D:" + i.a[1].v)
                no.copy("D:" + r, "D:" + i.a[2].v)
            merged = union_join(yes, no)
            s.d = merged.d
            s.eq = merged.eq
            s.bt = merged.bt
            s.bf = merged.bf
            s.truth = merged.truth
            s.live = merged.live
        elif i.op == "cast" and len(i.a) == 1 and "D:" + r in self.base:
            # (the object it reads, at another type: lowering erases it. An object cast's is one
            # of its union's classes', which the union proof holds its box to; a member cast's
            # class is what tests of the object's class show where it is read)
            s.copy("D:" + r, "D:" + i.a[0].v)
            if i.s == "object":
                s.narrow("D:" + r, self.base["D:" + r])

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
                s.forget("D:" + r)
                self.forget_bool(s, r)
                continue
            a = i.a[i.b.index(source)]
            if "D:" + r in self.base or i.t == "%ptr":
                # (also an object as a machine word, which an object cast reads)
                dests.append("D:" + r)
                sources.append("D:" + a.v)
            elif i.t == "bool":
                bools.append(r)
                bsources.append(a.v)
        # (phi assignments are simultaneous: a loop's values may swap)
        for j in range(len(dests)):
            s.copy("phi:" + dests[j], sources[j])
        bs: list[UnionState] = []
        for j in range(len(bools)):
            q = s.clone()
            q.boolcopy(bools[j], bsources[j])
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
        for i in b.code:
            if i.op == "phi":
                continue
            throwing = i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume" or i.op == "raise" or i.op == "throw" or i.op == "check"
            if b.handler != "" and throwing:
                targets.append(b.handler)
                edges.append(s.conditional(i.a[0].v, True) if i.op == "check" else s.clone())
            self.transfer(s, i, b.label, False)
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
        elif last.op == "switch" and len(last.a) > 0 and last.a[0].v in self.words and len(last.a) == len(last.b):
            # (a class dispatcher: each case takes the classes of its tag, the default the rest)
            word = "D:" + last.a[0].v
            taken: dict[str, bool] = {}
            for j in range(1, len(last.a)):
                arm = s.clone()
                matched = self.tagged(last.a[j].v)
                arm.narrow(word, sorted(["?"] + matched))
                for m in matched:
                    taken[m] = True
                targets.append(last.b[j])
                edges.append(arm)
            rest = s.clone()
            rest.narrow(word, [m for m in self.full if m not in taken])
            targets.append(last.b[0])
            edges.append(rest)
        else:
            for target in last.b:
                targets.append(target)
                edges.append(s.clone())

    def check_phis(self, starts: dict[str, UnionState]) -> None:
        # a phi's operand from a block reads its value on the edge from it: with the facts the
        # edge carries, before the phi joins them
        for label in starts:
            b = self.fn.blocks[self.blocks[label]]
            s = starts[label].clone()
            targets: list[str] = []
            edges: list[UnionState] = []
            self.flow(b, s, targets, edges)
            for j in range(len(targets)):
                if targets[j] not in self.blocks or not edges[j].live:
                    continue
                for i in self.fn.blocks[self.blocks[targets[j]]].code:
                    if i.op != "phi":
                        break
                    if label not in i.b:
                        continue
                    a = i.a[i.b.index(label)]
                    t = self.read_class(a.v, a.t)
                    if t != "":
                        self.check(edges[j], a.v, t, targets[j], "phi operand from " + label)

    def run(self) -> None:
        self.check_phis(forward_fixpoint(self))
