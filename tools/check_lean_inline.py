#!/usr/bin/env python3
"""Check actual overflow edges before consuming checked integer results.

The graph checker and mathematical corollaries are kernel-checked in
PystachyBoundary/PystachyInline. Snapshot fidelity, CFG/SSA normalization and
LLVM's implementation of the signed overflow primitive remain trusted.
"""
from __future__ import annotations

import hashlib
import subprocess

import check_lean_boundary as bridge

SUPPORTED = bridge.SUPPORTED_OPS | {"gen.start", "gen.yield", "gen.ret", "gen.done"}
EXITS = {"ret", "ret.none", "raise", "throw", "unreachable", "gen.ret", "gen.done"}


def args(op):
    return [operand["value"] for operand in op["operands"]]


def relevant(fn):
    # Starting at both checked operations and their reconstruction keeps an
    # unchecked add/sub/mul replacement from making the inventory disappear.
    return any(op["op"] in {"ovf", "big.make"} for block in fn["blocks"] for op in block["operations"])


class Normalize:
    def __init__(self, fn):
        self.fn, self.blocks = fn, fn["blocks"]
        self.defs, self.owners = {}, {}
        self.words, self.flags = {}, {}
        self.starts, self.pending = {}, []
        self.nodes = [{"op": "stop"}]
        self.sites = []
        for block in self.blocks:
            label = block["label"]
            bridge.require(label not in self.starts, "duplicate block label")
            self.starts[label] = None
            for index, op in enumerate(block["operations"]):
                bridge.require(isinstance(op, dict) and set(op) == bridge.OP_KEYS, "invalid instruction fields")
                if op["op"] not in SUPPORTED:
                    raise bridge.Unsupported("unclassified inline instruction: " + op["op"])
                if op["op"] in bridge.SUPPORTED_OPS:
                    bridge.instruction(op)
                for number in op["results"]:
                    name = f"%t{number}"
                    bridge.require(name not in self.defs, "duplicate temporary: " + name)
                    self.defs[name], self.owners[name] = op, (label, index)
                if op["op"] == "ovf":
                    bridge.shape(op, 2, 3, typ="int", texts=("+", "-", "*"))
                    word, flag = (f"%t{number}" for number in op["results"][1:])
                    self.words[word] = flag
                    self.flags[flag] = op
        selected = set()
        for block in self.blocks:
            for op in block["operations"]:
                if op["op"] != "big.make":
                    continue
                bridge.require(len(args(op)) == 2, "big.make takes two operands")
                low = args(op)[0]
                if low.startswith("%t") and low[2:].isdigit():
                    bridge.require(low in self.defs, "undefined reconstruction word: " + low)
                transported = self.arithmetic_sources(args(op)[0])
                if transported.intersection(self.words) and args(op)[0] not in self.words:
                    raise bridge.Unsupported("transformed checked arithmetic reconstruction")
                if args(op)[0] in self.words:
                    bridge.require(args(op)[1] == "null", "checked arithmetic reconstruction has unexpected digits")
                    selected.add(args(op)[0])
                for source in transported:
                    word = self.defs.get(source)
                    if word and word["op"] == "scalar.bin" and word["text"] in {"add", "sub", "mul"}:
                        if any(any(self.defs.get(origin, {}).get("op") == "big.lo"
                                   for origin in self.arithmetic_sources(value)) for value in args(word)):
                            raise bridge.Unsupported("unchecked promoting add/sub/mul reconstruction")
        self.observed_operations = len(self.words)
        self.words = {word: flag for word, flag in self.words.items() if word in selected}
        self.flags = {flag: op for flag, op in self.flags.items() if flag in self.words.values()}
        if self.words:
            self.validate_ssa()

    def arithmetic_sources(self, value):
        """Trace only pure scalar transport, stopping at loads/calls/new values.

        Unknown transformed checked results must not disappear from inventory.
        General memory and runtime arithmetic provenance is outside this model.
        """
        pending, seen = [(value, 0)], set()
        while pending:
            value, depth = pending.pop()
            if value in seen:
                continue
            if depth > bridge.MAX_CONDITION:
                raise bridge.Unsupported("arithmetic provenance nests too deeply")
            seen.add(value)
            bridge.require(len(seen) < bridge.MAX_INSTRUCTIONS, "arithmetic provenance exceeds bound")
            if value.startswith("%t") and value[2:].isdigit():
                bridge.require(value in self.defs, "undefined arithmetic provenance: " + value)
            op = self.defs.get(value)
            if op and op["op"] in {"scalar.bin", "scalar.cast", "num.cast", "scalar.cmp", "num.cmp",
                                   "int.ucmp", "select", "phi", "slot.pack", "slot.unpack"}:
                pending.extend((argument, depth + 1) for argument in args(op))
        return seen

    def validate_ssa(self):
        edges = {}
        for block in self.blocks:
            bridge.require(block["operations"], "empty inline block")
            last = block["operations"][-1]
            out = list(last["targets"])
            if last["op"] == "check":
                error = self.fn.get("check_targets", {}).get(last["descriptor"] or last["text"])
                bridge.require(error in self.starts, "check lacks error target")
                out.append(error)
            if block["handler"] and block["handler"] in self.starts and any(op["op"] in bridge.INVOKES | {"check", "raise", "throw", "gen.start", "gen.yield"}
                                        for op in block["operations"]):
                out.append(block["handler"])
            bridge.require(all(target != "" and target in self.starts for target in out), "unknown control-flow target")
            edges[block["label"]] = out
        entry = self.blocks[0]["label"]
        reached, pending = {entry}, [entry]
        while pending:
            for target in edges[pending.pop()]:
                if target not in reached:
                    reached.add(target)
                    pending.append(target)
        predecessors = {label: set() for label in reached}
        for label in reached:
            for target in edges[label]:
                predecessors[target].add(label)
        dominators = {label: {entry} if label == entry else set(reached) for label in reached}
        changed = True
        while changed:
            changed = False
            for label in reached - {entry}:
                common = set.intersection(*(dominators[p] for p in predecessors[label]))
                updated = {label} | common
                if updated != dominators[label]:
                    dominators[label], changed = updated, True
        for block in self.blocks:
            label = block["label"]
            if label not in reached:
                continue
            for index, op in enumerate(block["operations"]):
                if op["op"] == "phi":
                    bridge.require(len(op["targets"]) == len(args(op)), "phi predecessor arity mismatch")
                    bridge.require(set(op["targets"]) == predecessors[label]
                                   and len(set(op["targets"])) == len(op["targets"]), "invalid phi predecessors")
                for position, value in enumerate(args(op)):
                    if not (value.startswith("%t") and value[2:].isdigit()):
                        continue
                    bridge.require(value in self.owners, "undefined temporary: " + value)
                    owner, offset = self.owners[value]
                    at = op["targets"][position] if op["op"] == "phi" else label
                    if at in reached:
                        bridge.require(owner in dominators[at], "temporary does not dominate use: " + value)
                        if owner == at and op["op"] != "phi":
                            bridge.require(offset < index, "temporary read precedes definition: " + value)

    def add(self, node):
        bridge.require(len(self.nodes) < bridge.MAX_INSTRUCTIONS, "inline graph exceeds instruction bound")
        self.nodes.append(node)
        return len(self.nodes) - 1

    def edge(self, label, previous):
        bridge.require(label in self.starts, "unknown control-flow target")
        index = self.add({"op": "jump", "next": 0})
        self.pending.append((index, label, previous))
        return index

    def condition(self, value, yes, no, depth=0):
        if depth > bridge.MAX_CONDITION:
            raise bridge.Unsupported("inline condition nests too deeply")
        if value in {"true", "false"}:
            return yes if value == "true" else no
        if value in self.flags:
            return self.add({"op": "guard", "value": value, "tags": ["overflow"], "yes": yes, "no": no})
        op = self.defs.get(value)
        if op and op["op"] == "scalar.bin" and op["type"] == "bool" and len(args(op)) == 2:
            a, b = args(op)
            if op["text"] == "and":
                return self.condition(a, self.condition(b, yes, no, depth + 1), no, depth + 1)
            if op["text"] == "or":
                return self.condition(a, yes, self.condition(b, yes, no, depth + 1), depth + 1)
            if op["text"] == "xor" and b == "true":
                return self.condition(a, no, yes, depth + 1)
            if op["text"] == "xor" and a == "true":
                return self.condition(b, no, yes, depth + 1)
        return self.add({"op": "choice", "yes": yes, "no": no})

    def use(self, value, nxt, block, operation):
        if value not in self.words:
            return nxt
        flag = self.words[value]
        node = self.add({"op": "payload", "value": flag, "tags": ["exact"], "next": nxt})
        self.sites.append({"node": node, "block": block, "operation": operation, "word": value,
                           "overflow_flag": flag, "operator": self.flags[flag]["text"]})
        return node

    def build(self):
        for block in self.blocks:
            label, nxt = block["label"], 0
            for op in reversed(block["operations"]):
                kind, values = op["op"], args(op)
                if kind in {"br", "landing", "gen.start", "gen.yield"}:
                    bridge.require(len(op["targets"]) == 1, "invalid jump targets")
                    nxt = self.edge(op["targets"][0], label)
                elif kind == "cbr":
                    bridge.shape(op, 1, 0, targets=2)
                    nxt = self.condition(values[0], self.edge(op["targets"][0], label),
                                         self.edge(op["targets"][1], label))
                elif kind == "check":
                    error = self.fn["check_targets"][op["descriptor"] or op["text"]]
                    nxt = self.condition(values[0], self.edge(error, label), self.edge(op["targets"][0], label))
                elif kind == "switch":
                    targets = [self.edge(target, label) for target in op["targets"]]
                    bridge.require(targets, "empty switch")
                    nxt = targets[0]
                    for target in targets[1:]:
                        nxt = self.add({"op": "choice", "yes": target, "no": nxt})
                elif kind in EXITS:
                    nxt = self.edge(op["targets"][0], label) if op["targets"] else 0
                elif kind == "phi":
                    continue  # Reads occur on each incoming edge, before parallel assignments.
                elif op["targets"]:
                    bridge.require(kind in bridge.INVOKES and len(op["targets"]) == 2, "unknown inline CFG edge")
                    nxt = self.add({"op": "choice", "yes": self.edge(op["targets"][0], label),
                                    "no": self.edge(op["targets"][1], label)})
                if block["handler"] and block["handler"] in self.starts and kind in bridge.INVOKES | {"check", "raise", "throw", "gen.start", "gen.yield"}:
                    nxt = self.add({"op": "choice", "yes": nxt, "no": self.edge(block["handler"], label)})
                if kind == "ovf" and f"%t{op['results'][2]}" in self.flags:
                    flag = f"%t{op['results'][2]}"
                    # Reexecuting an SSA definition in a loop must forget the old
                    # iteration's overflow result before declaring its Boolean domain.
                    nxt = self.add({"op": "guard", "value": flag, "tags": ["exact", "overflow"], "yes": nxt, "no": 0})
                    nxt = self.add({"op": "havoc", "dst": flag, "next": nxt})
                for value in reversed(values):
                    nxt = self.use(value, nxt, label, kind)
            self.starts[label] = nxt
        for index, label, previous in self.pending:
            nxt = self.starts[label]
            for op in next(block for block in self.blocks if block["label"] == label)["operations"]:
                if op["op"] == "phi":
                    for predecessor, value in zip(op["targets"], args(op), strict=True):
                        if predecessor == previous:
                            nxt = self.use(value, nxt, previous, "phi")
            self.nodes[index]["next"] = nxt
        entry = self.starts[self.blocks[0]["label"]]
        certificate = bridge.infer_certificate(self.nodes, entry)
        return {"schema_version": 2, "program": {"nodes": self.nodes, "entry": entry}, "certificate": certificate}


def check_all(snapshot, checker=bridge.DEFAULT_CHECKER):
    bridge.check_header(snapshot)
    records = []
    for fn in snapshot["functions"]:
        if not relevant(fn):
            continue
        record = {"function": fn["symbol"], "operations": sum(op["op"] == "ovf" for block in fn["blocks"]
                                                              for op in block["operations"])}
        try:
            normal = Normalize(fn)
            record["observed_operations"] = normal.observed_operations
            record["operations"] = len(normal.words)
            if not normal.words:
                continue
            candidate = normal.build()
            record.update(uses=len(normal.sites), nodes=len(normal.nodes))
            if not normal.sites:
                continue
            encoded = bridge.encode(candidate)
            accepted = bridge.run_checker(checker, encoded, {"nodes": len(normal.nodes), "payloads": len(normal.sites)})
            record.update(status="accepted" if accepted else "rejected",
                          candidate_sha256=hashlib.sha256(encoded.encode()).hexdigest())
            if not accepted:
                record["unproved"] = [site for site in normal.sites if not any(
                    fact[0] == site["overflow_flag"] and set(fact[1]) <= {"exact"}
                    for fact in candidate["certificate"][site["node"]])]
        except bridge.Unsupported as error:
            record.update(status="unsupported", message=str(error))
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError, RecursionError) as error:
            record.update(status="error", message=str(error))
        records.append(record)
    worst = max((record["status"] for record in records), key=bridge.SEVERITY.index, default="accepted")
    totals = {key: sum(record.get(key, 0) for record in records) for key in ("operations", "uses")}
    totals["observed_operations"] = sum(op["op"] == "ovf" for fn in snapshot["functions"]
                                       for block in fn["blocks"] for op in block["operations"])
    totals["outside_scope_operations"] = totals["observed_operations"] - totals["operations"]
    totals["proved_uses"] = sum(record.get("uses", 0) for record in records if record["status"] == "accepted")
    return {"status": worst, "functions": records, "totals": totals}, bridge.OUTCOMES[worst]
