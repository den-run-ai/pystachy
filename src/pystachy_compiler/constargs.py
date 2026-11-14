"""Tests of arguments and fields that the whole program gives one constant.

Run after ordinary compilation, before effects and the function passes: the program is
typed and its diagnostics are decided, so no source is inferred again. Where every call that
can run gives a parameter one constant (None, a bool, an int, a module constant's address),
the function's tests of it are decided, and so are those of the locals that follow from it.
A field that every store that can run gives the value its object starts with is that value
wherever it is read. The branch not taken becomes one unreachable op, and the functions that
only such code called are left without a caller, for LLVM to discard.
"""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, ClassInfo, Data, IFn, Ins, Val, slot_register, tmpname
from src.pystachy_compiler.utils import lt

# A value is "" while no code that can run has given one, a constant's spelling once all of
# it gives that one, and VARIES from the second: it only ever moves that way.
VARIES = "!"
# how many times the whole program is read: each reading may find more fields constant
ROUNDS = 8
# A function of more ops than this is read as it is written. Reading one closely follows each
# of its locals through each of its blocks, and the few functions this large (an interpreter's
# loop, say) are where that costs most and decides least: LLVM folds what stays in a function
# once its parameters are constants, and what this pass adds, the code that a decided test
# leaves without a caller, is found in the functions that call such code, which are small.
CLOSE_OPS = 4096
# the ops whose result is a constant where their operands are (Fold.result)
PASSES_ON: dict[str, bool] = {"phi": True, "select": True, "slot.pack": True, "slot.unpack": True, "ptr.cmp": True, "num.cmp": True, "scalar.cmp": True, "scalar.bin": True}
SIGNED: dict[str, str] = {"eq": "==", "ne": "!=", "slt": "<", "sle": "<=", "sgt": ">", "sge": ">="}
# Shared by every function whose tuples' items are not known; nothing changes it in place.
# The pass keeps what it reads of the program in a few long lists, each function's part
# between its "first" and the next function's, and a Fold keeps its states in one: the
# compiler's own program has a million ops, and a list or dict for each value or block of it
# would be millions of objects for the collector to mark.
NOITEMS: list[str] = []


def constant(v: str) -> bool:
    # an operand that is one value wherever it is written: None's null, a bool, an int
    # literal that fits a machine word with room to spare, or a module constant's address.
    # (A value or a local, which most operands are, is told apart first: a str's startswith()
    # counts code points, and costs more than every other step of reading an op.)
    if v.startswith("%"):
        return False
    if v == "null" or v == "true" or v == "false" or v.startswith("@"):
        return True
    d = v[1:] if v.startswith("-") else v
    return d.isdigit() and len(d) <= 18


def meet(a: str, b: str) -> str:
    if a == "":
        return b
    if b == "" or a == b:
        return a
    return VARIES


def integer(v: str) -> bool:
    d = v[1:] if v.startswith("-") else v
    return d.isdigit() and len(d) <= 18


def compare(p: str, a: str, b: str, t: str) -> str:
    # a p b of two constants of type t (bool or int), or VARIES where this does not decide it
    if t == "bool":
        if (a != "true" and a != "false") or (b != "true" and b != "false"):
            return VARIES
        if p == "==":
            return "true" if a == b else "false"
        if p == "!=":
            return "true" if a != b else "false"
        return VARIES
    if not integer(a) or not integer(b):
        return VARIES
    x = int(a)
    y = int(b)
    r = False
    if p == "==":
        r = x == y
    elif p == "!=":
        r = x != y
    elif p == "<":
        r = x < y
    elif p == "<=":
        r = x <= y
    elif p == ">":
        r = x > y
    elif p == ">=":
        r = x >= y
    else:
        return VARIES
    return "true" if r else "false"


class Facts:
    # What one reading of the program found, which the next one starts from: the fields that
    # hold one constant, and for each function the constant every return that can run gives
    # (retv), or the items of the fixed tuples they make (rett).
    def __init__(self, index: dict[str, int], fconst: dict[str, str]):
        self.index = index
        self.fconst = fconst
        self.retv: list[str] = []
        self.rett: list[list[str]] = []
        self.seen: list[bool] = []
        for _ in index:
            self.retv.append(VARIES)
            self.rett.append(NOITEMS)
            self.seen.append(False)

    def returned(self, g: int, v: str, items: list[str]) -> None:
        if not self.seen[g]:
            self.seen[g] = True
            self.retv[g] = v
            self.rett[g] = [x if x != "" else VARIES for x in items]
            return
        self.retv[g] = meet(self.retv[g], v)
        if len(items) != len(self.rett[g]):
            self.rett[g] = NOITEMS
            return
        self.rett[g] = [meet(self.rett[g][x], items[x] if items[x] != "" else VARIES) for x in range(len(items))]

    def knows(self, g: int) -> bool:
        if self.retv[g] != VARIES:
            return True
        for x in self.rett[g]:
            if x != VARIES:
                return True
        return False

    def same(self, other: Facts) -> bool:
        if len(self.fconst) != len(other.fconst):
            return False
        for g in range(len(self.retv)):
            if self.retv[g] != other.retv[g] or len(self.rett[g]) != len(other.rett[g]):
                return False
            for x in range(len(self.rett[g])):
                if self.rett[g][x] != other.rett[g][x]:
                    return False
        return True


class Fold:
    # One function, given what its parameters are: the blocks that can run, the edges taken
    # between them, and the values that are constants there. Its values are SSA. A local's
    # slot is followed along the control flow where it is private (only loaded and stored):
    # it starts as lowering zeroes it, a store gives it its operand, and a block starts with
    # what the edges taken to it agree on. A block that a try statement covers gives its
    # landing block what the slots hold anywhere in it.
    def __init__(self, fn: IFn, params: list[str], first: int, faddr: dict[str, str], facts: Facts):
        # (params: every function's parameters in one list, fn's from first)
        self.fn = fn
        self.faddr = faddr  # its field addresses -> the field's name
        self.facts = facts
        self.fconst = facts.fconst  # the fields that hold one constant, program-wide
        # a fixed tuple made here or returned by a call -> what its items are; a tuple never
        # changes once it is made, and its stores follow its allocation in the same block
        self.tup: dict[str, list[str]] = {}
        self.tupat: dict[str, int] = {}
        self.ok = True  # False: a shape this does not follow, so the function stays as it is
        self.folds = 0  # the branches it decides
        self.nb = len(fn.blocks)
        self.at: dict[str, int] = {}
        self.live: list[bool] = [False] * self.nb
        self.edges: dict[int, bool] = {}
        self.val: dict[str, str] = {}
        self.sidx: dict[str, int] = {}  # a private slot's register -> its place in a state
        # the blocks that read a value: uhead gives the last one listed, unext the one before
        self.uhead: dict[str, int] = {}
        self.ublk: list[int] = []
        self.unext: list[int] = []
        # the ops this reads, each block's from its bfirst: those that may define a constant,
        # the stores into the slots it follows, and every op that names a block
        self.bfirst: list[int] = []
        self.bops: list[Ins] = []
        # the blocks to read (again), taken in the order they were built, which follows the
        # control flow but for a loop's way back: a block is then read once most of what
        # reaches it is known. redo: a block before the one being read is waiting
        self.queued: list[bool] = [False] * self.nb
        self.reading = 0
        self.redo = False
        self.given: list[str] = []  # the parameters it was read with
        tracked: dict[str, str] = {}
        for j in range(self.nb):
            l = fn.blocks[j].label
            if l != "":
                if l in self.at:
                    self.ok = False
                self.at[l] = j
            if len(fn.blocks[j].code) == 0:
                self.ok = False
        for s in fn.slots:
            if s.k == 0:
                tracked[slot_register(s)] = lt(s.t)
        for b in fn.blocks if len(tracked) > 0 else fn.blocks[:0]:
            for i in b.code:
                for k in range(len(i.a)):
                    if i.a[k].v in tracked and not (k == 0 and (i.op == "mem.load" or i.op == "mem.store")):
                        del tracked[i.a[k].v]  # (its address goes elsewhere: anything may store there)
        for x in range(len(fn.ps)):
            p = params[first + x]
            self.given.append(p)
            self.val[f"%a{fn.ps[x]}"] = p if p != "" else VARIES
        # Of those slots, the ones that some store may give a constant: the others only
        # ever vary once assigned, and following them through every edge of a large
        # function is most of this pass's time. A value may be a constant where it is one
        # as written, a constant parameter, or what an op that passes constants on makes
        # of such a value; the two sets grow together until neither does.
        maybe: dict[str, bool] = {}
        seeded: dict[str, bool] = {}
        grew = True
        while grew:
            grew = False
            for b in fn.blocks:
                for i in b.code:
                    op = i.op
                    if op == "mem.store":
                        if i.a[0].v in tracked and i.a[0].v not in seeded and self.may(i.a[1].v, maybe):
                            seeded[i.a[0].v] = True
                            grew = True
                        continue
                    if len(i.r) == 0:
                        continue
                    name = tmpname(i.r[len(i.r) - 1])
                    if name in maybe:
                        continue
                    can = False
                    if op == "mem.load":
                        can = i.a[0].v in seeded or (i.a[0].v in faddr and faddr[i.a[0].v] in self.fconst)
                    elif op == "call":
                        can = i.s in facts.index and facts.knows(facts.index[i.s])
                    elif op == "tuple.load":
                        can = len(i.r) == 2 and i.a[0].v in maybe
                    elif op == "alloc.fixed":
                        can = i.t.startswith("tuple[")
                    elif op in PASSES_ON and (op != "scalar.bin" or i.t == "bool"):
                        for a in i.a:
                            if self.may(a.v, maybe):
                                can = True
                                break
                    if can:
                        maybe[name] = True
                        grew = True
        self.zero: list[str] = []
        for register in tracked:
            if register not in seeded:
                continue
            self.sidx[register] = len(self.zero)
            t = tracked[register]
            self.zero.append("null" if t == "ptr" else "false" if t == "i1" else "0" if t == "i64" else VARIES)
        self.maybe: dict[str, bool] = maybe
        for j in range(self.nb):
            self.bfirst.append(len(self.bops))
            for i in fn.blocks[j].code:
                keep = len(i.b) > 0 and i.op != "phi"
                if not keep and len(i.r) > 0:
                    keep = tmpname(i.r[len(i.r) - 1]) in maybe
                if not keep and i.op == "mem.store":
                    keep = i.a[0].v in self.sidx
                if not keep and i.op == "tuple.store":
                    keep = len(i.a) == 2 and i.a[0].v in maybe
                if not keep:
                    continue
                self.bops.append(i)
                for a in i.a:
                    if a.v in maybe:
                        h = self.uhead[a.v] if a.v in self.uhead else -1
                        if h < 0 or self.ublk[h] != j:
                            self.uhead[a.v] = len(self.ublk)
                            self.ublk.append(j)
                            self.unext.append(h)
        self.bfirst.append(len(self.bops))
        # each block's state where it starts, once it can run: block j's from j * ns; st and
        # anywhere are the state of the block being read, and what its slots hold anywhere in it
        self.ns = len(self.zero)
        self.sin: list[str] = [""] * (self.nb * self.ns)
        self.st: list[str] = [""] * self.ns
        self.anywhere: list[str] = [""] * self.ns

    def may(self, v: str, maybe: dict[str, bool]) -> bool:
        # can operand v be a constant: one as written, a constant parameter, or a value in maybe
        if v in maybe:
            return True
        if v in self.val:
            return self.val[v] != VARIES
        return constant(v)

    def value(self, a: Val) -> str:
        v = a.v
        if v in self.val:
            return self.val[v]
        if v in self.maybe:
            return ""  # (not read yet)
        return v if constant(v) else VARIES

    def flow(self, j: int, label: str, st: list[str]) -> None:
        # block j goes to label with the slots as st has them
        if label not in self.at:
            self.ok = False
            return
        k = self.at[label]
        key = j * self.nb + k
        changed = key not in self.edges or not self.live[k]
        self.edges[key] = True
        self.live[k] = True
        base = k * self.ns
        for x in range(self.ns):
            new = st[x]
            old = self.sin[base + x]
            if new != old and new != "" and old != VARIES:
                self.sin[base + x] = new if old == "" else VARIES  # (meet)
                changed = True
        if changed and not self.queued[k]:
            self.queued[k] = True
            if k <= self.reading:
                self.redo = True

    def result(self, i: Ins, j: int) -> str:
        # what the one value that i defines is (but a load of a private slot: block)
        op = i.op
        if op == "phi":
            out = ""
            for k in range(len(i.b)):
                if i.b[k] in self.at and (self.at[i.b[k]] * self.nb + j) in self.edges:
                    out = meet(out, self.value(i.a[k]))
            return out
        if op == "ptr.cmp" and (i.s == "==" or i.s == "!=") and len(i.a) == 2:
            a = self.value(i.a[0])
            b = self.value(i.a[1])
            if a == VARIES or b == VARIES:
                return VARIES
            if a == "" or b == "":
                return ""
            # one spelling is one object. Two spellings decide nothing here: the test that is
            # kept may be what proves a later read of the object safe
            if a != b:
                return VARIES
            return "true" if i.s == "==" else "false"
        if op == "scalar.bin" and i.t == "bool" and len(i.a) == 2:
            a = self.value(i.a[0])
            b = self.value(i.a[1])
            if i.s == "and" and (a == "false" or b == "false"):
                return "false"
            if i.s == "or" and (a == "true" or b == "true"):
                return "true"
            if a == VARIES or b == VARIES:
                return VARIES
            if a == "" or b == "":
                return ""
            if (a != "true" and a != "false") or (b != "true" and b != "false"):
                return VARIES
            if i.s == "xor":
                return "true" if a != b else "false"
            if i.s == "and":
                return "true" if a == "true" and b == "true" else "false"
            if i.s == "or":
                return "true" if a == "true" or b == "true" else "false"
            return VARIES
        if (op == "num.cmp" or op == "scalar.cmp") and len(i.a) == 2 and i.a[0].t == i.a[1].t and (i.a[0].t == "int" or i.a[0].t == "bool"):
            p = i.s
            if op == "scalar.cmp":
                if p not in SIGNED:
                    return VARIES
                p = SIGNED[p]
            a = self.value(i.a[0])
            b = self.value(i.a[1])
            if a == VARIES or b == VARIES:
                return VARIES
            if a == "" or b == "":
                return ""
            return compare(p, a, b, i.a[0].t)
        if (op == "slot.pack" or op == "slot.unpack") and len(i.a) == 1:
            return self.value(i.a[0])  # (the same value, in a container's or a native's form)
        if op == "select" and len(i.a) == 3:
            c = self.value(i.a[0])
            if c == "":
                return ""
            if c == "true":
                return self.value(i.a[1])
            if c == "false":
                return self.value(i.a[2])
            return meet(self.value(i.a[1]), self.value(i.a[2]))
        return VARIES

    def define(self, name: str, new: str) -> None:
        old = self.val[name] if name in self.val else ""
        if old != "":
            new = meet(old, new)
        if new == old:
            return
        self.val[name] = new
        h = self.uhead[name] if name in self.uhead else -1
        while h >= 0:
            k = self.ublk[h]
            if self.live[k] and not self.queued[k]:
                self.queued[k] = True
                if k <= self.reading:
                    self.redo = True
            h = self.unext[h]

    def block(self, j: int) -> None:
        b = self.fn.blocks[j]
        st = self.st
        anywhere = self.anywhere
        covered = b.handler != ""
        for x in range(self.ns):
            st[x] = self.sin[j * self.ns + x]
            anywhere[x] = st[x]
        for y in range(self.bfirst[j], self.bfirst[j + 1]):
            i = self.bops[y]
            op = i.op
            if (op == "mem.store" or op == "mem.load") and i.a[0].v in self.sidx:
                k = self.sidx[i.a[0].v]
                if op == "mem.load":
                    self.define(tmpname(i.r[0]), st[k])
                    continue
                st[k] = self.value(i.a[1])
                if covered:
                    anywhere[k] = meet(anywhere[k], st[k])
                continue
            if op == "mem.load" and i.a[0].v in self.faddr and self.faddr[i.a[0].v] in self.fconst:
                self.define(tmpname(i.r[0]), self.fconst[self.faddr[i.a[0].v]])
                continue
            if op == "call" and len(i.r) == 1 and i.s in self.facts.index:
                g = self.facts.index[i.s]
                name = tmpname(i.r[0])
                if len(self.facts.rett[g]) > 0:
                    self.tup[name] = self.facts.rett[g]
                    self.tupat[name] = -1
                self.define(name, self.facts.retv[g])
                continue
            if op == "alloc.fixed" and i.t.startswith("tuple[") and len(i.r) == 1:
                self.tup[tmpname(i.r[0])] = []
                self.tupat[tmpname(i.r[0])] = j
            elif op == "tuple.store" and len(i.a) == 2 and i.a[0].v in self.tup:
                if self.tupat[i.a[0].v] != j or i.k < 0:
                    self.tupat[i.a[0].v] = -2  # (a store this does not follow: its items are not known)
                    self.tup[i.a[0].v] = []
                else:
                    items = self.tup[i.a[0].v]
                    while len(items) <= i.k:
                        items.append(VARIES)
                    items[i.k] = self.value(i.a[1])
            elif op == "tuple.load" and len(i.r) == 2 and len(i.a) == 1 and i.a[0].v in self.tup and i.k >= 0 and i.k < len(self.tup[i.a[0].v]):
                self.define(tmpname(i.r[0]), VARIES)
                self.define(tmpname(i.r[1]), self.tup[i.a[0].v][i.k])
                continue
            if len(i.r) == 1:
                self.define(tmpname(i.r[0]), self.result(i, j))
            elif len(i.r) > 1:
                for n in i.r:
                    self.define(tmpname(n), VARIES)
            if op == "phi" or len(i.b) == 0:
                continue
            if op == "cbr" and len(i.b) == 2:
                c = self.value(i.a[0])
                if c == "true":
                    self.flow(j, i.b[0], st)
                elif c == "false":
                    self.flow(j, i.b[1], st)
                elif c != "":
                    self.flow(j, i.b[0], st)
                    self.flow(j, i.b[1], st)
                continue
            if op == "switch":
                c = self.value(i.a[0])
                if c == "":
                    continue
                if c != VARIES and integer(c):
                    self.flow(j, self.case(i, c), st)
                    continue
            if op == "check":
                key = i.x if i.x != "" else i.s
                if key in self.fn.cold:
                    self.flow(j, self.fn.cold[key], st)
                else:
                    self.ok = False
            for l in i.b:
                self.flow(j, l, st)
        if covered:
            self.flow(j, b.handler, anywhere)  # (where what it raises goes)

    def case_index(self, i: Ins, c: str) -> int:
        # which label a switch on the int constant c goes to: its case's, or the default's (0)
        for k in range(1, len(i.a)):
            if i.a[k].v == c and k < len(i.b):
                return k
        return 0

    def case(self, i: Ins, c: str) -> str:
        return i.b[self.case_index(i, c)]

    def run(self) -> None:
        if not self.ok:
            return
        self.live[0] = True
        for x in range(self.ns):
            self.sin[x] = self.zero[x]
        self.queued[0] = True
        self.redo = True
        while self.ok and self.redo:
            self.redo = False
            for j in range(self.nb):
                if self.queued[j]:
                    self.queued[j] = False
                    self.reading = j
                    self.block(j)
        for j in range(self.nb if self.ok else 0):
            if not self.live[j]:
                continue
            code = self.fn.blocks[j].code
            t = code[len(code) - 1]
            if t.op == "cbr" or t.op == "switch":
                c = self.value(t.a[0])
                if c == "":
                    self.ok = False  # (a test of no value at all: nothing here can say where it goes)
                elif t.op == "cbr" and (c == "true" or c == "false"):
                    self.folds += 1
                elif t.op == "switch" and c != VARIES and integer(c):
                    self.folds += 1

    def returns(self, facts: Facts, g: int) -> None:
        # what the returns that can run give, into facts' summary of function g
        for j in range(self.nb):
            if not self.live[j]:
                continue
            code = self.fn.blocks[j].code
            t = code[len(code) - 1]
            if t.op != "ret" or len(t.a) != 1:
                continue
            facts.returned(g, self.argument(t.a[0]), self.tup[t.a[0].v] if t.a[0].v in self.tup and self.tupat[t.a[0].v] >= 0 else [])

    def argument(self, a: Val) -> str:
        # what a call that can run passes: a constant, or VARIES
        v = self.value(a)
        return v if v != "" else VARIES

    def stop(self, line: int, trap: str) -> list[Ins]:
        # what a block that cannot run becomes: nothing, or with trap (a str constant) the
        # sys.exit(trap) that says it ran after all
        u = Ins("unreachable", "", "")
        u.line = line
        if trap == "":
            return [u]
        x = Ins("rt", "None", "exit_msg")
        x.line = line
        x.a = [Val(trap, "str")]
        return [x, u]

    def apply(self, trap: str) -> int:
        # Rewrite the function: a decided branch is a br, a block that cannot run is one
        # unreachable op (its label stays, for the loops, try statements and checks that name
        # it), and a phi keeps the predecessors that still branch to it. With trap, the test
        # stays, and what it was decided not to reach is a block that stops the program.
        # How many ops changed.
        fn = self.fn
        n = 0
        stops = ""  # trap: the label of the block that the edges not taken go to
        for j in range(self.nb):
            b = fn.blocks[j]
            code = b.code
            t = code[len(code) - 1]
            if not self.live[j]:
                if len(code) == 1 and t.op == "unreachable" and b.handler == "":
                    continue
                b.code = self.stop(t.line, trap)
                b.handler = ""
                n += 1
                continue
            keep = -1  # the one label of its terminator that it goes to
            if t.op == "cbr":
                c = self.value(t.a[0])
                if c == "true":
                    keep = 0
                elif c == "false":
                    keep = 1
            elif t.op == "switch":
                c = self.value(t.a[0])
                if c != VARIES and integer(c):
                    keep = self.case_index(t, c)
            if keep >= 0 and trap == "":
                br = Ins("br", "", "")
                br.line = t.line
                br.b = [t.b[keep]]
                code[len(code) - 1] = br
                n += 1
            elif keep >= 0:
                if stops == "":
                    fn.n += 1
                    stops = f"L{fn.n}"
                t.b = [t.b[x] if x == keep else stops for x in range(len(t.b))]
                n += 1
            for i in code:
                if i.op != "phi":
                    break
                vals: list[Val] = []
                labels: list[str] = []
                for k in range(len(i.b)):
                    if i.b[k] in self.at and (self.at[i.b[k]] * self.nb + j) in self.edges:
                        vals.append(i.a[k])
                        labels.append(i.b[k])
                if len(labels) != len(i.b):
                    i.a = vals
                    i.b = labels
                    n += 1
        if stops != "":
            last = Blk(stops)
            last.code = self.stop(0, trap)
            fn.blocks.append(last)
        # a loop whose blocks are not all left is no loop the loop passes know
        loops = [lp for lp in fn.loops if self.whole([lp.head, lp.body, lp.step, lp.exit] + lp.tests)]
        if len(loops) != len(fn.loops):
            fn.loops = loops
        return n

    def whole(self, labels: list[str]) -> bool:
        for l in labels:
            if l in self.at and not self.live[self.at[l]]:
                return False
        return True


def taken_symbols(taken: dict[str, bool], index: dict[str, int], consts: list[Data], texts: list[str]) -> None:
    # The functions that something other than a call op names, besides the ops' own values
    # (Fields): a module constant (a closure's code, a Callable's adapter) or text the backend
    # wrote. Anything may call those, with any arguments.
    for d in consts:
        if d.text.startswith("@") and d.text in index:
            taken[d.text] = True
        for r in d.refs:
            if r in index:
                taken[r] = True
        for it in d.items:
            if it.v.startswith("@") and it.v in index:
                taken[it.v] = True
    for text in texts:
        if "@" not in text:
            continue
        for word in text.replace("(", " ").replace(")", " ").replace(",", " ").replace("\n", " ").split(" "):
            if word.startswith("@") and word in index:
                taken[word] = True


class Fields:
    # What the program's code does with objects' fields, calls and results, read once. A field
    # is named by its name alone, whatever its class: a derived class's layout repeats its
    # bases' fields, and two classes that share a name only make this less exact. Its objects
    # start zeroed (pys_alloc), so a field holds that zero or what a store gave it: a mem.store
    # through a field.addr, which is how compiled code assigns one (setattr() and copy.copy()
    # too). A field leaves this (VARIES) where something else may write it: an exception's (the
    # runtime sets some), a hidden one (a hierarchy's class tag), one whose address goes
    # anywhere but a load or a store, one of an object that machine ops address, that the
    # runtime returns or that a function outside the program takes.
    def __init__(self, fns: list[IFn], index: dict[str, int], classes: dict[str, ClassInfo]):
        nf = len(fns)
        self.zero: dict[str, str] = {}
        self.taken: dict[str, bool] = {}  # the functions that an op names as a value, not a callee
        self.addr: list[dict[str, str]] = []  # each function's field addresses -> the field's name
        # each function's part of these lists is from its first to the next function's:
        self.lfirst: list[int] = []  # the fields it reads,
        self.lname: list[str] = []
        self.sfirst: list[int] = []  # its stores of fields: the block, the field and the value,
        self.sblk: list[int] = []
        self.sname: list[str] = []
        self.sval: list[Val] = []
        self.cfirst: list[int] = []  # and its calls of the program's functions: the block, the
        self.cblk: list[int] = []  # op and the function
        self.cins: list[Ins] = []
        self.cfn: list[int] = []
        # what each function returns as it is written: a constant where every return names
        # that one, VARIES otherwise, "" where it has no return of a value
        self.plain: list[str] = []
        self.small: list[bool] = []  # it has no more than CLOSE_OPS ops
        # a module function or method that only its symbol can reach: no generator, export or
        # function of another language (whether a value names it is taken's to say)
        self.direct: list[bool] = []
        for c in classes:
            ci = classes[c]
            for name in ci.fields:
                t = lt(ci.ftypes[name]) if name in ci.ftypes else ""
                z = "null" if t == "ptr" else "false" if t == "i1" else "0" if t == "i64" else VARIES
                if ci.exc != "" or name.startswith(" "):
                    z = VARIES
                self.zero[name] = meet(self.zero[name], z) if name in self.zero else z
        read: dict[str, int] = {}  # a field -> the last function whose reads list it
        for j in range(nf):
            fn = fns[j]
            f = fn.f
            fa: dict[str, str] = {}
            for b in fn.blocks:
                for i in b.code:
                    if i.op == "field.addr" and len(i.r) == 1 and len(i.a) == 1 and i.a[0].t in classes and i.k < len(classes[i.a[0].t].fields):
                        fa[tmpname(i.r[0])] = classes[i.a[0].t].fields[i.k]
            fielded = len(fa) > 0
            self.addr.append(fa)
            self.lfirst.append(len(self.lname))
            self.sfirst.append(len(self.sname))
            self.cfirst.append(len(self.cins))
            machine = False  # some machine op addresses a value or a parameter
            plain = ""
            ops = 0
            for x in range(len(fn.blocks)):
                ops += len(fn.blocks[x].code)
                for i in fn.blocks[x].code:
                    op = i.op
                    for k in range(len(i.a)):
                        v = i.a[k].v
                        if v in index:
                            self.taken[v] = True  # (a function as a value)
                        elif fielded and v in fa:
                            name = fa[v]
                            if k == 0 and op == "mem.load":
                                if name not in read or read[name] != j:
                                    read[name] = j
                                    self.lname.append(name)
                            elif k == 0 and op == "mem.store":
                                self.sblk.append(x)
                                self.sname.append(name)
                                self.sval.append(i.a[1])
                            else:
                                self.zero[name] = VARIES
                    if op == "call":
                        if i.s in index:
                            self.cblk.append(x)
                            self.cins.append(i)
                            self.cfn.append(index[i.s])
                        else:
                            for a in i.a:
                                if a.t in classes:
                                    self.raw(classes[a.t], True)
                        continue
                    if i.s in index:
                        self.taken[i.s] = True
                    if op == "mach.store" or op == "mach.addr":
                        machine = machine or i.a[0].v.startswith("%t") or i.a[0].v.startswith("%a")
                    elif op == "ret" and len(i.a) == 1:
                        plain = meet(plain, i.a[0].v if constant(i.a[0].v) else VARIES)
                    elif op == "rt" and i.t in classes:
                        self.raw(classes[i.t], True)  # (an object the runtime made or found)
            self.plain.append(plain if not fn.coro and not f.gen else "")
            self.small.append(ops <= CLOSE_OPS)
            self.direct.append((f.ll.startswith("@f.") or f.ll.startswith("@m.")) and not fn.coro and not f.gen and not f.export and not f.pyexport and not f.extern)
            if machine:
                self.machine(fn, classes)
        self.lfirst.append(len(self.lname))
        self.sfirst.append(len(self.sname))
        self.cfirst.append(len(self.cins))
        # callers before callees (a reverse postorder of the calls): the order in which a
        # reading takes the functions, so that it reads one once its callers have said what
        # they pass, and again only where calls go round
        state: list[int] = [0] * nf
        post: list[int] = []
        stack: list[int] = []
        at: list[int] = []
        for root in range(nf):
            if state[root] != 0:
                continue
            state[root] = 1
            stack.append(root)
            at.append(self.cfirst[root])
            while len(stack) > 0:
                j = stack[len(stack) - 1]
                k = at[len(at) - 1]
                if k < self.cfirst[j + 1]:
                    at[len(at) - 1] = k + 1
                    g = self.cfn[k]
                    if state[g] == 0:
                        state[g] = 1
                        stack.append(g)
                        at.append(self.cfirst[g])
                else:
                    stack.pop()
                    at.pop()
                    post.append(j)
        self.order: list[int] = [post[len(post) - 1 - x] for x in range(len(post))]
        self.pos: list[int] = [0] * nf
        for x in range(len(self.order)):
            self.pos[self.order[x]] = x

    def raw(self, ci: ClassInfo, every: bool) -> None:
        # something other than a field's stores may write an object of class ci: its first
        # field alone (a hierarchy's class tag, a machine store at the object), or every one
        for name in ci.fields if every else ci.fields[:1]:
            self.zero[name] = VARIES

    def machine(self, fn: IFn, classes: dict[str, ClassInfo]) -> None:
        # fn's machine ops that address an object: a mach.store at it writes its first word,
        # and a mach.addr of it may reach any of them
        bases: dict[str, bool] = {}
        for b in fn.blocks:
            for i in b.code:
                if i.op == "mach.store" or i.op == "mach.addr":
                    v = i.a[0].v
                    bases[v] = i.op == "mach.addr" or (v in bases and bases[v])
        f = fn.f
        for p in fn.ps:
            if f"%a{p}" in bases and p < len(f.ptypes) and f.ptypes[p] in classes:
                self.raw(classes[f.ptypes[p]], bases[f"%a{p}"])
        for b in fn.blocks:
            for i in b.code:
                if len(i.r) == 1 and i.t in classes and tmpname(i.r[0]) in bases:
                    self.raw(classes[i.t], bases[tmpname(i.r[0])])

    def constants(self, given: dict[str, str]) -> dict[str, str]:
        # the fields that hold one constant: their zero, where the stores (given) gave no other
        out: dict[str, str] = {}
        for name in self.zero:
            v = meet(self.zero[name], given[name]) if name in given else self.zero[name]
            if v != VARIES and v != "":
                out[name] = v
        return out


class Round:
    # One reading of the whole program, given what the one before found (facts): the
    # functions and blocks that can run, what each parameter is, what the stores that can run
    # give each field and what the returns that can run give. Fewer constants only ever leave
    # more of the program able to run, so a reading made with what an earlier one found is
    # right as well.
    def __init__(self, fns: list[IFn], fields: Fields, facts: Facts, before: Round | None):
        nf = len(fns)
        self.fns = fns
        self.fields = fields
        self.facts = facts
        self.before: Round | None = before  # the reading before this one, whose close readings may serve again
        self.folds: list[Fold | None] = []
        self.given: dict[str, str] = {}
        self.found = Facts(facts.index, {})
        # every function's parameters in one list, each function's from its pfirst
        self.pfirst: list[int] = []
        self.params: list[str] = []
        self.closed: list[bool] = []  # the functions whose every caller is a call op that this reads
        self.reached: list[bool] = [False] * nf
        self.queued: list[bool] = [False] * nf
        self.mode: list[int] = [0] * nf  # how it was last read: 1 as it is written, 2 closely
        self.plain: list[int] = []  # the functions to read, of either kind
        # those of them to read closely, a heap by their place in the order (callers first)
        self.heap: list[int] = []
        self.heaped: list[bool] = [False] * nf
        # 1: what facts say of the fields it reads and the functions it calls has it read closely
        self.told: list[int] = [-1] * nf
        for j in range(nf):
            fn = fns[j]
            f = fn.f
            ll = f.ll
            own = fields.direct[j] and ll not in fields.taken
            self.closed.append(own)
            self.pfirst.append(len(self.params))
            for _ in fn.ps:
                self.params.append("" if own else VARIES)
            self.folds.append(None)
            if not own:
                self.reached[j] = True
                self.queued[j] = True
                self.plain.append(j)
        self.pfirst.append(len(self.params))
        # The functions that are read as they are written go first, all of them: what they
        # pass is then known before any function is read closely, which costs its size each
        # time a caller lowers one of its parameters afterwards. Of those to read closely, the
        # one that comes first in the order is next.
        while True:
            while len(self.plain) > 0:
                j = self.plain.pop()
                if self.closely(j):
                    if not self.heaped[j]:
                        self.heaped[j] = True
                        self.push(j)
                else:
                    self.queued[j] = False
                    self.read(j, False)
            if len(self.heap) == 0:
                break
            j = self.pop()
            self.heaped[j] = False
            if self.queued[j]:
                self.queued[j] = False
                self.read(j, self.closely(j))
        for j in range(nf):
            if not self.reached[j]:
                continue
            fo = self.folds[j]
            if fo is not None:
                fo.returns(self.found, j)
            elif fields.plain[j] != "":
                self.found.returned(j, fields.plain[j], NOITEMS)
            for x in range(fields.sfirst[j], fields.sfirst[j + 1]):
                if fo is not None and not fo.live[fields.sblk[x]]:
                    continue
                a = fields.sval[x]
                v = fo.argument(a) if fo is not None else a.v if constant(a.v) else VARIES
                name = fields.sname[x]
                self.given[name] = meet(self.given[name], v) if name in self.given else v
        self.found.fconst = fields.constants(self.given)

    def closely(self, j: int) -> bool:
        # is function j read with what its values are (Fold), not as it is written: where a
        # parameter, a field it reads or the result of a function it calls is a constant
        fn = self.fns[j]
        if fn.coro or fn.f.gen or not self.fields.small[j]:
            return False
        for x in range(self.pfirst[j], self.pfirst[j + 1]):
            if self.params[x] != VARIES and self.params[x] != "":
                return True
        if self.told[j] < 0:
            fields = self.fields
            self.told[j] = 0
            for x in range(fields.lfirst[j], fields.lfirst[j + 1]):
                if fields.lname[x] in self.facts.fconst:
                    self.told[j] = 1
                    break
            for x in range(fields.cfirst[j], fields.cfirst[j + 1] if self.told[j] == 0 else fields.cfirst[j]):
                if self.facts.knows(fields.cfn[x]):
                    self.told[j] = 1
                    break
        return self.told[j] == 1

    def kept(self, j: int) -> Fold | None:
        # the reading before this one's close reading of function j, where it was made with
        # what j is read with now: the same parameters, and the same facts of the fields it
        # reads and the functions it calls. A close reading depends on nothing else.
        if self.before is None:
            return None
        fo = self.before.folds[j]
        if fo is None:
            return None
        first = self.pfirst[j]
        for x in range(len(fo.given)):
            if fo.given[x] != self.params[first + x]:
                return None
        fields = self.fields
        now = self.facts
        was = self.before.facts
        for x in range(fields.lfirst[j], fields.lfirst[j + 1]):
            name = fields.lname[x]
            if (name in now.fconst) != (name in was.fconst) or (name in now.fconst and now.fconst[name] != was.fconst[name]):
                return None
        for x in range(fields.cfirst[j], fields.cfirst[j + 1]):
            g = fields.cfn[x]
            if now.retv[g] != was.retv[g] or len(now.rett[g]) != len(was.rett[g]):
                return None
            for y in range(len(now.rett[g])):
                if now.rett[g][y] != was.rett[g][y]:
                    return None
        return fo

    def push(self, j: int) -> None:
        heap = self.heap
        pos = self.fields.pos
        heap.append(j)
        k = len(heap) - 1
        while k > 0:
            up = (k - 1) // 2
            if pos[heap[up]] <= pos[heap[k]]:
                break
            moved = heap[up]
            heap[up] = heap[k]
            heap[k] = moved
            k = up

    def pop(self) -> int:
        heap = self.heap
        pos = self.fields.pos
        top = heap[0]
        last = heap.pop()
        if len(heap) > 0:
            heap[0] = last
            k = 0
            while True:
                least = k
                if 2 * k + 1 < len(heap) and pos[heap[2 * k + 1]] < pos[heap[least]]:
                    least = 2 * k + 1
                if 2 * k + 2 < len(heap) and pos[heap[2 * k + 2]] < pos[heap[least]]:
                    least = 2 * k + 2
                if least == k:
                    break
                moved = heap[least]
                heap[least] = heap[k]
                heap[k] = moved
                k = least
        return top

    def read(self, j: int, closely: bool) -> None:
        # Read function j with what its parameters are now, and give its callees what its
        # calls that can run pass. A callee that was read as it is written is not read
        # again: what it passes does not depend on its parameters, and once read, a function
        # that was not read closely never is (its parameters only lose their constants).
        fields = self.fields
        fo: Fold | None = None
        if closely:
            fo = self.kept(j)
            if fo is None:
                fo = Fold(self.fns[j], self.params, self.pfirst[j], fields.addr[j], self.facts)
                fo.run()
            if not fo.ok:
                fo = None
        self.folds[j] = fo
        self.mode[j] = 1 if fo is None else 2
        for x in range(fields.cfirst[j], fields.cfirst[j + 1]):
            if fo is not None and not fo.live[fields.cblk[x]]:
                continue  # (a call that cannot run passes nothing)
            i = fields.cins[x]
            g = fields.cfn[x]
            changed = not self.reached[g]
            self.reached[g] = True
            if self.closed[g]:
                first = self.pfirst[g]
                for k in range(self.pfirst[g + 1] - first):
                    old = self.params[first + k]
                    if old == VARIES:
                        continue
                    v = VARIES
                    if k < len(i.a):
                        if fo is not None:
                            v = fo.argument(i.a[k])
                        elif constant(i.a[k].v):
                            v = i.a[k].v
                    new = meet(old, v)
                    if new != old:
                        self.params[first + k] = new
                        changed = True
            if changed and not self.queued[g] and self.mode[g] != 1:
                self.queued[g] = True
                self.plain.append(g)


def fold_constant_arguments(fns: list[IFn], consts: list[Data], texts: list[str], classes: dict[str, ClassInfo], trap: str) -> int:
    # Decide, over the whole program, which parameters, fields and results hold one constant
    # wherever code that can run reads them, and fold the functions that test them. With trap
    # (a str constant), nothing is folded: the code that was decided not to run stops the
    # program with that message, which tests a decision instead of trusting it. How many ops
    # changed.
    index: dict[str, int] = {}
    for j in range(len(fns)):
        index[fns[j].f.ll] = j
    fields = Fields(fns, index, classes)
    taken_symbols(fields.taken, index, consts, texts)
    # the first reading trusts what the program says as it is written: a field that no store,
    # anywhere, gives another value, and a function whose every return names one constant
    given: dict[str, str] = {}
    for x in range(len(fields.sname)):
        a = fields.sval[x]
        v = a.v if constant(a.v) else VARIES
        name = fields.sname[x]
        given[name] = meet(given[name], v) if name in given else v
    facts = Facts(index, fields.constants(given))
    for j in range(len(fns)):
        if fields.plain[j] != "":
            facts.returned(j, fields.plain[j], NOITEMS)
    rd = Round(fns, fields, facts, None)
    for _ in range(ROUNDS - 1):
        if rd.found.same(facts):
            break  # (a reading finds no less than it was given)
        facts = rd.found
        rd.before = None  # (the reading before the last is no longer needed)
        rd = Round(fns, fields, facts, rd)
    n = 0
    for fo in rd.folds:
        if fo is not None and fo.folds > 0:
            n += fo.apply(trap)
    return n
