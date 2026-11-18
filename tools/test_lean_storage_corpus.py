"""Storage-proof selection and accounting must fail closed independently of Lean."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_corpus as traversal
import check_lean_storage_corpus as corpus
from src.pystachy_compiler.diagnostics import int_pragma


class StorageCorpusTests(unittest.TestCase):
    def test_selection_follows_imported_int_mode_and_path_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "helpers"
            helper.mkdir()
            (helper / "large.py").write_text("# pystachy: python-int\nx = 2 ** 80\n")
            program = root / "case.py"
            program.write_text("from large import x\nprint(x)\n")
            program.with_suffix(".path").write_text(str(helper))
            self.assertEqual(corpus.select([str(program)]), [str(program)])
            program.write_text("print(1)\n")
            self.assertEqual(corpus.select([str(program)]), [])

    def test_selector_uses_compiler_pragma_recognizer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program = root / "case.py"
            for data in (b"# pystachy: python-int\nprint(1)\n",
                         b"\xef\xbb\xbf# pystachy: python-int\nprint(1)\n",
                         b"# mention # pystachy: python-int\nprint(1)\n"):
                with self.subTest(data=data):
                    program.write_bytes(data)
                    self.assertEqual(traversal.Reach(pragma=int_pragma).dynamic(program, [root]),
                                     int_pragma(data.decode("latin-1")))

    def test_failed_functions_and_vanished_inventory_cannot_pass(self):
        good = {"program": "good.py", "status": "accepted",
                "totals": {"obligations": 4, "proved_obligations": 4,
                           "stack_copy_reads": 6, "stack_copy_obligations": 2}}
        bad = {"program": "bad.py", "status": "unsupported",
               "totals": {"obligations": 2, "proved_obligations": 0}}
        report = corpus.summarize([good, bad], 0)
        self.assertEqual(report["status"], "unsupported")
        self.assertEqual(report["totals"]["obligations"], 6)
        self.assertEqual(report["totals"]["proved_obligations"], 4)
        self.assertEqual(report["totals"]["failed_programs"], 1)
        self.assertEqual(report["totals"]["stack_copy_reads"], 6)
        self.assertEqual(report["totals"]["stack_copy_obligations"], 2)
        self.assertEqual(corpus.summarize([], 0)["status"], "error")
        self.assertEqual(corpus.summarize([{"program": "empty.py", "status": "accepted"}], 0)["status"],
                         "unsupported")

    def test_incomplete_proof_accounting_cannot_report_acceptance(self):
        for totals in ({"obligations": 4, "proved_obligations": 3},
                       {"obligations": 4, "proved_obligations": 4, "unclassified_functions": 1}):
            with self.subTest(totals=totals):
                report = corpus.summarize([{"program": "case.py", "status": "accepted", "totals": totals}], 0)
                self.assertEqual(report["status"], "error")

    def test_current_selection_includes_import_only_boundaries(self):
        selected = corpus.select()
        self.assertIn("tests/programs/numbers/python_int_lists.py", selected)
        self.assertIn("tests/programs/numbers/python_int_import.py", selected)
        self.assertNotIn("tests/programs/strings/bom.py", selected)
        self.assertEqual(selected, sorted(set(selected), key=lambda name: name.encode()))

    def test_shipped_decimal_enrolls_only_the_programs_that_import_it(self):
        # lib/decimal.py opts in to promoting ints. statistics, which random names in its
        # self-test, loads it in CPython only: a program that imports random or statistics
        # compiles no decimal code, and must not join this corpus through them.
        selected = corpus.select()
        self.assertIn("tests/programs/library/lib_decimal.py", selected)
        self.assertEqual([name for name in selected if "/lib_statistics" in name or "/lib_random" in name], [])


@unittest.skipUnless(corpus.storage.DEFAULT_CHECKER.is_file() and
                     corpus.storage.arithmetic.DEFAULT_CHECKER.is_file(), "build the Lean checkers")
class StorageCorpusRunTests(unittest.TestCase):
    def run_program(self, source):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        program, report = root / "case.py", root / "report.json"
        program.write_text(source)
        completed = subprocess.run(
            [sys.executable, str(corpus.ROOT / "tools/check_lean_storage_corpus.py"),
             "--jobs", "2", "--timeout", "60", "--report", str(report), str(program)],
            cwd=corpus.ROOT, capture_output=True, text=True, timeout=90)
        return completed, json.loads(report.read_text())

    def test_report_retains_accepted_function_candidates(self):
        completed, report = self.run_program(
            "# pystachy: python-int\ndef increment(x: int) -> int:\n    return x + 1\n\n"
            "print(increment(2 ** 80))\n")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(report["status"], "accepted")
        record = report["programs"][0]
        self.assertRegex(record["snapshot_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(record["totals"]["obligations"], 0)
        self.assertEqual(len(record["functions"]), record["totals"]["obligation_functions"])
        self.assertIn("@f.increment", {fn["function"] for fn in record["functions"]})
        for fn in record["functions"]:
            self.assertEqual(fn["status"], "accepted")
            self.assertTrue(fn["normalization_complete"])
            self.assertRegex(fn["candidate_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(len(fn["candidate_sha256s"]), fn["proof_batches"])
            for digest in fn["candidate_sha256s"]:
                self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(record["failures"], [])

    def test_failed_inspection_cannot_report_acceptance(self):
        completed, report = self.run_program("# pystachy: python-int\ndef broken(:\n")
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["totals"]["failed_programs"], 1)
        self.assertEqual(report["programs"][0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
