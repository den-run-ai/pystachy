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
from check_lean_effects import RUNTIME, summaries, targs
from src.pystachy_compiler.specs import BIG  # (check_lean_effects puts the checkout on sys.path)

NULL = "null"
NONNULL = "nonnull"
REMOVALS = "removed null checks (before-pass redundancy)"
REMOVAL_CHAIN = 8  # field cells that certificate inference follows from live values
# The facts a deref's proof can use (PystachyAccess: ne by itself or through equal values and
# cells); inference suggests no others for removals. Lean checks whatever is suggested.
REMOVAL_FACTS = frozenset({"eq", "ne", "cell", "absurd"})
LIMITATIONS = (
    "Proves union guard safety in a normalized finite-tag model, across writes and calls only where "
    "no compiled code may write a union box (typed memory, the runtime ABI and complete inspection "
    "trusted), that union payload bits are read, boxed and stored in split union locals only as their "
    "box's member, and removed null checks redundant in the before-pass graph in the access model "
    "(fields, tracked globals, closure cells and write effects) or the finite-tag model. The Python "
    "adapters, inspection fidelity (split slot records included), declared parameter union domains, "
    "IR operand and container item types, the classes table, runtime effect contracts and union "
    "tag/layout ABI are trusted; union return domains are proved. Does not prove reconstruction "
    "from other tag sources, memory/container provenance, GC, lifetime, pass equivalence or "
    "source/LLVM semantics. Unsupported forms fail closed."
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


def field_word(classes, layouts, cls, index):
    """The memory word field index of an object of class cls names: (the class whose struct first
    has that index, index). A class's struct is a prefix of each subclass's (class_layouts: its
    fields, then its flags and identity boxes, which a subclass's fields begin with), so every
    view of one object's word has the same key."""
    seen = set()
    while cls not in seen:
        seen.add(cls)
        base = (classes.get(cls) or {}).get("base") or ""
        layout = layouts.get(base)
        if layout is None or index >= max([len(layout["fields"]), *[k + 1 for k in layout["flags"].values()],
                                           *[k + 1 for k in (layout.get("boxes") or {}).values()]]):
            break
        cls = base
    return cls, index


def union_context(snapshot):
    """What the union inventory types memory by, or None without the classes tables: the field
    words some view types as a union (a field address *U of a union U, in any function), their
    classes, whose objects a raw access may read such a word of, and the functions that may return
    a union value's address as another type (transports), whose call results are union values."""
    classes, layouts = snapshot.get("classes"), snapshot.get("class_layouts")
    if not isinstance(classes, dict) or not isinstance(layouts, dict):
        return None
    words, unknown = set(), set()
    for fn in snapshot["functions"]:
        for block in fn["blocks"]:
            for op in block["operations"]:
                if (op["op"] == "field.addr" and len(op["operands"]) == 1 and op["type"].startswith("*")
                        and union_members(op["type"][1:]) is not None):
                    cls = op["operands"][0]["type"]
                    if cls in layouts:
                        words.add(field_word(classes, layouts, cls, op["immediate"]))
                    else:
                        unknown.add(cls)  # (its field addresses stay storage: union_provenance)
    # An object of a class whose struct shares a word's root class (a base's or a subclass's view),
    # or of one that may be the same object (its secondary role, or an overlap: classes), may
    # hold the word; a field address names it, a raw access any word.
    def hierarchy(cls):
        seen = set()
        while cls not in seen and ((classes.get(cls) or {}).get("base") or "") in layouts:
            seen.add(cls)
            cls = classes[cls]["base"]
        return cls
    roots = {hierarchy(cls) for cls, _ in words}
    holders = {cls for cls in layouts if hierarchy(cls) in roots} | unknown
    for cls, info in classes.items():
        if cls in holders or info.get("role") in holders or any(o in holders for o in info.get("overlaps") or []):
            holders.add(cls)
            if info.get("role"):
                holders.add(info["role"])
            holders.update(info.get("overlaps") or [])
    context = {"classes": classes, "layouts": layouts, "words": words, "holders": holders, "transports": set()}
    # (the least set: a function returns a union value's address as another type where a ret's
    # operand is a union value by its own provenance, given what its callees return)
    while True:
        transports = {fn["symbol"] for fn in snapshot["functions"]
                      if union_members(fn.get("return_representation") or "") is None
                      and any(op["op"] == "ret" and op["operands"] and op["operands"][0]["value"] in roots
                              for roots in [union_provenance(fn, context)]
                              for block in fn["blocks"] for op in block["operations"])}
        if transports <= context["transports"]:
            return context
        context["transports"] |= transports


_CONTEXT = [None, None]  # (the last snapshot union_context was computed for, its context)


def snapshot_context(snapshot):
    """union_context(snapshot), computed once for the snapshot last asked about."""
    if _CONTEXT[0] is not snapshot:
        _CONTEXT[:] = [snapshot, union_context(snapshot)]
    return _CONTEXT[1]


def union_items(typ):
    """Whether a tuple type has an item of union type (directly)."""
    return typ.startswith("tuple[") and any(union_members(item) is not None for item in targs(typ))


def union_provenance(fn, context=None):
    """Conservative union value/address provenance, independent of guard facts.

    Values: union-typed ones and what any operation makes of them (opaque results may transport a
    box's address), but for what reads a box's words (a tag, payload bits, a word a machine read
    loaded through a box's address). Storage: memory such a value is stored into, and loads from it
    are values. With context (union_context), memory the IR types as a union is the exception: a
    field word some view types as a union, and a tuple item whose type is one, hold union values
    whose loads are unions by type; their objects and tuples are not storage, except to a raw
    access, which may read such a word under any type."""
    roots = {f"%a{n}" for n, p in enumerate(fn["parameters"])
             if union_members(p["representation"]) is not None}
    operations = [op for block in fn["blocks"] for op in block["operations"]]
    for op in operations:
        if union_members(op["type"]) is not None or (op["op"] == "rt" and op["text"] in {"ubox", "ubox_opt"}):
            roots.update(f"%t{n}" for n in op["results"])
    storage, typed, held = set(), set(), set()
    # (a private slot or module global named by its register, whose address nothing else uses: it
    # holds the union value stored into it, which its loads are, as a value)
    named = set()
    if context is not None:
        named = {slot_name(op) for op in fn["slots"]} | {a["value"] for op in operations for a in op["operands"]
                                                         if a["value"].startswith("@g.")}
        named -= {a["value"] for op in operations for position, a in enumerate(op["operands"])
                  if not (position == 0 and op["op"] in {"mem.load", "mem.store"})}
    # (a tuple value each operand of which, and its definition, types alike: its union items are
    # what its typed loads read; another view of it may read them as anything)
    views = {}
    for op in operations:
        for a in op["operands"]:
            views.setdefault(a["value"], set()).add(a["type"])
    for op in operations:
        for n in op["results"]:
            views.setdefault(f"%t{n}", set()).add(op["type"])
    for n, p in enumerate(fn["parameters"]):
        views.setdefault(f"%a{n}", set()).add(p["representation"])
    def items(tuple_value, index):
        typ = next(iter(views.get(tuple_value, set())), "")
        return (len(views.get(tuple_value, set())) == 1 and typ.startswith("tuple[")
                and index < len(targs(typ)) and union_members(targs(typ)[index]) is not None)
    if context is not None:
        for op in operations:
            if (op["op"] == "field.addr" and len(op["operands"]) == 1
                    and op["operands"][0]["type"] in context["layouts"]
                    and field_word(context["classes"], context["layouts"], op["operands"][0]["type"],
                                   op["immediate"]) in context["words"]):
                # (whatever type this view loads it as: loads from it are values)
                storage.update(f"%t{n}" for n in op["results"])
                typed.update(f"%t{n}" for n in op["results"])
            elif op["op"] == "tuple.load" and len(op["results"]) == 2 and op["operands"] and (
                    union_members(op["text"]) is not None or items(op["operands"][0]["value"], op["immediate"])):
                # (a union item's address and word, by its text or its tuple's type)
                storage.add(f"%t{op['results'][0]}")
                typed.add(f"%t{op['results'][0]}")
                roots.add(f"%t{op['results'][1]}")
    def raw(op):
        # (memory accessed through the address of an object or tuple that may hold a union word,
        # other than by a field address or a typed tuple item: it may read that word as any type;
        # but a tagged class's first word, its class tag)
        if context is None or op["op"] not in {"mach.addr", "mach.load", "mach.store", "mem.load", "mem.store"}:
            return False
        typ = op["operands"][0]["type"] if op["operands"] else ""
        if typ in context["holders"]:
            return not (op["op"] in {"mach.load", "mem.load"} and context["classes"].get(typ, {}).get("tagged")
                        and op["type"] == "int")
        return union_items(typ)
    types = {f"%a{n}": p["representation"] for n, p in enumerate(fn["parameters"])}
    types.update((f"%t{n}", op["type"]) for op in operations for n in op["results"])
    for _ in range(2 * len(operations) + 1):
        prior = (len(roots), len(storage), len(held))
        for op in operations:
            args = op["operands"]
            results = {f"%t{n}" for n in op["results"]}
            # Opaque results may transport union bits; inventory must not depend
            # on an allowlist of casts, big words or packing operations. A box's tag and payload
            # bits, and a word a machine read loads through a union-typed value (a box's), are not
            # its address (payload bits are each a member's value, whose uses normalize obliges).
            # A compiled callee's result is what it returns, typed by its return type, which a
            # union value has (box_values takes call results as opaque too).
            reads = context is not None and (op["op"] in {"union.tag", "union.payload", "union.raw"} or (
                op["op"] == "call" and op["text"] not in context["transports"]) or (
                op["op"] in {"mach.load", "mem.load"} and op["type"] == "int" and args
                and union_members(types.get(args[0]["value"], "")) is not None and args[0]["value"] not in storage))
            if any(a["value"] in roots for a in args):
                if not reads:
                    roots.update(results)
                elif op["op"] in {"union.payload", "union.raw"}:
                    roots.add(f"%t{op['results'][0]}")  # (the payload's address)
            if any(a["value"] in storage for a in args) and not (
                    op["op"] in {"mem.load", "mach.load"} and args[0]["value"] in typed):
                # (but a union a typed word holds is a value, not memory: a store through it
                # would write a box, box_writes's subject)
                storage.update(results)
            if (op["op"] in {"mem.store", "mach.store", "tuple.store"} and len(args) == 2
                    and args[1]["value"] in roots | storage):
                if op["op"] == "mem.store" and args[0]["value"] in named and args[1]["value"] not in storage:
                    held.add(args[0]["value"])
                elif not (op["op"] == "tuple.store" and context is not None
                          and items(args[0]["value"], op["immediate"]) and union_members(op["text"]) is not None):
                    storage.add(args[0]["value"])
            if raw(op):
                storage.add(args[0]["value"])
            if context is not None and op["op"] not in {"tuple.load", "tuple.store"}:
                # (a tuple with union items that an operation makes a value of another type of may
                # be read through that value as anything: it is memory again)
                for a in args:
                    if union_items(a["type"]) and any(types.get(r) != a["type"] for r in results):
                        storage.add(a["value"])
            if any(r in storage and r not in typed for r in results):
                # (named values only: a literal such as 1 or null names no memory, and as
                # storage it would taint every operation that uses the same literal)
                storage.update(a["value"] for a in args if a["value"].startswith(("%", "@")))
            if op["op"] in {"mem.load", "mach.load", "tuple.load"} and args and args[0]["value"] in storage | held:
                roots.update(results)
        if (len(roots), len(storage), len(held)) == prior:
            break
    return roots


def union_writes(fn, context=None):
    roots = union_provenance(fn, context)
    if not roots:
        return []
    private = {f"%{op['text']}.def.{op['results'][0]}" if op["immediate"] == 1
               else f"%{op['text'] or 'h'}.{op['results'][0]}" for op in fn["slots"] if op["immediate"] != 2}
    return [(block["label"], offset, op["op"]) for block in fn["blocks"]
            for offset, op in enumerate(block["operations"])
            if op["op"] in {"mem.store", "mach.store", "tuple.store", "landing"}
            and op["operands"] and (op["operands"][0]["value"] in roots
                                    or op["operands"][0]["value"] not in private)]


# Obligations on the bits of union payloads (normalize): beyond inventoried reads, each read of
# payload bits as a member's, each box made of a tag and bits, each split pair stored.
PAYLOAD_OBLIGATIONS = frozenset({"payload interpretation", "union box payload", "split union payload"})
PRESENT = "present"  # (an opt[None] split's tag 1: the member is its payload's, split_layout)
SCALAR_MEMBERS = frozenset({"member:bool", "member:float", "member:int"})
OPTIONAL_SCALARS = frozenset({"opt[bool]", "opt[float]", "opt[int]"})
# Operand types that carry a payload word without saying which member's bits it holds.
GENERIC_WORDS = frozenset({"%slot", "%ptr", "*T", "*K", "*V", "S", "*dyn", "dyn"})


def split_layout(fn, slots, tag_names):
    """The virtual union boxes of fn: the slots optimizations.gen_unionslots split, each pair of
    an int tag slot and an int payload slot replacing a local's slot (inspect_compiler's
    split_unions, which names the type it held). Tag slot -> (payload slot, the members its box
    may be, and the member each literal tag stands for: a union of numbers keeps its union tags,
    an optional scalar has 0 for None and 1 for its value, gen_uparts)."""
    records = fn.get("split_unions", [])
    boundary.require(isinstance(records, list), "invalid split union records")
    layout = {}
    for record in records:
        boundary.require(isinstance(record, dict) and all(isinstance(record.get(key), str)
                                                          for key in ("tag", "payload", "type")),
                         "invalid split union record")
        tag, payload, typ = record["tag"], record["payload"], record["type"]
        boundary.require(slots.get(tag) == "int" and slots.get(payload) == "int" and tag != payload,
                         "split union record names no int slots")
        boundary.require(tag not in layout and all(payload not in (other, entry[0]) and tag != entry[0]
                                                   for other, entry in layout.items()),
                         "split union slot named twice")
        if typ in OPTIONAL_SCALARS:
            member = "member:" + typ[4:-1]
            layout[tag] = (payload, sorted([member, NULL]), {"0": NULL, "1": member})
            continue
        if typ == "opt[None]":
            # (a None-first local, its slot's type still provisional: None or a scalar, whose
            # member is that of the bits each store pairs with presence 1, PRESENT)
            layout[tag] = (payload, sorted(SCALAR_MEMBERS | {NULL}), {"0": NULL, "1": PRESENT})
            continue
        members = union_members(typ)
        if members is None or not set(members) <= SCALAR_MEMBERS:
            raise boundary.Unsupported(f"split union of {typ}")
        decode = {literal: member for literal, member in tag_names.items() if member in members}
        boundary.require(len(decode) == len(members), "split union member without a union tag")
        layout[tag] = (payload, members, decode)
    # (only unionslots names slots so: a pair the inspection did not record stays unmodeled)
    named = {slot for slot in slots if slot.rsplit(".", 1)[0].endswith((".tag", ".pay"))}
    if named - set(layout) - {payload for payload, _, _ in layout.values()}:
        raise boundary.Unsupported("split union slots without their inspection record")
    return layout


def split_accesses(fn, layout):
    """The accesses of fn's split slots, which gen_unionslots makes in pairs: a store of the tag
    and, next, of the payload; a load of the tag and, next, of the payload. (label, offset of the
    tag access) -> (tag slot, tag value, payload value), for stores and for loads; and the
    payload accesses those cover. Any other access or use of the slots is unsupported."""
    payloads = {entry[0]: tag for tag, entry in layout.items()}
    stores, loads, covered = {}, {}, set()
    for block in fn["blocks"]:
        operations = block["operations"]
        for offset, op in enumerate(operations):
            for position, operand in enumerate(op["operands"]):
                slot = operand["value"]
                if slot not in layout and slot not in payloads:
                    continue
                if position != 0 or op["op"] not in {"mem.store", "mem.load"}:
                    raise boundary.Unsupported("split union slot used other than by its loads and stores")
                if slot in payloads:
                    if (block["label"], offset) not in covered:
                        raise boundary.Unsupported("split union payload accessed without its tag")
                    continue
                partner = operations[offset + 1] if offset + 1 < len(operations) else None
                if (partner is None or partner["op"] != op["op"] or not partner["operands"]
                        or partner["operands"][0]["value"] != layout[slot][0]):
                    raise boundary.Unsupported("split union tag accessed without its payload")
                if op["op"] == "mem.store":
                    stores[(block["label"], offset)] = (slot, op["operands"][1]["value"],
                                                        partner["operands"][1]["value"])
                else:
                    boundary.require(len(op["results"]) == 1 and len(partner["results"]) == 1,
                                     "malformed split union load")
                    loads[(block["label"], offset)] = (slot, f"%t{op['results'][0]}",
                                                       f"%t{partner['results'][0]}")
                covered.add((block["label"], offset + 1))
    return stores, loads, covered


def slot_name(op):
    """A slot's register (ir.slot_register): an assigned flag, a stack tuple or a local."""
    number = op["results"][0]
    if op["immediate"] == 1:
        return f"%{op['text']}.def.{number}"
    return f"%stk.{number}" if op["immediate"] == 2 else f"%{op['text'] or 'h'}.{number}"


# What may write a union box. pys_ubox and pys_ubox_opt alone make union boxes (runtime.c: a
# fresh box, its tag and payload stored once); the compiler treats a box as an immutable value
# (specs.FX has no effect letter for writing one), and the runtime functions it passes boxes to
# read them or store them whole, by value (eq, repr, list and dict writes). So a box's words can
# change only through a store of compiled code (or a raw copy into its destination) whose
# address lies in the box, or through code this check cannot see. Addresses that lie elsewhere:
# a stack slot, a module global, the caller's identity-return slot, a field of an object of a
# class of the program, a closure cell that an environment holds, a generator's promise, memory
# the function allocated itself, and words of such memory (in bounds: storage proofs, not this
# check, cover indexing). A list or dict write's receiver must be no box either.
FRESH_MEMORY = frozenset({"alloc", "alloc_atomic", "new"})
# Results that are words a load read, or a callee or comparison made, or the address of a tuple's
# item a tuple.store wrote: not an address the stored or other operands point into (a union-typed
# one is a box by its type).
OPAQUE_RESULTS = frozenset({"mem.load", "mach.load", "tuple.load", "tuple.store", "list.load", "list.len", "union.tag",
                            "dyn.type", "call", "icall", "init", "rt", "gen.promise", "gen.resume",
                            "ptr.cmp", "num.cmp", "int.ucmp", "scalar.cmp", "exc.match", "landing"})
WORD_READS = frozenset({"union.payload", "union.raw", "dyn.payload", "dyn.raw"})


def box_values(fn):
    """Values that may point into a union box: union-typed values, pys_ubox results and payload
    addresses, whatever addressing, selection, casts and packing make from them, and whatever
    such operations make them from (memory a function allocated and then used as a union)."""
    producers = {f"%t{n}": op for block in fn["blocks"] for op in block["operations"] for n in op["results"]}
    boxes = {f"%a{index}" for index, parameter in enumerate(fn["parameters"])
             if union_members(parameter["representation"]) is not None}
    for value, op in producers.items():
        if (union_members(op["type"]) is not None or (op["op"] == "rt" and op["text"] in {"ubox", "ubox_opt"})
                or (op["op"] in {"union.payload", "union.raw"} and value == f"%t{op['results'][0]}")):
            boxes.add(value)
    changed = True
    while changed:
        changed = False
        for value, op in producers.items():
            if (value in boxes or op["op"] in OPAQUE_RESULTS
                    or (op["op"] in WORD_READS and value != f"%t{op['results'][0]}")):
                continue
            if any(operand["value"] in boxes for operand in op["operands"]):
                boxes.add(value)
                changed = True
    sources = set(boxes)
    changed = True
    while changed:
        changed = False
        for value, op in producers.items():
            if value in sources and op["op"] not in OPAQUE_RESULTS and op["op"] not in WORD_READS:
                for operand in op["operands"]:
                    if operand["value"].startswith("%") and operand["value"] not in sources:
                        sources.add(operand["value"])
                        changed = True
    return sources


def box_writes(snapshot):
    """Every operation of every compiled function that may write a union box: (function, block,
    offset, reason). Empty, no compiled code writes one, and union tags are immutable."""
    classes = snapshot.get("classes")
    boundary.require(isinstance(classes, dict), "missing classes table: inspect with --guard-evidence")
    defined = {fn["symbol"] for fn in snapshot["functions"]}
    return [found for fn in snapshot["functions"] for found in function_box_writes(fn, classes, defined)]


def function_box_writes(fn, classes, defined):
    """box_writes's operations of one function, given the snapshot's classes table and the
    functions it defines."""
    slots = {slot_name(op) for op in fn["slots"]}
    producers = {f"%t{n}": op for block in fn["blocks"] for op in block["operations"] for n in op["results"]}
    boxes = box_values(fn)
    environments = {value for value, op in producers.items() if op["type"] == "env"}
    environments.update(f"%a{index}" for index, parameter in enumerate(fn["parameters"])
                        if parameter.get("representation") == "env")

    def outside(value, seen=frozenset()):
        if value in slots or value.startswith("@") or value == "%idret":
            return True
        op = producers.get(value)
        if op is None or value in seen or value in boxes:
            return False
        kind, operands, seen = op["op"], op["operands"], seen | {value}
        if kind == "field.addr":
            return len(operands) == 1 and operands[0]["type"] in classes
        if kind in {"alloc.fixed", "vtuple.make", "gen.promise"}:
            return True
        if kind == "rt":
            return op["text"] in FRESH_MEMORY
        if kind == "mach.load":
            # (a closure cell: the pointer at a constant word of an environment)
            address = producers.get(operands[0]["value"]) if len(operands) == 1 else None
            return (op["type"] == "%ptr" and address is not None and address["op"] == "mach.addr"
                    and len(address["operands"]) == 2 and address["operands"][0]["value"] in environments
                    and address["operands"][1]["value"].isdigit())
        if kind == "mach.addr":
            return bool(operands) and outside(operands[0]["value"], seen)
        if kind in {"select", "phi"}:
            values = [o["value"] for o in operands[1 if kind == "select" else 0:]]
            return all(v == "null" or outside(v, seen) for v in values)
        return False

    found = []
    for block in fn["blocks"]:
        for offset, op in enumerate(block["operations"]):
            kind, operands = op["op"], op["operands"]
            reason = None
            if kind in {"mem.store", "mach.store", "tuple.store", "landing"} or (
                    kind == "rt" and op["text"] == "memmove"):
                if not operands or not outside(operands[0]["value"]):
                    reason = f"{kind} to an address not shown outside union boxes"
            elif kind == "rt" and op["text"] not in RUNTIME:
                reason = f"unknown runtime function {op['text']}"
            elif kind == "rt":
                # (a box goes to the runtime only as a value word, *T or *V, which it reads or
                # stores whole: as a raw pointer or a receiver it might be written)
                parameters = targs("f[" + RUNTIME[op["text"]].split("|")[0].partition(":")[2] + "]")
                if any(operand["value"] in boxes and not (position < len(parameters)
                                                         and parameters[position].startswith("*"))
                       for position, operand in enumerate(operands)):
                    reason = f"union box passed to {op['text']} other than as a value"
            elif kind in {"list.store", "empty.kind"}:
                if operands and operands[0]["value"] in boxes:
                    reason = f"{kind} into a union box"
            elif kind == "call" and op["text"] not in defined:
                reason = f"call of {op['text']}, which the snapshot does not define"
            elif kind == "init" and "@init." + op["text"] not in defined:
                reason = f"initialization of {op['text']}, which the snapshot does not define"
            elif kind in {"gen.resume", "gen.drop"} and not (operands and operands[0]["type"].startswith("gen[")):
                reason = f"{kind} of a value that is no generator"
            if reason is not None:
                found.append((fn["symbol"], block["label"], offset, reason))
    return found


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


def payload_bits(fn):
    """Whether fn handles union payload bits normalize obliges beyond inventoried reads: split
    union slots, payloads read or raw, or boxes made of a tag and bits."""
    return bool(fn.get("split_unions")) or any(
        op["op"] in {"union.payload", "union.raw"} or (op["op"] == "rt" and op["text"] in {"ubox", "ubox_opt"})
        for block in fn["blocks"] for op in block["operations"])


def inventory(fn, context=None):
    """Inventory opcodes and union-derived addresses before guard recognition (context:
    union_context of the function's snapshot)."""
    roots = union_provenance(fn, context)
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


def normalize(snapshot, fn, null_obligations=None, immutable_boxes=False, returns=None,
              obligate_returns=False):
    """Conservative CFG translation; all facts are checked by Lean afterwards.

    With immutable_boxes (box_writes found no compiled store that may write a union box),
    writes and calls cannot change a box's tag: they change only memory the graph does not
    track (escaped slots, fields, globals), whose loads are unknown values. returns maps
    functions to the union domains their results may be assumed in (check_all proves each:
    obligate_returns makes every returned union value of fn the obligations, not its reads)."""
    null_mode = null_obligations is not None
    context = snapshot_context(snapshot)
    read_inventory = set(inventory(fn, context)) if not null_mode and not obligate_returns else set()
    returns = returns or {}
    returned = union_members(fn.get("return_representation") or "") if obligate_returns else None
    boundary.require(not obligate_returns or (not null_mode and returned is not None),
                     "return obligations need a union-returning function")
    # Reuse structural validation, SSA dominance and opcode validation; discard its
    # analysis and certificate. Pre-exception pass snapshots are accepted only here
    # with their original check and handler edges retained below.
    validation = dict(snapshot, functions=[fn])
    boundary.normalize_snapshot(validation, fn["symbol"])
    if not null_mode and not immutable_boxes and union_writes(fn, context):
        raise boundary.Unsupported("nonprivate writes may alias immutable union boxes")
    if not null_mode and not immutable_boxes:
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
    # Split union slot pairs (virtual boxes, split_layout) are tracked as a whole below.
    layout = {} if null_mode else split_layout(fn, slots, tag_names)
    halves = set(layout) | {payload for payload, _, _ in layout.values()}
    immutable = {slot: rows[0][2] for slot, rows in writes.items() if len(rows) == 1
                 and slot not in halves and rows[0][0] == entry and slot not in escapes
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
    # A split pair's tag and payload are written and read together (split_accesses): a pair load
    # gives its tag value a location, a copy of the virtual box (the tag slot's location), which
    # is what the tag tests on that value test and what its payload's bits hold.
    pair_stores, pair_loads, covered = split_accesses(fn, layout)
    decoders = {tag: layout[slot][2] for slot, tag, _ in pair_loads.values()}
    snapshots = {tag: slot for slot, tag, _ in pair_loads.values()}
    # Payload words: the bits union.payload and union.raw read of a box (results: its address,
    # then the bits), a pair load's payload, and what slot.pack and phis make of them. Each has
    # the location whose tags are the members its bits may be: its box (whose tag never
    # changes), its pair load's tag value, or a phi's own (copies on its edges, word_phis).
    words, tag_sources = {}, {}
    if not null_mode:
        used = {a["value"] for block in fn["blocks"] for op in block["operations"] for a in op["operands"]}
        for value, op in producers.items():
            if op["op"] in {"union.payload", "union.raw"}:
                if value == f"%t{op['results'][0]}":
                    if value in used:
                        raise boundary.Unsupported("union payload address used")
                else:
                    words[value] = canonical(op["operands"][0]["value"])
            elif op["op"] == "union.tag":
                tag_sources[value] = canonical(op["operands"][0]["value"])
        for _, tag, payload in pair_loads.values():
            words[payload] = tag_sources[tag] = tag
    def close_words():
        changed = True
        while changed:
            changed = False
            for value, op in producers.items():
                if value in words:
                    continue
                if op["op"] == "slot.pack" and op["operands"][0]["value"] in words:
                    words[value] = words[op["operands"][0]["value"]]
                    changed = True
                elif op["op"] == "phi" and any(a["value"] in words for a in op["operands"]):
                    words[value] = value
                    changed = True
                elif (op["op"] == "select" and op["type"] in GENERIC_WORDS
                      and any(a["value"] in words for a in op["operands"][1:])):
                    # (a typed select reads its payload operands as its type: interpretation)
                    raise boundary.Unsupported("untyped select of union payload words")
    close_words()
    def static_kinds(value, seen=frozenset()):
        """The members bits that come from no box may be, by what makes them: a word literal an
        int or a bool, a typed value its type (a slot.pack's operand's, a fixed tuple's item's or
        the type a dynamic payload read proved, their text), a phi its operands', else unknown
        (None)."""
        if value == "null":
            return [NULL]
        if value.lstrip("-").isdigit():
            return ["member:bool", "member:int"]
        if value in {"true", "false"}:
            return ["member:bool"]
        op = producers.get(value)
        if op is not None and op["op"] == "phi" and value not in words and value not in seen:
            joined = set()
            for operand in op["operands"]:
                kinds = static_kinds(operand["value"], seen | {value})
                if kinds is None:
                    return None
                joined.update(kinds)
            return sorted(joined)
        if op is not None and op["op"] == "slot.pack" and len(op["operands"]) == 1:
            typ = op["operands"][0]["type"]
        elif op is not None and op["op"] in {"tuple.load", "dyn.payload"} and value == f"%t{op['results'][-1]}":
            typ = op["text"]
        elif op is not None and op["type"].startswith("*") and value == f"%t{op['results'][0]}" and (
                op["op"] == "list.load" or (op["op"] == "rt" and op["text"] in {"list.get", "list.pop"})):
            # (a list's item, encoded *element: typed-ir.md's list reads; a generic *T one is
            # the receiver's item, as union payload provenance takes it there)
            typ = op["type"][1:]
            receiver = types.get(op["operands"][0]["value"], "") if op["operands"] else ""
            if typ == "T" and receiver.startswith("list[") and receiver.endswith("]"):
                typ = targs(receiver)[0]
        else:
            typ = types.get(value) if op is not None or value.startswith("%a") else None
        if typ is None or typ in GENERIC_WORDS or value in words:
            return None
        if typ.startswith("opt[") and typ.endswith("]"):
            return sorted(["member:" + typ[4:-1], NULL])
        return ["member:" + typ]
    def reconstructed(tag, payload):
        """The location whose tags a box made of this tag value and payload word has: both read
        of one box (union.tag and union.raw) or one pair load; else None."""
        source = tag_sources.get(tag)
        return source if source is not None and words.get(payload) == source else None
    def location_domain(location):
        return layout[snapshots[location]][1] if location in snapshots else domain(location)
    def domain(value, seen=frozenset()):
        if null_mode:
            return [NULL, NONNULL]
        value = canonical(value)
        op = producers.get(value)
        if op is not None and op["op"] == "rt" and op["text"] in {"ubox", "ubox_opt"}:
            tag = tag_names.get(op["operands"][0]["value"])
            if tag is None:
                source = reconstructed(op["operands"][0]["value"], op["operands"][1]["value"])
                if source is None or op["text"] != "ubox":
                    raise boundary.Unsupported("dynamic union reconstruction tag")
                return location_domain(source)
            return [tag] + ([NULL] if op["text"] == "ubox_opt" else [])
        tags = union_members(types.get(value, ""))
        if tags is None and op is not None and op["op"] in {"select", "phi"} and value not in seen:
            # (one of its operands, as a raw pointer: unions or null, whatever its annotation)
            joined = set()
            for operand in op["operands"][1 if op["op"] == "select" else 0:]:
                if operand["value"] == "null":
                    joined.add(NULL)
                    continue
                incoming = domain(operand["value"], seen | {value}) if operand["value"] in types else None
                if incoming is None:
                    return None
                joined.update(incoming)
            return sorted(joined)
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
                decode = decoders.get(a["value"], tag_names)
                if a["value"] in reads and b["value"] in decode and decode[b["value"]] != PRESENT:
                    answer = ("atom", reads[a["value"]], (decode[b["value"]],))
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
    reads.update((tag, tag) for tag in snapshots)
    # What a split pair store writes into its virtual box (pair_source): the member its literal
    # tag stands for, whose box its payload must hold the bits of (an obligation, but for None);
    # the box both parts were read of (union.tag and union.raw, or one pair load); or a pair phi,
    # a phi of tags and a phi of payloads in one block, which writes each edge's pair (pair_phis:
    # block -> its pair phis, each named by its tag phi, a location).
    blocks_of = {f"%t{n}": block["label"] for block in fn["blocks"] for op in block["operations"]
                 for n in op["results"]}
    pair_phis, pair_edges = {}, {}
    def phi_incoming(phi):
        op = producers[phi]
        boundary.require(len(op["targets"]) == len(op["operands"]) and len(set(op["targets"])) == len(op["targets"]),
                         "malformed phi")
        return dict(zip(op["targets"], (a["value"] for a in op["operands"]), strict=True))
    def looked_up(tag_op, payload_op):
        """The member of a dict lookup's split optional (gen_uparts): presence num.cast(raw >= 0)
        and payload dict.val_or_zero(d, raw) of one dict.find(d, key), d a dict of that scalar
        member; the payload is the value the lookup found exactly where presence is 1."""
        if (tag_op is None or payload_op is None or tag_op["op"] != "num.cast" or len(tag_op["operands"]) != 1
                or payload_op["op"] != "rt" or payload_op["text"] != "dict.val_or_zero"
                or len(payload_op["operands"]) != 2):
            return None
        test = producers.get(tag_op["operands"][0]["value"])
        raw = payload_op["operands"][1]["value"]
        lookup = producers.get(raw)
        receiver = types.get(payload_op["operands"][0]["value"], "")
        if (test is None or test["op"] != "num.cmp" or test["text"] != ">="
                or [a["value"] for a in test["operands"]] != [raw, "0"] or lookup is None
                or lookup["op"] != "rt" or lookup["text"] != "dict.find" or not lookup["operands"]
                or canonical(lookup["operands"][0]["value"]) != canonical(payload_op["operands"][0]["value"])
                or not receiver.startswith("dict[") or not receiver.endswith("]")):
            return None
        member = "member:" + targs(receiver)[1]
        return member if member in SCALAR_MEMBERS else None
    def pair_source(tag, payload, decode):
        if tag in decode:
            return ("literal", decode[tag], payload)
        source = reconstructed(tag, payload)
        if source is not None:
            return ("copy", source)
        tag_op, payload_op = producers.get(tag), producers.get(payload)
        found = looked_up(tag_op, payload_op)
        if found is not None and decode.get("1") in {found, PRESENT}:
            return ("tags", sorted([NULL, found]))
        if (tag_op is None or payload_op is None or tag_op["op"] != "phi" or payload_op["op"] != "phi"
                or blocks_of[tag] != blocks_of[payload] or set(tag_op["targets"]) != set(payload_op["targets"])):
            raise boundary.Unsupported("split union store of parts of no one box")
        entries = pair_phis.setdefault(blocks_of[tag], {})
        if entries.get(tag, (payload, decode)) != (payload, decode):
            raise boundary.Unsupported("one tag phi paired twice")
        entries[tag] = (payload, decode)
        return ("copy", tag)
    pair_writes = {key: pair_source(tag, payload, layout[slot][2])
                   for key, (slot, tag, payload) in pair_stores.items()}
    pending = True
    while pending:
        pending = False
        for label, entries in list(pair_phis.items()):
            for tag, (payload, decode) in list(entries.items()):
                tags, payloads = phi_incoming(tag), phi_incoming(payload)
                for source, value in tags.items():
                    if (tag, source) not in pair_edges:
                        pair_edges[(tag, source)] = pair_source(value, payloads[source], decode)
                        pending = True
    # (a pair phi's payload phi is a word of its own, whatever else uses it)
    for entries in pair_phis.values():
        for payload, _ in entries.values():
            words.setdefault(payload, payload)
    close_words()
    split_ops = {}  # id of a split pair's tag access -> its virtual box and what it writes or reads
    for block in fn["blocks"]:
        for offset, op in enumerate(block["operations"]):
            key = (block["label"], offset)
            if key in pair_stores:
                split_ops[id(op)] = ("store", pair_stores[key][0], pair_writes[key])
            elif key in pair_loads:
                split_ops[id(op)] = ("load", pair_loads[key][0], pair_loads[key][1])
    # Must-equality of private slots and immutable SSA copies. A write or SSA
    # redefinition invalidates the pair; exception edges keep only pairs that
    # hold at every instruction in the covered block. A virtual box equals the
    # box or pair load it was written from, and its pair loads' tag values.
    def pairing(pairs, op):
        results = {f"%t{n}" for n in op["results"]}
        pairs = {pair for pair in pairs if pair[0] not in results}
        args = op["operands"]
        address = args[0]["value"] if args else ""
        split = split_ops.get(id(op))
        if split is not None:
            kind, box, what = split
            if kind == "store":
                pairs = {pair for pair in pairs if pair[1] != box}
                if what[0] == "copy":
                    pairs.add((what[1], box))
            else:
                pairs.add((what, box))
            return frozenset(pairs)
        private = address in slots and address not in escapes and address not in halves
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
    # A union phi is its incoming operand on each edge: copies on every edge into its block keep
    # what is known of the operands (a join of boxes of one member keeps that member). One edge's
    # copies are parallel; where an operand is a phi of the same block, they havoc instead.
    # (A threaded guard join's phi feeds only its own branch and needs none.)
    phi_copies = {}
    if not null_mode:
        for block in fn["blocks"]:
            if block["label"] in joins:
                continue
            entries = []
            for op in block["operations"]:
                if op["op"] != "phi":
                    break
                result = f"%t{op['results'][0]}"
                if domain(result) is not None:
                    boundary.require(len(op["targets"]) == len(op["operands"])
                                     and len(set(op["targets"])) == len(op["targets"]), "malformed union phi")
                    entries.append((result, dict(zip(op["targets"], (a["value"] for a in op["operands"]),
                                                     strict=True))))
            if entries:
                phi_copies[block["label"]] = entries
    copied = {result for entries in phi_copies.values() for result, _ in entries}
    # A phi of payload words is a location of its own: on each edge, the incoming word's (or
    # the members the bits that come from no box may be, static_kinds).
    word_phis = {}
    for value in words:
        if value == words[value]:
            if value in copied:
                raise boundary.Unsupported("union phi of payload words")
            word_phis.setdefault(blocks_of[value], []).append(value)
    active_pairs = frozenset()
    nodes, labels, obligations = [], {}, 0
    origins = {}  # id of an obligation node -> its operation (label, offset, opcode)
    stop = ("node", {"op": "stop"})
    payload_checks = not null_mode and not obligate_returns
    def assign(dst, src, target):
        # dst gets src's value, then target: null's tag, an SSA value's tags or nothing known
        if src == "null":
            return ("node", {"op": "havoc", "dst": dst, "next": (
                "node", {"op": "guard", "value": dst, "tags": [NULL], "yes": target, "no": stop})})
        if src in types:
            return ("node", {"op": "copy", "dst": dst, "src": canonical(src), "next": target})
        return ("node", {"op": "havoc", "dst": dst, "next": target})
    def holds(word, member, target, site, deref=False):
        """target, once the bits word holds are proved a member's: of its location's, or of
        static_kinds's (a fresh location assumed so); unknown bits are unsupported. deref: the
        bits are the word a pointer of opt[K] points at, a boxed scalar's or a promoting int's
        low word (pys_ubox_opt)."""
        if not payload_checks:
            return target
        location = None if deref else words.get(word)
        if location is None:
            kinds = static_kinds(word)
            if deref and kinds is not None:
                kinds = sorted({"member:int" if kind == "member:" + BIG else kind for kind in kinds})
            if kinds is None:
                raise boundary.Unsupported(f"union payload bits of no known member at {site[0]}:{site[1]}")
            if word.lstrip("-").isdigit() or word in {"true", "false"}:
                # (a word literal is the bits of whichever of its members the box is, if any)
                kinds = [kind for kind in kinds if kind in member] or kinds
            location = f"%bits.{site[0]}.{site[1]}.{len(origins)}"
            check = {"op": "payload", "value": location, "tags": member, "next": target}
            origins[id(check)] = site
            return ("node", {"op": "havoc", "dst": location, "next": (
                "node", {"op": "guard", "value": location, "tags": kinds, "yes": ("node", check), "no": stop})})
        check = {"op": "payload", "value": location, "tags": member, "next": target}
        origins[id(check)] = site
        return ("node", check)
    def interpretation(op, position, operand):
        """The members whose bits op reads the payload word operand (at position) as: its
        result's type for slot.unpack, else the operand's; None where op only moves the bits
        (slot.pack, a phi, a select's choice) or makes a box of them (ubox, checked there)."""
        kind = op["op"]
        if kind in {"slot.pack", "phi"} or (
                kind == "rt" and op["text"] in {"ubox", "ubox_opt"} and position == 1):
            return None
        typ = op["type"] if kind in {"slot.unpack", "select"} else operand["type"]
        if typ.startswith("*") and typ not in GENERIC_WORDS:
            typ = typ[1:]  # (an encoded *element word, as a list write takes it: typed-ir.md)
        if kind == "rt" and op["text"] == "box" and position == 0:
            # (a scalar box of the bits, its member that of its uses: each an opt[K] or a K box)
            typed = {a["type"] for block in fn["blocks"] for use in block["operations"] for a in use["operands"]
                     if op["results"] and a["value"] == f"%t{op['results'][0]}"}
            if len(typed) != 1 or not next(iter(typed)).startswith("opt["):
                raise boundary.Unsupported("scalar box of union payload bits of no one type")
            typ = next(iter(typed))[4:-1]
        if typ in GENERIC_WORDS:
            raise boundary.Unsupported(f"union payload bits used by {kind} with no member type")
        if typ.startswith("opt[") and typ.endswith("]"):
            return sorted(["member:" + typ[4:-1], NULL])
        return ["member:" + typ]
    def write_pair(dst, what, target, site):
        """dst, a virtual box or pair phi, gets what a pair writes (pair_source), then target."""
        if what[0] == "copy":
            return ("node", {"op": "copy", "dst": dst, "src": what[1], "next": target})
        if what[0] == "tags":
            return ("node", {"op": "havoc", "dst": dst, "next": (
                "node", {"op": "guard", "value": dst, "tags": what[1], "yes": target, "no": stop})})
        _, member, payload = what
        if member == PRESENT:
            # (an opt[None] split's value: the member of its bits, known unless unsupported)
            if payload in words:
                return ("node", {"op": "copy", "dst": dst, "src": words[payload], "next": target})
            kinds = static_kinds(payload)
            if kinds is None or NULL in kinds or not set(kinds) <= SCALAR_MEMBERS:
                raise boundary.Unsupported(f"split optional of bits of no known scalar at {site[0]}:{site[1]}")
            member = kinds
        else:
            member = [member]
        made = ("node", {"op": "havoc", "dst": dst, "next": (
            "node", {"op": "guard", "value": dst, "tags": member, "yes": target, "no": stop})})
        return made if member == [NULL] else holds(payload, member, made, site)
    def into(source, target):
        # (one edge's copies are parallel: a source that is a phi of the target block is havoc)
        phis = ({result for result, _ in phi_copies.get(target, [])} | set(pair_phis.get(target, {}))
                | set(word_phis.get(target, [])))
        after = target
        for word in reversed(word_phis.get(target, [])):
            value = phi_incoming(word).get(source)
            if value is None:
                raise boundary.Unsupported("payload phi has no incoming value for an edge")
            location = words.get(value)
            if location == word:
                continue  # (a loop's phi meets itself)
            if location is not None and location not in phis:
                after = ("node", {"op": "copy", "dst": word, "src": location, "next": after})
                continue
            kinds = None if location is not None else static_kinds(value)
            if kinds is not None and (value.lstrip("-").isdigit() or value in {"true", "false"}):
                # (a word literal is the bits of whichever member the phi's type names)
                kinds = [kind for kind in kinds if kind == "member:" + producers[word]["type"]] or kinds
            after = ("node", {"op": "havoc", "dst": word, "next": after if kinds is None else (
                "node", {"op": "guard", "value": word, "tags": kinds, "yes": after, "no": stop})})
        for tag in reversed(list(pair_phis.get(target, {}))):
            what = pair_edges.get((tag, source))
            if what is None:
                raise boundary.Unsupported("pair phi has no incoming value for an edge")
            if what == ("copy", tag):
                continue  # (a loop's pair meets itself)
            if what[0] == "copy" and what[1] in phis:
                after = ("node", {"op": "havoc", "dst": tag, "next": after})
                continue
            after = write_pair(tag, what, after, (source, target, "split union payload"))
        entries = phi_copies.get(target)
        if not entries:
            return after
        values = [(result, incoming.get(source)) for result, incoming in entries]
        if any(value is None for _, value in values):
            raise boundary.Unsupported("union phi has no incoming value for an edge")
        parallel = not any(value in {result for result, _ in entries} for _, value in values)
        for result, value in reversed(values):
            after = assign(result, value, after) if parallel else ("node", {"op": "havoc", "dst": result, "next": after})
        return after
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
            return into(source, target)
        incoming, (yes, no), pointer = joins[target]
        yes, no = into(target, yes), into(target, no)
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
                emit({"op": "choice", "yes": len(nodes) + 1, "no": into(label, block["handler"])})
            if null_mode and (label, offset) in null_obligations:
                test = producers.get(args[0]["value"], {})
                boundary.require(test.get("op") == "ptr.cmp" and test.get("text") == "==", "removed check is not null equality")
                values = [a["value"] for a in test["operands"]]
                boundary.require(values.count("null") == 1, "removed check has no unique null operand")
                value = canonical(values[1] if values[0] == "null" else values[0])
                follow({"op": "payload", "value": value, "tags": [NONNULL]})
                origins[id(nodes[-1])] = (label, offset, "removed check")
                obligations += 1
            split = split_ops.get(id(op))
            if split is not None or (label, offset) in covered:
                boundary.require((label, offset, kind) not in read_inventory, "split union access inventoried as a read")
                # (a split pair's two accesses as one: its tag access writes or reads the box)
                if split is not None and split[0] == "store":
                    after = len(nodes) + 1
                    emit({"op": "jump", "next": write_pair(split[1], split[2], after,
                                                           (label, offset, "split union payload"))})
                elif split is not None:
                    follow({"op": "copy", "dst": split[2], "src": split[1]})
                active_pairs = pairing(active_pairs, op)
                continue
            if payload_checks:
                for position, operand in enumerate(args):
                    if operand["value"] in words:
                        member = interpretation(op, position, operand)
                        if member is not None:
                            follow({"op": "payload", "value": words[operand["value"]], "tags": member})
                            origins[id(nodes[-1])] = (label, offset, "payload interpretation")
            is_read = (label, offset, kind) in read_inventory
            if is_read:
                value = canonical(args[0]["value"])
                tags = domain(value)
                if not tags:
                    raise boundary.Unsupported(f"union read has no declared source domain: {value}")
                allowed = ["member:" + op["text"]] if kind == "union.payload" else [t for t in tags if t != NULL]
                boundary.require(bool(allowed), "union read has no accepted member")
                follow({"op": "payload", "value": value, "tags": allowed})
                origins[id(nodes[-1])] = (label, offset, kind)
                obligations += 1
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
                target = into(label, op["targets"][0])
                decode = decoders.get(args[0]["value"], tag_names)
                for arg, successor in reversed(list(zip(args[1:], op["targets"][1:], strict=True))):
                    if decode.get(arg["value"], PRESENT) == PRESENT:
                        raise boundary.Unsupported("unknown union switch tag")
                    target = decide(("atom", reads[args[0]["value"]], (decode[arg["value"]],)),
                                    into(label, successor), target)
                emit({"op": "jump", "next": target})
            elif kind in {"ret", "ret.none", "unreachable"} or (kind in {"raise", "throw"} and not op["targets"]):
                if returned is not None and kind == "ret":
                    value = args[0]["value"] if len(args) == 1 else ""
                    if value not in types:
                        # (null, or a value nothing is known of: a dead block's return goes
                        # unchecked, as Lean checks only what the entry reaches)
                        follow({"op": "havoc", "dst": "%returned"})
                        if value == "null":
                            assume("%returned", [NULL])
                        value = "%returned"
                    follow({"op": "payload", "value": canonical(value), "tags": returned})
                    origins[id(nodes[-1])] = (label, offset, "returned union")
                    obligations += 1
                emit({"op": "stop"})
            else:
                if kind == "mem.store" and args[0]["value"] in slots and args[0]["value"] not in escapes:
                    follow({"op": "copy", "dst": args[0]["value"], "src": canonical(args[1]["value"])})
                elif kind in {"mach.store", "landing"} and args and args[0]["value"] in slots:
                    follow({"op": "havoc", "dst": args[0]["value"]})
                if kind == "select" and not null_mode and len(args) == 3 and domain(results[0]) is not None:
                    # (either operand, as its condition decides)
                    after = len(nodes) + 1
                    emit({"op": "jump", "next": decide(condition(args[0]["value"]),
                                                       assign(results[0], args[1]["value"], after),
                                                       assign(results[0], args[2]["value"], after))})
                    copied.add(results[0])
                if kind == "rt" and op["text"] in {"ubox", "ubox_opt"} and not null_mode:
                    # A box of a literal tag holds that member's bits (a fresh box, pys_ubox); one
                    # made again of the parts of a box or a pair load is that box.
                    tag, payload = args[0]["value"], args[1]["value"]
                    if tag in tag_names:
                        allowed = sorted([tag_names[tag]] + ([NULL] if op["text"] == "ubox_opt" else []))
                        after = len(nodes) + 1
                        emit({"op": "jump", "next": holds(payload, allowed, after, (label, offset, "union box payload"),
                                                          deref=op["text"] == "ubox_opt" and len(args) == 3 and args[2]["value"] == "1")})
                    else:
                        domain(results[0])  # (unsupported unless reconstructed)
                        follow({"op": "copy", "dst": results[0], "src": reconstructed(tag, payload)})
                        copied.add(results[0])
                for result in results:
                    tags = domain(result)
                    if not tags or result in aliases or result in copied:
                        continue
                    if kind == "mem.load" and args[0]["value"] in slots and args[0]["value"] not in escapes:
                        follow({"op": "copy", "dst": result, "src": args[0]["value"]})
                    else:
                        follow({"op": "havoc", "dst": result})
                        # Result annotations do not prove construction: a phi,
                        # select or cast may carry null or a wider member set.
                        if null_mode or (kind == "rt" and op["text"] in {"ubox", "ubox_opt"}):
                            assume(result, tags)
                        elif kind == "call" and op["text"] in returns and len(results) == 1:
                            # (what the callee returns, each of its returns proved in this domain)
                            assume(result, returns[op["text"]])
                if op["targets"] and kind != "phi":
                    for target in op["targets"][:-1]:
                        emit({"op": "choice", "yes": into(label, target), "no": len(nodes) + 1})
                    emit({"op": "jump", "next": into(label, op["targets"][-1])})
                else:
                    emit({"op": "jump", "next": len(nodes) + 1})
            active_pairs = pairing(active_pairs, op)
    placed = {}
    def place(value):
        if not isinstance(value, tuple):
            return labels[value] if isinstance(value, str) else value
        if id(value) not in placed:
            node = dict(value[1])
            if id(value[1]) in origins:
                origins[id(node)] = origins[id(value[1])]
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
    located = {index: origins[id(node)] for index, node in enumerate(nodes) if id(node) in origins}
    checked_payloads = sum(site[2] in PAYLOAD_OBLIGATIONS for site in located.values())
    candidate = {"schema_version": 2, "program": {"entry": 0, "nodes": nodes},
                 "certificate": boundary.infer_certificate(nodes)}
    return candidate, {"function": fn["symbol"], "obligations": obligations, "nodes": len(nodes),
                       "payloads": payloads, "payload_obligations": checked_payloads,
                       "omitted_unreachable_obligations": obligations + checked_payloads - payloads,
                       "scope": "removed null checks (before-pass redundancy)" if null_mode else "closed-union guards",
                       "origins": located}


def explain(candidate, origins):
    """The first obligation the inferred certificate does not cover, for a rejected candidate:
    an investigation target, not a verdict (Lean's rejection is the verdict)."""
    nodes, certificate = candidate["program"]["nodes"], candidate["certificate"]
    for index, node in enumerate(nodes):
        if node["op"] != "payload":
            continue
        known = dict((value, tags) for value, tags in certificate[index]).get(node["value"])
        if known is None or not set(known) <= set(node["tags"]):
            label, offset, kind = origins.get(index, ("?", "?", "?"))
            return (f"{kind} at {label}:{offset} needs {node['value']} in {node['tags']}; "
                    f"known: {'nothing' if known is None else known}")
    return None


def proved_returns(snapshot, checker=boundary.DEFAULT_CHECKER):
    """The declared union domains of the functions each of whose returns Lean proves in that
    domain, every proof assuming the others' results (normalize's returns): a greatest fixed
    point, which drops a function whose proof fails and redoes the others without it. Over the
    returns of a run, by induction, each such function returns a value of its domain, given
    union boxes are immutable (box_writes) and parameters hold their declared domains, as every
    union read proof assumes too."""
    functions = {fn["symbol"]: fn for fn in snapshot["functions"]}
    assumed = {symbol: union_members(fn.get("return_representation") or "") for symbol, fn in functions.items()}
    assumed = {symbol: tags for symbol, tags in assumed.items() if tags}
    while True:
        proved = {}
        for symbol, tags in assumed.items():
            try:
                candidate, meta = normalize(snapshot, functions[symbol], immutable_boxes=True, returns=assumed,
                                            obligate_returns=True)
                meta.pop("origins")
                if boundary.run_checker(checker, boundary.encode(candidate), meta):
                    proved[symbol] = tags
            except (boundary.Unsupported, ValueError, KeyError, OSError, subprocess.SubprocessError, RecursionError):
                pass
        if proved.keys() == assumed.keys():
            return proved
        assumed = proved


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
    context = snapshot_context(snapshot)
    work = [(fn, None) for fn in snapshot["functions"]
            if inventory(fn, context) or union_writes(fn, context) or payload_bits(fn)]
    # (without a classes table no field address is shown to lie outside boxes: every write
    # and call remains a possible box mutation, as box_writes reports none of it)
    writes = box_writes(snapshot) if isinstance(snapshot.get("classes"), dict) else None
    returns = proved_returns(snapshot, checker) if writes == [] else {}
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
            candidate, meta = normalize(snapshot, fn, removed, immutable_boxes=writes == [], returns=returns)
            origins = meta.pop("origins")
            encoded = boundary.encode(candidate)
            accepted = boundary.run_checker(checker, encoded, meta)
            code = 0 if accepted else 1
            records.append(dict(meta, candidate_sha256=hashlib.sha256(encoded.encode()).hexdigest(), status="accepted" if accepted else "rejected", checked=accepted))
            if not accepted:
                records[-1]["error"] = explain(candidate, origins) or "a transfer is not justified"
            codes.append(code)
        except (boundary.Unsupported, ValueError, KeyError, OSError, subprocess.SubprocessError, RecursionError) as error:
            code = 2 if isinstance(error, boundary.Unsupported) else 3
            records.append({"function": fn.get("symbol"), "status": "unsupported" if code == 2 else "error", "error": str(error),
                            "union_box_writes": len(union_writes(fn, context))})
            codes.append(code)
    code = 3 if 3 in codes else 1 if 1 in codes else 2 if 2 in codes else 0
    return {"status": {0: "accepted", 1: "rejected", 2: "unsupported", 3: "error"}[code],
            "checked": code == 0, "records": records,
            "union_reads": sum(len(inventory(fn, context)) for fn in snapshot["functions"]),
            "union_box_writes": sum(len(union_writes(fn, context)) for fn in snapshot["functions"]),
            "possible_box_writes": None if writes is None else len(writes),
            "union_returns": sum(union_members(fn.get("return_representation") or "") is not None
                                 for fn in snapshot["functions"]),
            "proved_union_returns": len(returns),
            "removed_checks": sum(r["reported_rewrites"] for r in snapshot["nullcheck_evidence"]),
            "proved_union_reads": sum(r.get("obligations", 0) for r in records if r["status"] == "accepted"
                                      and r.get("scope") == "closed-union guards"),
            "payload_obligations": sum(r.get("payload_obligations", 0) for r in records
                                       if r.get("scope") == "closed-union guards"),
            "proved_payload_obligations": sum(r.get("payload_obligations", 0) for r in records
                                              if r["status"] == "accepted" and r.get("scope") == "closed-union guards"),
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
