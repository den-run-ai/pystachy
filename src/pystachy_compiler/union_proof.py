"""Finite tag and payload proofs for closed unions in typed IR.

Domains come from definitions and storage declarations, never narrowed operand metadata.
The worklist joins tag possibilities and loses equalities/conditional implications until
stable. It keeps one state per block, not a product of whole-function execution paths.
"""
from __future__ import annotations
from src.pystachy_compiler.dataflow import forward_fixpoint, live_values
from src.pystachy_compiler.ir import Blk, Data, IFn, Ins, Val, slot_register
from src.pystachy_compiler.specs import BIG
from src.pystachy_compiler.union_state import UnionState, intersect_tags, union_join
from src.pystachy_compiler.utils import gelem, is_gen, is_opt, is_union, targs, umembers


def proof_number(v: str, start: int, limit: int) -> int:
    """Read exactly a canonical nonnegative ASCII integer without slicing or overflow."""
    if start >= len(v) or (v[start] == "0" and start + 1 != len(v)):
        return -1
    n = 0
    if len(v) - start <= 6:
        # Dense metadata IDs are bounded to 262144. Any six ASCII digits fit
        # safely in an integer, so check their range once instead of dividing
        # for an overflow check at every digit. Longer literals keep that check.
        for j in range(start, len(v)):
            digit = ord(v[j]) - 48
            if digit < 0 or digit > 9:
                return -1
            n = n * 10 + digit
        return n if n <= limit else -1
    for j in range(start, len(v)):
        digit = ord(v[j]) - 48
        if digit < 0 or digit > 9 or n > (limit - digit) // 10:
            return -1
        n = n * 10 + digit
    return n


def proof_slot(v: str, definitions: list[Ins | None]) -> int:
    """Match the declaration's complete slot name, separately from temporary names."""
    if not v.startswith("%"):
        return -1
    dot = v.rfind(".")
    if dot < 1:
        return -1
    n = proof_number(v, dot + 1, len(definitions) - 1)
    if n < 0:
        return -1
    i = definitions[n]
    if i is None or i.op != "slot":
        return -1
    name = i.s if i.s != "" else "h"
    if dot != len(name) + 1:
        return -1
    for j in range(len(name)):
        if v[j + 1] != name[j]:
            return -1
    return n


def proof_origin(v: str, fn: IFn, definitions: list[Ins | None], origins: list[int]) -> int:
    if v.startswith("%a"):
        n = proof_number(v, 2, len(fn.f.ptypes) - 1)
        return n if n >= 0 and is_union(fn.f.ptypes[n]) else -1
    if v.startswith("%t"):
        n = proof_number(v, 2, len(definitions) - 1)
        if n >= 0:
            i = definitions[n]
            if i is not None and i.op == "mem.load":
                return origins[n]
    return -1


def simple_union_proof(fn: IFn, utags: dict[str, int], at: dict[str, int] | None = None, successors: list[list[str]] | None = None, types: dict[str, list[str]] | None = None) -> bool:
    """Certify immutable parameter narrowing without allocating dataflow states.

    This is a sufficient proof, never a rejection rule. Unrecognized sources, mutable
    storage, nullable values, raw transport and nonlocal control-flow proofs use the
    general solver. No fact comes from an operand's narrowed type annotation.
    """
    domains: dict[str, list[str]] = {} if types is None else types
    found = False
    for t in fn.f.ptypes:
        if is_union(t):
            ts = domains[t] if t in domains else umembers(t)
            for member in ts:
                if member == "" or member == "None" or is_opt(member) or is_union(member):
                    return False
            # This cache is local to this proof/verification call; it is never reused
            # to skip shape validation of another function or a changed instruction.
            domains[t] = ts
            found = True
    if not found:
        return False
    size = len(fn.slots) + len(fn.blocks) + 1
    for b in fn.blocks:
        size += len(b.code)
    # IFn.n also numbers labels and slots. Bound both absolute space and sparsity
    # before allocating: malformed or unusually sparse functions use the solver.
    if fn.n < 0 or fn.n > 262144 or fn.n > size * 8:
        return False
    definitions: list[Ins | None] = [None] * (fn.n + 1)
    origins: list[int] = [-1] * (fn.n + 1)
    for i in fn.slots:
        n = i.r[0]
        if n < 0 or n > fn.n or definitions[n] is not None:
            return False
        definitions[n] = i
        # -2 is an uninitialized union slot; -1 means unusable or unknown.
        if is_union(i.t):
            origins[n] = -2
    predecessors: list[int] = [-1] * len(fn.blocks)
    blocks = {fn.blocks[n].label: n for n in range(len(fn.blocks))} if at is None else at
    # Collect every definition and inspect all slot writes/escapes before deriving
    # any load alias. A late overwrite or escape must invalidate earlier loads too.
    for bn in range(len(fn.blocks)):
        b = fn.blocks[bn]
        if b.handler != "" or len(b.code) == 0:
            return False
        for i in b.code:
            if i.op == "union.raw" or (i.op == "rt" and (i.s == "ubox" or i.s == "ubox_opt")):
                return False
            for n in i.r:
                if n < 0 or n > fn.n or definitions[n] is not None:
                    return False
                definitions[n] = i
            for j in range(len(i.a)):
                n = proof_slot(i.a[j].v, definitions)
                if n >= 0 and origins[n] != -1:
                    if j != 0 or (i.op != "mem.load" and i.op != "mem.store"):
                        origins[n] = -1
                    elif i.op == "mem.load" and b.label == "entry" and origins[n] == -2:
                        origins[n] = -1
                    elif i.op == "mem.store":
                        source = i.a[1].v
                        p = proof_number(source, 2, len(fn.f.ptypes) - 1) if source.startswith("%a") else -1
                        if b.label == "entry" and origins[n] == -2 and p >= 0 and is_union(fn.f.ptypes[p]):
                            origins[n] = p
                        else:
                            origins[n] = -1
        targets = list(b.code[-1].b) if successors is None else successors[bn]
        if successors is None:
            last = b.code[-1]
            if last.op == "check":
                ck = last.x if last.x != "" else last.s
                if ck in fn.cold:
                    targets.append(fn.cold[ck])
        for target in targets:
            if target == "entry" or target not in blocks:
                return False
            n = blocks[target]
            predecessors[n] = bn if predecessors[n] == -1 else -2
    guards: list[int] = [-1] * len(fn.blocks)
    for bn in range(len(fn.blocks)):
        b = fn.blocks[bn]
        branch = b.code[-1]
        tag = -1
        origin = -1
        for i in b.code:
            for a in i.a:
                n = proof_number(a.v, 2, fn.n) if a.v.startswith("%t") else -1
                producer = definitions[n] if n >= 0 else None
                if producer is not None and producer.op == "union.payload":
                    # Definitions are complete before checking any consumer, even
                    # a use textually before its producer or in an earlier block.
                    if n == producer.r[0]:
                        return False
                    if i.op == "phi" or i.op == "select" or i.op == "slot.pack" or i.op == "mem.store" or i.op == "mach.store" or i.op == "rt":
                        return False
                    t = i.t if i.op == "slot.unpack" else a.t
                    if t != producer.s:
                        return False
            if i.op == "mem.load" and is_union(i.t):
                n = proof_slot(i.a[0].v, definitions)
                if n >= 0 and origins[n] >= 0:
                    origins[i.r[0]] = origins[n]
            if i.op == "union.tag" or (i.op == "mach.load" and i.t == "int"):
                origin = proof_origin(i.a[0].v, fn, definitions, origins)
                if origin < 0:
                    return False
                tag = i.r[0]
            if (i.op == "num.cmp" or i.op == "scalar.cmp") and (i.s == "==" or i.s == "!=" or i.s == "eq" or i.s == "ne") and i.a[0].t == "int" and i.a[1].t == "int" and branch.op == "cbr" and branch.a[0].v.startswith("%t") and proof_number(branch.a[0].v, 2, fn.n) == i.r[0]:
                x = i.a[0].v
                y = i.a[1].v
                if y.startswith("%t") and proof_number(y, 2, fn.n) == tag:
                    x = y
                if x.startswith("%t") and proof_number(x, 2, fn.n) == tag and origin >= 0:
                    guards[bn] = i.r[0]
                    origins[i.r[0]] = origin
    for bn in range(len(fn.blocks)):
        for i in fn.blocks[bn].code:
            if i.op != "union.payload":
                continue
            origin = proof_origin(i.a[0].v, fn, definitions, origins)
            if origin < 0:
                return False
            domain = domains[fn.f.ptypes[origin]]
            possible = domain
            proven = possible[0] if len(possible) == 1 else ""
            node = bn
            # Bound this local search independently of function size. Longer proofs
            # use the general worklist rather than multiplying backward walks.
            steps = 0
            while proven == "" and len(possible) > 1 and predecessors[node] >= 0 and steps < 8:
                parent = predecessors[node]
                guard = guards[parent]
                if guard >= 0 and origins[guard] == origin:
                    cmp = definitions[guard]
                    if cmp is None:
                        return False
                    literal = cmp.a[1].v if cmp.a[0].v.startswith("%t") else cmp.a[0].v
                    value = proof_number(literal, 0, 9223372036854775807)
                    member = ""
                    for t in domain:
                        if value >= 0 and t in utags and utags[t] == value:
                            member = t
                    if member != "":
                        branch = fn.blocks[parent].code[-1]
                        yes = (fn.blocks[node].label == branch.b[0]) == (cmp.s == "==" or cmp.s == "eq")
                        if len(possible) == 2 and possible[0] != possible[1] and member in possible:
                            proven = member if yes else possible[1] if possible[0] == member else possible[0]
                        else:
                            possible = [t for t in possible if (t == member) == yes]
                            if len(possible) == 1:
                                proven = possible[0]
                node = parent
                steps += 1
            if proven == "" or proven != i.s:
                return False
    return True


class UnionProof:
    def __init__(self, fn: IFn, utags: dict[str, int], writes: dict[str, bool] | None = None, globals: dict[str, str] | None = None, raises: dict[str, bool] | None = None, declarations: list[Val] | None = None, consts: dict[str, Data] | None = None):
        self.fn = fn
        self.writes: dict[str, bool] = {} if writes is None else writes
        self.raises: dict[str, bool] = {} if raises is None else raises
        self.tags: dict[str, str] = {}
        self.full: list[str] = ["?", "None"]
        for t in utags:
            self.tags[str(utags[t])] = t
            if t not in self.full:
                self.full.append(t)
        self.full.sort()
        self.base: dict[str, list[str]] = {}
        # Finalized domains are immutable, as in UnionState. Many declarations
        # have the same type; share its domain only within this proof invocation.
        self.domains: dict[str, list[str]] = {}
        self.native: dict[str, str] = {}
        self.memtypes: dict[str, str] = {}
        self.declaredtypes: dict[str, str] = {}  # (declared(), by value)
        self.defs: dict[str, Ins] = {}
        self.blocks: dict[str, int] = {}
        self.raw: dict[str, bool] = {}
        self.rawslots: dict[str, bool] = {}
        self.bitsneeded: dict[str, bool] = {}
        self.bitsslots: dict[str, bool] = {}
        self.tagvals: dict[str, bool] = {}
        self.tagslots: dict[str, bool] = {}
        self.private: dict[str, bool] = {}
        self.roots: dict[str, str] = {}
        self.addresses: dict[str, bool] = {}
        self.bad: list[str] = []
        self.badblocks: list[str] = []
        self.visits = 0
        wanted: dict[str, bool] = {}
        # Storage facts can be read only at addresses named by this function.
        # Include every block, even unreachable ones and later phi operands.
        # Keep named globals separate so unused names need no prefixed strings.
        references: dict[str, bool] = {}
        named: dict[str, bool] = {}
        for b in fn.blocks:
            for i in b.code:
                for a in i.a:
                    references[a.v] = True
                    if a.v.startswith("@g."):
                        named[a.v[3:]] = True
        if globals is not None:
            for v in globals:
                if v in named:
                    self.typebase("MU:@g." + v, globals[v])
                    self.memtypes["@g." + v] = globals[v]
                else:
                    self.type_domain(globals[v])
        if declarations is not None:
            # Hidden defaults and class storage have the same declared native types
            # as named globals. A call can change their values, not their layouts.
            for declaration in declarations:
                if declaration.v in references:
                    self.typebase("MU:" + declaration.v, declaration.t)
                    self.memtypes[declaration.v] = declaration.t
                else:
                    self.type_domain(declaration.t)
        for n in range(len(fn.f.ptypes)):
            t = fn.f.ptypes[n]
            v = "%a" + str(n)
            self.native[v] = t
            if t.startswith("*"):
                self.memtypes[v] = t[1:]
            self.typebase(("MU:" if t.startswith("*") else "U:") + v, t[1:] if t.startswith("*") else t)
        for i in fn.slots:
            if i.k == 2:
                # (a stack tuple's register is a tuple value, not storage that is loaded; its
                # type still joins the fallback universe, as an unreferenced declaration's does)
                self.type_domain(i.t)
                continue
            # (a local's "is assigned" flag shares its number: named by number alone, its bool
            # would replace the local's storage type)
            v = slot_register(i)
            self.private[v] = True
            self.roots[v] = v
            self.memtypes[v] = i.t
            self.typebase("MU:" + v, i.t)
        for bn in range(len(fn.blocks)):
            b = fn.blocks[bn]
            self.blocks[b.label] = bn
            for i in b.code:
                for number in i.r:
                    v = "%t" + str(number)
                    self.defs[v] = i
                    self.native[v] = i.t
                if i.op == "ovf":
                    self.native["%t" + str(i.r[1])] = "int"
                    self.native["%t" + str(i.r[2])] = "bool"
                if (i.op == "tuple.load" or i.op == "dyn.payload"):
                    # Their element/member contracts are checked by their own typed
                    # operations; closed-union proof tracking starts at union reads.
                    self.native["%t" + str(i.r[-1])] = i.s
                if i.op == "alloc.fixed" or (i.op == "rt" and (i.s == "alloc" or i.s == "alloc_atomic")):
                    v = "%t" + str(i.r[0])
                    self.roots[v] = v
                for a in i.a:
                    if consts is not None and a.v in consts:
                        # A constant tuple (Gen.tuple_const) is immutable storage of its own
                        # fixed tuple type (its Data's text), as an alloc.fixed's tuple is once
                        # its slots are stored; an indexed read may see it as a machine pointer.
                        self.roots[a.v] = a.v
                        self.native[a.v] = consts[a.v].text
                if len(i.r) == 1:
                    self.typebase(("MU:" if i.t.startswith("*") else "U:") + "%t" + str(i.r[0]), i.t[1:] if i.t.startswith("*") else i.t)
                    if i.t.startswith("*") and i.op != "rt":
                        self.memtypes["%t" + str(i.r[0])] = i.t[1:]
                for j in range(len(i.a)):
                    v = i.a[j].v
                    if v in self.private and (j != 0 or (i.op != "mem.load" and i.op != "mem.store")):
                        del self.private[v]
                if (i.op == "union.tag" or i.op == "union.payload" or i.op == "union.raw"):
                    wanted["U:" + i.a[0].v] = True
                    if i.op == "union.tag":
                        self.tagvals["%t" + str(i.r[0])] = True
                    else:
                        self.raw["%t" + str(i.r[1])] = True
                        self.bitsneeded["%t" + str(i.r[1])] = True
                        self.addresses["%t" + str(i.r[0])] = True
                if i.op == "ptr.cmp":
                    for a in i.a:
                        wanted["U:" + a.v] = True
                if i.op == "rt" and (i.s == "ubox" or i.s == "ubox_opt"):
                    wanted["U:%t" + str(i.r[0])] = True
                    if i.a[0].v.startswith("%"):
                        self.tagvals[i.a[0].v] = True
                    if i.s == "ubox" and i.a[1].v.startswith("%"):
                        self.bitsneeded[i.a[1].v] = True
        for b in fn.blocks:
            for i in b.code:
                if (i.op == "rt" and len(i.r) == 1) or i.op == "list.load":
                    self.native["%t" + str(i.r[0])] = self.runtime_type(i, i.t)
                if i.op == "mach.addr" and len(i.r) == 1 and len(i.a) == 2:
                    # An item slot of a tuple whose items are all of one union type (a fixed
                    # tuple's, or a tuple[U, ...]'s past its length) holds a box of that union:
                    # container typing is its own contract, as for a list's items (list.get), so
                    # an item read from the slot has its members. A length read is no union read.
                    # (Also of a tuple that may be None, read where it is not: a field's.)
                    owner = self.declared(i.a[0].v)
                    owner = owner[4:-1] if is_opt(owner) else owner
                    items = targs(owner) if owner.startswith("tuple[") or owner.startswith("vtuple[") else []
                    if len(items) > 0 and all(x == items[0] for x in items) and is_union(items[0][4:-1] if is_opt(items[0]) else items[0]) and self.item_slot(i, owner.startswith("vtuple["), len(items)):
                        self.typebase("MU:%t" + str(i.r[0]), items[0])
        # Backward relevance for boxed values and forward/backward transport closure for
        # tags and bits. Literals never become tainted: the same integer spelling in an
        # unrelated loop index does not make that index a payload.
        for k in self.base:
            if len(self.base[k]) > 1:
                wanted[k] = True
        changed = True
        while changed:
            before = len(wanted) + len(self.raw) + len(self.rawslots) + len(self.bitsneeded) + len(self.bitsslots) + len(self.tagvals) + len(self.tagslots) + len(self.roots)
            for b in fn.blocks:
                for i in b.code:
                    r = "%t" + str(i.r[0]) if len(i.r) > 0 else ""
                    if (i.op == "mach.addr" or i.op == "field.addr") and i.a[0].v in self.roots:
                        self.roots[r] = self.roots[i.a[0].v]
                    if "U:" + r in wanted:
                        if (i.op == "phi" or i.op == "slot.pack" or i.op == "slot.unpack"):
                            for a in i.a:
                                wanted["U:" + a.v] = True
                        if i.op == "select":
                            for a in i.a[1:]:
                                wanted["U:" + a.v] = True
                        if (i.op == "mem.load" or i.op == "mach.load"):
                            wanted["MU:" + i.a[0].v] = True
                    if (i.op == "mem.store" or i.op == "mach.store") and "MU:" + i.a[0].v in wanted:
                        wanted["U:" + i.a[1].v] = True
                    if i.op == "mach.load" and i.t == "int" and "U:" + i.a[0].v in wanted and not self.length_read(i.a[0].v):
                        self.tagvals[r] = True
                    self.transport_closure(i, self.raw, self.rawslots, True)
                    if i.op != "slot.pack":
                        self.transport_closure(i, self.bitsneeded, self.bitsslots, False)
                    self.transport_closure(i, self.tagvals, self.tagslots, False)
            for v in self.raw:
                self.bitsneeded[v] = True
            for v in self.rawslots:
                self.bitsslots[v] = True
            changed = before != len(wanted) + len(self.raw) + len(self.rawslots) + len(self.bitsneeded) + len(self.bitsslots) + len(self.tagvals) + len(self.tagslots) + len(self.roots)
        for k in list(self.base):
            if k not in wanted:
                del self.base[k]
        for v in self.bitsslots:
            if v not in self.memtypes and v in self.roots:
                owner = self.native.get(self.roots[v], "")
                if owner.startswith("tuple["):
                    elements = targs(owner)
                    if len(elements) > 0 and all(t == elements[0] for t in elements):
                        # A homogeneous fixed tuple keeps one native element contract
                        # after its element load is lowered to an indexed machine load.
                        self.memtypes[v] = elements[0]
            if v in self.memtypes:
                self.base["MB:" + v] = [self.memtypes[v]]
        # Facts matter only while their value or storage address can still be read.
        # Retaining completed selectors at every later join multiplies unrelated work.
        self.livevalues: dict[str, dict[str, bool]] = live_values(fn, self.blocks)

    def transport_closure(self, i: Ins, vals: dict[str, bool], slots: dict[str, bool], bits: bool) -> None:
        r = "%t" + str(i.r[0]) if len(i.r) > 0 else ""
        if (i.op == "phi" or i.op == "select" or i.op == "slot.pack") and (bits or (i.t == "int" or i.t == "%slot")):
            aa = i.a[1:] if i.op == "select" else i.a
            for a in aa:
                if a.v in vals:
                    vals[r] = True
            if r in vals and not bits:
                for a in aa:
                    if a.v.startswith("%"):
                        vals[a.v] = True
        if (i.op == "mem.load" or i.op == "mach.load"):
            if r in vals and not bits:
                slots[i.a[0].v] = True
            if i.a[0].v in slots:
                vals[r] = True
        if (i.op == "mem.store" or i.op == "mach.store"):
            if i.a[1].v in vals:
                slots[i.a[0].v] = True
            if not bits and i.a[0].v in slots and i.a[1].v.startswith("%"):
                vals[i.a[1].v] = True

    def runtime_type(self, i: Ins, t: str) -> str:
        if len(i.a) == 0:
            return t
        receiver = self.native.get(i.a[0].v, "")
        if t == "S":
            return receiver if receiver != "" else t
        if receiver.startswith("list[") and (i.op == "list.load" or (i.op == "rt" and i.s == "list.get")):
            # The packed result still carries the receiver definition's semantic
            # element, independently of narrowed operand or result annotations.
            return targs(receiver)[0]
        if receiver.startswith("dict[") and (t == "*K" or t == "*V"):
            return targs(receiver)[0 if t == "*K" else 1]
        if (receiver.startswith("list[") or receiver.startswith("set[") or receiver.startswith("frozenset[")) and t == "*T":
            return targs(receiver)[0]
        return t

    def typebase(self, k: str, t: str) -> None:
        ts = self.type_domain(t)
        if len(ts) > 0:
            self.base[k] = ts

    def type_domain(self, t: str) -> list[str]:
        # Unreferenced declarations still contribute every member to the fallback
        # universe. Omitting their types could turn unknown facts into a proof.
        if t in self.domains:
            return self.domains[t]
        u = t[4:-1] if is_opt(t) else t
        ts: list[str] = []
        if is_union(u):
            ts = umembers(u)
        elif t != "" and not t.startswith("%") and not t.startswith("*") and t != "#":
            ts = [u]
        if len(ts) > 0:
            if is_opt(t) and "None" not in ts:
                ts.append("None")
            ts.sort()
            for v in ts:
                if v not in self.full:
                    self.full.append(v)
            self.full.sort()
        self.domains[t] = ts
        return ts

    def item_slot(self, i: Ins, vtuple: bool, n: int) -> bool:
        # Does mach.addr i address an item's slot, as gen_seq_item's addresses do: words, at
        # an index of a fixed tuple's n items, or past a runtime-length tuple's length word
        # (index + 1)? Not its length word, nor bytes. Whether the item index is below the
        # length is the loop's test (Loop.idx), as a list.load's index is its caller's.
        if i.s != "int":
            return False
        k = i.a[1].v
        if not vtuple:
            return not k.startswith("-") and (k.startswith("%") or proof_number(k, 0, n - 1) >= 0)
        d = self.defs[k] if k in self.defs else None
        if d is None or d.op != "scalar.bin" or d.s != "add" or d.t != "int" or len(d.a) != 2:
            return False
        x = d.a[0].v if d.a[1].v == "1" else d.a[1].v if d.a[0].v == "1" else ""
        return x.startswith("%") or proof_number(x, 0, 1 << 62) >= 0

    def length_read(self, v: str) -> bool:
        # Is an integer machine load from v the length word of a tuple[T, ...] that may be None
        # (a field's, read after its test): no union's tag, though None and the tuple make two
        # members of v's domain. The compiler checks None before such a read where it must.
        t = self.declared(v)
        return is_opt(t) and t[4:-1].startswith("vtuple[")

    def declared(self, v: str) -> str:
        # The type that value v's definition declares: a load's is that of its storage
        # (memtypes: a parameter's, a local's, a global's or a field's declaration), and a
        # transport's (phi, select, slot.pack, slot.unpack) is the one its operands all declare
        # (declared_from), never the op's own annotation, which a narrower type could spell;
        # "" where that cannot be established. Else its definition's.
        if v not in self.declaredtypes:
            t = self.declared_from(v, {})
            self.declaredtypes[v] = t if t != "?" else ""
        return self.declaredtypes[v]

    def declared_from(self, v: str, seen: dict[str, bool]) -> str:
        # (declared) seen: the transports on the way to v. "?" for one of them again (a loop's
        # back edge, which brings what the other edges declare) and for None (null), which has
        # no items: they constrain nothing
        d = self.defs[v] if v in self.defs else None
        if v == "null":
            return "?"
        if d is not None and (d.op == "mem.load" or d.op == "mach.load"):
            return self.memtypes[d.a[0].v] if len(d.a) > 0 and d.a[0].v in self.memtypes else ""
        if d is not None and (d.op == "phi" or d.op == "select" or d.op == "slot.pack" or d.op == "slot.unpack"):
            if v in seen:
                return "?"
            seen[v] = True
            t = "?"
            for a in d.a[1:] if d.op == "select" else d.a[:1] if d.op != "phi" else d.a:
                x = self.declared_from(a.v, seen)
                if x == "" or (x != "?" and t != "?" and x != t):
                    return ""
                t = x if x != "?" else t
            return t
        return self.native.get(v, "")

    def box(self, s: UnionState, v: str) -> str:
        k = "U:" + v
        if v == "null":
            s.set(k, ["None"])
        return k

    def bits(self, s: UnionState, a: Val) -> str:
        k = "B:" + a.v
        if self.integer(a.v):
            # A join may have forgotten an earlier use of this literal. Its kind
            # is intrinsic, unlike a transported register's possible payloads.
            s.set(k, ["int"])
            return k
        opaque = False
        if a.v in self.defs:
            opaque = (self.defs[a.v].op == "phi" or self.defs[a.v].op == "select" or self.defs[a.v].op == "mem.load" or self.defs[a.v].op == "mach.load" or self.defs[a.v].op == "union.payload" or self.defs[a.v].op == "union.raw" or self.defs[a.v].op == "slot.pack")
        if k not in s.d and (a.v not in self.bitsneeded or not opaque):
            t = self.native[a.v] if a.v in self.native else "int" if self.integer(a.v) else "?"
            s.set(k, [t])
        return k

    def integer(self, v: str) -> bool:
        return (v[1:] if v.startswith("-") else v).isdigit()

    def tag(self, s: UnionState, v: str) -> str:
        k = "T:" + v
        if self.integer(v):
            s.set(k, [self.tags[v] if v in self.tags else "?"])
        return k

    def killmem(self, s: UnionState, address: str = "") -> None:
        written = self.roots.get(address, "")
        for k in list(s.d):
            if (k.startswith("MU:") or k.startswith("MB:") or k.startswith("MT:")) and k[3:] not in self.private:
                root = self.roots.get(k[3:], "")
                if written == "" or root == "" or root == written:
                    s.forget(k)

    def compare(self, s: UnionState, r: str, key: str, allowed: list[str], equal: bool) -> None:
        domain = s.dom(key)
        yes = intersect_tags(domain, allowed)
        no = [t for t in domain if t not in allowed]
        bt: dict[str, list[str]] = {}
        bf: dict[str, list[str]] = {}
        if yes != domain:
            bt[key] = yes
        if no != domain:
            bf[key] = no
        rep = s.eq.get(key, key)
        for k in s.eq:
            if s.eq[k] == rep:
                yt = intersect_tags(s.dom(k), yes)
                nt = intersect_tags(s.dom(k), no)
                if yt != s.dom(k):
                    bt[k] = yt
                if nt != s.dom(k):
                    bf[k] = nt
        s.truth[r] = (2 if len(yes if equal else no) > 0 else 0) | (1 if len(no if equal else yes) > 0 else 0)
        s.bt[r] = bt if equal else bf
        s.bf[r] = bf if equal else bt

    def error(self, b: str, message: str) -> None:
        self.badblocks.append(b)
        self.bad.append(message)

    def checkbits(self, s: UnionState, v: str, t: str, b: str, op: str) -> None:
        if v in self.raw and s.dom("B:" + v) != [t]:
            self.error(b, op + " interprets payload " + v + " as " + t + " without its tag proof")

    def transfer(self, s: UnionState, i: Ins, b: str, checking: bool) -> None:
        op = i.op
        a = i.a
        r = "%t" + str(i.r[0]) if len(i.r) > 0 else ""
        for n in i.r:
            v = "%t" + str(n)
            if self.native[v] == "bool":
                if v in s.truth:
                    del s.truth[v]
                if v in s.bt:
                    del s.bt[v]
                if v in s.bf:
                    del s.bf[v]
        if (op != "phi" and op != "select" and op != "mem.load" and op != "mach.load" and op != "union.payload" and op != "union.raw" and op != "slot.pack"):
            for n in i.r:
                v = "%t" + str(n)
                if v in self.bitsneeded:
                    s.set("B:" + v, [self.native[v]])
        if checking:
            for operand in a:
                if operand.v in self.addresses:
                    self.error(b, "union payload address " + operand.v + " escapes its extraction")
        if (op == "union.tag" or op == "union.payload" or op == "union.raw"):
            u = self.box(s, a[0].v)
            d = s.dom(u)
            if checking and "None" in d:
                self.error(b, op + " needs a nonnull proof for " + a[0].v)
            if op == "union.tag":
                s.copy("T:" + r, u)
            else:
                s.copy("B:%t" + str(i.r[1]), u)
                if checking and op == "union.payload" and d != [i.s]:
                    self.error(b, "union.payload needs tag " + i.s + " for " + a[0].v)
            return
        if (op == "mem.load" or op == "mach.load"):
            addr = a[0].v
            if op == "mach.load" and i.t == "int" and ("U:" + addr in self.base or "U:" + addr in s.d) and not self.length_read(addr):
                u = self.box(s, addr)
                if checking and "None" in s.dom(u):
                    self.error(b, "mach.load needs a nonnull proof for " + addr)
                s.copy("T:" + r, u)
                return
            if "U:" + r in self.base:
                mk = "MU:" + addr
                if mk not in s.d:
                    s.set(mk, self.base[mk] if mk in self.base else self.base["U:" + r])
                s.copy("U:" + r, mk)
            if r in self.tagvals:
                s.copy("T:" + r, "MT:" + addr)
            if r in self.bitsneeded:
                s.copy("B:" + r, "MB:" + addr)
            return
        if (op == "mem.store" or op == "mach.store"):
            addr = a[0].v
            v = a[1].v
            t = a[1].t
            if addr not in self.private:
                self.killmem(s, addr)
            if "MU:" + addr in self.base or "U:" + v in self.base or "U:" + v in s.d:
                s.copy("MU:" + addr, self.box(s, v))
            else:
                s.forget("MU:" + addr)
            if addr in self.tagslots:
                s.copy("MT:" + addr, self.tag(s, v))
            if addr in self.bitsslots:
                payload = self.bits(s, a[1])
                source = self.defs[v] if v in self.defs else None
                generic = source is not None and (source.op == "list.load" or (source.op == "rt" and (source.s == "list.get" or source.s == "list.pop" or source.s == "dict.get" or source.s == "dict.pop" or source.s == "set.pop")))
                if v not in self.raw and generic and self.native.get(v, "") in ["T", "K", "V", "*T", "*K", "*V"] and addr in self.memtypes:
                    # Generic runtime element results are instantiated by native
                    # storage declarations. Container element typing is its own
                    # contract; opaque union payloads never use this boundary.
                    s.set("MB:" + addr, [self.memtypes[addr]])
                else:
                    s.copy("MB:" + addr, payload)
            if checking and v in self.raw and addr not in self.private:
                self.checkbits(s, v, t, b, op)
            return
        if op == "rt" and i.s == "box":
            payload = self.bits(s, a[0])
            domain = s.dom(payload)
            scalar = len(domain) == 1 and (domain[0] == "int" or domain[0] == "float" or domain[0] == "bool")
            if checking and a[0].v in self.raw and not scalar:
                self.error(b, "box needs a proved scalar payload type")
            if scalar or a[0].v in self.raw:
                s.copy("U:" + r, payload)
            else:
                # Native scalar boxing may consume a generic runtime container result.
                # Container typing proves its scalar kind; this proof must not invent
                # a more precise member from the runtime signature's T/V placeholders.
                s.set("U:" + r, ["bool", "float", "int"])
        elif op == "rt" and i.s == "big.box":
            s.set("U:" + r, [BIG])  # (a promoting int's box, never None: bigints.py)
        elif op == "rt" and (i.s == "ubox" or i.s == "ubox_opt"):
            t = self.tag(s, a[0].v)
            d = s.dom(t)
            if checking and i.s == "ubox":
                p = self.bits(s, a[1])
                pd = s.dom(p)
                tr = s.eq[t] if t in s.eq else t
                pr = s.eq[p] if p in s.eq else p
                if d != pd or (len(d) > 1 and tr != pr):
                    self.error(b, "ubox needs matching tag and payload provenance")
            s.copy("U:" + r, t)
            if i.s == "ubox_opt" and "None" not in d:
                nd = [v for v in d]
                nd.append("None")
                nd.sort()
                s.set("U:" + r, nd)
        elif op == "slot.pack":
            if "U:" + r in self.base or "U:" + a[0].v in s.d:
                s.copy("U:" + r, self.box(s, a[0].v))
            if a[0].v in self.raw:
                s.copy("B:" + r, self.bits(s, a[0]))
            else:
                s.set("B:" + r, [a[0].t])
        elif op == "slot.unpack":
            if "U:" + r in self.base:
                if "U:" + a[0].v in s.d:
                    s.copy("U:" + r, "U:" + a[0].v)
                else:
                    s.set("U:" + r, self.base["U:" + r])
            if checking:
                self.checkbits(s, a[0].v, i.t, b, op)
            if (i.t == "str" or i.t == "bytes") and a[0].v in self.raw and "U:" + r in self.base:
                s.copy("U:" + r, "B:" + a[0].v)
        elif (op == "num.cmp" or op == "scalar.cmp") and (i.s == "==" or i.s == "!=" or i.s == "eq" or i.s == "ne"):
            x = a[0].v
            y = a[1].v
            if self.integer(x):
                tmp = x
                x = y
                y = tmp
            if x in self.tagvals and self.integer(y):
                self.compare(s, r, self.tag(s, x), [self.tags[y] if y in self.tags else "?"], (i.s == "==" or i.s == "eq"))
        elif op == "ptr.cmp" and (a[0].v == "null" or a[1].v == "null"):
            v = a[0].v if a[1].v == "null" else a[1].v
            if "U:" + v in self.base or "U:" + v in s.d:
                self.compare(s, r, self.box(s, v), ["None"], i.s == "==")
        elif op == "scalar.bin" and i.t == "bool":
            x = a[0].v
            y = a[1].v
            if i.s == "xor" and y == "true":
                s.boolean(r, s.conditional(x, False), s.conditional(x, True))
            elif (i.s == "or" or i.s == "and"):
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
        elif op == "select":
            yes = s.conditional(a[0].v, True)
            no = s.conditional(a[0].v, False)
            if "U:" + r in self.base:
                yes.copy("U:" + r, self.box(yes, a[1].v))
                no.copy("U:" + r, self.box(no, a[2].v))
            if r in self.bitsneeded:
                yes.copy("B:" + r, self.bits(yes, a[1]))
                no.copy("B:" + r, self.bits(no, a[2]))
            if r in self.tagvals:
                yes.copy("T:" + r, self.tag(yes, a[1].v))
                no.copy("T:" + r, self.tag(no, a[2].v))
            q = union_join(yes, no)
            s.d = q.d
            s.eq = q.eq
            s.bt = q.bt
            s.bf = q.bf
            s.truth = q.truth
        elif r != "" and "U:" + r in self.base:
            s.set("U:" + r, self.base["U:" + r])
        if checking:
            for j in range(len(a)):
                operand = a[j]
                transport = (op == "phi" or op == "select" or op == "slot.pack" or op == "slot.unpack" or op == "mem.load" or op == "mach.load") or (op == "rt" and ((i.s == "ubox" and j == 1) or (i.s == "box" and j == 0)))
                if not transport:
                    t = self.runtime_type(i, operand.t) if op == "rt" else operand.t
                    if op == "gen.yield" and j == 0 and is_gen(self.fn.f.ret):
                        # (the word a suspension yields is its value as the generator's element
                        # type, gen_slots, which its consumer's slot.unpack reads)
                        t = gelem(self.fn.f.ret)
                    self.checkbits(s, operand.v, t, b, op)
        if (op == "rt" or op == "call" or op == "icall" or op == "init" or op == "gen.resume") and self.writes.get(op + "|" + i.s + "|" + i.x, True):
            self.killmem(s)

    def edge(self, s: UnionState, frm: str, to: str) -> UnionState:
        z = s.clone()
        dests: list[str] = []
        srcs: list[str] = []
        bools: list[str] = []
        bsources: list[str] = []
        for i in self.fn.blocks[self.blocks[to]].code:
            if i.op != "phi":
                break
            if frm not in i.b:
                continue
            a = i.a[i.b.index(frm)]
            r = "%t" + str(i.r[0])
            if i.t == "bool":
                bools.append(r)
                bsources.append(a.v)
            if "U:" + r in self.base:
                dests.append("U:" + r)
                srcs.append(self.box(z, a.v))
            if r in self.bitsneeded:
                dests.append("B:" + r)
                srcs.append(self.bits(z, a))
            if r in self.tagvals:
                dests.append("T:" + r)
                srcs.append(self.tag(z, a.v))
        for j in range(len(dests)):
            z.copy("phi:" + dests[j], srcs[j])
        bc: list[UnionState] = []
        for j in range(len(bools)):
            q = z.clone()
            q.boolcopy(bools[j], bsources[j])
            # A loop's saved boolean can refer to the previous values of its
            # phi destinations. Do not restore those implications after the
            # simultaneous assignments. Only captured incoming-value facts
            # describe the new destinations, including a paired value/guard.
            for facts in [q.bt[bools[j]], q.bf[bools[j]]]:
                for k in dests:
                    if k in facts:
                        del facts[k]
                    if "phi:" + k in facts:
                        facts[k] = facts["phi:" + k]
                        del facts["phi:" + k]
            bc.append(q)
        for k in dests:
            z.copy(k, "phi:" + k)
        for k in dests:
            z.forget("phi:" + k)
        for j in range(len(bools)):
            k = bools[j]
            z.truth[k] = bc[j].truth[k]
            z.bt[k] = bc[j].bt[k]
            z.bf[k] = bc[j].bf[k]
        z.retain(self.livevalues[to])
        return z

    def flow(self, b: Blk, s: UnionState, dests: list[str], edges: list[UnionState]) -> None:
        # one block for the worklist (dataflow.forward_fixpoint): s becomes its facts at its
        # end, and each edge that leaves it joins dests and edges
        label = b.label
        for i in b.code:
            if i.op == "phi":
                continue
            self.transfer(s, i, label, False)
            call = (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume")
            throwing = (i.op == "raise" or i.op == "throw" or i.op == "check") or (call and self.raises.get(i.op + "|" + i.s + "|" + i.x, True))
            if b.handler != "" and throwing:
                ex = s.conditional(i.a[0].v, True) if i.op == "check" else s.clone()
                self.killmem(ex)
                dests.append(b.handler)
                edges.append(ex)
        last = b.code[-1]
        if last.op == "cbr":
            dests.extend(last.b)
            edges.append(s.conditional(last.a[0].v, True))
            edges.append(s.conditional(last.a[0].v, False))
        elif last.op == "check":
            dests.append(last.b[0])
            edges.append(s.conditional(last.a[0].v, False))
            ck = last.x if last.x != "" else last.s
            if ck in self.fn.cold:
                dests.append(self.fn.cold[ck])
                edges.append(s.conditional(last.a[0].v, True))
        elif last.op == "switch" and last.a[0].v in self.tagvals:
            key = self.tag(s, last.a[0].v)
            default = s.clone()
            dests.extend(last.b)
            edges.append(default)
            for j in range(1, len(last.a)):
                arm = s.clone()
                literal = last.a[j].v
                # Only canonical, known tag IDs establish an exact member.
                # Other spellings and the many unknown IDs grouped by '?'
                # remain conservative on both the case and default edges.
                if literal in self.tags:
                    member = self.tags[literal]
                    arm.narrow(key, [member])
                    default.narrow(key, [t for t in default.dom(key) if t != member])
                edges.append(arm)
        else:
            for l in last.b:
                dests.append(l)
                edges.append(s.clone())

    def run(self) -> None:
        forward_fixpoint(self)
