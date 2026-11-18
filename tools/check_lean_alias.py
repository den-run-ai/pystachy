#!/usr/bin/env python3
"""Check the live reference-box transfer's address and tracing contract with Lean.

The bounded C-AST adapter, C layout compiler, payload lowerer, allocator semantics
and collector remain trusted. Unknown body shapes fail closed. This is not a
general C verifier or a collector correctness proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.ir import Ins, Val  # noqa: E402
from src.pystachy_compiler.lowering import gen_lower_ins  # noqa: E402

CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-alias"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def clang_path():
    return shutil.which(str(Path(os.environ["PYSTACHY_LLVM"]) / "clang")
                        if os.environ.get("PYSTACHY_LLVM") else "clang")


def run_clang(arguments, *, source=None):
    clang = clang_path()
    require(clang, "clang is required for the reference transfer correspondence")
    result = subprocess.run([clang, *arguments], input=source, text=True, capture_output=True,
                            timeout=30)
    require(result.returncode == 0, "C correspondence compilation failed: " + result.stderr[:2000])
    require(len(result.stdout) <= 4 * 1024 * 1024, "C correspondence output exceeds 4 MiB")
    return result.stdout


def expression(node):
    """Retain every statement; erase only transparent AST wrappers.

    Explicit C casts retain their type/kind, so pointer arithmetic or a narrowed
    integer cast cannot become a reference copy. No arbitrary C is evaluated.
    """
    kind = node.get("kind")
    children = [expression(child) for child in node.get("inner", [])]
    if kind == "ImplicitCastExpr":
        require(node.get("castKind") in {"LValueToRValue", "FunctionToPointerDecay", "BitCast",
                                         "IntegralCast", "NoOp"}, "unsupported implicit C cast")
        require(len(children) == 1, "invalid implicit C cast")
        return children[0]
    if kind == "ParenExpr":
        require(len(children) == 1, "invalid C parentheses")
        return children[0]
    if kind == "DeclRefExpr":
        return ("name", node["referencedDecl"]["name"])
    if kind == "IntegerLiteral":
        return ("int", int(node["value"]))
    if kind == "CStyleCastExpr":
        return ("cast", node["castKind"], node["type"]["qualType"], *children)
    if kind == "MemberExpr":
        return ("member", node["name"], node.get("isArrow"), *children)
    if kind in {"UnaryOperator", "BinaryOperator"}:
        return ("operator", node["opcode"], *children)
    if kind == "VarDecl":
        return ("var", node["name"], node["type"]["qualType"], *children)
    require(kind in {"CompoundStmt", "IfStmt", "ReturnStmt", "DeclStmt", "CallExpr",
                     "ConditionalOperator"}, f"unsupported C transfer node: {kind}")
    return (kind, *children)


def function_ast(path, symbol, signature, parameters):
    raw = run_clang(["-Xclang", "-ast-dump=json", "-Xclang", f"-ast-dump-filter={symbol}",
                     "-fsyntax-only", str(path)])
    node = json.loads(raw)
    require(node.get("kind") == "FunctionDecl" and node.get("name") == symbol
            and node.get("type", {}).get("qualType") == signature, "changed C function signature")
    children = node.get("inner", [])
    args = [(entry.get("name"), entry.get("type", {}).get("qualType")) for entry in children
            if entry.get("kind") == "ParmVarDecl"]
    require(args == parameters, "changed C parameter binding")
    bodies = [entry for entry in children if entry.get("kind") == "CompoundStmt"]
    require(len(bodies) == 1, "C transfer needs exactly one body")
    return expression(bodies[0])


def physical_layout(path):
    # Compile constants in the *same translation unit*, not extracted source
    # declarations: macros can change a field's width only at its declaration.
    stub = '#include ' + json.dumps(str(Path(path).resolve())) + "\n" + """
const uint64_t alias_size = sizeof(Dyn);
const uint64_t alias_word = sizeof(I);
const uint64_t alias_pointer = sizeof(void *);
const uint64_t alias_tag = offsetof(Dyn, t);
const uint64_t alias_payload = offsetof(Dyn, v);
const uint64_t alias_payload_size = sizeof(((Dyn *)0)->v);
const uint64_t alias_tag_size = sizeof(((Dyn *)0)->t);
"""
    llvm = run_clang(["-x", "c", "-S", "-emit-llvm", "-o", "-", "-"], source=stub)
    layout = {name: int(value) for name, value in
              re.findall(r"^@alias_(\w+) = .*constant i64 (\d+)", llvm, re.M)}
    require(layout.keys() == {"size", "word", "pointer", "tag", "payload", "payload_size", "tag_size"}, "incomplete C layout")
    require(layout["word"] == layout["pointer"] == layout["payload_size"] == layout["tag_size"] == 8
            and layout["size"] % 8 == 0
            and layout["tag"] % 8 == layout["payload"] % 8 == 0, "unsupported box word ABI")
    return layout


def payload_word():
    generated = SimpleNamespace(out=[])
    payload = Ins("dyn.payload", "%slot", "list[int]")
    payload.r, payload.a = [1, 2], [Val("%box", "dyn")]
    gen_lower_ins(generated, None, payload)
    lines = [line.strip() for line in generated.out]
    require(len(lines) == 2 and lines[1] == "%t2 = load i64, ptr %t1", "unsupported payload load lowering")
    match = re.fullmatch(r"%t1 = getelementptr i64, ptr %box, i64 (\d+)", lines[0])
    require(match, "unsupported payload address lowering")
    return int(match[1])


def normalize_runtime(path):
    """Derive one complete non-null transfer from the actual reference boxer.

    The null-return path and native-list preparation must match their bounded
    shapes. The latter can mutate items but cannot rebind the input pointer.
    Allocation and each field store are derived, never supplied as certificates.
    """
    path = Path(path)
    layout = physical_layout(path)
    body = function_ast(path, "pys_dyn_ref", "Dyn *(const DynType *, void *)",
                        [("t", "const DynType *"), ("p", "void *")])
    null_case = ("IfStmt", ("operator", "!", ("name", "p")),
                 ("ReturnStmt", ("cast", "NoOp", "Dyn *", ("operator", "&", ("name", "pys_dyn_none_box")))))
    prepare = ("IfStmt", ("CallExpr", ("name", "dyn_native_list_type"), ("name", "t")),
               ("CallExpr", ("name", "pys_list_identity"),
                ("cast", "BitCast", "List *", ("name", "p")), ("int", 1)))
    require(len(body) >= 6 and body[0] == "CompoundStmt" and body[1:3] == (null_case, prepare),
            "unsupported null/reference preparation path")
    allocation = body[3]
    require(allocation[:1] == ("DeclStmt",) and len(allocation) == 2, "missing reference box allocation")
    declaration = allocation[1]
    require(len(declaration) == 4 and declaration[:3] == ("var", "d", "Dyn *"), "changed box binding")
    call = declaration[3]
    require(len(call) == 3 and call[:2] == ("CallExpr", ("name", "gc_box"))
            and call[2] in {("int", 0), ("int", 1)}, "unsupported box allocation")
    atomic = call[2][1]
    allocator = function_ast(path, "gc_box", "void *(int)", [("atomic", "int")])
    require(len(allocator) == 2 and allocator[0] == "CompoundStmt"
            and allocator[1][0] == "ReturnStmt" and len(allocator[1]) == 2, "changed box allocator body")
    choice = allocator[1][1]
    require(len(choice) == 4 and choice[:2] == ("ConditionalOperator", ("name", "atomic")),
            "changed box allocator selection")
    selected = choice[2 if atomic else 3]
    require(len(selected) == 3 and selected[0] == "CallExpr"
            and selected[1] in {("name", "pys_alloc"), ("name", "pys_alloc_atomic")}
            and selected[2][0] == "int", "unsupported box allocator")
    require(selected[2][1] + 1 == layout["size"], "box allocation extent disagrees with C layout")
    require(body[-1] == ("ReturnStmt", ("name", "d")), "reference box result was replaced")
    stores = []
    for statement in body[4:-1]:
        require(len(statement) == 4 and statement[:2] == ("operator", "="), "unsupported box statement")
        member, value = statement[2:]
        require(len(member) == 4 and member[0] == "member" and member[2:] == (True, ("name", "d"))
                and member[1] in {"t", "v"}, "store does not target the new reference box")
        sources = {("name", "t"): "tag", ("cast", "PointerToIntegral", "I", ("name", "p")): "reference",
                   ("int", 0): "zero"}
        require(value in sources, "unsupported reference transfer value")
        stores.append({"word": layout["tag" if member[1] == "t" else "payload"] // 8,
                       "source": sources[value]})
    require(stores, "reference transfer has no stores")
    candidate = {"schema_version": 1, "words": layout["size"] // 8,
                 "scanned": selected[1] == ("name", "pys_alloc"), "stores": stores,
                 "read_word": payload_word()}
    return candidate


def checked(candidate, checker=CHECKER):
    result = subprocess.run([str(checker)], input=json.dumps(candidate), text=True, capture_output=True, timeout=10)
    require(result.returncode in {0, 1}, "Lean alias checker error: " + result.stdout + result.stderr)
    response = json.loads(result.stdout)
    require(response.get("accepted") is (result.returncode == 0)
            and response.get("stores") == len(candidate["stores"]), "inconsistent Lean alias result")
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
                          "scope": "Non-null reference-box address, alias write and abstract tracing edge preservation.",
                          "trusted": "C AST adapter/layout, payload lowering correspondence, allocator and collector implementations."}))
        return 0 if accepted else 1
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "error", "checked": False, "error": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
