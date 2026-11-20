"""Each source line is annotated with the typed IR and the LLVM IR it compiles to.

Run with python3 -m unittest discover -s tools -p test_typed_ir_annotate.py.
"""
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import annotate_ir

ROOT = Path(__file__).resolve().parent.parent
PROGRAM = '''from helper import twice


def add(a: int, b: int) -> int:
    return a + b


def greet(name: str, n: int) -> str:
    return f"{name} has {n} items"


def below(x: int, y: int) -> bool:
    return x < y


print(add(2, 3), greet("ada", 3), below(1, twice(2)))
'''
HELPER = '''def twice(x: int) -> int:
    return x * 2
'''


class AnnotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "program.py"
        cls.path.write_text(PROGRAM)
        (Path(cls.directory.name) / "helper.py").write_text(HELPER)
        cls.records = annotate_ir.annotate(cls.path)
        cls.lines = annotate_ir.by_line(cls.records)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def instructions(self, line):
        return [item["ins"] for _, item in self.lines.get(line, []) if item["kind"] == "instruction"]

    def test_a_line_holds_its_instructions_each_with_its_llvm(self):
        add = self.instructions(5)
        checked = next(i for i in add if i["op"] == "ovf")
        self.assertTrue(any("@llvm.sadd.with.overflow.i64" in x for x in checked["llvm"]), checked)
        self.assertEqual(len(checked["llvm"]), 3)  # (the call and its two extractvalues)
        self.assertIn("R", [e for i in add for e in i["effects"]])
        self.assertTrue(all(not re.search(r"!dbg", x) for i in add for x in i["llvm"]))
        compare = next(i for i in self.instructions(13) if "icmp" in " ".join(i["llvm"]))
        self.assertIn("icmp slt i64", " ".join(compare["llvm"]))

    def test_a_line_counts_its_runtime_calls(self):
        self.assertEqual(annotate_ir.summary(self.lines[9])[0], 2)  # (pys_str_int and pys_str_cat)
        self.assertIn("A", annotate_ir.summary(self.lines[9])[1])
        self.assertEqual(annotate_ir.summary(self.lines[5])[0], 1)  # (pys_raise, where the add overflows)
        self.assertEqual(annotate_ir.summary(self.lines[13])[0], 0)
        self.assertGreaterEqual(annotate_ir.summary(self.lines[16])[0], 3)

    def test_a_def_line_holds_its_function_and_slots(self):
        functions = [fn for fn, item in self.lines[4] if item["kind"] == "function"]
        self.assertEqual([fn["symbol"] for fn in functions], ["@f.add"])
        self.assertTrue(functions[0]["define"].startswith("define internal i64 @f.add("))
        self.assertTrue(any("alloca" in x for x in functions[0]["prologue"]))
        self.assertEqual(len(functions[0]["slots"]), 2)

    def test_only_the_programs_own_file_is_annotated(self):
        symbols = {fn["symbol"] for fn in self.records["functions"]}
        self.assertIn("@main.init", symbols)
        self.assertFalse(any("twice" in s for s in symbols), symbols)

    def test_text_shows_every_source_line_in_order(self):
        text = annotate_ir.render_text(self.records)
        numbered = [line for line in text.splitlines() if re.match(r"\s*\d+ \|", line)]
        self.assertEqual([int(line.split("|")[0]) for line in numbered], list(range(1, PROGRAM.count("\n") + 1)))
        self.assertIn("@llvm.sadd.with.overflow.i64", text)
        self.assertIn("; 2 runtime calls; A", text)

    def test_html_is_one_self_contained_page(self):
        page = annotate_ir.render_html(self.records)
        self.assertNotRegex(page, r"(src|href)=\"?https?:")
        self.assertEqual(page.count("<details"), page.count("</details>"))
        self.assertIn("return x &lt; y", page)
        self.assertIn('class="ln heat2"', page)
        for line in PROGRAM.splitlines():
            if line:
                self.assertIn(annotate_ir.html.escape(line), page)


class CommandTests(unittest.TestCase):
    def test_command_writes_records_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.py"
            path.write_text("def f(x: int) -> int:\n    return x + 1\n\n\nprint(f(1))\n")
            page, records = Path(directory) / "out.html", Path(directory) / "out.json"
            done = subprocess.run([sys.executable, str(ROOT / "tools/annotate_ir.py"), str(path), "--html", str(page),
                                   "--json", str(records)], capture_output=True, text=True, timeout=600)
            self.assertEqual((done.returncode, done.stdout), (0, ""), done.stderr)
            self.assertIn("@f.f", [fn["symbol"] for fn in json.loads(records.read_text())["functions"]])
            self.assertTrue(page.read_text().startswith("<!doctype html>"))
            path.write_text("def f(x: int) -> int:\n    return x + 'a'\n")
            done = subprocess.run([sys.executable, str(ROOT / "tools/annotate_ir.py"), str(path)],
                                  capture_output=True, text=True, timeout=600)
            self.assertEqual((done.returncode, done.stdout), (1, ""))
            self.assertIn("annotate_ir:", done.stderr)


if __name__ == "__main__":
    unittest.main()
