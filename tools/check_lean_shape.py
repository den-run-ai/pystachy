#!/usr/bin/env python3
"""Check typed-IR functions' shape and def-before-use with Lean, against the operation table.

Lean checks that each instruction has the operand, result and label counts and only the fields
its row of OPS declares, that each block ends in its one terminator, that labels name blocks,
and that each value number has one definition that every operand reading it can name; then that
the definition is reached on every path from the entry block to each read (PystachyDominance).
Inputs are inspection snapshots (typed-before.json, typed-after.json) or typed-IR text (.tir).

    python3 tools/check_lean_shape.py /tmp/inspect/typed-after.json
    python3 tools/check_lean_shape.py tools/fixtures/typed_ir/score_samples.listget.after.tir

This adapter is trusted: it reads the table, interns labels, classifies each operand's spelling
(ir.operand_kind) and numbers the operations. The dominator tree it computes is a claim that Lean
tests against every edge, not trusted. Lean proves nothing of types, effects or lowering.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import typed_ir_ops  # noqa: E402
import typed_ir_text  # noqa: E402
from src.pystachy_compiler import ir  # noqa: E402

DEFAULT_CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-shape"
FIELDS = (("type", "", 1), ("text", "", 2), ("immediate", 0, 4), ("descriptor", "", 8))
# Lean's operand kinds: a value, a parameter, a slot, or a constant (a symbol, a literal, a
# constant expression and the identity result need no definition in the function). 4 is none.
VALUE, PARAM, SLOT, CONSTANT, UNKNOWN = 0, 1, 2, 3, 4
LIMITATIONS = [
    "Checks instruction shape against OPS, block terminators, label resolution and single definition of value numbers.",
    "Checks that each value's definition is reached on every path to each read; code no path reaches is not checked.",
    "Operand and result types, effects and lowering are not checked.",
    "The Python adapter, the operation table it reads, operand classification and the native Lean executable are trusted.",
    "A snapshot or text is an observation of the compiler's IR, not the IR that lowering consumed.",
]


class Rejected(ValueError):
    """An input the adapter cannot normalize."""


def require(condition, message):
    if not condition:
        raise Rejected(message)


def slot_register(slot):
    """A slot's register, as ir.slot_register names it."""
    number = slot["results"][0] if len(slot["results"]) == 1 else "?"
    if slot["immediate"] == 1:
        return f"%{slot['text']}.def.{number}"
    if slot["immediate"] == 2:
        return f"%stk.{number}"
    return f"%{slot['text'] or 'h'}.{number}"


def normalize(record, names):
    """One function record as the Lean checker takes it."""
    labels = {}

    def label(name):
        require(isinstance(name, str), "a label must be a string")
        return labels.setdefault(name, len(labels))

    for block in record["blocks"]:
        label(block["label"])
    registers = {slot_register(slot) for slot in record["slots"]}

    def operand(value):
        require(isinstance(value, str), "an operand's value must be a string")
        kind = ir.operand_kind(value)
        if kind == ir.OPERAND_VALUE:
            return [VALUE, int(value[2:])]
        if kind == ir.OPERAND_PARAM and value != "%idret":
            return [PARAM, int(re.search(r"\d+$", value).group(0))]
        if kind == ir.OPERAND_SLOT:
            # The register must be a slot's own: its number alone is no name (a flag shares it).
            return [SLOT if value in registers else UNKNOWN, int(re.search(r"\d+$", value).group(0))]
        return [UNKNOWN if kind < 0 else CONSTANT, 0]

    def instruction(ins):
        require(isinstance(ins["op"], str), "an operation must be a string")
        require(all(type(r) is int and 0 <= r <= 4294967296 for r in ins["results"]), "invalid result number")
        implicit = []
        if ins["op"] == "check":
            key = ins["descriptor"] if ins["descriptor"] != "" else ins["text"]
            # (a check whose error block the function does not hold names a label of no block)
            implicit = [label(record["check_targets"][key]) if key in record["check_targets"]
                        else labels.setdefault(("no error block", key), len(labels))]
        return {
            "op": names.get(ins["op"], len(names)),
            "a": [operand(a["value"]) for a in ins["operands"]],
            "r": list(ins["results"]),
            "b": [label(name) for name in ins["targets"]],
            "e": implicit,
            "f": sum(bit for key, empty, bit in FIELDS if ins[key] != empty),
            "j": ins["op"] == "phi",
        }

    blocks = [{"label": labels[block["label"]], "code": [instruction(ins) for ins in block["operations"]]}
              for block in record["blocks"]]
    return {
        "symbol": record["symbol"],
        "params": len(record["parameters"]),
        "slots": [instruction(slot) for slot in record["slots"]],
        # (two blocks of one label have one number, which Lean's distinct labels reject)
        "blocks": blocks,
        "tree": dominator_tree(blocks),
    }


def dominator_tree(blocks):
    """Each block that the entry block reaches, but the entry block, with its immediate dominator:
    [label, parent] pairs (Cooper, Harvey and Kennedy's iteration in reverse postorder). Lean
    checks this claim against every edge, as PystachyDominance.successors draws them."""
    if not blocks:
        return []
    successors = {block["label"]: [] for block in blocks}
    for block in blocks:
        for ins in block["code"]:
            if not ins["j"]:
                successors[block["label"]].extend(l for l in ins["b"] + ins["e"] if l in successors)
    entry = blocks[0]["label"]
    postorder, seen, stack = [], {entry}, [(entry, iter(successors[entry]))]
    while stack:
        node, pending = stack[-1]
        following = next((s for s in pending if s not in seen), None)
        if following is None:
            stack.pop()
            postorder.append(node)
        else:
            seen.add(following)
            stack.append((following, iter(successors[following])))
    order = postorder[::-1]
    rank = {label: n for n, label in enumerate(order)}
    predecessors = {label: [] for label in order}
    for label in order:
        for s in successors[label]:
            predecessors[s].append(label)
    parent = {entry: entry}

    def meet(a, b):
        while a != b:
            while rank[a] > rank[b]:
                a = parent[a]
            while rank[b] > rank[a]:
                b = parent[b]
        return a

    changed = True
    while changed:
        changed = False
        for label in order[1:]:
            found = None
            for p in predecessors[label]:
                if p in parent:
                    found = p if found is None else meet(p, found)
            if parent.get(label) != found:
                parent[label] = found
                changed = True
    return [[label, parent[label]] for label in order[1:]]


def candidate(records):
    """The checker's input for function records (typed_ir_text's)."""
    rows = typed_ir_ops.rows()
    names = {row["name"]: index for index, row in enumerate(rows)}
    return {"table": typed_ir_ops.schema(), "functions": [normalize(record, names) for record in records]}


def load(path):
    """The function records of a snapshot or of typed-IR text."""
    source = Path(path).read_text(encoding="utf-8")
    if str(path).endswith(".json"):
        snapshot = json.loads(source)
        require(isinstance(snapshot, dict) and snapshot.get("schema_version") == 1
                and isinstance(snapshot.get("functions"), list), "expected an inspection snapshot of schema_version 1")
        return [typed_ir_text.from_snapshot(function) for function in snapshot["functions"]]
    return typed_ir_text.parse_functions(source)


def check(records, checker=DEFAULT_CHECKER, timeout=600):
    """(the checker's verdict, whether it accepted every function)."""
    require(Path(checker).is_file(), f"Lean shape checker is missing: build tools/lean_boundary ({checker})")
    encoded = json.dumps(candidate(records), separators=(",", ":"))
    done = subprocess.run([str(checker)], input=encoded, capture_output=True, text=True, timeout=timeout)
    require(done.returncode in (0, 1, 2) and done.stdout.strip() != "", f"the Lean checker failed: {done.stderr.strip()[:400]}")
    verdict = json.loads(done.stdout)
    require(isinstance(verdict, dict) and type(verdict.get("accepted")) is bool, "the Lean checker printed no verdict")
    require("error" not in verdict, f"the Lean checker rejected its input: {verdict.get('error')}")
    require(verdict["accepted"] == (done.returncode == 0) and verdict.get("functions") == len(records),
            "the Lean checker's verdict does not match its exit status or the functions sent")
    return verdict, verdict["accepted"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path, help="inspection snapshots (.json) or typed-IR text")
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    parser.add_argument("--function", default="", help="only functions whose symbol contains this")
    args = parser.parse_args(argv)
    status = 0
    for path in args.paths:
        try:
            records = [r for r in load(path) if args.function in r["symbol"]]
            verdict, accepted = check(records, args.checker)
        except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError) as error:
            print(json.dumps({"path": str(path), "accepted": False, "error": str(error)}))
            status = max(status, 2)
            continue
        print(json.dumps({"path": str(path), **verdict, "limitations": LIMITATIONS}))
        status = max(status, 0 if accepted else 1)
    return status


if __name__ == "__main__":
    sys.exit(main())
