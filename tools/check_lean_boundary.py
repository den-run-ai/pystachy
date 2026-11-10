#!/usr/bin/env python3
"""Check a selected exported IR function's dyn.payload guards with Lean.

This prototype's Python normalization is part of the trusted correspondence to
Pystachy. The inferred facts are untrusted: the Lean executable checks them.
It proves neither full typed-IR validity nor the correctness of LLVM lowering.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-boundary"
MAX_BYTES = 4 * 1024 * 1024
MAX_INSTRUCTIONS = 1024
MAX_NODES = 4096
MAX_FACTS = 16384
TAGS = {"float", "str", "bool"}
OP_KEYS = {"op", "type", "text", "immediate", "descriptor", "results", "operands", "targets"}
# How each typed-IR operation (IROPS, src/pystachy_compiler/specs.py) is normalized. Ordinary
# operations write no private slot (a slot whose address reaches any other operation is not
# private) and no box (boxes are immutable; a store through an address derived from a box is
# refused), so they only define their results: a result the function uses as dyn gets an
# unknown tag. Tag operations make guards and payload reads; terminators make the edges.
ORDINARY = {"rt", "call", "icall", "init", "phi", "select", "ovf", "list.load", "list.len",
            "alloc.fixed", "vtuple.make", "mem.load", "mem.store", "mach.load", "mach.store",
            "mach.addr", "tuple.load", "tuple.store", "field.addr", "slot.pack", "slot.unpack",
            "scalar.bin", "scalar.cast", "scalar.cmp", "num.cast", "num.cmp", "int.ucmp",
            "empty.kind", "union.tag", "union.payload", "union.raw", "dyn.raw", "big.make",
            "big.lo", "big.hi", "exc.match"}
TAG_OPS = {"dyn.type", "ptr.cmp", "dyn.payload"}
TERMINATORS = {"br", "cbr", "switch", "check", "ret", "ret.none", "raise", "throw",
               "unreachable", "landing"}
# A call that may raise inside a try statement is an invoke: it ends its block, and its second
# target is the unwind edge to a landing block.
INVOKES = {"rt", "call", "icall", "init"}
# Operations that may read or write a slot named as their first operand; any other use of a
# slot's address makes it escape.
SLOT_ACCESS = {"mem.load", "mem.store", "mach.load", "mach.store", "landing"}
SUPPORTED_OPS = ORDINARY | TAG_OPS | TERMINATORS
LIMITATIONS = [
    "Only dyn.payload guard safety in the selected normalized function is checked.",
    "Python normalization, snapshot fidelity, runtime tag contracts and LLVM lowering are not proved.",
    "Generators, other payload types and stores into boxes are rejected; null values get unknown tags.",
    "The native Lean executable adds the Lean compiler and runtime to the trusted base.",
]


class Unsupported(ValueError):
    """Valid-looking IR outside the deliberately bounded prototype."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def name(value, what):
    require(isinstance(value, str) and 0 < len(value) <= 256 and "\0" not in value,
            f"invalid {what}")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_snapshot(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), "snapshot must be a regular file")
        raw = source.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, f"snapshot exceeds {MAX_BYTES} bytes")
    return json.loads(raw, object_pairs_hook=unique_object), hashlib.sha256(raw).hexdigest()


def instruction(value, slot=False):
    require(isinstance(value, dict) and set(value) == OP_KEYS, "invalid instruction fields")
    for key in ("op", "type", "text", "descriptor"):
        require(isinstance(value[key], str) and len(value[key]) <= 4096, f"invalid instruction {key}")
    if value["op"] not in ({"slot"} if slot else SUPPORTED_OPS):
        raise Unsupported(f"unsupported operation: {value['op']}")
    require(type(value["immediate"]) is int and (value["immediate"] in (0, 1, 2) if slot
                                                 else 0 <= value["immediate"] < 2 ** 31),
            "invalid instruction immediate")
    require(isinstance(value["results"], list) and len(value["results"]) <= 8,
            "invalid instruction results")
    require(all(type(n) is int and 0 <= n <= 1000000 for n in value["results"]),
            "invalid result identifier")
    require(isinstance(value["operands"], list) and len(value["operands"]) <= 256,
            "invalid instruction operands")
    for operand in value["operands"]:
        require(isinstance(operand, dict) and set(operand) == {"value", "type"}, "invalid operand")
        name(operand["value"], "operand value")
        name(operand["type"], "operand type")
    require(isinstance(value["targets"], list) and len(value["targets"]) <= 256,
            "invalid instruction targets")
    for target in value["targets"]:
        name(target, "branch target")
    return value


def shape(op, operands, results, targets=0, typ=None, texts=("",)):
    require(len(op["operands"]) == operands and len(op["results"]) == results
            and len(op["targets"]) == targets and op["text"] in texts
            and (typ is None or op["type"] == typ), f"invalid {op['op']} shape")


def successors(node):
    if node["op"] == "stop":
        return []
    if node["op"] in {"guard", "choice"}:
        return [node["yes"], node["no"]]
    return [node["next"]]


def infer_certificate(nodes, entry=0):
    """Suggest forward must-facts. Lean independently checks every transfer."""
    facts = [None] * len(nodes)
    facts[entry] = set()
    pending = deque([entry])
    iterations = 0
    while pending:
        index = pending.popleft()
        known = facts[index]
        node = nodes[index]
        outgoing = set(known)
        if node["op"] in {"copy", "havoc"}:
            outgoing = {(value, tag) for value, tag in known if value != node["dst"]}
            if node["op"] == "copy":
                outgoing.update((node["dst"], tag) for value, tag in known if value == node["src"])
        for edge, target in enumerate(successors(node)):
            transferred = set(outgoing)
            if node["op"] == "guard" and edge == 0:
                transferred.add((node["value"], node["tag"]))
            previous = facts[target]
            merged = transferred if previous is None else previous & transferred
            if merged != previous:
                facts[target] = merged
                pending.append(target)
        iterations += 1
        if iterations > 20000 or sum(len(f or ()) for f in facts) > MAX_FACTS:
            raise Unsupported("candidate inference exceeds the prototype's resource bound")
    return [[list(fact) for fact in sorted(known or ())] for known in facts]


def normalize_snapshot(snapshot, function):
    name(function, "function selector")
    require(isinstance(snapshot, dict), "snapshot must be an object")
    require(type(snapshot.get("schema_version")) is int and snapshot["schema_version"] == 1,
            "expected inspection schema_version 1")
    if snapshot.get("stage") != "typed-after" or snapshot.get("status") != "completed":
        raise Unsupported("only completed typed-after snapshots are supported")
    functions = snapshot.get("functions")
    require(isinstance(functions, list) and len(functions) <= 2048, "invalid functions list")
    require(all(isinstance(fn, dict) for fn in functions), "invalid function record")
    selected = [fn for fn in functions if fn.get("symbol") == function or fn.get("name") == function]
    require(len(selected) == 1, "--function must select exactly one function by exact name or symbol")
    fn = selected[0]
    symbol = name(fn.get("symbol"), "function symbol")
    name(fn.get("return_representation"), "return representation")
    recursion = fn.get("recursion")
    require(isinstance(recursion, dict), "invalid recursion record")
    if recursion.get("generator") or recursion.get("coroutine"):
        raise Unsupported("generators are outside the prototype")
    parameters = fn.get("parameters")
    require(isinstance(parameters, list) and len(parameters) <= 128, "invalid parameters")
    # Registers defined on entry: parameters of any representation, the identity boxes that
    # accompany numeric parameters (%aidN) and the identity-return address (%idret).
    definitions = {"%idret": ("*dyn", None, -1)}
    for index, parameter in enumerate(parameters):
        require(isinstance(parameter, dict), "invalid parameter")
        definitions[f"%a{index}"] = (name(parameter.get("representation"), "parameter representation"), None, -1)
        definitions[f"%aid{index}"] = ("dyn", None, -1)
    targets_of_checks = fn.get("check_targets", {})
    require(isinstance(targets_of_checks, dict) and all(
        isinstance(key, str) and len(key) <= 4096 and isinstance(label, str)
        for key, label in targets_of_checks.items()), "invalid check targets")
    blocks = fn.get("blocks")
    require(isinstance(blocks, list) and blocks, "invalid blocks")
    if len(blocks) > 256:
        raise Unsupported("function exceeds 256 blocks")
    slots = {}
    require(isinstance(fn.get("slots"), list) and len(fn["slots"]) <= MAX_INSTRUCTIONS, "invalid slots")
    for raw in fn["slots"]:
        # Slot kinds: storage, a local's "is assigned" flag and a stack tuple, whose register is
        # a tuple value rather than storage.
        op = instruction(raw, slot=True)
        shape(op, 0, 1, texts=(op["text"],))
        name(op["type"], "slot representation")
        # Name a slot as lowering does (slot_register, src/pystachy_compiler/ir.py): a local's
        # "is assigned" flag and numeric identity companions share its number, which is no name.
        number = op["results"][0]
        if op["immediate"] == 2:
            definitions[f"%stk.{number}"] = (op["type"], None, -1)
            continue
        if op["immediate"] == 1:
            require(op["type"] == "bool" and op["text"] != "", "invalid assignment flag slot")
            slot = f"%{op['text']}.def.{number}"
        else:
            slot = f"%{op['text'] or 'h'}.{number}"
        require(slot not in slots and slot not in definitions and len(slot) <= 256, "duplicate or invalid slot")
        slots[slot] = op["type"]
    starts = {}
    total = 0
    numbers = set()
    for block in blocks:
        require(isinstance(block, dict) and set(block) == {"label", "handler", "operations"},
                "invalid block fields")
        label = block.get("label")
        # (LLVM starts an unlabeled block after a terminator; no branch can name it)
        require(isinstance(label, str) and len(label) <= 256 and (label == "" or name(label, "block label")),
                "invalid block label")
        require(label == "" or label not in starts, "duplicate block label")
        require(isinstance(block.get("handler"), str) and len(block["handler"]) <= 256, "invalid handler")
        operations = block.get("operations")
        require(isinstance(operations, list) and operations, "empty or invalid block")
        if label != "":
            starts[label] = None
        total += len(operations)
        if total > MAX_INSTRUCTIONS:
            raise Unsupported(f"function exceeds {MAX_INSTRUCTIONS} instructions")
        for offset, raw in enumerate(operations):
            op = instruction(raw)
            invoke = op["op"] in INVOKES and len(op["targets"]) == 2
            require((op["op"] in TERMINATORS or invoke) == (offset == len(operations) - 1),
                    "each block must end with its only terminator")
            for position, number in enumerate(op["results"]):
                require(number not in numbers, "duplicate result identifier")
                numbers.add(number)
                definitions[f"%t{number}"] = (op["type"], label, offset)
    for block in blocks:
        last = block["operations"][-1]
        for target in last["targets"] if last["op"] != "phi" else ():
            require(target in starts, "unknown branch target")
        if block["handler"] != "" and block["handler"] not in starts:
            raise Unsupported("a covered block's landing block is missing")
    # Every edge: terminator targets (an invoke's unwind edge among them), each check's separate
    # error block, and, conservatively, from anywhere in a covered block to its landing block.
    edges = {}
    for block in blocks:
        last = block["operations"][-1]
        out = list(last["targets"])
        if last["op"] == "check":
            key = last["descriptor"] or last["text"]
            if key not in targets_of_checks or targets_of_checks[key] not in starts:
                raise Unsupported("a check's error block is not in the snapshot")
            out.append(targets_of_checks[key])
        if block["handler"] != "":
            out.append(block["handler"])
        edges.setdefault(block["label"], [])
        edges[block["label"]] += out
    entry_label = blocks[0]["label"]
    require(entry_label != "", "the entry block needs a label")
    reached = {entry_label}
    pending = [entry_label]
    while pending:
        for target in edges[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    # Blocks that no edge reaches cannot run; they are omitted and counted.
    live = [block for block in blocks if block["label"] in reached]
    predecessors = {block["label"]: set() for block in live}
    for block in live:
        for target in edges[block["label"]]:
            predecessors[target].add(block["label"])
    dominators = {block["label"]: ({entry_label} if block["label"] == entry_label else set(reached))
                  for block in live}
    changed = True
    while changed:
        changed = False
        for block in live:
            label = block["label"]
            if label != entry_label:
                common = set.intersection(*(dominators[p] for p in predecessors[label]))
                updated = {label} | common
                if updated != dominators[label]:
                    dominators[label] = updated
                    changed = True

    # Values the function uses as dyn, which alone can carry a tag; a slot whose address reaches
    # anything but an access is not private; addresses derived from a box must not be stored to.
    dynamic = {f"%aid{index}" for index in range(len(parameters))}
    escaped = set()
    for block in live:
        for op in block["operations"]:
            if op["type"] == "dyn":
                dynamic.update(f"%t{number}" for number in op["results"])
            for position, operand in enumerate(op["operands"]):
                value = operand["value"]
                if operand["type"] == "dyn" and value.startswith("%"):
                    dynamic.add(value)
                if value in slots and not (position == 0 and op["op"] in SLOT_ACCESS):
                    escaped.add(value)
    for parameter in range(len(parameters)):
        if definitions[f"%a{parameter}"][0] == "dyn":
            dynamic.add(f"%a{parameter}")
    boxes = set(dynamic)
    for block in live:
        for op in block["operations"]:
            if op["op"] in {"mach.addr", "field.addr"} and op["operands"] and op["operands"][0]["value"] in boxes:
                boxes.update(f"%t{number}" for number in op["results"])
            if op["op"] in {"dyn.payload", "dyn.raw"} and op["results"]:
                boxes.add(f"%t{op['results'][0]}")

    def check_operand(operand, label, offset, predecessor=None):
        value = operand["value"]
        if value in slots:
            require(operand["type"] in {"*" + slots[value], "%ptr", "%addr"}, "slot address has wrong type")
        elif value.startswith("%"):
            require(value in definitions, f"undefined operand: {value}")
            _, defined_block, defined_offset = definitions[value]
            if defined_block is not None:
                require(defined_block in dominators, f"definition is not reachable: {value}")
                if predecessor is not None:
                    # (a phi's operand is read at the end of its predecessor, if that can run)
                    require(predecessor not in dominators or defined_block in dominators[predecessor],
                            f"definition does not dominate use: {value}")
                else:
                    require((defined_offset < offset if defined_block == label
                             else defined_block in dominators[label]), f"definition does not dominate use: {value}")

    # A block that holds only a bool phi and a branch on it joins a short-circuit condition
    # ("flag and isinstance(x, str)"). An edge into it whose incoming value is known (a constant,
    # the branch condition that chose the edge, or a tag comparison of its own block) goes
    # straight to the matching successor, as that guard where it is a comparison.
    joins = {}
    for block in live:
        operations = block["operations"]
        if (block["handler"] == "" and len(operations) == 2 and operations[0]["op"] == "phi"
                and operations[0]["type"] == "bool" and len(operations[0]["results"]) == 1
                and operations[1]["op"] == "cbr" and len(operations[1]["operands"]) == 1
                and operations[1]["operands"][0]["value"] == f"%t{operations[0]['results'][0]}"):
            phi = operations[0]
            require(len(phi["operands"]) == len(phi["targets"]), "invalid phi")
            joins[block["label"]] = ({target: operand["value"] for operand, target
                                      in zip(phi["operands"], phi["targets"])}, operations[1]["targets"])

    nodes = []
    payloads = 0
    remapped_guards = 0
    threaded = 0

    def emit(node):
        nodes.append(node)
        return len(nodes) - 1

    def following(node):
        node["next"] = len(nodes) + 1
        return emit(node)

    def guarded(state, value):
        # the guard's location: a private slot the compared value was just loaded from
        nonlocal remapped_guards
        loaded = state["loads"].get(value)
        if loaded and state["writes"].get(loaded[0], -1) == loaded[1]:
            remapped_guards += 1
            return loaded[0]
        return value

    def edge(state, target, known=None):
        # an edge to target, threaded through a short-circuit join when its value is known
        # here; known is a branch condition and its value on this edge
        nonlocal threaded
        if target not in joins:
            return {"op": "jump", "next": target}
        incoming, (yes, no) = joins[target]
        value = incoming.get(state["label"])
        if value in {"true", "false"}:
            outcome = value == "true"
        elif known is not None and value == known[0]:
            outcome = known[1]
        elif value in state["comparisons"]:
            compared, tag, predicate = state["comparisons"][value]
            threaded += 1
            return {"op": "guard", "value": guarded(state, compared), "tag": tag,
                    "yes": yes if predicate == "==" else no, "no": no if predicate == "==" else yes}
        else:
            return {"op": "jump", "next": target}
        threaded += 1
        return {"op": "jump", "next": yes if outcome else no}

    def branch_to(state, node, key, target, known):
        # point node's edge at target, or at a new node that threads the join
        threaded_node = edge(state, target, known)
        node[key] = threaded_node["next"] if threaded_node["op"] == "jump" else ("pending", threaded_node)

    for block in live:
        label = block["label"]
        starts[label] = len(nodes)
        handler = block["handler"]
        state = {"label": label, "loads": {}, "tag_reads": {}, "comparisons": {}, "writes": {}}
        loads, tag_reads, comparisons, writes = (state[key] for key in ("loads", "tag_reads", "comparisons", "writes"))

        for offset, op in enumerate(block["operations"]):
            kind, operands, results = op["op"], op["operands"], [f"%t{n}" for n in op["results"]]
            for position, operand in enumerate(operands):
                check_operand(operand, label, offset,
                              op["targets"][position] if kind == "phi" and position < len(op["targets"]) else None)
            if handler != "":
                # (an invoke's own unwind edge follows below; this covers every other point)
                emit({"op": "choice", "yes": len(nodes) + 1, "no": handler})
            address = operands[0]["value"] if operands else ""
            private = address in slots and address not in escaped
            if kind in {"mem.store", "mach.store"}:
                require(len(operands) == 2 and not results, f"invalid {kind} shape")
                if address in boxes:
                    raise Unsupported("a store into a dynamic box is outside the prototype")
            if kind == "mem.load" and private:
                shape(op, 1, 1)
                following({"op": "copy", "dst": results[0], "src": address})
                loads[results[0]] = (address, writes.get(address, -1))
            elif kind in {"mem.store", "mach.store"} and private:
                writes[address] = offset
                source = operands[1]["value"]
                if kind == "mem.store" and source in definitions:
                    following({"op": "copy", "dst": address, "src": source})
                else:
                    # (a constant, or null: an unbound local or an identity box not made yet,
                    # which has no tag for a guard to match)
                    following({"op": "havoc", "dst": address})
            elif kind == "landing":
                require(len(op["targets"]) == 1, "invalid landing shape")
                if private:
                    writes[address] = offset
                    following({"op": "havoc", "dst": address})
                emit({"op": "jump", "next": op["targets"][0]})
            elif kind == "dyn.type":
                shape(op, 1, 1, typ="dyntype")
                require(operands[0]["value"] in definitions, "dyn.type must read a dynamic argument or SSA value")
                tag_reads[results[0]] = operands[0]["value"]
                emit({"op": "jump", "next": len(nodes) + 1})
            elif kind == "ptr.cmp":
                shape(op, 2, 1, typ="bool", texts=("==", "!="))
                for read, descriptor in (operands, operands[::-1]):
                    expected = "@pys_dyntype_"
                    if read["value"] in tag_reads and descriptor["value"].startswith(expected):
                        tag = descriptor["value"][len(expected):]
                        if tag in TAGS and read["type"] == descriptor["type"] == "dyntype":
                            comparisons[results[0]] = (tag_reads[read["value"]], tag, op["text"])
                emit({"op": "jump", "next": len(nodes) + 1})
            elif kind == "dyn.payload":
                if op["text"] not in TAGS:
                    raise Unsupported(f"unsupported payload type: {op['text']}")
                shape(op, 1, 2, typ="%slot", texts=tuple(TAGS))
                require(operands[0]["type"] == "dyn" and operands[0]["value"] in definitions,
                        "dyn.payload requires a dynamic register")
                following({"op": "payload", "value": operands[0]["value"], "tag": op["text"]})
                payloads += 1
            elif kind == "br":
                shape(op, 0, 0, 1, "")
                emit(edge(state, op["targets"][0]))
            elif kind == "cbr":
                shape(op, 1, 0, 2, "")
                condition = operands[0]["value"]
                yes, no = op["targets"]
                comparison = comparisons.get(condition)
                if comparison:
                    value, tag, predicate = comparison
                    node = {"op": "guard", "value": guarded(state, value), "tag": tag}
                    keys = ("yes", "no") if predicate == "==" else ("no", "yes")
                else:
                    node = {"op": "choice"}
                    keys = ("yes", "no")
                branch_to(state, node, keys[0], yes, (condition, True))
                branch_to(state, node, keys[1], no, (condition, False))
                emit(node)
            elif kind == "switch" or (kind in {"raise", "throw"} and op["targets"]):
                # (a raise or throw in a try statement may branch to the code that handles it)
                for target in op["targets"][:-1]:
                    emit({"op": "choice", "yes": target, "no": len(nodes) + 1})
                emit({"op": "jump", "next": op["targets"][-1]})
            elif kind == "check":
                require(len(op["targets"]) == 1, "invalid check shape")
                emit({"op": "choice", "yes": op["targets"][0],
                      "no": targets_of_checks[op["descriptor"] or op["text"]]})
            elif kind in {"ret", "ret.none", "raise", "throw", "unreachable"}:
                emit({"op": "stop"})
            elif kind in INVOKES and len(op["targets"]) == 2:
                emit({"op": "choice", "yes": len(nodes) + 1, "no": op["targets"][1]})
                for result in results:
                    if result in dynamic:
                        following({"op": "havoc", "dst": result})
                emit({"op": "jump", "next": op["targets"][0]})
            else:
                # An ordinary operation, including a private slot read that is not a mem.load
                # and every access to a slot that escaped: dyn results get unknown tags.
                require(not op["targets"] or kind == "phi", f"invalid {kind} targets")
                unknown = [result for result in results if result in dynamic]
                if kind in {"mem.store", "mach.store"} and address in slots:
                    writes[address] = offset
                if not unknown:
                    emit({"op": "jump", "next": len(nodes) + 1})
                for result in unknown:
                    following({"op": "havoc", "dst": result})
            if len(nodes) > MAX_NODES:
                raise Unsupported(f"normalized function exceeds {MAX_NODES} nodes")

    # Threaded edges become their own nodes; then labels become node indices.
    for node in list(nodes):
        for key in ("yes", "no"):
            if isinstance(node.get(key), tuple):
                node[key] = emit(node[key][1])
    require(len(nodes) <= MAX_NODES, f"normalized function exceeds {MAX_NODES} nodes")
    for node in nodes:
        for key in ("next", "yes", "no"):
            if isinstance(node.get(key), str):
                node[key] = starts[node[key]]
    require(all(0 <= target < len(nodes) for node in nodes for target in successors(node)),
            "normalized target out of range")
    # Nodes the entry cannot reach never run, such as a join whose every edge was threaded;
    # dropping them keeps their unconstrained facts from weakening the nodes they lead to.
    kept = {0}
    pending = [0]
    while pending:
        for target in successors(nodes[pending.pop()]):
            if target not in kept:
                kept.add(target)
                pending.append(target)
    renumber = {old: new for new, old in enumerate(sorted(kept))}
    nodes = [nodes[old] for old in sorted(kept)]
    for node in nodes:
        for key in ("next", "yes", "no"):
            if key in node:
                node[key] = renumber[node[key]]
    certificate = infer_certificate(nodes)
    candidate = {"schema_version": 1, "program": {"entry": 0, "nodes": nodes}, "certificate": certificate}
    return candidate, {"function": symbol, "stage": "typed-after", "nodes": len(nodes),
                       "payloads": payloads, "remapped_guards": remapped_guards,
                       "threaded_edges": threaded, "omitted_blocks": len(blocks) - len(live),
                       "escaped_slots": len(escaped),
                       "scope": "dyn.payload guards in one normalized function", "limitations": LIMITATIONS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--function", required=True, help="exact function name or LLVM symbol")
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    parser.add_argument("--emit", type=Path, help="write a new candidate JSON file without checking it")
    args = parser.parse_args(argv)
    report = {"checked": False}
    try:
        snapshot, digest = read_snapshot(args.snapshot)
        report["snapshot_sha256"] = digest
        candidate, metadata = normalize_snapshot(snapshot, args.function)
        report.update(metadata)
        encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":")) + "\n"
        require(len(encoded.encode()) <= MAX_BYTES, "normalized candidate exceeds the checker input bound")
        report["candidate_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
        if args.emit:
            with args.emit.open("x", encoding="utf-8") as output:
                output.write(encoded)
            report.update(status="prepared", candidate=str(args.emit), message="Candidate only; Lean has not checked it.")
            code = 0
        else:
            completed = subprocess.run([str(args.checker.resolve())], input=encoded, capture_output=True,
                                       text=True, timeout=10)
            result = json.loads(completed.stdout, object_pairs_hook=unique_object)
            require(isinstance(result, dict) and type(result.get("accepted")) is bool,
                    "checker did not return an acceptance result")
            require(result.get("nodes") == metadata["nodes"] and result.get("payloads") == metadata["payloads"],
                    "checker counts disagree with normalized input")
            accepted = result["accepted"]
            require(completed.returncode == (0 if accepted else 1), "checker result/exit status mismatch")
            report.update(status="accepted" if accepted else "rejected", checked=True)
            code = 0 if accepted else 1
    except Unsupported as error:
        report.update(status="unsupported", message=str(error))
        code = 2
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as error:
        report.update(status="error", message=str(error))
        code = 3
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
