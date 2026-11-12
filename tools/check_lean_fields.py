#!/usr/bin/env python3
"""Check with Lean that objects under construction have their unflagged fields assigned.

A field that a class's code reads without testing an "is assigned" flag (fl_fields gives it none,
or no read finds it unassigned) must hold a value wherever that code can see the object. An object
is complete once every field that its class's code, and each base class's code, reads unflagged is
assigned: a class's struct is a prefix of each subclass's, so a field keeps its index in each view.
Code sees an object under construction where the function that allocated it, or a function given
it, lets it escape. Obligations, each a Lean payload over one object's field state (set or unset):

- an unflagged read of a field of an object under construction follows a store of the field;
- an object under construction escapes (any use but a field access, a private slot, a comparison,
  a join or a call that a contract covers) only once complete, as far as its view can tell;
- a function given an object under construction (an __init__'s self, or an argument a call passes
  one in) returns normally with its contract's post-condition assigned; each call that passes one
  first assigns the pre-condition and, where the callee lets the argument escape, the fields of
  the object's class that the parameter's class cannot see.

Every other object (a parameter no contract covers, a load from memory, a call's result) is
complete: the function that allocated it let it escape only once complete. Contracts are inferred
(a greatest fixed point of pre- and post-conditions over the call graph), then Lean checks every
function separately with them; a function that Lean rejects gives its callers no contract, so its
calls are escapes, and its callers are checked again (as proved_returns does).
"""
import argparse
from collections import deque
import heapq
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import check_lean_boundary as boundary  # noqa: E402

SET, UNSET, OTHER, STALE = "set", "unset", "other", "stale"
EXCEPTION_HIDDEN = (" cls", " str", " args")  # (exc_object's ExcClass, str(e) and repr(e) text)
CALLS = {"call", "invoke", "icall", "rt", "init"}
KINDS = ("reads", "escapes", "calls", "returns", "flags")
LIMITATIONS = ("Proves, in a finite-tag model, that each field a class's code reads without a flag "
               "test is assigned before that code can see an object under construction; trusts the "
               "inspection's class layouts and classes table, that only compiled allocations make "
               "objects of the program's classes, that complete objects' flags are set only after their "
               "fields, the IR's operand views and typed memory; a closure capturing, or a raw access "
               "of, an object under construction counts as an escape")


def unchecked(layout):
    """The struct indexes a class's code reads without a flag test: its fields without a flag
    (or whose flag only hasattr tests), its class tag and an exception's hidden fields."""
    return {k for k, field in enumerate(layout["fields"])
            if (field == " class" or field in EXCEPTION_HIDDEN or not field.startswith(" "))
            and (field not in layout["flags"] or field in layout["sure"])}


def class_tables(snapshot):
    """Each class's layout, and its view: what its code and its bases' code read unflagged."""
    layouts = snapshot.get("class_layouts")
    classes = snapshot.get("classes")
    boundary.require(isinstance(layouts, dict) and isinstance(classes, dict),
                     "missing class_layouts: inspect with --guard-evidence")
    view = {}
    for name in layouts:
        seen, line = set(), name
        view[name] = set()
        while line in layouts and line not in seen:
            seen.add(line)
            view[name] |= unchecked(layouts[line])
            line = classes.get(line, {}).get("base", "")
    return layouts, view


def init_class(fn, layouts):
    """The class of the object an __init__ method is given (its self), or None."""
    params = fn.get("parameters") or []
    if fn.get("name") == "__init__" and fn.get("symbol", "").startswith("@m.") and params:
        typ = params[0].get("representation")
        if typ in layouts:
            return typ
    return None


def param_class(fn, position, layouts):
    params = fn.get("parameters") or []
    typ = params[position].get("representation") if position < len(params) else None
    return typ if typ in layouts else None


def facts(nodes, keep=None):
    """Forward may-facts of a graph: each location's possible tags at each node, kept only where a
    later node reads the location (a payload or a guard) or keep names it at a node (a probe)."""
    keep = keep or {}
    successors = [boundary.successors(node) for node in nodes]
    predecessors = [[] for _ in nodes]
    for index, targets in enumerate(successors):
        for target in targets:
            predecessors[target].append(index)
    live = [set() for _ in nodes]
    pending = deque(range(len(nodes) - 1, -1, -1))
    queued = [True] * len(nodes)
    while pending:
        index = pending.popleft()
        queued[index] = False
        node = nodes[index]
        later = set().union(*(live[t] for t in successors[index])) if successors[index] else set()
        if node["op"] == "copy":
            needed = node["dst"] in later
            later.discard(node["dst"])
            if needed:
                later.add(node["src"])
        elif node["op"] == "havoc":
            later.discard(node["dst"])
        elif node["op"] in {"payload", "guard"}:
            later.add(node["value"])
        later |= keep.get(index, set())
        if later != live[index]:
            live[index] = later
            for predecessor in predecessors[index]:
                if not queued[predecessor]:
                    queued[predecessor] = True
                    pending.append(predecessor)
    state = [None] * len(nodes)
    state[0] = {}
    pending, queued, work = [0], {0}, 0
    while pending:
        # (in node order: a graph is emitted mostly forward, so few nodes are visited again)
        index = heapq.heappop(pending)
        queued.discard(index)
        known = state[index]
        node = nodes[index]
        out = known
        if node["op"] in {"copy", "havoc"}:
            out = {k: v for k, v in known.items() if k != node["dst"]}
            if node["op"] == "copy" and node["src"] in known:
                out[node["dst"]] = known[node["src"]]
        for edge, target in enumerate(successors[index]):
            moved = out
            if node["op"] == "guard":
                moved = dict(out)
                tested = frozenset(node["tags"])
                if edge == 0:
                    moved[node["value"]] = known[node["value"]] & tested if node["value"] in known else tested
                elif node["value"] in known:
                    moved[node["value"]] = known[node["value"]] - tested
            moved = {k: v for k, v in moved.items() if k in live[target]}
            previous = state[target]
            merged = moved if previous is None else {k: previous[k] | moved[k] for k in previous.keys() & moved.keys()}
            if merged != previous:
                state[target] = merged
                work += len(merged)
                if work > 64 * boundary.MAX_FACTS:
                    raise boundary.Unsupported("field facts exceed the prototype's resource bound")
                if target not in queued:
                    queued.add(target)
                    heapq.heappush(pending, target)
    return state


def loop_blocks(fn):
    """Blocks on a cycle of the block graph, exception edges included (an allocation there may
    run again while a value holds its previous object)."""
    succ = {}
    for b in fn["blocks"]:
        targets = list(b["operations"][-1]["targets"]) if b["operations"] else []
        if b["operations"] and b["operations"][-1]["op"] == "check":
            last = b["operations"][-1]
            targets.append(fn["check_targets"].get(last["descriptor"] or last["text"], ""))
        if b["handler"]:
            targets.append(b["handler"])
        succ[b["label"]] = [t for t in targets if t]
    out = set()
    for start in succ:
        seen, stack = set(), list(succ[start])
        while stack:
            x = stack.pop()
            if x == start:
                out.add(start)
                break
            if x not in seen and x in succ:
                seen.add(x)
                stack.extend(succ[x])
    return out


class Graph:
    def __init__(self):
        self.nodes = []
        self.origins = {}

    def emit(self, node):
        self.nodes.append(node)
        return len(self.nodes) - 1

    def follow(self, node):
        return self.emit(dict(node, next=len(self.nodes) + 1))

    def when(self, value, tag, body):
        """If value's tag is tag, the nodes body() emits (each continuing to the next), then on."""
        guard = self.emit({"op": "guard", "value": value, "tags": [tag], "yes": len(self.nodes) + 1, "no": None})
        body()
        join = self.emit({"op": "jump", "next": None})
        self.nodes[guard]["no"] = len(self.nodes)
        self.nodes[join]["next"] = len(self.nodes)


class Context:
    """One snapshot's tables, and what does not change between rounds of contracts: each
    function's validation and loops, and its graph for the contracts it depends on (its own and
    its direct callees')."""

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.layouts, self.view = class_tables(snapshot)
        self.functions = {f["symbol"]: f for f in snapshot["functions"]}
        self.validated, self.loops, self.graphs, self.callees = {}, {}, {}, {}

    def validate(self, fn):
        symbol = fn["symbol"]
        if symbol not in self.validated:
            try:
                boundary.normalize_snapshot(dict(self.snapshot, functions=[fn]), symbol)
                self.validated[symbol] = None
            except boundary.Unsupported as error:
                self.validated[symbol] = error
            except ValueError as error:
                # (beyond the shared validator's bounds, such as a type name longer than it reads)
                self.validated[symbol] = boundary.Unsupported(f"outside the boundary validator: {error}")
        if self.validated[symbol] is not None:
            raise self.validated[symbol]

    def loop(self, fn):
        if fn["symbol"] not in self.loops:
            self.loops[fn["symbol"]] = loop_blocks(fn)
        return self.loops[fn["symbol"]]

    def graph(self, fn, contracts):
        symbol = fn["symbol"]
        if symbol not in self.callees:
            self.callees[symbol] = {op["text"] for b in fn["blocks"] for op in b["operations"]
                                    if op["op"] in {"call", "invoke"}}
        depends = self.callees[symbol] | {symbol}
        key = (symbol, tuple(sorted((k, tuple(sorted(v[0])), tuple(sorted(v[1])), v[2])
                                    for k, v in contracts.items() if k[0] in depends)))
        if key not in self.graphs:
            try:
                self.graphs[key] = normalize(self, fn, contracts)
            except boundary.Unsupported as error:
                self.graphs[key] = error
        if isinstance(self.graphs[key], boundary.Unsupported):
            raise self.graphs[key]
        return self.graphs[key]


def normalize(ctx, fn, contracts):
    """The function's field-initialization graph, its metadata and probes: node indexes where
    infer_contracts reads the state at each call passing an object under construction, and at
    each return of a function with a contract.

    A field store, a callee's post-condition or an obligation concerns the object a value is.
    Lean's guards narrow only the tested value: a branch for an object the value cannot be still
    needs that object's facts, and a join of a conditional update loses it. So a pass's facts give
    the tags each value may have at each site, which the next pass asserts (a payload Lean checks),
    branching only over those objects, or none where the value is one object; likewise whether an
    allocation's previous object is complete where it runs again."""
    ctx.validate(fn)
    nodes, meta, probes, marks, keep = emit(ctx, fn, contracts, None)
    for _ in range(4):
        # (each pass's facts sharpen the next: identities first, then the fields they update)
        state = facts(nodes, keep)
        known = {key: state[index] or {} for key, index in marks.items()}
        refined, meta, probes, marks, keep = emit(ctx, fn, contracts, known)
        if refined == nodes:
            break
        nodes = refined
    return refined, meta, probes, keep


def emit(ctx, fn, contracts, known):
    layouts, view = ctx.layouts, ctx.view
    symbol = fn["symbol"]
    blocks = [b for b in fn["blocks"] if b["label"] != ""]
    labels = {b["label"] for b in blocks}
    functions = ctx.functions
    slots = set()
    for op in fn["slots"]:
        if op["immediate"] != 2:
            number = op["results"][0]
            slots.add(f"%{op['text']}.def.{number}" if op["immediate"] == 1 else f"%{op['text'] or 'h'}.{number}")
    private = set(slots)
    for block in blocks:
        for op in block["operations"]:
            for pos, arg in enumerate(op["operands"]):
                if arg["value"] in slots and not (pos == 0 and op["op"] in {"mem.load", "mem.store"}):
                    private.discard(arg["value"])
    # The objects under construction: each allocation of a class, and each parameter a contract
    # covers (an __init__'s self, or one a call passes an object under construction in).
    objects, may = {}, {}
    given = sorted(p for (s, p) in contracts if s == symbol)
    params = {f"arg{p}": p for p in given}
    for p in given:
        objects[f"arg{p}"] = param_class(fn, p, layouts)
        may[f"%a{p}"] = {f"arg{p}"}
    for block in blocks:
        for offset, op in enumerate(block["operations"]):
            if op["op"] == "alloc.fixed" and op["type"] in layouts:
                site = f"{block['label']}.{offset}"
                objects[site] = op["type"]
                may[f"%t{op['results'][0]}"] = {site}
    # may[v]: the objects a value or private slot may be (a flow-insensitive closure of copies).
    changed = bool(may)
    while changed:
        changed = False
        for block in blocks:
            for op in block["operations"]:
                args = [a["value"] for a in op["operands"]]
                flows = []
                if op["op"] == "mem.store" and args[0] in private:
                    flows = [(args[0], args[1])]
                elif op["op"] == "mem.load" and args[0] in private:
                    flows = [(f"%t{op['results'][0]}", args[0])]
                elif op["op"] == "phi":
                    flows = [(f"%t{op['results'][0]}", a) for a in args]
                elif op["op"] == "select":
                    flows = [(f"%t{op['results'][0]}", a) for a in args[1:]]
                for dst, src in flows:
                    extra = may.get(src, set()) - may.get(dst, set())
                    if extra:
                        may.setdefault(dst, set()).update(extra)
                        changed = True
    addresses = {}  # field.addr result -> (object value, index, class of the access's view)
    for block in blocks:
        for op in block["operations"]:
            if op["op"] == "field.addr" and op["operands"][0]["value"] in may:
                addresses[f"%t{op['results'][0]}"] = (op["operands"][0]["value"], op["immediate"], op["operands"][0]["type"])

    def flag_field(cls, index):
        """The field whose "is assigned" flag a struct index of class cls is, or None."""
        layout = layouts.get(cls)
        for name, flag in (layout["flags"] if layout else {}).items():
            if flag == index and name in layout["fields"]:
                return layout["fields"].index(name)
        return None
    # A loaded flag (as hasattr tests one) and the bools made of it: where it is true, its field
    # was stored (a flag is set only after its field: fl_fields's setfield, and the obligations
    # at its stores below), and stays assigned.
    conds = {}
    for block in blocks:
        for op in block["operations"]:
            args = [a["value"] for a in op["operands"]]
            result = f"%t{op['results'][0]}" if op["results"] else ""
            if op["op"] == "mem.load" and args[0] in addresses:
                obj, index, cls = addresses[args[0]]
                k = flag_field(cls, index)
                if k is not None:
                    conds[result] = ("flag", obj, k)
            elif op["op"] == "scalar.bin" and op["text"] == "xor" and len(args) == 2 and "true" in args:
                conds[result] = ("not", args[0] if args[1] == "true" else args[1])
            elif op["op"] == "scalar.bin" and op["text"] in {"and", "or"} and len(args) == 2:
                conds[result] = (op["text"], args[0], args[1])
            elif op["op"] == "phi" and len([a for a in args if a != "false"]) == 1:
                conds[result] = ("same", next(a for a in args if a != "false"))

    def stored(value, truth, seen=frozenset()):
        """The (object value, field) pairs whose flags were set where value is truth."""
        if value in seen or value not in conds:
            return set()
        c, seen = conds[value], seen | {value}
        if c[0] == "flag":
            return {(c[1], c[2])} if truth else set()
        if c[0] == "not":
            return stored(c[1], not truth, seen)
        if c[0] == "same":  # (a phi whose other values are false: true only as that one)
            return stored(c[1], True, seen) if truth else set()
        if (c[0] == "and") == truth:
            return stored(c[1], truth, seen) | stored(c[2], truth, seen)
        return set()
    g = Graph()
    counts = dict.fromkeys(KINDS, 0)
    probes = {"calls": [], "returns": [], "wanted": []}
    keep = {}  # node index -> locations a probe or mark reads there (facts keeps them)
    leaks = dict.fromkeys(given, False)
    marks = {}

    def field(o, k):
        return f"F:{o}#{k}"

    def const(tag):
        return "#" + tag

    def src(value):
        return value if value in may else const(OTHER)

    def relevant(o):
        return view[objects[o]]

    def possible(value, key, strict=True):
        """The objects value may be at a site: per the first pass's facts, which Lean checks here
        (strictly, a value never is a previous object of an allocation that runs again, if not
        complete)."""
        marks[key] = len(g.nodes)
        keep.setdefault(len(g.nodes), set()).add(value)
        if known is None:
            return sorted(may.get(value, set())), False
        tags = known.get(key, {}).get(value, frozenset())
        allowed = sorted(tags - {STALE} if strict else tags) or [OTHER]
        index = g.follow({"op": "payload", "value": value, "tags": allowed})
        g.origins[index] = (key[0], key[1], "possible objects", "", -1)
        objs = sorted(t[4:] for t in tags if t.startswith("obj:"))
        return objs, len(tags) == 1 and len(objs) == 1

    def require(value, indexes_of, site, kind):
        objs, single = possible(value, (site[0], site[1], value, kind))
        for o in objs:
            def body(o=o):
                for k in sorted(indexes_of(o)):
                    index = g.follow({"op": "payload", "value": field(o, k), "tags": [SET]})
                    g.origins[index] = (site[0], site[1], kind, o, k)
                    counts[kind] += 1
                if kind == "escapes":
                    # (complete from here on: these obligations show it, or the function is rejected;
                    # so one unproved escape is not reported again at each later use)
                    for k in sorted(relevant(o)):
                        g.follow({"op": "copy", "dst": field(o, k), "src": const(SET)})
            if single:
                body()
            else:
                g.when(value, "obj:" + o, body)
        if kind == "escapes":
            for p in given:
                if f"arg{p}" in objs:
                    leaks[p] = True

    def assign(value, indexes_of, key, strict=True):
        objs, single = possible(value, key, strict)
        for o in objs:
            def body(o=o):
                for k in sorted(indexes_of(o) & relevant(o)):
                    g.follow({"op": "copy", "dst": field(o, k), "src": const(SET)})
            if single:
                body()
            else:
                g.when(value, "obj:" + o, body)

    in_loop = ctx.loop(fn)
    in_loop_objects = {o for o in objects if o not in params and o.rsplit(".", 1)[0] in in_loop}
    tags = [SET, UNSET, OTHER, STALE] + ["obj:" + o for o in sorted(objects)]
    for tag in tags:
        g.emit({"op": "guard", "value": const(tag), "tags": [tag], "yes": None, "no": None})
    stop = g.emit({"op": "stop"})
    for index in range(len(tags)):
        g.nodes[index]["yes"] = index + 1 if index + 1 < len(tags) else stop + 1
        g.nodes[index]["no"] = stop
    for value in sorted(v for v in may if v in private):
        g.follow({"op": "copy", "dst": value, "src": const(OTHER)})
    for n in range(len(fn["parameters"])):
        if f"%a{n}" in may:
            g.follow({"op": "copy", "dst": f"%a{n}", "src": const(f"obj:arg{n}" if n in given else OTHER)})
    for o in sorted(objects):
        # (no object of an allocation exists before it runs: as good as complete; a parameter's
        # holds its pre-condition)
        pre = contracts[(symbol, params[o])][0] if o in params else None
        for k in sorted(relevant(o)):
            g.follow({"op": "copy", "dst": field(o, k), "src": const(SET if pre is None or k in pre else UNSET)})
    phis = {}
    for block in blocks:
        for op in block["operations"]:
            if op["op"] == "phi" and f"%t{op['results'][0]}" in may:
                phis.setdefault(block["label"], []).append(op)
    starts = {}

    def goto(target, source):
        return ("edge", source, target)

    g.emit({"op": "jump", "next": goto(blocks[0]["label"], None)})
    for block in blocks:
        label = block["label"]
        starts[label] = len(g.nodes)
        handler = block["handler"] if block["handler"] in labels else ""
        for offset, op in enumerate(block["operations"]):
            kind, args = op["op"], [a["value"] for a in op["operands"]]
            results = [f"%t{r}" for r in op["results"]]
            site = (label, offset)
            if handler:
                g.emit({"op": "choice", "yes": len(g.nodes) + 1, "no": goto(handler, label)})
            if kind == "phi":
                continue
            uses = [(pos, value) for pos, value in enumerate(args) if value in may or value in addresses]
            if kind == "alloc.fixed" and op["type"] in layouts:
                o = f"{label}.{offset}"
                if o in in_loop_objects:
                    # (values holding the previous object: other where it is complete, else stale;
                    # where the first pass finds it complete, Lean checks that instead)
                    holders = sorted(v for v, objs in may.items() if o in objs)
                    key = (label, offset, "", "previous")
                    marks[key] = len(g.nodes)
                    keep.setdefault(len(g.nodes), set()).update(field(o, k) for k in relevant(o))
                    before = (known or {}).get(key, {})
                    if known is not None and all(before.get(field(o, k)) == frozenset([SET]) for k in relevant(o)):
                        for k in sorted(relevant(o)):
                            index = g.follow({"op": "payload", "value": field(o, k), "tags": [SET]})
                            g.origins[index] = (label, offset, "previous allocation complete", o, k)
                        for v in holders:
                            g.when(v, "obj:" + o, lambda v=v: g.follow({"op": "copy", "dst": v, "src": const(OTHER)}))
                    else:
                        tests = [g.emit({"op": "guard", "value": field(o, k), "tags": [SET], "yes": len(g.nodes) + 1, "no": None})
                                 for k in sorted(relevant(o))]
                        for v in holders:
                            g.when(v, "obj:" + o, lambda v=v: g.follow({"op": "copy", "dst": v, "src": const(OTHER)}))
                        done = g.emit({"op": "jump", "next": None})
                        for t in tests:
                            g.nodes[t]["no"] = len(g.nodes)
                        for v in holders:
                            g.when(v, "obj:" + o, lambda v=v: g.follow({"op": "copy", "dst": v, "src": const(STALE)}))
                        g.nodes[done]["next"] = len(g.nodes)
                for k in sorted(relevant(o)):
                    g.follow({"op": "copy", "dst": field(o, k), "src": const(UNSET)})
                g.follow({"op": "copy", "dst": results[0], "src": const("obj:" + o)})
                continue
            if kind == "field.addr" and results and results[0] in addresses:
                continue
            after = []
            if kind == "mem.load" and args[0] in addresses:
                obj, k, cls = addresses[args[0]]
                boundary.require(cls in layouts, "field read through an unknown class view")
                if k in unchecked(layouts[cls]):
                    require(obj, lambda o, k=k: {k}, site, "reads")
                uses = [u for u in uses if u[0] != 0]
            elif kind == "mem.load" and args[0] in private:
                if results[0] in may:
                    g.follow({"op": "copy", "dst": results[0], "src": args[0]})
                uses = []
            elif kind == "mem.store" and args[0] in addresses:
                obj, k, cls = addresses[args[0]]
                flagged = flag_field(cls, k)
                if flagged is not None:
                    # (a flag is set only after its field: what a test of it relies on)
                    require(obj, lambda o, flagged=flagged: {flagged} & relevant(o), site, "flags")
                after.append(lambda obj=obj, k=k, site=site: assign(obj, lambda o: {k}, (site[0], site[1], obj, "store")))
                uses = [u for u in uses if u[0] != 0]
            elif kind == "mem.store" and args[0] in private:
                if args[0] in may:
                    g.follow({"op": "copy", "dst": args[0], "src": src(args[1])})
                uses = []
            elif kind == "mach.store" and args and args[0] in may:
                # (a raw store into the object; at offset 0 of a tagged class, its class tag)
                if op["immediate"] == 0:
                    after.append(lambda args=args, site=site: assign(
                        args[0], lambda name: {0} if layouts[objects[name]]["fields"][:1] == [" class"] else set(),
                        (site[0], site[1], args[0], "tag")))
                uses = [u for u in uses if u[0] != 0]
            elif kind == "mach.load" and args and args[0] in may:
                if op["immediate"] != 0:
                    raise boundary.Unsupported("raw read of an object under construction")
                require(args[0], lambda o: {0} & relevant(o), site, "reads")
                uses = [u for u in uses if u[0] != 0]
            elif kind == "ptr.cmp":
                uses = []
            elif kind == "select" and results[0] in may:
                choice = g.emit({"op": "choice", "yes": len(g.nodes) + 1, "no": None})
                first = g.emit({"op": "copy", "dst": results[0], "src": src(args[1]), "next": None})
                g.nodes[choice]["no"] = len(g.nodes)
                g.follow({"op": "copy", "dst": results[0], "src": src(args[2])})
                g.nodes[first]["next"] = len(g.nodes)
                uses = [u for u in uses if u[0] == 0]
            callee = functions.get(op["text"]) if kind in {"call", "invoke"} else None
            if callee is not None:
                covered = []
                for pos, value in uses:
                    if value not in may or pos >= len(callee.get("parameters") or []):
                        continue
                    contract = contracts.get((op["text"], pos))
                    if contract is None:
                        # (a call no contract covers yet: one, if the object may be incomplete here)
                        if param_class(callee, pos, layouts) is not None:
                            probes["wanted"].append((len(g.nodes), op["text"], pos, value))
                            keep.setdefault(len(g.nodes), set()).update(
                                {value} | {field(o, k) for o in may[value] for k in relevant(o)})
                        continue
                    pre, post, callee_leaks = contract
                    cls = param_class(callee, pos, layouts)
                    probes["calls"].append((len(g.nodes), op["text"], pos, value))
                    keep.setdefault(len(g.nodes), set()).update(
                        {value} | {field(o, k) for o in may[value] for k in view[cls]})
                    require(value, lambda o, pre=pre, cls=cls, callee_leaks=callee_leaks: (pre & view[cls]) | (
                        (relevant(o) - view[cls]) if callee_leaks else set()), site, "calls")
                    if callee_leaks:
                        for p in given:
                            if f"arg{p}" in may.get(value, set()):
                                leaks[p] = True
                    after.append(lambda value=value, post=post, site=site, pos=pos: assign(
                        value, lambda o: post, (site[0], site[1], value, f"post{pos}")))
                    covered.append((pos, value))
                uses = [u for u in uses if u not in covered]
            for pos, value in uses:
                obj = addresses[value][0] if value in addresses else value
                require(obj, relevant, site, "escapes")
            if kind in {"ret", "ret.none"}:
                for p in given:
                    probes["returns"].append((len(g.nodes), p))
                    keep.setdefault(len(g.nodes), set()).update(field(f"arg{p}", k) for k in relevant(f"arg{p}"))
                    for k in sorted(contracts[(symbol, p)][1]):
                        index = g.follow({"op": "payload", "value": field(f"arg{p}", k), "tags": [SET]})
                        g.origins[index] = (label, offset, "returns", f"arg{p}", k)
                        counts["returns"] += 1
            for result in results:
                if result in may and kind not in {"mem.load", "select"}:
                    g.follow({"op": "copy", "dst": result, "src": const(OTHER)})
            targets = op["targets"]
            if kind in CALLS and len(targets) == 2:
                # (its normal successor, and the landing block an exception reaches)
                g.emit({"op": "choice", "yes": len(g.nodes) + 1, "no": goto(targets[1], label)})
                for action in after:
                    action()
                g.emit({"op": "jump", "next": goto(targets[0], label)})
                continue
            for action in after:
                action()
            if kind == "br":
                g.emit({"op": "jump", "next": goto(targets[0], label)})
            elif kind in {"cbr", "check"}:
                if kind == "check":
                    yes, no = fn["check_targets"][op["descriptor"] or op["text"]], targets[0]
                else:
                    yes, no = targets
                choice = g.emit({"op": "choice", "yes": len(g.nodes) + 1, "no": None})
                for truth, target in ((True, yes), (False, no)):
                    if not truth:
                        g.nodes[choice]["no"] = len(g.nodes)
                    for obj, k in sorted(stored(args[0], truth)):
                        assign(obj, lambda o, k=k: {k}, (label, offset, obj, f"flag {k} {truth}"), strict=False)
                    g.emit({"op": "jump", "next": goto(target, label)})
            elif kind in {"ret", "ret.none", "unreachable"} or (kind in {"raise", "throw"} and not targets):
                g.emit({"op": "stop"})
            elif targets:
                for target in targets[:-1]:
                    g.emit({"op": "choice", "yes": goto(target, label), "no": len(g.nodes) + 1})
                g.emit({"op": "jump", "next": goto(targets[-1], label)})
    # Each edge: its target's phi copies (parallel: through temporaries), then the block.
    edges = {}

    def edge_node(source, target):
        key = (source, target)
        if key in edges:
            return edges[key]
        boundary.require(target in starts, f"edge to an unknown block: {target}")
        start = len(g.nodes)
        moves = []
        for op in phis.get(target, []):
            value = None
            for arg, pred in zip(op["operands"], op["targets"], strict=True):
                if pred == source:
                    value = arg["value"]
            boundary.require(value is not None, "phi has no incoming value for an edge")
            temp = f"%phi.{op['results'][0]}"
            g.follow({"op": "copy", "dst": temp, "src": src(value)})
            moves.append((f"%t{op['results'][0]}", temp))
        for dst, temp in moves:
            g.follow({"op": "copy", "dst": dst, "src": temp})
        g.emit({"op": "jump", "next": starts[target]})
        edges[key] = start
        return start
    for node in list(g.nodes):
        for key in ("yes", "no", "next"):
            target = node.get(key)
            if isinstance(target, tuple):
                node[key] = edge_node(target[1], target[2])
    nodes = g.nodes
    boundary.require(all(isinstance(t, int) and 0 <= t < len(nodes) for n in nodes for t in boundary.successors(n)),
                     "invalid field graph edge")
    # Nodes that nothing reaches cannot run: dropped, as the other adapters drop them.
    reached, pending = {0}, [0]
    while pending:
        for target in boundary.successors(nodes[pending.pop()]):
            if target not in reached:
                reached.add(target)
                pending.append(target)
    renumber = {old: new for new, old in enumerate(sorted(reached))}
    nodes = [nodes[old] for old in sorted(reached)]
    for node in nodes:
        for key in ("yes", "no", "next"):
            if key in node:
                node[key] = renumber[node[key]]
    boundary.require(len(nodes) <= boundary.MAX_NODES, "field graph exceeds resource bound")
    origins = {renumber[i]: site for i, site in g.origins.items() if i in renumber}
    probes = {"calls": [(renumber[i], *rest) for i, *rest in probes["calls"] if i in renumber],
              "wanted": [(renumber[i], *rest) for i, *rest in probes["wanted"] if i in renumber],
              "returns": [(renumber[i], p) for i, p in probes["returns"] if i in renumber]}
    marks = {key: renumber[i] for key, i in marks.items() if i in renumber}
    keep = {renumber[i]: locations for i, locations in keep.items() if i in renumber}
    meta = {"function": symbol, "objects": dict(objects), "leaks": leaks,
            "counts": counts, "obligations": sum(counts.values()), "origins": origins}
    return nodes, meta, probes, marks, keep


def relevant_function(fn, layouts, contracts):
    """Whether fn allocates an object of a class, is an __init__ or is given a contract."""
    if init_class(fn, layouts) is not None or any(s == fn["symbol"] for s, _ in contracts):
        return True
    return any(op["op"] == "alloc.fixed" and op["type"] in layouts for b in fn["blocks"] for op in b["operations"])


def infer_contracts(ctx, proved, refused=frozenset()):
    """Contracts (pre, post, leaks) of the parameters given objects under construction: every
    __init__'s self, and each (function, position) that a call passes one in, unless refused.
    A greatest fixed point; Lean checks each function with them afterwards."""
    layouts, view, functions, snapshot = ctx.layouts, ctx.view, ctx.functions, ctx.snapshot

    def supported(symbol):
        # (a function beyond the shared validator never gets a contract: its calls are escapes)
        try:
            ctx.validate(functions[symbol])
            return True
        except boundary.Unsupported:
            return False
    keys = {(fn["symbol"], 0) for fn in snapshot["functions"] if init_class(fn, layouts) is not None}
    keys = {k for k in keys if k[0] in proved and supported(k[0])} - set(refused)
    for _ in range(64):
        contracts = {k: (set(view[param_class(functions[k[0]], k[1], layouts)]),) * 2 + (False,) for k in keys}
        for _ in range(64):
            pres = {k: set(contracts[k][0]) for k in contracts}
            posts = {k: set(contracts[k][1]) for k in contracts}
            leaks = {k: False for k in contracts}
            wanted = set()
            for fn in snapshot["functions"]:
                if not relevant_function(fn, layouts, contracts):
                    continue
                try:
                    nodes, meta, probes, keep = ctx.graph(fn, contracts)
                except boundary.Unsupported:
                    for k in contracts:
                        if k[0] == fn["symbol"]:
                            posts[k] = set()
                            leaks[k] = True
                    continue
                state = facts(nodes, keep)
                for index, callee, pos, value in probes["wanted"]:
                    known = state[index] or {}
                    for tag in known.get(value, ()):
                        o = tag[4:]
                        if tag.startswith("obj:") and any(known.get(f"F:{o}#{k}") != frozenset([SET])
                                                          for k in view[meta["objects"][o]]):
                            wanted.add((callee, pos))
                for index, callee, pos, value in probes["calls"]:
                    known = state[index] or {}
                    cls = param_class(functions[callee], pos, layouts)
                    for tag in known.get(value, ()):
                        if tag.startswith("obj:"):
                            o = tag[4:]
                            pres[(callee, pos)] &= {k for k in view[cls] if known.get(f"F:{o}#{k}") == frozenset([SET])}
                for p, value in meta["leaks"].items():
                    leaks[(fn["symbol"], p)] |= value
                for index, p in probes["returns"]:
                    known = state[index]
                    if known is not None:
                        posts[(fn["symbol"], p)] &= {k for k in contracts[(fn["symbol"], p)][1]
                                                     if known.get(f"F:arg{p}#{k}") == frozenset([SET])}
            updated = {k: (pres[k], posts[k], leaks[k] or contracts[k][2]) for k in contracts}
            if updated == contracts:
                break
            contracts = updated
        else:
            raise boundary.Unsupported("field contracts did not converge")
        new = {w for w in wanted if w[0] in proved and w not in refused and supported(w[0])} - keys
        if not new:
            return contracts, wanted
        keys |= new
    raise boundary.Unsupported("field contract discovery did not converge")


def check_all(snapshot, checker=boundary.DEFAULT_CHECKER):
    """Check every function that allocates an object of a class or is given one under
    construction, removing the contracts of rejected functions until none is rejected."""
    ctx = Context(snapshot)
    layouts = ctx.layouts
    proved = {fn["symbol"] for fn in snapshot["functions"]}
    dropped = {}  # (a rejected function given contracts, its result: reported, and no longer assumed)
    while True:
        contracts, wanted = infer_contracts(ctx, proved)
        results, rejected = [], set()
        for fn in snapshot["functions"]:
            if fn["symbol"] in dropped and (init_class(fn, layouts) is not None
                                            or any(w[0] == fn["symbol"] for w in wanted)):
                # (still given an object under construction, which it was rejected for)
                results.append(dropped[fn["symbol"]])
                continue
            if not relevant_function(fn, layouts, contracts):
                continue
            try:
                nodes, meta, _, _ = ctx.graph(fn, contracts)
                origins = meta["origins"]
                meta = {k: v for k, v in meta.items() if k != "origins"}
                candidate = {"schema_version": 2, "program": {"entry": 0, "nodes": nodes},
                             "certificate": boundary.infer_certificate(nodes)}
                ok = boundary.run_checker(checker, boundary.encode(candidate), {
                    "nodes": len(nodes), "payloads": sum(node["op"] == "payload" for node in nodes)})
                failures = [] if ok else explain(nodes, candidate["certificate"], origins)
                refused = {callee for callee in (refusing_callee(ctx, fn, f["site"]) for f in failures)}
                if failures and None not in refused:
                    # (each failure is an escape into a function the validator refuses)
                    results.append(dict(meta, status="unsupported",
                                        why=f"gives an object under construction to unsupported {sorted(refused)}"))
                else:
                    results.append(dict(meta, status="accepted" if ok else "rejected",
                                        why=failures[0] if failures else None))
            except boundary.Unsupported as error:
                results.append({"function": fn["symbol"], "status": "unsupported", "why": str(error)})
                ok = False
            if not ok and any(s == fn["symbol"] for s, _ in contracts):
                rejected.add(fn["symbol"])
                dropped[fn["symbol"]] = results[-1]
        if not rejected & proved:
            return results, contracts
        proved -= rejected


def program_report(results):
    """A program's field obligations: proved only in functions Lean accepts; an unsupported
    function's are not counted, and makes the program unsupported."""
    status = max((r["status"] for r in results), key=boundary.SEVERITY.index, default="accepted")
    return {"field_status": status,
            "field_obligations": sum(r.get("obligations", 0) for r in results),
            "proved_field_obligations": sum(r.get("obligations", 0) for r in results if r["status"] == "accepted"),
            "field_functions": len(results),
            "unproved_field_functions": [{"function": r["function"], "status": r["status"], "why": r["why"]}
                                         for r in results if r["status"] != "accepted"]}


def explain(nodes, certificate, origins):
    """The payloads the inferred facts do not cover: where Lean's check fails."""
    out = []
    for index, node in enumerate(nodes):
        if node["op"] != "payload":
            continue
        known = {v: set(t) for v, t in certificate[index]} if index < len(certificate) else {}
        tags = known.get(node["value"])
        if tags is None or not tags <= set(node["tags"]):
            out.append({"node": index, "site": origins.get(index), "value": node["value"], "known": sorted(tags or [])})
    return out or [{"node": None, "site": None, "value": None, "known": []}]


def refusing_callee(ctx, fn, site):
    """The callee of the call at an obligation's site, if the validator refuses it; else None."""
    if not site:
        return None
    block = next((b for b in fn["blocks"] if b["label"] == site[0]), None)
    op = block["operations"][site[1]] if block is not None and 0 <= site[1] < len(block["operations"]) else None
    if op is None or op["op"] not in {"call", "invoke"} or op["text"] not in ctx.functions:
        return None
    try:
        ctx.validate(ctx.functions[op["text"]])
        return None
    except boundary.Unsupported:
        return op["text"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--checker", default=str(boundary.DEFAULT_CHECKER))
    args = parser.parse_args(argv)
    snapshot, _ = boundary.read_snapshot(Path(args.snapshot), boundary.MAX_PROGRAM_BYTES)
    results, contracts = check_all(snapshot, Path(args.checker))
    report = {"limitations": LIMITATIONS, "functions": results,
              "contracts": [{"function": s, "parameter": p, "pre": sorted(a), "post": sorted(b), "leaks": c}
                            for (s, p), (a, b, c) in sorted(contracts.items())]}
    print(json.dumps(report, indent=1, default=list))
    return boundary.OUTCOMES[program_report(results)["field_status"]]


if __name__ == "__main__":
    sys.exit(main())
