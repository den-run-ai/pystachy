"""Ircheck component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import dynamic_program, fail, int_lists, int_program
from src.pystachy_compiler.dynamic_proof import DynamicProof, DynTypes
from src.pystachy_compiler.ir import Blk, IFn, Ins, NOLABELS, merged_blocks, operand_kind, slot_register, tmpname, value_definitions
from src.pystachy_compiler.scalar_ir import SCALAR_INTS
from src.pystachy_compiler.symbols import ClassInfo
from src.pystachy_compiler.union_proof import UnionProof, simple_union_proof
from src.pystachy_compiler.specs import BIG, CAST_KINDS, EMPTYFS, FX, FXALL, FXBIT, ICMP, IROPS, LIST_READS, LIST_WRITES, NONEVAR, RAWR, RAWW, RUNTIME, TYPE_CLASSES
from src.pystachy_compiler.specs import OPS, OP_ENTRY, OP_FIELDS, OP_INVOKE, OP_K, OP_LABELS, OP_MAX, OP_MIN, OP_OPERAND_TYPES, OP_PER_OPERAND, OP_RESULT_TYPE, OP_S, OP_T, OP_TEMPS, OP_X, RESULT_NUMBERS
from src.pystachy_compiler.utils import RT_VARS, gelem, generator_identity, is_dict, is_gen, is_list, is_opt, is_set, is_tuple, is_union, list_read_error, list_receiver_error, list_write_error, lt, packed_item, rt_generic, rt_instance_error, same_kind, targs, tslots, umembers, unopt

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


def big_digits(d: str) -> bool:
    # may a value of descriptor d hold an int whose repr runtime.c's walks write from its digits, in
    # a program whose lists, dicts and sets of ints hold promoting ints (int_lists): a list's int
    # (Li), a set's (Si, Fi) or a dict's (D, its value: any dict whose descriptor holds an int),
    # whose repr raises CPython's ValueError past 4300 digits (digits_deep)
    return "Li" in d or "Si" in d or "Fi" in d or ("D" in d and "i" in d)


def has_machine_union_tag(fn: IFn) -> bool:
    # A machine pointer annotation alone says nothing about its source. Recognize
    # union boxes from parameter and result declarations, not narrowed operands.
    # Only functions with an integer machine load need this scan.
    sources: dict[str, bool] = {}
    for n in range(len(fn.f.ptypes)):
        t = fn.f.ptypes[n]
        if is_union(t[4:-1] if is_opt(t) else t):
            sources["%a" + str(n)] = True
    for b in fn.blocks:
        for i in b.code:
            if len(i.r) == 1 and is_union(i.t[4:-1] if is_opt(i.t) else i.t):
                sources["%t" + str(i.r[0])] = True
    if len(sources) == 0:
        return False
    for b in fn.blocks:
        for i in b.code:
            if i.op == "mach.load" and i.t == "int" and i.a[0].v in sources:
                return True
    return False


def op_shape_error(i: Ins, entry: bool) -> str:
    # What its row of the operation table (specs.OPS) says of i's shape, or "": its place (entry
    # is whether it is among a function's slots), its operand and label counts, and the fields
    # it may set. Its result count is Gen.nums', which reads a call's from its signature.
    op = i.op
    if OP_ENTRY[op] != entry:
        return f"{op} in a block, where entry storage belongs among the slots" if OP_ENTRY[op] else f"{op} among the slots"
    n = len(i.a)
    if n < OP_MIN[op] or (OP_MAX[op] >= 0 and n > OP_MAX[op]):
        return f"{op} with {n} operands, where the operation table has {OPS[op].split('|')[1]}"
    rule = OP_LABELS[op]
    m = len(i.b)
    if (m != n) if rule == OP_PER_OPERAND else (m != 0 and m != 2) if rule == OP_INVOKE else m != rule:
        return f"{op} with {m} labels, where the operation table has {OPS[op].split('|')[3]}"
    fields = OP_FIELDS[op]
    field = "t" if i.t != "" and fields & OP_T == 0 else "s" if i.s != "" and fields & OP_S == 0 else "k" if i.k != 0 and fields & OP_K == 0 else "x" if i.x != "" and fields & OP_X == 0 else ""
    if field != "":
        # (the row's fields, by their names: t, s:operator)
        named = ", ".join(OPS[op].split("|")[4].split())
        return f"{op} sets {field}, where its row of the operation table names {named or 'no field'}"
    return ""


# the element types a runtime-length tuple holds besides objects of declared classes (Gen.vtuple_holds)
VTUPLE_ELEMS: list[str] = ["int", "float", "bool", "str", "dyn", "opt[int]", "opt[float]", "opt[bool]", "opt[str]", "opt[dyn]"]


def native_type(t: str, classes: dict[str, ClassInfo]) -> bool:
    # a Python value's native type (specs.TYPE_CLASSES): no machine type (%), address (&), packed
    # slot (*) or descriptor (#), and a runtime type variable only where a class has its name
    return t != "" and not t.startswith("%") and not t.startswith("&") and not t.startswith("*") and t != "#" and (t not in RT_VARS or t in classes)


def fixed_tuple(t: str) -> bool:
    # a fixed tuple's type: every item's type given, none a runtime length (...)
    if not is_tuple(t) or not t.endswith("]") or t.count("[") != t.count("]"):
        return False
    ts = targs(t)
    return "" not in ts and "..." not in ts


def union_members(u: str, classes: dict[str, ClassInfo]) -> list[str]:
    # the members of a nonoptional closed union: two or more, each a distinct native value type,
    # and none None, optional or a union; [] for any other type
    ms = umembers(u) if is_union(u) and u.endswith("]") else []
    if len(ms) < 2:
        return []
    for j in range(len(ms)):
        m = ms[j]
        if m == "None" or is_opt(m) or is_union(m) or m.count("[") != m.count("]") or ms.index(m) != j or not native_type(m, classes):
            return []
    return ms


def name_end(c: str, at: int) -> int:
    # where the name of a type variable or class that starts at c[at] ends
    while at < len(c) and (c[at].isalnum() or c[at] == "_"):
        at += 1
    return at


def constraint_parts(c: str) -> list[str]:
    # constraint c of a types column by its parts: the text before its variable, the variable's
    # name ("" for none), the class given after the name ("" for none) and the text after them
    v = c.find("$")
    if v < 0:
        return [c, "", "", ""]
    e = name_end(c, v + 1)
    if e < len(c) and c[e] == ":":
        k = name_end(c, e + 1)
        return [c[:v], c[v + 1 : e], c[e + 1 : k], c[k:]]
    return [c[:v], c[v + 1 : e], "", c[e:]]


def read_constraints() -> dict[str, list[str]]:
    # the parts of each constraint that the operation table's types columns hold (constraint_parts)
    parts: dict[str, list[str]] = {}
    for op in OP_OPERAND_TYPES:
        for c in OP_OPERAND_TYPES[op] + [OP_RESULT_TYPE[op]]:
            if c not in parts:
                parts[c] = constraint_parts(c)
    return parts


def read_kinds() -> dict[str, dict[str, str]]:
    # each op's variables' classes, given at any of the names its row has for them
    kinds: dict[str, dict[str, str]] = {}
    for op in OP_OPERAND_TYPES:
        kinds[op] = {}
        for c in OP_OPERAND_TYPES[op] + [OP_RESULT_TYPE[op]]:
            p = CONSTRAINT_PARTS[c]
            if p[2] != "":
                kinds[op][p[1]] = p[2]
    return kinds


# The operation table's types columns, read once (op_type_error): each constraint's parts, and
# each op's variables' classes
CONSTRAINT_PARTS: dict[str, list[str]] = read_constraints()
OP_KINDS: dict[str, dict[str, str]] = read_kinds()


def placed(j: int) -> str:
    # where a types column's variable was bound: operand j, or the result where j < 0
    return "the result" if j < 0 else f"operand {j}"


class OpTypes:
    # The types column's check of a function's ops (specs.OPS, op_type_error): its declared
    # classes, and the closed unions found so far, each validated once, whose members the union
    # proofs read. Per op: each variable's class (kinds, OP_KINDS's), its type (bound) and where
    # that is (an operand's position, -1 for the result).
    def __init__(self, fn: IFn, classes: dict[str, ClassInfo], unions: dict[str, list[str]]):
        self.fn = fn
        self.classes = classes
        self.unions = unions
        self.kinds: dict[str, str] = {}
        self.bound: dict[str, str] = {}
        self.where: dict[str, int] = {}

    def admits(self, name: str, t: str) -> bool:
        # whether type t is of the type class name (specs.TYPE_CLASSES)
        native = native_type(t, self.classes)
        if name == "any":
            return True
        if name == "native":
            return native
        if name == "scalar":
            return (native and t != "None") or t == "%ptr" or t == "%byte" or t == "%i32" or t == "%slot" or (t.startswith("*") and native_type(t[1:], self.classes))
        if name == "packed":
            return t == "%slot" or (t.startswith("*") and native_type(t[1:], self.classes))
        if name == "machine":
            return (native and t != "None") or t == "%ptr" or t == "%byte" or t == "%i32" or t == "%slot" or (t.startswith("*") and native_type(t[1:], self.classes))
        if name == "ref":
            return native and (t == "None" or lt(t) == "ptr")
        if name == "number":
            return t == "int" or t == "float"
        if name == "numeric":
            return t == "bool" or t == "int" or t == "float"
        if name == "arith":
            return t in SCALAR_INTS or t == "float"
        if name == "bits":
            return t in SCALAR_INTS or t == "float" or t == "%ptr"
        if name == "union":
            if t not in self.unions:
                ms = union_members(t, self.classes)
                if len(ms) == 0:
                    return False
                self.unions[t] = ms
            return True
        if name == "ftuple":
            return fixed_tuple(t)
        if name == "class":
            return t in self.classes
        if name == "layout":
            return t in self.classes or fixed_tuple(t)
        if name == "velem":
            if t in VTUPLE_ELEMS:
                return True
            # (or objects of declared classes, also of a union of them: Gen.vtuple_holds)
            for m in umembers(t) if is_union(t) else [t]:
                if m not in self.classes:
                    return False
            return True
        if name == "item":
            return list_receiver_error("list[" + t + "]") == ""
        if name == "dictset":
            return is_dict(t) or is_set(t)
        if name == "gen":
            return is_gen(t)
        if name == "return":
            # (or, in a function that returns opt[T] of a reference T, a T, whose pointer is its
            # value as null is None; and an empty container's whose types are not known yet,
            # Gen.holes, of the kind it returns)
            r = self.fn.f.ret
            some = unopt(r) if is_opt(r) and lt(unopt(r)) == "ptr" else r
            return t == r or t == some or ("?" in t and (same_kind(t, r) or same_kind(t, some)))
        fail(f"internal error: the operation table names {name}, which is no type class", 0)
        return False

    def need(self, c: str, t: str, place: int) -> str:
        # What constraint c of a types column asks for where type t is not that, or "". c is a
        # type, a type class, or a type around a variable ($T, *$T, list[$E]): the variable is
        # bound to its part of the first type it meets, which must be of its class, and later
        # each must be what that makes it. place: t's operand, -1 for the result
        p = CONSTRAINT_PARTS[c]
        name = p[1]
        if name == "":
            if c in TYPE_CLASSES:
                return "" if self.admits(c, t) else TYPE_CLASSES[c]
            return "" if t == c else c
        prefix = p[0]
        suffix = p[3]
        if name in self.bound:
            want = prefix + self.bound[name] + suffix
            return "" if t == want else f"{want} (${name} is {self.bound[name]} at {placed(self.where[name])})"
        kind = self.kinds[name] if name in self.kinds else ""
        inner = ""
        if len(t) > len(prefix) + len(suffix) and t.startswith(prefix) and t.endswith(suffix):
            inner = t[len(prefix) : len(t) - len(suffix)]
        if inner == "" or (kind != "" and not self.admits(kind, inner)):
            what = TYPE_CLASSES[kind] if kind != "" else "a type"
            return what if prefix == "" and suffix == "" else f"{prefix}${name}{suffix}, ${name} {what}"
        self.bound[name] = inner
        self.where[name] = place
        return ""


def op_type_error(check: OpTypes, i: Ins) -> str:
    # What the types column of i's row (specs.OPS) says of its operand and result types, or "".
    # Its last operand constraint holds for any further operands, and a variable's class may be
    # given at any of its names. (An rt, call, icall or init op is built to its signature.)
    if i.op not in OP_OPERAND_TYPES:
        return ""
    cs = OP_OPERAND_TYPES[i.op]
    result = OP_RESULT_TYPE[i.op]
    check.kinds = OP_KINDS[i.op]
    if len(check.bound) > 0:
        # (the previous op's bindings; most ops bind none, and keep the empty ones)
        check.bound = {}
        check.where = {}
    for j in range(len(i.a) if len(cs) > 0 else 0):
        need = check.need(cs[j] if j < len(cs) else cs[len(cs) - 1], i.a[j].t, j)
        if need != "":
            return f"{i.op} operand {j} needs {need}, got {i.a[j].t or 'no type'}"
    if result != "":
        need = check.need(result, i.t, -1)
        if need != "":
            return f"{i.op} result needs {need}, got {i.t or 'no type'}"
    return ""


def ref_type(t: str) -> bool:
    # is t a type whose value is a pointer: no machine type, address, packed slot or None
    return t != "" and not t.startswith("%") and not t.startswith("&") and not t.startswith("*") and lt(t) == "ptr"


def held_none(t: str) -> bool:
    # may a local first assigned None, whose slot keeps NONEVAR once inference has typed it,
    # hold a t: a pointer, null for None, but a union's or a dyn's box
    return ref_type(t) and t != "dyn" and not t.startswith("union[") and not t.startswith("opt[dyn")


def type_view(self, a: str, b: str, generic: bool, parent: str) -> str:
    # The view of specs.TYPE_VIEWS that reads type a as type b, both of them perhaps inside a
    # type's brackets, or "": same, instance (a placeholder, or a runtime type variable that names no
    # class or, where generic, any, stands for any one type), alias, optional or class. generic:
    # an rt op defines the value or reads it, so the types may be its signature's; parent: the
    # name of the type whose brackets hold them, "" for none
    if a == b:
        return "same"
    if a == "?" or b == "?" or (a in RT_VARS and (generic or a not in self.classes)) or (b in RT_VARS and (generic or b not in self.classes)):
        return "instance"
    if (a == NONEVAR and held_none(b)) or (b == NONEVAR and held_none(a)):
        return "instance"
    if (a == "str" and b == "bytes") or (a == "bytes" and b == "str") or (a == "exc" and b == "exctype") or (a == "exctype" and b == "exc"):
        return "alias"
    if (a.startswith("rec[") and a[4:-1] in self.recursive and self.recursive[a[4:-1]] == b) or (b.startswith("rec[") and b[4:-1] in self.recursive and self.recursive[b[4:-1]] == a):
        return "alias"
    if b.startswith("rec[") and b[4:-1] in self.recursive and is_union(unopt(a)):
        # A smaller closed union stores the same tag and payload in a recursive
        # value slot. The alias must admit every incoming member, including None.
        target = self.recursive[b[4:-1]]
        if is_union(unopt(target)) and (not is_opt(a) or is_opt(target)):
            members = umembers(unopt(target))
            if all([m in members for m in umembers(unopt(a))]):
                return "alias"
    if parent != "" and ((a == "int" and b == BIG) or (a == BIG and b == "int")):
        return "alias"
    if parent == "tuple" and a == "bool" and b == "int":
        return "alias"
    if (a == EMPTYFS and is_set(b)) or (b == EMPTYFS and is_set(a)):
        return "alias"
    if (a.startswith("*") and b.startswith("*")) or (a.startswith("&") and b.startswith("&")):
        return type_view(self, a[1:], b[1:], generic, parent)
    if a == "None" and (is_opt(b) or ref_type(b)):
        return "optional"
    if is_opt(b) and not is_opt(a) and ref_type(a) and type_view(self, a, unopt(b), generic, parent) != "":
        return "optional"
    if is_opt(a) and not is_opt(b) and ref_type(b) and type_view(self, unopt(a), b, generic, parent) != "":
        return "optional"
    if builtin_view(self, a, b, generic, parent) or builtin_view(self, b, a, generic, parent):
        return "builtin base"
    if related(self, a, b):
        return "class"
    if is_union(a) and is_union(b):
        ms = umembers(b)
        for m in umembers(a):
            if m in ms:
                return "class"
    ha = a.find("[")
    hb = b.find("[")
    if ha <= 0 or hb <= 0 or not a.endswith("]") or not b.endswith("]") or a.startswith("fn[") or b.startswith("fn["):
        return ""
    na = a[:ha]
    nb = b[:hb]
    keyed = parent == "" and ((na == "tuple" and nb == "kw") or (na == "kw" and nb == "tuple"))
    if na != nb and not keyed and not (is_set(a) and is_set(b)):
        return ""
    xs = targs(a)
    ys = targs(b)
    if na == "gen" and nb == "gen" and len(xs) > 0 and len(ys) > 0:
        # (a generator, typed by what it yields and perhaps by what it returns)
        xs = xs[:1]
        ys = ys[:1]
    if len(xs) != len(ys):
        return ""
    view = "same" if na == nb else "alias"
    for j in range(len(xs)):
        # (a keyword record's item is name:type)
        x = xs[j][xs[j].find(":") + 1 :] if keyed and na == "kw" else xs[j]
        y = ys[j][ys[j].find(":") + 1 :] if keyed and nb == "kw" else ys[j]
        v = type_view(self, x, y, generic, na)
        if v == "":
            return ""
        if view == "same":
            view = v
    return view


def builtin_view(self, c: str, t: str, generic: bool, parent: str) -> bool:
    # is c a class deriving from a builtin container (builtin_bases.py) and t that container's type,
    # list[T] or dict[K, V], as Gen.bview reads its objects: by its items' types too, once the
    # frontend has decided them (Gen.bbase)
    k = self.bkind(c)
    if not ((k == "list" and is_list(t)) or (k == "dict" and is_dict(t))):
        return False
    o = self.classes[c].origin if self.classes[c].origin != "" else c
    b = self.bsub[o] if o in self.bsub else ""
    return b == "" or "?" in b or type_view(self, b, t, generic, parent) != ""


def related(self, x: str, y: str) -> bool:
    # is one of classes x and y derived from the other or from a class that has a common derived
    # class with the other (ClassInfo.overlaps: dispatch on an object of x that isinstance() found
    # to be of such a base reads it as each class derived from that base); every class derives
    # from object
    if x in self.classes and (y == "object" or self.derives(x, y)):
        return True
    if y in self.classes and (x == "object" or self.derives(y, x)):
        return True
    if x in self.classes and y in self.classes:
        for z in self.classes[x].overlaps:
            if self.derives(y, z):
                return True
        for z in self.classes[y].overlaps:
            if self.derives(x, z):
                return True
    return False


def receiver(f: str) -> str:
    # the receiver type of a bound method's type f (fn[m:C.name], fn[d:name:C]), env for a
    # closure's (fn[c:...]), else ""
    if f.startswith("fn[m:") and "." in f:
        return f[5 : f.rfind(".")]  # (a nested class's name holds dots, a method's none: fn[m:Outer.Inner.f])
    if f.startswith("fn[d:") and f.endswith("]"):
        return f[f.rfind(":") + 1 : -1]
    return "env" if f.startswith("fn[c:") else ""


def value_view(self, d: str, u: str, rt_result: bool, rt_operand: bool) -> str:
    # The view of specs.TYPE_VIEWS by which an operand of type u reads a value whose definition
    # gives it type d, or "" for none; value_types decides the machine and bits views, which
    # depend on addresses. rt_result: an rt op defines the value; rt_operand: one reads it
    generic = rt_result or rt_operand
    view = type_view(self, d, u, generic, "")
    if view != "":
        return view
    if (d == "int" and u.startswith("*") and type_view(self, u[1:], "int", generic, "") != "") or (u == "int" and d.startswith("*") and type_view(self, d[1:], "int", generic, "") != ""):
        return "int slot"
    if (rt_result and d == "bool" and u == "int") or (rt_operand and d == "int" and u == "bool"):
        return "runtime bool"
    x = receiver(d)
    y = receiver(u)
    if (x != "" and type_view(self, x, unopt(u), generic, "") != "") or (y != "" and type_view(self, unopt(d), y, generic, "") != ""):
        return "method"
    return ""


def optional_reads(self, fn: IFn) -> dict[str, dict[str, bool]]:
    # The values of fn that an operand reads at a type without None where their definition gives
    # them opt[U] of a reference U (the optional view that narrows, specs.TYPE_VIEWS), with the
    # types those operands read them at: the closed-union proof must show each such value not
    # None where an operand reads it so (UnionProof.check_some)
    types: dict[str, str] = {}
    makers: dict[str, str] = {}
    value_definitions(fn, types, makers)
    found: dict[str, dict[str, bool]] = {}
    for b in fn.blocks:
        for i in b.code:
            for a in i.a:
                d = types.get(a.v, "")
                if is_opt(d) and narrows_none(self, d, a.t, makers[a.v] == "rt", i.op == "rt"):
                    if a.v not in found:
                        found[a.v] = {}
                    found[a.v][a.t] = True
    return found


def narrows_none(self, d: str, u: str, rt_result: bool, rt_operand: bool) -> bool:
    # does an operand of type u read a value of type d, an opt[U], at a type that holds no None
    # (U, or a type that a view reads U as), so that the read needs a proof that it is not None
    return u != "None" and not is_opt(u) and lt(u) == "ptr" and value_view(self, d, u, rt_result, rt_operand) == "optional"


def related_reads(self, a: str, b: str) -> bool:
    # may two operands read one value, whose definition gives it only a machine type, a runtime
    # type variable or a placeholder, as types a and b: by a view between them
    x = unopt(a)
    y = unopt(b)
    return x == y or type_view(self, a, b, False, "") != "" or type_view(self, b, a, False, "") != ""


def class_union(self, t: str) -> bool:
    # is t a closed union of classes (union_members), whose box holds an object of one of them
    ms = union_members(t, self.classes)
    return len(ms) > 0 and all(m in self.classes for m in ms)


def cast_error(self, fn: IFn, i: Ins, objects: dict[str, bool], types: dict[str, str]) -> str:
    # What the rule of cast i's kind (specs.CAST_KINDS) says of its operand and its result, or "".
    # Every kind keeps the operand's LLVM type, since lowering erases the cast and its uses read
    # the operand (Gen.erase_casts). A rule holds of the value the operand reads, of the type its
    # definition gives it (types: ir.value_definitions), which the operand reads at that type: a
    # view would read any reference as a %ptr, any packed slot as a %slot, and an object cast's
    # union as another with a common member (specs.TYPE_VIEWS). (A constant or a symbol has no
    # definition; an opaque cast's reference may be read by a view.) objects: the values of the
    # function's object casts
    v = i.a[0].v
    a = i.a[0].t
    t = i.t
    if i.s not in CAST_KINDS:
        return f"cast {i.s or 'of no kind'}, where a cast is of a kind of specs.CAST_KINDS"
    if lt(a) != lt(t) or a == t:
        return f"cast {i.s} of a {a} to a {t}, where a cast reads its operand at another type of its LLVM type"
    if i.s != "opaque" and v in types and types[v] != a:
        return f"cast {i.s} of {v}, a {types[v]} read as a {a}, where a cast of kind {i.s} reads {CAST_KINDS[i.s]}"
    ok = False
    if i.s == "bits":
        ok = (a == "%ptr" and (ref_type(t) or (t.startswith("&") and native_type(t[1:], self.classes)))) or (a == "%slot" and (t == "int" or (t.startswith("*") and native_type(t[1:], self.classes))))
    elif i.s == "object":
        ok = a == "%ptr" and class_union(self, t)
    elif i.s == "member":
        ok = i.a[0].v in objects and t in self.classes and len([m for m in umembers(a) if t == m or self.derives(t, m)]) > 0
    else:
        ok = fn.f.mod == "_pystachy_copy" and ref_type(a) and ref_type(t) and (a == "str" or t == "str")
    return "" if ok else f"cast {i.s} of a {a} to a {t}, where a cast of kind {i.s} reads {CAST_KINDS[i.s]}"


def value_types(self, fn: IFn) -> None:
    # Each operand reads its value at the type the value's definition gives it (ir.value_definitions),
    # or by a view of specs.TYPE_VIEWS, as an MLIR operand has its value's one type. An address
    # has a type &T and a packed slot a type *T, and no view reads one as the other.
    types: dict[str, str] = {}
    makers: dict[str, str] = {}
    value_definitions(fn, types, makers)
    # (the values whose definition gives them only a machine type, a runtime type variable or a
    # placeholder; the first type an operand of an op but rt reads each at, and where; and the
    # views decided so far, as many operands read alike)
    loose: dict[str, bool] = {}
    for v in types:
        d = types[v]
        if d == "%ptr" or d == "%slot" or "?" in d or NONEVAR in d or rt_generic(d):
            loose[v] = True
    read: dict[str, str] = {}
    first: dict[str, str] = {}
    decided: dict[str, bool] = {}
    for b in fn.blocks:
        for i in b.code:
            for j in range(len(i.a)):
                v = i.a[j].v
                if v not in types:
                    continue
                d = types[v]
                u = i.a[j].t
                if d == u and v not in loose:
                    continue
                if d.startswith("&") and u.startswith("*"):
                    self.bad_ir(fn, b, f"{i.op} operand {j} reads the address {v} as a packed slot")
                if d.startswith("*") and u.startswith("&"):
                    self.bad_ir(fn, b, f"{i.op} operand {j} reads {v}, a packed slot, as an address")
                ok = d == u
                rt = v in makers and makers[v] == "rt"
                if ok:
                    pass
                elif u == "%ptr":
                    ok = d.startswith("&") or ref_type(d) or d == "None"
                elif u == "%slot":
                    ok = d.startswith("*") or d == "int"
                elif u == "%addr":
                    ok = d.startswith("&")
                elif d == "%ptr" or d == "%slot":
                    # bits, of an rt op's result, whose type is its RUNTIME signature's, or read by an
                    # rt op's operand of a runtime type variable (*T, S), which only the rt ops that
                    # passes add after Gen.instantiate keep (unionslots' boxes): other ops state their
                    # results' types, and a cast reads a machine word as a typed value
                    ok = (rt or (i.op == "rt" and rt_generic(u))) and ((u.startswith("&") or ref_type(u)) if d == "%ptr" else (u == "int" or u.startswith("*") or (i.op == "rt" and u == "bool")))
                else:
                    key = d + "|" + u + ("|1" if rt else "|0") + ("1" if i.op == "rt" else "0")
                    if key not in decided:
                        decided[key] = value_view(self, d, u, rt, i.op == "rt") != ""
                    ok = decided[key]
                if not ok:
                    self.bad_ir(fn, b, f"{i.op} operand {j} reads {v} as {u}, but it is {d}")
                if v in loose and i.op != "rt" and not u.startswith("%") and "?" not in u and NONEVAR not in u:
                    if v not in read:
                        read[v] = u
                        first[v] = f"{i.op} operand {j}"
                    elif read[v] != u:
                        key = read[v] + "|" + u + "|reads"
                        if key not in decided:
                            decided[key] = related_reads(self, read[v], u)
                        if not decided[key]:
                            self.bad_ir(fn, b, f"{i.op} operand {j} reads {v} as {u}, where {first[v]} reads it as {read[v]}")


def verify_dynamic_raw(self, fn: IFn) -> None:
    # Raw dynamic payload bits are only an identity-comparison input: a bits cast reads them as
    # an int, which only a direct integer equality comparison reads. Collect all producers
    # before uses: block order and an operand's annotation cannot hide a reinterpretation or
    # later producer. No phi/slot/call transport is admitted, so another pass cannot launder
    # the bits into a type. (The op's address is a temporary of its lowering, which gen_verify
    # admits as no op's operand.)
    payloads: dict[str, bool] = {}
    words: dict[str, bool] = {}
    for b in fn.blocks:
        for i in b.code:
            if i.op == "dyn.raw":
                payloads[tmpname(i.r[1])] = True
    for b in fn.blocks:
        for i in b.code:
            if i.op == "cast" and i.s == "bits" and i.t == "int" and len(i.a) == 1 and i.a[0].v in payloads:
                words[tmpname(i.r[0])] = True
    for b in fn.blocks:
        for i in b.code:
            for a in i.a:
                if (a.v in payloads and not (i.op == "cast" and i.s == "bits" and i.t == "int")) or (a.v in words and not (i.op == "num.cmp" and (i.s == "==" or i.s == "!=") and a.t == "int")):
                    self.bad_ir(fn, b, "dyn.raw bits require a bits cast to an int that a direct integer equality comparison reads")


def gen_verify(self, fn: IFn, eh: bool) -> None:
    # PYSTACHY_IRCHECK=1: fn is well formed. Every op is in IROPS, an rt op's key in RUNTIME;
    # call and init ops call compiled
    # functions (or, in runtime mode, runtime.c's functions that runtime.py declares); every block ends with its one terminator; branches go to blocks of fn; a phi
    # starts its block, and its predecessors branch there; each op holds exactly the numbers
    # its lowering prints (Ins.r), and no number or label is above IFn.n. Exceptions (once the
    # passes of eh_ir have run, eh): a landing op is alone in its block, which only the unwind
    # edges of invokes reach, and every invoke's unwind edge goes to one; in a block that a
    # try statement covers, no call that may raise is left a call, nor a raise or throw. In a
    # function the compiler built (IFn.located), every op, a slot too, has its source line
    at: dict[str, int] = {}
    union_types: dict[str, list[str]] = {}
    union_proofs = False
    dynamic_proofs = False
    dynamic_raw = False
    machine_tags = False
    lands: dict[str, bool] = {}
    temps: dict[str, str] = {}  # (each lowering temporary that an op defines, OP_TEMPS: its op)
    objects: dict[str, bool] = {}  # (the values of object casts, which few ops may read: cast_error)
    casts = False
    for b in fn.blocks:
        if len(b.code) > 0 and b.code[0].op == "landing":
            lands[b.label] = True
        for i in b.code:
            if i.op in OP_TEMPS:
                for j in OP_TEMPS[i.op]:
                    if j < len(i.r):
                        temps[tmpname(i.r[j])] = i.op
            if i.op == "cast":
                casts = True
                if i.s == "object" and len(i.r) == 1:
                    objects[tmpname(i.r[0])] = True
    # (the type of each value where it is defined, of which a cast's rule holds: cast_error)
    defined: dict[str, str] = {}
    makers: dict[str, str] = {}
    if casts:
        value_definitions(fn, defined, makers)
    for i in fn.slots:
        if i.op != "slot" or len(i.r) != 1:
            self.bad_ir(fn, fn.blocks[0], f"a {i.op} op among the slots, with {len(i.r)} numbers")
        if i.r[0] > fn.n:
            self.bad_ir(fn, fn.blocks[0], f"the slot of {i.s} numbered {i.r[0]}, above IFn.n ({fn.n})")
        shape = op_shape_error(i, True)
        if shape != "":
            self.bad_ir(fn, fn.blocks[0], shape)
        if i.line == 0 and fn.located:
            self.bad_ir(fn, fn.blocks[0], f"slot {slot_register(i)} has no source line")
    for j in range(len(fn.blocks)):
        l = fn.blocks[j].label
        if l in at:
            self.bad_ir(fn, fn.blocks[j], "a second block of that name")
        if l.startswith("L") and int(l[1:]) > fn.n:
            self.bad_ir(fn, fn.blocks[j], f"a label above IFn.n ({fn.n})")
        at[l] = j
    succ: list[list[str]] = []
    types = OpTypes(fn, self.classes, union_types)
    merged = merged_blocks(fn, self.source_lines.enabled)
    for b in fn.blocks:
        # Most blocks can borrow their terminator's labels without combining edges.
        out: list[str] = NOLABELS
        owned = False
        for j in range(len(b.code)):
            i = b.code[j]
            if i.op not in IROPS:
                self.bad_ir(fn, b, f"unknown op {i.op}")
            # (its row first, its shape and then its types, as MLIR's generated verifiers precede
            # an op's own; the checks of each op below assume both)
            shape = op_shape_error(i, False)
            if shape == "":
                shape = op_type_error(types, i)
            if shape != "":
                self.bad_ir(fn, b, shape)
            if i.line == 0 and fn.located and b.label not in merged:
                self.bad_ir(fn, b, f"{i.op} {i.s} has no source line" if i.s != "" else f"{i.op} has no source line")
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
            if i.op == "rt":
                if i.s == "ubox":
                    union_proofs = True
                if i.s not in self.rtfns:
                    self.bad_ir(fn, b, f"no RUNTIME entry for {i.s}" if i.s not in RUNTIME else f"{i.s}, which runtime() did not declare")
                # (its types instantiate its runtime function's signature, Gen.instantiate; a
                # native list read's or write's own contract below is stricter)
                error = rt_instance_error(i, self.rtfns[i.s].sig) if i.s not in LIST_READS and i.s not in LIST_WRITES else ""
                if error != "":
                    self.bad_ir(fn, b, error)
                if i.s in LIST_WRITES:
                    error = list_write_error(i, int_lists(), self.rtfns[i.s].sig)
                    if error != "":
                        self.bad_ir(fn, b, error)
            if i.op == "list.store" and (int_lists() or dynamic_program()):
                # an item assignment that listguard proved within the list's length, in a program
                # whose lists hold no numeric identities (none opts in): no index check, and no
                # identity companion to update, which list.set would
                self.bad_ir(fn, b, "list.store in a program whose lists may hold numeric identities")
            if i.op == "list.len" or i.op == "list.load" or (i.op == "rt" and i.s in LIST_READS):
                error = list_read_error(i, self.rtfns[i.s].sig if i.op == "rt" else None)
                if error != "":
                    self.bad_ir(fn, b, error)
            if i.op == "empty.kind":
                if i.k < 0 or i.k >= len(self.holes):
                    self.bad_ir(fn, b, "empty.kind needs a valid type hole")
                t = i.a[0].t
                if i.k == 0 and "?" in t:
                    self.bad_ir(fn, b, "empty.kind needs a dict/set key type or a deferred hole")
                h = self.holes[i.k] if i.k > 0 else t
                if h != "" and (not same_kind(t, h) or "?" in h):
                    self.bad_ir(fn, b, "empty.kind needs a concrete hole of the same dict/set kind")
            if i.op == "scalar.bin" or i.op == "scalar.cast" or i.op == "scalar.cmp":
                self.verify_scalar(fn, b, i)
            if i.op == "switch":
                # (its cases are distinct int literals, with the default's label and then one for
                # each case; a block that starts with a phi it reaches by one edge at most, as a
                # phi has one entry for each block that branches there)
                cases: dict[str, bool] = {}
                for cv in i.a[1:]:
                    if not (cv.v[1:] if cv.v.startswith("-") else cv.v).isdigit() or cv.v in cases:
                        self.bad_ir(fn, b, "switch needs distinct int literal cases")
                    cases[cv.v] = True
                edges: dict[str, int] = {}
                for l in i.b:
                    edges[l] = edges[l] + 1 if l in edges else 1
                    if edges[l] == 2 and l in at and len(fn.blocks[at[l]].code) > 0 and fn.blocks[at[l]].code[0].op == "phi":
                        self.bad_ir(fn, b, f"a switch reaches {l}, which starts with a phi, by more than one edge")
            if i.op == "mach.load" or i.op == "mach.store" or i.op == "mach.addr":
                if i.op == "mach.load" and i.t == "int":
                    machine_tags = True
                self.verify_memory(fn, b, i, False)
            if (i.op == "alloc.fixed" or i.op == "vtuple.make") and "alloc" not in self.rtfns:
                self.bad_ir(fn, b, f"{i.op} needs the alloc runtime declaration")
            if i.op == "field.addr":
                ci = self.classes[i.a[0].t]
                if i.k < 0 or (i.k >= len(ci.fields) and i.k not in ci.fflag.values() and i.k not in ci.fbox.values()):
                    self.bad_ir(fn, b, "field.addr needs a declared field, assignment flag or identity box index")
                t = ci.ftypes[ci.fields[i.k]] if i.k < len(ci.fields) else "dyn" if i.k in ci.fbox.values() else "bool"
                if i.t != "&" + t and not (i.t == "&" + NONEVAR and lt(t) == "ptr"):
                    # (but a field compiled while only None had been given to it: Gen.none_field)
                    self.bad_ir(fn, b, "field.addr result must address the declared member type")
            if i.op == "tuple.load" or i.op == "tuple.store":
                t = i.a[0].t
                ts = targs(t)
                if i.k < 0 or i.k >= tslots(t):
                    self.bad_ir(fn, b, f"{i.op} needs an in-range item index")
                if i.k >= len(ts) and (i.s != BIG or ts[i.k - len(ts)] != BIG):
                    self.bad_ir(fn, b, f"{i.op} of a slot past the items needs a promoting int item's Mpz word")  # (tslots)
                if i.k < len(ts) and (i.s != ts[i.k] or not native_type(i.s, self.classes)):
                    self.bad_ir(fn, b, f"{i.op} needs the declared native item type")
                # (an item's slot is packed: it holds the item, a promoting int's its 64-bit int; a
                # slot past the items holds an Mpz word, which no type describes; %slot claims none)
                got = i.t if i.op == "tuple.load" else i.a[1].t if len(i.a) == 2 else ""
                if 0 <= i.k < len(ts) and got != "%slot" and got != "*" + packed_item(ts[i.k]):
                    self.bad_ir(fn, b, f"{i.op} of item {i.k} needs *{packed_item(ts[i.k])}, got {got}")
                if i.k >= len(ts) and got != "%slot":
                    self.bad_ir(fn, b, f"{i.op} of an Mpz word needs %slot, got {got}")
            if i.op == "slot.unpack" and len(i.a) == 1 and i.a[0].t != "%slot" and i.a[0].t != "*" + i.t:
                self.bad_ir(fn, b, f"slot.unpack of a {i.t} needs *{i.t} or %slot, got {i.a[0].t}")
            if i.op == "slot.pack" and i.t != "%slot" and len(i.a) == 1 and i.t != "*" + i.a[0].t:
                self.bad_ir(fn, b, f"slot.pack of a {i.a[0].t} needs *{i.a[0].t} or %slot, got {i.t}")
            if i.op == "cast" and len(i.a) == 1:
                error = cast_error(self, fn, i, objects, defined)
                if error != "":
                    self.bad_ir(fn, b, error)
            if i.op == "num.cast" and i.a[0].t != "bool" and not (i.a[0].t == "int" and i.t == "float"):
                self.bad_ir(fn, b, "num.cast needs bool to int/float or int to float")
            if i.op == "num.cmp" and i.s not in ICMP:
                self.bad_ir(fn, b, "num.cmp needs a source comparison: ==, !=, <, <=, > or >=")
            if i.op == "int.ucmp" and i.s not in ["<", "<=", ">", ">="]:
                self.bad_ir(fn, b, "int.ucmp needs an unsigned order comparison: <, <=, > or >=")
            if i.op == "ptr.cmp" and i.s != "==" and i.s != "!=":
                self.bad_ir(fn, b, "ptr.cmp needs == or !=")
            if i.op == "union.tag" or i.op == "union.payload" or i.op == "union.raw":
                # (its operand's members, which its types validated: OpTypes.unions)
                union_proofs = True
                if i.op == "union.payload" and i.s not in union_types[i.a[0].t]:
                    self.bad_ir(fn, b, f"union.payload of {i.s or 'no member'}, which {i.a[0].t} does not hold")
                if i.op == "union.payload" and i.t != "%slot" and i.t != "*" + i.s:
                    self.bad_ir(fn, b, f"union.payload of {i.s} needs the packed slot *{i.s}, got {i.t}")
            if i.op == "dyn.payload":
                dynamic_proofs = True
                if i.s == "" or i.s == "dyn" or i.s.startswith("%"):
                    self.bad_ir(fn, b, "dyn.payload needs the type of the payload it reads")
                if i.t != "%slot" and i.t != "*" + i.s:
                    self.bad_ir(fn, b, f"dyn.payload of {i.s} needs the packed slot *{i.s}, got {i.t}")
            if i.op == "dyn.raw":
                dynamic_raw = True
                if len(i.r) != 2 or i.r[0] < 0 or i.r[1] < 0 or i.r[0] == i.r[1]:
                    self.bad_ir(fn, b, "dyn.raw needs two distinct nonnegative result numbers")
            if i.op.startswith("gen."):
                self.verify_gen(fn, b, i, j)
            for a in i.a:
                if operand_kind(a.v) < 0:
                    self.bad_ir(fn, b, f"{i.op} operand {a.v} is no value, parameter, slot, symbol or constant")
                if a.v in temps:
                    self.bad_ir(fn, b, f"{i.op} operand {a.v} is a temporary of a {temps[a.v]} op's lowering, which no op may use")
                if a.v in objects and not (i.op == "ptr.cmp" or (i.op == "mach.load" and a.t == "%ptr" and (i.t == "int" or i.t == "%ptr")) or (i.op == "cast" and i.s == "member")):
                    self.bad_ir(fn, b, f"{i.op} reads {a.v}, an object cast's value, which only a ptr.cmp, a mach.load of its class word (an int or a %ptr) or a member cast reads")
            n = self.nums(i)
            if len(i.r) != n:
                self.bad_ir(fn, b, f"{i.op} {i.s} with {len(i.r)} numbers, where its lowering prints {n}")
            for x in i.r:
                if x > fn.n:
                    self.bad_ir(fn, b, f"{i.op} {i.s} numbered {x}, above IFn.n ({fn.n})")
            if (i.op == "call" and i.s not in self.fll and i.s not in self.externs) or (i.op == "init" and "@init." + i.s not in self.fll):
                self.bad_ir(fn, b, f"a call of {i.s}, which is not compiled")
            if i.op != "phi" and len(i.b) > 0:
                if len(out) == 0:
                    out = i.b
                else:
                    if not owned:
                        out = [l for l in out]
                        owned = True
                    out.extend(i.b)
            if i.op == "check":
                ck = i.x if i.x != "" else i.s
                if not owned:
                    out = [l for l in out]
                    owned = True
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
    if dynamic_raw:
        verify_dynamic_raw(self, fn)
    if dynamic_proofs:
        dynamic = DynamicProof(fn, DynTypes(self.consts, self.dyntypes, self.dynfnt))
        dynamic.run()
        for j in range(len(dynamic.bad)):
            self.bad_ir(fn, fn.blocks[at[dynamic.badblocks[j]]], dynamic.bad[j])
    narrowed = optional_reads(self, fn)
    unions = union_proofs or (machine_tags and has_machine_union_tag(fn))
    if len(narrowed) > 0 or (unions and not simple_union_proof(fn, self.utags, at, succ, union_types)):
        writes: dict[str, bool] = {}
        raises: dict[str, bool] = {}
        written: dict[str, int] = {}  # (the storage classes each call writes: its RAWW and wG bits)
        for b in fn.blocks:
            for i in b.code:
                if (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume"):
                    key = i.op + "|" + i.s + "|" + i.x
                    effects = self.opfx(i, fn.fa)
                    writes[key] = effects & (RAWW | FXBIT["wG"]) != 0
                    written[key] = effects & (RAWW | FXBIT["wG"])
                    raises[key] = effects & FXBIT["R"] != 0
        # (the classes of the objects whose fields fn addresses, each with those that may be the
        # same object: related, ClassInfo.overlaps, or equal; a store to one's field may change
        # another's only so)
        kin: dict[str, dict[str, bool]] = {}
        for b in fn.blocks:
            for i in b.code:
                if i.op == "field.addr" and i.a[0].t not in kin:
                    kin[i.a[0].t] = {}
        for x in kin:
            for y in kin:
                kin[x][y] = x == y or x not in self.classes or y not in self.classes or related(self, x, y)
        proof = UnionProof(fn, self.utags, writes, self.gtypes, raises, self.globs, self.tconstdata, narrowed, written, kin, unions)
        proof.run()
        for j in range(len(proof.bad)):
            self.bad_ir(fn, fn.blocks[at[proof.badblocks[j]]], proof.bad[j])
    # (after the proofs above, whose findings name what a reading breaks more closely)
    value_types(self, fn)

def gen_verify_gen(self, fn: IFn, b: Blk, i: Ins, j: int) -> None:
    # a generator op (docs/internals.md#generators), past its row's shape and types: gen.start
    # ends the entry block of a generator function (IFn.coro) and names it; gen.yield (cleanup 0
    # or 1) and gen.ret suspend one, with the %ptr of a promoting int after the slot in a program
    # that opts in to them (specs.GENVALP), and in identity-tracking code a scalar or optional
    # numeric gen.yield also with its dyn identity companion; gen.promise without an operand is
    # its own promise
    own = i.op == "gen.start" or i.op == "gen.yield" or i.op == "gen.ret" or (i.op == "gen.promise" and len(i.a) == 0)
    if own and not fn.coro:
        self.bad_ir(fn, b, f"{i.op} outside a generator function")
    if i.k < 0 or i.k > 1:
        # (only gen.yield's row names k, its cleanup: the others' is reported as outside their rows)
        self.bad_ir(fn, b, f"{i.op} with cleanup {i.k}, where it is 0 or 1")
    if i.op == "gen.start" and b is not fn.blocks[0]:
        self.bad_ir(fn, b, "gen.start must end the entry block, with the generator's name and its first block")
    hi = len(i.a) == 2 and int_program()
    companion = fn.coro and is_gen(fn.f.ret) and generator_identity(gelem(fn.f.ret), self.fn_identity(fn.f))
    pair = len(i.a) == 3 and companion
    if pair and (not int_program() or gelem(fn.f.ret) != "int") and i.a[1].v != "null":
        self.bad_ir(fn, b, "gen.yield without a wide integer needs a null high placeholder")
    if i.op == "gen.yield" and (not pair if companion else len(i.a) != 1 and not hi):
        self.bad_ir(fn, b, "gen.yield needs the value's slot and the block where it resumes")
    if i.op == "gen.ret" and len(i.a) > 1 and not hi:
        self.bad_ir(fn, b, "gen.ret needs the slot of its value, if any")
    if i.op == "gen.start" and j != len(b.code) - 1:
        self.bad_ir(fn, b, "gen.start before other ops")

def gen_nums(self, i: Ins) -> int:
    # Runtime and compiled calls depend on their signature; all other counts are
    # fixed by the operation's lowering and need no per-instruction opcode chain.
    if i.op == "rt":
        return 0 if self.rtfns[i.s].sig[0] == "None" else 1
    if i.op == "call" or i.op == "icall":
        return 0 if i.t == "None" else 1
    return RESULT_NUMBERS.get(i.op, 0)

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
        # (a function's entry depth, gen_enter's snapshot, adds no effect of its own: a counted
        # function's entry gets its own (Gen.recursionscope), an uncounted one keeps it only for
        # its handlers' restorations, whose effects count, and the others drop it)
        snap: Ins | None = None
        if fn.rdepth != "" and len(fn.blocks) > 0 and len(fn.blocks[0].code) > 0:
            first = fn.blocks[0].code[0]
            if first.op == "rt" and first.s == "recursion.depth" and len(first.r) == 1 and tmpname(first.r[0]) == fn.rdepth:
                snap = first
        for b in fn.blocks:
            for i in b.code:
                if i is snap:
                    continue
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
        # (and a dynamic value, A, may hold any of these: dynamic.py; a list, set or dict of ints may
        # hold one whose text is past CPython's limit, in a program whose lists, sets and dicts hold
        # promoting ints: big_digits, bigints.py; and so may a promoting int, J, of a tuple or a box)
        fx = f.fx | (FXBIT["R"] if f.rq and ("R" in i.x or "A" in i.x or "J" in i.x or (big_digits(i.x) and int_lists())) else 0)
        u = "O" in i.x or "H" in i.x or "A" in i.x or ("P" in i.x and fx & FXBIT["R"] != 0) or ("E" in i.x and len(self.xcls) > 0)
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
