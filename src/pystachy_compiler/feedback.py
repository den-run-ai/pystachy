"""Native call-site feedback for bounded reference-union template arguments.

This is offline type feedback: both the generic body and selected concrete body
use the ordinary compiler. It is not an interpreter or an online tracing JIT.
"""
from __future__ import annotations
import os
from src.pystachy_compiler.analysis import local_names
from src.pystachy_compiler.diagnostics import RAW, shown
from src.pystachy_compiler.ir import FnInfo, Ins, Val
from src.pystachy_compiler.syntax import Node, mentions, names_in
from src.pystachy_compiler.utils import umembers, unopt


def load_feedback() -> dict[str, str]:
    out: dict[str, str] = {}
    path = os.getenv("PYSTACHY_FEEDBACK_PROFILE", "")
    if path == "":
        return out
    try:
        fp = open(path, "r", encoding=RAW)
        data = fp.read(65537)
        fp.close()
    except OSError:
        return out
    lines = data.splitlines()
    if len(data) > 65536 or len(lines) == 0 or lines[0] != "pystachy-feedback-v1":
        return out
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    best: dict[str, str] = {}
    seen: dict[str, bool] = {}
    bad: dict[str, bool] = {}
    for line in lines[1:]:
        row = line.split("\t")
        if len(row) != 3:
            return {}
        site, member, count = row
        if len(site) > 500 or len(member) > 200 or len(count) == 0 or len(count) > 12:
            return {}
        for c in count:
            if not "0" <= c <= "9":
                return {}
        key = site + "\t" + member
        if key in seen:
            bad[site] = True
        seen[key] = True
        n = int(count)
        totals[site] = totals.get(site, 0) + n
        if n > counts.get(site, 0):
            counts[site] = n
            best[site] = member
    for site in totals:
        if site not in bad and totals[site] >= 100 and counts.get(site, 0) * 100 >= totals[site] * 90:
            out[site] = best[site]
    return out


def feedback_safe_body(body: Node, param: str) -> bool:
    # A concrete input can narrow the inferred type of aliases and constructor
    # results. Do not then rebind those locals under a narrower contract. A local
    # annotation keeps its own contract; a single assignment inside a loop is
    # still one binding site. This is conservative syntactic eligibility, not an
    # analysis of arbitrary forwarded helpers or their mutable object contracts.
    nodes = [body]
    annotated: dict[str, int] = {}
    bindings: dict[str, int] = {}
    assignments: list[Node] = []
    i = 0
    while i < len(nodes):
        n = nodes[i]
        i += 1
        if len(nodes) > 4096 or n.kind in ["def", "lambda", "class", "subclass", "global", "nonlocal", "walrus"]:
            return False
        if n.kind == "annassign" and n.kids[0].kind == "name":
            name = n.kids[0].s
            if name not in annotated or n.line < annotated[name]:
                annotated[name] = n.line
        if n.kind in ["assign", "annassign", "augassign", "for", "del"]:
            assignments.append(n)
            targets = n.kids[:-1] if n.kind == "assign" else n.kids if n.kind == "del" else n.kids[:1]
            for target in targets:
                names: list[str] = []
                names_in(target, names)
                for name in names:
                    bindings[name] = bindings.get(name, 0) + 1
        nodes.extend(n.kids)
    # A later annotation cannot repair an earlier inferred alias in a clone.
    # Same-line assignment/annotation order is conservatively ineligible too.
    for n in assignments:
        if n.kind == "annassign":
            continue
        targets = n.kids[:-1] if n.kind == "assign" else n.kids if n.kind == "del" else n.kids[:1]
        for target in targets:
            names: list[str] = []
            names_in(target, names)
            for name in names:
                if name in annotated and n.line <= annotated[name]:
                    del annotated[name]
    tainted = [param]
    changed = True
    while changed:
        changed = False
        for n in assignments:
            if n.kind != "assign" or not mentions(n.kids[-1], tainted):
                continue
            for target in n.kids[:-1]:
                names: list[str] = []
                names_in(target, names)
                for name in names:
                    if name not in annotated and name not in tainted:
                        tainted.append(name)
                        changed = True
    for name in tainted:
        if bindings.get(name, 0) > 1:
            return False
    for n in nodes:
        if n.kind in ["list", "tuple", "dict", "set", "listcomp", "dictcomp", "setcomp", "nestedcomp", "with"] and mentions(n, tainted):
            return False
        if n.kind == "for" and mentions(n.kids[1], tainted):
            return False
        if n.kind in ["assign", "annassign", "augassign"]:
            targets = n.kids[:-1] if n.kind == "assign" else n.kids[:1]
            for target in targets:
                # Fixed scalar field settings (lexer.whitespace_split = True)
                # preserve their contracts. Other dependency stores may change
                # an inferred container item or object field contract.
                if target.kind != "name" and mentions(target, tainted):
                    if target.kind != "attr" or n.kind != "assign" or n.kids[-1].kind not in ["True", "False", "int", "float", "str", "None"]:
                        return False
    return True


def feedback_note(self, site: str, member: str) -> None:
    self.rt("pys_feedback", "void", ["ptr " + self.sconst(site), "ptr " + self.sconst(member)])


def gen_feedback_call(self, f: FnInfo, vals: list[Val], want: str) -> Val | None:
    if self.feedback_function == "" or shown(f.name) != self.feedback_function or self.rtmode:
        return None
    if not f.generic or f.cls != "" or f.clo >= 0 or f.vararg >= 0 or f.kwarg >= 0 or f.ll in self.feedback_active:
        return None
    js = [j for j in range(len(vals)) if self.reference_union(unopt(vals[j].t))]
    if len(js) != 1:
        return None
    j = js[0]
    if f.ptypes[j] != "":
        return None
    assigned: dict[str, bool] = {}
    local_names(f.node.kids[2].kids, assigned)
    if f.params[j] in assigned or f.params[j] in self.cellvars(f, f.node.kids[2].kids):
        return None
    if not feedback_safe_body(f.node.kids[2], f.params[j]):
        return None
    # Caller types distinguish contexts even when the source call line is shared.
    site = shown(self.curfn.name) + "(" + ",".join(self.curfn.ptypes) + "):" + str(self.line) + ":" + shown(f.name) + ":" + f.params[j]
    if len(site) > 500:
        return None
    ms = umembers(unopt(vals[j].t))
    self.feedback_active[f.ll] = True
    nnp = [f.params[k] for k in range(len(vals)) if vals[k].t in self.classes and vals[k].v in self.nn and self.dispatches(f, f.params[k])]
    baseline = self.instance(f, [v.t for v in vals], nnp)
    chosen = self.feedback.get(site, "")
    member = ""
    for m in ms:
        if m == chosen:
            member = m
    clone = baseline
    cnnp = [p for p in nnp]
    if member in self.classes and f.params[j] not in cnnp and self.dispatches(f, f.params[j]):
        cnnp.append(f.params[j])
    key = f.ll + ":" + ",".join([member if k == j else vals[k].t for k in range(len(vals))]) + " " + ",".join(cnnp)
    if member != "" and (key in self.feedback_clones or len(self.feedback_clones) < 16):
        self.feedback_clones[key] = True
        ts = [v.t for v in vals]
        ts[j] = member
        clone = self.instance(f, ts, cnnp)
        if clone.ret != baseline.ret or clone.noret != baseline.noret:
            member = ""
    else:
        member = ""
    del self.feedback_active[f.ll]
    value = vals[j]
    if self.feedback_record:
        end = self.label()
        nonnull = self.label()
        null = self.label()
        self.cbr(self.ins(f"icmp eq ptr {value.v}, null"), null, nonnull)
        self.place(null)
        feedback_note(self, site, "<none>")
        self.br(end)
        self.place(nonnull)
        tag = self.ins(f"load i64, ptr {value.v}")
        for m in ms:
            hit = self.label()
            nxt = self.label()
            self.cbr(self.ins(f"icmp eq i64 {tag}, {self.utag(m)}"), hit, nxt)
            self.place(hit)
            feedback_note(self, site, m)
            self.br(end)
            self.place(nxt)
        feedback_note(self, site, "<other>")
        self.br(end)
        self.place(end)
    if member == "":
        return self.call_bound(baseline, vals, want)
    check = self.label()
    hot = self.label()
    miss = self.label()
    end = self.label()
    self.cbr(self.ins(f"icmp eq ptr {value.v}, null"), miss, check)
    self.place(check)
    tag = self.ins(f"load i64, ptr {value.v}")
    self.cbr(self.ins(f"icmp eq i64 {tag}, {self.utag(member)}"), hot, miss)
    narrow = dict(self.narrowed)
    results: list[Val] = []
    edges: list[str] = []
    self.place(hot)
    if self.feedback_counters:
        feedback_note(self, site, "<hot>")
    args = [v for v in vals]
    args[j] = self.uget(value.v, member)
    r = self.call_bound(clone, args, want)
    if not self.term:
        results.append(r)
        edges.append(self.cur)
        self.br(end)
    self.place(miss)
    self.narrowed = dict(narrow)
    if self.feedback_counters:
        feedback_note(self, site, "<miss>")
    r = self.call_bound(baseline, vals, want)
    if not self.term:
        results.append(r)
        edges.append(self.cur)
        self.br(end)
    self.narrowed = narrow
    self.place(end)
    if len(results) == 0:
        self.unreachable()
        return r
    if baseline.ret == "None":
        return Val("null", "None")
    phi = Ins("phi", baseline.ret, "")
    for i in range(len(results)):
        self.incoming(phi, results[i].v, edges[i])
    return Val(self.phi(phi), baseline.ret)
