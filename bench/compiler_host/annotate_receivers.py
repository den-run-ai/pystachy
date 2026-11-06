"""Explicit research overlay for mypyc's erased generic compiler receivers.

This changes only the prepared host, never the benchmark's frozen source input.
TYPE_CHECKING avoids runtime import cycles. The following runtime import aliases
Gen to Any, retaining Pystachy's call-site specialization; the explicit assignment
ignore preserves mypyc's concrete static receiver type. Keeping that fallback out
of an else branch avoids mypyc 2.4.0's unreachable-code trap. Three type-only
assertions express existing branch invariants without runtime casts. This is a
host-preparation overlay, not a compiler algorithm change.
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
        text = text.replace(needle, needle + "from typing import TYPE_CHECKING\n"
                            "if TYPE_CHECKING:\n    from src.pystachy_compiler.gen import Gen\n"
                            "from typing import Any as Gen  # type: ignore[assignment]\n", 1)
        replacements = {
            "structs": [("    sf = parse_struct(c.s)",
                         "    if TYPE_CHECKING:\n        assert c is not None\n    sf = parse_struct(c.s)"),
                        ('    b = self.expr(buf, "bytes")',
                         '    if TYPE_CHECKING:\n        assert buf is not None\n    b = self.expr(buf, "bytes")')],
            "exceptions": [("            kws.append(a if pure_arg(a.kids[0]) else mk(",
                            "            if TYPE_CHECKING:\n                assert init is not None\n"
                            "            kws.append(a if pure_arg(a.kids[0]) else mk(")],
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
