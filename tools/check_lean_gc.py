#!/usr/bin/env python3
"""Check with Lean that the collector scans every array that may hold a pointer.

runtime.c's collector scans each object but its atomic memory. A list of ints, floats or bools
keeps its items in an atomic array where the compiler makes it with pys_list_new_atomic (or
pys_list_new where lowering resolved an empty list's type hole to such a list), a dict of such
values its values (pys_dict_new_atomic, or a resolved hole), and a dict or set of int keys its keys
(keymem, by the key kind the compiler passes: 0, or a hash descriptor of an int or a bool, which
empty.kind may store again). Runtime copies keep each array's kind. A pointer in an atomic array is
invisible to the collector, which may free what it points to while the program still uses it.

Each list, dict and set value has a tag per array, its kind; Lean checks, in the finite-tag model,
that every use whose type lets an array hold pointers (a list of strs, a dict of objects, a set of
tuples) uses a value whose array is scanned, and that every write of words that may be pointers
into an array (an item, or another container's words) writes into a scanned one, or takes them from
an atomic one. A value's tag comes from what made it: an allocation (its runtime function, type hole
and key kind), a runtime copy or column (an operand's), a phi or select (its operands'), empty.kind
(its old tag or the stored kind's), or else a load, parameter, call result or unpacked word, which
may be what its declared type allows: either kind of a numeric array, a scanned other. A memory
word is typed once for the program (memory_types; an open global by what its stores hold), and a
list's items or a dict's values that a declared result type leaves open are scanned. That rests on
every use that stores, passes or returns such a value being checked, in every function: a program
is proved where Lean accepts each of its functions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess

import check_lean_boundary as boundary
from check_lean_effects import targs
from check_lean_guards import argument_parameters, direct_access, memory_key

NONE = "none"  # (a null value has no array: every use allows it)
ATOMIC, SCANNED = "atomic", "scanned"  # (the kind of one array: a location per array)
EITHER = sorted([ATOMIC, SCANNED, NONE])
POINTERS = sorted([SCANNED, NONE])  # (what an array a pointer may be written into is)
NUMERIC = frozenset({"int", "float", "bool"})
INT_KEYS = frozenset({"int", "bool"})  # (keymem: a key kind 0, or a descriptor of an int or a bool)
PLACEHOLDERS = frozenset({"T", "K", "V", "S", "?", "*T", "*K", "*V"})
KEYS = "#keys"  # (a dict's key array's location: the value's own is its value array's)
# The boundary validator's bounds here: a function's work is linear in its blocks, so the regex
# engine's sre_match (about 1,300 blocks and 4,500 instructions) is checked; its graph keeps
# the checker's node bound.
MAX_BLOCKS, MAX_INSTRUCTIONS = 4096, 16384


SPEC_VARIABLES = frozenset({"T", "K", "V", "S"})  # (specs.py's type variables of runtime functions)
LIMITATIONS = (
    "Proves, per function in the finite-tag model, that no list, dict or set whose item, value or key "
    "array may be atomic (unscanned) reaches a use whose type lets that array hold pointers, and that "
    "words that may be pointers are written only into scanned arrays. The runtime's array kinds "
    "(allocators, copies, columns and writes keep their arrays' kinds; empty.kind sets the kind of a "
    "dict's or set's next tables), the exported type holes and key descriptors, IR operand and "
    "declared types, item types and the Python adapter are trusted; a program's proof needs every "
    "function accepted. Does not prove pointers in other atomic memory (strings, buffers), GC roots "
    "or lifetime.")


def container(typ):
    """The list, dict or set type a value of type typ is, if any: an optional one's (null has no
    array), or the receiver of a builtin method bound to it (fn[d:append:list[str]] is the list)."""
    while typ.startswith("opt[") and typ.endswith("]"):
        typ = typ[4:-1]
    if typ.startswith("fn[d:") and typ.endswith("]") and typ.count(":") >= 2:
        typ = typ[typ.index(":", 5) + 1:-1]
    return typ


def family(typ):
    typ = container(typ)
    for prefix, name in (("list[", "list"), ("dict[", "dict"), ("set[", "set"), ("frozenset[", "set")):
        if typ.startswith(prefix) and typ.endswith("]"):
            return name
    return None


def open_part(part):
    return part in PLACEHOLDERS or "?" in part


def arrays(typ):
    """Each array a value of type typ has, with what a use of that type allows it to be: (suffix,
    tags) where a pointer may be in it (scanned, or null), or (suffix, None) where it may not or
    its part of the type is a placeholder the IR leaves unresolved. A dict's key array is its
    #keys location."""
    name = family(typ)
    if name is None:
        return []
    parts = targs(container(typ))
    def kind(part, numeric):
        return None if open_part(part) or part in numeric else sorted([SCANNED, NONE])
    if name == "list":
        return [("", kind(parts[0], NUMERIC))]
    if name == "set":
        return [("", kind(parts[0], INT_KEYS))]
    return [("", kind(parts[1], NUMERIC)), (KEYS, kind(parts[0], INT_KEYS))]


def assumed(typ):
    """What each array of a value of declared type typ that this function did not make may be: (suffix,
    tags), tags None where its part of the type is a placeholder (unknown)."""
    name = family(typ)
    if name is None:
        return []
    parts = targs(container(typ))
    opened = [open_part(parts[0])] if name != "dict" else [open_part(parts[1]), open_part(parts[0])]
    return [(suffix, None if unknown else tags or EITHER) for (suffix, tags), unknown in zip(arrays(typ), opened)]


def open_results(typ):
    """The arrays of a value whose declared type leaves its list's items or dict's values open: a
    function that returns one (a template's empty result, typed later by its caller) makes it with
    pys_list_new or pys_dict_new, whose such arrays are scanned. Its returns are checked by this,
    and a direct call's result assumes it (a set's or dict's keys are not: empty.kind sets them)."""
    name = family(typ)
    if name in ("list", "dict") and open_part(targs(container(typ))[-1]):
        return [("", POINTERS)]
    return []


def empty_kind(typ):
    """The tag of the key array a dict or set gets after empty.kind stores the key kind of type typ
    into it (lowering: an unresolved hole's kind is 0), or None where the type leaves it open."""
    if typ == "":
        return ATOMIC
    if family(typ) not in ("dict", "set"):
        return None
    key = targs(container(typ))[0]
    return None if open_part(key) else ATOMIC if key in INT_KEYS else SCANNED


def key_kind(operand, descriptors):
    """The kind of the key array a key kind operand makes (keymem), or None where it is unknown."""
    value = operand["value"]
    if value.lstrip("-").isdigit():
        return ATOMIC if int(value) == 0 else SCANNED if int(value) in (1, 2, 3) else None
    if value.startswith("ptrtoint (ptr @s.") and value.endswith(" to i64)"):
        text = descriptors.get(value[len("ptrtoint (ptr "):-len(" to i64)")])
        if not isinstance(text, str) or not text:
            return None
        text = text[1:] if text.startswith("!") else text
        return ATOMIC if text[:1] in ("i", "b") else SCANNED
    return None


def hole_kinds(holes, index, maker):
    """The kinds of the arrays of an empty list, dict or set whose type hole index lowering resolved
    (holes): its allocator and key kind (lowering.py: an unresolved hole's key kind is 0), as
    (values or items, keys)."""
    boundary.require(isinstance(holes, list) and 0 < index < len(holes), "missing type hole: inspect with --guard-evidence")
    hole = holes[index]
    if maker == "list.new":
        return (ATOMIC if family(hole) == "list" and targs(hole)[0] in NUMERIC else SCANNED), None
    if hole == "":
        return SCANNED, ATOMIC
    boundary.require(family(hole) in ("dict", "set"), "type hole of another kind")
    keys = ATOMIC if targs(hole)[0] in INT_KEYS else SCANNED
    if maker == "set.new":
        return keys, None
    return (ATOMIC if family(hole) == "dict" and targs(hole)[1] in NUMERIC else SCANNED), keys


def requirement(typ):
    """What a memory word of container type typ holds in each array: {suffix: tags}, tags None where
    the type leaves its part open."""
    parts = targs(container(typ))
    held = [parts[1], parts[0]] if family(typ) == "dict" else [parts[0]]  # (arrays' order: values, then keys)
    return {suffix: None if open_part(part) else tags or EITHER for (suffix, tags), part in zip(arrays(typ), held)}


def memory_types(snapshot):
    """Each memory word's arrays for the whole program, whatever view one access types it by: a module
    global's or class variable's (by its symbol) or a field's (by its word: check_lean_guards'
    memory_key), from all its views' concrete container types (the strictest where they differ).
    Returns ({key: {suffix: tags}}, the globals every view of which leaves open). A word whose
    address some operation uses other than as a load's or store's is neither: its accesses keep
    their own views. Every store of a word is checked against what its loads then assume."""
    context = {"classes": snapshot.get("classes") or {}, "layouts": snapshot.get("class_layouts") or {}}
    views, escaped = {}, set()
    for fn in snapshot["functions"]:
        producers = {f"%t{n}": op for block in fn["blocks"] for op in block["operations"] for n in op["results"]}
        for block in fn["blocks"]:
            for op in block["operations"]:
                for position, operand in enumerate(op["operands"]):
                    if position == 0 and direct_access(op):
                        key = memory_key(context, producers, operand["value"])
                        if key is not None and operand["type"].startswith("*") and family(operand["type"][1:]):
                            views.setdefault(key, set()).add(container(operand["type"][1:]))
                    elif operand["value"].startswith("@"):
                        escaped.add(("global", operand["value"]))
                    elif operand["value"] in producers and producers[operand["value"]]["op"] == "field.addr":
                        key = memory_key(context, producers, operand["value"])
                        if key is not None:
                            escaped.add(key)
    types, opened = {}, set()
    for key, seen in views.items():
        if key in escaped or len({family(typ) for typ in seen}) != 1:
            continue
        concrete = [typ for typ in seen if not any(map(open_part, targs(typ)))]
        if not concrete:
            if key[0] == "global":
                opened.add(key)
            continue
        merged = {}
        for typ in concrete:
            for suffix, tags in requirement(typ).items():
                merged[suffix] = sorted(set(merged.get(suffix, tags)) & set(tags))
        types[key] = merged
    return types, opened


# Runtime functions whose results' arrays the runtime makes from their operands' (atomic_items: a
# list keeps its kind, and a dict its arrays', through growth, copies and set algebra; list.add's is
# atomic only where both are, which one of them stands for here) or a column of one's (col,
# pys_set_list), or atomic from scratch (numeric lists: pys_list_new_atomic and its users).
COPIES = frozenset({"list.slice", "list.slice_step", "list.copy", "list.add", "list.mul", "list.take",
                    "dict.copy", "dict.from", "set.copy", "set.or", "set.and", "set.and_list", "set.sub",
                    "set.sub_list", "set.sub_dict", "set.xor", "set.xor_list", "set.xor_dict"})
NUMERIC_MAKERS = {"list.new_atomic": [ATOMIC], "list.from_const": [ATOMIC], "range.list": [ATOMIC],
                  "bytes.list": [ATOMIC], "m.floats": [ATOMIC, SCANNED], "m.ufloats": [ATOMIC]}
COLUMNS = {"dict.keys": KEYS, "dict.values": "", "set.list": ""}

# Runtime functions that write words into an array of their receiver (specs.py's RUNTIME with wL or
# wD; removals, pops and clears write none, and a big int's other words are in dbig, kbig and sbig):
# the receiver's operand, that array, and where the words come from: an item operand ("item", i),
# another container's array ("array", i, suffix), a list's items ("items", i) or one part of its
# tuples ("pairs", i, part). Such a write needs the array scanned where its words may be pointers,
# whatever any view of the receiver says: a container no typed use holds is checked too.
WRITES = {
    "list.append": [(0, "", ("item", 1))], "list.set": [(0, "", ("item", 2))], "list.insert": [(0, "", ("item", 2))],
    "list.append_identity": [(0, "", ("item", 1))], "list.set_identity": [(0, "", ("item", 2))],
    "list.insert_identity": [(0, "", ("item", 2))],
    "list.extend": [(0, "", ("array", 1, ""))], "list.set_slice": [(0, "", ("array", 4, ""))],
    "dict.set": [(0, KEYS, ("item", 1)), (0, "", ("item", 2))],
    "dict.setdefault": [(0, KEYS, ("item", 1)), (0, "", ("item", 2))],
    "dict.entry_set": [(0, "", ("item", 2))], "dict.bkey_setdefault": [(0, "", ("item", 3))],
    "dict.set_big": [(0, KEYS, ("item", 1))], "dict.big_setdefault": [(0, KEYS, ("item", 1))],
    "dict.update": [(0, "", ("array", 1, "")), (0, KEYS, ("array", 1, KEYS))],
    "dict.update_pairs": [(0, KEYS, ("pairs", 1, 0)), (0, "", ("pairs", 1, 1))],
    "dict.update_pairs_big": [(0, KEYS, ("pairs", 1, 0)), (0, "", ("pairs", 1, 1))],
    "set.add": [(0, "", ("item", 1))], "set.update": [(0, "", ("array", 1, ""))],
    "set.assign": [(0, "", ("array", 1, ""))], "set.ixor": [(0, "", ("array", 1, ""))],
    "set.union_more": [(0, "", ("array", 1, "")), (0, "", ("array", 2, ""))],
    "set.update_list": [(0, "", ("items", 1))], "set.ixor_list": [(0, "", ("items", 1))],
    "set.update_dict": [(0, "", ("array", 1, KEYS))], "set.ixor_dict": [(0, "", ("array", 1, KEYS))],
}
# Runtime functions whose new result also takes another operand's words (its arrays have the first
# operand's kind, or dict.fromkeys's key kind's): checked once the result is made.
FILLS = {"set.or": [("", ("array", 1, ""))], "set.xor": [("", ("array", 1, ""))],
         "set.and_list": [("", ("items", 1))], "set.xor_list": [("", ("items", 1))],
         "set.xor_dict": [("", ("array", 1, KEYS))], "dict.fromkeys": [(KEYS, ("items", 1))]}


# Runtime functions that read a word of their receiver's array (specs.py's RUNTIME): the receiver's
# operand, the part of its type the word has, and the operands whose word it may return instead (a
# default). A fresh container (FRESH) is empty: one no other operation reads holds no word.
READS = {"dict.get": (0, 1, (2,)), "dict.getitem": (0, 1, ()), "dict.pop": (0, 1, ()), "dict.del": (0, 1, ()),
         "dict.pop_default": (0, 1, (2,)), "dict.setdefault": (0, 1, (2,)), "dict.getbox": (0, 1, (2,)),
         "dict.popbox": (0, 1, (2,)), "dict.val": (0, 1, ()), "dict.val_or_zero": (0, 1, ()), "dict.key": (0, 0, ()),
         "list.get": (0, 0, ()), "list.pop": (0, 0, ()), "list.minmax": (0, 0, ()), "set.pop": (0, 0, ()),
         "set.key": (0, 0, ())}
FRESH = frozenset({"list.new", "list.new_atomic", "dict.new", "dict.new_atomic", "set.new"})
# Runtime functions that list a dict's or set's words: their result's type from their source's parts.
LISTED = {"dict.keys": lambda parts: f"list[{parts[0]}]", "dict.values": lambda parts: f"list[{parts[-1]}]",
          "dict.items": lambda parts: f"list[tuple[{parts[0]},{parts[-1]}]]", "set.list": lambda parts: f"list[{parts[0]}]",
          "dict.big_items": lambda parts: f"list[tuple[{parts[0]},{parts[-1]}]]"}


def writes_of(op):
    """A write's (receiver, array, source) entries: a runtime function's (WRITES), or a list.store's,
    an item stored at an index below its list's length (as pys_list_set stores it)."""
    if op["op"] == "rt":
        return WRITES.get(op["text"], ())
    return [(0, "", ("item", 2))] if op["op"] == "list.store" else ()


def holds_pointer(typ):
    """Whether a word of type typ may point to a collected object; None where typ is unknown."""
    if not typ or open_part(typ) or typ.startswith("%") or typ == "S":
        return None
    return typ not in NUMERIC and typ != "None"


def signatures(snapshot):
    """Each function's declared parameter and return types, by its symbol: a call is checked and
    assumed by its callee's, whatever its operands' and result's views say, as a store and a load are
    by the memory's. A call's operands are its callee's parameters but those of type None, which take
    none, then numeric identity companions (check_lean_guards.argument_parameters)."""
    return {other["symbol"]: ([other["parameters"][i]["representation"] for i in argument_parameters(other["parameters"])],
                              other.get("return_representation") or "") for other in snapshot["functions"]}


def normalize(snapshot, fn, memory=None, declared=None):
    """The finite-tag candidate of fn. memory: (memory_types' words, {open global: {suffix: tags} or
    None}); with it, a load of a word assumes what the program's stores of it are checked to hold, and
    meta["stored"] gives the facts the open globals' stores of fn have, by which check_all infers them.
    declared: signatures(snapshot), if the caller has them."""
    words, invariants = memory or ({}, {})
    context = {"classes": snapshot.get("classes") or {}, "layouts": snapshot.get("class_layouts") or {}}
    validation = dict(snapshot, functions=[boundary.word_validation(fn)])
    try:
        boundary.normalize_snapshot(validation, fn["symbol"], MAX_BLOCKS, MAX_INSTRUCTIONS, certify=False)
    except ValueError as error:
        # (a form the boundary validator refuses, such as a type name past its bound)
        raise boundary.Unsupported(f"outside the boundary validator: {error}") from error
    holes = snapshot.get("holes")
    descriptors = snapshot.get("key_descriptors") or {}
    declared = signatures(snapshot) if declared is None else declared
    producers, types = {}, {f"%a{n}": p["representation"] for n, p in enumerate(fn["parameters"])}
    for block in fn["blocks"]:
        for op in block["operations"]:
            for n in op["results"]:
                producers[f"%t{n}"] = op
                types[f"%t{n}"] = op["type"]
    def word(address):
        """What a memory word holds, {suffix: tags}, for an address of a typed word or an open global
        (None: unknown); or None where the address names no such word (its accesses keep their views)."""
        key = memory_key(context, producers, address)
        if key in words:
            return words[key]
        if key in invariants:
            return invariants[key] or {}
        return None
    stores = []
    # (each value a use or its definition types as a list, dict or set, and which: a runtime copy's
    # result and operands are typed S, their receiver's type, which their other uses show)
    kinds = {}
    for value, typ in types.items():
        if family(typ) is not None:
            kinds.setdefault(value, family(typ))
    for block in fn["blocks"]:
        for op in block["operations"]:
            for a in op["operands"]:
                if family(a["type"]) is not None and a["value"].startswith("%"):
                    kinds.setdefault(a["value"], family(a["type"]))
    slots = {f"%{op['text']}.def.{op['results'][0]}" if op["immediate"] == 1 else f"%{op['text'] or 'h'}.{op['results'][0]}"
             for op in fn["slots"] if op["immediate"] != 2}
    # (a write's receiver and a fill's result are of their runtime function's family)
    for block in fn["blocks"]:
        for op in block["operations"]:
            for receiver in {receiver for receiver, _, _ in writes_of(op)}:
                value = op["operands"][receiver]["value"] if receiver < len(op["operands"]) else ""
                if value.startswith("%") and value not in slots:
                    kinds.setdefault(value, "list" if op["op"] == "list.store" else op["text"].split(".")[0])
            if op["op"] == "rt" and op["text"] in FILLS:
                for n in op["results"]:
                    kinds.setdefault(f"%t{n}", op["text"].split(".")[0])
    # (a runtime copy's S operands and result are one family: what any of them is, all are)
    changed = True
    while changed:
        changed = False
        for block in fn["blocks"]:
            for op in block["operations"]:
                if op["op"] == "rt" and op["text"] in COPIES:
                    members = [a["value"] for a in op["operands"] if a["type"] == "S" and a["value"].startswith("%")]
                    members += [f"%t{n}" for n in op["results"]]
                    known = {kinds[m] for m in members if m in kinds}
                    if len(known) == 1:
                        for member in members:
                            if member not in kinds:
                                kinds[member] = next(iter(known))
                                changed = True
    # (a slot only direct loads and stores, or a landing, reach by their address is private)
    escaped = {a["value"] for block in fn["blocks"] for op in block["operations"] for position, a in enumerate(op["operands"])
               if a["value"] in slots and not (position == 0 and (direct_access(op) or op["op"] == "landing"))}
    private = slots - escaped
    for slot in fn["slots"]:
        name = f"%{slot['text']}.def.{slot['results'][0]}" if slot["immediate"] == 1 else f"%{slot['text'] or 'h'}.{slot['results'][0]}"
        if name in private and family(slot["type"]) is not None:
            kinds.setdefault(name, family(slot["type"]))
    for block in fn["blocks"]:
        for op in block["operations"]:
            # (a private slot's family by what its accesses view it as)
            if direct_access(op) and op["operands"] and op["operands"][0]["value"] in private \
                    and op["operands"][0]["type"].startswith("*") and family(op["operands"][0]["type"][1:]) is not None:
                kinds.setdefault(op["operands"][0]["value"], family(op["operands"][0]["type"][1:]))
    # (each value's static container types: its own, its uses' views, the memory it is stored in, the
    # parameter it is passed for, the result it is returned as and an empty one's resolved type hole;
    # a runtime copy's S operands and result share theirs)
    static = {}

    def note(value, typ):
        # (a part the type leaves open is unknown where it is read: holds_pointer)
        if value.startswith("%") and family(typ) is not None and not all(map(open_part, targs(container(typ)))):
            static.setdefault(value, set()).add(container(typ))
    for value, typ in types.items():
        # (a runtime function's own result type is its spec's, whose T, K, V and S stand for nothing)
        if not (value in producers and producers[value]["op"] == "rt" and SPEC_VARIABLES & set(re.split(r"[\[\],]", typ))):
            note(value, typ)
    for block in fn["blocks"]:
        for op in block["operations"]:
            args = op["operands"]
            for position, a in enumerate(args):
                note(a["value"], a["type"])
                if op["op"] == "call" and op["text"] in declared and position < len(declared[op["text"]][0]):
                    note(a["value"], declared[op["text"]][0][position])
                if op["op"] in ("mem.store", "mach.store") and position == 1 and args[0]["type"].startswith("*"):
                    note(a["value"], args[0]["type"][1:])
                if op["op"] == "ret":
                    note(a["value"], fn.get("return_representation") or "")
            if op["op"] == "rt" and op["text"] in ("list.new", "dict.new", "set.new", "dict.new_atomic") \
                    and op["immediate"] > 0 and isinstance(holes, list) and op["immediate"] < len(holes):
                for n in op["results"]:
                    note(f"%t{n}", holes[op["immediate"]])
    changed = True
    while changed:
        changed = False
        for block in fn["blocks"]:
            for op in block["operations"]:
                if op["op"] == "rt" and op["text"] in COPIES:
                    members = [a["value"] for a in op["operands"] if a["type"] == "S" and a["value"].startswith("%")]
                    members += [f"%t{n}" for n in op["results"]]
                    shared = set().union(*(static.get(m, set()) for m in members))
                    for member in members:
                        if not shared <= static.get(member, set()):
                            static.setdefault(member, set()).update(shared)
                            changed = True
                if op["op"] == "rt" and op["text"] == "vtuple.new" and op["operands"] and op["results"]:
                    # (a vtuple of a list's items: vtuple[T] of its list[T], beside the result's %ptr)
                    made = {f"vtuple[{targs(typ)[0]}]" for typ in static.get(op["operands"][0]["value"], ()) if family(typ) == "list"}
                    result = f"%t{op['results'][0]}"
                    if not made <= static.get(result, set()):
                        static.setdefault(result, set()).update(made)
                        changed = True
                if op["op"] == "rt" and op["text"] == "vtuple.list" and op["operands"] and op["results"]:
                    # (a vtuple's list: of its items' type, the vtuple's own)
                    made = {f"list[{targs(typ)[0]}]" for typ in [types.get(op["operands"][0]["value"], ""),
                                                                 *static.get(op["operands"][0]["value"], ())]
                            if typ.startswith("vtuple[") and typ.endswith("]") and len(targs(typ)) == 1}
                    result = f"%t{op['results'][0]}"
                    if not made <= static.get(result, set()):
                        static.setdefault(result, set()).update(made)
                        changed = True
                if op["op"] == "rt" and op["text"] in LISTED and op["operands"] and op["results"]:
                    # (a column or the pairs of a dict, a set's list: of its source's static types)
                    made = {LISTED[op["text"]](targs(typ)) for typ in static.get(op["operands"][0]["value"], ())
                            if family(typ) in ("dict", "set")}
                    result = f"%t{op['results'][0]}"
                    if not made <= static.get(result, set()):
                        static.setdefault(result, set()).update(made)
                        changed = True
    slot_types = {f"%{slot['text']}.def.{slot['results'][0]}" if slot["immediate"] == 1 else
                  f"%{slot['text'] or 'h'}.{slot['results'][0]}": slot["type"] for slot in fn["slots"]}

    uses = {}
    for block in fn["blocks"]:
        for op in block["operations"]:
            for a in op["operands"]:
                uses[a["value"]] = uses.get(a["value"], 0) + 1

    def item_types(operand, seen):
        """The static types the word an item operand passes may have: its *T view's, else those of
        what made it: a slot.pack's operand, a tuple.load's item type (its text), a container read's
        part of the container's static types (or a default it returns), a phi's or select's operands'
        or the value's own type; a constant of no global is a number or null. "?" where unknown."""
        value, typ = operand["value"], operand["type"]
        if typ.startswith("*") and not open_part(typ[1:]):
            return {typ[1:]}
        if not value.startswith("%"):
            return {"?" if "@" in value else "int"}
        if value in seen:
            return set()
        seen.add(value)
        producer = producers.get(value)
        if producer is not None and producer["op"] == "slot.pack" and producer["operands"]:
            return {producer["operands"][0]["type"]}
        if producer is not None and producer["op"] == "tuple.load" and producer["text"]:
            return {producer["text"]}
        if producer is not None and producer["op"] in ("phi", "select"):
            found = set()
            for a in producer["operands"][1:] if producer["op"] == "select" else producer["operands"]:
                found |= item_types(a, seen)
            return found
        if producer is not None and producer["op"] == "rt" and producer["text"] in READS:
            position, part, defaults = READS[producer["text"]]
            args = producer["operands"]
            found = {targs(typ)[part] if len(targs(typ)) > part else "?"
                     for typ in static.get(args[position]["value"] if position < len(args) else "", ())} or {"?"}
            for extra in defaults:
                found |= item_types(args[extra], seen) if extra < len(args) else {"?"}
            return found
        own = slot_types.get(value) or types.get(value) or "?"
        return {own[1:] if own.startswith("*") and not open_part(own[1:]) else own}  # (list.load's word)

    def source_location(op, source):
        """The location of the array a write or fill takes its words from, if it has one: where it is
        atomic, the words hold no pointer (each pointer written into it was checked). An item word
        a container read returned (READS, no default) comes from that container's array."""
        how, position = source[0], source[1]
        if position >= len(op["operands"]):
            return None
        if how == "item":
            producer = producers.get(op["operands"][position]["value"])
            if producer is None or producer["op"] != "rt" or producer["text"] not in READS or READS[producer["text"]][2]:
                return None
            read, part, _ = READS[producer["text"]]
            value = producer["operands"][read]["value"] if read < len(producer["operands"]) else ""
            if value not in kinds or value in slots:
                return None
            return value + (KEYS if part == 0 and kinds[value] == "dict" else "")
        value = op["operands"][position]["value"]
        if value not in kinds or value in slots:
            return None
        suffix = source[2] if how == "array" and kinds[value] == "dict" else ""
        return value + suffix

    def source_pointer(op, source):
        """Whether the words a write or fill takes from source may point to collected objects
        (where their type is unknown, they may)."""
        how, position = source[0], source[1]
        if position >= len(op["operands"]):
            return True
        operand = op["operands"][position]
        if how == "item":
            found = item_types(operand, set())
            return not found or any(holds_pointer(typ) is not False for typ in found)
        if not operand["value"].startswith("%"):
            return "@" in operand["value"]  # (null has no words)
        producer = producers.get(operand["value"])
        if producer is not None and producer["op"] == "rt" and producer["text"] in FRESH and uses.get(operand["value"]) == 1:
            return False  # (a fresh container only this write reads: empty)
        found = set()
        for typ in static.get(operand["value"], ()):
            name, parts = family(typ), targs(typ)
            if how == "array":
                part = parts[1] if name == "dict" and source[2] == "" else parts[0]
            elif how == "items":
                part = parts[0] if name == "list" else None
            else:
                pair = parts[0] if name == "list" else ""
                inner = targs(pair) if pair.startswith("tuple[") and pair.endswith("]") else []
                part = inner[source[2]] if source[2] < len(inner) else None
            found.add(holds_pointer(part))
        return found != {False}

    labels = {block["label"] for block in fn["blocks"]}
    nodes, origins, obligations = [], {}, 0
    stop = ("node", {"op": "stop"})

    def emit(node):
        nodes.append(node)

    def follow(node):
        emit(dict(node, next=len(nodes) + 1))

    eithers = []

    def either(target, source, origin):
        """A write of a source array's words into target's array: target scanned, or the source
        atomic (it then holds no pointer). Both are emitted; one is kept once facts are inferred."""
        nonlocal obligations
        follow({"op": "payload", "value": target, "tags": POINTERS})
        origins[id(nodes[-1])] = origin
        first = nodes[-1]
        follow({"op": "payload", "value": source, "tags": EITHER})
        origins[id(nodes[-1])] = origin
        eithers.append((first, nodes[-1]))
        obligations += 1

    def suffixes(value):
        return ["", KEYS] if kinds.get(value) == "dict" else [""]

    def made(dst, tags, target):
        return ("node", {"op": "havoc", "dst": dst, "next": target if tags is None else (
            "node", {"op": "guard", "value": dst, "tags": tags, "yes": target, "no": stop})})

    def moved(dst, src, target):
        """dst's arrays get src's (null has none: any use allows it; an unknown source, anything)."""
        for suffix in reversed(suffixes(dst)):
            if src == "null":
                target = made(dst + suffix, [NONE], target)
            elif src in kinds:
                target = ("node", {"op": "copy", "dst": dst + suffix, "src": src + suffix, "next": target})
            else:
                target = made(dst + suffix, None, target)
        return target

    phis = {}
    for block in fn["blocks"]:
        entries = []
        for op in block["operations"]:
            if op["op"] != "phi":
                break
            if f"%t{op['results'][0]}" in kinds:
                boundary.require(len(op["targets"]) == len(op["operands"]), "malformed phi")
                entries.append((f"%t{op['results'][0]}", dict(zip(op["targets"], (a["value"] for a in op["operands"])))))
        if entries:
            phis[block["label"]] = entries

    def into(source, target):
        entries = phis.get(target, [])
        values = [(result, incoming.get(source)) for result, incoming in entries]
        boundary.require(all(value is not None for _, value in values), "phi has no incoming value for an edge")
        parallel = not any(value in {result for result, _ in entries} for _, value in values)
        after = target
        for result, value in reversed(values):
            if parallel:
                after = moved(result, value, after)
            else:
                for suffix in suffixes(result):
                    after = made(result + suffix, None, after)
        return after

    def defined(op, result, after):
        """The node chain that gives result's arrays their kinds, then after."""
        kind, args = op["op"], op["operands"]
        def typed(typ, returned=False):
            # (what typ allows each array; unknown where typ is another family's or none; a call's
            # open items or values as its callee's returns were checked: open_results)
            known = dict(assumed(typ)) if family(typ) == kinds.get(result) else {}
            if returned and known:
                known.update(open_results(typ))
            chain = after
            for suffix in reversed(suffixes(result)):
                chain = made(result + suffix, known.get(suffix), chain)
            return chain
        if kind == "rt":
            name = op["text"]
            if name in NUMERIC_MAKERS:
                return made(result, NUMERIC_MAKERS[name], after)
            if name in ("list.new", "dict.new", "set.new", "dict.new_atomic") and op["immediate"] > 0:
                values, keys = hole_kinds(holes, op["immediate"], "dict.new" if name == "dict.new_atomic" else name)
                if name == "dict.new_atomic":
                    values = ATOMIC
                chain = after if keys is None else made(result + KEYS, [keys], after)
                return made(result, [values], chain)
            if name == "list.new":
                return made(result, [SCANNED], after)
            if name in ("dict.new", "dict.new_atomic", "dict.fromkeys", "set.new"):
                keys = key_kind(args[0], descriptors) if args else None
                keys = [keys] if keys else [ATOMIC, SCANNED]
                if name == "set.new":
                    return made(result, keys, after)
                return made(result, [ATOMIC if name == "dict.new_atomic" else SCANNED], made(result + KEYS, keys, after))
            if name in COPIES:
                sources = [a["value"] for a in args if a["value"] in kinds and kinds[a["value"]] == kinds.get(result)]
                if not sources:
                    return typed("")
                chain = moved(result, sources[-1], after)
                for source in reversed(sources[:-1]):
                    chain = ("node", {"op": "choice", "yes": moved(result, source, after), "no": chain})
                return chain
            if name == "dict.fromkeys_dict" and args and args[0]["value"] in kinds:
                # (pys_dict_fromkeys_dict: a new dict of its source's key kind, pys_dict_new's values)
                source = args[0]["value"] + (KEYS if kinds[args[0]["value"]] == "dict" else "")
                return made(result, [SCANNED], ("node", {"op": "copy", "dst": result + KEYS, "src": source, "next": after}))
            if name in COLUMNS and args and args[0]["value"] in kinds:
                return ("node", {"op": "copy", "dst": result, "src": args[0]["value"] + COLUMNS[name], "next": after})
            # (any other list the runtime makes is pys_list_new's, scanned; another dict or set,
            # what its type allows)
            if kinds.get(result) == "list":
                return made(result, [SCANNED], after)
            return typed(op["type"])
        if kind in ("mem.load", "mach.load") and args and args[0]["value"] in private:
            return moved(result, args[0]["value"], after)
        if kind in ("mem.load", "mach.load") and direct_access(op) and args and word(args[0]["value"]) is not None:
            held = word(args[0]["value"])  # (what the program's stores of the word hold)
            chain = after
            for suffix in reversed(suffixes(result)):
                chain = made(result + suffix, None if held is None else held.get(suffix), chain)
            return chain
        if kind in ("mem.load", "mach.load") and args and args[0]["type"].startswith("*"):
            return typed(args[0]["type"][1:])  # (the memory's type, whatever this load views it as)
        if kind == "call" and op["text"] in declared:
            return typed(declared[op["text"]][1], returned=True)
        if kind == "select" and len(args) == 3:
            return ("node", {"op": "choice", "yes": moved(result, args[1]["value"], after),
                             "no": moved(result, args[2]["value"], after)})
        if kind == "scalar.cast" and args and args[0]["value"] in kinds:
            return moved(result, args[0]["value"], after)
        if kind in ("mem.load", "mach.load", "call", "icall", "slot.unpack", "dyn.payload", "tuple.load", "list.load",
                    "gen.resume", "gen.ret", "landing", "exc.match", "union.payload", "init"):
            return typed(op["type"] if kind != "dyn.payload" else op["text"])
        return typed("")

    for slot in sorted(private):
        # (lowering stores zeroinitializer into each slot at entry: a slot read before any store is null)
        if slot in kinds:
            for suffix in suffixes(slot):
                emit({"op": "jump", "next": made(slot + suffix, [NONE], len(nodes) + 1)})
    for value in list(types)[:len(fn["parameters"])]:
        if value in kinds:
            emit({"op": "jump", "next": defined({"op": "call", "type": types[value], "operands": [], "text": ""}, value,
                                                 len(nodes) + 1)})

    def yielded(op):
        """A suspension's use of what it yields, as its generator's declared yield type (gen[T, ...]):
        the value slot.pack packed (its caller's slot.unpack assumes that type). A yielded word of
        a type with arrays that may hold pointers is otherwise unsupported."""
        made = fn.get("return_representation") or ""
        parts = targs(made) if made.startswith("gen[") else []
        word = op["operands"][0]["value"] if op["operands"] else ""
        packer = producers.get(word)
        if packer is not None and packer["op"] == "slot.pack" and packer["operands"] and parts:
            return [{"value": packer["operands"][0]["value"], "type": parts[0]}]
        if parts and not word.startswith("%") and "@" not in word:
            return []  # (a constant: a number, or null, which has no array)
        if not parts or any(tags is not None for _, tags in arrays(parts[0])):
            raise boundary.Unsupported(f"a yielded word of type {parts[0] if parts else made} that no slot.pack here made")
        return []

    entry_of = {}
    for block in fn["blocks"]:
        label = block["label"]
        entry_of[label] = len(nodes)
        for offset, op in enumerate(block["operations"]):
            kind, args = op["op"], op["operands"]
            if block["handler"] and block["handler"] in labels:
                emit({"op": "choice", "yes": len(nodes) + 1, "no": into(label, block["handler"])})
            # (a suspension uses what it yields, not the word it passes)
            used = yielded(op) if kind == "gen.yield" else args
            if kind not in ("phi", "empty.kind"):  # (empty.kind sets a kind: no use of an array)
                for position, operand in enumerate(used):
                    if not operand["value"].startswith("%") or operand["value"] in slots:
                        continue
                    # (its own view; a callee's parameter, the function's result and a store's
                    # memory are declared types too)
                    views, required = [operand["type"]], {}
                    if kind == "call" and op["text"] in declared and position < len(declared[op["text"]][0]):
                        views.append(declared[op["text"]][0][position])
                    if kind == "ret":
                        views.append(fn.get("return_representation") or "")
                        required.update(open_results(fn.get("return_representation") or ""))
                    if kind in ("mem.store", "mach.store") and position == 1 and args[0]["type"].startswith("*"):
                        views.append(args[0]["type"][1:])
                    key = memory_key(context, producers, args[0]["value"]) if kind in ("mem.store", "mach.store") \
                        and position == 1 and direct_access(op) else None
                    if key in words or key in invariants:
                        for suffix, tags in (words.get(key) or invariants.get(key) or {}).items():
                            # (a word's array that may be either kind constrains nothing)
                            if tags is not None and tags != EITHER and suffix in suffixes(operand["value"]):
                                required[suffix] = sorted(set(required.get(suffix, tags)) & set(tags))
                    if key in invariants:
                        for suffix in suffixes(operand["value"]):
                            follow({"op": "payload", "value": operand["value"] + suffix, "tags": EITHER})
                            stores.append((nodes[-1], key, suffix))
                    for view in views:
                        for suffix, tags in arrays(view):
                            if tags is not None:
                                required[suffix] = sorted(set(required.get(suffix, tags)) & set(tags))
                    sourced = []
                    for receiver, suffix, source in writes_of(op):
                        if position == receiver and (suffix == "" or kinds.get(operand["value"]) == "dict") \
                                and source_pointer(op, source):
                            if source_location(op, source) is None:
                                required[suffix] = sorted(set(required.get(suffix, POINTERS)) & set(POINTERS))
                            else:
                                sourced.append((suffix, source_location(op, source)))
                    for suffix, tags in required.items():
                        follow({"op": "payload", "value": operand["value"] + suffix, "tags": tags})
                        origins[id(nodes[-1])] = (label, offset, kind, position)
                        obligations += 1
                    for suffix, location in sourced:
                        either(operand["value"] + suffix, location, (label, offset, kind, position))
            if kind == "br":
                emit({"op": "jump", "next": into(label, op["targets"][0])})
                continue
            if kind in ("cbr", "switch", "check"):
                targets = list(op["targets"])
                if kind == "check":
                    targets.append(fn["check_targets"][op["descriptor"] or op["text"]])
                after = into(label, targets[-1])
                for target in reversed(targets[:-1]):
                    after = ("node", {"op": "choice", "yes": into(label, target), "no": after})
                emit({"op": "jump", "next": after})
                continue
            if kind in ("ret", "ret.none", "unreachable", "gen.ret") or (kind in ("raise", "throw") and not op["targets"]):
                emit({"op": "stop"})
                continue
            if kind == "empty.kind" and args and args[0]["value"] in kinds and args[0]["value"] not in slots:
                # (it stores a key kind into a dict or set: the tables it makes from then on have that
                # kind, while a table it may hold already keeps its own: a call cycle's forwarded result.
                # A set's first eight slots are scanned whatever its kind)
                holder = args[0]["value"]
                kept = holder + (KEYS if kinds[holder] == "dict" else "")
                tag = empty_kind(holes[op["immediate"]] if op["immediate"] > 0 and isinstance(holes, list)
                                 and op["immediate"] < len(holes) else args[0]["type"])
                tags = None if tag is None else sorted({tag, SCANNED}) if kinds[holder] == "set" else [tag]
                emit({"op": "choice", "yes": len(nodes) + 1, "no": made(kept, tags, len(nodes) + 1)})
            if kind in ("mem.store", "mach.store") and direct_access(op) and args[0]["value"] in private and args[0]["value"] in kinds:
                emit({"op": "jump", "next": moved(args[0]["value"], args[1]["value"], len(nodes) + 1)})
            elif kind in ("mach.store", "landing") and args and args[0]["value"] in private and args[0]["value"] in kinds:
                for suffix in suffixes(args[0]["value"]):
                    follow({"op": "havoc", "dst": args[0]["value"] + suffix})
            for result in (f"%t{n}" for n in op["results"]):
                if kind != "phi" and result in kinds:
                    emit({"op": "jump", "next": defined(op, result, len(nodes) + 1)})
                    for suffix, source in FILLS.get(op["text"], ()) if kind == "rt" else ():
                        if (suffix == "" or kinds[result] == "dict") and source_pointer(op, source):
                            if source_location(op, source) is None:
                                follow({"op": "payload", "value": result + suffix, "tags": POINTERS})
                                origins[id(nodes[-1])] = (label, offset, kind, "result")
                                obligations += 1
                            else:
                                either(result + suffix, source_location(op, source), (label, offset, kind, "result"))
            if op["targets"] and kind != "phi":
                for target in op["targets"][:-1]:
                    emit({"op": "choice", "yes": into(label, target), "no": len(nodes) + 1})
                emit({"op": "jump", "next": into(label, op["targets"][-1])})
            else:
                emit({"op": "jump", "next": len(nodes) + 1})
        if not block["operations"]:
            emit({"op": "stop"})

    placed = {}

    def place(value):
        if isinstance(value, str):
            return entry_of[value]
        if not isinstance(value, tuple):
            return value
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
    if len(nodes) > boundary.MAX_NODES:
        raise boundary.Unsupported(f"graph exceeds {boundary.MAX_NODES} nodes")
    reached, pending = {0}, [0]
    while pending:
        for target in boundary.successors(nodes[pending.pop()]):
            if target not in reached:
                reached.add(target)
                pending.append(target)
    order = sorted(reached)
    index = {old: new for new, old in enumerate(order)}
    located = {index[old]: origins[id(nodes[old])] for old in order if id(nodes[old]) in origins}
    nodes = [nodes[old] for old in order]
    for node in nodes:
        for key in ("yes", "no", "next"):
            if key in node:
                node[key] = index[node[key]]
    if eithers:
        certificate = boundary.infer_certificate(nodes)
        at = {id(node): position for position, node in enumerate(nodes)}
        for target, source in eithers:
            if id(target) not in at:
                continue
            facts = dict((value, tags) for value, tags in certificate[at[id(target)]])
            proved = facts.get(target["value"]) is not None and set(facts[target["value"]]) <= set(POINTERS)
            clean = facts.get(source["value"]) is not None and set(facts[source["value"]]) <= {ATOMIC, NONE}
            dropped = source if proved or not clean else target
            if dropped is target:
                source["tags"] = sorted([ATOMIC, NONE])
            following = dropped["next"]
            dropped.clear()
            dropped.update({"op": "jump", "next": following})
    stored = {}
    if stores:
        certificate = boundary.infer_certificate(nodes)
        at = {id(node): position for position, node in enumerate(nodes)}
        for probe, key, suffix in stores:
            if id(probe) in at:
                facts = dict((value, tags) for value, tags in certificate[at[id(probe)]]).get(probe["value"])
                held = stored.setdefault(key, {})
                held[suffix] = None if facts is None or held.get(suffix, ()) is None else sorted(set(held.get(suffix, ())) | set(facts))
            following = probe["next"]
            probe.clear()
            probe.update({"op": "jump", "next": following})
    candidate = {"schema_version": 2, "program": {"entry": 0, "nodes": nodes},
                 "certificate": boundary.infer_certificate(nodes)}
    return candidate, {"function": fn["symbol"], "obligations": obligations, "nodes": len(nodes),
                       "payloads": sum(node["op"] == "payload" for node in nodes), "origins": located,
                       "stored": stored}


def explain(candidate, origins):
    nodes, certificate = candidate["program"]["nodes"], candidate["certificate"]
    for index, node in enumerate(nodes):
        if node["op"] != "payload":
            continue
        known = dict((value, tags) for value, tags in certificate[index]).get(node["value"])
        if known is None or not set(known) <= set(node["tags"]):
            label, offset, kind, position = origins.get(index, ("?", "?", "?", "?"))
            return (f"{kind} at {label}:{offset} (operand {position}) needs {node['value']} in {node['tags']}; "
                    f"known: {'nothing' if known is None else known}")
    return None


def relevant(fn, declared, stored=frozenset()):
    """Whether fn uses a list, dict or set whose arrays may hold pointers: by an operand's view, its
    return type, a store's memory or a callee's parameter (declared: symbol -> parameter types), or
    writes such an array or a memory word whose stores are checked (stored: its addresses)."""
    def restricts(typ):
        return any(tags is not None for _, tags in arrays(typ))
    for block in fn["blocks"]:
        for op in block["operations"]:
            if op["op"] in ("mem.store", "mach.store") and op["operands"] and op["operands"][0]["value"] in stored:
                return True
            if any(restricts(a["type"]) for a in op["operands"]):
                return True
            if op["op"] in ("mem.store", "mach.store") and op["operands"] and op["operands"][0]["type"].startswith("*") \
                    and restricts(op["operands"][0]["type"][1:]):
                return True
            if op["op"] == "call" and any(restricts(t) for t in declared.get(op["text"], ())):
                return True
            if writes_of(op) or (op["op"] == "rt" and op["text"] in FILLS):
                return True
    # (its returns are checked where their type leaves list items or dict values open: open_results;
    # a generator's suspensions, by what it yields)
    made = fn.get("return_representation") or ""
    if made.startswith("gen[") and targs(made) and restricts(targs(made)[0]):
        return True
    return restricts(made) or bool(open_results(made))


def infer_invariants(snapshot, words, opened, rounds=3, declared=None):
    """What each open global holds, {suffix: tags} or None (unknown): the facts its stores' values
    have, with null (a global starts as null), found again with the loads assuming them until they
    hold. Only a guess: Lean checks each store of a global against what its loads then assume."""
    invariants = {key: None for key in opened}
    if not opened:
        return invariants
    context = {"classes": snapshot.get("classes") or {}, "layouts": snapshot.get("class_layouts") or {}}
    storing = []
    for fn in snapshot["functions"]:
        producers = {f"%t{n}": op for block in fn["blocks"] for op in block["operations"] for n in op["results"]}
        keys = {memory_key(context, producers, op["operands"][0]["value"]) for block in fn["blocks"]
                for op in block["operations"] if op["op"] in ("mem.store", "mach.store") and op["operands"]
                and direct_access(op)} & opened
        if keys:
            storing.append((fn, keys))
    for _ in range(rounds):
        held, unknown = {}, set()
        for fn, keys in storing:
            try:
                _, meta = normalize(snapshot, fn, (words, invariants), declared)
            except (boundary.Unsupported, ValueError, KeyError, RecursionError):
                unknown |= keys
                continue
            for key, facts in meta["stored"].items():
                for suffix, tags in facts.items():
                    known = held.setdefault(key, {})
                    known[suffix] = None if tags is None or known.get(suffix, ()) is None else sorted(set(known.get(suffix, ())) | set(tags))
        found = {key: None if key in unknown or not held.get(key) or None in held[key].values()
                 else {suffix: sorted(set(tags) | {NONE}) for suffix, tags in held[key].items()} for key in opened}
        if found == invariants:
            break
        invariants = found
    return invariants


def check_all(snapshot, checker=boundary.DEFAULT_CHECKER):
    boundary.check_header(snapshot)
    boundary.require("holes" in snapshot and "key_descriptors" in snapshot,
                     "type holes missing: inspect with --guard-evidence")
    records, codes = [], [0]
    declared = {fn["symbol"]: [fn["parameters"][i]["representation"] for i in argument_parameters(fn["parameters"])]
                for fn in snapshot["functions"]}
    words, opened = memory_types(snapshot)
    typed = signatures(snapshot)
    invariants = infer_invariants(snapshot, words, opened, declared=typed)
    context = {"classes": snapshot.get("classes") or {}, "layouts": snapshot.get("class_layouts") or {}}
    for fn in snapshot["functions"]:
        producers = {f"%t{n}": op for block in fn["blocks"] for op in block["operations"] for n in op["results"]}
        stored = {op["operands"][0]["value"] for block in fn["blocks"] for op in block["operations"]
                  if op["op"] in ("mem.store", "mach.store") and op["operands"] and direct_access(op)
                  and (memory_key(context, producers, op["operands"][0]["value"]) in words
                       or invariants.get(memory_key(context, producers, op["operands"][0]["value"])))}
        if not relevant(fn, declared, stored):
            continue
        try:
            candidate, meta = normalize(snapshot, fn, (words, invariants), typed)
            origins = meta.pop("origins")
            meta.pop("stored")
            encoded = boundary.encode(candidate)
            accepted = boundary.run_checker(checker, encoded, meta)
            record = dict(meta, status="accepted" if accepted else "rejected",
                          candidate_sha256=hashlib.sha256(encoded.encode()).hexdigest())
            if not accepted:
                record["error"] = explain(candidate, origins) or "a transfer is not justified"
            codes.append(0 if accepted else 1)
        except (boundary.Unsupported, ValueError, KeyError, OSError, subprocess.SubprocessError, RecursionError) as error:
            unsupported = isinstance(error, boundary.Unsupported)
            record = {"function": fn["symbol"], "status": "unsupported" if unsupported else "error", "error": str(error)}
            codes.append(2 if unsupported else 3)
        records.append(record)
    code = 3 if 3 in codes else 1 if 1 in codes else 2 if 2 in codes else 0
    return {"status": {0: "accepted", 1: "rejected", 2: "unsupported", 3: "error"}[code], "checked": code == 0,
            "records": records, "functions": len(records),
            "obligations": sum(r.get("obligations", 0) for r in records),
            "proved_obligations": sum(r.get("obligations", 0) for r in records if r["status"] == "accepted"),
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
