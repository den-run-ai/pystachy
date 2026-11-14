#!/usr/bin/env python3
"""Check promoting integer storage guards in completed inspection snapshots.

The Python adapter is trusted; its dataflow certificates are checked independently
by the Lean boundary checker. Storage semantics are proved in PystachyStorage.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import check_lean_boundary as bridge
import check_lean_int as arithmetic
from src.pystachy_compiler.utils import is_kw, is_tuple, kw_types, targs, tslots, unopt

DEFAULT_CHECKER = bridge.DEFAULT_CHECKER
Unsupported = bridge.Unsupported
require = bridge.require
LIMITATIONS = [
    "Checks guard safety in normalized typed IR, not source or LLVM equivalence.",
    "Snapshot fidelity, normalization, canonical integer encoding, immutable tuple views, "
    "runtime paired-word contracts and declared parameter layouts remain trusted.",
    "Arithmetic fit claims are checked by the separate Lean integer checker.",
    "Stack tuple copies trust the call ABI: an on-stack tuple has all slots of "
    "its exact specialization layout; only complete same-index copies are supported.",
]
MIN = "-9223372036854775808"
# Argument offsets at which runtime helpers accept one canonical (lo, digits) pair.
PAIRS = {
    "big.op": (0, 2), "big.cmp": (0, 2), "big.truediv": (0, 2),
    "big.cmp_float": (0,), "big.str": (0,), "big.hash": (0,), "big.float": (0,),
    "big.bit_length": (0,), "big.bit_count": (0,), "big.format": (0,),
    "big.powmod": (0, 2, 4), "big.sum": (1,), "big.box": (0,),
    "dyn.big": (0,), "dyn.big_box": (0,), "list.big_find": (1,),
    "dict.set_big": (2,), "dict.entry_set_big": (2,), "dict.big_pop": (3,),
    "dict.bkey_get": (1,), "dict.bkey_getbox": (1,), "dict.bkey_pop": (1,),
    "dict.bkey_pop_default": (1,), "dict.bkey_popbox": (1,), "dict.bkey_setdefault": (1,),
    "dict.big_setdefault": (2,), "dict.big_find": (1,), "dict.big_entry": (1,),
    "dict.big_put": (1,), "dict.big_del": (1,), "dict.bkey_big_pop": (1, 4),
    "dict.bkey_big_setdefault": (1, 3), "set.big_add": (1,), "set.big_has": (1,),
    "set.big_discard": (1,), "set.big_remove": (1,),
}
MAX_TYPE_TEXT = 4096  # of a representation's type, which unlike a name grows with its nesting
# These instructions are total on machine integers. Their intermediate low words
# may be speculative; obligations are retained until a non-speculative consumer.
PURE = {"scalar.cmp", "num.cmp", "int.ucmp", "select", "slot.pack", "slot.unpack"}
TOTAL_BINARY = {"add", "sub", "mul", "and", "or", "xor"}
TOTAL_CAST = {"ptrtoint", "inttoptr", "zext", "sext", "trunc", "bitcast"}


def args(op):
    return [a["value"] for a in op["operands"]]


def result(op):
    return f"%t{op['results'][-1]}"


def record_tuple(layout):
    """A **kwargs record kw[a:A,b:B] is the tuple of its values at run time (utils.is_kw), and a
    function reads it as that tuple. Any other layout is itself."""
    if not layout or not is_kw(layout):
        return layout
    return "tuple[" + ",".join(kw_types(layout)) + "]"


def pure(op):
    return (op["op"] in PURE or op["op"] == "scalar.bin" and op["text"] in TOTAL_BINARY
            or op["op"] == "scalar.cast" and op["text"] in TOTAL_CAST)


class Normalize:
    def __init__(self, fn):
        self.fn = fn
        metadata = fn.get("representation_metadata")
        if not isinstance(metadata, dict) or metadata.get("version") != 1:
            raise Unsupported("storage checks require representation_metadata version 1")
        require(type(metadata.get("int_containers")) is bool and isinstance(metadata.get("sources"), list),
                "invalid representation metadata")
        require(metadata.get("scope") == "definition and container-read representations; not physical allocation extents",
                "unknown representation metadata scope")
        seen_sources = set()
        for source in metadata["sources"]:
            require(isinstance(source, dict) and source.get("origin") in
                    {"parameter", "allocation", "definition", "constant", "held_value", "held_read", "held_pair", "big_popitem", "search_hold"},
                    "invalid representation source")
            bridge.name(source.get("value"), "representation value")
            # A type's text grows with its nesting: stat's table of file modes is a tuple type of
            # 406 characters, more than a name's 256.
            representation = source.get("representation")
            require(isinstance(representation, str) and 0 < len(representation) <= MAX_TYPE_TEXT
                    and "\0" not in representation, "invalid representation type")
            require(source["value"] not in seen_sources, "duplicate representation source")
            seen_sources.add(source["value"])
        self.defs = {}
        self.defined_at = {}
        self.nodes = [{"op": "stop"}]
        self.intern = {}
        self.origins = {}
        self.blocks = fn["blocks"]
        self.starts = {}
        self.pending = []
        self.edge_cache = {}
        self.tuple_resets = []
        self.obligations = []
        self.counts = Counter(low_word_uses=0, tail_reads=0, boundaries=0,
                              stack_copy_reads=0, stack_copy_obligations=0)
        self.sources = {s["value"]: s for s in fn["representation_metadata"]["sources"]}
        self.layout_cache = {}
        self.path_cache = {}
        self.fit_cache = {}
        self.layout = {s["value"]: s["representation"] for s in
                       fn.get("representation_metadata", {}).get("sources", [])}
        self.slots = set()
        self.slot_layout = {}
        for slot in fn.get("slots", []):
            n = slot["results"][0]
            if slot["immediate"] == 2:
                self.layout[f"%stk.{n}"] = slot["type"]
            else:
                suffix = ".def" if slot["immediate"] == 1 else ""
                name = f"%{slot['text'] or 'h'}{suffix}.{n}"
                self.slots.add(name)
                self.slot_layout[name] = slot["type"]
        for j, p in enumerate(fn["parameters"]):
            self.layout.setdefault(f"%a{j}", p["representation"])
        for b in self.blocks:
            require(b["label"] not in self.starts, "duplicate block label")
            self.starts[b["label"]] = None
            for offset, o in enumerate(b["operations"]):
                require(isinstance(o, dict) and set(o) == bridge.OP_KEYS, "invalid instruction fields")
                if o["op"] not in bridge.SUPPORTED_OPS | {"gen.start", "gen.yield", "gen.ret"}:
                    raise Unsupported("unclassified storage instruction: " + o["op"])
                for n in o["results"]:
                    v = f"%t{n}"
                    require(v not in self.defs, "duplicate result")
                    self.defs[v] = o
                    self.defined_at[v] = (b["label"], offset)
                if o["results"]:
                    self.layout.setdefault(result(o), o["type"])
        self.validate_ssa()
        self.stack_copy_loads, self.stack_copy_stores = self.stack_copies()
        self.stack_copy_sources = {copy[0] for copy in self.stack_copy_loads.values()}
        # Escaped slots are not private and cannot retain fit facts across calls.
        for b in self.blocks:
            for o in b["operations"]:
                for j, a in enumerate(args(o)):
                    if a in self.slots and not (j == 0 and o["op"] in {"mem.load", "mem.store"}):
                        self.slots.remove(a)
        self.taints = {}
        self.active = set()

    def stack_copies(self):
        """Recognize keep_stack's whole tuple transport, never a decoded read.

        The call ABI supplies full physical layout for on-stack tuples. Read-view
        metadata by itself does not supply that extent. Keep the stack predicate
        as a checked obligation at every copied trailing word.
        """
        loads, stores = {}, set()
        uses = Counter(v for b in self.blocks for op in b["operations"] for v in args(op))
        for block in self.blocks:
            operations = block["operations"]
            for offset, allocation in enumerate(operations):
                typ = allocation["type"]
                if allocation["op"] != "alloc.fixed" or not is_tuple(typ):
                    continue
                count = tslots(typ)
                sequence = operations[offset + 1:offset + 1 + 4 * count]
                if not count or len(sequence) != 4 * count:
                    continue
                base, copied, written = None, {}, set()
                for index in range(count):
                    src, load, dst, store = sequence[4 * index:4 * index + 4]
                    if ([o["op"] for o in (src, load, dst, store)] !=
                            ["mach.addr", "mach.load", "mach.addr", "mach.store"] or
                            src["type"] != "%ptr" or dst["type"] != "%ptr" or
                            src["text"] != "int" or dst["text"] != "int" or load["type"] != "int" or
                            any(o["targets"] for o in (src, load, dst, store)) or
                            len(args(src)) != 2 or args(src)[1] != str(index) or
                            args(dst) != [result(allocation), str(index)] or
                            args(load) != [result(src)] or args(store) != [result(dst), result(load)] or
                            any(uses[result(o)] != 1 for o in (src, load, dst))):
                        break
                    source = args(src)[0]
                    pointer = self.defs.get(source)
                    if (pointer is None or pointer["op"] != "mach.load" or pointer["type"] != "%ptr" or
                            len(args(pointer)) != 1 or self.slot_layout.get(args(pointer)[0]) != typ or
                            base is not None and base != source):
                        break
                    base = source
                    copied[result(load)] = (source, index, typ)
                    written.add(id(store))
                else:
                    loads.update(copied)
                    stores.update(written)
        return loads, stores

    def validate_ssa(self):
        edges = {}
        for b in self.blocks:
            require(b["operations"], "empty storage block")
            last = b["operations"][-1]
            out = list(last["targets"])
            if last["op"] == "check":
                target = self.fn.get("check_targets", {}).get(last["descriptor"] or last["text"])
                require(target in self.starts, "check lacks error target")
                out.append(target)
            if b["handler"] and b["handler"] in self.starts and any(o["op"] in bridge.INVOKES | {"check", "raise", "throw", "gen.start", "gen.yield"}
                                                    for o in b["operations"]):
                out.append(b["handler"])
            require(all(t != "" and t in self.starts for t in out), "unknown control-flow target")
            edges[b["label"]] = out
        entry = self.blocks[0]["label"]
        reached, pending = {entry}, [entry]
        while pending:
            for target in edges[pending.pop()]:
                if target not in reached:
                    reached.add(target)
                    pending.append(target)
        predecessors = {b: set() for b in reached}
        for b in reached:
            for target in edges[b]:
                predecessors[target].add(b)
        dom = {b: {entry} if b == entry else set(reached) for b in reached}
        changed = True
        while changed:
            changed = False
            for b in reached - {entry}:
                common = set.intersection(*(dom[p] for p in predecessors[b]))
                updated = {b} | common
                if updated != dom[b]:
                    dom[b] = updated
                    changed = True
        for b in self.blocks:
            if b["label"] not in reached:
                continue
            for index, op in enumerate(b["operations"]):
                if op["op"] == "phi":
                    require(len(op["targets"]) == len(args(op)), "phi predecessor arity mismatch")
                for position, value in enumerate(args(op)):
                    if not (value.startswith("%t") and value[2:].isdigit()):
                        continue
                    require(value in self.defined_at, "undefined temporary: " + value)
                    owner, offset = self.defined_at[value]
                    at = op["targets"][position] if op["op"] == "phi" else b["label"]
                    if at not in reached:
                        continue
                    require(owner in dom[at], "temporary does not dominate use: " + value)
                    if owner == at and op["op"] != "phi":
                        require(offset < index, "temporary read precedes definition: " + value)

    def add(self, node):
        if node["op"] == "choice" and node["yes"] == node["no"]:
            return node["yes"]
        key = tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in node.items()))
        if key in self.intern:
            return self.intern[key]
        require(len(self.nodes) < bridge.MAX_NODES, "storage graph exceeds node bound")
        self.nodes.append(node)
        self.intern[key] = len(self.nodes) - 1
        return len(self.nodes) - 1

    def jump(self, target):
        return self.add({"op": "jump", "next": target})

    def fact(self, value, tags, nxt):
        # The normalized assignment has this exact known abstract value.
        guard = self.add({"op": "guard", "value": value, "tags": tags, "yes": nxt, "no": 0})
        return self.add({"op": "havoc", "dst": value, "next": guard})

    def payload(self, value, tag, nxt, kind, source):
        n = self.add({"op": "payload", "value": value, "tags": [tag], "next": nxt})
        self.obligations.append({"node": n, "kind": kind, "source": source})
        return n

    def tuple_path(self, value, depth=0):
        if value not in self.path_cache:
            self.path_cache[value] = self._tuple_path(value, depth)
        return self.path_cache[value]

    def _tuple_path(self, value, depth=0):
        if depth > 64:
            raise Unsupported("nested tuple identity exceeds limit")
        op = self.defs.get(value)
        if op and op["op"] in {"slot.unpack", "slot.pack"}:
            return self.tuple_path(args(op)[0], depth + 1)
        if op and op["op"] == "tuple.load" and is_tuple(op["text"]):
            return self.tuple_path(args(op)[0], depth + 1) + "/" + str(op["immediate"])
        return value

    def layout_type(self, value, depth=0):
        if value not in self.layout_cache:
            self.layout_cache[value] = record_tuple(self._layout_type(value, depth))
        return self.layout_cache[value]

    def _layout_type(self, value, depth=0):
        if depth > 64:
            raise Unsupported("nested tuple representation exceeds limit")
        explicit = self.sources.get(value)
        if explicit and explicit["origin"] != "definition":
            return explicit["representation"]
        op = self.defs.get(value)
        if op and op["op"] == "mach.load" and op["type"] == "%ptr" and len(args(op)) == 1:
            slot = self.slot_layout.get(args(op)[0])
            if slot and is_tuple(unopt(slot)):
                return slot
        if op and op["op"] in {"slot.unpack", "slot.pack"}:
            inherited = self.layout_type(args(op)[0], depth + 1)
            if inherited and is_tuple(inherited):
                return inherited
        if op and op["op"] == "tuple.load":
            parent = self.layout_type(args(op)[0], depth + 1)
            if parent and is_tuple(parent) and op["immediate"] < len(targs(parent)):
                return targs(parent)[op["immediate"]]
        return self.layout.get(value)

    def tuple_word(self, value):
        op = self.defs.get(value)
        if op and op["op"] in {"slot.pack", "slot.unpack"}:
            return self.tuple_word(args(op)[0])
        if op and op["op"] == "tuple.load":
            return self.tuple_path(args(op)[0]), op["immediate"]
        return None

    def fit(self, value):
        if value not in self.fit_cache:
            self.fit_cache[value] = self._fit(value)
        return self.fit_cache[value]

    def _fit(self, value):
        # A canonical tget merges the ordinary word+null path and the marker
        # word+digits path. The result denotes the same immutable tuple item.
        op = self.defs.get(value)
        if op and op["op"] == "phi" and op["type"] == "int+" and len(args(op)) == 2:
            first, second = [self.defs.get(v) for v in args(op)]
            if first and second and first["op"] == second["op"] == "big.make":
                lo, hi = args(first)
                cell = self.tuple_word(lo)
                digit = self.defs.get(args(second)[1])
                if cell and hi == "null" and digit and digit["op"] == "scalar.cast" and digit["text"] == "inttoptr":
                    tail = self.tuple_word(args(digit)[0])
                    raw = self.defs.get(lo)
                    while raw and raw["op"] in {"slot.pack", "slot.unpack"}:
                        raw = self.defs.get(args(raw)[0])
                    if tail and raw and tail == (cell[0], cell[1] + len(targs(raw["operands"][0]["type"]))):
                        return f"fit-cell:{cell[0]}:{cell[1]}"
        return "fit:" + value

    def boundary(self, value, target, nxt):
        source = self.layout_type(value)
        target = unopt(target)
        if not is_tuple(target):
            return nxt
        if source:
            source = unopt(source)
        if not source or not is_tuple(source):
            if value in {"null", "undef"}:
                return nxt  # null/unbound safety is a separate obligation
            raise Unsupported("tuple view has unknown source representation: " + value)
        if source == target:
            return nxt
        path = self.tuple_path(value)
        def compare(a, b, key, following):
            aa, bb = targs(a), targs(b)
            require(len(aa) == len(bb), "tuple boundary changes arity")
            for index in reversed(range(len(aa))):
                if aa[index] == bb[index]:
                    continue
                cell = f"{key}:{index}"
                if aa[index] == "int+" and bb[index] == "int":
                    self.counts["boundaries"] += 1
                    following = self.payload("fit-cell:" + cell, "fit", following, "narrowing", value)
                elif aa[index] == "int" and bb[index] == "int+":
                    self.counts["boundaries"] += 1
                    following = self.payload("marker:" + cell, "ordinary", following, "promoting-view", value)
                elif is_tuple(aa[index]) and is_tuple(bb[index]):
                    following = compare(aa[index], bb[index], key + "/" + str(index), following)
                else:
                    raise Unsupported("tuple boundary changes a non-integer representation")
            return following
        return compare(source, target, path, nxt)

    def origin(self, value):
        op = self.defs.get(value)
        return args(op)[0] if op and op["op"] == "big.lo" else None

    def hi(self, value):
        op = self.defs.get(value)
        return args(op)[0] if op and op["op"] == "big.hi" else None

    def tuple_address(self, value, seen=None):
        seen = set() if seen is None else seen
        if value in seen:
            return False
        if len(seen) > 64:
            raise Unsupported("tuple address provenance exceeds limit")
        seen.add(value)
        typ = self.layout_type(value)
        if typ and is_tuple(unopt(typ)):
            return True
        op = self.defs.get(value)
        if op and op["op"] in {"mach.addr", "scalar.cast", "scalar.bin", "phi", "select", "slot.pack", "slot.unpack"}:
            operands = args(op)[1:] if op["op"] == "select" else args(op)
            return any(self.tuple_address(v, set(seen)) for v in operands)
        return False

    def machine_tuple(self, op):
        if op["op"] != "mach.load" or not args(op):
            return None
        address = self.defs.get(args(op)[0])
        if not address or address["op"] != "mach.addr" or len(args(address)) != 2:
            return None
        base, index = args(address)
        typ = self.layout_type(base)
        if typ:
            typ = unopt(typ)
        if not typ or not is_tuple(typ):
            return None
        return base, index, typ

    def marker(self, value):
        op = self.defs.get(value)
        if op and op["op"] in {"slot.unpack", "slot.pack"}:
            return self.marker(args(op)[0])
        if op and op["op"] == "tuple.load":
            return f"marker:{self.tuple_path(args(op)[0])}:{op['immediate']}"
        machine = self.machine_tuple(op) if op else None
        if machine:
            base, index, _ = machine
            return f"marker:{self.tuple_path(base)}:{index}"
        return "marker:" + value

    def zero(self, value, yes, no, depth=0):
        if depth > 64:
            raise Unsupported("integer guard expression exceeds depth limit")
        if value in {"0", "null", "false"}:
            return self.jump(yes)
        if value in {"true", "1"}:
            return self.jump(no)
        op = self.defs.get(value)
        if op:
            a = args(op)
            if op["op"] == "rt" and op["text"] == "on_stack" and len(a) == 1:
                return self.add({"op": "guard", "value": "stack:" + a[0], "tags": ["heap"],
                                 "yes": yes, "no": no})
            if op["op"] == "big.hi":
                return self.add({"op": "guard", "value": self.fit(a[0]), "tags": ["fit"],
                                 "yes": yes, "no": no})
            if op["op"] == "scalar.cast" and op["text"] in {"ptrtoint", "inttoptr"}:
                return self.zero(a[0], yes, no, depth + 1)
            if op["op"] == "scalar.bin" and op["text"] == "or":
                return self.zero(a[0], self.zero(a[1], yes, no, depth + 1), no, depth + 1)
            if op["op"] == "select":
                return self.condition(a[0], self.zero(a[1], yes, no, depth + 1),
                                      self.zero(a[2], yes, no, depth + 1), depth + 1)
            if op["op"] == "tuple.load":
                return self.add({"op": "guard", "value": "digits:" + self.marker(value)[7:],
                                 "tags": ["null"], "yes": yes, "no": no})
        layout = self.layout_type(value)
        if layout and layout.startswith("opt[") and is_tuple(unopt(layout)):
            def absent(typ, path, following):
                for index, item in enumerate(targs(typ)):
                    if item == "int+":
                        following = self.fact(f"fit-cell:{path}:{index}", ["fit"], following)
                    elif is_tuple(item):
                        following = absent(item, path + "/" + str(index), following)
                return following
            # Optional fit-cell means absent OR item fits; it is an actual
            # numeric fit fact only on the nonnull paths that decode an item.
            yes = absent(unopt(layout), self.tuple_path(value), yes)
        return self.add({"op": "guard", "value": "zero:" + value, "tags": ["null"],
                         "yes": yes, "no": no})

    def condition(self, value, yes, no, depth=0):
        if depth > 64:
            raise Unsupported("integer guard expression exceeds depth limit")
        if value in {"true", "false"}:
            return self.jump(yes if value == "true" else no)
        op = self.defs.get(value)
        if op:
            a = args(op)
            if op["op"] == "scalar.bin" and op["type"] == "bool":
                if op["text"] == "and":
                    return self.condition(a[0], self.condition(a[1], yes, no, depth + 1), no, depth + 1)
                if op["text"] == "or":
                    return self.condition(a[0], yes, self.condition(a[1], yes, no, depth + 1), depth + 1)
                if op["text"] == "xor" and "true" in a:
                    return self.condition(a[1] if a[0] == "true" else a[0], no, yes, depth + 1)
            stack_test = op["op"] == "num.cmp" and any(
                self.defs.get(v, {}).get("op") == "rt" and self.defs[v]["text"] == "on_stack" for v in a)
            if (op["op"] in {"scalar.cmp", "ptr.cmp"} or stack_test) and op["text"] in {"eq", "ne", "==", "!="}:
                if op["text"] in {"ne", "!="}:
                    yes, no = no, yes
                if a[0] in {"0", "null"}:
                    a = list(reversed(a))
                if a[1] in {"0", "null"}:
                    return self.zero(a[0], yes, no, depth + 1)
                if MIN in a:
                    other = a[1] if a[0] == MIN else a[0]
                    test = self.add({"op": "guard", "value": self.marker(other), "tags": ["marker"],
                                     "yes": yes, "no": no})
                    return self.add({"op": "guard", "value": self.marker(other), "tags": ["marker", "ordinary"],
                                     "yes": test, "no": 0})
            if op["op"] == "select":
                return self.condition(a[0], self.condition(a[1], yes, no, depth + 1),
                                      self.condition(a[2], yes, no, depth + 1), depth + 1)
        return self.add({"op": "choice", "yes": yes, "no": no})

    def paired_truth(self, op):
        if op["op"] != "scalar.cmp" or op["text"] not in {"eq", "ne"}:
            return False
        a = args(op)
        if len(a) != 2 or a[1] != "0":
            return False
        combined = self.defs.get(a[0])
        if not combined or combined["op"] != "scalar.bin" or combined["text"] != "or":
            return False
        lo, digits = args(combined)
        cast = self.defs.get(digits)
        return bool(self.origin(lo) is not None and cast and cast["op"] == "scalar.cast"
                    and cast["text"] == "ptrtoint" and self.hi(args(cast)[0]) == self.origin(lo))

    def is_pure(self, op):
        if pure(op):
            return True
        if op["op"] == "rt" and op["text"] == "range.has" and len(args(op)) == 4:
            # The only exception (zero step) depends on the unchanged step,
            # never on the speculative sought value. The helper has no writes.
            return not any(self.taint(v) for v in args(op)[1:])
        if op["op"] == "rt" and op["text"] == "list.find" and op["descriptor"] == "b":
            # Bool equality runs no callbacks and cannot raise; query truncation
            # may be speculative until the surrounding fits mask is evaluated.
            return len(args(op)) == 3 and not self.taint(args(op)[0]) and not self.taint(args(op)[2])
        return False

    def taint(self, value):
        if value in self.taints:
            return self.taints[value]
        if value in self.active:
            return False
        self.active.add(value)
        op = self.defs.get(value)
        found = bool(op and not self.paired_truth(op) and
                     (op["op"] == "big.lo" or self.is_pure(op) and any(self.taint(v) for v in args(op))))
        self.active.remove(value)
        self.taints[value] = found
        return found

    def needed(self, value, nxt, depth=0):
        """Demand numeric correctness only on paths on which a pure expression matters."""
        if not self.taint(value):
            return nxt
        if depth > 64:
            raise Unsupported("speculative low-word expression exceeds depth limit")
        op = self.defs[value]
        a = args(op)
        if op["op"] == "big.lo":
            return self.payload(self.fit(a[0]), "fit", nxt, "low-word", value)
        if op["op"] == "select":
            start = self.condition(a[0], self.needed(a[1], nxt, depth + 1),
                                   self.needed(a[2], nxt, depth + 1))
            return self.needed(a[0], start, depth + 1)
        if op["op"] == "scalar.bin" and op["type"] == "bool" and op["text"] in {"and", "or"}:
            # A trusted, untainted mask may suppress a speculative comparison.
            # If both sides depend on low words, demand both: neither is a
            # trustworthy mask for the other until its own value is justified.
            if self.taint(a[0]) and self.taint(a[1]):
                return self.needed(a[0], self.needed(a[1], nxt, depth + 1), depth + 1)
            mask, dependent = (a[1], a[0]) if self.taint(a[0]) else (a[0], a[1])
            needed = self.needed(dependent, nxt, depth + 1)
            return self.condition(mask, needed, nxt) if op["text"] == "and" else self.condition(mask, nxt, needed)
        for v in reversed(a):
            nxt = self.needed(v, nxt, depth + 1)
        return nxt

    def transport_origin(self, value, depth=0):
        if depth > 4:
            return None
        direct = self.origin(value)
        if direct is not None:
            return direct
        op = self.defs.get(value)
        if not op or op["op"] != "scalar.bin" or op["text"] != "and":
            return None
        left, mask = args(op)
        original = self.transport_origin(left, depth + 1)
        call = self.defs.get(original)
        selected = self.defs.get(mask)
        if not call or call["op"] != "rt" or call["text"] != "big.op" or args(call)[-1] != "5":
            return None
        if not selected or selected["op"] != "select" or args(selected)[2] != "-1":
            return None
        operand = self.origin(args(selected)[1])
        if operand is None:
            return None
        operands = args(call)
        x = arithmetic.operand_identity(operands[0], operands[1], self.defs)
        y = arithmetic.operand_identity(operands[2], operands[3], self.defs)
        ident = arithmetic.identity(operand, self.defs)
        side = "X" if ident == x else "Y" if ident == y else None
        if side is None:
            return None
        expected = {"and": ["fits" + side, "nonneg" + side]}
        try:
            condition = arithmetic.formula(args(selected)[0], x, y, self.defs)
        except Unsupported:
            return None
        # PystachyInt.and_mask: masking x&n again by the same nonnegative n
        # preserves the result. When it does not fit the canonical low word is 0.
        return original if condition == expected else None

    def pair(self, lo, hi):
        origin = self.origin(lo)
        return origin is not None and self.hi(hi) == origin

    def edge(self, label, previous):
        require(label != "" and label in self.starts, "unknown branch target")
        key = label, previous
        if key in self.edge_cache:
            return self.edge_cache[key]
        # Branch targets are patched once block entries are known; unlike other
        # nodes these placeholders must not be shared by hash-consing.
        require(len(self.nodes) < bridge.MAX_NODES, "storage graph exceeds node bound")
        n = len(self.nodes)
        self.nodes.append({"op": "jump", "next": 0})
        self.pending.append((n, label, previous))
        self.edge_cache[key] = n
        return n

    def fit_assignment(self, value, hi, nxt):
        yes = self.fact(self.fit(value), ["fit"], nxt)
        no = self.fact(self.fit(value), ["large"], nxt)
        return self.zero(hi, yes, no)

    def tail(self, op, nxt):
        copied = self.stack_copy_loads.get(result(op)) if op["results"] else None
        if copied:
            self.counts["stack_copy_reads"] += 1
            source, index, typ = copied
            if index >= len(targs(typ)):
                self.counts["stack_copy_obligations"] += 1
                return self.payload("stack:" + source, "stack", nxt, "stack-tail-copy", result(op))
            return nxt
        machine = self.machine_tuple(op)
        if op["op"] in {"mach.load", "mem.load"} and args(op) and self.tuple_address(args(op)[0]) and not machine:
            raise Unsupported("unclassified tuple-derived memory read")
        if machine:
            base, index, typ = machine
            pointer = self.defs.get(base)
            if pointer and pointer["op"] == "mach.load" and pointer["type"] == "%ptr":
                # Raw loads from tuple-valued local slots occur in keep_stack's
                # complete transport. If that shape fails, no computed index or
                # missing destination may make the source reads disappear.
                raise Unsupported("raw tuple-slot read is not part of a complete guarded stack copy")
            ts = targs(typ)
            if index.lstrip("-").isdigit() and not 0 <= int(index) < len(ts):
                raise Unsupported("raw tuple tail is not part of a complete guarded stack copy")
            offset = self.defs.get(index)
            if offset and offset["op"] == "scalar.bin" and offset["text"] == "add" and args(offset)[1] == str(len(ts)):
                self.counts["tail_reads"] += 1
                if any(t != "int+" for t in ts):
                    raise Unsupported("dynamic tuple digit read lacks homogeneous promoting layout")
                marker = f"marker:{self.tuple_path(base)}:{args(offset)[0]}"
                return self.payload(marker, "marker", nxt, "dynamic-tail-marker", result(op))
            if any(o["op"] == "scalar.cast" and o["text"] == "inttoptr" and result(op) in args(o)
                   for o in self.defs.values()):
                raise Unsupported("tuple digit pointer read lacks checked trailing offset")
            # The dynamic item changes each loop iteration even though its SSA
            # name is reused by the snapshot; discard the previous item's fact.
            return self.fact(f"marker:{self.tuple_path(base)}:{index}", ["marker", "ordinary"], nxt)
        if op["op"] != "tuple.load":
            return nxt
        v = args(op)[0]
        typ = op["operands"][0]["type"]
        if not is_tuple(typ):
            raise Unsupported("tuple read has no fixed tuple view")
        ts = targs(typ)
        k = op["immediate"]
        if k < len(ts):
            return nxt
        self.counts["tail_reads"] += 1
        item = k - len(ts)
        require(item < len(ts) and ts[item] == "int+", "tail slot is not a promoting item's digits")
        marker = f"marker:{self.tuple_path(v)}:{item}"
        source = self.layout_type(v)
        if source:
            source = unopt(source)
        if not source or not is_tuple(source):
            raise Unsupported("tuple tail has unknown source representation")
        source_items = targs(source)
        require(len(source_items) == len(ts), "tuple view changes arity")
        if source_items[item] == "int":
            # A plain tuple has no usable digit slot. The path must be impossible:
            # the earlier view test excludes marker, then this read requires marker.
            nxt = self.payload(marker, "ordinary", nxt, "tail-layout", v)
        elif source_items[item] != "int+":
            raise Unsupported("tuple tail source is not an integer item")
        return self.payload(marker, "marker", nxt, "tail-marker", v)

    def build(self, infer=True):
        for block in self.blocks:
            label = block["label"]
            nxt = 0
            for op in reversed(block["operations"]):
                k, a = op["op"], args(op)
                if k in {"br", "landing", "gen.start", "gen.yield"}:
                    nxt = self.edge(op["targets"][0], label)
                    if k == "gen.yield" and not (len(a) == 2 and self.pair(*a)):
                        for v in reversed(a):
                            nxt = self.needed(v, nxt)
                elif k == "cbr":
                    nxt = self.condition(a[0], self.edge(op["targets"][0], label),
                                         self.edge(op["targets"][1], label))
                    nxt = self.needed(a[0], nxt)
                elif k == "check":
                    error = self.fn["check_targets"].get(op["descriptor"] or op["text"])
                    require(error in self.starts, "check lacks error target")
                    nxt = self.condition(a[0], self.edge(error, label), self.edge(op["targets"][0], label))
                    nxt = self.needed(a[0], nxt)
                elif k == "switch":
                    # All successors remain possible: no fabricated integer facts.
                    targets = [self.edge(t, label) for t in op["targets"]]
                    require(targets, "empty switch")
                    nxt = targets[0]
                    for target in targets[1:]:
                        nxt = self.add({"op": "choice", "yes": target, "no": nxt})
                    nxt = self.needed(a[0], nxt)
                elif k in {"ret", "ret.none", "raise", "throw", "unreachable", "gen.ret", "gen.done"}:
                    nxt = self.edge(op["targets"][0], label) if op["targets"] else 0
                    paired = k == "gen.ret" and len(a) == 2 and self.pair(*a)
                    for operand in reversed(op["operands"]):
                        if is_tuple(unopt(operand["type"])):
                            nxt = self.boundary(operand["value"], operand["type"], nxt)
                    if not paired:
                        for v in reversed(a):
                            nxt = self.needed(v, nxt)
                elif k == "phi":
                    pass  # parallel assignments are put on incoming edges below
                else:
                    if op["targets"]:
                        require(len(op["targets"]) == 2, "unknown operation control-flow targets")
                        nxt = self.add({"op": "choice", "yes": self.edge(op["targets"][0], label),
                                         "no": self.edge(op["targets"][1], label)})
                    if op["results"] and k not in {"slot.pack", "slot.unpack", "tuple.load"}:
                        if result(op) in self.stack_copy_sources:
                            nxt = self.fact("stack:" + result(op), ["stack", "heap"], nxt)
                        representation = self.layout_type(result(op))
                        if representation and is_tuple(unopt(representation)):
                            reset = len(self.nodes)
                            self.nodes.append({"op": "jump", "next": nxt})
                            self.tuple_resets.append((reset, self.tuple_path(result(op))))
                            nxt = reset
                    if op["results"] and op["type"] == "int+":
                        value = result(op)
                        if k == "big.make":
                            nxt = self.fit_assignment(value, a[1], nxt)
                        elif k == "mem.load" and a[0] in self.slots:
                            nxt = self.add({"op": "copy", "dst": self.fit(value),
                                            "src": "fit:" + a[0], "next": nxt})
                        else:
                            nxt = self.fact(self.fit(value), ["fit", "large"], nxt)
                    if k == "mem.store" and a[0] in self.slots and op["operands"][1]["type"] == "int+":
                        nxt = self.add({"op": "copy", "dst": "fit:" + a[0], "src": self.fit(a[1]), "next": nxt})
                    if k == "rt" and op["text"] == "on_stack" and len(a) == 1:
                        nxt = self.fact("stack:" + a[0], ["stack", "heap"], nxt)
                    if k in {"mach.store", "mem.store"} and a and self.tuple_address(a[0]) and id(op) not in self.stack_copy_stores:
                        raise Unsupported("raw stores through tuple-derived addresses are not supported")
                    if k == "tuple.store":
                        tuple_value = a[0]
                        allocation = self.defs.get(tuple_value)
                        if not tuple_value.startswith("%stk.") and (not allocation or allocation["op"] != "alloc.fixed"):
                            raise Unsupported("tuple stores require a fresh allocation or stack tuple")
                        typ = op["operands"][0]["type"]
                        require(is_tuple(typ), "tuple store lacks tuple representation")
                        index = op["immediate"]
                        if index < len(targs(typ)) and is_tuple(unopt(targs(typ)[index])):
                            packed = self.defs.get(a[1])
                            if packed and packed["op"] == "slot.pack":
                                nxt = self.boundary(args(packed)[0], targs(typ)[index], nxt)
                            else:
                                raise Unsupported("nested tuple store lacks typed slot.pack source")
                        item = index if index < len(targs(typ)) else index - len(targs(typ))
                        cell = f"{self.tuple_path(tuple_value)}:{item}"
                        nxt = self.fact("fit-cell:" + cell, ["fit", "large"], nxt)
                        prefix, domain = (("marker:", ["marker", "ordinary"]) if index < len(targs(typ))
                                          else ("digits:", ["null", "digits"]))
                        nxt = self.fact(prefix + cell, domain, nxt)
                    nxt = self.tail(op, nxt)
                    for operand in reversed(op["operands"]):
                        if is_tuple(unopt(operand["type"])) and k not in {"slot.pack", "ptr.cmp"}:
                            nxt = self.boundary(operand["value"], operand["type"], nxt)
                        if k == "rt" and operand["type"].startswith("*tuple["):
                            target = operand["type"][1:]
                            if self.fn["representation_metadata"]["int_containers"]:
                                from src.pystachy_compiler.bigints import big_view
                                target = big_view(target)
                            packed = self.defs.get(operand["value"])
                            if packed and packed["op"] == "slot.pack":
                                nxt = self.boundary(args(packed)[0], target, nxt)
                    ignored = set()
                    if k == "rt":
                        pairs = PAIRS.get(op["text"], ())
                        if op["text"] == "list.big_find" and (len(a) < 4 or a[3] not in {"0", "false"}):
                            pairs = ()
                        for j in pairs:
                            if j + 1 < len(a) and self.pair(a[j], a[j + 1]):
                                ignored.add(j)
                    if k == "big.make" and self.pair(*a):
                        ignored.add(0)
                    if k == "big.make":
                        hi_op = self.defs.get(a[1])
                        if hi_op and hi_op["op"] == "select":
                            original = self.hi(args(hi_op)[2])
                            if original is not None and self.transport_origin(a[0]) == original:
                                ignored.add(0)  # arithmetic checker verifies every such claim
                    if not self.is_pure(op) and k not in {"big.lo", "big.hi"}:
                        for j in reversed(range(len(a))):
                            if j not in ignored:
                                nxt = self.needed(a[j], nxt)
                # Lowered throwing calls are invokes; retain the handler edge
                # additionally at all operations that can execute runtime code.
                # Pure scalar/tuple instructions cannot throw a Python exception.
                if block["handler"] and block["handler"] in self.starts and k in bridge.INVOKES | {"check", "raise", "throw", "gen.start", "gen.yield"}:
                    nxt = self.add({"op": "choice", "yes": nxt,
                                    "no": self.edge(block["handler"], label)})
            self.starts[label] = nxt
        cell_names = {node.get("value", node.get("dst", "")) for node in self.nodes
                      if node.get("value", node.get("dst", "")).startswith(("marker:", "digits:", "fit-cell:"))}
        def cells(root):
            return sorted(cell for cell in cell_names if any(
                cell.startswith(prefix + root + end) for prefix in ("marker:", "digits:", "fit-cell:")
                for end in (":", "/")))
        for reset, root in self.tuple_resets:
            target = self.nodes[reset]["next"]
            for cell in cells(root):
                target = self.add({"op": "havoc", "dst": cell, "next": target})
            self.nodes[reset]["next"] = target
        for n, label, previous in self.pending:
            target = self.starts[label]
            phis = [o for o in next(b for b in self.blocks if b["label"] == label)["operations"] if o["op"] == "phi"]
            assignments = []
            edge_checks = []
            for op in phis:
                require(len(op["targets"]) == len(op["operands"]), "malformed phi")
                incoming = [a["value"] for p, a in zip(op["targets"], op["operands"], strict=True) if p == previous]
                require(len(incoming) == 1, "missing or duplicate phi predecessor")
                if is_tuple(unopt(op["type"])):
                    target_type = self.layout_type(result(op)) or op["type"]
                    edge_checks.append(("boundary", incoming[0], target_type))
                    destination = self.tuple_path(result(op))
                    source = self.tuple_path(incoming[0])
                    for cell in cells(destination):
                        prefix, rest = cell.split(":", 1)
                        if incoming[0] == "null":
                            target = self.fact(cell, ["fit"] if prefix == "fit-cell" else
                                               ["marker", "ordinary"] if prefix == "marker" else ["null", "digits"], target)
                        else:
                            assignments.append((cell, prefix + ":" + source + rest[len(destination):]))
                if op["type"] == "int+":
                    destination = self.fit(result(op))
                    if destination.startswith("fit-cell:"):
                        index = args(op).index(incoming[0])
                        tag = "ordinary" if index == 0 else "marker"
                        edge_checks.append(("decode", "marker:" + destination[len("fit-cell:"):], tag))
                    assignments.append((destination, self.fit(incoming[0])))
                else:
                    edge_checks.append(("needed", incoming[0], ""))
            # Two passes preserve simultaneous phi semantics even on backedges.
            for j, (dst, _) in reversed(list(enumerate(assignments))):
                target = self.add({"op": "copy", "dst": dst, "src": f"phi:{n}:{j}", "next": target})
            for j, (_, src) in reversed(list(enumerate(assignments))):
                target = self.add({"op": "copy", "dst": f"phi:{n}:{j}", "src": src, "next": target})
            for kind, value, typ in reversed(edge_checks):
                if kind == "boundary":
                    target = self.boundary(value, typ, target)
                elif kind == "decode":
                    target = self.payload(value, typ, target, "tuple-decode", value)
                else:
                    target = self.needed(value, target)
            self.nodes[n]["next"] = target
        # Include cells created by phi-edge boundary checks, and clear them at
        # every execution of their producing instruction (SSA names repeat in loops).
        all_cells = {node.get("value", node.get("dst", "")) for node in self.nodes
                     if node.get("value", node.get("dst", "")).startswith(("marker:", "digits:", "fit-cell:"))}
        extra_cells = all_cells - cell_names
        for reset, root in self.tuple_resets:
            target = self.nodes[reset]["next"]
            for cell in sorted(extra_cells):
                if any(cell.startswith(prefix + root + end) for prefix in ("marker:", "digits:", "fit-cell:")
                       for end in (":", "/")):
                    target = self.add({"op": "havoc", "dst": cell, "next": target})
            self.nodes[reset]["next"] = target
        entry = self.starts[self.blocks[0]["label"]]
        for source in self.fn.get("representation_metadata", {}).get("sources", []):
            if source.get("origin") == "constant":
                for index, item in enumerate(source.get("items", [])):
                    if item.get("representation") == "int":
                        tag = "marker" if item["value"] == MIN else "ordinary"
                        entry = self.fact(f"marker:{source['value']}:{index}", [tag], entry)
        # Remove unreachable nodes; an unused branch body is not a proof obligation.
        reachable, todo = set(), [entry]
        while todo:
            n = todo.pop()
            if n not in reachable:
                reachable.add(n)
                todo.extend(bridge.successors(self.nodes[n]))
        order = sorted(reachable)
        remap = {n: j for j, n in enumerate(order)}
        nodes = []
        for n in order:
            node = dict(self.nodes[n])
            for key in ("next", "yes", "no"):
                if key in node:
                    node[key] = remap[node[key]]
            nodes.append(node)
        certificate = (bridge.infer_certificate(nodes, remap[entry]) if infer and any(node["op"] == "payload" for node in nodes)
                       else [[] for _ in nodes])
        self.counts["low_word_uses"] = sum(self.origin(v) is not None for b in self.blocks
                                          for op in b["operations"] for v in args(op))
        obligations = list({o["node"]: dict(o, node=remap[o["node"]]) for o in self.obligations
                            if o["node"] in remap}.values())
        candidate = {"schema_version": 2, "program": {"nodes": nodes, "entry": remap[entry]},
                     "certificate": certificate}
        return candidate, {**self.counts, "nodes": len(nodes), "payloads": len(obligations),
                           "obligations": len(obligations), "sites": obligations}


def normalize_snapshot(snapshot, function):
    bridge.check_header(snapshot)
    selected = [f for f in snapshot["functions"] if function in {f["symbol"], f["name"]}]
    require(len(selected) == 1, "function selector must be unique")
    return Normalize(selected[0]).build()


def proof_batches(candidate, batch_size=128):
    """Keep the complete CFG while checking disjoint batches of read obligations.

    A payload instruction changes no state, so replacing an unselected one by
    its jump preserves every execution. All original payload nodes are covered
    exactly once; no resource limit of the Lean checker is increased.
    """
    require(type(batch_size) is int and batch_size > 0, "proof batch size must be positive")
    original = candidate["program"]["nodes"]
    sites = [j for j, node in enumerate(original) if node["op"] == "payload"]
    groups = [sites] if len(sites) <= 128 else [sites[j:j + batch_size] for j in range(0, len(sites), batch_size)]
    pending = list(reversed(groups))
    while pending:
        group = pending.pop()
        selected = set(group)
        nodes = [dict(node) if node["op"] != "payload" or j in selected else {"op": "jump", "next": node["next"]}
                 for j, node in enumerate(original)]
        entry = candidate["program"]["entry"]
        try:
            certificate = bridge.infer_certificate(nodes, entry) if group else [[] for _ in nodes]
        except Unsupported as error:
            if len(group) <= 1 or "inference exceeds" not in str(error):
                raise
            middle = len(group) // 2
            pending.extend([group[middle:], group[:middle]])
            continue
        yield {"schema_version": 2, "program": {"nodes": nodes, "entry": entry}, "certificate": certificate}, group


def check_all(snapshot, checker=DEFAULT_CHECKER):
    bridge.check_header(snapshot)
    records = []
    for fn in snapshot["functions"]:
        ops = [o for b in fn["blocks"] for o in b["operations"]]
        if not any(o["op"] == "big.lo" or is_tuple(unopt(o["type"])) or
                   any(is_tuple(unopt(a["type"])) for a in o["operands"]) for o in ops):
            continue
        raw_defs = {f"%t{n}": o for o in ops for n in o["results"]}
        low_uses = sum(raw_defs.get(a["value"], {}).get("op") == "big.lo" for o in ops for a in o["operands"])
        fixed_tails = sum(o["op"] == "tuple.load" and is_tuple(o["operands"][0]["type"])
                          and o["immediate"] >= len(targs(o["operands"][0]["type"])) for o in ops)
        record = {"function": fn["symbol"], "low_word_uses": low_uses, "tail_reads": fixed_tails,
                  "normalization_complete": False}
        try:
            candidate, metadata = Normalize(fn).build(infer=False)
            record.update({k: v for k, v in metadata.items() if k != "sites"})
            record["normalization_complete"] = True
            hashes, covered, unproved = [], set(), []
            accepted = True
            for batch, sites in proof_batches(candidate):
                require(not covered.intersection(sites), "proof batches repeat an obligation")
                covered.update(sites)
                encoded = bridge.encode(batch)
                hashes.append(hashlib.sha256(encoded.encode()).hexdigest())
                ok = bridge.run_checker(checker, encoded, {"nodes": metadata["nodes"], "payloads": len(sites)})
                accepted &= ok
                if not ok:
                    unproved += [s for s in metadata["sites"] if s["node"] in sites and not any(
                        fact[0] == batch["program"]["nodes"][s["node"]]["value"] and
                        set(fact[1]) <= set(batch["program"]["nodes"][s["node"]]["tags"])
                        for fact in batch["certificate"][s["node"]])]
            require(len(covered) == metadata["obligations"], "proof batches omit an obligation")
            record.update(proof_batches=len(hashes), candidate_sha256s=hashes)
            record["candidate_sha256"] = hashlib.sha256(json.dumps(hashes, separators=(",", ":")).encode()).hexdigest()
            record["status"] = "accepted" if accepted else "rejected"
            if not accepted:
                record["unproved"] = unproved
        except Unsupported as error:
            record.update(status="unsupported", message=str(error))
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError, RecursionError) as error:
            record.update(status="error", message=str(error))
        records.append(record)
    arithmetic_result, _ = arithmetic.check_all(snapshot)
    worst = max([r["status"] for r in records] + [arithmetic_result["status"]], key=bridge.SEVERITY.index)
    totals = {k: sum(r.get(k, 0) for r in records) for k in
              ("low_word_uses", "tail_reads", "boundaries", "stack_copy_reads", "stack_copy_obligations",
               "obligations", "proof_batches")}
    totals.update(functions=len(snapshot["functions"]), obligation_functions=len(records),
                  unclassified_functions=sum(not r["normalization_complete"] for r in records),
                  proved_obligations=sum(r.get("obligations", 0) for r in records if r["status"] == "accepted"),
                  **{s: sum(r["status"] == s for r in records) for s in bridge.SEVERITY})
    return {"status": worst, "checked": worst not in {"error", "unsupported"}, "functions": records,
            "totals": totals, "arithmetic": arithmetic_result, "limitations": LIMITATIONS}, bridge.OUTCOMES[worst]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--checker", default=DEFAULT_CHECKER, type=Path)
    ns = parser.parse_args(argv)
    try:
        snapshot, digest = bridge.read_snapshot(ns.snapshot, bridge.MAX_PROGRAM_BYTES)
        report, code = check_all(snapshot, ns.checker)
        report["snapshot_sha256"] = digest
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report, code = {"status": "error", "message": str(error), "checked": False}, 3
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
