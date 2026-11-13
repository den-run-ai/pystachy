#!/usr/bin/env python3
"""Check with Lean that the unchecked accesses of typed-IR snapshots are safe.

Some typed-IR operations read memory without the runtime check that would otherwise guard
them. `list.load` reads a list item behind a length test, inside a loop over the list or after
the unpacking check of its length; `dict.val`, `dict.key`, `dict.entry_set` and the other entry
operations of dicts and sets use the entry that a lookup or an iteration step found (`dictfuse`,
iteration and the frontend's lookups). This tool normalizes the functions of a completed
typed-after snapshot (tools/inspect_compiler.py) to the access model of
tools/lean_boundary/PystachyAccess.lean, suggests facts at each point and asks the Lean
checker to verify them: every list read's index must be within the list's current length and
every entry used must still be live, on every path. Exit 0 when Lean accepts every function,
1 when it rejects one, 2 when one is outside the supported abstraction and 3 on a malformed
snapshot or another operational error.
"""
from __future__ import annotations

import argparse
from collections import deque
import functools
import hashlib
import heapq
import json
from pathlib import Path
import re
import subprocess
import sys

from check_lean_boundary import (INVOKES, MAX_PROGRAM_BYTES, OP_KEYS, OUTCOMES, SEVERITY,
                                 TERMINATORS, Unsupported, check_header, name, read_snapshot,
                                 require, unique_object)
from check_lean_effects import summaries

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.specs import IROPS, RUNTIME  # noqa: E402

DEFAULT_CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-access"
MAX_INSTRUCTIONS = 16384
MAX_NODES = 65536
MAX_FACTS_AT = 4096
MAX_FACTS = 1048576
MAX_CANDIDATE_BYTES = 64 * 1024 * 1024
MIN_I64 = -(2 ** 63)
MAX_I64 = 2 ** 63 - 1
MAX_LEN = 2 ** 62  # (PystachyAccess.maxLen: the most items a list holds)
# Runtime operations that read or write a dict's or set's entry by its index without checking
# it (runtime.c: d->vals[e] and the like): the entry must be live. A write of an entry's value
# moves no entry; deleting one is a dict write after it.
ACCESS_RT = {"dict.val", "dict.key", "dict.big_val", "dict.big_key", "dict.entry_set", "dict.entry_set_big",
             "dict.entry_del", "set.key", "set.big_key", "set.slot_del", "dict.val_or_zero",
             "dict.eq_find", "dict.eq_pair_find"}
SOURCE_ENTRY_RT = {"dict.eq_find", "dict.eq_pair_find"}
# Lookups and iteration steps that return -1 or a live entry, and lookups that return a live
# entry or raise (runtime.c). A dict comparison's lookup of one dict's key in the other
# (dict.eq_find, dict.eq_pair_find) runs the keys' __eq__ and restarts when it changes the table.
FINDS = {"dict.find", "dict.big_find", "dict.find_int_nobox", "dict.int_find_any", "dict.next", "dict.prev",
         "dict.eq_next", "dict.eq_find", "dict.eq_pair_find", "set.next", "set.int_find_any"}
# dict.big_put finds or adds a promoting int key: its entry, live.
ENTRIES = {"dict.entry", "dict.big_entry", "dict.big_put"}
# Runtime operations whose list writes touch only the new list they return (runtime.c): no
# existing list's length changes. A slice records missing item identities of its source too,
# which leaves its length alone.
FRESH_LIST_WRITES = {"list.slice"}
# Runtime list writes that store one item of an existing list and change no list's length
# (runtime.c's pys_list_set raises IndexError or stores; listguard's copies keep them where a list
# may hold numeric identities).
ITEM_WRITES = {"list.set"}
LIMITATIONS = [
    "Only list.load bounds and the inventoried dict/set entry accesses in each normalized function are checked.",
    "Python normalization, snapshot fidelity, runtime effects (RUNTIME and the U? descriptor rule), "
    "the independent body-effect scan, the runtime's lookup, length, slicing and unpacking contracts, the List "
    "header layout and LLVM lowering are not proved.",
    "Fields of one class at different indices are assumed to be distinct memory.",
    "Closure environments hold pointers to cells; recognized native-container cell loads use the "
    "same heap model and are invalidated by writes or callbacks, not assumed immutable.",
    "A suspended generator's caller may change any list, dict, field or global; phi and select "
    "results and other memory loads get unknown values.",
    "The native Lean executable adds the Lean compiler and runtime to the trusted base.",
]
LITERAL = re.compile(r"-?[0-9]+")
MAX_TYPE = 1 << 20


def instruction(value, slot=False):
    """A validated operation of the snapshot (a type, such as a long tuple's, can be long)."""
    require(isinstance(value, dict) and set(value) == OP_KEYS, "invalid instruction fields")
    for key in ("op", "text", "descriptor"):
        require(isinstance(value[key], str) and len(value[key]) <= 4096, f"invalid instruction {key}")
    require(isinstance(value["type"], str) and len(value["type"]) <= MAX_TYPE, "invalid instruction type")
    if value["op"] not in ({"slot"} if slot else IROPS):
        raise Unsupported(f"unsupported operation: {value['op']}")
    require(type(value["immediate"]) is int and 0 <= value["immediate"] < 2 ** 31, "invalid instruction immediate")
    require(isinstance(value["results"], list) and len(value["results"]) <= 8
            and all(type(n) is int and 0 <= n <= 1000000 for n in value["results"]), "invalid instruction results")
    require(isinstance(value["operands"], list) and len(value["operands"]) <= 65536, "invalid instruction operands")
    for operand in value["operands"]:
        require(isinstance(operand, dict) and set(operand) == {"value", "type"}, "invalid operand")
        name(operand["value"], "operand value")
        require(isinstance(operand["type"], str) and len(operand["type"]) <= MAX_TYPE, "invalid operand type")
    require(isinstance(value["targets"], list) and len(value["targets"]) <= 256, "invalid instruction targets")
    for target in value["targets"]:
        name(target, "branch target")
    return value


def runtime_effects(key, descriptor=""):
    """The effect tokens of runtime operation key (RUNTIME's `result:params|effects|symbol`),
    or None where it may do anything. A possible effect (`U?`) is the compiler's (gen_opfx):
    user code runs only where the static descriptor of its values can hold an object (`O`, `H`,
    `P`), an exception (`E`) or a dynamic value (`A`); then any effect is possible."""
    entry = RUNTIME.get(key)
    if entry is None:
        return None
    effects = set(entry.split("|")[1].split())
    if "U?" in effects:
        if any(letter in descriptor for letter in "OHPEA"):
            return None
        effects.discard("U?")
    effects.discard("R?")
    return effects


def kills(effects):
    """Which of the model's states an operation with these effect tokens may change: list
    lengths (a list write or unknown code), dict entries (a dict write or unknown code), globals
    (a global write or unknown code) and object fields (an object write or unknown code)."""
    if effects is None:
        return True, True, True, True
    unknown = "U" in effects or "U?" in effects
    return (unknown or "wL" in effects, unknown or "wD" in effects, unknown or "wG" in effects,
            unknown or "wO" in effects)


def operand_of(value):
    """A model operand: a register's name, an integer literal or None (unknown)."""
    if value.startswith("%"):
        return value
    if value in ("null", "false"):
        return 0
    if value == "true":
        return 1
    if LITERAL.fullmatch(value):
        number = int(value)
        if MIN_I64 <= number <= MAX_I64:
            return number
    return None


# ---- the access model's facts, mirroring PystachyAccess.lean's rules ----

@functools.lru_cache(maxsize=1 << 16)
def mentions(fact):
    """The values a fact is about (a cell's field label is none)."""
    if fact[0] == "cell":
        return (fact[1], fact[4])
    return tuple(part for part in fact[1:] if isinstance(part, str))


@functools.lru_cache(maxsize=1 << 16)
def mention_set(fact):
    return frozenset(mentions(fact))


def rename(fact, x, y):
    return tuple(y if isinstance(part, str) and part == x and index > 0 and not (fact[0] == "cell" and index == 2)
                 else part for index, part in enumerate(fact))  # (a cell's class is no value)


def survives(node, fact):
    op = node["op"]
    if "dst" in node:
        return node["dst"] not in mentions(fact)
    if op == "lists":
        return fact[0] != "len"
    if op == "dicts":
        return fact[0] not in ("found", "entry")
    if op == "write_field":
        # (another field of the same class, of any object, is other memory)
        return fact[0] != "cell" or (fact[2] == node["class"] and fact[3] != node["index"])
    if op == "heap":
        return fact[0] != "cell"
    return True


def no_wrap(facts, src, k):
    """PystachyAccess.noWrap: src + k fits."""
    if k <= 0 and any(f[0] == "ge" and f[1] == src and MIN_I64 <= f[2] + k for f in facts):
        return True
    if 0 <= k <= 1 and any(f[0] in ("below", "found") and f[1] == src for f in facts):
        return True
    # (src = b + c exactly, so src + k <= b where c + k <= 0)
    if 0 <= k and any(f[0] == "off" and f[1] == src and f[3] + k <= 0 for f in facts):
        return True
    # (a length plus a constant: a list has at most MAX_LEN items)
    return 0 <= k <= MAX_I64 - MAX_LEN and any(f[0] == "len" and f[1] == src for f in facts)


def no_wrap_sum(facts, x, y):
    """PystachyAccess.noWrapSum: x + y fits, as x < c where some s = c + y, and lower bounds of x
    and y that add up to at least the least 64-bit value."""
    return (any(f[0] == "lt" and f[1] == x and any(
                g[0] == "sum" and ((g[2] == f[2] and g[3] == y) or (g[2] == y and g[3] == f[2])) for g in facts)
                for f in facts) and
            any(f[0] == "ge" and f[1] == x and any(
                g[0] == "ge" and g[1] == y and MIN_I64 <= f[2] + g[2] for g in facts) for f in facts))


def no_wrap_sum_premises(facts, x, y):
    """The facts no_wrap_sum(facts, x, y) uses, or None."""
    for f in facts:
        if f[0] != "lt" or f[1] != x:
            continue
        s = next((g for g in facts if g[0] == "sum" and ((g[2] == f[2] and g[3] == y) or (g[2] == y and g[3] == f[2]))),
                 None)
        if s is None:
            continue
        for g in facts:
            if g[0] == "ge" and g[1] == x:
                h = next((h for h in facts if h[0] == "ge" and h[1] == y and MIN_I64 <= g[2] + h[2]), None)
                if h is not None:
                    return [f, s, g, h]
    return None


def cond_facts(cond, outcome):
    kind, a, b = cond["cmp"], cond["a"], cond["b"]
    reg_a, reg_b = isinstance(a, str), isinstance(b, str)
    if kind == "slt":
        if outcome and reg_a and reg_b:
            return [("lt", a, b)]
        if outcome and reg_a and not reg_b:
            return [("atMost", a, b - 1)]
        if not outcome and not reg_a and reg_b:
            return [("atMost", b, a)]
        if outcome and not reg_a and reg_b:
            return [("ge", b, a + 1)]
        if not outcome and reg_a and not reg_b:
            return [("ge", a, b)]
    elif kind == "sle":
        if outcome and reg_a and reg_b:
            return [("le", a, b, 0)]
        if outcome and reg_a and not reg_b:
            return [("atMost", a, b)]
        if not outcome and not reg_a and reg_b:
            return [("atMost", b, a - 1)]
        if outcome and not reg_a and reg_b:
            return [("ge", b, a)]
        if not outcome and reg_a and not reg_b:
            return [("ge", a, b + 1)]
    elif kind == "ult":
        if outcome and reg_a and reg_b:
            return [("ult", a, b)]
    elif kind == "eq":
        if reg_a and not reg_b:
            return [("ge", a, b)] if outcome else [("ne", a, b)]
        if not reg_a and reg_b:
            return [("ge", b, a)] if outcome else [("ne", b, a)]
        if reg_a and reg_b and outcome:
            return [("eq", a, b)]
    return []


def bound_facts(facts, cond, outcome):
    """PystachyAccess.boundFacts: an unsigned `k < b` of a nonnegative b bounds b below."""
    a, b = cond["a"], cond["b"]
    if cond["cmp"] == "ult" and outcome and isinstance(a, int) and isinstance(b, str) and nonneg(facts, b):
        if 0 <= a <= MAX_I64:
            return [("ge", b, a + 1)]
        if MIN_I64 <= a < 0:
            # (a negative a reads as at least 2**63 unsigned: no nonnegative b exceeds it)
            return [("absurd",)]
    return []


def nonneg(facts, x):
    return any((f[0] == "ge" and f[1] == x and f[2] >= 0) or (f[0] == "len" and f[1] == x) for f in facts)


def nonneg_fact(facts, x):
    """A fact of facts that shows x >= 0 (a premise nonneg needs), or None."""
    for f in facts:
        if (f[0] == "ge" and f[1] == x and f[2] >= 0) or (f[0] == "len" and f[1] == x):
            return f
    return None


def encodable_fact(fact):
    """Fact constants fit the Lean checker's bounded JSON representation."""
    return all(type(part) is not int or MIN_I64 <= part <= MAX_I64 for part in fact)


def generated(facts, node, edge):
    return [fact for fact in generated_unbounded(facts, node, edge) if encodable_fact(fact)]


def generated_unbounded(facts, node, edge):
    op = node["op"]
    dst = node.get("dst")
    if op == "copy":
        return [] if dst == node["src"] else [("eq", dst, node["src"])]
    if op == "lit":
        return [("ge", dst, node["value"])]
    if op == "add":
        return ([("off", dst, node["src"], node["k"])]
                if dst != node["src"] and no_wrap(facts, node["src"], node["k"]) else [])
    if op == "add_checked":
        return [("off", dst, node["src"], node["k"])] if edge == 0 and dst != node["src"] else []
    if op == "add_reg":
        x, y = node["x"], node["y"]
        return ([("sum", dst, x, y)] if dst not in (x, y) and (no_wrap_sum(facts, x, y) or no_wrap_sum(facts, y, x))
                else [])
    if op == "add_checked_reg":
        return [("sum", dst, node["x"], node["y"])] if edge == 0 and dst not in (node["x"], node["y"]) else []
    if op == "length":
        return [] if dst == node["list"] else [("len", dst, node["list"])]
    if op == "find":
        return [] if dst == node["dict"] else [("found", dst, node["dict"])]
    if op == "entry":
        return [] if dst == node["dict"] else [("entry", dst, node["dict"])]
    if op == "read_field":
        return [] if dst == node["object"] else [("cell", node["object"], node["class"], node["index"], dst)]
    if op == "write_field":
        return [("cell", node["object"], node["class"], node["index"], node["value"])]
    if op == "test":
        found = cond_facts(node["cond"], edge == 0)
        return found + [fact for fact in bound_facts(facts, node["cond"], edge == 0) if fact not in found]
    return []


def immediates(node, edge, facts):
    kept = [fact for fact in facts if survives(node, fact)]
    return kept + [fact for fact in generated(facts, node, edge) if fact not in kept]


def conclusions(fact, by_name, index, relevant, lower_bounds=()):
    """What one rule derives from fact and a known fact that shares a value with it, each
    with its premises (a semi-naive step: the rules need at least one new premise)."""
    out = []
    kind = fact[0]
    names = mentions(fact)

    def partners(name, kinds):
        return [other for other in by_name.get(name, ()) if other[0] in kinds]

    if kind == "cell":
        for other in partners(fact[1], ("cell",)):
            if other[1:4] == fact[1:4] and other[4] != fact[4]:
                out.append((("eq", fact[4], other[4]), [fact, other]))
    # An equality restates facts about one value as facts about the other; a fact restated so
    # is enough (one equality serves both directions, and restated equalities would only chain
    # equal values, which the facts restated along each copy already do).
    if kind == "eq":
        a, b = fact[1], fact[2]
        for x, y in ((a, b), (b, a)):
            if y in relevant:
                for other in list(by_name.get(x, ())):
                    if other[0] != "eq":
                        out.append((rename(other, x, y), [fact, other]))
    else:
        for x in set(names):
            # (the reverse: an equality known before restates this new fact)
            for other in partners(x, ("eq",)):
                y = other[2] if other[1] == x else other[1]
                if y in relevant and y != x:
                    out.append((rename(fact, x, y), [other, fact]))
    if kind == "ge":
        a, k = fact[1], fact[2]
        if k > 0:
            out.append((("ge", a, 0), [fact]))
        for bound in lower_bounds:
            if bound < k:
                out.append((("ge", a, bound), [fact]))
        if k >= 0 and ("found", a) in {other[:2] for other in partners(a, ("found",))}:
            # (a lookup's result of at least 0 is not -1)
            out.append((("ne", a, -1), [fact]))
        for other in partners(a, ("off",)):
            if other[2] == a:
                out.append((("ge", other[1], k + other[3]), [other, fact]))
                if other[3] < 0 and -other[3] <= k:
                    out.append((("below", other[1], a), [other, fact]))
        if k >= 0:
            for other in partners(a, ("lt", "ult")):
                if other[0] == "lt" and other[1] == a:
                    out.append((("below", a, other[2]), [other, fact]))
                if other[0] == "ult" and other[2] == a:
                    out.append((("below", other[1], a), [other, fact]))
        if k >= 0:
            for other in partners(a, ("le",)):
                if other[1] == a and other[3] >= 1:
                    out.append((("below", a, other[2]), [other, fact]))
        # (b = a + j going back: b's bound through it)
        for other in partners(a, ("off",)):
            if other[1] == a:
                out.append((("ge", other[2], k - other[3]), [other, fact]))
        # (a length known to be at least k above a constant bound of an index; or, a nonnegative
        # index of such a bound)
        for other in index:
            if other[0] == "atMost" and other[2] < k:
                lower = nonneg_fact(index, other[1])
                if lower is not None:
                    out.append((("below", other[1], a), [other, fact, lower]))
        if k >= 0:
            for other in partners(a, ("atMost",)):
                for g in index:
                    if g[0] == "ge" and g[2] > other[2]:
                        out.append((("below", a, g[1]), [other, g, fact]))
    elif kind == "atMost":
        a, c = fact[1], fact[2]
        for other in partners(a, ("off",)):
            if other[2] == a:  # (x = a + j)
                out.append((("atMost", other[1], c + other[3]), [other, fact]))
        lower = nonneg_fact(index, a)
        if lower is not None:
            for g in index:
                if g[0] == "ge" and g[2] > c:
                    out.append((("below", a, g[1]), [fact, g, lower]))
    elif kind == "le":
        # a + k <= b (PystachyAccess: a difference bound)
        a, b, k = fact[1], fact[2], fact[3]
        for other in partners(b, ("off",)):
            if other[1] == b:  # (b = n + k2)
                out.append((("le", a, other[2], k - other[3]), [fact, other]))
        for other in partners(a, ("lt", "off", "ge", "len")):
            if other[0] == "lt" and other[2] == a:  # (x < a)
                out.append((("le", other[1], b, k + 1), [other, fact]))
            elif other[0] == "off" and other[2] == a:  # (x = a + k1)
                out.append((("le", other[1], b, k - other[3]), [other, fact]))
            elif k >= 1 and other[1] == a and ((other[0] == "ge" and other[2] >= 0) or other[0] == "len"):
                out.append((("below", a, b), [fact, other]))
    elif kind in ("below", "entry"):
        out.append((("ge", fact[1], 0), [fact]))
    elif kind == "len":
        n = fact[1]
        out.append((("ge", n, 0), [fact]))
        for other in partners(n, ("le",)):
            if other[1] == n and other[3] >= 1:
                out.append((("below", n, other[2]), [other, fact]))
        for other in partners(n, ("lt", "ult")):
            if other[0] == "lt" and other[1] == n:
                out.append((("below", n, other[2]), [other, fact]))
            if other[0] == "ult" and other[2] == n:
                out.append((("below", other[1], n), [other, fact]))
    elif kind == "off":
        a, b, j = fact[1], fact[2], fact[3]
        for other in partners(a, ("le",)):
            if other[2] == a:  # (x + k <= a = b + j)
                out.append((("le", other[1], b, other[3] - j), [other, fact]))
        for other in partners(b, ("atMost",)):
            if other[1] == b:  # (b <= c, a = b + j)
                out.append((("atMost", a, other[2] + j), [fact, other]))
        for other in partners(a, ("ge",)):
            if other[1] == a:  # (a >= g, b = a - j)
                out.append((("ge", b, other[2] - j), [fact, other]))
        for other in partners(b, ("le",)):
            if other[1] == b:  # (b + k <= c, a = b + j)
                out.append((("le", a, other[2], other[3] - j), [fact, other]))
        for other in partners(b, ("ge", "off")):
            if other[0] == "ge":
                out.append((("ge", a, other[2] + j), [fact, other]))
                if j < 0 and -j <= other[2]:
                    out.append((("below", a, b), [fact, other]))
            elif other[1] == b and other != fact:
                out.append((("off", a, other[2], j + other[3]), [fact, other]))
        for other in partners(a, ("ne", "off")):
            if other[0] == "ne":
                out.append((("ne", b, other[2] - j), [fact, other]))
            elif other[2] == a and other != fact:
                out.append((("off", other[1], b, other[3] + j), [other, fact]))
    elif kind == "ne":
        a, k = fact[1], fact[2]
        for other in partners(a, ("off",)):
            if other[1] == a:
                out.append((("ne", other[2], k - other[3]), [other, fact]))
        if k == -1:
            for other in partners(a, ("found",)):
                if other[1] == a:
                    out.append((("entry", a, other[2]), [other, fact]))
    elif kind in ("lt", "ult"):
        i, n = fact[1], fact[2]
        if kind == "lt":
            for other in partners(n, ("le",)):
                if other[1] == n:  # (i < n, n + k <= b)
                    out.append((("le", i, other[2], other[3] + 1), [fact, other]))
        bounded = i if kind == "lt" else n
        for other in partners(bounded, ("ge", "len")):
            if (other[0] == "ge" and other[2] >= 0) or (other[0] == "len" and other[1] == bounded):
                out.append((("below", i, n), [fact, other]))
    elif kind == "found" and ("ne", fact[1], -1) in index:
        out.append((("entry", fact[1], fact[2]), [fact, ("ne", fact[1], -1)]))
    out.extend(sum_conclusions(fact, by_name, index))
    return out


def sum_conclusions(fact, by_name, index):
    """PystachyAccess.sumStep's conclusions that fact takes part in: x = p + q and z = r + t with
    an addend in common and the others ordered give x < z, and lower bounds of p and q one of x."""
    out = []
    kind = fact[0]

    def sums(name):
        return [other for other in by_name.get(name, ()) if other[0] == "sum"]

    def ordered(f, g):
        # (x < z from sums f of x and g of z: the lt fact it needs, or None)
        p, q, r, t = f[2], f[3], g[2], g[3]
        for shared, mine, theirs in ((p == r, q, t), (p == t, q, r), (q == r, p, t), (q == t, p, r)):
            if shared and ("lt", mine, theirs) in index:
                return ("lt", mine, theirs)
        return None

    def bounded(f):
        # (x >= k₁ + k₂ from a sum f of x and lower bounds of its addends)
        for g in by_name.get(f[2], ()):
            if g[0] == "ge" and g[1] == f[2]:
                for h in by_name.get(f[3], ()):
                    if h[0] == "ge" and h[1] == f[3]:
                        out.append((("ge", f[1], g[2] + h[2]), [f, g, h]))

    if kind == "sum":
        for name in set(fact[2:]):
            for other in sums(name):
                if other is fact or other[1] == fact[1]:
                    continue
                less = ordered(fact, other)
                if less is not None:
                    out.append((("lt", fact[1], other[1]), [fact, other, less]))
                less = ordered(other, fact)
                if less is not None:
                    out.append((("lt", other[1], fact[1]), [other, fact, less]))
        bounded(fact)
    elif kind == "lt":
        a, c = fact[1], fact[2]
        for f in sums(a):
            if a not in f[2:]:
                continue
            for g in sums(c):
                if c in g[2:] and g[1] != f[1] and ordered(f, g) == fact:
                    out.append((("lt", f[1], g[1]), [f, g, fact]))
    elif kind == "ge":
        for f in sums(fact[1]):
            if fact[1] in f[2:]:
                bounded(f)
    return out


def closure(start, new, relevant, lower_bounds=()):
    """start and what the rules derive from it, in an order Lean can check (each fact from
    start or from facts before it), with each derived fact's premises. Facts in start other
    than new were closed where they were derived; only facts about relevant values are
    derived."""
    facts = list(start)
    if not new:
        return facts, {}
    index = set(facts)
    by_name = {}
    for fact in facts:
        for part in set(mentions(fact)):
            by_name.setdefault(part, []).append(fact)
    premises = {}
    pending = deque(fact for fact in new if fact in index)
    while pending:
        fact = pending.popleft()
        for derived, needs in conclusions(fact, by_name, index, relevant, lower_bounds):
            # Rules use mathematical integers, but the checked wire format
            # accepts i64 constants. An impossible overflow-free path can
            # suggest >= INT64_MAX+1; keep representable weaker facts instead.
            if not encodable_fact(derived):
                continue
            if derived in index or (derived[0] == "eq" and derived[1] == derived[2]) or any(
                    part not in relevant for part in mentions(derived)):
                continue
            facts.append(derived)
            index.add(derived)
            premises[derived] = needs
            for part in set(mentions(derived)):
                by_name.setdefault(part, []).append(derived)
            pending.append(derived)
            if len(facts) > MAX_FACTS_AT:
                raise Unsupported("facts at one point exceed the prototype's resource bound")
    return facts, premises


def prune(facts, live):
    """The facts worth carrying forward: those about a value read later, and facts about
    values that only those facts mention (a length a bound refers to)."""
    kept = set()
    names = set()
    for fact in facts:
        parts = mention_set(fact)
        if not parts or not parts.isdisjoint(live):
            kept.add(fact)
            names |= parts
    return [fact for fact in facts if fact in kept or mention_set(fact) <= names]


def safe(facts, node):
    """Whether facts prove the node's access safe (PystachyAccess.safeFacts)."""
    if ("absurd",) in facts:
        return True
    op = node["op"]
    if op == "load":
        index = node["index"]
        if isinstance(index, str):
            return any(f[0] == "below" and f[1] == index and ("len", f[2], node["list"]) in facts for f in facts)
        return index >= 0 and any(
            f[0] == "len" and f[2] == node["list"] and any(g[0] == "ge" and g[1] == f[1] and index < g[2]
                                                         for g in facts) for f in facts)
    if op == "value":
        return ("entry", node["entry"], node["dict"]) in facts
    return True


def substituted(known, goal):
    eqs = [f for f in known if f[0] == "eq"]
    return any(rename(g, f[1], f[2]) == goal or rename(g, f[2], f[1]) == goal for f in eqs for g in known)


def sum_rule(known, goal):
    """PystachyAccess.sumStep, for diagnostics."""
    if goal[0] == "lt":
        x, z = goal[1], goal[2]
        for f in known:
            if f[0] != "sum" or f[1] != x:
                continue
            p, q = f[2], f[3]
            for g in known:
                if g[0] == "sum" and g[1] == z:
                    r, t = g[2], g[3]
                    if ((p == r and ("lt", q, t) in known) or (p == t and ("lt", q, r) in known) or
                            (q == r and ("lt", p, t) in known) or (q == t and ("lt", p, r) in known)):
                        return True
    if goal[0] == "ge":
        x, k = goal[1], goal[2]
        return any(f[0] == "sum" and f[1] == x and any(
            g[0] == "ge" and g[1] == f[2] and any(h[0] == "ge" and h[1] == f[3] and k <= g[2] + h[2] for h in known)
            for g in known) for f in known)
    return False


def rule(known, goal):
    """PystachyAccess.rule, for diagnostics: whether goal follows in one step from known."""
    if ("absurd",) in known or sum_rule(known, goal):
        return True
    kind = goal[0]
    if kind == "eq":
        return (("eq", goal[2], goal[1]) in known or any(
            f[0] == "cell" and f[4] == goal[1] and ("cell", f[1], f[2], f[3], goal[2]) in known for f in known)
            or substituted(known, goal))
    if kind == "ge":
        a, k = goal[1], goal[2]
        for f in known:
            if f[0] == "ge" and f[1] == a and k <= f[2]:
                return True
            if f[0] in ("below", "len", "entry") and f[1] == a and k <= 0:
                return True
            if f[0] == "off" and f[1] == a and any(g[0] == "ge" and g[1] == f[2] and k <= g[2] + f[3] for g in known):
                return True
            if f[0] == "off" and f[2] == a and any(g[0] == "ge" and g[1] == f[1] and k <= g[2] - f[3] for g in known):
                return True
        return substituted(known, goal)
    if kind == "atMost":
        a, k = goal[1], goal[2]
        if any(f[0] == "atMost" and f[1] == a and f[2] <= k for f in known):
            return True
        if any(f[0] == "off" and f[1] == a and any(g[0] == "atMost" and g[1] == f[2] and g[2] + f[3] <= k
                                                    for g in known) for f in known):
            return True
        return substituted(known, goal)
    if kind == "le":
        a, b, k = goal[1], goal[2], goal[3]
        for f in known:
            if f[0] == "le" and f[1] == a and ((f[2] == b and k <= f[3]) or any(
                    g[0] == "off" and g[1] == f[2] and g[2] == b and k <= f[3] - g[3] for g in known)):
                return True
            if f[0] == "lt" and f[1] == a and any(g[0] == "le" and g[1] == f[2] and g[2] == b and k <= g[3] + 1
                                                   for g in known):
                return True
            if f[0] == "off" and f[1] == a and any(g[0] == "le" and g[1] == f[2] and g[2] == b and k <= g[3] - f[3]
                                                    for g in known):
                return True
        return substituted(known, goal)
    if kind == "below":
        i, n = goal[1], goal[2]
        if ("lt", i, n) in known and nonneg(known, i):
            return True
        if any(f[0] == "le" and f[1] == i and f[2] == n and f[3] >= 1 for f in known) and nonneg(known, i):
            return True
        if any(f[0] == "atMost" and f[1] == i and any(g[0] == "ge" and g[1] == n and f[2] < g[2] for g in known)
               for f in known) and nonneg(known, i):
            return True
        if ("ult", i, n) in known and nonneg(known, n):
            return True
        if any(f[0] == "off" and f[1] == i and f[2] == n and f[3] < 0 and any(
                g[0] == "ge" and g[1] == n and -f[3] <= g[2] for g in known) for f in known):
            return True
        return substituted(known, goal)
    if kind == "off":
        a, b, k = goal[1], goal[2], goal[3]
        if any(f[0] == "off" and f[1] == a and any(g[0] == "off" and g[1] == f[2] and g[2] == b and f[3] + g[3] == k
                                                     for g in known) for f in known):
            return True
        return substituted(known, goal)
    if kind == "ne":
        b, k = goal[1], goal[2]
        if any(f[0] == "off" and f[2] == b and ("ne", f[1], k + f[3]) in known for f in known):
            return True
        if any(f[0] == "ge" and f[1] == b and k < f[2] for f in known):
            return True
        return substituted(known, goal)
    if kind == "entry":
        if ("found", goal[1], goal[2]) in known and ("ne", goal[1], -1) in known:
            return True
        return substituted(known, goal)
    return substituted(known, goal)


def explain(candidate):
    """The first obligation PystachyAccess.check would reject, as text, or None: a mirror for
    diagnostics only; Lean's verdict is the result."""
    nodes, certificate = candidate["program"]["nodes"], candidate["certificate"]
    facts_at = [[tuple(fact) for fact in facts] for facts in certificate]
    if facts_at[candidate["program"]["entry"]]:
        return "facts at entry"
    for index, node in enumerate(nodes):
        facts = facts_at[index]
        if node["op"] in ("load", "value") and not safe(facts, node):
            return f"node {index}: {node} is not proved by {facts}"
        for edge, target in enumerate(successors(node)):
            known = immediates(node, edge, facts)
            for fact in facts_at[target]:
                if fact not in known and not rule(known, fact):
                    return f"edge {index}->{target} ({node['op']}): {fact} is not justified by {known}"
                known = known + [fact]
    return None


# ---- normalization ----

def successors(node):
    op = node["op"]
    if op == "stop":
        return []
    if op in ("test", "choice"):
        return [node["yes"], node["no"]]
    if op in ("add_checked", "add_checked_reg"):
        return [node["next"], node["overflow"]]
    return [node["next"]]


def reads(node):
    op = node["op"]
    if op in ("copy", "add", "add_checked"):
        return {node["src"]}
    if op in ("add_reg", "add_checked_reg"):
        return {node["x"], node["y"]}
    if op == "length":
        return {node["list"]}
    if op in ("find", "entry"):
        return {node["dict"]}
    if op == "test":
        return {part for part in (node["cond"]["a"], node["cond"]["b"]) if isinstance(part, str)}
    if op == "load":
        return {node["list"]} | ({node["index"]} if isinstance(node["index"], str) else set())
    if op == "value":
        return {node["dict"], node["entry"]}
    if op == "read_field":
        return {node["object"]}
    if op == "write_field":
        return {node["object"], node["value"]}  # (and a cell's class and index are labels)
    return set()


def liveness(nodes, predecessors):
    live = [set() for _ in nodes]
    pending = deque(range(len(nodes) - 1, -1, -1))
    queued = [True] * len(nodes)
    while pending:
        index = pending.popleft()
        queued[index] = False
        node = nodes[index]
        later = set().union(*(live[target] for target in successors(node)))
        later.discard(node.get("dst"))
        later |= reads(node)
        if later != live[index]:
            live[index] = later
            for predecessor in predecessors[index]:
                if not queued[predecessor]:
                    queued[predecessor] = True
                    pending.append(predecessor)
    return live


def generation_premises(facts, node, fact):
    """The facts of node's predecessor that a generated fact needs: an add's proof that its
    sum fits."""
    if node["op"] == "test" and node["cond"]["cmp"] == "ult" and isinstance(node["cond"]["b"], str) and (
            fact[0] == "absurd" or (fact[0] == "ge" and fact[1] == node["cond"]["b"])):
        # (a bound from an unsigned test of a literal needs its operand nonnegative)
        b = node["cond"]["b"]
        for f in facts:
            if (f[0] == "ge" and f[1] == b and f[2] >= 0) or (f[0] == "len" and f[1] == b):
                return [f]
    if node["op"] == "add_reg" and fact[0] == "sum":
        found = no_wrap_sum_premises(facts, node["x"], node["y"]) or no_wrap_sum_premises(facts, node["y"], node["x"])
        return found or []
    if node["op"] == "add" and fact[0] == "off":
        src, k = node["src"], node["k"]
        for f in facts:
            if k <= 0 and f[0] == "ge" and f[1] == src and MIN_I64 <= f[2] + k:
                return [f]
            if 0 <= k <= 1 and f[0] in ("below", "found") and f[1] == src:
                return [f]
            if 0 <= k and f[0] == "off" and f[1] == src and f[3] + k <= 0:
                return [f]
            if 0 <= k <= MAX_I64 - MAX_LEN and f[0] == "len" and f[1] == src:
                return [f]
    return []


def infer_certificate(nodes, entry=0):
    """Facts at each node: forward must-facts closed under the model's rules, then only those
    that an access needs, directly or through the facts that justify them. A node with several
    predecessors is reached through a jump of its own from each (normalize adds them), whose
    facts it intersects."""
    # A loop starting at 1 and advancing by 2 must retain i >= 1 at its
    # join: exact-set intersection of >=1 and >=3 otherwise keeps only >=0.
    # Derive a finite set of relevant weaker bounds before joins. These are
    # certificate suggestions; Lean's existing ge rule checks every weakening.
    lower_bounds = sorted({node["value"] for node in nodes if node["op"] == "lit" and node["value"] > 0}
                          | {-node["k"] for node in nodes
                             if node["op"] in ("add", "add_checked") and node["k"] < 0})
    predecessors = [[] for _ in nodes]
    for index, node in enumerate(nodes):
        for edge, target in enumerate(successors(node)):
            predecessors[target].append((index, edge))
    live = liveness(nodes, [[q for q, _ in incoming] for incoming in predecessors])
    known = [None] * len(nodes)     # the facts carried forward
    derived = [None] * len(nodes)   # every fact at a node, in order, with how it is justified
    known[entry] = []
    derived[entry] = ([], {})
    # (in reverse postorder, so that a loop's body follows its entry before its back edge)
    order, seen, stack = [], {entry}, [(entry, iter(successors(nodes[entry])))]
    while stack:
        index, rest = stack[-1]
        target = next(rest, None)
        if target is None:
            order.append(index)
            stack.pop()
        elif target not in seen:
            seen.add(target)
            stack.append((target, iter(successors(nodes[target]))))
    rank = {index: position for position, index in enumerate(reversed(order))}
    pending = [(rank[entry], entry)]
    queued = {entry}
    visits = 0
    while pending:
        index = heapq.heappop(pending)[1]
        queued.discard(index)
        visits += 1
        if visits > 400000:
            raise Unsupported("certificate inference exceeds the prototype's resource bound")
        node = nodes[index]
        for edge, target in enumerate(successors(node)):
            if target == entry:
                continue
            start = immediates(node, edge, known[index])
            new = generated(known[index], node, edge)
            if len(predecessors[target]) > 1:
                # (a join of jumps: what every visited one knows)
                incoming = prune(start, live[target])
                if known[target] is None:
                    merged = incoming
                else:
                    arriving = set(incoming)
                    merged = [f for f in known[target] if f in arriving]
                justification = ([], {})
            else:
                relevant = (live[target] | set().union(*(set(mentions(fact)) for fact in start))) if new else live[target]
                facts, premises = closure(start, new, relevant, lower_bounds)
                merged = prune(facts, live[target])
                justification = (facts, premises)
            if merged != known[target] or derived[target] is None:
                known[target] = merged
                derived[target] = justification
                if target not in queued:
                    queued.add(target)
                    heapq.heappush(pending, (rank[target], target))
    # Which facts each node must list: those its access uses, and, backward, the facts that
    # justify each listed fact on every edge into its node.
    need = [set() for _ in nodes]
    work = deque()

    def want(index, fact):
        if fact not in need[index]:
            need[index].add(fact)
            work.append((index, fact))

    for index, node in enumerate(nodes):
        if known[index] is None:
            continue
        facts = set(known[index])
        op = node["op"]
        if op in ("load", "value") and ("absurd",) in facts:
            want(index, ("absurd",))
        elif op == "load":
            ix, l = node["index"], node["list"]
            if isinstance(ix, str):
                for f in known[index]:
                    if f[0] == "below" and f[1] == ix and ("len", f[2], l) in facts:
                        want(index, f)
                        want(index, ("len", f[2], l))
                        break
            else:
                for f in known[index]:
                    if f[0] == "len" and f[2] == l:
                        bound = next((g for g in known[index] if g[0] == "ge" and g[1] == f[1] and ix < g[2]), None)
                        if bound is not None and ix >= 0:
                            want(index, f)
                            want(index, bound)
                            break
        elif op == "value" and ("entry", node["entry"], node["dict"]) in facts:
            want(index, ("entry", node["entry"], node["dict"]))
    while work:
        index, fact = work.popleft()
        incoming = predecessors[index]
        if len(incoming) > 1:
            for pad, _ in incoming:
                want(pad, fact)
            continue
        if not incoming:
            continue
        q, edge = incoming[0]
        facts, premises = derived[index]
        pending_facts = [fact]
        seen = set()
        while pending_facts:
            f = pending_facts.pop()
            if f in seen:
                continue
            seen.add(f)
            if f in premises:
                for premise in premises[f]:
                    if premise in premises:
                        want(index, premise)
                    pending_facts.append(premise)
            elif f in known[q] and survives(nodes[q], f):
                want(q, f)
            else:
                for premise in generation_premises(known[q], nodes[q], f):
                    want(q, premise)
    certificate = []
    for index in range(len(nodes)):
        order = derived[index][0] if derived[index] is not None and derived[index][0] else (known[index] or [])
        listed = [fact for fact in order if fact in need[index]]
        listed += [fact for fact in (known[index] or []) if fact in need[index] and fact not in listed]
        certificate.append([list(fact) for fact in listed])
    if sum(len(facts) for facts in certificate) > MAX_FACTS:
        raise Unsupported("the certificate exceeds the prototype's resource bound")
    return certificate, known


def function_record(snapshot, function):
    name(function, "function selector")
    functions = snapshot.get("functions")
    require(isinstance(functions, list) and len(functions) <= 65536, "invalid functions list")
    require(all(isinstance(fn, dict) for fn in functions), "invalid function record")
    selected = [fn for fn in functions if fn.get("symbol") == function or fn.get("name") == function]
    require(len(selected) == 1, "--function must select exactly one function by exact name or symbol")
    return selected[0]


def check_dominance(blocks, block_edges, sites):
    """Every register's definition dominates its uses (a phi's operand: the end of its edge's
    predecessor): wherever a test's or a field address's result is used, the registers it read
    still hold what it read. Cooper, Harvey and Kennedy's dominators, then intervals of the tree."""
    labels = [block["label"] for block in blocks]
    successors_of = {block["label"]: block_edges(block) for block in blocks}
    order, seen, stack = [], {labels[0]}, [(labels[0], iter(successors_of[labels[0]]))]
    while stack:
        label, rest = stack[-1]
        target = next(rest, None)
        if target is None:
            order.append(label)
            stack.pop()
        elif target not in seen:
            seen.add(target)
            stack.append((target, iter(successors_of[target])))
    order.reverse()
    rank = {label: index for index, label in enumerate(order)}
    predecessors = {label: [] for label in order}
    for label in order:
        for target in successors_of[label]:
            predecessors[target].append(label)
    idom = {order[0]: order[0]}
    changed = True
    while changed:
        changed = False
        for label in order[1:]:
            ready = [p for p in predecessors[label] if p in idom]
            new = ready[0]
            for p in ready[1:]:
                a, b = p, new
                while a != b:
                    while rank[a] > rank[b]:
                        a = idom[a]
                    while rank[b] > rank[a]:
                        b = idom[b]
                new = a
            if idom.get(label) != new:
                idom[label] = new
                changed = True
    children = {label: [] for label in order}
    for label in order[1:]:
        children[idom[label]].append(label)
    enter, leave, clock, stack = {}, {}, 0, [(order[0], False)]
    while stack:
        label, done = stack.pop()
        if done:
            leave[label] = clock
            clock += 1
            continue
        enter[label] = clock
        clock += 1
        stack.append((label, True))
        stack += [(child, False) for child in children[label]]

    def dominates(a, b):
        return enter[a] <= enter[b] and leave[b] <= leave[a]

    for block in blocks:
        for offset, op in enumerate(block["operations"]):
            for position, operand in enumerate(op["operands"]):
                value = operand["value"]
                if value not in sites:
                    continue
                label, at = sites[value]
                require(label in enter, f"definition is not reachable: {value}")
                if op["op"] == "phi":
                    require(position < len(op["targets"]), "invalid phi")
                    edge = op["targets"][position]
                    require(edge not in enter or dominates(label, edge),
                            f"definition does not dominate use: {value}")
                else:
                    require(at < offset if label == block["label"] else dominates(label, block["label"]),
                            f"definition does not dominate use: {value}")


def normalize_snapshot(snapshot, function, effects_of=None):
    """The access-model program of one function, with an inferred certificate, and its counts."""
    return certify(*normalize_program(snapshot, function, effects_of))


def certify(nodes, metadata):
    """The candidate of normalized nodes: the program and an inferred certificate."""
    certificate, _ = infer_certificate(nodes)
    unproved = [index for index, node in enumerate(nodes)
                if node["op"] in ("load", "value") and not safe([tuple(f) for f in certificate[index]], node)]
    return ({"schema_version": 1, "program": {"entry": 0, "nodes": nodes}, "certificate": certificate},
            dict(metadata, unproved=len(unproved)))


def normalize_program(snapshot, function, effects_of=None):
    """The access-model nodes of one function, entry first, and its counts."""
    check_header(snapshot)
    fn = function_record(snapshot, function)
    symbol = name(fn.get("symbol"), "function symbol")
    if effects_of is None:
        effects_of = summaries(snapshot)
    require(isinstance(fn.get("recursion"), dict), "invalid recursion record")
    targets_of_checks = fn.get("check_targets", {})
    require(isinstance(targets_of_checks, dict), "invalid check targets")
    blocks = fn.get("blocks")
    require(isinstance(blocks, list) and blocks, "invalid blocks")
    slots = {}
    require(isinstance(fn.get("slots"), list), "invalid slots")
    for raw in fn["slots"]:
        op = instruction(raw, slot=True)
        number = op["results"][0]
        if op["immediate"] == 2:
            continue  # (a stack tuple's register is a tuple value, not storage)
        slot = (f"%{op['text']}.def.{number}" if op["immediate"] == 1
                else f"%{op['text'] or 'h'}.{number}")
        require(slot not in slots, "duplicate slot")
        slots[slot] = op["type"]
    labels = set()
    total = 0
    definitions = {}
    sites = {}
    for block in blocks:
        require(isinstance(block, dict) and set(block) == {"label", "handler", "operations"},
                "invalid block fields")
        require(isinstance(block["label"], str) and isinstance(block["handler"], str), "invalid block")
        require(block["label"] == "" or block["label"] not in labels, "duplicate block label")
        labels.add(block["label"])
        operations = block["operations"]
        require(isinstance(operations, list) and operations, "empty or invalid block")
        total += len(operations)
        if total > MAX_INSTRUCTIONS:
            raise Unsupported(f"function exceeds {MAX_INSTRUCTIONS} instructions")
        for offset, raw in enumerate(operations):
            op = instruction(raw)
            invoke = op["op"] in INVOKES and len(op["targets"]) == 2
            require((op["op"] in TERMINATORS or invoke or op["op"] in ("gen.yield", "gen.ret", "gen.start"))
                    == (offset == len(operations) - 1), "each block must end with its only terminator")
            for number in op["results"]:
                require(f"%t{number}" not in definitions, "duplicate result identifier")
                definitions[f"%t{number}"] = op
                sites[f"%t{number}"] = (block["label"], offset)
    blocks = [dict(block, handler="") if block["handler"] not in labels else block for block in blocks]
    by_label = {block["label"]: block for block in blocks}
    entry_label = blocks[0]["label"]
    require(entry_label != "", "the entry block needs a label")

    def block_edges(block):
        last = block["operations"][-1]
        out = list(last["targets"]) if last["op"] != "phi" else []
        if last["op"] == "check":
            key = last["descriptor"] or last["text"]
            if key not in targets_of_checks or targets_of_checks[key] not in labels:
                raise Unsupported("a check's error block is not in the snapshot")
            out.append(targets_of_checks[key])
        if block["handler"]:
            out.append(block["handler"])
        for target in out:
            require(target in labels and target != "", "unknown branch target")
        return out

    reached, pending = {entry_label}, [entry_label]
    while pending:
        for target in block_edges(by_label[pending.pop()]):
            if target not in reached:
                reached.add(target)
                pending.append(target)
    live_blocks = [block for block in blocks if block["label"] in reached]
    check_dominance(live_blocks, block_edges, sites)
    into = {}   # (each reached block's predecessors, once per edge)
    for block in live_blocks:
        for target in block_edges(block):
            into.setdefault(target, []).append(block["label"])

    # A slot is private when its address reaches only loads and stores of it.
    escaped = set()
    for block in live_blocks:
        for op in block["operations"]:
            for position, operand in enumerate(op["operands"]):
                if operand["value"] in slots and not (
                        position == 0 and op["op"] in ("mem.load", "mem.store", "mach.load", "mach.store", "landing")):
                    escaped.add(operand["value"])
    private = set(slots) - escaped
    # Each field address: the object register and the field's label (its class and index). A
    # field.addr's operands are SSA values, unchanged wherever its result is used.
    field_of = {f"%t{op['results'][0]}": (op["operands"][0]["value"], op["operands"][0]["type"], op["immediate"])
                for op in definitions.values() if op["op"] == "field.addr" and op["results"]
                and len(op["operands"]) == 1 and op["operands"][0]["value"].startswith("%")}
    # An env is an array of pointers to closure cells. Recognize only constant
    # pointer-slot loads from a value whose definition/parameter has env type.
    # The captured cell itself is mutable: reuse read_field's heap invalidation,
    # never private-slot persistence. Do not infer a cell from an arbitrary ptr.
    environments = {f"%t{number}" for op in definitions.values() if op["type"] == "env"
                    for number in op["results"]}
    environments.update(f"%a{index}" for index, parameter in enumerate(fn.get("parameters", []))
                        if parameter.get("representation") == "env")
    environment_slots = {f"%t{op['results'][0]}" for op in definitions.values()
                         if op["op"] == "mach.addr" and op["text"] == "%ptr"
                         and len(op["results"]) == 1 and len(op["operands"]) == 2
                         and op["operands"][0]["value"] in environments
                         and isinstance(operand_of(op["operands"][1]["value"]), int)
                         and operand_of(op["operands"][1]["value"]) >= 0}
    closure_cells = {f"%t{op['results'][0]}" for op in definitions.values()
                     if op["op"] == "mach.load" and op["type"] == "%ptr" and op["text"] == ""
                     and len(op["results"]) == 1 and len(op["operands"]) == 1
                     and op["operands"][0]["value"] in environment_slots}
    # A module global that the function only loads and stores directly holds the value last
    # stored there, until an operation that may write globals runs.
    # (A class variable is such a global, which machine loads and stores of the whole word at
    # its address read and write, as the compiler's effects (rG, wG) treat them.)
    def direct(op):
        return op["op"] in ("mem.load", "mem.store") or (
            op["op"] in ("mach.load", "mach.store") and op["text"] == ""
            and len(op["operands"]) == (1 if op["op"] == "mach.load" else 2))

    addressed, other_uses = set(), set()
    for block in live_blocks:
        for op in block["operations"]:
            for position, operand in enumerate(op["operands"]):
                if operand["value"].startswith("@"):
                    if position == 0 and direct(op):
                        addressed.add(operand["value"])
                    else:
                        other_uses.add(operand["value"])
    tracked_globals = addressed - other_uses
    # The registers the IR types as native lists somewhere: a list's address is its List.
    list_registers = {operand["value"] for block in live_blocks for op in block["operations"]
             for operand in op["operands"] if operand["type"].startswith("list[")
             and operand["value"].startswith("%t")}

    # The comparison that defines each boolean, as a model condition and the polarity of its
    # result: SSA operands are unchanged wherever the result is used.
    def comparison(value):
        op = definitions.get(value)
        if op is None or len(op["operands"]) != 2:
            return None
        if op["op"] == "scalar.bin" and op["text"] == "xor" and op["operands"][1]["value"] == "true":
            inner = comparison(op["operands"][0]["value"])
            return None if inner is None else (inner[0], not inner[1])
        a, b = (operand_of(operand["value"]) for operand in op["operands"])
        if a is None or b is None:
            return None
        text = op["text"]
        if op["op"] == "num.cmp" and op["operands"][0]["type"] == "int" or (
                op["op"] == "scalar.cmp" and op["operands"][0]["type"] == "int"):
            table = {"<": ("slt", a, b, True), "<=": ("sle", a, b, True), ">": ("slt", b, a, True),
                     ">=": ("sle", b, a, True), "==": ("eq", a, b, True), "!=": ("eq", a, b, False),
                     "slt": ("slt", a, b, True), "sle": ("sle", a, b, True), "sgt": ("slt", b, a, True),
                     "sge": ("sle", b, a, True), "eq": ("eq", a, b, True), "ne": ("eq", a, b, False),
                     "ult": ("ult", a, b, True), "ugt": ("ult", b, a, True)}
        elif op["op"] == "int.ucmp":
            table = {"<": ("ult", a, b, True), ">": ("ult", b, a, True)}
        elif op["op"] == "ptr.cmp":
            table = {"==": ("eq", a, b, True), "!=": ("eq", a, b, False)}
        else:
            return None
        if text not in table:
            return None
        kind, x, y, polarity = table[text]
        return {"cmp": kind, "a": x, "b": y}, polarity

    # An overflow flag that only its block's terminator tests splits the path at its ovf.
    flag_uses = {}
    for block in live_blocks:
        for position, op in enumerate(block["operations"]):
            for operand in op["operands"]:
                flag_uses.setdefault(operand["value"], []).append((block["label"], position, op))

    nodes = []
    starts = {}
    accesses = {"list.load": 0}

    def emit(node):
        nodes.append(node)
        if len(nodes) > MAX_NODES:
            raise Unsupported("the normalized function exceeds the prototype's node bound")
        return len(nodes) - 1

    def ref(label):
        return ("block", label)

    def kill_nodes(lists, dicts, globals_=False, fields_=False):
        return (([{"op": "lists"}] if lists else []) + ([{"op": "dicts"}] if dicts else []) +
                ([{"op": "havoc", "dst": name_} for name_ in sorted(tracked_globals)] if globals_ else []) +
                ([{"op": "heap"}] if fields_ else []))

    def havocs(op):
        return [{"op": "havoc", "dst": f"%t{number}"} for number in op["results"]]

    def store(address, value):
        # (a private slot gets the stored value: a register's, a literal or an unknown one)
        source = operand_of(value)
        if isinstance(source, str) and (source in definitions or source in private or not source.startswith("%t")):
            return [{"op": "copy", "dst": address, "src": source}]
        if isinstance(source, int):
            return [{"op": "lit", "dst": address, "value": source}]
        return [{"op": "havoc", "dst": address}]

    def effects(op):
        """What one non-terminating operation does before it may raise (the lengths and entries
        it may change), and then what it defines: two lists of nodes."""
        kind, operands = op["op"], op["operands"]
        values = [operand["value"] for operand in operands]
        if kind in ("mem.load", "mach.load") and values and (
                values[0] in private or (direct(op) and values[0] in tracked_globals)) and op["results"]:
            return [], [{"op": "copy", "dst": f"%t{op['results'][0]}", "src": values[0]}]
        if kind in ("mem.store", "mach.store") and len(values) == 2 and (
                values[0] in private or (direct(op) and values[0] in tracked_globals)):
            return [], store(values[0], values[1])
        if kind == "mem.load" and values and values[0] in field_of and op["results"]:
            obj, cls, index = field_of[values[0]]
            return [], [{"op": "read_field", "dst": f"%t{op['results'][0]}", "object": obj, "class": cls,
                         "index": index}]
        if (kind == "mem.load" and len(values) == 1 and values[0] in closure_cells and op["results"]
                and op["type"].startswith(("list[", "dict[", "set["))):
            return [], [{"op": "read_field", "dst": f"%t{op['results'][0]}", "object": values[0],
                         "class": "<closure-cell>", "index": 0}]
        if kind == "mem.store" and len(values) == 2 and values[0] in field_of:
            # (a field's new value: a register's, else a literal or an unknown value held by a
            # name of the store's own, its address and "=", which no register's name contains)
            obj, cls, index = field_of[values[0]]
            source = operand_of(values[1])
            if isinstance(source, str) and source.startswith("%"):
                return [], [{"op": "write_field", "object": obj, "class": cls, "index": index, "value": source}]
            stored = values[0] + "="
            held = ({"op": "lit", "dst": stored, "value": source} if isinstance(source, int)
                    else {"op": "havoc", "dst": stored})
            return [], [held, {"op": "write_field", "object": obj, "class": cls, "index": index, "value": stored}]
        if kind == "mem.store":
            # A named global is distinct from the other named globals; an
            # unknown address may alias a tracked global as well as the heap.
            heap = not values[0].startswith("@")
            return kill_nodes(heap, heap, heap, heap), []
        if kind == "mach.store":
            return kill_nodes(True, True, True, True), []
        if (kind == "mach.load" and op["type"] == "int" and op["text"] in ("", "length") and values
                and values[0] in list_registers and op["results"]):
            # (a List is {len, cap, a}: a word load at a list's address reads its length)
            return [], [{"op": "length", "dst": f"%t{op['results'][0]}", "list": values[0]}]
        if kind == "list.len" and len(values) == 1 and isinstance(operand_of(values[0]), str):
            return [], [{"op": "length", "dst": f"%t{op['results'][0]}", "list": values[0]}]
        if kind == "list.load":
            accesses["list.load"] += 1
            index = operand_of(values[1])
            if not isinstance(operand_of(values[0]), str) or index is None:
                raise Unsupported("a list read of an unknown list or index")
            return [], [{"op": "load", "list": values[0], "index": index}] + havocs(op)
        if kind == "list.store":
            # (listguard's unchecked item assignment: the read's obligation, the index within the
            # length; the model tracks lengths, not items, and a store changes none)
            accesses["list.store"] = accesses.get("list.store", 0) + 1
            index = operand_of(values[1])
            if not isinstance(operand_of(values[0]), str) or index is None:
                raise Unsupported("a list store to an unknown list or index")
            return [], [{"op": "load", "list": values[0], "index": index}]
        if kind == "scalar.bin" and op["text"] in ("add", "sub") and len(values) == 2 and op["type"] == "int":
            a, b = operand_of(values[0]), operand_of(values[1])
            if isinstance(a, str) and isinstance(b, int):
                k = b if op["text"] == "add" else -b
                if MIN_I64 <= k <= MAX_I64:
                    return [], [{"op": "add", "dst": f"%t{op['results'][0]}", "src": a, "k": k}]
            if isinstance(b, str) and isinstance(a, int) and op["text"] == "add":
                return [], [{"op": "add", "dst": f"%t{op['results'][0]}", "src": b, "k": a}]
            if isinstance(a, str) and isinstance(b, str) and op["text"] == "add":
                # (a sum of two values, such as listguard's base plus a loop's index)
                return [], [{"op": "add_reg", "dst": f"%t{op['results'][0]}", "x": a, "y": b}]
            return [], havocs(op)
        if kind == "rt":
            key = op["text"]
            access_before = []
            if key in ACCESS_RT:
                accesses[key] = accesses.get(key, 0) + 1
                if key in SOURCE_ENTRY_RT:
                    if (len(values) < 3 or not isinstance(operand_of(values[1]), str)
                            or not isinstance(operand_of(values[2]), str)):
                        raise Unsupported("an equality lookup of an unknown source table or entry")
                    # The runtime snapshots the source key/hash before target lookup can run
                    # user code. Check that access before invalidating facts for the callback.
                    access_before = [{"op": "value", "dict": values[1], "entry": values[2]}]
                elif key == "dict.val_or_zero":
                    if (len(values) < 2 or not isinstance(operand_of(values[0]), str)
                            or operand_of(values[1]) is None):
                        raise Unsupported("an optional entry access of an unknown table or entry")
                    return [], [{"op": "optional_value", "dict": values[0],
                                 "entry": operand_of(values[1])}] + havocs(op)
                else:
                    if (len(values) < 2 or not isinstance(operand_of(values[0]), str)
                            or not isinstance(operand_of(values[1]), str)):
                        raise Unsupported("an entry access of an unknown table or entry")
                    after = kill_nodes(False, True) if key in ("dict.entry_del", "set.slot_del") else []
                    return [], [{"op": "value", "dict": values[0], "entry": values[1]}] + after + havocs(op)
            effects_now = runtime_effects(key, op["descriptor"])
            lists, dicts, globals_, fields_ = kills(effects_now)
            if (key in FRESH_LIST_WRITES or key in ITEM_WRITES) and effects_now is not None:
                lists = "U" in effects_now
            before = access_before + kill_nodes(lists, dicts, globals_, fields_)
            if key in FINDS and op["results"] and isinstance(operand_of(values[0]), str):
                return before, [{"op": "find", "dst": f"%t{op['results'][0]}", "dict": values[0]}]
            if key in ENTRIES and op["results"] and isinstance(operand_of(values[0]), str):
                return before, [{"op": "entry", "dst": f"%t{op['results'][0]}", "dict": values[0]}]
            return before, havocs(op)
        if kind == "call":
            return kill_nodes(*kills(effects_of.get(op["text"]))), havocs(op)
        if kind in ("icall", "init", "gen.resume", "gen.drop"):
            return kill_nodes(True, True, True, True), havocs(op)
        if kind == "tuple.store":
            return kill_nodes(True, True, False, True), havocs(op)
        if kind == "empty.kind":
            return kill_nodes(False, True), havocs(op)
        return [], havocs(op)

    def unpack_test(op):
        # unpack_check(n, k) returns where n == k, unpack_ex_check(n, k) where n >= k; each
        # raises ValueError otherwise
        if len(op["operands"]) != 2:
            return None
        n, k = (operand_of(operand["value"]) for operand in op["operands"])
        if not isinstance(n, str) or not isinstance(k, int):
            return None
        if op["text"] == "unpack_check":
            return {"cmp": "eq", "a": n, "b": k}
        return {"cmp": "sle", "a": k, "b": n}

    def phi_lookup(op, label):
        # A phi of -1 and of lookups' results (-1 or a live entry) of one dict is -1 or an entry
        # live now, as a lookup of that dict at the phi may return, where nothing runs between
        # each lookup and the phi: the lookup is its block's last operation before a jump here,
        # or an invoke whose normal edge is a block, reached only from it, of only that jump.
        # The dict, or None.
        if (len(op["results"]) != 1 or op["type"] not in ("int", "%slot") or not op["operands"]
                or len(op["operands"]) != len(op["targets"])):
            return None
        table = None
        for operand, source in zip(op["operands"], op["targets"]):
            value = operand_of(operand["value"])
            if value == -1:
                continue
            if not isinstance(value, str) or value not in definitions:
                return None
            lookup, (site, offset) = definitions[value], sites[value]
            if lookup["op"] != "rt" or lookup["text"] not in FINDS or f"%t{lookup['results'][0]}" != value:
                return None
            operations = by_label[site]["operations"]
            if site == source:
                direct = (offset == len(operations) - 2 and operations[-1]["op"] == "br"
                          and operations[-1]["targets"] == [label])
            else:
                forward = by_label.get(source, {}).get("operations", [])
                direct = (offset == len(operations) - 1 and lookup["targets"][:1] == [source]
                          and len(forward) == 1 and forward[0]["op"] == "br" and forward[0]["targets"] == [label]
                          and into.get(source) == [site])
            if not direct:
                return None
            looked = operand_of(lookup["operands"][0]["value"]) if lookup["operands"] else None
            if not isinstance(looked, str) or table not in (None, looked):
                return None
            table = looked
        return table

    def sequence(block, start, known):
        """Emit block's operations from start, with the overflow flags known on this path; the
        index of the first node."""
        operations = block["operations"]
        handler = block["handler"]
        head = None
        dangling = []

        def put(node, continues=("next",)):
            nonlocal head, dangling
            index = emit(node)
            if head is None:
                head = index
            for previous, field in dangling:
                nodes[previous][field] = index
            dangling = [(index, field) for field in continues]
            return index

        def run(chain):
            for node in chain:
                if node["op"] != "optional_value":
                    put(dict(node, next=None))
                    continue
                # dict.val_or_zero does not touch storage for any negative entry. Its
                # nonnegative path has the ordinary live-entry obligation. This marker is
                # expanded here; it adds no node or contract to the Lean model.
                entry = node["entry"]
                if isinstance(entry, int):
                    if entry >= 0:
                        held = f"%access.{len(nodes)}="  # (IR register names contain no '=')
                        put({"op": "lit", "dst": held, "value": entry, "next": None})
                        put({"op": "value", "dict": node["dict"], "entry": held, "next": None})
                    continue
                branch = put({"op": "test", "cond": {"cmp": "slt", "a": entry, "b": 0},
                              "yes": None, "no": None}, ())
                read = put({"op": "value", "dict": node["dict"], "entry": entry, "next": None})
                join = put({"op": "jump", "next": None})
                nodes[branch]["yes"] = join
                nodes[branch]["no"] = read

        def raising_point():
            # (from any point of a block a try statement covers, after an operation's effects,
            # its landing block)
            if handler:
                put({"op": "choice", "yes": None, "no": ref(handler)}, ("yes",))

        for position in range(start, len(operations)):
            op = operations[position]
            last = position == len(operations) - 1
            kind, values = op["op"], [operand["value"] for operand in op["operands"]]
            if kind == "phi":
                looked = phi_lookup(op, block["label"])
                if looked is not None:
                    run([{"op": "find", "dst": f"%t{op['results'][0]}", "dict": looked}])
                else:
                    run(havocs(op))
                continue
            if not last and kind == "ovf":
                flag = f"%t{op['results'][2]}" if len(op["results"]) == 3 else ""
                a, b = (operand_of(value) for value in values) if len(values) == 2 else (None, None)
                uses = flag_uses.get(flag, [])
                terminator = operations[-1]
                only_terminator = all(use[0] == block["label"] and use[1] == len(operations) - 1 for use in uses)
                k = (b if op["text"] == "+" else -b) if isinstance(b, int) and op["text"] in ("+", "-") else None
                raising_point()
                if (flag and only_terminator and isinstance(a, str) and k is not None and op["type"] == "int"
                        and terminator["op"] in ("check", "cbr") and len(known) < 4 and MIN_I64 <= k <= MAX_I64):
                    # (the flag's test is decided on each path: the sum fits, or it overflows)
                    run(havocs({"results": [op["results"][0], op["results"][2]]}))
                    index = put({"op": "add_checked", "dst": f"%t{op['results'][1]}", "src": a, "k": k,
                                 "next": None, "overflow": None}, ())
                    nodes[index]["next"] = sequence(block, position + 1, {**known, flag: False})
                    nodes[index]["overflow"] = sequence(block, position + 1, {**known, flag: True})
                    return head
                if (flag and only_terminator and isinstance(a, str) and isinstance(b, str) and op["text"] == "+"
                        and op["type"] == "int" and terminator["op"] in ("check", "cbr") and len(known) < 4):
                    # (a checked sum of two values, as listguard's stop plus a base before a loop)
                    run(havocs({"results": [op["results"][0], op["results"][2]]}))
                    index = put({"op": "add_checked_reg", "dst": f"%t{op['results'][1]}", "x": a, "y": b,
                                 "next": None, "overflow": None}, ())
                    nodes[index]["next"] = sequence(block, position + 1, {**known, flag: False})
                    nodes[index]["overflow"] = sequence(block, position + 1, {**known, flag: True})
                    return head
                run(havocs(op))
                continue
            if not last:
                before, after = effects(op)
                run(before)
                raising_point()
                if kind == "rt" and op["text"] in ("unpack_check", "unpack_ex_check"):
                    cond = unpack_test(op)
                    if cond is not None:
                        put({"op": "test", "cond": cond, "yes": None, "no": emit({"op": "stop"})}, ("yes",))
                run(after)
                continue
            # the terminator
            targets = op["targets"]
            if kind in INVOKES and len(targets) == 2:
                before, after = effects(op)
                run(before)
                raising_point()
                cond = unpack_test(op) if kind == "rt" and op["text"] in ("unpack_check", "unpack_ex_check") else None
                if cond is not None:
                    # (an unpacking check in a try statement: its normal edge where the length matches)
                    put({"op": "test", "cond": cond, "yes": None, "no": ref(targets[1])}, ("yes",))
                else:
                    put({"op": "choice", "yes": None, "no": ref(targets[1])}, ("yes",))
                run(after)
                put({"op": "jump", "next": ref(targets[0])}, ())
            elif kind == "br":
                put({"op": "jump", "next": ref(targets[0])}, ())
            elif kind in ("cbr", "check"):
                if kind == "cbr":
                    yes, no = targets[0], targets[1]
                else:
                    # (a check raises where its flag is true)
                    yes, no = targets_of_checks[op["descriptor"] or op["text"]], targets[0]
                flag = values[0]
                if flag in known or flag in ("true", "false"):
                    outcome = known[flag] if flag in known else flag == "true"
                    put({"op": "jump", "next": ref(yes if outcome else no)}, ())
                else:
                    tested = comparison(flag)
                    if tested is None:
                        put({"op": "choice", "yes": ref(yes), "no": ref(no)}, ())
                    else:
                        cond, polarity = tested
                        put({"op": "test", "cond": cond, "yes": ref(yes if polarity else no),
                             "no": ref(no if polarity else yes)}, ())
            elif kind == "switch":
                for target in targets[:-1]:
                    put({"op": "choice", "yes": ref(target), "no": None}, ("no",))
                put({"op": "jump", "next": ref(targets[-1])}, ())
            elif kind == "landing":
                if values and values[0] in private:
                    run([{"op": "havoc", "dst": values[0]}])
                put({"op": "jump", "next": ref(targets[0])}, ())
            elif kind in ("gen.start", "gen.yield") and len(targets) == 1:
                # (while a generator is suspended its caller runs: any list, dict, field or global
                # may change, but not the generator's own slots; a throw() or close() raises here)
                run(kill_nodes(True, True, True, True))
                raising_point()
                run(havocs(op))
                put({"op": "jump", "next": ref(targets[0])}, ())
            elif kind == "gen.ret":
                put({"op": "stop"}, ())
            elif kind in ("raise", "throw") and targets:
                put({"op": "jump", "next": ref(targets[0])}, ())
            elif kind in ("ret", "ret.none", "raise", "throw", "unreachable"):
                put({"op": "stop"}, ())
            else:
                raise Unsupported(f"unsupported terminator: {kind}")
        require(not dangling, "a block's last node has no successor")
        return head

    for block in live_blocks:
        starts[block["label"]] = sequence(block, 0, {})

    def resolve(target):
        if isinstance(target, tuple):
            return starts[target[1]]
        return target

    for node in nodes:
        for field in ("next", "yes", "no", "overflow"):
            if field in node:
                require(node[field] is not None, "an unresolved successor")
                node[field] = resolve(node[field])
    # The program's entry is the entry block's first node; a join gets a jump from each predecessor.
    predecessors = [[] for _ in nodes]
    for index, node in enumerate(nodes):
        for field in ("next", "yes", "no", "overflow"):
            if field in node:
                predecessors[node[field]].append((index, field))
    for target, incoming in enumerate(predecessors):
        if len(incoming) > 1:
            for index, field in incoming:
                nodes[index][field] = emit({"op": "jump", "next": target})
    entry = starts[entry_label]
    candidate_nodes = relocate(nodes, entry)
    metadata = {"function": symbol, "nodes": len(candidate_nodes),
                "accesses": sum(node["op"] in ("load", "value") for node in candidate_nodes),
                "list_loads": accesses["list.load"], "list_stores": accesses.get("list.store", 0),
                "dict_entries": sum(count for key, count in accesses.items()
                                    if key not in ("list.load", "list.store"))}
    return candidate_nodes, metadata


def relocate(nodes, entry):
    """The nodes that entry reaches, renumbered from 0 in reaching order."""
    order, seen, pending = [], {entry}, [entry]
    while pending:
        index = pending.pop()
        order.append(index)
        for target in reversed(successors(nodes[index])):
            if target not in seen:
                seen.add(target)
                pending.append(target)
    mapping = {old: new for new, old in enumerate(order)}
    out = []
    for old in order:
        node = dict(nodes[old])
        for field in ("next", "yes", "no", "overflow"):
            if field in node:
                node[field] = mapping[node[field]]
        out.append(node)
    return out


def encode(candidate):
    encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":")) + "\n"
    require(len(encoded.encode()) <= MAX_CANDIDATE_BYTES, "normalized candidate exceeds the checker input bound")
    return encoded


def run_checker(checker, encoded, metadata, timeout=60):
    """Whether the Lean checker accepts every obligation of one encoded candidate."""
    completed = subprocess.run([str(Path(checker).resolve())], input=encoded, capture_output=True,
                               text=True, timeout=timeout)
    result = json.loads(completed.stdout, object_pairs_hook=unique_object)
    require(isinstance(result, dict) and type(result.get("accepted")) is bool,
            "checker did not return an acceptance result")
    require(result.get("nodes") == metadata["nodes"] and result.get("accesses") == metadata["accesses"],
            "checker counts disagree with normalized input")
    accepted = result["accepted"]
    require(completed.returncode == (0 if accepted else 1), "checker result/exit status mismatch")
    return accepted


def access_functions(snapshot):
    """(symbol, unchecked accesses) for each function of the snapshot that has any."""
    functions = snapshot.get("functions") if isinstance(snapshot, dict) else None
    require(isinstance(functions, list) and len(functions) <= 65536, "invalid functions list")
    found = []
    for fn in functions:
        require(isinstance(fn, dict) and isinstance(fn.get("blocks"), list)
                and all(isinstance(block, dict) and isinstance(block.get("operations"), list)
                        for block in fn["blocks"]), "invalid function record")
        count = sum(isinstance(op, dict) and (op.get("op") in ("list.load", "list.store") or (
            op.get("op") == "rt" and op.get("text") in ACCESS_RT))
                    for block in fn["blocks"] for op in block["operations"])
        if count:
            found.append((name(fn.get("symbol"), "function symbol"), count))
    require(len({symbol for symbol, _ in found}) == len(found), "duplicate function symbol")
    return found


def check_all(snapshot, checker=DEFAULT_CHECKER, verdicts=None):
    """Check every function of the snapshot with an unchecked access. The report's fields and
    the exit code of the worst result. verdicts, a dict, keeps each checked result by its
    normalized nodes and checker, so that another snapshot's identical function (a library's,
    in a corpus) reuses it: inference and Lean see only those nodes."""
    check_header(snapshot)
    effects_of = summaries(snapshot)
    records = []
    for symbol, count in access_functions(snapshot):
        record = {"function": symbol, "accesses": count}
        try:
            nodes, metadata = normalize_program(snapshot, symbol, effects_of)
            key = cached = None
            if verdicts is not None:
                key = (str(Path(checker).resolve()), hashlib.sha256(
                    json.dumps(nodes, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
                cached = verdicts.get(key)
            if cached is not None:
                record.update(cached)
            else:
                candidate, metadata = certify(nodes, metadata)
                encoded = encode(candidate)
                record.update(nodes=metadata["nodes"], unproved=metadata["unproved"],
                              candidate_sha256=hashlib.sha256(encoded.encode()).hexdigest())
                record["status"] = "accepted" if run_checker(checker, encoded, metadata) else "rejected"
                if record["status"] == "rejected":
                    record["message"] = (explain(candidate) or "")[:1000]
                if key is not None:
                    verdicts[key] = {field: record[field] for field in
                                     ("nodes", "unproved", "candidate_sha256", "status", "message") if field in record}
        except Unsupported as error:
            record.update(status="unsupported", message=str(error))
        except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as error:
            record.update(status="error", message=str(error))
        records.append(record)
    worst = max((record["status"] for record in records), key=SEVERITY.index, default="accepted")
    counts = {status: sum(record["status"] == status for record in records) for status in SEVERITY}
    totals = {"functions": len(snapshot["functions"]), "access_functions": len(records),
              "accesses": sum(record["accesses"] for record in records),
              "proved_accesses": sum(record["accesses"] for record in records if record["status"] == "accepted"),
              **counts}
    return {"status": worst, "checked": counts["unsupported"] + counts["error"] == 0,
            "functions": records, "totals": totals,
            "scope": "list.load bounds and inventoried dict/set entry accesses in every normalized function of one snapshot",
            "limitations": LIMITATIONS}, OUTCOMES[worst]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--function", help="exact function name or LLVM symbol")
    selection.add_argument("--all", action="store_true",
                           help="every function with an unchecked access; exit with the worst result")
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    parser.add_argument("--emit", type=Path, help="write a new candidate JSON file without checking it")
    args = parser.parse_args(argv)
    if args.all and args.emit:
        parser.error("--emit writes one function's candidate: select it with --function")
    report = {"checked": False}
    try:
        snapshot, digest = read_snapshot(args.snapshot, MAX_PROGRAM_BYTES)
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
