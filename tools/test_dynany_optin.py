"""Fail-closed controls for the maintained dynamic Any opt-in sweep."""
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dynany_optin as sweep


class SourceTests(unittest.TestCase):
    def test_pragma_header_bytes(self):
        for source in (b"print(1)\n", b"\xef\xbb\xbfprint(1)\n", b"# coding: latin-1\nprint('\xe9')\n",
                       b"#!/usr/bin/python\n# coding=latin-1\nprint('\xe9')\n", b"# coding: utf-8",
                       b"# coding: latin-1\rprint('\xe9')\r", b"# pystachy: dynamic-any\rprint(1)\r",
                       b"print('# pystachy: dynamic-any')\n"):
            with self.subTest(source=source):
                result = sweep.opt_in(source)
                self.assertIn(sweep.PRAGMA, result)
                self.assertIn(sweep.PRAGMA.strip(), [line.strip() for line in result.removeprefix(b"\xef\xbb\xbf").split(b"\n")])
                self.assertEqual(sweep.opt_in(result), result)
                compile(result, "case.py", "exec")
        self.assertTrue(sweep.opt_in(b"\xef\xbb\xbfprint(1)\n").startswith(b"\xef\xbb\xbf"))
        self.assertEqual(sweep.opt_in(b"# coding: latin-1\nprint('\xe9')\n").splitlines()[0], b"# coding: latin-1")
        self.assertEqual(sweep.opt_in(b"#!/usr/bin/python\n# coding=latin-1\nprint('\xe9')\n").splitlines()[1], b"# coding=latin-1")

    def test_existing_pragma_does_not_move_source(self):
        for source in (sweep.PRAGMA + b"print(1)\n", b"\xef\xbb\xbf\n  " + sweep.PRAGMA + b"pass\n"):
            self.assertEqual(sweep.opt_in(source), source)

    def test_overlay_preserves_fixtures_sidecars_and_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "original"
            root.mkdir()
            case = root / "tests/programs/a/hello.py"
            case.parent.mkdir(parents=True)
            case.write_bytes(b"print(1)\n")
            case.with_suffix(".out").write_text("1\n[exit 0]\n")
            case.with_suffix(".path").write_text("tests/helpers\n")
            helpers = root / "tests/helpers"
            helpers.mkdir()
            (helpers / "fixture.py").write_text("value = 3\n")
            (helpers / "dangling").symlink_to("missing")
            (helpers / "loop1").symlink_to("loop2")
            (helpers / "loop2").symlink_to("loop1")
            (root / "examples").mkdir()
            (root / "examples/notice.txt").write_text("hello")
            target = Path(tmp) / "overlay"
            sweep.prepare_tree(root, target, ["tests/programs/a/hello.py"])
            self.assertEqual(case.read_bytes(), b"print(1)\n")
            self.assertEqual((target / "tests/programs/a/hello.py").read_bytes(), sweep.PRAGMA + case.read_bytes())
            self.assertEqual((target / "tests/programs/a/hello.path").read_text(), "tests/helpers\n")
            self.assertTrue((target / "tests/helpers/dangling").is_symlink())
            self.assertTrue((target / "tests/helpers/loop1").is_symlink())
            self.assertEqual((target / "examples/notice.txt").read_text(), "hello")

    def test_selected_symlink_cannot_modify_original_or_external_files(self):
        for external in (True, False):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "original"
                case = root / "tests/programs/a/main.py"
                case.parent.mkdir(parents=True)
                source = Path(tmp) / "outside.py" if external else root / "tests/helper.py"
                source.write_bytes(b"print(1)\n")
                case.symlink_to(source if external else "../../helper.py")
                target = Path(tmp) / "overlay"
                if external:
                    with self.assertRaisesRegex(ValueError, "symlink leaves"):
                        sweep.prepare_tree(root, target, ["tests/programs/a/main.py"])
                else:
                    sweep.prepare_tree(root, target, ["tests/programs/a/main.py"])
                    self.assertEqual((target / "tests/helper.py").read_bytes(), sweep.PRAGMA + b"print(1)\n")
                self.assertEqual(source.read_bytes(), b"print(1)\n")


class HarnessTests(unittest.TestCase):
    case = "tests/programs/a/sample.py"

    def test_exact_success_and_syntax_count(self):
        self.assertEqual(sweep.harness_result(0, "selected 1 cases\n1 passed, 0 failed\n", self.case), (True, ""))
        self.assertEqual(sweep.harness_result(0, "selected 1 cases\n2 passed, 0 failed\n", "tests/programs/a/syntax_ok.py"), (True, ""))
        for status, output in ((1, "selected 1 cases\n1 passed, 0 failed\n"),
                               (0, "selected 0 cases\n0 passed, 0 failed\n"),
                               (0, "1 passed, 0 failed\n"),
                               (0, "selected 1 cases\n1 passed, 0 failed\nextra\n")):
            self.assertFalse(sweep.harness_result(status, output, self.case)[0])

    def test_failure_signature_requires_complete_single_case_report(self):
        diagnostic = self.case + ":2: error: incompatible types"
        output = f"FAIL sample (jit)\n  stderr:\n{diagnostic}\nselected 1 cases\n0 passed, 1 failed\n"
        self.assertEqual(sweep.harness_result(1, output, self.case), (False, diagnostic))
        for changed in (output.replace("selected 1 cases\n", ""),
                        output.replace("selected 1", "selected 2"),
                        output.replace("FAIL sample", "FAIL other"),
                        "FAIL extra (jit)\n" + output,
                        output.replace(diagnostic, diagnostic + "\n" + diagnostic),
                        output + "extra\n"):
            self.assertNotEqual(sweep.harness_result(1, changed, self.case)[1], diagnostic)

    def test_exact_exceptions_and_obsolete_pass(self):
        exception = {"diagnostic": "tests/programs/a/sample.py:2: error: exact error"}
        self.assertEqual(sweep.classify(False, "tests/programs/a/sample.py:2: error: exact error", exception, b"1\n"), "expected-failure")
        self.assertEqual(sweep.classify(False, "tests/programs/a/sample.py:2: error: exact error plus another", exception), "fail")
        self.assertEqual(sweep.classify(True, "", exception), "fail")
        self.assertEqual(sweep.classify(False, "tests/programs/a/sample.py:2: error: exact error", None), "fail")
        self.assertEqual(sweep.classify(True, "", None), "pass")
        for malformed in ("harness exit 124: timeout", "incomplete output", "a.py:0: error: bad",
                          "a.py:1: error: bad\nextra"):
            self.assertEqual(sweep.classify(False, malformed, {"diagnostic": malformed}), "fail")

    def test_rejection_wrapper_rejects_crashes_extra_output_and_duplicate_calls(self):
        diagnostic = self.case + ":2: error: incompatible types"
        exception = {"diagnostic": diagnostic}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mode in ("jit", "aot"):
                action = "run" if mode == "jit" else "build"
                for status, extra in ((1, ""), (139, ""), (0, ""), (1, "extra output")):
                    compiler = root / "fake-compiler.sh"
                    compiler.write_text("#!/bin/sh\nprintf '%s\\n' '" + diagnostic + "' >&2\n" +
                                        ("printf '%s\\n' '" + extra + "'\n" if extra else "") + f"exit {status}\n")
                    command, trace = sweep.rejection_wrapper("sh " + str(compiler), self.case, mode, root)
                    actual_status, _ = sweep.run(command.split() + [action, self.case], root, os.environ, 5)
                    self.assertEqual(actual_status, status)
                    result = sweep.classify(False, diagnostic, exception, sweep.rejection_status(trace, diagnostic))
                    self.assertEqual(result, "expected-failure" if status == 1 and not extra else "fail")
                    if status == 1 and not extra:
                        sweep.run(command.split() + [action, self.case], root, os.environ, 5)
                        self.assertEqual(sweep.classify(False, diagnostic, exception,
                                                       sweep.rejection_status(trace, diagnostic)), "fail")

    def test_environment_cannot_disable_ir_or_gc_and_shares_only_private_cache(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {
                "PYSTACHY_GC": "off", "PYSTACHY_IRCHECK": "0", "PYSTACHY_PATH": "bad",
                "PYSTACHY_GC_STRESS": "99", "PYTHONPATH": "bad", "PYSTACHY_CACHE": "/bad",
                "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "LC_CTYPE": "C.UTF-8"}):
            a = sweep.environment(Path(tmp), Path(tmp) / "a")
            b = sweep.environment(Path(tmp), Path(tmp) / "b")
            self.assertEqual(a["PYSTACHY_CACHE"], b["PYSTACHY_CACHE"])
            self.assertNotEqual(a["TMPDIR"], b["TMPDIR"])
            self.assertEqual(a["PYSTACHY_IRCHECK"], "1")
            self.assertEqual(a["PYSTACHY_GC_STRESS_PROGRAM"], "0")
            for key in ("LANG", "LC_ALL", "LC_CTYPE"):
                self.assertEqual(a[key], "C.UTF-8")
            for key in ("PYSTACHY_GC", "PYSTACHY_PATH", "PYSTACHY_GC_STRESS", "PYTHONPATH"):
                self.assertNotIn(key, a)

    def test_timeout_terminates_descendants(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "escaped"
            code = "import pathlib,time;time.sleep(.5);pathlib.Path(" + repr(str(marker)) + ").touch()"
            parent = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c'," + repr(code) + "]);time.sleep(30)"
            status, output = sweep.run([sys.executable, "-c", parent], Path(tmp), os.environ, .1)
            self.assertEqual(status, 124)
            self.assertTrue(output.startswith("timeout after"))
            time.sleep(.6)
            self.assertFalse(marker.exists())

    def test_foreground_sigint_is_delivered(self):
        code = "import os,signal;os.kill(os.getpid(),signal.SIGINT)"
        with tempfile.TemporaryDirectory() as tmp:
            status, output = sweep.run([sys.executable, "-c", code], Path(tmp), os.environ, 5)
        self.assertEqual(status, -signal.SIGINT)
        self.assertIn("KeyboardInterrupt", output)

    def test_fresh_recording_accepts_unfinished_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = "tests/programs/runtime/rt_print_partial.py"
            output = "rt_print_partial: total: [exit 1] AttributeError: boom\n"
            path = (root / case).with_suffix(".out")
            path.parent.mkdir(parents=True)
            self.assertFalse(sweep.recorded(0, output, case, root))
            path.write_bytes(b"total: [exit 1]\n")
            self.assertTrue(sweep.recorded(0, output, case, root))
            self.assertFalse(sweep.recorded(1, output, case, root))
            self.assertFalse(sweep.recorded(0, "other: [exit 0]\n", case, root))
            for malformed in (b"total: ", b"total: [exit 1]", b"total: [exit 1]\nextra\n"):
                path.write_bytes(malformed)
                self.assertFalse(sweep.recorded(0, output, case, root))

    def test_success_without_creating_new_recording_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recording = (root / self.case).with_suffix(".out")
            recording.parent.mkdir(parents=True)
            recording.write_text("old output\n[exit 0]\n")
            with mock.patch.object(sweep, "run", return_value=(0, "sample: [exit 0]\n")) as run:
                result = sweep.one(self.case, root, root, root, "compiler", ["jit"], 5, {})
            self.assertFalse(result["oracle"])
            self.assertFalse(recording.exists())
            self.assertEqual(run.call_count, 1)

    def test_baseline_failure_never_uses_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = self.case
            diagnostic = case + ":2: error: mismatch"
            failure = f"FAIL sample (jit)\n{diagnostic}\nselected 1 cases\n0 passed, 1 failed\n"
            recording = (root / case).with_suffix(".out")
            recording.parent.mkdir(parents=True)
            def mocked_run(command, *_args):
                if command[1] == "tests/record.sh":
                    recording.write_text("[exit 0]\n")
                    return 0, "sample: [exit 0]\n"
                return 1, failure
            with mock.patch.object(sweep, "run", side_effect=mocked_run):
                result = sweep.one(case, root, root, root, "compiler", ["jit"], 5,
                                   {(case, "jit"): {"diagnostic": diagnostic}})
            self.assertEqual(result["results"][0]["result"], "fail")
            self.assertIn("baseline also fails", result["results"][0]["diagnostic"])

    def test_oracle_failure_does_not_run_compiler(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sweep, "run", return_value=(124, "timeout")) as run:
            result = sweep.one(self.case, Path(tmp), Path(tmp), Path(tmp), "compiler", ["jit"], 5, {})
            self.assertFalse(result["oracle"])
            self.assertEqual(result["results"], [])
            self.assertEqual(run.call_count, 1)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        (self.root / "tests/programs/a").mkdir(parents=True)
        (self.root / "tests/corpus.sh").write_text("corpus() { for f in tests/programs/*/*.py; do printf '%s\\n' \"$f\"; done; }\n")
        self.paths = [f"tests/programs/a/case{i}.py" for i in range(4)]
        for path in self.paths:
            (self.root / path).write_text("print(1)\n")
            (self.root / path).with_suffix(".out").write_text("1\n[exit 0]\n")
        self.manifest = self.root / sweep.MANIFEST
        self.manifest.write_text('{"schema":1,"exceptions":[]}\n')
        selected = self.paths[1::2]
        self.report = {"schema": 1, "corpus_cases": 4, "corpus_sha256": sweep.corpus_digest(self.root, self.paths),
                       "exceptions_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
                       "shard_index": 1, "shard_count": 2, "modes": ["jit", "aot"], "cases": selected, "subset": False,
                       "oracle_cases": 2, "expected_checks": 4, "completed_checks": 4, "passed_checks": 4,
                       "expected_failures": 0, "failures": [], "results": [
                           {"case": case, "mode": mode, "result": "pass", "diagnostic": ""}
                           for case in selected for mode in sweep.MODES]}

    def test_complete_report(self):
        sweep.validate_report(self.report, self.root)
        self.assertEqual(sweep.programs(self.root), self.paths)
        self.assertEqual(sum(len(self.paths[i::3]) for i in range(3)), 4)

    def test_partial_duplicate_stale_and_false_success_reports_fail(self):
        mutations = [lambda r: r.update(cases=r["cases"][:-1]),
                     lambda r: r.update(results=r["results"][:-1]),
                     lambda r: r["results"].__setitem__(1, r["results"][0]),
                     lambda r: r["results"][0].update(result="fail"),
                     lambda r: r["results"][0].update(diagnostic="hidden failure"),
                     lambda r: r.update(oracle_cases=1), lambda r: r.update(completed_checks=3),
                     lambda r: r.update(expected_checks=3), lambda r: r.update(passed_checks=3),
                     lambda r: r.update(expected_failures=1), lambda r: r.update(failures=["failure"]),
                     lambda r: r.update(modes=["jit"]), lambda r: r.update(subset=True),
                     lambda r: r.update(corpus_sha256="0" * 64), lambda r: r.update(exceptions_sha256="0" * 64),
                     lambda r: r.update(shard_index=2), lambda r: r.update(shard_count=0)]
        for mutate in mutations:
            report = copy.deepcopy(self.report)
            mutate(report)
            with self.subTest(report=report), self.assertRaises(ValueError):
                sweep.validate_report(report, self.root)
        for key in ("schema", "shard_index", "shard_count", "corpus_cases", "oracle_cases", "expected_checks",
                    "completed_checks", "passed_checks", "expected_failures"):
            report = copy.deepcopy(self.report)
            report[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                sweep.validate_report(report, self.root)

    def test_inputs_changed_during_execution_fail(self):
        digest = self.report["corpus_sha256"]
        manifest_digest = self.report["exceptions_sha256"]
        sweep.check_inputs(self.root, self.paths, digest, manifest_digest)
        (self.root / self.paths[0]).write_text("print(2)\n")
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            sweep.check_inputs(self.root, self.paths, digest, manifest_digest)
        (self.root / self.paths[0]).write_text("print(1)\n")
        self.manifest.write_text('{"schema":1,"exceptions":[]}\n\n')
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            sweep.check_inputs(self.root, self.paths, digest, manifest_digest)

    def test_changed_source_sidecar_or_added_case_invalidates_report(self):
        for suffix in (".py", ".out", ".err", ".in", ".full", ".path"):
            path = (self.root / self.paths[0]).with_suffix(suffix)
            original = path.read_bytes() if path.exists() else None
            path.write_bytes(b"changed")
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                sweep.validate_report(self.report, self.root)
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)
        (self.root / "tests/programs/a/new.py").write_text("pass\n")
        (self.root / "tests/programs/a/new.out").write_text("[exit 0]\n")
        with self.assertRaises(ValueError):
            sweep.validate_report(self.report, self.root)

    def test_manifest_and_reports_reject_duplicate_keys(self):
        self.manifest.write_text('{"schema":1,"schema":1,"exceptions":[]}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            sweep.exceptions(self.root, self.paths)

    def test_stale_duplicate_and_malformed_exceptions(self):
        entry = {"case": self.paths[1], "mode": "jit", "diagnostic": "tests/programs/a/sample.py:2: error: exact error",
                 "reason": "tracked opt-in rejection", "issue": "https://github.com/den-run-ai/pystachy/issues/782"}
        for entries in ([{**entry, "case": "missing.py"}], [entry, entry], [{**entry, "mode": "wrong"}],
                        [{**entry, "diagnostic": ""}], [{**entry, "issue": "https://example.com/1"}],
                        [{**entry, "diagnostic": "harness exit 124: timeout"}]):
            self.manifest.write_text(json.dumps({"schema": 1, "exceptions": entries}))
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                sweep.exceptions(self.root, self.paths)

    def test_exact_exception_and_unexpected_pass(self):
        entry = {"case": self.paths[1], "mode": "jit", "diagnostic": "tests/programs/a/sample.py:2: error: exact error",
                 "reason": "tracked opt-in rejection", "issue": "https://github.com/den-run-ai/pystachy/issues/782"}
        self.manifest.write_text(json.dumps({"schema": 1, "exceptions": [entry]}))
        report = self.report
        report["exceptions_sha256"] = hashlib.sha256(self.manifest.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            sweep.validate_report(report, self.root)
        report["passed_checks"], report["expected_failures"] = 3, 1
        report["results"][0].update(result="expected-failure", diagnostic="tests/programs/a/sample.py:2: error: exact error")
        sweep.validate_report(report, self.root)
        report["results"][0]["diagnostic"] += " changed"
        with self.assertRaises(ValueError):
            sweep.validate_report(report, self.root)

    def test_empty_corpus_and_missing_recording_fail(self):
        (self.root / self.paths[0]).with_suffix(".out").unlink()
        with self.assertRaises(ValueError):
            sweep.programs(self.root)
        for path in self.paths:
            (self.root / path).unlink()
        with self.assertRaises(ValueError):
            sweep.programs(self.root)


if __name__ == "__main__":
    unittest.main()
