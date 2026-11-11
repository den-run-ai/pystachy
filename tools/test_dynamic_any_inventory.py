"""Keep the dynamic-Any boundary inventory in step with the shipped opt-ins.

docs/dynamic-any-boundaries.md gives every lib/ and ports/json_repair/ module that opts in to
dynamic Any a row: its consumer, retained boundary and containment debt (the admission rule of
docs/dynamic-any.md). An opt-in without a row, or a row naming a module that does not opt in,
fails here. Whether a row's reasoning holds remains a review question.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler.diagnostics import dynamic_pragma  # noqa: E402  (the compiler's own rule)

INVENTORY = ROOT / "docs/dynamic-any-boundaries.md"
# Each inventory section, the directory its first-column names are relative to, and whether they
# name modules (dotted, as imported) or files.
SECTIONS = {
    "Library modules": ("lib", "module"),
    "JSON repair port modules": ("ports/json_repair", "file"),
}
# Shipped and maintained code whose opt-ins need rows; tests exercise dynamic behavior on purpose.
SCANNED = ("lib", "ports")


def opted_in(root):
    """Files under root/SCANNED whose leading comment lines hold the dynamic-any pragma."""
    found = set()
    for top in SCANNED:
        for path in sorted((root / top).rglob("*.py")):
            if "__pycache__" not in path.parts:
                # (the compiler reads sources as Latin-1, so a UTF-8 byte order mark is three
                # characters, which dynamic_pragma skips)
                if dynamic_pragma(path.read_bytes().decode("latin-1")):
                    found.add(path.relative_to(root).as_posix())
    return found


def sections(text):
    """The first-column names of each "## " section's table rows."""
    names = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = names.setdefault(line[3:].strip(), [])
        elif current is not None and line.startswith("|") and not re.fullmatch(r"\|[-| :]*\|", line):
            first = line.split("|")[1]
            current.append(re.findall(r"`([^`]+)`", first))
    # (each table's first row is its header, which names no module)
    return {title: rows[1:] for title, rows in names.items()}


def resolve(root, base, kind, name):
    if kind == "file":
        path = root / base / name
        return path.relative_to(root).as_posix() if path.is_file() else None
    stem = root / base / name.replace(".", "/")
    # (a package directory takes precedence over a module file of the same name, as in imports)
    for path in (stem / "__init__.py", stem.with_name(stem.name + ".py")):
        if path.is_file():
            return path.relative_to(root).as_posix()
    return None


def problems(root, text):
    """Mismatches between the opt-ins under root and the inventory text, as messages."""
    tables = sections(text)
    found = []
    listed = set()
    for title, (base, kind) in SECTIONS.items():
        if title not in tables or not any(tables[title]):
            found.append(f"inventory section '## {title}' with a table is missing")
            continue
        for cell in tables[title]:
            if not cell:
                found.append(f"'{title}' row names no module in its first column")
            for name in cell:
                path = resolve(root, base, kind, name)
                if path is None:
                    found.append(f"'{title}' lists `{name}`, which is not a {kind} under {base}/")
                elif path in listed:
                    found.append(f"{path} has more than one inventory row")
                else:
                    listed.add(path)
    actual = opted_in(root)
    for path in sorted(actual - listed):
        found.append(f"{path} opts in to dynamic Any but has no inventory row: record its consumer, "
                     "retained boundary and containment debt (docs/dynamic-any.md#admission-and-containment)")
    for path in sorted(listed - actual):
        found.append(f"{path} has an inventory row but does not opt in: remove or update the row")
    return found


class InventoryTests(unittest.TestCase):
    def test_every_shipped_opt_in_has_exactly_one_row_and_every_row_an_opt_in(self):
        self.assertEqual(problems(ROOT, INVENTORY.read_text(encoding="utf-8")), [])

    def test_the_inventory_still_covers_both_sections(self):
        # A restructured document must not pass vacuously.
        tables = sections(INVENTORY.read_text(encoding="utf-8"))
        for title in SECTIONS:
            self.assertTrue(tables.get(title), title)


class ControlTests(unittest.TestCase):
    """The check against temporary trees: each mismatch it exists to catch is reported."""

    def tree(self, files):
        import tempfile
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        return root

    INVENTORY = ("# Dynamic library boundaries\n\n## Library modules\n\n| Module | Boundary | Debt |\n|---|---|---|\n"
                 "| `pkg._inner` | open | none |\n| `single` | open | none |\n\n"
                 "## JSON repair port modules\n\n| Modules | Boundary | Debt |\n|---|---|---|\n"
                 "| `a.py`, `sub/b.py` | open | none |\n")
    PRAGMA = "# pystachy: dynamic-any\nx = 1\n"

    def base_files(self):
        return {"lib/pkg/__init__.py": "x = 1\n", "lib/pkg/_inner.py": self.PRAGMA,
                "lib/single/__init__.py": "# a comment\n\n" + self.PRAGMA,
                "ports/json_repair/a.py": self.PRAGMA, "ports/json_repair/sub/b.py": self.PRAGMA}

    def test_matching_tree_passes(self):
        self.assertEqual(problems(self.tree(self.base_files()), self.INVENTORY), [])

    def test_unlisted_opt_ins_fail_in_lib_ports_and_other_ports(self):
        files = self.base_files()
        files["lib/extra.py"] = self.PRAGMA
        files["ports/json_repair/new.py"] = "﻿# pystachy: dynamic-any\n"
        files["ports/other/mod.py"] = self.PRAGMA
        found = problems(self.tree(files), self.INVENTORY)
        self.assertEqual([m.split(" ")[0] for m in found],
                         ["lib/extra.py", "ports/json_repair/new.py", "ports/other/mod.py"])
        self.assertTrue(all("has no inventory row" in m for m in found))

    def test_rows_without_an_opt_in_fail(self):
        files = self.base_files()
        files["lib/pkg/_inner.py"] = "x = 1\n" + self.PRAGMA   # after code: not an opt-in
        files["ports/json_repair/a.py"] = "# pystachy: dynamic-any (sic)\n"
        found = problems(self.tree(files), self.INVENTORY)
        self.assertEqual(found, ["lib/pkg/_inner.py has an inventory row but does not opt in: remove or update the row",
                                 "ports/json_repair/a.py has an inventory row but does not opt in: remove or update the row"])

    def test_unknown_duplicate_and_missing_entries_fail(self):
        text = self.INVENTORY.replace("| `single` |", "| `single`, `missing.mod` |")
        text += "| `a.py` | again | none |\n| no module | x | y |\n"
        found = problems(self.tree(self.base_files()), text)
        self.assertIn("'Library modules' lists `missing.mod`, which is not a module under lib/", found)
        self.assertIn("ports/json_repair/a.py has more than one inventory row", found)
        self.assertIn("'JSON repair port modules' row names no module in its first column", found)

    def test_missing_section_fails_rather_than_passing_vacuously(self):
        text = self.INVENTORY.split("## JSON repair")[0]
        found = problems(self.tree(self.base_files()), text)
        self.assertIn("inventory section '## JSON repair port modules' with a table is missing", found)

    def test_non_python_files_and_tests_are_not_scanned(self):
        files = self.base_files()
        files["ports/json_repair/PORT.md"] = self.PRAGMA
        files["tests/programs/inference/case.py"] = self.PRAGMA
        files["lib/__pycache__/cached.py"] = self.PRAGMA
        self.assertEqual(problems(self.tree(files), self.INVENTORY), [])


if __name__ == "__main__":
    unittest.main()
