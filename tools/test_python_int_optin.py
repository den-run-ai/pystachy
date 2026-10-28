"""Controls for the python-int opt-in corpus sweep (tools/python_int_optin.py)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dynany_optin
import python_int_optin as sweep

A = "tests/programs/x/a.py"
B = "tests/programs/x/b.py"


class SourceTests(unittest.TestCase):
    def test_pragma_header_bytes(self):
        for source in (b"print(1)\n", b"\xef\xbb\xbfprint(1)\n", b"# coding: latin-1\nprint('\xe9')\n",
                       b"#!/usr/bin/python\n# coding=latin-1\nprint('\xe9')\n", b"# pystachy: dynamic-any\nprint(1)\n"):
            with self.subTest(source=source):
                result = dynany_optin.opt_in(source, sweep.PRAGMA)
                lines = [line.strip() for line in result.removeprefix(b"\xef\xbb\xbf").split(b"\n")]
                self.assertIn(sweep.PRAGMA.strip(), lines)
                self.assertEqual(dynany_optin.opt_in(result, sweep.PRAGMA), result)
                compile(result, "case.py", "exec")
        # (dynamic Any's comment is another, which stays; the dynamic Any sweep's is unchanged)
        self.assertEqual(dynany_optin.opt_in(b"# pystachy: dynamic-any\nprint(1)\n", sweep.PRAGMA),
                         sweep.PRAGMA + b"# pystachy: dynamic-any\nprint(1)\n")
        self.assertEqual(dynany_optin.opt_in(sweep.PRAGMA + b"pass\n", sweep.PRAGMA), sweep.PRAGMA + b"pass\n")
        self.assertEqual(dynany_optin.opt_in(b"print(1)\n"), dynany_optin.PRAGMA + b"print(1)\n")

    def test_overlay_gives_only_selected_cases_the_pragma(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "original"
            for case in (A, B):
                (root / case).parent.mkdir(parents=True, exist_ok=True)
                (root / case).write_bytes(b"print(1)\n")
            target = Path(tmp) / "overlay"
            dynany_optin.prepare_tree(root, target, [A], sweep.PRAGMA)
            self.assertEqual((target / A).read_bytes(), sweep.PRAGMA + b"print(1)\n")
            self.assertEqual((target / B).read_bytes(), b"print(1)\n")
            self.assertEqual((root / A).read_bytes(), b"print(1)\n")


class OracleTests(unittest.TestCase):
    def test_version_warning_is_no_failure_only_with_any_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            overlay = Path(tmp)
            (overlay / A).parent.mkdir(parents=True)
            (overlay / A).with_suffix(".out").write_bytes(b"1\n[exit 0]\n")
            warned = "tests/record.sh: warning: python3 is CPython 3.13.17, not 3.13.16 (.python-version)\na: [exit 0] \n"
            self.assertFalse(dynany_optin.recorded(0, warned, A, overlay))
            self.assertTrue(sweep.unwarned(0, warned, A, overlay))
            self.assertFalse(sweep.unwarned(1, warned, A, overlay))
            self.assertFalse(sweep.unwarned(0, "tests/record.sh: error: no CPython\na: [exit 0] \n", A, overlay))

    def test_python_version(self):
        self.assertTrue(sweep.python_ok("3.13.16", "3.13.16", False))
        self.assertFalse(sweep.python_ok("3.13.17", "3.13.16", False))
        self.assertTrue(sweep.python_ok("3.13.17", "3.13.16", True))
        self.assertFalse(sweep.python_ok("3.12.9", "3.13.16", True))


class ReportTests(unittest.TestCase):
    def test_rows_give_each_mode_of_a_failed_oracle(self):
        cases = [{"case": A, "oracle": True, "results": [
                     {"case": A, "mode": "jit", "result": "pass", "diagnostic": ""},
                     {"case": A, "mode": "aot", "result": "fail", "diagnostic": "a.py:1: error: no"}]},
                 {"case": B, "oracle": False, "results": [], "failure": "b.py: oracle exit 1"}]
        rows = sweep.rows(cases, ["jit", "aot"])
        self.assertEqual([(r["case"], r["mode"], r["result"]) for r in rows],
                         [(A, "jit", "pass"), (A, "aot", "fail"), (B, "jit", "oracle"), (B, "aot", "oracle")])
        self.assertEqual(rows[2]["diagnostic"], "b.py: oracle exit 1")
        self.assertEqual(sweep.checks({"schema": 1, "results": rows})[(B, "aot")], "oracle")

    def test_malformed_and_duplicate_rows_are_rejected(self):
        row = {"case": A, "mode": "jit", "result": "pass", "diagnostic": ""}
        for report in ({"schema": 2, "results": [row]}, {"schema": 1}, {"schema": 1, "results": [row, row]},
                       {"schema": 1, "results": [{**row, "mode": "interp"}]},
                       {"schema": 1, "results": [{**row, "result": "ok"}]}, []):
            with self.subTest(report=report), self.assertRaises(ValueError):
                sweep.checks(report)

    def test_compare(self):
        base = {("a", "jit"): "pass", ("b", "jit"): "fail", ("c", "jit"): "pass", ("d", "jit"): "pass"}
        new = {("a", "jit"): "fail", ("b", "jit"): "pass", ("c", "jit"): "pass", ("e", "jit"): "fail"}
        self.assertEqual(sweep.compare(base, new), ([("a", "jit")], [("b", "jit")], [("d", "jit")]))
        # (an oracle that no longer records a passing check is a regression too)
        self.assertEqual(sweep.compare({("a", "jit"): "pass"}, {("a", "jit"): "oracle"})[0], [("a", "jit")])


class MainTests(unittest.TestCase):
    def run_main(self, tmp, results, base=None, corpus=None, extra=()):
        # main over a corpus of two cases whose JIT results are given, without a compiler
        report = Path(tmp) / "report.json"
        args = ["--report", str(report), "--compiler", "true", "--modes", "jit", *extra]
        if base is not None:
            (Path(tmp) / "base.json").write_text(json.dumps({"schema": 1, "results": [
                {"case": case, "mode": "jit", "result": result, "diagnostic": ""} for case, result in base.items()]}))
            args += ["--compare", str(Path(tmp) / "base.json")]

        def one(case, root, overlay, temp, compiler, modes, timeout, allowed, oracle):
            self.assertEqual((allowed, modes, oracle), ({}, ["jit"], dynany_optin.recorded))
            return {"case": case, "oracle": True,
                    "results": [{"case": case, "mode": "jit", "result": results[case], "diagnostic": ""}]}
        with mock.patch.object(sweep.optin, "programs", side_effect=corpus or [[A, B], [A, B]]), \
             mock.patch.object(sweep.optin, "corpus_digest", return_value="digest"), \
             mock.patch.object(sweep.optin, "prepare_tree") as prepare, \
             mock.patch.object(sweep.optin, "run", return_value=(0, "")), \
             mock.patch.object(sweep.optin, "one", side_effect=one), \
             mock.patch.object(sweep, "python_ok", return_value=True), \
             mock.patch("sys.stdout"):
            status = sweep.main(args)
        self.assertEqual(prepare.call_args.args[3], sweep.PRAGMA)
        return status, json.loads(report.read_text())

    def test_report_counts_every_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, report = self.run_main(tmp, {A: "pass", B: "fail"})
        self.assertEqual(status, 0)
        self.assertEqual((report["checks"], report["passed_checks"], report["failed_checks"]), (2, 1, 1))
        self.assertEqual((report["pragma"], report["cases"], report["subset"]), ("# pystachy: python-int", [A, B], False))

    def test_compare_fails_only_on_a_check_that_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_main(tmp, {A: "fail", B: "pass"}, base={A: "pass", B: "fail"})[0], 1)
            self.assertEqual(self.run_main(tmp, {A: "pass", B: "pass"}, base={A: "fail", B: "pass"})[0], 0)
            self.assertEqual(self.run_main(tmp, {A: "fail", B: "fail"}, base={A: "fail"})[0], 0)

    def test_subset_and_corpus_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, report = self.run_main(tmp, {B: "pass"}, extra=["--cases", B])
            self.assertEqual((status, report["cases"], report["subset"]), (0, [B], True))
            self.assertEqual(self.run_main(tmp, {A: "pass", B: "pass"}, corpus=[[A, B], [A]])[0], 1)
            with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                self.run_main(tmp, {}, extra=["--cases", "tests/programs/x/c.py"])

    def test_invalid_settings(self):
        for extra in (["--jobs", "0"], ["--timeout", "0"], ["--modes", "jit", "jit"]):
            with self.subTest(extra=extra), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                sweep.main(["--report", "r.json", *extra])


if __name__ == "__main__":
    unittest.main()
