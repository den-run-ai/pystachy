#!/usr/bin/env python3
"""Check live numeric-list identity stores, copies and tracing edges with Lean.

The contract covers an initialized companion, successful in-bounds stores and
successful reserve/slice copies. Materialization, allocation-time liveness,
callbacks and the concrete allocator/collector remain outside the proof. The
bounded adapters fail closed on unknown shapes and are part of the trusted base:
clang's AST of the functions that runtime.c defines, and Python's of the list
constructor, growth and slice copy, which runtime.py defines.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import check_lean_alias as alias
from src.pystachy_compiler.specs import RTRECORDS

ROOT = alias.ROOT
CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-companion"

# Clang parses these bounded contracts in the actual translation unit. Comparing
# normalized ASTs rather than C text retains macro expansion, casts, store order,
# conditions and every statement. Allocator names are extracted separately. The
# list kind's 3/11 masks do not change an address or scanned extent; materializing
# a correct numeric value is deliberately not claimed by the tracing theorem.
CONTRACTS = r"""
static void companion_contract_list_identity_slow(List *l, I kind) {
  opt_in();
  if (big_list(l) && (kind & 3) == 1) {
    if (!l->cap) { l->ids = empty_identity_int; return; }
    for (I i = 0; i < l->len; i++) {
      Mpz *m = l->a[i] == INT64_MIN ? (Mpz *)l->ids[i + 1] : NULL;
      l->ids[i + 1] = (I)pys_dyn_big(m ? 0 : l->a[i], m);
    }
    l->ids[0] = 1;
    return;
  }
  if (!l->ids) {
    if (l->cap > INT64_MAX / (I)sizeof(I) - 1) oom();
    I *ids = pys_alloc((l->cap + 1) * sizeof(I));
    ids[0] = kind & 3; l->ids = ids;
  }
  for (I i = 0; i < l->len; i++)
    if (!l->ids[i + 1]) l->ids[i + 1] = list_box(l->a[i], l->ids[0]);
  l->ids[0] &= 3;
}
static void companion_contract_pys_list_set_identity(List *l, I i, I v, Dyn *id, I kind) {
  i = idx(i, l->len, "IndexError: list assignment index out of range");
  pys_list_identity(l, kind); l->ids[i + 1] = (I)id; ((Slot *)l->a)[i].v = v;
}
static Dyn *companion_contract_pys_list_get_identity(List *l, I i, I kind) {
  i = idx(i, l->len, "IndexError: list index out of range");
  pys_list_identity(l, kind); return (Dyn *)l->ids[i + 1];
}
static int companion_contract_big_list(List *l) {
  return l->ids && (l->ids[0] & 3) == BIGIDS && opt_in();
}
static void companion_contract_pys_list_identity(List *l, I kind) {
  if (!l->ids || (l->ids[0] & 4) || ((kind & 3) == 1 && big_list(l))) list_identity_slow(l, kind);
}
"""
FUNCTIONS = ("list_identity_slow", "pys_list_set_identity", "pys_list_get_identity",
             "big_list", "pys_list_identity")

# runtime.py defines the constructor, growth and the slice copy. Python parses these bounded
# contracts as it parses runtime.py, and the trees must be equal: every statement, call,
# operand and field name. A field is a literal that the compiler resolves in RTRECORDS, whose
# List record must be the header that clang lays out (tools/check_runtime.py compares the
# two as well). Comments are no part of a tree.
PY_CONTRACTS = '''
@_rt.unchecked
def pys_list_make(cap: int, atomic: int) -> _rt.Ptr:
    if atomic == 0 and cap <= 4:
        l = pys_alloc(_rt.sizeof("List") + 32)
        _rt.set(l, "List.cap", 4)
        _rt.setp(l, "List.a", list_inline(l))
        return l
    l = pys_alloc(_rt.sizeof("List") - 1)
    c = cap if cap > 4 else 4
    _rt.set(l, "List.cap", c)
    _rt.setp(l, "List.a", item_array(c, atomic))
    return l


@_rt.unchecked
def pys_list_reserve(l: _rt.Ptr, n: int) -> None:
    if n <= _rt.get(l, "List.cap"):
        return
    c = _rt.get(l, "List.cap") * 2 if _rt.get(l, "List.cap") * 2 > n else n
    if c < 4:
        c = 4
    a = _rt.nil()
    if _rt.getp(l, "List.a") is pys_rt_empty_inline() and c == 4:
        a = list_inline(l)
    else:
        a = item_array(c, pys_rt_atomic_items(_rt.getp(l, "List.a")))
        _rt.cpy(a, _rt.getp(l, "List.a"), _rt.get(l, "List.len") * 8)
        if _rt.getp(l, "List.a") is list_inline(l):
            _rt.fill(_rt.getp(l, "List.a"), 0, 32)
    _rt.setp(l, "List.a", a)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        if c > 1152921504606846974:
            pys_rt_oom()
        ids = pys_alloc((c + 1) * 8)
        _rt.cpy(ids, _rt.getp(l, "List.ids"), (_rt.get(l, "List.len") + 1) * 8)
        _rt.setp(l, "List.ids", ids)
    _rt.set(l, "List.cap", c)


@_rt.unchecked
def pys_list_slice(l: _rt.Ptr, lo: int, hi: int) -> _rt.Ptr:
    n = _rt.get(l, "List.len")
    lo = span_lo(lo, n)
    hi = span_hi(hi, n)
    if hi < lo:
        hi = lo
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        pys_list_identity(l, _rt.word(_rt.getp(l, "List.ids"), 0))
    r = pys_list_make(hi - lo, pys_rt_atomic_items(_rt.getp(l, "List.a")))
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        ids = _rt.getp(l, "List.ids")
        pys_list_identity(r, _rt.word(ids, 0))
        _rt.cpy(_rt.at(_rt.getp(r, "List.ids"), 1), _rt.at(ids, lo + 1), (hi - lo) * 8)
    _rt.cpy(_rt.getp(r, "List.a"), _rt.at(_rt.getp(l, "List.a"), lo), (hi - lo) * 8)
    _rt.set(r, "List.len", hi - lo)
    return r


def pys_list_copy(l: _rt.Ptr) -> _rt.Ptr:
    return pys_list_slice(l, -9223372036854775807 - 1, -9223372036854775807 - 1)
'''
PY_FUNCTIONS = ("pys_list_make", "pys_list_reserve", "pys_list_slice", "pys_list_copy")
ALLOCATORS = ("pys_alloc", "pys_alloc_atomic")

# Source macros must not rewrite the independent reference operations. The live
# functions were parsed before these undefines, so redirecting memcpy or an
# allocator is observable even when a function-like macro expands in both calls.
REFERENCE_UNDEFINES = "".join("#undef " + name + "\n" for name in (
    *FUNCTIONS, "pys_alloc", "pys_alloc_atomic", "memcpy", "memset", "item_array",
    "atomic_items", "inline_items", "idx", "opt_in", "oom", "list_box", "span", "pys_dyn_big"))
FIELD_UNDEFINES = "".join("#undef " + name + "\n" for name in (
    "len", "cap", "a", "ids", "List", "I", "Slot", "v", "sizeof", "__builtin_offsetof"))


def expression(node):
    """Erase source locations/transparent casts, retaining all executable nodes."""
    if not node:
        return ("empty",)
    kind = node.get("kind")
    children = tuple(expression(child) for child in node.get("inner", []))
    if kind in {"ImplicitCastExpr", "ParenExpr"}:
        if kind == "ImplicitCastExpr":
            alias.require(node.get("castKind") in {"LValueToRValue", "FunctionToPointerDecay",
                          "BitCast", "IntegralCast", "NoOp", "ArrayToPointerDecay", "NullToPointer"},
                          "unsupported implicit companion cast: " + str(node.get("castKind")))
        alias.require(len(children) == 1, "invalid companion expression wrapper")
        return children[0]
    if kind == "DeclRefExpr":
        return ("name", node["referencedDecl"]["name"])
    if kind == "IntegerLiteral":
        return ("int", int(node["value"]))
    if kind == "StringLiteral":
        return ("string", node["value"])
    if kind == "CStyleCastExpr":
        return ("cast", node["castKind"], node["type"]["qualType"], *children)
    if kind == "UnaryExprOrTypeTraitExpr":
        alias.require(node.get("name") == "sizeof" and not children, "unsupported companion sizeof")
        return ("sizeof", node["argType"]["qualType"])
    if kind == "MemberExpr":
        return ("member", node["name"], node.get("isArrow"), *children)
    if kind == "ArraySubscriptExpr":
        return ("index", *children)
    if kind in {"UnaryOperator", "BinaryOperator", "CompoundAssignOperator"}:
        return ("operator", node["opcode"], bool(node.get("isPostfix")), *children)
    if kind == "VarDecl":
        return ("var", node["name"], node["type"]["qualType"], *children)
    alias.require(kind in {"CompoundStmt", "IfStmt", "ReturnStmt", "DeclStmt", "CallExpr",
                          "ConditionalOperator", "ForStmt"}, f"unsupported companion C node: {kind}")
    return (kind, *children)


def parse_functions(raw):
    """Clang's name filter may emit several consecutive JSON declarations."""
    decoder, result = json.JSONDecoder(), {}
    while raw.strip():
        node, end = decoder.raw_decode(raw.lstrip())
        raw = raw.lstrip()[end:]
        if node.get("kind") != "FunctionDecl":
            continue
        bodies = [child for child in node.get("inner", []) if child.get("kind") == "CompoundStmt"]
        if not bodies:
            continue
        alias.require(len(bodies) == 1 and node["name"] not in result, "duplicate companion function")
        parameters = tuple((child["name"], child["type"]["qualType"])
                           for child in node.get("inner", []) if child.get("kind") == "ParmVarDecl")
        result[node["name"]] = (node["type"]["qualType"], parameters, expression(bodies[0]))
    return result


def normalized_shape(tree):
    if not isinstance(tree, tuple):
        return tree
    if tree in {("name", "pys_alloc"), ("name", "pys_alloc_atomic")}:
        return ("name", "allocation")
    children = tuple(normalized_shape(child) for child in tree)
    if len(children) == 5 and children[:2] in {("operator", "&"), ("operator", "&=")}:
        if children[-1] in {("int", 3), ("int", 11)}:
            return (*children[:-1], ("kind-mask",))
    return children


def allocations(tree):
    found = []
    if not isinstance(tree, tuple):
        return found
    if len(tree) >= 2 and tree[0] == "CallExpr" and tree[1] in {
            ("name", "pys_alloc"), ("name", "pys_alloc_atomic")}:
        found.append(tree[1][1])
    for child in tree:
        found.extend(allocations(child))
    return found


def python_functions(source):
    """The contract's functions in runtime.py's source, by name, and its allocators' declarations."""
    found, declared = {}, {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name in PY_FUNCTIONS:
            alias.require(node.name not in found, "duplicate companion function: " + node.name)
            found[node.name] = node
        elif isinstance(node, ast.FunctionDef) and node.name in ALLOCATORS:
            # runtime.c's allocator, which runtime.py only declares: a definition of that name
            # would give every call in the contract another meaning
            body = node.body[0] if len(node.body) == 1 else None
            alias.require(node.name not in declared and isinstance(body, ast.Expr)
                          and isinstance(body.value, ast.Constant) and body.value.value is Ellipsis
                          and not node.decorator_list, "runtime.py must only declare " + node.name)
            declared[node.name] = True
        else:
            alias.require(not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.ClassDef)),
                          "runtime.py binds a module name outside its functions")
    return found, declared


def python_shape(node):
    """The tree with either allocator's name as one: the inventory, not the shape, tells them apart."""
    node = copy.deepcopy(node)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in ALLOCATORS:
            child.id = "allocation"
    return ast.dump(node)


def python_allocations(node):
    calls = [child for child in ast.walk(node) if isinstance(child, ast.Call)
             and isinstance(child.func, ast.Name) and child.func.id in ALLOCATORS]
    return [call.func.id for call in sorted(calls, key=lambda call: (call.lineno, call.col_offset))]


def physical_layout(path):
    source = '#include ' + json.dumps(str(Path(path).resolve())) + "\n" + FIELD_UNDEFINES + """
const uint64_t companion_header = sizeof(List);
const uint64_t companion_field = __builtin_offsetof(List, ids);
const uint64_t companion_field_width = sizeof(((List *)0)->ids);
const uint64_t companion_item_width = sizeof(*((List *)0)->ids);
const uint64_t companion_word = sizeof(I);
const uint64_t companion_pointer = sizeof(void *);
const uint64_t companion_length = __builtin_offsetof(List, len);
const uint64_t companion_length_width = sizeof(((List *)0)->len);
const uint64_t companion_capacity = __builtin_offsetof(List, cap);
const uint64_t companion_capacity_width = sizeof(((List *)0)->cap);
const uint64_t companion_raw = __builtin_offsetof(List, a);
const uint64_t companion_raw_width = sizeof(((List *)0)->a);
const uint64_t companion_slot_size = sizeof(Slot);
const uint64_t companion_slot_value = __builtin_offsetof(Slot, v);
const uint64_t companion_slot_width = sizeof(((Slot *)0)->v);
"""
    llvm = alias.run_clang(["-x", "c", "-S", "-emit-llvm", "-o", "-", "-"], source=source)
    layout = {key: int(value) for key, value in
              re.findall(r"^@companion_(\w+) = .*constant i64 (\d+)", llvm, re.M)}
    alias.require(layout.keys() == {"header", "field", "field_width", "item_width", "word", "pointer",
                                    "length", "length_width", "capacity", "capacity_width", "raw", "raw_width",
                                    "slot_size", "slot_value", "slot_width"},
                  "incomplete companion physical layout")
    alias.require(layout["field_width"] == layout["item_width"] == layout["word"] == layout["pointer"] == 8
                  and layout["length_width"] == layout["capacity_width"] == layout["raw_width"] == 8
                  and layout["header"] % 8 == 0,
                  "unsupported companion pointer/word ABI")
    # Raw writes and capacity updates must not alias the identity pointer. Check
    # physical ranges independently of the runtime's own static assertions:
    # anonymous unions can give correctly sized fields the same address.
    fields = [layout[name] for name in ("length", "capacity", "raw", "field")]
    alias.require(all(offset % 8 == 0 and offset + 8 <= layout["header"] for offset in fields)
                  and len(set(fields)) == len(fields), "overlapping or invalid companion header fields")
    alias.require(layout["slot_size"] == layout["slot_width"] == 8 and layout["slot_value"] == 0,
                  "raw list slot stride or value offset disagrees with companion storage")
    return layout


def normalize_runtime(path, python=None):
    path = Path(path).resolve()
    layout = physical_layout(path)
    # runtime.py names the header's fields; the compiler places them by this record
    record = RTRECORDS["List"].split()
    alias.require(record == ["len", "cap", "a*", "ids*"] and [layout[name] for name in ("length", "capacity", "raw", "field")]
                  == [8 * record.index(name) for name in record], "runtime.py's List record is not the companion header")
    reference = parse_functions(alias.run_clang([
        "-x", "c", "-Xclang", "-ast-dump=json", "-Xclang", "-ast-dump-filter=companion_contract_",
        "-fsyntax-only", "-"], source='#include ' + json.dumps(str(path)) + "\n" +
        FIELD_UNDEFINES + REFERENCE_UNDEFINES + CONTRACTS))
    bodies = {}
    for name in FUNCTIONS:
        functions = parse_functions(alias.run_clang([
            "-Xclang", "-ast-dump=json", "-Xclang", f"-ast-dump-filter={name}",
            "-fsyntax-only", str(path)]))
        alias.require(name in functions, "missing companion function: " + name)
        actual = functions[name]
        alias.require(normalized_shape(actual) == normalized_shape(reference["companion_contract_" + name]),
                      "unsupported companion function shape: " + name)
        bodies[name] = actual[2]
    reference, _ = python_functions(PY_CONTRACTS)
    actual, declared = python_functions(Path(python or ROOT / "runtime.py").read_text(encoding="utf-8"))
    alias.require(sorted(declared) == sorted(ALLOCATORS), "runtime.py does not declare both allocators")
    for name in PY_FUNCTIONS:
        alias.require(name in actual, "missing companion function: " + name)
        alias.require(python_shape(actual[name]) == python_shape(reference[name]),
                      "unsupported companion function shape: " + name)
    header_allocations = python_allocations(actual["pys_list_make"])
    array_allocations = allocations(bodies["list_identity_slow"])
    growth_allocations = python_allocations(actual["pys_list_reserve"])
    alias.require(len(header_allocations) == 2 and len(array_allocations) == len(growth_allocations) == 1,
                  "companion allocator inventory changed")
    # Matching the complete ASTs establishes exactly one fresh-array attachment
    # to l->ids and identical i+1 pointer-word setter/getter addresses. The one
    # prefix word is the kind header, not an item or an independently supplied fact.
    return {"schema_version": 2, "header_words": layout["header"] // 8,
            "header_scanned": all(name == "pys_alloc" for name in header_allocations),
            "store_word": layout["field"] // 8, "read_word": layout["field"] // 8,
            "array_scanned": array_allocations == ["pys_alloc"],
            "prefix_words": 1, "store_offset": 1, "read_offset": 1,
            "growth": {"array_scanned": growth_allocations == ["pys_alloc"], "allocation_prefix": 1,
                       "source_offset": 0, "target_offset": 0, "copy_extra": 1},
            "slice": {"array_scanned": array_allocations == ["pys_alloc"], "allocation_prefix": 1,
                      "source_offset": 1, "target_offset": 1, "copy_extra": 0}}


def checked(candidate, checker=CHECKER):
    result = subprocess.run([str(checker)], input=json.dumps(candidate), text=True, capture_output=True, timeout=10)
    alias.require(result.returncode in {0, 1}, "Lean companion checker error: " + result.stdout + result.stderr)
    response = json.loads(result.stdout)
    alias.require(response.get("accepted") is (result.returncode == 0), "inconsistent Lean companion result")
    return response["accepted"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=ROOT / "runtime.c")
    parser.add_argument("--runtime-py", type=Path, default=ROOT / "runtime.py")
    parser.add_argument("--checker", type=Path, default=CHECKER)
    args = parser.parse_args(argv)
    try:
        candidate = normalize_runtime(args.runtime, args.runtime_py)
        accepted = checked(candidate, args.checker)
        print(json.dumps({"status": "accepted" if accepted else "rejected", "checked": True,
                          "runtime_sha256": hashlib.sha256(args.runtime.read_bytes()).hexdigest(),
                          "runtime_py_sha256": hashlib.sha256(args.runtime_py.read_bytes()).hexdigest(),
                          "candidate": candidate,
                          "scope": "Initialized numeric-list companion: identity readback and tracing after direct stores, reserve growth and contiguous slice/copy.",
                          "trusted": "C and Python AST/layout adapters, the compiler's lowering of runtime.py's fields and words, initialized live indices, valid nonoverflowing extents, materialization and allocation-time liveness, called helpers, allocator and collector implementations."}))
        return 0 if accepted else 1
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "error", "checked": False, "error": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
