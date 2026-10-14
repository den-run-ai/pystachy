"""Native call-site feedback for bounded reference-union template arguments.

Offline feedback selects ordinary templates during the initial compilation.
The separate opt-in online path records members in the running native process
and calls an entry compiled and loaded after its site becomes hot.
"""
from __future__ import annotations
import os
from src.pystachy_compiler.analysis import local_names
from src.pystachy_compiler.diagnostics import RAW, shown
from src.pystachy_compiler.ir import FnInfo, Ins, Val
from src.pystachy_compiler.syntax import Node, mentions, names_in
from src.pystachy_compiler.utils import is_callable, targs, umembers, unopt


def online_callback_eligible(self, key: str) -> bool:
    # A Callable adapter can coerce its input and result. Replacing it by a
    # direct function must retain that contract. This tier admits only exact
    # annotated signatures; generic callbacks and coercing adapters fall back.
    split = key.find(" ")
    if split < 0 or not key.startswith("fn[f:"):
        return False
    name = key[5:split - 1]
    if name not in self.funcs or not is_callable(key[split + 1:]):
        return False
    f = self.funcs[name]
    ts = targs(key[split + 1:])
    return not f.generic and f.clo < 0 and f.vararg < 0 and f.kwarg < 0 and f.ptypes == ts[1:] and f.ret == ts[0]


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


def online_note(self, site: str, member: str) -> str:
    return self.rt("pys_online", "ptr", ["ptr " + self.sconst(site), "ptr " + self.sconst(member)])


def online_reference(self, site: str, value: Val) -> str:
    # Argument binding has finished. The observer can return code only for the
    # current member; null/unknown members and failed compilation keep the same
    # generic native call. The indirect call is typed IR, so ordinary exception
    # lowering covers an exception from the newly loaded body without replay.
    end = self.label()
    nonnull = self.label()
    null = self.label()
    pointers: list[str] = []
    edges: list[str] = []
    self.cbr(self.ins(f"icmp eq ptr {value.v}, null"), null, nonnull)
    self.place(null)
    pointers.append(online_note(self, site, "<none>"))
    edges.append(self.cur)
    self.br(end)
    self.place(nonnull)
    tag = self.ins(f"load i64, ptr {value.v}")
    for member in umembers(unopt(value.t)):
        hit = self.label()
        miss = self.label()
        self.cbr(self.ins(f"icmp eq i64 {tag}, {self.utag(member)}"), hit, miss)
        self.place(hit)
        pointers.append(online_note(self, site, member))
        edges.append(self.cur)
        self.br(end)
        self.place(miss)
    pointers.append(online_note(self, site, "<other>"))
    edges.append(self.cur)
    self.br(end)
    self.place(end)
    entry = Ins("phi", "env", "")
    for i in range(len(pointers)):
        self.incoming(entry, pointers[i], edges[i])
    return self.phi(entry)


def online_call(self, site: str, baseline: FnInfo, value: Val) -> Val:
    if is_callable(value.t):
        # Only immutable top-level Callable singletons are registered. Closures,
        # bound methods and unknown values keep the ordinary native call.
        code = self.rt("pys_online_callable", "ptr", ["ptr " + self.sconst(site), "ptr " + value.v])
    else:
        code = online_reference(self, site, value)
    hot = self.label()
    cold = self.label()
    join = self.label()
    self.cbr(self.ins(f"icmp eq ptr {code}, null"), cold, hot)
    narrowed = dict(self.narrowed)
    self.place(hot)
    call = Ins("icall", "int", "")
    call.a = [Val(code, "env"), value]
    self.put(call, 1)
    result = Val(f"%t{call.r[0]}", "int")
    hot_edge = self.cur
    self.br(join)
    self.place(cold)
    self.narrowed = dict(narrowed)
    fallback = self.call_bound(baseline, [value], "int")
    cold_edge = self.cur
    self.br(join)
    self.narrowed = narrowed
    self.place(join)
    merged = Ins("phi", "int", "")
    self.incoming(merged, result.v, hot_edge)
    self.incoming(merged, fallback.v, cold_edge)
    return Val(self.phi(merged), "int")


def gen_online_build(self) -> bool:
    # Called after the complete ordinary baseline has compiled. Delaying the
    # selected template preserves the host's class/template/global numbering;
    # the program's online manifest validates that baseline before publication.
    if not self.online_child or self.online_built:
        return False
    self.online_built = True
    site = self.online_site
    if site not in self.online_candidates or site not in self.online_baselines:
        self.err("online compilation site is missing or has an unsupported signature")
    f = self.online_candidates[site]
    baseline = self.online_baselines[site]
    member = self.online_member
    callable_arg = is_callable(baseline.ptypes[0])
    if callable_arg:
        key = member + " " + baseline.ptypes[0]
        if key not in self.adapters or not online_callback_eligible(self, key):
            self.err("online callback is outside the baseline callable identities")
        if "@cvo." + self.adapters[key][4:] not in self.cvos:
            self.err("online callback has no immutable baseline singleton")
    elif member not in umembers(unopt(baseline.ptypes[0])):
        self.err("online compilation member is outside the baseline union")
    nnp = [f.params[0]] if member in self.classes and self.dispatches(f, f.params[0]) else []
    self.feedback_active[f.ll] = True
    clone = self.instance(f, [member], nnp)
    del self.feedback_active[f.ll]
    if clone.ret != baseline.ret or clone.noret != baseline.noret:
        self.err("online compilation changed the baseline return contract")
    wrapper = FnInfo("<online entry>", "@pystachy_online_entry", f.node, "")
    wrapper.params = [f.params[0]]
    wrapper.ptypes = [baseline.ptypes[0]]
    wrapper.ret = "int"
    wrapper.npos = 1
    wrapper.export = True
    frame = self.save()
    self.modlevel = False
    self.lenient = False
    self.enter(wrapper, [])
    self.fn.ps.append(0)
    value = Val("null", member) if callable_arg else self.uget("%a0", member)
    result = self.call_bound(clone, [value], "int")
    self.ret_(result)
    self.fn.n = self.n
    self.fns.append(self.fn)
    self.compiled[wrapper.ll] = True
    self.restore(frame)
    self.online_entry = wrapper.ll
    self.online_selected_signature = self.online_signatures[site]
    return True


def gen_feedback_call(self, f: FnInfo, vals: list[Val], want: str) -> Val | None:
    if self.feedback_function == "" or shown(f.name) != self.feedback_function or self.rtmode:
        return None
    if not f.generic or f.cls != "" or f.clo >= 0 or f.vararg >= 0 or f.kwarg >= 0 or f.ll in self.feedback_active:
        return None
    js = [j for j in range(len(vals)) if self.reference_union(unopt(vals[j].t)) or ((self.online_host or self.online_child) and is_callable(vals[j].t))]
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
    callable_arg = is_callable(vals[j].t)
    ms: list[str] = []
    if not callable_arg:
        ms = umembers(unopt(vals[j].t))
    self.feedback_active[f.ll] = True
    nnp = [f.params[k] for k in range(len(vals)) if vals[k].t in self.classes and vals[k].v in self.nn and self.dispatches(f, f.params[k])]
    baseline = self.instance(f, [v.t for v in vals], nnp)
    if self.online_host or self.online_child:
        del self.feedback_active[f.ll]
        # One pointer argument: a reference union or immutable Callable object.
        # Unsupported sites retain generic execution and never compile a hot
        # clone in the host, even if offline profile flags are also present.
        if len(vals) != 1 or baseline.ret != "int" or baseline.noret:
            return self.call_bound(baseline, vals, want)
        signature = f.ll + "|0|int|" + baseline.ptypes[0]
        if site not in self.online_signatures and len(self.online_signatures) >= 16:
            return self.call_bound(baseline, vals, want)
        if site in self.online_signatures and self.online_signatures[site] != signature:
            self.err("online call-site identity has conflicting signatures")
        self.online_signatures[site] = signature
        self.online_candidates[site] = f
        self.online_baselines[site] = baseline
        if self.online_child:
            # Reserve the host observer's literal and tag identities without
            # emitting an observer. Later semantic literals keep their original
            # numbers and can import the running host's exact string pointers.
            self.sconst(site)
            if not callable_arg:
                self.sconst("<none>")
                for m in ms:
                    self.utag(m)
                    self.sconst(m)
                self.sconst("<other>")
            return self.call_bound(baseline, vals, want)
        return online_call(self, site, baseline, vals[0])
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
