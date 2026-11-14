"""The example CLI smoke gate must fail on missing work and byte-level differences."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import check_example_cli as cli
import merge_verification as merge


def passed_report():
    return {"schema": 1, "result": "pass", "python": (cli.ROOT / ".python-version").read_text().strip(),
            "modes": list(cli.MODES), "cases": cli.case_names(), "integrations": copy.deepcopy(cli.integrations())}


class SmokeTests(unittest.TestCase):
    def test_real_cpython_oracles_exercise_every_entry_point(self):
        self.assertEqual(set(cli.CASES), {"csvstat", "latency", "mailmerge", "topk", "urlstats", "route"})
        self.assertEqual(len(cli.case_names()), 24)
        self.assertEqual(len(set(cli.case_names())), 24)
        replay = cli.integrations()["json_repair_replay"]
        self.assertEqual(replay, {"cases": 962, "modes": ["jit", "aot"]})
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = cli.fixtures(directory)
            env = cli.environment(directory / "cache")
            for example, cases in cli.CASES.items():
                source = cli.ROOT / "examples" / example / (example + ".py")
                for case in cases:
                    with self.subTest(example=example, case=case.name):
                        result = cli.run(example + "/" + case.name, [sys.executable, str(source), *case.args],
                                         env, directory, status=case.status)
                        self.assertTrue(result.stdout if case.status == 0 else result.stderr)
                        self.assertEqual({path.name: path.read_bytes() for path in directory.iterdir()}, original)
            # Success diagnostics must also be compared, rather than discarded by a stdout-only check.
            result = cli.run("mailmerge/substitute", [sys.executable, str(cli.ROOT / "examples/mailmerge/mailmerge.py"),
                                                     "notice.txt", "people.tsv"], env, directory)
            self.assertEqual(result.stderr, b"mailmerge: 2 messages\n")

    def test_environment_keeps_only_llvm_from_inherited_compiler_options(self):
        dirty = {"PYSTACHY_LLVM": "/llvm", "PYSTACHY_PATH": "/foreign", "PYSTACHY_HOME": "/foreign",
                 "PYSTACHY_GC_STRESS": "1", "PYSTACHY_JOBS": "99", "PYTHONPATH": "/foreign",
                 "PYTHONOPTIMIZE": "2", "PATH": "/bin"}
        with mock.patch.dict(os.environ, dirty, clear=True):
            env = cli.environment(Path("/cache"))
            self.assertEqual(dict(os.environ), dirty)
        self.assertEqual(env["PYSTACHY_LLVM"], "/llvm")
        self.assertEqual(env["PYSTACHY_HOME"], str(cli.ROOT))
        self.assertEqual(env["PYSTACHY_CACHE"], "/cache")
        self.assertEqual(env["PYSTACHY_JOBS"], "2")
        for key in ("PYSTACHY_PATH", "PYSTACHY_GC_STRESS", "PYTHONPATH", "PYTHONOPTIMIZE"):
            self.assertNotIn(key, env)

    def test_runner_keeps_both_byte_streams_and_requires_expected_status(self):
        command = [sys.executable, "-c", "import os; os.write(1, b'\\xff\\n'); os.write(2, b'diagnostic\\n'); exit(2)"]
        result = cli.run("usage/cpython", command, os.environ.copy(), cli.ROOT, status=2)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (2, b"\xff\n", b"diagnostic\n"))
        with self.assertRaises(RuntimeError) as caught:
            cli.run("usage/jit", command, os.environ.copy(), cli.ROOT)
        for required in ("usage/jit", "timeout=120s", "exit=2", "expected exit=0", "stdout=b'", "stderr=b'diagnostic"):
            self.assertIn(required, str(caught.exception))
        # status=None returns any exit status to the caller, e.g. a checker whose report it inspects.
        result = cli.run("replay/check", command, os.environ.copy(), cli.ROOT, status=None)
        self.assertEqual((result.returncode, result.stdout), (2, b"\xff\n"))

    def test_timeout_terminates_owned_grandchildren_and_retains_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "escaped-child"
            child = "import pathlib,sys,time; time.sleep(2); pathlib.Path(sys.argv[1]).touch()"
            script = ("import subprocess,sys,time; "
                      f"subprocess.Popen([sys.executable, '-c', {child!r}, sys.argv[1]]); "
                      "print('started', flush=True); print('pending', file=sys.stderr, flush=True); time.sleep(30)")
            with self.assertRaises(RuntimeError) as caught:
                cli.run("topk/heap/aot", [sys.executable, "-c", script, str(marker)], os.environ.copy(),
                        cli.ROOT, timeout=0.2)
            for required in ("topk/heap/aot", "timeout=0.2s", "exit=timeout", "started", "pending"):
                self.assertIn(required, str(caught.exception))
            # communicate waits for the child's inherited pipe too: killing only its parent would
            # return after the child survived long enough to create this file.
            self.assertFalse(marker.exists())

    def test_oracle_comparison_is_exact_for_status_stdout_and_stderr(self):
        reference = subprocess.CompletedProcess(["cpython"], 0, b"one\n", b"count: 1\n")
        for status, stdout, stderr in ((0, b"one", b"count: 1\n"), (0, b"one\nextra\n", b"count: 1\n"),
                                       (0, b"one\n", b""), (1, b"one\n", b"count: 1\n")):
            with self.subTest(status=status, stdout=stdout, stderr=stderr), self.assertRaisesRegex(ValueError, "mailmerge/substitute/aot"):
                cli.compare("mailmerge/substitute/aot", subprocess.CompletedProcess(["exe"], status, stdout, stderr), reference)
        cli.compare("same", reference, reference)

    def test_build_requires_fresh_executable_and_no_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "source.py"
            for stdout, stderr in ((b"", b""), (b"unexpected", b""), (b"", b"warning")):
                with self.subTest(stdout=stdout, stderr=stderr), mock.patch.object(cli, "run", return_value=
                        subprocess.CompletedProcess(["compiler", "build"], 0, stdout, stderr)):
                    with self.assertRaisesRegex(ValueError, "topk/build"):
                        cli.build("topk", source, Path("compiler"), directory, {})
                (directory / "topk").touch(mode=0o755)

    def test_report_is_replaced_before_failure_and_cannot_retain_old_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text(json.dumps(passed_report()))

            def fail(*args):
                self.assertEqual(json.loads(path.read_text())["result"], "running")
                raise RuntimeError("csvstat/table/aot: wrong output")

            with mock.patch.object(cli, "check", side_effect=fail), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["--json", str(path)]), 1)
            report = json.loads(path.read_text())
            self.assertEqual(report["result"], "fail")
            self.assertEqual(report["cases"], [])
            self.assertIn("csvstat/table/aot", report["error"])

    def test_json_repair_replay_fails_closed_on_any_unmatched_case(self):
        count = cli.integrations()["json_repair_replay"]["cases"]
        passed = f"{count}/{count} match; 0 problems\n".encode()

        def fake_run(mode, checker_stdout, replay_stderr):
            # Every command succeeds except the given mode's replay or check.
            def run(label, command, env, cwd, status=0, timeout=120):
                if label.endswith("/check"):
                    failed = label == f"json_repair/replay/{mode}/check"
                    return subprocess.CompletedProcess(command, int(failed), checker_stdout if failed else passed, b"")
                err = replay_stderr if label == f"json_repair/replay/{mode}" else b""
                return subprocess.CompletedProcess(command, 0, b"{}\n", err)
            return run

        for mode, checker_stdout, replay_stderr in (
                ("jit", f"{count - 1}/{count} match; 1 problems\n".encode(), b""),
                ("aot", passed, b"warning\n")):
            report = {"python": "3.13.16", "integrations": {}}
            with tempfile.TemporaryDirectory() as temporary, \
                    mock.patch.object(cli, "run", fake_run(mode, checker_stdout, replay_stderr)), \
                    mock.patch.object(cli, "build", lambda *args: "exe"):
                with self.subTest(mode=mode), self.assertRaises(ValueError) as caught:
                    cli.replay_json_repair(Path("pystachy"), {}, Path(temporary), report)
            self.assertIn(f"json_repair/replay/{mode}", str(caught.exception))
            self.assertNotIn(mode, report["integrations"]["json_repair_replay"]["modes"])

    def test_report_and_aggregate_reject_missing_modes_cases_and_integrations(self):
        valid = passed_report()
        cli.validate_report(valid)
        mutations = [lambda r: r.update(schema=True), lambda r: r.update(result="running"),
                     lambda r: r.update(python="3.12.0"), lambda r: r.update(modes=["jit", "aot"]),
                     lambda r: r["cases"].pop(), lambda r: r["cases"].append(r["cases"][0]),
                     lambda r: r.update(cases=[]), lambda r: r.pop("integrations"),
                     lambda r: r["integrations"].update(json_repair=0),
                     lambda r: r["integrations"].update(json_repair=20.0),
                     lambda r: r["integrations"]["agent_http"].pop(), lambda r: r.update(error="skipped"),
                     lambda r: r["integrations"].pop("json_repair_replay"),
                     lambda r: r["integrations"]["json_repair_replay"]["modes"].pop(),
                     lambda r: r["integrations"]["json_repair_replay"].update(cases=961),
                     lambda r: r["integrations"]["json_repair_replay"].update(cases=962.0)]
        for mutate in mutations:
            data = copy.deepcopy(valid)
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                cli.validate_report(data)
            # The final merge must check the nested evidence even when the step claims success.
            aggregate = {"project": "Pystachy", "group": "benchmarks", "result": "pass",
                         "summary": {"steps": 2, "passed": 2, "failed": 0, "seconds": 0},
                         "steps": [{"name": "bootstrap", "result": "pass", "seconds": 0},
                                   {"name": "example-cli", "result": "pass", "seconds": 0, "example_cli": data}]}
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, "example-cli"):
                merge.validate_report(aggregate, "benchmarks", ["bootstrap", "example-cli"])


if __name__ == "__main__":
    unittest.main()
