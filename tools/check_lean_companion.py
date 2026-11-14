#!/usr/bin/env python3
"""Check live numeric-list identity stores and their two tracing edges with Lean.

The contract covers a stable, initialized companion and a successful in-bounds
setter/getter. Materialization, growth/copies, callbacks, collection scheduling,
and the concrete allocator/collector remain outside the proof. The bounded C-AST
adapter fails closed on unknown statement shapes; it is part of the trusted base.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import check_lean_alias as alias

ROOT = alias.ROOT
CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-companion"

# Clang parses these bounded contracts in the actual translation unit. Comparing
# normalized ASTs rather than C text retains macro expansion, casts, store order,
# conditions and every statement. Allocator names are extracted separately. The
# list kind's 3/11 masks do not change an address or scanned extent; materializing
# a correct numeric value is deliberately not claimed by the tracing theorem.
CONTRACTS = r"""
static List *companion_contract_list_new(I cap, int atomic) {
  if (!atomic && cap <= INLINE_CAP) {
    List *l = pys_alloc(sizeof(List) + INLINE_CAP * sizeof(I));
    l->cap = INLINE_CAP; l->a = inline_items(l); return l;
  }
  List *l = pys_alloc(sizeof(List) - 1);
  l->cap = cap > INLINE_CAP ? cap : INLINE_CAP;
  l->a = item_array(l->cap, atomic); return l;
}
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
"""
FUNCTIONS = ("list_new", "list_identity_slow", "pys_list_set_identity", "pys_list_get_identity")


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


def physical_layout(path):
    source = '#include ' + json.dumps(str(Path(path).resolve())) + "\n" + """
const uint64_t companion_header = sizeof(List);
const uint64_t companion_field = offsetof(List, ids);
const uint64_t companion_field_width = sizeof(((List *)0)->ids);
const uint64_t companion_item_width = sizeof(*((List *)0)->ids);
const uint64_t companion_word = sizeof(I);
const uint64_t companion_pointer = sizeof(void *);
"""
    llvm = alias.run_clang(["-x", "c", "-S", "-emit-llvm", "-o", "-", "-"], source=source)
    layout = {key: int(value) for key, value in
              re.findall(r"^@companion_(\w+) = .*constant i64 (\d+)", llvm, re.M)}
    alias.require(layout.keys() == {"header", "field", "field_width", "item_width", "word", "pointer"},
                  "incomplete companion physical layout")
    alias.require(layout["field_width"] == layout["item_width"] == layout["word"] == layout["pointer"] == 8
                  and layout["header"] % 8 == layout["field"] % 8 == 0,
                  "unsupported companion pointer/word ABI")
    return layout


def normalize_runtime(path):
    path = Path(path).resolve()
    layout = physical_layout(path)
    reference = parse_functions(alias.run_clang([
        "-x", "c", "-Xclang", "-ast-dump=json", "-Xclang", "-ast-dump-filter=companion_contract_",
        "-fsyntax-only", "-"], source='#include ' + json.dumps(str(path)) + "\n" + CONTRACTS))
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
    header_allocations = allocations(bodies["list_new"])
    array_allocations = allocations(bodies["list_identity_slow"])
    alias.require(len(header_allocations) == 2 and len(array_allocations) == 1,
                  "companion allocator inventory changed")
    # Matching the complete ASTs establishes exactly one fresh-array attachment
    # to l->ids and identical i+1 pointer-word setter/getter addresses. The one
    # prefix word is the kind header, not an item or an independently supplied fact.
    return {"schema_version": 1, "header_words": layout["header"] // 8,
            "header_scanned": all(name == "pys_alloc" for name in header_allocations),
            "store_word": layout["field"] // 8, "read_word": layout["field"] // 8,
            "array_scanned": array_allocations == ["pys_alloc"],
            "prefix_words": 1, "store_offset": 1, "read_offset": 1}


def checked(candidate, checker=CHECKER):
    result = subprocess.run([str(checker)], input=json.dumps(candidate), text=True, capture_output=True, timeout=10)
    alias.require(result.returncode in {0, 1}, "Lean companion checker error: " + result.stdout + result.stderr)
    response = json.loads(result.stdout)
    alias.require(response.get("accepted") is (result.returncode == 0), "inconsistent Lean companion result")
    return response["accepted"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=ROOT / "runtime.c")
    parser.add_argument("--checker", type=Path, default=CHECKER)
    args = parser.parse_args(argv)
    try:
        candidate = normalize_runtime(args.runtime)
        accepted = checked(candidate, args.checker)
        print(json.dumps({"status": "accepted" if accepted else "rejected", "checked": True,
                          "runtime_sha256": hashlib.sha256(args.runtime.read_bytes()).hexdigest(),
                          "candidate": candidate,
                          "scope": "Stable initialized numeric-list companion: exact identity readback and header/array tracing edges.",
                          "trusted": "C AST/layout adapter, initialized live index, materialization/lifecycle, allocator and collector implementations."}))
        return 0 if accepted else 1
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "error", "checked": False, "error": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
