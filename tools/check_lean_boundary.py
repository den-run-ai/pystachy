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
import re
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-boundary"
MAX_BYTES = 4 * 1024 * 1024
MAX_NODES = 1024
MAX_FACTS = 16384
TAGS = {"float", "str", "bool"}
NATIVE_TYPES = TAGS | {"int", "None", "dyn"}
OP_KEYS = {"op", "type", "text", "immediate", "descriptor", "results", "operands", "targets"}
TERMINATORS = {"br", "cbr", "ret", "unreachable"}
SUPPORTED_OPS = TERMINATORS | {"slot", "mem.load", "mem.store", "dyn.type", "ptr.cmp",
                                "dyn.payload", "slot.pack", "slot.unpack", "scalar.bin"}
LIMITATIONS = [
    "Only dyn.payload guard safety in the selected normalized function is checked.",
    "Python normalization, snapshot fidelity, runtime tag contracts and LLVM lowering are not proved.",
    "Calls, exceptions, escaping storage, phi nodes and other unsupported operations are rejected.",
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


def instruction(value):
    require(isinstance(value, dict) and set(value) == OP_KEYS, "invalid instruction fields")
    for key in ("op", "type", "text", "descriptor"):
        require(isinstance(value[key], str) and len(value[key]) <= 256, f"invalid instruction {key}")
    if value["op"] not in SUPPORTED_OPS:
        raise Unsupported(f"unsupported operation: {value['op']}")
    require(type(value["immediate"]) is int and value["immediate"] == 0,
            "nonzero instruction immediate is unsupported")
    require(value["descriptor"] == "", "instruction descriptor is unsupported")
    require(isinstance(value["results"], list) and len(value["results"]) <= 2,
            "invalid instruction results")
    require(all(type(n) is int and 0 <= n <= 1000000 for n in value["results"]),
            "invalid result identifier")
    require(isinstance(value["operands"], list) and len(value["operands"]) <= 3,
            "invalid instruction operands")
    for operand in value["operands"]:
        require(isinstance(operand, dict) and set(operand) == {"value", "type"}, "invalid operand")
        name(operand["value"], "operand value")
        name(operand["type"], "operand type")
    require(isinstance(value["targets"], list) and len(value["targets"]) <= 2,
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
    return_type = fn.get("return_representation")
    require(isinstance(return_type, str), "invalid return representation")
    if return_type not in NATIVE_TYPES:
        raise Unsupported(f"unsupported return representation: {return_type}")
    parameters = fn.get("parameters")
    require(isinstance(parameters, list) and len(parameters) <= 128, "invalid parameters")
    definitions = {}
    for index, parameter in enumerate(parameters):
        require(isinstance(parameter, dict), "invalid parameter")
        typ = parameter.get("representation")
        require(isinstance(typ, str), "invalid parameter representation")
        if typ not in NATIVE_TYPES:
            raise Unsupported(f"unsupported parameter representation: {typ}")
        definitions[f"%a{index}"] = (typ, None, -1)
    blocks = fn.get("blocks")
    require(isinstance(blocks, list) and 0 < len(blocks) <= 256, "invalid blocks")
    slots = {}
    numbers = set()
    require(isinstance(fn.get("slots"), list) and len(fn["slots"]) <= MAX_NODES, "invalid slots")
    for raw in fn["slots"]:
        op = instruction(raw)
        shape(op, 0, 1, texts=(op["text"],))
        require(op["op"] == "slot", "expected private slot declaration")
        if op["type"] not in NATIVE_TYPES:
            raise Unsupported(f"unsupported private slot representation: {op['type']}")
        number = op["results"][0]
        require(number not in numbers, "duplicate result identifier")
        numbers.add(number)
        slot = f"%{op['text'] or 'h'}.{number}"
        require(slot not in slots and len(slot) <= 256, "duplicate or invalid slot")
        slots[slot] = op["type"]
    starts = {}
    total = 0
    for block in blocks:
        require(isinstance(block, dict) and set(block) == {"label", "handler", "operations"},
                "invalid block fields")
        label = name(block.get("label"), "block label")
        require(label not in starts, "duplicate block label")
        if block.get("handler") != "":
            raise Unsupported("exception handlers are outside the prototype")
        operations = block.get("operations")
        require(isinstance(operations, list) and operations, "empty or invalid block")
        starts[label] = total
        total += len(operations)
        require(total <= MAX_NODES, f"function exceeds {MAX_NODES} instructions")
        for offset, raw in enumerate(operations):
            op = instruction(raw)
            require((op["op"] in TERMINATORS) == (offset == len(operations) - 1),
                    "each block must end with its only supported terminator")
            for position, number in enumerate(op["results"]):
                require(number not in numbers, "duplicate result identifier")
                numbers.add(number)
                typ = "%ptr" if op["op"] == "dyn.payload" and position == 0 else op["type"]
                definitions[f"%t{number}"] = (typ, label, offset)
    entry_label = blocks[0]["label"]
    predecessors = {label: set() for label in starts}
    edges = {}
    for block in blocks:
        label = block["label"]
        targets = block["operations"][-1]["targets"]
        require(all(target in starts for target in targets), "unknown branch target")
        edges[label] = set(targets)
        for target in targets:
            predecessors[target].add(label)
    reached = {entry_label}
    pending = [entry_label]
    while pending:
        for target in edges[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    if reached != set(starts):
        raise Unsupported("unreachable blocks are outside the prototype")
    dominators = {label: ({label} if label == entry_label else set(starts)) for label in starts}
    changed = True
    while changed:
        changed = False
        for label in starts:
            if label != entry_label:
                common = set.intersection(*(dominators[p] for p in predecessors[label]))
                updated = {label} | common
                if updated != dominators[label]:
                    dominators[label] = updated
                    changed = True

    def check_operand(operand, label, offset):
        value, typ = operand["value"], operand["type"]
        if value in slots:
            require(typ == "*" + slots[value], "slot address has wrong type")
        elif value == "%idret":
            require(typ == "*dyn", "identity-return address has wrong type")
        elif value.startswith("%"):
            require(value in definitions, f"undefined operand: {value}")
            actual, defined_block, defined_offset = definitions[value]
            require(actual == typ, f"operand type disagrees with definition: {value}")
            if defined_block is not None:
                require((defined_offset < offset if defined_block == label
                         else defined_block in dominators[label]), f"definition does not dominate use: {value}")
        else:
            numeric = typ == "int" and re.fullmatch(r"-?[0-9]+", value)
            floating = typ == "float" and re.fullmatch(r"(?:-?[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?|0x[0-9A-Fa-f]+)", value)
            boolean = typ == "bool" and value in {"true", "false"}
            pointer = typ in {"dyn", "str", "None", "dyntype"} and (value == "null" or value.startswith("@"))
            require(numeric or floating or boolean or pointer, f"unsupported constant: {value}:{typ}")

    nodes = []
    payloads = 0
    remapped_guards = 0
    for block in blocks:
        label = block["label"]
        loads = {}
        tag_reads = {}
        comparisons = {}
        writes = {}
        for offset, op in enumerate(block["operations"]):
            index = len(nodes)
            nxt = index + 1
            kind, operands = op["op"], op["operands"]
            for operand in operands:
                check_operand(operand, label, offset)
                if operand["value"] in slots or operand["value"] == "%idret":
                    require(kind in {"mem.load", "mem.store"} and operand is operands[0],
                            "private/identity-return storage cannot escape")
            node = {"op": "jump", "next": nxt}
            if kind in {"mem.load", "mem.store"}:
                load = kind == "mem.load"
                shape(op, 1 if load else 2, 1 if load else 0)
                address = operands[0]["value"]
                require(address in slots or (not load and address == "%idret"),
                        "memory access must use a private slot or write-only identity return")
                typ = slots.get(address, "dyn")
                require(operands[0]["type"] == "*" + typ and
                        (op["type"] == typ if load else op["type"] == "" and operands[1]["type"] == typ),
                        "memory access types disagree")
                if load:
                    result = f"%t{op['results'][0]}"
                    if typ == "dyn":
                        node = {"op": "copy", "dst": result, "src": address, "next": nxt}
                        loads[result] = (address, writes.get(address, -1))
                else:
                    writes[address] = offset
                    if typ == "dyn":
                        source = operands[1]["value"]
                        if source.startswith("%") and source in definitions:
                            node = {"op": "copy", "dst": address, "src": source, "next": nxt}
                        else:
                            if address != "%idret" and source == "null":
                                raise Unsupported("unbound dynamic private slots are outside the prototype")
                            node = {"op": "havoc", "dst": address, "next": nxt}
            elif kind == "dyn.type":
                shape(op, 1, 1, typ="dyntype")
                require(operands[0]["type"] == "dyn", "dyn.type requires a dyn operand")
                value = operands[0]["value"]
                require(value in definitions, "dyn.type must read a dynamic argument or SSA value")
                tag_reads[f"%t{op['results'][0]}"] = value
            elif kind == "ptr.cmp":
                shape(op, 2, 1, typ="bool", texts=("==", "!="))
                require(all(a["type"] in {"dyntype", "dyn", "str", "None"} for a in operands),
                        "unsupported pointer comparison")
                for read, descriptor in (operands, operands[::-1]):
                    expected = "@pys_dyntype_"
                    if read["value"] in tag_reads and descriptor["value"].startswith(expected):
                        tag = descriptor["value"][len(expected):]
                        if tag in TAGS and read["type"] == descriptor["type"] == "dyntype":
                            comparisons[f"%t{op['results'][0]}"] = (tag_reads[read["value"]], tag, op["text"])
            elif kind == "dyn.payload":
                if op["text"] not in TAGS:
                    raise Unsupported(f"unsupported payload type: {op['text']}")
                shape(op, 1, 2, typ="%slot", texts=tuple(TAGS))
                require(operands[0]["type"] == "dyn", "dyn.payload requires a dyn operand")
                node = {"op": "payload", "value": operands[0]["value"], "tag": op["text"], "next": nxt}
                payloads += 1
            elif kind in {"slot.pack", "slot.unpack"}:
                shape(op, 1, 1)
                native = operands[0]["type"] if kind == "slot.pack" else op["type"]
                opaque = op["type"] if kind == "slot.pack" else operands[0]["type"]
                require(native in NATIVE_TYPES - {"dyn", "None"} and opaque == "%slot",
                        "unsupported opaque slot conversion")
            elif kind == "scalar.bin":
                shape(op, 2, 1, texts=("fadd", "fsub", "fmul", "fdiv", "frem", "add", "sub", "mul", "and", "or", "xor"))
                require(op["type"] in {"float", "int", "bool"} and all(a["type"] == op["type"] for a in operands),
                        "unsupported scalar operation")
                require(op["text"].startswith("f") == (op["type"] == "float"), "scalar opcode/type mismatch")
            elif kind == "br":
                shape(op, 0, 0, 1, "")
                node = {"op": "jump", "next": starts[op["targets"][0]]}
            elif kind == "cbr":
                shape(op, 1, 0, 2, "")
                require(operands[0]["type"] == "bool", "conditional branch requires a bool")
                yes, no = (starts[target] for target in op["targets"])
                comparison = comparisons.get(operands[0]["value"])
                if comparison:
                    value, tag, predicate = comparison
                    loaded = loads.get(value)
                    if loaded and writes.get(loaded[0], -1) == loaded[1]:
                        value = loaded[0]
                        remapped_guards += 1
                    node = {"op": "guard", "value": value, "tag": tag,
                            "yes": yes if predicate == "==" else no, "no": no if predicate == "==" else yes}
                else:
                    node = {"op": "choice", "yes": yes, "no": no}
            elif kind == "ret":
                shape(op, 0 if fn.get("return_representation") == "None" else 1, 0, typ="")
                if operands:
                    require(operands[0]["type"] == fn.get("return_representation"), "return type mismatch")
                node = {"op": "stop"}
            elif kind == "unreachable":
                shape(op, 0, 0, typ="")
                node = {"op": "stop"}
            else:
                raise Unsupported(f"unsupported operation {kind} in {label} at instruction {offset}")
            nodes.append(node)
    require(all(0 <= target < len(nodes) for node in nodes for target in successors(node)),
            "normalized target out of range")
    certificate = infer_certificate(nodes)
    candidate = {"schema_version": 1, "program": {"entry": 0, "nodes": nodes}, "certificate": certificate}
    return candidate, {"function": symbol, "stage": "typed-after", "nodes": len(nodes),
                       "payloads": payloads, "remapped_guards": remapped_guards,
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
