"""Bounded, opt-in profile hints for guarded native caller specialization."""
from __future__ import annotations
import os
from src.pystachy_compiler.analysis import local_names
from src.pystachy_compiler.diagnostics import RAW, shown
from src.pystachy_compiler.ir import FnInfo, Ins, Val
from src.pystachy_compiler.syntax import Node


def skew_reads(n: Node, param: str) -> bool:
    if n.kind == "name" and n.s == param:
        return True
    for child in n.kids:
        if skew_reads(child, param):
            return True
    return False


def skew_uses(n: Node, param: str) -> bool:
    # Replacing an input's type can also narrow an inferred alias or container.
    # Keep this prototype to direct receiver uses and None tests; don't change
    # inferred local contracts. Explicitly annotated assignments keep their type.
    if n.kind == "assign" and skew_reads(n.kids[-1], param):
        return False
    if n.kind == "for" and skew_reads(n.kids[1], param):
        return False
    for item in n.kids[:-1] if n.kind == "with" else n.kids[:0]:
        if skew_reads(item, param):
            return False
    if n.kind in ["list", "tuple", "dict", "set", "listcomp", "dictcomp", "setcomp"] and skew_reads(n, param):
        return False
    for i in range(len(n.kids)):
        child = n.kids[i]
        if child.kind == "name" and child.s == param:
            attr = n.kind == "attr" and i == 0
            none = n.kind == "cmp" and n.s in ["is", "is not", "==", "!="] and len(n.kids) == 2 and n.kids[1 - i].kind == "None"
            if not attr and not none:
                return False
        elif not skew_uses(child, param):
            return False
    return True


def skew_contracts(self, n: Node, param: str, base: str) -> bool:
    # A covariant result can specialize a downstream template to a new type and
    # invalidate one of its inferred aliases. Only fixed field/method contracts
    # across the declared receiver family enter this minimal prototype.
    if n.kind == "attr" and n.kids[0].kind == "name" and n.kids[0].s == param:
        root = self.classes[base]
        if n.s in root.ftypes:
            for ci in self.classes.values():
                if self.derives(ci.name, base) and (n.s not in ci.ftypes or ci.ftypes[n.s] != root.ftypes[n.s]):
                    return False
        elif n.s in root.methods:
            method = root.methods[n.s]
            if method.node.kids[1].kind == "noann" or method.ret == "":
                return False
            for ci in self.classes.values():
                if self.derives(ci.name, base):
                    if n.s not in ci.methods:
                        return False
                    other = ci.methods[n.s]
                    if other.node.kids[1].kind == "noann" or other.ret != method.ret:
                        return False
        else:
            return False
    for child in n.kids:
        if not skew_contracts(self, child, param, base):
            return False
    return True


def load_skew() -> dict[str, list[str]]:
    # Profiles are hints, never type evidence. Ignore missing, malformed and ambiguous
    # rows; cap input and counters so the self-hosted compiler has bounded work too.
    out: dict[str, list[str]] = {}
    path = os.getenv("PYSTACHY_SKEW_PROFILE", "")
    if path == "":
        return out
    try:
        fp = open(path, "r", encoding=RAW)
        data = fp.read(65537)
        fp.close()
    except OSError:
        return out
    lines = data.splitlines()
    if len(data) > 65536 or len(lines) == 0 or lines[0] != "pystachy-skew-v1":
        return out
    seen: dict[str, bool] = {}
    for line in lines[1:]:
        row = line.split("\t")
        if len(row) != 5:
            continue
        fn, param, cls, hits, total = row
        if fn in seen:
            out.pop(fn, [])
            continue
        seen[fn] = True
        valid = 0 < len(hits) <= 15 and 0 < len(total) <= 15
        for char in hits + total:
            valid = valid and "0" <= char <= "9"
        if fn == "" or param == "" or cls == "" or not valid:
            continue
        count = int(hits)
        calls = int(total)
        if calls >= 100 and count <= calls and count * 100 >= calls * 90:
            out[fn] = [param, cls]
    return out


def gen_skew_call(self, f: FnInfo, vals: list[Val], want: str) -> Val | None:
    # The ordinary signature has already bound and coerced every argument, once.
    # Only a non-null exact class tag selects a clone. A changed distribution merely
    # takes the original native function, including its declared return contract.
    name = shown(f.name)
    if name not in self.skew or f.generic or f.inst or f.cls != "" or f.clo >= 0 or f.vararg >= 0 or f.kwarg >= 0 or f.extern or f.export or f.pyexport or f.node.kids[1].kind == "noann" or f.ll in self.skewactive or self.rtmode:
        return None
    if f.mod.startswith("src.pystachy_compiler") or self.curfn.ll.startswith("@cv."):
        return None
    if f.ll not in self.skewclones and len(self.skewclones) >= 16:
        return None
    seed = self.skew[name]
    param = seed[0]
    if param not in f.params:
        return None
    j = f.params.index(param)
    base = f.ptypes[j]
    cls = ""
    for ci in self.classes.values():
        if shown(ci.name) == seed[1]:
            cls = ci.name
    if base not in self.classes or cls not in self.classes or cls == base or self.classes[base].tag == 0 or self.classes[cls].tag == 0 or not self.derives(cls, base):
        return None
    assigned: dict[str, bool] = {}
    local_names(f.node.kids[2].kids, assigned)
    if param in assigned or param in self.cellvars(f, f.node.kids[2].kids) or not skew_uses(f.node.kids[2], param) or not skew_contracts(self, f.node.kids[2], param, base):
        return None
    # Validate the normal body first. Cloning may narrow an input but cannot make an
    # otherwise unsupported original program compile, or hide its diagnostics.
    if f.ll not in self.compiled and f.ll in self.building:
        return None
    # Reserve before validating the original: its calls can recursively request
    # other seeded clones, and active work must count toward the global budget.
    self.skewclones[f.ll] = True
    self.skewactive[f.ll] = True
    if f.ll not in self.compiled:
        frame = self.save()
        self.modlevel = False
        self.lenient = False
        self.function(f, f.node.kids[2].kids)
        self.restore(frame)
    ts = [t for t in f.ptypes]
    ts[j] = cls
    clone = self.instance(f, ts, [param])
    del self.skewactive[f.ll]
    hot = self.label()
    miss = self.label()
    check = self.label()
    end = self.label()
    value = vals[j]
    self.cbr(self.ins(f"icmp eq ptr {value.v}, null"), miss, check)
    self.place(check)
    tag = self.ins(f"load i64, ptr {value.v}")
    self.cbr(self.ins(f"icmp eq i64 {tag}, {self.classes[cls].tag}"), hot, miss)
    self.place(hot)
    narrow = dict(self.narrowed)
    args = [v for v in vals]
    args[j] = Val(value.v, cls)
    result = self.call_bound(clone, args, want)
    results: list[Val] = []
    edges: list[str] = []
    if not self.term:
        results.append(result)
        edges.append(self.cur)
        self.br(end)
    self.place(miss)
    self.narrowed = dict(narrow)
    result = self.call_bound(f, vals, want)
    if not self.term:
        results.append(result)
        edges.append(self.cur)
        self.br(end)
    self.narrowed = narrow
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return result
    if f.ret == "None":
        return Val("null", "None")
    phi = Ins("phi", f.ret, "")
    for i in range(len(results)):
        self.incoming(phi, results[i].v, edges[i])
    return Val(self.phi(phi), f.ret)
