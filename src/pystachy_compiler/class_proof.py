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

from src.pystachy_compiler.dataflow import flow_targets, forward_fixpoint, live_values
from src.pystachy_compiler.ir import Blk, IFn, Ins, slot_register, tmpname
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
        # (what the ops the proof sees would otherwise build again on every visit: each value's
        # key and each phi key, each type's domain and class word index, and the domains a test
        # of each class word leaves where it holds and where it fails. A domain is shared and
        # never changed once made: UnionState)
        self.dkeys: dict[str, str] = {}
        self.pkeys: dict[str, str] = {}
        self.domains: dict[str, list[str]] = {}
        self.indexes: dict[str, int] = {}
        self.matched: dict[str, list[str]] = {}
        self.unmatched: dict[str, list[str]] = {}
        named: dict[str, bool] = {}
        for c in members:
            for m in members[c]:
                named[m] = True
        self.full: list[str] = sorted(["?", "None"] + [m for m in named])
        self.none: list[str] = ["None"]
        self.unknown: list[str] = ["?"]
        self.empty: list[str] = []
        self.objects: list[str] = [m for m in self.full if m != "None"]
        # (the classes whose objects' class word each tag or descriptor literal is, in full's
        # order)
        self.wordclasses: dict[str, list[str]] = {}
        for m in self.full:
            if m != "?" and m in classes:
                if classes[m].tag > 0:
                    self.add_word(str(classes[m].tag), m)
                if classes[m].exc != "":
                    self.add_word("@x." + m, m)
        # (the values that are an object's class word, and the field addresses of one, by
        # the object they belong to)
        self.words: dict[str, str] = {}
        self.wordfields: dict[str, str] = {}
        for b in fn.blocks:
            for i in b.code:
                if i.op == "field.addr" and len(i.r) == 1 and len(i.a) == 1 and self.word_index(i.a[0].t) == i.k:
                    self.wordfields[tmpname(i.r[0])] = i.a[0].v
        for b in fn.blocks:
            for i in b.code:
                if len(i.r) != 1 or len(i.a) != 1:
                    continue
                if i.op == "mach.load" and i.a[0].t == "%ptr" and (i.t == "int" or i.t == "%ptr") and self.word_index(self.types.get(i.a[0].v, "")) == 0:
                    self.words[tmpname(i.r[0])] = i.a[0].v
                elif i.op == "mem.load" and i.a[0].v in self.wordfields:
                    self.words[tmpname(i.r[0])] = self.wordfields[i.a[0].v]
        for v in types:
            domain = self.domain(types[v])
            if len(domain) > 0:
                self.base[self.key(v)] = domain
        # (the fields of a class that field.addr addresses, by result: the key's index and the
        # object, and the field's keys, by the object and by the slot it was loaded from, each
        # with the field type's domain; owners: the values and slots that own such keys, with
        # their keys' prefix)
        self.fields: dict[str, int] = {}
        self.fieldobjs: dict[str, str] = {}
        self.objfields: dict[str, str] = {}
        self.slotfields: dict[str, str] = {}
        self.owners: dict[str, str] = {}
        self.suffixes: dict[int, str] = {}
        loads: dict[str, str] = {}
        for b in fn.blocks:
            for i in b.code:
                if i.op == "mem.load" and len(i.r) == 1 and len(i.a) == 1:
                    loads[tmpname(i.r[0])] = i.a[0].v
        for b in fn.blocks:
            for i in b.code:
                if i.op == "field.addr" and len(i.r) == 1 and len(i.a) == 1 and i.t.startswith("&") and i.a[0].v.startswith("%"):
                    domain = self.domain(i.t[1:])
                    if len(domain) == 0:
                        continue
                    r = tmpname(i.r[0])
                    obj = i.a[0].v
                    self.fields[r] = i.k
                    self.fieldobjs[r] = obj
                    self.objfields[r] = self.field_key(obj, i.k)
                    self.base[self.objfields[r]] = domain
                    slot = loads.get(obj, "")
                    if slot.startswith("%"):
                        self.slotfields[r] = self.field_key(slot, i.k)
                        self.base[self.slotfields[r]] = domain
        # (None, which an object's operand may read: no object, so of no class)
        self.base[self.key("null")] = self.none
        # (each private slot's key, "M:" and its register)
        for i in fn.slots:
            if i.k != 2 and len(self.domain(i.t)) > 0:
                self.private[slot_register(i)] = "M:" + slot_register(i)
                self.base[self.private[slot_register(i)]] = self.domain(i.t)
        for bn in range(len(fn.blocks)):
            b = fn.blocks[bn]
            self.blocks[b.label] = bn
            for i in b.code:
                # (a slot is private while every use of its address is a direct load or store)
                for j in range(len(i.a)):
                    v = i.a[j].v
                    if v in self.private and (j != 0 or (i.op != "mem.load" and i.op != "mem.store")):
                        del self.private[v]
        # (the blocks that a phi reads a value from at a class that needs a proof: check_phis)
        self.phisources: dict[str, bool] = {}
        # (the blocks that may reach a read that needs a proof: a block with one, a block whose
        # phi reads from another block so, and each block with a path to one of those. Facts
        # anywhere else prove nothing, and flow leaves out the edges into such a block)
        self.relevant: dict[str, bool] = {}
        work: list[str] = []
        preds: dict[str, list[str]] = {}
        for b in fn.blocks:
            preds[b.label] = []
            for i in b.code:
                if i.op == "phi":
                    for j in range(len(i.b)):
                        if j < len(i.a) and self.read_class(i.a[j].v, i.a[j].t) != "":
                            self.phisources[i.b[j]] = True
                            work.append(b.label)
                elif i.op != "ptr.cmp":
                    for a in i.a:
                        if self.read_class(a.v, a.t) != "":
                            work.append(b.label)
        for b in fn.blocks:
            for label in flow_targets(fn, b):
                if label in preds:
                    preds[label].append(b.label)
        while len(work) > 0:
            label = work.pop()
            if label not in self.relevant:
                self.relevant[label] = True
                for p in preds[label]:
                    work.append(p)
        self.livevalues: dict[str, dict[str, bool]] = live_values(fn, self.blocks)

    def add_word(self, word: str, m: str) -> None:
        if word not in self.wordclasses:
            self.wordclasses[word] = []
        self.wordclasses[word].append(m)

    def key(self, v: str) -> str:
        # the key of the facts of value v's object, "D:" and v, made once per value: every key of
        # a value that a state holds is one of dkeys
        if v not in self.dkeys:
            self.dkeys[v] = "D:" + v
        return self.dkeys[v]

    def tracked(self, v: str) -> bool:
        # does value v's type hold objects of classes, so that it has a domain of its own
        return v in self.dkeys and self.dkeys[v] in self.base

    def phikey(self, k: str) -> str:
        # where an edge keeps key k's facts while it assigns its phis at once
        if k not in self.pkeys:
            self.pkeys[k] = "phi:" + k
        return self.pkeys[k]

    def field_key(self, owner: str, index: int) -> str:
        # the key of field index of the object that owner, a slot or an SSA value, names (without
        # its %, so that liveness keeps it: UnionState.needed); owners keeps the prefix
        if owner not in self.owners:
            self.owners[owner] = "F:" + owner[1:] + "#"
        return self.owners[owner] + str(index)

    def field_of(self, s: UnionState, addr: str) -> str:
        # the key of the field that addr, a field.addr result, addresses: by the slot that its
        # object was loaded from while the slot still holds it (UnionState.loaded), else by the
        # object
        if self.fieldobjs[addr] in s.loaded:
            return self.slotfields[addr] if addr in self.slotfields else ""
        return self.objfields[addr]

    def forget_fields(self, s: UnionState, index: int, owner: str) -> None:
        # forget the facts of field index of every object (-1: of every field), or of owner's
        # fields alone (owner != "": one of owners)
        prefix = self.owners[owner] if owner != "" else "F:"
        if index >= 0 and index not in self.suffixes:
            self.suffixes[index] = "#" + str(index)
        suffix = self.suffixes[index] if index >= 0 else ""
        found = False
        for k in s.d:
            if k.startswith(prefix) and (index < 0 or k.endswith(suffix)):
                found = True
                break
        if found:
            for k in [k for k in s.d if k.startswith(prefix) and (index < 0 or k.endswith(suffix))]:
                s.forget(k)

    def word_index(self, t: str) -> int:
        # the index of the field that holds the class word of an object of type t (its tag's,
        # or its exception descriptor's), or -1 where it has none; of a closed union of classes,
        # where all its classes' objects hold it at one index (found once per type)
        if t not in self.indexes:
            self.indexes[t] = self.type_word_index(t)
        return self.indexes[t]

    def type_word_index(self, t: str) -> int:
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
        # classes' members together, and "?" for an object; [] for a type of no object (made
        # once per type)
        if t not in self.domains:
            self.domains[t] = self.type_domain(t)
        return self.domains[t]

    def type_domain(self, t: str) -> list[str]:
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
        proven = len(accepted) > 0
        for m in s.dom(self.key(v)):
            if m != "None" and m not in accepted:
                proven = False
                break
        if not proven:
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
        return self.wordclasses[literal] if literal in self.wordclasses else self.empty

    def matching(self, literal: str) -> list[str]:
        # the domain that a test of a class word against literal leaves where it holds: the
        # literal's classes and "?", which no test removes; unmatched keeps the domain where
        # it fails
        if literal not in self.matched:
            found = self.tagged(literal)
            self.matched[literal] = sorted(["?"] + found)
            self.unmatched[literal] = [m for m in self.full if m not in found]
        return self.matched[literal]

    def assign(self, s: UnionState, key: str, domain: list[str]) -> None:
        # the object of key (and of each key equal to it: the same object) has a class of domain
        # alone now, whatever its facts were
        rep = s.eq.get(key, key)
        for x in s.eq:
            if s.eq[x] == rep:
                s.d[x] = domain
        s.d[key] = domain

    def compare(self, s: UnionState, result: str, key: str, literal: str, equal: bool) -> None:
        # a test of a class word against literal: its value is one of literal's words where it
        # holds
        yes = self.matching(literal)
        no = self.unmatched[literal]
        s.test(result, key, yes if equal else no, no if equal else yes)

    def transfer(self, s: UnionState, i: Ins, block: str, checking: bool) -> None:
        r = tmpname(i.r[0]) if len(i.r) > 0 else ""
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
            v = tmpname(n)
            # (a loop may redefine the SSA value; a value whose key was never made has no facts)
            if v in self.dkeys:
                s.forget(self.dkeys[v])
            self.forget_bool(s, v)
            if v in s.loaded:
                del s.loaded[v]
            if v in self.owners:
                self.forget_fields(s, -1, v)
        if len(self.owners) > 0 and (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume"):
            self.forget_fields(s, -1, "")
        if r in self.words:
            s.copy(self.key(r), self.key(self.words[r]))
        elif (i.op == "mem.load" or i.op == "mach.load") and len(i.a) == 1 and i.a[0].v in self.private and r != "":
            s.copy(self.key(r), self.private[i.a[0].v])
            s.loaded[r] = i.a[0].v
        elif i.op == "mem.load" and len(i.a) == 1 and i.a[0].v in self.fields and r != "" and self.tracked(r):
            key = self.field_of(s, i.a[0].v)
            if key in self.base:
                s.copy(self.key(r), key)
        elif (i.op == "mem.store" or i.op == "mach.store") and len(i.a) == 2:
            addr = i.a[0].v
            v = i.a[1].v
            if addr in self.private:
                s.forget(self.private[addr])
                s.copy(self.private[addr], self.key(v))
                stale = False
                for o in s.loaded:
                    if s.loaded[o] == addr:
                        stale = True
                        break
                if stale:
                    for obj in [o for o in s.loaded if s.loaded[o] == addr]:
                        del s.loaded[obj]
                if addr in self.owners:
                    self.forget_fields(s, -1, addr)
            elif addr in self.fields:
                # (any object's field of that index may be the one stored)
                self.forget_fields(s, self.fields[addr], "")
                key = self.field_of(s, addr)
                if key in self.base:
                    s.copy(key, self.key(v))
            # (an allocation's class word, which its constructor stores before any read)
            owner = self.wordfields[addr] if addr in self.wordfields else addr if i.op == "mach.store" and self.word_index(self.types.get(addr, "")) == 0 else ""
            if owner != "":
                matched = self.tagged(v)
                self.assign(s, self.key(owner), matched if len(matched) > 0 else self.unknown)
        elif (i.op == "num.cmp" or i.op == "ptr.cmp" or i.op == "scalar.cmp") and (i.s == "==" or i.s == "!=" or i.s == "eq" or i.s == "ne") and len(i.a) == 2 and r != "":
            for j in range(2):
                v = i.a[j].v
                other = i.a[1 - j].v
                if v in self.words and not other.startswith("%"):
                    self.compare(s, r, self.key(v), other, i.s == "==" or i.s == "eq")
                    break
                if other == "null" and v.startswith("%") and (i.op == "ptr.cmp" or i.a[j].t == "%ptr") and self.tracked(v) and len(s.dom(self.key(v))) > 0:
                    # (a test of an object against None, also of its pointer as a machine word)
                    equal = i.s == "==" or i.s == "eq"
                    s.test(r, self.key(v), self.none if equal else self.objects, self.objects if equal else self.none)
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
            elif self.tracked(r):
                yes.copy(self.key(r), self.key(i.a[1].v))
                no.copy(self.key(r), self.key(i.a[2].v))
            merged = union_join(yes, no)
            s.d = merged.d
            s.eq = merged.eq
            s.bt = merged.bt
            s.bf = merged.bf
            s.truth = merged.truth
            s.live = merged.live
        elif i.op == "cast" and len(i.a) == 1 and self.tracked(r):
            # (the object it reads, at another type: lowering erases it. An object cast's is one
            # of its union's classes', which the union proof holds its box to; a member cast's
            # class is what tests of the object's class show where it is read)
            s.copy(self.key(r), self.key(i.a[0].v))
            if i.s == "object":
                s.narrow(self.key(r), self.base[self.key(r)])

    def edge(self, state: UnionState, source: str, target: str) -> UnionState:
        # the facts at target's start where control comes from source with facts state, which
        # are the edge's own (flow gives each edge facts of its own), so they change in place
        code = self.fn.blocks[self.blocks[target]].code
        if len(code) > 0 and code[0].op == "phi":
            self.assign_phis(state, source, code)
        state.retain(self.livevalues[target])
        return state

    def assign_phis(self, s: UnionState, source: str, code: list[Ins]) -> None:
        dests: list[str] = []
        sources: list[str] = []
        bools: list[str] = []
        bsources: list[str] = []
        for i in code:
            if i.op != "phi":
                break
            r = tmpname(i.r[0])
            if source not in i.b:
                if r in self.dkeys:
                    s.forget(self.dkeys[r])
                self.forget_bool(s, r)
                continue
            a = i.a[i.b.index(source)]
            if self.tracked(r) or i.t == "%ptr":
                # (also an object as a machine word, which an object cast reads)
                dests.append(self.key(r))
                sources.append(self.key(a.v))
            elif i.t == "bool":
                bools.append(r)
                bsources.append(a.v)
        # (phi assignments are simultaneous: a loop's values may swap)
        for j in range(len(dests)):
            s.copy(self.phikey(dests[j]), sources[j])
        bs: list[UnionState] = []
        for j in range(len(bools)):
            q = s.clone()
            q.boolcopy(bools[j], bsources[j])
            for facts in [q.bt[bools[j]], q.bf[bools[j]]]:
                for k in dests:
                    if k in facts:
                        del facts[k]
                    if self.phikey(k) in facts:
                        facts[k] = facts[self.phikey(k)]
                        del facts[self.phikey(k)]
            bs.append(q)
        for k in dests:
            s.copy(k, self.phikey(k))
        for k in dests:
            s.forget(self.phikey(k))
        for j in range(len(bools)):
            k = bools[j]
            s.truth[k] = bs[j].truth[k]
            s.bt[k] = bs[j].bt[k]
            s.bf[k] = bs[j].bf[k]

    def flow(self, b: Blk, s: UnionState, targets: list[str], edges: list[UnionState]) -> None:
        # one block for the worklist (dataflow.forward_fixpoint): s, the facts at the block's
        # start, becomes its facts at its end, and each edge that leaves it for a block that may
        # reach a read (relevant) joins targets and edges with facts of its own: the last, s
        for i in b.code:
            if i.op == "phi":
                continue
            throwing = i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume" or i.op == "raise" or i.op == "throw" or i.op == "check"
            if b.handler != "" and throwing and b.handler in self.relevant:
                targets.append(b.handler)
                edges.append(s.conditional(i.a[0].v, True) if i.op == "check" else s.clone())
            self.transfer(s, i, b.label, False)
        last = b.code[-1]
        if last.op == "cbr":
            self.branch(s, last.a[0].v, last.b[0], True, last.b[1], targets, edges)
        elif last.op == "check":
            key = last.x if last.x != "" else last.s
            self.branch(s, last.a[0].v, last.b[0], False, self.fn.cold[key] if key in self.fn.cold else "", targets, edges)
        elif last.op == "switch" and len(last.a) > 0 and last.a[0].v in self.words and len(last.a) == len(last.b):
            # (a class dispatcher: each case takes the classes of its tag, the default the rest)
            word = self.key(last.a[0].v)
            taken: dict[str, bool] = {}
            for j in range(1, len(last.a)):
                for m in self.tagged(last.a[j].v):
                    taken[m] = True
                if last.b[j] in self.relevant:
                    arm = s.clone()
                    arm.narrow(word, self.matching(last.a[j].v))
                    targets.append(last.b[j])
                    edges.append(arm)
            if last.b[0] in self.relevant:
                s.narrow(word, [m for m in self.full if m not in taken])
                targets.append(last.b[0])
                edges.append(s)
        else:
            n = 0
            for label in last.b:
                if label in self.relevant:
                    n += 1
            for label in last.b:
                if label in self.relevant:
                    n -= 1
                    targets.append(label)
                    edges.append(s if n == 0 else s.clone())

    def branch(self, s: UnionState, v: str, first: str, holds: bool, second: str, targets: list[str], edges: list[UnionState]) -> None:
        # the edges of a two-way branch on boolean v that flow keeps: to first where v is holds,
        # and to second ("" for none) where it is not
        if first in self.relevant:
            targets.append(first)
            if second in self.relevant:
                edges.append(s.conditional(v, holds))
            else:
                s.cond(v, holds)
                edges.append(s)
        if second in self.relevant:
            targets.append(second)
            s.cond(v, not holds)
            edges.append(s)

    def check_phis(self, starts: dict[str, UnionState]) -> None:
        # a phi's operand from a block reads its value on the edge from it: with the facts the
        # edge carries, before the phi joins them (phisources: the blocks with such an operand)
        for label in starts:
            if label not in self.phisources:
                continue
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
