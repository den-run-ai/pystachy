#!/usr/bin/env python3
"""Check inventoried closed-union reads and removed null checks with Lean.

The existing, audited finite-tag checker supplies the proof kernel. This adapter
never asks the compiler's union or nullcheck solver whether an obligation holds.
"""
import argparse
from collections import Counter
import hashlib
import subprocess
import json
from pathlib import Path

import check_lean_access as access
import check_lean_boundary as boundary
from check_lean_effects import summaries

NULL = "null"
NONNULL = "nonnull"
REMOVALS = "removed null checks (before-pass redundancy)"
REMOVAL_CHAIN = 8  # field cells that certificate inference follows from live values
# The facts a deref's proof can use (PystachyAccess: ne by itself or through equal values and
# cells); inference suggests no others for removals. Lean checks whatever is suggested.
REMOVAL_FACTS = frozenset({"eq", "ne", "cell", "absurd"})
LIMITATIONS = (
    "Proves union guard safety in a normalized finite-tag model, and removed null checks redundant "
    "in the before-pass graph in the access model (fields, tracked globals, closure cells and write "
    "effects) or the finite-tag model. The Python adapters, inspection fidelity, declared union "
    "domains, the classes table, runtime effect contracts and union tag/layout ABI are trusted. "
    "Does not prove raw union reconstruction, payload unpacking, GC, lifetime, pass "
    "equivalence or source/LLVM semantics. Unsupported forms fail closed."
)


def union_members(typ):
    optional = typ.startswith("opt[") and typ.endswith("]")
    if optional:
        typ = typ[4:-1]
    if not typ.startswith("union[") or not typ.endswith("]"):
        return None
    body, level, start, parts = typ[6:-1], 0, 0, []
    for pos, char in enumerate(body):
        if char == "[":
            level += 1
        elif char == "]":
            level -= 1
        elif char == "," and level == 0:
            parts.append(body[start:pos])
            start = pos + 1
        boundary.require(level >= 0, "unbalanced union type")
    parts.append(body[start:])
    boundary.require(level == 0 and len(parts) >= 2 and len(set(parts)) == len(parts)
                     and all(parts), "invalid union type")
    # Class/file union members may themselves be null. Conservatively retain null
    # unless every member belongs to a known nonnullable value representation.
    value = {"int", "float", "bool", "str", "bytes", "big", "complex"}
    nullable = optional or any(p not in value and not p.startswith(
        ("list[", "dict[", "set[", "frozenset[", "tuple[")) for p in parts)
    return sorted(["member:" + part for part in parts] + ([NULL] if nullable else []))


def union_provenance(fn):
    """Conservative union value/address provenance, independent of guard facts."""
    roots = {f"%a{n}" for n, p in enumerate(fn["parameters"])
             if union_members(p["representation"]) is not None}
    operations = [op for block in fn["blocks"] for op in block["operations"]]
    for op in operations:
        if union_members(op["type"]) is not None or (op["op"] == "rt" and op["text"] in {"ubox", "ubox_opt"}):
            roots.update(f"%t{n}" for n in op["results"])
    storage = set()
    for _ in range(2 * len(operations) + 1):
        prior = (len(roots), len(storage))
        for op in operations:
            args = op["operands"]
            # Opaque results may transport union bits; inventory must not depend
            # on an allowlist of casts, big words or packing operations.
            if any(a["value"] in roots for a in args):
                roots.update(f"%t{n}" for n in op["results"])
            if any(a["value"] in storage for a in args):
                storage.update(f"%t{n}" for n in op["results"])
            if (op["op"] in {"mem.store", "mach.store", "tuple.store"} and len(args) == 2
                    and args[1]["value"] in roots | storage):
                storage.add(args[0]["value"])
            if any(f"%t{n}" in storage for n in op["results"]):
                storage.update(a["value"] for a in args)
            if op["op"] in {"mem.load", "mach.load", "tuple.load"} and args and args[0]["value"] in storage:
                roots.update(f"%t{n}" for n in op["results"])
        if (len(roots), len(storage)) == prior:
            break
    return roots


def union_writes(fn):
    roots = union_provenance(fn)
    if not roots:
        return []
    private = {f"%{op['text']}.def.{op['results'][0]}" if op["immediate"] == 1
               else f"%{op['text'] or 'h'}.{op['results'][0]}" for op in fn["slots"] if op["immediate"] != 2}
    return [(block["label"], offset, op["op"]) for block in fn["blocks"]
            for offset, op in enumerate(block["operations"])
            if op["op"] in {"mem.store", "mach.store", "tuple.store", "landing"}
            and op["operands"] and (op["operands"][0]["value"] in roots
                                    or op["operands"][0]["value"] not in private)]


def check_call_order(fn, reads):
    """Unknown effects must not precede a read or revive a stale tag predicate."""
    labels = {block["label"] for block in fn["blocks"]}
    successors = {}
    for block in fn["blocks"]:
        targets = {target for op in block["operations"] if op["op"] != "phi" for target in op["targets"]}
        for op in block["operations"]:
            if op["op"] == "check":
                targets.add(fn["check_targets"][op["descriptor"] or op["text"]])
        if block["handler"]:
            targets.add(block["handler"])
        successors[block["label"]] = targets & labels
    reaches = {label for label, _, _ in reads}
    while True:
        earlier = reaches | {label for label, targets in successors.items() if targets & reaches}
        if earlier == reaches:
            break
        reaches = earlier
    for block in fn["blocks"]:
        later = bool(successors[block["label"]] & reaches)
        for offset in range(len(block["operations"]) - 1, -1, -1):
            op = block["operations"][offset]
            if later and op["op"] in {"rt", "call", "icall", "init", "gen.promise", "gen.resume", "gen.drop"} and not (
                    op["op"] == "rt" and op["text"] in {"ubox", "ubox_opt"}):
                raise boundary.Unsupported("opaque call may mutate a union box before a later read")
            later |= (block["label"], offset, op["op"]) in reads


def inventory(fn):
    """Inventory opcodes and union-derived addresses before guard recognition."""
    roots = union_provenance(fn)
    found = []
    for block in fn["blocks"]:
        for offset, op in enumerate(block["operations"]):
            kind = op["op"]
            machine = (kind in {"mach.load", "mem.load"} and op["type"] == "int" and op["operands"]
                       and op["operands"][0]["value"] in roots)
            if kind in {"union.tag", "union.payload", "union.raw"} or machine:
                found.append((block["label"], offset, kind))
    return found


def removed_checks(record):
    before, after = record["before"], record["after"]
    boundary.require(before["symbol"] == after["symbol"], "pass changed function identity")
    # A check's condition is an SSA identifier. Block merging changes labels and
    # targets, but does not renumber surviving conditions or change their failure.
    def key(op):
        return (op["operands"][0]["value"], op["descriptor"], op["text"])
    kept = Counter(key(op) for block in after["blocks"] for op in block["operations"] if op["op"] == "check")
    original = Counter(key(op) for block in before["blocks"] for op in block["operations"] if op["op"] == "check")
    boundary.require(all(count <= original[check] for check, count in kept.items()),
                     "nullcheck introduced or changed a check")
    boundary.require(type(record["reported_rewrites"]) is int
                     and sum(original.values()) - sum(kept.values()) == record["reported_rewrites"],
                     "removed-check inventory disagrees with pass count")
    if any(0 < kept[check] < count for check, count in original.items() if count > 1):
        raise boundary.Unsupported("ambiguous partial removal of duplicate checks")
    removed = []
    for block in before["blocks"]:
        for offset, op in enumerate(block["operations"]):
            if op["op"] != "check":
                continue
            if kept[key(op)]:
                kept[key(op)] -= 1
            else:
                removed.append((block["label"], offset))
    boundary.require(not any(kept.values()), "nullcheck introduced or changed a check")
    boundary.require(type(record["reported_rewrites"]) is int
                     and len(removed) == record["reported_rewrites"], "removed-check inventory disagrees with pass count")
    return removed


def normalize(snapshot, fn, null_obligations=None):
    """Conservative CFG translation; all facts are checked by Lean afterwards."""
    null_mode = null_obligations is not None
    read_inventory = set(inventory(fn)) if not null_mode else set()
    # Reuse structural validation, SSA dominance and opcode validation; discard its
    # analysis and certificate. Pre-exception pass snapshots are accepted only here
    # with their original check and handler edges retained below.
    validation = dict(snapshot, functions=[fn])
    boundary.normalize_snapshot(validation, fn["symbol"])
    if not null_mode and union_writes(fn):
        raise boundary.Unsupported("nonprivate writes may alias immutable union boxes")
    if not null_mode:
        check_call_order(fn, read_inventory)
    union_tags = snapshot.get("union_tags")
    if not null_mode:
        boundary.require(isinstance(union_tags, dict), "missing union_tags: inspect with --guard-evidence")
        boundary.require(all(isinstance(k, str) and type(v) is int and v > 0 for k, v in union_tags.items())
                         and len(set(union_tags.values())) == len(union_tags), "invalid union tag inventory")
    tag_names = {str(v): "member:" + k for k, v in (union_tags or {}).items()}
    types = {f"%a{n}": p["representation"] for n, p in enumerate(fn["parameters"])}
    producers, slots = {}, {}
    for op in fn["slots"]:
        if op["immediate"] == 2:
            continue
        number = op["results"][0]
        slot = f"%{op['text']}.def.{number}" if op["immediate"] == 1 else f"%{op['text'] or 'h'}.{number}"
        slots[slot] = op["type"]
    for block in fn["blocks"]:
        for offset, op in enumerate(block["operations"]):
            for result in op["results"]:
                types[f"%t{result}"] = op["type"]
                producers[f"%t{result}"] = op
    # Private immutable slots: exactly one entry store, no address escape, and
    # every load occurs after that store. SSA dominance was checked above.
    writes, escapes, load_sites = {}, set(), {}
    for block in fn["blocks"]:
        for offset, op in enumerate(block["operations"]):
            for pos, arg in enumerate(op["operands"]):
                value = arg["value"]
                if value not in slots:
                    continue
                if pos == 0 and op["op"] == "mem.store":
                    writes.setdefault(value, []).append((block["label"], offset, op["operands"][1]["value"]))
                elif pos == 0 and op["op"] == "mem.load":
                    load_sites.setdefault(value, []).append((block["label"], offset))
                else:
                    escapes.add(value)
    entry = fn["blocks"][0]["label"]
    immutable = {slot: rows[0][2] for slot, rows in writes.items() if len(rows) == 1
                 and rows[0][0] == entry and slot not in escapes
                 and (not fn["blocks"][0]["handler"] or fn["blocks"][0]["handler"] not in {b["label"] for b in fn["blocks"]})
                 and all(label != entry or pos > rows[0][1] for label, pos in load_sites.get(slot, []))}
    # Entry backedges would execute stores again and are deliberately unsupported.
    if immutable and any(entry in block["operations"][-1]["targets"] for block in fn["blocks"]):
        raise boundary.Unsupported("entry backedge with immutable slots")
    aliases = {}
    for value, op in producers.items():
        if op["op"] == "mem.load" and op["operands"][0]["value"] in immutable:
            aliases[value] = immutable[op["operands"][0]["value"]]
    def canonical(value):
        seen = set()
        while value in aliases:
            boundary.require(value not in seen, "cyclic immutable-slot alias")
            seen.add(value)
            value = aliases[value]
        return value
    def domain(value):
        if null_mode:
            return [NULL, NONNULL]
        value = canonical(value)
        op = producers.get(value)
        if op is not None and op["op"] == "rt" and op["text"] in {"ubox", "ubox_opt"}:
            tag = tag_names.get(op["operands"][0]["value"])
            if tag is None:
                raise boundary.Unsupported("dynamic union reconstruction tag")
            return [tag] + ([NULL] if op["text"] == "ubox_opt" else [])
        tags = union_members(types.get(value, ""))
        if (tags is not None and op is not None and op["op"] in {"mem.load", "mach.load"}
                and (op["operands"][0]["value"] not in slots or op["operands"][0]["value"] in escapes)
                and NULL not in tags):
            # Unknown memory may contain an uninitialized/null slot even if its
            # load's annotation promises a nonoptional union. Demand an actual
            # guard instead of treating that annotation as initialization proof.
            tags = sorted(tags + [NULL])
        return tags
    reads = {}  # tag SSA -> original box
    conditions = {}
    def condition(value, visiting=frozenset()):
        if value in {"true", "false"}:
            return ("constant", value == "true")
        if value in visiting:
            raise boundary.Unsupported("cyclic boolean definition")
        if value in conditions:
            return conditions[value]
        op = producers.get(value)
        answer = ("opaque",)
        if op is None:
            return answer
        args = op["operands"]
        if op["op"] == "ptr.cmp" and op["text"] in {"==", "!="} and len(args) == 2:
            vals = [a["value"] for a in args]
            if vals.count("null") == 1:
                box = canonical(vals[1] if vals[0] == "null" else vals[0])
                # Nullness is checked independently of narrowed use-site types.
                if null_mode or domain(box) is not None:
                    answer = ("atom", box, (NULL,))
        elif op["op"] == "num.cmp" and op["text"] in {"==", "!="} and len(args) == 2:
            for a, b in (args, args[::-1]):
                if a["value"] in reads and b["value"] in tag_names:
                    answer = ("atom", reads[a["value"]], (tag_names[b["value"]],))
                    break
        elif op["op"] == "scalar.bin" and op["type"] == "bool" and len(args) == 2:
            left, right = [condition(a["value"], visiting | {value}) for a in args]
            if op["text"] in {"and", "or"}:
                answer = (op["text"], left, right)
            elif op["text"] == "xor" and args[1]["value"] == "true":
                answer = ("not", left)
            elif op["text"] == "xor" and args[0]["value"] == "true":
                answer = ("not", right)
        if op["op"] in {"ptr.cmp", "num.cmp"} and op["text"] == "!=":
            answer = ("not", answer)
        conditions[value] = answer
        return answer
    for value, op in producers.items():
        if op["op"] == "union.tag" or (op["op"] in {"mach.load", "mem.load"} and op["type"] == "int" and op["operands"]
                                        and domain(op["operands"][0]["value"]) is not None):
            reads[value] = canonical(op["operands"][0]["value"])
    # Must-equality of private slots and immutable SSA copies. A write or SSA
    # redefinition invalidates the pair; exception edges keep only pairs that
    # hold at every instruction in the covered block.
    def pairing(pairs, op):
        results = {f"%t{n}" for n in op["results"]}
        pairs = {pair for pair in pairs if pair[0] not in results}
        args = op["operands"]
        address = args[0]["value"] if args else ""
        private = address in slots and address not in escapes
        if private and op["op"] in {"mem.store", "mach.store", "landing"}:
            pairs = {pair for pair in pairs if pair[1] != address}
            if op["op"] == "mem.store" and args[1]["value"] in types:
                pairs.add((canonical(args[1]["value"]), address))
        elif private and op["op"] == "mem.load" and len(results) == 1:
            pairs.add((canonical(next(iter(results))), address))
        return frozenset(pairs)
    entry_pairs = {entry: frozenset()}
    for _ in range(1000):
        changed = False
        for block in fn["blocks"]:
            label = block["label"]
            if label not in entry_pairs:
                continue
            pairs = entry_pairs[label]
            everywhere = pairs
            for op in block["operations"]:
                pairs = pairing(pairs, op)
                everywhere &= pairs
            last = block["operations"][-1]
            outgoing = [(target, pairs) for target in last["targets"]]
            if last["op"] in boundary.INVOKES and len(last["targets"]) == 2:
                outgoing[1] = (last["targets"][1], everywhere)
            if last["op"] == "check":
                outgoing.append((fn["check_targets"][last["descriptor"] or last["text"]], pairs))
            if block["handler"] and block["handler"] in {b["label"] for b in fn["blocks"]}:
                outgoing.append((block["handler"], everywhere))
            for target, state in outgoing:
                updated = entry_pairs[target] & state if target in entry_pairs else state
                if target not in entry_pairs or updated != entry_pairs[target]:
                    entry_pairs[target] = updated
                    changed = True
        if not changed:
            break
    else:
        raise boundary.Unsupported("guard pairing exceeded iteration bound")
    uses = Counter(a["value"] for block in fn["blocks"] for op in block["operations"] for a in op["operands"])
    joins = {}
    for block in fn["blocks"]:
        ops = block["operations"]
        if block["handler"] or len(ops) not in {2, 3} or ops[0]["op"] != "phi" or ops[-1]["op"] != "cbr":
            continue
        phi, branch = ops[0], ops[-1]
        value = f"%t{phi['results'][0]}"
        if uses[value] != 1:
            continue
        pointer = None
        if len(ops) == 2 and phi["type"] == "bool" and branch["operands"][0]["value"] == value:
            pass
        elif len(ops) == 3 and ops[1]["op"] == "ptr.cmp" and ops[1]["text"] in {"==", "!="}:
            cmp = ops[1]
            if uses[f"%t{cmp['results'][0]}"] != 1:
                continue
            if (branch["operands"][0]["value"] != f"%t{cmp['results'][0]}"
                    or sorted(a["value"] for a in cmp["operands"]) != sorted([value, "null"])):
                continue
            pointer = cmp["text"]
        else:
            continue
        boundary.require(len(phi["targets"]) == len(phi["operands"])
                         and len(set(phi["targets"])) == len(phi["targets"]), "malformed guard phi")
        joins[block["label"]] = (dict(zip(phi["targets"], (a["value"] for a in phi["operands"]), strict=True)),
                                  branch["targets"], pointer)
    active_pairs = frozenset()
    nodes, labels, obligations = [], {}, 0
    stop = ("node", {"op": "stop"})
    def emit(op):
        nodes.append(op)
    def follow(op):
        emit(dict(op, next=len(nodes) + 1))
    def assume(value, tags):
        emit({"op": "guard", "value": value, "tags": tags, "yes": len(nodes) + 1, "no": stop})
    def decide(test, yes, no):
        if test[0] == "constant":
            return yes if test[1] else no
        if test[0] == "opaque":
            return ("node", {"op": "choice", "yes": yes, "no": no})
        if test[0] == "not":
            return decide(test[1], no, yes)
        if test[0] == "and":
            return decide(test[1], decide(test[2], yes, no), no)
        if test[0] == "or":
            return decide(test[1], yes, decide(test[2], yes, no))
        slot_names = sorted(slot for value, slot in active_pairs if value == test[1])
        yes_path, no_path = yes, no
        for slot in slot_names:
            yes_path = ("node", {"op": "guard", "value": slot, "tags": list(test[2]), "yes": yes_path, "no": stop})
            no_path = ("node", {"op": "guard", "value": slot, "tags": list(test[2]), "yes": stop, "no": no_path})
        return ("node", {"op": "guard", "value": test[1], "tags": list(test[2]), "yes": yes_path, "no": no_path})
    def edge(source, target, known=None):
        if target not in joins:
            return target
        incoming, (yes, no), pointer = joins[target]
        value = incoming.get(source)
        if value is None:
            raise boundary.Unsupported("guard phi has no incoming edge")
        if pointer is not None:
            if value == "null":
                return yes if pointer == "==" else no
            return ("node", {"op": "choice", "yes": yes, "no": no})
        if known is not None and value == known[0]:
            return yes if known[1] else no
        return decide(condition(value), yes, no)
    # Parameter declaration domains constrain only the execution environment, not
    # a read's operand annotation. Null proofs assume neither parameter nonnullness
    # nor the safety of any earlier dereference.
    for value in list(types)[:len(fn["parameters"])]:
        tags = domain(value)
        if tags:
            assume(value, tags)
    if null_mode:
        assume("null", [NULL])
    for block in fn["blocks"]:
        label = block["label"]
        if label == "":
            continue
        labels[label] = len(nodes)
        active_pairs = entry_pairs.get(label, frozenset())
        for offset, op in enumerate(block["operations"]):
            kind, args, results = op["op"], op["operands"], [f"%t{n}" for n in op["results"]]
            if block["handler"] and block["handler"] in {b["label"] for b in fn["blocks"]}:
                emit({"op": "choice", "yes": len(nodes) + 1, "no": block["handler"]})
            if null_mode and (label, offset) in null_obligations:
                test = producers.get(args[0]["value"], {})
                boundary.require(test.get("op") == "ptr.cmp" and test.get("text") == "==", "removed check is not null equality")
                values = [a["value"] for a in test["operands"]]
                boundary.require(values.count("null") == 1, "removed check has no unique null operand")
                value = canonical(values[1] if values[0] == "null" else values[0])
                follow({"op": "payload", "value": value, "tags": [NONNULL]})
                obligations += 1
            is_read = (label, offset, kind) in read_inventory
            if is_read:
                value = canonical(args[0]["value"])
                tags = domain(value)
                if not tags:
                    raise boundary.Unsupported(f"union read has no declared source domain: {value}")
                allowed = ["member:" + op["text"]] if kind == "union.payload" else [t for t in tags if t != NULL]
                boundary.require(bool(allowed), "union read has no accepted member")
                follow({"op": "payload", "value": value, "tags": allowed})
                obligations += 1
            if kind == "union.raw" and not null_mode:
                raise boundary.Unsupported("raw union payload transport is outside guard-only scope")
            if kind == "br":
                emit({"op": "jump", "next": edge(label, op["targets"][0])})
            elif kind in {"cbr", "check"}:
                if kind == "check":
                    yes = fn["check_targets"][op["descriptor"] or op["text"]]
                    no = op["targets"][0]
                else:
                    yes, no = op["targets"]
                emit({"op": "jump", "next": decide(condition(args[0]["value"]),
                                                   edge(label, yes, (args[0]["value"], True)),
                                                   edge(label, no, (args[0]["value"], False)))})
            elif kind == "switch" and args[0]["value"] in reads:
                target = op["targets"][0]
                for arg, successor in reversed(list(zip(args[1:], op["targets"][1:], strict=True))):
                    if arg["value"] not in tag_names:
                        raise boundary.Unsupported("unknown union switch tag")
                    target = decide(("atom", reads[args[0]["value"]], (tag_names[arg["value"]],)), successor, target)
                emit({"op": "jump", "next": target})
            elif kind in {"ret", "ret.none", "unreachable"} or (kind in {"raise", "throw"} and not op["targets"]):
                emit({"op": "stop"})
            else:
                if kind == "mem.store" and args[0]["value"] in slots and args[0]["value"] not in escapes:
                    follow({"op": "copy", "dst": args[0]["value"], "src": canonical(args[1]["value"])})
                elif kind in {"mach.store", "landing"} and args and args[0]["value"] in slots:
                    follow({"op": "havoc", "dst": args[0]["value"]})
                for result in results:
                    tags = domain(result)
                    if not tags or result in aliases:
                        continue
                    if kind == "mem.load" and args[0]["value"] in slots and args[0]["value"] not in escapes:
                        follow({"op": "copy", "dst": result, "src": args[0]["value"]})
                    else:
                        follow({"op": "havoc", "dst": result})
                        # Result annotations do not prove construction: a phi,
                        # select or cast may carry null or a wider member set.
                        if null_mode or (kind == "rt" and op["text"] in {"ubox", "ubox_opt"}):
                            assume(result, tags)
                if op["targets"] and kind != "phi":
                    for target in op["targets"][:-1]:
                        emit({"op": "choice", "yes": target, "no": len(nodes) + 1})
                    emit({"op": "jump", "next": op["targets"][-1]})
                else:
                    emit({"op": "jump", "next": len(nodes) + 1})
            active_pairs = pairing(active_pairs, op)
    placed = {}
    def place(value):
        if not isinstance(value, tuple):
            return labels[value] if isinstance(value, str) else value
        if id(value) not in placed:
            node = dict(value[1])
            for key in ("yes", "no", "next"):
                if key in node:
                    node[key] = place(node[key])
            placed[id(value)] = len(nodes)
            nodes.append(node)
        return placed[id(value)]
    for node in list(nodes):
        for key in ("yes", "no", "next"):
            if key in node:
                node[key] = place(node[key])
    boundary.require(len(nodes) <= boundary.MAX_NODES, "guard graph exceeds resource bound")
    boundary.require(all(0 <= target < len(nodes) for node in nodes for target in boundary.successors(node)), "invalid guard edge")
    reached, pending = {0}, [0]
    while pending:
        for target in boundary.successors(nodes[pending.pop()]):
            if target not in reached:
                reached.add(target)
                pending.append(target)
    indices = {old: new for new, old in enumerate(sorted(reached))}
    nodes = [nodes[old] for old in sorted(reached)]
    for node in nodes:
        for key in ("yes", "no", "next"):
            if key in node:
                node[key] = indices[node[key]]
    payloads = sum(node["op"] == "payload" for node in nodes)
    candidate = {"schema_version": 2, "program": {"entry": 0, "nodes": nodes},
                 "certificate": boundary.infer_certificate(nodes)}
    return candidate, {"function": fn["symbol"], "obligations": obligations, "nodes": len(nodes),
                       "payloads": payloads, "omitted_unreachable_obligations": obligations - payloads, "scope": "removed null checks (before-pass redundancy)" if null_mode else "closed-union guards"}


def prove_removals(snapshot, fn, removed, effects_of, checker=boundary.DEFAULT_CHECKER,
                   access_checker=access.DEFAULT_CHECKER):
    """One nullcheck invocation's removed checks of one function, proved in the before-pass
    graph by either Lean model: the access model (PystachyAccess.lean: field cells, tracked
    globals, private slots and write effects), else the finite-tag model of this module. Each is
    a separately audited theorem over the same inventory, so either acceptance proves every
    obligation; both verdicts are reported where the first does not accept."""
    attempts = []
    try:
        nodes, meta = access.normalize_program(snapshot, fn["symbol"], effects_of, derefs=removed, record=fn)
        # (a removal may rest on a chain of field reloads from a global or slot: pi.pong.ping)
        candidate, meta = access.certify(nodes, meta, chain=REMOVAL_CHAIN, kinds=REMOVAL_FACTS)
        encoded = access.encode(candidate)
        accepted = access.run_checker(access_checker, encoded, meta)
        attempt = {"model": "access", "status": "accepted" if accepted else "rejected", "nodes": meta["nodes"],
                   "payloads": meta["derefs"], "candidate_sha256": hashlib.sha256(encoded.encode()).hexdigest()}
        if not accepted:
            attempt["error"] = (access.explain(candidate) or "")[:1000]
    except (boundary.Unsupported, ValueError, KeyError, OSError, subprocess.SubprocessError, RecursionError) as error:
        attempt = {"model": "access", "status": "unsupported" if isinstance(error, boundary.Unsupported) else "error",
                   "error": str(error)}
    attempts.append(attempt)
    if attempt["status"] != "accepted":
        try:
            candidate, meta = normalize(snapshot, fn, removed)
            encoded = boundary.encode(candidate)
            accepted = boundary.run_checker(checker, encoded, meta)
            attempt = {"model": "finite-tag", "status": "accepted" if accepted else "rejected", "nodes": meta["nodes"],
                       "payloads": meta["payloads"], "candidate_sha256": hashlib.sha256(encoded.encode()).hexdigest()}
        except (boundary.Unsupported, ValueError, KeyError, OSError, subprocess.SubprocessError,
                RecursionError) as error:
            attempt = {"model": "finite-tag", "status": "unsupported" if isinstance(error, boundary.Unsupported)
                       else "error", "error": str(error)}
        attempts.append(attempt)
    proof = next((a for a in attempts if a["status"] == "accepted"), None)
    if proof is not None:
        status = "accepted"
    else:
        status = max((a["status"] for a in attempts), key=boundary.SEVERITY.index)
    record = {"function": fn["symbol"], "scope": REMOVALS, "obligations": len(removed), "status": status,
              "checked": status == "accepted", "attempts": attempts}
    if proof is not None:
        record.update(model=proof["model"], nodes=proof["nodes"], payloads=proof["payloads"],
                      candidate_sha256=proof["candidate_sha256"])
    else:
        record["error"] = "; ".join(f"{a['model']}: {a.get('error', a['status'])}" for a in attempts)
    return record


def check_all(snapshot, checker=boundary.DEFAULT_CHECKER, access_checker=access.DEFAULT_CHECKER):
    boundary.check_header(snapshot)
    boundary.require("nullcheck_evidence" in snapshot and "union_tags" in snapshot,
                     "guard inventory missing: inspect with --guard-evidence")
    evidence = snapshot["nullcheck_evidence"]
    manifest = snapshot.get("guard_inventory")
    boundary.require(isinstance(evidence, list) and isinstance(manifest, dict), "missing guard inventory manifest")
    boundary.require(manifest.get("nullcheck_passes") == len(evidence)
                     and manifest.get("removed_checks") == sum(r["reported_rewrites"] for r in evidence),
                     "guard inventory manifest mismatch")
    records, codes = [], [0]
    work = [(fn, None) for fn in snapshot["functions"] if inventory(fn) or union_writes(fn)]
    effects_of = None
    for record in snapshot["nullcheck_evidence"]:
        try:
            removed = removed_checks(record)
        except boundary.Unsupported as error:
            records.append({"function": record["before"]["symbol"], "status": "unsupported",
                            "scope": REMOVALS, "error": str(error)})
            codes.append(2)
            continue
        if removed:
            if effects_of is None:
                effects_of = summaries(snapshot)
            proved = prove_removals(snapshot, record["before"], removed, effects_of, checker, access_checker)
            records.append(proved)
            codes.append(boundary.OUTCOMES[proved["status"]])
    for fn, removed in work:
        try:
            candidate, meta = normalize(snapshot, fn, removed)
            encoded = boundary.encode(candidate)
            accepted = boundary.run_checker(checker, encoded, meta)
            code = 0 if accepted else 1
            records.append(dict(meta, candidate_sha256=hashlib.sha256(encoded.encode()).hexdigest(), status="accepted" if accepted else "rejected", checked=accepted))
            codes.append(code)
        except (boundary.Unsupported, ValueError, KeyError, OSError, subprocess.SubprocessError, RecursionError) as error:
            code = 2 if isinstance(error, boundary.Unsupported) else 3
            records.append({"function": fn.get("symbol"), "status": "unsupported" if code == 2 else "error", "error": str(error),
                            "union_box_writes": len(union_writes(fn))})
            codes.append(code)
    code = 3 if 3 in codes else 1 if 1 in codes else 2 if 2 in codes else 0
    return {"status": {0: "accepted", 1: "rejected", 2: "unsupported", 3: "error"}[code],
            "checked": code == 0, "records": records,
            "union_reads": sum(len(inventory(fn)) for fn in snapshot["functions"]),
            "union_box_writes": sum(len(union_writes(fn)) for fn in snapshot["functions"]),
            "removed_checks": sum(r["reported_rewrites"] for r in snapshot["nullcheck_evidence"]),
            "proved_union_reads": sum(r.get("obligations", 0) for r in records if r["status"] == "accepted"
                                      and r.get("scope") == "closed-union guards"),
            "proved_removed_checks": sum(r.get("obligations", 0) for r in records if r["status"] == "accepted"
                                         and r.get("scope") == REMOVALS),
            "limitations": LIMITATIONS}, code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--checker", type=Path, default=boundary.DEFAULT_CHECKER)
    args = parser.parse_args(argv)
    try:
        snapshot, digest = boundary.read_snapshot(args.snapshot, boundary.MAX_PROGRAM_BYTES)
        report, code = check_all(snapshot, args.checker)
        report["snapshot_sha256"] = digest
    except (ValueError, KeyError, OSError, boundary.Unsupported) as error:
        report, code = {"status": "error", "error": str(error)}, 3
    print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
