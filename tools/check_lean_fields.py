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

A closure's cells (closure_shapes) are private slots of the function that allocates them until
an environment holding one escapes, where the cell is published: the objects it holds escape,
so does each one stored into it later, and each later load may give another, complete object (a
nonlocal assignment by other code). A direct call of a closure function, given an environment
none of whose cells is published, is covered by a contract for each cell holding an object under
construction, which the closure function, loading the cell from its environment, is checked with;
so is an icall of a Callable the function made, through an adapter that only passes it on.
"""
import argparse
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
               "fields, the closure layout (cells, environments and Callables), the IR's operand views and "
               "typed memory; a Callable that escapes lets its environment's objects escape, and a raw "
               "access of an object under construction counts as an escape")


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


def holder(position):
    """The object a contract's position gives a function: a parameter's (arg<n>), or the one in the
    cell at word i of a closure function's environment (env<i>)."""
    return f"arg{position}" if isinstance(position, int) else position


def private_slots(fn):
    """The function's stack slots that only loads and stores use (never their address)."""
    slots = set()
    for op in fn["slots"]:
        if op["immediate"] != 2:
            number = op["results"][0]
            slots.add(f"%{op['text']}.def.{number}" if op["immediate"] == 1 else f"%{op['text'] or 'h'}.{number}")
    private = set(slots)
    for block in fn["blocks"]:
        for op in block["operations"]:
            for pos, arg in enumerate(op["operands"]):
                if arg["value"] in slots and not (pos == 0 and op["op"] in {"mem.load", "mem.store"}):
                    private.discard(arg["value"])
    return private


def adapter_targets(functions):
    """Each Callable adapter (the code word of a Callable made of a def or lambda: @cv.N) that gives
    its environment, its first parameter, only to one call of a closure function, as that call's
    environment -> the closure function."""
    out = {}
    for symbol, fn in functions.items():
        params = fn.get("parameters") or []
        if not params or not str(params[0].get("representation", "")).startswith("fn[c:"):
            continue
        private = private_slots(fn)
        carried, changed = {"%a0"}, True
        while changed:
            changed = False
            for block in fn["blocks"]:
                for op in block["operations"]:
                    args = [a["value"] for a in op["operands"]]
                    if op["op"] == "mem.store" and args[0] in private and args[1] in carried and args[0] not in carried:
                        carried.add(args[0])
                        changed = True
                    elif op["op"] == "mem.load" and args[0] in carried and op["results"] and f"%t{op['results'][0]}" not in carried:
                        carried.add(f"%t{op['results'][0]}")
                        changed = True
        calls, ok = set(), True
        for block in fn["blocks"]:
            for op in block["operations"]:
                for pos, arg in enumerate(op["operands"]):
                    if arg["value"] not in carried:
                        continue
                    if op["op"] in {"mem.load", "mem.store"} and pos == 0 and arg["value"] in private:
                        continue
                    if op["op"] == "mem.store" and pos == 1 and op["operands"][0]["value"] in private:
                        continue
                    callee = functions.get(op["text"]) if op["op"] in {"call", "invoke"} and pos == 0 else None
                    if callee is not None and (callee.get("parameters") or [{}])[0].get("representation") == "env":
                        calls.add(op["text"])
                        continue
                    ok = False
        if ok and len(calls) == 1:
            out[symbol] = next(iter(calls))
    return out


def closure_shapes(fn, private, loops, adapters=None):
    """A function's closure cells and environments, as gen_function_body and closure() make them.

    A variable that a function's defs and lambdas take lives in a cell: a word the function
    allocates as it begins (rt alloc; a second word, if any, holds a number's identity box), which
    loads and stores at the cell itself read and write. A def or lambda's environment is an
    allocation whose words hold the cells it takes (and default values); its closure function is
    given it (its .env parameter) and loads each cell from its word. Returns a dict:

    - cells: each cell pointer -> its content location: C:%tN for a cell the function allocates,
      C:env<i> for the one it loads from word i of its own environment;
    - envs: each environment the function allocates -> {word: content location of its cell};
    - env_ops: (block, offset) -> [(operand, value, closure function or None)] for each other use
      of a value that may be an environment of the function's (a closure call passes it as its
      first operand; an icall of a Callable the function made, through its verified adapter);
    - own_ops: (block, offset) -> the words whose cells' objects escape there, through any other
      use of the function's own environment or of a cell loaded from it;
    - loads: word -> the types the function loads from that word's cell.

    An allocation used otherwise is no cell (an object stored into it escapes, as into any memory)."""
    blocks = [b for b in fn["blocks"] if b["label"] != ""]
    defs, uses, where = {}, {}, {}
    for block in blocks:
        for offset, op in enumerate(block["operations"]):
            for r in op["results"]:
                defs[f"%t{r}"] = (block["label"], op)
            for pos, arg in enumerate(op["operands"]):
                uses.setdefault(arg["value"], []).append((op, pos))
            where[id(op)] = (block["label"], offset)
    words = {}  # a mach.addr result -> (its base, word)
    for value, (_, op) in defs.items():
        if op["op"] == "mach.addr" and len(op["operands"]) == 2 and op["operands"][1]["value"].isdigit():
            words[value] = (op["operands"][0]["value"], int(op["operands"][1]["value"]))
    allocs = {v for v, (_, op) in defs.items() if op["op"] == "rt" and op["text"] == "alloc"}

    def only(value, allowed):
        return all((op["op"], pos) in allowed for op, pos in uses.get(value, []))

    def carried(seeds):
        """Each value -> the seeds it may be, through private slots, phis and selects."""
        may = {seed: {seed} for seed in seeds}
        changed = True
        while changed:
            changed = False
            for block in blocks:
                for op in block["operations"]:
                    args = [a["value"] for a in op["operands"]]
                    result = f"%t{op['results'][0]}" if op["results"] else ""
                    flows = []
                    if op["op"] == "mem.store" and args[0] in private:
                        flows = [(args[0], args[1])]
                    elif op["op"] == "mem.load" and args[0] in private:
                        flows = [(result, args[0])]
                    elif op["op"] == "phi":
                        flows = [(result, a) for a in args]
                    elif op["op"] == "select":
                        flows = [(result, a) for a in args[1:]]
                    for dst, src in flows:
                        extra = may.get(src, set()) - may.get(dst, set())
                        if extra:
                            may.setdefault(dst, set()).update(extra)
                            changed = True
        return may
    flow_uses = {("mem.store", 1), ("phi", 0), ("select", 1), ("select", 2)}

    def flows_only(op, pos, value):
        return ((op["op"], pos) in flow_uses and (op["op"] != "mem.store" or op["operands"][0]["value"] in private)) \
            or (op["op"] == "phi" and value in [a["value"] for a in op["operands"]])
    # A closure function's own environment, and the cells it loads from its words.
    cells, own_ops, loads = {}, {}, {}
    params = fn.get("parameters") or []
    own = carried({"%a0"}) if params and params[0].get("representation") == "env" else {}
    for value in own:
        for op, pos in uses.get(value, []):
            result = f"%t{op['results'][0]}" if op["results"] else ""
            if flows_only(op, pos, value) or (value in private and op["op"] in {"mem.load", "mem.store"} and pos == 0):
                continue
            if op["op"] == "mach.addr" and pos == 0 and result in words and only(result, {("mach.load", 0)}):
                for load, _ in uses.get(result, []):
                    cells[f"%t{load['results'][0]}"] = f"C:env{words[result][1]}"
                continue
            # (the environment itself escapes: each cell in it)
            own_ops.setdefault(where[id(op)], set()).add(None)
    # A cell the function allocates: in its entry block, used only at the cell itself and where an
    # allocation of the function's takes it (or its identity box's word).
    entry = blocks[0]["label"] if blocks else ""
    for value in sorted(allocs):
        if defs[value][0] != entry or entry in loops:
            continue
        ok = True
        for op, pos in uses.get(value, []):
            result = f"%t{op['results'][0]}" if op["results"] else ""
            if op["op"] in {"mem.load", "mem.store"} and pos == 0:
                continue
            if op["op"] == "mach.store" and pos == 1 and op["operands"][0]["value"] in words \
                    and words[op["operands"][0]["value"]][0] in allocs - {value}:
                continue
            if op["op"] == "mach.addr" and pos == 0 and result in words and words[result][1] >= 1 \
                    and only(result, {("mach.load", 0), ("mach.store", 0)}):
                continue
            ok = False
        if ok:
            cells[value] = f"C:{value}"
    # The uses of a cell loaded from the own environment: other than at the cell itself, or where
    # an allocation of the function's takes it, its object escapes (and the cell with it).
    for value, location in cells.items():
        if not location.startswith("C:env"):
            continue
        for op, pos in uses.get(value, []):
            result = f"%t{op['results'][0]}" if op["results"] else ""
            if op["op"] in {"mem.load", "mem.store"} and pos == 0:
                if op["op"] == "mem.load":
                    loads.setdefault(int(location[5:]), set()).add(op["type"])
                continue
            if op["op"] == "mach.store" and pos == 1 and op["operands"][0]["value"] in words \
                    and words[op["operands"][0]["value"]][0] in allocs:
                continue
            if op["op"] == "mach.addr" and pos == 0 and result in words and words[result][1] >= 1 \
                    and only(result, {("mach.load", 0), ("mach.store", 0)}):
                continue
            own_ops.setdefault(where[id(op)], set()).add(int(location[5:]))
    # The environments the function allocates: whose words take its cells.
    envs = {}
    for value, location in cells.items():
        for op, pos in uses.get(value, []):
            if op["op"] == "mach.store" and pos == 1 and op["operands"][0]["value"] in words:
                base, word = words[op["operands"][0]["value"]]
                if base in allocs:
                    envs.setdefault(base, {})[word] = location
    env_may = carried(set(envs))
    # A Callable the function makes of a def or lambda: a two-word allocation whose word 0 is an
    # adapter (adapter_targets) and word 1 one of its environments; its icall, with the code and
    # environment loaded from it, calls the adapter's closure function with that environment.
    adapters = adapters or {}
    structs = {}
    for value in sorted(allocs - set(envs) - set(cells)):
        code = [op["operands"][1]["value"] for op, pos in uses.get(value, []) if op["op"] == "mach.store" and pos == 0]
        held = [store["operands"][1]["value"] for op, pos in uses.get(value, []) if op["op"] == "mach.addr" and pos == 0
                and words.get(f"%t{op['results'][0]}") == (value, 1)
                for store, at in uses.get(f"%t{op['results'][0]}", []) if store["op"] == "mach.store" and at == 0]
        if len(code) == 1 and code[0] in adapters and len(held) == 1 and len(env_may.get(held[0], set())) == 1:
            structs[value] = (adapters[code[0]], next(iter(env_may[held[0]])), held[0])
    struct_may = carried(set(structs))
    code_of, env_of = {}, {}  # a load of a Callable's code word or environment word -> the Callable
    for value, sites in struct_may.items():
        for op, pos in uses.get(value, []):
            result = f"%t{op['results'][0]}" if op["results"] else ""
            if op["op"] == "mach.load" and pos == 0 and len(sites) == 1:
                code_of[result] = next(iter(sites))
            elif op["op"] == "mach.addr" and pos == 0 and words.get(result) == (value, 1) and len(sites) == 1:
                for load, at in uses.get(result, []):
                    if load["op"] == "mach.load" and at == 0:
                        env_of[f"%t{load['results'][0]}"] = next(iter(sites))
    for value, struct in env_of.items():
        env_may[value] = {structs[struct][1]}
    env_ops = {}
    for value, sites in env_may.items():
        for op, pos in uses.get(value, []):
            result = f"%t{op['results'][0]}" if op["results"] else ""
            if flows_only(op, pos, value) or (value in private and op["op"] in {"mem.load", "mem.store"} and pos == 0):
                continue
            if op["op"] == "mach.addr" and pos == 0 and result in words and only(result, {("mach.store", 0)}) \
                    and value in envs:
                continue
            if op["op"] == "mach.store" and pos == 1 and any(held == value and words.get(op["operands"][0]["value"]) == (struct, 1)
                                                             for struct, (_, _, held) in structs.items()):
                continue  # (into a Callable of the function's, whose uses are classified below)
            callee = op["text"] if op["op"] in {"call", "invoke"} and pos == 0 else None
            if op["op"] == "icall" and pos == 1 and value in env_of and code_of.get(op["operands"][0]["value"]) == env_of[value]:
                callee = structs[env_of[value]][0]
            env_ops.setdefault(where[id(op)], []).append((pos, value, callee))
    # (any other use of a Callable lets its environment escape: its cells are published there)
    for value, sites in struct_may.items():
        for op, pos in uses.get(value, []):
            result = f"%t{op['results'][0]}" if op["results"] else ""
            if flows_only(op, pos, value) or (value in private and op["op"] in {"mem.load", "mem.store"} and pos == 0):
                continue
            if op["op"] == "mach.store" and pos == 0 and value in structs:
                continue  # (its code word)
            if op["op"] == "mach.load" and pos == 0 and only(result, {("icall", 0)}):
                continue  # (its code, which only its icalls call)
            if op["op"] == "mach.addr" and pos == 0 and words.get(result) == (value, 1) \
                    and only(result, {("mach.load", 0)} | ({("mach.store", 0)} if value in structs else set())):
                continue  # (its environment's word, which its icalls load)
            for struct in sorted(sites):
                env_ops.setdefault(where[id(op)], []).append((pos, structs[struct][1], None))
    return {"cells": cells, "envs": envs, "env_may": env_may, "env_ops": env_ops,
            "own_ops": own_ops, "loads": loads}


def facts(nodes, keep=None):
    """Forward may-facts of a graph: each location's possible tags at each node, kept only where a
    later node reads the location (a payload or a guard) or keep names it at a node (a probe).
    Nodes whose facts do not change share them: a caller must not change a node's facts."""
    keep = keep or {}
    successors = [boundary.successors(node) for node in nodes]
    predecessors = [[] for _ in nodes]
    for index, targets in enumerate(successors):
        for target in targets:
            predecessors[target].append(index)
    # (the least fixed point, which any order of visits reaches: later nodes first, as each
    # depends on its successors)
    live = [set() for _ in nodes]
    pending = [-index for index in range(len(nodes))]
    heapq.heapify(pending)
    queued = [True] * len(nodes)
    while pending:
        index = -heapq.heappop(pending)
        queued[index] = False
        node = nodes[index]
        targets = successors[index]
        if not targets:
            later = set()
        elif len(targets) == 1:
            later = set(live[targets[0]])
        else:
            later = live[targets[0]].union(*(live[t] for t in targets[1:]))
        if node["op"] == "copy":
            if node["dst"] in later:
                later.discard(node["dst"])
                later.add(node["src"])
        elif node["op"] == "havoc":
            later.discard(node["dst"])
        elif node["op"] in {"payload", "guard"}:
            later.add(node["value"])
        if keep.get(index):
            later |= keep[index]
        if later != live[index]:
            live[index] = later
            for predecessor in predecessors[index]:
                if not queued[predecessor]:
                    queued[predecessor] = True
                    heapq.heappush(pending, -predecessor)
    alone = [len(froms) == 1 for froms in predecessors]
    state = [None] * len(nodes)
    state[0] = {}
    pending, queued, work = [0], {0}, 0
    while pending:
        # (in node order: a graph is emitted mostly forward, so few nodes are visited again; the
        # resource bound counts the facts of each change, so the order is part of the result)
        index = heapq.heappop(pending)
        queued.discard(index)
        known = state[index]
        node = nodes[index]
        out = known
        if node["op"] in {"copy", "havoc"} and (node["dst"] in known or node.get("src") in known):
            out = dict(known)
            out.pop(node["dst"], None)
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
            if not live[target].issuperset(moved.keys()):
                moved = {k: v for k, v in moved.items() if k in live[target]}
            previous = state[target]
            if previous is not None and alone[target]:
                # (a node's facts only lose locations and gain tags, and so do those it gives: they
                # are the join with what it gave before)
                if moved == previous:
                    continue
            elif previous is not None:
                # (the locations both know, each with the tags of either: unchanged unless one
                # is lost or gains a tag)
                merged, changed = {}, len(moved) < len(previous)
                for k, v in previous.items():
                    w = moved.get(k)
                    if w is None:
                        changed = True
                    elif w is v or w <= v:
                        merged[k] = v
                    else:
                        merged[k], changed = v | w, True
                if not changed:
                    continue
                moved = merged
            state[target] = moved
            work += len(moved)
            if work > 64 * boundary.MAX_FACTS:
                raise boundary.Unsupported("field facts exceed the prototype's resource bound")
            if target not in queued:
                queued.add(target)
                heapq.heappush(pending, target)
    return state


def loop_blocks(fn):
    """Blocks on a cycle of the block graph, exception edges included (an allocation there may
    run again while a value holds its previous object): those of a strongly connected component
    with more than one block, or with an edge to itself (Tarjan's algorithm, iteratively)."""
    succ = {}
    for b in fn["blocks"]:
        targets = list(b["operations"][-1]["targets"]) if b["operations"] else []
        if b["operations"] and b["operations"][-1]["op"] == "check":
            last = b["operations"][-1]
            targets.append(fn["check_targets"].get(last["descriptor"] or last["text"], ""))
        if b["handler"]:
            targets.append(b["handler"])
        succ[b["label"]] = [t for t in targets if t]
    index, low, stack, on_stack, out = {}, {}, [], set(), set()
    for root in succ:
        if root in index:
            continue
        work = [(root, iter(succ[root]))]
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        while work:
            node, edges = work[-1]
            for target in edges:
                if target not in succ:
                    continue
                if target == node:
                    out.add(node)
                if target not in index:
                    index[target] = low[target] = len(index)
                    stack.append(target)
                    on_stack.add(target)
                    work.append((target, iter(succ[target])))
                    break
                if target in on_stack:
                    low[node] = min(low[node], index[target])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    if len(component) > 1:
                        out.update(component)
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
        self.validated, self.loops, self.graphs, self.callees, self.closures = {}, {}, {}, {}, {}
        self.states = {}
        self.adapters = adapter_targets(self.functions)

    def shapes(self, fn):
        if fn["symbol"] not in self.closures:
            self.closures[fn["symbol"]] = closure_shapes(fn, private_slots(fn), self.loop(fn), self.adapters)
        return self.closures[fn["symbol"]]

    def position_class(self, fn, position):
        """The class of the object a contract's position gives fn, or None: a parameter's, or the
        one type fn loads from the cell at word i of its environment."""
        if isinstance(position, int):
            return param_class(fn, position, self.layouts)
        params = fn.get("parameters") or []
        if not params or params[0].get("representation") != "env":
            return None
        types = self.shapes(fn)["loads"].get(int(position[3:]), set())
        return next(iter(types)) if len(types) == 1 and next(iter(types)) in self.layouts else None

    def validate(self, fn):
        symbol = fn["symbol"]
        if symbol not in self.validated:
            try:
                boundary.normalize_snapshot(dict(self.snapshot, functions=[boundary.word_validation(fn)]), symbol,
                                            certify=False)
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
            # (whose contracts the graph uses: each call's callee, and each closure function an
            # icall reaches through its Callable's adapter)
            self.callees[symbol] = {op["text"] for b in fn["blocks"] for op in b["operations"]
                                    if op["op"] in {"call", "invoke"}} | {
                callee for uses in self.shapes(fn)["env_ops"].values() for _, _, callee in uses if callee}
        depends = self.callees[symbol] | {symbol}
        key = (symbol, tuple(sorted(((k, tuple(sorted(v[0])), tuple(sorted(v[1])), v[2])
                                     for k, v in contracts.items() if k[0] in depends), key=lambda c: (c[0][0], str(c[0][1])))))
        if key not in self.graphs:
            try:
                self.graphs[key] = normalize(self, fn, contracts)
            except boundary.Unsupported as error:
                self.graphs[key] = error
        if isinstance(self.graphs[key], boundary.Unsupported):
            raise self.graphs[key]
        return self.graphs[key]

    def facts(self, graph):
        """A graph's facts, inferred once: a round of contract inference that leaves a function's
        contracts as they were reuses its graph and them."""
        if id(graph) not in self.states:
            self.states[id(graph)] = facts(graph[0], graph[3])
        return self.states[id(graph)]


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
    private = private_slots(fn)
    shapes = ctx.shapes(fn)
    # where a load or store's pointer names a location of the graph: a private slot, or a cell's
    # content (C:...); a cell is private until an environment that holds it escapes (published)
    slot_of = {v: v for v in private} | shapes["cells"]
    cells = sorted(set(shapes["cells"].values()))
    # The objects under construction: each allocation of a class, and each position a contract
    # covers (an __init__'s self, an argument a call passes an object under construction in, or
    # the content of a cell in a closure function's environment that a closure call passes one in).
    objects, may = {}, {}
    given = sorted((p for (s, p) in contracts if s == symbol), key=str)
    params = {holder(p): p for p in given}
    for p in given:
        objects[holder(p)] = ctx.position_class(fn, p)
        may[f"%a{p}" if isinstance(p, int) else f"C:{p}"] = {holder(p)}
    for block in blocks:
        for offset, op in enumerate(block["operations"]):
            if op["op"] == "alloc.fixed" and op["type"] in layouts:
                site = f"{block['label']}.{offset}"
                objects[site] = op["type"]
                may[f"%t{op['results'][0]}"] = {site}
    # may[v]: the objects a value, private slot or cell may be (a flow-insensitive closure of copies).
    changed = bool(may)
    while changed:
        changed = False
        for block in blocks:
            for op in block["operations"]:
                args = [a["value"] for a in op["operands"]]
                flows = []
                if op["op"] == "mem.store" and args[0] in slot_of:
                    flows = [(slot_of[args[0]], args[1])]
                elif op["op"] == "mem.load" and args[0] in slot_of:
                    flows = [(f"%t{op['results'][0]}", slot_of[args[0]])]
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
                if holder(p) in objs:
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
    cells = [c for c in cells if c in may]  # (a cell no object under construction reaches needs no state)
    for location in cells:
        # (a cell the function allocates holds no object yet, one in its environment the contract's;
        # neither is published yet)
        g.follow({"op": "copy", "dst": location, "src": const(f"obj:{location[2:]}" if location[2:] in params else OTHER)})
        g.follow({"op": "copy", "dst": "P:" + location, "src": const(UNSET)})

    def published(location, site):
        """Whether a cell may be published at a site, per the previous pass's facts, which Lean
        checks here where it is not (the first pass assumes it is not)."""
        key = (site[0], site[1], location, "published")
        marks[key] = len(g.nodes)
        keep.setdefault(len(g.nodes), set()).add("P:" + location)
        if known is None:
            return False
        if SET in known.get(key, {}).get("P:" + location, frozenset()):
            return True
        index = g.follow({"op": "payload", "value": "P:" + location, "tags": [UNSET]})
        g.origins[index] = (site[0], site[1], "unpublished cell", location, -1)
        return False

    def publish(location, site):
        """A cell that other code may now reach (its environment escapes): the objects it holds
        escape, and so does each one stored into it later; its content may change where that
        code runs (a nonlocal assignment), which each later load allows for."""
        require(location, relevant, site, "escapes")
        g.follow({"op": "copy", "dst": "P:" + location, "src": const(SET)})
        if location[2:] in params:
            leaks[params[location[2:]]] = True

    def overwritten(location):
        """A cell's content after code that may assign it: as before, or another, complete object."""
        choice = g.emit({"op": "choice", "yes": len(g.nodes) + 1, "no": None})
        g.follow({"op": "copy", "dst": location, "src": const(OTHER)})
        g.nodes[choice]["no"] = len(g.nodes)

    def closure_call(symbol, value, site):
        """A call of closure function symbol, given an environment of this function's whose cells
        hold objects under construction: covered by a contract for each such cell (which the callee
        reads and assigns as a parameter's), if none is published; else the environment escapes.
        Returns the actions after the call (its post-conditions), or None where not covered."""
        callee = functions.get(symbol)
        sites = shapes["env_may"].get(value, set())
        if callee is None or len(sites) != 1:
            return None
        holding = sorted((word, location) for word, location in shapes["envs"][next(iter(sites))].items() if location in cells)
        covered = True
        for word, location in holding:
            position = f"env{word}"
            if (symbol, position) not in contracts:
                if ctx.position_class(callee, position) is not None:
                    probes["wanted"].append((len(g.nodes), symbol, position, location))
                    keep.setdefault(len(g.nodes), set()).update(
                        {location} | {field(o, k) for o in may[location] for k in relevant(o)})
                covered = False
        if not covered or any([published(location, site) for _, location in holding]):
            return None
        actions = []
        for word, location in holding:
            position = f"env{word}"
            pre, post, callee_leaks = contracts[(symbol, position)]
            cls = ctx.position_class(callee, position)
            probes["calls"].append((len(g.nodes), symbol, position, location))
            keep.setdefault(len(g.nodes), set()).update(
                {location} | {field(o, k) for o in may[location] for k in view[cls]})
            require(location, lambda o, pre=pre, cls=cls, callee_leaks=callee_leaks: (pre & view[cls]) | (
                (relevant(o) - view[cls]) if callee_leaks else set()), site, "calls")
            if callee_leaks:
                # (the callee lets the object or its cell escape, or assigns the cell: published)
                for p in given:
                    if holder(p) in may[location]:
                        leaks[p] = True
                g.follow({"op": "copy", "dst": "P:" + location, "src": const(SET)})
                overwritten(location)
            actions.append(lambda location=location, post=post, site=site, position=position: assign(
                location, lambda o: post, (site[0], site[1], location, "post " + position)))
        return actions
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
            # (first what the operation does with environments and cells, which an exception it
            # raises, on the way to the handler, has done too)
            after = []
            for pos, value, callee in shapes["env_ops"].get(site, []):
                actions = closure_call(callee, value, site) if callee is not None else None
                if actions is None:
                    for env in sorted(shapes["env_may"].get(value, set())):
                        for location in sorted(set(shapes["envs"][env].values()) & set(cells)):
                            publish(location, site)
                else:
                    after += actions
            for word in sorted(shapes["own_ops"].get(site, set()), key=str):
                for p in given:
                    if not isinstance(p, int) and (word is None or p == f"env{word}"):
                        publish("C:" + p, site)
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
            if kind == "mem.load" and args[0] in addresses:
                obj, k, cls = addresses[args[0]]
                boundary.require(cls in layouts, "field read through an unknown class view")
                if k in unchecked(layouts[cls]):
                    require(obj, lambda o, k=k: {k}, site, "reads")
                uses = [u for u in uses if u[0] != 0]
            elif kind == "mem.load" and args[0] in slot_of:
                location = slot_of[args[0]]
                if results[0] in may:
                    choice = None
                    if location in cells and published(location, site):
                        # (other code may have assigned a published cell: as before, or another object)
                        choice = g.emit({"op": "choice", "yes": len(g.nodes) + 1, "no": None})
                    g.follow({"op": "copy", "dst": results[0], "src": location})
                    if choice is not None:
                        jump = g.emit({"op": "jump", "next": None})
                        g.nodes[choice]["no"] = len(g.nodes)
                        g.follow({"op": "copy", "dst": results[0], "src": const(OTHER)})
                        g.nodes[jump]["next"] = len(g.nodes)
                uses = []
            elif kind == "mem.store" and args[0] in addresses:
                obj, k, cls = addresses[args[0]]
                flagged = flag_field(cls, k)
                if flagged is not None:
                    # (a flag is set only after its field: what a test of it relies on)
                    require(obj, lambda o, flagged=flagged: {flagged} & relevant(o), site, "flags")
                after.append(lambda obj=obj, k=k, site=site: assign(obj, lambda o: {k}, (site[0], site[1], obj, "store")))
                uses = [u for u in uses if u[0] != 0]
            elif kind == "mem.store" and args[0] in slot_of:
                location = slot_of[args[0]]
                if location in cells:
                    caller = location[2:] in params
                    if caller:
                        # (a nonlocal assignment of the caller's cell, which the caller allows for)
                        leaks[params[location[2:]]] = True
                    if (caller or published(location, site)) and args[1] in may:
                        # (what other code can load from the cell: complete)
                        require(args[1], relevant, site, "escapes")
                if location in may:
                    g.follow({"op": "copy", "dst": location, "src": src(args[1])})
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
                # None parameters have no call operand, but contracts and %aN names use
                # source parameter positions. Keep the two indexes distinct.
                positions = [i for i, p in enumerate(callee.get("parameters") or [])
                             if p.get("representation") != "None"]
                for argument, value in uses:
                    if value not in may or argument >= len(positions):
                        continue
                    pos = positions[argument]
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
                            if holder(p) in may.get(value, set()):
                                leaks[p] = True
                    after.append(lambda value=value, post=post, site=site, pos=pos: assign(
                        value, lambda o: post, (site[0], site[1], value, f"post{pos}")))
                    covered.append((argument, value))
                uses = [u for u in uses if u not in covered]
            for pos, value in uses:
                obj = addresses[value][0] if value in addresses else value
                require(obj, relevant, site, "escapes")
            if kind in {"ret", "ret.none", "gen.start"}:
                # (a call of a generator function returns at gen.start, before its body runs: its
                # post-condition holds there, and its body's reads are required at the call, as
                # fields only become assigned while it is suspended)
                for p in given:
                    probes["returns"].append((len(g.nodes), p))
                    keep.setdefault(len(g.nodes), set()).update(field(holder(p), k) for k in relevant(holder(p)))
                    for k in sorted(contracts[(symbol, p)][1]):
                        index = g.follow({"op": "payload", "value": field(holder(p), k), "tags": [SET]})
                        g.origins[index] = (label, offset, "returns", holder(p), k)
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
            elif kind in {"ret", "ret.none", "unreachable", "gen.ret"} or (kind in {"raise", "throw"} and not targets):
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
        contracts = {k: (set(view[ctx.position_class(functions[k[0]], k[1])]),) * 2 + (False,) for k in keys}
        for _ in range(64):
            pres = {k: set(contracts[k][0]) for k in contracts}
            posts = {k: set(contracts[k][1]) for k in contracts}
            leaks = {k: False for k in contracts}
            wanted = set()
            for fn in snapshot["functions"]:
                if not relevant_function(fn, layouts, contracts):
                    continue
                try:
                    graph = ctx.graph(fn, contracts)
                except boundary.Unsupported:
                    for k in contracts:
                        if k[0] == fn["symbol"]:
                            posts[k] = set()
                            leaks[k] = True
                    continue
                nodes, meta, probes, keep = graph
                state = ctx.facts(graph)
                for index, callee, pos, value in probes["wanted"]:
                    known = state[index] or {}
                    for tag in known.get(value, ()):
                        o = tag[4:]
                        if tag.startswith("obj:") and any(known.get(f"F:{o}#{k}") != frozenset([SET])
                                                          for k in view[meta["objects"][o]]):
                            wanted.add((callee, pos))
                for index, callee, pos, value in probes["calls"]:
                    known = state[index] or {}
                    cls = ctx.position_class(functions[callee], pos)
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
                                                     if known.get(f"F:{holder(p)}#{k}") == frozenset([SET])}
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
                            for (s, p), (a, b, c) in sorted(contracts.items(), key=lambda item: (item[0][0], str(item[0][1])))]}
    print(json.dumps(report, indent=1, default=list))
    return boundary.OUTCOMES[program_report(results)["field_status"]]


if __name__ == "__main__":
    sys.exit(main())
