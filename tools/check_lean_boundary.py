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
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.utils import numeric_identity  # noqa: E402

DEFAULT_CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-boundary"
MAX_BYTES = 4 * 1024 * 1024
# (a whole program's snapshot, for --all; each normalized candidate keeps MAX_BYTES)
MAX_PROGRAM_BYTES = 512 * 1024 * 1024
MAX_INSTRUCTIONS = 4096
MAX_NODES = 16384
MAX_FACTS = 65536
# runtime.c's builtin DynTypes and their kinds (DK_*); their cls word is -1 and they have no
# base. A dynamic box's tag is the address of its DynType: one of these, or one the program
# emits, which the snapshot's dynamic_types table lists.
DK_NONE, DK_INT, DK_OBJ = 0, 2, 8
DF_ROLE = 256
BUILTIN_TYPES = {"@pys_dyntype_none": 0, "@pys_dyntype_bool": 1, "@pys_dyntype_int": 2,
                 "@pys_dyntype_bigint": 2, "@pys_dyntype_float": 3, "@pys_dyntype_str": 4,
                 "@pys_dyntype_list": 5, "@pys_dyntype_intlist": 5, "@pys_dyntype_biglist": 5,
                 "@pys_dyntype_dict": 6, "@pys_dyntype_tuple": 7, "@pys_dyntype_type": 12}
# Builtin payload types and the tags of the boxes whose payload has that layout (dynamic.py's
# BUILTIN and ListLayout): a bool's payload is its int value, 0 or 1, and checked and promoting
# int lists share one layout. A class's payload is read from its own and its subclasses' boxes.
BUILTIN_PAYLOADS = {
    "bool": ("@pys_dyntype_bool",), "int": ("@pys_dyntype_int", "@pys_dyntype_bool"),
    "float": ("@pys_dyntype_float",), "str": ("@pys_dyntype_str",),
    "dict[dyn,dyn]": ("@pys_dyntype_dict",), "vtuple[dyn]": ("@pys_dyntype_tuple",),
    "list[dyn]": ("@pys_dyntype_list",), "list[int]": ("@pys_dyntype_intlist", "@pys_dyntype_biglist")}
# struct DynType's cls word, in i64 words: class dispatchers switch on it
CLASS_WORD = "3"
MAX_TAGS = 262144
MAX_CONDITION = 64
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
            "big.lo", "big.hi", "exc.match", "gen.promise", "gen.resume", "gen.drop"}
TAG_OPS = {"dyn.type", "ptr.cmp", "dyn.payload"}
TERMINATORS = {"br", "cbr", "switch", "check", "ret", "ret.none", "raise", "throw",
               "unreachable", "landing"}
# A call that may raise inside a try statement is an invoke: it ends its block, and its second
# target is the unwind edge to a landing block. Resuming a generator runs its code as a call
# does; outside a generator, its promise and frame operations write no private slot or box.
INVOKES = {"rt", "call", "icall", "init", "gen.resume"}
# Operations that may read or write a slot named as their first operand; any other use of a
# slot's address makes it escape.
SLOT_ACCESS = {"mem.load", "mem.store", "mach.load", "mach.store", "landing"}
SUPPORTED_OPS = ORDINARY | TAG_OPS | TERMINATORS
LIMITATIONS = [
    "Dynamic payload guards and inventoried class layout prefixes are checked in each selected normalized function.",
    "Python normalization, snapshot fidelity, the descriptor table, runtime tag and payload layout "
    "contracts and LLVM lowering are not proved.",
    "Generators, unlisted payload types and stores into boxes or descriptors are rejected; null "
    "values get unknown tags.",
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


def read_snapshot(path, limit=MAX_BYTES):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), "snapshot must be a regular file")
        raw = source.read(limit + 1)
    require(len(raw) <= limit, f"snapshot exceeds {limit} bytes")
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


def check_payload_consumers(blocks):
    """Tie a projection's claimed type to its direct consumers, before proving its guard.

    dyn.payload lowers to an internal address and a slot of bits. Only int uses
    those bits directly; every other type first unpacks that same slot as the
    projection's declared type. Do not trust a consumer's operand annotation to
    identify a producer, or let opaque transport hide a reinterpretation.
    """
    addresses = set()
    payloads = {}
    for block in blocks:
        for op in block["operations"]:
            if op["op"] == "dyn.payload":
                shape(op, 1, 2, typ="%slot", texts=(op["text"],))
                addresses.add(f"%t{op['results'][0]}")
                payloads[f"%t{op['results'][1]}"] = op["text"]
    for block in blocks:
        for op in block["operations"]:
            for position, operand in enumerate(op["operands"]):
                value = operand["value"]
                require(value not in addresses, "dyn.payload internal address cannot be used")
                if value not in payloads:
                    continue
                typ = payloads[value]
                if op["op"] == "slot.unpack":
                    shape(op, 1, 1, typ=typ)
                    require(operand["type"] == "%slot", "dyn.payload unpack requires a slot operand")
                elif typ == "int":
                    # The runtime ABI names an uninterpreted i64 slot *T. These
                    # two constructors copy that word unchanged into a fresh
                    # optional/union box; they do not dereference it as a pointer.
                    boxed = op["op"] == "rt" and op["text"] in {"box", "ubox"}
                    if boxed and operand["type"] == "*T":
                        index = 1 if op["text"] == "ubox" else 0
                        shape(op, index + 1, 1, typ="%ptr", texts=(op["text"],))
                        require(position == index and (index == 0 or op["operands"][0]["type"] == "int"),
                                "dyn.payload int boxing requires the runtime slot argument")
                    else:
                        require(operand["type"] == "int", "dyn.payload int bits require an int operand")
                else:
                    raise Unsupported("dyn.payload bits require direct slot.unpack of the declared type")


def successors(node):
    if node["op"] == "stop":
        return []
    if node["op"] in {"guard", "choice"}:
        return [node["yes"], node["no"]]
    return [node["next"]]


def live_locations(nodes):
    """Locations whose facts a later payload may need before they are written.

    Guards inspect runtime tags without requiring prior facts. A prior fact at a
    guard matters only when a successor's obligations need it; the normal backward
    propagation already retains those. Dead copies similarly need no source facts.
    """
    reads = [{node["value"]} if node["op"] in {"payload", "class_payload"} else set() for node in nodes]
    predecessors = [[] for _ in nodes]
    for index, node in enumerate(nodes):
        for target in successors(node):
            predecessors[target].append(index)
    live = [set() for _ in nodes]
    pending = deque(range(len(nodes) - 1, -1, -1))
    queued = [True] * len(nodes)
    while pending:
        index = pending.popleft()
        queued[index] = False
        node = nodes[index]
        later = set().union(*(live[target] for target in successors(node)))
        if node["op"] == "copy":
            # A copy's source matters only when its assigned value will be read.
            # Keeping dead copy sources live can grow a certificate quadratically.
            needed = node["dst"] in later
            later.discard(node["dst"])
            if needed:
                later.add(node["src"])
        elif node["op"] == "havoc":
            later.discard(node["dst"])
        else:
            later |= reads[index]
        if later != live[index]:
            live[index] = later
            for predecessor in predecessors[index]:
                if not queued[predecessor]:
                    queued[predecessor] = True
                    pending.append(predecessor)
    return live


def infer_certificate(nodes, entry=0):
    """Suggest forward must-facts: each confines a location's tag to a set. Lean independently
    checks every transfer. Facts about locations no later node reads are dropped: a successor
    that needs one still reads it, so its predecessors keep it too."""
    live = live_locations(nodes)
    facts = [None] * len(nodes)
    facts[entry] = {}
    pending = deque([entry])
    queued = [False] * len(nodes)
    queued[entry] = True
    fact_count = 0
    iterations = 0
    while pending:
        index = pending.popleft()
        queued[index] = False
        known = facts[index]
        node = nodes[index]
        outgoing = known
        if node["op"] in {"copy", "havoc"}:
            outgoing = {value: tags for value, tags in known.items() if value != node["dst"]}
            if node["op"] == "copy" and node["src"] in known:
                outgoing[node["dst"]] = known[node["src"]]
        for edge, target in enumerate(successors(node)):
            transferred = outgoing
            if node["op"] == "guard":
                value, tested = node["value"], frozenset(node["tags"])
                transferred = dict(outgoing)
                if edge == 0:
                    transferred[value] = known[value] & tested if value in known else tested
                elif value in known:
                    transferred[value] = known[value] - tested
            transferred = {value: tags for value, tags in transferred.items() if value in live[target]}
            previous = facts[target]
            merged = (dict(transferred) if previous is None else
                      {value: previous[value] | transferred[value] for value in previous.keys() & transferred.keys()})
            if merged != previous:
                fact_count += len(merged) - len(previous or ())
                facts[target] = merged
                if not queued[target]:
                    queued[target] = True
                    pending.append(target)
        iterations += 1
        if iterations > 200000 or fact_count > MAX_FACTS:
            raise Unsupported("candidate inference exceeds the prototype's resource bound")
    certificate = [[[value, sorted(tags)] for value, tags in sorted((known or {}).items())] for known in facts]
    if sum(len(tags) for known in certificate for _, tags in known) > MAX_TAGS:
        raise Unsupported("candidate certificate exceeds the prototype's resource bound")
    return certificate


def descriptor_table(snapshot):
    """The tags of the program's boxes: runtime.c's builtin DynTypes and the program's own."""
    raw = snapshot.get("dynamic_types")
    if raw is None:
        raise Unsupported("the snapshot has no dynamic_types table; inspect the program again")
    require(isinstance(raw, list) and len(raw) <= 65536, "invalid dynamic_types table")
    types = {symbol: {"kind": kind, "cls": -1, "flags": 0, "base": "", "role": "", "payload": ""}
             for symbol, kind in BUILTIN_TYPES.items()}
    for entry in raw:
        require(isinstance(entry, dict) and set(entry) == {"symbol", "kind", "cls", "flags", "base", "role", "payload"},
                "invalid descriptor fields")
        symbol = name(entry["symbol"], "descriptor symbol")
        require(symbol.startswith("@") and symbol not in types, "duplicate or invalid descriptor")
        require(all(type(entry[key]) is int and -1 <= entry[key] < 2 ** 31 for key in ("kind", "cls", "flags")),
                "invalid descriptor word")
        require(all(isinstance(entry[key], str) and len(entry[key]) <= 4096 for key in ("base", "role", "payload")),
                "invalid descriptor reference")
        types[symbol] = {key: entry[key] for key in ("kind", "cls", "flags", "base", "role", "payload")}
    derived = {symbol: {symbol} for symbol in types}
    for symbol in types:
        # (pys_dyn_isa follows bases: each of a descriptor's ancestors admits it)
        seen = [symbol]
        base = types[symbol]["base"]
        while base:
            require(base in types and base not in seen, "invalid or cyclic descriptor base")
            derived[base].add(symbol)
            seen.append(base)
            base = types[base]["base"]
        require(types[symbol]["role"] == "" or types[symbol]["role"] in types, "invalid descriptor role")
    roles = {symbol: {other for other, entry in types.items() if entry["flags"] & DF_ROLE and entry["role"] == symbol}
             for symbol in types}
    classes = {}
    for symbol, entry in types.items():
        if entry["kind"] == DK_OBJ and entry["cls"] >= 0:
            classes.setdefault(entry["cls"], set()).add(symbol)
    return types, derived, roles, classes


def descriptor_layouts(snapshot, types):
    """Cross-check descriptor claims against the independently exported class layouts.

    Same-width pointer members remain distinct source representations. The
    ordered LLVM types also capture padding/alignment inputs, including hidden
    fields. Prefix compatibility itself is checked by Lean, not trusted here.
    """
    descriptors = {symbol: entry for symbol, entry in types.items() if entry["kind"] == DK_OBJ}
    raw = snapshot.get("dynamic_layouts")
    if not descriptors and raw is None:
        return {}
    if raw is None:
        raise Unsupported("the snapshot has no dynamic_layouts table; inspect the program again")
    require(isinstance(raw, list) and len(raw) <= 65536, "invalid dynamic_layouts table")
    layouts = {}
    for entry in raw:
        require(isinstance(entry, dict) and set(entry) == {
            "name", "descriptor", "base", "role", "number", "members", "llvm"}, "invalid class layout fields")
        payload = name(entry["name"], "class layout name")
        symbol = name(entry["descriptor"], "class layout descriptor")
        require(symbol in descriptors and symbol not in layouts, "duplicate or unknown class layout descriptor")
        descriptor = descriptors[symbol]
        require(descriptor["payload"] == payload and descriptor["cls"] == entry["number"]
                and type(entry["number"]) is int and descriptor["base"] == entry["base"]
                and descriptor["role"] == entry["role"], "descriptor and class layout disagree")
        require(isinstance(entry["members"], list) and isinstance(entry["llvm"], list)
                and len(entry["members"]) == len(entry["llvm"]) <= 4096, "invalid class layout members")
        members = []
        for representation, llvm in zip(entry["members"], entry["llvm"], strict=True):
            require(isinstance(representation, str) and isinstance(llvm, str), "invalid class member type")
            members.append(name(json.dumps([representation, llvm], separators=(",", ":")), "class member representation"))
        layouts[symbol] = members
    require(layouts.keys() == descriptors.keys(), "class layout inventory is incomplete")
    return layouts


def isa_tags(types, derived, symbol):
    """The tags for which runtime.c's pys_dyn_isa(x, symbol) is true."""
    tags = {symbol}
    if types[symbol]["kind"] == DK_INT:
        tags |= {other for other, entry in types.items() if entry["kind"] == DK_INT}
    if types[symbol]["kind"] == DK_OBJ:
        tags |= derived[symbol] | {other for other, entry in types.items() if entry["kind"] == DK_NONE}
    return tags


def condition_size(condition):
    return 1 if condition[0] in {"atom", "const", "opaque"} else sum(condition_size(c) for c in condition[1:])


def check_header(snapshot):
    """Every check reads a completed typed-after snapshot of inspection schema 1."""
    require(isinstance(snapshot, dict), "snapshot must be an object")
    require(type(snapshot.get("schema_version")) is int and snapshot["schema_version"] == 1,
            "expected inspection schema_version 1")
    if snapshot.get("stage") != "typed-after" or snapshot.get("status") != "completed":
        raise Unsupported("only completed typed-after snapshots are supported")


def normalize_snapshot(snapshot, function):
    name(function, "function selector")
    check_header(snapshot)
    functions = snapshot.get("functions")
    require(isinstance(functions, list) and len(functions) <= 65536, "invalid functions list")
    require(all(isinstance(fn, dict) for fn in functions), "invalid function record")
    selected = [fn for fn in functions if fn.get("symbol") == function or fn.get("name") == function]
    require(len(selected) == 1, "--function must select exactly one function by exact name or symbol")
    fn = selected[0]
    symbol = name(fn.get("symbol"), "function symbol")
    types, derived, roles, classes = descriptor_table(snapshot)
    layouts = descriptor_layouts(snapshot, types)
    referenced_layouts = {}
    read_layouts = {}

    def accepted(payload):
        # the tags of the boxes whose payload a read of static type payload may take
        if payload in BUILTIN_PAYLOADS:
            return set(BUILTIN_PAYLOADS[payload])
        holders = [symbol for symbol, entry in types.items() if entry["payload"] == payload]
        if len(holders) != 1:
            raise Unsupported(f"unsupported payload type: {payload}")
        holder = holders[0]
        if types[holder]["kind"] == DK_OBJ:
            # Every admitted concrete descriptor must support this projection.
            # An ancestry edge or a secondary-role flag is not itself evidence.
            tags = derived[holder] | roles[holder]
            for tag in sorted(tags):
                require(tag in layouts, "class payload descriptor has no layout")
                referenced_layouts[tag] = layouts[tag]
            referenced_layouts[holder] = layouts[holder]
            read_layouts[payload] = holder
            return tags
        return {holder}
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
    identity_arguments = set()
    for index, parameter in enumerate(parameters):
        require(isinstance(parameter, dict), "invalid parameter")
        typ = name(parameter.get("representation"), "parameter representation")
        definitions[f"%a{index}"] = (typ, None, -1)
        if numeric_identity(typ):
            identity_arguments.add(f"%aid{index}")
            definitions[f"%aid{index}"] = ("dyn", None, -1)
    targets_of_checks = fn.get("check_targets", {})
    require(isinstance(targets_of_checks, dict) and all(
        isinstance(key, str) and len(key) <= 4096 and isinstance(label, str)
        for key, label in targets_of_checks.items()), "invalid check targets")
    blocks = fn.get("blocks")
    require(isinstance(blocks, list) and blocks, "invalid blocks")
    if len(blocks) > 1024:
        raise Unsupported("function exceeds 1024 blocks")
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
    # A typed-after snapshot follows exception lowering (gen_eh_ir): each call that a landing
    # block covers and that may raise became an invoke, whose unwind edge is a target, and a
    # landing block that no invoke reaches was dropped. A block whose landing block was dropped
    # keeps a stale handler name but has no exception edge: a call there that raises anyway
    # leaves the function.
    blocks = [dict(block, handler="") if block["handler"] != "" and block["handler"] not in starts
              else block for block in blocks]
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
    check_payload_consumers(live)
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
    dynamic = set(identity_arguments)
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
    # (to a fixed point: blocks need not be listed in dominance order)
    boxes = set(dynamic)
    changed = True
    while changed:
        changed = False
        for block in live:
            for op in block["operations"]:
                derived_addresses = set()
                if op["op"] in {"dyn.payload", "dyn.raw", "dyn.type"} and op["results"]:
                    # (a box's payload address and its immutable DynType)
                    derived_addresses.add(f"%t{op['results'][0]}")
                if op["op"] in {"mach.addr", "field.addr", "select", "phi"} and any(
                        operand["value"] in boxes for operand in op["operands"]):
                    derived_addresses.update(f"%t{number}" for number in op["results"])
                if not derived_addresses <= boxes:
                    boxes |= derived_addresses
                    changed = True

    def check_operand(operand, label, offset, predecessor=None):
        value = operand["value"]
        if value in slots:
            require(operand["type"] in {"*" + slots[value], "%ptr", "%addr"}, "slot address has wrong type")
        elif value == "%idret":
            require(operand["type"] == "*dyn", "identity-return address has wrong type")
        elif value in identity_arguments:
            require(operand["type"] == "dyn", "identity argument has wrong type")
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

    # A private slot that holds the same box as an SSA value: one loaded from it or stored into
    # it, with no write to the slot on any path since. A guard of that value then also guards
    # the slot, whose later reloads keep the fact. Each definition of the value (a loop runs it
    # again) or write to the slot ends the pairing; joins keep the pairs every predecessor has,
    # and a landing block those its covered block has at every point.
    def pairing(state, op):
        kind, operands = op["op"], op["operands"]
        address = operands[0]["value"] if operands else ""
        results = {f"%t{n}" for n in op["results"]}
        state = {pair for pair in state if pair[0] not in results}
        if address in slots and address not in escaped and kind in {"mem.store", "mach.store", "landing"}:
            state = {pair for pair in state if pair[1] != address}
            if (kind == "mem.store" and len(operands) == 2 and operands[1]["type"] == "dyn"
                    and operands[1]["value"] in definitions and slots[address] == "dyn"):
                state.add((operands[1]["value"], address))
        elif (kind == "mem.load" and address in slots and address not in escaped
              and slots[address] == "dyn" and op["type"] == "dyn" and len(results) == 1):
            state.add((f"%t{op['results'][0]}", address))
        return frozenset(state)

    entry_pairs = {entry_label: frozenset()}
    exit_pairs = {}
    order = [block["label"] for block in live]
    by_label = {block["label"]: block for block in live}
    changed = True
    rounds = 0
    while changed:
        changed = False
        rounds += 1
        if rounds > 1000:
            raise Unsupported("slot pairing exceeds the prototype's resource bound")
        for label in order:
            if label not in entry_pairs:
                continue
            block = by_label[label]
            state = entry_pairs[label]
            everywhere = state
            for op in block["operations"]:
                if op["op"] == "phi":
                    state = frozenset(pair for pair in state if pair[0] not in {f"%t{n}" for n in op["results"]})
                    continue
                state = pairing(state, op)
                everywhere = everywhere & state
            exit_pairs[label] = state
            last = block["operations"][-1]
            outgoing = [(target, state) for target in last["targets"]]
            if last["op"] in INVOKES and len(last["targets"]) == 2:
                outgoing[1] = (last["targets"][1], everywhere)
            if last["op"] == "check":
                outgoing.append((targets_of_checks[last["descriptor"] or last["text"]], state))
            if block["handler"] != "":
                outgoing.append((block["handler"], everywhere))
            for target, pairs in outgoing:
                merged = pairs if target not in entry_pairs else entry_pairs[target] & pairs
                if target not in entry_pairs or merged != entry_pairs[target]:
                    entry_pairs[target] = merged
                    changed = True

    # A block that holds only a bool phi and a branch on it joins a short-circuit condition
    # ("flag and isinstance(x, str)"). An edge into it whose incoming value is known (a constant,
    # the branch condition that chose the edge, or a condition of its own block) goes straight
    # to the matching successor, through that condition's guards.
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
    paired_guards = 0
    threaded = 0
    stop = ("node", {"op": "stop"})

    def emit(node):
        nodes.append(node)
        return len(nodes) - 1

    def following(node):
        node["next"] = len(nodes) + 1
        return emit(node)

    # A condition is a tree over atoms: ("atom", box, tags) holds when the box's tag is one of
    # tags. Unknown booleans are opaque: both outcomes stay possible. A reference to code is a
    # block label, a node index or a ("node", fields) tree that is placed once, at the end.
    def decide(state, condition, yes, no):
        nonlocal paired_guards
        kind = condition[0]
        if kind == "const":
            return yes if condition[1] else no
        if kind == "not":
            return decide(state, condition[1], no, yes)
        if kind == "and":
            return decide(state, condition[1], decide(state, condition[2], yes, no), no)
        if kind == "or":
            return decide(state, condition[1], yes, decide(state, condition[2], yes, no))
        if kind == "opaque":
            return ("node", {"op": "choice", "yes": yes, "no": no})
        box, tags = condition[1], sorted(condition[2])
        slots_of = sorted(slot for value, slot in state["pairs"] if value == box)
        if not slots_of:
            return ("node", {"op": "guard", "value": box, "tags": tags, "yes": yes, "no": no})
        # (the slot holds this box: a path on which their tests disagree cannot run)
        paired_guards += 1
        return ("node", {"op": "guard", "value": slots_of[0], "tags": tags,
                         "yes": ("node", {"op": "guard", "value": box, "tags": tags, "yes": yes, "no": stop}),
                         "no": ("node", {"op": "guard", "value": box, "tags": tags, "yes": stop, "no": no})})

    def edge(state, target, known=None):
        # a reference to target, threaded through a short-circuit join when its value is known
        # here; known is a branch condition and its value on this edge
        nonlocal threaded
        if target not in joins:
            return target
        incoming, (yes, no) = joins[target]
        value = incoming.get(state["label"])
        if value in {"true", "false"}:
            outcome = value == "true"
        elif known is not None and value == known[0]:
            outcome = known[1]
        elif value in conditions:
            threaded += 1
            return decide(state, conditions[value], yes, no)
        else:
            return target
        threaded += 1
        return yes if outcome else no

    # Tests of a box's tag: pys_dyn_isa and pys_dyn_role_isa (runtime.c), comparisons of its
    # DynType with a descriptor, the class number a DynType holds, and boolean combinations of
    # these. Operands are SSA values whose definitions dominate their uses (check_operand), so
    # wherever a test's result is used its boxes still hold the values it tested.
    tag_reads, class_addresses, class_reads, conditions = {}, {}, {}, {}

    def condition_of(value):
        if value in {"true", "false"}:
            return ("const", value == "true")
        return conditions.get(value, ("opaque",))

    changed = True
    while changed:
        changed = False
        for block in live:
            for op in block["operations"]:
                kind, operands, results = op["op"], op["operands"], [f"%t{n}" for n in op["results"]]
                if len(results) != 1:
                    continue
                result = results[0]
                found, test = None, None
                if kind == "dyn.type" and len(operands) == 1:
                    found = tag_reads, operands[0]["value"]
                elif (kind == "mach.addr" and op["text"] == "int" and len(operands) == 2
                      and operands[0]["value"] in tag_reads and operands[1]["value"] == CLASS_WORD):
                    found = class_addresses, tag_reads[operands[0]["value"]]
                elif (kind == "mach.load" and op["type"] == "int" and len(operands) == 1
                      and operands[0]["value"] in class_addresses):
                    found = class_reads, class_addresses[operands[0]["value"]]
                elif kind == "rt" and op["text"] in {"dyn.isa", "dyn.role_isa"} and not op["targets"]:
                    shape(op, 2, 1, texts=(op["text"],))
                    box, descriptor = operands[0]["value"], operands[1]["value"]
                    if (box in dynamic or box.startswith("@")) and descriptor in types:
                        tags = isa_tags(types, derived, descriptor)
                        if op["text"] == "dyn.role_isa":
                            tags |= roles[descriptor]
                        test = ("atom", box, frozenset(tags))
                elif kind == "ptr.cmp" and op["text"] in {"==", "!="} and len(operands) == 2:
                    for read, descriptor in (operands, operands[::-1]):
                        if (read["value"] in tag_reads and descriptor["value"] in types
                                and read["type"] == descriptor["type"] == "dyntype"):
                            atom = ("atom", tag_reads[read["value"]], frozenset({descriptor["value"]}))
                            test = atom if op["text"] == "==" else ("not", atom)
                            break
                elif kind == "num.cmp" and op["text"] in {"==", "!="} and len(operands) == 2:
                    for tested, zero in (operands, operands[::-1]):
                        if tested["value"] in conditions and zero["value"] == "0":
                            test = conditions[tested["value"]]
                            test = test if op["text"] == "!=" else ("not", test)
                            break
                elif (kind == "scalar.bin" and op["type"] == "bool" and op["text"] in {"and", "or", "xor"}
                      and len(operands) == 2):
                    left, right = (condition_of(operand["value"]) for operand in operands)
                    if op["text"] == "xor":
                        if operands[1]["value"] == "true":
                            test = ("not", left)
                        elif operands[0]["value"] == "true":
                            test = ("not", right)
                    elif left != ("opaque",) or right != ("opaque",):
                        test = (op["text"], left, right)
                if test is not None and condition_size(test) <= MAX_CONDITION:
                    found = conditions, test
                if found is not None and found[0].get(result) != found[1]:
                    found[0][result] = found[1]
                    changed = True

    for block in live:
        label = block["label"]
        starts[label] = len(nodes)
        handler = block["handler"]
        state = {"label": label, "pairs": entry_pairs[label]}

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
            if kind in {"gen.promise", "gen.resume", "gen.drop"} and len(operands) != 1:
                # (without a handle, gen.promise is a generator's own suspension state)
                raise Unsupported("a generator's own suspension is outside the prototype")
            if kind in {"mem.store", "mach.store"}:
                require(len(operands) == 2 and not results, f"invalid {kind} shape")
                if address in boxes:
                    raise Unsupported("a store into a dynamic box or its descriptor is outside the prototype")
            if kind == "mem.load" and private:
                shape(op, 1, 1)
                following({"op": "copy", "dst": results[0], "src": address})
            elif kind in {"mem.store", "mach.store"} and private:
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
                    following({"op": "havoc", "dst": address})
                emit({"op": "jump", "next": op["targets"][0]})
            elif kind == "dyn.type":
                shape(op, 1, 1, typ="dyntype")
                # (a dyn operand is in `dynamic`, so each of its definitions resets its tag)
                require(operands[0]["type"] == "dyn" and (operands[0]["value"] in definitions
                                                          or operands[0]["value"].startswith("@")),
                        "dyn.type must read a dynamic argument, SSA value or constant box")
                emit({"op": "jump", "next": len(nodes) + 1})
            elif kind == "ptr.cmp":
                shape(op, 2, 1, typ="bool", texts=("==", "!="))
                emit({"op": "jump", "next": len(nodes) + 1})
            elif kind == "dyn.payload":
                tags = accepted(op["text"])
                shape(op, 1, 2, typ="%slot", texts=(op["text"],))
                require(operands[0]["type"] == "dyn" and (operands[0]["value"] in definitions
                                                          or operands[0]["value"].startswith("@")),
                        "dyn.payload requires a dynamic register or constant box")
                node = {"op": "payload", "value": operands[0]["value"], "tags": sorted(tags)}
                if op["text"] in read_layouts:
                    node.update(op="class_payload", layout=read_layouts[op["text"]])
                following(node)
                payloads += 1
            elif kind == "br":
                shape(op, 0, 0, 1, "")
                emit({"op": "jump", "next": edge(state, op["targets"][0])})
            elif kind == "cbr":
                shape(op, 1, 0, 2, "")
                condition = operands[0]["value"]
                yes, no = op["targets"]
                emit({"op": "jump", "next": decide(state, condition_of(condition),
                                                   edge(state, yes, (condition, True)),
                                                   edge(state, no, (condition, False)))})
            elif kind == "check":
                # (its error block runs where its condition holds)
                require(len(op["targets"]) == 1 and len(operands) == 1, "invalid check shape")
                emit({"op": "jump", "next": decide(state, condition_of(operands[0]["value"]),
                                                   targets_of_checks[op["descriptor"] or op["text"]],
                                                   op["targets"][0])})
            elif kind == "switch" and operands and operands[0]["value"] in class_reads:
                # A class dispatcher: its cases are class numbers, whose program DynTypes it
                # takes (no builtin descriptor has one); the first target is the default.
                require(len(op["targets"]) == len(operands), "invalid switch shape")
                cases = [operand["value"] for operand in operands[1:]]
                require(len(set(cases)) == len(cases), "a switch repeats a case")
                choice = op["targets"][0]
                for case, target in reversed(list(zip(cases, op["targets"][1:]))):
                    number = int(case) if case.isdigit() else -1
                    tags = classes.get(number, set())
                    test = ("atom", class_reads[operands[0]["value"]], frozenset(tags)) if tags else ("opaque",)
                    choice = decide(state, test, target, choice)
                emit({"op": "jump", "next": choice})
            elif kind == "switch" or (kind in {"raise", "throw"} and op["targets"]):
                # (a raise or throw in a try statement may branch to the code that handles it)
                for target in op["targets"][:-1]:
                    emit({"op": "choice", "yes": target, "no": len(nodes) + 1})
                emit({"op": "jump", "next": op["targets"][-1]})
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
                if not unknown:
                    emit({"op": "jump", "next": len(nodes) + 1})
                for result in unknown:
                    following({"op": "havoc", "dst": result})
            if kind != "phi":
                state["pairs"] = pairing(state["pairs"], op)
            else:
                state["pairs"] = frozenset(pair for pair in state["pairs"] if pair[0] not in results)
            if len(nodes) > MAX_NODES:
                raise Unsupported(f"normalized function exceeds {MAX_NODES} nodes")

    # Condition trees become their own nodes; then labels become node indices.
    placed = {}

    def place(reference):
        if not isinstance(reference, tuple):
            return reference
        if id(reference) not in placed:
            node = dict(reference[1])
            for key in ("yes", "no", "next"):
                if key in node:
                    node[key] = place(node[key])
            placed[id(reference)] = emit(node)
            if len(nodes) > MAX_NODES:
                raise Unsupported(f"normalized function exceeds {MAX_NODES} nodes")
        return placed[id(reference)]

    for node in list(nodes):
        for key in ("yes", "no", "next"):
            if isinstance(node.get(key), tuple):
                node[key] = place(node[key])
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
    candidate = {"schema_version": 3, "program": {"entry": 0, "nodes": nodes}, "certificate": certificate,
                 "layouts": [{"tag": tag, "members": members} for tag, members in sorted(referenced_layouts.items())]}
    return candidate, {"function": symbol, "stage": "typed-after", "nodes": len(nodes),
                       "payloads": payloads, "layouts": sum(len(node["tags"]) for node in nodes if node["op"] == "class_payload"),
                       "paired_guards": paired_guards,
                       "threaded_edges": threaded, "omitted_blocks": len(blocks) - len(live),
                       "escaped_slots": len(escaped),
                       "scope": "dyn.payload guards in one normalized function", "limitations": LIMITATIONS}


def encode(candidate):
    encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":")) + "\n"
    require(len(encoded.encode()) <= MAX_BYTES, "normalized candidate exceeds the checker input bound")
    return encoded


def run_checker(checker, encoded, metadata):
    """Whether the Lean checker accepts every proof obligation of one encoded candidate."""
    completed = subprocess.run([str(Path(checker).resolve())], input=encoded, capture_output=True,
                               text=True, timeout=10)
    result = json.loads(completed.stdout, object_pairs_hook=unique_object)
    require(isinstance(result, dict) and type(result.get("accepted")) is bool,
            "checker did not return an acceptance result")
    require(result.get("nodes") == metadata["nodes"] and result.get("payloads") == metadata["payloads"],
            "checker counts disagree with normalized input")
    if "layouts" in metadata:
        require(result.get("layouts") == metadata["layouts"], "checker layout count disagrees with normalized input")
    accepted = result["accepted"]
    require(completed.returncode == (0 if accepted else 1), "checker result/exit status mismatch")
    return accepted


def payload_functions(snapshot):
    """(symbol, dyn.payload operations) for each function of the snapshot that has any."""
    functions = snapshot.get("functions") if isinstance(snapshot, dict) else None
    require(isinstance(functions, list) and len(functions) <= 65536, "invalid functions list")
    found = []
    for fn in functions:
        require(isinstance(fn, dict) and isinstance(fn.get("blocks"), list)
                and all(isinstance(block, dict) and isinstance(block.get("operations"), list)
                        for block in fn["blocks"]), "invalid function record")
        reads = sum(isinstance(op, dict) and op.get("op") == "dyn.payload"
                    for block in fn["blocks"] for op in block["operations"])
        if reads:
            found.append((name(fn.get("symbol"), "function symbol"), reads))
    require(len({symbol for symbol, _ in found}) == len(found), "duplicate function symbol")
    return found


# Severity order of --all's results: its status and exit code are its worst function's.
OUTCOMES = {"accepted": 0, "unsupported": 2, "rejected": 1, "error": 3}
SEVERITY = ("accepted", "unsupported", "rejected", "error")


def check_all(snapshot, checker=DEFAULT_CHECKER):
    """Check every function of the snapshot that reads a dynamic payload. A read in a block that
    no edge reaches cannot run: it counts as proved with its function. Returns the report's
    fields and the exit code of the worst result. The header is checked first: a snapshot with
    no payload read passes only if it is complete."""
    check_header(snapshot)
    records = []
    for symbol, reads in payload_functions(snapshot):
        record = {"function": symbol, "reads": reads}
        try:
            candidate, metadata = normalize_snapshot(snapshot, symbol)
            encoded = encode(candidate)
            record.update(payloads=metadata["payloads"], nodes=metadata["nodes"],
                          candidate_sha256=hashlib.sha256(encoded.encode()).hexdigest())
            record["status"] = "accepted" if run_checker(checker, encoded, metadata) else "rejected"
        except Unsupported as error:
            record.update(status="unsupported", message=str(error))
        except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as error:
            record.update(status="error", message=str(error))
        records.append(record)
    worst = max((record["status"] for record in records), key=SEVERITY.index, default="accepted")
    counts = {status: sum(record["status"] == status for record in records) for status in SEVERITY}
    totals = {"functions": len(snapshot["functions"]), "payload_functions": len(records),
              "reads": sum(record["reads"] for record in records),
              "proved_reads": sum(record["reads"] for record in records if record["status"] == "accepted"),
              **counts}
    return {"status": worst, "checked": counts["unsupported"] + counts["error"] == 0,
            "functions": records, "totals": totals,
            "scope": "dyn.payload guards in every normalized function of one snapshot",
            "limitations": LIMITATIONS}, OUTCOMES[worst]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--function", help="exact function name or LLVM symbol")
    selection.add_argument("--all", action="store_true",
                           help="every function that reads a dynamic payload; exit with the worst result")
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    parser.add_argument("--emit", type=Path, help="write a new candidate JSON file without checking it")
    args = parser.parse_args(argv)
    if args.all and args.emit:
        parser.error("--emit writes one function's candidate: select it with --function")
    report = {"checked": False}
    try:
        snapshot, digest = read_snapshot(args.snapshot, MAX_PROGRAM_BYTES if args.all else MAX_BYTES)
        report["snapshot_sha256"] = digest
        if args.all:
            fields, code = check_all(snapshot, args.checker)
            report.update(fields)
            print(json.dumps(report, sort_keys=True))
            return code
        candidate, metadata = normalize_snapshot(snapshot, args.function)
        report.update(metadata)
        encoded = encode(candidate)
        report["candidate_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
        if args.emit:
            with args.emit.open("x", encoding="utf-8") as output:
                output.write(encoded)
            report.update(status="prepared", candidate=str(args.emit), message="Candidate only; Lean has not checked it.")
            code = 0
        else:
            accepted = run_checker(args.checker, encoded, metadata)
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
