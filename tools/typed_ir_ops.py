#!/usr/bin/env python3
"""Views of the typed IR's operation table (OPS, src/pystachy_compiler/specs.py).

The table is the one definition of each operation's shape. This tool writes the reference
table of docs/typed-ir.md from it (--write), fails when that table is out of date (--check),
and prints the rows as JSON for other tools (--json): the Lean shape checker reads them.

    python3 tools/typed_ir_ops.py --check
    python3 tools/typed_ir_ops.py --write
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler.specs import FX, OPS  # noqa: E402

DOC = ROOT / "docs/typed-ir.md"
BEGIN = "<!-- typed-ir-ops: begin (written by tools/typed_ir_ops.py --write) -->"
END = "<!-- typed-ir-ops: end -->"
COLUMNS = ("effects", "operands", "results", "labels", "fields", "value")
FLAGS = ("T", "E", "*")
FIELD_BITS = {"t": 1, "s": 2, "k": 4, "x": 8}


def rows():
    """Each operation's row as a dict, in the table's order; a malformed row raises ValueError."""
    result = []
    for name, text in OPS.items():
        cells = text.split("|")
        if len(cells) != len(COLUMNS):
            raise ValueError(f"{name}: expected {len(COLUMNS)} columns, got {len(cells)}")
        row = dict(zip(COLUMNS, cells, strict=True))
        tokens = row["effects"].split()
        if any(t not in FX and t not in FLAGS for t in tokens) or len(set(tokens)) != len(tokens):
            raise ValueError(f"{name}: unknown or repeated effect in {row['effects']!r}")
        operands = row["operands"]
        if operands.endswith("+"):
            low, high = int(operands[:-1]), None
        elif "-" in operands:
            low, high = (int(x) for x in operands.split("-"))
        else:
            low = high = int(operands)
        if low < 0 or (high is not None and high < low) or operands != (
                f"{low}+" if high is None else str(low) if high == low else f"{low}-{high}"):
            raise ValueError(f"{name}: invalid operand count {operands!r}")
        roles = row["results"]
        if roles == "?":
            results, temporaries = None, []
        elif roles.isdigit() and str(int(roles)) == roles:
            results, temporaries = int(roles), []
        elif roles != "" and set(roles) <= {"v", "."} and "." in roles:
            # (one letter per number: v a value, . a temporary of the op's lowering)
            results, temporaries = len(roles), [j for j, c in enumerate(roles) if c == "."]
        else:
            raise ValueError(f"{name}: invalid results {roles!r}: a count, ?, or v and . per number with some .")
        labels = row["labels"]
        if labels not in ("a", "i") and (not labels.isdigit() or str(int(labels)) != labels):
            raise ValueError(f"{name}: invalid label count {labels!r}")
        fields = row["fields"].split()
        if any(f not in FIELD_BITS for f in fields) or fields != [f for f in FIELD_BITS if f in fields]:
            raise ValueError(f"{name}: fields must be some of t s k x, in that order: {row['fields']!r}")
        value = int(row["value"])
        if value not in (0, 1, 2, 3) or (results is not None and value in (1, 2) and value > results):
            raise ValueError(f"{name}: value {value} names no number of its {row['results']} results")
        if "E" in tokens and ("T" in tokens or labels != "0"):
            raise ValueError(f"{name}: entry storage neither ends a block nor branches")
        result.append({
            "name": name, "text": text, "effects": [t for t in tokens if t not in FLAGS],
            "terminator": "T" in tokens, "entry": "E" in tokens, "varies": "*" in tokens,
            "min": low, "max": high, "results": results, "temporaries": temporaries, "labels": labels,
            "fields": fields, "value": value,
        })
    return result


def schema():
    """The rows as the Lean shape checker takes them (tools/lean_boundary/ShapeMain.lean)."""
    return [{
        "terminator": row["terminator"], "entry": row["entry"], "min": row["min"], "max": row["max"],
        "results": row["results"],
        "labels": [2] if row["labels"] == "a" else [1] if row["labels"] == "i" else [0, int(row["labels"]), int(row["labels"])],
        "fields": sum(FIELD_BITS[f] for f in row["fields"]),
    } for row in rows()]


def reference():
    """The Markdown reference table, one line per operation."""
    words = {"a": "one per operand", "i": "0, or 2 as an invoke"}
    lines = [BEGIN, "", "| Operation | Effects | Operands | Results | Labels | Fields | Value |", "|---|---|---|---|---|---|---|"]
    for row in rows():
        kind = [w for flag, w in (("terminator", "ends its block"), ("entry", "entry storage"),
                                  ("varies", "per instruction")) if row[flag]]
        effects = ", ".join([*kind, *(f"`{e}`" for e in row["effects"])]) or "none"
        operands = str(row["min"]) if row["max"] == row["min"] else f"{row['min']} or more" if row["max"] is None else f"{row['min']} to {row['max']}"
        results = ("0 or 1, by signature" if row["results"] is None else str(row["results"]) if not row["temporaries"]
                   else f"{row['results']}: " + ", ".join("temporary" if j in row["temporaries"] else "value"
                                                           for j in range(row["results"])))
        fields = ", ".join(f"`{f}`" for f in row["fields"]) or "none"
        value = ("none", "first", "second", "each")[row["value"]]
        lines.append(f"| `{row['name']}` | {effects} | {operands} | {results} | {words.get(row['labels'], row['labels'])} | {fields} | {value} |")
    return "\n".join([*lines, "", END])


def current(text):
    """The reference table that a document holds, or None where its markers are missing."""
    start, stop = text.find(BEGIN), text.find(END)
    return None if start < 0 or stop < start else text[start:stop + len(END)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if docs/typed-ir.md's table is out of date")
    mode.add_argument("--write", action="store_true", help="rewrite docs/typed-ir.md's table")
    mode.add_argument("--json", action="store_true", help="print the rows as JSON")
    args = parser.parse_args()
    try:
        if args.json:
            print(json.dumps(rows(), indent=1))
            return 0
        text = DOC.read_text(encoding="utf-8")
        held = current(text)
        if held is None:
            print(f"typed_ir_ops: {DOC} has no operation reference markers", file=sys.stderr)
            return 1
        wanted = reference()
        if args.write:
            if held != wanted:
                DOC.write_text(text.replace(held, wanted), encoding="utf-8")
            return 0
        if held != wanted:
            print("typed_ir_ops: docs/typed-ir.md's operation reference is out of date; "
                  "run python3 tools/typed_ir_ops.py --write", file=sys.stderr)
            return 1
        print(f"typed_ir_ops: the reference of {len(rows())} operations is current")
        return 0
    except ValueError as error:
        print(f"typed_ir_ops: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
