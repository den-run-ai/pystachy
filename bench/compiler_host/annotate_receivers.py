"""Explicit research overlay for mypyc's erased generic compiler receivers.

This changes only the prepared host, never the benchmark's frozen source input.
TYPE_CHECKING avoids runtime import cycles. Three casts express existing branch
invariants; typing.cast returns its argument unchanged. The overlay is not a
proposal to introduce circular compiler dependencies into Pystachy's source.
"""
from __future__ import annotations

import ast
import difflib
import json
from pathlib import Path


def apply(work: Path):
    counts, patches = {}, []
    for path in sorted((work / "src/pystachy_compiler").glob("*.py")):
        before = path.read_text()
        lines, count = before.splitlines(keepends=True), 0
        for node in ast.parse(before).body:
            if not isinstance(node, ast.FunctionDef) or not node.args.args:
                continue
            arg = node.args.args[0]
            if arg.arg != "self" or arg.annotation is not None:
                continue
            line = arg.lineno - 1
            lines[line] = lines[line][:arg.col_offset] + lines[line][arg.col_offset:].replace("self", "self: Gen", 1)
            count += 1
        if not count:
            continue
        text = "".join(lines)
        needle = "from __future__ import annotations\n"
        if needle not in text:
            raise RuntimeError(f"missing postponed annotations in {path}")
        cast = ", cast" if path.stem in ("structs", "exceptions") else ""
        text = text.replace(needle, needle + f"from typing import TYPE_CHECKING{cast}\n"
                            "if TYPE_CHECKING:\n    from src.pystachy_compiler.gen import Gen\n", 1)
        replacements = {
            "structs": [("parse_struct(c.s)", "parse_struct(cast(Node, c).s)"),
                        ('b = self.expr(buf, "bytes")', 'b = self.expr(cast(Node, buf), "bytes")')],
            "exceptions": [("self.kw_type(init, a.s)", "self.kw_type(cast(FnInfo, init), a.s)")],
        }
        for old, new in replacements.get(path.stem, []):
            if text.count(old) != 1:
                raise RuntimeError(f"overlay anchor changed in {path}: {old}")
            text = text.replace(old, new)
        path.write_text(text)
        name = str(path.relative_to(work))
        counts[name] = count
        patches.extend(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
                                           fromfile="a/" + name, tofile="b/" + name, n=0))
    (work / "receiver-overlay.diff").write_text("".join(patches))
    (work / "receiver-counts.json").write_text(json.dumps(counts, indent=2) + "\n")
    return counts
